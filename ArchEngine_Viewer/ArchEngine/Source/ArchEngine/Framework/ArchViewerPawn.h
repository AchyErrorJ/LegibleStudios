// ArchViewerPawn.h - Orbit camera pawn for architectural visualization
// Provides orbit, pan, zoom controls around a focus point

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "ArchViewerPawn.generated.h"

class USpringArmComponent;
class UCameraComponent;

UCLASS()
class ARCHENGINE_API AArchViewerPawn : public APawn
{
	GENERATED_BODY()

public:
	AArchViewerPawn();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaTime) override;
	virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

	// ============= CAMERA CONTROL =============

	// Focus camera on a world location
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Camera")
	void FocusOnLocation(FVector Location, float Distance = 0.0f);

	// Focus camera on an actor's bounds
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Camera")
	void FocusOnActor(AActor* Actor);

	// Reset camera to default view
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Camera")
	void ResetCamera();

	// Set view preset
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Camera")
	void SetViewPreset(FName PresetName);

	// Get current focus point
	UFUNCTION(BlueprintPure, Category = "ArchViewer|Camera")
	FVector GetFocusPoint() const { return FocusPoint; }

	// Get current camera distance
	UFUNCTION(BlueprintPure, Category = "ArchViewer|Camera")
	float GetCameraDistance() const { return CameraDistance; }

	// ============= CAMERA PROPERTIES =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float MinCameraDistance = 500.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float MaxCameraDistance = 100000.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float DefaultCameraDistance = 10000.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float OrbitSensitivity = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float PanSensitivity = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float ZoomSensitivity = 0.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float ZoomSmoothSpeed = 10.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float OrbitSmoothSpeed = 15.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float MinPitchAngle = -89.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Camera")
	float MaxPitchAngle = 89.0f;

	// ============= COMPONENTS =============

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	USceneComponent* RootSceneComponent;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	USpringArmComponent* CameraArm;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
	UCameraComponent* Camera;

protected:
	// Input handlers
	void HandleOrbitInput(const FVector2D& Delta);
	void HandlePanInput(const FVector2D& Delta);
	void HandleZoomInput(float Delta);

	// Camera state
	FVector FocusPoint = FVector::ZeroVector;
	float CameraDistance = 10000.0f;
	float TargetCameraDistance = 10000.0f;
	float CameraYaw = -45.0f;
	float CameraPitch = -30.0f;
	float TargetCameraYaw = -45.0f;
	float TargetCameraPitch = -30.0f;

	// Input state
	bool bIsOrbiting = false;
	bool bIsPanning = false;
	FVector2D LastMousePosition;
	float PendingZoomDelta = 0.0f;

public:
	// Called by controller to apply zoom input
	void ApplyZoomInput(float Delta) { PendingZoomDelta += Delta; }

protected:

	// Update camera transform from current state
	void UpdateCameraTransform(float DeltaTime);

	// View presets
	TMap<FName, FRotator> ViewPresets;
	void InitializeViewPresets();

};
