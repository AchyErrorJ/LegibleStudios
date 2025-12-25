// ArchViewerHUD.cpp - HUD implementation

#include "Framework/ArchViewerHUD.h"
#include "Framework/ArchViewerPawn.h"
#include "Framework/ArchViewerController.h"
#include "Framework/ArchSelectionManager.h"
#include "UI/ArchMainWidget.h"
#include "UI/Panels/ArchPropertiesPanel.h"
#include "UI/Panels/ArchProjectPanel.h"
#include "UI/Panels/ArchViewStrip.h"
#include "Actors/ArchBuildingActor.h"
#include "Blueprint/UserWidget.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Kismet/GameplayStatics.h"

AArchViewerHUD::AArchViewerHUD()
{
}

void AArchViewerHUD::BeginPlay()
{
	Super::BeginPlay();

	// Create main widget - use ArchMainWidget by default
	if (MainWidgetClass)
	{
		MainWidget = CreateWidget<UUserWidget>(GetOwningPlayerController(), MainWidgetClass);
	}
	else
	{
		// Create ArchMainWidget directly
		MainWidget = CreateWidget<UArchMainWidget>(GetOwningPlayerController(), UArchMainWidget::StaticClass());
	}

	if (MainWidget)
	{
		MainWidget->AddToViewport(0);
		UE_LOG(LogTemp, Log, TEXT("ArchViewerHUD: Created main widget"));

		// Wire up the panels
		UArchMainWidget* ArchWidget = Cast<UArchMainWidget>(MainWidget);
		if (ArchWidget)
		{
			// Find building actor and bind panels
			TArray<AActor*> FoundActors;
			UGameplayStatics::GetAllActorsOfClass(GetWorld(), AArchBuildingActor::StaticClass(), FoundActors);
			AArchBuildingActor* BuildingActor = FoundActors.Num() > 0 ? Cast<AArchBuildingActor>(FoundActors[0]) : nullptr;

			// Get selection manager from controller
			AArchViewerController* ViewerController = Cast<AArchViewerController>(GetOwningPlayerController());
			UArchSelectionManager* SelectionManager = ViewerController ? ViewerController->GetSelectionManager() : nullptr;

			// Bind properties panel to selection
			if (ArchWidget->GetPropertiesPanel() && SelectionManager)
			{
				ArchWidget->GetPropertiesPanel()->BindToSelectionManager(SelectionManager);
			}

			// Bind project panel to building
			if (ArchWidget->GetProjectPanel())
			{
				if (BuildingActor)
				{
					ArchWidget->GetProjectPanel()->BindToBuildingActor(BuildingActor);
				}
				if (SelectionManager)
				{
					ArchWidget->GetProjectPanel()->BindToSelectionManager(SelectionManager);
				}
			}

			// Bind view strip to building
			if (ArchWidget->GetViewStrip() && BuildingActor)
			{
				ArchWidget->GetViewStrip()->BindToBuildingActor(BuildingActor);
			}
		}
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("ArchViewerHUD: Failed to create main widget"));
	}
}

void AArchViewerHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (MainWidget)
	{
		MainWidget->RemoveFromParent();
		MainWidget = nullptr;
	}

	Super::EndPlay(EndPlayReason);
}

void AArchViewerHUD::DrawHUD()
{
	Super::DrawHUD();

	if (bShowViewerDebug)
	{
		DrawDebugInfo();
	}
}

void AArchViewerHUD::SetUIVisible(bool bVisible)
{
	bUIVisible = bVisible;

	if (MainWidget)
	{
		if (bVisible)
		{
			MainWidget->SetVisibility(ESlateVisibility::Visible);
		}
		else
		{
			MainWidget->SetVisibility(ESlateVisibility::Hidden);
		}
	}
}

void AArchViewerHUD::DrawDebugInfo()
{
	if (bShowCameraInfo)
	{
		DrawCameraInfo();
	}

	if (bShowSelectionInfo)
	{
		DrawSelectionInfo();
	}
}

void AArchViewerHUD::DrawCameraInfo()
{
	AArchViewerController* ViewerController = Cast<AArchViewerController>(GetOwningPlayerController());
	if (!ViewerController)
	{
		return;
	}

	AArchViewerPawn* ViewerPawn = ViewerController->GetViewerPawn();
	if (!ViewerPawn)
	{
		return;
	}

	float X = 20.0f;
	float Y = 20.0f;
	float LineHeight = 18.0f;
	FLinearColor TextColor = FLinearColor::White;

	// Draw camera info
	DrawText(TEXT("=== Camera ==="), TextColor, X, Y);
	Y += LineHeight;

	FVector FocusPoint = ViewerPawn->GetFocusPoint();
	DrawText(FString::Printf(TEXT("Focus: (%.0f, %.0f, %.0f)"), FocusPoint.X, FocusPoint.Y, FocusPoint.Z), TextColor, X, Y);
	Y += LineHeight;

	float Distance = ViewerPawn->GetCameraDistance();
	DrawText(FString::Printf(TEXT("Distance: %.0f"), Distance), TextColor, X, Y);
	Y += LineHeight;

	// Controls hint
	Y += LineHeight;
	DrawText(TEXT("Controls:"), FLinearColor::Yellow, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  RMB Drag: Orbit"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  MMB Drag: Pan"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  Scroll: Zoom"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  F: Focus on selection"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  LMB: Select"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  Ctrl+LMB: Multi-select"), TextColor, X, Y);
	Y += LineHeight;
	DrawText(TEXT("  Escape: Clear selection"), TextColor, X, Y);
}

void AArchViewerHUD::DrawSelectionInfo()
{
	AArchViewerController* ViewerController = Cast<AArchViewerController>(GetOwningPlayerController());
	if (!ViewerController)
	{
		return;
	}

	UArchSelectionManager* SelectionManager = ViewerController->GetSelectionManager();
	if (!SelectionManager)
	{
		return;
	}

	float X = 20.0f;
	float Y = 250.0f;
	float LineHeight = 18.0f;
	FLinearColor TextColor = FLinearColor::White;
	FLinearColor HighlightColor = FLinearColor(0.2f, 0.6f, 1.0f);

	DrawText(TEXT("=== Selection ==="), TextColor, X, Y);
	Y += LineHeight;

	int32 SelectionCount = SelectionManager->GetSelectionCount();
	DrawText(FString::Printf(TEXT("Selected: %d"), SelectionCount), TextColor, X, Y);
	Y += LineHeight;

	if (SelectionCount > 0)
	{
		TArray<FArchSelectionInfo> Selection = SelectionManager->GetSelection();
		int32 DisplayCount = FMath::Min(Selection.Num(), 5);  // Show max 5 items

		for (int32 i = 0; i < DisplayCount; ++i)
		{
			const FArchSelectionInfo& Info = Selection[i];
			FString DisplayName = Info.Actor ? Info.Actor->GetName() : TEXT("None");
			DrawText(FString::Printf(TEXT("  %d: %s"), i + 1, *DisplayName), HighlightColor, X, Y);
			Y += LineHeight;
		}

		if (Selection.Num() > 5)
		{
			DrawText(FString::Printf(TEXT("  ... and %d more"), Selection.Num() - 5), TextColor, X, Y);
		}
	}
}

UArchMainWidget* AArchViewerHUD::GetArchMainWidget() const
{
	return Cast<UArchMainWidget>(MainWidget);
}
