// ArchViewerController.cpp - Player controller implementation

#include "Framework/ArchViewerController.h"
#include "Framework/ArchViewerPawn.h"
#include "Framework/ArchSelectionManager.h"
#include "GameFramework/InputSettings.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

AArchViewerController::AArchViewerController()
{
	PrimaryActorTick.bCanEverTick = true;

	// Show mouse cursor by default
	bShowMouseCursor = true;
	bEnableClickEvents = true;
	bEnableMouseOverEvents = true;

	// Default input mode
	DefaultMouseCursor = EMouseCursor::Default;
}

void AArchViewerController::BeginPlay()
{
	Super::BeginPlay();

	// Create selection manager
	SelectionManager = NewObject<UArchSelectionManager>(this, TEXT("SelectionManager"));
	if (SelectionManager)
	{
		SelectionManager->Initialize(this);
	}

	// Set input mode to game and UI
	SetGameAndUIInputMode();
}

void AArchViewerController::SetupInputComponent()
{
	Super::SetupInputComponent();

	// Input is handled directly via Tick and InputAxis
	// This bypasses the input mapping system for immediate functionality
}

void AArchViewerController::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);

	// Handle LMB for selection
	bool bLMBPressed = IsInputKeyDown(EKeys::LeftMouseButton);
	if (bLMBPressed && !bMousePressed)
	{
		OnLeftMousePressed();
	}
	else if (!bLMBPressed && bMousePressed)
	{
		OnLeftMouseReleased();
	}

	// Handle Escape
	if (WasInputKeyJustPressed(EKeys::Escape))
	{
		OnEscapePressed();
	}

	// Handle Delete
	if (WasInputKeyJustPressed(EKeys::Delete))
	{
		OnDeletePressed();
	}

	// Handle F for focus
	if (WasInputKeyJustPressed(EKeys::F))
	{
		OnFocusPressed();
	}
}

bool AArchViewerController::InputKey(const FInputKeyParams& Params)
{
	// Forward mouse wheel to pawn for zoom
	if (Params.Key == EKeys::MouseWheelAxis)
	{
		AArchViewerPawn* ViewerPawn = GetViewerPawn();
		if (ViewerPawn)
		{
			ViewerPawn->ApplyZoomInput(Params.Delta.X);
		}
	}

	return Super::InputKey(Params);
}

void AArchViewerController::OnLeftMousePressed()
{
	bMousePressed = true;
	MousePressTime = GetWorld()->GetTimeSeconds();
	GetMousePosition(MousePressPosition.X, MousePressPosition.Y);
}

void AArchViewerController::OnLeftMouseReleased()
{
	if (!bMousePressed)
	{
		return;
	}

	bMousePressed = false;

	// Check if this was a click (not a drag)
	float CurrentTime = GetWorld()->GetTimeSeconds();
	float ClickDuration = CurrentTime - MousePressTime;

	FVector2D CurrentMousePos;
	GetMousePosition(CurrentMousePos.X, CurrentMousePos.Y);

	float MouseMovement = FVector2D::Distance(MousePressPosition, CurrentMousePos);

	// Only select if it was a quick click without much movement
	if (ClickDuration < ClickTimeThreshold && MouseMovement < ClickThreshold)
	{
		if (bEnableClickSelection)
		{
			bool bAddToSelection = IsInputKeyDown(EKeys::LeftControl) || IsInputKeyDown(EKeys::RightControl);
			SelectAtScreenPosition(CurrentMousePos, bAddToSelection);
		}
	}
}

void AArchViewerController::OnEscapePressed()
{
	ClearSelection();
}

void AArchViewerController::OnDeletePressed()
{
	// Future: Delete selected elements or dimensions
}

void AArchViewerController::OnFocusPressed()
{
	if (SelectionManager && SelectionManager->HasSelection())
	{
		AArchViewerPawn* ViewerPawn = GetViewerPawn();
		if (ViewerPawn)
		{
			// Focus on selected actor
			AActor* SelectedActor = SelectionManager->GetSelectedActor();
			if (SelectedActor)
			{
				ViewerPawn->FocusOnActor(SelectedActor);
			}
		}
	}
}

void AArchViewerController::SelectAtCursor()
{
	FVector2D MousePos;
	GetMousePosition(MousePos.X, MousePos.Y);
	SelectAtScreenPosition(MousePos, false);
}

void AArchViewerController::SelectAtScreenPosition(FVector2D ScreenPosition, bool bAddToSelection)
{
	if (!SelectionManager)
	{
		return;
	}

	// Perform line trace from camera through screen position
	FVector WorldLocation, WorldDirection;
	if (DeprojectScreenPositionToWorld(ScreenPosition.X, ScreenPosition.Y, WorldLocation, WorldDirection))
	{
		FVector TraceEnd = WorldLocation + WorldDirection * 100000.0f;

		FHitResult HitResult;
		FCollisionQueryParams QueryParams;
		QueryParams.bTraceComplex = true;
		QueryParams.bReturnFaceIndex = true;

		if (GetWorld()->LineTraceSingleByChannel(HitResult, WorldLocation, TraceEnd, SelectionTraceChannel, QueryParams))
		{
			SelectionManager->SelectActor(HitResult.GetActor(), HitResult.GetComponent(), HitResult.FaceIndex, bAddToSelection);
		}
		else
		{
			// Clicked on nothing
			if (!bAddToSelection)
			{
				SelectionManager->ClearSelection();
			}
		}
	}
}

void AArchViewerController::ClearSelection()
{
	if (SelectionManager)
	{
		SelectionManager->ClearSelection();
	}
}

AArchViewerPawn* AArchViewerController::GetViewerPawn() const
{
	return Cast<AArchViewerPawn>(GetPawn());
}

void AArchViewerController::SetUIInputMode()
{
	FInputModeUIOnly InputMode;
	InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	SetInputMode(InputMode);
	SetShowMouseCursor(true);
}

void AArchViewerController::SetGameInputMode()
{
	FInputModeGameOnly InputMode;
	SetInputMode(InputMode);
	SetShowMouseCursor(false);
}

void AArchViewerController::SetGameAndUIInputMode()
{
	FInputModeGameAndUI InputMode;
	InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
	InputMode.SetHideCursorDuringCapture(false);
	SetInputMode(InputMode);
	SetShowMouseCursor(true);
}
