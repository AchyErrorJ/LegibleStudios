@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  ArchEngine Installer Build Script
echo ============================================
echo.

:: Store script directory
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

:: Configuration
set ISCC_PATH=
set VC_REDIST_URL=https://aka.ms/vs/17/release/vc_redist.x64.exe

:: Find Inno Setup Compiler
echo [1/5] Locating Inno Setup Compiler...

:: Check common installation paths
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
)

:: Check if we found it
if "!ISCC_PATH!"=="" (
    echo ERROR: Inno Setup 6 not found!
    echo.
    echo Please install Inno Setup 6 from:
    echo   https://jrsoftware.org/isdl.php
    echo.
    echo Or specify the path manually by editing this script.
    exit /b 1
)

echo   Found: !ISCC_PATH!
echo.

:: Check for Release build
echo [2/5] Checking Release build...
if not exist "..\build\Release\ArchEngine.exe" (
    echo WARNING: Release build not found!
    echo.

    :: Check if build directory exists
    if exist "..\build" (
        echo Attempting to build Release configuration...
        cd ..\build
        cmake --build . --config Release
        cd "%SCRIPT_DIR%"

        if not exist "..\build\Release\ArchEngine.exe" (
            echo ERROR: Build failed! Please build the project manually:
            echo   cd build
            echo   cmake --build . --config Release
            exit /b 1
        )
    ) else (
        echo ERROR: Build directory not found. Please configure and build the project first:
        echo   mkdir build ^&^& cd build
        echo   cmake ..
        echo   cmake --build . --config Release
        exit /b 1
    )
)
echo   Found: ..\build\Release\ArchEngine.exe
echo.

:: Check for shaders
echo [3/5] Checking shaders...
set SHADER_COUNT=0
for %%f in (..\shaders\*.spv) do set /a SHADER_COUNT+=1

if %SHADER_COUNT%==0 (
    echo ERROR: No compiled shaders found in ..\shaders\
    echo Please compile shaders before building installer.
    exit /b 1
)
echo   Found %SHADER_COUNT% compiled shader files
echo.

:: Check/Download VC++ Redistributable
echo [4/5] Checking VC++ Redistributable...
if not exist "redist" mkdir redist

if not exist "redist\vc_redist.x64.exe" (
    echo   VC++ Redistributable not found. Downloading...

    :: Try curl first (Windows 10+)
    where curl >nul 2>&1
    if !errorlevel! equ 0 (
        curl -L -o "redist\vc_redist.x64.exe" "%VC_REDIST_URL%"
        if !errorlevel! neq 0 (
            echo ERROR: Failed to download VC++ Redistributable
            echo Please download manually from:
            echo   %VC_REDIST_URL%
            echo And save to:
            echo   %SCRIPT_DIR%redist\vc_redist.x64.exe
            exit /b 1
        )
    ) else (
        :: Try PowerShell as fallback
        powershell -Command "Invoke-WebRequest -Uri '%VC_REDIST_URL%' -OutFile 'redist\vc_redist.x64.exe'" 2>nul
        if !errorlevel! neq 0 (
            echo ERROR: Failed to download VC++ Redistributable
            echo Please download manually from:
            echo   %VC_REDIST_URL%
            echo And save to:
            echo   %SCRIPT_DIR%redist\vc_redist.x64.exe
            exit /b 1
        )
    )
    echo   Downloaded successfully.
) else (
    echo   Found: redist\vc_redist.x64.exe
)
echo.

:: Check for Vulkan runtime installer
echo   Checking Vulkan Runtime installer...
if not exist "..\dist\vulkan_runtime\VulkanRT-Installer.exe" (
    echo WARNING: VulkanRT-Installer.exe not found in ..\dist\vulkan_runtime\
    echo Installer will be built but Vulkan runtime may need to be installed manually.
) else (
    echo   Found: ..\dist\vulkan_runtime\VulkanRT-Installer.exe
)
echo.

:: Check for icon file
if not exist "assets\icon.ico" (
    echo WARNING: assets\icon.ico not found.
    echo   The installer will use the default icon.
    echo   To add a custom icon, place icon.ico in the assets folder.
    echo.

    :: Create a placeholder note
    if not exist "assets" mkdir assets
    echo Please place your icon.ico file here for the installer. > "assets\README.txt"
)

:: Build installer
echo [5/5] Building installer...
echo.
echo Running Inno Setup Compiler...
echo ----------------------------------------

"!ISCC_PATH!" ArchEngine.iss

if !errorlevel! neq 0 (
    echo.
    echo ----------------------------------------
    echo ERROR: Installer build failed!
    exit /b 1
)

echo.
echo ============================================
echo  BUILD SUCCESSFUL!
echo ============================================
echo.
echo Installer created:
echo   %SCRIPT_DIR%Output\ArchEngine-0.1.0-Setup.exe
echo.

:: Show file size
for %%A in ("Output\ArchEngine-0.1.0-Setup.exe") do (
    set SIZE=%%~zA
    set /a SIZE_MB=!SIZE!/1048576
    echo Size: !SIZE_MB! MB
)
echo.

:: Optionally open output folder
echo Press any key to open the output folder, or Ctrl+C to exit...
pause >nul
explorer "Output"

endlocal
