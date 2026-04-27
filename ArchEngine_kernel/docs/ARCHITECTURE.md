# ArchEngine Kernel Architecture

This document provides a comprehensive overview of the ArchEngine kernel architecture, its components, and how they interact.

## Table of Contents

1. [Overview](#overview)
2. [Architecture Layers](#architecture-layers)
3. [Core Components](#core-components)
4. [Rendering Pipeline](#rendering-pipeline)
5. [Data Flow](#data-flow)
6. [Shader System](#shader-system)
7. [Material System](#material-system)
8. [Building Code Integration](#building-code-integration)

---

## Overview

ArchEngine is a modular Vulkan-based architectural visualization and structural analysis engine. It provides:

- Real-time PBR rendering with HDR pipeline
- Structural stress visualization
- Building code compliance validation (Ontario Building Code)
- Parametric wall assembly generation
- IPC integration with CAD applications

---

## Architecture Layers

```
+-------------------------------------------------------------+
|                    APPLICATION LAYER                         |
|  (main.cpp, IPC Server, ImGui Integration)                   |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                 RENDERING PIPELINE LAYER                     |
| (Renderer, Pipeline, Post-Processing, Shadow Maps)          |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                SCENE & GRAPHICS LAYER                        |
| (Mesh, Texture, EnvironmentMap, Materials)                   |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|              VULKAN ABSTRACTION LAYER                        |
| (VulkanContext, DescriptorManager, Command Buffers)         |
+-----------------------------+-------------------------------+
                              |
+-----------------------------v-------------------------------+
|                LOW-LEVEL SUPPORT LAYER                       |
| (Types, Window, Memory, Physics Bridge, QBD Interface)      |
+-------------------------------------------------------------+
```

---

## Core Components

### Rendering Engine (Tier 1)

| Component | Header | Description |
|-----------|--------|-------------|
| **Renderer** | `renderer.hpp` | Main rendering interface; manages frame lifecycle, draw calls, visualization modes |
| **VulkanContext** | `vulkan_context.hpp` | Vulkan device initialization, memory management, swapchain handling |
| **Pipeline** | `pipeline.hpp` | Graphics pipeline creation, shader compilation, layout management |

### Geometry & Mesh System (Tier 2)

| Component | Header | Description |
|-----------|--------|-------------|
| **Mesh** | `mesh.hpp` | GPU vertex/index buffers, procedural geometry generators |
| **Texture** | `texture.hpp` | Texture loading, sampler management, PBR material system |
| **EnvironmentMap** | `environment_map.hpp` | HDR cubemap creation from equirectangular images |

### Visual Effects (Tier 2)

| Component | Header | Description |
|-----------|--------|-------------|
| **PostProcess** | `post_process.hpp` | SSAO, Bloom, HDR tonemapping |
| **ShadowMap** | `shadow_map.hpp` | Directional shadow mapping with PCF filtering |

### Architectural Domain (Tier 3)

| Component | Header | Description |
|-----------|--------|-------------|
| **QBDInterface** | `qbd_interface.hpp` | QBD JSON layout parsing, building generation |
| **OBCEngine** | `obc_engine.hpp` | Ontario Building Code compliance checking |
| **WallSystem** | `wall_system.hpp` | Parametric wall generation with multi-layer assemblies |
| **Slicer2D** | `slicer_2d.hpp` | 2D floor plan and section generation |

### Supporting Systems (Tier 3-4)

| Component | Header | Description |
|-----------|--------|-------------|
| **Types** | `types.hpp` | Core data structures (Vertex, Camera, Building, WallType) |
| **Window** | `window.hpp` | GLFW window management, input handling |
| **ImGuiLayer** | `imgui_layer.hpp` | UI overlay for settings and debugging |

---

## Rendering Pipeline

### Frame Flow

```
beginFrame()
    |
    +-- Acquire swapchain image
    +-- Reset command buffer
    |
    v
[Shadow Pass] (if enabled)
    |
    +-- Render from light perspective
    +-- Output: 2048x2048 depth map
    |
    v
[HDR Render Pass] (or Main Pass)
    |
    +-- Clear HDR buffer
    +-- Render scene with PBR
    +-- Apply stress coloring
    +-- Render sky
    |
    v
[Post-Processing] (if HDR enabled)
    |
    +-- SSAO computation
    +-- Bloom extraction + blur
    +-- Composite with tonemapping
    |
    v
endFrame()
    |
    +-- Submit command buffer
    +-- Present to swapchain
```

### Descriptor Set Layout

```cpp
// Set 0: Global per-frame data
binding 0: UniformBufferObject (view, proj, lightViewProj, etc.)
binding 1: sampler2DShadow shadowMap

// Set 1: Per-material textures
binding 0: sampler2D albedoMap
binding 1: sampler2D normalMap
binding 2: sampler2D roughnessMap
binding 3: sampler2D metallicMap
binding 4: sampler2D aoMap
binding 5: sampler2D emissiveMap
binding 6: sampler2D opacityMap

// Push constants: Per-draw data
mat4 model
vec4 color (RGB + stress)
vec4 material (metallic, roughness, ao, emission)
```

---

## Data Flow

### Building Load to Render

```
QBD JSON File
    |
    v
QBDInterface::loadFromJSON()
    |
    v
QBDLayout (walls, doors, windows, rooms)
    |
    v
QBDInterface::toParametricWalls()
    |
    v
WallSystem::detectCorners()
    |
    v
WallSystem::generateWallGeometry()
    |
    v
Building struct
    |
    v
PhysicsBridge::analyzeStructure() [optional]
    |
    v
Renderer::drawStructuralFrame()
    |
    v
GPU Rendering with stress coloring
```

---

## Shader System

### Shader Files

| Shader | Type | Purpose |
|--------|------|---------|
| `structural.vert/frag` | Vertex/Fragment | Main PBR rendering with stress coloring |
| `sky.vert/frag` | Vertex/Fragment | Procedural or cubemap sky |
| `shadow.vert` | Vertex | Shadow map depth pass |
| `ssao.frag` | Fragment | Screen-space ambient occlusion |
| `ssao_blur.frag` | Fragment | SSAO blur pass |
| `bloom_bright.frag` | Fragment | Bright color extraction |
| `bloom_blur.frag` | Fragment | Gaussian blur for bloom |
| `composite.frag` | Fragment | Final HDR composite with tonemapping |
| `denoise.comp` | Compute | Temporal denoising |
| `raygen.rgen` | Ray Gen | Ray tracing primary rays |
| `closesthit.rchit` | Closest Hit | Ray tracing PBR shading |
| `miss.rmiss` | Miss | Ray tracing sky sampling |
| `shadow_miss.rmiss` | Miss | Ray tracing shadow testing |

### Stress Coloring

Stress values are mapped to colors in the shader:

| Range | Color | State |
|-------|-------|-------|
| 0.0 - 0.7 | Green (#22c55e) | Safe |
| 0.7 - 0.9 | Yellow (#eab308) | Warning |
| 0.9 - 1.0 | Orange (#f97316) | Critical |
| > 1.0 | Red (#ef4444) | Failure |

---

## Material System

### PBR Implementation

The engine uses Cook-Torrance BRDF with:

- **GGX Normal Distribution** for specular highlights
- **Schlick-GGX Geometry** for shadowing/masking
- **Fresnel-Schlick** for reflectance at different angles

### Material Presets

```cpp
Materials::Steel()      // metallic=0.9, roughness=0.3
Materials::Drywall()    // metallic=0.0, roughness=0.95
Materials::Glass()      // metallic=0.1, roughness=0.05
Materials::Concrete()   // metallic=0.0, roughness=0.9
Materials::Wood()       // metallic=0.0, roughness=0.7
```

### Texture Maps

Each material supports:
- Albedo (sRGB color)
- Normal (tangent-space)
- Roughness (linear grayscale)
- Metallic (linear grayscale)
- Ambient Occlusion (linear grayscale)
- Emissive (sRGB color)
- Opacity (linear grayscale)

---

## Building Code Integration

### Ontario Building Code (OBC) Engine

The OBC engine validates designs against code requirements:

```cpp
// Structural span validation
ComplianceReport report = obc.validateJoist(
    "SPF", "No.2",  // Species, grade
    "2x10",         // Size
    12.5f,          // Span (feet)
    16              // Spacing (inches OC)
);

// Thermal compliance
f32 required = obc.getMinimumRValue("Zone 6", "exterior_wall");
bool compliant = wallType.getTotalRValue() >= required;
```

### Wall Assembly System

Walls are defined as layered assemblies:

```cpp
WallType exteriorWall;
exteriorWall.name = "2x6 Exterior Wall";
exteriorWall.layers = {
    {"Vinyl Siding", "vinyl", LayerFunction::ExteriorFinish, 0.01f},
    {"Sheathing", "osb", LayerFunction::Sheathing, 0.0417f},
    {"2x6 Stud", "wood", LayerFunction::Structure, 0.4583f},
    {"Batt Insulation", "fiberglass", LayerFunction::Insulation, 0.4583f},
    {"Vapor Barrier", "poly", LayerFunction::VaporBarrier, 0.001f},
    {"Drywall", "gypsum", LayerFunction::InteriorFinish, 0.0417f}
};
```

---

## Configuration

### Vulkan Configuration

```cpp
VulkanConfig config;
config.enableValidation = true;
config.maxFramesInFlight = 2;
config.msaaSamples = VK_SAMPLE_COUNT_4_BIT;
config.shadowMapResolution = 2048;
```

### Runtime Settings

```cpp
renderer.setSSAOEnabled(true);
renderer.setBloomEnabled(true);
renderer.setExposure(1.0f);
renderer.setTonemapMode(1);  // 0=Reinhard, 1=ACES, 2=Uncharted2
renderer.setVisualizationMode(VisualizationMode::Structural);
```

---

## Design Patterns

1. **RAII** - All GPU resources cleaned up in destructors
2. **Non-copyable, Movable** - Prevent accidental resource duplication
3. **Builder Pattern** - Fluent API for complex object construction
4. **Callback System** - Decoupled event handling
5. **Material Library** - Lazy loading with fallbacks

---

## See Also

- [API Reference](./API.md)
- [Shader Development](./SHADERS.md)
- [Building Code Reference](./OBC.md)
