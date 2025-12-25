// ArchPropertiesPanel.h - Properties panel for selected elements
// Shows details, materials, and constraints for the current selection

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Types/ArchTypes.h"
#include "ArchPropertiesPanel.generated.h"

class UVerticalBox;
class UScrollBox;
class UTextBlock;
class UBorder;
class UArchSelectionManager;
struct FArchSelectionInfo;

// Property row for displaying key-value pairs
USTRUCT(BlueprintType)
struct FArchPropertyRow
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite)
	FString Label;

	UPROPERTY(BlueprintReadWrite)
	FString Value;

	UPROPERTY(BlueprintReadWrite)
	FString Category;

	FArchPropertyRow() {}
	FArchPropertyRow(const FString& InLabel, const FString& InValue, const FString& InCategory = TEXT(""))
		: Label(InLabel), Value(InValue), Category(InCategory) {}
};

UCLASS()
class ARCHENGINE_API UArchPropertiesPanel : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;

	// ============= SELECTION BINDING =============

	// Bind to a selection manager to receive updates
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Properties")
	void BindToSelectionManager(UArchSelectionManager* SelectionManager);

	// Manually update with selection info
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Properties")
	void UpdateFromSelection(const TArray<FArchSelectionInfo>& Selection);

	// Clear the panel
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Properties")
	void ClearProperties();

	// ============= STYLING =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor BackgroundColor = FLinearColor(0.05f, 0.05f, 0.05f, 0.9f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor HeaderColor = FLinearColor(0.1f, 0.1f, 0.1f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor TextColor = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor LabelColor = FLinearColor(0.6f, 0.6f, 0.6f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float PanelPadding = 8.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float RowSpacing = 4.0f;

protected:
	// UI Elements
	UPROPERTY()
	UBorder* PanelBackground;

	UPROPERTY()
	UScrollBox* ContentScrollBox;

	UPROPERTY()
	UVerticalBox* ContentVerticalBox;

	UPROPERTY()
	UTextBlock* TitleText;

	UPROPERTY()
	UTextBlock* NoSelectionText;

	// Cached selection manager
	UPROPERTY()
	UArchSelectionManager* BoundSelectionManager;

	// Build the panel layout
	void BuildLayout();

	// Add a property row to the panel
	void AddPropertyRow(const FString& Label, const FString& Value);

	// Add a section header
	void AddSectionHeader(const FString& SectionName);

	// Add a spacer
	void AddSpacer(float Height = 8.0f);

	// Populate properties from a wall type
	void PopulateWallTypeProperties(const FArchWallType& WallType);

	// Populate properties from a door
	void PopulateDoorProperties(const FArchDoor& Door);

	// Populate properties from a window
	void PopulateWindowProperties(const FArchWindow& Window);

	// Populate properties from a room
	void PopulateRoomProperties(const FArchRoom& Room);

	// Populate properties from a level
	void PopulateLevelProperties(const FArchLevel& Level);

	// Selection changed callback
	UFUNCTION()
	void OnSelectionChanged(const TArray<FArchSelectionInfo>& NewSelection);
};
