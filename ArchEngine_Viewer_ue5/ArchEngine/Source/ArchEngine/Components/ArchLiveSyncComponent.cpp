// ArchLiveSyncComponent.cpp - Production-ready WebSocket client for real-time sync with 2D editor
// Supports heartbeat, message queuing, diagnostics, and backwards compatibility

#include "Components/ArchLiveSyncComponent.h"
#include "Actors/ArchBuildingActor.h"
#include "WebSocketsModule.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// ============= CONSTRUCTOR =============

UArchLiveSyncComponent::UArchLiveSyncComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickInterval = 0.1f;  // 10 Hz tick for responsive updates
}

// ============= LIFECYCLE =============

void UArchLiveSyncComponent::BeginPlay()
{
	Super::BeginPlay();

	// Find the ArchBuildingActor owner
	BuildingActor = Cast<AArchBuildingActor>(GetOwner());

	// Initialize diagnostics
	ResetDiagnostics();

	if (bAutoConnect)
	{
		Connect();
	}
}

void UArchLiveSyncComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	Disconnect();
	CleanupWebSocket();
	Super::EndPlay(EndPlayReason);
}

void UArchLiveSyncComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	// Update diagnostics
	UpdateDiagnostics(DeltaTime);

	// Handle reconnection logic
	if (bAutoReconnect && bWantsToConnect && ConnectionState == EArchLiveSyncConnectionState::Disconnected)
	{
		// Check if we have exceeded max attempts (0 = unlimited)
		if (MaxReconnectAttempts == 0 || CurrentReconnectAttempts < MaxReconnectAttempts)
		{
			TimeSinceLastReconnect += DeltaTime;
			if (TimeSinceLastReconnect >= ReconnectInterval)
			{
				AttemptReconnect();
			}
		}
	}

	// Handle heartbeat
	if (bEnableHeartbeat && ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		TimeSinceLastHeartbeat += DeltaTime;

		// Send heartbeat at interval
		if (TimeSinceLastHeartbeat >= HeartbeatInterval)
		{
			SendHeartbeat();
		}

		// Check for timeout (only if we have sent at least one heartbeat)
		if (LastHeartbeatSentTime > 0.0)
		{
			double TimeSinceResponse = FPlatformTime::Seconds() - LastHeartbeatReceivedTime;
			if (TimeSinceResponse > HeartbeatTimeout && LastHeartbeatReceivedTime > 0.0)
			{
				OnHeartbeatTimeout();
			}
		}
	}

	// Process outgoing queue when connected
	if (ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		ProcessOutgoingQueue();
	}

	// Prune stale messages from queue
	PruneStaleQueuedMessages();
}

// ============= CONNECTION MANAGEMENT =============

void UArchLiveSyncComponent::Connect()
{
	if (ConnectionState == EArchLiveSyncConnectionState::Connecting ||
		ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		return;
	}

	bWantsToConnect = true;
	SetConnectionState(EArchLiveSyncConnectionState::Connecting);

	CreateWebSocket();

	if (WebSocket.IsValid())
	{
		UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connecting to %s"), *ServerUrl);
		ConnectionStartTime = FPlatformTime::Seconds();
		WebSocket->Connect();
	}
	else
	{
		SetConnectionState(EArchLiveSyncConnectionState::Error);
		Diagnostics.LastError = TEXT("Failed to create WebSocket");
		OnError.Broadcast(Diagnostics.LastError);
	}
}

void UArchLiveSyncComponent::Disconnect()
{
	bWantsToConnect = false;
	CurrentReconnectAttempts = 0;

	if (WebSocket.IsValid() && WebSocket->IsConnected())
	{
		WebSocket->Close();
	}

	CleanupWebSocket();
	SetConnectionState(EArchLiveSyncConnectionState::Disconnected);
}

bool UArchLiveSyncComponent::IsConnected() const
{
	return ConnectionState == EArchLiveSyncConnectionState::Connected;
}

EArchLiveSyncConnectionState UArchLiveSyncComponent::GetConnectionState() const
{
	return ConnectionState;
}

void UArchLiveSyncComponent::CreateWebSocket()
{
	CleanupWebSocket();

	// Ensure WebSockets module is loaded
	FModuleManager::Get().LoadModuleChecked(TEXT("WebSockets"));

	// Create WebSocket
	WebSocket = FWebSocketsModule::Get().CreateWebSocket(ServerUrl, TEXT("ws"));

	if (WebSocket.IsValid())
	{
		// Bind events
		WebSocket->OnConnected().AddUObject(this, &UArchLiveSyncComponent::OnWebSocketConnected);
		WebSocket->OnConnectionError().AddUObject(this, &UArchLiveSyncComponent::OnWebSocketConnectionError);
		WebSocket->OnClosed().AddUObject(this, &UArchLiveSyncComponent::OnWebSocketClosed);
		WebSocket->OnMessage().AddUObject(this, &UArchLiveSyncComponent::OnWebSocketMessage);
	}
}

void UArchLiveSyncComponent::CleanupWebSocket()
{
	if (WebSocket.IsValid())
	{
		WebSocket->OnConnected().RemoveAll(this);
		WebSocket->OnConnectionError().RemoveAll(this);
		WebSocket->OnClosed().RemoveAll(this);
		WebSocket->OnMessage().RemoveAll(this);
		WebSocket.Reset();
	}
}

void UArchLiveSyncComponent::AttemptReconnect()
{
	TimeSinceLastReconnect = 0.0f;
	CurrentReconnectAttempts++;
	Diagnostics.ReconnectAttempts = CurrentReconnectAttempts;

	SetConnectionState(EArchLiveSyncConnectionState::Reconnecting);

	UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Reconnection attempt %d%s"),
		CurrentReconnectAttempts,
		MaxReconnectAttempts > 0 ? *FString::Printf(TEXT("/%d"), MaxReconnectAttempts) : TEXT(""));

	CreateWebSocket();

	if (WebSocket.IsValid())
	{
		ConnectionStartTime = FPlatformTime::Seconds();
		WebSocket->Connect();
	}
	else
	{
		SetConnectionState(EArchLiveSyncConnectionState::Error);
		Diagnostics.LastError = TEXT("Failed to create WebSocket on reconnect");
		OnError.Broadcast(Diagnostics.LastError);
	}
}

void UArchLiveSyncComponent::SetConnectionState(EArchLiveSyncConnectionState NewState)
{
	if (ConnectionState != NewState)
	{
		EArchLiveSyncConnectionState OldState = ConnectionState;
		ConnectionState = NewState;
		Diagnostics.ConnectionState = NewState;

		UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: State changed from %d to %d"), (int32)OldState, (int32)NewState);

		OnConnectionStateChanged.Broadcast(NewState);
	}
}

// ============= WEBSOCKET CALLBACKS =============

void UArchLiveSyncComponent::OnWebSocketConnected()
{
	SetConnectionState(EArchLiveSyncConnectionState::Connected);
	CurrentReconnectAttempts = 0;
	TimeSinceLastReconnect = 0.0f;
	TimeSinceLastHeartbeat = 0.0f;
	LastHeartbeatReceivedTime = FPlatformTime::Seconds();  // Assume healthy on connect

	UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connected to 2D editor at %s"), *ServerUrl);
}

void UArchLiveSyncComponent::OnWebSocketConnectionError(const FString& Error)
{
	Diagnostics.LastError = Error;
	SetConnectionState(EArchLiveSyncConnectionState::Error);

	UE_LOG(LogTemp, Warning, TEXT("ArchLiveSync: Connection error: %s"), *Error);
	OnError.Broadcast(Error);

	// If we want to stay connected, transition to disconnected for reconnect
	if (bWantsToConnect && bAutoReconnect)
	{
		SetConnectionState(EArchLiveSyncConnectionState::Disconnected);
	}
}

void UArchLiveSyncComponent::OnWebSocketClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
	UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connection closed (code %d, clean: %s): %s"),
		StatusCode, bWasClean ? TEXT("yes") : TEXT("no"), *Reason);

	CleanupWebSocket();
	SetConnectionState(EArchLiveSyncConnectionState::Disconnected);
}

void UArchLiveSyncComponent::OnWebSocketMessage(const FString& Message)
{
	// Update diagnostics
	Diagnostics.MessagesReceived++;
	Diagnostics.BytesReceived += Message.Len();
	LastMessageReceivedTime = FPlatformTime::Seconds();
	Diagnostics.TimeSinceLastMessage = 0.0f;

	if (bLogMessages)
	{
		UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Received message (%d bytes)"), Message.Len());
	}

	// Detect protocol on first message if not already detected
	if (!bProtocolDetected)
	{
		DetectProtocol(Message);
	}

	// Parse the message
	FArchLiveSyncMessage ParsedMessage = ParseMessage(Message);

	// Fire generic message event
	OnMessageReceived.Broadcast(ParsedMessage);

	// Handle based on message type
	switch (ParsedMessage.Type)
	{
	case EArchLiveSyncMessageType::BuildingData:
	case EArchLiveSyncMessageType::BuildingDelta:
		ProcessBuildingData(ParsedMessage.Payload);
		break;

	case EArchLiveSyncMessageType::HeartbeatAck:
		LastHeartbeatReceivedTime = FPlatformTime::Seconds();
		if (ParsedMessage.Timestamp > 0)
		{
			UpdateHeartbeatLatency((double)ParsedMessage.Timestamp / 1000.0);
		}
		else
		{
			UpdateHeartbeatLatency(LastHeartbeatSentTime);
		}
		OnHeartbeatReceived.Broadcast();
		break;

	case EArchLiveSyncMessageType::Heartbeat:
		// Server sent heartbeat, respond with ack
		LastHeartbeatReceivedTime = FPlatformTime::Seconds();
		SendTypedMessage(EArchLiveSyncMessageType::HeartbeatAck, TEXT("{}"), 10);
		OnHeartbeatReceived.Broadcast();
		break;

	case EArchLiveSyncMessageType::SelectionChanged:
		HandleStructuredMessage(ParsedMessage);
		break;

	case EArchLiveSyncMessageType::Error:
		OnError.Broadcast(ParsedMessage.Payload);
		break;

	default:
		// For legacy protocol or unknown types, try to process as building data
		if (DetectedProtocol == EArchLiveSyncProtocol::Legacy)
		{
			ProcessBuildingData(Message);
		}
		break;
	}
}

// ============= MESSAGE HANDLING =============

bool UArchLiveSyncComponent::DetectProtocol(const FString& Message)
{
	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);

	if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
	{
		// V1 protocol has "type" field at root
		if (JsonObject->HasField(TEXT("type")))
		{
			FString TypeStr = JsonObject->GetStringField(TEXT("type"));
			// V1 type strings: "building_data", "heartbeat", "selection", etc.
			if (TypeStr.StartsWith(TEXT("building")) ||
				TypeStr == TEXT("heartbeat") ||
				TypeStr == TEXT("selection") ||
				TypeStr == TEXT("error"))
			{
				DetectedProtocol = EArchLiveSyncProtocol::V1;
				bProtocolDetected = true;
				Diagnostics.DetectedProtocol = DetectedProtocol;
				UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Detected V1 structured protocol"));
				return true;
			}
		}

		// Legacy protocol: raw building JSON with walls/levels/elements
		if (JsonObject->HasField(TEXT("walls_batch")) ||
			JsonObject->HasField(TEXT("levels")) ||
			JsonObject->HasField(TEXT("elements")) ||
			JsonObject->HasField(TEXT("walls")))
		{
			DetectedProtocol = EArchLiveSyncProtocol::Legacy;
			bProtocolDetected = true;
			Diagnostics.DetectedProtocol = DetectedProtocol;
			UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Detected Legacy raw JSON protocol"));
			return true;
		}
	}

	// Default to legacy
	DetectedProtocol = EArchLiveSyncProtocol::Legacy;
	bProtocolDetected = true;
	Diagnostics.DetectedProtocol = DetectedProtocol;
	return false;
}

FArchLiveSyncMessage UArchLiveSyncComponent::ParseMessage(const FString& RawMessage)
{
	FArchLiveSyncMessage Result;

	TSharedPtr<FJsonObject> JsonObject;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(RawMessage);

	if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
	{
		Result.Type = EArchLiveSyncMessageType::Unknown;
		Result.Payload = RawMessage;
		return Result;
	}

	if (DetectedProtocol == EArchLiveSyncProtocol::V1)
	{
		// Parse V1 envelope
		FString TypeStr = JsonObject->GetStringField(TEXT("type"));

		if (TypeStr == TEXT("building_data"))
		{
			Result.Type = EArchLiveSyncMessageType::BuildingData;
		}
		else if (TypeStr == TEXT("building_delta"))
		{
			Result.Type = EArchLiveSyncMessageType::BuildingDelta;
		}
		else if (TypeStr == TEXT("heartbeat"))
		{
			Result.Type = EArchLiveSyncMessageType::Heartbeat;
		}
		else if (TypeStr == TEXT("heartbeat_ack") || TypeStr == TEXT("pong"))
		{
			Result.Type = EArchLiveSyncMessageType::HeartbeatAck;
		}
		else if (TypeStr == TEXT("selection"))
		{
			Result.Type = EArchLiveSyncMessageType::SelectionChanged;
		}
		else if (TypeStr == TEXT("view"))
		{
			Result.Type = EArchLiveSyncMessageType::ViewChanged;
		}
		else if (TypeStr == TEXT("error"))
		{
			Result.Type = EArchLiveSyncMessageType::Error;
		}
		else if (TypeStr == TEXT("status"))
		{
			Result.Type = EArchLiveSyncMessageType::Status;
		}
		else
		{
			Result.Type = EArchLiveSyncMessageType::Unknown;
		}

		// Extract payload
		const TSharedPtr<FJsonObject>* PayloadObj;
		if (JsonObject->TryGetObjectField(TEXT("payload"), PayloadObj))
		{
			TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Result.Payload);
			FJsonSerializer::Serialize(PayloadObj->ToSharedRef(), Writer);
		}
		else
		{
			Result.Payload = RawMessage;
		}

		// Extract timestamp
		if (JsonObject->HasField(TEXT("timestamp")))
		{
			Result.Timestamp = (int64)JsonObject->GetNumberField(TEXT("timestamp"));
		}

		// Extract message ID
		if (JsonObject->HasField(TEXT("id")))
		{
			Result.MessageId = JsonObject->GetStringField(TEXT("id"));
		}

		// Check for full sync flag
		if (JsonObject->HasField(TEXT("full_sync")))
		{
			Result.bIsFullSync = JsonObject->GetBoolField(TEXT("full_sync"));
		}
	}
	else
	{
		// Legacy protocol - entire message is building data
		Result.Type = EArchLiveSyncMessageType::BuildingData;
		Result.Payload = RawMessage;
		Result.bIsFullSync = true;
	}

	return Result;
}

void UArchLiveSyncComponent::ProcessBuildingData(const FString& JsonData)
{
	Diagnostics.BuildingUpdatesReceived++;

	// Fire legacy event for backwards compatibility
	OnBuildingDataReceived.Broadcast(JsonData);

	// Update building actor if enabled
	if (bAutoUpdateBuilding && BuildingActor)
	{
		BuildingActor->LoadFromJsonString(JsonData);
		UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Building updated from 2D editor"));
	}
}

void UArchLiveSyncComponent::HandleStructuredMessage(const FArchLiveSyncMessage& Message)
{
	if (Message.Type == EArchLiveSyncMessageType::SelectionChanged)
	{
		FArchLiveSyncSelection Selection;

		TSharedPtr<FJsonObject> JsonObject;
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message.Payload);

		if (FJsonSerializer::Deserialize(Reader, JsonObject) && JsonObject.IsValid())
		{
			const TArray<TSharedPtr<FJsonValue>>* IdsArray;
			if (JsonObject->TryGetArrayField(TEXT("selected_ids"), IdsArray))
			{
				for (const auto& IdValue : *IdsArray)
				{
					Selection.SelectedElementIds.Add(IdValue->AsString());
				}
			}

			if (JsonObject->HasField(TEXT("source")))
			{
				Selection.SelectionSource = JsonObject->GetStringField(TEXT("source"));
			}
		}

		OnSelectionChanged.Broadcast(Selection);
	}
}

// ============= MESSAGE SENDING =============

void UArchLiveSyncComponent::SendMessage(const FString& Message)
{
	if (WebSocket.IsValid() && ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		WebSocket->Send(Message);
		Diagnostics.MessagesSent++;
		Diagnostics.BytesSent += Message.Len();
	}
	else
	{
		// Queue for later if important
		FArchLiveSyncOutgoingMessage OutMsg;
		OutMsg.Type = EArchLiveSyncMessageType::Unknown;
		OutMsg.Payload = Message;
		OutMsg.Priority = 0;
		EnqueueMessage(OutMsg);
	}
}

void UArchLiveSyncComponent::SendTypedMessage(EArchLiveSyncMessageType Type, const FString& Payload, int32 Priority)
{
	FArchLiveSyncOutgoingMessage OutMsg;
	OutMsg.Type = Type;
	OutMsg.Payload = Payload;
	OutMsg.Priority = Priority;
	OutMsg.bRequiresConnection = true;

	if (ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		FString Serialized = SerializeOutgoingMessage(OutMsg);
		if (WebSocket.IsValid())
		{
			WebSocket->Send(Serialized);
			Diagnostics.MessagesSent++;
			Diagnostics.BytesSent += Serialized.Len();
		}
	}
	else
	{
		EnqueueMessage(OutMsg);
	}
}

void UArchLiveSyncComponent::SendSelectionChanged(const TArray<FString>& SelectedIds)
{
	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

	TArray<TSharedPtr<FJsonValue>> IdsArray;
	for (const FString& Id : SelectedIds)
	{
		IdsArray.Add(MakeShareable(new FJsonValueString(Id)));
	}
	JsonObject->SetArrayField(TEXT("selected_ids"), IdsArray);
	JsonObject->SetStringField(TEXT("source"), TEXT("viewer"));

	FString Payload;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

	SendTypedMessage(EArchLiveSyncMessageType::SelectionChanged, Payload, 5);
}

void UArchLiveSyncComponent::SendViewChanged(FVector Location, FRotator Rotation)
{
	TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

	TSharedPtr<FJsonObject> LocationObj = MakeShareable(new FJsonObject);
	LocationObj->SetNumberField(TEXT("x"), Location.X);
	LocationObj->SetNumberField(TEXT("y"), Location.Y);
	LocationObj->SetNumberField(TEXT("z"), Location.Z);
	JsonObject->SetObjectField(TEXT("location"), LocationObj);

	TSharedPtr<FJsonObject> RotationObj = MakeShareable(new FJsonObject);
	RotationObj->SetNumberField(TEXT("pitch"), Rotation.Pitch);
	RotationObj->SetNumberField(TEXT("yaw"), Rotation.Yaw);
	RotationObj->SetNumberField(TEXT("roll"), Rotation.Roll);
	JsonObject->SetObjectField(TEXT("rotation"), RotationObj);

	FString Payload;
	TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
	FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

	SendTypedMessage(EArchLiveSyncMessageType::ViewChanged, Payload, 1);
}

// ============= HEARTBEAT =============

void UArchLiveSyncComponent::SendHeartbeat()
{
	TimeSinceLastHeartbeat = 0.0f;
	LastHeartbeatSentTime = FPlatformTime::Seconds();

	// For legacy protocol, send a simple ping that server will ignore
	// For V1 protocol, send proper heartbeat message
	if (DetectedProtocol == EArchLiveSyncProtocol::V1)
	{
		TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);
		JsonObject->SetNumberField(TEXT("timestamp"), LastHeartbeatSentTime * 1000.0);

		FString Payload;
		TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Payload);
		FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

		// Send directly, do not queue heartbeats
		if (WebSocket.IsValid() && ConnectionState == EArchLiveSyncConnectionState::Connected)
		{
			FString HeartbeatMsg = FString::Printf(TEXT("{\"type\":\"heartbeat\",\"payload\":%s}"), *Payload);
			WebSocket->Send(HeartbeatMsg);
			Diagnostics.MessagesSent++;
			Diagnostics.BytesSent += HeartbeatMsg.Len();
		}
	}
	else
	{
		// Legacy: send simple ping
		if (WebSocket.IsValid() && ConnectionState == EArchLiveSyncConnectionState::Connected)
		{
			FString PingMsg = TEXT("{\"type\":\"ping\"}");
			WebSocket->Send(PingMsg);
			Diagnostics.MessagesSent++;
			Diagnostics.BytesSent += PingMsg.Len();
			// For legacy, we do not expect a response, so mark heartbeat as received
			LastHeartbeatReceivedTime = FPlatformTime::Seconds();
		}
	}
}

void UArchLiveSyncComponent::OnHeartbeatTimeout()
{
	UE_LOG(LogTemp, Warning, TEXT("ArchLiveSync: Heartbeat timeout, connection may be stale"));

	Diagnostics.LastError = TEXT("Heartbeat timeout");
	OnError.Broadcast(Diagnostics.LastError);

	// Force reconnect
	if (WebSocket.IsValid())
	{
		WebSocket->Close();
	}
}

void UArchLiveSyncComponent::UpdateHeartbeatLatency(double SentTime)
{
	double Now = FPlatformTime::Seconds();
	float LatencyMs = (float)((Now - SentTime) * 1000.0);

	Diagnostics.LastHeartbeatLatencyMs = LatencyMs;

	// Track recent latencies for averaging
	RecentLatencies.Add(LatencyMs);
	if (RecentLatencies.Num() > 10)
	{
		RecentLatencies.RemoveAt(0);
	}

	// Calculate average
	float Sum = 0.0f;
	for (float L : RecentLatencies)
	{
		Sum += L;
	}
	Diagnostics.AverageLatencyMs = Sum / RecentLatencies.Num();
}

// ============= QUEUE MANAGEMENT =============

void UArchLiveSyncComponent::EnqueueMessage(const FArchLiveSyncOutgoingMessage& Message)
{
	FScopeLock Lock(&QueueLock);

	// Check queue size limit
	if (OutgoingQueue.Num() >= MaxQueueSize)
	{
		// Remove lowest priority message
		int32 LowestPriorityIdx = 0;
		int32 LowestPriority = OutgoingQueue[0].Priority;
		for (int32 i = 1; i < OutgoingQueue.Num(); i++)
		{
			if (OutgoingQueue[i].Priority < LowestPriority)
			{
				LowestPriority = OutgoingQueue[i].Priority;
				LowestPriorityIdx = i;
			}
		}
		OutgoingQueue.RemoveAt(LowestPriorityIdx);
		Diagnostics.DroppedMessages++;
	}

	FArchLiveSyncOutgoingMessage NewMsg = Message;
	NewMsg.QueuedAtTime = FPlatformTime::Seconds();
	OutgoingQueue.Add(NewMsg);
	Diagnostics.OutgoingQueueSize = OutgoingQueue.Num();
}

void UArchLiveSyncComponent::ProcessOutgoingQueue()
{
	FScopeLock Lock(&QueueLock);

	if (OutgoingQueue.Num() == 0 || !WebSocket.IsValid())
	{
		return;
	}

	// Sort by priority (highest first)
	OutgoingQueue.Sort([](const FArchLiveSyncOutgoingMessage& A, const FArchLiveSyncOutgoingMessage& B)
	{
		return A.Priority > B.Priority;
	});

	// Process up to 5 messages per tick to avoid blocking
	int32 ProcessCount = FMath::Min(5, OutgoingQueue.Num());
	for (int32 i = 0; i < ProcessCount; i++)
	{
		FArchLiveSyncOutgoingMessage& Msg = OutgoingQueue[i];
		FString Serialized = SerializeOutgoingMessage(Msg);
		WebSocket->Send(Serialized);
		Diagnostics.MessagesSent++;
		Diagnostics.BytesSent += Serialized.Len();
	}

	// Remove processed messages
	OutgoingQueue.RemoveAt(0, ProcessCount);
	Diagnostics.OutgoingQueueSize = OutgoingQueue.Num();
}

void UArchLiveSyncComponent::PruneStaleQueuedMessages()
{
	if (MaxQueueAge <= 0.0f)
	{
		return;
	}

	FScopeLock Lock(&QueueLock);

	double Now = FPlatformTime::Seconds();
	int32 PrunedCount = 0;

	for (int32 i = OutgoingQueue.Num() - 1; i >= 0; i--)
	{
		double Age = Now - OutgoingQueue[i].QueuedAtTime;
		if (Age > MaxQueueAge)
		{
			OutgoingQueue.RemoveAt(i);
			PrunedCount++;
		}
	}

	if (PrunedCount > 0)
	{
		Diagnostics.DroppedMessages += PrunedCount;
		Diagnostics.OutgoingQueueSize = OutgoingQueue.Num();
		UE_LOG(LogTemp, Verbose, TEXT("ArchLiveSync: Pruned %d stale queued messages"), PrunedCount);
	}
}

FString UArchLiveSyncComponent::SerializeOutgoingMessage(const FArchLiveSyncOutgoingMessage& Message)
{
	// For legacy protocol, just send raw payload
	if (DetectedProtocol == EArchLiveSyncProtocol::Legacy)
	{
		return Message.Payload;
	}

	// V1 protocol: create envelope
	FString TypeStr;
	switch (Message.Type)
	{
	case EArchLiveSyncMessageType::BuildingData: TypeStr = TEXT("building_data"); break;
	case EArchLiveSyncMessageType::BuildingDelta: TypeStr = TEXT("building_delta"); break;
	case EArchLiveSyncMessageType::Heartbeat: TypeStr = TEXT("heartbeat"); break;
	case EArchLiveSyncMessageType::HeartbeatAck: TypeStr = TEXT("heartbeat_ack"); break;
	case EArchLiveSyncMessageType::SelectionChanged: TypeStr = TEXT("selection"); break;
	case EArchLiveSyncMessageType::ViewChanged: TypeStr = TEXT("view"); break;
	case EArchLiveSyncMessageType::Command: TypeStr = TEXT("command"); break;
	case EArchLiveSyncMessageType::Error: TypeStr = TEXT("error"); break;
	default: TypeStr = TEXT("unknown"); break;
	}

	return FString::Printf(TEXT("{\"type\":\"%s\",\"payload\":%s,\"timestamp\":%lld}"),
		*TypeStr,
		*Message.Payload,
		(int64)(FPlatformTime::Seconds() * 1000.0));
}

void UArchLiveSyncComponent::ClearOutgoingQueue()
{
	FScopeLock Lock(&QueueLock);
	OutgoingQueue.Empty();
	Diagnostics.OutgoingQueueSize = 0;
}

int32 UArchLiveSyncComponent::GetOutgoingQueueSize() const
{
	return OutgoingQueue.Num();
}

// ============= DIAGNOSTICS =============

FArchLiveSyncDiagnostics UArchLiveSyncComponent::GetDiagnostics() const
{
	return Diagnostics;
}

void UArchLiveSyncComponent::ResetDiagnostics()
{
	Diagnostics = FArchLiveSyncDiagnostics();
	Diagnostics.ConnectionState = ConnectionState;
	Diagnostics.DetectedProtocol = DetectedProtocol;
	RecentLatencies.Empty();
}

void UArchLiveSyncComponent::UpdateDiagnostics(float DeltaTime)
{
	// Update uptime
	if (ConnectionState == EArchLiveSyncConnectionState::Connected)
	{
		Diagnostics.ConnectionUptime = (float)(FPlatformTime::Seconds() - ConnectionStartTime);
	}

	// Update time since last message
	if (LastMessageReceivedTime > 0.0)
	{
		Diagnostics.TimeSinceLastMessage = (float)(FPlatformTime::Seconds() - LastMessageReceivedTime);
	}

	// Update queue size
	Diagnostics.OutgoingQueueSize = OutgoingQueue.Num();
}
