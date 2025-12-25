// ArchViewStrip.cpp - View strip implementation

#include "UI/Panels/ArchViewStrip.h"
#include "Actors/ArchBuildingActor.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/Border.h"
#include "Components/TextBlock.h"
#include "Components/Image.h"
#include "Components/Spacer.h"
#include "Components/SizeBox.h"
#include "Blueprint/WidgetTree.h"

void UArchViewStrip::NativeConstruct()
{
	Super::NativeConstruct();

	InitializeDefaultPresets();
	BuildLayout();
}

void UArchViewStrip::InitializeDefaultPresets()
{
	if (ViewPresets.Num() == 0)
	{
		// Create default visualization mode presets
		ViewPresets.Add(FArchViewPreset(
			TEXT("Structural"),
			EVisualizationMode::Structural,
			FLinearColor(0.2f, 0.4f, 0.8f, 1.0f),
			TEXT("Show structural stress visualization")
		));

		ViewPresets.Add(FArchViewPreset(
			TEXT("Thermal"),
			EVisualizationMode::Thermal,
			FLinearColor(1.0f, 0.3f, 0.1f, 1.0f),
			TEXT("Show thermal R-values and heat flow")
		));

		ViewPresets.Add(FArchViewPreset(
			TEXT("Lighting"),
			EVisualizationMode::Lighting,
			FLinearColor(1.0f, 0.9f, 0.5f, 1.0f),
			TEXT("Show daylight analysis")
		));

		ViewPresets.Add(FArchViewPreset(
			TEXT("Acoustic"),
			EVisualizationMode::Acoustic,
			FLinearColor(0.5f, 0.8f, 0.3f, 1.0f),
			TEXT("Show sound transmission analysis")
		));

		ViewPresets.Add(FArchViewPreset(
			TEXT("Material"),
			EVisualizationMode::Material,
			FLinearColor(0.8f, 0.6f, 0.4f, 1.0f),
			TEXT("Show material types and colors")
		));
	}
}

void UArchViewStrip::BuildLayout()
{
	// Create background border
	StripBackground = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), FName("StripBackground"));
	StripBackground->SetBrushColor(BackgroundColor);
	StripBackground->SetPadding(FMargin(PreviewSpacing));
	WidgetTree->RootWidget = StripBackground;

	// Create horizontal container for previews
	PreviewContainer = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName("PreviewContainer"));
	StripBackground->AddChild(PreviewContainer);

	// Create preview panels for each preset
	PreviewPanels.Empty();
	for (int32 i = 0; i < ViewPresets.Num(); ++i)
	{
		UWidget* PreviewPanel = CreatePreviewPanel(ViewPresets[i], i);
		if (PreviewPanel)
		{
			UHorizontalBoxSlot* PanelSlot = PreviewContainer->AddChildToHorizontalBox(PreviewPanel);
			PanelSlot->SetPadding(FMargin(PreviewSpacing / 2, 0));
			PanelSlot->SetHorizontalAlignment(HAlign_Center);
			PanelSlot->SetVerticalAlignment(VAlign_Fill);
		}
	}

	// Add spacer to push previews to left
	USpacer* EndSpacer = WidgetTree->ConstructWidget<USpacer>(USpacer::StaticClass(), FName("EndSpacer"));
	UHorizontalBoxSlot* SpacerSlot = PreviewContainer->AddChildToHorizontalBox(EndSpacer);
	SpacerSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	UpdateSelectionVisuals();
}

UWidget* UArchViewStrip::CreatePreviewPanel(const FArchViewPreset& Preset, int32 Index)
{
	// Create outer border (for selection indicator)
	UBorder* OuterBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
	OuterBorder->SetPadding(FMargin(2.0f));
	PreviewPanels.Add(OuterBorder);

	// Create inner container
	UVerticalBox* InnerVBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
	OuterBorder->AddChild(InnerVBox);

	// Create preview area (colored box representing the view mode)
	UBorder* PreviewArea = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
	PreviewArea->SetBrushColor(Preset.TintColor * 0.5f);  // Darker version of tint

	// Size box for preview
	USizeBox* PreviewSizeBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
	PreviewSizeBox->SetWidthOverride(PreviewWidth);
	PreviewSizeBox->SetHeightOverride(PreviewHeight);
	PreviewSizeBox->AddChild(PreviewArea);

	// Add content to preview area
	UVerticalBox* PreviewContent = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass());
	PreviewArea->SetPadding(FMargin(8.0f));
	PreviewArea->AddChild(PreviewContent);

	// Mode icon/indicator (simple colored box for now)
	UBorder* ModeIndicator = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass());
	ModeIndicator->SetBrushColor(Preset.TintColor);

	USizeBox* IndicatorSize = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass());
	IndicatorSize->SetWidthOverride(40.0f);
	IndicatorSize->SetHeightOverride(40.0f);
	IndicatorSize->AddChild(ModeIndicator);

	UVerticalBoxSlot* IndicatorSlot = PreviewContent->AddChildToVerticalBox(IndicatorSize);
	IndicatorSlot->SetHorizontalAlignment(HAlign_Center);
	IndicatorSlot->SetVerticalAlignment(VAlign_Center);
	IndicatorSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Add size box to inner vbox
	UVerticalBoxSlot* PreviewSlot = InnerVBox->AddChildToVerticalBox(PreviewSizeBox);
	PreviewSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Add label below preview
	UTextBlock* LabelText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
	LabelText->SetText(FText::FromString(Preset.Name));
	LabelText->SetColorAndOpacity(TextColor);
	LabelText->SetJustification(ETextJustify::Center);
	FSlateFontInfo LabelFont = LabelText->GetFont();
	LabelFont.Size = 10;
	LabelText->SetFont(LabelFont);

	UVerticalBoxSlot* LabelSlot = InnerVBox->AddChildToVerticalBox(LabelText);
	LabelSlot->SetPadding(FMargin(0, 4, 0, 0));
	LabelSlot->SetHorizontalAlignment(HAlign_Center);

	return OuterBorder;
}

void UArchViewStrip::SetViewPresets(const TArray<FArchViewPreset>& Presets)
{
	ViewPresets = Presets;

	// Rebuild UI
	if (PreviewContainer)
	{
		PreviewContainer->ClearChildren();
		PreviewPanels.Empty();

		for (int32 i = 0; i < ViewPresets.Num(); ++i)
		{
			UWidget* PreviewPanel = CreatePreviewPanel(ViewPresets[i], i);
			if (PreviewPanel)
			{
				UHorizontalBoxSlot* PanelSlot = PreviewContainer->AddChildToHorizontalBox(PreviewPanel);
				PanelSlot->SetPadding(FMargin(PreviewSpacing / 2, 0));
			}
		}

		UpdateSelectionVisuals();
	}
}

void UArchViewStrip::SelectPreset(int32 PresetIndex)
{
	if (PresetIndex < 0 || PresetIndex >= ViewPresets.Num())
	{
		return;
	}

	SelectedPresetIndex = PresetIndex;
	UpdateSelectionVisuals();

	// Apply visualization mode to building actor
	if (BoundBuildingActor)
	{
		BoundBuildingActor->SetVisualizationMode(ViewPresets[PresetIndex].VisualizationMode);
	}

	// Broadcast event
	OnViewPresetSelected.Broadcast(ViewPresets[PresetIndex]);
}

void UArchViewStrip::BindToBuildingActor(AArchBuildingActor* BuildingActor)
{
	BoundBuildingActor = BuildingActor;

	// Set initial visualization mode
	if (BoundBuildingActor && ViewPresets.IsValidIndex(SelectedPresetIndex))
	{
		BoundBuildingActor->SetVisualizationMode(ViewPresets[SelectedPresetIndex].VisualizationMode);
	}
}

void UArchViewStrip::UpdateSelectionVisuals()
{
	for (int32 i = 0; i < PreviewPanels.Num(); ++i)
	{
		UBorder* Panel = PreviewPanels[i];
		if (Panel)
		{
			if (i == SelectedPresetIndex)
			{
				Panel->SetBrushColor(SelectedBorderColor);
			}
			else
			{
				Panel->SetBrushColor(FLinearColor(0.2f, 0.2f, 0.2f, 1.0f));
			}
		}
	}
}
