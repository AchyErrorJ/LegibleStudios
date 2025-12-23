// ArchLiveSyncComponent.cpp - WebSocket client for real-time sync

#include "Components/ArchLiveSyncComponent.h"
#include "Actors/ArchBuildingActor.h"
#include "WebSocketsModule.h"

UArchLiveSyncComponent::UArchLiveSyncComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickInterval = 0.1f;  // 10 Hz tick
}

void UArchLiveSyncComponent::BeginPlay()
{
    Super::BeginPlay();

    // Find the ArchBuildingActor owner
    BuildingActor = Cast<AArchBuildingActor>(GetOwner());

    if (bAutoConnect)
    {
        Connect();
    }
}

void UArchLiveSyncComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Disconnect();
    Super::EndPlay(EndPlayReason);
}

void UArchLiveSyncComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    // Handle reconnection
    if (bAutoReconnect && bWantsToConnect && !bIsConnected)
    {
        TimeSinceLastReconnect += DeltaTime;
        if (TimeSinceLastReconnect >= ReconnectInterval)
        {
            AttemptReconnect();
        }
    }
}

void UArchLiveSyncComponent::Connect()
{
    if (bIsConnected || WebSocket.IsValid())
    {
        return;
    }

    bWantsToConnect = true;

    // Ensure WebSockets module is loaded
    FModuleManager::Get().LoadModuleChecked(TEXT("WebSockets"));

    // Create WebSocket
    WebSocket = FWebSocketsModule::Get().CreateWebSocket(ServerUrl, TEXT("ws"));

    // Bind events
    WebSocket->OnConnected().AddUObject(this, &UArchLiveSyncComponent::OnConnected);
    WebSocket->OnConnectionError().AddUObject(this, &UArchLiveSyncComponent::OnConnectionError);
    WebSocket->OnClosed().AddUObject(this, &UArchLiveSyncComponent::OnClosed);
    WebSocket->OnMessage().AddUObject(this, &UArchLiveSyncComponent::OnMessage);

    // Connect
    UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connecting to %s"), *ServerUrl);
    WebSocket->Connect();
}

void UArchLiveSyncComponent::Disconnect()
{
    bWantsToConnect = false;

    if (WebSocket.IsValid())
    {
        if (bIsConnected)
        {
            WebSocket->Close();
        }
        WebSocket.Reset();
    }
    bIsConnected = false;
}

bool UArchLiveSyncComponent::IsConnected() const
{
    return bIsConnected;
}

void UArchLiveSyncComponent::SendMessage(const FString& Message)
{
    if (WebSocket.IsValid() && bIsConnected)
    {
        WebSocket->Send(Message);
    }
}

void UArchLiveSyncComponent::OnConnected()
{
    bIsConnected = true;
    TimeSinceLastReconnect = 0.0f;
    UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connected to 2D editor"));
}

void UArchLiveSyncComponent::OnConnectionError(const FString& Error)
{
    UE_LOG(LogTemp, Warning, TEXT("ArchLiveSync: Connection error: %s"), *Error);
    bIsConnected = false;
}

void UArchLiveSyncComponent::OnClosed(int32 StatusCode, const FString& Reason, bool bWasClean)
{
    UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Connection closed (code %d): %s"), StatusCode, *Reason);
    bIsConnected = false;

    // Clean up socket for reconnection
    if (WebSocket.IsValid())
    {
        WebSocket.Reset();
    }
}

void UArchLiveSyncComponent::OnMessage(const FString& Message)
{
    UE_LOG(LogTemp, Verbose, TEXT("ArchLiveSync: Received message (%d bytes)"), Message.Len());

    // Fire event for Blueprint binding
    OnBuildingDataReceived.Broadcast(Message);

    // Update building actor directly
    if (BuildingActor)
    {
        // Parse and reload the building
        BuildingActor->LoadFromJsonString(Message);
        UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Building updated from 2D editor"));
    }
}

void UArchLiveSyncComponent::AttemptReconnect()
{
    TimeSinceLastReconnect = 0.0f;

    if (WebSocket.IsValid())
    {
        WebSocket.Reset();
    }

    UE_LOG(LogTemp, Log, TEXT("ArchLiveSync: Attempting reconnect..."));

    // Create new socket and connect
    WebSocket = FWebSocketsModule::Get().CreateWebSocket(ServerUrl, TEXT("ws"));

    WebSocket->OnConnected().AddUObject(this, &UArchLiveSyncComponent::OnConnected);
    WebSocket->OnConnectionError().AddUObject(this, &UArchLiveSyncComponent::OnConnectionError);
    WebSocket->OnClosed().AddUObject(this, &UArchLiveSyncComponent::OnClosed);
    WebSocket->OnMessage().AddUObject(this, &UArchLiveSyncComponent::OnMessage);

    WebSocket->Connect();
}
