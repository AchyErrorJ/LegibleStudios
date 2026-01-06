// ArchProjectPanel.cpp - Project organizer panel implementation

#include "UI/Panels/ArchProjectPanel.h"
#include "Framework/ArchSelectionManager.h"
#include "Actors/ArchBuildingActor.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/Button.h"
#include "Components/Spacer.h"
#include "Blueprint/WidgetTree.h"

void UArchProjectPanel::NativeConstruct()
{
	Super::NativeConstruct();
	BuildLayout();
}

void UArchProjectPanel::NativeDestruct()
{
	Super::NativeDestruct();
}

void UArchProjectPanel::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
	Super::NativeTick(MyGeometry, InDeltaTime);

	// Check if building data changed and refresh
	if (BoundBuildingActor && CheckBuildingDataChanged())
	{
		RefreshTree();
	}
}

void UArchProjectPanel::BuildLayout()
{
	// Create background border
	PanelBackground = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName("PanelBackground"));
	PanelBackground->SetBrushColor(BackgroundColor);
	PanelBackground->SetPadding(FMargin(8.0f));
	WidgetTree->RootWidget = PanelBackground;

	// Create vertical box for layout
	UVerticalBox* MainVBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName("MainVBox"));
	PanelBackground->AddChild(MainVBox);

	// Add title
	TitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName("TitleText"));
	TitleText->SetText(FText::FromString(TEXT("PROJECT")));
	TitleText->SetColorAndOpacity(TextColor);
	FSlateFontInfo TitleFont = TitleText->GetFont();
	TitleFont.Size = 14;
	TitleText->SetFont(TitleFont);
	UVerticalBoxSlot* TitleSlot = MainVBox->AddChildToVerticalBox(TitleText);
	TitleSlot->SetPadding(FMargin(0, 0, 0, 8));

	// Create scroll box for tree content
	ContentScrollBox = WidgetTree->ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName("ContentScrollBox"));
	UVerticalBoxSlot* ScrollSlot = MainVBox->AddChildToVerticalBox(ContentScrollBox);
	ScrollSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Create tree vertical box
	TreeVerticalBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName("TreeVerticalBox"));
	ContentScrollBox->AddChild(TreeVerticalBox);

	// Add placeholder text
	UTextBlock* PlaceholderText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName("PlaceholderText"));
	PlaceholderText->SetText(FText::FromString(TEXT("No building loaded")));
	PlaceholderText->SetColorAndOpacity(FLinearColor(0.5f, 0.5f, 0.5f, 1.0f));
	TreeVerticalBox->AddChildToVerticalBox(PlaceholderText);
}

void UArchProjectPanel::BindToBuildingActor(AArchBuildingActor* BuildingActor)
{
	BoundBuildingActor = BuildingActor;
	RefreshTree();
}

void UArchProjectPanel::BindToSelectionManager(UArchSelectionManager* SelectionManager)
{
	BoundSelectionManager = SelectionManager;
}

void UArchProjectPanel::RefreshTree()
{
	if (!BoundBuildingActor)
	{
		return;
	}

	BuildTreeFromBuilding(BoundBuildingActor->BuildingData);
	RebuildTreeUI();
}

void UArchProjectPanel::BuildTreeFromBuilding(const FArchBuilding& Building)
{
	// Create root node
	RootNode = FArchTreeNode(TEXT("building"), Building.Name.IsEmpty() ? TEXT("Building") : Building.Name, EArchTreeNodeType::Building, 0);
	RootNode.bExpanded = true;

	// Add levels
	for (int32 i = 0; i < Building.Levels.Num(); ++i)
	{
		const FArchLevel& Level = Building.Levels[i];
		FArchTreeNode LevelNode(Level.Id, Level.Name, EArchTreeNodeType::Level, 1);
		LevelNode.bExpanded = true;
		LevelNode.ElementIndex = i;

		// Add rooms for this level
		FArchTreeNode RoomGroupNode(FString::Printf(TEXT("%s_rooms"), *Level.Id), TEXT("Rooms"), EArchTreeNodeType::RoomGroup, 2);
		int32 RoomCount = 0;
		for (const auto& RoomPair : Building.Rooms)
		{
			if (RoomPair.Value.Level == Level.Name || RoomPair.Value.Level == Level.Id)
			{
				FArchTreeNode RoomNode(RoomPair.Key, RoomPair.Value.Name, EArchTreeNodeType::Room, 3);
				RoomGroupNode.Children.Add(RoomNode);
				RoomCount++;
			}
		}
		if (RoomCount > 0)
		{
			RoomGroupNode.DisplayName = FString::Printf(TEXT("Rooms (%d)"), RoomCount);
			LevelNode.Children.Add(RoomGroupNode);
		}

		RootNode.Children.Add(LevelNode);
	}

	// Add walls group
	if (Building.ParametricWalls.Num() > 0)
	{
		FArchTreeNode WallGroupNode(TEXT("walls"), FString::Printf(TEXT("Walls (%d)"), Building.ParametricWalls.Num()), EArchTreeNodeType::WallGroup, 1);
		for (int32 i = 0; i < Building.ParametricWalls.Num(); ++i)
		{
			const FArchParametricWall& Wall = Building.ParametricWalls[i];
			FArchTreeNode WallNode(Wall.Id, FString::Printf(TEXT("Wall %d"), i + 1), EArchTreeNodeType::Wall, 2);
			WallNode.ElementIndex = i;
			WallGroupNode.Children.Add(WallNode);
		}
		RootNode.Children.Add(WallGroupNode);
	}

	// Add doors group
	if (Building.Doors.Num() > 0)
	{
		FArchTreeNode DoorGroupNode(TEXT("doors"), FString::Printf(TEXT("Doors (%d)"), Building.Doors.Num()), EArchTreeNodeType::DoorGroup, 1);
		for (int32 i = 0; i < Building.Doors.Num(); ++i)
		{
			FArchTreeNode DoorNode(FString::Printf(TEXT("door_%d"), i), FString::Printf(TEXT("Door %d"), i + 1), EArchTreeNodeType::Door, 2);
			DoorNode.ElementIndex = i;
			DoorGroupNode.Children.Add(DoorNode);
		}
		RootNode.Children.Add(DoorGroupNode);
	}

	// Add windows group
	if (Building.Windows.Num() > 0)
	{
		FArchTreeNode WindowGroupNode(TEXT("windows"), FString::Printf(TEXT("Windows (%d)"), Building.Windows.Num()), EArchTreeNodeType::WindowGroup, 1);
		for (int32 i = 0; i < Building.Windows.Num(); ++i)
		{
			FArchTreeNode WindowNode(FString::Printf(TEXT("window_%d"), i), FString::Printf(TEXT("Window %d"), i + 1), EArchTreeNodeType::Window, 2);
			WindowNode.ElementIndex = i;
			WindowGroupNode.Children.Add(WindowNode);
		}
		RootNode.Children.Add(WindowGroupNode);
	}

	// Add roofs group
	if (Building.Roofs.Num() > 0)
	{
		FArchTreeNode RoofGroupNode(TEXT("roofs"), FString::Printf(TEXT("Roofs (%d)"), Building.Roofs.Num()), EArchTreeNodeType::RoofGroup, 1);
		for (int32 i = 0; i < Building.Roofs.Num(); ++i)
		{
			const FArchRoof& Roof = Building.Roofs[i];
			FString RoofTypeName;
			switch (Roof.Type)
			{
				case EArchRoofType::Gable: RoofTypeName = TEXT("Gable"); break;
				case EArchRoofType::Hip: RoofTypeName = TEXT("Hip"); break;
				case EArchRoofType::Flat: RoofTypeName = TEXT("Flat"); break;
				case EArchRoofType::Shed: RoofTypeName = TEXT("Shed"); break;
				default: RoofTypeName = TEXT("Roof"); break;
			}
			FArchTreeNode RoofNode(Roof.Id, FString::Printf(TEXT("%s %d"), *RoofTypeName, i + 1), EArchTreeNodeType::Roof, 2);
			RoofNode.ElementIndex = i;
			RoofGroupNode.Children.Add(RoofNode);
		}
		RootNode.Children.Add(RoofGroupNode);
	}

	// Add stairs group
	if (Building.Stairs.Num() > 0)
	{
		FArchTreeNode StairGroupNode(TEXT("stairs"), FString::Printf(TEXT("Stairs (%d)"), Building.Stairs.Num()), EArchTreeNodeType::StairGroup, 1);
		for (int32 i = 0; i < Building.Stairs.Num(); ++i)
		{
			const FArchStair& Stair = Building.Stairs[i];
			FArchTreeNode StairNode(Stair.Id, FString::Printf(TEXT("%s to %s"), *Stair.FromLevel, *Stair.ToLevel), EArchTreeNodeType::Stair, 2);
			StairNode.ElementIndex = i;
			StairGroupNode.Children.Add(StairNode);
		}
		RootNode.Children.Add(StairGroupNode);
	}
}

void UArchProjectPanel::RebuildTreeUI()
{
	if (!TreeVerticalBox || !WidgetTree)
	{
		return;
	}

	// Clear existing UI
	TreeVerticalBox->ClearChildren();

	// Flatten tree respecting expanded state
	TArray<FArchTreeNode> FlatNodes;
	FlattenTree(RootNode, FlatNodes);

	// Create UI for each node
	for (const FArchTreeNode& Node : FlatNodes)
	{
		UWidget* RowWidget = CreateTreeRow(Node);
		if (RowWidget)
		{
			TreeVerticalBox->AddChildToVerticalBox(RowWidget);
		}
	}
}

void UArchProjectPanel::FlattenTree(const FArchTreeNode& Node, TArray<FArchTreeNode>& OutNodes)
{
	OutNodes.Add(Node);

	if (Node.bExpanded)
	{
		for (const FArchTreeNode& Child : Node.Children)
		{
			FlattenTree(Child, OutNodes);
		}
	}
}

UWidget* UArchProjectPanel::CreateTreeRow(const FArchTreeNode& Node)
{
	// Create horizontal box for the row
	UHorizontalBox* RowBox = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());

	// Add indent spacer
	if (Node.IndentLevel > 0)
	{
		USpacer* IndentSpacer = WidgetTree->ConstructWidget<USpacer>(USpacer::StaticClass());
		IndentSpacer->SetSize(FVector2D(IndentWidth * Node.IndentLevel, 1));
		RowBox->AddChildToHorizontalBox(IndentSpacer);
	}

	// Add expand/collapse indicator if has children
	UTextBlock* ExpandIndicator = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	if (Node.Children.Num() > 0)
	{
		ExpandIndicator->SetText(FText::FromString(Node.bExpanded ? TEXT("-") : TEXT("+")));
	}
	else
	{
		ExpandIndicator->SetText(FText::FromString(TEXT(" ")));
	}
	ExpandIndicator->SetColorAndOpacity(TextColor);
	ExpandIndicator->SetMinDesiredWidth(16.0f);
	RowBox->AddChildToHorizontalBox(ExpandIndicator);

	// Add icon based on type
	UTextBlock* IconText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	FString IconStr;
	switch (Node.NodeType)
	{
		case EArchTreeNodeType::Building: IconStr = TEXT("[B]"); break;
		case EArchTreeNodeType::Level: IconStr = TEXT("[L]"); break;
		case EArchTreeNodeType::RoomGroup:
		case EArchTreeNodeType::Room: IconStr = TEXT("[R]"); break;
		case EArchTreeNodeType::WallGroup:
		case EArchTreeNodeType::Wall: IconStr = TEXT("[W]"); break;
		case EArchTreeNodeType::DoorGroup:
		case EArchTreeNodeType::Door: IconStr = TEXT("[D]"); break;
		case EArchTreeNodeType::WindowGroup:
		case EArchTreeNodeType::Window: IconStr = TEXT("[N]"); break;
		case EArchTreeNodeType::RoofGroup:
		case EArchTreeNodeType::Roof: IconStr = TEXT("[^]"); break;
		case EArchTreeNodeType::StairGroup:
		case EArchTreeNodeType::Stair: IconStr = TEXT("[S]"); break;
		default: IconStr = TEXT("[ ]"); break;
	}
	IconText->SetText(FText::FromString(IconStr));
	IconText->SetColorAndOpacity(FLinearColor(0.6f, 0.6f, 0.6f, 1.0f));
	UHorizontalBoxSlot* IconSlot = RowBox->AddChildToHorizontalBox(IconText);
	IconSlot->SetPadding(FMargin(0, 0, 4, 0));

	// Add name text
	UTextBlock* NameText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	NameText->SetText(FText::FromString(Node.DisplayName));
	NameText->SetColorAndOpacity(Node.Id == SelectedNodeId ? SelectedColor : TextColor);
	UHorizontalBoxSlot* NameSlot = RowBox->AddChildToHorizontalBox(NameText);
	NameSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Add visibility toggle
	UTextBlock* VisibilityText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	VisibilityText->SetText(FText::FromString(Node.bVisible ? TEXT("o") : TEXT("-")));
	VisibilityText->SetColorAndOpacity(FLinearColor(0.5f, 0.5f, 0.5f, 1.0f));
	RowBox->AddChildToHorizontalBox(VisibilityText);

	// Wrap in a border for hover/selection highlighting
	UBorder* RowBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
	if (Node.Id == SelectedNodeId)
	{
		RowBorder->SetBrushColor(SelectedColor);
	}
	else
	{
		RowBorder->SetBrushColor(FLinearColor(0, 0, 0, 0));
	}
	RowBorder->SetPadding(FMargin(2, 1));
	RowBorder->AddChild(RowBox);

	return RowBorder;
}

FArchTreeNode* UArchProjectPanel::FindNode(FArchTreeNode& StartNode, const FString& NodeId)
{
	if (StartNode.Id == NodeId)
	{
		return &StartNode;
	}

	for (FArchTreeNode& Child : StartNode.Children)
	{
		FArchTreeNode* Found = FindNode(Child, NodeId);
		if (Found)
		{
			return Found;
		}
	}

	return nullptr;
}

void UArchProjectPanel::ToggleNodeExpanded(const FString& NodeId)
{
	FArchTreeNode* Node = FindNode(RootNode, NodeId);
	if (Node)
	{
		Node->bExpanded = !Node->bExpanded;
		RebuildTreeUI();
	}
}

void UArchProjectPanel::ToggleNodeVisibility(const FString& NodeId)
{
	FArchTreeNode* Node = FindNode(RootNode, NodeId);
	if (Node)
	{
		Node->bVisible = !Node->bVisible;
		RebuildTreeUI();
		// TODO: Actually hide/show the elements in the 3D view
	}
}

void UArchProjectPanel::ExpandAll()
{
	TArray<FArchTreeNode*> NodesToProcess;
	NodesToProcess.Add(&RootNode);

	while (NodesToProcess.Num() > 0)
	{
		FArchTreeNode* Node = NodesToProcess.Pop();
		Node->bExpanded = true;
		for (FArchTreeNode& Child : Node->Children)
		{
			NodesToProcess.Add(&Child);
		}
	}

	RebuildTreeUI();
}

void UArchProjectPanel::CollapseAll()
{
	TArray<FArchTreeNode*> NodesToProcess;
	NodesToProcess.Add(&RootNode);

	while (NodesToProcess.Num() > 0)
	{
		FArchTreeNode* Node = NodesToProcess.Pop();
		if (Node != &RootNode)  // Keep root expanded
		{
			Node->bExpanded = false;
		}
		for (FArchTreeNode& Child : Node->Children)
		{
			NodesToProcess.Add(&Child);
		}
	}

	RebuildTreeUI();
}

void UArchProjectPanel::SelectNode(const FString& NodeId)
{
	SelectedNodeId = NodeId;
	RebuildTreeUI();

	// TODO: Select corresponding element in the 3D view via SelectionManager
}

void UArchProjectPanel::OnNodeClicked(const FString& NodeId)
{
	FArchTreeNode* Node = FindNode(RootNode, NodeId);
	if (Node)
	{
		if (Node->Children.Num() > 0)
		{
			ToggleNodeExpanded(NodeId);
		}
		SelectNode(NodeId);
	}
}

void UArchProjectPanel::OnVisibilityToggled(const FString& NodeId)
{
	ToggleNodeVisibility(NodeId);
}

bool UArchProjectPanel::CheckBuildingDataChanged()
{
	if (!BoundBuildingActor)
	{
		return false;
	}

	// Simple hash based on element counts
	const FArchBuilding& Building = BoundBuildingActor->BuildingData;
	int32 Hash = Building.Levels.Num() * 1000 +
	             Building.Rooms.Num() * 100 +
	             Building.ParametricWalls.Num() * 10 +
	             Building.Doors.Num() +
	             Building.Windows.Num();

	if (Hash != LastBuildingDataHash)
	{
		LastBuildingDataHash = Hash;
		return true;
	}

	return false;
}
