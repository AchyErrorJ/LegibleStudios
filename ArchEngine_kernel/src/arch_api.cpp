/**
 * ArchEngine C API Implementation
 *
 * Wraps the Vulkan renderer for embedding in Qt/Python applications.
 */

#include "arch_api.h"

#include "types.hpp"
#include "vulkan_context.hpp"
#include "renderer.hpp"
#include "qbd_interface.hpp"
#include "path_tracer.hpp"

#include <memory>
#include <string>
#include <cstring>
#include <mutex>
#include <iostream>
#include <set>

#ifdef _WIN32
#define VK_USE_PLATFORM_WIN32_KHR
#include <windows.h>
#include <vulkan/vulkan.h>
#include <vulkan/vulkan_win32.h>
#endif

using namespace arch;

// Global state
namespace {
    std::unique_ptr<VulkanContext> g_context;
    std::unique_ptr<Renderer> g_renderer;
    std::unique_ptr<PathTracer> g_pathTracer;
    Building g_building;
    qbd::QBDLayout g_layout;  // Store layout for room access
    PathTracerConfig g_ptConfig;  // Path tracer configuration

    // Camera state
    float g_cameraYaw = 0.5f;
    float g_cameraPitch = 0.4f;
    float g_cameraDistance = 60.0f;
    vec3 g_cameraTarget = {20.0f, 10.0f, 15.0f};
    float g_cameraFOV = 45.0f;
    bool g_cameraOrthographic = false;

    // State
    bool g_initialized = false;
    int g_width = 800;
    int g_height = 600;
    int g_selectedElement = -1;
    VisualizationMode g_vizMode = VisualizationMode::Material;
    bool g_terrainEnabled = true;  // Terrain rendering enabled by default

    // Error handling
    std::string g_lastError;
    std::mutex g_mutex;

    // Vulkan handles for embedded mode
    VkInstance g_instance = VK_NULL_HANDLE;
    VkSurfaceKHR g_surface = VK_NULL_HANDLE;

    void setError(const std::string& error) {
        g_lastError = error;
        std::cerr << "[ArchAPI] Error: " << error << std::endl;
    }

    void updateCamera() {
        if (!g_renderer) return;

        Camera camera;
        camera.position.x = g_cameraTarget.x + g_cameraDistance * cos(g_cameraPitch) * sin(g_cameraYaw);
        camera.position.y = g_cameraTarget.y + g_cameraDistance * sin(g_cameraPitch);
        camera.position.z = g_cameraTarget.z + g_cameraDistance * cos(g_cameraPitch) * cos(g_cameraYaw);
        camera.target = g_cameraTarget;
        camera.up = vec3(0, 1, 0);
        camera.fov = g_cameraFOV;
        camera.nearPlane = 0.1f;
        camera.farPlane = 100000.0f;  // Large value to handle mm units
        camera.isOrthographic = g_cameraOrthographic;
        camera.orthoSize = g_cameraDistance * 0.5f;  // Scale ortho based on distance

        g_renderer->setCamera(camera);
    }
}

extern "C" {

ARCH_API int arch_init(void* hwnd, int width, int height) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (g_initialized) {
        setError("Already initialized");
        return -1;
    }

    try {
        g_width = width;
        g_height = height;

#ifdef _WIN32
        HWND hWnd = static_cast<HWND>(hwnd);

        // Create Vulkan instance
        VkApplicationInfo appInfo{};
        appInfo.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
        appInfo.pApplicationName = "ArchEngine";
        appInfo.applicationVersion = VK_MAKE_VERSION(1, 0, 0);
        appInfo.pEngineName = "ArchEngine";
        appInfo.engineVersion = VK_MAKE_VERSION(1, 0, 0);
        appInfo.apiVersion = VK_API_VERSION_1_2;

        std::vector<const char*> extensions = {
            VK_KHR_SURFACE_EXTENSION_NAME,
            VK_KHR_WIN32_SURFACE_EXTENSION_NAME
        };

        std::vector<const char*> layers;
#ifdef _DEBUG
        layers.push_back("VK_LAYER_KHRONOS_validation");
        extensions.push_back(VK_EXT_DEBUG_UTILS_EXTENSION_NAME);
#endif

        VkInstanceCreateInfo createInfo{};
        createInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
        createInfo.pApplicationInfo = &appInfo;
        createInfo.enabledExtensionCount = static_cast<uint32_t>(extensions.size());
        createInfo.ppEnabledExtensionNames = extensions.data();
        createInfo.enabledLayerCount = static_cast<uint32_t>(layers.size());
        createInfo.ppEnabledLayerNames = layers.data();

        if (vkCreateInstance(&createInfo, nullptr, &g_instance) != VK_SUCCESS) {
            setError("Failed to create Vulkan instance");
            return -2;
        }

        // Create Win32 surface
        VkWin32SurfaceCreateInfoKHR surfaceInfo{};
        surfaceInfo.sType = VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR;
        surfaceInfo.hwnd = hWnd;
        surfaceInfo.hinstance = GetModuleHandle(nullptr);

        if (vkCreateWin32SurfaceKHR(g_instance, &surfaceInfo, nullptr, &g_surface) != VK_SUCCESS) {
            setError("Failed to create window surface");
            vkDestroyInstance(g_instance, nullptr);
            g_instance = VK_NULL_HANDLE;
            return -3;
        }

        // Create Vulkan context with existing instance and surface
        VulkanConfig config{};
        config.enableValidation = false;  // Already set up
        config.maxFramesInFlight = 2;

        g_context = std::make_unique<VulkanContext>(g_instance, g_surface, width, height, config);
        g_renderer = std::make_unique<Renderer>(*g_context);

        // Initialize with empty building
        g_building.name = "Empty";

        g_initialized = true;
        std::cout << "[ArchAPI] Initialized " << width << "x" << height << std::endl;
        return 0;
#else
        setError("Only Windows is supported");
        return -4;
#endif
    }
    catch (const std::exception& e) {
        setError(std::string("Init failed: ") + e.what());
        return -5;
    }
}

ARCH_API int arch_init_headless(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (g_initialized) {
        setError("Already initialized");
        return -1;
    }

    try {
        // Create headless Vulkan context (no window/surface)
        VulkanConfig config{};
        config.enableValidation = false;
        config.headless = true;

        g_context = VulkanContext::createHeadless(config);
        // No renderer needed for headless path tracing
        // g_renderer is left null - only path tracer will be used

        // Initialize with empty building
        g_building.name = "Empty";

        g_initialized = true;
        std::cout << "[ArchAPI] Initialized in headless mode" << std::endl;
        return 0;
    }
    catch (const std::exception& e) {
        setError(std::string("Headless init failed: ") + e.what());
        return -1;
    }
}

ARCH_API void arch_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized) return;

    if (g_context) {
        g_context->waitIdle();
    }

    g_pathTracer.reset();
    g_renderer.reset();
    g_context.reset();

    if (g_surface != VK_NULL_HANDLE) {
        vkDestroySurfaceKHR(g_instance, g_surface, nullptr);
        g_surface = VK_NULL_HANDLE;
    }

    if (g_instance != VK_NULL_HANDLE) {
        vkDestroyInstance(g_instance, nullptr);
        g_instance = VK_NULL_HANDLE;
    }

    g_initialized = false;
    std::cout << "[ArchAPI] Shutdown complete" << std::endl;
}

ARCH_API int arch_is_initialized(void) {
    return g_initialized ? 1 : 0;
}

ARCH_API int arch_load_json(const char* json_str) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized) {
        setError("Not initialized");
        return -1;
    }

    try {
        // Clear mesh cache before loading new scene to prevent memory leaks
        if (g_renderer) {
            g_renderer->clearMeshCache();
        }

        auto& qbd = qbd::getQBDInterface();
        auto layoutOpt = qbd.loadFromJSON(std::string(json_str));

        if (!layoutOpt.has_value()) {
            setError("Failed to parse JSON");
            return -2;
        }

        g_layout = *layoutOpt;  // Store layout for room access
        g_building = qbd.toBuilding(g_layout);
        g_building.name = "Loaded Building";

        // Scale from mm to feet
        const float mmToFeet = 1.0f / 304.8f;
        for (auto& elem : g_building.elements) {
            elem.start *= mmToFeet;
            elem.end *= mmToFeet;
            elem.width *= mmToFeet;
            elem.depth *= mmToFeet;
            for (auto& v : elem.mesh.vertices) {
                v *= mmToFeet;
            }
        }

        std::cout << "[ArchAPI] Loaded building with " << g_building.elements.size() << " elements" << std::endl;

        // Reset camera to fit
        arch_reset_camera();

        return 0;
    }
    catch (const std::exception& e) {
        setError(std::string("Load failed: ") + e.what());
        return -3;
    }
}

ARCH_API int arch_load_file(const char* file_path) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized) {
        setError("Not initialized");
        return -1;
    }

    try {
        // Clear mesh cache before loading new scene to prevent memory leaks
        if (g_renderer) {
            g_renderer->clearMeshCache();
        }

        auto& qbd = qbd::getQBDInterface();
        auto layoutOpt = qbd.loadFromFile(std::string(file_path));

        if (!layoutOpt.has_value()) {
            setError("Failed to load file");
            return -2;
        }

        g_layout = *layoutOpt;  // Store layout for room access
        g_building = qbd.toBuilding(g_layout);
        g_building.name = file_path;

        // Scale from mm to feet
        const float mmToFeet = 1.0f / 304.8f;
        for (auto& elem : g_building.elements) {
            elem.start *= mmToFeet;
            elem.end *= mmToFeet;
            elem.width *= mmToFeet;
            elem.depth *= mmToFeet;
            for (auto& v : elem.mesh.vertices) {
                v *= mmToFeet;
            }
        }

        std::cout << "[ArchAPI] Loaded file: " << file_path << " (" << g_building.elements.size() << " elements)" << std::endl;

        arch_reset_camera();
        return 0;
    }
    catch (const std::exception& e) {
        setError(std::string("Load failed: ") + e.what());
        return -3;
    }
}

ARCH_API int arch_render_frame(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized || !g_renderer) {
        return -1;
    }

    try {
        updateCamera();

        if (g_renderer->beginFrame()) {
            // Render shadow pass
            g_renderer->renderShadowPass(g_building.elements);

            // Main render pass
            vec4 clearColor = {0.05f, 0.05f, 0.08f, 1.0f};
            g_renderer->beginRenderPass(clearColor);

            g_renderer->drawSky();
            g_renderer->drawGrid(150.0f, 5.0f);

            // Draw terrain if enabled
            if (g_terrainEnabled && g_building.terrainMesh.hasData()) {
                g_renderer->drawTerrain(g_building.terrainMesh);
            }

            // Draw building with selection
            std::set<int> selected;
            if (g_selectedElement >= 0) {
                selected.insert(g_selectedElement);
            }
            g_renderer->drawStructuralFrame(g_building.elements, g_building, selected);

            g_renderer->endRenderPass();
            g_renderer->endFrame();
        }

        return 0;
    }
    catch (const std::exception& e) {
        setError(std::string("Render failed: ") + e.what());
        return -2;
    }
}

ARCH_API void arch_resize(int width, int height) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized || width <= 0 || height <= 0) return;

    g_width = width;
    g_height = height;

    if (g_renderer) {
        g_renderer->onResize();
    }

    std::cout << "[ArchAPI] Resized to " << width << "x" << height << std::endl;
}

ARCH_API void arch_set_camera(float yaw, float pitch, float distance) {
    g_cameraYaw = yaw;
    g_cameraPitch = glm::clamp(pitch, -1.4f, 1.4f);
    g_cameraDistance = glm::clamp(distance, 10.0f, 500.0f);
}

ARCH_API void arch_set_camera_target(float x, float y, float z) {
    g_cameraTarget = vec3(x, y, z);
}

ARCH_API void arch_reset_camera(void) {
    if (g_building.elements.empty()) {
        g_cameraTarget = vec3(0, 0, 0);
        g_cameraDistance = 60.0f;
        return;
    }

    vec3 minBound(1e9f), maxBound(-1e9f);
    for (const auto& elem : g_building.elements) {
        minBound = glm::min(minBound, glm::min(elem.start, elem.end));
        maxBound = glm::max(maxBound, glm::max(elem.start, elem.end));
    }

    g_cameraTarget = (minBound + maxBound) * 0.5f;
    float size = glm::length(maxBound - minBound);
    g_cameraDistance = size * 1.5f;
    g_cameraYaw = 0.5f;
    g_cameraPitch = 0.4f;

    std::cout << "[Camera] Bounds: (" << minBound.x << ", " << minBound.y << ", " << minBound.z << ") to ("
              << maxBound.x << ", " << maxBound.y << ", " << maxBound.z << ")\n";
    std::cout << "[Camera] Target: (" << g_cameraTarget.x << ", " << g_cameraTarget.y << ", " << g_cameraTarget.z
              << "), Distance: " << g_cameraDistance << "\n";
}

ARCH_API void arch_set_camera_fov(float fov) {
    g_cameraFOV = glm::clamp(fov, 10.0f, 120.0f);
}

ARCH_API float arch_get_camera_fov(void) {
    return g_cameraFOV;
}

ARCH_API void arch_set_orthographic(int enabled) {
    g_cameraOrthographic = (enabled != 0);
}

ARCH_API int arch_get_orthographic(void) {
    return g_cameraOrthographic ? 1 : 0;
}

ARCH_API void arch_set_viz_mode(int mode) {
    if (mode >= 0 && mode <= 5) {
        g_vizMode = static_cast<VisualizationMode>(mode);
        if (g_renderer) {
            g_renderer->setVisualizationMode(g_vizMode);
        }
    }
}

ARCH_API void arch_select_element(int element_index) {
    g_selectedElement = element_index;
}

ARCH_API int arch_get_selected_element(void) {
    return g_selectedElement;
}

ARCH_API int arch_pick_element(int screen_x, int screen_y) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized || g_building.elements.empty()) {
        return -1;
    }

    // Convert screen coordinates to normalized device coordinates (-1 to 1)
    float ndcX = (2.0f * screen_x / g_width) - 1.0f;
    float ndcY = 1.0f - (2.0f * screen_y / g_height);  // Flip Y

    // Get camera position
    vec3 camPos;
    camPos.x = g_cameraTarget.x + g_cameraDistance * cos(g_cameraPitch) * sin(g_cameraYaw);
    camPos.y = g_cameraTarget.y + g_cameraDistance * sin(g_cameraPitch);
    camPos.z = g_cameraTarget.z + g_cameraDistance * cos(g_cameraPitch) * cos(g_cameraYaw);

    // Build view and projection matrices
    mat4 view = glm::lookAt(camPos, g_cameraTarget, vec3(0, 1, 0));
    mat4 proj;
    float aspect = float(g_width) / float(g_height);

    if (g_cameraOrthographic) {
        float orthoSize = g_cameraDistance * 0.5f;
        proj = glm::ortho(-orthoSize * aspect, orthoSize * aspect, -orthoSize, orthoSize, 0.1f, 500.0f);
    } else {
        proj = glm::perspective(glm::radians(g_cameraFOV), aspect, 0.1f, 500.0f);
    }

    // Inverse view-projection to get ray
    mat4 invViewProj = glm::inverse(proj * view);

    // Ray in world space
    vec4 rayStart4 = invViewProj * vec4(ndcX, ndcY, -1.0f, 1.0f);
    vec4 rayEnd4 = invViewProj * vec4(ndcX, ndcY, 1.0f, 1.0f);
    vec3 rayStart = vec3(rayStart4) / rayStart4.w;
    vec3 rayEnd = vec3(rayEnd4) / rayEnd4.w;
    vec3 rayDir = glm::normalize(rayEnd - rayStart);

    // Test ray against each element's AABB
    int closestElement = -1;
    float closestDist = 1e9f;

    for (size_t i = 0; i < g_building.elements.size(); ++i) {
        const auto& elem = g_building.elements[i];

        // Compute element AABB
        vec3 minB = glm::min(elem.start, elem.end);
        vec3 maxB = glm::max(elem.start, elem.end);

        // Expand by element width/depth (approximate)
        float halfW = elem.width * 0.5f + 0.1f;
        float halfD = elem.depth * 0.5f + 0.1f;
        minB -= vec3(halfW, 0, halfD);
        maxB += vec3(halfW, elem.depth, halfD);

        // Ray-AABB intersection test (slab method)
        vec3 invDir = 1.0f / rayDir;
        vec3 t1 = (minB - rayStart) * invDir;
        vec3 t2 = (maxB - rayStart) * invDir;

        vec3 tMin = glm::min(t1, t2);
        vec3 tMax = glm::max(t1, t2);

        float tNear = glm::max(glm::max(tMin.x, tMin.y), tMin.z);
        float tFar = glm::min(glm::min(tMax.x, tMax.y), tMax.z);

        if (tNear <= tFar && tFar > 0) {
            float dist = tNear > 0 ? tNear : tFar;
            if (dist < closestDist) {
                closestDist = dist;
                closestElement = static_cast<int>(i);
            }
        }
    }

    return closestElement;
}

ARCH_API int arch_get_element_count(void) {
    return static_cast<int>(g_building.elements.size());
}

ARCH_API const char* arch_get_error(void) {
    return g_lastError.c_str();
}

// =============================================================================
// Section Clipping API
// =============================================================================

ARCH_API void arch_set_clipping_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setClippingEnabled(enabled != 0);
    }
}

ARCH_API int arch_get_clipping_enabled(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_renderer && g_renderer->getClippingEnabled()) ? 1 : 0;
}

ARCH_API void arch_set_clip_axis(int axis) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && axis >= 0 && axis <= 2) {
        g_renderer->setClipAxis(axis);
    }
}

ARCH_API int arch_get_clip_axis(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getClipAxis() : 1;
}

ARCH_API void arch_set_clip_height(float height) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setClipHeight(height);
    }
}

ARCH_API float arch_get_clip_height(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getClipHeight() : 0.0f;
}

ARCH_API void arch_set_clip_flipped(int flipped) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setClipFlipped(flipped != 0);
    }
}

ARCH_API int arch_get_clip_flipped(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_renderer && g_renderer->getClipFlipped()) ? 1 : 0;
}

ARCH_API void arch_set_section_floor_plan(float y_height) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setClipAxis(1);  // Y axis
        g_renderer->setClipHeight(y_height);
        g_renderer->setClipFlipped(false);
        g_renderer->setClippingEnabled(true);
    }
}

ARCH_API void arch_set_section_elevation(int axis, float position) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && (axis == 0 || axis == 2)) {
        g_renderer->setClipAxis(axis);
        g_renderer->setClipHeight(position);
        g_renderer->setClipFlipped(false);
        g_renderer->setClippingEnabled(true);
    }
}

// =============================================================================
// Material Style API
// =============================================================================

ARCH_API void arch_set_material_style(int style) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && style >= 0 && style <= 3) {
        g_renderer->setMaterialStyle(static_cast<MaterialStyle>(style));
    }
}

ARCH_API int arch_get_material_style(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? static_cast<int>(g_renderer->getMaterialStyle()) : 1; // Default: Clean
}

ARCH_API void arch_set_uv_scale(float scale_u, float scale_v) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        // Use average of U and V for now (renderer uses single scale)
        g_renderer->setMaterialUVScale((scale_u + scale_v) * 0.5f);
    }
}

ARCH_API void arch_get_uv_scale(float* out_u, float* out_v) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && out_u && out_v) {
        float scale = g_renderer->getMaterialUVScale();
        *out_u = scale;
        *out_v = scale;
    }
}

ARCH_API void arch_set_roughness_multiplier(float multiplier) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        // Use offset: multiplier 1.0 = offset 0, multiplier 0.5 = offset -0.5, etc.
        g_renderer->setMaterialRoughnessOffset(multiplier - 1.0f);
    }
}

ARCH_API float arch_get_roughness_multiplier(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? (g_renderer->getMaterialRoughnessOffset() + 1.0f) : 1.0f;
}

ARCH_API void arch_set_metallic_multiplier(float multiplier) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setMaterialMetallicOffset(multiplier - 1.0f);
    }
}

ARCH_API float arch_get_metallic_multiplier(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? (g_renderer->getMaterialMetallicOffset() + 1.0f) : 1.0f;
}

ARCH_API void arch_set_ao_strength(float strength) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setMaterialAOStrength(strength);
    }
}

ARCH_API float arch_get_ao_strength(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getMaterialAOStrength() : 1.0f;
}

// =============================================================================
// Shadows & Lighting API
// =============================================================================

ARCH_API void arch_set_shadows_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setShadowsEnabled(enabled != 0);
    }
}

ARCH_API int arch_get_shadows_enabled(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_renderer && g_renderer->getShadowsEnabled()) ? 1 : 0;
}

ARCH_API void arch_set_light_direction(float x, float y, float z) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setLightDirection(vec3(x, y, z));
    }
}

ARCH_API void arch_get_light_direction(float* out_x, float* out_y, float* out_z) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && out_x && out_y && out_z) {
        const vec3& dir = g_renderer->getLightDirection();
        *out_x = dir.x;
        *out_y = dir.y;
        *out_z = dir.z;
    }
}

// =============================================================================
// SSAO API
// =============================================================================

ARCH_API void arch_set_ssao_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setSSAOEnabled(enabled != 0);
    }
}

ARCH_API int arch_get_ssao_enabled(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_renderer && g_renderer->getSSAOEnabled()) ? 1 : 0;
}

ARCH_API void arch_set_ssao_radius(float radius) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setSSAORadius(radius);
    }
}

ARCH_API float arch_get_ssao_radius(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getSSAORadius() : 0.5f;
}

ARCH_API void arch_set_ssao_intensity(float intensity) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setSSAOIntensity(intensity);
    }
}

ARCH_API float arch_get_ssao_intensity(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getSSAOIntensity() : 1.0f;
}

// =============================================================================
// Bloom API
// =============================================================================

ARCH_API void arch_set_bloom_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setBloomEnabled(enabled != 0);
    }
}

ARCH_API int arch_get_bloom_enabled(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_renderer && g_renderer->getBloomEnabled()) ? 1 : 0;
}

ARCH_API void arch_set_bloom_threshold(float threshold) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setBloomThreshold(threshold);
    }
}

ARCH_API float arch_get_bloom_threshold(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getBloomThreshold() : 1.0f;
}

ARCH_API void arch_set_bloom_intensity(float intensity) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setBloomIntensity(intensity);
    }
}

ARCH_API float arch_get_bloom_intensity(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getBloomIntensity() : 0.5f;
}

// =============================================================================
// Tonemapping & Exposure API
// =============================================================================

ARCH_API void arch_set_exposure(float exposure) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->setExposure(exposure);
    }
}

ARCH_API float arch_get_exposure(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? g_renderer->getExposure() : 1.0f;
}

ARCH_API void arch_set_tonemap_mode(int mode) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer && mode >= 0 && mode <= 2) {
        g_renderer->setTonemapMode(static_cast<u32>(mode));
    }
}

ARCH_API int arch_get_tonemap_mode(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_renderer ? static_cast<int>(g_renderer->getTonemapMode()) : 1; // Default: ACES
}

// =============================================================================
// Room Data Export API
// =============================================================================

ARCH_API int arch_get_room_count(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return static_cast<int>(g_layout.rooms.size());
}

ARCH_API int arch_get_room_data(int index, ArchRoomData* out_room) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!out_room) return -1;
    if (index < 0 || index >= static_cast<int>(g_layout.rooms.size())) return -2;

    // Get room by index (iterate the map)
    auto it = g_layout.rooms.begin();
    std::advance(it, index);

    const auto& room = it->second;

    // Copy strings safely
    strncpy(out_room->id, room.id.c_str(), sizeof(out_room->id) - 1);
    out_room->id[sizeof(out_room->id) - 1] = '\0';

    strncpy(out_room->name, room.name.c_str(), sizeof(out_room->name) - 1);
    out_room->name[sizeof(out_room->name) - 1] = '\0';

    strncpy(out_room->room_type, room.roomType.c_str(), sizeof(out_room->room_type) - 1);
    out_room->room_type[sizeof(out_room->room_type) - 1] = '\0';

    // Copy bounds (in mm)
    out_room->bounds_x = room.bounds.x;
    out_room->bounds_y = room.bounds.y;
    out_room->bounds_width = room.bounds.width;
    out_room->bounds_height = room.bounds.height;

    // Copy center (in mm)
    out_room->center_x = room.center.x;
    out_room->center_y = room.center.y;

    out_room->area = room.area;
    out_room->zone = static_cast<int>(room.zone);

    return 0;
}

ARCH_API int arch_get_all_rooms(ArchRoomData* out_rooms, int max_rooms) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!out_rooms || max_rooms <= 0) return 0;

    int count = 0;
    for (const auto& [id, room] : g_layout.rooms) {
        if (count >= max_rooms) break;

        ArchRoomData& out = out_rooms[count];

        strncpy(out.id, room.id.c_str(), sizeof(out.id) - 1);
        out.id[sizeof(out.id) - 1] = '\0';

        strncpy(out.name, room.name.c_str(), sizeof(out.name) - 1);
        out.name[sizeof(out.name) - 1] = '\0';

        strncpy(out.room_type, room.roomType.c_str(), sizeof(out.room_type) - 1);
        out.room_type[sizeof(out.room_type) - 1] = '\0';

        out.bounds_x = room.bounds.x;
        out.bounds_y = room.bounds.y;
        out.bounds_width = room.bounds.width;
        out.bounds_height = room.bounds.height;
        out.center_x = room.center.x;
        out.center_y = room.center.y;
        out.area = room.area;
        out.zone = static_cast<int>(room.zone);

        count++;
    }

    return count;
}

// =============================================================================
// Per-Element Material Override Implementation
// =============================================================================

ARCH_API int arch_set_element_material(int element_index,
                                       float uv_scale,
                                       float normal_strength,
                                       float brightness,
                                       float contrast) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return -1;
    }

    if (element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        setError("Invalid element index");
        return -2;
    }

    // Build override mask
    u32 mask = 0;
    if (uv_scale != 1.0f) mask |= (1u << 0);  // OVERRIDE_UV_SCALE
    if (normal_strength != 1.0f) mask |= (1u << 1);  // OVERRIDE_NORMAL_STRENGTH
    if (brightness != 0.0f) mask |= (1u << 2);  // OVERRIDE_BRIGHTNESS
    if (contrast != 1.0f) mask |= (1u << 3);  // OVERRIDE_CONTRAST

    // Apply override via renderer
    g_renderer->setElementOverride(element_index, mask, uv_scale, normal_strength, brightness, contrast);

    return 0;
}

ARCH_API int arch_clear_element_material(int element_index) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return -1;
    }

    if (element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        setError("Invalid element index");
        return -2;
    }

    g_renderer->clearElementOverride(element_index);
    return 0;
}

ARCH_API void arch_clear_all_material_overrides(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_renderer) {
        g_renderer->clearAllElementOverrides();
    }
}

ARCH_API int arch_has_material_override(int element_index) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer || element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        return 0;
    }

    return g_renderer->hasElementOverride(element_index) ? 1 : 0;
}

ARCH_API int arch_get_element_material(int element_index,
                                      float* out_uv_scale,
                                      float* out_normal_strength,
                                      float* out_brightness,
                                      float* out_contrast) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return -1;
    }

    if (element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        setError("Invalid element index");
        return -2;
    }

    if (!g_renderer->hasElementOverride(element_index)) {
        return -3;  // No override
    }

    // Get override values
    const auto* override = g_renderer->getElementOverride(element_index);
    if (override) {
        if (out_uv_scale) *out_uv_scale = override->uvScale;
        if (out_normal_strength) *out_normal_strength = override->normalStrength;
        if (out_brightness) *out_brightness = override->brightness;
        if (out_contrast) *out_contrast = override->contrast;
    }

    return 0;
}

ARCH_API int arch_apply_material_batch(const int* indices, int count,
                                       float uv_scale,
                                       float normal_strength,
                                       float brightness,
                                       float contrast) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return 0;
    }

    if (!indices || count <= 0) {
        setError("Invalid indices array");
        return 0;
    }

    // Build override mask
    u32 mask = 0;
    if (uv_scale != 1.0f) mask |= (1u << 0);
    if (normal_strength != 1.0f) mask |= (1u << 1);
    if (brightness != 0.0f) mask |= (1u << 2);
    if (contrast != 1.0f) mask |= (1u << 3);

    int updated = 0;
    for (int i = 0; i < count; i++) {
        int idx = indices[i];
        if (idx >= 0 && idx < static_cast<int>(g_building.elements.size())) {
            g_renderer->setElementOverride(idx, mask, uv_scale, normal_strength, brightness, contrast);
            updated++;
        }
    }

    return updated;
}

ARCH_API int arch_get_override_count(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        return 0;
    }

    return static_cast<int>(g_renderer->getOverrideCount());
}

ARCH_API int arch_get_override_indices(int* out_indices, int max_indices) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        return 0;
    }

    if (!out_indices || max_indices <= 0) {
        return 0;
    }

    return g_renderer->getElementOverrideIndices(out_indices, max_indices);
}

// =============================================================================
// Material Library API Implementation
// =============================================================================

ARCH_API int arch_get_material_count(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        return 0;
    }

    return static_cast<int>(g_renderer->getMaterialNames().size());
}

ARCH_API const char* arch_get_material_name(int index) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return nullptr;
    }

    const auto& materials = g_renderer->getMaterialNames();
    if (index < 0 || index >= static_cast<int>(materials.size())) {
        setError("Invalid material index");
        return nullptr;
    }

    // Store in static buffer for next API call (valid until next call)
    static std::string g_materialNameBuffer;
    g_materialNameBuffer = materials[index];
    return g_materialNameBuffer.c_str();
}

ARCH_API const char* arch_get_material_category(int index) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return nullptr;
    }

    const auto& materials = g_renderer->getMaterialNames();
    if (index < 0 || index >= static_cast<int>(materials.size())) {
        setError("Invalid material index");
        return nullptr;
    }

    // Extract category from material path (format: "category/material_name")
    const std::string& materialPath = materials[index];
    size_t slashPos = materialPath.find('/');
    std::string category = (slashPos != std::string::npos)
                          ? materialPath.substr(0, slashPos)
                          : "general";

    static std::string g_categoryBuffer;
    g_categoryBuffer = category;
    return g_categoryBuffer.c_str();
}

ARCH_API int arch_get_materials_by_category(const char* category,
                                            int* out_indices,
                                            int max_indices) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return 0;
    }

    if (!category || !out_indices || max_indices <= 0) {
        setError("Invalid parameters");
        return 0;
    }

    const auto& materials = g_renderer->getMaterialNames();
    std::string catPrefix = std::string(category) + "/";
    int found = 0;

    for (size_t i = 0; i < materials.size() && found < max_indices; i++) {
        // Check if material starts with category prefix
        if (materials[i].compare(0, catPrefix.length(), catPrefix) == 0) {
            out_indices[found++] = static_cast<int>(i);
        }
    }

    return found;
}

ARCH_API int arch_find_material(const char* name) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        return -1;
    }

    if (!name) {
        return -1;
    }

    const auto& materials = g_renderer->getMaterialNames();
    for (size_t i = 0; i < materials.size(); i++) {
        if (materials[i] == name) {
            return static_cast<int>(i);
        }
    }

    return -1;  // Not found
}

ARCH_API int arch_apply_material_to_element(int element_index, const char* material_name) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return -1;
    }

    if (element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        setError("Invalid element index");
        return -2;
    }

    if (!material_name) {
        setError("Invalid material name");
        return -3;
    }

    // Find material index
    int matIndex = arch_find_material(material_name);
    if (matIndex < 0) {
        setError("Material not found");
        return -4;
    }

    // Get category from material path
    const std::string& materialPath = g_renderer->getMaterialNames()[matIndex];
    size_t slashPos = materialPath.find('/');
    std::string category = (slashPos != std::string::npos)
                          ? materialPath.substr(0, slashPos)
                          : "general";

    // Set override mask for material application
    u32 mask = (1u << 0);  // UV_SCALE

    // Different UV scales for different categories
    float uvScale = 1.0f;
    if (category == "walls") uvScale = 1.0f;
    else if (category == "floors") uvScale = 2.0f;
    else if (category == "roofs") uvScale = 1.5f;

    g_renderer->setElementOverride(element_index, mask, uvScale, 1.0f, 0.0f, 1.0f);

    return 0;
}

ARCH_API int arch_apply_material_to_batch(const int* indices, int count, const char* material_name) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return 0;
    }

    if (!indices || count <= 0) {
        setError("Invalid indices array");
        return 0;
    }

    if (!material_name) {
        setError("Invalid material name");
        return 0;
    }

    // Find material index
    int matIndex = arch_find_material(material_name);
    if (matIndex < 0) {
        setError("Material not found");
        return 0;
    }

    int updated = 0;
    for (int i = 0; i < count; i++) {
        int idx = indices[i];
        if (idx >= 0 && idx < static_cast<int>(g_building.elements.size())) {
            if (arch_apply_material_to_element(idx, material_name) == 0) {
                updated++;
            }
        }
    }

    return updated;
}

ARCH_API int arch_get_element_material_name(int element_index, char* out_name, int max_length) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_renderer) {
        setError("Renderer not initialized");
        return -1;
    }

    if (element_index < 0 || element_index >= static_cast<int>(g_building.elements.size())) {
        setError("Invalid element index");
        return -2;
    }

    if (!out_name || max_length <= 0) {
        setError("Invalid output buffer");
        return -3;
    }

    // Check if element has an override
    if (!g_renderer->hasElementOverride(element_index)) {
        // No override - return empty string
        out_name[0] = '\0';
        return -4;
    }

    // For now, return "custom" since we don't track which material was applied
    // TODO: Track applied material names in element metadata
    std::strncpy(out_name, "custom", max_length - 1);
    out_name[max_length - 1] = '\0';

    return 0;
}

} // extern "C" (temporarily close for C++ terrain helpers)

// =============================================================================
// Terrain Mesh API Implementation
// =============================================================================

// Global terrain state (C++ namespace, not exported)
namespace {
    // g_terrainEnabled is defined at top of file with other globals
    vec3 g_terrainOffset = {0.0f, 0.0f, 0.0f};
    float g_terrainRoughness = 0.8f;
    float g_terrainMetallic = 0.0f;
    int g_terrainColorMode = 0;  // 0=elevation gradient

    // Elevation color gradient (same as geometry_loader.cpp)
    vec3 getTerrainElevationColor(float normalizedElevation) {
        float t = glm::clamp(normalizedElevation, 0.0f, 1.0f);

        // Four-stop gradient: green -> tan -> gray -> white
        const vec3 lowGreen = vec3(0.34f, 0.55f, 0.30f);   // Low elevation - grass/forest
        const vec3 midTan = vec3(0.72f, 0.60f, 0.40f);     // Mid elevation - dirt/rock
        const vec3 highGray = vec3(0.55f, 0.55f, 0.55f);   // High elevation - bare rock
        const vec3 peakWhite = vec3(0.95f, 0.95f, 0.95f);  // Peak - snow

        if (t < 0.33f) {
            return glm::mix(lowGreen, midTan, t / 0.33f);
        } else if (t < 0.66f) {
            return glm::mix(midTan, highGray, (t - 0.33f) / 0.33f);
        } else {
            return glm::mix(highGray, peakWhite, (t - 0.66f) / 0.34f);
        }
    }
}

extern "C" {  // Re-open for C API functions

ARCH_API int arch_set_terrain_data(const ArchTerrainVertex* vertices, int vertex_count,
                                   const unsigned int* indices, int index_count,
                                   float width_ft, float depth_ft,
                                   float min_elevation, float max_elevation) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!vertices || vertex_count <= 0) {
        setError("Invalid vertices array");
        return -1;
    }

    if (!indices || index_count <= 0 || index_count % 3 != 0) {
        setError("Invalid indices array (must be multiple of 3)");
        return -2;
    }

    // Clear existing terrain
    g_building.terrainMesh.vertices.clear();
    g_building.terrainMesh.indices.clear();

    // Store metadata
    g_building.terrainMesh.width_ft = width_ft;
    g_building.terrainMesh.depth_ft = depth_ft;
    g_building.terrainMesh.min_elevation = min_elevation;
    g_building.terrainMesh.max_elevation = max_elevation;

    // Compute elevation range for color mapping
    float elevRange = max_elevation - min_elevation;
    if (elevRange < 0.001f) elevRange = 1.0f;  // Avoid division by zero

    // Convert vertices (keep in feet, same units as building elements)
    g_building.terrainMesh.vertices.reserve(vertex_count);

    for (int i = 0; i < vertex_count; i++) {
        const ArchTerrainVertex& src = vertices[i];
        Vertex vert{};

        // Position: keep in feet (same units as building elements)
        // API: X=east, Y=up(elevation), Z=north
        // Engine: X=east, Y=up, Z=south (flip Z)
        vert.position = vec3(
            src.pos_x,
            src.pos_y,   // Y is elevation (up)
            -src.pos_z   // Flip Z for south
        );

        // Apply offset (in feet)
        vert.position += vec3(
            g_terrainOffset.x,
            g_terrainOffset.y,
            -g_terrainOffset.z
        );

        // Normal (swap Y/Z, flip Z)
        vert.normal = glm::normalize(vec3(src.normal_x, src.normal_y, -src.normal_z));

        // UV
        vert.texCoord = vec2(src.u, src.v);

        // Compute color from elevation
        float normalizedElev = (src.pos_y - min_elevation) / elevRange;
        if (g_terrainColorMode == 0) {
            vert.color = getTerrainElevationColor(normalizedElev);
        } else {
            // Uniform gray
            vert.color = vec3(0.5f, 0.5f, 0.5f);
        }

        g_building.terrainMesh.vertices.push_back(vert);
    }

    // Copy indices
    g_building.terrainMesh.indices.reserve(index_count);
    for (int i = 0; i < index_count; i++) {
        g_building.terrainMesh.indices.push_back(indices[i]);
    }

    // Reset renderer's terrain cache to force rebuild
    if (g_renderer) {
        g_renderer->invalidateTerrainCache();
    }

    std::cout << "[Terrain API] Set terrain: " << vertex_count << " vertices, "
              << (index_count / 3) << " triangles, elevation " << min_elevation
              << "-" << max_elevation << " ft\n";

    return 0;
}

ARCH_API void arch_clear_terrain(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    g_building.terrainMesh.vertices.clear();
    g_building.terrainMesh.indices.clear();
    g_building.terrainMesh.width_ft = 0.0f;
    g_building.terrainMesh.depth_ft = 0.0f;
    g_building.terrainMesh.min_elevation = 0.0f;
    g_building.terrainMesh.max_elevation = 0.0f;

    if (g_renderer) {
        g_renderer->invalidateTerrainCache();
    }

    std::cout << "[Terrain API] Cleared terrain data\n";
}

ARCH_API int arch_has_terrain(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_building.terrainMesh.hasData() ? 1 : 0;
}

ARCH_API int arch_get_terrain_info(float* out_width_ft, float* out_depth_ft,
                                   float* out_min_elev, float* out_max_elev,
                                   int* out_vertex_count, int* out_triangle_count) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_building.terrainMesh.hasData()) {
        return -1;
    }

    if (out_width_ft) *out_width_ft = g_building.terrainMesh.width_ft;
    if (out_depth_ft) *out_depth_ft = g_building.terrainMesh.depth_ft;
    if (out_min_elev) *out_min_elev = g_building.terrainMesh.min_elevation;
    if (out_max_elev) *out_max_elev = g_building.terrainMesh.max_elevation;
    if (out_vertex_count) *out_vertex_count = static_cast<int>(g_building.terrainMesh.vertices.size());
    if (out_triangle_count) *out_triangle_count = static_cast<int>(g_building.terrainMesh.indices.size() / 3);

    return 0;
}

ARCH_API void arch_set_terrain_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_terrainEnabled = (enabled != 0);
}

ARCH_API int arch_get_terrain_enabled(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_terrainEnabled ? 1 : 0;
}

ARCH_API void arch_set_terrain_offset(float offset_x, float offset_y, float offset_z) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_terrainOffset = vec3(offset_x, offset_y, offset_z);

    // If terrain exists, we need to rebuild it with the new offset
    // For now, just store the offset - a full rebuild would require re-calling set_terrain_data
    std::cout << "[Terrain API] Set offset: (" << offset_x << ", " << offset_y << ", " << offset_z << ") ft\n";
}

ARCH_API void arch_get_terrain_offset(float* out_x, float* out_y, float* out_z) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (out_x) *out_x = g_terrainOffset.x;
    if (out_y) *out_y = g_terrainOffset.y;
    if (out_z) *out_z = g_terrainOffset.z;
}

ARCH_API void arch_set_terrain_material(float roughness, float metallic) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_terrainRoughness = glm::clamp(roughness, 0.0f, 1.0f);
    g_terrainMetallic = glm::clamp(metallic, 0.0f, 1.0f);
}

ARCH_API void arch_set_terrain_color_mode(int mode) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_terrainColorMode = mode;
}

// =============================================================================
// Path Tracer API Implementation
// =============================================================================

ARCH_API int arch_pt_set_config(int width, int height, int samples, int bounces) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (width <= 0 || height <= 0 || samples <= 0 || bounces <= 0) {
        setError("Invalid path tracer configuration");
        return -1;
    }

    g_ptConfig.width = static_cast<u32>(width);
    g_ptConfig.height = static_cast<u32>(height);
    g_ptConfig.samplesPerPixel = static_cast<u32>(samples);
    g_ptConfig.maxBounces = static_cast<u32>(bounces);

    std::cout << "[PathTracer API] Config: " << width << "x" << height
              << ", " << samples << " spp, " << bounces << " bounces\n";

    return 0;
}

ARCH_API int arch_pt_start_render(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized || !g_context) {
        setError("Not initialized");
        return -1;
    }

    if (g_building.elements.empty()) {
        setError("No scene loaded");
        return -2;
    }

    // Create path tracer if needed
    if (!g_pathTracer) {
        g_pathTracer = std::make_unique<PathTracer>(*g_context);
        // Load PBR textures from materials directory
        g_pathTracer->loadMaterialTextures("materials");
    }

    // Set scene
    if (!g_pathTracer->setScene(g_building.elements)) {
        setError("Failed to upload scene to path tracer");
        return -3;
    }

    // Set camera
    Camera camera;
    camera.position.x = g_cameraTarget.x + g_cameraDistance * cos(g_cameraPitch) * sin(g_cameraYaw);
    camera.position.y = g_cameraTarget.y + g_cameraDistance * sin(g_cameraPitch);
    camera.position.z = g_cameraTarget.z + g_cameraDistance * cos(g_cameraPitch) * cos(g_cameraYaw);
    camera.target = g_cameraTarget;
    camera.up = vec3(0, 1, 0);
    camera.fov = g_cameraFOV;
    camera.nearPlane = 0.1f;
    camera.farPlane = 100000.0f;  // Large value to handle mm units
    camera.isOrthographic = g_cameraOrthographic;
    camera.orthoSize = g_cameraDistance * 0.5f;

    std::cout << "[PathTracer] Camera pos: (" << camera.position.x << ", " << camera.position.y << ", " << camera.position.z
              << "), target: (" << camera.target.x << ", " << camera.target.y << ", " << camera.target.z << ")\n";

    g_pathTracer->setCamera(camera);
    g_pathTracer->setConfig(g_ptConfig);

    // Pass section clipping from renderer to path tracer
    if (g_renderer) {
        g_pathTracer->setClipPlane(g_renderer->getClipPlane(), g_renderer->getClippingEnabled());
        std::cout << "[PathTracer] Clipping: enabled=" << g_renderer->getClippingEnabled()
                  << ", plane=(" << g_renderer->getClipPlane().x << ", " << g_renderer->getClipPlane().y
                  << ", " << g_renderer->getClipPlane().z << ", " << g_renderer->getClipPlane().w << ")\n";
    }

    // Start render
    g_pathTracer->startRender();

    return 0;
}

ARCH_API int arch_pt_render_frame(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_pathTracer) {
        return -1;
    }

    if (!g_pathTracer->isRendering()) {
        return g_pathTracer->isComplete() ? 0 : -1;
    }

    bool moreFrames = g_pathTracer->renderFrame();
    return moreFrames ? 1 : 0;
}

ARCH_API int arch_pt_get_progress(float* progress) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!progress) {
        return -1;
    }

    if (!g_pathTracer) {
        *progress = 0.0f;
        return 0;
    }

    *progress = g_pathTracer->getProgress();
    return 0;
}

ARCH_API void arch_pt_stop(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (g_pathTracer) {
        g_pathTracer->stopRender();
    }
}

ARCH_API int arch_pt_is_rendering(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_pathTracer && g_pathTracer->isRendering()) ? 1 : 0;
}

ARCH_API int arch_pt_is_complete(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return (g_pathTracer && g_pathTracer->isComplete()) ? 1 : 0;
}

ARCH_API int arch_pt_get_sample_count(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_pathTracer) {
        return 0;
    }

    return static_cast<int>(g_pathTracer->getCurrentSample());
}

ARCH_API int arch_pt_save_png(const char* path, float exposure) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_pathTracer) {
        setError("Path tracer not initialized");
        return -1;
    }

    if (!path) {
        setError("Invalid path");
        return -2;
    }

    if (!g_pathTracer->savePNG(std::string(path), exposure)) {
        setError("Failed to save PNG");
        return -3;
    }

    return 0;
}

ARCH_API int arch_pt_save_hdr(const char* path) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_pathTracer) {
        setError("Path tracer not initialized");
        return -1;
    }

    if (!path) {
        setError("Invalid path");
        return -2;
    }

    if (!g_pathTracer->saveEXR(std::string(path))) {
        setError("Failed to save HDR");
        return -3;
    }

    return 0;
}

ARCH_API int arch_pt_apply_denoise(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_pathTracer) {
        setError("Path tracer not initialized");
        return -1;
    }

    g_pathTracer->applyDenoising();
    return 0;
}

ARCH_API void arch_pt_set_exposure(float exposure) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_ptConfig.exposure = exposure;

    if (g_pathTracer) {
        g_pathTracer->setConfig(g_ptConfig);
    }
}

ARCH_API float arch_pt_get_exposure(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_ptConfig.exposure;
}

ARCH_API void arch_pt_set_tonemap_mode(int mode) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (mode >= 0 && mode <= 2) {
        g_ptConfig.tonemapMode = static_cast<u32>(mode);
        if (g_pathTracer) {
            g_pathTracer->setConfig(g_ptConfig);
        }
    }
}

ARCH_API int arch_pt_get_tonemap_mode(void) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return static_cast<int>(g_ptConfig.tonemapMode);
}

ARCH_API void arch_pt_set_nee_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_ptConfig.enableNEE = (enabled != 0);

    if (g_pathTracer) {
        g_pathTracer->setConfig(g_ptConfig);
    }
}

ARCH_API void arch_pt_set_rr_enabled(int enabled) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_ptConfig.enableRR = (enabled != 0);

    if (g_pathTracer) {
        g_pathTracer->setConfig(g_ptConfig);
    }
}

} // extern "C"
