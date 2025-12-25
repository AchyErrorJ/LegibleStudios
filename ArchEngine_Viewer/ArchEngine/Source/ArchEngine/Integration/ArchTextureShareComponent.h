// ArchTextureShareComponent.h - D3D11 shared texture component for Qt integration
// Captures scene to a shared GPU texture accessible from external processes

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "ArchTextureShareTypes.h"
#include "Integration/ArchIPCServer.h"
#include "ArchTextureShareComponent.generated.h"

// Delegates
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnTextureSharingStarted);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnTextureSharingStopped);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnTextureSharingError, const FString&, ErrorMessage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnClientConnected, bool, bConnected);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnInputReceived, const FString&, InputType);

UCLASS(ClassGroup=(ArchEngine), meta=(BlueprintSpawnableComponent))
class ARCHENGINE_API UArchTextureShareComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UArchTextureShareComponent();
	virtual ~UArchTextureShareComponent();

	// ============= CONFIGURATION =============

	// Viewport configuration (resolution, upscaling)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Config")
	FArchViewportConfig ViewportConfig;

	// Unique name for this share (used for pipe and texture handle)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Config")
	FString ShareName = TEXT("ArchEngine_Viewport");

	// Auto-start sharing on BeginPlay
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Config")
	bool bAutoStart = true;

	// Capture every frame (vs on-demand)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Config")
	bool bContinuousCapture = true;

	// Target framerate for capture (0 = unlimited)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Config",
		meta = (ClampMin = "0", ClampMax = "144"))
	int32 TargetCaptureFramerate = 60;

	// ============= SCENE CAPTURE SETTINGS =============

	// Use main camera view (vs separate scene capture)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Capture")
	bool bCaptureMainView = true;

	// Scene capture source (if not using main view)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "TextureShare|Capture",
		meta = (EditCondition = "!bCaptureMainView"))
	TObjectPtr<USceneCaptureComponent2D> ExternalSceneCapture;

	// ============= CONTROL =============

	// Start texture sharing
	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	bool StartSharing();

	// Stop texture sharing
	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	void StopSharing();

	// Check if sharing is active
	UFUNCTION(BlueprintPure, Category = "TextureShare")
	bool IsSharing() const;

	// Capture a single frame (for on-demand mode)
	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	void CaptureFrame();

	// Change resolution at runtime
	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	bool SetResolution(EArchResolutionPreset Preset);

	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	bool SetCustomResolution(FIntPoint Resolution);

	// Change upscaling settings at runtime
	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	void SetRenderScale(EArchRenderScale Scale);

	UFUNCTION(BlueprintCallable, Category = "TextureShare")
	void SetUpscaleMethod(EArchUpscaleMethod Method);

	// ============= DIAGNOSTICS =============

	// Get current diagnostics
	UFUNCTION(BlueprintPure, Category = "TextureShare")
	FArchTextureShareDiagnostics GetDiagnostics() const;

	// Get current texture info
	UFUNCTION(BlueprintPure, Category = "TextureShare")
	FArchSharedTextureInfo GetTextureInfo() const;

	// ============= EVENTS =============

	UPROPERTY(BlueprintAssignable, Category = "TextureShare|Events")
	FOnTextureSharingStarted OnSharingStarted;

	UPROPERTY(BlueprintAssignable, Category = "TextureShare|Events")
	FOnTextureSharingStopped OnSharingStopped;

	UPROPERTY(BlueprintAssignable, Category = "TextureShare|Events")
	FOnTextureSharingError OnSharingError;

	UPROPERTY(BlueprintAssignable, Category = "TextureShare|Events")
	FOnClientConnected OnClientConnected;

	UPROPERTY(BlueprintAssignable, Category = "TextureShare|Events")
	FOnInputReceived OnInputReceived;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType,
		FActorComponentTickFunction* ThisTickFunction) override;

private:
	// ============= INTERNAL STATE =============

	// Current state
	EArchTextureShareState CurrentState = EArchTextureShareState::Stopped;

	// Render target for scene capture
	UPROPERTY()
	TObjectPtr<UTextureRenderTarget2D> RenderTarget;

	// Internal scene capture (if not using external)
	UPROPERTY()
	TObjectPtr<USceneCaptureComponent2D> InternalSceneCapture;

	// IPC server for Qt communication
	TUniquePtr<FArchIPCServer> IPCServer;

	// D3D11 resources (Windows only)
	void* D3D11Device = nullptr;           // ID3D11Device*
	void* D3D11Context = nullptr;          // ID3D11DeviceContext*
	void* SharedTexture = nullptr;         // ID3D11Texture2D*
	void* SharedTextureHandle = nullptr;   // HANDLE
	void* KeyedMutex = nullptr;            // IDXGIKeyedMutex*

	// Frame timing
	double LastCaptureTime = 0.0;
	double MinCaptureInterval = 0.0;
	uint64 FrameNumber = 0;

	// Diagnostics
	FArchTextureShareDiagnostics Diagnostics;
	double CopyStartTime = 0.0;

	// ============= INTERNAL METHODS =============

	// Setup methods
	bool InitializeD3D11();
	void ShutdownD3D11();
	bool CreateSharedTexture();
	void DestroySharedTexture();
	bool CreateRenderTarget();
	void DestroyRenderTarget();
	bool SetupSceneCapture();
	void TeardownSceneCapture();

	// Runtime methods
	void CopyToSharedTexture();
	void UpdateDiagnostics(float DeltaTime);
	void ApplyUpscalingSettings();

	// IPC handlers
	void HandleClientConnected(bool bConnected);
	void HandleMouseMove(const FArchInputMouseMove& Input);
	void HandleMouseButton(const FArchInputMouseButton& Input);
	void HandleMouseWheel(const FArchInputMouseWheel& Input);
	void HandleKeyboard(const FArchInputKeyboard& Input);
	void HandleSelectionChanged(const TArray<FString>& SelectedIds);

	// Error handling
	void SetError(const FString& ErrorMessage);
};
