// ArchTextureShareTypes.h - Types for UE5-Qt texture sharing
// Supports up to 8K resolution with temporal upscaling

#pragma once

#include "CoreMinimal.h"
#include "ArchTextureShareTypes.generated.h"

// ============= RESOLUTION PRESETS =============

UENUM(BlueprintType)
enum class EArchResolutionPreset : uint8
{
	Custom       UMETA(DisplayName = "Custom"),
	HD_720p      UMETA(DisplayName = "720p (1280x720)"),
	FHD_1080p    UMETA(DisplayName = "1080p (1920x1080)"),
	QHD_1440p    UMETA(DisplayName = "1440p (2560x1440)"),
	UHD_4K       UMETA(DisplayName = "4K (3840x2160)"),
	UHD_5K       UMETA(DisplayName = "5K (5120x2880)"),
	UHD_6K       UMETA(DisplayName = "6K (6144x3456)"),
	UHD_8K       UMETA(DisplayName = "8K (7680x4320)")
};

// ============= RENDER SCALING =============

UENUM(BlueprintType)
enum class EArchRenderScale : uint8
{
	Native       UMETA(DisplayName = "Native (100%)"),
	Quality      UMETA(DisplayName = "Quality (67%)"),
	Balanced     UMETA(DisplayName = "Balanced (50%)"),
	Performance  UMETA(DisplayName = "Performance (33%)")
};

UENUM(BlueprintType)
enum class EArchUpscaleMethod : uint8
{
	None         UMETA(DisplayName = "None (Native)"),
	TSR          UMETA(DisplayName = "Temporal Super Resolution"),
	DLSS         UMETA(DisplayName = "NVIDIA DLSS"),
	FSR          UMETA(DisplayName = "AMD FSR 2"),
	XeSS         UMETA(DisplayName = "Intel XeSS")
};

// ============= SHARING STATE =============

UENUM(BlueprintType)
enum class EArchTextureShareState : uint8
{
	Stopped,
	Starting,
	Running,
	Error
};

// ============= IPC MESSAGE TYPES =============

UENUM(BlueprintType)
enum class EArchIPCMessageType : uint8
{
	// UE5 -> Qt
	TextureReady,           // Texture handle is available
	TextureResized,         // Resolution changed
	TextureDestroyed,       // Sharing stopped
	FrameReady,             // New frame available (with frame number)

	// Qt -> UE5
	InputMouseMove,
	InputMouseButton,
	InputMouseWheel,
	InputKeyboard,
	InputTouch,

	// Bidirectional
	SelectionChanged,       // Selection sync
	ViewChanged,            // Camera sync
	Command,                // Generic command
	Ping,                   // Keepalive
	Pong                    // Keepalive response
};

// ============= VIEWPORT CONFIGURATION =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchViewportConfig
{
	GENERATED_BODY()

	// Output resolution preset
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Resolution")
	EArchResolutionPreset ResolutionPreset = EArchResolutionPreset::UHD_4K;

	// Custom resolution (used when preset is Custom)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Resolution",
		meta = (EditCondition = "ResolutionPreset == EArchResolutionPreset::Custom"))
	FIntPoint CustomResolution = FIntPoint(3840, 2160);

	// Render scale for upscaling
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upscaling")
	EArchRenderScale RenderScale = EArchRenderScale::Quality;

	// Upscaling method
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upscaling")
	EArchUpscaleMethod UpscaleMethod = EArchUpscaleMethod::TSR;

	// Dynamic resolution (adjusts render scale based on GPU load)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upscaling")
	bool bEnableDynamicResolution = false;

	// Target framerate for dynamic resolution
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Upscaling",
		meta = (EditCondition = "bEnableDynamicResolution", ClampMin = "30", ClampMax = "144"))
	int32 TargetFramerate = 60;

	// Get the output resolution based on preset
	FIntPoint GetOutputResolution() const
	{
		switch (ResolutionPreset)
		{
			case EArchResolutionPreset::HD_720p:   return FIntPoint(1280, 720);
			case EArchResolutionPreset::FHD_1080p: return FIntPoint(1920, 1080);
			case EArchResolutionPreset::QHD_1440p: return FIntPoint(2560, 1440);
			case EArchResolutionPreset::UHD_4K:    return FIntPoint(3840, 2160);
			case EArchResolutionPreset::UHD_5K:    return FIntPoint(5120, 2880);
			case EArchResolutionPreset::UHD_6K:    return FIntPoint(6144, 3456);
			case EArchResolutionPreset::UHD_8K:    return FIntPoint(7680, 4320);
			case EArchResolutionPreset::Custom:
			default:
				return CustomResolution;
		}
	}

	// Get the render scale multiplier
	float GetRenderScaleMultiplier() const
	{
		switch (RenderScale)
		{
			case EArchRenderScale::Quality:     return 0.67f;
			case EArchRenderScale::Balanced:    return 0.50f;
			case EArchRenderScale::Performance: return 0.33f;
			case EArchRenderScale::Native:
			default:
				return 1.0f;
		}
	}

	// Get the internal render resolution (before upscaling)
	FIntPoint GetRenderResolution() const
	{
		if (UpscaleMethod == EArchUpscaleMethod::None)
		{
			return GetOutputResolution();
		}

		FIntPoint Output = GetOutputResolution();
		float Scale = GetRenderScaleMultiplier();
		return FIntPoint(
			FMath::RoundToInt(Output.X * Scale),
			FMath::RoundToInt(Output.Y * Scale)
		);
	}

	// Calculate memory usage for the shared texture
	int64 GetSharedTextureMemoryBytes() const
	{
		FIntPoint Output = GetOutputResolution();
		return static_cast<int64>(Output.X) * Output.Y * 4; // RGBA8
	}

	// Get human-readable memory string
	FString GetMemoryUsageString() const
	{
		int64 Bytes = GetSharedTextureMemoryBytes();
		if (Bytes >= 1024 * 1024)
		{
			return FString::Printf(TEXT("%.1f MB"), Bytes / (1024.0 * 1024.0));
		}
		return FString::Printf(TEXT("%.1f KB"), Bytes / 1024.0);
	}
};

// ============= TEXTURE INFO (IPC) =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchSharedTextureInfo
{
	GENERATED_BODY()

	// Shared handle name for cross-process access
	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	FString HandleName;

	// Output dimensions
	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	int32 Width = 0;

	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	int32 Height = 0;

	// DXGI format (DXGI_FORMAT_R8G8B8A8_UNORM = 28)
	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	int32 Format = 28;

	// Frame counter for sync
	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	int64 FrameNumber = 0;

	// Timestamp of last update
	UPROPERTY(BlueprintReadOnly, Category = "TextureShare")
	double Timestamp = 0.0;
};

// ============= INPUT MESSAGES (Qt -> UE5) =============

USTRUCT()
struct FArchInputMouseMove
{
	GENERATED_BODY()

	UPROPERTY()
	FVector2D Position = FVector2D::ZeroVector;

	UPROPERTY()
	FVector2D Delta = FVector2D::ZeroVector;
};

USTRUCT()
struct FArchInputMouseButton
{
	GENERATED_BODY()

	UPROPERTY()
	FVector2D Position = FVector2D::ZeroVector;

	UPROPERTY()
	uint8 Button = 0;  // 0=Left, 1=Right, 2=Middle

	UPROPERTY()
	bool bPressed = false;
};

USTRUCT()
struct FArchInputMouseWheel
{
	GENERATED_BODY()

	UPROPERTY()
	FVector2D Position = FVector2D::ZeroVector;

	UPROPERTY()
	float Delta = 0.0f;
};

USTRUCT()
struct FArchInputKeyboard
{
	GENERATED_BODY()

	UPROPERTY()
	int32 KeyCode = 0;

	UPROPERTY()
	bool bPressed = false;

	UPROPERTY()
	bool bShift = false;

	UPROPERTY()
	bool bCtrl = false;

	UPROPERTY()
	bool bAlt = false;
};

// ============= DIAGNOSTICS =============

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchTextureShareDiagnostics
{
	GENERATED_BODY()

	// State
	UPROPERTY(BlueprintReadOnly, Category = "State")
	EArchTextureShareState State = EArchTextureShareState::Stopped;

	// Resolution info
	UPROPERTY(BlueprintReadOnly, Category = "Resolution")
	FIntPoint OutputResolution = FIntPoint::ZeroValue;

	UPROPERTY(BlueprintReadOnly, Category = "Resolution")
	FIntPoint RenderResolution = FIntPoint::ZeroValue;

	// Performance
	UPROPERTY(BlueprintReadOnly, Category = "Performance")
	float CopyTimeMs = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Performance")
	float FrameTimeMs = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Performance")
	float CurrentFPS = 0.0f;

	// Frames
	UPROPERTY(BlueprintReadOnly, Category = "Frames")
	int64 FramesCopied = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Frames")
	int64 FramesDropped = 0;

	// Memory
	UPROPERTY(BlueprintReadOnly, Category = "Memory")
	int64 SharedTextureMemoryBytes = 0;

	// IPC
	UPROPERTY(BlueprintReadOnly, Category = "IPC")
	bool bClientConnected = false;

	UPROPERTY(BlueprintReadOnly, Category = "IPC")
	int32 MessagesReceived = 0;

	UPROPERTY(BlueprintReadOnly, Category = "IPC")
	int32 MessagesSent = 0;

	// Errors
	UPROPERTY(BlueprintReadOnly, Category = "Errors")
	FString LastError;
};
