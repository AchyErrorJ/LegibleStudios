#pragma once

#include "types.hpp"
#include "window.hpp"
#include <optional>
#include <set>

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
};

class VulkanContext {
public:
    VulkanContext(Window& window, const VulkanConfig& config = {});
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

    u32 findMemoryType(u32 typeFilter, VkMemoryPropertyFlags properties);

    // Image creation helpers
    void createImage(u32 width, u32 height, VkFormat format, VkImageTiling tiling,
                    VkImageUsageFlags usage, VkMemoryPropertyFlags properties,
                    VkImage& image, VkDeviceMemory& imageMemory);

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
    Window& m_window;

    // Core Vulkan objects
    VkInstance m_instance = VK_NULL_HANDLE;
    VkDebugUtilsMessengerEXT m_debugMessenger = VK_NULL_HANDLE;
    VkSurfaceKHR m_surface = VK_NULL_HANDLE;
    VkPhysicalDevice m_physicalDevice = VK_NULL_HANDLE;
    VkDevice m_device = VK_NULL_HANDLE;

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
