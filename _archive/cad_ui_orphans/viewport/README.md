# ArchEngine Viewport - UE5 Integration

Embeds UE5 rendered viewport in PyQt6 applications using shared GPU textures.

## Features

- **Zero-copy GPU sharing**: D3D11 shared textures with keyed mutex sync
- **Up to 8K resolution**: With TSR/DLSS/FSR temporal upscaling
- **Full input forwarding**: Mouse, keyboard, touch events sent to UE5
- **Hardware interop**: Uses WGL_NV_DX_interop when available (NVIDIA/AMD)
- **CPU fallback**: Works on all systems with staging texture copy

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PyQt6 Application                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                UE5ViewportWidget (OpenGL)                ││
│  │  ┌─────────────────┐    ┌─────────────────────────────┐ ││
│  │  │ ViewportBridge  │<-->│ IPCClient (Named Pipe)      │ ││
│  │  │ D3D11 -> OpenGL │    │ Input forwarding            │ ││
│  │  └────────┬────────┘    └──────────────┬──────────────┘ ││
│  └───────────┼─────────────────────────────┼────────────────┘│
└──────────────┼─────────────────────────────┼─────────────────┘
               │ DXGI Shared Texture          │ Named Pipe
               │ (GPU Memory)                 │ (IPC)
┌──────────────┼─────────────────────────────┼─────────────────┐
│              │         UE5 Process          │                 │
│  ┌───────────┴─────────────────────────────┴───────────────┐ │
│  │              UArchTextureShareComponent                  │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

## Building the Native Library

### Prerequisites

- Visual Studio 2022 with C++ workload
- CMake 3.16+
- Windows SDK (for D3D11)

### Build Steps

```powershell
cd viewport/native
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

This produces `archengine_viewport.dll` in `build/Release/`.

## Usage

### Quick Start

```python
from PyQt6.QtWidgets import QApplication, QMainWindow
from viewport import UE5ViewportWidget

app = QApplication([])
window = QMainWindow()

# Create viewport widget
viewport = UE5ViewportWidget()
window.setCentralWidget(viewport)

# Connect to UE5 (must have ArchTextureShareComponent running)
viewport.connect_to_ue5("ArchEngine_Viewport")

window.show()
app.exec()
```

### Full Example

See `example_integration.py` for a complete example with controls:

```bash
python -m viewport.example_integration
```

### Integration with CAD App

Add the viewport to your existing layout:

```python
from viewport import UE5ViewportWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Your existing layout
        splitter = QSplitter()

        # Add 2D CAD view
        splitter.addWidget(self.cad_view)

        # Add UE5 3D viewport
        self.viewport_3d = UE5ViewportWidget()
        self.viewport_3d.connected.connect(self.on_3d_connected)
        splitter.addWidget(self.viewport_3d)

        # Connect when ready
        self.viewport_3d.connect_to_ue5()
```

## UE5 Setup

1. Add `UArchTextureShareComponent` to an actor in your level

2. Configure settings:
   ```cpp
   // In Blueprint or C++
   TextureShare->ViewportConfig.ResolutionPreset = EArchResolutionPreset::UHD_4K;
   TextureShare->ViewportConfig.RenderScale = EArchRenderScale::Quality;
   TextureShare->ViewportConfig.UpscaleMethod = EArchUpscaleMethod::TSR;
   TextureShare->ShareName = "ArchEngine_Viewport";
   ```

3. The component auto-starts sharing on BeginPlay

## API Reference

### UE5ViewportWidget

| Signal | Description |
|--------|-------------|
| `connected` | Connection to UE5 established |
| `disconnected` | Connection to UE5 lost |
| `texture_ready(width, height)` | Shared texture is available |
| `frame_updated` | New frame received |

| Method | Description |
|--------|-------------|
| `connect_to_ue5(pipe_name)` | Connect to UE5 |
| `disconnect_from_ue5()` | Disconnect |
| `is_connected` | Check connection status |

### ViewportBridge (Low-level)

| Method | Description |
|--------|-------------|
| `initialize()` | Init D3D11/OpenGL (call from GL thread) |
| `open_texture(name, w, h)` | Open shared texture |
| `acquire()` / `release()` | Lock texture for rendering |
| `gl_texture` | Get OpenGL texture ID |

### IPCClient (Low-level)

| Method | Description |
|--------|-------------|
| `connect(pipe_name)` | Connect to named pipe |
| `send_mouse_move(x, y, dx, dy)` | Send mouse move |
| `send_mouse_button(x, y, btn, pressed)` | Send mouse button |
| `send_keyboard(key, pressed, ...)` | Send keyboard |

## Troubleshooting

### "archengine_viewport.dll not found"

Build the native library:
```
cd viewport/native && mkdir build && cd build && cmake .. && cmake --build . --config Release
```

### "Failed to initialize viewport bridge"

- Ensure you have a valid OpenGL context
- Check that D3D11 is available (Windows only)

### "Connection failed"

- Verify UE5 is running with `ArchTextureShareComponent`
- Check the pipe name matches (`ShareName` in UE5)
- Ensure no firewall blocking named pipes

### Low performance

- Enable hardware interop (requires NVIDIA/AMD with WGL_NV_DX_interop)
- Use render scaling (67% with TSR looks nearly identical to native)
- Reduce target framerate in UE5 component
