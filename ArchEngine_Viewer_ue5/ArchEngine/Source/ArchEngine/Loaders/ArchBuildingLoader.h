// ArchBuildingLoader.h - JSON loader for building data

#pragma once

#include "CoreMinimal.h"
#include "Types/ArchTypes.h"
#include "ArchBuildingLoader.generated.h"

UCLASS(BlueprintType)
class ARCHENGINE_API UArchBuildingLoader : public UObject
{
    GENERATED_BODY()

public:
    // Load building from JSON file
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static bool LoadBuildingFromFile(const FString& FilePath, FArchBuilding& OutBuilding);

    // Load building from JSON string
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static bool LoadBuildingFromString(const FString& JsonString, FArchBuilding& OutBuilding);

    // Save building to JSON file
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static bool SaveBuildingToFile(const FString& FilePath, const FArchBuilding& Building);

    // Convert building to JSON string
    UFUNCTION(BlueprintCallable, Category = "ArchEngine")
    static FString BuildingToJsonString(const FArchBuilding& Building);

private:
    // Format detection
    static bool IsQBDFormat(const TSharedPtr<FJsonObject>& JsonObject);

    // Parse helpers - Standard format
    static bool ParseBuilding(const TSharedPtr<FJsonObject>& JsonObject, FArchBuilding& OutBuilding);
    static bool ParseElement(const TSharedPtr<FJsonObject>& JsonObject, FArchElement& OutElement);
    static bool ParseWallType(const TSharedPtr<FJsonObject>& JsonObject, FArchWallType& OutWallType);
    static bool ParseWallLayer(const TSharedPtr<FJsonObject>& JsonObject, FArchWallLayer& OutLayer);
    static bool ParseFastener(const TSharedPtr<FJsonObject>& JsonObject, FArchFastener& OutFastener);
    static bool ParseConstraint(const TSharedPtr<FJsonObject>& JsonObject, FArchConstraint& OutConstraint);
    static bool ParseParametricWall(const TSharedPtr<FJsonObject>& JsonObject, FArchParametricWall& OutWall);

    // Parse helpers - QBD format
    static bool ParseQBDBuilding(const TSharedPtr<FJsonObject>& JsonObject, FArchBuilding& OutBuilding);
    static bool ParseQBDWallType(const TSharedPtr<FJsonObject>& JsonObject, FArchWallType& OutWallType);
    static bool ParseQBDWall(const TSharedPtr<FJsonObject>& JsonObject, FArchElement& OutElement, FArchParametricWall& OutParamWall, int32 WallIndex);
    static bool ParseQBDDoor(const TSharedPtr<FJsonObject>& JsonObject, FArchDoor& OutDoor);
    static bool ParseQBDWindow(const TSharedPtr<FJsonObject>& JsonObject, FArchWindow& OutWindow);
    static FArchWallType CreateDefaultExteriorWallType();
    static FArchWallType CreateDefaultInteriorWallType();
    static FArchWallType CreateDefaultWetWallType();

    // QBD enum parsers
    static EArchDoorType ParseDoorType(const FString& TypeStr);
    static EArchDoorSwing ParseDoorSwing(const FString& SwingStr);
    static EArchWindowType ParseWindowType(const FString& TypeStr);

    // Parse helpers - QBD v2.0 new types
    static bool ParseQBDLevel(const TSharedPtr<FJsonObject>& JsonObject, FArchLevel& OutLevel);
    static bool ParseQBDRoom(const FString& RoomId, const TSharedPtr<FJsonObject>& JsonObject, FArchRoom& OutRoom);
    static bool ParseQBDDimension(const TSharedPtr<FJsonObject>& JsonObject, FArchDimension& OutDimension);
    static bool ParseQBDRoof(const TSharedPtr<FJsonObject>& JsonObject, FArchRoof& OutRoof);
    static bool ParseQBDDormer(const TSharedPtr<FJsonObject>& JsonObject, FArchDormer& OutDormer);
    static bool ParseQBDSkylight(const TSharedPtr<FJsonObject>& JsonObject, FArchSkylight& OutSkylight);
    static bool ParseQBDStair(const TSharedPtr<FJsonObject>& JsonObject, FArchStair& OutStair);
    static bool ParseQBDGuardrail(const TSharedPtr<FJsonObject>& JsonObject, FArchGuardrail& OutGuardrail);
    static bool ParseQBDElevator(const TSharedPtr<FJsonObject>& JsonObject, FArchElevator& OutElevator);
    static bool ParseQBDMEP(const TSharedPtr<FJsonObject>& JsonObject, FArchMEP& OutMEP);
    static bool ParseQBDPlumbingFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchPlumbingFixture& OutFixture);
    static bool ParseQBDElectricalFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchElectricalFixture& OutFixture);
    static bool ParseQBDHVACFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchHVACFixture& OutFixture);
    static bool ParseQBDMaterials(const TSharedPtr<FJsonObject>& JsonObject, FArchMaterials& OutMaterials);
    static bool ParseQBDAssembly(const TSharedPtr<FJsonObject>& JsonObject, FArchAssembly& OutAssembly);

    // Parse helpers - Annotations
    static bool ParseQBDAnnotationSet(const TSharedPtr<FJsonObject>& JsonObject, FArchAnnotationSet& OutSet);
    static bool ParseQBDTextLabel(const TSharedPtr<FJsonObject>& JsonObject, FArchTextLabel& OutLabel);
    static bool ParseQBDLeader(const TSharedPtr<FJsonObject>& JsonObject, FArchLeader& OutLeader);
    static bool ParseQBDSymbol(const TSharedPtr<FJsonObject>& JsonObject, FArchSymbol& OutSymbol);
    static bool ParseQBDRoofAnnotation(const TSharedPtr<FJsonObject>& JsonObject, FArchRoofAnnotation& OutAnnotation);
    static bool ParseQBDGridLine(const TSharedPtr<FJsonObject>& JsonObject, FArchGridLine& OutGridLine);

    // Enum converters
    static EArchElementType StringToElementType(const FString& Str);
    static ELayerFunction StringToLayerFunction(const FString& Str);
    static EFastenerType StringToFastenerType(const FString& Str);
    static EArchConstraintType StringToConstraintType(const FString& Str);
    static EArchRoofType StringToRoofType(const FString& Str);
    static EArchStairType StringToStairType(const FString& Str);
    static EArchRoomZone StringToRoomZone(const FString& Str);
    static EArchDimensionType StringToDimensionType(const FString& Str);
    static EArchElevatorType StringToElevatorType(const FString& Str);
    static EArchPlanType StringToPlanType(const FString& Str);
    static EArchSymbolType StringToSymbolType(const FString& Str);
    static EArchRoofAnnotationType StringToRoofAnnotationType(const FString& Str);

    static FString ElementTypeToString(EArchElementType Type);
    static FString LayerFunctionToString(ELayerFunction Func);
    static FString FastenerTypeToString(EFastenerType Type);
    static FString ConstraintTypeToString(EArchConstraintType Type);
};
