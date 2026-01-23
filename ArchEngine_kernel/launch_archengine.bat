@echo off
setlocal enabledelayedexpansion

:: ArchEngine Launcher with Vulkan Dependency Check
:: This script checks for Vulkan and offers to install it if missing

set "APP_NAME=ArchEngine"
set "VULKAN_INSTALLER=vulkan_runtime\VulkanRT-Installer.exe"
set "VULKAN_DOWNLOAD_URL=https://sdk.lunarg.com/sdk/download/latest/windows/vulkan-runtime.exe"
set "EXE_NAME=ArchEngine.exe"

echo ========================================
echo   %APP_NAME% Launcher
echo ========================================
echo.

:: Check if Vulkan DLL exists in system
set "VULKAN_FOUND=0"

:: Check common Vulkan installation locations
if exist "C:\Windows\System32\vulkan-1.dll" (
    set "VULKAN_FOUND=1"
    echo [OK] Vulkan runtime detected on system
)

if exist "C:\Windows\SysWOW64\vulkan-1.dll" (
    set "VULKAN_FOUND=1"
    echo [OK] Vulkan runtime detected on system
)

:: Check if Vulkan SDK is installed
if exist "C:\VulkanSDK\1.3.*" (
    set "VULKAN_FOUND=1"
    echo [OK] Vulkan SDK detected
)

echo.

if "%VULKAN_FOUND%"=="0" (
    echo [WARNING] Vulkan runtime not found!
    echo.
    echo Vulkan is required to run %APP_NAME%.
    echo.

    :: Check if installer is included
    if exist "%VULKAN_INSTALLER%" (
        echo Vulkan installer is included in this package.
        echo.
        choice /C YN /M "Do you want to install Vulkan Runtime now"
        if errorlevel 2 (
            echo.
            echo Installation cancelled. %APP_NAME% cannot run without Vulkan.
            echo.
            echo You can install Vulkan later from: %VULKAN_DOWNLOAD_URL%
            pause
            exit /b 1
        )

        echo.
        echo Launching Vulkan installer...
        echo Please follow the installation prompts.
        echo.
        start /wait "" "%VULKAN_INSTALLER%"

        echo.
        echo Vulkan installation complete.
        timeout /t 2 /nobreak >nul
    ) else (
        echo Vulkan installer not found in package.
        echo.
        echo Please download and install Vulkan from:
        echo %VULKAN_DOWNLOAD_URL%
        echo.
        pause
        exit /b 1
    )
)

:: Launch the application
echo.
echo Starting %APP_NAME%...
echo.

:: Check if executable exists
if exist "%EXE_NAME%" (
    start "" "%EXE_NAME%"
) else (
    echo [ERROR] %EXE_NAME% not found!
    echo.
    echo Please make sure you're running this script from the
    echo %APP_NAME% installation directory.
    echo.
    pause
    exit /b 1
)

endlocal
