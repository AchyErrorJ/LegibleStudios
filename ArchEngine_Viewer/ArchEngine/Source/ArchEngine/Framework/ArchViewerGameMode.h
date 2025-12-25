// ArchViewerGameMode.h - Game mode for architectural viewer application
// Configures the default pawn, controller, and HUD classes

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "ArchViewerGameMode.generated.h"

UCLASS()
class ARCHENGINE_API AArchViewerGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AArchViewerGameMode();

	virtual void StartPlay() override;
	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

	// Find and focus on the building actor in the level
	UFUNCTION(BlueprintCallable, Category = "ArchViewer")
	void FocusOnBuilding();

protected:
	// Called when the game starts
	virtual void BeginPlay() override;
};
