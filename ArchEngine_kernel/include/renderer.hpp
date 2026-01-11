/**
 * @file renderer.hpp
 * @brief Main rendering interface for ArchEngine
 *
 * This file contains the Renderer class which provides the primary interface
 * for all rendering operations in ArchEngine. It manages the Vulkan rendering
 * pipeline, including frame management, draw calls, post-processing effects,
 * and visualization modes for architectural analysis.
 *
 * @see VulkanContext for low-level Vulkan operations
 * @see PostProcess for SSAO, bloom, and tonemapping
 * @see ShadowMap for shadow mapping implementation
 */

#pragma once

#include "types.hpp"
#include <set>
#include <functional>
#include "vulkan_context.hpp"
#include "pipeline.hpp"
#include "mesh.hpp"
#include "shadow_map.hpp"
#include "environment_map.hpp"
#include "post_process.hpp"
#include "texture.hpp"
#include <unordered_map>

namespace arch {

/**
 * @brief Statistics collected during rendering
 *
 * Contains performance metrics and rendering statistics that can be
 * used for profiling and debugging.
 */
struct RenderStats {
    u32 drawCalls = 0;      ///< Number of draw calls this frame
    u32 triangles = 0;      ///< Total triangles rendered this frame
    f32 frameTimeMs = 0.0f; ///< CPU frame time in milliseconds
    f32 gpuTimeMs = 0.0f;   ///< GPU frame time in milliseconds
};

/**
 * @brief Main rendering class for ArchEngine
 *
 * The Renderer class is the primary interface for all rendering operations.
 * It manages:
 * - Frame lifecycle (begin/end frame)
 * - Render passes (main, HDR, shadow, composite)
 * - Structural element drawing with stress visualization
 * - Post-processing effects (SSAO, bloom, tonemapping)
 * - Material and PBR settings
 * - Visualization modes for different analysis types
 *
 * @note This class is non-copyable. Only one Renderer should exist per VulkanContext.
 *
 * Example usage:
 * @code
 * VulkanContext context(window, config);
 * Renderer renderer(context);
 *
 * renderer.setCamera(camera);
 * renderer.setShadowsEnabled(true);
 * renderer.setSSAOEnabled(true);
 *
 * while (!window.shouldClose()) {
 *     if (renderer.beginFrame()) {
 *         renderer.beginHDRRenderPass();
 *         renderer.drawStructuralFrame(elements, building);
 *         renderer.drawSky();
 *         renderer.endHDRRenderPass();
 *         renderer.runPostProcessing();
 *         renderer.beginCompositePass();
 *         // ImGui rendering here
 *         renderer.endFrame();
 *     }
 * }
 * @endcode
 */
class Renderer {
public:
    /**
     * @brief Construct a new Renderer
     * @param context Reference to the VulkanContext for GPU operations
     */
    Renderer(VulkanContext& context);

    /**
     * @brief Destructor - cleans up all Vulkan resources
     */
    ~Renderer();

    /// @name Non-copyable
    /// @{
    Renderer(const Renderer&) = delete;
    Renderer& operator=(const Renderer&) = delete;
    /// @}

    /// @name Frame Management
    /// @{

    /**
     * @brief Begin a new frame
     * @return true if frame was successfully started, false if swapchain needs recreation
     *
     * Acquires the next swapchain image and begins command buffer recording.
     * Must be called before any draw commands.
     */
    bool beginFrame();

    /**
     * @brief End the current frame
     *
     * Submits the command buffer and presents the image to the swapchain.
     * Must be called after all draw commands are complete.
     */
    void endFrame();
    /// @}

    /// @name Render Pass Management
    /// @{

    /**
     * @brief Begin the main render pass (SDR path)
     * @param clearColor Background clear color (RGBA)
     *
     * Use this for simple rendering without post-processing.
     * For HDR rendering with effects, use beginHDRRenderPass() instead.
     */
    void beginRenderPass(vec4 clearColor = {0.1f, 0.1f, 0.15f, 1.0f});

    /**
     * @brief End the main render pass
     */
    void endRenderPass();

    /**
     * @brief Enable or disable the HDR post-processing pipeline
     * @param enabled True to enable HDR rendering with SSAO, bloom, and tonemapping
     */
    void setPostProcessingEnabled(bool enabled) { m_postProcessingEnabled = enabled; }

    /**
     * @brief Check if post-processing is enabled
     * @return True if HDR pipeline is active
     */
    bool isPostProcessingEnabled() const { return m_postProcessingEnabled; }

    /**
     * @brief Begin HDR render pass for post-processing path
     * @param clearColor Background clear color (RGBA)
     *
     * Renders to an HDR float buffer instead of the swapchain.
     * Follow with endHDRRenderPass(), runPostProcessing(), beginCompositePass().
     */
    void beginHDRRenderPass(vec4 clearColor = {0.1f, 0.1f, 0.15f, 1.0f});

    /**
     * @brief End the HDR render pass
     */
    void endHDRRenderPass();

    /**
     * @brief Run post-processing effects (SSAO, bloom)
     *
     * Must be called after endHDRRenderPass() and before beginCompositePass().
     */
    void runPostProcessing();

    /**
     * @brief Begin the composite pass to output to swapchain
     *
     * Composites HDR scene with effects and applies tonemapping.
     * Leaves render pass open for ImGui overlay rendering.
     */
    void beginCompositePass();
    /// @}

    /// @name Shadow Mapping
    /// @{

    /**
     * @brief Render the shadow pass for directional light shadows
     * @param elements Structural elements to render to shadow map
     *
     * Call before beginRenderPass() or beginHDRRenderPass().
     */
    void renderShadowPass(const std::vector<StructuralElement>& elements);
    /// @}

    /// @name Camera
    /// @{

    /**
     * @brief Set the camera for rendering
     * @param camera Camera containing position, target, FOV, and projection settings
     */
    void setCamera(const Camera& camera);
    /// @}

    /// @name Drawing Functions
    /// @{

    /**
     * @brief Draw a mesh with transform and color
     * @param mesh The mesh to draw
     * @param transform Model transformation matrix
     * @param color RGB color for the mesh
     * @param stress Stress value [0-1+] for stress coloring visualization
     */
    void drawMesh(Mesh& mesh, const mat4& transform, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw a structural beam
     * @param start Start position of the beam
     * @param end End position of the beam
     * @param width Width of the beam cross-section
     * @param height Height of the beam cross-section
     * @param color RGB color
     * @param stress Stress ratio [0-1+] where 1.0 = at capacity
     * @param deflection Deflection value for visualization
     */
    void drawBeam(vec3 start, vec3 end, f32 width, f32 height, vec3 color, f32 stress = 0.0f, f32 deflection = 0.0f);

    /**
     * @brief Draw a structural column
     * @param position Base position of the column
     * @param width Width (X dimension)
     * @param depth Depth (Z dimension)
     * @param height Height (Y dimension)
     * @param color RGB color
     * @param stress Stress ratio [0-1+]
     */
    void drawColumn(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw a column with explicit PBR material parameters
     * @param position Base position
     * @param width Width (X dimension)
     * @param depth Depth (Z dimension)
     * @param height Height (Y dimension)
     * @param color RGB color
     * @param stress Stress ratio
     * @param material Vec4 with (metallic, roughness, ao, emission)
     */
    void drawColumnWithMaterial(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress, vec4 material);

    /**
     * @brief Draw a floor slab
     * @param position Corner position of the floor
     * @param width Width (X dimension)
     * @param depth Depth (Z dimension)
     * @param thickness Thickness (Y dimension)
     * @param color RGB color
     * @param stress Stress ratio [0-1+]
     */
    void drawFloor(vec3 position, f32 width, f32 depth, f32 thickness, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw a door opening
     * @param position Position of the door
     * @param width Width of the door
     * @param height Height of the door
     * @param depth Thickness of the door
     * @param color RGB color
     * @param stress Stress ratio (typically 0 for doors)
     */
    void drawDoor(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw a window
     * @param position Position of the window
     * @param width Width of the window
     * @param height Height of the window
     * @param depth Thickness/depth of the window
     * @param color RGB color (typically blueish for glass)
     * @param stress Stress ratio (typically 0 for windows)
     */
    void drawWindow(vec3 position, f32 width, f32 height, f32 depth, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw a roof element
     * @param position Base corner position
     * @param width Width (X dimension)
     * @param depth Depth (Z dimension)
     * @param height Peak height (Y dimension)
     * @param color RGB color
     * @param stress Stress ratio [0-1+]
     */
    void drawRoof(vec3 position, f32 width, f32 depth, f32 height, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw custom mesh geometry
     * @param meshData Vertex and index data for the mesh
     * @param color RGB color
     * @param stress Stress ratio [0-1+]
     */
    void drawCustomMesh(const MeshData& meshData, vec3 color, f32 stress = 0.0f);

    /**
     * @brief Draw custom mesh with explicit material parameters
     * @param meshData Vertex and index data
     * @param color RGB color
     * @param stress Stress ratio
     * @param material Vec4 with (metallic, roughness, ao, emission)
     */
    void drawCustomMeshWithMaterial(const MeshData& meshData, vec3 color, f32 stress, vec4 material);

    /**
     * @brief Draw mesh with explicit material parameters
     * @param mesh The mesh to draw
     * @param transform Model transformation matrix
     * @param color RGB color
     * @param stress Stress ratio
     * @param material Vec4 with (metallic, roughness, ao, emission)
     */
    void drawMeshWithMaterial(Mesh& mesh, const mat4& transform, vec3 color, f32 stress, vec4 material);

    /**
     * @brief Draw a reference grid on the ground plane
     * @param size Total size of the grid
     * @param spacing Distance between grid lines
     */
    void drawGrid(f32 size = 50.0f, f32 spacing = 1.0f);

    /**
     * @brief Draw an arrow indicating a load
     * @param start Start position of the arrow
     * @param end End position (tip) of the arrow
     * @param magnitude Load magnitude for scaling
     */
    void drawLoadArrow(vec3 start, vec3 end, f32 magnitude);

    /**
     * @brief Draw the sky (procedural or cubemap)
     *
     * Uses environment map if loaded, otherwise renders procedural sky.
     */
    void drawSky();

    /**
     * @brief Draw all structural elements from a building
     * @param elements Vector of structural elements to draw
     * @param building Building data containing thermal/acoustic info for visualization
     * @param selectedIndices Set of element indices that are selected (highlighted)
     *
     * This is the main function for rendering a complete structural frame.
     * Elements are colored based on the current visualization mode.
     */
    void drawStructuralFrame(const std::vector<StructuralElement>& elements, const Building& building, const std::set<int>& selectedIndices = {});
    /// @}

    /// @name Visualization Settings
    /// @{

    /**
     * @brief Set the visualization mode
     * @param mode Visualization mode (Structural, Thermal, Lighting, Acoustic, Material, Wireframe)
     *
     * Changes how elements are colored:
     * - Structural: Stress-based coloring (green=safe, red=failure)
     * - Thermal: Temperature gradient
     * - Lighting: Daylight/lux levels
     * - Acoustic: Sound absorption
     * - Material: Material type coloring
     * - Wireframe: Wire outline mode
     */
    void setVisualizationMode(VisualizationMode mode) { m_vizMode = mode; }

    /** @brief Get current visualization mode */
    VisualizationMode getVisualizationMode() const { return m_vizMode; }
    /// @}

    /// @name Shadow Settings
    /// @{

    /** @brief Enable or disable shadow mapping */
    void setShadowsEnabled(bool enabled) { m_shadowsEnabled = enabled; }

    /** @brief Check if shadows are enabled */
    bool getShadowsEnabled() const { return m_shadowsEnabled; }

    /**
     * @brief Set the directional light direction
     * @param dir Direction vector (will be normalized)
     */
    void setLightDirection(const vec3& dir) { m_lightDirection = glm::normalize(dir); }

    /** @brief Get the current light direction */
    const vec3& getLightDirection() const { return m_lightDirection; }

    /**
     * @brief Set shadow depth bias to reduce shadow acne
     * @param bias Bias value (typically 0.001 - 0.05)
     */
    void setShadowBias(f32 bias) { m_shadowBias = bias; }

    /** @brief Get current shadow bias */
    f32 getShadowBias() const { return m_shadowBias; }
    /// @}

    /// @name Environment Map Settings
    /// @{

    /**
     * @brief Load an HDR environment map for image-based lighting
     * @param filepath Path to equirectangular HDR image
     * @return true if successfully loaded
     */
    bool loadHdrEnvironment(const std::string& filepath);

    /** @brief Enable or disable HDR environment map usage */
    void setUseHdrEnvMap(bool use) { m_useHdrEnvMap = use; }

    /** @brief Check if HDR environment map is being used */
    bool getUseHdrEnvMap() const { return m_useHdrEnvMap; }

    /** @brief Check if an HDR environment map is loaded */
    bool hasHdrEnvMap() const { return m_envMap && m_envMap->isLoaded(); }
    /// @}

    /// @name SSAO Settings
    /// @{

    /** @brief Enable or disable Screen-Space Ambient Occlusion */
    void setSSAOEnabled(bool enabled);

    /** @brief Check if SSAO is enabled */
    bool getSSAOEnabled() const { return m_ssaoEnabled; }

    /**
     * @brief Set SSAO sampling radius
     * @param radius Radius in view space (typically 0.1 - 1.0)
     */
    void setSSAORadius(f32 radius);

    /** @brief Get current SSAO radius */
    f32 getSSAORadius() const;

    /**
     * @brief Set SSAO intensity/strength
     * @param intensity Intensity multiplier (typically 1.0 - 3.0)
     */
    void setSSAOIntensity(f32 intensity);

    /** @brief Get current SSAO intensity */
    f32 getSSAOIntensity() const;

    /**
     * @brief Set SSAO depth bias
     * @param bias Bias to prevent self-occlusion (typically 0.01 - 0.1)
     */
    void setSSAOBias(f32 bias);

    /** @brief Get current SSAO bias */
    f32 getSSAOBias() const;

    /** @brief Get raw pointer to PostProcess for advanced configuration */
    PostProcess* getPostProcess() { return m_postProcess.get(); }
    /// @}

    /// @name Bloom Settings
    /// @{

    /** @brief Enable or disable bloom effect */
    void setBloomEnabled(bool enabled);

    /** @brief Check if bloom is enabled */
    bool getBloomEnabled() const { return m_bloomEnabled; }

    /**
     * @brief Set bloom brightness threshold
     * @param threshold Luminance threshold for bloom extraction (typically 0.8 - 2.0)
     */
    void setBloomThreshold(f32 threshold);

    /** @brief Get current bloom threshold */
    f32 getBloomThreshold() const;

    /**
     * @brief Set bloom intensity
     * @param intensity Bloom strength multiplier (typically 0.1 - 1.0)
     */
    void setBloomIntensity(f32 intensity);

    /** @brief Get current bloom intensity */
    f32 getBloomIntensity() const;

    /**
     * @brief Set number of bloom blur iterations
     * @param iterations Number of blur passes (more = softer bloom)
     */
    void setBloomIterations(u32 iterations);

    /** @brief Get current bloom blur iterations */
    u32 getBloomIterations() const;
    /// @}

    /// @name Tonemapping Settings
    /// @{

    /**
     * @brief Set exposure value for HDR tonemapping
     * @param exposure Exposure multiplier (typically 0.5 - 3.0)
     */
    void setExposure(f32 exposure);

    /** @brief Get current exposure value */
    f32 getExposure() const;

    /**
     * @brief Set tonemapping operator
     * @param mode 0=Reinhard, 1=ACES Filmic, 2=Uncharted2
     */
    void setTonemapMode(u32 mode);

    /** @brief Get current tonemapping mode */
    u32 getTonemapMode() const;
    /// @}

    /// @name Section Clipping Settings
    /// @{

    /** @brief Enable or disable section clipping plane */
    void setClippingEnabled(bool enabled) { m_clippingEnabled = enabled; }

    /** @brief Check if clipping is enabled */
    bool getClippingEnabled() const { return m_clippingEnabled; }

    /**
     * @brief Set the clipping plane directly
     * @param plane Plane equation (normal.xyz, distance.w)
     */
    void setClipPlane(const vec4& plane) { m_clipPlane = plane; }

    /** @brief Get current clipping plane */
    const vec4& getClipPlane() const { return m_clipPlane; }

    /**
     * @brief Set clipping axis
     * @param axis 0=X, 1=Y, 2=Z
     */
    void setClipAxis(int axis) { m_clipAxis = axis; updateClipPlane(); }

    /** @brief Get current clipping axis */
    int getClipAxis() const { return m_clipAxis; }

    /**
     * @brief Set clipping plane height/position along axis
     * @param height Position along the clip axis
     */
    void setClipHeight(f32 height) { m_clipHeight = height; updateClipPlane(); }

    /** @brief Get current clip height */
    f32 getClipHeight() const { return m_clipHeight; }

    /**
     * @brief Flip the clipping direction
     * @param flipped True to clip below instead of above
     */
    void setClipFlipped(bool flipped) { m_clipFlipped = flipped; updateClipPlane(); }

    /** @brief Check if clipping is flipped */
    bool getClipFlipped() const { return m_clipFlipped; }
    /// @}

    /// @name Statistics
    /// @{

    /**
     * @brief Get rendering statistics from the last frame
     * @return RenderStats with draw calls, triangles, and timing
     */
    const RenderStats& getStats() const { return m_stats; }
    /// @}

    /// @name PBR Material Settings
    /// @{

    /**
     * @brief Set default metallic value for elements without textures
     * @param metallic Metallic value [0-1] where 1 = fully metallic
     */
    void setDefaultMetallic(f32 metallic) { m_defaultMetallic = metallic; }

    /** @brief Get default metallic value */
    f32 getDefaultMetallic() const { return m_defaultMetallic; }

    /**
     * @brief Set default roughness value
     * @param roughness Roughness value [0-1] where 0 = mirror smooth
     */
    void setDefaultRoughness(f32 roughness) { m_defaultRoughness = roughness; }

    /** @brief Get default roughness value */
    f32 getDefaultRoughness() const { return m_defaultRoughness; }

    /**
     * @brief Set default ambient occlusion value
     * @param ao AO value [0-1] where 1 = fully lit
     */
    void setDefaultAO(f32 ao) { m_defaultAO = ao; }

    /** @brief Get default AO value */
    f32 getDefaultAO() const { return m_defaultAO; }

    /**
     * @brief Set default emission intensity
     * @param emission Emission multiplier [0+]
     */
    void setDefaultEmission(f32 emission) { m_defaultEmission = emission; }

    /** @brief Get default emission value */
    f32 getDefaultEmission() const { return m_defaultEmission; }
    /// @}

    /// @name Wall Material Settings
    /// @{

    /** @brief Set metallic value for wall elements */
    void setWallMetallic(f32 metallic) { m_wallMetallic = metallic; }
    f32 getWallMetallic() const { return m_wallMetallic; }

    /** @brief Set roughness value for wall elements */
    void setWallRoughness(f32 roughness) { m_wallRoughness = roughness; }
    f32 getWallRoughness() const { return m_wallRoughness; }

    /** @brief Set AO value for wall elements */
    void setWallAO(f32 ao) { m_wallAO = ao; }
    f32 getWallAO() const { return m_wallAO; }

    /** @brief Set emission value for wall elements */
    void setWallEmission(f32 emission) { m_wallEmission = emission; }
    f32 getWallEmission() const { return m_wallEmission; }
    /// @}

    /// @name Roof Material Settings
    /// @{

    /** @brief Set metallic value for roof elements */
    void setRoofMetallic(f32 metallic) { m_roofMetallic = metallic; }
    f32 getRoofMetallic() const { return m_roofMetallic; }

    /** @brief Set roughness value for roof elements */
    void setRoofRoughness(f32 roughness) { m_roofRoughness = roughness; }
    f32 getRoofRoughness() const { return m_roofRoughness; }

    /** @brief Set AO value for roof elements */
    void setRoofAO(f32 ao) { m_roofAO = ao; }
    f32 getRoofAO() const { return m_roofAO; }

    /** @brief Set emission value for roof elements */
    void setRoofEmission(f32 emission) { m_roofEmission = emission; }
    f32 getRoofEmission() const { return m_roofEmission; }

    /**
     * @brief Set UV scale for material texture tiling
     * @param scale UV multiplier (higher = more repetition)
     */
    void setMaterialUVScale(f32 scale) { m_materialUVScale = scale; }
    f32 getMaterialUVScale() const { return m_materialUVScale; }

    /**
     * @brief Set normal map strength
     * @param strength Normal map intensity multiplier
     */
    void setNormalStrength(f32 strength) { m_normalStrength = strength; }
    f32 getNormalStrength() const { return m_normalStrength; }

    // Material adjustment parameters
    void setMaterialBrightness(f32 v) { m_materialBrightness = v; }
    f32 getMaterialBrightness() const { return m_materialBrightness; }
    void setMaterialContrast(f32 v) { m_materialContrast = v; }
    f32 getMaterialContrast() const { return m_materialContrast; }
    void setMaterialSaturation(f32 v) { m_materialSaturation = v; }
    f32 getMaterialSaturation() const { return m_materialSaturation; }
    void setMaterialRoughnessOffset(f32 v) { m_materialRoughnessOffset = v; }
    f32 getMaterialRoughnessOffset() const { return m_materialRoughnessOffset; }
    void setMaterialMetallicOffset(f32 v) { m_materialMetallicOffset = v; }
    f32 getMaterialMetallicOffset() const { return m_materialMetallicOffset; }
    void setMaterialAOStrength(f32 v) { m_materialAOStrength = v; }
    f32 getMaterialAOStrength() const { return m_materialAOStrength; }
    void setMaterialTint(vec3 v) { m_materialTint = v; }
    vec3 getMaterialTint() const { return m_materialTint; }
    /// @}

    /// @name Material Style
    /// @{

    /**
     * @brief Set the overall material style preset
     * @param style MaterialStyle (Realistic, Clean, Schematic, Blueprint)
     *
     * Applies a preset of material settings optimized for the style.
     */
    void setMaterialStyle(MaterialStyle style) { m_materialStyle = style; applyMaterialStyle(); }

    /** @brief Get current material style */
    MaterialStyle getMaterialStyle() const { return m_materialStyle; }
    /// @}

    /// @name Material Library
    /// @{

    /** @brief Get the root directory for material textures */
    const std::string& getMaterialRoot() const { return m_materialRoot; }

    /**
     * @brief Reload materials from a directory
     * @param root Root directory containing material subdirectories
     * @return true if successfully loaded
     */
    bool reloadMaterialLibrary(const std::string& root);

    /**
     * @brief Get list of loaded material names
     * @return Vector of material names available for use
     */
    std::vector<std::string> getMaterialNames() const;

    /**
     * @brief Get material preset for an element type
     * @param type The element type (Beam, Column, Wall, etc.)
     * @return MaterialPreset with appropriate PBR values for the style
     */
    MaterialPreset getMaterialForElement(ElementType type) const;
    /// @}

    /// @name Vulkan Access
    /// @{

    /** @brief Get the render pass handle for ImGui integration */
    VkRenderPass getRenderPass() const { return m_renderPass; }

    /** @brief Get the current command buffer for custom draw commands */
    VkCommandBuffer getCurrentCommandBuffer() const { return m_currentCommandBuffer; }
    /// @}

    /// @name Resize Handling
    /// @{

    /**
     * @brief Handle window/swapchain resize
     *
     * Call when the window size changes to recreate framebuffers.
     */
    void onResize();
    /// @}

    /// @name High-Resolution Rendering
    /// @{

    /**
     * @brief Render the current scene to a high-resolution offscreen buffer
     * @param elements Structural elements to render
     * @param building Building data for visualization
     * @param width Target width in pixels
     * @param height Target height in pixels
     * @param samples Number of samples for anti-aliasing accumulation
     * @param progressCallback Optional callback for progress updates (0.0 - 1.0)
     * @return true if rendering succeeded
     *
     * This function renders the scene to an offscreen buffer at the specified
     * resolution. For multi-sample renders, it accumulates multiple frames with
     * jittered camera positions for high-quality anti-aliasing.
     */
    bool renderHighRes(
        const std::vector<StructuralElement>& elements,
        const Building& building,
        u32 width,
        u32 height,
        int samples = 1,
        float brightness = 1.3f,
        std::function<void(float)> progressCallback = nullptr
    );

    /**
     * @brief Get the high-res render result as raw pixel data
     * @return Vector of RGBA8 pixel data (4 bytes per pixel)
     *
     * Call after renderHighRes() to retrieve the rendered image.
     * The data is in row-major order, top-to-bottom, left-to-right.
     */
    const std::vector<u8>& getHighResPixels() const { return m_highResPixels; }

    /**
     * @brief Get high-res render width
     */
    u32 getHighResWidth() const { return m_highResWidth; }

    /**
     * @brief Get high-res render height
     */
    u32 getHighResHeight() const { return m_highResHeight; }

    /**
     * @brief Save the high-res render to a PNG file
     * @param filepath Output file path
     * @return true if save succeeded
     */
    bool saveHighResPNG(const std::string& filepath);

    /**
     * @brief Save the high-res render to an EXR (HDR) file
     * @param filepath Output file path
     * @return true if save succeeded
     */
    bool saveHighResEXR(const std::string& filepath);
    /// @}

private:
    static constexpr u32 kMaxMaterialSets = 128;

    void createRenderPass();
    void createFramebuffers();
    void createCommandBuffers();
    void createSyncObjects();
    void createDescriptorPool();
    void createDescriptorSets();
    void createMaterialDescriptorSetLayout();
    void createDefaultMaterialDescriptorSet();
    void createUniformBuffers();
    void createPipeline();
    void createSkyPipeline();

    void cleanupSwapchain();
    void recreateSwapchain();

    void updateUniformBuffer(u32 frameIndex);

    VkDescriptorSet createMaterialDescriptorSetForMaterial(const Material& material);
    void buildMaterialDescriptorSets();
    void bindMaterialDescriptorSet(const std::string& materialName);
    std::string resolveMaterialName(const StructuralElement& element) const;

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

    // Material descriptor set (set 1)
    VkDescriptorSetLayout m_materialDescriptorSetLayout = VK_NULL_HANDLE;
    VkDescriptorSet m_defaultMaterialDescriptorSet = VK_NULL_HANDLE;
    std::unordered_map<std::string, VkDescriptorSet> m_materialDescriptorSets;
    std::unique_ptr<MaterialLibrary> m_materialLibrary;
    std::string m_materialRoot = "materials";

    // Uniform buffers
    std::vector<VkBuffer> m_uniformBuffers;
    std::vector<VkDeviceMemory> m_uniformBuffersMemory;
    std::vector<void*> m_uniformBuffersMapped;

    // Pipeline
    VkPipelineLayout m_pipelineLayout = VK_NULL_HANDLE;
    std::unique_ptr<Pipeline> m_pipeline;
    std::unique_ptr<Pipeline> m_wireframePipeline;
    std::unique_ptr<Pipeline> m_transparentPipeline;  // For glass/transparent materials

    // HDR pipelines (for post-processing path - no MSAA, HDR render pass)
    std::unique_ptr<Pipeline> m_hdrPipeline;
    std::unique_ptr<Pipeline> m_hdrWireframePipeline;
    std::unique_ptr<Pipeline> m_hdrTransparentPipeline;  // For glass/transparent in HDR mode

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
    VisualizationMode m_vizMode = VisualizationMode::Material;

    // Material style
    MaterialStyle m_materialStyle = MaterialStyle::Realistic;

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
    f32 m_materialUVScale = 1.0f;
    f32 m_normalStrength = 1.0f;
    f32 m_materialBrightness = 0.0f;
    f32 m_materialContrast = 1.0f;
    f32 m_materialSaturation = 1.0f;
    f32 m_materialRoughnessOffset = 0.0f;
    f32 m_materialMetallicOffset = 0.0f;
    f32 m_materialAOStrength = 1.0f;
    vec3 m_materialTint = vec3(1.0f);

    // Stats
    RenderStats m_stats;

    // High-res rendering resources
    VkImage m_highResImage = VK_NULL_HANDLE;
    VkDeviceMemory m_highResMemory = VK_NULL_HANDLE;
    VkImageView m_highResView = VK_NULL_HANDLE;
    VkImage m_highResDepthImage = VK_NULL_HANDLE;
    VkDeviceMemory m_highResDepthMemory = VK_NULL_HANDLE;
    VkImageView m_highResDepthView = VK_NULL_HANDLE;
    VkFramebuffer m_highResFramebuffer = VK_NULL_HANDLE;
    VkRenderPass m_highResRenderPass = VK_NULL_HANDLE;
    std::unique_ptr<Pipeline> m_highResPipeline;  // Single-sample pipeline for high-res
    std::unique_ptr<Pipeline> m_highResTransparentPipeline;  // Transparent pipeline for high-res
    std::vector<u8> m_highResPixels;
    std::vector<f32> m_highResHDRPixels;  // For EXR export
    u32 m_highResWidth = 0;
    u32 m_highResHeight = 0;

    void createHighResResources(u32 width, u32 height);
    void cleanupHighResResources();
    void copyHighResImageToBuffer();
};

} // namespace arch
