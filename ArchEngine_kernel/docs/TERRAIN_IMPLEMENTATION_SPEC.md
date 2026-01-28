# Terrain Mesh Rendering - Implementation Specification

## Overview

Add support for rendering terrain meshes generated from Google Maps Elevation API data. The Python side (CAD application) already generates terrain mesh data. This spec covers the C++ kernel changes needed to render it.

## Context

- Terrain data comes from `core/terrain.py` in the CAD application
- Mesh format: vertices (position, normal, UV) and triangle indices
- Elevation data is in feet, converted to millimeters for rendering
- Terrain should render with height-based coloring (topographic visualization)

## Files to Modify

1. **include/types.hpp** - Add terrain mesh data structure
2. **src/geometry_loader.cpp** - Parse terrain from JSON
3. **include/renderer.hpp** - Add terrain rendering method
4. **src/renderer.cpp** - Implement terrain rendering
5. **shaders/terrain.vert** (new) - Terrain vertex shader
6. **shaders/terrain.frag** (new) - Terrain fragment shader with elevation coloring

---

## 1. Data Structure (types.hpp)

### Add TerrainMesh struct after MeshData (around line 125)

```cpp
// Terrain mesh from elevation data
struct TerrainMesh {
    std::vector<Vertex> vertices;  // Position, normal, color, UV, stress (unused)
    std::vector<u32> indices;      // Triangle indices

    f32 width_ft;                  // Property width in feet
    f32 depth_ft;                  // Property depth in feet
    f32 min_elevation;             // Minimum elevation in feet
    f32 max_elevation;             // Maximum elevation in feet

    bool hasData() const { return !vertices.empty() && !indices.empty(); }
};
```

### Add terrain_mesh field to Building struct (around line 554)

```cpp
struct Building {
    std::string name;
    std::vector<StructuralElement> elements;
    std::unordered_map<std::string, ThermalData> thermalData;
    std::unordered_map<std::string, LightingData> lightingData;
    std::unordered_map<std::string, AcousticData> acousticData;

    // Parametric wall system
    std::vector<WallType> wallTypes;
    std::vector<ParametricWall> parametricWalls;
    std::vector<WallCorner> wallCorners;

    // Terrain mesh from elevation data
    TerrainMesh terrainMesh;
};
```

---

## 2. JSON Parsing (geometry_loader.cpp)

### Add to from_json function (after line 443)

```cpp
// Parse terrain mesh
if (j.contains("terrain_mesh")) {
    const auto& tm = j["terrain_mesh"];

    b.terrainMesh.width_ft = tm.value("width_ft", 100.0f);
    b.terrainMesh.depth_ft = tm.value("depth_ft", 120.0f);
    b.terrainMesh.min_elevation = tm.value("min_elevation", 0.0f);
    b.terrainMesh.max_elevation = tm.value("max_elevation", 100.0f);

    // Parse vertices
    if (tm.contains("vertices")) {
        for (const auto& v : tm["vertices"]) {
            Vertex vertex;

            // Position (convert feet to millimeters: 1 ft = 304.8 mm)
            if (v.contains("position")) {
                f32 x = v["position"][0];
                f32 y = v["position"][1];
                f32 z = v["position"][2];
                vertex.position = vec3(x * 304.8f, y * 304.8f, z * 304.8f);
            }

            // Normal
            if (v.contains("normal")) {
                vertex.normal = vec3(v["normal"][0], v["normal"][1], v["normal"][2]);
            }

            // UV coordinates
            if (v.contains("uv")) {
                vertex.texCoord = vec2(v["uv"][0], v["uv"][1]);
            }

            // Color (will be computed from elevation in shader)
            vertex.color = vec3(0.5f, 0.5f, 0.5f);
            vertex.stress = 0.0f;

            b.terrainMesh.vertices.push_back(vertex);
        }
    }

    // Parse indices
    if (tm.contains("indices")) {
        for (const auto& idx : tm["indices"]) {
            b.terrainMesh.indices.push_back(idx);
        }
    }

    std::cout << "[Terrain] Loaded mesh: " << b.terrainMesh.vertices.size()
              << " vertices, " << b.terrainMesh.indices.size() / 3 << " triangles\n";
    std::cout << "[Terrain] Elevation range: " << b.terrainMesh.min_elevation
              << "' to " << b.terrainMesh.max_elevation << "'\n";
}
```

---

## 3. Renderer Header (renderer.hpp)

### Add public method (after drawStructuralFrame, around line 200)

```cpp
/**
 * @brief Draw terrain mesh with elevation-based coloring
 * @param terrainMesh The terrain mesh to render
 */
void drawTerrain(const TerrainMesh& terrainMesh);
```

### Add private member (in class, around line 400)

```cpp
// Terrain rendering pipeline
std::unique_ptr<Pipeline> terrainPipeline_;
VkPipelineLayout terrainPipelineLayout_ = VK_NULL_HANDLE;
VkDescriptorSetLayout terrainDescriptorLayout_ = VK_NULL_HANDLE;

// Terrain vertex/index buffers
VkBuffer terrainVertexBuffer_ = VK_NULL_HANDLE;
VkDeviceMemory terrainVertexMemory_ = VK_NULL_HANDLE;
VkBuffer terrainIndexBuffer_ = VK_NULL_HANDLE;
VkDeviceMemory terrainIndexMemory_ = VK_NULL_HANDLE;
u32 terrainIndexCount_ = 0;
```

---

## 4. Renderer Implementation (renderer.cpp)

### Initialization (in constructor or initRenderPasses)

Create the terrain pipeline descriptor set layout and pipeline:

```cpp
void Renderer::initTerrainPipeline() {
    // Descriptor set layout (uniform buffers for camera, elevation range)
    std::array<VkDescriptorSetLayoutBinding, 2> bindings{};

    // Binding 0: Uniform buffer (MVP + elevation range)
    bindings[0].binding = 0;
    bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    bindings[0].descriptorCount = 1;
    bindings[0].stageFlags = VK_SHADER_STAGE_VERTEX_BIT;

    // Binding 1: Texture (optional, for contour lines)
    bindings[1].binding = 1;
    bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
    bindings[1].descriptorCount = 1;
    bindings[1].stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

    VkDescriptorSetLayoutCreateInfo layoutInfo{};
    layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    layoutInfo.bindingCount = static_cast<u32>(bindings.size());
    layoutInfo.pBindings = bindings.data();

    vkCreateDescriptorSetLayout(device_, &layoutInfo, nullptr, &terrainDescriptorLayout_);

    // Pipeline layout
    VkPipelineLayoutCreateInfo pipelineLayoutInfo{};
    pipelineLayoutInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    pipelineLayoutInfo.setLayoutCount = 1;
    pipelineLayoutInfo.pSetLayouts = &terrainDescriptorLayout_;

    vkCreatePipelineLayout(device_, &pipelineLayoutInfo, nullptr, &terrainPipelineLayout_);

    // Graphics pipeline (similar to structural pipeline but with terrain shaders)
    PipelineConfig config{};
    config.vertexShader = "shaders/terrain.vert.spv";
    config.fragmentShader = "shaders/terrain.frag.spv";
    config.vertexBindings = Vertex::getBindingDescriptions();
    config.vertexAttributes = Vertex::getAttributeDescriptions();
    config.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
    config.cullMode = VK_CULL_MODE_BACK_BIT;
    config.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
    config.depthTestEnable = VK_TRUE;
    config.depthWriteEnable = VK_TRUE;

    terrainPipeline_ = std::make_unique<Pipeline>(context_, config, terrainPipelineLayout_, renderPass_);
}
```

### Buffer Upload Method

```cpp
void Renderer::uploadTerrainBuffers(const TerrainMesh& terrain) {
    if (!terrain.hasData()) return;

    // Upload vertices
    VkDeviceSize vertexBufferSize = sizeof(Vertex) * terrain.vertices.size();
    createBuffer(vertexBufferSize, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
                 VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                 terrainVertexBuffer_, terrainVertexMemory_);

    void* data;
    vkMapMemory(device_, terrainVertexMemory_, 0, vertexBufferSize, 0, &data);
    memcpy(data, terrain.vertices.data(), vertexBufferSize);
    vkUnmapMemory(device_, terrainVertexMemory_);

    // Upload indices
    VkDeviceSize indexBufferSize = sizeof(u32) * terrain.indices.size();
    createBuffer(indexBufferSize, VK_BUFFER_USAGE_INDEX_BUFFER_BIT,
                 VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT,
                 terrainIndexBuffer_, terrainIndexMemory_);

    vkMapMemory(device_, terrainIndexMemory_, 0, indexBufferSize, 0, &data);
    memcpy(data, terrain.indices.data(), indexBufferSize);
    vkUnmapMemory(device_, terrainIndexMemory_);

    terrainIndexCount_ = static_cast<u32>(terrain.indices.size());
}
```

### Draw Method

```cpp
void Renderer::drawTerrain(const TerrainMesh& terrain) {
    if (!terrain.hasData()) return;

    // Upload buffers if changed (add dirty tracking in production)
    uploadTerrainBuffers(terrain);

    // Update elevation range in push constants or uniform buffer
    struct TerrainPushConstants {
        float minElevation;
        float maxElevation;
        float elevationRange;  // max - min
        float padding;
    } pushConsts{
        terrain.min_elevation,
        terrain.max_elevation,
        terrain.max_elevation - terrain.min_elevation,
        0.0f
    };

    // Bind pipeline
    vkCmdBindPipeline(commandBuffer_, VK_PIPELINE_BIND_POINT_GRAPHICS, terrainPipeline_->getPipeline());

    // Bind vertex/index buffers
    VkBuffer vertexBuffers[] = {terrainVertexBuffer_};
    VkDeviceSize offsets[] = {0};
    vkCmdBindVertexBuffers(commandBuffer_, 0, 1, vertexBuffers, offsets);
    vkCmdBindIndexBuffer(commandBuffer_, terrainIndexBuffer_, 0, VK_INDEX_TYPE_UINT32);

    // Bind descriptor sets (camera, etc.)
    vkCmdBindDescriptorSets(commandBuffer_, VK_PIPELINE_BIND_POINT_GRAPHICS,
                           terrainPipelineLayout_, 0, 1, &descriptorSet_, 0, nullptr);

    // Push elevation constants
    vkCmdPushConstants(commandBuffer_, terrainPipelineLayout_,
                      VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT,
                      0, sizeof(TerrainPushConstants), &pushConsts);

    // Draw
    vkCmdDrawIndexed(commandBuffer_, terrainIndexCount_, 1, 0, 0, 0);
}
```

### Cleanup (in destructor)

```cpp
if (terrainVertexBuffer_) vkDestroyBuffer(device_, terrainVertexBuffer_, nullptr);
if (terrainVertexMemory_) vkFreeMemory(device_, terrainVertexMemory_, nullptr);
if (terrainIndexBuffer_) vkDestroyBuffer(device_, terrainIndexBuffer_, nullptr);
if (terrainIndexMemory_) vkFreeMemory(device_, terrainIndexMemory_, nullptr);
if (terrainPipelineLayout_) vkDestroyPipelineLayout(device_, terrainPipelineLayout_, nullptr);
if (terrainDescriptorLayout_) vkDestroyDescriptorSetLayout(device_, terrainDescriptorLayout_, nullptr);
```

---

## 5. Shaders

### terrain.vert

```glsl
#version 450

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec3 inColor;
layout(location = 3) in vec2 inTexCoord;

layout(binding = 0) uniform CameraBuffer {
    mat4 view;
    mat4 proj;
    mat4 viewProj;
} camera;

layout(push_constant) uniform TerrainConstants {
    float minElevation;
    float maxElevation;
    float elevationRange;
    float padding;
} terrain;

layout(location = 0) out vec3 fragPosition;
layout(location = 1) out vec3 fragNormal;
layout(location = 2) out float fragElevation;  // Normalized 0-1

void main() {
    vec4 worldPos = vec4(inPosition, 1.0);
    gl_Position = camera.viewProj * worldPos;

    fragPosition = worldPos.xyz;
    fragNormal = inNormal;

    // Normalize elevation to 0-1 for coloring
    float elevationFeet = inPosition.z / 304.8;  // Convert mm back to feet
    fragElevation = (elevationFeet - terrain.minElevation) / max(terrain.elevationRange, 0.001);
}
```

### terrain.frag

```glsl
#version 450

layout(location = 0) in vec3 fragPosition;
layout(location = 1) in vec3 fragNormal;
layout(location = 2) in float fragElevation;

layout(location = 0) out vec4 outColor;

// Topographic color ramp (low to high elevation)
const vec3 COLOR_DEEP = vec3(0.1, 0.3, 0.5);    // Deep blue/green
const vec3 COLOR_LOW = vec3(0.2, 0.5, 0.3);     // Green
const vec3 COLOR_MID = vec3(0.6, 0.5, 0.3);     // Tan/brown
const vec3 COLOR_HIGH = vec3(0.7, 0.7, 0.7);    // Gray
const vec3 COLOR_PEAK = vec3(1.0, 1.0, 1.0);    // White

vec3 getElevationColor(float t) {
    // Smooth gradient between colors
    if (t < 0.25) {
        return mix(COLOR_DEEP, COLOR_LOW, t * 4.0);
    } else if (t < 0.5) {
        return mix(COLOR_LOW, COLOR_MID, (t - 0.25) * 4.0);
    } else if (t < 0.75) {
        return mix(COLOR_MID, COLOR_HIGH, (t - 0.5) * 4.0);
    } else {
        return mix(COLOR_HIGH, COLOR_PEAK, (t - 0.75) * 4.0);
    }
}

void main() {
    // Base color from elevation
    vec3 baseColor = getElevationColor(fragElevation);

    // Simple lighting
    vec3 lightDir = normalize(vec3(1.0, 1.0, 0.5));
    float diffuse = max(dot(normalize(fragNormal), lightDir), 0.0);
    float ambient = 0.3;

    vec3 finalColor = baseColor * (diffuse + ambient);

    // Add subtle contour lines
    float contour = step(0.95, fract(fragElevation * 20.0));
    finalColor = mix(finalColor, vec3(0.4, 0.3, 0.2), contour * 0.3);

    outColor = vec4(finalColor, 1.0);
}
```

---

## 6. Integration

### In main render loop (renderer.cpp or application entry)

After calling `drawStructuralFrame()`, add:

```cpp
// Draw terrain if available
if (building.terrainMesh.hasData()) {
    renderer.drawTerrain(building.terrainMesh);
}
```

---

## 7. CMakeLists.txt

Add new shader files:

```cmake
# Shaders
set(SHADER_FILES
    shaders/structural.vert
    shaders/structural.frag
    shaders/terrain.vert      # NEW
    shaders/terrain.frag      # NEW
)
```

---

## 8. Testing

### Test Data Format

```json
{
  "terrain_mesh": {
    "vertices": [
      {"position": [0.0, 0.0, 100.0], "normal": [0.0, 0.0, 1.0], "uv": [0.0, 0.0]},
      {"position": [10.0, 0.0, 105.0], "normal": [0.0, 0.0, 1.0], "uv": [1.0, 0.0]},
      {"position": [0.0, 10.0, 102.0], "normal": [0.0, 0.0, 1.0], "uv": [0.0, 1.0]},
      {"position": [10.0, 10.0, 107.0], "normal": [0.0, 0.0, 1.0], "uv": [1.0, 1.0]}
    ],
    "indices": [0, 1, 2, 1, 3, 2],
    "width_ft": 100.0,
    "depth_ft": 120.0,
    "min_elevation": 100.0,
    "max_elevation": 107.0
  }
}
```

### Verification Steps

1. Load a JSON with terrain data
2. Check console output for terrain mesh statistics
3. Verify terrain renders below the building
4. Confirm elevation-based coloring (low = green, high = white/gray)
5. Test contour lines are visible
6. Verify depth testing works (building doesn't clip through terrain)

---

## 9. Notes

- **Units**: Python uses feet, C++ renderer uses millimeters. Conversion factor: 1 ft = 304.8 mm
- **Coordinate System**: X = longitude (east-west), Y = latitude (north-south), Z = elevation (up)
- **Performance**: For large terrains (>10k vertices), consider LOD or tessellation
- **Memory**: Terrain buffers can be reused if mesh doesn't change
- **Shaders**: Compile with `glslc` or `glslangValidator` to .spv files

---

## 10. Future Enhancements

- [ ] Add texture support (satellite imagery overlay)
- [ ] Implement LOD system for large terrains
- [ ] Add water level visualization
- [ ] Support for contour line generation
- [ ] Add vegetation layer rendering
