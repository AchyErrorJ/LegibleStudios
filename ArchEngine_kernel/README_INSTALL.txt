====================================
  ArchEngine v0.1.0 - Installation Guide
====================================

QUICK START
------------

Simply double-click:  launch_archengine.bat

This script will automatically check for Vulkan and offer to install it if missing.


SYSTEM REQUIREMENTS
-------------------

- Windows 10/11 (64-bit)
- Vulkan-compatible GPU (GTX 1060 / RX 580 or better)
- 4 GB RAM minimum
- 500 MB free disk space


MANUAL INSTALLATION
-------------------

If the launcher script doesn't work:

1. Install Vulkan Runtime (required):
   - Run: vulkan_runtime\VulkanRT-Installer.exe
   - OR download from: https://vulkan.lunarg.com/sdk/home

2. Launch ArchEngine:
   - Double-click: ArchEngine.exe


INCLUDED FEATURES
-----------------

✅ Real-time PBR (Physically Based Rendering)
✅ Tessellation and displacement mapping
✅ Shadow mapping with soft shadows
✅ SSAO (Screen Space Ambient Occlusion)
✅ Bloom post-processing
✅ HDR with tone mapping
✅ Material editor with 37 materials
✅ Per-element material overrides:
   - UV Scale
   - Normal Strength
   - Brightness
   - Contrast


MATERIAL EDITOR
---------------

1. Select any wall, floor, or element in the scene
2. Open "Material Inspector" panel
3. Adjust material properties:
   - UV Scale: Change texture tiling density
   - Normal Strength: Adjust normal map intensity
   - Brightness: Add emissive glow
   - Contrast: Increase/decrease contrast
4. Click "Apply to Selected" to apply changes


TROUBLESHOOTING
---------------

Q: Application crashes on startup
A: Make sure Vulkan Runtime is installed. Run launch_archengine.bat

Q: "Failed to open shader file" error
A: Ensure the "shaders" folder is in the same directory as ArchEngine.exe

Q: "vulkan-1.dll missing" error
A: Install Vulkan Runtime from vulkan_runtime\VulkanRT-Installer.exe

Q: Poor performance
A: Try lowering:
   - Resolution in window settings
   - Disable tessellation (if available)
   - Reduce shadow quality


CONTROLS
--------

Camera:
  - Right-click + drag: Rotate view
  - Middle-click + drag: Pan view
  - Scroll wheel: Zoom in/out

Selection:
  - Left-click: Select element
  - Ctrl+click: Multi-select
  - Esc: Deselect all


PACKAGE CONTENTS
----------------

ArchEngine.exe              - Main application
ArchEngineLib.dll           - Engine library
launch_archengine.bat       - Smart launcher (recommended)
vulkan_runtime/             - Vulkan Runtime installer
shaders/                    - GPU shaders
materials/                  - Material library (37 materials)


SUPPORT
-------

For issues, feature requests, or contributions:
https://github.com/yourusername/ArchEngine


LICENSE
-------

See LICENSE file for details


CHANGELOG
---------

v0.1.0 (2026-01-14)
- Initial release
- PBR rendering pipeline
- Material override system (4 parameters)
- Tessellation support
- Real-time shadows and lighting
- Post-processing effects (SSAO, Bloom, HDR)


Enjoy using ArchEngine!
