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

// Constraint types (prefixed to avoid UE engine conflict)
UENUM(BlueprintType)
enum class EArchConstraintType : uint8
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
struct ARCHENGINE_API FArchFastener
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
struct ARCHENGINE_API FArchConstraint
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchConstraintType Type = EArchConstraintType::CodeSection;

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
struct ARCHENGINE_API FArchWallLayer
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
struct ARCHENGINE_API FArchWallIntent
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
struct ARCHENGINE_API FArchWallType
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
struct ARCHENGINE_API FArchMeshData
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
struct ARCHENGINE_API FArchElement
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

    // For wall elements: the original JSON wall_index (used for door/window matching)
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 WallIndex = -1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchMeshData Mesh;
};

// Parametric wall instance
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchParametricWall
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

// Door type enum
UENUM(BlueprintType)
enum class EArchDoorType : uint8
{
    Swing,
    Entry,
    Pocket,
    Sliding,
    Bifold,
    French,
    Barn
};

// Door swing direction
UENUM(BlueprintType)
enum class EArchDoorSwing : uint8
{
    LeftIn,
    RightIn,
    LeftOut,
    RightOut,
    Left,
    Right
};

// Window type enum
UENUM(BlueprintType)
enum class EArchWindowType : uint8
{
    Fixed,
    Casement,
    DoubleHung,
    Sliding,
    Awning
};

// Door opening
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchDoor
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 WallIndex = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Offset = 0.0f;  // Distance from wall start to door center (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 90.0f;  // Door width (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 210.0f;  // Door height (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchDoorType Type = EArchDoorType::Swing;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchDoorSwing Swing = EArchDoorSwing::LeftIn;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room1;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room2;
};

// Window opening
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchWindow
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 WallIndex = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Offset = 0.0f;  // Distance from wall start to window center (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 120.0f;  // Window width (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 120.0f;  // Window height (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float SillHeight = 90.0f;  // Height from floor to bottom of window (cm)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchWindowType Type = EArchWindowType::DoubleHung;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LevelName;
};

// ========== LEVEL ==========

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLevel
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Elevation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float FloorToFloorHeight = 3048.0f;  // Default 10ft in mm
};

// ========== ROOM ==========

// Room zone types
UENUM(BlueprintType)
enum class EArchRoomZone : uint8
{
    Public,
    Private,
    Service,
    Circulation
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoomBounds
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float X = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Y = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 0.0f;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoom
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchRoomBounds Bounds;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Area = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector2D Center = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString RoomType;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchRoomZone Zone = EArchRoomZone::Public;
};

// ========== DIMENSION ==========

UENUM(BlueprintType)
enum class EArchDimensionType : uint8
{
    Linear,
    Angular,
    Radial
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchDimension
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchDimensionType Type = EArchDimensionType::Linear;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Value = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Unit;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;

    // Display properties
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TextHeight = 100.0f;  // mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float OffsetDistance = 200.0f;  // Distance from geometry

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bShowValue = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Precision = 0;  // Decimal places (0 = feet-inches format)
};

// ========== ANNOTATIONS ==========

// Plan types for different drawing views
UENUM(BlueprintType)
enum class EArchPlanType : uint8
{
    FloorPlan,
    RoofPlan,
    ReflectedCeilingPlan,
    SitePlan,
    FoundationPlan,
    FramingPlan,
    ElectricalPlan,
    PlumbingPlan,
    MechanicalPlan,
    Elevation,
    Section,
    Detail
};

// Symbol types for plan annotations
UENUM(BlueprintType)
enum class EArchSymbolType : uint8
{
    NorthArrow,
    SectionMarker,
    DetailMarker,
    ElevationMarker,
    DoorTag,
    WindowTag,
    RoomTag,
    ColumnGrid,
    LevelMarker,
    BreakLine,
    CenterLine,
    MatchLine,
    RevisionCloud
};

// Roof-specific annotation types
UENUM(BlueprintType)
enum class EArchRoofAnnotationType : uint8
{
    PitchIndicator,      // Shows slope as X:12
    DrainageArrow,       // Arrow showing water flow direction
    RidgeLine,           // Ridge annotation
    ValleyLine,          // Valley annotation
    HipLine,             // Hip annotation
    EaveLine,            // Eave edge
    RakeLine,            // Rake edge (gable end)
    CricketArrow,        // Cricket/saddle flow
    RoofDrain,           // Drain location
    Scupper,             // Scupper location
    Overflow,            // Overflow drain
    SlopeArrow           // General slope direction
};

// Text label for rooms, areas, callouts
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchTextLabel
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Text;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;  // Degrees

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TextHeight = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString FontStyle;  // "regular", "bold", "italic"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Justification;  // "left", "center", "right"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bShowBorder = false;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bShowBackground = false;
};

// Leader line with text callout
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLeader
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector ArrowPoint = FVector::ZeroVector;  // Point being called out

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector TextPosition = FVector::ZeroVector;  // Where text appears

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FVector> BendPoints;  // Intermediate points for multi-segment leaders

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Text;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TextHeight = 100.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ArrowStyle;  // "closed", "open", "dot", "none"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;
};

// Symbol (section markers, north arrows, etc.)
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchSymbol
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchSymbolType Type = EArchSymbolType::SectionMarker;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Scale = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Label;  // e.g., "A" for section A

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString SheetReference;  // e.g., "A3.1" for sheet reference

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Direction = FVector(0, 1, 0);  // View direction for section/elevation

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;
};

// Roof annotation (pitch, drainage, ridges)
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoofAnnotation
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchRoofAnnotationType Type = EArchRoofAnnotationType::PitchIndicator;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPosition = FVector::ZeroVector;  // For lines (ridge, valley, etc.)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;  // Arrow direction in degrees

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Pitch = 4.0f;  // For PitchIndicator: rise per 12 run (e.g., 4:12)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float SlopePercent = 0.0f;  // Alternative: slope as percentage

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Label;  // Custom label text

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString RoofSurfaceId;  // Which roof surface this annotates
};

// Grid line for structural grids
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchGridLine
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Label;  // "A", "B", "1", "2", etc.

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bIsPrimary = true;  // Primary grid vs secondary

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    bool bShowBubble = true;  // Show grid bubble at ends
};

// Annotation set - collection of annotations for a specific plan
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchAnnotationSet
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchPlanType PlanType = EArchPlanType::FloorPlan;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;  // Which level this annotation set applies to

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Scale = 48.0f;  // Drawing scale (1/4" = 1'-0" = 48)

    // Annotation collections
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchDimension> Dimensions;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchTextLabel> Labels;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchLeader> Leaders;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchSymbol> Symbols;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchRoofAnnotation> RoofAnnotations;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchGridLine> GridLines;

    // Viewport settings
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector ViewportCenter = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ViewportWidth = 10000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ViewportHeight = 8000.0f;
};

// ========== ROOF ==========

UENUM(BlueprintType)
enum class EArchRoofType : uint8
{
    Gable,
    Hip,
    Flat,
    Shed,
    Mansard,
    Gambrel
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchDormer
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "gable", "shed", "hip"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 1219.2f;  // 4ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 1524.0f;  // 5ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 914.4f;  // 3ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString RoofSurfaceId;  // Which roof surface this is on
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchSkylight
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "fixed", "venting", "tubular"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 609.6f;  // 2ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 914.4f;  // 3ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString RoofSurfaceId;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoofRidge
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 0.0f;  // Ridge height from base elevation
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoofSurface
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FVector> Vertices;  // 3D points defining the surface

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Pitch = 6.0f;  // Rise over 12" run (e.g., 6:12)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Orientation;  // "north", "south", "east", "west"
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoof
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchRoofType Type = EArchRoofType::Gable;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Pitch = 6.0f;  // Rise over 12" run

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Overhang = 609.6f;  // 2ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;  // "asphalt_shingle", "metal", "tile", "slate"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LevelName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchRoofRidge> Ridges;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchRoofSurface> Surfaces;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchDormer> Dormers;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchSkylight> Skylights;
};

// ========== VERTICAL TRANSPORTATION ==========

UENUM(BlueprintType)
enum class EArchStairType : uint8
{
    Straight,
    LShaped,
    UShaped,
    Winder,
    Spiral
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchStairTread
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Index = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;  // Center of tread

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 914.4f;  // 36" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 254.0f;  // 10" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Thickness = 25.4f;  // 1" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Nosing = 25.4f;  // 1" overhang

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;  // For winder stairs
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchStairRiser
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Index = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 914.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 177.8f;  // 7" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Thickness = 19.05f;  // 3/4" in mm
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchLanding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 914.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 914.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Thickness = 25.4f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Elevation = 0.0f;
};

// Guardrail components
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchHandrail
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Profile;  // "round", "rectangular", "custom"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Diameter = 38.1f;  // 1.5" in mm (for round)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 863.6f;  // 34" in mm from tread nosing

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchBaluster
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Style;  // "square", "turned", "metal"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 31.75f;  // 1.25" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 31.75f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Spacing = 101.6f;  // 4" max per code

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchNewelPost
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 88.9f;  // 3.5" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 88.9f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 1066.8f;  // 42" in mm total height

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Style;  // "box", "turned", "craftsman"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchGuardrail
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 1066.8f;  // 42" per code for guards

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchHandrail Handrail;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchBaluster Baluster;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchNewelPost> NewelPosts;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Side;  // "left", "right", "both"
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchStair
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchStairType Type = EArchStairType::Straight;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString FromLevel;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ToLevel;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Direction = 0.0f;  // Rotation in degrees

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 914.4f;  // 36" min per code

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TotalRise = 2743.2f;  // Floor to floor height

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TreadDepth = 254.0f;  // 10" min per code

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float RiserHeight = 177.8f;  // 7" max per code

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 NumTreads = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchStairTread> Treads;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchStairRiser> Risers;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchLanding> Landings;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchGuardrail> Guardrails;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString StringerMaterial;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString TreadMaterial;
};

UENUM(BlueprintType)
enum class EArchElevatorType : uint8
{
    Passenger,
    Freight,
    Residential,
    Dumbwaiter
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchElevator
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    EArchElevatorType Type = EArchElevatorType::Passenger;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector ShaftPosition = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ShaftWidth = 1828.8f;  // 6ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float ShaftDepth = 1828.8f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float CabWidth = 1524.0f;  // 5ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float CabDepth = 1524.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float CabHeight = 2438.4f;  // 8ft in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FString> ServedLevels;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Capacity = 2500;  // lbs

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float DoorWidth = 914.4f;  // 36" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString DoorSide;  // "front", "rear", "side", "through"
};

// ========== MEP FIXTURES ==========

UENUM(BlueprintType)
enum class EArchFixtureCategory : uint8
{
    Plumbing,
    Electrical,
    HVAC
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchRoughIn
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString ConnectionType;  // "hot", "cold", "drain", "vent", "gas"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Offset = FVector::ZeroVector;  // Offset from fixture center

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Size = 12.7f;  // Pipe/conduit size in mm (1/2")
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchPlumbingFixture
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "toilet", "sink", "shower", "tub", "water_heater"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LevelName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchRoughIn> RoughIns;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString WallId;  // For wall-mounted fixtures
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchElectricalFixture
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "outlet", "switch", "panel", "light", "smoke_detector"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LevelName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float MountHeight = 0.0f;  // Height from floor (0 = ceiling mount)

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Circuit = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Amperage = 15;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString WallId;  // For wall-mounted fixtures
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchHVACFixture
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "supply_register", "return_grille", "thermostat", "exhaust_fan"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector Position = FVector::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Rotation = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Room;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString LevelName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 304.8f;  // 12" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Height = 152.4f;  // 6" in mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 CFM = 100;  // Cubic feet per minute
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchMEP
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchPlumbingFixture> PlumbingFixtures;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchElectricalFixture> ElectricalFixtures;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchHVACFixture> HVACFixtures;
};

// ========== MATERIALS ==========

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchMaterialLayer
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Material;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Thickness = 0.0f;  // In mm

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float RValue = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float CostPerSqFt = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString FireRating;  // "1-hour", "2-hour", etc.

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FLinearColor VisualizationColor = FLinearColor::White;
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchAssembly
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString AssemblyType;  // "wall", "floor", "roof", "ceiling"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchMaterialLayer> Layers;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TotalRValue = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float TotalCostPerSqFt = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString FireRating;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString CodeReference;  // IRC/IBC section

    // Calculate totals from layers
    void CalculateTotals()
    {
        TotalRValue = 0.0f;
        TotalCostPerSqFt = 0.0f;
        for (const auto& Layer : Layers)
        {
            TotalRValue += Layer.RValue;
            TotalCostPerSqFt += Layer.CostPerSqFt;
        }
    }
};

USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchMaterials
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchAssembly> WallAssemblies;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchAssembly> FloorAssemblies;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchAssembly> RoofAssemblies;
};

// Complete building data
USTRUCT(BlueprintType)
struct ARCHENGINE_API FArchBuilding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString BuildingId;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Unit;  // "mm" or "feet"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Width = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Depth = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float SqFt = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchElement> Elements;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchWallType> WallTypes;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchParametricWall> ParametricWalls;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchDoor> Doors;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchWindow> Windows;

    // New schema additions
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchLevel> Levels;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TMap<FString, FArchRoom> Rooms;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchDimension> Dimensions;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchRoof> Roofs;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchStair> Stairs;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchElevator> Elevators;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchMEP MEP;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FArchMaterials Materials;

    // Annotation sets for different plan types (floor plan, roof plan, etc.)
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchAnnotationSet> AnnotationSets;

    // Grid system
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TArray<FArchGridLine> GridLines;
};
