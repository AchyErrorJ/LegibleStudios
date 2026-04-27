// ArchSelectionManager.h - Manages selection state for architectural elements
// Handles single/multi selection, highlighting, and selection events

#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "ArchSelectionManager.generated.h"

class APlayerController;
class UPrimitiveComponent;

// Selection info for a single element
USTRUCT(BlueprintType)
struct FArchSelectionInfo
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Selection")
	AActor* Actor = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Selection")
	UPrimitiveComponent* Component = nullptr;

	UPROPERTY(BlueprintReadOnly, Category = "Selection")
	int32 FaceIndex = -1;

	UPROPERTY(BlueprintReadOnly, Category = "Selection")
	FString ElementId;

	UPROPERTY(BlueprintReadOnly, Category = "Selection")
	FString ElementType;

	bool IsValid() const { return Actor != nullptr; }

	bool operator==(const FArchSelectionInfo& Other) const
	{
		return Actor == Other.Actor && Component == Other.Component && FaceIndex == Other.FaceIndex;
	}
};

// Delegate for selection changes
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnSelectionChanged, const TArray<FArchSelectionInfo>&, Selection);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnElementHovered, const FArchSelectionInfo&, HoveredElement);

UCLASS(BlueprintType)
class ARCHENGINE_API UArchSelectionManager : public UObject
{
	GENERATED_BODY()

public:
	UArchSelectionManager();

	// Initialize with owning controller
	void Initialize(APlayerController* InOwnerController);

	// ============= SELECTION OPERATIONS =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void SelectActor(AActor* Actor, UPrimitiveComponent* Component = nullptr, int32 FaceIndex = -1, bool bAddToSelection = false);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void DeselectActor(AActor* Actor);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void ClearSelection();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void SetSelection(const TArray<FArchSelectionInfo>& NewSelection);

	// ============= SELECTION QUERIES =============

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	bool HasSelection() const { return Selection.Num() > 0; }

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	int32 GetSelectionCount() const { return Selection.Num(); }

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	TArray<FArchSelectionInfo> GetSelection() const { return Selection; }

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	FArchSelectionInfo GetPrimarySelection() const;

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	AActor* GetSelectedActor() const;

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	TArray<AActor*> GetSelectedActors() const;

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	bool IsActorSelected(AActor* Actor) const;

	// ============= HOVER =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void SetHoveredElement(AActor* Actor, UPrimitiveComponent* Component = nullptr, int32 FaceIndex = -1);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void ClearHover();

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	FArchSelectionInfo GetHoveredElement() const { return HoveredElement; }

	// ============= HIGHLIGHTING =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Selection")
	FLinearColor SelectionHighlightColor = FLinearColor(0.2f, 0.6f, 1.0f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Selection")
	FLinearColor HoverHighlightColor = FLinearColor(1.0f, 0.8f, 0.2f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Selection")
	float SelectionOutlineThickness = 2.0f;

	// ============= EVENTS =============

	UPROPERTY(BlueprintAssignable, Category = "ArchViewer|Selection|Events")
	FOnSelectionChanged OnSelectionChanged;

	UPROPERTY(BlueprintAssignable, Category = "ArchViewer|Selection|Events")
	FOnElementHovered OnElementHovered;

protected:
	UPROPERTY()
	APlayerController* OwnerController;

	UPROPERTY()
	TArray<FArchSelectionInfo> Selection;

	UPROPERTY()
	FArchSelectionInfo HoveredElement;

	// Apply visual highlighting to selected elements
	void ApplySelectionHighlight(const FArchSelectionInfo& Info, bool bSelected);

	// Try to get element info from actor (queries ArchBuildingActor)
	FArchSelectionInfo CreateSelectionInfo(AActor* Actor, UPrimitiveComponent* Component, int32 FaceIndex);

	// Notify listeners of selection change
	void BroadcastSelectionChanged();
};
