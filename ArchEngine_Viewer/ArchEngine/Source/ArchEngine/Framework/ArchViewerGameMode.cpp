// ArchViewerGameMode.cpp - Game mode implementation

#include "Framework/ArchViewerGameMode.h"
#include "Framework/ArchViewerPawn.h"
#include "Framework/ArchViewerController.h"
#include "Framework/ArchViewerHUD.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"

AArchViewerGameMode::AArchViewerGameMode()
{
	// Set default classes
	DefaultPawnClass = AArchViewerPawn::StaticClass();
	PlayerControllerClass = AArchViewerController::StaticClass();
	HUDClass = AArchViewerHUD::StaticClass();
}

void AArchViewerGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	UE_LOG(LogTemp, Log, TEXT("ArchViewerGameMode: Initializing game on map %s"), *MapName);
}

void AArchViewerGameMode::BeginPlay()
{
	Super::BeginPlay();

	UE_LOG(LogTemp, Log, TEXT("ArchViewerGameMode: BeginPlay"));
}

void AArchViewerGameMode::StartPlay()
{
	Super::StartPlay();

	UE_LOG(LogTemp, Log, TEXT("ArchViewerGameMode: StartPlay"));

	// Focus camera on building after a short delay to ensure everything is loaded
	FTimerHandle TimerHandle;
	GetWorld()->GetTimerManager().SetTimer(TimerHandle, this, &AArchViewerGameMode::FocusOnBuilding, 0.5f, false);
}

void AArchViewerGameMode::FocusOnBuilding()
{
	// Find ArchBuildingActor in the level
	TArray<AActor*> FoundActors;
	UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), FoundActors);

	AActor* BuildingActor = nullptr;
	for (AActor* Actor : FoundActors)
	{
		if (Actor->GetClass()->GetName().Contains(TEXT("ArchBuilding")))
		{
			BuildingActor = Actor;
			break;
		}
	}

	if (BuildingActor)
	{
		// Get the player's pawn and focus on the building
		APlayerController* PC = UGameplayStatics::GetPlayerController(GetWorld(), 0);
		if (PC)
		{
			AArchViewerPawn* ViewerPawn = Cast<AArchViewerPawn>(PC->GetPawn());
			if (ViewerPawn)
			{
				ViewerPawn->FocusOnActor(BuildingActor);
				UE_LOG(LogTemp, Log, TEXT("ArchViewerGameMode: Focused camera on %s"), *BuildingActor->GetName());
			}
		}
	}
	else
	{
		UE_LOG(LogTemp, Warning, TEXT("ArchViewerGameMode: No ArchBuildingActor found in level"));
	}
}
