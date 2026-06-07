// ArchLiveSyncComponent.h - Production-ready WebSocket client for real-time sync with 2D editor
// Supports heartbeat, message queuing, diagnostics, and backwards compatibility

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "IWebSocket.h"
#include "ArchLiveSyncTypes.h"
#include "ArchLiveSyncComponent.generated.h"

class AArchBuildingActor;

// ============= DELEGATE DECLARATIONS =============

// Legacy delegate (maintained for backwards compatibility)
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBuildingDataReceived, const FString&, JsonData);

// New structured delegates
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLiveSyncConnectionStateChanged, EArchLiveSyncConnectionState, NewState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLiveSyncMessageReceived, const FArchLiveSyncMessage&, Message);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLiveSyncSelectionChanged, const FArchLiveSyncSelection&, Selection);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLiveSyncError, const FString&, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnLiveSyncHeartbeatReceived);

// ============= COMPONENT CLASS =============

UCLASS(ClassGroup=(ArchEngine), meta=(BlueprintSpawnableComponent))
class ARCHENGINE_API UArchLiveSyncComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UArchLiveSyncComponent();

	// ============= LIFECYCLE =============
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
	                           FActorComponentTickFunction* ThisTickFunction) override;

	// ============= CONNECTION MANAGEMENT =============

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void Connect();

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void Disconnect();

	UFUNCTION(BlueprintPure, Category = "ArchEngine|LiveSync")
	bool IsConnected() const;

	UFUNCTION(BlueprintPure, Category = "ArchEngine|LiveSync")
	EArchLiveSyncConnectionState GetConnectionState() const;

	// ============= MESSAGE SENDING =============

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void SendMessage(const FString& Message);

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void SendTypedMessage(EArchLiveSyncMessageType Type, const FString& Payload, int32 Priority = 0);

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void SendSelectionChanged(const TArray<FString>& SelectedIds);

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void SendViewChanged(FVector Location, FRotator Rotation);

	// ============= DIAGNOSTICS =============

	UFUNCTION(BlueprintPure, Category = "ArchEngine|LiveSync|Diagnostics")
	FArchLiveSyncDiagnostics GetDiagnostics() const;

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync|Diagnostics")
	void ResetDiagnostics();

	// ============= QUEUE MANAGEMENT =============

	UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
	void ClearOutgoingQueue();

	UFUNCTION(BlueprintPure, Category = "ArchEngine|LiveSync")
	int32 GetOutgoingQueueSize() const;

	// ============= CONNECTION PROPERTIES =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Connection")
	FString ServerUrl = TEXT("ws://localhost:8765");

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Connection")
	bool bAutoConnect = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Connection")
	bool bAutoReconnect = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Connection",
	          meta = (ClampMin = "0.5", ClampMax = "30.0"))
	float ReconnectInterval = 2.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Connection",
	          meta = (ClampMin = "0", ClampMax = "100"))
	int32 MaxReconnectAttempts = 0;

	// ============= HEARTBEAT PROPERTIES =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Heartbeat")
	bool bEnableHeartbeat = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Heartbeat",
	          meta = (ClampMin = "1.0", ClampMax = "60.0"))
	float HeartbeatInterval = 5.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Heartbeat",
	          meta = (ClampMin = "2.0", ClampMax = "120.0"))
	float HeartbeatTimeout = 15.0f;

	// ============= QUEUE PROPERTIES =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Queue",
	          meta = (ClampMin = "10", ClampMax = "1000"))
	int32 MaxQueueSize = 100;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Queue",
	          meta = (ClampMin = "0", ClampMax = "300"))
	float MaxQueueAge = 60.0f;

	// ============= BEHAVIOR PROPERTIES =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Behavior")
	bool bAutoUpdateBuilding = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync|Behavior")
	bool bLogMessages = false;

	// ============= BLUEPRINT EVENTS =============

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnBuildingDataReceived OnBuildingDataReceived;

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnLiveSyncConnectionStateChanged OnConnectionStateChanged;

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnLiveSyncMessageReceived OnMessageReceived;

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnLiveSyncSelectionChanged OnSelectionChanged;

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnLiveSyncError OnError;

	UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync|Events")
	FOnLiveSyncHeartbeatReceived OnHeartbeatReceived;

private:
	// WebSocket callbacks
	void OnWebSocketConnected();
	void OnWebSocketConnectionError(const FString& Error);
	void OnWebSocketClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
	void OnWebSocketMessage(const FString& Message);

	// Connection management
	void AttemptReconnect();
	void SetConnectionState(EArchLiveSyncConnectionState NewState);
	void CreateWebSocket();
	void CleanupWebSocket();

	// Message handling
	FArchLiveSyncMessage ParseMessage(const FString& RawMessage);
	bool DetectProtocol(const FString& Message);
	void ProcessBuildingData(const FString& JsonData);
	void HandleStructuredMessage(const FArchLiveSyncMessage& Message);

	// Heartbeat
	void SendHeartbeat();
	void OnHeartbeatTimeout();
	void UpdateHeartbeatLatency(double SentTime);

	// Queue management
	void EnqueueMessage(const FArchLiveSyncOutgoingMessage& Message);
	void ProcessOutgoingQueue();
	void PruneStaleQueuedMessages();
	FString SerializeOutgoingMessage(const FArchLiveSyncOutgoingMessage& Message);

	// Diagnostics
	void UpdateDiagnostics(float DeltaTime);

	// Member variables
	TSharedPtr<IWebSocket> WebSocket;

	EArchLiveSyncConnectionState ConnectionState = EArchLiveSyncConnectionState::Disconnected;
	bool bWantsToConnect = false;
	float TimeSinceLastReconnect = 0.0f;
	int32 CurrentReconnectAttempts = 0;

	double LastHeartbeatSentTime = 0.0;
	double LastHeartbeatReceivedTime = 0.0;
	float TimeSinceLastHeartbeat = 0.0f;
	TArray<float> RecentLatencies;

	TArray<FArchLiveSyncOutgoingMessage> OutgoingQueue;
	FCriticalSection QueueLock;

	EArchLiveSyncProtocol DetectedProtocol = EArchLiveSyncProtocol::Legacy;
	bool bProtocolDetected = false;

	FArchLiveSyncDiagnostics Diagnostics;
	double ConnectionStartTime = 0.0;
	double LastMessageReceivedTime = 0.0;

	UPROPERTY()
	AArchBuildingActor* BuildingActor = nullptr;
};
