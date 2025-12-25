// ArchProjectPanel.h - Project organizer panel with building hierarchy tree
// Shows levels, rooms, walls, doors, windows in a collapsible tree structure

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Types/ArchTypes.h"
#include "ArchProjectPanel.generated.h"

class UVerticalBox;
class UScrollBox;
class UTextBlock;
class UBorder;
class UButton;
class AArchBuildingActor;
class UArchSelectionManager;

// Tree node types
UENUM(BlueprintType)
enum class EArchTreeNodeType : uint8
{
	Building,
	Level,
	RoomGroup,
	Room,
	WallGroup,
	Wall,
	DoorGroup,
	Door,
	WindowGroup,
	Window,
	RoofGroup,
	Roof,
	StairGroup,
	Stair
};

// Tree node data
USTRUCT(BlueprintType)
struct FArchTreeNode
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite)
	FString Id;

	UPROPERTY(BlueprintReadWrite)
	FString DisplayName;

	UPROPERTY(BlueprintReadWrite)
	EArchTreeNodeType NodeType = EArchTreeNodeType::Building;

	UPROPERTY(BlueprintReadWrite)
	int32 ElementIndex = -1;

	UPROPERTY(BlueprintReadWrite)
	bool bExpanded = false;

	UPROPERTY(BlueprintReadWrite)
	bool bVisible = true;

	UPROPERTY(BlueprintReadWrite)
	int32 IndentLevel = 0;

	// Children array - not exposed to Blueprint due to recursion limitation
	TArray<FArchTreeNode> Children;

	FArchTreeNode() {}
	FArchTreeNode(const FString& InId, const FString& InName, EArchTreeNodeType InType, int32 InIndent = 0)
		: Id(InId), DisplayName(InName), NodeType(InType), IndentLevel(InIndent) {}
};

UCLASS()
class ARCHENGINE_API UArchProjectPanel : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;
	virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

	// ============= BUILDING BINDING =============

	// Bind to a building actor to display its hierarchy
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void BindToBuildingActor(AArchBuildingActor* BuildingActor);

	// Bind to selection manager for highlighting
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void BindToSelectionManager(UArchSelectionManager* SelectionManager);

	// Refresh the tree from building data
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void RefreshTree();

	// ============= TREE OPERATIONS =============

	// Expand/collapse a node
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void ToggleNodeExpanded(const FString& NodeId);

	// Toggle visibility of a node's elements
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void ToggleNodeVisibility(const FString& NodeId);

	// Expand all nodes
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void ExpandAll();

	// Collapse all nodes
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void CollapseAll();

	// Select a node (and its corresponding element)
	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Project")
	void SelectNode(const FString& NodeId);

	// ============= STYLING =============

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor BackgroundColor = FLinearColor(0.05f, 0.05f, 0.05f, 0.9f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor HeaderColor = FLinearColor(0.1f, 0.1f, 0.1f, 1.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor TextColor = FLinearColor::White;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	FLinearColor SelectedColor = FLinearColor(0.2f, 0.4f, 0.8f, 0.5f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float IndentWidth = 16.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Style")
	float RowHeight = 24.0f;

protected:
	// UI Elements
	UPROPERTY()
	UBorder* PanelBackground;

	UPROPERTY()
	UScrollBox* ContentScrollBox;

	UPROPERTY()
	UVerticalBox* TreeVerticalBox;

	UPROPERTY()
	UTextBlock* TitleText;

	// Bound actors
	UPROPERTY()
	AArchBuildingActor* BoundBuildingActor;

	UPROPERTY()
	UArchSelectionManager* BoundSelectionManager;

	// Tree data
	UPROPERTY()
	FArchTreeNode RootNode;

	// Currently selected node
	FString SelectedNodeId;

	// Build the panel layout
	void BuildLayout();

	// Build tree from building data
	void BuildTreeFromBuilding(const FArchBuilding& Building);

	// Rebuild the UI from tree data
	void RebuildTreeUI();

	// Create a tree row widget
	UWidget* CreateTreeRow(const FArchTreeNode& Node);

	// Find node by ID (recursive)
	FArchTreeNode* FindNode(FArchTreeNode& StartNode, const FString& NodeId);

	// Flatten tree for display (respecting expanded state)
	void FlattenTree(const FArchTreeNode& Node, TArray<FArchTreeNode>& OutNodes);

	// Node click handler
	UFUNCTION()
	void OnNodeClicked(const FString& NodeId);

	// Visibility toggle handler
	UFUNCTION()
	void OnVisibilityToggled(const FString& NodeId);

	// Track if building data changed
	int32 LastBuildingDataHash = 0;
	bool CheckBuildingDataChanged();
};
