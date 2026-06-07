// ArchIPCServer.cpp - Named pipe server implementation

#include "Integration/ArchIPCServer.h"
#include "HAL/PlatformProcess.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/MemoryReader.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include "Windows/WindowsHWrapper.h"
#include <Windows.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

// Windows TRUE/FALSE compatibility
#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

FArchIPCServer::FArchIPCServer()
	: PipeHandle(nullptr)
	, StopEvent(nullptr)
	, Thread(nullptr)
	, bIsRunning(false)
	, bClientConnected(false)
	, bStopRequested(false)
	, MessagesReceived(0)
	, MessagesSent(0)
{
	ReceiveBuffer.SetNumUninitialized(BUFFER_SIZE);
}

FArchIPCServer::~FArchIPCServer()
{
	Stop();
}

bool FArchIPCServer::Start(const FString& InPipeName)
{
	if (bIsRunning)
	{
		UE_LOG(LogTemp, Warning, TEXT("ArchIPCServer: Already running"));
		return false;
	}

	PipeName = InPipeName;
	bStopRequested = false;

#if PLATFORM_WINDOWS
	// Create stop event
	StopEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
	if (!StopEvent)
	{
		UE_LOG(LogTemp, Error, TEXT("ArchIPCServer: Failed to create stop event"));
		return false;
	}
#endif

	// Create and start thread
	Thread = FRunnableThread::Create(this, TEXT("ArchIPCServer"), 0, TPri_Normal);
	if (!Thread)
	{
		UE_LOG(LogTemp, Error, TEXT("ArchIPCServer: Failed to create thread"));
#if PLATFORM_WINDOWS
		CloseHandle(StopEvent);
		StopEvent = nullptr;
#endif
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Started with pipe name '%s'"), *PipeName);
	return true;
}

void FArchIPCServer::Stop()
{
	if (!bIsRunning && !Thread)
	{
		return;
	}

	bStopRequested = true;

#if PLATFORM_WINDOWS
	if (StopEvent)
	{
		SetEvent(static_cast<HANDLE>(StopEvent));
	}
#endif

	if (Thread)
	{
		Thread->WaitForCompletion();
		delete Thread;
		Thread = nullptr;
	}

	ClosePipe();

#if PLATFORM_WINDOWS
	if (StopEvent)
	{
		CloseHandle(static_cast<HANDLE>(StopEvent));
		StopEvent = nullptr;
	}
#endif

	bIsRunning = false;
	bClientConnected = false;

	UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Stopped"));
}

bool FArchIPCServer::Init()
{
	bIsRunning = true;
	return CreatePipe();
}

uint32 FArchIPCServer::Run()
{
	UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Thread started"));

	while (!bStopRequested)
	{
		// Wait for client connection
		if (!bClientConnected)
		{
			if (WaitForClient())
			{
				bClientConnected = true;
				UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Client connected"));

				// Notify on game thread
				AsyncTask(ENamedThreads::GameThread, [this]()
				{
					OnClientConnected.ExecuteIfBound(true);
				});
			}
			else if (bStopRequested)
			{
				break;
			}
			continue;
		}

		// Read messages from client
		if (!ReadMessage())
		{
			// Client disconnected or error
			bClientConnected = false;
			UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Client disconnected"));

			AsyncTask(ENamedThreads::GameThread, [this]()
			{
				OnClientConnected.ExecuteIfBound(false);
			});

			// Recreate pipe for next client
			ClosePipe();
			if (!CreatePipe())
			{
				UE_LOG(LogTemp, Error, TEXT("ArchIPCServer: Failed to recreate pipe"));
				break;
			}
		}
	}

	UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Thread exiting"));
	return 0;
}

void FArchIPCServer::Exit()
{
	bIsRunning = false;
}

bool FArchIPCServer::CreatePipe()
{
#if PLATFORM_WINDOWS
	FString FullPipeName = FString::Printf(TEXT("\\\\.\\pipe\\%s"), *PipeName);

	PipeHandle = CreateNamedPipeW(
		*FullPipeName,
		PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
		PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
		1,                    // Max instances
		BUFFER_SIZE,          // Out buffer size
		BUFFER_SIZE,          // In buffer size
		0,                    // Default timeout
		nullptr               // Security attributes
	);

	if (PipeHandle == INVALID_HANDLE_VALUE)
	{
		UE_LOG(LogTemp, Error, TEXT("ArchIPCServer: Failed to create pipe '%s', error %d"),
			*FullPipeName, GetLastError());
		PipeHandle = nullptr;
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("ArchIPCServer: Created pipe '%s'"), *FullPipeName);
	return true;
#else
	UE_LOG(LogTemp, Error, TEXT("ArchIPCServer: Named pipes only supported on Windows"));
	return false;
#endif
}

void FArchIPCServer::ClosePipe()
{
#if PLATFORM_WINDOWS
	if (PipeHandle)
	{
		DisconnectNamedPipe(static_cast<HANDLE>(PipeHandle));
		CloseHandle(static_cast<HANDLE>(PipeHandle));
		PipeHandle = nullptr;
	}
#endif
}

bool FArchIPCServer::WaitForClient()
{
#if PLATFORM_WINDOWS
	if (!PipeHandle)
	{
		return false;
	}

	OVERLAPPED Overlapped = {};
	Overlapped.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);

	BOOL Result = ConnectNamedPipe(static_cast<HANDLE>(PipeHandle), &Overlapped);
	DWORD Error = GetLastError();

	if (Result || Error == ERROR_PIPE_CONNECTED)
	{
		CloseHandle(Overlapped.hEvent);
		return true;
	}

	if (Error != ERROR_IO_PENDING)
	{
		CloseHandle(Overlapped.hEvent);
		return false;
	}

	// Wait for connection or stop event
	HANDLE WaitHandles[2] = { Overlapped.hEvent, static_cast<HANDLE>(StopEvent) };
	DWORD WaitResult = WaitForMultipleObjects(2, WaitHandles, FALSE, INFINITE);

	CloseHandle(Overlapped.hEvent);

	if (WaitResult == WAIT_OBJECT_0)
	{
		DWORD BytesTransferred;
		if (GetOverlappedResult(static_cast<HANDLE>(PipeHandle), &Overlapped, &BytesTransferred, FALSE))
		{
			return true;
		}
	}

	// Stop requested or error
	CancelIo(static_cast<HANDLE>(PipeHandle));
	return false;
#else
	return false;
#endif
}

bool FArchIPCServer::ReadMessage()
{
#if PLATFORM_WINDOWS
	if (!PipeHandle || !bClientConnected)
	{
		return false;
	}

	OVERLAPPED Overlapped = {};
	Overlapped.hEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);

	DWORD BytesRead = 0;
	BOOL Result = ReadFile(
		static_cast<HANDLE>(PipeHandle),
		ReceiveBuffer.GetData(),
		BUFFER_SIZE,
		&BytesRead,
		&Overlapped
	);

	if (!Result)
	{
		DWORD Error = GetLastError();
		if (Error == ERROR_IO_PENDING)
		{
			// Wait for data or stop event
			HANDLE WaitHandles[2] = { Overlapped.hEvent, static_cast<HANDLE>(StopEvent) };
			DWORD WaitResult = WaitForMultipleObjects(2, WaitHandles, FALSE, 100); // 100ms timeout

			if (WaitResult == WAIT_OBJECT_0)
			{
				if (!GetOverlappedResult(static_cast<HANDLE>(PipeHandle), &Overlapped, &BytesRead, FALSE))
				{
					CloseHandle(Overlapped.hEvent);
					return false;
				}
			}
			else if (WaitResult == WAIT_TIMEOUT)
			{
				// No data, but still connected
				CancelIo(static_cast<HANDLE>(PipeHandle));
				CloseHandle(Overlapped.hEvent);
				return true;
			}
			else
			{
				// Stop requested or error
				CancelIo(static_cast<HANDLE>(PipeHandle));
				CloseHandle(Overlapped.hEvent);
				return false;
			}
		}
		else if (Error == ERROR_BROKEN_PIPE || Error == ERROR_PIPE_NOT_CONNECTED)
		{
			CloseHandle(Overlapped.hEvent);
			return false;
		}
		else
		{
			CloseHandle(Overlapped.hEvent);
			return true; // Other error, keep trying
		}
	}

	CloseHandle(Overlapped.hEvent);

	// Process received data
	if (BytesRead >= sizeof(FArchIPCMessageHeader))
	{
		FArchIPCMessageHeader* Header = reinterpret_cast<FArchIPCMessageHeader*>(ReceiveBuffer.GetData());

		if (Header->Magic == MAGIC && Header->Version == VERSION)
		{
			const uint8* Payload = ReceiveBuffer.GetData() + sizeof(FArchIPCMessageHeader);
			ProcessMessage(*Header, Payload);
			MessagesReceived++;
		}
		else
		{
			UE_LOG(LogTemp, Warning, TEXT("ArchIPCServer: Invalid message header"));
		}
	}

	return true;
#else
	return false;
#endif
}

bool FArchIPCServer::SendMessage(EArchIPCMessageType Type, const void* Payload, uint32 PayloadSize)
{
#if PLATFORM_WINDOWS
	if (!PipeHandle || !bClientConnected)
	{
		return false;
	}

	// Build message
	TArray<uint8> MessageBuffer;
	MessageBuffer.SetNumUninitialized(sizeof(FArchIPCMessageHeader) + PayloadSize);

	FArchIPCMessageHeader* Header = reinterpret_cast<FArchIPCMessageHeader*>(MessageBuffer.GetData());
	Header->Magic = MAGIC;
	Header->Version = VERSION;
	Header->MessageType = static_cast<uint8>(Type);
	Header->PayloadSize = PayloadSize;
	Header->Timestamp = FPlatformTime::Cycles64();

	if (PayloadSize > 0 && Payload)
	{
		FMemory::Memcpy(MessageBuffer.GetData() + sizeof(FArchIPCMessageHeader), Payload, PayloadSize);
	}

	// Send
	DWORD BytesWritten = 0;
	BOOL Result = WriteFile(
		static_cast<HANDLE>(PipeHandle),
		MessageBuffer.GetData(),
		MessageBuffer.Num(),
		&BytesWritten,
		nullptr
	);

	if (Result && BytesWritten == MessageBuffer.Num())
	{
		MessagesSent++;
		return true;
	}

	UE_LOG(LogTemp, Warning, TEXT("ArchIPCServer: Failed to send message, error %d"), GetLastError());
	return false;
#else
	return false;
#endif
}

void FArchIPCServer::ProcessMessage(const FArchIPCMessageHeader& Header, const uint8* Payload)
{
	EArchIPCMessageType Type = static_cast<EArchIPCMessageType>(Header.MessageType);

	switch (Type)
	{
		case EArchIPCMessageType::InputMouseMove:
		{
			if (Header.PayloadSize >= sizeof(FArchInputMouseMove))
			{
				FArchInputMouseMove Input;
				FMemory::Memcpy(&Input, Payload, sizeof(FArchInputMouseMove));
				AsyncTask(ENamedThreads::GameThread, [this, Input]()
				{
					OnMouseMove.ExecuteIfBound(Input);
				});
			}
			break;
		}

		case EArchIPCMessageType::InputMouseButton:
		{
			if (Header.PayloadSize >= sizeof(FArchInputMouseButton))
			{
				FArchInputMouseButton Input;
				FMemory::Memcpy(&Input, Payload, sizeof(FArchInputMouseButton));
				AsyncTask(ENamedThreads::GameThread, [this, Input]()
				{
					OnMouseButton.ExecuteIfBound(Input);
				});
			}
			break;
		}

		case EArchIPCMessageType::InputMouseWheel:
		{
			if (Header.PayloadSize >= sizeof(FArchInputMouseWheel))
			{
				FArchInputMouseWheel Input;
				FMemory::Memcpy(&Input, Payload, sizeof(FArchInputMouseWheel));
				AsyncTask(ENamedThreads::GameThread, [this, Input]()
				{
					OnMouseWheel.ExecuteIfBound(Input);
				});
			}
			break;
		}

		case EArchIPCMessageType::InputKeyboard:
		{
			if (Header.PayloadSize >= sizeof(FArchInputKeyboard))
			{
				FArchInputKeyboard Input;
				FMemory::Memcpy(&Input, Payload, sizeof(FArchInputKeyboard));
				AsyncTask(ENamedThreads::GameThread, [this, Input]()
				{
					OnKeyboard.ExecuteIfBound(Input);
				});
			}
			break;
		}

		case EArchIPCMessageType::Ping:
		{
			AsyncTask(ENamedThreads::GameThread, [this]()
			{
				OnPing.ExecuteIfBound();
			});
			SendPong();
			break;
		}

		case EArchIPCMessageType::SelectionChanged:
		{
			// Parse selection IDs from payload
			TArray<FString> SelectedIds;
			if (Header.PayloadSize > 0)
			{
				FMemoryReader Reader(TArray<uint8>(Payload, Header.PayloadSize));
				int32 Count = 0;
				Reader << Count;
				for (int32 i = 0; i < Count; ++i)
				{
					FString Id;
					Reader << Id;
					SelectedIds.Add(Id);
				}
			}
			AsyncTask(ENamedThreads::GameThread, [this, SelectedIds]()
			{
				OnSelectionChanged.ExecuteIfBound(SelectedIds);
			});
			break;
		}

		default:
			UE_LOG(LogTemp, Verbose, TEXT("ArchIPCServer: Unhandled message type %d"), Header.MessageType);
			break;
	}
}

void FArchIPCServer::SerializeTextureInfo(TArray<uint8>& OutBuffer, const FArchSharedTextureInfo& Info)
{
	FMemoryWriter Writer(OutBuffer);

	// Write handle name as length-prefixed string
	int32 NameLen = Info.HandleName.Len();
	Writer << NameLen;
	Writer.Serialize(TCHAR_TO_ANSI(*Info.HandleName), NameLen);

	// Write dimensions and format
	int32 Width = Info.Width;
	int32 Height = Info.Height;
	int32 Format = Info.Format;
	uint64 FrameNumber = Info.FrameNumber;
	double Timestamp = Info.Timestamp;

	Writer << Width;
	Writer << Height;
	Writer << Format;
	Writer << FrameNumber;
	Writer << Timestamp;
}

bool FArchIPCServer::SendTextureReady(const FArchSharedTextureInfo& TextureInfo)
{
	TArray<uint8> Payload;
	SerializeTextureInfo(Payload, TextureInfo);
	return SendMessage(EArchIPCMessageType::TextureReady, Payload.GetData(), Payload.Num());
}

bool FArchIPCServer::SendTextureResized(const FArchSharedTextureInfo& TextureInfo)
{
	TArray<uint8> Payload;
	SerializeTextureInfo(Payload, TextureInfo);
	return SendMessage(EArchIPCMessageType::TextureResized, Payload.GetData(), Payload.Num());
}

bool FArchIPCServer::SendTextureDestroyed()
{
	return SendMessage(EArchIPCMessageType::TextureDestroyed, nullptr, 0);
}

bool FArchIPCServer::SendFrameReady(uint64 FrameNumber)
{
	return SendMessage(EArchIPCMessageType::FrameReady, &FrameNumber, sizeof(FrameNumber));
}

bool FArchIPCServer::SendPong()
{
	return SendMessage(EArchIPCMessageType::Pong, nullptr, 0);
}
