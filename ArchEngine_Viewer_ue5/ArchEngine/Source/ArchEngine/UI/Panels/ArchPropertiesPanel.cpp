// ArchPropertiesPanel.cpp - Properties panel implementation

#include "UI/Panels/ArchPropertiesPanel.h"
#include "Framework/ArchSelectionManager.h"
#include "Actors/ArchBuildingActor.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/ScrollBox.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/Spacer.h"
#include "Blueprint/WidgetTree.h"
#include "Kismet/GameplayStatics.h"

void UArchPropertiesPanel::NativeConstruct()
{
	Super::NativeConstruct();
	BuildLayout();
}

void UArchPropertiesPanel::NativeDestruct()
{
	if (BoundSelectionManager)
	{
		BoundSelectionManager->OnSelectionChanged.RemoveDynamic(this, &UArchPropertiesPanel::OnSelectionChanged);
	}
	Super::NativeDestruct();
}

void UArchPropertiesPanel::BuildLayout()
{
	// Create background border
	PanelBackground = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName("PanelBackground"));
	PanelBackground->SetBrushColor(BackgroundColor);
	PanelBackground->SetPadding(FMargin(PanelPadding));
	WidgetTree->RootWidget = PanelBackground;

	// Create scroll box for content
	ContentScrollBox = WidgetTree->ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), FName("ContentScrollBox"));
	PanelBackground->AddChild(ContentScrollBox);

	// Create content vertical box
	ContentVerticalBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName("ContentVerticalBox"));
	ContentScrollBox->AddChild(ContentVerticalBox);

	// Add title
	TitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName("TitleText"));
	TitleText->SetText(FText::FromString(TEXT("PROPERTIES")));
	TitleText->SetColorAndOpacity(TextColor);
	FSlateFontInfo TitleFont = TitleText->GetFont();
	TitleFont.Size = 14;
	TitleText->SetFont(TitleFont);
	UVerticalBoxSlot* TitleSlot = ContentVerticalBox->AddChildToVerticalBox(TitleText);
	TitleSlot->SetPadding(FMargin(0, 0, 0, 8));

	// Add "No Selection" text
	NoSelectionText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), FName("NoSelectionText"));
	NoSelectionText->SetText(FText::FromString(TEXT("No element selected")));
	NoSelectionText->SetColorAndOpacity(LabelColor);
	ContentVerticalBox->AddChildToVerticalBox(NoSelectionText);
}

void UArchPropertiesPanel::BindToSelectionManager(UArchSelectionManager* SelectionManager)
{
	if (BoundSelectionManager)
	{
		BoundSelectionManager->OnSelectionChanged.RemoveDynamic(this, &UArchPropertiesPanel::OnSelectionChanged);
	}

	BoundSelectionManager = SelectionManager;

	if (BoundSelectionManager)
	{
		BoundSelectionManager->OnSelectionChanged.AddDynamic(this, &UArchPropertiesPanel::OnSelectionChanged);
	}
}

void UArchPropertiesPanel::OnSelectionChanged(const TArray<FArchSelectionInfo>& NewSelection)
{
	UpdateFromSelection(NewSelection);
}

void UArchPropertiesPanel::UpdateFromSelection(const TArray<FArchSelectionInfo>& Selection)
{
	ClearProperties();

	if (Selection.Num() == 0)
	{
		if (NoSelectionText)
		{
			NoSelectionText->SetVisibility(ESlateVisibility::Visible);
		}
		return;
	}

	if (NoSelectionText)
	{
		NoSelectionText->SetVisibility(ESlateVisibility::Collapsed);
	}

	// Get the primary selection
	const FArchSelectionInfo& PrimarySelection = Selection[0];

	// Show selection count if multi-select
	if (Selection.Num() > 1)
	{
		AddPropertyRow(TEXT("Selected"), FString::Printf(TEXT("%d elements"), Selection.Num()));
		AddSpacer();
	}

	// Try to get building data from the selected actor
	AArchBuildingActor* BuildingActor = Cast<AArchBuildingActor>(PrimarySelection.Actor);
	if (!BuildingActor)
	{
		// Maybe it's a component of the building actor
		if (PrimarySelection.Actor)
		{
			TArray<AActor*> FoundActors;
			UGameplayStatics::GetAllActorsOfClass(GetWorld(), AArchBuildingActor::StaticClass(), FoundActors);
			if (FoundActors.Num() > 0)
			{
				BuildingActor = Cast<AArchBuildingActor>(FoundActors[0]);
			}
		}
	}

	// Show basic actor info
	AddSectionHeader(TEXT("Selection"));
	if (PrimarySelection.Actor)
	{
		AddPropertyRow(TEXT("Actor"), PrimarySelection.Actor->GetName());
	}
	if (!PrimarySelection.ElementType.IsEmpty())
	{
		AddPropertyRow(TEXT("Type"), PrimarySelection.ElementType);
	}
	if (!PrimarySelection.ElementId.IsEmpty())
	{
		AddPropertyRow(TEXT("ID"), PrimarySelection.ElementId);
	}

	// If we have building data, try to show more details
	if (BuildingActor)
	{
		const FArchBuilding& Building = BuildingActor->BuildingData;

		AddSpacer();
		AddSectionHeader(TEXT("Building"));
		AddPropertyRow(TEXT("Name"), Building.Name);
		AddPropertyRow(TEXT("Size"), FString::Printf(TEXT("%.0f x %.0f"), Building.Width, Building.Depth));
		AddPropertyRow(TEXT("Area"), FString::Printf(TEXT("%.0f sq ft"), Building.SqFt));

		// Show level info
		if (Building.Levels.Num() > 0)
		{
			AddSpacer();
			AddSectionHeader(TEXT("Levels"));
			for (const FArchLevel& Level : Building.Levels)
			{
				AddPropertyRow(Level.Name, FString::Printf(TEXT("%.0f mm"), Level.Elevation));
			}
		}

		// Show room count
		if (Building.Rooms.Num() > 0)
		{
			AddSpacer();
			AddSectionHeader(TEXT("Rooms"));
			AddPropertyRow(TEXT("Count"), FString::FromInt(Building.Rooms.Num()));
		}

		// Show wall types
		if (Building.WallTypes.Num() > 0)
		{
			AddSpacer();
			AddSectionHeader(TEXT("Wall Types"));
			for (const FArchWallType& WallType : Building.WallTypes)
			{
				AddPropertyRow(WallType.Name, FString::Printf(TEXT("R-%.1f"), WallType.GetTotalRValue()));
			}
		}
	}

	// Show component info if available
	if (PrimarySelection.Component)
	{
		AddSpacer();
		AddSectionHeader(TEXT("Component"));
		AddPropertyRow(TEXT("Name"), PrimarySelection.Component->GetName());

		if (PrimarySelection.FaceIndex >= 0)
		{
			AddPropertyRow(TEXT("Face"), FString::FromInt(PrimarySelection.FaceIndex));
		}
	}
}

void UArchPropertiesPanel::ClearProperties()
{
	if (!ContentVerticalBox)
	{
		return;
	}

	// Remove all children except title and no-selection text
	TArray<UWidget*> Children = ContentVerticalBox->GetAllChildren();
	for (UWidget* Child : Children)
	{
		if (Child != TitleText && Child != NoSelectionText)
		{
			Child->RemoveFromParent();
		}
	}
}

void UArchPropertiesPanel::AddPropertyRow(const FString& Label, const FString& Value)
{
	if (!ContentVerticalBox || !WidgetTree)
	{
		return;
	}

	// Create horizontal box for the row
	UHorizontalBox* RowBox = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());

	// Label
	UTextBlock* LabelText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	LabelText->SetText(FText::FromString(Label));
	LabelText->SetColorAndOpacity(LabelColor);
	UHorizontalBoxSlot* LabelSlot = RowBox->AddChildToHorizontalBox(LabelText);
	LabelSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	LabelSlot->SetHorizontalAlignment(HAlign_Left);

	// Value
	UTextBlock* ValueText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	ValueText->SetText(FText::FromString(Value));
	ValueText->SetColorAndOpacity(TextColor);
	UHorizontalBoxSlot* ValueSlot = RowBox->AddChildToHorizontalBox(ValueText);
	ValueSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
	ValueSlot->SetHorizontalAlignment(HAlign_Right);

	// Add to content
	UVerticalBoxSlot* RowSlot = ContentVerticalBox->AddChildToVerticalBox(RowBox);
	RowSlot->SetPadding(FMargin(0, RowSpacing / 2));
}

void UArchPropertiesPanel::AddSectionHeader(const FString& SectionName)
{
	if (!ContentVerticalBox || !WidgetTree)
	{
		return;
	}

	// Create header with border
	UBorder* HeaderBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
	HeaderBorder->SetBrushColor(HeaderColor);
	HeaderBorder->SetPadding(FMargin(4, 2));

	UTextBlock* HeaderText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	HeaderText->SetText(FText::FromString(SectionName.ToUpper()));
	HeaderText->SetColorAndOpacity(TextColor);
	FSlateFontInfo HeaderFont = HeaderText->GetFont();
	HeaderFont.Size = 10;
	HeaderText->SetFont(HeaderFont);

	HeaderBorder->AddChild(HeaderText);

	UVerticalBoxSlot* HeaderSlot = ContentVerticalBox->AddChildToVerticalBox(HeaderBorder);
	HeaderSlot->SetPadding(FMargin(0, RowSpacing, 0, RowSpacing / 2));
}

void UArchPropertiesPanel::AddSpacer(float Height)
{
	if (!ContentVerticalBox || !WidgetTree)
	{
		return;
	}

	USpacer* SpacerWidget = WidgetTree->ConstructWidget<USpacer>(USpacer::StaticClass());
	SpacerWidget->SetSize(FVector2D(1, Height));
	ContentVerticalBox->AddChildToVerticalBox(SpacerWidget);
}

void UArchPropertiesPanel::PopulateWallTypeProperties(const FArchWallType& WallType)
{
	AddSectionHeader(TEXT("Wall Type"));
	AddPropertyRow(TEXT("Name"), WallType.Name);
	AddPropertyRow(TEXT("ID"), WallType.Id);
	AddPropertyRow(TEXT("Thickness"), FString::Printf(TEXT("%.0f mm"), WallType.GetTotalThickness()));
	AddPropertyRow(TEXT("R-Value"), FString::Printf(TEXT("R-%.1f"), WallType.GetTotalRValue()));
	AddPropertyRow(TEXT("Layers"), FString::FromInt(WallType.Layers.Num()));

	if (WallType.Layers.Num() > 0)
	{
		AddSpacer(4.0f);
		for (const FArchWallLayer& Layer : WallType.Layers)
		{
			AddPropertyRow(Layer.Name, FString::Printf(TEXT("%.0f mm"), Layer.Thickness));
		}
	}
}

void UArchPropertiesPanel::PopulateDoorProperties(const FArchDoor& Door)
{
	AddSectionHeader(TEXT("Door"));
	AddPropertyRow(TEXT("Width"), FString::Printf(TEXT("%.0f cm"), Door.Width));
	AddPropertyRow(TEXT("Height"), FString::Printf(TEXT("%.0f cm"), Door.Height));
	AddPropertyRow(TEXT("Wall Index"), FString::FromInt(Door.WallIndex));
	AddPropertyRow(TEXT("Offset"), FString::Printf(TEXT("%.0f cm"), Door.Offset));

	// Door type
	FString TypeStr;
	switch (Door.Type)
	{
		case EArchDoorType::Swing: TypeStr = TEXT("Swing"); break;
		case EArchDoorType::Entry: TypeStr = TEXT("Entry"); break;
		case EArchDoorType::Pocket: TypeStr = TEXT("Pocket"); break;
		case EArchDoorType::Sliding: TypeStr = TEXT("Sliding"); break;
		case EArchDoorType::Bifold: TypeStr = TEXT("Bifold"); break;
		case EArchDoorType::French: TypeStr = TEXT("French"); break;
		case EArchDoorType::Barn: TypeStr = TEXT("Barn"); break;
		default: TypeStr = TEXT("Unknown"); break;
	}
	AddPropertyRow(TEXT("Type"), TypeStr);
}

void UArchPropertiesPanel::PopulateWindowProperties(const FArchWindow& Window)
{
	AddSectionHeader(TEXT("Window"));
	AddPropertyRow(TEXT("Width"), FString::Printf(TEXT("%.0f cm"), Window.Width));
	AddPropertyRow(TEXT("Height"), FString::Printf(TEXT("%.0f cm"), Window.Height));
	AddPropertyRow(TEXT("Sill Height"), FString::Printf(TEXT("%.0f cm"), Window.SillHeight));
	AddPropertyRow(TEXT("Wall Index"), FString::FromInt(Window.WallIndex));

	// Window type
	FString TypeStr;
	switch (Window.Type)
	{
		case EArchWindowType::Fixed: TypeStr = TEXT("Fixed"); break;
		case EArchWindowType::Casement: TypeStr = TEXT("Casement"); break;
		case EArchWindowType::DoubleHung: TypeStr = TEXT("Double Hung"); break;
		case EArchWindowType::Sliding: TypeStr = TEXT("Sliding"); break;
		case EArchWindowType::Awning: TypeStr = TEXT("Awning"); break;
		default: TypeStr = TEXT("Unknown"); break;
	}
	AddPropertyRow(TEXT("Type"), TypeStr);
}

void UArchPropertiesPanel::PopulateRoomProperties(const FArchRoom& Room)
{
	AddSectionHeader(TEXT("Room"));
	AddPropertyRow(TEXT("Name"), Room.Name);
	AddPropertyRow(TEXT("Type"), Room.RoomType);
	AddPropertyRow(TEXT("Level"), Room.Level);
	AddPropertyRow(TEXT("Area"), FString::Printf(TEXT("%.0f sq units"), Room.Area));

	// Room zone
	FString ZoneStr;
	switch (Room.Zone)
	{
		case EArchRoomZone::Public: ZoneStr = TEXT("Public"); break;
		case EArchRoomZone::Private: ZoneStr = TEXT("Private"); break;
		case EArchRoomZone::Service: ZoneStr = TEXT("Service"); break;
		case EArchRoomZone::Circulation: ZoneStr = TEXT("Circulation"); break;
		default: ZoneStr = TEXT("Unknown"); break;
	}
	AddPropertyRow(TEXT("Zone"), ZoneStr);
}

void UArchPropertiesPanel::PopulateLevelProperties(const FArchLevel& Level)
{
	AddSectionHeader(TEXT("Level"));
	AddPropertyRow(TEXT("Name"), Level.Name);
	AddPropertyRow(TEXT("Elevation"), FString::Printf(TEXT("%.0f mm"), Level.Elevation));
	AddPropertyRow(TEXT("Floor Height"), FString::Printf(TEXT("%.0f mm"), Level.FloorToFloorHeight));
}
