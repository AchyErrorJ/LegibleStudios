// ArchTextureShareComponent.cpp - D3D11 shared texture implementation

#include "Integration/ArchTextureShareComponent.h"
#include "Integration/ArchIPCServer.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Components/SceneCaptureComponent2D.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "Kismet/GameplayStatics.h"
#include "RHI.h"
#include "RHIResources.h"
#include "DynamicRHI.h"

#if PLATFORM_WINDOWS
#include "Windows/AllowWindowsPlatformTypes.h"
#include <d3d11.h>
#include <dxgi1_2.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

UArchTextureShareComponent::UArchTextureShareComponent()
{
	PrimaryComponentTick.bCanEverTick = true;
	PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}

UArchTextureShareComponent::~UArchTextureShareComponent()
{
	StopSharing();
}

void UArchTextureShareComponent::BeginPlay()
{
	Super::BeginPlay();

	// Calculate min capture interval
	if (TargetCaptureFramerate > 0)
	{
		MinCaptureInterval = 1.0 / TargetCaptureFramerate;
	}

	if (bAutoStart)
	{
		StartSharing();
	}
}

void UArchTextureShareComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	StopSharing();
	Super::EndPlay(EndPlayReason);
}

void UArchTextureShareComponent::TickComponent(float DeltaTime, ELevelTick TickType,
	FActorComponentTickFunction* ThisTickFunction)
{
	Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

	if (CurrentState != EArchTextureShareState::Running)
	{
		return;
	}

	// Check frame timing
	if (bContinuousCapture && MinCaptureInterval > 0.0)
	{
		double CurrentTime = FPlatformTime::Seconds();
		if (CurrentTime - LastCaptureTime < MinCaptureInterval)
		{
			return;
		}
		LastCaptureTime = CurrentTime;
	}

	// Capture and copy
	if (bContinuousCapture)
	{
		CaptureFrame();
	}

	UpdateDiagnostics(DeltaTime);
}

bool UArchTextureShareComponent::StartSharing()
{
	if (CurrentState == EArchTextureShareState::Running)
	{
		UE_LOG(LogTemp, Warning, TEXT("ArchTextureShare: Already running"));
		return true;
	}

	CurrentState = EArchTextureShareState::Starting;
	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Starting with %dx%d output, %dx%d render"),
		ViewportConfig.GetOutputResolution().X, ViewportConfig.GetOutputResolution().Y,
		ViewportConfig.GetRenderResolution().X, ViewportConfig.GetRenderResolution().Y);

#if PLATFORM_WINDOWS
	// Initialize D3D11
	if (!InitializeD3D11())
	{
		SetError(TEXT("Failed to initialize D3D11"));
		return false;
	}

	// Create render target
	if (!CreateRenderTarget())
	{
		SetError(TEXT("Failed to create render target"));
		ShutdownD3D11();
		return false;
	}

	// Create shared texture
	if (!CreateSharedTexture())
	{
		SetError(TEXT("Failed to create shared texture"));
		DestroyRenderTarget();
		ShutdownD3D11();
		return false;
	}

	// Setup scene capture
	if (!SetupSceneCapture())
	{
		SetError(TEXT("Failed to setup scene capture"));
		DestroySharedTexture();
		DestroyRenderTarget();
		ShutdownD3D11();
		return false;
	}

	// Create IPC server
	IPCServer = MakeUnique<FArchIPCServer>();
	IPCServer->OnClientConnected.BindUObject(this, &UArchTextureShareComponent::HandleClientConnected);
	IPCServer->OnMouseMove.BindUObject(this, &UArchTextureShareComponent::HandleMouseMove);
	IPCServer->OnMouseButton.BindUObject(this, &UArchTextureShareComponent::HandleMouseButton);
	IPCServer->OnMouseWheel.BindUObject(this, &UArchTextureShareComponent::HandleMouseWheel);
	IPCServer->OnKeyboard.BindUObject(this, &UArchTextureShareComponent::HandleKeyboard);
	IPCServer->OnSelectionChanged.BindUObject(this, &UArchTextureShareComponent::HandleSelectionChanged);

	if (!IPCServer->Start(ShareName))
	{
		SetError(TEXT("Failed to start IPC server"));
		DestroySharedTexture();
		DestroyRenderTarget();
		ShutdownD3D11();
		return false;
	}

	// Apply upscaling settings
	ApplyUpscalingSettings();

	CurrentState = EArchTextureShareState::Running;
	FrameNumber = 0;
	LastCaptureTime = FPlatformTime::Seconds();

	// Update diagnostics
	Diagnostics.State = CurrentState;
	Diagnostics.OutputResolution = ViewportConfig.GetOutputResolution();
	Diagnostics.RenderResolution = ViewportConfig.GetRenderResolution();
	Diagnostics.SharedTextureMemoryBytes = ViewportConfig.GetSharedTextureMemoryBytes();

	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Started successfully"));
	OnSharingStarted.Broadcast();
	return true;

#else
	SetError(TEXT("Texture sharing only supported on Windows"));
	return false;
#endif
}

void UArchTextureShareComponent::StopSharing()
{
	if (CurrentState == EArchTextureShareState::Stopped)
	{
		return;
	}

	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Stopping"));

	// Notify client
	if (IPCServer && IPCServer->IsClientConnected())
	{
		IPCServer->SendTextureDestroyed();
	}

	// Stop IPC
	if (IPCServer)
	{
		IPCServer->Stop();
		IPCServer.Reset();
	}

	// Cleanup
	TeardownSceneCapture();
	DestroySharedTexture();
	DestroyRenderTarget();
	ShutdownD3D11();

	CurrentState = EArchTextureShareState::Stopped;
	Diagnostics.State = CurrentState;

	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Stopped"));
	OnSharingStopped.Broadcast();
}

bool UArchTextureShareComponent::IsSharing() const
{
	return CurrentState == EArchTextureShareState::Running;
}

void UArchTextureShareComponent::CaptureFrame()
{
	if (CurrentState != EArchTextureShareState::Running)
	{
		return;
	}

#if PLATFORM_WINDOWS
	CopyStartTime = FPlatformTime::Seconds();

	// The scene capture automatically renders to RenderTarget
	// We just need to copy to shared texture
	CopyToSharedTexture();

	FrameNumber++;

	// Notify client of new frame
	if (IPCServer && IPCServer->IsClientConnected())
	{
		IPCServer->SendFrameReady(FrameNumber);
	}

	// Update timing
	double CopyEndTime = FPlatformTime::Seconds();
	Diagnostics.CopyTimeMs = static_cast<float>((CopyEndTime - CopyStartTime) * 1000.0);
	Diagnostics.FramesCopied = FrameNumber;
#endif
}

bool UArchTextureShareComponent::SetResolution(EArchResolutionPreset Preset)
{
	ViewportConfig.ResolutionPreset = Preset;

	if (CurrentState == EArchTextureShareState::Running)
	{
		// Need to recreate texture
		StopSharing();
		return StartSharing();
	}

	return true;
}

bool UArchTextureShareComponent::SetCustomResolution(FIntPoint Resolution)
{
	ViewportConfig.ResolutionPreset = EArchResolutionPreset::Custom;
	ViewportConfig.CustomResolution = Resolution;

	if (CurrentState == EArchTextureShareState::Running)
	{
		StopSharing();
		return StartSharing();
	}

	return true;
}

void UArchTextureShareComponent::SetRenderScale(EArchRenderScale Scale)
{
	ViewportConfig.RenderScale = Scale;

	if (CurrentState == EArchTextureShareState::Running)
	{
		ApplyUpscalingSettings();
		Diagnostics.RenderResolution = ViewportConfig.GetRenderResolution();
	}
}

void UArchTextureShareComponent::SetUpscaleMethod(EArchUpscaleMethod Method)
{
	ViewportConfig.UpscaleMethod = Method;

	if (CurrentState == EArchTextureShareState::Running)
	{
		ApplyUpscalingSettings();
	}
}

FArchTextureShareDiagnostics UArchTextureShareComponent::GetDiagnostics() const
{
	return Diagnostics;
}

FArchSharedTextureInfo UArchTextureShareComponent::GetTextureInfo() const
{
	FArchSharedTextureInfo Info;
	Info.HandleName = ShareName;
	Info.Width = ViewportConfig.GetOutputResolution().X;
	Info.Height = ViewportConfig.GetOutputResolution().Y;
	Info.Format = 28; // DXGI_FORMAT_R8G8B8A8_UNORM
	Info.FrameNumber = FrameNumber;
	Info.Timestamp = FPlatformTime::Seconds();
	return Info;
}

// ============= D3D11 IMPLEMENTATION =============

bool UArchTextureShareComponent::InitializeD3D11()
{
#if PLATFORM_WINDOWS
	// Get D3D11 device from RHI
	if (GDynamicRHI)
	{
		D3D11Device = GDynamicRHI->RHIGetNativeDevice();
		if (D3D11Device)
		{
			ID3D11Device* Device = static_cast<ID3D11Device*>(D3D11Device);
			Device->GetImmediateContext(reinterpret_cast<ID3D11DeviceContext**>(&D3D11Context));

			if (D3D11Context)
			{
				UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: D3D11 initialized"));
				return true;
			}
		}
	}

	UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to get D3D11 device from RHI"));
	return false;
#else
	return false;
#endif
}

void UArchTextureShareComponent::ShutdownD3D11()
{
#if PLATFORM_WINDOWS
	if (D3D11Context)
	{
		// Don't release - we don't own it
		D3D11Context = nullptr;
	}
	D3D11Device = nullptr;
#endif
}

bool UArchTextureShareComponent::CreateSharedTexture()
{
#if PLATFORM_WINDOWS
	if (!D3D11Device)
	{
		return false;
	}

	ID3D11Device* Device = static_cast<ID3D11Device*>(D3D11Device);
	FIntPoint OutputRes = ViewportConfig.GetOutputResolution();

	// Create shared texture
	D3D11_TEXTURE2D_DESC Desc = {};
	Desc.Width = OutputRes.X;
	Desc.Height = OutputRes.Y;
	Desc.MipLevels = 1;
	Desc.ArraySize = 1;
	Desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
	Desc.SampleDesc.Count = 1;
	Desc.SampleDesc.Quality = 0;
	Desc.Usage = D3D11_USAGE_DEFAULT;
	Desc.BindFlags = D3D11_BIND_SHADER_RESOURCE | D3D11_BIND_RENDER_TARGET;
	Desc.CPUAccessFlags = 0;
	Desc.MiscFlags = D3D11_RESOURCE_MISC_SHARED_NTHANDLE | D3D11_RESOURCE_MISC_SHARED_KEYEDMUTEX;

	ID3D11Texture2D* Texture = nullptr;
	HRESULT hr = Device->CreateTexture2D(&Desc, nullptr, &Texture);
	if (FAILED(hr))
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to create shared texture, hr=0x%08X"), hr);
		return false;
	}

	SharedTexture = Texture;

	// Get keyed mutex
	hr = Texture->QueryInterface(__uuidof(IDXGIKeyedMutex), &KeyedMutex);
	if (FAILED(hr))
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to get keyed mutex, hr=0x%08X"), hr);
		Texture->Release();
		SharedTexture = nullptr;
		return false;
	}

	// Create shared handle
	IDXGIResource1* DXGIResource = nullptr;
	hr = Texture->QueryInterface(__uuidof(IDXGIResource1), reinterpret_cast<void**>(&DXGIResource));
	if (FAILED(hr))
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to get DXGI resource, hr=0x%08X"), hr);
		static_cast<IDXGIKeyedMutex*>(KeyedMutex)->Release();
		KeyedMutex = nullptr;
		Texture->Release();
		SharedTexture = nullptr;
		return false;
	}

	// Create named shared handle
	FString HandleName = FString::Printf(TEXT("Global\\%s_Texture"), *ShareName);
	hr = DXGIResource->CreateSharedHandle(
		nullptr,
		DXGI_SHARED_RESOURCE_READ,
		*HandleName,
		reinterpret_cast<HANDLE*>(&SharedTextureHandle)
	);
	DXGIResource->Release();

	if (FAILED(hr))
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to create shared handle, hr=0x%08X"), hr);
		static_cast<IDXGIKeyedMutex*>(KeyedMutex)->Release();
		KeyedMutex = nullptr;
		Texture->Release();
		SharedTexture = nullptr;
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Created shared texture %dx%d, handle='%s'"),
		OutputRes.X, OutputRes.Y, *HandleName);
	return true;
#else
	return false;
#endif
}

void UArchTextureShareComponent::DestroySharedTexture()
{
#if PLATFORM_WINDOWS
	if (SharedTextureHandle)
	{
		CloseHandle(static_cast<HANDLE>(SharedTextureHandle));
		SharedTextureHandle = nullptr;
	}

	if (KeyedMutex)
	{
		static_cast<IDXGIKeyedMutex*>(KeyedMutex)->Release();
		KeyedMutex = nullptr;
	}

	if (SharedTexture)
	{
		static_cast<ID3D11Texture2D*>(SharedTexture)->Release();
		SharedTexture = nullptr;
	}
#endif
}

bool UArchTextureShareComponent::CreateRenderTarget()
{
	FIntPoint RenderRes = ViewportConfig.GetRenderResolution();

	RenderTarget = NewObject<UTextureRenderTarget2D>(this);
	RenderTarget->InitCustomFormat(RenderRes.X, RenderRes.Y, PF_R8G8B8A8, false);
	RenderTarget->RenderTargetFormat = RTF_RGBA8;
	RenderTarget->bAutoGenerateMips = false;
	RenderTarget->ClearColor = FLinearColor::Black;
	RenderTarget->UpdateResourceImmediate(true);

	if (!RenderTarget->GetResource())
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: Failed to create render target resource"));
		return false;
	}

	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Created render target %dx%d"), RenderRes.X, RenderRes.Y);
	return true;
}

void UArchTextureShareComponent::DestroyRenderTarget()
{
	if (RenderTarget)
	{
		RenderTarget->ReleaseResource();
		RenderTarget = nullptr;
	}
}

bool UArchTextureShareComponent::SetupSceneCapture()
{
	if (bCaptureMainView)
	{
		// Create internal scene capture
		AActor* Owner = GetOwner();
		if (!Owner)
		{
			UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: No owner actor"));
			return false;
		}

		InternalSceneCapture = NewObject<USceneCaptureComponent2D>(Owner);
		InternalSceneCapture->RegisterComponent();
		InternalSceneCapture->AttachToComponent(Owner->GetRootComponent(),
			FAttachmentTransformRules::KeepRelativeTransform);

		InternalSceneCapture->TextureTarget = RenderTarget;
		InternalSceneCapture->CaptureSource = SCS_FinalColorLDR;
		InternalSceneCapture->bCaptureEveryFrame = bContinuousCapture;
		InternalSceneCapture->bCaptureOnMovement = false;
		InternalSceneCapture->bAlwaysPersistRenderingState = true;

		// Match player camera
		APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
		if (PC && PC->PlayerCameraManager)
		{
			InternalSceneCapture->SetWorldLocation(PC->PlayerCameraManager->GetCameraLocation());
			InternalSceneCapture->SetWorldRotation(PC->PlayerCameraManager->GetCameraRotation());
			InternalSceneCapture->FOVAngle = PC->PlayerCameraManager->GetFOVAngle();
		}

		UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Scene capture setup complete"));
	}
	else if (ExternalSceneCapture)
	{
		ExternalSceneCapture->TextureTarget = RenderTarget;
	}
	else
	{
		UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: No scene capture source"));
		return false;
	}

	return true;
}

void UArchTextureShareComponent::TeardownSceneCapture()
{
	if (InternalSceneCapture)
	{
		InternalSceneCapture->DestroyComponent();
		InternalSceneCapture = nullptr;
	}
}

void UArchTextureShareComponent::CopyToSharedTexture()
{
#if PLATFORM_WINDOWS
	if (!SharedTexture || !KeyedMutex || !RenderTarget || !D3D11Context)
	{
		return;
	}

	IDXGIKeyedMutex* Mutex = static_cast<IDXGIKeyedMutex*>(KeyedMutex);
	ID3D11DeviceContext* Context = static_cast<ID3D11DeviceContext*>(D3D11Context);
	ID3D11Texture2D* DstTexture = static_cast<ID3D11Texture2D*>(SharedTexture);

	// Acquire mutex (key 0 = producer)
	HRESULT hr = Mutex->AcquireSync(0, 16); // 16ms timeout
	if (hr == WAIT_TIMEOUT)
	{
		Diagnostics.FramesDropped++;
		return;
	}
	if (FAILED(hr))
	{
		UE_LOG(LogTemp, Warning, TEXT("ArchTextureShare: Failed to acquire mutex, hr=0x%08X"), hr);
		return;
	}

	// Get source texture from render target
	FTextureRenderTargetResource* RTResource = RenderTarget->GameThread_GetRenderTargetResource();
	if (RTResource)
	{
		FRHITexture2D* RHITexture = RTResource->GetRenderTargetTexture();
		if (RHITexture)
		{
			// Get native D3D11 texture
			void* NativeResource = RHITexture->GetNativeResource();
			if (NativeResource)
			{
				ID3D11Texture2D* SrcTexture = static_cast<ID3D11Texture2D*>(NativeResource);

				// Copy (handles resolution mismatch with stretch if needed)
				D3D11_TEXTURE2D_DESC SrcDesc, DstDesc;
				SrcTexture->GetDesc(&SrcDesc);
				DstTexture->GetDesc(&DstDesc);

				if (SrcDesc.Width == DstDesc.Width && SrcDesc.Height == DstDesc.Height)
				{
					// Direct copy
					Context->CopyResource(DstTexture, SrcTexture);
				}
				else
				{
					// Need to handle resolution mismatch
					// For now, copy what we can
					D3D11_BOX SrcBox = {};
					SrcBox.right = FMath::Min(SrcDesc.Width, DstDesc.Width);
					SrcBox.bottom = FMath::Min(SrcDesc.Height, DstDesc.Height);
					SrcBox.back = 1;
					Context->CopySubresourceRegion(DstTexture, 0, 0, 0, 0, SrcTexture, 0, &SrcBox);
				}
			}
		}
	}

	// Release mutex (key 1 = consumer can acquire)
	Mutex->ReleaseSync(1);
#endif
}

void UArchTextureShareComponent::UpdateDiagnostics(float DeltaTime)
{
	Diagnostics.FrameTimeMs = DeltaTime * 1000.0f;
	Diagnostics.CurrentFPS = 1.0f / DeltaTime;
	Diagnostics.bClientConnected = IPCServer ? IPCServer->IsClientConnected() : false;
	Diagnostics.MessagesReceived = IPCServer ? IPCServer->GetMessagesReceived() : 0;
	Diagnostics.MessagesSent = IPCServer ? IPCServer->GetMessagesSent() : 0;
}

void UArchTextureShareComponent::ApplyUpscalingSettings()
{
	// Apply TSR/DLSS/FSR settings via console commands
	switch (ViewportConfig.UpscaleMethod)
	{
		case EArchUpscaleMethod::TSR:
		{
			float Scale = ViewportConfig.GetRenderScaleMultiplier();
			GEngine->Exec(GetWorld(), *FString::Printf(TEXT("r.ScreenPercentage %d"),
				FMath::RoundToInt(Scale * 100.0f)));
			GEngine->Exec(GetWorld(), TEXT("r.AntiAliasingMethod 4")); // TSR
			break;
		}
		case EArchUpscaleMethod::DLSS:
		{
			// DLSS requires plugin - set mode
			GEngine->Exec(GetWorld(), TEXT("r.NGX.DLSS.Enable 1"));
			break;
		}
		case EArchUpscaleMethod::FSR:
		{
			GEngine->Exec(GetWorld(), TEXT("r.FidelityFX.FSR2.Enabled 1"));
			break;
		}
		default:
		{
			GEngine->Exec(GetWorld(), TEXT("r.ScreenPercentage 100"));
			break;
		}
	}
}

void UArchTextureShareComponent::SetError(const FString& ErrorMessage)
{
	CurrentState = EArchTextureShareState::Error;
	Diagnostics.State = CurrentState;
	Diagnostics.LastError = ErrorMessage;
	UE_LOG(LogTemp, Error, TEXT("ArchTextureShare: %s"), *ErrorMessage);
	OnSharingError.Broadcast(ErrorMessage);
}

// ============= IPC HANDLERS =============

void UArchTextureShareComponent::HandleClientConnected(bool bConnected)
{
	UE_LOG(LogTemp, Log, TEXT("ArchTextureShare: Client %s"), bConnected ? TEXT("connected") : TEXT("disconnected"));
	OnClientConnected.Broadcast(bConnected);

	if (bConnected && IPCServer)
	{
		// Send texture info to client
		IPCServer->SendTextureReady(GetTextureInfo());
	}
}

void UArchTextureShareComponent::HandleMouseMove(const FArchInputMouseMove& Input)
{
	// Forward to input system
	OnInputReceived.Broadcast(TEXT("MouseMove"));

	// TODO: Inject into Slate/viewport
}

void UArchTextureShareComponent::HandleMouseButton(const FArchInputMouseButton& Input)
{
	OnInputReceived.Broadcast(Input.bPressed ? TEXT("MouseDown") : TEXT("MouseUp"));

	// TODO: Inject into Slate/viewport
}

void UArchTextureShareComponent::HandleMouseWheel(const FArchInputMouseWheel& Input)
{
	OnInputReceived.Broadcast(TEXT("MouseWheel"));

	// TODO: Inject into Slate/viewport
}

void UArchTextureShareComponent::HandleKeyboard(const FArchInputKeyboard& Input)
{
	OnInputReceived.Broadcast(Input.bPressed ? TEXT("KeyDown") : TEXT("KeyUp"));

	// TODO: Inject into Slate/viewport
}

void UArchTextureShareComponent::HandleSelectionChanged(const TArray<FString>& SelectedIds)
{
	UE_LOG(LogTemp, Verbose, TEXT("ArchTextureShare: Selection changed, %d items"), SelectedIds.Num());

	// TODO: Forward to selection manager
}
