// ArchViewerHUD.h - HUD class for architectural viewer
// Hosts the main UI widget and manages UI state

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "ArchViewerHUD.generated.h"

class UUserWidget;
class UArchMainWidget;

UCLASS()
class ARCHENGINE_API AArchViewerHUD : public AHUD
{
	GENERATED_BODY()

public:
	AArchViewerHUD();

	virtual void BeginPlay() override;
	virtual void DrawHUD() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

	// ============= UI MANAGEMENT =============

	// Get the main widget
	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	UUserWidget* GetMainWidget() const { return MainWidget; }

	// Get the main widget as ArchMainWidget
	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	UArchMainWidget* GetArchMainWidget() const;

	// Show/hide the main UI
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void SetUIVisible(bool bVisible);

	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	bool IsUIVisible() const { return bUIVisible; }

	// ============= DEBUG DISPLAY =============

	// Show viewer debug overlay
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Debug")
	bool bShowViewerDebug = false;

	// Show camera info
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Debug")
	bool bShowCameraInfo = true;

	// Show selection info
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Debug")
	bool bShowSelectionInfo = true;

protected:
	// Main UI widget class (set in Blueprint or defaults)
	UPROPERTY(EditDefaultsOnly, Category = "ArchViewer|UI")
	TSubclassOf<UUserWidget> MainWidgetClass;

	// Instance of main widget
	UPROPERTY()
	UUserWidget* MainWidget;

	bool bUIVisible = true;

	// Draw debug information
	void DrawDebugInfo();
	void DrawCameraInfo();
	void DrawSelectionInfo();
};
