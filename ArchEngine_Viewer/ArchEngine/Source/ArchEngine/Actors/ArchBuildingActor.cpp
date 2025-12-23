// ArchBuildingActor.cpp - Building visualization implementation

#include "ArchBuildingActor.h"
#include "Loaders/ArchBuildingLoader.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "UObject/ConstructorHelpers.h"
#include "HAL/FileManager.h"

AArchBuildingActor::AArchBuildingActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;

    // Create root component
    RootSceneComponent = CreateDefaultSubobject<USceneComponent>(TEXT("RootComponent"));
    RootComponent = RootSceneComponent;

    // Create section plane indicator mesh
    SectionPlaneMesh = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("SectionPlane"));
    SectionPlaneMesh->SetupAttachment(RootComponent);
    SectionPlaneMesh->SetVisibility(false);
    SectionPlaneMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    // Find base material (use default if not found)
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(
        TEXT("/Engine/BasicShapes/BasicShapeMaterial"));
    if (MaterialFinder.Succeeded())
    {
        BaseMaterial = MaterialFinder.Object;
    }
}

void AArchBuildingActor::BeginPlay()
{
    Super::BeginPlay();

    // Auto-load JSON file if path is set (only if not already loaded)
    if (bAutoLoadOnPlay && !JsonFilePath.IsEmpty() && BuildingData.Elements.Num() == 0)
    {
        UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: Auto-loading from %s"), *JsonFilePath);
        LoadFromFile(JsonFilePath);
    }
    else if (BuildingData.Elements.Num() > 0)
    {
        UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: Building already loaded with %d elements, skipping auto-load"), BuildingData.Elements.Num());
        // Reapply section view if needed
        if (SectionViewMode != ESectionViewMode::Solid)
        {
            SetSectionViewMode(SectionViewMode);
        }
    }

    // Initialize file watching
    if (bWatchFileForChanges && !JsonFilePath.IsEmpty())
    {
        LastFileModTime = IFileManager::Get().GetTimeStamp(*JsonFilePath);
        bFileWatchInitialized = true;
        FileWatchTimer = 0.0f;
        UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: File watching enabled for %s"), *JsonFilePath);
    }
}

void AArchBuildingActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    // File watching - check periodically for changes
    if (bWatchFileForChanges && bFileWatchInitialized && !JsonFilePath.IsEmpty())
    {
        FileWatchTimer += DeltaTime;
        if (FileWatchTimer >= FileWatchInterval)
        {
            FileWatchTimer = 0.0f;

            if (HasFileChanged())
            {
                UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: JSON file changed, reloading..."));
                ReloadFromFile();
            }
        }
    }
}

bool AArchBuildingActor::HasFileChanged() const
{
    if (JsonFilePath.IsEmpty())
    {
        return false;
    }

    FDateTime CurrentModTime = IFileManager::Get().GetTimeStamp(*JsonFilePath);
    return CurrentModTime > LastFileModTime;
}

void AArchBuildingActor::ReloadFromFile()
{
    if (JsonFilePath.IsEmpty())
    {
        return;
    }

    // Update the last mod time before loading (so we don't re-trigger)
    LastFileModTime = IFileManager::Get().GetTimeStamp(*JsonFilePath);

    // Reload the building
    if (LoadFromFile(JsonFilePath))
    {
        UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: Successfully reloaded building from %s"), *JsonFilePath);
    }
    else
    {
        UE_LOG(LogTemp, Warning, TEXT("AArchBuildingActor: Failed to reload building from %s"), *JsonFilePath);
    }
}

void AArchBuildingActor::OnConstruction(const FTransform& Transform)
{
    Super::OnConstruction(Transform);
}

#if WITH_EDITOR
void AArchBuildingActor::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
    Super::PostEditChangeProperty(PropertyChangedEvent);

    FName PropertyName = PropertyChangedEvent.Property ? PropertyChangedEvent.Property->GetFName() : NAME_None;

    if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, JsonFilePath))
    {
        // Load building when JSON path is set in editor
        if (!JsonFilePath.IsEmpty())
        {
            UE_LOG(LogTemp, Log, TEXT("AArchBuildingActor: Loading from editor path change: %s"), *JsonFilePath);
            LoadFromFile(JsonFilePath);
        }
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, SectionViewMode))
    {
        SetSectionViewMode(SectionViewMode);
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, SectionPlaneAlpha) ||
             PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, SectionAxis))
    {
        // Update plane position/normal from slider and axis
        UpdateSectionPlaneFromAlpha();
        UpdateSectionPlaneMesh();
        UpdateSectionVisibility();
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, bShowSectionPlane))
    {
        if (SectionPlaneMesh)
        {
            SectionPlaneMesh->SetVisibility(bShowSectionPlane && SectionViewMode != ESectionViewMode::Solid);
        }
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, SectionDepth))
    {
        UpdateSectionVisibility();
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, ExplodedSeparation))
    {
        if (SectionViewMode == ESectionViewMode::Exploded)
        {
            GenerateSectionGeometry();
        }
    }
    else if (PropertyName == GET_MEMBER_NAME_CHECKED(AArchBuildingActor, ScaleFactor))
    {
        // Rebuild meshes when scale factor changes
        RebuildMeshes();
    }
}
#endif

bool AArchBuildingActor::LoadFromFile(const FString& FilePath)
{
    if (UArchBuildingLoader::LoadBuildingFromFile(FilePath, BuildingData))
    {
        RebuildMeshes();

        // Reapply section view mode if not solid
        if (SectionViewMode != ESectionViewMode::Solid)
        {
            SetSectionViewMode(SectionViewMode);
        }

        return true;
    }
    return false;
}

bool AArchBuildingActor::LoadFromJsonString(const FString& JsonString)
{
    if (UArchBuildingLoader::LoadBuildingFromString(JsonString, BuildingData))
    {
        RebuildMeshes();

        // Reapply section view mode if not solid
        if (SectionViewMode != ESectionViewMode::Solid)
        {
            SetSectionViewMode(SectionViewMode);
        }

        return true;
    }
    return false;
}

void AArchBuildingActor::RebuildMeshes()
{
    // Clear existing meshes
    for (auto* MeshComp : ElementMeshes)
    {
        if (MeshComp)
        {
            MeshComp->DestroyComponent();
        }
    }
    ElementMeshes.Empty();
    DynamicMaterials.Empty();

    // Generate mesh for each wall element
    for (int32 i = 0; i < BuildingData.Elements.Num(); i++)
    {
        GenerateElementMesh(BuildingData.Elements[i], i);
    }

    // Load clipping material if not already loaded
    if (!ClippingBaseMaterial)
    {
        LoadClippingMaterial();
    }

    // Generate door meshes
    for (int32 i = 0; i < BuildingData.Doors.Num(); i++)
    {
        FString CompName = FString::Printf(TEXT("Door_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        // Use clipping material if available
        UMaterialInterface* MaterialToUse = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
        if (MaterialToUse)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(MaterialToUse, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.4f, 0.25f, 0.15f)); // Wood brown
            DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateDoorMesh(MeshComp, BuildingData.Doors[i]);
        ElementMeshes.Add(MeshComp);
    }

    // Generate window meshes
    for (int32 i = 0; i < BuildingData.Windows.Num(); i++)
    {
        FString CompName = FString::Printf(TEXT("Window_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        // Use clipping material if available
        UMaterialInterface* MaterialToUse = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
        if (MaterialToUse)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(MaterialToUse, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.7f, 0.85f, 0.95f)); // Light blue glass
            DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateWindowMesh(MeshComp, BuildingData.Windows[i]);
        ElementMeshes.Add(MeshComp);
    }

    // Generate stair meshes
    for (int32 i = 0; i < BuildingData.Stairs.Num(); i++)
    {
        const FArchStair& Stair = BuildingData.Stairs[i];

        // Main stair mesh (treads, risers, stringers)
        FString CompName = FString::Printf(TEXT("Stair_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        if (BaseMaterial)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.6f, 0.45f, 0.3f)); // Wood color
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateStairMesh(MeshComp, Stair);
        ElementMeshes.Add(MeshComp);

        // Generate guardrail meshes for this stair
        for (int32 j = 0; j < Stair.Guardrails.Num(); j++)
        {
            FString RailName = FString::Printf(TEXT("Stair_%d_Guardrail_%d"), i, j);
            UProceduralMeshComponent* RailMesh = NewObject<UProceduralMeshComponent>(this, *RailName);
            RailMesh->SetupAttachment(RootComponent);
            RailMesh->RegisterComponent();

            if (BaseMaterial)
            {
                UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
                DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.5f, 0.35f, 0.2f)); // Darker wood
                RailMesh->SetMaterial(0, DynMat);
                DynamicMaterials.Add(DynMat);
            }

            GenerateGuardrailMesh(RailMesh, Stair.Guardrails[j], Stair);
            ElementMeshes.Add(RailMesh);
        }
    }

    // Generate roof meshes
    for (int32 i = 0; i < BuildingData.Roofs.Num(); i++)
    {
        const FArchRoof& Roof = BuildingData.Roofs[i];

        FString CompName = FString::Printf(TEXT("Roof_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        // Use clipping material if available (for section view)
        UMaterialInterface* MaterialToUse = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
        if (MaterialToUse)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(MaterialToUse, this);
            // Color based on material
            FLinearColor RoofColor = FLinearColor(0.3f, 0.3f, 0.35f); // Default gray
            if (Roof.Material == TEXT("asphalt_shingle"))
                RoofColor = FLinearColor(0.25f, 0.25f, 0.28f);
            else if (Roof.Material == TEXT("metal"))
                RoofColor = FLinearColor(0.5f, 0.5f, 0.55f);
            else if (Roof.Material == TEXT("tile"))
                RoofColor = FLinearColor(0.7f, 0.35f, 0.2f);
            else if (Roof.Material == TEXT("slate"))
                RoofColor = FLinearColor(0.35f, 0.35f, 0.4f);

            DynMat->SetVectorParameterValue(TEXT("BaseColor"), RoofColor);
            DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateRoofMesh(MeshComp, Roof);
        ElementMeshes.Add(MeshComp);

        // Generate dormer meshes
        for (int32 j = 0; j < Roof.Dormers.Num(); j++)
        {
            FString DormerName = FString::Printf(TEXT("Roof_%d_Dormer_%d"), i, j);
            UProceduralMeshComponent* DormerMesh = NewObject<UProceduralMeshComponent>(this, *DormerName);
            DormerMesh->SetupAttachment(RootComponent);
            DormerMesh->RegisterComponent();

            UMaterialInterface* DormerMat = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
            if (DormerMat)
            {
                UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(DormerMat, this);
                DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.9f, 0.9f, 0.85f)); // Light exterior
                DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);
                DormerMesh->SetMaterial(0, DynMat);
                DynamicMaterials.Add(DynMat);
            }

            GenerateDormerMesh(DormerMesh, Roof.Dormers[j], Roof);
            ElementMeshes.Add(DormerMesh);
        }

        // Generate skylight meshes
        for (int32 j = 0; j < Roof.Skylights.Num(); j++)
        {
            FString SkylightName = FString::Printf(TEXT("Roof_%d_Skylight_%d"), i, j);
            UProceduralMeshComponent* SkylightMesh = NewObject<UProceduralMeshComponent>(this, *SkylightName);
            SkylightMesh->SetupAttachment(RootComponent);
            SkylightMesh->RegisterComponent();

            UMaterialInterface* SkylightMat = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
            if (SkylightMat)
            {
                UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(SkylightMat, this);
                DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.7f, 0.85f, 0.95f)); // Glass blue
                DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);
                SkylightMesh->SetMaterial(0, DynMat);
                DynamicMaterials.Add(DynMat);
            }

            GenerateSkylightMesh(SkylightMesh, Roof.Skylights[j]);
            ElementMeshes.Add(SkylightMesh);
        }
    }

    // Generate elevator meshes
    for (int32 i = 0; i < BuildingData.Elevators.Num(); i++)
    {
        const FArchElevator& Elevator = BuildingData.Elevators[i];
        FString CompName = FString::Printf(TEXT("Elevator_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        if (BaseMaterial)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.5f, 0.5f, 0.55f)); // Metal gray
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateElevatorMesh(MeshComp, Elevator);
        ElementMeshes.Add(MeshComp);
    }

    // Generate MEP fixture meshes
    // Plumbing fixtures
    for (int32 i = 0; i < BuildingData.MEP.PlumbingFixtures.Num(); i++)
    {
        const FArchPlumbingFixture& Fixture = BuildingData.MEP.PlumbingFixtures[i];
        FString CompName = FString::Printf(TEXT("Plumbing_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        if (BaseMaterial)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.95f, 0.95f, 0.95f)); // White porcelain
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GeneratePlumbingFixtureMesh(MeshComp, Fixture);
        ElementMeshes.Add(MeshComp);
    }

    // Electrical fixtures
    for (int32 i = 0; i < BuildingData.MEP.ElectricalFixtures.Num(); i++)
    {
        const FArchElectricalFixture& Fixture = BuildingData.MEP.ElectricalFixtures[i];
        FString CompName = FString::Printf(TEXT("Electrical_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        if (BaseMaterial)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.9f, 0.88f, 0.8f)); // Almond
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateElectricalFixtureMesh(MeshComp, Fixture);
        ElementMeshes.Add(MeshComp);
    }

    // HVAC fixtures
    for (int32 i = 0; i < BuildingData.MEP.HVACFixtures.Num(); i++)
    {
        const FArchHVACFixture& Fixture = BuildingData.MEP.HVACFixtures[i];
        FString CompName = FString::Printf(TEXT("HVAC_%d"), i);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        if (BaseMaterial)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.9f, 0.9f, 0.9f)); // White
            MeshComp->SetMaterial(0, DynMat);
            DynamicMaterials.Add(DynMat);
        }

        GenerateHVACFixtureMesh(MeshComp, Fixture);
        ElementMeshes.Add(MeshComp);
    }

    UE_LOG(LogTemp, Warning, TEXT("RebuildMeshes: Generated %d total meshes:"), ElementMeshes.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d element meshes"), BuildingData.Elements.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d door meshes"), BuildingData.Doors.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d window meshes"), BuildingData.Windows.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d stair meshes"), BuildingData.Stairs.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d roof meshes"), BuildingData.Roofs.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d elevator meshes"), BuildingData.Elevators.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d plumbing fixtures"), BuildingData.MEP.PlumbingFixtures.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d electrical fixtures"), BuildingData.MEP.ElectricalFixtures.Num());
    UE_LOG(LogTemp, Warning, TEXT("  - %d HVAC fixtures"), BuildingData.MEP.HVACFixtures.Num());
}

void AArchBuildingActor::GenerateElementMesh(const FArchElement& Element, int32 ElementIndex)
{
    // Create procedural mesh component
    FString CompName = FString::Printf(TEXT("Element_%d"), ElementIndex);
    UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
    MeshComp->SetupAttachment(RootComponent);
    MeshComp->RegisterComponent();

    // Create dynamic material
    UMaterialInstanceDynamic* DynMat = nullptr;
    if (BaseMaterial)
    {
        DynMat = UMaterialInstanceDynamic::Create(BaseMaterial, this);
        MeshComp->SetMaterial(0, DynMat);
        DynamicMaterials.Add(DynMat);
    }

    // Generate mesh based on element type
    if (Element.Mesh.HasData())
    {
        GenerateCustomMesh(MeshComp, Element);
    }
    else
    {
        switch (Element.Type)
        {
            case EArchElementType::Beam:
                GenerateBeamMesh(MeshComp, Element);
                break;
            case EArchElementType::Column:
                GenerateColumnMesh(MeshComp, Element);
                break;
            case EArchElementType::Wall:
                GenerateWallMesh(MeshComp, Element, ElementIndex);
                break;
            case EArchElementType::Floor:
            case EArchElementType::Roof:
                GenerateSlabMesh(MeshComp, Element);
                break;
            default:
                // Default to beam-style mesh
                GenerateBeamMesh(MeshComp, Element);
                break;
        }
    }

    // Set color based on visualization mode
    FLinearColor Color;
    switch (VisualizationMode)
    {
        case EVisualizationMode::Structural:
            Color = GetStressColor(Element.Stress);
            break;
        case EVisualizationMode::Material:
            Color = GetMaterialColor(Element.Material);
            break;
        default:
            Color = FLinearColor::White;
            break;
    }

    if (DynMat)
    {
        DynMat->SetVectorParameterValue(TEXT("BaseColor"), Color);
    }

    ElementMeshes.Add(MeshComp);
}

void AArchBuildingActor::GenerateBeamMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element)
{
    FVector Start = KernelToUnreal(Element.Start);
    FVector End = KernelToUnreal(Element.End);
    FVector Center = (Start + End) * 0.5f;

    FVector Dir = (End - Start).GetSafeNormal();
    float Length = FVector::Dist(Start, End);
    float HalfWidth = Element.Width * ScaleFactor * 0.5f;
    float HalfDepth = Element.Depth * ScaleFactor * 0.5f;

    // Create box extents
    FVector Extents(Length * 0.5f, HalfWidth, HalfDepth);

    // Get rotation to align with beam direction
    FRotator Rotation = Dir.Rotation();

    // Create the mesh at origin then transform
    CreateBoxMesh(MeshComp, FVector::ZeroVector, Extents, GetStressColor(Element.Stress));

    // Position and rotate the mesh component
    MeshComp->SetWorldLocation(Center);
    MeshComp->SetWorldRotation(Rotation);
}

void AArchBuildingActor::GenerateColumnMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element)
{
    FVector Start = KernelToUnreal(Element.Start);
    FVector End = KernelToUnreal(Element.End);
    FVector Center = (Start + End) * 0.5f;

    float Height = FVector::Dist(Start, End);
    float HalfWidth = Element.Width * ScaleFactor * 0.5f;
    float HalfDepth = Element.Depth * ScaleFactor * 0.5f;

    FVector Extents(HalfWidth, HalfDepth, Height * 0.5f);

    CreateBoxMesh(MeshComp, FVector::ZeroVector, Extents, GetStressColor(Element.Stress));
    MeshComp->SetWorldLocation(Center);
}

void AArchBuildingActor::GenerateWallMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element, int32 ElementIndex)
{
    FVector Start = KernelToUnreal(Element.Start);
    FVector End = KernelToUnreal(Element.End);

    float WallLength = FMath::Sqrt(FMath::Square(End.X - Start.X) + FMath::Square(End.Y - Start.Y));
    float WallHeight = End.Z - Start.Z;
    float Thickness = Element.Depth * ScaleFactor;

    FVector Center = (Start + End) * 0.5f;
    FVector Dir = FVector(End.X - Start.X, End.Y - Start.Y, 0).GetSafeNormal();
    FVector Normal = FVector(-Dir.Y, Dir.X, 0);

    // Use the Element's stored WallIndex (from JSON) for matching doors/windows
    // This is more reliable than using ElementIndex which depends on array position
    int32 WallIndex = Element.WallIndex >= 0 ? Element.WallIndex : ElementIndex;

    // Collect openings for this wall
    TArray<FWallOpening> Openings;

    for (const FArchDoor& Door : BuildingData.Doors)
    {
        if (Door.WallIndex == WallIndex)
        {
            FWallOpening Op;
            Op.OffsetAlongWall = Door.Offset * ScaleFactor;
            Op.Width = Door.Width * ScaleFactor;
            Op.Height = Door.Height * ScaleFactor;
            Op.BottomZ = 0.0f;  // Doors start at floor
            Op.bIsDoor = true;
            Openings.Add(Op);
        }
    }

    for (const FArchWindow& Window : BuildingData.Windows)
    {
        if (Window.WallIndex == WallIndex)
        {
            FWallOpening Op;
            Op.OffsetAlongWall = Window.Offset * ScaleFactor;
            Op.Width = Window.Width * ScaleFactor;
            Op.Height = Window.Height * ScaleFactor;
            Op.BottomZ = Window.SillHeight * ScaleFactor;
            Op.bIsDoor = false;
            Openings.Add(Op);
        }
    }

    // Sort openings by position along wall
    Openings.Sort([](const FWallOpening& A, const FWallOpening& B) {
        return A.OffsetAlongWall < B.OffsetAlongWall;
    });

    // Debug logging for openings
    if (Openings.Num() > 0)
    {
        UE_LOG(LogTemp, Warning, TEXT("Element[%d] WallIndex=%d: WallLength=%.1f, WallHeight=%.1f, Found %d openings"),
               ElementIndex, WallIndex, WallLength, WallHeight, Openings.Num());
        for (int32 oi = 0; oi < Openings.Num(); oi++)
        {
            UE_LOG(LogTemp, Warning, TEXT("  Opening %d: Offset=%.1f, Width=%.1f, Height=%.1f, Bottom=%.1f, IsDoor=%d"),
                   oi, Openings[oi].OffsetAlongWall, Openings[oi].Width, Openings[oi].Height,
                   Openings[oi].BottomZ, Openings[oi].bIsDoor ? 1 : 0);
        }
    }
    else
    {
        UE_LOG(LogTemp, Log, TEXT("Element[%d] WallIndex=%d: WallLength=%.1f, No openings (checking against %d doors, %d windows)"),
               ElementIndex, WallIndex, WallLength, BuildingData.Doors.Num(), BuildingData.Windows.Num());
    }

    // If no openings, use simple box
    if (Openings.Num() == 0)
    {
        FVector Extents(WallLength * 0.5f, Thickness * 0.5f, WallHeight * 0.5f);
        CreateBoxMesh(MeshComp, FVector::ZeroVector, Extents, GetMaterialColor(Element.Material));
        MeshComp->SetWorldLocation(Center);
        MeshComp->SetWorldRotation(Dir.Rotation());
        return;
    }

    // Generate wall mesh with openings
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor WallColor = GetMaterialColor(Element.Material).ToFColor(true);
    float HalfThick = Thickness * 0.5f;
    float HalfLen = WallLength * 0.5f;

    // Lambda to add a quad (two triangles)
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(WallColor); Colors.Add(WallColor); Colors.Add(WallColor); Colors.Add(WallColor);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Generate wall segments between/around openings
    // X coordinate is along wall length (-HalfLen to +HalfLen in local space)
    // Y coordinate is thickness (-HalfThick to +HalfThick)
    // Z coordinate is height (0 to WallHeight)

    float CurrentX = -HalfLen;  // Start from left edge

    for (int32 i = 0; i <= Openings.Num(); i++)
    {
        float SegmentEnd;
        if (i < Openings.Num())
        {
            // Segment ends at the left edge of this opening
            SegmentEnd = Openings[i].OffsetAlongWall - Openings[i].Width * 0.5f - HalfLen;
        }
        else
        {
            // Last segment goes to right edge
            SegmentEnd = HalfLen;
        }

        // Generate solid wall segment from CurrentX to SegmentEnd (full height)
        if (SegmentEnd > CurrentX + 0.1f)  // Avoid degenerate segments
        {
            // Front face (+Y)
            AddQuad(
                FVector(CurrentX, HalfThick, 0),
                FVector(SegmentEnd, HalfThick, 0),
                FVector(SegmentEnd, HalfThick, WallHeight),
                FVector(CurrentX, HalfThick, WallHeight),
                FVector(0, 1, 0)
            );
            // Back face (-Y)
            AddQuad(
                FVector(SegmentEnd, -HalfThick, 0),
                FVector(CurrentX, -HalfThick, 0),
                FVector(CurrentX, -HalfThick, WallHeight),
                FVector(SegmentEnd, -HalfThick, WallHeight),
                FVector(0, -1, 0)
            );
            // Top face
            AddQuad(
                FVector(CurrentX, -HalfThick, WallHeight),
                FVector(CurrentX, HalfThick, WallHeight),
                FVector(SegmentEnd, HalfThick, WallHeight),
                FVector(SegmentEnd, -HalfThick, WallHeight),
                FVector(0, 0, 1)
            );
            // Bottom face
            AddQuad(
                FVector(CurrentX, HalfThick, 0),
                FVector(CurrentX, -HalfThick, 0),
                FVector(SegmentEnd, -HalfThick, 0),
                FVector(SegmentEnd, HalfThick, 0),
                FVector(0, 0, -1)
            );
            // Left end cap (only for first segment)
            if (i == 0)
            {
                AddQuad(
                    FVector(CurrentX, -HalfThick, 0),
                    FVector(CurrentX, HalfThick, 0),
                    FVector(CurrentX, HalfThick, WallHeight),
                    FVector(CurrentX, -HalfThick, WallHeight),
                    FVector(-1, 0, 0)
                );
            }
            // Right end cap (only for last segment)
            if (i == Openings.Num())
            {
                AddQuad(
                    FVector(SegmentEnd, HalfThick, 0),
                    FVector(SegmentEnd, -HalfThick, 0),
                    FVector(SegmentEnd, -HalfThick, WallHeight),
                    FVector(SegmentEnd, HalfThick, WallHeight),
                    FVector(1, 0, 0)
                );
            }
        }

        // Generate geometry around the opening
        if (i < Openings.Num())
        {
            const FWallOpening& Op = Openings[i];
            float OpLeft = Op.OffsetAlongWall - Op.Width * 0.5f - HalfLen;
            float OpRight = Op.OffsetAlongWall + Op.Width * 0.5f - HalfLen;
            float OpBottom = Op.BottomZ;
            float OpTop = Op.BottomZ + Op.Height;

            // Header (above opening) - front face
            if (OpTop < WallHeight - 0.1f)
            {
                AddQuad(
                    FVector(OpLeft, HalfThick, OpTop),
                    FVector(OpRight, HalfThick, OpTop),
                    FVector(OpRight, HalfThick, WallHeight),
                    FVector(OpLeft, HalfThick, WallHeight),
                    FVector(0, 1, 0)
                );
                // Header - back face
                AddQuad(
                    FVector(OpRight, -HalfThick, OpTop),
                    FVector(OpLeft, -HalfThick, OpTop),
                    FVector(OpLeft, -HalfThick, WallHeight),
                    FVector(OpRight, -HalfThick, WallHeight),
                    FVector(0, -1, 0)
                );
                // Header - top face
                AddQuad(
                    FVector(OpLeft, -HalfThick, WallHeight),
                    FVector(OpLeft, HalfThick, WallHeight),
                    FVector(OpRight, HalfThick, WallHeight),
                    FVector(OpRight, -HalfThick, WallHeight),
                    FVector(0, 0, 1)
                );
                // Header - bottom (soffit of opening)
                AddQuad(
                    FVector(OpLeft, HalfThick, OpTop),
                    FVector(OpLeft, -HalfThick, OpTop),
                    FVector(OpRight, -HalfThick, OpTop),
                    FVector(OpRight, HalfThick, OpTop),
                    FVector(0, 0, -1)
                );
            }

            // Sill (below opening - for windows)
            if (OpBottom > 0.1f)
            {
                AddQuad(
                    FVector(OpLeft, HalfThick, 0),
                    FVector(OpRight, HalfThick, 0),
                    FVector(OpRight, HalfThick, OpBottom),
                    FVector(OpLeft, HalfThick, OpBottom),
                    FVector(0, 1, 0)
                );
                AddQuad(
                    FVector(OpRight, -HalfThick, 0),
                    FVector(OpLeft, -HalfThick, 0),
                    FVector(OpLeft, -HalfThick, OpBottom),
                    FVector(OpRight, -HalfThick, OpBottom),
                    FVector(0, -1, 0)
                );
                // Sill top surface
                AddQuad(
                    FVector(OpLeft, -HalfThick, OpBottom),
                    FVector(OpLeft, HalfThick, OpBottom),
                    FVector(OpRight, HalfThick, OpBottom),
                    FVector(OpRight, -HalfThick, OpBottom),
                    FVector(0, 0, 1)
                );
                // Bottom face
                AddQuad(
                    FVector(OpLeft, HalfThick, 0),
                    FVector(OpLeft, -HalfThick, 0),
                    FVector(OpRight, -HalfThick, 0),
                    FVector(OpRight, HalfThick, 0),
                    FVector(0, 0, -1)
                );
            }

            // Left jamb reveal (inside the opening)
            AddQuad(
                FVector(OpLeft, HalfThick, OpBottom),
                FVector(OpLeft, -HalfThick, OpBottom),
                FVector(OpLeft, -HalfThick, OpTop),
                FVector(OpLeft, HalfThick, OpTop),
                FVector(-1, 0, 0)
            );

            // Right jamb reveal
            AddQuad(
                FVector(OpRight, -HalfThick, OpBottom),
                FVector(OpRight, HalfThick, OpBottom),
                FVector(OpRight, HalfThick, OpTop),
                FVector(OpRight, -HalfThick, OpTop),
                FVector(1, 0, 0)
            );

            // Move current position past this opening
            CurrentX = OpRight;
        }
    }

    UE_LOG(LogTemp, Warning, TEXT("Element[%d] WallIndex=%d: Creating mesh with %d openings: %d verts, %d tris"),
           ElementIndex, WallIndex, Openings.Num(), Vertices.Num(), Triangles.Num() / 3);
    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);
    // Position at horizontal center but at floor level (Start.Z)
    // Mesh vertices are X: -HalfLen to +HalfLen (centered), Z: 0 to WallHeight (from floor)
    FVector MeshPosition = FVector(Center.X, Center.Y, Start.Z);
    MeshComp->SetWorldLocation(MeshPosition);
    MeshComp->SetWorldRotation(Dir.Rotation());
}

void AArchBuildingActor::GenerateSlabMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element)
{
    FVector Start = KernelToUnreal(Element.Start);
    FVector End = KernelToUnreal(Element.End);
    FVector Center = (Start + End) * 0.5f;

    float Width = FMath::Abs(End.X - Start.X);
    float Depth = FMath::Abs(End.Y - Start.Y);
    float Thickness = Element.Depth * ScaleFactor;

    FVector Extents(Width * 0.5f, Depth * 0.5f, Thickness * 0.5f);

    CreateBoxMesh(MeshComp, FVector::ZeroVector, Extents, GetMaterialColor(Element.Material));
    MeshComp->SetWorldLocation(Center);
}

void AArchBuildingActor::GenerateCustomMesh(UProceduralMeshComponent* MeshComp, const FArchElement& Element)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FLinearColor Color = GetStressColor(Element.Stress);
    FColor VertColor = Color.ToFColor(true);

    // Convert vertices
    for (const FVector& V : Element.Mesh.Vertices)
    {
        Vertices.Add(KernelToUnreal(V));
        Colors.Add(VertColor);
        UVs.Add(FVector2D(0, 0));
    }

    // Copy triangles
    Triangles = Element.Mesh.Triangles;

    // Calculate normals
    Normals.SetNum(Vertices.Num());
    for (int32 i = 0; i < Triangles.Num(); i += 3)
    {
        int32 I0 = Triangles[i];
        int32 I1 = Triangles[i + 1];
        int32 I2 = Triangles[i + 2];

        FVector V0 = Vertices[I0];
        FVector V1 = Vertices[I1];
        FVector V2 = Vertices[I2];

        FVector Normal = FVector::CrossProduct(V1 - V0, V2 - V0).GetSafeNormal();
        Normals[I0] = Normal;
        Normals[I1] = Normal;
        Normals[I2] = Normal;
    }

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);
}

void AArchBuildingActor::CreateBoxMesh(UProceduralMeshComponent* MeshComp, FVector Center, FVector Extents, FLinearColor Color)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor VertColor = Color.ToFColor(true);

    // 8 corners of box
    FVector Corners[8] = {
        Center + FVector(-Extents.X, -Extents.Y, -Extents.Z),
        Center + FVector(+Extents.X, -Extents.Y, -Extents.Z),
        Center + FVector(+Extents.X, +Extents.Y, -Extents.Z),
        Center + FVector(-Extents.X, +Extents.Y, -Extents.Z),
        Center + FVector(-Extents.X, -Extents.Y, +Extents.Z),
        Center + FVector(+Extents.X, -Extents.Y, +Extents.Z),
        Center + FVector(+Extents.X, +Extents.Y, +Extents.Z),
        Center + FVector(-Extents.X, +Extents.Y, +Extents.Z)
    };

    // Create 6 faces (24 vertices for proper normals)
    auto AddFace = [&](int32 A, int32 B, int32 C, int32 D, FVector Normal)
    {
        int32 StartIdx = Vertices.Num();
        Vertices.Add(Corners[A]);
        Vertices.Add(Corners[B]);
        Vertices.Add(Corners[C]);
        Vertices.Add(Corners[D]);

        Normals.Add(Normal);
        Normals.Add(Normal);
        Normals.Add(Normal);
        Normals.Add(Normal);

        UVs.Add(FVector2D(0, 0));
        UVs.Add(FVector2D(1, 0));
        UVs.Add(FVector2D(1, 1));
        UVs.Add(FVector2D(0, 1));

        Colors.Add(VertColor);
        Colors.Add(VertColor);
        Colors.Add(VertColor);
        Colors.Add(VertColor);

        Triangles.Add(StartIdx + 0);
        Triangles.Add(StartIdx + 1);
        Triangles.Add(StartIdx + 2);
        Triangles.Add(StartIdx + 0);
        Triangles.Add(StartIdx + 2);
        Triangles.Add(StartIdx + 3);
    };

    AddFace(0, 1, 2, 3, FVector(0, 0, -1));  // Bottom
    AddFace(4, 7, 6, 5, FVector(0, 0, +1));  // Top
    AddFace(0, 4, 5, 1, FVector(0, -1, 0));  // Front
    AddFace(2, 6, 7, 3, FVector(0, +1, 0));  // Back
    AddFace(0, 3, 7, 4, FVector(-1, 0, 0));  // Left
    AddFace(1, 5, 6, 2, FVector(+1, 0, 0));  // Right

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);
}

void AArchBuildingActor::SetVisualizationMode(EVisualizationMode NewMode)
{
    VisualizationMode = NewMode;
    UpdateMaterialColors();
}

void AArchBuildingActor::UpdateMaterialColors()
{
    for (int32 i = 0; i < BuildingData.Elements.Num() && i < DynamicMaterials.Num(); i++)
    {
        const FArchElement& Element = BuildingData.Elements[i];
        UMaterialInstanceDynamic* DynMat = DynamicMaterials[i];

        if (!DynMat) continue;

        FLinearColor Color;
        switch (VisualizationMode)
        {
            case EVisualizationMode::Structural:
                Color = GetStressColor(Element.Stress);
                break;
            case EVisualizationMode::Material:
                Color = GetMaterialColor(Element.Material);
                break;
            default:
                Color = FLinearColor::White;
                break;
        }

        DynMat->SetVectorParameterValue(TEXT("BaseColor"), Color);
    }
}

FLinearColor AArchBuildingActor::GetStressColor(float Stress)
{
    // Matches kernel StressColors
    const FLinearColor SAFE(0.133f, 0.773f, 0.369f, 1.0f);      // Green
    const FLinearColor WARNING(0.918f, 0.702f, 0.031f, 1.0f);   // Yellow
    const FLinearColor CRITICAL(0.976f, 0.451f, 0.086f, 1.0f);  // Orange
    const FLinearColor FAILURE(0.937f, 0.267f, 0.267f, 1.0f);   // Red

    if (Stress < 0.7f) return SAFE;
    if (Stress < 0.9f) return FMath::Lerp(SAFE, WARNING, (Stress - 0.7f) / 0.2f);
    if (Stress < 1.0f) return FMath::Lerp(WARNING, CRITICAL, (Stress - 0.9f) / 0.1f);
    return FMath::Lerp(CRITICAL, FAILURE, FMath::Min((Stress - 1.0f) / 0.5f, 1.0f));
}

FLinearColor AArchBuildingActor::GetMaterialColor(const FString& Material)
{
    if (Material == TEXT("steel")) return FLinearColor(0.5f, 0.5f, 0.6f);
    if (Material == TEXT("concrete")) return FLinearColor(0.7f, 0.7f, 0.7f);
    if (Material == TEXT("wood")) return FLinearColor(0.8f, 0.6f, 0.4f);
    if (Material == TEXT("glass")) return FLinearColor(0.7f, 0.9f, 1.0f);
    if (Material == TEXT("door")) return FLinearColor(0.5f, 0.3f, 0.2f);
    if (Material == TEXT("roof")) return FLinearColor(0.3f, 0.3f, 0.35f);
    return FLinearColor::White;
}

FVector AArchBuildingActor::KernelToUnreal(const FVector& KernelPos) const
{
    // Kernel uses Y-up, Unreal uses Z-up
    // Kernel: X=right, Y=up, Z=forward
    // Unreal: X=forward, Y=right, Z=up
    return FVector(
        KernelPos.Z * ScaleFactor,   // Kernel Z -> Unreal X
        KernelPos.X * ScaleFactor,   // Kernel X -> Unreal Y
        KernelPos.Y * ScaleFactor    // Kernel Y -> Unreal Z
    );
}

bool AArchBuildingActor::GetWallGeometry(int32 WallIndex, FVector& OutStart, FVector& OutEnd, FVector& OutDir, FVector& OutNormal) const
{
    if (WallIndex < 0 || WallIndex >= BuildingData.Elements.Num())
    {
        return false;
    }

    const FArchElement& Wall = BuildingData.Elements[WallIndex];
    OutStart = KernelToUnreal(Wall.Start);
    OutEnd = KernelToUnreal(Wall.End);

    // Direction along the wall (horizontal)
    FVector HorizDir = FVector(OutEnd.X - OutStart.X, OutEnd.Y - OutStart.Y, 0.0f);
    OutDir = HorizDir.GetSafeNormal();

    // Normal perpendicular to wall
    OutNormal = FVector(-OutDir.Y, OutDir.X, 0.0f);

    return true;
}

void AArchBuildingActor::GenerateDoorMesh(UProceduralMeshComponent* MeshComp, const FArchDoor& Door)
{
    FVector WallStart, WallEnd, WallDir, WallNormal;
    if (!GetWallGeometry(Door.WallIndex, WallStart, WallEnd, WallDir, WallNormal))
    {
        UE_LOG(LogTemp, Warning, TEXT("GenerateDoorMesh: Failed to get wall geometry for wall index %d"), Door.WallIndex);
        return;
    }

    UE_LOG(LogTemp, Log, TEXT("GenerateDoorMesh: Door on wall %d, offset=%.1f, size=%.1fx%.1f"),
        Door.WallIndex, Door.Offset, Door.Width, Door.Height);

    // Door dimensions (already in cm from loader, convert to Unreal units)
    float DoorWidth = Door.Width * ScaleFactor;
    float DoorHeight = Door.Height * ScaleFactor;
    float DoorOffset = Door.Offset * ScaleFactor;

    // Frame dimensions (in Unreal units - 5cm = 5 * ScaleFactor / 100)
    float FrameWidth = 5.0f * ScaleFactor;     // 5cm frame width
    float FrameDepth = 3.0f * ScaleFactor;     // 3cm frame depth
    float PanelThick = 4.0f * ScaleFactor;     // 4cm door panel thickness

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor WoodColor = FLinearColor(0.45f, 0.28f, 0.15f).ToFColor(true);
    FColor FrameColor = FLinearColor(0.35f, 0.22f, 0.12f).ToFColor(true);

    float HalfWidth = DoorWidth * 0.5f;

    // Lambda to add a quad with color
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Door panel (in local space, X = along wall, Y = thickness, Z = height)
    float PanelHalfW = HalfWidth - FrameWidth;
    float PanelHalfT = PanelThick * 0.5f;
    float PanelH = DoorHeight - FrameWidth;

    // Front face of door panel
    AddQuad(FVector(-PanelHalfW, PanelHalfT, 0), FVector(PanelHalfW, PanelHalfT, 0),
            FVector(PanelHalfW, PanelHalfT, PanelH), FVector(-PanelHalfW, PanelHalfT, PanelH),
            FVector(0, 1, 0), WoodColor);
    // Back face
    AddQuad(FVector(PanelHalfW, -PanelHalfT, 0), FVector(-PanelHalfW, -PanelHalfT, 0),
            FVector(-PanelHalfW, -PanelHalfT, PanelH), FVector(PanelHalfW, -PanelHalfT, PanelH),
            FVector(0, -1, 0), WoodColor);
    // Top
    AddQuad(FVector(-PanelHalfW, -PanelHalfT, PanelH), FVector(-PanelHalfW, PanelHalfT, PanelH),
            FVector(PanelHalfW, PanelHalfT, PanelH), FVector(PanelHalfW, -PanelHalfT, PanelH),
            FVector(0, 0, 1), WoodColor);
    // Left edge
    AddQuad(FVector(-PanelHalfW, -PanelHalfT, 0), FVector(-PanelHalfW, PanelHalfT, 0),
            FVector(-PanelHalfW, PanelHalfT, PanelH), FVector(-PanelHalfW, -PanelHalfT, PanelH),
            FVector(-1, 0, 0), WoodColor);
    // Right edge
    AddQuad(FVector(PanelHalfW, PanelHalfT, 0), FVector(PanelHalfW, -PanelHalfT, 0),
            FVector(PanelHalfW, -PanelHalfT, PanelH), FVector(PanelHalfW, PanelHalfT, PanelH),
            FVector(1, 0, 0), WoodColor);

    // Door frame - left jamb
    float FrameHalfD = FrameDepth * 0.5f;
    AddQuad(FVector(-HalfWidth, FrameHalfD, 0), FVector(-HalfWidth + FrameWidth, FrameHalfD, 0),
            FVector(-HalfWidth + FrameWidth, FrameHalfD, DoorHeight), FVector(-HalfWidth, FrameHalfD, DoorHeight),
            FVector(0, 1, 0), FrameColor);
    // Right jamb
    AddQuad(FVector(HalfWidth - FrameWidth, FrameHalfD, 0), FVector(HalfWidth, FrameHalfD, 0),
            FVector(HalfWidth, FrameHalfD, DoorHeight), FVector(HalfWidth - FrameWidth, FrameHalfD, DoorHeight),
            FVector(0, 1, 0), FrameColor);
    // Head (top frame)
    AddQuad(FVector(-HalfWidth, FrameHalfD, DoorHeight - FrameWidth), FVector(HalfWidth, FrameHalfD, DoorHeight - FrameWidth),
            FVector(HalfWidth, FrameHalfD, DoorHeight), FVector(-HalfWidth, FrameHalfD, DoorHeight),
            FVector(0, 1, 0), FrameColor);

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position at door location
    FVector DoorPos = WallStart + WallDir * DoorOffset;
    MeshComp->SetWorldLocation(DoorPos);
    MeshComp->SetWorldRotation(WallDir.Rotation());
}

void AArchBuildingActor::GenerateWindowMesh(UProceduralMeshComponent* MeshComp, const FArchWindow& Window)
{
    FVector WallStart, WallEnd, WallDir, WallNormal;
    if (!GetWallGeometry(Window.WallIndex, WallStart, WallEnd, WallDir, WallNormal))
    {
        UE_LOG(LogTemp, Warning, TEXT("GenerateWindowMesh: Failed to get wall geometry for wall index %d"), Window.WallIndex);
        return;
    }

    UE_LOG(LogTemp, Log, TEXT("GenerateWindowMesh: Window on wall %d, offset=%.1f, size=%.1fx%.1f, sill=%.1f"),
        Window.WallIndex, Window.Offset, Window.Width, Window.Height, Window.SillHeight);

    // Window dimensions (already in cm from loader, convert to Unreal units)
    float WinWidth = Window.Width * ScaleFactor;
    float WinHeight = Window.Height * ScaleFactor;
    float WinOffset = Window.Offset * ScaleFactor;
    float SillZ = Window.SillHeight * ScaleFactor;

    // Frame dimensions (in Unreal units)
    float FrameWidth = 5.0f * ScaleFactor;     // 5cm frame width
    float FrameDepth = 7.0f * ScaleFactor;     // 7cm frame depth
    float GlassThick = 1.0f * ScaleFactor;     // 1cm glass thickness

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor FrameColor = FLinearColor(0.85f, 0.85f, 0.85f).ToFColor(true);  // Light gray/white frame
    FColor GlassColor = FLinearColor(0.6f, 0.75f, 0.9f).ToFColor(true);    // Light blue glass

    float HalfWidth = WinWidth * 0.5f;
    float HalfHeight = WinHeight * 0.5f;
    float FrameHalfD = FrameDepth * 0.5f;

    // Lambda to add a quad with color
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Glass pane (centered)
    float GlassHalfW = HalfWidth - FrameWidth;
    float GlassHalfH = HalfHeight - FrameWidth;
    float GlassHalfT = GlassThick * 0.5f;

    // Front face of glass
    AddQuad(FVector(-GlassHalfW, GlassHalfT, -GlassHalfH), FVector(GlassHalfW, GlassHalfT, -GlassHalfH),
            FVector(GlassHalfW, GlassHalfT, GlassHalfH), FVector(-GlassHalfW, GlassHalfT, GlassHalfH),
            FVector(0, 1, 0), GlassColor);
    // Back face of glass
    AddQuad(FVector(GlassHalfW, -GlassHalfT, -GlassHalfH), FVector(-GlassHalfW, -GlassHalfT, -GlassHalfH),
            FVector(-GlassHalfW, -GlassHalfT, GlassHalfH), FVector(GlassHalfW, -GlassHalfT, GlassHalfH),
            FVector(0, -1, 0), GlassColor);

    // Window frame - bottom sill
    AddQuad(FVector(-HalfWidth, FrameHalfD, -HalfHeight), FVector(HalfWidth, FrameHalfD, -HalfHeight),
            FVector(HalfWidth, FrameHalfD, -HalfHeight + FrameWidth), FVector(-HalfWidth, FrameHalfD, -HalfHeight + FrameWidth),
            FVector(0, 1, 0), FrameColor);
    // Top frame
    AddQuad(FVector(-HalfWidth, FrameHalfD, HalfHeight - FrameWidth), FVector(HalfWidth, FrameHalfD, HalfHeight - FrameWidth),
            FVector(HalfWidth, FrameHalfD, HalfHeight), FVector(-HalfWidth, FrameHalfD, HalfHeight),
            FVector(0, 1, 0), FrameColor);
    // Left frame
    AddQuad(FVector(-HalfWidth, FrameHalfD, -HalfHeight), FVector(-HalfWidth + FrameWidth, FrameHalfD, -HalfHeight),
            FVector(-HalfWidth + FrameWidth, FrameHalfD, HalfHeight), FVector(-HalfWidth, FrameHalfD, HalfHeight),
            FVector(0, 1, 0), FrameColor);
    // Right frame
    AddQuad(FVector(HalfWidth - FrameWidth, FrameHalfD, -HalfHeight), FVector(HalfWidth, FrameHalfD, -HalfHeight),
            FVector(HalfWidth, FrameHalfD, HalfHeight), FVector(HalfWidth - FrameWidth, FrameHalfD, HalfHeight),
            FVector(0, 1, 0), FrameColor);

    // Center mullion (vertical divider) for double-hung look
    if (Window.Type == EArchWindowType::DoubleHung || Window.Type == EArchWindowType::Casement)
    {
        float MullionHalfW = 2.0f * ScaleFactor;  // 4cm wide mullion
        AddQuad(FVector(-MullionHalfW, FrameHalfD, -GlassHalfH), FVector(MullionHalfW, FrameHalfD, -GlassHalfH),
                FVector(MullionHalfW, FrameHalfD, GlassHalfH), FVector(-MullionHalfW, FrameHalfD, GlassHalfH),
                FVector(0, 1, 0), FrameColor);
    }

    // Horizontal meeting rail for double-hung
    if (Window.Type == EArchWindowType::DoubleHung)
    {
        float RailHalfH = 2.0f * ScaleFactor;
        AddQuad(FVector(-GlassHalfW, FrameHalfD, -RailHalfH), FVector(GlassHalfW, FrameHalfD, -RailHalfH),
                FVector(GlassHalfW, FrameHalfD, RailHalfH), FVector(-GlassHalfW, FrameHalfD, RailHalfH),
                FVector(0, 1, 0), FrameColor);
    }

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position at window location (center of window)
    FVector WinPos = WallStart + WallDir * WinOffset;
    WinPos.Z = WallStart.Z + SillZ + HalfHeight;
    MeshComp->SetWorldLocation(WinPos);
    MeshComp->SetWorldRotation(WallDir.Rotation());
}

// ============================================================================
// SECTION VIEW IMPLEMENTATION
// ============================================================================

FLinearColor AArchBuildingActor::GetLayerColor(ELayerFunction Function)
{
    switch (Function)
    {
        case ELayerFunction::ExteriorFinish:
            return FLinearColor(0.2f, 0.6f, 0.2f);      // Green - siding
        case ELayerFunction::Sheathing:
            return FLinearColor(1.0f, 0.6f, 0.0f);      // Orange - OSB/plywood
        case ELayerFunction::Insulation:
            return FLinearColor(1.0f, 0.4f, 0.7f);      // Hot pink - fiberglass
        case ELayerFunction::Structure:
            return FLinearColor(0.8f, 0.5f, 0.2f);      // Brown - wood studs
        case ELayerFunction::InteriorFinish:
            return FLinearColor(0.9f, 0.9f, 0.8f);      // Off-white - drywall
        case ELayerFunction::AirGap:
            return FLinearColor(0.3f, 0.7f, 1.0f);      // Sky blue - air gap
        case ELayerFunction::Membrane:
            return FLinearColor(0.0f, 0.4f, 0.9f);      // Bright blue - vapor barrier
        default:
            return FLinearColor(0.5f, 0.5f, 0.5f);      // Gray
    }
}

void AArchBuildingActor::SetSectionViewMode(ESectionViewMode NewMode)
{
    SectionViewMode = NewMode;

    UE_LOG(LogTemp, Log, TEXT("SetSectionViewMode: %d"), (int)NewMode);

    if (NewMode == ESectionViewMode::Solid)
    {
        // Show solid walls, hide layer meshes
        ClearLayerMeshes();

        // Hide section plane indicator
        if (SectionPlaneMesh)
        {
            SectionPlaneMesh->SetVisibility(false);
        }

        // Show ALL element meshes (walls, doors, windows)
        for (UProceduralMeshComponent* Mesh : ElementMeshes)
        {
            if (Mesh)
            {
                Mesh->SetVisibility(true);
            }
        }
    }
    else
    {
        // Calculate building bounds first
        CalculateBuildingBounds();

        // Update section plane from alpha slider
        UpdateSectionPlaneFromAlpha();

        // Show section plane indicator
        UpdateSectionPlaneMesh();
        if (SectionPlaneMesh && bShowSectionPlane)
        {
            SectionPlaneMesh->SetVisibility(true);
        }

        // Always regenerate section geometry when switching to section/exploded mode
        GenerateSectionGeometry();

        // Hide wall element meshes, keep doors/windows visible
        for (int32 i = 0; i < BuildingData.Elements.Num() && i < ElementMeshes.Num(); i++)
        {
            if (ElementMeshes[i])
            {
                ElementMeshes[i]->SetVisibility(false);
            }
        }

        // Doors and windows remain visible
        for (int32 i = BuildingData.Elements.Num(); i < ElementMeshes.Num(); i++)
        {
            if (ElementMeshes[i])
            {
                ElementMeshes[i]->SetVisibility(true);
            }
        }

        // Enable material-based clipping and update parameters
        UpdateSectionMaterialParams();
        UpdateSectionVisibility();
    }
}

void AArchBuildingActor::SetSectionPlane(FVector Position, FVector Normal)
{
    SectionPlanePosition = Position;
    SectionPlaneNormal = Normal.GetSafeNormal();
    UpdateSectionVisibility();
}

void AArchBuildingActor::AnimateSectionPlane(float Alpha)
{
    if (!BuildingBounds.IsValid)
    {
        CalculateBuildingBounds();
    }

    // Animate plane from min to max along the normal direction
    FVector Min = BuildingBounds.Min;
    FVector Max = BuildingBounds.Max;
    FVector Center = BuildingBounds.GetCenter();

    // Default: animate along Y axis (front to back)
    float MinY = Min.Y - 100.0f;
    float MaxY = Max.Y + 100.0f;

    SectionPlanePosition = FVector(Center.X, FMath::Lerp(MinY, MaxY, Alpha), Center.Z);
    SectionPlaneNormal = FVector(0, 1, 0);

    UpdateSectionVisibility();
}

void AArchBuildingActor::GenerateSectionGeometry()
{
    ClearLayerMeshes();
    CalculateBuildingBounds();

    // Load clipping material if not already loaded
    if (!ClippingBaseMaterial)
    {
        LoadClippingMaterial();
    }

    // Generate layer meshes for each parametric wall
    for (int32 WallIdx = 0; WallIdx < BuildingData.ParametricWalls.Num(); WallIdx++)
    {
        const FArchParametricWall& ParamWall = BuildingData.ParametricWalls[WallIdx];

        // Get wall type
        if (ParamWall.WallTypeIndex >= 0 && ParamWall.WallTypeIndex < BuildingData.WallTypes.Num())
        {
            const FArchWallType& WallType = BuildingData.WallTypes[ParamWall.WallTypeIndex];
            GenerateWallLayerMeshes(WallIdx, ParamWall, WallType);
        }
    }

    UE_LOG(LogTemp, Log, TEXT("Generated %d layer meshes for section view"), LayerMeshes.Num());
}

void AArchBuildingActor::GenerateWallLayerMeshes(int32 WallIndex, const FArchParametricWall& ParamWall, const FArchWallType& WallType)
{
    if (WallIndex >= BuildingData.Elements.Num()) return;

    const FArchElement& Element = BuildingData.Elements[WallIndex];

    FVector Start = KernelToUnreal(Element.Start);
    FVector End = KernelToUnreal(Element.End);
    float WallHeight = End.Z - Start.Z;

    // Wall direction, center, and normal
    FVector Dir = FVector(End.X - Start.X, End.Y - Start.Y, 0).GetSafeNormal();
    FVector Normal = FVector(-Dir.Y, Dir.X, 0);

    // Calculate wall center for positioning mesh (horizontal center at floor level)
    FVector WallCenter = FVector((Start.X + End.X) * 0.5f, (Start.Y + End.Y) * 0.5f, Start.Z);

    // Calculate wall endpoints at floor level (for visibility checks)
    FVector WallStartFloor = FVector(Start.X, Start.Y, Start.Z);
    FVector WallEndFloor = FVector(End.X, End.Y, Start.Z);

    // Collect openings for this wall
    TArray<FWallOpening> Openings;
    for (const FArchDoor& Door : BuildingData.Doors)
    {
        if (Door.WallIndex == WallIndex)
        {
            FWallOpening Op;
            Op.OffsetAlongWall = Door.Offset * ScaleFactor;
            Op.Width = Door.Width * ScaleFactor;
            Op.Height = Door.Height * ScaleFactor;
            Op.BottomZ = 0.0f;
            Op.bIsDoor = true;
            Openings.Add(Op);
        }
    }
    for (const FArchWindow& Window : BuildingData.Windows)
    {
        if (Window.WallIndex == WallIndex)
        {
            FWallOpening Op;
            Op.OffsetAlongWall = Window.Offset * ScaleFactor;
            Op.Width = Window.Width * ScaleFactor;
            Op.Height = Window.Height * ScaleFactor;
            Op.BottomZ = Window.SillHeight * ScaleFactor;
            Op.bIsDoor = false;
            Openings.Add(Op);
        }
    }
    Openings.Sort([](const FWallOpening& A, const FWallOpening& B) {
        return A.OffsetAlongWall < B.OffsetAlongWall;
    });

    // Calculate total thickness and start position
    float TotalThickness = WallType.GetTotalThickness() * ScaleFactor;
    float CurrentDepth = -TotalThickness * 0.5f;  // Start from exterior side

    // Generate mesh for each layer
    for (int32 LayerIdx = 0; LayerIdx < WallType.Layers.Num(); LayerIdx++)
    {
        const FArchWallLayer& Layer = WallType.Layers[LayerIdx];
        float LayerThick = Layer.Thickness * ScaleFactor;

        // Create mesh component for this layer
        FString CompName = FString::Printf(TEXT("Wall%d_Layer%d_%s"), WallIndex, LayerIdx, *Layer.Name);
        UProceduralMeshComponent* MeshComp = NewObject<UProceduralMeshComponent>(this, *CompName);
        MeshComp->SetupAttachment(RootComponent);
        MeshComp->RegisterComponent();

        // Create material with layer color - use clipping material if available
        UMaterialInterface* MaterialToUse = ClippingBaseMaterial ? ClippingBaseMaterial : BaseMaterial;
        if (MaterialToUse)
        {
            UMaterialInstanceDynamic* DynMat = UMaterialInstanceDynamic::Create(MaterialToUse, this);
            FLinearColor LayerColor = Layer.Color.A > 0.01f ? Layer.Color : GetLayerColor(Layer.Function);
            DynMat->SetVectorParameterValue(TEXT("BaseColor"), LayerColor);

            // Initialize section plane parameters
            DynMat->SetVectorParameterValue(TEXT("SectionPlanePos"),
                FLinearColor(SectionPlanePosition.X, SectionPlanePosition.Y, SectionPlanePosition.Z, 1.0f));
            DynMat->SetVectorParameterValue(TEXT("SectionPlaneNormal"),
                FLinearColor(SectionPlaneNormal.X, SectionPlaneNormal.Y, SectionPlaneNormal.Z, 0.0f));
            DynMat->SetScalarParameterValue(TEXT("ClipEnabled"), 0.0f);

            MeshComp->SetMaterial(0, DynMat);
            LayerMaterials.Add(DynMat);
        }

        GenerateLayerMesh(MeshComp, Layer, Start, End, WallHeight, CurrentDepth, LayerThick, LayerIdx, Openings);

        // Position and rotate mesh to match wall orientation
        MeshComp->SetWorldLocation(WallCenter);
        MeshComp->SetWorldRotation(Dir.Rotation());

        LayerMeshes.Add(MeshComp);

        // Store wall info for visibility calculations
        FLayerMeshInfo Info;
        Info.WallStart = WallStartFloor;
        Info.WallEnd = WallEndFloor;
        Info.WallCenter = WallCenter + FVector(0, 0, WallHeight * 0.5f);  // Center including height
        Info.WallHeight = WallHeight;
        LayerMeshInfos.Add(Info);

        CurrentDepth += LayerThick;
    }
}

void AArchBuildingActor::GenerateLayerMesh(UProceduralMeshComponent* MeshComp, const FArchWallLayer& Layer,
                                            FVector WallStart, FVector WallEnd, float WallHeight,
                                            float LayerStartDepth, float LayerThickness, int32 LayerIndex,
                                            const TArray<FWallOpening>& Openings)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FLinearColor LayerColor = Layer.Color.A > 0.01f ? Layer.Color : GetLayerColor(Layer.Function);
    FColor VertColor = LayerColor.ToFColor(true);

    FVector Dir = FVector(WallEnd.X - WallStart.X, WallEnd.Y - WallStart.Y, 0).GetSafeNormal();

    float WallLength = FMath::Sqrt(FMath::Square(WallEnd.X - WallStart.X) + FMath::Square(WallEnd.Y - WallStart.Y));
    float HalfLen = WallLength * 0.5f;

    // In local space: X along wall, Y is depth (into wall), Z is height
    float Y0 = LayerStartDepth;
    float Y1 = LayerStartDepth + LayerThickness;

    // Exploded view offset
    float ExplodeOffset = 0.0f;
    if (SectionViewMode == ESectionViewMode::Exploded)
    {
        ExplodeOffset = LayerIndex * ExplodedSeparation;
    }
    Y0 += ExplodeOffset;
    Y1 += ExplodeOffset;

    // Lambda to add quad
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(VertColor); Colors.Add(VertColor); Colors.Add(VertColor); Colors.Add(VertColor);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // If no openings, generate simple box
    if (Openings.Num() == 0)
    {
        // Front face
        AddQuad(FVector(-HalfLen, Y1, 0), FVector(HalfLen, Y1, 0),
                FVector(HalfLen, Y1, WallHeight), FVector(-HalfLen, Y1, WallHeight), FVector(0, 1, 0));
        // Back face
        AddQuad(FVector(HalfLen, Y0, 0), FVector(-HalfLen, Y0, 0),
                FVector(-HalfLen, Y0, WallHeight), FVector(HalfLen, Y0, WallHeight), FVector(0, -1, 0));
        // Top face
        AddQuad(FVector(-HalfLen, Y0, WallHeight), FVector(-HalfLen, Y1, WallHeight),
                FVector(HalfLen, Y1, WallHeight), FVector(HalfLen, Y0, WallHeight), FVector(0, 0, 1));
        // Bottom face
        AddQuad(FVector(-HalfLen, Y1, 0), FVector(-HalfLen, Y0, 0),
                FVector(HalfLen, Y0, 0), FVector(HalfLen, Y1, 0), FVector(0, 0, -1));
        // Left cap
        AddQuad(FVector(-HalfLen, Y0, 0), FVector(-HalfLen, Y1, 0),
                FVector(-HalfLen, Y1, WallHeight), FVector(-HalfLen, Y0, WallHeight), FVector(-1, 0, 0));
        // Right cap
        AddQuad(FVector(HalfLen, Y1, 0), FVector(HalfLen, Y0, 0),
                FVector(HalfLen, Y0, WallHeight), FVector(HalfLen, Y1, WallHeight), FVector(1, 0, 0));
    }
    else
    {
        // Generate layer with openings (similar to wall mesh generation)
        float CurrentX = -HalfLen;

        for (int32 i = 0; i <= Openings.Num(); i++)
        {
            float SegmentEnd;
            if (i < Openings.Num())
            {
                SegmentEnd = Openings[i].OffsetAlongWall - Openings[i].Width * 0.5f - HalfLen;
            }
            else
            {
                SegmentEnd = HalfLen;
            }

            // Generate solid segment from CurrentX to SegmentEnd (full height)
            if (SegmentEnd > CurrentX + 0.1f)
            {
                // Front face
                AddQuad(FVector(CurrentX, Y1, 0), FVector(SegmentEnd, Y1, 0),
                        FVector(SegmentEnd, Y1, WallHeight), FVector(CurrentX, Y1, WallHeight), FVector(0, 1, 0));
                // Back face
                AddQuad(FVector(SegmentEnd, Y0, 0), FVector(CurrentX, Y0, 0),
                        FVector(CurrentX, Y0, WallHeight), FVector(SegmentEnd, Y0, WallHeight), FVector(0, -1, 0));
                // Top face
                AddQuad(FVector(CurrentX, Y0, WallHeight), FVector(CurrentX, Y1, WallHeight),
                        FVector(SegmentEnd, Y1, WallHeight), FVector(SegmentEnd, Y0, WallHeight), FVector(0, 0, 1));
                // Bottom face
                AddQuad(FVector(CurrentX, Y1, 0), FVector(CurrentX, Y0, 0),
                        FVector(SegmentEnd, Y0, 0), FVector(SegmentEnd, Y1, 0), FVector(0, 0, -1));
                // Left cap (first segment only)
                if (i == 0)
                {
                    AddQuad(FVector(CurrentX, Y0, 0), FVector(CurrentX, Y1, 0),
                            FVector(CurrentX, Y1, WallHeight), FVector(CurrentX, Y0, WallHeight), FVector(-1, 0, 0));
                }
                // Right cap (last segment only)
                if (i == Openings.Num())
                {
                    AddQuad(FVector(SegmentEnd, Y1, 0), FVector(SegmentEnd, Y0, 0),
                            FVector(SegmentEnd, Y0, WallHeight), FVector(SegmentEnd, Y1, WallHeight), FVector(1, 0, 0));
                }
            }

            // Generate geometry around opening
            if (i < Openings.Num())
            {
                const FWallOpening& Op = Openings[i];
                float OpLeft = Op.OffsetAlongWall - Op.Width * 0.5f - HalfLen;
                float OpRight = Op.OffsetAlongWall + Op.Width * 0.5f - HalfLen;
                float OpBottom = Op.BottomZ;
                float OpTop = Op.BottomZ + Op.Height;

                // Header (above opening)
                if (OpTop < WallHeight - 0.1f)
                {
                    AddQuad(FVector(OpLeft, Y1, OpTop), FVector(OpRight, Y1, OpTop),
                            FVector(OpRight, Y1, WallHeight), FVector(OpLeft, Y1, WallHeight), FVector(0, 1, 0));
                    AddQuad(FVector(OpRight, Y0, OpTop), FVector(OpLeft, Y0, OpTop),
                            FVector(OpLeft, Y0, WallHeight), FVector(OpRight, Y0, WallHeight), FVector(0, -1, 0));
                    AddQuad(FVector(OpLeft, Y0, WallHeight), FVector(OpLeft, Y1, WallHeight),
                            FVector(OpRight, Y1, WallHeight), FVector(OpRight, Y0, WallHeight), FVector(0, 0, 1));
                    // Soffit (bottom of header)
                    AddQuad(FVector(OpLeft, Y1, OpTop), FVector(OpLeft, Y0, OpTop),
                            FVector(OpRight, Y0, OpTop), FVector(OpRight, Y1, OpTop), FVector(0, 0, -1));
                }

                // Sill (below opening - for windows)
                if (OpBottom > 0.1f)
                {
                    AddQuad(FVector(OpLeft, Y1, 0), FVector(OpRight, Y1, 0),
                            FVector(OpRight, Y1, OpBottom), FVector(OpLeft, Y1, OpBottom), FVector(0, 1, 0));
                    AddQuad(FVector(OpRight, Y0, 0), FVector(OpLeft, Y0, 0),
                            FVector(OpLeft, Y0, OpBottom), FVector(OpRight, Y0, OpBottom), FVector(0, -1, 0));
                    AddQuad(FVector(OpLeft, Y0, OpBottom), FVector(OpLeft, Y1, OpBottom),
                            FVector(OpRight, Y1, OpBottom), FVector(OpRight, Y0, OpBottom), FVector(0, 0, 1));
                    AddQuad(FVector(OpLeft, Y1, 0), FVector(OpLeft, Y0, 0),
                            FVector(OpRight, Y0, 0), FVector(OpRight, Y1, 0), FVector(0, 0, -1));
                }

                // Left jamb reveal
                AddQuad(FVector(OpLeft, Y1, OpBottom), FVector(OpLeft, Y0, OpBottom),
                        FVector(OpLeft, Y0, OpTop), FVector(OpLeft, Y1, OpTop), FVector(-1, 0, 0));

                // Right jamb reveal
                AddQuad(FVector(OpRight, Y0, OpBottom), FVector(OpRight, Y1, OpBottom),
                        FVector(OpRight, Y1, OpTop), FVector(OpRight, Y0, OpTop), FVector(1, 0, 0));

                CurrentX = OpRight;
            }
        }
    }

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position and rotate to match wall
    FVector Center = (WallStart + WallEnd) * 0.5f;
    Center.Z = WallStart.Z;
    MeshComp->SetWorldLocation(Center);
    MeshComp->SetWorldRotation(Dir.Rotation());
}

void AArchBuildingActor::UpdateSectionVisibility()
{
    if (SectionViewMode == ESectionViewMode::Solid)
    {
        return;
    }

    // Update material parameters for all layer meshes
    // This enables real-time clipping via the shader
    UpdateSectionMaterialParams();

    // All layer meshes stay visible - clipping is done by the material shader
    for (UProceduralMeshComponent* MeshComp : LayerMeshes)
    {
        if (MeshComp)
        {
            MeshComp->SetVisibility(true);
        }
    }
}

void AArchBuildingActor::ClearLayerMeshes()
{
    for (auto* MeshComp : LayerMeshes)
    {
        if (MeshComp)
        {
            MeshComp->DestroyComponent();
        }
    }
    LayerMeshes.Empty();
    LayerMaterials.Empty();
    LayerMeshInfos.Empty();
}

void AArchBuildingActor::CalculateBuildingBounds()
{
    BuildingBounds = FBox(ForceInit);

    for (const FArchElement& Element : BuildingData.Elements)
    {
        FVector Start = KernelToUnreal(Element.Start);
        FVector End = KernelToUnreal(Element.End);
        BuildingBounds += Start;
        BuildingBounds += End;
    }

    if (!BuildingBounds.IsValid)
    {
        BuildingBounds = FBox(FVector(-1000, -1000, 0), FVector(1000, 1000, 500));
    }
}

void AArchBuildingActor::UpdateSectionPlaneFromAlpha()
{
    if (!BuildingBounds.IsValid)
    {
        CalculateBuildingBounds();
    }

    FVector Min = BuildingBounds.Min;
    FVector Max = BuildingBounds.Max;
    FVector Center = BuildingBounds.GetCenter();

    // Add padding so plane extends beyond building
    const float Padding = 100.0f;

    switch (SectionAxis)
    {
    case ESectionAxis::X_LeftRight:
        // Cut along X axis (YZ plane)
        SectionPlanePosition = FVector(
            FMath::Lerp(Min.X - Padding, Max.X + Padding, SectionPlaneAlpha),
            Center.Y,
            Center.Z
        );
        SectionPlaneNormal = FVector(1, 0, 0);
        break;

    case ESectionAxis::Y_FrontBack:
        // Cut along Y axis (XZ plane) - Default
        SectionPlanePosition = FVector(
            Center.X,
            FMath::Lerp(Min.Y - Padding, Max.Y + Padding, SectionPlaneAlpha),
            Center.Z
        );
        SectionPlaneNormal = FVector(0, 1, 0);
        break;

    case ESectionAxis::Z_TopDown:
        // Cut along Z axis (XY plane)
        SectionPlanePosition = FVector(
            Center.X,
            Center.Y,
            FMath::Lerp(Min.Z - Padding, Max.Z + Padding, SectionPlaneAlpha)
        );
        SectionPlaneNormal = FVector(0, 0, 1);
        break;
    }

    UE_LOG(LogTemp, Log, TEXT("Section plane updated: Alpha=%.2f, Axis=%d, Pos=(%.0f, %.0f, %.0f)"),
        SectionPlaneAlpha, (int)SectionAxis,
        SectionPlanePosition.X, SectionPlanePosition.Y, SectionPlanePosition.Z);
}

void AArchBuildingActor::UpdateSectionPlaneMesh()
{
    if (!SectionPlaneMesh) return;

    if (!BuildingBounds.IsValid)
    {
        CalculateBuildingBounds();
    }

    // Clear existing mesh
    SectionPlaneMesh->ClearAllMeshSections();

    FVector Size = BuildingBounds.GetSize();
    FVector Center = BuildingBounds.GetCenter();
    FVector Min = BuildingBounds.Min;
    FVector Max = BuildingBounds.Max;

    // Make plane slightly larger than building
    const float Padding = 200.0f;

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor PlaneColor = FLinearColor(0.2f, 0.6f, 1.0f, 0.3f).ToFColor(true);

    // Create quad based on axis - vertices define the plane at SectionPlanePosition
    switch (SectionAxis)
    {
    case ESectionAxis::X_LeftRight:
        // YZ plane at X position - plane spans Y and Z of building
        Vertices.Add(FVector(SectionPlanePosition.X, Min.Y - Padding, Min.Z));
        Vertices.Add(FVector(SectionPlanePosition.X, Max.Y + Padding, Min.Z));
        Vertices.Add(FVector(SectionPlanePosition.X, Max.Y + Padding, Max.Z + Padding));
        Vertices.Add(FVector(SectionPlanePosition.X, Min.Y - Padding, Max.Z + Padding));
        for (int i = 0; i < 4; i++) Normals.Add(FVector(1, 0, 0));
        break;

    case ESectionAxis::Y_FrontBack:
        // XZ plane at Y position - plane spans X and Z of building
        Vertices.Add(FVector(Min.X - Padding, SectionPlanePosition.Y, Min.Z));
        Vertices.Add(FVector(Max.X + Padding, SectionPlanePosition.Y, Min.Z));
        Vertices.Add(FVector(Max.X + Padding, SectionPlanePosition.Y, Max.Z + Padding));
        Vertices.Add(FVector(Min.X - Padding, SectionPlanePosition.Y, Max.Z + Padding));
        for (int i = 0; i < 4; i++) Normals.Add(FVector(0, 1, 0));
        break;

    case ESectionAxis::Z_TopDown:
        // XY plane at Z position - plane spans X and Y of building
        Vertices.Add(FVector(Min.X - Padding, Min.Y - Padding, SectionPlanePosition.Z));
        Vertices.Add(FVector(Max.X + Padding, Min.Y - Padding, SectionPlanePosition.Z));
        Vertices.Add(FVector(Max.X + Padding, Max.Y + Padding, SectionPlanePosition.Z));
        Vertices.Add(FVector(Min.X - Padding, Max.Y + Padding, SectionPlanePosition.Z));
        for (int i = 0; i < 4; i++) Normals.Add(FVector(0, 0, 1));
        break;
    }

    UVs.Add(FVector2D(0, 0));
    UVs.Add(FVector2D(1, 0));
    UVs.Add(FVector2D(1, 1));
    UVs.Add(FVector2D(0, 1));

    for (int i = 0; i < 4; i++) Colors.Add(PlaneColor);

    // Two triangles for quad (both sides)
    Triangles.Add(0); Triangles.Add(1); Triangles.Add(2);
    Triangles.Add(0); Triangles.Add(2); Triangles.Add(3);
    // Back face
    Triangles.Add(0); Triangles.Add(2); Triangles.Add(1);
    Triangles.Add(0); Triangles.Add(3); Triangles.Add(2);

    // Tangents (not critical for simple plane)
    TArray<FProcMeshTangent> Tangents;
    for (int i = 0; i < 4; i++) Tangents.Add(FProcMeshTangent(1, 0, 0));

    SectionPlaneMesh->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);

    // Create translucent material for section plane
    if (!SectionPlaneMaterial && BaseMaterial)
    {
        SectionPlaneMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
        SectionPlaneMaterial->SetVectorParameterValue(TEXT("BaseColor"), FLinearColor(0.2f, 0.6f, 1.0f, 0.5f));
    }

    if (SectionPlaneMaterial)
    {
        SectionPlaneMesh->SetMaterial(0, SectionPlaneMaterial);
    }
}

void AArchBuildingActor::LoadClippingMaterial()
{
    // Try to load the clipping material from the specified path
    if (!ClippingMaterialPath.IsEmpty())
    {
        ClippingBaseMaterial = Cast<UMaterialInterface>(
            StaticLoadObject(UMaterialInterface::StaticClass(), nullptr, *ClippingMaterialPath));

        if (ClippingBaseMaterial)
        {
            UE_LOG(LogTemp, Log, TEXT("Loaded clipping material from: %s"), *ClippingMaterialPath);
        }
        else
        {
            UE_LOG(LogTemp, Warning, TEXT("Could not load clipping material from: %s - using default material"), *ClippingMaterialPath);
        }
    }
}

void AArchBuildingActor::UpdateSectionMaterialParams()
{
    float ClipEnabled = (SectionViewMode == ESectionViewMode::SectionCut) ? 1.0f : 0.0f;

    // Lambda to update a material with section plane parameters
    auto UpdateMaterial = [&](UMaterialInstanceDynamic* Mat) {
        if (Mat)
        {
            Mat->SetVectorParameterValue(TEXT("SectionPlanePos"),
                FLinearColor(SectionPlanePosition.X, SectionPlanePosition.Y, SectionPlanePosition.Z, 1.0f));
            Mat->SetVectorParameterValue(TEXT("SectionPlaneNormal"),
                FLinearColor(SectionPlaneNormal.X, SectionPlaneNormal.Y, SectionPlaneNormal.Z, 0.0f));
            Mat->SetScalarParameterValue(TEXT("ClipEnabled"), ClipEnabled);
        }
    };

    // Update layer mesh materials (walls in section view)
    for (UMaterialInstanceDynamic* Mat : LayerMaterials)
    {
        UpdateMaterial(Mat);
    }

    // Update element mesh materials (doors, windows, etc.)
    for (UMaterialInstanceDynamic* Mat : DynamicMaterials)
    {
        UpdateMaterial(Mat);
    }
}

// ============================================================================
// STAIR MESH GENERATION
// ============================================================================

void AArchBuildingActor::GenerateStairMesh(UProceduralMeshComponent* MeshComp, const FArchStair& Stair)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor TreadColor = FLinearColor(0.6f, 0.45f, 0.3f).ToFColor(true);  // Wood
    FColor RiserColor = FLinearColor(0.55f, 0.4f, 0.28f).ToFColor(true);
    FColor StringerColor = FLinearColor(0.5f, 0.35f, 0.22f).ToFColor(true);

    // Lambda to add a quad
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Get stair parameters (convert from mm to Unreal units)
    float StairWidth = Stair.Width * ScaleFactor / 10.0f;  // mm to cm to UE units
    float TreadDepth = Stair.TreadDepth * ScaleFactor / 10.0f;
    float RiserHeight = Stair.RiserHeight * ScaleFactor / 10.0f;
    float TreadThickness = 2.54f * ScaleFactor;  // 1" thick treads
    float RiserThickness = 1.905f * ScaleFactor; // 3/4" thick risers
    float NoseOverhang = 2.54f * ScaleFactor;    // 1" nosing

    int32 NumTreads = Stair.NumTreads > 0 ? Stair.NumTreads : FMath::CeilToInt(Stair.TotalRise / Stair.RiserHeight);
    float HalfWidth = StairWidth * 0.5f;

    // If we have explicit tread data, use it
    if (Stair.Treads.Num() > 0)
    {
        for (const FArchStairTread& Tread : Stair.Treads)
        {
            FVector TreadPos = FVector(
                Tread.Position.Z * ScaleFactor / 10.0f,
                Tread.Position.X * ScaleFactor / 10.0f,
                Tread.Position.Y * ScaleFactor / 10.0f
            );

            float TW = Tread.Width * ScaleFactor / 10.0f * 0.5f;
            float TD = Tread.Depth * ScaleFactor / 10.0f;
            float TT = Tread.Thickness * ScaleFactor / 10.0f;
            float Nose = Tread.Nosing * ScaleFactor / 10.0f;

            // Tread top
            AddQuad(
                TreadPos + FVector(-Nose, -TW, TT),
                TreadPos + FVector(-Nose, TW, TT),
                TreadPos + FVector(TD, TW, TT),
                TreadPos + FVector(TD, -TW, TT),
                FVector(0, 0, 1), TreadColor
            );
            // Tread bottom
            AddQuad(
                TreadPos + FVector(-Nose, TW, 0),
                TreadPos + FVector(-Nose, -TW, 0),
                TreadPos + FVector(TD, -TW, 0),
                TreadPos + FVector(TD, TW, 0),
                FVector(0, 0, -1), TreadColor
            );
            // Front (nose)
            AddQuad(
                TreadPos + FVector(-Nose, -TW, 0),
                TreadPos + FVector(-Nose, TW, 0),
                TreadPos + FVector(-Nose, TW, TT),
                TreadPos + FVector(-Nose, -TW, TT),
                FVector(-1, 0, 0), TreadColor
            );
            // Left side
            AddQuad(
                TreadPos + FVector(-Nose, -TW, 0),
                TreadPos + FVector(-Nose, -TW, TT),
                TreadPos + FVector(TD, -TW, TT),
                TreadPos + FVector(TD, -TW, 0),
                FVector(0, -1, 0), TreadColor
            );
            // Right side
            AddQuad(
                TreadPos + FVector(-Nose, TW, TT),
                TreadPos + FVector(-Nose, TW, 0),
                TreadPos + FVector(TD, TW, 0),
                TreadPos + FVector(TD, TW, TT),
                FVector(0, 1, 0), TreadColor
            );
        }
    }
    else
    {
        // Generate treads procedurally
        for (int32 i = 0; i < NumTreads; i++)
        {
            float TreadZ = i * RiserHeight;
            float TreadX = i * TreadDepth;

            // Tread top
            AddQuad(
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX + TreadDepth, HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX + TreadDepth, -HalfWidth, TreadZ + TreadThickness),
                FVector(0, 0, 1), TreadColor
            );
            // Tread bottom
            AddQuad(
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ),
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ),
                FVector(TreadX + TreadDepth, -HalfWidth, TreadZ),
                FVector(TreadX + TreadDepth, HalfWidth, TreadZ),
                FVector(0, 0, -1), TreadColor
            );
            // Nose front
            AddQuad(
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ),
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ),
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ + TreadThickness),
                FVector(-1, 0, 0), TreadColor
            );
            // Left edge
            AddQuad(
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ),
                FVector(TreadX - NoseOverhang, -HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX + TreadDepth, -HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX + TreadDepth, -HalfWidth, TreadZ),
                FVector(0, -1, 0), TreadColor
            );
            // Right edge
            AddQuad(
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ + TreadThickness),
                FVector(TreadX - NoseOverhang, HalfWidth, TreadZ),
                FVector(TreadX + TreadDepth, HalfWidth, TreadZ),
                FVector(TreadX + TreadDepth, HalfWidth, TreadZ + TreadThickness),
                FVector(0, 1, 0), TreadColor
            );

            // Riser (vertical face between treads)
            if (i > 0)
            {
                float RiserX = TreadX;
                float PrevTreadZ = (i - 1) * RiserHeight + TreadThickness;

                // Riser front
                AddQuad(
                    FVector(RiserX, -HalfWidth, PrevTreadZ),
                    FVector(RiserX, HalfWidth, PrevTreadZ),
                    FVector(RiserX, HalfWidth, TreadZ),
                    FVector(RiserX, -HalfWidth, TreadZ),
                    FVector(-1, 0, 0), RiserColor
                );
            }
        }
    }

    // Generate stringers (diagonal supports on sides)
    float StringerWidth = 3.0f * ScaleFactor;  // 3cm stringer width
    float StringerThick = 3.8f * ScaleFactor;  // 1.5" stringer thickness
    float TotalRun = NumTreads * TreadDepth;
    float TotalRise = NumTreads * RiserHeight;

    // Left stringer
    float LeftY = -HalfWidth - StringerThick;
    // Outer face
    AddQuad(
        FVector(0, LeftY, 0),
        FVector(TotalRun, LeftY, TotalRise),
        FVector(TotalRun, LeftY, TotalRise - StringerWidth),
        FVector(0, LeftY, -StringerWidth),
        FVector(0, -1, 0), StringerColor
    );
    // Inner face
    AddQuad(
        FVector(TotalRun, LeftY + StringerThick, TotalRise),
        FVector(0, LeftY + StringerThick, 0),
        FVector(0, LeftY + StringerThick, -StringerWidth),
        FVector(TotalRun, LeftY + StringerThick, TotalRise - StringerWidth),
        FVector(0, 1, 0), StringerColor
    );

    // Right stringer
    float RightY = HalfWidth;
    AddQuad(
        FVector(TotalRun, RightY, TotalRise),
        FVector(0, RightY, 0),
        FVector(0, RightY, -StringerWidth),
        FVector(TotalRun, RightY, TotalRise - StringerWidth),
        FVector(0, -1, 0), StringerColor
    );
    AddQuad(
        FVector(0, RightY + StringerThick, 0),
        FVector(TotalRun, RightY + StringerThick, TotalRise),
        FVector(TotalRun, RightY + StringerThick, TotalRise - StringerWidth),
        FVector(0, RightY + StringerThick, -StringerWidth),
        FVector(0, 1, 0), StringerColor
    );

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position at stair start point
    FVector StairPos = FVector(
        Stair.StartPoint.Z * ScaleFactor / 10.0f,
        Stair.StartPoint.X * ScaleFactor / 10.0f,
        Stair.StartPoint.Y * ScaleFactor / 10.0f
    );
    MeshComp->SetWorldLocation(StairPos);
    MeshComp->SetWorldRotation(FRotator(0, Stair.Direction, 0));
}

void AArchBuildingActor::GenerateGuardrailMesh(UProceduralMeshComponent* MeshComp, const FArchGuardrail& Guardrail, const FArchStair& Stair)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor HandrailColor = FLinearColor(0.5f, 0.35f, 0.2f).ToFColor(true);
    FColor BalusterColor = FLinearColor(0.45f, 0.3f, 0.18f).ToFColor(true);
    FColor NewelColor = FLinearColor(0.4f, 0.28f, 0.15f).ToFColor(true);

    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Lambda to create a box
    auto AddBox = [&](FVector Center, FVector Extents, FColor C) {
        float X = Extents.X, Y = Extents.Y, Z = Extents.Z;
        // Top
        AddQuad(Center + FVector(-X, -Y, Z), Center + FVector(-X, Y, Z),
                Center + FVector(X, Y, Z), Center + FVector(X, -Y, Z), FVector(0, 0, 1), C);
        // Bottom
        AddQuad(Center + FVector(-X, Y, -Z), Center + FVector(-X, -Y, -Z),
                Center + FVector(X, -Y, -Z), Center + FVector(X, Y, -Z), FVector(0, 0, -1), C);
        // Front
        AddQuad(Center + FVector(X, -Y, -Z), Center + FVector(X, Y, -Z),
                Center + FVector(X, Y, Z), Center + FVector(X, -Y, Z), FVector(1, 0, 0), C);
        // Back
        AddQuad(Center + FVector(-X, Y, -Z), Center + FVector(-X, -Y, -Z),
                Center + FVector(-X, -Y, Z), Center + FVector(-X, Y, Z), FVector(-1, 0, 0), C);
        // Left
        AddQuad(Center + FVector(-X, -Y, -Z), Center + FVector(X, -Y, -Z),
                Center + FVector(X, -Y, Z), Center + FVector(-X, -Y, Z), FVector(0, -1, 0), C);
        // Right
        AddQuad(Center + FVector(X, Y, -Z), Center + FVector(-X, Y, -Z),
                Center + FVector(-X, Y, Z), Center + FVector(X, Y, Z), FVector(0, 1, 0), C);
    };

    // Get rail parameters
    float HandrailDiam = Guardrail.Handrail.Diameter * ScaleFactor / 10.0f;
    float HandrailHeight = Guardrail.Handrail.Height * ScaleFactor / 10.0f;
    float BalusterWidth = Guardrail.Baluster.Width * ScaleFactor / 10.0f;
    float BalusterSpacing = Guardrail.Baluster.Spacing * ScaleFactor / 10.0f;

    // Calculate rail run
    FVector StartPt = FVector(
        Guardrail.StartPoint.Z * ScaleFactor / 10.0f,
        Guardrail.StartPoint.X * ScaleFactor / 10.0f,
        Guardrail.StartPoint.Y * ScaleFactor / 10.0f
    );
    FVector EndPt = FVector(
        Guardrail.EndPoint.Z * ScaleFactor / 10.0f,
        Guardrail.EndPoint.X * ScaleFactor / 10.0f,
        Guardrail.EndPoint.Y * ScaleFactor / 10.0f
    );

    FVector RailDir = (EndPt - StartPt).GetSafeNormal();
    float RailLength = FVector::Dist(StartPt, EndPt);

    // Handrail (simplified as rectangular profile)
    float HRHalf = HandrailDiam * 0.5f;
    FVector HRStart = StartPt + FVector(0, 0, HandrailHeight);
    FVector HREnd = EndPt + FVector(0, 0, HandrailHeight);

    // Top of handrail
    AddQuad(
        HRStart + FVector(0, -HRHalf, HRHalf),
        HRStart + FVector(0, HRHalf, HRHalf),
        HREnd + FVector(0, HRHalf, HRHalf),
        HREnd + FVector(0, -HRHalf, HRHalf),
        FVector(0, 0, 1), HandrailColor
    );
    // Bottom
    AddQuad(
        HRStart + FVector(0, HRHalf, -HRHalf),
        HRStart + FVector(0, -HRHalf, -HRHalf),
        HREnd + FVector(0, -HRHalf, -HRHalf),
        HREnd + FVector(0, HRHalf, -HRHalf),
        FVector(0, 0, -1), HandrailColor
    );
    // Left side
    AddQuad(
        HRStart + FVector(0, -HRHalf, -HRHalf),
        HRStart + FVector(0, -HRHalf, HRHalf),
        HREnd + FVector(0, -HRHalf, HRHalf),
        HREnd + FVector(0, -HRHalf, -HRHalf),
        FVector(0, -1, 0), HandrailColor
    );
    // Right side
    AddQuad(
        HRStart + FVector(0, HRHalf, HRHalf),
        HRStart + FVector(0, HRHalf, -HRHalf),
        HREnd + FVector(0, HRHalf, -HRHalf),
        HREnd + FVector(0, HRHalf, HRHalf),
        FVector(0, 1, 0), HandrailColor
    );

    // Generate balusters along the run
    int32 NumBalusters = FMath::Max(2, FMath::FloorToInt(RailLength / BalusterSpacing));
    float ActualSpacing = RailLength / (NumBalusters - 1);

    for (int32 i = 0; i < NumBalusters; i++)
    {
        float T = (float)i / (float)(NumBalusters - 1);
        FVector BalPos = FMath::Lerp(StartPt, EndPt, T);
        float BalHeight = HandrailHeight - HRHalf;

        // Baluster as a vertical box
        FVector BalCenter = BalPos + FVector(0, 0, BalHeight * 0.5f);
        FVector BalExtents = FVector(BalusterWidth * 0.5f, BalusterWidth * 0.5f, BalHeight * 0.5f);
        AddBox(BalCenter, BalExtents, BalusterColor);
    }

    // Generate newel posts
    for (const FArchNewelPost& Newel : Guardrail.NewelPosts)
    {
        FVector NewelPos = FVector(
            Newel.Position.Z * ScaleFactor / 10.0f,
            Newel.Position.X * ScaleFactor / 10.0f,
            Newel.Position.Y * ScaleFactor / 10.0f
        );

        float NW = Newel.Width * ScaleFactor / 10.0f * 0.5f;
        float ND = Newel.Depth * ScaleFactor / 10.0f * 0.5f;
        float NH = Newel.Height * ScaleFactor / 10.0f;

        FVector NewelCenter = NewelPos + FVector(0, 0, NH * 0.5f);
        AddBox(NewelCenter, FVector(NW, ND, NH * 0.5f), NewelColor);
    }

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);
}

// ============================================================================
// ROOF MESH GENERATION
// ============================================================================

void AArchBuildingActor::GenerateRoofMesh(UProceduralMeshComponent* MeshComp, const FArchRoof& Roof)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor RoofColor = FLinearColor(0.3f, 0.3f, 0.35f).ToFColor(true);
    if (Roof.Material == TEXT("asphalt_shingle"))
        RoofColor = FLinearColor(0.25f, 0.25f, 0.28f).ToFColor(true);
    else if (Roof.Material == TEXT("metal"))
        RoofColor = FLinearColor(0.5f, 0.5f, 0.55f).ToFColor(true);
    else if (Roof.Material == TEXT("tile"))
        RoofColor = FLinearColor(0.7f, 0.35f, 0.2f).ToFColor(true);

    // Lambda to add a triangle
    auto AddTri = [&](FVector V0, FVector V1, FVector V2, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2);
        Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(0.5f, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
    };

    // Lambda to add a quad
    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    float RoofThickness = 30.48f;  // 1 foot thick roof assembly in Unreal units
    float RoofLift = RoofThickness; // Raise roof so soffit aligns with wall tops
    float FasciaHeight = 20.0f;    // ~200mm fascia board height in Unreal units (cm)
    float FasciaThickness = 1.9f;  // ~19mm (3/4") fascia board thickness
    FColor FasciaColor = FLinearColor(0.95f, 0.95f, 0.9f).ToFColor(true);  // White/off-white trim

    // First pass: collect all world-space vertices to calculate center
    // Include RoofLift in center calculation
    TArray<FVector> AllWorldVerts;
    for (const FArchRoofSurface& Surface : Roof.Surfaces)
    {
        for (const FVector& V : Surface.Vertices)
        {
            AllWorldVerts.Add(KernelToUnreal(V) + FVector(0, 0, RoofLift));
        }
    }

    // Calculate center of all roof vertices (like walls do)
    FVector RoofCenter = FVector::ZeroVector;
    if (AllWorldVerts.Num() > 0)
    {
        for (const FVector& V : AllWorldVerts)
        {
            RoofCenter += V;
        }
        RoofCenter /= AllWorldVerts.Num();
    }

    // Generate mesh from roof surfaces (vertices relative to center)
    for (const FArchRoofSurface& Surface : Roof.Surfaces)
    {
        if (Surface.Vertices.Num() < 3) continue;

        // Convert vertices using KernelToUnreal, then offset by center
        // Add RoofLift so soffit (bottom of roof) aligns with wall tops
        TArray<FVector> SurfVerts;
        for (const FVector& V : Surface.Vertices)
        {
            SurfVerts.Add(KernelToUnreal(V) - RoofCenter + FVector(0, 0, RoofLift));
        }

        // Calculate surface normal
        FVector Normal = FVector::ZeroVector;
        if (SurfVerts.Num() >= 3)
        {
            FVector Edge1 = SurfVerts[1] - SurfVerts[0];
            FVector Edge2 = SurfVerts[2] - SurfVerts[0];
            Normal = FVector::CrossProduct(Edge1, Edge2).GetSafeNormal();
        }

        // Triangulate the surface (simple fan triangulation for convex polygons)
        for (int32 i = 1; i < SurfVerts.Num() - 1; i++)
        {
            AddTri(SurfVerts[0], SurfVerts[i], SurfVerts[i + 1], Normal, RoofColor);
        }

        // Add thickness by creating bottom surface
        // Use vertical offset (not normal-based) so adjacent surfaces meet at ridge/hip
        TArray<FVector> BottomVerts;
        for (const FVector& V : SurfVerts)
        {
            BottomVerts.Add(V - FVector(0, 0, RoofThickness));
        }

        // Bottom surface (reversed winding)
        for (int32 i = 1; i < BottomVerts.Num() - 1; i++)
        {
            AddTri(BottomVerts[0], BottomVerts[i + 1], BottomVerts[i], -Normal, RoofColor);
        }

        // Edge faces - only for eave edges (where both vertices are at similar Z height)
        // Skip edge faces for ridge/hip edges (where vertices have different Z = interior seams)
        for (int32 i = 0; i < SurfVerts.Num(); i++)
        {
            int32 NextI = (i + 1) % SurfVerts.Num();

            // Check if this is an eave edge (both vertices at similar Z height)
            // In Unreal coords (after KernelToUnreal): Z is height (from kernel Y)
            float HeightDiff = FMath::Abs(SurfVerts[i].Z - SurfVerts[NextI].Z);

            // Only add edge faces for horizontal edges (eaves) - skip sloped edges (ridges/hips)
            if (HeightDiff < 1.0f)  // Tolerance for floating point comparison
            {
                FVector EdgeDir = (SurfVerts[NextI] - SurfVerts[i]).GetSafeNormal();
                FVector EdgeNormal = FVector::CrossProduct(EdgeDir, Normal).GetSafeNormal();

                // Roof edge face (soffit area)
                AddQuad(
                    SurfVerts[i], SurfVerts[NextI],
                    BottomVerts[NextI], BottomVerts[i],
                    EdgeNormal, RoofColor
                );

                // Fascia board - vertical board at the eave edge
                // Positioned at the outer edge, extending down from top of roof
                FVector FasciaOutward = EdgeNormal * FasciaThickness;
                FVector FasciaDown = FVector(0, 0, -FasciaHeight);

                // Extend fascia past corners to close gaps at joints
                FVector EdgeExtension = EdgeDir * FasciaThickness;

                // Fascia front face (outward facing) - starts at top of roof edge
                FVector F0 = SurfVerts[i] - EdgeExtension;
                FVector F1 = SurfVerts[NextI] + EdgeExtension;
                FVector F2 = SurfVerts[NextI] + EdgeExtension + FasciaDown;
                FVector F3 = SurfVerts[i] - EdgeExtension + FasciaDown;
                AddQuad(F0, F1, F2, F3, EdgeNormal, FasciaColor);

                // Fascia bottom face
                FVector FasciaBottomNormal = FVector(0, 0, -1);
                AddQuad(
                    F3, F2,
                    F2 + FasciaOutward, F3 + FasciaOutward,
                    FasciaBottomNormal, FasciaColor
                );

                // Fascia back face (toward roof)
                AddQuad(
                    F3 + FasciaOutward, F2 + FasciaOutward,
                    F1 + FasciaOutward, F0 + FasciaOutward,
                    -EdgeNormal, FasciaColor
                );

                // Fascia top face (connects to roof bottom)
                FVector FasciaTopNormal = FVector(0, 0, 1);
                AddQuad(
                    F0 + FasciaOutward, F1 + FasciaOutward,
                    F1, F0,
                    FasciaTopNormal, FasciaColor
                );
            }
        }
    }

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position the mesh at the roof center (like walls do)
    MeshComp->SetWorldLocation(RoofCenter);
}

void AArchBuildingActor::GenerateDormerMesh(UProceduralMeshComponent* MeshComp, const FArchDormer& Dormer, const FArchRoof& Roof)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor WallColor = FLinearColor(0.9f, 0.9f, 0.85f).ToFColor(true);
    FColor RoofColor = FLinearColor(0.3f, 0.3f, 0.35f).ToFColor(true);

    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    auto AddTri = [&](FVector V0, FVector V1, FVector V2, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2);
        Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(0.5f, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
    };

    // Convert position using KernelToUnreal (same as walls)
    FVector Pos = KernelToUnreal(Dormer.Position);

    float W = Dormer.Width * ScaleFactor * 0.5f;
    float H = Dormer.Height * ScaleFactor;
    float D = Dormer.Depth * ScaleFactor;

    // Build vertices relative to origin (will position with SetWorldLocation)
    // Front wall (with gable peak for gable dormers)
    if (Dormer.Type == TEXT("gable"))
    {
        float PeakH = H * 0.3f;  // Gable peak height

        // Front wall below peak
        AddQuad(
            FVector(0, -W, 0), FVector(0, W, 0),
            FVector(0, W, H), FVector(0, -W, H),
            FVector(-1, 0, 0), WallColor
        );

        // Gable triangles
        AddTri(
            FVector(0, -W, H), FVector(0, W, H),
            FVector(0, 0, H + PeakH),
            FVector(-1, 0, 0), WallColor
        );

        // Dormer roof (two sloped surfaces)
        FVector RidgeFront = FVector(0, 0, H + PeakH);
        FVector RidgeBack = FVector(D, 0, H + PeakH);

        // Left roof surface
        AddQuad(
            FVector(0, -W, H), RidgeFront,
            RidgeBack, FVector(D, -W, H),
            FVector::CrossProduct(FVector(0, -W, 0) - FVector(0, 0, PeakH), FVector(D, 0, 0)).GetSafeNormal(),
            RoofColor
        );

        // Right roof surface
        AddQuad(
            RidgeFront, FVector(0, W, H),
            FVector(D, W, H), RidgeBack,
            FVector::CrossProduct(FVector(0, W, 0) - FVector(0, 0, PeakH), FVector(D, 0, 0)).GetSafeNormal(),
            RoofColor
        );
    }
    else  // Shed dormer
    {
        // Front wall
        AddQuad(
            FVector(0, -W, 0), FVector(0, W, 0),
            FVector(0, W, H), FVector(0, -W, H),
            FVector(-1, 0, 0), WallColor
        );

        // Shed roof
        AddQuad(
            FVector(0, -W, H), FVector(0, W, H),
            FVector(D, W, H * 0.7f), FVector(D, -W, H * 0.7f),
            FVector(0.3f, 0, 1).GetSafeNormal(), RoofColor
        );
    }

    // Side walls
    AddQuad(
        FVector(0, -W, 0), FVector(0, -W, H),
        FVector(D, -W, H), FVector(D, -W, 0),
        FVector(0, -1, 0), WallColor
    );
    AddQuad(
        FVector(0, W, H), FVector(0, W, 0),
        FVector(D, W, 0), FVector(D, W, H),
        FVector(0, 1, 0), WallColor
    );

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position the mesh at the dormer location (like walls do)
    MeshComp->SetWorldLocation(Pos);
}

void AArchBuildingActor::GenerateSkylightMesh(UProceduralMeshComponent* MeshComp, const FArchSkylight& Skylight)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor FrameColor = FLinearColor(0.3f, 0.3f, 0.35f).ToFColor(true);
    FColor GlassColor = FLinearColor(0.6f, 0.8f, 0.95f).ToFColor(true);

    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Convert position using KernelToUnreal (same as walls)
    FVector Pos = KernelToUnreal(Skylight.Position);

    float W = Skylight.Width * ScaleFactor * 0.5f;
    float H = Skylight.Height * ScaleFactor * 0.5f;
    float FrameW = 5.0f * ScaleFactor;  // 5cm frame
    float FrameH = 10.0f * ScaleFactor; // 10cm curb height
    float GlassThick = 2.0f * ScaleFactor;

    // Build vertices relative to origin (will position with SetWorldLocation)
    // Glass panel (top surface)
    AddQuad(
        FVector(-H, -W, FrameH), FVector(-H, W, FrameH),
        FVector(H, W, FrameH), FVector(H, -W, FrameH),
        FVector(0, 0, 1), GlassColor
    );

    // Frame sides
    // Front
    AddQuad(
        FVector(-H - FrameW, -W - FrameW, 0), FVector(-H - FrameW, W + FrameW, 0),
        FVector(-H - FrameW, W + FrameW, FrameH), FVector(-H - FrameW, -W - FrameW, FrameH),
        FVector(-1, 0, 0), FrameColor
    );
    // Back
    AddQuad(
        FVector(H + FrameW, W + FrameW, 0), FVector(H + FrameW, -W - FrameW, 0),
        FVector(H + FrameW, -W - FrameW, FrameH), FVector(H + FrameW, W + FrameW, FrameH),
        FVector(1, 0, 0), FrameColor
    );
    // Left
    AddQuad(
        FVector(-H - FrameW, -W - FrameW, 0), FVector(-H - FrameW, -W - FrameW, FrameH),
        FVector(H + FrameW, -W - FrameW, FrameH), FVector(H + FrameW, -W - FrameW, 0),
        FVector(0, -1, 0), FrameColor
    );
    // Right
    AddQuad(
        FVector(-H - FrameW, W + FrameW, FrameH), FVector(-H - FrameW, W + FrameW, 0),
        FVector(H + FrameW, W + FrameW, 0), FVector(H + FrameW, W + FrameW, FrameH),
        FVector(0, 1, 0), FrameColor
    );
    // Top frame rim
    AddQuad(
        FVector(-H - FrameW, -W - FrameW, FrameH), FVector(-H - FrameW, W + FrameW, FrameH),
        FVector(-H, W, FrameH), FVector(-H, -W, FrameH),
        FVector(0, 0, 1), FrameColor
    );
    AddQuad(
        FVector(H, -W, FrameH), FVector(H, W, FrameH),
        FVector(H + FrameW, W + FrameW, FrameH), FVector(H + FrameW, -W - FrameW, FrameH),
        FVector(0, 0, 1), FrameColor
    );

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);

    // Position the mesh at the skylight location (like walls do)
    MeshComp->SetWorldLocation(Pos);
}

// ============================================================================
// ELEVATOR MESH GENERATION
// ============================================================================

void AArchBuildingActor::GenerateElevatorMesh(UProceduralMeshComponent* MeshComp, const FArchElevator& Elevator)
{
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;

    FColor ShaftColor = FLinearColor(0.4f, 0.4f, 0.45f).ToFColor(true);  // Gray concrete
    FColor CabColor = FLinearColor(0.7f, 0.7f, 0.75f).ToFColor(true);    // Metal cab
    FColor DoorColor = FLinearColor(0.5f, 0.5f, 0.55f).ToFColor(true);   // Metal doors

    auto AddQuad = [&](FVector V0, FVector V1, FVector V2, FVector V3, FVector N, FColor C) {
        int32 BaseIdx = Vertices.Num();
        Vertices.Add(V0); Vertices.Add(V1); Vertices.Add(V2); Vertices.Add(V3);
        Normals.Add(N); Normals.Add(N); Normals.Add(N); Normals.Add(N);
        UVs.Add(FVector2D(0, 0)); UVs.Add(FVector2D(1, 0)); UVs.Add(FVector2D(1, 1)); UVs.Add(FVector2D(0, 1));
        Colors.Add(C); Colors.Add(C); Colors.Add(C); Colors.Add(C);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 1); Triangles.Add(BaseIdx + 2);
        Triangles.Add(BaseIdx); Triangles.Add(BaseIdx + 2); Triangles.Add(BaseIdx + 3);
    };

    // Convert position (mm to Unreal units)
    FVector ShaftPos = FVector(
        Elevator.ShaftPosition.Z * ScaleFactor / 10.0f,
        Elevator.ShaftPosition.X * ScaleFactor / 10.0f,
        Elevator.ShaftPosition.Y * ScaleFactor / 10.0f
    );

    float ShaftW = Elevator.ShaftWidth * ScaleFactor / 10.0f;
    float ShaftD = Elevator.ShaftDepth * ScaleFactor / 10.0f;
    float CabW = Elevator.CabWidth * ScaleFactor / 10.0f;
    float CabD = Elevator.CabDepth * ScaleFactor / 10.0f;
    float CabH = Elevator.CabHeight * ScaleFactor / 10.0f;
    float DoorW = Elevator.DoorWidth * ScaleFactor / 10.0f;

    // Calculate shaft height based on served levels
    float ShaftH = BuildingData.Levels.Num() > 1 ?
        BuildingData.Levels[BuildingData.Levels.Num() - 1].Elevation * ScaleFactor / 10.0f + CabH :
        CabH * 2;

    // Shaft walls (exterior faces)
    // Back wall
    AddQuad(
        ShaftPos + FVector(0, 0, 0),
        ShaftPos + FVector(0, ShaftW, 0),
        ShaftPos + FVector(0, ShaftW, ShaftH),
        ShaftPos + FVector(0, 0, ShaftH),
        FVector(-1, 0, 0), ShaftColor
    );
    // Front wall (with door opening)
    float SideW = (ShaftW - DoorW) / 2.0f;
    // Left of door
    AddQuad(
        ShaftPos + FVector(ShaftD, 0, 0),
        ShaftPos + FVector(ShaftD, SideW, 0),
        ShaftPos + FVector(ShaftD, SideW, ShaftH),
        ShaftPos + FVector(ShaftD, 0, ShaftH),
        FVector(1, 0, 0), ShaftColor
    );
    // Right of door
    AddQuad(
        ShaftPos + FVector(ShaftD, ShaftW - SideW, 0),
        ShaftPos + FVector(ShaftD, ShaftW, 0),
        ShaftPos + FVector(ShaftD, ShaftW, ShaftH),
        ShaftPos + FVector(ShaftD, ShaftW - SideW, ShaftH),
        FVector(1, 0, 0), ShaftColor
    );
    // Above door
    AddQuad(
        ShaftPos + FVector(ShaftD, SideW, CabH),
        ShaftPos + FVector(ShaftD, ShaftW - SideW, CabH),
        ShaftPos + FVector(ShaftD, ShaftW - SideW, ShaftH),
        ShaftPos + FVector(ShaftD, SideW, ShaftH),
        FVector(1, 0, 0), ShaftColor
    );
    // Side walls
    AddQuad(
        ShaftPos + FVector(0, 0, 0),
        ShaftPos + FVector(ShaftD, 0, 0),
        ShaftPos + FVector(ShaftD, 0, ShaftH),
        ShaftPos + FVector(0, 0, ShaftH),
        FVector(0, -1, 0), ShaftColor
    );
    AddQuad(
        ShaftPos + FVector(ShaftD, ShaftW, 0),
        ShaftPos + FVector(0, ShaftW, 0),
        ShaftPos + FVector(0, ShaftW, ShaftH),
        ShaftPos + FVector(ShaftD, ShaftW, ShaftH),
        FVector(0, 1, 0), ShaftColor
    );

    // Elevator cab (simplified box at ground level)
    float CabOffset = (ShaftW - CabW) / 2.0f;
    float CabDepthOffset = (ShaftD - CabD) / 2.0f;
    FVector CabPos = ShaftPos + FVector(CabDepthOffset, CabOffset, 0);

    // Cab floor
    AddQuad(
        CabPos + FVector(0, 0, 0.5f),
        CabPos + FVector(CabD, 0, 0.5f),
        CabPos + FVector(CabD, CabW, 0.5f),
        CabPos + FVector(0, CabW, 0.5f),
        FVector(0, 0, 1), CabColor
    );
    // Cab ceiling
    AddQuad(
        CabPos + FVector(0, 0, CabH),
        CabPos + FVector(0, CabW, CabH),
        CabPos + FVector(CabD, CabW, CabH),
        CabPos + FVector(CabD, 0, CabH),
        FVector(0, 0, 1), CabColor
    );
    // Cab back wall
    AddQuad(
        CabPos + FVector(0, 0, 0),
        CabPos + FVector(0, CabW, 0),
        CabPos + FVector(0, CabW, CabH),
        CabPos + FVector(0, 0, CabH),
        FVector(-1, 0, 0), CabColor
    );
    // Cab side walls
    AddQuad(
        CabPos + FVector(0, 0, 0),
        CabPos + FVector(0, 0, CabH),
        CabPos + FVector(CabD, 0, CabH),
        CabPos + FVector(CabD, 0, 0),
        FVector(0, -1, 0), CabColor
    );
    AddQuad(
        CabPos + FVector(0, CabW, 0),
        CabPos + FVector(CabD, CabW, 0),
        CabPos + FVector(CabD, CabW, CabH),
        CabPos + FVector(0, CabW, CabH),
        FVector(0, 1, 0), CabColor
    );

    MeshComp->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, TArray<FProcMeshTangent>(), true);
}

// ============================================================================
// MEP FIXTURE MESH GENERATION
// ============================================================================

void AArchBuildingActor::GeneratePlumbingFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchPlumbingFixture& Fixture)
{
    // Convert position
    FVector Pos = FVector(
        Fixture.Position.Z * ScaleFactor / 10.0f,
        Fixture.Position.X * ScaleFactor / 10.0f,
        Fixture.Position.Y * ScaleFactor / 10.0f
    );

    // Fixture sizes (in cm, scaled to Unreal units)
    FVector Extents;
    FLinearColor Color;

    if (Fixture.Type == TEXT("toilet"))
    {
        Extents = FVector(35.0f, 45.0f, 40.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);  // White porcelain
    }
    else if (Fixture.Type == TEXT("sink"))
    {
        Extents = FVector(45.0f, 55.0f, 20.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else if (Fixture.Type == TEXT("shower"))
    {
        Extents = FVector(90.0f, 90.0f, 5.0f) * ScaleFactor / 100.0f;  // Base only
        Color = FLinearColor(0.9f, 0.9f, 0.9f);
    }
    else if (Fixture.Type == TEXT("tub"))
    {
        Extents = FVector(75.0f, 150.0f, 50.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else if (Fixture.Type == TEXT("water_heater"))
    {
        Extents = FVector(45.0f, 45.0f, 120.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.85f, 0.85f, 0.85f);  // Metal
    }
    else
    {
        // Default box
        Extents = FVector(30.0f, 30.0f, 30.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.7f, 0.7f, 0.8f);
    }

    CreateBoxMesh(MeshComp, Pos + FVector(0, 0, Extents.Z * 0.5f), Extents * 0.5f, Color);
}

void AArchBuildingActor::GenerateElectricalFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchElectricalFixture& Fixture)
{
    // Convert position
    FVector Pos = FVector(
        Fixture.Position.Z * ScaleFactor / 10.0f,
        Fixture.Position.X * ScaleFactor / 10.0f,
        Fixture.Position.Y * ScaleFactor / 10.0f
    );

    // Fixture sizes
    FVector Extents;
    FLinearColor Color;

    if (Fixture.Type == TEXT("outlet") || Fixture.Type == TEXT("gfci"))
    {
        Extents = FVector(3.0f, 7.0f, 11.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.93f, 0.85f);  // Almond
    }
    else if (Fixture.Type == TEXT("switch"))
    {
        Extents = FVector(3.0f, 7.0f, 11.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.93f, 0.85f);
    }
    else if (Fixture.Type == TEXT("panel"))
    {
        Extents = FVector(10.0f, 35.0f, 60.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.5f, 0.5f, 0.55f);  // Gray metal
    }
    else if (Fixture.Type == TEXT("light"))
    {
        Extents = FVector(15.0f, 60.0f, 5.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else if (Fixture.Type == TEXT("smoke_detector"))
    {
        Extents = FVector(12.0f, 12.0f, 3.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else if (Fixture.Type == TEXT("thermostat"))
    {
        Extents = FVector(3.0f, 8.0f, 12.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else
    {
        Extents = FVector(5.0f, 5.0f, 5.0f) * ScaleFactor / 100.0f;
        Color = FLinearColor(0.8f, 0.8f, 0.8f);
    }

    // Apply mount height
    float MountH = Fixture.MountHeight * ScaleFactor / 10.0f;
    CreateBoxMesh(MeshComp, Pos + FVector(0, 0, MountH), Extents * 0.5f, Color);
}

void AArchBuildingActor::GenerateHVACFixtureMesh(UProceduralMeshComponent* MeshComp, const FArchHVACFixture& Fixture)
{
    // Convert position
    FVector Pos = FVector(
        Fixture.Position.Z * ScaleFactor / 10.0f,
        Fixture.Position.X * ScaleFactor / 10.0f,
        Fixture.Position.Y * ScaleFactor / 10.0f
    );

    // Fixture dimensions from JSON
    float W = Fixture.Width * ScaleFactor / 10.0f;
    float H = Fixture.Height * ScaleFactor / 10.0f;
    float D = 5.0f * ScaleFactor;  // Depth for registers

    FVector Extents;
    FLinearColor Color;

    if (Fixture.Type == TEXT("supply_register") || Fixture.Type == TEXT("return_grille"))
    {
        Extents = FVector(D, W, H) * 0.5f;
        Color = FLinearColor(0.9f, 0.9f, 0.9f);  // White register
    }
    else if (Fixture.Type == TEXT("exhaust_fan"))
    {
        Extents = FVector(10.0f, 30.0f, 30.0f) * ScaleFactor / 100.0f * 0.5f;
        Color = FLinearColor(0.95f, 0.95f, 0.95f);
    }
    else if (Fixture.Type == TEXT("range_hood"))
    {
        Extents = FVector(50.0f, 75.0f, 15.0f) * ScaleFactor / 100.0f * 0.5f;
        Color = FLinearColor(0.5f, 0.5f, 0.55f);  // Stainless
    }
    else
    {
        Extents = FVector(D, W, H) * 0.5f;
        Color = FLinearColor(0.85f, 0.85f, 0.85f);
    }

    CreateBoxMesh(MeshComp, Pos, Extents, Color);
}
