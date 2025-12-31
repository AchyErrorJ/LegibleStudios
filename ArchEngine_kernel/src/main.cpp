#include "window.hpp"
#include "vulkan_context.hpp"
#include "renderer.hpp"
#include "physics_bridge.hpp"
#include "wall_system.hpp"
#include "geometry_loader.hpp"
#include "imgui_layer.hpp"
#include "mesh.hpp"
#include "qbd_interface.hpp"
#include "ipc_server.hpp"
#include <iostream>
#include <algorithm>
#include <chrono>
#include <fstream>
#include <filesystem>

using namespace arch;

// Ray-box intersection for element picking
bool rayBoxIntersect(vec3 rayOrigin, vec3 rayDir, vec3 boxMin, vec3 boxMax, float& tMin) {
    vec3 invDir = 1.0f / rayDir;
    vec3 t1 = (boxMin - rayOrigin) * invDir;
    vec3 t2 = (boxMax - rayOrigin) * invDir;
    vec3 tMinV = glm::min(t1, t2);
    vec3 tMaxV = glm::max(t1, t2);
    float tEnter = glm::max(glm::max(tMinV.x, tMinV.y), tMinV.z);
    float tExit = glm::min(glm::min(tMaxV.x, tMaxV.y), tMaxV.z);
    if (tEnter > tExit || tExit < 0) return false;
    tMin = tEnter > 0 ? tEnter : tExit;
    return true;
}

// Ray-plane intersection for ground plane picking (Y = planeY)
bool rayPlaneIntersect(vec3 rayOrigin, vec3 rayDir, float planeY, vec3& hitPoint) {
    // Plane normal is (0, 1, 0)
    if (std::abs(rayDir.y) < 0.0001f) return false;  // Ray parallel to plane
    float t = (planeY - rayOrigin.y) / rayDir.y;
    if (t < 0) return false;  // Plane behind ray
    hitPoint = rayOrigin + rayDir * t;
    return true;
}

// Get element bounding box
void getElementBounds(const StructuralElement& elem, vec3& minB, vec3& maxB) {
    // If element has custom mesh, use mesh bounds
    if (elem.mesh.hasData()) {
        minB = vec3(1e9f);
        maxB = vec3(-1e9f);
        for (const auto& v : elem.mesh.vertices) {
            minB = glm::min(minB, v);
            maxB = glm::max(maxB, v);
        }
        // Add small padding for easier selection
        minB -= vec3(0.5f);
        maxB += vec3(0.5f);
        return;
    }

    minB = glm::min(elem.start, elem.end);
    maxB = glm::max(elem.start, elem.end);
    // Expand by width/depth
    float hw = elem.width / 2.0f;
    float hd = elem.depth / 2.0f;
    minB -= vec3(hw, 0, hd);
    maxB += vec3(hw, 0, hd);
}

// ============================================================================
// QBD END-TO-END TEST
// ============================================================================
bool runQBDTest(const std::string& jsonPath, const std::string& outputDir) {
    std::cout << "\n========================================\n";
    std::cout << "QBD END-TO-END TEST\n";
    std::cout << "========================================\n";

    // Step 1: Load QBD JSON
    std::cout << "\n[1] Loading QBD JSON: " << jsonPath << "\n";
    auto& qbd = qbd::getQBDInterface();
    auto layoutOpt = qbd.loadFromFile(jsonPath);

    if (!layoutOpt.has_value()) {
        std::cerr << "ERROR: Failed to load QBD JSON\n";
        return false;
    }

    auto& layout = layoutOpt.value();
    std::cout << "    SUCCESS: Loaded layout\n";
    std::cout << "    - Dimensions: " << layout.width << " x " << layout.depth << " ft\n";
    std::cout << "    - Square footage: " << layout.sqft << " sqft\n";
    std::cout << "    - Walls: " << layout.walls.size() << "\n";
    std::cout << "    - Doors: " << layout.doors.size() << "\n";
    std::cout << "    - Rooms: " << layout.rooms.size() << "\n";

    // Step 2: Run OBC Validation
    std::cout << "\n[2] Running OBC Validation (Zone 6)...\n";
    auto validation = qbd.validateLayout(layout, "Zone 6");

    std::cout << "    Overall Pass: " << (validation.overallPass ? "YES" : "NO") << "\n";
    std::cout << "    Walls Checked: " << validation.wallsChecked << "\n";
    std::cout << "    Walls Passed: " << validation.wallsPassed << "\n";
    std::cout << "    Walls Failed: " << validation.wallsFailed << "\n";
    std::cout << "    Thermal Compliance: " << (validation.thermalCompliance ? "YES" : "NO") << "\n";
    std::cout << "    Average R-Value: " << validation.averageRValue << "\n";
    std::cout << "    Exterior Wall Area: " << validation.totalExteriorWallArea << " sqft\n";

    // Print wall reports
    std::cout << "\n    Wall Reports:\n";
    for (const auto& report : validation.wallReports) {
        std::cout << "      - " << (report.passes() ? "[PASS]" : "[FAIL]") << " "
                  << report.elementType << " (" << report.elementId << ")\n";
        for (const auto& check : report.checks) {
            if (check.status != obc::ComplianceStatus::Pass) {
                std::cout << "        " << check.ruleName << ": " << check.message << "\n";
            }
        }
    }

    // Step 3: Generate Documentation
    std::cout << "\n[3] Generating Documentation...\n";
    auto docs = qbd.generateDocumentation(layout, "QBD Test Project");

    std::cout << "    Floor Plan: " << docs.floorPlan.lines.size() << " lines, "
              << docs.floorPlan.arcs.size() << " arcs\n";
    std::cout << "    Wall Details: " << docs.wallDetails.size() << "\n";

    // Step 4: Export to files
    std::cout << "\n[4] Exporting to: " << outputDir << "\n";

    // Create output directory if needed
    std::filesystem::create_directories(outputDir);

    // Export floor plan SVG
    std::string svgPath = outputDir + "/floor_plan.svg";
    auto& slicerEngine = slicer::getSlicer();
    std::string svg = slicerEngine.exportToSVG(docs.floorPlan, 0.1f);  // 0.1 pixels per mm = 100 pixels per meter

    std::ofstream svgFile(svgPath);
    if (svgFile.is_open()) {
        svgFile << svg;
        svgFile.close();
        std::cout << "    Wrote: " << svgPath << " (" << svg.size() << " bytes)\n";
    } else {
        std::cerr << "    ERROR: Could not write " << svgPath << "\n";
    }

    // Export floor plan DXF
    std::string dxfPath = outputDir + "/floor_plan.dxf";
    std::string dxf = slicerEngine.exportToDXF(docs.floorPlan);

    std::ofstream dxfFile(dxfPath);
    if (dxfFile.is_open()) {
        dxfFile << dxf;
        dxfFile.close();
        std::cout << "    Wrote: " << dxfPath << " (" << dxf.size() << " bytes)\n";
    } else {
        std::cerr << "    ERROR: Could not write " << dxfPath << "\n";
    }

    // Write validation report
    std::string reportPath = outputDir + "/validation_report.txt";
    std::ofstream reportFile(reportPath);
    if (reportFile.is_open()) {
        reportFile << "QBD VALIDATION REPORT\n";
        reportFile << "=====================\n\n";
        reportFile << "Project: QBD Test Project\n";
        reportFile << "Generated: " << docs.generatedDate << "\n\n";
        reportFile << "LAYOUT SUMMARY\n";
        reportFile << "--------------\n";
        reportFile << "Dimensions: " << layout.width << " x " << layout.depth << " ft\n";
        reportFile << "Square Footage: " << layout.sqft << " sqft\n";
        reportFile << "Walls: " << layout.summary.totalWalls << " (Ext: " << layout.summary.exteriorWalls
                   << ", Int: " << layout.summary.interiorWalls << ", Wet: " << layout.summary.wetWalls << ")\n";
        reportFile << "Doors: " << layout.summary.doors << "\n";
        reportFile << "Rooms: " << layout.summary.roomsPlaced << "/" << layout.summary.roomsRequested << " placed\n\n";
        reportFile << "OBC COMPLIANCE (Zone 6)\n";
        reportFile << "-----------------------\n";
        reportFile << "Overall: " << (validation.overallPass ? "PASS" : "FAIL") << "\n";
        reportFile << "Thermal: " << (validation.thermalCompliance ? "PASS" : "FAIL") << "\n";
        reportFile << "Avg R-Value: " << validation.averageRValue << "\n\n";
        reportFile << "WALL DETAILS\n";
        reportFile << "------------\n";
        for (const auto& report : validation.wallReports) {
            reportFile << (report.passes() ? "[PASS] " : "[FAIL] ")
                       << report.elementType << " (" << report.elementId << ")\n";
            for (const auto& check : report.checks) {
                reportFile << "  " << check.ruleName << " [" << check.codeSection << "]: "
                           << (check.status == obc::ComplianceStatus::Pass ? "PASS" : "FAIL")
                           << " - " << check.message << "\n";
            }
        }
        reportFile.close();
        std::cout << "    Wrote: " << reportPath << "\n";
    }

    // Step 5: Convert to Building for visualization
    std::cout << "\n[5] Converting to Building...\n";
    Building building = qbd.toBuilding(layout);
    std::cout << "    Elements: " << building.elements.size() << "\n";
    std::cout << "    Parametric Walls: " << building.parametricWalls.size() << "\n";

    std::cout << "\n========================================\n";
    std::cout << "QBD TEST COMPLETE\n";
    std::cout << "========================================\n\n";

    return validation.overallPass;
}

int main(int argc, char* argv[]) {
    // Check for --qbd-test argument
    bool runTest = false;
    std::string testJsonPath = "../Shared/TestData/sample_qbd_output.json";
    std::string testOutputDir = "../Shared/TestData/output";

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--qbd-test") {
            runTest = true;
        } else if (arg == "--qbd-json" && i + 1 < argc) {
            testJsonPath = argv[++i];
        } else if (arg == "--qbd-output" && i + 1 < argc) {
            testOutputDir = argv[++i];
        }
    }

    if (runTest) {
        bool success = runQBDTest(testJsonPath, testOutputDir);
        return success ? 0 : 1;
    }

    try {
        // Create window
        WindowConfig windowConfig{};
        windowConfig.width = 1600;
        windowConfig.height = 900;
        windowConfig.title = "ArchEngine - Multi-Physics Visualizer";
        windowConfig.resizable = true;

        Window window(windowConfig);

        // Initialize Vulkan
        VulkanConfig vulkanConfig{};
        vulkanConfig.enableValidation = true;
        vulkanConfig.enableDebugMarkers = true;
        vulkanConfig.maxFramesInFlight = 2;

        VulkanContext context(window, vulkanConfig);

        // Create renderer
        Renderer renderer(context);

        // Initialize physics bridge
        PhysicsBridge physics;
        if (physics.isAvailable()) {
            std::cout << "Physics engine connected\n";
        } else {
            std::cout << "Running without physics engine\n";
        }

        // Initialize IPC server for CAD app sync
        IPCServer ipcServer;
        bool ipcBuildingDirty = false;
        std::string ipcBuildingJson;
        std::mutex ipcMutex;

        ipcServer.onBuildingData = [&](const std::string& json) {
            std::lock_guard<std::mutex> lock(ipcMutex);
            ipcBuildingJson = json;
            ipcBuildingDirty = true;
            std::cout << "[IPC] Building data received (" << json.size() << " bytes)\n";
        };

        ipcServer.onClientConnected = [](bool connected) {
            std::cout << "[IPC] CAD app " << (connected ? "connected" : "disconnected") << "\n";
        };

        if (ipcServer.start("ArchEngine_Kernel")) {
            std::cout << "[IPC] Server listening on \\\\.\\pipe\\ArchEngine_Kernel\n";
        } else {
            std::cout << "[IPC] Failed to start server - CAD sync disabled\n";
        }

        // Create ImGui layer
        ImGuiLayer imgui(context, window.getHandle(), renderer.getRenderPass());

        // Load sample buildings
        std::vector<Building> buildings = {
            GeometryLoader::createSimpleFrame(40.0f, 30.0f, 12.0f),
            GeometryLoader::createMultiStoryFrame(3, 60.0f, 40.0f, 12.0f),
            GeometryLoader::createWarehouse(100.0f, 80.0f, 30.0f),
            GeometryLoader::createResidential(40.0f, 30.0f, 2)
        };

        // Try to load QBD JSON from generated_building.json
        {
            auto& qbd = qbd::getQBDInterface();
            // Try multiple paths - works from build/, build/Release/, or build/Debug/
            std::vector<std::string> jsonPaths = {
                "../../Shared/TestData/output/generated_building.json",  // From build/Release/ or build/Debug/
                "../Shared/TestData/output/generated_building.json",     // From build/
                "X:/ARCH/Software/ArchEngine_Suite/Shared/TestData/output/generated_building.json"  // Absolute path
            };

            std::optional<qbd::QBDLayout> layoutOpt;
            std::string usedPath;
            for (const auto& path : jsonPaths) {
                layoutOpt = qbd.loadFromFile(path);
                if (layoutOpt.has_value()) {
                    usedPath = path;
                    break;
                }
            }

            if (layoutOpt.has_value()) {
                Building qbdBuilding = qbd.toBuilding(*layoutOpt);
                qbdBuilding.name = "QBD Generated House";

                // Scale from mm to visualization units (mm / 1000 = meters, then * 3.28 = feet approx)
                // For now, scale down by 304.8 to convert mm to feet (1 foot = 304.8 mm)
                const float mmToFeet = 1.0f / 304.8f;
                for (auto& elem : qbdBuilding.elements) {
                    elem.start *= mmToFeet;
                    elem.end *= mmToFeet;
                    elem.width *= mmToFeet;
                    elem.depth *= mmToFeet;

                    // Scale mesh vertices if present
                    for (auto& v : elem.mesh.vertices) {
                        v *= mmToFeet;
                    }
                }

                buildings.push_back(qbdBuilding);
                std::cout << "[Main] Loaded QBD building from " << usedPath << " with " << qbdBuilding.elements.size() << " elements\n";
            } else {
                std::cout << "[Main] No QBD JSON found. Tried paths:\n";
                for (const auto& p : jsonPaths) {
                    std::cout << "  - " << p << "\n";
                }
                std::cout << "[Main] Using sample buildings only\n";
            }
        }

        size_t currentBuilding = 0;
        VisualizationMode vizMode = VisualizationMode::Structural;
        FrameAnalysis lastAnalysis{};
        bool showDemo = false;
        bool showMetrics = false;
        bool showHelp = false;
        bool showGeometryEditor = true;  // Show by default
        // Selection is now stored in imgui.getSelectedElements()

        // Camera setup
        Camera camera;
        camera.position = {30.0f, 20.0f, 50.0f};
        camera.target = {20.0f, 6.0f, 15.0f};
        camera.up = {0.0f, 1.0f, 0.0f};
        camera.fov = 45.0f;
        camera.nearPlane = 0.1f;
        camera.farPlane = 500.0f;

        // Camera control state
        f32 cameraDistance = 60.0f;
        f32 cameraYaw = 0.5f;
        f32 cameraPitch = 0.4f;
        vec3 cameraFocus = {20.0f, 10.0f, 15.0f};
        bool isDragging = false;
        // Element selection cycling state
        std::vector<std::pair<int, float>> hitCandidates;  // (element index, distance)
        size_t hitCycleIndex = 0;
        f64 lastMouseX = 0, lastMouseY = 0;

        // Reset camera to fit current building
        auto resetCamera = [&]() {
            auto& elements = buildings[currentBuilding].elements;
            if (elements.empty()) return;

            vec3 minBound(1e9f), maxBound(-1e9f);
            for (const auto& elem : elements) {
                minBound = glm::min(minBound, glm::min(elem.start, elem.end));
                maxBound = glm::max(maxBound, glm::max(elem.start, elem.end));
            }
            cameraFocus = (minBound + maxBound) * 0.5f;
            f32 size = glm::length(maxBound - minBound);
            cameraDistance = size * 1.5f;
            cameraYaw = 0.5f;
            cameraPitch = 0.4f;
        };

        resetCamera();

        std::cout << "\n=== ArchEngine Started ===\n";
        std::cout << "Building: " << buildings[currentBuilding].name << "\n";
        std::cout << "Press H for help\n\n";

        // Set up input callbacks
        window.setScrollCallback([&](f64 xoffset, f64 yoffset) {
            (void)xoffset;
            if (imgui.wantCaptureMouse()) return;  // ImGui is using mouse
            cameraDistance -= static_cast<f32>(yoffset) * cameraDistance * 0.1f;
            cameraDistance = glm::clamp(cameraDistance, 10.0f, 500.0f);
        });

        window.setMouseButtonCallback([&](i32 button, i32 action, i32 mods) {
            (void)mods;
            if (imgui.wantCaptureMouse()) return;  // ImGui is using mouse

            // Left click for element selection
            if (button == GLFW_MOUSE_BUTTON_LEFT && action == GLFW_PRESS) {
                f64 mouseX, mouseY;
                window.getCursorPos(mouseX, mouseY);

                // Get window size
                auto [winWidth, winHeight] = window.getWindowSize();

                // Convert to NDC
                float ndcX = (2.0f * static_cast<float>(mouseX) / static_cast<float>(winWidth)) - 1.0f;
                float ndcY = 1.0f - (2.0f * static_cast<float>(mouseY) / static_cast<float>(winHeight));

                // Get inverse view-projection matrix
                float aspect = static_cast<float>(winWidth) / static_cast<float>(winHeight);
                mat4 proj = camera.getProjectionMatrix(aspect);
                mat4 view = camera.getViewMatrix();
                mat4 invVP = glm::inverse(proj * view);

                // Create ray from camera
                vec4 nearPoint = invVP * vec4(ndcX, ndcY, -1.0f, 1.0f);
                vec4 farPoint = invVP * vec4(ndcX, ndcY, 1.0f, 1.0f);
                nearPoint /= nearPoint.w;
                farPoint /= farPoint.w;

                vec3 rayOrigin = vec3(nearPoint);
                vec3 rayDir = glm::normalize(vec3(farPoint) - vec3(nearPoint));

                // Handle drawing mode - click to place points on ground plane
                if (imgui.isDrawing()) {
                    vec3 hitPoint;
                    if (rayPlaneIntersect(rayOrigin, rayDir, 0.0f, hitPoint)) {
                        // Snap to grid (1ft grid)
                        hitPoint.x = std::round(hitPoint.x);
                        hitPoint.z = std::round(hitPoint.z);
                        hitPoint.y = 0.0f;

                        imgui.addDrawPoint(hitPoint);
                        std::cout << "Draw point: (" << hitPoint.x << ", " << hitPoint.y << ", " << hitPoint.z << ")" << std::endl;

                        // Check if wall drawing is complete (2 points)
                        if (imgui.isWallDrawComplete()) {
                            const auto& points = imgui.getDrawPoints();
                            auto& newElem = imgui.getNewElement();
                            auto& building = buildings[currentBuilding];

                            // Create parametric wall from the two clicked points
                            ParametricWall wall;
                            wall.startPoint = vec2(points[0].x, points[0].z);
                            wall.endPoint = vec2(points[1].x, points[1].z);
                            wall.baseHeight = 0.0f;
                            wall.topHeight = newElem.wallHeight;
                            wall.wallTypeIndex = newElem.wallTypeIndex;

                            // Ensure wall types exist
                            while (building.wallTypes.size() <= static_cast<size_t>(wall.wallTypeIndex)) {
                                if (building.wallTypes.size() == 0)
                                    building.wallTypes.push_back(createExterior2x6Wall());
                                else if (building.wallTypes.size() == 1)
                                    building.wallTypes.push_back(createExterior2x4Wall());
                                else
                                    building.wallTypes.push_back(createInteriorWall());
                            }

                            building.parametricWalls.push_back(wall);

                            // Regenerate wall geometry
                            building.wallCorners = WallSystem::detectCorners(building.parametricWalls);
                            WallSystem::processCorners(building.parametricWalls, building.wallTypes, building.wallCorners);
                            auto wallElements = WallSystem::toStructuralElements(building.parametricWalls, building.wallTypes);

                            // Remove existing parametric wall elements
                            building.elements.erase(
                                std::remove_if(building.elements.begin(), building.elements.end(),
                                    [](const StructuralElement& e) {
                                        return e.type == ElementType::Wall && e.mesh.hasData();
                                    }),
                                building.elements.end());

                            // Add new wall elements
                            for (auto& elem : wallElements) {
                                building.elements.push_back(elem);
                            }

                            std::cout << "Created parametric wall: " << building.wallTypes[wall.wallTypeIndex].name << std::endl;
                            std::cout << "  From (" << points[0].x << ", " << points[0].z << ") to ("
                                      << points[1].x << ", " << points[1].z << ")" << std::endl;

                            // Exit drawing mode
                            imgui.setDrawMode(DrawMode::None);
                        }
                    }
                    return;  // Don't do normal selection when drawing
                }

                // Test intersection with all elements - collect ALL hits for cycling
                hitCandidates.clear();
                hitCycleIndex = 0;
                auto& elements = buildings[currentBuilding].elements;
                for (size_t i = 0; i < elements.size(); i++) {
                    vec3 minB, maxB;
                    getElementBounds(elements[i], minB, maxB);
                    float t;
                    if (rayBoxIntersect(rayOrigin, rayDir, minB, maxB, t)) {
                        hitCandidates.push_back({static_cast<int>(i), t});
                    }
                }

                // Sort by distance (closest first)
                std::sort(hitCandidates.begin(), hitCandidates.end(),
                    [](const auto& a, const auto& b) { return a.second < b.second; });

                // Handle selection based on Ctrl key
                bool ctrlHeld = glfwGetKey(window.getHandle(), GLFW_KEY_LEFT_CONTROL) == GLFW_PRESS ||
                               glfwGetKey(window.getHandle(), GLFW_KEY_RIGHT_CONTROL) == GLFW_PRESS;

                if (!hitCandidates.empty()) {
                    int selectedIdx = hitCandidates[0].first;
                    auto& elem = elements[selectedIdx];
                    const char* typeNames[] = {"Beam", "Column", "Floor", "Wall", "Foundation", "Connection", "Door", "Window", "Roof"};

                    if (ctrlHeld) {
                        // Ctrl+click: toggle selection
                        if (imgui.isSelected(selectedIdx)) {
                            imgui.removeFromSelection(selectedIdx);
                            std::cout << "Removed from selection: " << typeNames[static_cast<int>(elem.type)] << " #" << selectedIdx << std::endl;
                        } else {
                            imgui.addToSelection(selectedIdx);
                            std::cout << "Added to selection: " << typeNames[static_cast<int>(elem.type)] << " #" << selectedIdx << std::endl;
                        }
                    } else {
                        // Regular click: replace selection
                        imgui.setSelection(selectedIdx);
                        std::cout << "Selected: " << typeNames[static_cast<int>(elem.type)] << " #" << selectedIdx;
                        if (hitCandidates.size() > 1) {
                            std::cout << " (1/" << hitCandidates.size() << " - press Tab to cycle)";
                        }
                        std::cout << std::endl;
                    }

                    // Special handling for walls and roofs
                    if (elem.type == ElementType::Wall) {
                        imgui.setSelectedWallByElementIndex(selectedIdx);
                    }
                    if (elem.type == ElementType::Roof) {
                        imgui.setSelectedRoofIndex(selectedIdx);
                        std::cout << "Roof selected for gable constraint" << std::endl;
                    }
                } else {
                    if (!ctrlHeld) {
                        imgui.clearSelection();
                        std::cout << "Selection cleared" << std::endl;
                    }
                }
                std::cout << "Total selected: " << imgui.getSelectedElements().size() << std::endl;
            }

            if (button == GLFW_MOUSE_BUTTON_MIDDLE || button == GLFW_MOUSE_BUTTON_RIGHT) {
                isDragging = (action == GLFW_PRESS);
                if (isDragging) {
                    window.getCursorPos(lastMouseX, lastMouseY);
                }
            }
        });

        window.setCursorPosCallback([&](f64 xpos, f64 ypos) {
            if (imgui.wantCaptureMouse()) return;  // ImGui is using mouse
            if (isDragging) {
                f64 dx = xpos - lastMouseX;
                f64 dy = ypos - lastMouseY;
                lastMouseX = xpos;
                lastMouseY = ypos;

                cameraYaw -= static_cast<f32>(dx) * 0.005f;
                cameraPitch -= static_cast<f32>(dy) * 0.005f;
                cameraPitch = glm::clamp(cameraPitch, -1.4f, 1.4f);
            }
        });

        window.setKeyCallback([&](i32 key, i32 scancode, i32 action, i32 mods) {
            (void)scancode; (void)mods;
            if (imgui.wantCaptureKeyboard()) return;  // ImGui is using keyboard
            if (action == GLFW_PRESS || action == GLFW_REPEAT) {
                f32 moveSpeed = cameraDistance * 0.05f;
                switch (key) {
                    // Camera movement
                    case GLFW_KEY_W: cameraFocus.z -= moveSpeed; break;
                    case GLFW_KEY_S: cameraFocus.z += moveSpeed; break;
                    case GLFW_KEY_A: cameraFocus.x -= moveSpeed; break;
                    case GLFW_KEY_D: cameraFocus.x += moveSpeed; break;
                    case GLFW_KEY_Q: cameraFocus.y -= moveSpeed; break;
                    case GLFW_KEY_E: cameraFocus.y += moveSpeed; break;

                    // Visualization modes
                    case GLFW_KEY_1:
                        vizMode = VisualizationMode::Structural;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Structural (stress)\n";
                        break;
                    case GLFW_KEY_2:
                        vizMode = VisualizationMode::Thermal;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Thermal (temperature)\n";
                        break;
                    case GLFW_KEY_3:
                        vizMode = VisualizationMode::Lighting;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Lighting (daylight/lux)\n";
                        break;
                    case GLFW_KEY_4:
                        vizMode = VisualizationMode::Acoustic;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Acoustic (RT60)\n";
                        break;
                    case GLFW_KEY_5:
                        vizMode = VisualizationMode::Material;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Material types\n";
                        break;
                    case GLFW_KEY_6:
                        vizMode = VisualizationMode::Wireframe;
                        renderer.setVisualizationMode(vizMode);
                        std::cout << "Mode: Wireframe" << std::endl;
                        break;

                    // Building selection
                    case GLFW_KEY_LEFT_BRACKET:
                    case GLFW_KEY_COMMA:
                        currentBuilding = (currentBuilding + buildings.size() - 1) % buildings.size();
                        std::cout << "Building: " << buildings[currentBuilding].name << "\n";
                        resetCamera();
                        break;
                    case GLFW_KEY_RIGHT_BRACKET:
                    case GLFW_KEY_PERIOD:
                        currentBuilding = (currentBuilding + 1) % buildings.size();
                        std::cout << "Building: " << buildings[currentBuilding].name << "\n";
                        resetCamera();
                        break;

                    // Run physics analysis
                    case GLFW_KEY_P:
                        if (physics.isAvailable()) {
                            std::cout << "Running physics analysis...\n";
                            lastAnalysis = physics.analyzeFrame(buildings[currentBuilding].elements);
                            std::cout << "Analysis complete.\n";
                            std::cout << "  All pass: " << (lastAnalysis.allPass ? "YES" : "NO") << "\n";
                            std::cout << "  Max beam utilization: " << (lastAnalysis.maxBeamUtilization * 100) << "%\n";
                            std::cout << "  Max column utilization: " << (lastAnalysis.maxColumnUtilization * 100) << "%\n";

                            // Update stress values from analysis
                            buildings[currentBuilding].elements =
                                physics.convertToRenderElements(lastAnalysis, buildings[currentBuilding].elements);
                            std::cout << "Stress values updated.\n";
                        } else {
                            std::cout << "Physics engine not available\n";
                        }
                        break;

                    // Reset camera
                    // Cycle through overlapping elements
                    case GLFW_KEY_TAB:
                        if (!hitCandidates.empty()) {
                            hitCycleIndex = (hitCycleIndex + 1) % hitCandidates.size();
                            int selectedIdx = hitCandidates[hitCycleIndex].first;
                            auto& elem = buildings[currentBuilding].elements[selectedIdx];
                            const char* typeNames[] = {"Beam", "Column", "Floor", "Wall", "Foundation", "Connection", "Door", "Window", "Roof"};
                            
                            // Check if Ctrl is held for multi-select
                            bool ctrlHeld = glfwGetKey(window.getHandle(), GLFW_KEY_LEFT_CONTROL) == GLFW_PRESS ||
                                           glfwGetKey(window.getHandle(), GLFW_KEY_RIGHT_CONTROL) == GLFW_PRESS;
                            if (ctrlHeld) {
                                imgui.addToSelection(selectedIdx);
                                std::cout << "Added to selection: ";
                            } else {
                                imgui.setSelection(selectedIdx);
                                std::cout << "Cycled to: ";
                            }
                            std::cout << typeNames[static_cast<int>(elem.type)] << " #" << selectedIdx
                                     << " (" << (hitCycleIndex + 1) << "/" << hitCandidates.size() << ")" << std::endl;
                            
                            if (elem.type == ElementType::Wall) {
                                imgui.setSelectedWallByElementIndex(selectedIdx);
                            }
                            if (elem.type == ElementType::Roof) {
                                imgui.setSelectedRoofIndex(selectedIdx);
                            }
                        }
                        break;

                    case GLFW_KEY_R:
                        resetCamera();
                        std::cout << "Camera reset\n";
                        break;

                    // Help toggle
                    case GLFW_KEY_H:
                        showHelp = !showHelp;
                        break;

                    case GLFW_KEY_ESCAPE:
                        window.close();
                        break;
                }
            }
        });

        window.setResizeCallback([&](i32 width, i32 height) {
            (void)width; (void)height;
            renderer.onResize();
        });

        // Timing
        auto lastTime = std::chrono::high_resolution_clock::now();
        f32 deltaTime = 0.0f;
        u32 frameCount = 0;
        f32 fpsTimer = 0.0f;

        // Main loop
        while (!window.shouldClose()) {
            auto currentTime = std::chrono::high_resolution_clock::now();
            deltaTime = std::chrono::duration<f32>(currentTime - lastTime).count();
            lastTime = currentTime;

            // FPS tracking
            frameCount++;
            fpsTimer += deltaTime;
            f32 currentFps = frameCount / fpsTimer;
            if (fpsTimer >= 2.0f) {
                frameCount = 0;
                fpsTimer = 0.0f;
            }

            window.pollEvents();

            // Poll IPC server for CAD app updates
            ipcServer.poll();

            // Check if new building data was received from CAD app
            {
                std::lock_guard<std::mutex> lock(ipcMutex);
                if (ipcBuildingDirty) {
                    ipcBuildingDirty = false;
                    std::cout << "[IPC] Reloading building from CAD...\n";

                    auto& qbd = qbd::getQBDInterface();
                    auto layoutOpt = qbd.loadFromJSON(ipcBuildingJson);

                    if (layoutOpt.has_value()) {
                        Building qbdBuilding = qbd.toBuilding(*layoutOpt);
                        qbdBuilding.name = "CAD Live Sync";

                        // Scale from mm to feet
                        const float mmToFeet = 1.0f / 304.8f;
                        for (auto& elem : qbdBuilding.elements) {
                            elem.start *= mmToFeet;
                            elem.end *= mmToFeet;
                            elem.width *= mmToFeet;
                            elem.depth *= mmToFeet;
                            for (auto& v : elem.mesh.vertices) {
                                v *= mmToFeet;
                            }
                        }

                        // Add or update the live building
                        bool found = false;
                        for (size_t i = 0; i < buildings.size(); i++) {
                            if (buildings[i].name == "CAD Live Sync") {
                                buildings[i] = qbdBuilding;
                                currentBuilding = i;
                                found = true;
                                break;
                            }
                        }
                        if (!found) {
                            buildings.push_back(qbdBuilding);
                            currentBuilding = buildings.size() - 1;
                        }

                        resetCamera();
                        std::cout << "[IPC] Building updated: " << qbdBuilding.elements.size() << " elements\n";
                    } else {
                        std::cerr << "[IPC] Failed to parse building JSON\n";
                    }
                }
            }

            // Begin ImGui frame
            imgui.beginFrame();

            // Check if UI requested physics analysis
            if (imgui.wasAnalysisRequested() && physics.isAvailable()) {
                imgui.clearAnalysisRequest();
                std::cout << "Running physics analysis...\n";
                lastAnalysis = physics.analyzeFrame(buildings[currentBuilding].elements);
                std::cout << "Analysis complete.\n";
                std::cout << "  All pass: " << (lastAnalysis.allPass ? "YES" : "NO") << "\n";
                std::cout << "  Max beam utilization: " << (lastAnalysis.maxBeamUtilization * 100) << "%\n";
                std::cout << "  Max column utilization: " << (lastAnalysis.maxColumnUtilization * 100) << "%\n";
                buildings[currentBuilding].elements =
                    physics.convertToRenderElements(lastAnalysis, buildings[currentBuilding].elements);
                std::cout << "Stress values updated.\n";
            }

            // Update camera position from orbit controls (only in perspective mode)
            if (!camera.isOrthographic) {
                camera.position.x = cameraFocus.x + cameraDistance * cos(cameraPitch) * sin(cameraYaw);
                camera.position.y = cameraFocus.y + cameraDistance * sin(cameraPitch);
                camera.position.z = cameraFocus.z + cameraDistance * cos(cameraPitch) * cos(cameraYaw);
                camera.target = cameraFocus;
                camera.up = vec3(0, 1, 0);
            }

            // Render frame
            if (renderer.beginFrame()) {
                renderer.setCamera(camera);

                // Background color based on visualization mode
                vec4 clearColor;
                switch (vizMode) {
                    case VisualizationMode::Thermal:
                        clearColor = {0.02f, 0.02f, 0.05f, 1.0f};
                        break;
                    case VisualizationMode::Lighting:
                        clearColor = {0.1f, 0.1f, 0.12f, 1.0f};
                        break;
                    case VisualizationMode::Acoustic:
                        clearColor = {0.05f, 0.03f, 0.08f, 1.0f};
                        break;
                    default:
                        clearColor = {0.05f, 0.05f, 0.08f, 1.0f};
                }

                // Render shadow pass first
                renderer.renderShadowPass(buildings[currentBuilding].elements);

                // Use HDR render path for post-processing (SSAO, bloom, tonemapping)
                if (renderer.isPostProcessingEnabled()) {
                    // Render scene to HDR framebuffer
                    renderer.beginHDRRenderPass(clearColor);

                    renderer.drawSky();
                    renderer.drawGrid(150.0f, 5.0f);
                    renderer.drawStructuralFrame(buildings[currentBuilding].elements, buildings[currentBuilding], imgui.getSelectedElements());

                    renderer.endHDRRenderPass();

                    // Run post-processing passes (SSAO, bloom)
                    renderer.runPostProcessing();

                    // Composite to swapchain (leaves render pass open for ImGui)
                    renderer.beginCompositePass();
                } else {
                    // Direct rendering to swapchain (no post-processing)
                    renderer.beginRenderPass(clearColor);

                    // Draw sky background (renders behind everything)
                    renderer.drawSky();

                    // Draw reference grid
                    renderer.drawGrid(150.0f, 5.0f);

                    // Draw current building with visualization mode coloring
                    // Highlight all selected elements
                    renderer.drawStructuralFrame(buildings[currentBuilding].elements, buildings[currentBuilding], imgui.getSelectedElements());
                }

                // Draw ImGui panels
                imgui.drawMainMenuBar(vizMode, showDemo, showMetrics);
                imgui.drawBuildingPanel(buildings[currentBuilding], currentBuilding, buildings.size());
                imgui.drawPhysicsPanel(lastAnalysis, physics.isAvailable());
                imgui.drawVisualizationPanel(vizMode, renderer);
                renderer.setVisualizationMode(vizMode);  // Update renderer when UI changes mode
                imgui.drawGeometryEditor(showGeometryEditor);

                // Render settings panel (shadows, clipping)
                static bool showRenderSettings = true;
                imgui.drawRenderSettingsPanel(renderer, showRenderSettings);

                // Parametric Wall Test Panel
                static bool showWallSystem = false;
                if (ImGui::Begin("Wall System", &showWallSystem)) {
                    static bool wallsCreated = false;

                    if (!wallsCreated) {
                        ImGui::TextWrapped("Create a test room with parametric walls and proper corner connections.");
                        ImGui::Separator();

                        if (ImGui::Button("Create Test Room (20x15 ft)")) {
                            auto& building = buildings[currentBuilding];

                            // Initialize wall types if needed
                            if (building.wallTypes.empty()) {
                                building.wallTypes.push_back(createExterior2x6Wall());
                                building.wallTypes.push_back(createExterior2x4Wall());
                                building.wallTypes.push_back(createInteriorWall());
                            }

                            // Create a simple rectangular room
                            building.parametricWalls.clear();

                            // Room dimensions (feet)
                            f32 roomWidth = 20.0f;
                            f32 roomDepth = 15.0f;
                            f32 wallHeight = 10.0f;
                            f32 baseX = 5.0f, baseZ = 5.0f;  // Offset from origin

                            // North wall
                            ParametricWall north;
                            north.startPoint = vec2(baseX, baseZ);
                            north.endPoint = vec2(baseX + roomWidth, baseZ);
                            north.baseHeight = 0.0f;
                            north.topHeight = wallHeight;
                            north.wallTypeIndex = 0;  // 2x6 exterior
                            north.id = "north";
                            building.parametricWalls.push_back(north);

                            // East wall
                            ParametricWall east;
                            east.startPoint = vec2(baseX + roomWidth, baseZ);
                            east.endPoint = vec2(baseX + roomWidth, baseZ + roomDepth);
                            east.baseHeight = 0.0f;
                            east.topHeight = wallHeight;
                            east.wallTypeIndex = 0;
                            east.id = "east";
                            building.parametricWalls.push_back(east);

                            // South wall
                            ParametricWall south;
                            south.startPoint = vec2(baseX + roomWidth, baseZ + roomDepth);
                            south.endPoint = vec2(baseX, baseZ + roomDepth);
                            south.baseHeight = 0.0f;
                            south.topHeight = wallHeight;
                            south.wallTypeIndex = 0;
                            south.id = "south";
                            building.parametricWalls.push_back(south);

                            // West wall
                            ParametricWall west;
                            west.startPoint = vec2(baseX, baseZ + roomDepth);
                            west.endPoint = vec2(baseX, baseZ);
                            west.baseHeight = 0.0f;
                            west.topHeight = wallHeight;
                            west.wallTypeIndex = 0;
                            west.id = "west";
                            building.parametricWalls.push_back(west);

                            // Detect and process corners
                            building.wallCorners = WallSystem::detectCorners(building.parametricWalls);
                            WallSystem::processCorners(building.parametricWalls, building.wallTypes, building.wallCorners);

                            // Convert to structural elements for rendering
                            auto wallElements = WallSystem::toStructuralElements(building.parametricWalls, building.wallTypes);

                            // Add to building elements
                            for (auto& elem : wallElements) {
                                building.elements.push_back(elem);
                            }

                            wallsCreated = true;
                            std::cout << "Created parametric room with " << building.parametricWalls.size() << " walls, "
                                      << building.wallCorners.size() << " corners, "
                                      << wallElements.size() << " layer elements" << std::endl;
                        }
                    } else {
                        ImGui::TextColored(ImVec4(0.2f, 0.8f, 0.2f, 1.0f), "Test room created!");
                        ImGui::Text("Walls: %zu", buildings[currentBuilding].parametricWalls.size());
                        ImGui::Text("Corners: %zu", buildings[currentBuilding].wallCorners.size());
                        ImGui::Text("Wall Types:");

                        for (size_t i = 0; i < buildings[currentBuilding].wallTypes.size(); i++) {
                            const auto& type = buildings[currentBuilding].wallTypes[i];
                            ImGui::BulletText("%s (%.2f ft thick, R-%.1f)",
                                type.name.c_str(), type.getTotalThickness(), type.getTotalRValue());
                        }

                        ImGui::Separator();
                        if (ImGui::Button("Reset")) {
                            // Remove parametric wall elements
                            auto& elems = buildings[currentBuilding].elements;
                            elems.erase(
                                std::remove_if(elems.begin(), elems.end(),
                                    [](const StructuralElement& e) {
                                        return e.type == ElementType::Wall && e.mesh.hasData();
                                    }),
                                elems.end()
                            );
                            buildings[currentBuilding].parametricWalls.clear();
                            buildings[currentBuilding].wallCorners.clear();
                            wallsCreated = false;
                        }
                    }
                }
                ImGui::End();

                // Add menu item to show wall system panel
                static bool wallMenuAdded = false;
                imgui.drawWallEditor(buildings[currentBuilding], showGeometryEditor);
                imgui.drawHelpPanel(showHelp);
                imgui.drawPerformancePanel(currentFps, renderer.getStats().drawCalls, renderer.getStats().triangles);
                if (showDemo) ImGui::ShowDemoWindow(&showDemo);
                if (showMetrics) ImGui::ShowMetricsWindow(&showMetrics);

                // Handle geometry editor requests
                if (imgui.wasLoadRequested()) {
                    imgui.clearLoadRequest();
                    std::string path = imgui.getFilePath();
                    if (!path.empty()) {
                        Building newBuilding;
                        if (path.find(".ifc") != std::string::npos || path.find(".IFC") != std::string::npos) {
                            newBuilding = GeometryLoader::loadFromIFC(path);
                        } else {
                            newBuilding = GeometryLoader::loadFromJSON(path);
                        }
                        if (!newBuilding.elements.empty()) {
                            buildings.push_back(newBuilding);
                            currentBuilding = buildings.size() - 1;
                            resetCamera();
                            std::cout << "Loaded building: " << newBuilding.name << "\n";
                        }
                    }
                }
                // Handle camera view changes
                if (imgui.wasCameraViewRequested()) {
                    imgui.clearCameraViewRequest();
                    CameraView newView = imgui.getRequestedCameraView();
                    camera.view = newView;
                    
                    // Set camera position based on view
                    switch (newView) {
                        case CameraView::Perspective:
                            camera.isOrthographic = false;
                            cameraYaw = 0.5f;
                            cameraPitch = 0.4f;
                            break;
                        case CameraView::Top:
                            camera.isOrthographic = true;
                            camera.position = cameraFocus + vec3(0, cameraDistance, 0);
                            camera.target = cameraFocus;
                            camera.up = vec3(0, 0, -1);
                            camera.orthoSize = cameraDistance;
                            break;
                        case CameraView::Front:
                            camera.isOrthographic = true;
                            camera.position = cameraFocus + vec3(0, 0, cameraDistance);
                            camera.target = cameraFocus;
                            camera.up = vec3(0, 1, 0);
                            camera.orthoSize = cameraDistance;
                            break;
                        case CameraView::Right:
                            camera.isOrthographic = true;
                            camera.position = cameraFocus + vec3(cameraDistance, 0, 0);
                            camera.target = cameraFocus;
                            camera.up = vec3(0, 1, 0);
                            camera.orthoSize = cameraDistance;
                            break;
                        default:
                            break;
                    }
                    std::cout << "Camera view: " << (camera.isOrthographic ? "Orthographic" : "Perspective") << std::endl;
                }
                
                if (imgui.wasSaveRequested()) {
                    imgui.clearSaveRequest();
                    std::string path = imgui.getFilePath();
                    if (!path.empty()) {
                        GeometryLoader::saveToJSON(path, buildings[currentBuilding]);
                        std::cout << "Saved to: " << path << "\n";
                    }
                }
                if (imgui.wasAddElementRequested()) {
                    imgui.clearAddElementRequest();
                    auto& ne = imgui.getNewElement();
                    StructuralElement elem;
                    // Map UI type index to ElementType enum
                    // UI: 0=Beam, 1=Column, 2=Floor, 3=Wall, 4=Door, 5=Window, 6=Roof
                    // Enum: Beam=0, Column=1, Floor=2, Wall=3, Foundation=4, Connection=5, Door=6, Window=7, Roof=8
                    int typeMapping[] = {0, 1, 2, 3, 6, 7, 8};  // Skip Foundation(4) and Connection(5)
                    elem.type = static_cast<ElementType>(typeMapping[ne.type]);
                    elem.start = vec3(ne.start[0], ne.start[1], ne.start[2]);
                    elem.end = vec3(ne.end[0], ne.end[1], ne.end[2]);
                    elem.width = ne.width;
                    elem.depth = ne.depth;
                    const char* mats[] = {"steel", "concrete", "wood", "aluminum"};
                    elem.material = mats[ne.materialIndex];
                    elem.stress = 0.0f;
                    elem.deflection = 0.0f;
                    elem.failed = false;
                    buildings[currentBuilding].elements.push_back(elem);
                    const char* typeNames[] = {"beam", "column", "floor", "wall", "door", "window", "roof"};
                    std::cout << "Added " << typeNames[ne.type] << "\n";
                }

                // Handle wall extend request - create gable using roof geometry as constraint
                if (imgui.wasExtendWallRequested()) {
                    imgui.clearExtendWallRequest();
                    int wallIdx = imgui.getSelectedWallIndex();
                    if (wallIdx >= 0 && wallIdx < (int)buildings[currentBuilding].elements.size()) {
                        auto& wall = buildings[currentBuilding].elements[wallIdx];
                        if (wall.type == ElementType::Wall) {
                            // Store original wall height (before any gable extension)
                            // If wall already has mesh, it was already extended - use 10ft as default eave
                            float eaveHeight = wall.mesh.hasData() ? 10.0f : wall.end.y;
                            float baseHeight = wall.start.y;

                            // Clear any existing gable mesh to start fresh
                            wall.mesh.vertices.clear();
                            wall.mesh.faces.clear();

                            // Determine wall orientation
                            float xExtent = wall.end.x - wall.start.x;
                            float zExtent = wall.end.z - wall.start.z;

                            // Get selected roof index (if any)
                            int selectedRoofIdx = imgui.getSelectedRoofIndex();

                            // Helper to find roof height by interpolating along roof slope
                            auto findRoofHeightAt = [&](float targetX, float targetZ) -> float {
                                float bestHeight = eaveHeight;

                                // Collect roof vertices above eave
                                std::vector<std::pair<vec3, float>> roofPoints; // vertex, distance

                                for (size_t elemIdx = 0; elemIdx < buildings[currentBuilding].elements.size(); elemIdx++) {
                                    const auto& elem = buildings[currentBuilding].elements[elemIdx];
                                    if (elem.type != ElementType::Roof) continue;

                                    // If a specific roof is selected, only use that one
                                    if (selectedRoofIdx >= 0 && (int)elemIdx != selectedRoofIdx) continue;

                                    if (!elem.mesh.hasData()) continue;

                                    for (const auto& v : elem.mesh.vertices) {
                                        if (v.y > eaveHeight - 1.0f) {  // Include vertices slightly below eave
                                            float dx = v.x - targetX;
                                            float dz = v.z - targetZ;
                                            float dist = std::sqrt(dx*dx + dz*dz);
                                            roofPoints.push_back({v, dist});
                                        }
                                    }
                                }

                                if (roofPoints.empty()) return eaveHeight;

                                // Sort by distance
                                std::sort(roofPoints.begin(), roofPoints.end(),
                                    [](const auto& a, const auto& b) { return a.second < b.second; });

                                // Use closest point, or interpolate from nearest 2-3
                                if (roofPoints.size() >= 2 && roofPoints[0].second < 5.0f) {
                                    // Weighted average of closest points
                                    float totalWeight = 0;
                                    float weightedHeight = 0;
                                    int count = std::min(3, (int)roofPoints.size());
                                    for (int i = 0; i < count; i++) {
                                        float weight = 1.0f / (roofPoints[i].second + 0.1f);
                                        weightedHeight += roofPoints[i].first.y * weight;
                                        totalWeight += weight;
                                    }
                                    bestHeight = weightedHeight / totalWeight;
                                } else if (!roofPoints.empty()) {
                                    bestHeight = roofPoints[0].first.y;
                                }

                                // Offset to fit under roof
                                return bestHeight - 0.1f;
                            };

                            float halfThick = wall.depth / 2.0f;
                            if (halfThick < 0.1f) halfThick = 0.25f;

                            if (std::abs(xExtent) > std::abs(zExtent)) {
                                // Wall runs along X axis
                                float wallZ = (wall.start.z + wall.end.z) / 2.0f;
                                float z1 = wallZ - halfThick;
                                float z2 = wallZ + halfThick;

                                // Sample multiple points along the wall to find roof heights
                                float leftHeight = findRoofHeightAt(wall.start.x, wallZ);
                                float centerHeight = findRoofHeightAt((wall.start.x + wall.end.x) / 2.0f, wallZ);
                                float rightHeight = findRoofHeightAt(wall.end.x, wallZ);

                                // Ensure heights are at least eave height
                                leftHeight = std::max(leftHeight, eaveHeight);
                                rightHeight = std::max(rightHeight, eaveHeight);
                                centerHeight = std::max(centerHeight, std::max(leftHeight, rightHeight) + 0.1f);

                                float cx = (wall.start.x + wall.end.x) / 2.0f;

                                std::cout << "Gable: left=" << leftHeight << "ft, center=" << centerHeight << "ft, right=" << rightHeight << "ft" << std::endl;

                                // Front face vertices
                                wall.mesh.vertices.push_back(vec3(wall.start.x, baseHeight, z1));
                                wall.mesh.vertices.push_back(vec3(wall.end.x, baseHeight, z1));
                                wall.mesh.vertices.push_back(vec3(wall.end.x, rightHeight, z1));
                                wall.mesh.vertices.push_back(vec3(cx, centerHeight, z1));
                                wall.mesh.vertices.push_back(vec3(wall.start.x, leftHeight, z1));

                                // Back face vertices
                                wall.mesh.vertices.push_back(vec3(wall.start.x, baseHeight, z2));
                                wall.mesh.vertices.push_back(vec3(wall.end.x, baseHeight, z2));
                                wall.mesh.vertices.push_back(vec3(wall.end.x, rightHeight, z2));
                                wall.mesh.vertices.push_back(vec3(cx, centerHeight, z2));
                                wall.mesh.vertices.push_back(vec3(wall.start.x, leftHeight, z2));

                                // Front face
                                wall.mesh.faces.push_back({0, 1, 2});
                                wall.mesh.faces.push_back({0, 2, 4});
                                wall.mesh.faces.push_back({2, 3, 4});

                                // Back face
                                wall.mesh.faces.push_back({5, 9, 6});
                                wall.mesh.faces.push_back({6, 9, 7});
                                wall.mesh.faces.push_back({7, 9, 8});

                                // Bottom
                                wall.mesh.faces.push_back({0, 5, 6});
                                wall.mesh.faces.push_back({0, 6, 1});

                                // Left edge
                                wall.mesh.faces.push_back({0, 4, 9});
                                wall.mesh.faces.push_back({0, 9, 5});

                                // Right edge
                                wall.mesh.faces.push_back({1, 6, 7});
                                wall.mesh.faces.push_back({1, 7, 2});

                                // Top slopes
                                wall.mesh.faces.push_back({4, 3, 8});
                                wall.mesh.faces.push_back({4, 8, 9});
                                wall.mesh.faces.push_back({2, 7, 8});
                                wall.mesh.faces.push_back({2, 8, 3});

                                wall.end.y = centerHeight;

                            } else {
                                // Wall runs along Z axis
                                float wallX = (wall.start.x + wall.end.x) / 2.0f;
                                float x1 = wallX - halfThick;
                                float x2 = wallX + halfThick;

                                float startHeight = findRoofHeightAt(wallX, wall.start.z);
                                float centerHeight = findRoofHeightAt(wallX, (wall.start.z + wall.end.z) / 2.0f);
                                float endHeight = findRoofHeightAt(wallX, wall.end.z);

                                startHeight = std::max(startHeight, eaveHeight);
                                endHeight = std::max(endHeight, eaveHeight);
                                centerHeight = std::max(centerHeight, std::max(startHeight, endHeight) + 0.1f);

                                float cz = (wall.start.z + wall.end.z) / 2.0f;

                                std::cout << "Gable: start=" << startHeight << "ft, center=" << centerHeight << "ft, end=" << endHeight << "ft" << std::endl;

                                wall.mesh.vertices.push_back(vec3(x1, baseHeight, wall.start.z));
                                wall.mesh.vertices.push_back(vec3(x1, baseHeight, wall.end.z));
                                wall.mesh.vertices.push_back(vec3(x1, endHeight, wall.end.z));
                                wall.mesh.vertices.push_back(vec3(x1, centerHeight, cz));
                                wall.mesh.vertices.push_back(vec3(x1, startHeight, wall.start.z));

                                wall.mesh.vertices.push_back(vec3(x2, baseHeight, wall.start.z));
                                wall.mesh.vertices.push_back(vec3(x2, baseHeight, wall.end.z));
                                wall.mesh.vertices.push_back(vec3(x2, endHeight, wall.end.z));
                                wall.mesh.vertices.push_back(vec3(x2, centerHeight, cz));
                                wall.mesh.vertices.push_back(vec3(x2, startHeight, wall.start.z));

                                wall.mesh.faces.push_back({0, 4, 1});
                                wall.mesh.faces.push_back({1, 4, 2});
                                wall.mesh.faces.push_back({2, 4, 3});

                                wall.mesh.faces.push_back({5, 6, 9});
                                wall.mesh.faces.push_back({6, 7, 9});
                                wall.mesh.faces.push_back({7, 8, 9});

                                wall.mesh.faces.push_back({0, 1, 6});
                                wall.mesh.faces.push_back({0, 6, 5});

                                wall.mesh.faces.push_back({0, 5, 9});
                                wall.mesh.faces.push_back({0, 9, 4});

                                wall.mesh.faces.push_back({1, 2, 7});
                                wall.mesh.faces.push_back({1, 7, 6});

                                wall.mesh.faces.push_back({4, 9, 8});
                                wall.mesh.faces.push_back({4, 8, 3});
                                wall.mesh.faces.push_back({2, 3, 8});
                                wall.mesh.faces.push_back({2, 8, 7});

                                wall.end.y = centerHeight;
                            }

                            std::cout << "Created gable wall (idempotent)" << std::endl;
                        }
                    }
                }

                // Handle union request - combine selected elements into one
                if (imgui.wasUnionRequested()) {
                    imgui.clearUnionRequest();
                    const auto& selected = imgui.getSelectedElements();
                    if (selected.size() >= 2) {
                        auto& elements = buildings[currentBuilding].elements;
                        
                        // Convert selected indices to sorted vector (descending for safe removal)
                        std::vector<int> selIndices(selected.begin(), selected.end());
                        std::sort(selIndices.begin(), selIndices.end(), std::greater<int>());
                        
                        // Combine all meshes using CSG union
                        std::pair<std::vector<Vertex>, std::vector<u32>> combinedMesh;
                        bool firstMesh = true;
                        StructuralElement baseElement;
                        
                        for (int idx : selIndices) {
                            if (idx >= 0 && idx < (int)elements.size()) {
                                const auto& elem = elements[idx];
                                
                                // Get or generate mesh for this element
                                std::pair<std::vector<Vertex>, std::vector<u32>> elemMesh;
                                if (elem.mesh.hasData()) {
                                    // Convert embedded mesh to vertex/index format
                                    for (const auto& v : elem.mesh.vertices) {
                                        Vertex vert{};
                                        vert.position = v;
                                        vert.normal = vec3(0, 1, 0);
                                        vert.color = vec3(0.7f, 0.7f, 0.7f);
                                        elemMesh.first.push_back(vert);
                                    }
                                    for (const auto& face : elem.mesh.faces) {
                                        elemMesh.second.push_back(face[0]);
                                        elemMesh.second.push_back(face[1]);
                                        elemMesh.second.push_back(face[2]);
                                    }
                                } else {
                                    // Generate mesh from element type
                                    switch (elem.type) {
                                        case ElementType::Beam:
                                            elemMesh = Geometry::createBeam(elem.start, elem.end, elem.width, elem.depth);
                                            break;
                                        case ElementType::Column:
                                            elemMesh = Geometry::createColumn(elem.start, elem.width, elem.depth, elem.end.y - elem.start.y);
                                            break;
                                        case ElementType::Floor:
                                            elemMesh = Geometry::createFloorSlab(elem.start, elem.end.x - elem.start.x, elem.end.z - elem.start.z, elem.depth);
                                            break;
                                        case ElementType::Wall:
                                            elemMesh = Geometry::createBeam(elem.start, vec3(elem.end.x, elem.start.y, elem.end.z), elem.depth, elem.end.y - elem.start.y);
                                            break;
                                        case ElementType::Roof:
                                            elemMesh = Geometry::createFloorSlab(elem.start, elem.end.x - elem.start.x, elem.end.z - elem.start.z, elem.depth);
                                            break;
                                        default:
                                            continue;
                                    }
                                }
                                
                                if (firstMesh) {
                                    combinedMesh = elemMesh;
                                    baseElement = elem;
                                    firstMesh = false;
                                } else {
                                    combinedMesh = Geometry::CSG::meshUnion(combinedMesh, elemMesh);
                                }
                            }
                        }
                        
                        // Remove selected elements (already sorted descending)
                        for (int idx : selIndices) {
                            if (idx >= 0 && idx < (int)elements.size()) {
                                elements.erase(elements.begin() + idx);
                            }
                        }
                        
                        // Create new combined element
                        StructuralElement newElem;
                        newElem.type = baseElement.type;
                        newElem.material = baseElement.material;
                        newElem.start = baseElement.start;
                        newElem.end = baseElement.end;
                        newElem.width = baseElement.width;
                        newElem.depth = baseElement.depth;
                        
                        // Store combined mesh vertices and faces
                        for (const auto& v : combinedMesh.first) {
                            newElem.mesh.vertices.push_back(v.position);
                        }
                        for (size_t i = 0; i + 2 < combinedMesh.second.size(); i += 3) {
                            std::array<u32, 3> face;
                            face[0] = combinedMesh.second[i];
                            face[1] = combinedMesh.second[i + 1];
                            face[2] = combinedMesh.second[i + 2];
                            newElem.mesh.faces.push_back(face);
                        }
                        
                        elements.push_back(newElem);
                        
                        // Clear selection and select new element
                        imgui.clearSelection();
                        imgui.setSelection(static_cast<int>(elements.size() - 1));
                        
                        std::cout << "Union created: combined " << selIndices.size() << " elements into 1" << std::endl;
                        std::cout << "  Vertices: " << combinedMesh.first.size() << ", Faces: " << combinedMesh.second.size() / 3 << std::endl;
                    }
                }

                
                // Render ImGui
                imgui.endFrame(renderer.getCurrentCommandBuffer());

                renderer.endRenderPass();
                renderer.endFrame();
            }
        }

        context.waitIdle();
        std::cout << "ArchEngine shutdown complete\n";
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }
}
