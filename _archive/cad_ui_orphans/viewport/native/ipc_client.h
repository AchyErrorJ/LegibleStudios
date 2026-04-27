// ipc_client.h - Named pipe client for UE5 communication
#pragma once

#ifdef VIEWPORT_EXPORTS
#define VIEWPORT_API __declspec(dllexport)
#else
#define VIEWPORT_API __declspec(dllimport)
#endif

#include <cstdint>
#include <functional>
#include <thread>
#include <atomic>
#include <string>

// Message types (must match UE5 side)
enum class IPCMessageType : uint8_t
{
    // UE5 -> Qt
    TextureReady = 0,
    TextureResized = 1,
    TextureDestroyed = 2,
    FrameReady = 3,

    // Qt -> UE5
    InputMouseMove = 4,
    InputMouseButton = 5,
    InputMouseWheel = 6,
    InputKeyboard = 7,
    InputTouch = 8,

    // Bidirectional
    SelectionChanged = 9,
    ViewChanged = 10,
    Command = 11,
    Ping = 12,
    Pong = 13
};

#pragma pack(push, 1)
struct IPCMessageHeader
{
    uint32_t magic;         // 'ARCH' = 0x48435241
    uint32_t version;       // Protocol version
    uint8_t messageType;    // IPCMessageType
    uint32_t payloadSize;   // Size of payload
    uint64_t timestamp;     // Sender timestamp
};

struct TextureInfo
{
    char handleName[256];
    int32_t width;
    int32_t height;
    int32_t format;
    int64_t frameNumber;
    double timestamp;
};

struct MouseMoveInput
{
    float posX, posY;
    float deltaX, deltaY;
};

struct MouseButtonInput
{
    float posX, posY;
    uint8_t button;     // 0=Left, 1=Right, 2=Middle
    uint8_t pressed;    // 1=pressed, 0=released
};

struct MouseWheelInput
{
    float posX, posY;
    float delta;
};

struct KeyboardInput
{
    int32_t keyCode;
    uint8_t pressed;
    uint8_t shift;
    uint8_t ctrl;
    uint8_t alt;
};
#pragma pack(pop)

// Callbacks
typedef void (*OnTextureReadyCallback)(const TextureInfo* info);
typedef void (*OnTextureResizedCallback)(const TextureInfo* info);
typedef void (*OnTextureDestroyedCallback)();
typedef void (*OnFrameReadyCallback)(int64_t frameNumber);
typedef void (*OnConnectionChangedCallback)(int connected);

class VIEWPORT_API IPCClient
{
public:
    IPCClient();
    ~IPCClient();

    // Connection
    bool connect(const char* pipeName);
    void disconnect();
    bool isConnected() const;

    // Send input
    bool sendMouseMove(float x, float y, float deltaX, float deltaY);
    bool sendMouseButton(float x, float y, int button, bool pressed);
    bool sendMouseWheel(float x, float y, float delta);
    bool sendKeyboard(int keyCode, bool pressed, bool shift, bool ctrl, bool alt);
    bool sendPing();

    // Callbacks
    void setOnTextureReady(OnTextureReadyCallback cb) { onTextureReady = cb; }
    void setOnTextureResized(OnTextureResizedCallback cb) { onTextureResized = cb; }
    void setOnTextureDestroyed(OnTextureDestroyedCallback cb) { onTextureDestroyed = cb; }
    void setOnFrameReady(OnFrameReadyCallback cb) { onFrameReady = cb; }
    void setOnConnectionChanged(OnConnectionChangedCallback cb) { onConnectionChanged = cb; }

    // Statistics
    int getMessagesReceived() const { return messagesReceived; }
    int getMessagesSent() const { return messagesSent; }

private:
    void* pipeHandle;
    std::thread receiveThread;
    std::atomic<bool> running;
    std::atomic<bool> connected;
    std::atomic<int> messagesReceived;
    std::atomic<int> messagesSent;

    OnTextureReadyCallback onTextureReady = nullptr;
    OnTextureResizedCallback onTextureResized = nullptr;
    OnTextureDestroyedCallback onTextureDestroyed = nullptr;
    OnFrameReadyCallback onFrameReady = nullptr;
    OnConnectionChangedCallback onConnectionChanged = nullptr;

    void receiveLoop();
    bool sendMessage(IPCMessageType type, const void* payload, uint32_t size);
    void processMessage(const IPCMessageHeader& header, const uint8_t* payload);

    static constexpr uint32_t MAGIC = 0x48435241;
    static constexpr uint32_t VERSION = 1;
    static constexpr int BUFFER_SIZE = 65536;
};

// C API for Python ctypes
extern "C" {
    VIEWPORT_API IPCClient* ipc_create();
    VIEWPORT_API void ipc_destroy(IPCClient* client);
    VIEWPORT_API int ipc_connect(IPCClient* client, const char* pipeName);
    VIEWPORT_API void ipc_disconnect(IPCClient* client);
    VIEWPORT_API int ipc_is_connected(IPCClient* client);

    VIEWPORT_API int ipc_send_mouse_move(IPCClient* client, float x, float y, float dx, float dy);
    VIEWPORT_API int ipc_send_mouse_button(IPCClient* client, float x, float y, int button, int pressed);
    VIEWPORT_API int ipc_send_mouse_wheel(IPCClient* client, float x, float y, float delta);
    VIEWPORT_API int ipc_send_keyboard(IPCClient* client, int keyCode, int pressed, int shift, int ctrl, int alt);
    VIEWPORT_API int ipc_send_ping(IPCClient* client);

    VIEWPORT_API void ipc_set_texture_ready_callback(IPCClient* client, OnTextureReadyCallback cb);
    VIEWPORT_API void ipc_set_texture_resized_callback(IPCClient* client, OnTextureResizedCallback cb);
    VIEWPORT_API void ipc_set_texture_destroyed_callback(IPCClient* client, OnTextureDestroyedCallback cb);
    VIEWPORT_API void ipc_set_frame_ready_callback(IPCClient* client, OnFrameReadyCallback cb);
    VIEWPORT_API void ipc_set_connection_changed_callback(IPCClient* client, OnConnectionChangedCallback cb);
}
