# ArchEngine Suite - Agent Handoff

## Project Overview

Architectural CAD application with integrated real-time 3D visualization. The suite consists of:

- **ArchEngine_CAD/** - PyQt6-based 2D CAD application
- **ArchEngine_kernel/** - Vulkan renderer (C++), builds as embeddable DLL
- **ArchEngine_Viewer/** - UE5 project (legacy texture sharing approach, not currently used)

## Current Architecture

The CAD app embeds a Vulkan 3D viewport directly using ctypes:

```
ArchEngine_CAD (Python/PyQt6)
    └── VulkanViewportWidget
            └── ctypes → ArchEngineLib.dll (C API)
                            └── VulkanContext + Renderer
```

## Key Files

### CAD Application
- `ArchEngine_CAD/main.py` - Entry point
- `ArchEngine_CAD/app/application.py` - Main window, docks, menus
- `ArchEngine_CAD/viewport/vulkan_widget.py` - Qt widget embedding Vulkan renderer
- `ArchEngine_CAD/core/document.py` - Building document model

### Vulkan Renderer
- `ArchEngine_kernel/include/arch_api.h` - C API for Python/ctypes binding
- `ArchEngine_kernel/src/arch_api.cpp` - API implementation
- `ArchEngine_kernel/include/vulkan_context.hpp` - Vulkan setup (supports embedded mode)
- `ArchEngine_kernel/src/renderer.cpp` - Main rendering logic
- `ArchEngine_kernel/CMakeLists.txt` - Builds both .exe and .dll

## Building the DLL

After making changes to the Vulkan renderer:

```bash
cd ArchEngine_kernel/build
cmake --build . --config Release
```

The CAD app automatically loads from `ArchEngine_kernel/build/Release/ArchEngineLib.dll`.

## Git Branches

- `main` - Stable branch
- `cad` - CAD development (current working branch in this worktree)

This is a git worktree. The `main` branch is checked out at `X:\ARCH\Software\ArchEngine_Suite`.

## Recent Work (Dec 2024)

1. Abandoned UE5 texture sharing approach (D3D12 sync issues)
2. Refactored Vulkan renderer into embeddable DLL with C API
3. Created VulkanViewportWidget for direct Qt embedding
4. Integrated 3D viewport into CAD application
5. Real-time sync between 2D CAD edits and 3D view working

## Running the CAD App

```bash
cd ArchEngine_CAD
python main.py
```

Requires:
- Python 3.10+
- PyQt6
- Built ArchEngineLib.dll in kernel/build/Release/

## API Reference

See `ArchEngine_kernel/include/arch_api.h`:
- `arch_init(hwnd, width, height)` - Initialize with window handle
- `arch_load_json(json_str)` - Load building data
- `arch_render_frame()` - Render one frame
- `arch_resize(width, height)` - Handle resize
- `arch_set_camera(yaw, pitch, distance)` - Camera control
- `arch_shutdown()` - Cleanup
