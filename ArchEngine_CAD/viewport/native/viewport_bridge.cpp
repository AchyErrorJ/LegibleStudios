// viewport_bridge.cpp - D3D11 to OpenGL bridge implementation

#include "viewport_bridge.h"
#include <Windows.h>
#include <d3d11_1.h>
#include <dxgi1_2.h>
#include <GL/gl.h>
#include <string>

// OpenGL constants
#ifndef GL_CLAMP_TO_EDGE
#define GL_CLAMP_TO_EDGE 0x812F
#endif
#ifndef GL_RGBA8
#define GL_RGBA8 0x8058
#endif
#ifndef GL_SRGB8_ALPHA8
#define GL_SRGB8_ALPHA8 0x8C43
#endif
#ifndef GL_TEXTURE_2D
#define GL_TEXTURE_2D 0x0DE1
#endif

// OpenGL function types
typedef void (APIENTRY* PFNGLGENTEXTURESPROC)(GLsizei n, GLuint* textures);
typedef void (APIENTRY* PFNGLDELETETEXTURESPROC)(GLsizei n, const GLuint* textures);
typedef void (APIENTRY* PFNGLBINDTEXTUREPROC)(GLenum target, GLuint texture);
typedef void (APIENTRY* PFNGLTEXPARAMETERIPROC)(GLenum target, GLenum pname, GLint param);
typedef void (APIENTRY* PFNGLTEXIMAGE2DPROC)(GLenum target, GLint level, GLint internalformat, GLsizei width, GLsizei height, GLint border, GLenum format, GLenum type, const void* pixels);

// WGL_NV_DX_interop function types
typedef BOOL(WINAPI* PFNWGLDXSETRESOURCESHAREHANDLENVPROC)(void*, HANDLE);
typedef HANDLE(WINAPI* PFNWGLDXOPENDEVICENVPROC)(void*);
typedef BOOL(WINAPI* PFNWGLDXCLOSEDEVICENVPROC)(HANDLE);
typedef HANDLE(WINAPI* PFNWGLDXREGISTEROBJECTNVPROC)(HANDLE, void*, GLuint, GLenum, GLenum);
typedef BOOL(WINAPI* PFNWGLDXUNREGISTEROBJECTNVPROC)(HANDLE, HANDLE);
typedef BOOL(WINAPI* PFNWGLDXOBJECTACCESSNVPROC)(HANDLE, GLenum);
typedef BOOL(WINAPI* PFNWGLDXLOCKOBJECTSNVPROC)(HANDLE, GLint, HANDLE*);
typedef BOOL(WINAPI* PFNWGLDXUNLOCKOBJECTSNVPROC)(HANDLE, GLint, HANDLE*);

// WGL constants
#define WGL_ACCESS_READ_ONLY_NV 0x0000
#define WGL_ACCESS_READ_WRITE_NV 0x0001
#define WGL_ACCESS_WRITE_DISCARD_NV 0x0002

ViewportBridge::ViewportBridge()
    : initialized(false)
    , hardwareInterop(false)
    , width(0)
    , height(0)
    , d3dDevice(nullptr)
    , d3dContext(nullptr)
    , sharedTexture(nullptr)
    , keyedMutex(nullptr)
    , stagingTexture(nullptr)
    , glTexture(0)
    , glHandle(nullptr)
    , wglDXOpenDeviceNV(nullptr)
    , wglDXCloseDeviceNV(nullptr)
    , wglDXRegisterObjectNV(nullptr)
    , wglDXUnregisterObjectNV(nullptr)
    , wglDXLockObjectsNV(nullptr)
    , wglDXUnlockObjectsNV(nullptr)
    , interopDevice(nullptr)
{
}

ViewportBridge::~ViewportBridge()
{
    shutdown();
}

bool ViewportBridge::initialize()
{
    if (initialized)
    {
        return true;
    }

    if (!initD3D11())
    {
        return false;
    }

    // Try to initialize hardware interop
    hardwareInterop = initInterop();

    initialized = true;
    return true;
}

void ViewportBridge::shutdown()
{
    closeSharedTexture();
    cleanupInterop();
    cleanupD3D11();
    initialized = false;
}

bool ViewportBridge::initD3D11()
{
    // Create D3D11 device
    D3D_FEATURE_LEVEL featureLevels[] = {
        D3D_FEATURE_LEVEL_11_1,
        D3D_FEATURE_LEVEL_11_0,
        D3D_FEATURE_LEVEL_10_1,
        D3D_FEATURE_LEVEL_10_0
    };

    D3D_FEATURE_LEVEL featureLevel;
    UINT flags = 0;
#ifdef _DEBUG
    flags |= D3D11_CREATE_DEVICE_DEBUG;
#endif

    HRESULT hr = D3D11CreateDevice(
        nullptr,
        D3D_DRIVER_TYPE_HARDWARE,
        nullptr,
        flags,
        featureLevels,
        ARRAYSIZE(featureLevels),
        D3D11_SDK_VERSION,
        reinterpret_cast<ID3D11Device**>(&d3dDevice),
        &featureLevel,
        reinterpret_cast<ID3D11DeviceContext**>(&d3dContext)
    );

    return SUCCEEDED(hr);
}

void ViewportBridge::cleanupD3D11()
{
    if (d3dContext)
    {
        static_cast<ID3D11DeviceContext*>(d3dContext)->Release();
        d3dContext = nullptr;
    }
    if (d3dDevice)
    {
        static_cast<ID3D11Device*>(d3dDevice)->Release();
        d3dDevice = nullptr;
    }
}

bool ViewportBridge::initInterop()
{
    // Load WGL_NV_DX_interop functions
    wglDXOpenDeviceNV = (void*)wglGetProcAddress("wglDXOpenDeviceNV");
    wglDXCloseDeviceNV = (void*)wglGetProcAddress("wglDXCloseDeviceNV");
    wglDXRegisterObjectNV = (void*)wglGetProcAddress("wglDXRegisterObjectNV");
    wglDXUnregisterObjectNV = (void*)wglGetProcAddress("wglDXUnregisterObjectNV");
    wglDXLockObjectsNV = (void*)wglGetProcAddress("wglDXLockObjectsNV");
    wglDXUnlockObjectsNV = (void*)wglGetProcAddress("wglDXUnlockObjectsNV");

    if (!wglDXOpenDeviceNV || !wglDXCloseDeviceNV ||
        !wglDXRegisterObjectNV || !wglDXUnregisterObjectNV ||
        !wglDXLockObjectsNV || !wglDXUnlockObjectsNV)
    {
        return false;
    }

    // Open D3D device for interop
    auto openDevice = reinterpret_cast<PFNWGLDXOPENDEVICENVPROC>(wglDXOpenDeviceNV);
    interopDevice = openDevice(d3dDevice);

    return interopDevice != nullptr;
}

void ViewportBridge::cleanupInterop()
{
    if (interopDevice && wglDXCloseDeviceNV)
    {
        auto closeDevice = reinterpret_cast<PFNWGLDXCLOSEDEVICENVPROC>(wglDXCloseDeviceNV);
        closeDevice(interopDevice);
        interopDevice = nullptr;
    }
}

bool ViewportBridge::openSharedTexture(const char* handleName, int w, int h)
{
    closeSharedTexture();

    if (!d3dDevice)
    {
        fprintf(stderr, "[ViewportBridge] No D3D device\n");
        fflush(stderr);
        return false;
    }

    ID3D11Device* device = static_cast<ID3D11Device*>(d3dDevice);
    ID3D11Device1* device1 = nullptr;

    // Get ID3D11Device1 for OpenSharedResource1
    HRESULT hr = device->QueryInterface(__uuidof(ID3D11Device1), reinterpret_cast<void**>(&device1));
    if (FAILED(hr))
    {
        fprintf(stderr, "[ViewportBridge] QueryInterface ID3D11Device1 failed: 0x%08X\n", hr);
        fflush(stderr);
        return false;
    }

    // Build handle name
    std::wstring wHandleName(handleName, handleName + strlen(handleName));

    fprintf(stderr, "[ViewportBridge] Opening shared texture: %s (%dx%d)\n", handleName, w, h);
    fflush(stderr);

    // Open shared texture by name
    hr = device1->OpenSharedResourceByName(
        wHandleName.c_str(),
        DXGI_SHARED_RESOURCE_READ,
        __uuidof(ID3D11Texture2D),
        &sharedTexture
    );
    device1->Release();

    if (FAILED(hr))
    {
        fprintf(stderr, "[ViewportBridge] OpenSharedResourceByName failed: 0x%08X\n", hr);
        fflush(stderr);
        return false;
    }

    fprintf(stderr, "[ViewportBridge] Shared texture opened successfully\n");
    fflush(stderr);

    // Get keyed mutex
    ID3D11Texture2D* texture = static_cast<ID3D11Texture2D*>(sharedTexture);
    hr = texture->QueryInterface(__uuidof(IDXGIKeyedMutex), &keyedMutex);
    if (FAILED(hr))
    {
        fprintf(stderr, "[ViewportBridge] QueryInterface IDXGIKeyedMutex failed: 0x%08X\n", hr);
        fflush(stderr);
        texture->Release();
        sharedTexture = nullptr;
        return false;
    }
    fprintf(stderr, "[ViewportBridge] Got keyed mutex\n");
    fflush(stderr);

    width = w;
    height = h;

    // Create staging texture for CPU fallback
    D3D11_TEXTURE2D_DESC stagingDesc = {};
    stagingDesc.Width = width;
    stagingDesc.Height = height;
    stagingDesc.MipLevels = 1;
    stagingDesc.ArraySize = 1;
    stagingDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    stagingDesc.SampleDesc.Count = 1;
    stagingDesc.Usage = D3D11_USAGE_STAGING;
    stagingDesc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;

    device->CreateTexture2D(&stagingDesc, nullptr, reinterpret_cast<ID3D11Texture2D**>(&stagingTexture));

    // Create GL texture
    fprintf(stderr, "[ViewportBridge] Creating GL texture...\n");
    fflush(stderr);
    if (!createGLTexture())
    {
        fprintf(stderr, "[ViewportBridge] createGLTexture failed!\n");
        fflush(stderr);
        closeSharedTexture();
        return false;
    }

    fprintf(stderr, "[ViewportBridge] openSharedTexture complete!\n");
    fflush(stderr);
    return true;
}

void ViewportBridge::closeSharedTexture()
{
    destroyGLTexture();

    if (stagingTexture)
    {
        static_cast<ID3D11Texture2D*>(stagingTexture)->Release();
        stagingTexture = nullptr;
    }

    if (keyedMutex)
    {
        static_cast<IDXGIKeyedMutex*>(keyedMutex)->Release();
        keyedMutex = nullptr;
    }

    if (sharedTexture)
    {
        static_cast<ID3D11Texture2D*>(sharedTexture)->Release();
        sharedTexture = nullptr;
    }

    width = 0;
    height = 0;
}

bool ViewportBridge::createGLTexture()
{
    fprintf(stderr, "[ViewportBridge] createGLTexture: hardwareInterop=%d, interopDevice=%p\n",
            hardwareInterop, interopDevice);
    fflush(stderr);

    // Generate OpenGL texture
    glGenTextures(1, &glTexture);
    glBindTexture(GL_TEXTURE_2D, glTexture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

    if (hardwareInterop && interopDevice)
    {
        // Register D3D texture with OpenGL
        fprintf(stderr, "[ViewportBridge] Attempting hardware interop registration...\n");
        fflush(stderr);

        auto registerObject = reinterpret_cast<PFNWGLDXREGISTEROBJECTNVPROC>(wglDXRegisterObjectNV);
        glHandle = registerObject(
            interopDevice,
            sharedTexture,
            glTexture,
            GL_TEXTURE_2D,
            WGL_ACCESS_READ_ONLY_NV
        );

        if (!glHandle)
        {
            fprintf(stderr, "[ViewportBridge] Hardware interop registration failed! Falling back to CPU copy.\n");
            fflush(stderr);

            // Fall back to CPU copy mode instead of failing
            hardwareInterop = false;
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        }
        else
        {
            fprintf(stderr, "[ViewportBridge] Hardware interop registration succeeded, glHandle=%p\n", glHandle);
            fflush(stderr);
        }
    }
    else
    {
        // Allocate texture storage for CPU fallback
        // Use GL_SRGB8_ALPHA8 for correct gamma handling (UE5 outputs sRGB)
        fprintf(stderr, "[ViewportBridge] Using CPU copy mode (sRGB)\n");
        fflush(stderr);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_SRGB8_ALPHA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
    }

    glBindTexture(GL_TEXTURE_2D, 0);
    fprintf(stderr, "[ViewportBridge] GL texture created: %u\n", glTexture);
    fflush(stderr);
    return true;
}

void ViewportBridge::destroyGLTexture()
{
    if (glHandle && wglDXUnregisterObjectNV)
    {
        auto unregisterObject = reinterpret_cast<PFNWGLDXUNREGISTEROBJECTNVPROC>(wglDXUnregisterObjectNV);
        unregisterObject(interopDevice, glHandle);
        glHandle = nullptr;
    }

    if (glTexture)
    {
        glDeleteTextures(1, &glTexture);
        glTexture = 0;
    }
}

bool ViewportBridge::acquireTexture()
{
    if (!keyedMutex)
    {
        return false;
    }

    // Acquire keyed mutex (key 1 = consumer) with longer timeout
    // UE5 releases key 1 after each frame copy, we need to catch it
    IDXGIKeyedMutex* mutex = static_cast<IDXGIKeyedMutex*>(keyedMutex);
    HRESULT hr = mutex->AcquireSync(1, 100);  // Wait up to 100ms for better sync
    if (hr == WAIT_TIMEOUT || FAILED(hr))
    {
        static int timeoutCount = 0;
        if (++timeoutCount % 100 == 1)
        {
            fprintf(stderr, "[ViewportBridge] Mutex acquire timeout #%d (hr=0x%08X)\n", timeoutCount, hr);
            fflush(stderr);
        }
        return false;
    }

    // Lock for OpenGL access if using hardware interop
    if (hardwareInterop && glHandle && wglDXLockObjectsNV)
    {
        auto lockObjects = reinterpret_cast<PFNWGLDXLOCKOBJECTSNVPROC>(wglDXLockObjectsNV);
        HANDLE handles[] = { glHandle };
        if (!lockObjects(interopDevice, 1, handles))
        {
            mutex->ReleaseSync(0);
            return false;
        }
    }
    else if (!hardwareInterop && stagingTexture && d3dContext)
    {
        // CPU fallback: copy D3D texture to staging, then upload to OpenGL
        ID3D11DeviceContext* context = static_cast<ID3D11DeviceContext*>(d3dContext);
        ID3D11Texture2D* src = static_cast<ID3D11Texture2D*>(sharedTexture);
        ID3D11Texture2D* staging = static_cast<ID3D11Texture2D*>(stagingTexture);

        // Copy to staging
        context->CopyResource(staging, src);

        // Map and upload to GL
        D3D11_MAPPED_SUBRESOURCE mapped;
        hr = context->Map(staging, 0, D3D11_MAP_READ, 0, &mapped);
        if (SUCCEEDED(hr))
        {
            // Debug: log first successful copy and check data
            static int copyCount = 0;
            copyCount++;
            if (copyCount <= 3 || copyCount % 100 == 0)
            {
                // Check first few pixels
                uint8_t* pixels = static_cast<uint8_t*>(mapped.pData);
                uint32_t sum = 0;
                for (int i = 0; i < 1000 && i < width * height * 4; i++)
                {
                    sum += pixels[i];
                }
                fprintf(stderr, "[ViewportBridge] CPU copy #%d: %dx%d, pitch=%u, checksum=%u\n",
                        copyCount, width, height, mapped.RowPitch, sum);
                fflush(stderr);
            }

            // Handle row pitch mismatch - D3D may have padding
            if (mapped.RowPitch == width * 4)
            {
                // Direct upload
                glBindTexture(GL_TEXTURE_2D, glTexture);
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height,
                               GL_RGBA, GL_UNSIGNED_BYTE, mapped.pData);
                glBindTexture(GL_TEXTURE_2D, 0);
            }
            else
            {
                // Row-by-row upload with pitch handling
                glBindTexture(GL_TEXTURE_2D, glTexture);
                glPixelStorei(GL_UNPACK_ROW_LENGTH, mapped.RowPitch / 4);
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, width, height,
                               GL_RGBA, GL_UNSIGNED_BYTE, mapped.pData);
                glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
                glBindTexture(GL_TEXTURE_2D, 0);
            }
            context->Unmap(staging, 0);
        }
        else
        {
            static bool errorLogged = false;
            if (!errorLogged)
            {
                fprintf(stderr, "[ViewportBridge] Map failed: 0x%08X\n", hr);
                fflush(stderr);
                errorLogged = false;
            }
        }
    }

    return true;
}

void ViewportBridge::releaseTexture()
{
    // Unlock OpenGL access
    if (hardwareInterop && glHandle && wglDXUnlockObjectsNV)
    {
        auto unlockObjects = reinterpret_cast<PFNWGLDXUNLOCKOBJECTSNVPROC>(wglDXUnlockObjectsNV);
        HANDLE handles[] = { glHandle };
        unlockObjects(interopDevice, 1, handles);
    }

    // Release keyed mutex (key 0 = producer)
    if (keyedMutex)
    {
        IDXGIKeyedMutex* mutex = static_cast<IDXGIKeyedMutex*>(keyedMutex);
        mutex->ReleaseSync(0);
    }
}

bool ViewportBridge::copyToCPU(void* destBuffer, int destPitch)
{
    if (!sharedTexture || !stagingTexture || !d3dContext)
    {
        return false;
    }

    ID3D11DeviceContext* context = static_cast<ID3D11DeviceContext*>(d3dContext);
    ID3D11Texture2D* src = static_cast<ID3D11Texture2D*>(sharedTexture);
    ID3D11Texture2D* staging = static_cast<ID3D11Texture2D*>(stagingTexture);

    // Copy to staging
    context->CopyResource(staging, src);

    // Map and copy to dest
    D3D11_MAPPED_SUBRESOURCE mapped;
    HRESULT hr = context->Map(staging, 0, D3D11_MAP_READ, 0, &mapped);
    if (FAILED(hr))
    {
        return false;
    }

    // Copy row by row
    const uint8_t* srcRow = static_cast<const uint8_t*>(mapped.pData);
    uint8_t* dstRow = static_cast<uint8_t*>(destBuffer);
    int rowSize = width * 4;

    for (int y = 0; y < height; ++y)
    {
        memcpy(dstRow, srcRow, rowSize);
        srcRow += mapped.RowPitch;
        dstRow += destPitch;
    }

    context->Unmap(staging, 0);
    return true;
}

// C API implementation
extern "C" {

ViewportBridge* viewport_create()
{
    return new ViewportBridge();
}

void viewport_destroy(ViewportBridge* bridge)
{
    delete bridge;
}

int viewport_initialize(ViewportBridge* bridge)
{
    return bridge->initialize() ? 1 : 0;
}

void viewport_shutdown(ViewportBridge* bridge)
{
    bridge->shutdown();
}

int viewport_is_initialized(ViewportBridge* bridge)
{
    return bridge->isInitialized() ? 1 : 0;
}

int viewport_open_texture(ViewportBridge* bridge, const char* handleName, int width, int height)
{
    return bridge->openSharedTexture(handleName, width, height) ? 1 : 0;
}

void viewport_close_texture(ViewportBridge* bridge)
{
    bridge->closeSharedTexture();
}

int viewport_has_texture(ViewportBridge* bridge)
{
    return bridge->hasTexture() ? 1 : 0;
}

int viewport_acquire(ViewportBridge* bridge)
{
    return bridge->acquireTexture() ? 1 : 0;
}

void viewport_release(ViewportBridge* bridge)
{
    bridge->releaseTexture();
}

unsigned int viewport_get_gl_texture(ViewportBridge* bridge)
{
    return bridge->getGLTexture();
}

int viewport_get_width(ViewportBridge* bridge)
{
    return bridge->getWidth();
}

int viewport_get_height(ViewportBridge* bridge)
{
    return bridge->getHeight();
}

int viewport_copy_to_cpu(ViewportBridge* bridge, void* buffer, int pitch)
{
    return bridge->copyToCPU(buffer, pitch) ? 1 : 0;
}

int viewport_has_hardware_interop(ViewportBridge* bridge)
{
    return bridge->hasHardwareInterop() ? 1 : 0;
}

} // extern "C"
