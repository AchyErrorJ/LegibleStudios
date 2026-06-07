// ArchViewerController.h - Player controller for architectural viewer
// Handles input routing, cursor management, and UI interaction

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "ArchViewerController.generated.h"

class AArchViewerPawn;
class UArchSelectionManager;

UCLASS()
class ARCHENGINE_API AArchViewerController : public APlayerController
{
	GENERATED_BODY()

public:
	AArchViewerController();

	virtual void BeginPlay() override;
	virtual void SetupInputComponent() override;
	virtual void Tick(float DeltaTime) override;

	// Input handling
	virtual bool InputKey(const FInputKeyParams& Params) override;

	// ============= SELECTION =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void SelectAtCursor();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void SelectAtScreenPosition(FVector2D ScreenPosition, bool bAddToSelection = false);

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Selection")
	void ClearSelection();

	// Get selection manager
	UFUNCTION(BlueprintPure, Category = "ArchViewer|Selection")
	UArchSelectionManager* GetSelectionManager() const { return SelectionManager; }

	// ============= CAMERA ACCESS =============

	UFUNCTION(BlueprintPure, Category = "ArchViewer|Camera")
	AArchViewerPawn* GetViewerPawn() const;

	// ============= INPUT MODES =============

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Input")
	void SetUIInputMode();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Input")
	void SetGameInputMode();

	UFUNCTION(BlueprintCallable, Category = "ArchViewer|Input")
	void SetGameAndUIInputMode();

	// ============= PROPERTIES =============

	// Enable click-to-select
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Selection")
	bool bEnableClickSelection = true;

	// Selection trace channel
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchViewer|Selection")
	TEnumAsByte<ECollisionChannel> SelectionTraceChannel = ECC_Visibility;

protected:
	// Selection manager component
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "ArchViewer")
	UArchSelectionManager* SelectionManager;

	// Input handlers
	void OnLeftMousePressed();
	void OnLeftMouseReleased();
	void OnEscapePressed();
	void OnDeletePressed();
	void OnFocusPressed();

	// Track mouse state for click detection
	FVector2D MousePressPosition;
	float MousePressTime;
	bool bMousePressed;
	static constexpr float ClickThreshold = 5.0f;  // Pixels
	static constexpr float ClickTimeThreshold = 0.3f;  // Seconds
};
