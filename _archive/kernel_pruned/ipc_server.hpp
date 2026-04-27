#pragma once

#include "types.hpp"
#include <string>
#include <functional>
#include <thread>
#include <atomic>
#include <mutex>
#include <queue>

#ifdef _WIN32
#include <windows.h>
#endif

namespace arch {

// Message types for IPC
enum class IPCMessageType : u32 {
    Ping = 0,
    Pong = 1,
    BuildingData = 2,      // JSON building data
    CameraUpdate = 3,      // Camera position/rotation
    SelectElement = 4,     // Element selection
    Shutdown = 255
};

// IPC Message structure
struct IPCMessage {
    IPCMessageType type;
    std::string payload;
};

// Callback types
using OnBuildingDataCallback = std::function<void(const std::string& json)>;
using OnCameraUpdateCallback = std::function<void(float yaw, float pitch, float distance)>;
using OnClientConnectedCallback = std::function<void(bool connected)>;

/**
 * Named pipe server for receiving data from CAD app.
 *
 * Usage:
 *     IPCServer server;
 *     server.onBuildingData = [](const std::string& json) {
 *         // Reload building from JSON
 *     };
 *     server.start("ArchEngine_Kernel");
 *
 *     // In main loop:
 *     server.poll();  // Process pending messages
 */
class IPCServer {
public:
    IPCServer();
    ~IPCServer();

    // Non-copyable
    IPCServer(const IPCServer&) = delete;
    IPCServer& operator=(const IPCServer&) = delete;

    // Start/stop server
    bool start(const std::string& pipeName = "ArchEngine_Kernel");
    void stop();
    bool isRunning() const { return m_running; }

    // Poll for messages (call from main thread)
    void poll();

    // Check if client is connected
    bool isClientConnected() const { return m_clientConnected; }

    // Callbacks
    OnBuildingDataCallback onBuildingData;
    OnCameraUpdateCallback onCameraUpdate;
    OnClientConnectedCallback onClientConnected;

private:
    void serverThread();
    void handleMessage(const IPCMessage& msg);
    bool readMessage(IPCMessage& msg);
    bool writeMessage(const IPCMessage& msg);

#ifdef _WIN32
    HANDLE m_pipe = INVALID_HANDLE_VALUE;
#else
    int m_pipe = -1;
#endif

    std::string m_pipeName;
    std::thread m_serverThread;
    std::atomic<bool> m_running{false};
    std::atomic<bool> m_clientConnected{false};

    // Thread-safe message queue
    std::mutex m_queueMutex;
    std::queue<IPCMessage> m_messageQueue;
};

} // namespace arch
