// ArchSelectionManager.cpp - Selection manager implementation

#include "Framework/ArchSelectionManager.h"
#include "GameFramework/PlayerController.h"
#include "Components/PrimitiveComponent.h"

UArchSelectionManager::UArchSelectionManager()
{
}

void UArchSelectionManager::Initialize(APlayerController* InOwnerController)
{
	OwnerController = InOwnerController;
}

void UArchSelectionManager::SelectActor(AActor* Actor, UPrimitiveComponent* Component, int32 FaceIndex, bool bAddToSelection)
{
	if (!Actor)
	{
		if (!bAddToSelection)
		{
			ClearSelection();
		}
		return;
	}

	FArchSelectionInfo NewInfo = CreateSelectionInfo(Actor, Component, FaceIndex);

	if (!bAddToSelection)
	{
		// Clear existing selection
		for (const FArchSelectionInfo& Info : Selection)
		{
			ApplySelectionHighlight(Info, false);
		}
		Selection.Empty();
	}

	// Check if already selected
	bool bAlreadySelected = false;
	for (int32 i = Selection.Num() - 1; i >= 0; --i)
	{
		if (Selection[i] == NewInfo)
		{
			if (bAddToSelection)
			{
				// Toggle off if ctrl-clicking selected item
				ApplySelectionHighlight(Selection[i], false);
				Selection.RemoveAt(i);
				BroadcastSelectionChanged();
				return;
			}
			bAlreadySelected = true;
			break;
		}
	}

	if (!bAlreadySelected)
	{
		Selection.Add(NewInfo);
		ApplySelectionHighlight(NewInfo, true);
	}

	BroadcastSelectionChanged();
}

void UArchSelectionManager::DeselectActor(AActor* Actor)
{
	for (int32 i = Selection.Num() - 1; i >= 0; --i)
	{
		if (Selection[i].Actor == Actor)
		{
			ApplySelectionHighlight(Selection[i], false);
			Selection.RemoveAt(i);
		}
	}
	BroadcastSelectionChanged();
}

void UArchSelectionManager::ClearSelection()
{
	for (const FArchSelectionInfo& Info : Selection)
	{
		ApplySelectionHighlight(Info, false);
	}
	Selection.Empty();
	BroadcastSelectionChanged();
}

void UArchSelectionManager::SetSelection(const TArray<FArchSelectionInfo>& NewSelection)
{
	// Clear old
	for (const FArchSelectionInfo& Info : Selection)
	{
		ApplySelectionHighlight(Info, false);
	}

	Selection = NewSelection;

	// Apply new
	for (const FArchSelectionInfo& Info : Selection)
	{
		ApplySelectionHighlight(Info, true);
	}

	BroadcastSelectionChanged();
}

FArchSelectionInfo UArchSelectionManager::GetPrimarySelection() const
{
	if (Selection.Num() > 0)
	{
		return Selection[0];
	}
	return FArchSelectionInfo();
}

AActor* UArchSelectionManager::GetSelectedActor() const
{
	if (Selection.Num() > 0)
	{
		return Selection[0].Actor;
	}
	return nullptr;
}

TArray<AActor*> UArchSelectionManager::GetSelectedActors() const
{
	TArray<AActor*> Actors;
	for (const FArchSelectionInfo& Info : Selection)
	{
		if (Info.Actor && !Actors.Contains(Info.Actor))
		{
			Actors.Add(Info.Actor);
		}
	}
	return Actors;
}

bool UArchSelectionManager::IsActorSelected(AActor* Actor) const
{
	for (const FArchSelectionInfo& Info : Selection)
	{
		if (Info.Actor == Actor)
		{
			return true;
		}
	}
	return false;
}

void UArchSelectionManager::SetHoveredElement(AActor* Actor, UPrimitiveComponent* Component, int32 FaceIndex)
{
	FArchSelectionInfo NewHover = CreateSelectionInfo(Actor, Component, FaceIndex);

	if (!(NewHover == HoveredElement))
	{
		// Clear old hover highlight (unless it's selected)
		if (HoveredElement.IsValid() && !IsActorSelected(HoveredElement.Actor))
		{
			ApplySelectionHighlight(HoveredElement, false);
		}

		HoveredElement = NewHover;

		// Apply new hover highlight (unless it's already selected)
		if (HoveredElement.IsValid() && !IsActorSelected(HoveredElement.Actor))
		{
			// Use hover color instead of selection color
			if (HoveredElement.Component)
			{
				HoveredElement.Component->SetRenderCustomDepth(true);
				HoveredElement.Component->SetCustomDepthStencilValue(2);  // Different value for hover
			}
		}

		OnElementHovered.Broadcast(HoveredElement);
	}
}

void UArchSelectionManager::ClearHover()
{
	if (HoveredElement.IsValid() && !IsActorSelected(HoveredElement.Actor))
	{
		ApplySelectionHighlight(HoveredElement, false);
	}
	HoveredElement = FArchSelectionInfo();
	OnElementHovered.Broadcast(HoveredElement);
}

void UArchSelectionManager::ApplySelectionHighlight(const FArchSelectionInfo& Info, bool bSelected)
{
	if (!Info.IsValid())
	{
		return;
	}

	// Use custom depth for post-process outline
	// This requires a post-process material that reads custom depth
	if (Info.Component)
	{
		Info.Component->SetRenderCustomDepth(bSelected);
		Info.Component->SetCustomDepthStencilValue(bSelected ? 1 : 0);
	}
	else if (Info.Actor)
	{
		// Apply to all primitive components in actor
		TArray<UPrimitiveComponent*> Components;
		Info.Actor->GetComponents<UPrimitiveComponent>(Components);
		for (UPrimitiveComponent* Comp : Components)
		{
			Comp->SetRenderCustomDepth(bSelected);
			Comp->SetCustomDepthStencilValue(bSelected ? 1 : 0);
		}
	}
}

FArchSelectionInfo UArchSelectionManager::CreateSelectionInfo(AActor* Actor, UPrimitiveComponent* Component, int32 FaceIndex)
{
	FArchSelectionInfo Info;
	Info.Actor = Actor;
	Info.Component = Component;
	Info.FaceIndex = FaceIndex;

	if (Actor)
	{
		// Try to get element info from ArchBuildingActor
		// This will be expanded when we add element ID tracking to building actor
		Info.ElementType = Actor->GetClass()->GetName();

		// For now, generate a simple ID
		if (Component)
		{
			Info.ElementId = FString::Printf(TEXT("%s_%s_%d"),
				*Actor->GetName(),
				*Component->GetName(),
				FaceIndex);
		}
		else
		{
			Info.ElementId = Actor->GetName();
		}
	}

	return Info;
}

void UArchSelectionManager::BroadcastSelectionChanged()
{
	OnSelectionChanged.Broadcast(Selection);
}
