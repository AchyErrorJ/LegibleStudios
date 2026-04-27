// ipc_server.cpp - Named pipe IPC server for CAD integration
// Provides real-time sync between Python CAD app and Vulkan renderer

#include "ipc_server.hpp"
#include <iostream>
#include <cstring>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <fcntl.h>
#endif

namespace arch {

IPCServer::IPCServer() {}

IPCServer::~IPCServer() {
    stop();
}

bool IPCServer::start(const std::string& pipeName) {
    if (m_running) {
        return true;
    }

    m_pipeName = pipeName;

#ifdef _WIN32
    std::string fullPipeName = "\\\\.\\pipe\\" + pipeName;

    // Create named pipe
    m_pipe = CreateNamedPipeA(
        fullPipeName.c_str(),
        PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        1,              // Max instances
        65536,          // Output buffer size
        65536,          // Input buffer size
        0,              // Default timeout
        nullptr         // Security attributes
    );

    if (m_pipe == INVALID_HANDLE_VALUE) {
        std::cerr << "[IPC] Failed to create pipe: " << GetLastError() << std::endl;
        return false;
    }

    std::cout << "[IPC] Server started on " << fullPipeName << std::endl;
#else
    // Unix domain socket implementation
    std::string socketPath = "/tmp/" + pipeName + ".sock";
    unlink(socketPath.c_str());

    m_pipe = socket(AF_UNIX, SOCK_STREAM, 0);
    if (m_pipe < 0) {
        std::cerr << "[IPC] Failed to create socket" << std::endl;
        return false;
    }

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, socketPath.c_str(), sizeof(addr.sun_path) - 1);

    if (bind(m_pipe, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "[IPC] Failed to bind socket" << std::endl;
        close(m_pipe);
        m_pipe = -1;
        return false;
    }

    listen(m_pipe, 1);
    std::cout << "[IPC] Server started on " << socketPath << std::endl;
#endif

    m_running = true;
    m_serverThread = std::thread(&IPCServer::serverThread, this);

    return true;
}

void IPCServer::stop() {
    if (!m_running) {
        return;
    }

    m_running = false;

#ifdef _WIN32
    if (m_pipe != INVALID_HANDLE_VALUE) {
        CancelIoEx(m_pipe, nullptr);
        DisconnectNamedPipe(m_pipe);
        CloseHandle(m_pipe);
        m_pipe = INVALID_HANDLE_VALUE;
    }
#else
    if (m_pipe >= 0) {
        close(m_pipe);
        m_pipe = -1;
    }
#endif

    if (m_serverThread.joinable()) {
        m_serverThread.join();
    }

    std::cout << "[IPC] Server stopped" << std::endl;
}

void IPCServer::serverThread() {
    std::cout << "[IPC] Waiting for client connection..." << std::endl;

#ifdef _WIN32
    while (m_running) {
        // Wait for client connection
        OVERLAPPED overlapped = {};
        overlapped.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);

        BOOL connected = ConnectNamedPipe(m_pipe, &overlapped);
        if (!connected) {
            DWORD error = GetLastError();
            if (error == ERROR_IO_PENDING) {
                // Wait for connection with timeout
                DWORD waitResult = WaitForSingleObject(overlapped.hEvent, 100);
                if (waitResult == WAIT_TIMEOUT) {
                    CancelIo(m_pipe);
                    CloseHandle(overlapped.hEvent);
                    continue;
                }
            } else if (error != ERROR_PIPE_CONNECTED) {
                CloseHandle(overlapped.hEvent);
                continue;
            }
        }

        CloseHandle(overlapped.hEvent);

        m_clientConnected = true;
        std::cout << "[IPC] Client connected" << std::endl;

        if (onClientConnected) {
            std::lock_guard<std::mutex> lock(m_queueMutex);
            // Queue a connected notification
        }

        // Read messages from client
        while (m_running && m_clientConnected) {
            IPCMessage msg;
            if (readMessage(msg)) {
                std::lock_guard<std::mutex> lock(m_queueMutex);
                m_messageQueue.push(msg);
            } else {
                // Client disconnected or error
                break;
            }
        }

        m_clientConnected = false;
        std::cout << "[IPC] Client disconnected" << std::endl;

        // Disconnect and prepare for next client
        DisconnectNamedPipe(m_pipe);
    }
#else
    // Unix implementation
    while (m_running) {
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(m_pipe, &readfds);

        struct timeval tv;
        tv.tv_sec = 0;
        tv.tv_usec = 100000;  // 100ms timeout

        int ready = select(m_pipe + 1, &readfds, nullptr, nullptr, &tv);
        if (ready > 0) {
            int client = accept(m_pipe, nullptr, nullptr);
            if (client >= 0) {
                m_clientConnected = true;
                std::cout << "[IPC] Client connected" << std::endl;

                // Read messages
                char buffer[65536];
                while (m_running && m_clientConnected) {
                    ssize_t bytesRead = read(client, buffer, sizeof(buffer) - 1);
                    if (bytesRead > 0) {
                        buffer[bytesRead] = '\0';
                        IPCMessage msg;
                        msg.type = IPCMessageType::BuildingData;
                        msg.payload = std::string(buffer, bytesRead);

                        std::lock_guard<std::mutex> lock(m_queueMutex);
                        m_messageQueue.push(msg);
                    } else {
                        break;
                    }
                }

                close(client);
                m_clientConnected = false;
                std::cout << "[IPC] Client disconnected" << std::endl;
            }
        }
    }
#endif
}

bool IPCServer::readMessage(IPCMessage& msg) {
#ifdef _WIN32
    // Read message header (type + length)
    DWORD bytesRead = 0;
    u32 header[2];  // type, length

    OVERLAPPED overlapped = {};
    overlapped.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);

    BOOL success = ReadFile(m_pipe, header, sizeof(header), &bytesRead, &overlapped);
    if (!success) {
        DWORD error = GetLastError();
        if (error == ERROR_IO_PENDING) {
            // Wait with timeout
            DWORD waitResult = WaitForSingleObject(overlapped.hEvent, 1000);
            if (waitResult == WAIT_TIMEOUT) {
                CancelIo(m_pipe);
                CloseHandle(overlapped.hEvent);
                return false;
            }
            GetOverlappedResult(m_pipe, &overlapped, &bytesRead, FALSE);
        } else {
            CloseHandle(overlapped.hEvent);
            return false;
        }
    }
    CloseHandle(overlapped.hEvent);

    if (bytesRead != sizeof(header)) {
        return false;
    }

    msg.type = static_cast<IPCMessageType>(header[0]);
    u32 payloadLength = header[1];

    // Read payload
    if (payloadLength > 0) {
        msg.payload.resize(payloadLength);

        overlapped = {};
        overlapped.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr);

        success = ReadFile(m_pipe, msg.payload.data(), payloadLength, &bytesRead, &overlapped);
        if (!success) {
            DWORD error = GetLastError();
            if (error == ERROR_IO_PENDING) {
                DWORD waitResult = WaitForSingleObject(overlapped.hEvent, 5000);
                if (waitResult == WAIT_TIMEOUT) {
                    CancelIo(m_pipe);
                    CloseHandle(overlapped.hEvent);
                    return false;
                }
                GetOverlappedResult(m_pipe, &overlapped, &bytesRead, FALSE);
            } else {
                CloseHandle(overlapped.hEvent);
                return false;
            }
        }
        CloseHandle(overlapped.hEvent);

        if (bytesRead != payloadLength) {
            return false;
        }
    }

    return true;
#else
    return false;  // Simplified for Windows focus
#endif
}

bool IPCServer::writeMessage(const IPCMessage& msg) {
#ifdef _WIN32
    u32 header[2] = {
        static_cast<u32>(msg.type),
        static_cast<u32>(msg.payload.size())
    };

    DWORD bytesWritten = 0;
    if (!WriteFile(m_pipe, header, sizeof(header), &bytesWritten, nullptr)) {
        return false;
    }

    if (!msg.payload.empty()) {
        if (!WriteFile(m_pipe, msg.payload.data(), static_cast<DWORD>(msg.payload.size()), &bytesWritten, nullptr)) {
            return false;
        }
    }

    return true;
#else
    return false;
#endif
}

void IPCServer::poll() {
    std::lock_guard<std::mutex> lock(m_queueMutex);

    while (!m_messageQueue.empty()) {
        IPCMessage msg = m_messageQueue.front();
        m_messageQueue.pop();

        handleMessage(msg);
    }
}

void IPCServer::handleMessage(const IPCMessage& msg) {
    switch (msg.type) {
        case IPCMessageType::Ping:
            std::cout << "[IPC] Received ping" << std::endl;
            break;

        case IPCMessageType::BuildingData:
            std::cout << "[IPC] Received building data (" << msg.payload.size() << " bytes)" << std::endl;
            if (onBuildingData) {
                onBuildingData(msg.payload);
            }
            break;

        case IPCMessageType::CameraUpdate:
            // Parse camera data from payload
            if (onCameraUpdate && msg.payload.size() >= 12) {
                const float* data = reinterpret_cast<const float*>(msg.payload.data());
                onCameraUpdate(data[0], data[1], data[2]);
            }
            break;

        case IPCMessageType::SelectElement:
            std::cout << "[IPC] Received element selection" << std::endl;
            break;

        case IPCMessageType::Shutdown:
            std::cout << "[IPC] Received shutdown request" << std::endl;
            break;

        default:
            std::cout << "[IPC] Unknown message type: " << static_cast<int>(msg.type) << std::endl;
            break;
    }
}

} // namespace arch
