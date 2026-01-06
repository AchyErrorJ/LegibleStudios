// ArchLiveSyncTypes.h - Types for LiveSync protocol
// Production-ready WebSocket communication layer types

#pragma once

#include "CoreMinimal.h"
#include "ArchLiveSyncTypes.generated.h"

// ============= CONNECTION STATE =============

UENUM(BlueprintType)
enum class EArchLiveSyncConnectionState : uint8
{
	Disconnected,       // Not connected
	Connecting,         // Connection in progress
	Connected,          // Connected and ready
	Reconnecting,       // Lost connection, attempting reconnect
	Error               // Connection failed with error
};

// ============= MESSAGE TYPES =============

UENUM(BlueprintType)
enum class EArchLiveSyncMessageType : uint8
{
	Unknown,            // Unknown/unrecognized message
	BuildingData,       // Full building JSON (current format)
	BuildingDelta,      // Incremental update (future)
	Heartbeat,          // Keep-alive ping
	HeartbeatAck,       // Heartbeat acknowledgment
	Status,             // Status/info message
	SelectionChanged,   // Selection sync
	ViewChanged,        // Camera/view sync
	Command,            // Editor command
	Error               // Error message
};

// ============= PROTOCOL VERSION =============

UENUM(BlueprintType)
enum class EArchLiveSyncProtocol : uint8
{
	Legacy,             // Raw JSON (current Python server)
	V1                  // Structured message envelope
};

// ============= PARSED MESSAGE =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLiveSyncMessage
{
	GENERATED_BODY()

	// Message type
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync")
	EArchLiveSyncMessageType Type = EArchLiveSyncMessageType::Unknown;

	// Raw JSON payload
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync")
	FString Payload;

	// Server timestamp if provided
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync")
	int64 Timestamp = 0;

	// Optional message ID for correlation
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync")
	FString MessageId;

	// For building data: full sync vs delta update
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync")
	bool bIsFullSync = true;
};

// ============= OUTGOING MESSAGE =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLiveSyncOutgoingMessage
{
	GENERATED_BODY()

	// Message type
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	EArchLiveSyncMessageType Type = EArchLiveSyncMessageType::Unknown;

	// JSON payload
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	FString Payload;

	// Priority (higher = more important)
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	int32 Priority = 0;

	// Queue if disconnected
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	bool bRequiresConnection = true;

	// Internal tracking (not exposed to Blueprint)
	double QueuedAtTime = 0.0;
	int32 RetryCount = 0;
};

// ============= DIAGNOSTICS =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLiveSyncDiagnostics
{
	GENERATED_BODY()

	// Connection stats
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	EArchLiveSyncConnectionState ConnectionState = EArchLiveSyncConnectionState::Disconnected;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	float ConnectionUptime = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 ReconnectAttempts = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	FString LastError;

	// Message stats
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 MessagesReceived = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 MessagesSent = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int64 BytesReceived = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int64 BytesSent = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 BuildingUpdatesReceived = 0;

	// Latency tracking
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	float LastHeartbeatLatencyMs = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	float AverageLatencyMs = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	float TimeSinceLastMessage = 0.0f;

	// Queue stats
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 OutgoingQueueSize = 0;

	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	int32 DroppedMessages = 0;

	// Protocol detection
	UPROPERTY(BlueprintReadOnly, Category = "LiveSync|Diagnostics")
	EArchLiveSyncProtocol DetectedProtocol = EArchLiveSyncProtocol::Legacy;
};

// ============= SELECTION SYNC =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLiveSyncSelection
{
	GENERATED_BODY()

	// Selected element IDs
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	TArray<FString> SelectedElementIds;

	// Source of selection ("editor" or "viewer")
	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	FString SelectionSource;
};

// ============= VIEW SYNC (FUTURE) =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLiveSyncView
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	FVector CameraLocation = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	FRotator CameraRotation = FRotator::ZeroRotator;

	UPROPERTY(BlueprintReadWrite, Category = "LiveSync")
	FString ActiveLevel;
};
