// ArchMainWidget.cpp - Root UI container implementation

#include "UI/ArchMainWidget.h"
#include "UI/Panels/ArchPropertiesPanel.h"
#include "UI/Panels/ArchProjectPanel.h"
#include "UI/Panels/ArchViewStrip.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/SizeBox.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/Border.h"
#include "Blueprint/WidgetTree.h"
#include "Engine/Engine.h"

void UArchMainWidget::NativeConstruct()
{
	Super::NativeConstruct();

	BuildLayout();
	CreatePanels();
	UpdatePanelSizes();
}

void UArchMainWidget::NativeDestruct()
{
	Super::NativeDestruct();
}

void UArchMainWidget::BuildLayout()
{
	// Get or create root canvas
	UCanvasPanel* RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), FName("RootCanvas"));
	WidgetTree->RootWidget = RootCanvas;

	// Create main vertical box (contains: main area + bottom strip)
	RootVerticalBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), FName("RootVerticalBox"));
	UCanvasPanelSlot* VBoxSlot = RootCanvas->AddChildToCanvas(RootVerticalBox);
	VBoxSlot->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
	VBoxSlot->SetOffsets(FMargin(0.0f));

	// Create main horizontal box (contains: left panel + viewport space + right panel)
	MainHorizontalBox = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), FName("MainHorizontalBox"));
	UVerticalBoxSlot* HBoxSlot = RootVerticalBox->AddChildToVerticalBox(MainHorizontalBox);
	HBoxSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Left panel container
	LeftPanelContainer = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName("LeftPanelContainer"));
	LeftPanelContainer->SetMinDesiredWidth(MinPanelWidth);
	UHorizontalBoxSlot* LeftSlot = MainHorizontalBox->AddChildToHorizontalBox(LeftPanelContainer);
	LeftSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
	LeftSlot->SetHorizontalAlignment(HAlign_Fill);
	LeftSlot->SetVerticalAlignment(VAlign_Fill);

	// Center spacer (transparent - shows the 3D viewport behind)
	UOverlay* CenterSpacer = WidgetTree->ConstructWidget<UOverlay>(UOverlay::StaticClass(), FName("CenterSpacer"));
	UHorizontalBoxSlot* CenterSlot = MainHorizontalBox->AddChildToHorizontalBox(CenterSpacer);
	CenterSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));

	// Right panel container
	RightPanelContainer = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName("RightPanelContainer"));
	RightPanelContainer->SetMinDesiredWidth(MinPanelWidth);
	UHorizontalBoxSlot* RightSlot = MainHorizontalBox->AddChildToHorizontalBox(RightPanelContainer);
	RightSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
	RightSlot->SetHorizontalAlignment(HAlign_Fill);
	RightSlot->SetVerticalAlignment(VAlign_Fill);

	// Bottom panel container (view strip)
	BottomPanelContainer = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), FName("BottomPanelContainer"));
	BottomPanelContainer->SetMinDesiredHeight(MinPanelHeight);
	UVerticalBoxSlot* BottomSlot = RootVerticalBox->AddChildToVerticalBox(BottomPanelContainer);
	BottomSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
	BottomSlot->SetHorizontalAlignment(HAlign_Fill);
}

void UArchMainWidget::CreatePanels()
{
	// Create Properties Panel (left)
	if (PropertiesPanelClass)
	{
		PropertiesPanel = CreateWidget<UArchPropertiesPanel>(this, PropertiesPanelClass);
	}
	else
	{
		PropertiesPanel = CreateWidget<UArchPropertiesPanel>(this, UArchPropertiesPanel::StaticClass());
	}

	if (PropertiesPanel && LeftPanelContainer)
	{
		LeftPanelContainer->AddChild(PropertiesPanel);
	}

	// Create Project Panel (right)
	if (ProjectPanelClass)
	{
		ProjectPanel = CreateWidget<UArchProjectPanel>(this, ProjectPanelClass);
	}
	else
	{
		ProjectPanel = CreateWidget<UArchProjectPanel>(this, UArchProjectPanel::StaticClass());
	}

	if (ProjectPanel && RightPanelContainer)
	{
		RightPanelContainer->AddChild(ProjectPanel);
	}

	// Create View Strip (bottom)
	if (ViewStripClass)
	{
		ViewStrip = CreateWidget<UArchViewStrip>(this, ViewStripClass);
	}
	else
	{
		ViewStrip = CreateWidget<UArchViewStrip>(this, UArchViewStrip::StaticClass());
	}

	if (ViewStrip && BottomPanelContainer)
	{
		BottomPanelContainer->AddChild(ViewStrip);
	}
}

void UArchMainWidget::UpdatePanelSizes()
{
	// Get viewport size
	if (GEngine && GEngine->GameViewport)
	{
		FVector2D ViewportSize;
		GEngine->GameViewport->GetViewportSize(ViewportSize);
		CachedViewportSize = ViewportSize;

		// Calculate panel sizes based on ratios
		float LeftWidth = FMath::Max(ViewportSize.X * LeftPanelWidthRatio, MinPanelWidth);
		float RightWidth = FMath::Max(ViewportSize.X * RightPanelWidthRatio, MinPanelWidth);
		float BottomHeight = FMath::Max(ViewportSize.Y * BottomPanelHeightRatio, MinPanelHeight);

		// Apply sizes
		if (LeftPanelContainer)
		{
			LeftPanelContainer->SetWidthOverride(LeftWidth);
		}

		if (RightPanelContainer)
		{
			RightPanelContainer->SetWidthOverride(RightWidth);
		}

		if (BottomPanelContainer)
		{
			BottomPanelContainer->SetHeightOverride(BottomHeight);
		}
	}
}

void UArchMainWidget::SetPropertiesPanelVisible(bool bVisible)
{
	if (LeftPanelContainer)
	{
		LeftPanelContainer->SetVisibility(bVisible ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	}
}

void UArchMainWidget::SetProjectPanelVisible(bool bVisible)
{
	if (RightPanelContainer)
	{
		RightPanelContainer->SetVisibility(bVisible ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	}
}

void UArchMainWidget::SetViewStripVisible(bool bVisible)
{
	if (BottomPanelContainer)
	{
		BottomPanelContainer->SetVisibility(bVisible ? ESlateVisibility::Visible : ESlateVisibility::Collapsed);
	}
}

void UArchMainWidget::TogglePropertiesPanel()
{
	if (LeftPanelContainer)
	{
		bool bCurrentlyVisible = LeftPanelContainer->GetVisibility() == ESlateVisibility::Visible;
		SetPropertiesPanelVisible(!bCurrentlyVisible);
	}
}

void UArchMainWidget::ToggleProjectPanel()
{
	if (RightPanelContainer)
	{
		bool bCurrentlyVisible = RightPanelContainer->GetVisibility() == ESlateVisibility::Visible;
		SetProjectPanelVisible(!bCurrentlyVisible);
	}
}

void UArchMainWidget::ToggleViewStrip()
{
	if (BottomPanelContainer)
	{
		bool bCurrentlyVisible = BottomPanelContainer->GetVisibility() == ESlateVisibility::Visible;
		SetViewStripVisible(!bCurrentlyVisible);
	}
}

void UArchMainWidget::ResetLayout()
{
	// Reset to default ratios
	LeftPanelWidthRatio = 0.2f;
	RightPanelWidthRatio = 0.2f;
	BottomPanelHeightRatio = 0.15f;

	// Show all panels
	SetPropertiesPanelVisible(true);
	SetProjectPanelVisible(true);
	SetViewStripVisible(true);

	// Update sizes
	UpdatePanelSizes();
}
