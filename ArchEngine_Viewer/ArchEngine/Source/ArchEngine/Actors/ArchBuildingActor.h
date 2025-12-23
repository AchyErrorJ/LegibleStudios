// ArchBuildingActor.h - Main building visualization actor

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralMeshComponent.h"
#include "Types/ArchTypes.h"
#include "ArchBuildingActor.generated.h"

// Section view mode
UENUM(BlueprintType)
enum class ESectionViewMode : uint8
{
    Solid,          // Normal solid walls
    SectionCut,     // Show layers at section plane
    Exploded        // Exploded view of all layers
};

// Section plane axis
UENUM(BlueprintType)
enum class ESectionAxis : uint8
{
    X_LeftRight,    // Cut from left to right (YZ plane)
    Y_FrontBack,    // Cut from front to back (XZ plane) - Default
    Z_TopDown       // Cut from top to bottom (XY plane)
};

// Helper struct for wall openings (doors/windows)
struct FWallOpening
{
    float OffsetAlongWall;  // Distance from wall start to opening center
    float Width;
    float Height;
    float BottomZ;          // Height from floor to bottom of opening
    bool bIsDoor;
};

UCLASS(BlueprintType, Blueprintable)
class ARCHENGINE_API AArchBuildingActor : public AActor
{
    GENERATED_BODY()

public:
    AArchBuildingActor();

    // Building data
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Data")
    FArchBuilding BuildingData;

    // Visualization mode
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Visualization")
    EVisualizationMode VisualizationMode = EVisualizationMode::Structural;

    // Scale factor (feet to Unreal units - 1 foot = 30.48 cm)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Settings")
    float ScaleFactor = 30.48f;

    // JSON file path - set this and the building loads automatically on Play
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Settings")
    FString JsonFilePath;

    // Auto-load on BeginPlay
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Settings")
    bool bAutoLoadOnPlay = true;

    // Watch JSON file for changes and auto-reload (for live editing from ArchEngine kernel)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Settings")
    bool bWatchFileForChanges = true;

    // How often to check for file changes (seconds)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Settings", meta = (ClampMin = "0.1", ClampMax = "5.0"))
    float FileWatchInterval = 0.5f;

    // ========== Section View Settings ==========

    // Section view mode
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section")
    ESectionViewMode SectionViewMode = ESectionViewMode::Solid;

    // Section plane slider (0 = start of building, 1 = end of building)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section", meta = (ClampMin = "0.0", ClampMax = "1.0", UIMin = "0.0", UIMax = "1.0"))
    float SectionPlaneAlpha = 0.5f;

    // Which axis to cut along
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section")
    ESectionAxis SectionAxis = ESectionAxis::Y_FrontBack;

    // Show the section plane indicator
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section")
    bool bShowSectionPlane = true;

    // Section plane position (world space) - auto-calculated from Alpha
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "ArchEngine|Section")
    FVector SectionPlanePosition = FVector::ZeroVector;

    // Section plane normal (direction the plane faces) - auto-calculated from Axis
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "ArchEngine|Section")
    FVector SectionPlaneNormal = FVector(0, 1, 0);

    // Section cut depth (how deep to show layers)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section", meta = (ClampMin = "0", ClampMax = "500"))
    float SectionDepth = 100.0f;

    // Exploded view separation distance
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section", meta = (ClampMin = "0", ClampMax = "200"))
    float ExplodedSeparation = 20.0f;

    // Show layer labels in section view
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section")
    bool bShowLayerLabels = true;

    // Path to the section clipping material (must have SectionPlanePos and SectionPlaneNormal parameters)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "ArchEngine|Section")
    FString ClippingMaterialPath = TEXT("/Game/ArchEngine/Materials/M_SectionClip");

    // Load building from JSON file
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    bool LoadFromFile(const FString& FilePath);

    // Load building from JSON string (for live sync)
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    bool LoadFromJsonString(const FString& JsonString);

    // Regenerate all meshes from building data
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    void RebuildMeshes();

    // Set visualization mode and update colors
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    void SetVisualizationMode(EVisualizationMode NewMode);

    // Set section view mode
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|Section")
    void SetSectionViewMode(ESectionViewMode NewMode);

    // Move section plane
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|Section")
    void SetSectionPlane(FVector Position, FVector Normal);

    // Animate section plane through building
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|Section")
    void AnimateSectionPlane(float Alpha);

    // Get color for stress value
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static FLinearColor GetStressColor(float Stress);

    // Get color for element type
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static FLinearColor GetMaterialColor(const FString& Material);

    // Get color for wall layer function
    UFUNCTION(BlueprintCallable, Category = "ArchEngine|Section")
    static FLinearColor GetLayerColor(ELayerFunction Function);

    // Force reload from file (useful for Blueprint calls)
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    void ReloadFromFile();

    // Check if file has changed since last load
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    bool HasFileChanged() const;

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;
    virtual void OnConstruction(const FTransform& Transform) override;

#if WITH_EDITOR
    virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

private:
    // Root component
    UPROPERTY()
    USceneComponent* RootSceneComponent;

    // Procedural mesh components for each element
    UPROPERTY()
    TArray<UProceduralMeshComponent*> ElementMeshes;

    // Layer mesh components for section view (one per wall per layer)
    UPROPERTY()
    TArray<UProceduralMeshComponent*> LayerMeshes;

    // Materials
    UPROPERTY()
    UMaterialInterface* BaseMaterial;

    UPROPERTY()
    TArray<UMaterialInstanceDynamic*> DynamicMaterials;

    // Layer materials for section view
    UPROPERTY()
    TArray<UMaterialInstanceDynamic*> LayerMaterials;

    // Layer mesh world-space info for section visibility
    struct FLayerMeshInfo
    {
        FVector WallStart;      // World-space wall start
        FVector WallEnd;        // World-space wall end
        FVector WallCenter;     // World-space center of wall
        float WallHeight;       // Wall height
    };
    TArray<FLayerMeshInfo> LayerMeshInfos;

    // Section plane indicator mesh
    UPROPERTY()
    UProceduralMeshComponent* SectionPlaneMesh;

    // Section plane material
    UPROPERTY()
    UMaterialInstanceDynamic* SectionPlaneMaterial;

    // Material Parameter Collection for section clipping
    UPROPERTY()
    class UMaterialParameterCollection* SectionMPC;

    // Clipping material for layer meshes
    UPROPERTY()
    UMaterialInterface* ClippingBaseMaterial;

    // Building bounds for section plane animation
    FBox BuildingBounds;

    // Cached section plane alpha for change detection
    float CachedSectionPlaneAlpha = -1.0f;
    ESectionAxis CachedSectionAxis = ESectionAxis::Y_FrontBack;

    // File watching state
    FDateTime LastFileModTime;
    float FileWatchTimer = 0.0f;
    bool bFileWatchInitialized = false;

    // Generate mesh for a structural element
    void GenerateElementMesh(const FArchElement& Element, int32 ElementIndex);

    // Generate beam mesh
    void GenerateBeamMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element);

    // Generate column mesh
    void GenerateColumnMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element);

    // Generate wall mesh (with optional openings for doors/windows)
    void GenerateWallMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element, int32 WallIndex = -1);

    // Generate floor/roof mesh
    void GenerateSlabMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element);

    // Generate door frame mesh
    void GenerateDoorMesh(UProceduralMeshComponent* MeshComp, const FArchDoor& Door);

    // Generate window frame mesh
    void GenerateWindowMesh(UProceduralMeshComponent* MeshComp, const FArchWindow& Window);

    // Get wall direction and position from index
    bool GetWallGeometry(int32 WallIndex, FVector& OutStart, FVector& OutEnd, FVector& OutDir, FVector& OutNormal) const;

    // ========== Stair Generation Methods ==========

    // Generate complete stair mesh with treads, risers, and stringers
    void GenerateStairMesh(UProceduralMeshComponent* MeshComp, const FArchStair& Stair);

    // Generate guardrail mesh (handrail, balusters, newels)
    void GenerateGuardrailMesh(UProceduralMeshComponent* MeshComp, const FArchGuardrail& Guardrail, const FArchStair& Stair);

    // ========== Roof Generation Methods ==========

    // Generate roof mesh from surface definitions
    void GenerateRoofMesh(UProceduralMeshComponent* MeshComp, const FArchRoof& Roof);

    // Generate dormer mesh
    void GenerateDormerMesh(UProceduralMeshComponent* MeshComp, const FArchDormer& Dormer, const FArchRoof& Roof);

    // Generate skylight mesh (frame and glass)
    void GenerateSkylightMesh(UProceduralMeshComponent* MeshComp, const FArchSkylight& Skylight);

    // ========== Elevator Generation Methods ==========

    // Generate elevator shaft and cab mesh
    void GenerateElevatorMesh(UProceduralMeshComponent* MeshComp, const FArchElevator& Elevator);

    // ========== MEP Fixture Generation Methods ==========

    // Generate plumbing fixture mesh (toilet, sink, tub, etc.)
    void GeneratePlumbingFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchPlumbingFixture& Fixture);

    // Generate electrical fixture mesh (outlet, switch, panel, etc.)
    void GenerateElectricalFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchElectricalFixture& Fixture);

    // Generate HVAC fixture mesh (register, grille, etc.)
    void GenerateHVACFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchHVACFixture& Fixture);

    // Generate custom mesh from IFC data
    void GenerateCustomMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element);

    // Create box mesh helper
    void CreateBoxMesh(UProceduralMeshComponent* MeshComp, FVector Center, FVector Extents, FLinearColor Color);

    // Update material colors based on visualization mode
    void UpdateMaterialColors();

    // Convert kernel coordinates to Unreal coordinates
    FVector KernelToUnreal(const FVector& KernelPos) const;

    // ========== Section View Methods ==========

    // Generate section view geometry for all walls
    void GenerateSectionGeometry();

    // Generate layer meshes for a single wall
    void GenerateWallLayerMeshes(int32 WallIndex, const FArchParametricWall& ParamWall, const FArchWallType& WallType);

    // Generate a single layer mesh (with openings for doors/windows)
    void GenerateLayerMesh(UProceduralMeshComponent* MeshComp, const FArchWallLayer& Layer,
                           FVector WallStart, FVector WallEnd, float WallHeight,
                           float LayerStartDepth, float LayerThickness, int32 LayerIndex,
                           const TArray<FWallOpening>& Openings);

    // Update section view visibility based on section plane
    void UpdateSectionVisibility();

    // Clear all layer meshes
    void ClearLayerMeshes();

    // Calculate building bounds
    void CalculateBuildingBounds();

    // Update section plane from alpha and axis
    void UpdateSectionPlaneFromAlpha();

    // Create/update section plane indicator mesh
    void UpdateSectionPlaneMesh();

    // Update section material parameters for clipping
    void UpdateSectionMaterialParams();

    // Load clipping material if available
    void LoadClippingMaterial();
};
