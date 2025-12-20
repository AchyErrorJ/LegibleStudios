// ArchTypes.h - Core data types for ArchEngine Viewer
// Mirrors the kernel types for JSON interop

#pragma once

#include "CoreMinimal.h"
#include "ArchTypes.generated.h"

// Element types matching kernel ElementType enum
UENUM(BlueprintType)
enum class EArchElementType : uint8
{
    Beam = 0,
    Column = 1,
    Floor = 2,
    Wall = 3,
    Foundation = 4,
    Connection = 5,
    Door = 6,
    Window = 7,
    Roof = 8
};

// Layer function types
UENUM(BlueprintType)
enum class ELayerFunction : uint8
{
    ExteriorFinish,
    Sheathing,
    Insulation,
    Structure,
    InteriorFinish,
    AirGap,
    Membrane
};

// Fastener types
UENUM(BlueprintType)
enum class EFastenerType : uint8
{
    Nail,
    Screw,
    Bolt,
    Staple,
    Anchor,
    Strap,
    Hanger,
    Clip,
    Adhesive
};

// Constraint types
UENUM(BlueprintType)
enum class EConstraintType : uint8
{
    StructuralBearing,
    FireRating,
    ThermalPerformance,
    SoundTransmission,
    MoistureControl,
    AirBarrier,
    WindResistance,
    SeismicCategory,
    MaxSpan,
    MinThickness,
    CodeSection
};

// Visualization modes
UENUM(BlueprintType)
enum class EVisualizationMode : uint8
{
    Structural,
    Thermal,
    Lighting,
    Acoustic,
    Material,
    Wireframe
};

// Fastener specification
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchFastener
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EFastenerType Type = EFastenerType::Nail;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Diameter = 0.131f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Length = 3.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float FieldSpacing = 12.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float EdgeSpacing = 6.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString CodeReference;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ShearCapacity = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float WithdrawalCapacity = 0.0f;
};

// Assembly constraint
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchConstraint
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EConstraintType Type = EConstraintType::CodeSection;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Value;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString CodeSection;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Description;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bIsMet = false;
};

// Wall layer
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchWallLayer
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    ELayerFunction Function = ELayerFunction::Structure;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Thickness = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FLinearColor Color = FLinearColor::White;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float RValue = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchFastener> Fasteners;
};

// Wall assembly intent
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchWallIntent
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float RValueTarget = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString StructuralRole;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ClimateZone;
};

// Wall type (assembly)
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchWallType
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchWallIntent Intent;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchWallLayer> Layers;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchConstraint> Constraints;

    // Calculate total thickness
    float GetTotalThickness() const
    {
        float Total = 0.0f;
        for (const auto& Layer : Layers)
        {
            Total += Layer.Thickness;
        }
        return Total;
    }

    // Calculate total R-value
    float GetTotalRValue() const
    {
        float Total = 0.0f;
        for (const auto& Layer : Layers)
        {
            Total += Layer.RValue;
        }
        return Total;
    }
};

// Mesh data from JSON
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchMeshData
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FVector> Vertices;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<int32> Triangles;

    bool HasData() const { return Vertices.Num() > 0 && Triangles.Num() > 0; }
};

// Structural element
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchElement
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchElementType Type = EArchElementType::Beam;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Start = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector End = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 0.5f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Stress = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Deflection = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bFailed = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchMeshData Mesh;
};

// Parametric wall instance
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchParametricWall
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector2D StartPoint = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector2D EndPoint = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float BaseHeight = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TopHeight = 8.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 WallTypeIndex = 0;
};

// Complete building data
USTRUCT(BlueprintType)
struct ARCHENGINEV_API FArchBuilding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchElement> Elements;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchWallType> WallTypes;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchParametricWall> ParametricWalls;
};
