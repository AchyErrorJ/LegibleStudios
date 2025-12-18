#pragma once

#include "types.hpp"
#include <set>
#include "vulkan_context.hpp"
#include "pipeline.hpp"
#include "mesh.hpp"

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

    void setCamera(const Camera& camera);

    // Draw structural elements with color (stress in alpha controls shader behavior)
    void drawMesh(Mesh& mesh, const mat4& transform, vec3 color, f32 stress = 0.0f);
    void drawBeam(vec3 start, vec3 end, f32 width, f32 height, vec3 color, f32 stress = 0.0f, f32 deflection = 0.0f);
    void drawColumn(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);
    void drawFloor(vec3 position, f32 width, f32 depth, f32 thickness, vec3 color, f32 stress = 0.0f);
    void drawDoor(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);
    void drawWindow(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);
    void drawRoof(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);
    void drawCustomMesh(const MeshData& meshData, vec3 color, f32 stress = 0.0f);
    void drawGrid(f32 size = 50.0f, f32 spacing = 1.0f);
    void drawLoadArrow(vec3 start, vec3 end, f32 magnitude);

    // Draw structural frame from analysis data
    void drawStructuralFrame(const std::vector<StructuralElement>& elements, const Building& building, const std::set<int>& selectedIndices = {});

    // Visualization mode
    void setVisualizationMode(VisualizationMode mode) { m_vizMode = mode; }
    VisualizationMode getVisualizationMode() const { return m_vizMode; }

    // Stats
    const RenderStats& getStats() const { return m_stats; }

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

    void cleanupSwapchain();
    void recreateSwapchain();

    void updateUniformBuffer(u32 frameIndex);

    // Get element color based on visualization mode
    vec3 getElementColor(const StructuralElement& element, const Building& building, size_t index) const;

    VulkanContext& m_context;

    // Render pass and framebuffers
    VkRenderPass m_renderPass = VK_NULL_HANDLE;
    std::vector<VkFramebuffer> m_framebuffers;

    // Command buffers
    std::vector<VkCommandBuffer> m_commandBuffers;

    // Sync objects
    std::vector<VkSemaphore> m_imageAvailableSemaphores;
    std::vector<VkSemaphore> m_renderFinishedSemaphores;
    std::vector<VkFence> m_inFlightFences;

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

    // Dynamic meshes (cached for reuse)
    std::unordered_map<std::string, std::unique_ptr<Mesh>> m_meshCache;
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

    // Stats
    RenderStats m_stats;
};

} // namespace arch
