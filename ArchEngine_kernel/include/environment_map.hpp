#pragma once

#include "types.hpp"
#include "vulkan_context.hpp"
#include <string>

namespace arch {

class EnvironmentMap {
public:
    EnvironmentMap(VulkanContext& context);
    ~EnvironmentMap();

    // Non-copyable
    EnvironmentMap(const EnvironmentMap&) = delete;
    EnvironmentMap& operator=(const EnvironmentMap&) = delete;

    // Load HDR environment map from file (equirectangular format)
    bool loadFromFile(const std::string& filepath);

    // Load a default procedural sky (no file needed)
    void createProceduralSky();

    // Check if loaded
    bool isLoaded() const { return m_loaded; }

    // Getters for rendering
    VkImageView getCubemapView() const { return m_cubemapView; }
    VkSampler getSampler() const { return m_sampler; }
    VkDescriptorImageInfo getDescriptorInfo() const;

    // Get dimensions
    u32 getCubemapSize() const { return m_cubemapSize; }

private:
    void createCubemapFromEquirectangular(const float* hdrData, int width, int height);
    void createSampler();
    void cleanup();

    // Convert equirectangular to cubemap face
    vec3 getCubemapDirection(int face, float u, float v);

    VulkanContext& m_context;

    // Cubemap texture
    VkImage m_cubemapImage = VK_NULL_HANDLE;
    VkDeviceMemory m_cubemapMemory = VK_NULL_HANDLE;
    VkImageView m_cubemapView = VK_NULL_HANDLE;
    VkSampler m_sampler = VK_NULL_HANDLE;

    u32 m_cubemapSize = 512;  // Size of each cubemap face
    bool m_loaded = false;
};

} // namespace arch
