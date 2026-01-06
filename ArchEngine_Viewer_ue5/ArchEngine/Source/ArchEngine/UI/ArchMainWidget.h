// ArchMainWidget.h - Root UI container for the ArchEngine Viewer
// Provides the main layout with dockable panels

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "ArchMainWidget.generated.h"

class UCanvasPanel;
class UOverlay;
class USizeBox;
class UHorizontalBox;
class UVerticalBox;
class USplitter;
class UArchPropertiesPanel;
class UArchProjectPanel;
class UArchViewStrip;

UCLASS()
class ARCHENGINE_API UArchMainWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;

	// ============= PANEL ACCESS =============

	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	UArchPropertiesPanel* GetPropertiesPanel() const { return PropertiesPanel; }

	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	UArchProjectPanel* GetProjectPanel() const { return ProjectPanel; }

	UFUNCTION(BlueprintPure, Category = "ArchViewer|UI")
	UArchViewStrip* GetViewStrip() const { return ViewStrip; }

	// ============= PANEL VISIBILITY =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void SetPropertiesPanelVisible(bool bVisible);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void SetProjectPanelVisible(bool bVisible);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void SetViewStripVisible(bool bVisible);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void TogglePropertiesPanel();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void ToggleProjectPanel();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void ToggleViewStrip();

	// ============= LAYOUT =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|UI")
	void ResetLayout();

	// Panel width ratios (0.0 - 1.0)
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Layout")
	float LeftPanelWidthRatio = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Layout")
	float RightPanelWidthRatio = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Layout")
	float BottomPanelHeightRatio = 0.15f;

	// Minimum panel sizes
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Layout")
	float MinPanelWidth = 200.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Layout")
	float MinPanelHeight = 100.0f;

protected:
	// Panel classes (set in Blueprint defaults or CreateDefaultSubobject)
	UPROPERTY(EditDefaultsOnly, Category = "ArchViewer|UI")
	TSubclassOf<UArchPropertiesPanel> PropertiesPanelClass;

	UPROPERTY(EditDefaultsOnly, Category = "ArchViewer|UI")
	TSubclassOf<UArchProjectPanel> ProjectPanelClass;

	UPROPERTY(EditDefaultsOnly, Category = "ArchViewer|UI")
	TSubclassOf<UArchViewStrip> ViewStripClass;

	// Panel instances
	UPROPERTY()
	UArchPropertiesPanel* PropertiesPanel;

	UPROPERTY()
	UArchProjectPanel* ProjectPanel;

	UPROPERTY()
	UArchViewStrip* ViewStrip;

	// Layout containers (created in NativeConstruct)
	UPROPERTY()
	UVerticalBox* RootVerticalBox;

	UPROPERTY()
	UHorizontalBox* MainHorizontalBox;

	UPROPERTY()
	USizeBox* LeftPanelContainer;

	UPROPERTY()
	USizeBox* RightPanelContainer;

	UPROPERTY()
	USizeBox* BottomPanelContainer;

	// Build the layout programmatically
	void BuildLayout();
	void CreatePanels();
	void UpdatePanelSizes();

	// Cached viewport size for layout calculations
	FVector2D CachedViewportSize;
};
