#pragma once

#include "types.hpp"
#include "vulkan_context.hpp"
#include <random>

namespace arch {

// SSAO configuration
struct SSAOConfig {
    u32 kernelSize = 64;        // Number of sample points
    f32 radius = 0.5f;          // Sampling radius in world units
    f32 bias = 0.025f;          // Depth bias to prevent self-occlusion
    f32 intensity = 1.5f;       // AO intensity multiplier
    f32 power = 2.0f;           // Power curve for AO
    bool enabled = true;
};

// Bloom configuration
struct BloomConfig {
    f32 threshold = 1.0f;       // Brightness threshold for bloom
    f32 softThreshold = 0.5f;   // Soft knee for threshold
    f32 intensity = 0.3f;       // Bloom intensity
    u32 iterations = 5;         // Number of blur iterations
    bool enabled = true;
};

// Composite/Tonemapping configuration
struct CompositeConfig {
    f32 exposure = 1.0f;
    u32 tonemapMode = 1;        // 0=Reinhard, 1=ACES, 2=Uncharted2
    bool enabled = true;
};

// Post-processing pipeline
class PostProcess {
public:
    PostProcess(VulkanContext& context);
    ~PostProcess();

    // Initialize with render dimensions
    void initialize(u32 width, u32 height);
    void cleanup();
    void resize(u32 width, u32 height);
    void createCompositePipeline(VkRenderPass renderPass, VkSampleCountFlagBits samples);

    // SSAO
    void setSSAOConfig(const SSAOConfig& config) { m_ssaoConfig = config; }
    const SSAOConfig& getSSAOConfig() const { return m_ssaoConfig; }

    // Generate SSAO from depth and normal buffers
    void generateSSAO(VkCommandBuffer cmd,
                      VkImageView depthView,
                      VkImageView normalView,
                      const mat4& projection,
                      const mat4& view,
                      u32 frameIndex);

    // Get SSAO result for sampling in main shader
    VkImageView getSSAOImageView() const { return m_ssaoBlurredView; }
    VkSampler getSSAOSampler() const { return m_ssaoSampler; }

    // Bloom
    void setBloomConfig(const BloomConfig& config) { m_bloomConfig = config; }
    const BloomConfig& getBloomConfig() const { return m_bloomConfig; }

    void setCompositeConfig(const CompositeConfig& config) { m_compositeConfig = config; }
    const CompositeConfig& getCompositeConfig() const { return m_compositeConfig; }

    // HDR scene rendering - call these instead of direct swapchain rendering
    VkRenderPass getHDRRenderPass() const { return m_hdrRenderPass; }
    VkFramebuffer getHDRFramebuffer() const { return m_hdrFramebuffer; }
    VkImageView getHDRColorView() const { return m_hdrColorView; }
    VkImageView getHDRDepthView() const { return m_hdrDepthView; }

    // Generate bloom from HDR scene
    void generateBloom(VkCommandBuffer cmd, u32 frameIndex);
    VkImageView getBloomImageView() const { return m_bloomResultView; }

    // Final composite pass - outputs to provided framebuffer (swapchain)
    // beginRenderPass: if true, starts the render pass; if false, assumes already started
    // endRenderPass: if true, ends the render pass; if false, leaves it open (for ImGui)
    void composite(VkCommandBuffer cmd, VkRenderPass renderPass, VkFramebuffer framebuffer,
                   VkExtent2D extent, u32 frameIndex, bool beginRenderPass = true, bool endRenderPass = true);

    // Full-screen quad rendering helper
    void drawFullscreenQuad(VkCommandBuffer cmd);

    // Descriptor set for SSAO sampling in main shader
    VkDescriptorSet getSSAODescriptorSet() const { return m_ssaoSampleDescSet; }
    VkDescriptorSetLayout getSSAODescriptorSetLayout() const { return m_ssaoSampleDescLayout; }

private:
    void createHDRResources();
    void createHDRTargets();
    void cleanupHDRTargets();
    void createSSAOResources();
    void createSSAOPipeline();
    void createSSAOKernel();
    void createNoiseTexture();
    void createBlurPipeline();
    void createBloomResources();
    void createBloomPipelines();
    void createFullscreenQuad();

    void cleanupHDR();
    void cleanupSSAO();
    void cleanupSSAOSizeDependent();
    void cleanupBloom();
    void cleanupComposite();

    VulkanContext& m_context;
    u32 m_width = 0;
    u32 m_height = 0;
    bool m_initialized = false;

    // Configuration
    SSAOConfig m_ssaoConfig;
    BloomConfig m_bloomConfig;
    CompositeConfig m_compositeConfig;

    // HDR render target (scene is rendered here first)
    VkImage m_hdrColorImage = VK_NULL_HANDLE;
    VkDeviceMemory m_hdrColorMemory = VK_NULL_HANDLE;
    VkImageView m_hdrColorView = VK_NULL_HANDLE;
    VkImage m_hdrDepthImage = VK_NULL_HANDLE;
    VkDeviceMemory m_hdrDepthMemory = VK_NULL_HANDLE;
    VkImageView m_hdrDepthView = VK_NULL_HANDLE;
    VkRenderPass m_hdrRenderPass = VK_NULL_HANDLE;
    VkFramebuffer m_hdrFramebuffer = VK_NULL_HANDLE;
    VkSampler m_hdrSampler = VK_NULL_HANDLE;

    // SSAO kernel samples (hemisphere)
    std::vector<vec4> m_ssaoKernel;

    // SSAO noise texture (4x4 rotation vectors)
    VkImage m_noiseImage = VK_NULL_HANDLE;
    VkDeviceMemory m_noiseMemory = VK_NULL_HANDLE;
    VkImageView m_noiseView = VK_NULL_HANDLE;
    VkSampler m_noiseSampler = VK_NULL_HANDLE;

    // SSAO output texture
    VkImage m_ssaoImage = VK_NULL_HANDLE;
    VkDeviceMemory m_ssaoMemory = VK_NULL_HANDLE;
    VkImageView m_ssaoView = VK_NULL_HANDLE;

    // SSAO blurred output
    VkImage m_ssaoBlurredImage = VK_NULL_HANDLE;
    VkDeviceMemory m_ssaoBlurredMemory = VK_NULL_HANDLE;
    VkImageView m_ssaoBlurredView = VK_NULL_HANDLE;

    VkSampler m_ssaoSampler = VK_NULL_HANDLE;

    // SSAO render pass and framebuffer
    VkRenderPass m_ssaoRenderPass = VK_NULL_HANDLE;
    VkFramebuffer m_ssaoFramebuffer = VK_NULL_HANDLE;
    VkFramebuffer m_ssaoBlurFramebuffer = VK_NULL_HANDLE;

    // SSAO pipeline
    VkPipelineLayout m_ssaoPipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_ssaoPipeline = VK_NULL_HANDLE;
    VkPipeline m_ssaoBlurPipeline = VK_NULL_HANDLE;

    // SSAO descriptor sets
    VkDescriptorPool m_descriptorPool = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_ssaoDescriptorLayout = VK_NULL_HANDLE;
    std::vector<VkDescriptorSet> m_ssaoDescriptorSets;
    VkDescriptorSetLayout m_ssaoBlurDescLayout = VK_NULL_HANDLE;
    VkDescriptorSet m_ssaoBlurDescSet = VK_NULL_HANDLE;

    // Descriptor set for sampling SSAO in main shader
    VkDescriptorSetLayout m_ssaoSampleDescLayout = VK_NULL_HANDLE;
    VkDescriptorSet m_ssaoSampleDescSet = VK_NULL_HANDLE;

    // SSAO uniform buffer (kernel samples + params)
    VkBuffer m_ssaoUniformBuffer = VK_NULL_HANDLE;
    VkDeviceMemory m_ssaoUniformMemory = VK_NULL_HANDLE;
    void* m_ssaoUniformMapped = nullptr;

    // Bloom resources
    VkImage m_bloomImages[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
    VkDeviceMemory m_bloomMemory[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
    VkImageView m_bloomViews[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
    VkImageView m_bloomResultView = VK_NULL_HANDLE;
    VkSampler m_bloomSampler = VK_NULL_HANDLE;

    VkRenderPass m_bloomRenderPass = VK_NULL_HANDLE;
    VkFramebuffer m_bloomFramebuffers[2] = {VK_NULL_HANDLE, VK_NULL_HANDLE};
    VkPipelineLayout m_bloomPipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_bloomBrightPipeline = VK_NULL_HANDLE;
    VkPipeline m_bloomBlurPipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_bloomDescLayout = VK_NULL_HANDLE;
    std::vector<std::array<VkDescriptorSet, 2>> m_bloomDescSets;

    // Composite resources
    VkPipelineLayout m_compositePipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_compositePipeline = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_compositeDescLayout = VK_NULL_HANDLE;
    std::vector<VkDescriptorSet> m_compositeDescSets;

    // Fullscreen quad
    VkBuffer m_quadVertexBuffer = VK_NULL_HANDLE;
    VkDeviceMemory m_quadVertexMemory = VK_NULL_HANDLE;
    VkBuffer m_quadIndexBuffer = VK_NULL_HANDLE;
    VkDeviceMemory m_quadIndexMemory = VK_NULL_HANDLE;
};

} // namespace arch
