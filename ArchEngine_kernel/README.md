# ArchEngine

Vulkan-based architectural visualization and structural analysis tool.

## Features

- Real-time 3D rendering of structural elements (beams, columns, walls, floors, roofs)
- Parametric wall system with multi-layer construction (studs, insulation, sheathing, drywall)
- Click-to-place geometry creation
- IFC file import
- Physics/structural analysis integration
- CSG boolean operations for geometry

## Prerequisites

### Required
- **Vulkan SDK** - Download from https://vulkan.lunarg.com/
- **CMake 3.20+** - https://cmake.org/download/
- **C++20 compiler**:
  - Windows: Visual Studio 2019 or later
  - Linux: GCC 10+ or Clang 10+

### Optional (for IFC import)
- **Python 3.10+**
- **ifcopenshell** - `pip install ifcopenshell`

## Building

```bash
# Clone the repository
git clone https://aesir.tailb0b4db.ts.net/git/ArchEngine.git repo might be different 
cd ArchEngine

# Create build directory
mkdir build
cd build

# Configure (Windows with Visual Studio)
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

## Controls

- **Mouse drag** - Rotate camera
- **Scroll** - Zoom in/out
- **Click** - Select element
- **Ctrl+Click** - Multi-select
- **Tab** - Cycle through overlapping elements
- **H** - Show help

## Project Structure

```
ArchEngine/
├── include/          # Header files
├── src/              # Source files
├── shaders/          # GLSL shaders (pre-compiled .spv included)
├── scripts/          # Build and utility scripts
│   ├── physics_bridge.py   # Structural analysis
│   └── ifc_import.py       # IFC file import
└── CMakeLists.txt    # Build configuration
```

## CAD Integration (Embeddable DLL)

The renderer can be built as a DLL for embedding in the CAD application:

```bash
cd build

# Build Release DLL
cmake --build . --config Release

# Output: build/Release/ArchEngineLib.dll
```

The CAD app (`ArchEngine_CAD`) automatically loads the DLL from:
- `../ArchEngine_kernel/build/Release/`
- `../ArchEngine_kernel/build/Debug/`

After rebuilding, restart the CAD app to load the updated DLL.

See `include/arch_api.h` for the C API used by Python/ctypes.

## Dependencies (auto-downloaded by CMake)

- GLFW 3.3.8 - Window management
- GLM 0.9.9.8 - Math library
- Dear ImGui 1.90.1 - UI
- nlohmann/json 3.11.3 - JSON parsing
