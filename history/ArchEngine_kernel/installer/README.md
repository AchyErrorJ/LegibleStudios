# ArchEngine Installer

This folder contains scripts for building the ArchEngine Windows installer.

## Prerequisites

1. **Inno Setup 6** - Download from https://jrsoftware.org/isdl.php
2. **Release Build** - Build the project in Release mode first:
   ```
   cd build
   cmake --build . --config Release
   ```

## Building the Installer

Simply run:
```
build_installer.bat
```

The script will:
1. Locate Inno Setup compiler
2. Verify Release build exists
3. Check compiled shaders
4. Download VC++ Redistributable (if missing)
5. Build the installer

Output: `Output\ArchEngine-0.1.0-Setup.exe`

## Optional: Add Custom Icon

Place your `icon.ico` file in the `assets\` folder before building.

## Optional: Vulkan Runtime

For offline installations, download the Vulkan Runtime installer from:
https://vulkan.lunarg.com/sdk/home

Place `VulkanRT-Installer.exe` in `..\dist\vulkan_runtime\`

## Files Included in Installer

- ArchEngine.exe and ArchEngineLib.dll
- Compiled shaders (*.spv)
- Material library (polyhaven PBR textures)
- HDRI environment maps (if present)
- Sample building files
- Launch script and documentation
