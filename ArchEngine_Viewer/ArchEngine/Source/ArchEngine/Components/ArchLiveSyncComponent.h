// ArchLiveSyncComponent.h - WebSocket client for real-time sync with 2D editor

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "IWebSocket.h"
#include "ArchLiveSyncComponent.generated.h"

class AArchBuildingActor;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBuildingDataReceived, const FString&, JsonData);

UCLASS(ClassGroup=(ArchEngine), meta=(BlueprintSpawnableComponent))
class ARCHENGINE_API UArchLiveSyncComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UArchLiveSyncComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

    // Connect to the 2D editor's WebSocket server
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
    void Connect();

    // Disconnect from the server
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
    void Disconnect();

    // Check if connected
    UFUNCTION(BlueprintPure, Category = "ArchEngine|LiveSync")
    bool IsConnected() const;

    // Send a message to the editor (for bidirectional sync)
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|LiveSync")
    void SendMessage(const FString& Message);

    // WebSocket server URL
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync")
    FString ServerUrl = TEXT("ws://localhost:8765");

    // Auto-connect on play
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync")
    bool bAutoConnect = true;

    // Auto-reconnect on disconnect
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync")
    bool bAutoReconnect = true;

    // Reconnect interval in seconds
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|LiveSync")
    float ReconnectInterval = 2.0f;

    // Event fired when building data is received
    UPROPERTY(BlueprintAssignable, Category = "ArchEngine|LiveSync")
    FOnBuildingDataReceived OnBuildingDataReceived;

private:
    void OnConnected();
    void OnConnectionError(const FString& Error);
    void OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean);
    void OnMessage(const FString& Message);

    void AttemptReconnect();

    TSharedPtr<IWebSocket> WebSocket;
    bool bIsConnected = false;
    float TimeSinceLastReconnect = 0.0f;
    bool bWantsToConnect = false;

    // Reference to building actor
    UPROPERTY()
    AArchBuildingActor* BuildingActor = nullptr;
};
