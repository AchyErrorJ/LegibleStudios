#pragma once

#include "types.hpp"
#include "vulkan_context.hpp"
#include "pipeline.hpp"

namespace arch {

// Push constants for tessellated shadow pass
struct ShadowTessPushConstants {
    mat4 lightViewProj;
    mat4 model;
    f32 tessLevel;
    f32 dispScale;
    f32 uvScale;
    f32 padding;
};

// ============================================================================
// ShadowMap - Directional light shadow mapping with PCF
// ============================================================================
class ShadowMap {
public:
    ShadowMap(VulkanContext& context, u32 resolution = 2048);
    ~ShadowMap();

    // Non-copyable
    ShadowMap(const ShadowMap&) = delete;
    ShadowMap& operator=(const ShadowMap&) = delete;

    // Begin shadow pass rendering
    void beginShadowPass(VkCommandBuffer cmd);

    // End shadow pass rendering
    void endShadowPass(VkCommandBuffer cmd);

    // Update light matrices for shadow mapping
    void updateLightMatrix(const vec3& lightDir, const vec3& sceneCenter, f32 sceneRadius);

    // Get the light view-projection matrix for UBO
    const mat4& getLightViewProj() const { return m_lightViewProj; }

    // Get shadow map image view for binding to descriptor
    VkImageView getImageView() const { return m_depthImageView; }

    // Get shadow map sampler
    VkSampler getSampler() const { return m_sampler; }

    // Get the shadow pipeline layout
    VkPipelineLayout getPipelineLayout() const { return m_pipelineLayout; }

    // Get the shadow pipeline
    VkPipeline getPipeline() const { return m_pipeline; }

    // Get resolution
    u32 getResolution() const { return m_resolution; }

    // Get descriptor set layout for shadow pass
    VkDescriptorSetLayout getDescriptorSetLayout() const { return m_descriptorSetLayout; }

    // Tessellated shadow pass (for displacement mapping)
    VkPipeline getTessPipeline() const { return m_tessPipeline; }
    VkPipelineLayout getTessPipelineLayout() const { return m_tessPipelineLayout; }
    VkDescriptorSetLayout getHeightMapDescriptorSetLayout() const { return m_heightMapDescriptorSetLayout; }

private:
    void createDepthResources();
    void createRenderPass();
    void createFramebuffer();
    void createSampler();
    void createPipeline();
    void createTessPipeline();
    void createDescriptorSetLayout();

    VulkanContext& m_context;
    u32 m_resolution;

    // Depth texture
    VkImage m_depthImage = VK_NULL_HANDLE;
    VkDeviceMemory m_depthImageMemory = VK_NULL_HANDLE;
    VkImageView m_depthImageView = VK_NULL_HANDLE;

    // Render pass and framebuffer
    VkRenderPass m_renderPass = VK_NULL_HANDLE;
    VkFramebuffer m_framebuffer = VK_NULL_HANDLE;

    // Sampler with comparison for hardware PCF
    VkSampler m_sampler = VK_NULL_HANDLE;

    // Shadow pass pipeline (non-tessellated)
    VkPipelineLayout m_pipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_pipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_descriptorSetLayout = VK_NULL_HANDLE;

    // Tessellated shadow pass pipeline
    VkPipelineLayout m_tessPipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_tessPipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_heightMapDescriptorSetLayout = VK_NULL_HANDLE;

    // Light matrices
    mat4 m_lightView = mat4(1.0f);
    mat4 m_lightProj = mat4(1.0f);
    mat4 m_lightViewProj = mat4(1.0f);
};

} // namespace arch
