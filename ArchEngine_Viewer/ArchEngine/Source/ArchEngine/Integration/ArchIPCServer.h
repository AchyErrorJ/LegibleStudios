// ArchIPCServer.h - Named pipe server for UE5-Qt communication
// Handles texture handle exchange and input forwarding

#pragma once

#include "CoreMinimal.h"
#include "HAL/Runnable.h"
#include "HAL/RunnableThread.h"
#include "ArchTextureShareTypes.h"

DECLARE_DELEGATE_OneParam(FOnIPCClientConnected, bool /* bConnected */);
DECLARE_DELEGATE_OneParam(FOnIPCMouseMove, const FArchInputMouseMove&);
DECLARE_DELEGATE_OneParam(FOnIPCMouseButton, const FArchInputMouseButton&);
DECLARE_DELEGATE_OneParam(FOnIPCMouseWheel, const FArchInputMouseWheel&);
DECLARE_DELEGATE_OneParam(FOnIPCKeyboard, const FArchInputKeyboard&);
DECLARE_DELEGATE_OneParam(FOnIPCSelectionChanged, const TArray<FString>&);
DECLARE_DELEGATE(FOnIPCPing);

// IPC Message header (binary protocol)
#pragma pack(push, 1)
struct FArchIPCMessageHeader
{
	uint32 Magic;           // 'ARCH' = 0x48435241
	uint32 Version;         // Protocol version
	uint8 MessageType;      // EArchIPCMessageType
	uint32 PayloadSize;     // Size of payload following header
	uint64 Timestamp;       // Sender timestamp (microseconds)
};
#pragma pack(pop)

class ARCHENGINE_API FArchIPCServer : public FRunnable
{
public:
	FArchIPCServer();
	virtual ~FArchIPCServer();

	// Start the IPC server
	bool Start(const FString& InPipeName);

	// Stop the server
	void Stop();

	// Check if server is running
	bool IsRunning() const { return bIsRunning; }

	// Check if a client is connected
	bool IsClientConnected() const { return bClientConnected; }

	// Send texture info to client
	bool SendTextureReady(const FArchSharedTextureInfo& TextureInfo);

	// Send texture resized notification
	bool SendTextureResized(const FArchSharedTextureInfo& TextureInfo);

	// Send texture destroyed notification
	bool SendTextureDestroyed();

	// Send frame ready notification
	bool SendFrameReady(uint64 FrameNumber);

	// Send pong response
	bool SendPong();

	// Delegates for incoming messages
	FOnIPCClientConnected OnClientConnected;
	FOnIPCMouseMove OnMouseMove;
	FOnIPCMouseButton OnMouseButton;
	FOnIPCMouseWheel OnMouseWheel;
	FOnIPCKeyboard OnKeyboard;
	FOnIPCSelectionChanged OnSelectionChanged;
	FOnIPCPing OnPing;

	// Statistics
	int32 GetMessagesReceived() const { return MessagesReceived; }
	int32 GetMessagesSent() const { return MessagesSent; }

protected:
	// FRunnable interface
	virtual bool Init() override;
	virtual uint32 Run() override;
	virtual void Exit() override;

private:
	// Pipe name
	FString PipeName;

	// Windows handles (stored as void* for cross-platform header)
	void* PipeHandle;
	void* StopEvent;

	// Thread
	FRunnableThread* Thread;

	// State
	FThreadSafeBool bIsRunning;
	FThreadSafeBool bClientConnected;
	FThreadSafeBool bStopRequested;

	// Statistics
	TAtomic<int32> MessagesReceived;
	TAtomic<int32> MessagesSent;

	// Message buffer
	TArray<uint8> ReceiveBuffer;

	// Protocol constants
	static constexpr uint32 MAGIC = 0x48435241; // 'ARCH'
	static constexpr uint32 VERSION = 1;
	static constexpr int32 BUFFER_SIZE = 65536;

	// Internal methods
	bool CreatePipe();
	void ClosePipe();
	bool WaitForClient();
	bool ReadMessage();
	bool SendMessage(EArchIPCMessageType Type, const void* Payload, uint32 PayloadSize);
	void ProcessMessage(const FArchIPCMessageHeader& Header, const uint8* Payload);

	// Serialization helpers
	void SerializeTextureInfo(TArray<uint8>& OutBuffer, const FArchSharedTextureInfo& Info);
};
