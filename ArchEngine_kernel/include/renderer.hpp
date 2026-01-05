#pragma once

#include "types.hpp"
#include <set>
#include "vulkan_context.hpp"
#include "pipeline.hpp"
#include "mesh.hpp"
#include "shadow_map.hpp"
#include "environment_map.hpp"
#include "post_process.hpp"

namespace arch {

struct RenderStats {
    u32 drawCalls = 0;
    u32 triangles = 0;
    f32 frameTimeMs = 0.0f;
    f32 gpuTimeMs = 0.0f;
};

class Renderer {
public:
    Renderer(VulkanContext& context);
    ~Renderer();

    // Non-copyable
    Renderer(const Renderer&) = delete;
    Renderer& operator=(const Renderer&) = delete;

    // Frame management
    bool beginFrame();
    void endFrame();

    // Rendering commands
    void beginRenderPass(vec4 clearColor = {0.1f, 0.1f, 0.15f, 1.0f});
    void endRenderPass();

    // Post-processing render path (HDR -> SSAO -> Bloom -> Composite)
    void setPostProcessingEnabled(bool enabled) { m_postProcessingEnabled = enabled; }
    bool isPostProcessingEnabled() const { return m_postProcessingEnabled; }
    void beginHDRRenderPass(vec4 clearColor = {0.1f, 0.1f, 0.15f, 1.0f});
    void endHDRRenderPass();
    void runPostProcessing();  // Runs SSAO and bloom passes
    void beginCompositePass(); // Composites HDR+effects to swapchain, leaves render pass open for ImGui

    // Shadow pass - call before beginRenderPass
    void renderShadowPass(const std::vector<StructuralElement>& elements);

    void setCamera(const Camera& camera);

    // Draw structural elements with color (stress in alpha controls shader behavior)
    void drawMesh(Mesh& mesh, const mat4& transform, vec3 color, f32 stress = 0.0f);
    void drawBeam(vec3 start, vec3 end, f32 width, f32 height, vec3 color, f32 stress = 0.0f, f32 deflection = 0.0f);
    void drawColumn(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);
    void drawColumnWithMaterial(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress, vec4 material);
    void drawFloor(vec3 position, f32 width, f32 depth, f32 thickness, vec3 color, f32 stress = 0.0f);
    void drawDoor(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);
    void drawWindow(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);
    void drawRoof(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);
    void drawCustomMesh(const MeshData& meshData, vec3 color, f32 stress = 0.0f);
    void drawCustomMeshWithMaterial(const MeshData& meshData, vec3 color, f32 stress, vec4 material);
    void drawMeshWithMaterial(Mesh& mesh, const mat4& transform, vec3 color, f32 stress, vec4 material);
    void drawGrid(f32 size = 50.0f, f32 spacing = 1.0f);
    void drawLoadArrow(vec3 start, vec3 end, f32 magnitude);
    void drawSky();

    // Draw structural frame from analysis data
    void drawStructuralFrame(const std::vector<StructuralElement>& elements, const Building& building, const std::set<int>& selectedIndices = {});

    // Visualization mode
    void setVisualizationMode(VisualizationMode mode) { m_vizMode = mode; }
    VisualizationMode getVisualizationMode() const { return m_vizMode; }

    // Shadow settings
    void setShadowsEnabled(bool enabled) { m_shadowsEnabled = enabled; }
    bool getShadowsEnabled() const { return m_shadowsEnabled; }
    void setLightDirection(const vec3& dir) { m_lightDirection = glm::normalize(dir); }
    const vec3& getLightDirection() const { return m_lightDirection; }
    void setShadowBias(f32 bias) { m_shadowBias = bias; }
    f32 getShadowBias() const { return m_shadowBias; }

    // Environment map settings
    bool loadHdrEnvironment(const std::string& filepath);
    void setUseHdrEnvMap(bool use) { m_useHdrEnvMap = use; }
    bool getUseHdrEnvMap() const { return m_useHdrEnvMap; }
    bool hasHdrEnvMap() const { return m_envMap && m_envMap->isLoaded(); }

    // SSAO settings
    void setSSAOEnabled(bool enabled);
    bool getSSAOEnabled() const { return m_ssaoEnabled; }
    void setSSAORadius(f32 radius);
    f32 getSSAORadius() const;
    void setSSAOIntensity(f32 intensity);
    f32 getSSAOIntensity() const;
    void setSSAOBias(f32 bias);
    f32 getSSAOBias() const;
    PostProcess* getPostProcess() { return m_postProcess.get(); }

    // Bloom settings
    void setBloomEnabled(bool enabled);
    bool getBloomEnabled() const { return m_bloomEnabled; }
    void setBloomThreshold(f32 threshold);
    f32 getBloomThreshold() const;
    void setBloomIntensity(f32 intensity);
    f32 getBloomIntensity() const;
    void setBloomIterations(u32 iterations);
    u32 getBloomIterations() const;

    // Tonemapping settings
    void setExposure(f32 exposure);
    f32 getExposure() const;
    void setTonemapMode(u32 mode);  // 0=Reinhard, 1=ACES, 2=Uncharted2
    u32 getTonemapMode() const;

    // Section clipping settings
    void setClippingEnabled(bool enabled) { m_clippingEnabled = enabled; }
    bool getClippingEnabled() const { return m_clippingEnabled; }
    void setClipPlane(const vec4& plane) { m_clipPlane = plane; }
    const vec4& getClipPlane() const { return m_clipPlane; }
    void setClipAxis(int axis) { m_clipAxis = axis; updateClipPlane(); }
    int getClipAxis() const { return m_clipAxis; }
    void setClipHeight(f32 height) { m_clipHeight = height; updateClipPlane(); }
    f32 getClipHeight() const { return m_clipHeight; }
    void setClipFlipped(bool flipped) { m_clipFlipped = flipped; updateClipPlane(); }
    bool getClipFlipped() const { return m_clipFlipped; }

    // Stats
    const RenderStats& getStats() const { return m_stats; }

    // PBR Material defaults
    void setDefaultMetallic(f32 metallic) { m_defaultMetallic = metallic; }
    f32 getDefaultMetallic() const { return m_defaultMetallic; }
    void setDefaultRoughness(f32 roughness) { m_defaultRoughness = roughness; }
    f32 getDefaultRoughness() const { return m_defaultRoughness; }
    void setDefaultAO(f32 ao) { m_defaultAO = ao; }
    f32 getDefaultAO() const { return m_defaultAO; }
    void setDefaultEmission(f32 emission) { m_defaultEmission = emission; }
    f32 getDefaultEmission() const { return m_defaultEmission; }

    // Wall material
    void setWallMetallic(f32 metallic) { m_wallMetallic = metallic; }
    f32 getWallMetallic() const { return m_wallMetallic; }
    void setWallRoughness(f32 roughness) { m_wallRoughness = roughness; }
    f32 getWallRoughness() const { return m_wallRoughness; }
    void setWallAO(f32 ao) { m_wallAO = ao; }
    f32 getWallAO() const { return m_wallAO; }
    void setWallEmission(f32 emission) { m_wallEmission = emission; }
    f32 getWallEmission() const { return m_wallEmission; }

    // Roof material
    void setRoofMetallic(f32 metallic) { m_roofMetallic = metallic; }
    f32 getRoofMetallic() const { return m_roofMetallic; }
    void setRoofRoughness(f32 roughness) { m_roofRoughness = roughness; }
    f32 getRoofRoughness() const { return m_roofRoughness; }
    void setRoofAO(f32 ao) { m_roofAO = ao; }
    f32 getRoofAO() const { return m_roofAO; }
    void setRoofEmission(f32 emission) { m_roofEmission = emission; }
    f32 getRoofEmission() const { return m_roofEmission; }

    // Material style
    void setMaterialStyle(MaterialStyle style) { m_materialStyle = style; applyMaterialStyle(); }
    MaterialStyle getMaterialStyle() const { return m_materialStyle; }

    // Get material preset for element type (based on current style)
    MaterialPreset getMaterialForElement(ElementType type) const;

    // Access render pass for ImGui integration
    VkRenderPass getRenderPass() const { return m_renderPass; }
    VkCommandBuffer getCurrentCommandBuffer() const { return m_currentCommandBuffer; }

    // Swapchain resize
    void onResize();

private:
    void createRenderPass();
    void createFramebuffers();
    void createCommandBuffers();
    void createSyncObjects();
    void createDescriptorPool();
    void createDescriptorSets();
    void createUniformBuffers();
    void createPipeline();
    void createSkyPipeline();

    void cleanupSwapchain();
    void recreateSwapchain();

    void updateUniformBuffer(u32 frameIndex);

    // Get element color based on visualization mode
    vec3 getElementColor(const StructuralElement& element, const Building& building, size_t index) const;

    // Apply material style presets to current settings
    void applyMaterialStyle();

    VulkanContext& m_context;

    // Render pass and framebuffers
    VkRenderPass m_renderPass = VK_NULL_HANDLE;
    std::vector<VkFramebuffer> m_framebuffers;

    // Command buffers
    std::vector<VkCommandBuffer> m_commandBuffers;

    // Sync objects - per frame in flight
    std::vector<VkSemaphore> m_imageAvailableSemaphores;  // Per frame in flight
    std::vector<VkSemaphore> m_renderFinishedSemaphores;  // Per frame in flight
    std::vector<VkFence> m_inFlightFences;                // Per frame in flight
    std::vector<VkFence> m_imagesInFlight;                // Per swapchain image - tracks which fence is using each image

    // Descriptors
    VkDescriptorPool m_descriptorPool = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_descriptorSetLayout = VK_NULL_HANDLE;
    std::vector<VkDescriptorSet> m_descriptorSets;

    // Uniform buffers
    std::vector<VkBuffer> m_uniformBuffers;
    std::vector<VkDeviceMemory> m_uniformBuffersMemory;
    std::vector<void*> m_uniformBuffersMapped;

    // Pipeline
    VkPipelineLayout m_pipelineLayout = VK_NULL_HANDLE;
    std::unique_ptr<Pipeline> m_pipeline;
    std::unique_ptr<Pipeline> m_wireframePipeline;

    // HDR pipelines (for post-processing path - no MSAA, HDR render pass)
    std::unique_ptr<Pipeline> m_hdrPipeline;
    std::unique_ptr<Pipeline> m_hdrWireframePipeline;

    // Sky pipeline
    VkPipelineLayout m_skyPipelineLayout = VK_NULL_HANDLE;
    VkPipeline m_skyPipeline = VK_NULL_HANDLE;

    // Dynamic meshes (cached for reuse)
    std::unordered_map<std::string, std::unique_ptr<Mesh>> m_meshCache;
    std::unordered_map<const MeshData*, std::string> m_customMeshKeyCache;  // Maps custom mesh pointers to cache keys
    std::unique_ptr<Mesh> m_gridMesh;

    // Frame state
    u32 m_currentFrame = 0;
    u32 m_imageIndex = 0;
    bool m_frameStarted = false;
    VkCommandBuffer m_currentCommandBuffer = VK_NULL_HANDLE;

    // Camera and time
    Camera m_camera;
    f32 m_time = 0.0f;

    // Visualization mode
    VisualizationMode m_vizMode = VisualizationMode::Structural;

    // Material style
    MaterialStyle m_materialStyle = MaterialStyle::Clean;

    // Shadow mapping
    std::unique_ptr<ShadowMap> m_shadowMap;
    bool m_shadowsEnabled = true;
    vec3 m_lightDirection = glm::normalize(vec3(-0.5f, -1.0f, -0.3f));
    f32 m_shadowBias = 0.02f;  // Adjustable shadow bias
    bool m_outputLinearHDR = false;  // True when rendering to HDR buffer (skip in-shader tonemapping)

    // Environment mapping
    std::unique_ptr<EnvironmentMap> m_envMap;
    VkDescriptorSetLayout m_skyDescriptorSetLayout = VK_NULL_HANDLE;
    std::vector<VkDescriptorSet> m_skyDescriptorSets;
    bool m_useHdrEnvMap = false;

    // Post-processing (SSAO, bloom, etc.)
    std::unique_ptr<PostProcess> m_postProcess;
    bool m_ssaoEnabled = true;
    bool m_bloomEnabled = true;
    bool m_postProcessingEnabled = false;  // Master switch for HDR pipeline (TODO: need HDR-compatible sky pipeline)

    // Section clipping
    bool m_clippingEnabled = false;
    vec4 m_clipPlane = vec4(0.0f, 1.0f, 0.0f, 0.0f);  // Default: Y-up plane at origin
    int m_clipAxis = 1;      // 0=X, 1=Y, 2=Z
    f32 m_clipHeight = 0.0f; // Clip plane position along axis
    bool m_clipFlipped = false;

    void updateClipPlane();

    // PBR Material defaults (general)
    f32 m_defaultMetallic = 0.0f;
    f32 m_defaultRoughness = 0.5f;
    f32 m_defaultAO = 1.0f;
    f32 m_defaultEmission = 0.0f;

    // Wall material
    f32 m_wallMetallic = 0.0f;
    f32 m_wallRoughness = 0.9f;
    f32 m_wallAO = 1.0f;
    f32 m_wallEmission = 0.0f;

    // Roof material
    f32 m_roofMetallic = 0.0f;
    f32 m_roofRoughness = 0.7f;
    f32 m_roofAO = 1.0f;
    f32 m_roofEmission = 0.0f;

    // Stats
    RenderStats m_stats;
};

} // namespace arch
