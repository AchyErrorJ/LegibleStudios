# Add render settings panel to imgui_layer.cpp

$imguiCpp = "X:\arch\Software\Archengine_suite_kernel\ArchEngine_kernel\src\imgui_layer.cpp"
$cppContent = Get-Content $imguiCpp -Raw

# Add include for renderer at top
$oldIncludes = @"
#include "imgui_layer.hpp"
#include "physics_bridge.hpp"
"@

$newIncludes = @"
#include "imgui_layer.hpp"
#include "physics_bridge.hpp"
#include "renderer.hpp"
"@

$cppContent = $cppContent.Replace($oldIncludes, $newIncludes)

# Add the render settings panel function before the end of namespace
$oldNamespaceEnd = @"
} // namespace arch
"@

$newNamespaceEnd = @"
void ImGuiLayer::drawRenderSettingsPanel(Renderer& renderer, bool& show) {
    if (!show) return;

    ImGui::SetNextWindowSize(ImVec2(320, 400), ImGuiCond_FirstUseEver);
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
"@

$cppContent = $cppContent.Replace($oldNamespaceEnd, $newNamespaceEnd)

Set-Content $imguiCpp -Value $cppContent -NoNewline
Write-Host "Updated imgui_layer.cpp with render settings panel"
