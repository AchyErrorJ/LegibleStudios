// ArchViewStrip.h - Bottom strip with multiple view thumbnails
// Shows different visualization modes in small preview panels

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Types/ArchTypes.h"
#include "ArchViewStrip.generated.h"

class UHorizontalBox;
class UBorder;
class UTextBlock;
class UImage;
class UButton;
class AArchBuildingActor;

// View preset data
USTRUCT(BlueprintType)
struct FArchViewPreset
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Name;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	EVisualizationMode VisualizationMode = EVisualizationMode::Structural;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FLinearColor TintColor = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite)
	FString Description;

	FArchViewPreset() {}
	FArchViewPreset(const FString& InName, EVisualizationMode InMode, const FLinearColor& InColor, const FString& InDesc = TEXT(""))
		: Name(InName), VisualizationMode(InMode), TintColor(InColor), Description(InDesc) {}
};

// Delegate for when a view preset is selected
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnViewPresetSelected, const FArchViewPreset&, Preset);

UCLASS()
class ARCHENGINE_API UArchViewStrip : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;

	// ============= VIEW PRESETS =============

	// Get current presets
	UFUNCTION(BlueprintPure, Category = "ArchViewer|ViewStrip")
	TArray<FArchViewPreset> GetViewPresets() const { return ViewPresets; }

	// Set custom presets
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|ViewStrip")
	void SetViewPresets(const TArray<FArchViewPreset>& Presets);

	// Select a preset by index
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|ViewStrip")
	void SelectPreset(int32 PresetIndex);

	// Get currently selected preset index
	UFUNCTION(BlueprintPure, Category = "ArchViewer|ViewStrip")
	int32 GetSelectedPresetIndex() const { return SelectedPresetIndex; }

	// ============= BUILDING BINDING =============

	// Bind to building actor to apply visualization modes
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|ViewStrip")
	void BindToBuildingActor(AArchBuildingActor* BuildingActor);

	// ============= EVENTS =============

	UPROPERTY(BlueprintAssignable, Category = "ArchViewer|ViewStrip|Events")
	FOnViewPresetSelected OnViewPresetSelected;

	// ============= STYLING =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor BackgroundColor = FLinearColor(0.05f, 0.05f, 0.05f, 0.95f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor PreviewBackgroundColor = FLinearColor(0.1f, 0.1f, 0.1f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor SelectedBorderColor = FLinearColor(0.2f, 0.6f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor TextColor = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float PreviewWidth = 160.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float PreviewHeight = 90.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float PreviewSpacing = 8.0f;

protected:
	// Default view presets
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|ViewStrip")
	TArray<FArchViewPreset> ViewPresets;

	// Selected preset index
	int32 SelectedPresetIndex = 0;

	// Bound building actor
	UPROPERTY()
	AArchBuildingActor* BoundBuildingActor;

	// UI Elements
	UPROPERTY()
	UBorder* StripBackground;

	UPROPERTY()
	UHorizontalBox* PreviewContainer;

	// Preview panel widgets
	UPROPERTY()
	TArray<UBorder*> PreviewPanels;

	// Initialize default presets
	void InitializeDefaultPresets();

	// Build the strip layout
	void BuildLayout();

	// Create a preview panel for a preset
	UWidget* CreatePreviewPanel(const FArchViewPreset& Preset, int32 Index);

	// Update selection visuals
	void UpdateSelectionVisuals();
};
