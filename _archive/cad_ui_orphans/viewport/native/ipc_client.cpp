// ipc_client.cpp - Named pipe client implementation

#include "ipc_client.h"
#include <Windows.h>
#include <vector>
#include <cstring>

IPCClient::IPCClient()
    : pipeHandle(INVALID_HANDLE_VALUE)
    , running(false)
    , connected(false)
    , messagesReceived(0)
    , messagesSent(0)
{
}

IPCClient::~IPCClient()
{
    disconnect();
}

bool IPCClient::connect(const char* pipeName)
{
    if (connected)
    {
        return true;
    }

    // Build pipe path
    std::string fullPath = "\\\\.\\pipe\\";
    fullPath += pipeName;

    // Try to connect
    for (int retry = 0; retry < 10; ++retry)
    {
        pipeHandle = CreateFileA(
            fullPath.c_str(),
            GENERIC_READ | GENERIC_WRITE,
            0,
            nullptr,
            OPEN_EXISTING,
            FILE_FLAG_OVERLAPPED,
            nullptr
        );

        if (pipeHandle != INVALID_HANDLE_VALUE)
        {
            break;
        }

        DWORD error = GetLastError();
        if (error == ERROR_PIPE_BUSY)
        {
            // Wait for pipe to become available
            if (!WaitNamedPipeA(fullPath.c_str(), 1000))
            {
                continue;
            }
        }
        else
        {
            Sleep(100);
        }
    }

    if (pipeHandle == INVALID_HANDLE_VALUE)
    {
        return false;
    }

    // Set pipe to message mode
    DWORD mode = PIPE_READMODE_MESSAGE;
    if (!SetNamedPipeHandleState(pipeHandle, &mode, nullptr, nullptr))
    {
        CloseHandle(pipeHandle);
        pipeHandle = INVALID_HANDLE_VALUE;
        return false;
    }

    connected = true;
    running = true;

    // Start receive thread
    receiveThread = std::thread(&IPCClient::receiveLoop, this);

    if (onConnectionChanged)
    {
        onConnectionChanged(1);
    }

    return true;
}

void IPCClient::disconnect()
{
    if (!connected)
    {
        return;
    }

    running = false;
    connected = false;

    if (pipeHandle != INVALID_HANDLE_VALUE)
    {
        CancelIo(pipeHandle);
        CloseHandle(pipeHandle);
        pipeHandle = INVALID_HANDLE_VALUE;
    }

    if (receiveThread.joinable())
    {
        receiveThread.join();
    }

    if (onConnectionChanged)
    {
        onConnectionChanged(0);
    }
}

bool IPCClient::isConnected() const
{
    return connected;
}

void IPCClient::receiveLoop()
{
    std::vector<uint8_t> buffer(BUFFER_SIZE);
    OVERLAPPED overlapped = {};
    overlapped.hEvent = CreateEventA(nullptr, TRUE, FALSE, nullptr);

    while (running)
    {
        DWORD bytesRead = 0;
        BOOL result = ReadFile(
            pipeHandle,
            buffer.data(),
            BUFFER_SIZE,
            &bytesRead,
            &overlapped
        );

        if (!result)
        {
            DWORD error = GetLastError();
            if (error == ERROR_IO_PENDING)
            {
                // Wait for data with timeout
                DWORD waitResult = WaitForSingleObject(overlapped.hEvent, 100);
                if (waitResult == WAIT_OBJECT_0)
                {
                    if (!GetOverlappedResult(pipeHandle, &overlapped, &bytesRead, FALSE))
                    {
                        if (GetLastError() == ERROR_BROKEN_PIPE)
                        {
                            break;
                        }
                        continue;
                    }
                }
                else if (waitResult == WAIT_TIMEOUT)
                {
                    continue;
                }
                else
                {
                    break;
                }
            }
            else if (error == ERROR_BROKEN_PIPE)
            {
                break;
            }
            else
            {
                continue;
            }
        }

        // Process message
        if (bytesRead >= sizeof(IPCMessageHeader))
        {
            IPCMessageHeader* header = reinterpret_cast<IPCMessageHeader*>(buffer.data());
            if (header->magic == MAGIC && header->version == VERSION)
            {
                const uint8_t* payload = buffer.data() + sizeof(IPCMessageHeader);
                processMessage(*header, payload);
                messagesReceived++;
            }
        }
    }

    CloseHandle(overlapped.hEvent);
    connected = false;

    if (onConnectionChanged)
    {
        onConnectionChanged(0);
    }
}

bool IPCClient::sendMessage(IPCMessageType type, const void* payload, uint32_t size)
{
    if (!connected || pipeHandle == INVALID_HANDLE_VALUE)
    {
        return false;
    }

    std::vector<uint8_t> buffer(sizeof(IPCMessageHeader) + size);

    IPCMessageHeader* header = reinterpret_cast<IPCMessageHeader*>(buffer.data());
    header->magic = MAGIC;
    header->version = VERSION;
    header->messageType = static_cast<uint8_t>(type);
    header->payloadSize = size;
    header->timestamp = GetTickCount64();

    if (size > 0 && payload)
    {
        memcpy(buffer.data() + sizeof(IPCMessageHeader), payload, size);
    }

    DWORD bytesWritten = 0;
    if (!WriteFile(pipeHandle, buffer.data(), static_cast<DWORD>(buffer.size()), &bytesWritten, nullptr))
    {
        return false;
    }

    messagesSent++;
    return bytesWritten == buffer.size();
}

void IPCClient::processMessage(const IPCMessageHeader& header, const uint8_t* payload)
{
    IPCMessageType type = static_cast<IPCMessageType>(header.messageType);

    switch (type)
    {
        case IPCMessageType::TextureReady:
        {
            if (onTextureReady && header.payloadSize > 0)
            {
                TextureInfo info = {};
                // Parse payload (length-prefixed string + data)
                int nameLen = *reinterpret_cast<const int32_t*>(payload);
                if (nameLen > 0 && nameLen < 256)
                {
                    memcpy(info.handleName, payload + 4, nameLen);
                    info.handleName[nameLen] = '\0';
                }
                const uint8_t* data = payload + 4 + nameLen;
                info.width = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.height = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.format = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.frameNumber = *reinterpret_cast<const int64_t*>(data); data += 8;
                info.timestamp = *reinterpret_cast<const double*>(data);
                onTextureReady(&info);
            }
            break;
        }

        case IPCMessageType::TextureResized:
        {
            if (onTextureResized && header.payloadSize > 0)
            {
                TextureInfo info = {};
                int nameLen = *reinterpret_cast<const int32_t*>(payload);
                if (nameLen > 0 && nameLen < 256)
                {
                    memcpy(info.handleName, payload + 4, nameLen);
                }
                const uint8_t* data = payload + 4 + nameLen;
                info.width = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.height = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.format = *reinterpret_cast<const int32_t*>(data); data += 4;
                info.frameNumber = *reinterpret_cast<const int64_t*>(data); data += 8;
                info.timestamp = *reinterpret_cast<const double*>(data);
                onTextureResized(&info);
            }
            break;
        }

        case IPCMessageType::TextureDestroyed:
        {
            if (onTextureDestroyed)
            {
                onTextureDestroyed();
            }
            break;
        }

        case IPCMessageType::FrameReady:
        {
            if (onFrameReady && header.payloadSize >= sizeof(int64_t))
            {
                int64_t frameNumber = *reinterpret_cast<const int64_t*>(payload);
                onFrameReady(frameNumber);
            }
            break;
        }

        case IPCMessageType::Pong:
            // Ping response received
            break;

        default:
            break;
    }
}

bool IPCClient::sendMouseMove(float x, float y, float deltaX, float deltaY)
{
    MouseMoveInput input = { x, y, deltaX, deltaY };
    return sendMessage(IPCMessageType::InputMouseMove, &input, sizeof(input));
}

bool IPCClient::sendMouseButton(float x, float y, int button, bool pressed)
{
    MouseButtonInput input = { x, y, static_cast<uint8_t>(button), static_cast<uint8_t>(pressed ? 1 : 0) };
    return sendMessage(IPCMessageType::InputMouseButton, &input, sizeof(input));
}

bool IPCClient::sendMouseWheel(float x, float y, float delta)
{
    MouseWheelInput input = { x, y, delta };
    return sendMessage(IPCMessageType::InputMouseWheel, &input, sizeof(input));
}

bool IPCClient::sendKeyboard(int keyCode, bool pressed, bool shift, bool ctrl, bool alt)
{
    KeyboardInput input = {
        keyCode,
        static_cast<uint8_t>(pressed ? 1 : 0),
        static_cast<uint8_t>(shift ? 1 : 0),
        static_cast<uint8_t>(ctrl ? 1 : 0),
        static_cast<uint8_t>(alt ? 1 : 0)
    };
    return sendMessage(IPCMessageType::InputKeyboard, &input, sizeof(input));
}

bool IPCClient::sendPing()
{
    return sendMessage(IPCMessageType::Ping, nullptr, 0);
}

// C API implementation
extern "C" {

IPCClient* ipc_create()
{
    return new IPCClient();
}

void ipc_destroy(IPCClient* client)
{
    delete client;
}

int ipc_connect(IPCClient* client, const char* pipeName)
{
    return client->connect(pipeName) ? 1 : 0;
}

void ipc_disconnect(IPCClient* client)
{
    client->disconnect();
}

int ipc_is_connected(IPCClient* client)
{
    return client->isConnected() ? 1 : 0;
}

int ipc_send_mouse_move(IPCClient* client, float x, float y, float dx, float dy)
{
    return client->sendMouseMove(x, y, dx, dy) ? 1 : 0;
}

int ipc_send_mouse_button(IPCClient* client, float x, float y, int button, int pressed)
{
    return client->sendMouseButton(x, y, button, pressed != 0) ? 1 : 0;
}

int ipc_send_mouse_wheel(IPCClient* client, float x, float y, float delta)
{
    return client->sendMouseWheel(x, y, delta) ? 1 : 0;
}

int ipc_send_keyboard(IPCClient* client, int keyCode, int pressed, int shift, int ctrl, int alt)
{
    return client->sendKeyboard(keyCode, pressed != 0, shift != 0, ctrl != 0, alt != 0) ? 1 : 0;
}

int ipc_send_ping(IPCClient* client)
{
    return client->sendPing() ? 1 : 0;
}

void ipc_set_texture_ready_callback(IPCClient* client, OnTextureReadyCallback cb)
{
    client->setOnTextureReady(cb);
}

void ipc_set_texture_resized_callback(IPCClient* client, OnTextureResizedCallback cb)
{
    client->setOnTextureResized(cb);
}

void ipc_set_texture_destroyed_callback(IPCClient* client, OnTextureDestroyedCallback cb)
{
    client->setOnTextureDestroyed(cb);
}

void ipc_set_frame_ready_callback(IPCClient* client, OnFrameReadyCallback cb)
{
    client->setOnFrameReady(cb);
}

void ipc_set_connection_changed_callback(IPCClient* client, OnConnectionChangedCallback cb)
{
    client->setOnConnectionChanged(cb);
}

} // extern "C"
