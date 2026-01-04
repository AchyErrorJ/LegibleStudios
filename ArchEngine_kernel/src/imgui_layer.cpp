#include "imgui_layer.hpp"
#include "physics_bridge.hpp"
#include "renderer.hpp"
#include <GLFW/glfw3.h>
#include <algorithm>
#include <stdexcept>

namespace arch {

ImGuiLayer::ImGuiLayer(VulkanContext& context, GLFWwindow* window, VkRenderPass renderPass) : m_context(context) {
    // Create descriptor pool for ImGui
    createDescriptorPool();

    // Setup ImGui context
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;

    // Setup style
    ImGui::StyleColorsDark();
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 5.0f;
    style.FrameRounding = 3.0f;
    style.ScrollbarRounding = 3.0f;
    style.GrabRounding = 3.0f;

    // Initialize GLFW backend
    ImGui_ImplGlfw_InitForVulkan(window, true);

    // Initialize Vulkan backend
    ImGui_ImplVulkan_InitInfo initInfo{};
    initInfo.Instance = context.getInstance();
    initInfo.PhysicalDevice = context.getPhysicalDevice();
    initInfo.Device = context.getDevice();
    initInfo.QueueFamily = context.getGraphicsQueueFamily();
    initInfo.Queue = context.getGraphicsQueue();
    initInfo.DescriptorPool = m_imguiPool;
    initInfo.MinImageCount = 2;
    initInfo.ImageCount = static_cast<u32>(context.getSwapchainImageViews().size());
    initInfo.MSAASamples = context.getMsaaSamples();  // Match render pass MSAA

    ImGui_ImplVulkan_Init(&initInfo, renderPass);

    // Upload fonts
    uploadFonts();

    m_initialized = true;
}

ImGuiLayer::~ImGuiLayer() {
    if (m_initialized) {
        m_context.waitIdle();
        ImGui_ImplVulkan_Shutdown();
        ImGui_ImplGlfw_Shutdown();
        ImGui::DestroyContext();
    }

    if (m_imguiPool != VK_NULL_HANDLE) {
        vkDestroyDescriptorPool(m_context.getDevice(), m_imguiPool, nullptr);
    }
}

void ImGuiLayer::createDescriptorPool() {
    VkDescriptorPoolSize poolSizes[] = {
        { VK_DESCRIPTOR_TYPE_SAMPLER, 1000 },
        { VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1000 },
        { VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_TEXEL_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 1000 },
        { VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC, 1000 },
        { VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC, 1000 },
        { VK_DESCRIPTOR_TYPE_INPUT_ATTACHMENT, 1000 }
    };

    VkDescriptorPoolCreateInfo poolInfo{};
    poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    poolInfo.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;
    poolInfo.maxSets = 1000;
    poolInfo.poolSizeCount = static_cast<u32>(std::size(poolSizes));
    poolInfo.pPoolSizes = poolSizes;

    if (vkCreateDescriptorPool(m_context.getDevice(), &poolInfo, nullptr, &m_imguiPool) != VK_SUCCESS) {
        throw std::runtime_error("Failed to create ImGui descriptor pool");
    }
}

void ImGuiLayer::uploadFonts() {
    // In ImGui 1.90+, font upload is handled automatically by ImGui_ImplVulkan_CreateFontsTexture
    ImGui_ImplVulkan_CreateFontsTexture();
}

void ImGuiLayer::beginFrame() {
    ImGui_ImplVulkan_NewFrame();
    ImGui_ImplGlfw_NewFrame();
    ImGui::NewFrame();
}

void ImGuiLayer::endFrame(VkCommandBuffer cmd) {
    ImGui::Render();
    ImGui_ImplVulkan_RenderDrawData(ImGui::GetDrawData(), cmd);
}

void ImGuiLayer::drawMainMenuBar(VisualizationMode& mode, bool& showDemo, bool& showMetrics) {
    if (ImGui::BeginMainMenuBar()) {
        if (ImGui::BeginMenu("View")) {
            if (ImGui::MenuItem("Structural", "1", mode == VisualizationMode::Structural))
                mode = VisualizationMode::Structural;
            if (ImGui::MenuItem("Thermal", "2", mode == VisualizationMode::Thermal))
                mode = VisualizationMode::Thermal;
            if (ImGui::MenuItem("Lighting", "3", mode == VisualizationMode::Lighting))
                mode = VisualizationMode::Lighting;
            if (ImGui::MenuItem("Acoustic", "4", mode == VisualizationMode::Acoustic))
                mode = VisualizationMode::Acoustic;
            if (ImGui::MenuItem("Material", "5", mode == VisualizationMode::Material))
                mode = VisualizationMode::Material;
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Tools")) {
            ImGui::MenuItem("Show Demo", nullptr, &showDemo);
            ImGui::MenuItem("Show Metrics", nullptr, &showMetrics);
            ImGui::EndMenu();
        }
        ImGui::EndMainMenuBar();
    }
}

void ImGuiLayer::drawBuildingPanel(const Building& building, size_t currentIndex, size_t totalBuildings) {
    ImGui::SetNextWindowPos(ImVec2(10, 30), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(280, 200), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Building Info")) {
        ImGui::Text("Building: %s", building.name.c_str());
        ImGui::Text("Index: %zu / %zu", currentIndex + 1, totalBuildings);
        ImGui::Separator();

        ImGui::Text("Elements: %zu", building.elements.size());

        // Count element types
        size_t beams = 0, columns = 0, floors = 0;
        for (const auto& elem : building.elements) {
            switch (elem.type) {
                case ElementType::Beam: beams++; break;
                case ElementType::Column: columns++; break;
                case ElementType::Floor: floors++; break;
                default: break;
            }
        }

        ImGui::BulletText("Beams: %zu", beams);
        ImGui::BulletText("Columns: %zu", columns);
        ImGui::BulletText("Floors: %zu", floors);

        ImGui::Separator();
        ImGui::TextWrapped("Use [ ] to switch buildings");
    }
    ImGui::End();
}

void ImGuiLayer::drawPhysicsPanel(const FrameAnalysis& analysis, bool physicsAvailable) {
    ImGui::SetNextWindowPos(ImVec2(10, 240), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(280, 180), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Physics Analysis")) {
        if (!physicsAvailable) {
            ImGui::TextColored(ImVec4(1.0f, 0.5f, 0.0f, 1.0f), "Physics engine not available");
            ImGui::TextWrapped("Python physics module not found.");
        } else {
            // Status indicator
            if (analysis.allPass) {
                ImGui::TextColored(ImVec4(0.2f, 0.8f, 0.2f, 1.0f), "Status: PASS");
            } else {
                ImGui::TextColored(ImVec4(0.9f, 0.3f, 0.3f, 1.0f), "Status: FAIL");
            }

            ImGui::Separator();

            // Utilization bars
            ImGui::Text("Beam Utilization:");
            f32 beamUtil = analysis.maxBeamUtilization;
            ImVec4 beamColor = beamUtil > 1.0f ? ImVec4(0.9f, 0.3f, 0.3f, 1.0f) :
                              beamUtil > 0.9f ? ImVec4(0.9f, 0.7f, 0.0f, 1.0f) :
                              ImVec4(0.2f, 0.8f, 0.2f, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_PlotHistogram, beamColor);
            ImGui::ProgressBar(beamUtil, ImVec2(-1, 0),
                std::to_string(static_cast<int>(beamUtil * 100)).append("%").c_str());
            ImGui::PopStyleColor();

            ImGui::Text("Column Utilization:");
            f32 colUtil = analysis.maxColumnUtilization;
            ImVec4 colColor = colUtil > 1.0f ? ImVec4(0.9f, 0.3f, 0.3f, 1.0f) :
                             colUtil > 0.9f ? ImVec4(0.9f, 0.7f, 0.0f, 1.0f) :
                             ImVec4(0.2f, 0.8f, 0.2f, 1.0f);
            ImGui::PushStyleColor(ImGuiCol_PlotHistogram, colColor);
            ImGui::ProgressBar(colUtil, ImVec2(-1, 0),
                std::to_string(static_cast<int>(colUtil * 100)).append("%").c_str());
            ImGui::PopStyleColor();

            ImGui::Separator();
            if (ImGui::Button("Run Analysis (P)")) {
                m_analysisRequested = true;
            }
        }
    }
    ImGui::End();
}

void ImGuiLayer::drawVisualizationPanel(VisualizationMode& mode, Renderer& renderer) {
    ImGui::SetNextWindowPos(ImVec2(10, 430), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(280, 280), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Visualization Mode")) {
        // Camera view buttons
        ImGui::Text("Camera View:");
        if (ImGui::Button("Perspective")) {
            m_cameraViewRequested = true;
            m_requestedCameraView = CameraView::Perspective;
        }
        ImGui::SameLine();
        if (ImGui::Button("Top")) {
            m_cameraViewRequested = true;
            m_requestedCameraView = CameraView::Top;
        }
        ImGui::SameLine();
        if (ImGui::Button("Front")) {
            m_cameraViewRequested = true;
            m_requestedCameraView = CameraView::Front;
        }
        ImGui::SameLine();
        if (ImGui::Button("Right")) {
            m_cameraViewRequested = true;
            m_requestedCameraView = CameraView::Right;
        }

        ImGui::Separator();

        const char* modeNames[] = { "Structural", "Thermal", "Lighting", "Acoustic", "Material", "Wireframe" };
        int currentMode = static_cast<int>(mode);

        if (ImGui::Combo("Mode", &currentMode, modeNames, IM_ARRAYSIZE(modeNames))) {
            mode = static_cast<VisualizationMode>(currentMode);
        }

        // Material style selector
        const char* styleNames[] = { "Realistic", "Clean", "Schematic", "Blueprint" };
        int currentStyle = static_cast<int>(renderer.getMaterialStyle());

        if (ImGui::Combo("Style", &currentStyle, styleNames, IM_ARRAYSIZE(styleNames))) {
            renderer.setMaterialStyle(static_cast<MaterialStyle>(currentStyle));
        }

        ImGui::Separator();

        // Mode-specific legend
        switch (mode) {
            case VisualizationMode::Structural:
                ImGui::TextColored(ImVec4(0.13f, 0.77f, 0.37f, 1.0f), "Green: Safe (<70%%)");
                ImGui::TextColored(ImVec4(0.92f, 0.70f, 0.03f, 1.0f), "Yellow: Warning (70-90%%)");
                ImGui::TextColored(ImVec4(0.98f, 0.45f, 0.09f, 1.0f), "Orange: Critical (90-100%%)");
                ImGui::TextColored(ImVec4(0.94f, 0.27f, 0.27f, 1.0f), "Red: Failure (>100%%)");
                break;
            case VisualizationMode::Thermal:
                ImGui::TextColored(ImVec4(0.12f, 0.56f, 1.0f, 1.0f), "Blue: Cold");
                ImGui::TextColored(ImVec4(1.0f, 0.27f, 0.0f, 1.0f), "Red: Hot");
                break;
            case VisualizationMode::Lighting:
                ImGui::TextColored(ImVec4(1.0f, 0.96f, 0.61f, 1.0f), "Yellow: High lux");
                ImGui::TextColored(ImVec4(0.25f, 0.41f, 0.88f, 1.0f), "Blue: Low lux");
                break;
            case VisualizationMode::Acoustic:
                ImGui::TextColored(ImVec4(0.13f, 0.77f, 0.37f, 1.0f), "Green: Good RT60");
                ImGui::TextColored(ImVec4(0.92f, 0.70f, 0.03f, 1.0f), "Yellow: Moderate");
                ImGui::TextColored(ImVec4(0.94f, 0.27f, 0.27f, 1.0f), "Red: Poor");
                break;
            case VisualizationMode::Material:
                ImGui::Text("Colors by material type");
                break;
            default:
                break;
        }
    }
    ImGui::End();
}

void ImGuiLayer::drawHelpPanel(bool& show) {
    if (!show) return;

    ImGui::SetNextWindowPos(ImVec2(300, 100), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(350, 300), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Help", &show)) {
        ImGui::Text("Keyboard Shortcuts:");
        ImGui::Separator();

        ImGui::BulletText("1-5: Switch visualization mode");
        ImGui::BulletText("[ ]: Previous/Next building");
        ImGui::BulletText("P: Run physics analysis");
        ImGui::BulletText("H: Toggle help");
        ImGui::BulletText("ESC: Exit");

        ImGui::Separator();
        ImGui::Text("Mouse Controls:");
        ImGui::BulletText("Left drag: Orbit camera");
        ImGui::BulletText("Right drag: Pan camera");
        ImGui::BulletText("Scroll: Zoom");
    }
    ImGui::End();
}

void ImGuiLayer::drawPerformancePanel(f32 fps, u32 drawCalls, u32 triangles) {
    ImGui::SetNextWindowPos(ImVec2(ImGui::GetIO().DisplaySize.x - 160, 30), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(150, 100), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Performance", nullptr, ImGuiWindowFlags_NoResize)) {
        ImGui::Text("FPS: %.1f", fps);
        ImGui::Text("Draw Calls: %u", drawCalls);
        ImGui::Text("Triangles: %u", triangles);
    }
    ImGui::End();
}

bool ImGuiLayer::wantCaptureMouse() const {
    return ImGui::GetIO().WantCaptureMouse;
}

bool ImGuiLayer::wantCaptureKeyboard() const {
    return ImGui::GetIO().WantCaptureKeyboard;
}


void ImGuiLayer::drawGeometryEditor(bool& show) {
    if (!show) return;

    ImGui::SetNextWindowPos(ImVec2(300, 30), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(350, 550), ImGuiCond_FirstUseEver);

    if (ImGui::Begin("Geometry Editor", &show)) {
        // File Operations
        if (ImGui::CollapsingHeader("File Operations", ImGuiTreeNodeFlags_DefaultOpen)) {
            static char filepath[256] = "C:/Users/jerro/Desktop/channel_test/test.ifc";
            ImGui::InputText("Path", filepath, sizeof(filepath));
            m_filePath = filepath;

            // Quick load buttons
            if (ImGui::Button("Load")) {
                m_loadRequested = true;
            }
            ImGui::SameLine();
            if (ImGui::Button("Save")) {
                m_saveRequested = true;
            }
            
            ImGui::Separator();
            ImGui::Text("Quick Paths:");
            if (ImGui::Button("Desktop IFC")) {
                strcpy(filepath, "C:/Users/jerro/Desktop/channel_test/test.ifc");
                m_filePath = filepath;
                m_loadRequested = true;
            }
            ImGui::SameLine();
            if (ImGui::Button("Test JSON")) {
                strcpy(filepath, "X:/tmp/test_import.json");
                m_filePath = filepath;
                m_loadRequested = true;
            }
        }

        ImGui::Separator();

        // Add New Element
        if (ImGui::CollapsingHeader("Add Element", ImGuiTreeNodeFlags_DefaultOpen)) {
            const char* elementTypes[] = { "Beam", "Column", "Floor", "Wall", "Door", "Window", "Roof" };
            ImGui::Combo("Type", &m_newElement.type, elementTypes, IM_ARRAYSIZE(elementTypes));

            const char* materials[] = { "Steel", "Concrete", "Wood", "Aluminum" };
            ImGui::Combo("Material", &m_newElement.materialIndex, materials, IM_ARRAYSIZE(materials));

            ImGui::Separator();

            if (m_newElement.type == 0) {  // Beam
                ImGui::Text("Beam (horizontal member)");
                ImGui::DragFloat3("Start Point", m_newElement.start, 0.5f, -500.0f, 500.0f);
                ImGui::DragFloat3("End Point", m_newElement.end, 0.5f, -500.0f, 500.0f);
                ImGui::DragFloat("Width (ft)", &m_newElement.width, 0.05f, 0.1f, 5.0f);
                ImGui::DragFloat("Depth (ft)", &m_newElement.depth, 0.05f, 0.1f, 5.0f);
            }
            else if (m_newElement.type == 1) {  // Column
                ImGui::Text("Column (vertical member)");
                ImGui::DragFloat3("Base Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                float height = m_newElement.end[1] - m_newElement.start[1];
                if (height < 1.0f) height = 12.0f;
                if (ImGui::DragFloat("Height (ft)", &height, 0.5f, 1.0f, 100.0f)) {
                    m_newElement.end[0] = m_newElement.start[0];
                    m_newElement.end[1] = m_newElement.start[1] + height;
                    m_newElement.end[2] = m_newElement.start[2];
                }
                ImGui::DragFloat("Width (ft)", &m_newElement.width, 0.05f, 0.1f, 5.0f);
                ImGui::DragFloat("Depth (ft)", &m_newElement.depth, 0.05f, 0.1f, 5.0f);
            }
            else if (m_newElement.type == 2) {  // Floor
                ImGui::Text("Floor slab");
                ImGui::DragFloat3("Corner Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                float floorWidth = m_newElement.end[0] - m_newElement.start[0];
                float floorDepthZ = m_newElement.end[2] - m_newElement.start[2];
                if (floorWidth < 1.0f) floorWidth = 20.0f;
                if (floorDepthZ < 1.0f) floorDepthZ = 20.0f;
                if (ImGui::DragFloat("Width X (ft)", &floorWidth, 0.5f, 1.0f, 200.0f)) {
                    m_newElement.end[0] = m_newElement.start[0] + floorWidth;
                }
                if (ImGui::DragFloat("Depth Z (ft)", &floorDepthZ, 0.5f, 1.0f, 200.0f)) {
                    m_newElement.end[2] = m_newElement.start[2] + floorDepthZ;
                }
                m_newElement.end[1] = m_newElement.start[1];
                ImGui::DragFloat("Thickness (ft)", &m_newElement.depth, 0.05f, 0.1f, 2.0f);
            }
            else if (m_newElement.type == 3) {  // Wall
                ImGui::Text("Parametric Wall");

                // Wall type selection
                const char* wallTypes[] = { "2x6 Exterior", "2x4 Exterior", "2x4 Interior" };
                ImGui::Combo("Wall Type", &m_newElement.wallTypeIndex, wallTypes, IM_ARRAYSIZE(wallTypes));

                // Wall height
                ImGui::DragFloat("Height (ft)", &m_newElement.wallHeight, 0.5f, 4.0f, 20.0f);

                ImGui::Separator();

                // Drawing mode toggle
                if (m_drawMode == DrawMode::DrawWall) {
                    ImGui::TextColored(ImVec4(0.2f, 1.0f, 0.2f, 1.0f), "DRAWING MODE ACTIVE");
                    if (m_drawPoints.empty()) {
                        ImGui::Text("Click to place START point");
                    } else {
                        ImGui::Text("Click to place END point");
                        ImGui::Text("Start: (%.1f, %.1f, %.1f)",
                            m_drawPoints[0].x, m_drawPoints[0].y, m_drawPoints[0].z);
                    }
                    if (ImGui::Button("Cancel Drawing", ImVec2(-1, 25))) {
                        m_drawMode = DrawMode::None;
                        m_drawPoints.clear();
                    }
                } else {
                    if (ImGui::Button("Draw Wall (Click-to-Place)", ImVec2(-1, 30))) {
                        m_drawMode = DrawMode::DrawWall;
                        m_drawPoints.clear();
                    }
                    ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f),
                        "Or enter coordinates manually:");
                    ImGui::DragFloat3("Start Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                    ImGui::DragFloat3("End Position", m_newElement.end, 0.5f, -500.0f, 500.0f);
                }
            }
            else if (m_newElement.type == 4) {  // Door
                ImGui::Text("Door opening");
                ImGui::DragFloat3("Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                float doorHeight = m_newElement.end[1] - m_newElement.start[1];
                if (doorHeight < 1.0f) doorHeight = 7.0f;  // Default door height ~7ft
                if (ImGui::DragFloat("Height (ft)", &doorHeight, 0.1f, 4.0f, 12.0f)) {
                    m_newElement.end[1] = m_newElement.start[1] + doorHeight;
                }
                ImGui::DragFloat("Width (ft)", &m_newElement.width, 0.1f, 2.0f, 10.0f);
                ImGui::DragFloat("Depth (ft)", &m_newElement.depth, 0.05f, 0.1f, 1.0f);
            }
            else if (m_newElement.type == 5) {  // Window
                ImGui::Text("Window");
                ImGui::DragFloat3("Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                float windowHeight = m_newElement.end[1] - m_newElement.start[1];
                if (windowHeight < 0.5f) windowHeight = 4.0f;  // Default window height
                if (ImGui::DragFloat("Height (ft)", &windowHeight, 0.1f, 1.0f, 10.0f)) {
                    m_newElement.end[1] = m_newElement.start[1] + windowHeight;
                }
                ImGui::DragFloat("Width (ft)", &m_newElement.width, 0.1f, 1.0f, 15.0f);
                ImGui::DragFloat("Depth (ft)", &m_newElement.depth, 0.05f, 0.1f, 0.5f);
            }
            else if (m_newElement.type == 6) {  // Roof
                ImGui::Text("Roof slab");
                ImGui::DragFloat3("Corner Position", m_newElement.start, 0.5f, -500.0f, 500.0f);
                float roofWidth = m_newElement.end[0] - m_newElement.start[0];
                float roofDepthZ = m_newElement.end[2] - m_newElement.start[2];
                if (roofWidth < 1.0f) roofWidth = 30.0f;
                if (roofDepthZ < 1.0f) roofDepthZ = 30.0f;
                if (ImGui::DragFloat("Width X (ft)", &roofWidth, 0.5f, 1.0f, 200.0f)) {
                    m_newElement.end[0] = m_newElement.start[0] + roofWidth;
                }
                if (ImGui::DragFloat("Depth Z (ft)", &roofDepthZ, 0.5f, 1.0f, 200.0f)) {
                    m_newElement.end[2] = m_newElement.start[2] + roofDepthZ;
                }
                ImGui::DragFloat("Thickness (ft)", &m_newElement.depth, 0.05f, 0.1f, 2.0f);
            }

            ImGui::Separator();

if (ImGui::Button("Add Element", ImVec2(-1, 30))) {
                m_addElementRequested = true;
            }
        }

        ImGui::Separator();

        // Boolean Operations (CSG)
        if (ImGui::CollapsingHeader("Boolean Operations")) {
            ImGui::Text("Selected: %d elements", (int)m_selectedElements.size());
            ImGui::TextWrapped("Ctrl+Click to select multiple elements");

            ImGui::Separator();

            // Union button - enabled only when 2+ elements selected
            bool canUnion = m_selectedElements.size() >= 2;
            if (!canUnion) {
                ImGui::BeginDisabled();
            }
            if (ImGui::Button("Union Selected", ImVec2(-1, 30))) {
                m_unionRequested = true;
            }
            if (!canUnion) {
                ImGui::EndDisabled();
                ImGui::TextColored(ImVec4(0.7f, 0.7f, 0.7f, 1.0f), "Select 2+ elements to union");
            }

        }
    }
    ImGui::End();
}


void ImGuiLayer::drawWallEditor(Building& building, bool show) {
    if (!show) return;
    
    ImGui::SetNextWindowPos(ImVec2(660, 30), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(300, 400), ImGuiCond_FirstUseEver);
    
    if (ImGui::Begin("Wall Editor")) {
        // Get walls and roofs
        std::vector<int> wallIndices;
        std::vector<int> roofIndices;
        for (size_t i = 0; i < building.elements.size(); i++) {
            if (building.elements[i].type == ElementType::Wall) {
                wallIndices.push_back(static_cast<int>(i));
            }
            if (building.elements[i].type == ElementType::Roof) {
                roofIndices.push_back(static_cast<int>(i));
            }
        }

        ImGui::Text("Walls: %d, Roofs: %d", (int)wallIndices.size(), (int)roofIndices.size());

        // Wall selection - auto-select if element was clicked
        static int selectedIdx = 0;
        // Check if any selected element is a wall
        for (int selElem : m_selectedElements) {
            for (int i = 0; i < (int)wallIndices.size(); i++) {
                if (wallIndices[i] == selElem) {
                    selectedIdx = i;
                    break;
                }
            }
        }
        if (!wallIndices.empty()) {
            // Create wall labels
            std::vector<std::string> wallLabels;
            for (int idx : wallIndices) {
                auto& w = building.elements[idx];
                float height = w.end.y - w.start.y;
                char label[64];
                snprintf(label, sizeof(label), "Wall %d (%.1fft)", idx, height);
                wallLabels.push_back(label);
            }

            // Combo for wall selection
            if (ImGui::BeginCombo("Select Wall", wallLabels[selectedIdx].c_str())) {
                for (int i = 0; i < (int)wallLabels.size(); i++) {
                    bool isSelected = (selectedIdx == i);
                    if (ImGui::Selectable(wallLabels[i].c_str(), isSelected)) {
                        selectedIdx = i;
                    }
                    if (isSelected) ImGui::SetItemDefaultFocus();
                }
                ImGui::EndCombo();
            }

            // Show selected wall info
            int wallIdx = wallIndices[selectedIdx];
            auto& wall = building.elements[wallIdx];
            ImGui::Text("Current Height: %.1f ft", wall.end.y - wall.start.y);
            ImGui::Text("Position: (%.1f, %.1f) to (%.1f, %.1f)",
                       wall.start.x, wall.start.z, wall.end.x, wall.end.z);

            // Find roof peak above this wall
            float roofPeak = wall.end.y;
            for (int roofIdx : roofIndices) {
                auto& roof = building.elements[roofIdx];
                // Check if wall is under this roof (simple bounds check)
                float wallCenterX = (wall.start.x + wall.end.x) / 2;
                float wallCenterZ = (wall.start.z + wall.end.z) / 2;

                if (roof.mesh.hasData()) {
                    // Check mesh vertices for peak
                    for (const auto& v : roof.mesh.vertices) {
                        // If vertex is roughly above the wall
                        float dx = std::abs(v.x - wallCenterX);
                        float dz = std::abs(v.z - wallCenterZ);
                        float wallExtentX = std::abs(wall.end.x - wall.start.x) / 2 + 5.0f;
                        float wallExtentZ = std::abs(wall.end.z - wall.start.z) / 2 + 5.0f;
                        if (dx < wallExtentX && dz < wallExtentZ) {
                            roofPeak = std::max(roofPeak, v.y);
                        }
                    }
                } else {
                    // Use bounding box
                    if (wallCenterX >= roof.start.x - 5 && wallCenterX <= roof.end.x + 5 &&
                        wallCenterZ >= roof.start.z - 5 && wallCenterZ <= roof.end.z + 5) {
                        roofPeak = std::max(roofPeak, roof.end.y);
                    }
                }
            }

            ImGui::Text("Roof Peak Above: %.1f ft", roofPeak);

            // Height adjustment slider
            static float newHeight = 10.0f;
            newHeight = wall.end.y - wall.start.y;
            ImGui::SliderFloat("New Height (ft)", &newHeight, 1.0f, 30.0f);

            // Quick buttons
            if (ImGui::Button("Extend to Roof Peak")) {
                m_selectedWallIndex = wallIdx;
                // Subtract offset so wall fits under roof (accounts for roof thickness)
                m_wallExtendHeight = roofPeak - 0.5f;
                m_extendWallRequested = true;
            }
            ImGui::SameLine();
            if (ImGui::Button("Set Custom Height")) {
                m_selectedWallIndex = wallIdx;
                m_wallExtendHeight = wall.start.y + newHeight;
                m_extendWallRequested = true;
            }
        } else {
            ImGui::Text("No walls in model");
        }
    }
    ImGui::End();
}

void ImGuiLayer::drawRenderSettingsPanel(Renderer& renderer, bool& show) {
    if (!show) return;

    ImGui::SetNextWindowPos(ImVec2(10, 660), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(320, 300), ImGuiCond_FirstUseEver);
    if (ImGui::Begin("Render Settings", &show)) {
        // Shadow Settings
        if (ImGui::CollapsingHeader("Shadow Settings", ImGuiTreeNodeFlags_DefaultOpen)) {
            bool shadowsEnabled = renderer.getShadowsEnabled();
            if (ImGui::Checkbox("Enable Shadows", &shadowsEnabled)) {
                renderer.setShadowsEnabled(shadowsEnabled);
            }

            if (shadowsEnabled) {
                vec3 lightDir = renderer.getLightDirection();
                float lightAngles[2] = {
                    glm::degrees(std::atan2(lightDir.x, lightDir.z)),  // Azimuth
                    glm::degrees(std::asin(-lightDir.y))               // Elevation
                };

                if (ImGui::SliderFloat("Sun Azimuth", &lightAngles[0], -180.0f, 180.0f, "%.0f deg")) {
                    float az = glm::radians(lightAngles[0]);
                    float el = glm::radians(lightAngles[1]);
                    vec3 newDir = vec3(
                        std::sin(az) * std::cos(el),
                        -std::sin(el),
                        std::cos(az) * std::cos(el)
                    );
                    renderer.setLightDirection(newDir);
                }

                if (ImGui::SliderFloat("Sun Elevation", &lightAngles[1], 10.0f, 80.0f, "%.0f deg")) {
                    float az = glm::radians(lightAngles[0]);
                    float el = glm::radians(lightAngles[1]);
                    vec3 newDir = vec3(
                        std::sin(az) * std::cos(el),
                        -std::sin(el),
                        std::cos(az) * std::cos(el)
                    );
                    renderer.setLightDirection(newDir);
                }

                float shadowBias = renderer.getShadowBias();
                if (ImGui::SliderFloat("Shadow Bias", &shadowBias, 0.001f, 0.1f, "%.4f")) {
                    renderer.setShadowBias(shadowBias);
                }
                ImGui::SetItemTooltip("Increase to reduce shadow acne, decrease to reduce peter-panning");

                // Quick presets
                ImGui::Text("Light Presets:");
                if (ImGui::Button("Morning")) {
                    renderer.setLightDirection(vec3(-0.7f, -0.5f, 0.5f));
                }
                ImGui::SameLine();
                if (ImGui::Button("Noon")) {
                    renderer.setLightDirection(vec3(0.0f, -1.0f, 0.1f));
                }
                ImGui::SameLine();
                if (ImGui::Button("Evening")) {
                    renderer.setLightDirection(vec3(0.7f, -0.3f, -0.5f));
                }

                ImGui::Separator();

                // Sun animation
                static bool animateSun = false;
                static float animSpeed = 0.1f;  // Slower default
                static float sunAngle = 0.0f;

                ImGui::Checkbox("Animate Sun", &animateSun);
                if (animateSun) {
                    ImGui::SliderFloat("Speed", &animSpeed, 0.01f, 2.0f, "%.2fx");

                    // Update sun angle
                    sunAngle += animSpeed * 0.016f;  // ~60fps
                    if (sunAngle > 6.28318f) sunAngle -= 6.28318f;

                    // Calculate sun position (circular path)
                    float elevation = 0.5f + 0.3f * std::sin(sunAngle * 0.5f);  // Varies 0.2-0.8
                    vec3 newDir = vec3(
                        std::sin(sunAngle) * std::cos(elevation),
                        -std::sin(elevation),
                        std::cos(sunAngle) * std::cos(elevation)
                    );
                    renderer.setLightDirection(newDir);

                    // Show current time of day
                    float hours = (sunAngle / 6.28318f) * 24.0f;
                    int hour = static_cast<int>(hours) % 24;
                    int minute = static_cast<int>((hours - hour) * 60.0f) % 60;
                    ImGui::Text("Time: %02d:%02d", (hour + 6) % 24, minute);
                }
            }
        }

        ImGui::Separator();

        // SSAO Settings
        if (ImGui::CollapsingHeader("Ambient Occlusion (SSAO)", ImGuiTreeNodeFlags_DefaultOpen)) {
            bool ssaoEnabled = renderer.getSSAOEnabled();
            if (ImGui::Checkbox("Enable SSAO", &ssaoEnabled)) {
                renderer.setSSAOEnabled(ssaoEnabled);
            }

            if (ssaoEnabled) {
                float ssaoRadius = renderer.getSSAORadius();
                if (ImGui::SliderFloat("Radius", &ssaoRadius, 0.1f, 2.0f, "%.2f")) {
                    renderer.setSSAORadius(ssaoRadius);
                }

                float ssaoIntensity = renderer.getSSAOIntensity();
                if (ImGui::SliderFloat("Intensity", &ssaoIntensity, 0.5f, 4.0f, "%.1f")) {
                    renderer.setSSAOIntensity(ssaoIntensity);
                }

                float ssaoBias = renderer.getSSAOBias();
                if (ImGui::SliderFloat("Bias", &ssaoBias, 0.001f, 0.1f, "%.3f")) {
                    renderer.setSSAOBias(ssaoBias);
                }

                // Presets
                ImGui::Text("Presets:");
                if (ImGui::Button("Subtle")) {
                    renderer.setSSAORadius(0.3f);
                    renderer.setSSAOIntensity(1.0f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Medium")) {
                    renderer.setSSAORadius(0.5f);
                    renderer.setSSAOIntensity(1.5f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Strong")) {
                    renderer.setSSAORadius(0.8f);
                    renderer.setSSAOIntensity(2.5f);
                }
            }
        }

        ImGui::Separator();

        // Bloom Settings
        if (ImGui::CollapsingHeader("Bloom", ImGuiTreeNodeFlags_DefaultOpen)) {
            bool bloomEnabled = renderer.getBloomEnabled();
            if (ImGui::Checkbox("Enable Bloom", &bloomEnabled)) {
                renderer.setBloomEnabled(bloomEnabled);
            }

            if (bloomEnabled) {
                float bloomThreshold = renderer.getBloomThreshold();
                if (ImGui::SliderFloat("Threshold", &bloomThreshold, 0.1f, 3.0f, "%.2f")) {
                    renderer.setBloomThreshold(bloomThreshold);
                }

                float bloomIntensity = renderer.getBloomIntensity();
                if (ImGui::SliderFloat("Bloom Intensity", &bloomIntensity, 0.0f, 1.0f, "%.2f")) {
                    renderer.setBloomIntensity(bloomIntensity);
                }

                int bloomIterations = static_cast<int>(renderer.getBloomIterations());
                if (ImGui::SliderInt("Blur Iterations", &bloomIterations, 1, 10)) {
                    renderer.setBloomIterations(static_cast<u32>(bloomIterations));
                }

                // Presets
                ImGui::Text("Presets:");
                if (ImGui::Button("Subtle##bloom")) {
                    renderer.setBloomThreshold(1.5f);
                    renderer.setBloomIntensity(0.15f);
                    renderer.setBloomIterations(3);
                }
                ImGui::SameLine();
                if (ImGui::Button("Medium##bloom")) {
                    renderer.setBloomThreshold(1.0f);
                    renderer.setBloomIntensity(0.3f);
                    renderer.setBloomIterations(5);
                }
                ImGui::SameLine();
                if (ImGui::Button("Strong##bloom")) {
                    renderer.setBloomThreshold(0.5f);
                    renderer.setBloomIntensity(0.5f);
                    renderer.setBloomIterations(7);
                }
            }
        }

        ImGui::Separator();

        // Tonemapping Settings
        if (ImGui::CollapsingHeader("Tonemapping", ImGuiTreeNodeFlags_DefaultOpen)) {
            float exposure = renderer.getExposure();
            if (ImGui::SliderFloat("Exposure", &exposure, 0.1f, 5.0f, "%.2f")) {
                renderer.setExposure(exposure);
            }

            const char* tonemapModes[] = { "Reinhard", "ACES Filmic", "Uncharted 2" };
            int currentMode = static_cast<int>(renderer.getTonemapMode());
            if (ImGui::Combo("Tonemap Mode", &currentMode, tonemapModes, IM_ARRAYSIZE(tonemapModes))) {
                renderer.setTonemapMode(static_cast<u32>(currentMode));
            }

            // Exposure presets
            ImGui::Text("Exposure Presets:");
            if (ImGui::Button("Indoor")) {
                renderer.setExposure(1.5f);
            }
            ImGui::SameLine();
            if (ImGui::Button("Outdoor")) {
                renderer.setExposure(1.0f);
            }
            ImGui::SameLine();
            if (ImGui::Button("Bright")) {
                renderer.setExposure(0.7f);
            }
        }

        ImGui::Separator();

        // PBR Material Settings
        if (ImGui::CollapsingHeader("Material Properties", ImGuiTreeNodeFlags_DefaultOpen)) {
            // Wall Materials
            if (ImGui::TreeNode("Wall Material")) {
                float wallMetallic = renderer.getWallMetallic();
                if (ImGui::SliderFloat("Metallic##wall", &wallMetallic, 0.0f, 1.0f, "%.2f")) {
                    renderer.setWallMetallic(wallMetallic);
                }

                float wallRoughness = renderer.getWallRoughness();
                if (ImGui::SliderFloat("Roughness##wall", &wallRoughness, 0.04f, 1.0f, "%.2f")) {
                    renderer.setWallRoughness(wallRoughness);
                }

                // Wall presets
                if (ImGui::Button("Concrete##wall")) {
                    renderer.setWallMetallic(0.0f);
                    renderer.setWallRoughness(0.9f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Stucco##wall")) {
                    renderer.setWallMetallic(0.0f);
                    renderer.setWallRoughness(0.8f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Brick##wall")) {
                    renderer.setWallMetallic(0.0f);
                    renderer.setWallRoughness(0.85f);
                }
                ImGui::TreePop();
            }

            // Roof Materials
            if (ImGui::TreeNode("Roof Material")) {
                float roofMetallic = renderer.getRoofMetallic();
                if (ImGui::SliderFloat("Metallic##roof", &roofMetallic, 0.0f, 1.0f, "%.2f")) {
                    renderer.setRoofMetallic(roofMetallic);
                }

                float roofRoughness = renderer.getRoofRoughness();
                if (ImGui::SliderFloat("Roughness##roof", &roofRoughness, 0.04f, 1.0f, "%.2f")) {
                    renderer.setRoofRoughness(roofRoughness);
                }

                // Roof presets
                if (ImGui::Button("Shingle##roof")) {
                    renderer.setRoofMetallic(0.0f);
                    renderer.setRoofRoughness(0.8f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Metal##roof")) {
                    renderer.setRoofMetallic(0.9f);
                    renderer.setRoofRoughness(0.3f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Tile##roof")) {
                    renderer.setRoofMetallic(0.0f);
                    renderer.setRoofRoughness(0.6f);
                }
                ImGui::TreePop();
            }

            // Default/Other Materials
            if (ImGui::TreeNode("Other Elements")) {
                float metallic = renderer.getDefaultMetallic();
                if (ImGui::SliderFloat("Metallic##default", &metallic, 0.0f, 1.0f, "%.2f")) {
                    renderer.setDefaultMetallic(metallic);
                }

                float roughness = renderer.getDefaultRoughness();
                if (ImGui::SliderFloat("Roughness##default", &roughness, 0.04f, 1.0f, "%.2f")) {
                    renderer.setDefaultRoughness(roughness);
                }

                if (ImGui::Button("Steel##default")) {
                    renderer.setDefaultMetallic(0.95f);
                    renderer.setDefaultRoughness(0.4f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Wood##default")) {
                    renderer.setDefaultMetallic(0.0f);
                    renderer.setDefaultRoughness(0.7f);
                }
                ImGui::SameLine();
                if (ImGui::Button("Concrete##default")) {
                    renderer.setDefaultMetallic(0.0f);
                    renderer.setDefaultRoughness(0.9f);
                }
                ImGui::TreePop();
            }
        }

        ImGui::Separator();

        // Section Clipping Settings
        if (ImGui::CollapsingHeader("Section Clipping", ImGuiTreeNodeFlags_DefaultOpen)) {
            bool clippingEnabled = renderer.getClippingEnabled();
            if (ImGui::Checkbox("Enable Section Cut", &clippingEnabled)) {
                renderer.setClippingEnabled(clippingEnabled);
            }

            if (clippingEnabled) {
                // Axis selection
                const char* axisNames[] = { "X (Left/Right)", "Y (Up/Down)", "Z (Front/Back)" };
                int clipAxis = renderer.getClipAxis();
                if (ImGui::Combo("Cut Axis", &clipAxis, axisNames, 3)) {
                    renderer.setClipAxis(clipAxis);
                }

                // Height/position slider
                float clipHeight = renderer.getClipHeight();
                const char* heightLabel = "Cut Position";
                float minVal = -100.0f;
                float maxVal = 100.0f;

                switch (clipAxis) {
                    case 0: heightLabel = "X Position (ft)"; break;
                    case 1: heightLabel = "Y Position (ft)"; minVal = 0.0f; maxVal = 50.0f; break;
                    case 2: heightLabel = "Z Position (ft)"; break;
                }

                if (ImGui::SliderFloat(heightLabel, &clipHeight, minVal, maxVal, "%.1f")) {
                    renderer.setClipHeight(clipHeight);
                }

                // Flip direction
                bool flipped = renderer.getClipFlipped();
                if (ImGui::Checkbox("Flip Cut Direction", &flipped)) {
                    renderer.setClipFlipped(flipped);
                }

                ImGui::Separator();

                // Quick section presets
                ImGui::Text("Quick Sections:");
                if (ImGui::Button("Floor Plan (Y=4ft)")) {
                    renderer.setClipAxis(1);
                    renderer.setClipHeight(4.0f);
                    renderer.setClipFlipped(false);
                }
                ImGui::SameLine();
                if (ImGui::Button("Roof Plan (Y=10ft)")) {
                    renderer.setClipAxis(1);
                    renderer.setClipHeight(10.0f);
                    renderer.setClipFlipped(false);
                }

                if (ImGui::Button("Section A-A (X=0)")) {
                    renderer.setClipAxis(0);
                    renderer.setClipHeight(0.0f);
                    renderer.setClipFlipped(false);
                }
                ImGui::SameLine();
                if (ImGui::Button("Section B-B (Z=0)")) {
                    renderer.setClipAxis(2);
                    renderer.setClipHeight(0.0f);
                    renderer.setClipFlipped(false);
                }

                ImGui::Separator();

                // Help text
                ImGui::TextWrapped("Section clipping cuts away geometry to show interior views. "
                                   "Use Y axis for floor plans, X/Z for building sections.");
            }
        }

        ImGui::Separator();

        // Visualization mode (moved from elsewhere for convenience)
        if (ImGui::CollapsingHeader("Visualization")) {
            VisualizationMode mode = renderer.getVisualizationMode();
            const char* modeNames[] = { "Structural", "Thermal", "Lighting", "Acoustic", "Material", "Wireframe" };
            int currentMode = static_cast<int>(mode);
            if (ImGui::Combo("Mode", &currentMode, modeNames, 6)) {
                renderer.setVisualizationMode(static_cast<VisualizationMode>(currentMode));
            }
        }
    }
    ImGui::End();
}

} // namespace arch
