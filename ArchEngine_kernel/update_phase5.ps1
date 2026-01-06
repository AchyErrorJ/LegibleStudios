# Phase 5: Section Clipping Updates

# 1. Update renderer.hpp - Add section clipping methods
$rendererHpp = "X:\arch\Software\Archengine_suite_kernel\ArchEngine_kernel\include\renderer.hpp"
$hppContent = Get-Content $rendererHpp -Raw

# Add section clipping methods after shadow settings
$oldShadowSettings = @"
    // Shadow settings
    void setShadowsEnabled(bool enabled) { m_shadowsEnabled = enabled; }
    bool getShadowsEnabled() const { return m_shadowsEnabled; }
    void setLightDirection(const vec3& dir) { m_lightDirection = glm::normalize(dir); }
    const vec3& getLightDirection() const { return m_lightDirection; }
"@

$newShadowSettings = @"
    // Shadow settings
    void setShadowsEnabled(bool enabled) { m_shadowsEnabled = enabled; }
    bool getShadowsEnabled() const { return m_shadowsEnabled; }
    void setLightDirection(const vec3& dir) { m_lightDirection = glm::normalize(dir); }
    const vec3& getLightDirection() const { return m_lightDirection; }

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
"@

$hppContent = $hppContent.Replace($oldShadowSettings, $newShadowSettings)

# Add section clipping members after shadow mapping members
$oldShadowMembers = @"
    // Shadow mapping
    std::unique_ptr<ShadowMap> m_shadowMap;
    bool m_shadowsEnabled = true;
    vec3 m_lightDirection = glm::normalize(vec3(-0.5f, -1.0f, -0.3f));
"@

$newShadowMembers = @"
    // Shadow mapping
    std::unique_ptr<ShadowMap> m_shadowMap;
    bool m_shadowsEnabled = true;
    vec3 m_lightDirection = glm::normalize(vec3(-0.5f, -1.0f, -0.3f));

    // Section clipping
    bool m_clippingEnabled = false;
    vec4 m_clipPlane = vec4(0.0f, 1.0f, 0.0f, 0.0f);  // Default: Y-up plane at origin
    int m_clipAxis = 1;      // 0=X, 1=Y, 2=Z
    f32 m_clipHeight = 0.0f; // Clip plane position along axis
    bool m_clipFlipped = false;

    void updateClipPlane();
"@

$hppContent = $hppContent.Replace($oldShadowMembers, $newShadowMembers)

Set-Content $rendererHpp -Value $hppContent -NoNewline
Write-Host "1. Updated renderer.hpp with section clipping methods"

# 2. Update renderer.cpp - Add updateClipPlane and update UBO
$rendererCpp = "X:\arch\Software\Archengine_suite_kernel\ArchEngine_kernel\src\renderer.cpp"
$cppContent = Get-Content $rendererCpp -Raw

# Update the UBO update function to use clipping settings
$oldUboClip = @"
    // Section clipping plane (placeholder - Phase 5 will make this configurable)
    ubo.clipPlane = vec4(0.0f, 1.0f, 0.0f, 1000.0f);  // Y-up plane far above scene
    ubo.enableClipping = 0;  // Disabled by default
"@

$newUboClip = @"
    // Section clipping plane
    ubo.clipPlane = m_clipPlane;
    ubo.enableClipping = m_clippingEnabled ? 1 : 0;
"@

$cppContent = $cppContent.Replace($oldUboClip, $newUboClip)

# Add updateClipPlane function before the end of file
$oldNamespaceEnd = @"
} // namespace arch
"@

$newNamespaceEnd = @"
void Renderer::updateClipPlane() {
    // Create clip plane based on axis and height
    // Clip plane equation: ax + by + cz + d = 0
    // Points with dot(pos, plane) > 0 are kept
    vec3 normal(0.0f);
    switch (m_clipAxis) {
        case 0: normal.x = m_clipFlipped ? -1.0f : 1.0f; break;  // X axis
        case 1: normal.y = m_clipFlipped ? -1.0f : 1.0f; break;  // Y axis
        case 2: normal.z = m_clipFlipped ? -1.0f : 1.0f; break;  // Z axis
    }
    // d = -dot(normal, point_on_plane)
    // point_on_plane is (height, 0, 0) for X axis, etc.
    f32 d = -m_clipHeight * (m_clipFlipped ? -1.0f : 1.0f);
    m_clipPlane = vec4(normal, d);
}

} // namespace arch
"@

$cppContent = $cppContent.Replace($oldNamespaceEnd, $newNamespaceEnd)

Set-Content $rendererCpp -Value $cppContent -NoNewline
Write-Host "2. Updated renderer.cpp with section clipping implementation"

# 3. Update imgui_layer.hpp - Add section control panel method
$imguiHpp = "X:\arch\Software\Archengine_suite_kernel\ArchEngine_kernel\include\imgui_layer.hpp"
$imguiHppContent = Get-Content $imguiHpp -Raw

# Add forward declaration for Renderer
$oldForwardDecl = @"
// Forward declarations
struct Building;
struct FrameAnalysis;
"@

$newForwardDecl = @"
// Forward declarations
struct Building;
struct FrameAnalysis;
class Renderer;
"@

$imguiHppContent = $imguiHppContent.Replace($oldForwardDecl, $newForwardDecl)

# Add section panel method after drawPerformancePanel
$oldPerfPanel = @"
    void drawPerformancePanel(f32 fps, u32 drawCalls, u32 triangles);
    void drawGeometryEditor(bool& show);
"@

$newPerfPanel = @"
    void drawPerformancePanel(f32 fps, u32 drawCalls, u32 triangles);
    void drawRenderSettingsPanel(Renderer& renderer, bool& show);
    void drawGeometryEditor(bool& show);
"@

$imguiHppContent = $imguiHppContent.Replace($oldPerfPanel, $newPerfPanel)

Set-Content $imguiHpp -Value $imguiHppContent -NoNewline
Write-Host "3. Updated imgui_layer.hpp with render settings panel"

Write-Host "Phase 5 header updates complete!"
