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

#include <memory>
#include <string>
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
    Building g_building;

    // Camera state
    float g_cameraYaw = 0.5f;
    float g_cameraPitch = 0.4f;
    float g_cameraDistance = 60.0f;
    vec3 g_cameraTarget = {20.0f, 10.0f, 15.0f};

    // State
    bool g_initialized = false;
    int g_width = 800;
    int g_height = 600;
    int g_selectedElement = -1;
    VisualizationMode g_vizMode = VisualizationMode::Structural;

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
        camera.fov = 45.0f;
        camera.nearPlane = 0.1f;
        camera.farPlane = 500.0f;

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

ARCH_API void arch_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_mutex);

    if (!g_initialized) return;

    if (g_context) {
        g_context->waitIdle();
    }

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
        auto& qbd = qbd::getQBDInterface();
        auto layoutOpt = qbd.loadFromJSON(std::string(json_str));

        if (!layoutOpt.has_value()) {
            setError("Failed to parse JSON");
            return -2;
        }

        g_building = qbd.toBuilding(*layoutOpt);
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
        auto& qbd = qbd::getQBDInterface();
        auto layoutOpt = qbd.loadFromFile(std::string(file_path));

        if (!layoutOpt.has_value()) {
            setError("Failed to load file");
            return -2;
        }

        g_building = qbd.toBuilding(*layoutOpt);
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

ARCH_API int arch_get_element_count(void) {
    return static_cast<int>(g_building.elements.size());
}

ARCH_API const char* arch_get_error(void) {
    return g_lastError.c_str();
}

} // extern "C"
