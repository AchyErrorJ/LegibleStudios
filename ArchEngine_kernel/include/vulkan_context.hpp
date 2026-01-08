#pragma once

#include "types.hpp"
#include "window.hpp"
#include <optional>
#include <set>
#include <fstream>

namespace arch {

// Queue family indices
struct QueueFamilyIndices {
    std::optional<u32> graphicsFamily;
    std::optional<u32> presentFamily;

    bool isComplete() const {
        return graphicsFamily.has_value() && presentFamily.has_value();
    }
};

// Swapchain support details
struct SwapchainSupportDetails {
    VkSurfaceCapabilitiesKHR capabilities;
    std::vector<VkSurfaceFormatKHR> formats;
    std::vector<VkPresentModeKHR> presentModes;
};

// Vulkan context configuration
struct VulkanConfig {
    bool enableValidation = true;
    bool enableDebugMarkers = true;
    u32 maxFramesInFlight = 2;

    // MSAA settings (Phase 2)
    VkSampleCountFlagBits msaaSamples = VK_SAMPLE_COUNT_4_BIT;
    bool enableMsaa = true;

    // Shadow settings (Phase 4)
    u32 shadowMapResolution = 2048;
    bool enableShadows = true;

    // Pipeline cache path
    std::string pipelineCachePath = "pipeline_cache.bin";
};

class VulkanContext {
public:
    // Standard constructor with GLFW window
    VulkanContext(Window& window, const VulkanConfig& config = {});

    // Embedded mode constructor - accepts external instance and surface
    VulkanContext(VkInstance instance, VkSurfaceKHR surface, u32 width, u32 height, const VulkanConfig& config = {});

    ~VulkanContext();

    // Non-copyable
    VulkanContext(const VulkanContext&) = delete;
    VulkanContext& operator=(const VulkanContext&) = delete;

    // Accessors
    VkInstance getInstance() const { return m_instance; }
    VkDevice getDevice() const { return m_device; }
    VkPhysicalDevice getPhysicalDevice() const { return m_physicalDevice; }
    VkQueue getGraphicsQueue() const { return m_graphicsQueue; }
    VkQueue getPresentQueue() const { return m_presentQueue; }
    VkCommandPool getCommandPool() const { return m_commandPool; }
    VkSurfaceKHR getSurface() const { return m_surface; }
    const QueueFamilyIndices& getQueueFamilies() const { return m_queueFamilies; }
    u32 getGraphicsQueueFamily() const { return m_queueFamilies.graphicsFamily.value(); }
    u32 getMaxFramesInFlight() const { return m_config.maxFramesInFlight; }

    // Pipeline cache (Phase 0)
    VkPipelineCache getPipelineCache() const { return m_pipelineCache; }

    // MSAA support (Phase 2)
    VkSampleCountFlagBits getMsaaSamples() const { return m_msaaSamples; }
    VkSampleCountFlagBits getMaxUsableSampleCount() const;
    VkImageView getMsaaColorImageView() const { return m_msaaColorImageView; }
    bool supportsSamplerAnisotropy() const { return m_deviceFeatures.samplerAnisotropy == VK_TRUE; }
    float getMaxSamplerAnisotropy() const { return m_maxSamplerAnisotropy; }

    // Config access
    const VulkanConfig& getConfig() const { return m_config; }

    // Swapchain
    VkSwapchainKHR getSwapchain() const { return m_swapchain; }
    VkFormat getSwapchainFormat() const { return m_swapchainFormat; }
    VkExtent2D getSwapchainExtent() const { return m_swapchainExtent; }
    const std::vector<VkImageView>& getSwapchainImageViews() const { return m_swapchainImageViews; }
    u32 getSwapchainImageCount() const { return static_cast<u32>(m_swapchainImages.size()); }

    // Depth buffer
    VkImageView getDepthImageView() const { return m_depthImageView; }
    VkFormat getDepthFormat() const { return VK_FORMAT_D32_SFLOAT; }

    // Swapchain management
    void recreateSwapchain();
    void waitIdle() { vkDeviceWaitIdle(m_device); }

    // Command buffer helpers
    VkCommandBuffer beginSingleTimeCommands();
    void endSingleTimeCommands(VkCommandBuffer commandBuffer);

    // Buffer creation helpers
    void createBuffer(VkDeviceSize size, VkBufferUsageFlags usage,
                     VkMemoryPropertyFlags properties, VkBuffer& buffer,
                     VkDeviceMemory& bufferMemory);

    void copyBuffer(VkBuffer srcBuffer, VkBuffer dstBuffer, VkDeviceSize size);
    void copyBufferToImage(VkBuffer buffer, VkImage image, u32 width, u32 height);

    u32 findMemoryType(u32 typeFilter, VkMemoryPropertyFlags properties);

    // Image creation helpers
    void createImage(u32 width, u32 height, VkFormat format, VkImageTiling tiling,
                    VkImageUsageFlags usage, VkMemoryPropertyFlags properties,
                    VkImage& image, VkDeviceMemory& imageMemory,
                    VkSampleCountFlagBits samples = VK_SAMPLE_COUNT_1_BIT);

    VkImageView createImageView(VkImage image, VkFormat format, VkImageAspectFlags aspectFlags);

    void transitionImageLayout(VkImage image, VkFormat format,
                              VkImageLayout oldLayout, VkImageLayout newLayout);

    // Debug markers (for RenderDoc/NSight)
    void beginDebugLabel(VkCommandBuffer cmd, const char* name, vec4 color = {1,1,1,1});
    void endDebugLabel(VkCommandBuffer cmd);
    void insertDebugLabel(VkCommandBuffer cmd, const char* name, vec4 color = {1,1,1,1});

private:
    void createInstance();
    void setupDebugMessenger();
    void createSurface();
    void pickPhysicalDevice();
    void createLogicalDevice();
    void createSwapchain();
    void createImageViews();
    void createCommandPool();
    void createDepthResources();
    void createPipelineCache();
    void savePipelineCache();
    void createMsaaResources();

    void cleanupSwapchain();

    QueueFamilyIndices findQueueFamilies(VkPhysicalDevice device);
    SwapchainSupportDetails querySwapchainSupport(VkPhysicalDevice device);
    bool isDeviceSuitable(VkPhysicalDevice device);
    bool checkDeviceExtensionSupport(VkPhysicalDevice device);

    VkSurfaceFormatKHR chooseSwapSurfaceFormat(const std::vector<VkSurfaceFormatKHR>& formats);
    VkPresentModeKHR chooseSwapPresentMode(const std::vector<VkPresentModeKHR>& modes);
    VkExtent2D chooseSwapExtent(const VkSurfaceCapabilitiesKHR& capabilities);

    static VKAPI_ATTR VkBool32 VKAPI_CALL debugCallback(
        VkDebugUtilsMessageSeverityFlagBitsEXT severity,
        VkDebugUtilsMessageTypeFlagsEXT type,
        const VkDebugUtilsMessengerCallbackDataEXT* callbackData,
        void* userData);

    // Configuration
    VulkanConfig m_config;
    Window* m_window = nullptr;  // nullptr in embedded mode
    bool m_ownsInstance = true;  // false if using external instance
    bool m_ownsSurface = true;   // false if using external surface
    u32 m_embeddedWidth = 0;     // Used in embedded mode
    u32 m_embeddedHeight = 0;    // Used in embedded mode

    // Core Vulkan objects
    VkInstance m_instance = VK_NULL_HANDLE;
    VkDebugUtilsMessengerEXT m_debugMessenger = VK_NULL_HANDLE;
    VkSurfaceKHR m_surface = VK_NULL_HANDLE;
    VkPhysicalDevice m_physicalDevice = VK_NULL_HANDLE;
    VkDevice m_device = VK_NULL_HANDLE;
    VkPhysicalDeviceFeatures m_deviceFeatures{};
    float m_maxSamplerAnisotropy = 1.0f;

    // Pipeline cache (Phase 0)
    VkPipelineCache m_pipelineCache = VK_NULL_HANDLE;

    // MSAA resources (Phase 2)
    VkSampleCountFlagBits m_msaaSamples = VK_SAMPLE_COUNT_1_BIT;
    VkImage m_msaaColorImage = VK_NULL_HANDLE;
    VkDeviceMemory m_msaaColorMemory = VK_NULL_HANDLE;
    VkImageView m_msaaColorImageView = VK_NULL_HANDLE;

    // Queues
    VkQueue m_graphicsQueue = VK_NULL_HANDLE;
    VkQueue m_presentQueue = VK_NULL_HANDLE;
    QueueFamilyIndices m_queueFamilies;

    // Swapchain
    VkSwapchainKHR m_swapchain = VK_NULL_HANDLE;
    std::vector<VkImage> m_swapchainImages;
    std::vector<VkImageView> m_swapchainImageViews;
    VkFormat m_swapchainFormat;
    VkExtent2D m_swapchainExtent;

    // Depth buffer
    VkImage m_depthImage = VK_NULL_HANDLE;
    VkDeviceMemory m_depthImageMemory = VK_NULL_HANDLE;
    VkImageView m_depthImageView = VK_NULL_HANDLE;

    // Command pool
    VkCommandPool m_commandPool = VK_NULL_HANDLE;

    // Device extensions
    const std::vector<const char*> m_deviceExtensions = {
        VK_KHR_SWAPCHAIN_EXTENSION_NAME
    };

    // Validation layers
    const std::vector<const char*> m_validationLayers = {
        "VK_LAYER_KHRONOS_validation"
    };

    // Debug function pointers
    PFN_vkCmdBeginDebugUtilsLabelEXT m_vkCmdBeginDebugUtilsLabelEXT = nullptr;
    PFN_vkCmdEndDebugUtilsLabelEXT m_vkCmdEndDebugUtilsLabelEXT = nullptr;
    PFN_vkCmdInsertDebugUtilsLabelEXT m_vkCmdInsertDebugUtilsLabelEXT = nullptr;
};

} // namespace arch
