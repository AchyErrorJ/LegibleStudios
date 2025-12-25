// ArchViewerPawn.cpp - Orbit camera pawn implementation

#include "Framework/ArchViewerPawn.h"
#include "GameFramework/SpringArmComponent.h"
#include "Camera/CameraComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

AArchViewerPawn::AArchViewerPawn()
{
	PrimaryActorTick.bCanEverTick = true;

	// Create root component
	RootSceneComponent = CreateDefaultSubobject<USceneComponent>(TEXT("RootScene"));
	RootComponent = RootSceneComponent;

	// Create camera arm
	CameraArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraArm"));
	CameraArm->SetupAttachment(RootComponent);
	CameraArm->TargetArmLength = DefaultCameraDistance;
	CameraArm->bDoCollisionTest = false;
	CameraArm->bEnableCameraLag = true;
	CameraArm->CameraLagSpeed = 10.0f;
	CameraArm->bEnableCameraRotationLag = true;
	CameraArm->CameraRotationLagSpeed = 10.0f;

	// Create camera
	Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
	Camera->SetupAttachment(CameraArm);
	Camera->SetFieldOfView(60.0f);

	// Initialize camera state
	CameraDistance = DefaultCameraDistance;
	TargetCameraDistance = DefaultCameraDistance;

	// Don't rotate pawn with controller
	bUseControllerRotationPitch = false;
	bUseControllerRotationYaw = false;
	bUseControllerRotationRoll = false;
}

void AArchViewerPawn::BeginPlay()
{
	Super::BeginPlay();

	InitializeViewPresets();

	// Set initial camera position
	TargetCameraYaw = CameraYaw;
	TargetCameraPitch = CameraPitch;
	UpdateCameraTransform(0.0f);

	// Set initial arm length
	CameraArm->TargetArmLength = CameraDistance;
}

void AArchViewerPawn::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	APlayerController* PC = Cast<APlayerController>(GetController());
	if (!PC)
	{
		UpdateCameraTransform(DeltaTime);
		return;
	}

	// Get current mouse position
	float MouseX, MouseY;
	PC->GetMousePosition(MouseX, MouseY);
	FVector2D CurrentMousePos(MouseX, MouseY);

	// Check for RMB (orbit) and MMB (pan) state directly
	bool bRMBPressed = PC->IsInputKeyDown(EKeys::RightMouseButton);
	bool bMMBPressed = PC->IsInputKeyDown(EKeys::MiddleMouseButton);

	// Handle orbit start/stop
	if (bRMBPressed && !bIsOrbiting && !bIsPanning)
	{
		bIsOrbiting = true;
		PC->SetShowMouseCursor(false);
		LastMousePosition = CurrentMousePos;
	}
	else if (!bRMBPressed && bIsOrbiting)
	{
		bIsOrbiting = false;
		PC->SetShowMouseCursor(true);
	}

	// Handle pan start/stop
	if (bMMBPressed && !bIsPanning && !bIsOrbiting)
	{
		bIsPanning = true;
		PC->SetShowMouseCursor(false);
		LastMousePosition = CurrentMousePos;
	}
	else if (!bMMBPressed && bIsPanning)
	{
		bIsPanning = false;
		PC->SetShowMouseCursor(true);
	}

	// Apply orbit/pan movement
	if (bIsOrbiting || bIsPanning)
	{
		FVector2D Delta = CurrentMousePos - LastMousePosition;

		if (bIsOrbiting)
		{
			HandleOrbitInput(Delta);
		}
		else if (bIsPanning)
		{
			HandlePanInput(Delta);
		}
	}

	LastMousePosition = CurrentMousePos;

	// Process any pending zoom input from mouse wheel
	if (FMath::Abs(PendingZoomDelta) > KINDA_SMALL_NUMBER)
	{
		HandleZoomInput(PendingZoomDelta);
		PendingZoomDelta = 0.0f;
	}

	UpdateCameraTransform(DeltaTime);
}

void AArchViewerPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
	Super::SetupPlayerInputComponent(PlayerInputComponent);

	// Input is handled directly in Tick via key state checking
	// This bypasses the input mapping system for immediate functionality
}

void AArchViewerPawn::InitializeViewPresets()
{
	// Standard architectural view presets
	ViewPresets.Add(FName("Top"), FRotator(-90.0f, 0.0f, 0.0f));
	ViewPresets.Add(FName("Bottom"), FRotator(90.0f, 0.0f, 0.0f));
	ViewPresets.Add(FName("Front"), FRotator(0.0f, 0.0f, 0.0f));
	ViewPresets.Add(FName("Back"), FRotator(0.0f, 180.0f, 0.0f));
	ViewPresets.Add(FName("Left"), FRotator(0.0f, 90.0f, 0.0f));
	ViewPresets.Add(FName("Right"), FRotator(0.0f, -90.0f, 0.0f));
	ViewPresets.Add(FName("Isometric"), FRotator(-35.264f, -45.0f, 0.0f));  // True isometric
	ViewPresets.Add(FName("IsometricSE"), FRotator(-35.264f, -135.0f, 0.0f));
	ViewPresets.Add(FName("Perspective"), FRotator(-30.0f, -45.0f, 0.0f));  // Default
}

void AArchViewerPawn::HandleOrbitInput(const FVector2D& Delta)
{
	// Orbit around focus point
	TargetCameraYaw += Delta.X * OrbitSensitivity;
	TargetCameraPitch = FMath::Clamp(TargetCameraPitch - Delta.Y * OrbitSensitivity, MinPitchAngle, MaxPitchAngle);
}

void AArchViewerPawn::HandlePanInput(const FVector2D& Delta)
{
	// Pan the focus point
	FRotator CameraRotation(CameraPitch, CameraYaw, 0.0f);
	FVector RightVector = FRotationMatrix(CameraRotation).GetUnitAxis(EAxis::Y);
	FVector UpVector = FVector::UpVector;

	// Scale pan speed by distance for consistent feel
	float PanScale = CameraDistance * PanSensitivity * 0.001f;

	FocusPoint -= RightVector * Delta.X * PanScale;
	FocusPoint += UpVector * Delta.Y * PanScale;
}

void AArchViewerPawn::HandleZoomInput(float Delta)
{
	if (FMath::Abs(Delta) > KINDA_SMALL_NUMBER)
	{
		// Exponential zoom for natural feel
		float ZoomFactor = 1.0f - Delta * ZoomSensitivity;
		TargetCameraDistance = FMath::Clamp(TargetCameraDistance * ZoomFactor, MinCameraDistance, MaxCameraDistance);
	}
}

void AArchViewerPawn::UpdateCameraTransform(float DeltaTime)
{
	// Smooth interpolation
	if (DeltaTime > 0.0f)
	{
		CameraYaw = FMath::FInterpTo(CameraYaw, TargetCameraYaw, DeltaTime, OrbitSmoothSpeed);
		CameraPitch = FMath::FInterpTo(CameraPitch, TargetCameraPitch, DeltaTime, OrbitSmoothSpeed);
		CameraDistance = FMath::FInterpTo(CameraDistance, TargetCameraDistance, DeltaTime, ZoomSmoothSpeed);
	}
	else
	{
		// Instant update (for initialization)
		CameraYaw = TargetCameraYaw;
		CameraPitch = TargetCameraPitch;
		CameraDistance = TargetCameraDistance;
	}

	// Update root position to focus point
	SetActorLocation(FocusPoint);

	// Update camera arm rotation
	FRotator NewRotation(CameraPitch, CameraYaw, 0.0f);
	CameraArm->SetRelativeRotation(NewRotation);

	// Update camera distance
	CameraArm->TargetArmLength = CameraDistance;
}

void AArchViewerPawn::FocusOnLocation(FVector Location, float Distance)
{
	FocusPoint = Location;

	if (Distance > 0.0f)
	{
		TargetCameraDistance = FMath::Clamp(Distance, MinCameraDistance, MaxCameraDistance);
	}
}

void AArchViewerPawn::FocusOnActor(AActor* Actor)
{
	if (!Actor)
	{
		return;
	}

	// Get actor bounds
	FVector Origin;
	FVector BoxExtent;
	Actor->GetActorBounds(true, Origin, BoxExtent);

	// Focus on center
	FocusPoint = Origin;

	// Set distance based on bounds size
	float BoundsRadius = BoxExtent.Size();
	TargetCameraDistance = FMath::Clamp(BoundsRadius * 2.0f, MinCameraDistance, MaxCameraDistance);
}

void AArchViewerPawn::ResetCamera()
{
	FocusPoint = FVector::ZeroVector;
	TargetCameraYaw = -45.0f;
	TargetCameraPitch = -30.0f;
	TargetCameraDistance = DefaultCameraDistance;
}

void AArchViewerPawn::SetViewPreset(FName PresetName)
{
	if (FRotator* PresetRotation = ViewPresets.Find(PresetName))
	{
		TargetCameraPitch = PresetRotation->Pitch;
		TargetCameraYaw = PresetRotation->Yaw;
	}
}
