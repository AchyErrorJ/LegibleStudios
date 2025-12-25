// viewport_bridge.h - D3D11 shared texture to OpenGL bridge
#pragma once

#ifdef VIEWPORT_EXPORTS
#define VIEWPORT_API __declspec(dllexport)
#else
#define VIEWPORT_API __declspec(dllimport)
#endif

#include <cstdint>

// Viewport bridge for D3D11 shared texture -> OpenGL
class VIEWPORT_API ViewportBridge
{
public:
    ViewportBridge();
    ~ViewportBridge();

    // Initialize with OpenGL context (call from GL thread)
    bool initialize();
    void shutdown();
    bool isInitialized() const { return initialized; }

    // Open shared texture by handle name
    bool openSharedTexture(const char* handleName, int width, int height);
    void closeSharedTexture();
    bool hasTexture() const { return sharedTexture != nullptr; }

    // Acquire/release for rendering (keyed mutex sync)
    bool acquireTexture();
    void releaseTexture();

    // Get OpenGL texture ID (after acquire)
    unsigned int getGLTexture() const { return glTexture; }

    // Get dimensions
    int getWidth() const { return width; }
    int getHeight() const { return height; }

    // Copy to CPU buffer (fallback for systems without WGL_NV_DX_interop)
    bool copyToCPU(void* destBuffer, int destPitch);

    // Check if hardware interop is available
    bool hasHardwareInterop() const { return hardwareInterop; }

private:
    bool initialized;
    bool hardwareInterop;
    int width;
    int height;

    // D3D11 resources
    void* d3dDevice;           // ID3D11Device*
    void* d3dContext;          // ID3D11DeviceContext*
    void* sharedTexture;       // ID3D11Texture2D*
    void* keyedMutex;          // IDXGIKeyedMutex*
    void* stagingTexture;      // ID3D11Texture2D* (for CPU fallback)

    // OpenGL resources
    unsigned int glTexture;
    void* glHandle;            // HANDLE from wglDXRegisterObjectNV

    // WGL_NV_DX_interop function pointers
    void* wglDXOpenDeviceNV;
    void* wglDXCloseDeviceNV;
    void* wglDXRegisterObjectNV;
    void* wglDXUnregisterObjectNV;
    void* wglDXLockObjectsNV;
    void* wglDXUnlockObjectsNV;
    void* interopDevice;       // HANDLE from wglDXOpenDeviceNV

    bool initD3D11();
    void cleanupD3D11();
    bool initInterop();
    void cleanupInterop();
    bool createGLTexture();
    void destroyGLTexture();
};

// C API for Python ctypes
extern "C" {
    VIEWPORT_API ViewportBridge* viewport_create();
    VIEWPORT_API void viewport_destroy(ViewportBridge* bridge);
    VIEWPORT_API int viewport_initialize(ViewportBridge* bridge);
    VIEWPORT_API void viewport_shutdown(ViewportBridge* bridge);
    VIEWPORT_API int viewport_is_initialized(ViewportBridge* bridge);

    VIEWPORT_API int viewport_open_texture(ViewportBridge* bridge, const char* handleName, int width, int height);
    VIEWPORT_API void viewport_close_texture(ViewportBridge* bridge);
    VIEWPORT_API int viewport_has_texture(ViewportBridge* bridge);

    VIEWPORT_API int viewport_acquire(ViewportBridge* bridge);
    VIEWPORT_API void viewport_release(ViewportBridge* bridge);

    VIEWPORT_API unsigned int viewport_get_gl_texture(ViewportBridge* bridge);
    VIEWPORT_API int viewport_get_width(ViewportBridge* bridge);
    VIEWPORT_API int viewport_get_height(ViewportBridge* bridge);

    VIEWPORT_API int viewport_copy_to_cpu(ViewportBridge* bridge, void* buffer, int pitch);
    VIEWPORT_API int viewport_has_hardware_interop(ViewportBridge* bridge);
}
