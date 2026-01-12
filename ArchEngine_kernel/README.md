# ArchEngine Kernel

Vulkan-based architectural visualization and structural analysis engine.

## Features

### Rendering
- **PBR (Physically Based Rendering)** with metallic-roughness workflow
- **HDR pipeline** with SSAO, bloom, and tonemapping (Reinhard, ACES, Uncharted2)
- **Shadow mapping** with PCF filtering
- **MSAA anti-aliasing** (configurable 1x-8x)
- **Environment mapping** from HDR equirectangular images
- **Ray tracing support** (experimental) with global illumination

### Architectural Visualization
- Real-time 3D rendering of structural elements (beams, columns, walls, floors, roofs, doors, windows)
- **Stress visualization** with color-coded stress ratios (green=safe, yellow=warning, red=failure)
- **Multiple visualization modes**: Structural, Thermal, Lighting, Acoustic, Material, Wireframe
- **Section clipping planes** for cut-away views
- **Parametric wall system** with multi-layer construction assemblies

### Building Design
- **QBD (Quantum Building Design)** layout parsing and generation
- **Ontario Building Code (OBC)** compliance validation
- **Wall assembly system** with layered materials (studs, insulation, sheathing, drywall)
- **CSG boolean operations** for door/window cutouts
- **IFC file import** support

### Integration
- **CAD embedding** via DLL with C API
- **IPC server** for real-time communication with external applications
- **Physics bridge** for structural analysis integration

## Prerequisites

### Required
- **Vulkan SDK 1.3+** - Download from https://vulkan.lunarg.com/
- **CMake 3.20+** - https://cmake.org/download/
- **C++20 compiler**:
  - Windows: Visual Studio 2019 or later
  - Linux: GCC 10+ or Clang 10+

### Optional
- **Python 3.10+** (for IFC import and structural analysis)
- **ifcopenshell** - `pip install ifcopenshell`

## Building

### Windows (Visual Studio)

```bash
# Clone the repository
git clone <repository-url>
cd ArchEngine_kernel

# Create build directory
mkdir build
cd build

# Configure
cmake ..

# Build
cmake --build . --config Release

# Run
./Release/ArchEngine.exe
```

### Linux

```bash
mkdir build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
./ArchEngine
```

### Build Options

| Option | Default | Description |
|--------|---------|-------------|
| `ARCH_BUILD_DLL` | OFF | Build as shared library for CAD embedding |
| `ARCH_ENABLE_VALIDATION` | ON | Enable Vulkan validation layers |
| `ARCH_MSAA_SAMPLES` | 4 | Default MSAA sample count |

## Usage

### Basic Rendering Loop

```cpp
#include "window.hpp"
#include "vulkan_context.hpp"
#include "renderer.hpp"

int main() {
    // Create window and Vulkan context
    arch::Window window(1280, 720, "ArchEngine");
    arch::VulkanConfig config;
    config.msaaSamples = VK_SAMPLE_COUNT_4_BIT;
    arch::VulkanContext context(window, config);
    arch::Renderer renderer(context);

    // Configure rendering
    renderer.setPostProcessingEnabled(true);
    renderer.setSSAOEnabled(true);
    renderer.setBloomEnabled(true);
    renderer.setShadowsEnabled(true);

    // Main loop
    while (!window.shouldClose()) {
        window.pollEvents();

        if (renderer.beginFrame()) {
            renderer.renderShadowPass(elements);
            renderer.beginHDRRenderPass();
            renderer.drawStructuralFrame(elements, building);
            renderer.drawSky();
            renderer.endHDRRenderPass();
            renderer.runPostProcessing();
            renderer.beginCompositePass();
            // ImGui rendering here
            renderer.endFrame();
        }
    }
    return 0;
}
```

### Loading QBD Layouts

```cpp
#include "qbd_interface.hpp"

arch::QBDInterface qbd;
auto layout = qbd.loadFromFile("building.json");
if (layout) {
    arch::Building building = qbd.toBuilding(*layout);
    // Render building.elements
}
```

### Material Configuration

```cpp
// Load material textures from directory
renderer.reloadMaterialLibrary("materials/");

// Or set PBR values directly
renderer.setDefaultMetallic(0.0f);
renderer.setDefaultRoughness(0.5f);
renderer.setWallRoughness(0.9f);

// Change material style
renderer.setMaterialStyle(arch::MaterialStyle::Realistic);
```

## Controls

| Input | Action |
|-------|--------|
| Mouse drag | Rotate camera |
| Scroll | Zoom in/out |
| Click | Select element |
| Ctrl+Click | Multi-select |
| Tab | Cycle overlapping elements |
| H | Show help |

## Configuration

### Vulkan Settings

```cpp
arch::VulkanConfig config;
config.enableValidation = true;      // Enable validation layers
config.enableDebugMarkers = true;    // Enable RenderDoc markers
config.maxFramesInFlight = 2;        // Double buffering
config.msaaSamples = VK_SAMPLE_COUNT_4_BIT;
config.shadowMapResolution = 2048;
```

### Post-Processing

```cpp
renderer.setSSAORadius(0.5f);        // SSAO sample radius
renderer.setSSAOIntensity(1.5f);     // SSAO strength
renderer.setBloomThreshold(1.0f);    // Bloom luminance threshold
renderer.setBloomIntensity(0.3f);    // Bloom strength
renderer.setExposure(1.0f);          // HDR exposure
renderer.setTonemapMode(1);          // 0=Reinhard, 1=ACES, 2=Uncharted2
```

## Project Structure

```
ArchEngine_kernel/
├── docs/                 # Documentation
│   └── ARCHITECTURE.md   # System architecture
├── include/              # Header files
│   ├── renderer.hpp      # Main rendering interface
│   ├── vulkan_context.hpp # Vulkan device management
│   ├── pipeline.hpp      # Graphics pipeline
│   ├── mesh.hpp          # Geometry and meshes
│   ├── texture.hpp       # Textures and materials
│   ├── post_process.hpp  # SSAO, bloom, tonemapping
│   ├── shadow_map.hpp    # Shadow mapping
│   ├── qbd_interface.hpp # QBD layout parsing
│   ├── obc_engine.hpp    # Building code validation
│   └── types.hpp         # Core data structures
├── src/                  # Implementation files
├── shaders/              # GLSL shaders
│   ├── structural.*      # Main PBR shaders
│   ├── sky.*             # Sky rendering
│   ├── ssao.*            # Ambient occlusion
│   ├── bloom_*.*         # Bloom effect
│   ├── composite.*       # HDR composite
│   └── *.spv             # Pre-compiled SPIR-V
├── scripts/              # Utility scripts
│   ├── physics_bridge.py # Structural analysis
│   └── material_generate.py # AI material generation
├── materials/            # PBR material textures
└── CMakeLists.txt        # Build configuration
```

## CAD Integration

Build as DLL for embedding in CAD applications:

```bash
cmake -DARCH_BUILD_DLL=ON ..
cmake --build . --config Release
# Output: build/Release/ArchEngineLib.dll
```

See `include/arch_api.h` for the C API.

## Dependencies

Auto-downloaded by CMake:
- **GLFW 3.3.8** - Window management
- **GLM 0.9.9.8** - Mathematics
- **Dear ImGui 1.90.1** - User interface
- **nlohmann/json 3.11.3** - JSON parsing
- **stb_image** - Image loading

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and data flow
- Header files contain Doxygen-style API documentation

Generate HTML documentation:
```bash
cd docs
doxygen Doxyfile
```

## License

Proprietary - All rights reserved.
