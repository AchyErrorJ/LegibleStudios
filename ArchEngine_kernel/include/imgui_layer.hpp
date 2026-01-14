#pragma once

#include "types.hpp"
#include "vulkan_context.hpp"
#include <imgui.h>
#include <string>
#include <set>
#include <vector>
#include <imgui_impl_glfw.h>
#include <imgui_impl_vulkan.h>

struct GLFWwindow;

namespace arch {

// Forward declarations
struct Building;
struct FrameAnalysis;
class Renderer;

// Drawing modes for geometry creation
enum class DrawMode {
    None,           // Normal selection mode
    DrawWall,       // Click to place wall start/end
    DrawRoom,       // Click to place room corners
    DrawFloor       // Click to place floor corners
};

class ImGuiLayer {
public:
    struct MaterialGenerateRequest {
        std::string name;
        std::string prompt;
        std::string negativePrompt;
        std::string serverUrl;
        std::string pythonExe;
        std::string scriptPath;
        std::string outputRoot;
        int size = 1024;
        int steps = 30;
        float guidance = 7.5f;
        bool tileable = true;
    };

    struct MaterialUpscaleRequest {
        std::string materialName;
        std::string serverUrl;
        std::string pythonExe;
        std::string scriptPath;
        std::string materialRoot;
        int scale = 4;      // 2 or 4
        int method = 0;     // 0=realesrgan, 1=lanczos
    };

    struct HeightGenRequest {
        std::string materialName;
        std::string materialPath;
        std::string serverUrl;
        int method = 0;     // 0=hybrid, 1=normal, 2=diffuse
        float blur = 1.0f;
        float contrast = 1.0f;
        bool invert = false;
    };

    struct HighResRenderRequest {
        std::string outputPath;
        int resolution = 0;     // 0=4K, 1=6K, 2=8K
        int samples = 1;        // 1, 16, 64, 256
        int format = 0;         // 0=PNG, 1=EXR
        bool upscale = false;   // If true, render at 4K and upscale to target
        int upscaleMethod = 0;  // 0=realesrgan, 1=lanczos
        float brightness = 1.0f; // Brightness multiplier (1.0 = match viewport)
        int postProcessPreset = 0; // 0=none, 1=subtle, 2=vivid, 3=warm, 4=architectural, 5=golden_hour, 6=print_ready
        // Manual post-process overrides (negative = use preset values)
        float postExposure = -1.0f;
        float postContrast = -1.0f;
        float postSaturation = -1.0f;
        float postVibrance = -1.0f;
        float postSharpness = -1.0f;
        float postVignette = -1.0f;
    };

    ImGuiLayer(VulkanContext& context, GLFWwindow* window, VkRenderPass renderPass);
    ~ImGuiLayer();

    // Non-copyable
    ImGuiLayer(const ImGuiLayer&) = delete;
    ImGuiLayer& operator=(const ImGuiLayer&) = delete;

    // Frame lifecycle
    void beginFrame();
    void endFrame(VkCommandBuffer cmd);

    // UI Panels
    void drawMainMenuBar(VisualizationMode& mode, bool& showDemo, bool& showMetrics);
    void drawBuildingPanel(const Building& building, size_t currentIndex, size_t totalBuildings);
    void drawPhysicsPanel(const FrameAnalysis& analysis, bool physicsAvailable);
    void drawVisualizationPanel(VisualizationMode& mode, Renderer& renderer);
    void drawHelpPanel(bool& show);
    void drawPerformancePanel(f32 fps, u32 drawCalls, u32 triangles, u32 culledElements = 0);
    void drawRenderSettingsPanel(Renderer& renderer, bool& show);
    void drawGeometryEditor(bool& show);

    // Geometry editor state
    struct NewElement {
        int type = 0;  // 0=Beam, 1=Column, 2=Floor, 3=Wall, 4=Door, 5=Window, 6=Roof
        float start[3] = {0, 0, 0};
        float end[3] = {10, 0, 0};
        float width = 0.5f;
        float depth = 1.0f;
        int materialIndex = 0;
        int wallTypeIndex = 0;  // 0=2x6 Exterior, 1=2x4 Exterior, 2=Interior
        float wallHeight = 10.0f;
    };
    NewElement& getNewElement() { return m_newElement; }

    // File operations
    bool wasLoadRequested() const { return m_loadRequested; }
    bool wasSaveRequested() const { return m_saveRequested; }
    bool wasAddElementRequested() const { return m_addElementRequested; }
    void clearLoadRequest() { m_loadRequested = false; }
    void clearSaveRequest() { m_saveRequested = false; }
    void clearAddElementRequest() { m_addElementRequested = false; }
    const std::string& getFilePath() const { return m_filePath; }
    void setFilePath(const std::string& path) { m_filePath = path; }

    // Wall editing
    void drawWallEditor(Building& building, bool show);
    bool wasExtendWallRequested() const { return m_extendWallRequested; }
    void clearExtendWallRequest() { m_extendWallRequested = false; }
    int getSelectedWallIndex() const { return m_selectedWallIndex; }
    float getWallExtendHeight() const { return m_wallExtendHeight; }
    void setSelectedWallByElementIndex(int elemIdx) { m_selectedElements.clear(); m_selectedElements.insert(elemIdx); }
    const std::set<int>& getSelectedElements() const { return m_selectedElements; }
    void addToSelection(int idx) { m_selectedElements.insert(idx); }
    void removeFromSelection(int idx) { m_selectedElements.erase(idx); }
    void clearSelection() { m_selectedElements.clear(); }
    void setSelection(int idx) { m_selectedElements.clear(); m_selectedElements.insert(idx); }
    bool isSelected(int idx) const { return m_selectedElements.count(idx) > 0; }
    int getSelectedRoofIndex() const { return m_selectedRoofIdx; }
    void setSelectedRoofIndex(int idx) { m_selectedRoofIdx = idx; }
    void clearRoofSelection() { m_selectedRoofIdx = -1; }

    // Boolean operations (CSG)
    bool wasUnionRequested() const { return m_unionRequested; }
    void clearUnionRequest() { m_unionRequested = false; }

    // Drawing mode for interactive geometry creation
    DrawMode getDrawMode() const { return m_drawMode; }
    void setDrawMode(DrawMode mode) { m_drawMode = mode; m_drawPoints.clear(); }
    bool isDrawing() const { return m_drawMode != DrawMode::None; }

    // Drawing state - points clicked so far
    const std::vector<vec3>& getDrawPoints() const { return m_drawPoints; }
    void addDrawPoint(vec3 point) { m_drawPoints.push_back(point); }
    void clearDrawPoints() { m_drawPoints.clear(); }
    bool hasDrawPointStart() const { return !m_drawPoints.empty(); }

    // Check if wall creation is ready (2 points for wall)
    bool isWallDrawComplete() const { return m_drawMode == DrawMode::DrawWall && m_drawPoints.size() >= 2; }

    // Get parametric wall creation request
    bool wasParametricWallRequested() const { return m_parametricWallRequested; }
    void clearParametricWallRequest() { m_parametricWallRequested = false; }
    void requestParametricWall() { m_parametricWallRequested = true; }

    // State
    bool wantCaptureMouse() const;
    bool wantCaptureKeyboard() const;

    // UI action flags
    bool wasAnalysisRequested() const { return m_analysisRequested; }
    void clearAnalysisRequest() { m_analysisRequested = false; }

    // Camera view controls
    bool wasCameraViewRequested() const { return m_cameraViewRequested; }
    void clearCameraViewRequest() { m_cameraViewRequested = false; }
    CameraView getRequestedCameraView() const { return m_requestedCameraView; }

    // Material UI actions
    bool wasApplyMaterialRequested() const { return m_applyMaterialRequested; }
    const std::string& getApplyMaterialName() const { return m_applyMaterialName; }
    void clearApplyMaterialRequest() { m_applyMaterialRequested = false; }
    bool takeMaterialDrop(std::string& outName);

    bool wasMaterialGenerateRequested() const { return m_materialGenerateRequested; }
    MaterialGenerateRequest takeMaterialGenerateRequest();
    void setMaterialGenerationState(bool inFlight, const std::string& status);
    bool wasStartRenderServerRequested() const { return m_startRenderServerRequested; }
    void clearStartRenderServerRequest() { m_startRenderServerRequested = false; }
    bool wasStopRenderServerRequested() const { return m_stopRenderServerRequested; }
    void clearStopRenderServerRequest() { m_stopRenderServerRequested = false; }
    int getRenderServerPort() const { return m_renderServerPort; }

    // Material upscaling
    bool wasMaterialUpscaleRequested() const { return m_materialUpscaleRequested; }
    MaterialUpscaleRequest takeMaterialUpscaleRequest();
    void setMaterialUpscaleState(bool inFlight, const std::string& status);

    // Height map generation
    bool wasHeightGenRequested() const { return m_heightGenRequested; }
    HeightGenRequest takeHeightGenRequest();
    void setHeightGenState(bool inFlight, const std::string& status);

    // High-res rendering
    bool wasHighResRenderRequested() const { return m_highResRenderRequested; }
    HighResRenderRequest takeHighResRenderRequest();
    void setHighResRenderState(bool inFlight, const std::string& status, float progress = 0.0f);
    float getHighResRenderProgress() const { return m_highResRenderProgress; }

private:
    void createDescriptorPool();
    void uploadFonts();

    VulkanContext& m_context;
    bool m_analysisRequested = false;
    bool m_cameraViewRequested = false;
    CameraView m_requestedCameraView = CameraView::Perspective;
    bool m_loadRequested = false;
    bool m_saveRequested = false;
    bool m_addElementRequested = false;
    std::string m_filePath;
    NewElement m_newElement;
    VkDescriptorPool m_imguiPool = VK_NULL_HANDLE;
    bool m_initialized = false;

    // Wall editing state
    bool m_extendWallRequested = false;
    int m_selectedWallIndex = -1;
    float m_wallExtendHeight = 0.0f;
    std::set<int> m_selectedElements;
    int m_selectedRoofIdx = -1;

    // Boolean operations
    bool m_unionRequested = false;

    // Drawing mode state
    DrawMode m_drawMode = DrawMode::None;
    std::vector<vec3> m_drawPoints;
    bool m_parametricWallRequested = false;

    // Material UI state
    bool m_materialUiInitialized = false;
    int m_materialListIndex = -1;
    char m_materialFilter[96] = "";
    char m_materialRoot[260] = "materials";
    char m_materialOutputRoot[260] = "materials";
    char m_materialName[128] = "";
    char m_materialPrompt[512] = "";
    char m_materialNegative[256] = "blurry, low quality, distorted, watermark";
    char m_materialServerUrl[256] = "http://localhost:5000";
    char m_materialPythonExe[260] = "C:\\RevitMCP\\.venv-sd\\Scripts\\python.exe";
    char m_materialScriptPath[260] = "scripts/material_generate.py";
    int m_materialSize = 1024;
    int m_materialSteps = 30;
    float m_materialGuidance = 7.5f;
    bool m_materialTileable = true;
    int m_renderServerPort = 5000;
    bool m_applyMaterialRequested = false;
    std::string m_applyMaterialName;
    bool m_materialDropRequested = false;
    std::string m_materialDropName;
    bool m_materialDragActive = false;
    std::string m_materialDragName;
    bool m_materialGenerateRequested = false;
    MaterialGenerateRequest m_materialGenerateRequest;
    bool m_materialGenerateInFlight = false;
    std::string m_materialGenerateStatus;
    bool m_startRenderServerRequested = false;
    bool m_stopRenderServerRequested = false;

    // Material upscale state
    bool m_materialUpscaleRequested = false;
    MaterialUpscaleRequest m_materialUpscaleRequest;
    bool m_materialUpscaleInFlight = false;
    std::string m_materialUpscaleStatus;
    int m_upscaleScale = 4;
    int m_upscaleMethod = 0;

    // Height map generation state
    bool m_heightGenRequested = false;
    HeightGenRequest m_heightGenRequest;
    bool m_heightGenInFlight = false;
    std::string m_heightGenStatus;
    int m_heightGenMethod = 0;      // 0=hybrid, 1=normal, 2=diffuse
    float m_heightGenBlur = 1.0f;
    float m_heightGenContrast = 1.0f;
    bool m_heightGenInvert = false;

    // High-res render state
    bool m_highResRenderRequested = false;
    HighResRenderRequest m_highResRenderRequest;
    bool m_highResRenderInFlight = false;
    std::string m_highResRenderStatus;
    float m_highResRenderProgress = 0.0f;
    int m_renderResolution = 0;     // 0=4K, 1=6K, 2=8K
    int m_renderSamples = 0;        // 0=1, 1=16, 2=64, 3=256
    int m_renderFormat = 0;         // 0=PNG, 1=EXR
    bool m_renderUpscale = false;
    int m_renderUpscaleMethod = 0;
    float m_renderBrightness = 1.0f; // Brightness multiplier (1.0 = match viewport)
    int m_renderPostProcess = 4;    // 0=none, 1=subtle, 2=vivid, 3=warm, 4=architectural, 5=golden_hour, 6=print_ready
    char m_renderOutputPath[260] = "renders/render.png";

    // Post-process manual adjustments (negative = use preset)
    float m_postExposure = -1.0f;
    float m_postContrast = -1.0f;
    float m_postSaturation = -1.0f;
    float m_postVibrance = -1.0f;
    float m_postSharpness = -1.0f;
    float m_postVignette = -1.0f;
    bool m_showPostProcessAdvanced = false;

public:
    float getRenderBrightness() const { return m_renderBrightness; }
};

} // namespace arch
