// ArchBuildingLoader.cpp - JSON loader implementation

#include "ArchBuildingLoader.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"

bool UArchBuildingLoader::LoadBuildingFromFile(const FString& FilePath, FArchBuilding& OutBuilding)
{
    FString JsonString;
    if (!FFileHelper::LoadFileToString(JsonString, *FilePath))
    {
        UE_LOG(LogTemp, Error, TEXT("ArchBuildingLoader: Failed to load file: %s"), *FilePath);
        return false;
    }

    return LoadBuildingFromString(JsonString, OutBuilding);
}

bool UArchBuildingLoader::LoadBuildingFromString(const FString& JsonString, FArchBuilding& OutBuilding)
{
    TSharedPtr<FJsonObject> JsonObject;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonString);

    if (!FJsonSerializer::Deserialize(Reader, JsonObject) || !JsonObject.IsValid())
    {
        UE_LOG(LogTemp, Error, TEXT("ArchBuildingLoader: Failed to parse JSON"));
        return false;
    }

    // Auto-detect format
    if (IsQBDFormat(JsonObject))
    {
        UE_LOG(LogTemp, Log, TEXT("ArchBuildingLoader: Detected QBD format"));
        return ParseQBDBuilding(JsonObject, OutBuilding);
    }

    return ParseBuilding(JsonObject, OutBuilding);
}

bool UArchBuildingLoader::IsQBDFormat(const TSharedPtr<FJsonObject>& JsonObject)
{
    // QBD format has walls_batch and/or success field
    return JsonObject->HasField(TEXT("walls_batch")) ||
           (JsonObject->HasField(TEXT("success")) && JsonObject->HasField(TEXT("width")));
}

bool UArchBuildingLoader::SaveBuildingToFile(const FString& FilePath, const FArchBuilding& Building)
{
    FString JsonString = BuildingToJsonString(Building);
    return FFileHelper::SaveStringToFile(JsonString, *FilePath);
}

FString UArchBuildingLoader::BuildingToJsonString(const FArchBuilding& Building)
{
    TSharedPtr<FJsonObject> JsonObject = MakeShareable(new FJsonObject);

    JsonObject->SetStringField(TEXT("name"), Building.Name);

    // Elements
    TArray<TSharedPtr<FJsonValue>> ElementsArray;
    for (const auto& Elem : Building.Elements)
    {
        TSharedPtr<FJsonObject> ElemObj = MakeShareable(new FJsonObject);
        ElemObj->SetNumberField(TEXT("type"), static_cast<int32>(Elem.Type));

        TArray<TSharedPtr<FJsonValue>> StartArr;
        StartArr.Add(MakeShareable(new FJsonValueNumber(Elem.Start.X)));
        StartArr.Add(MakeShareable(new FJsonValueNumber(Elem.Start.Y)));
        StartArr.Add(MakeShareable(new FJsonValueNumber(Elem.Start.Z)));
        ElemObj->SetArrayField(TEXT("start"), StartArr);

        TArray<TSharedPtr<FJsonValue>> EndArr;
        EndArr.Add(MakeShareable(new FJsonValueNumber(Elem.End.X)));
        EndArr.Add(MakeShareable(new FJsonValueNumber(Elem.End.Y)));
        EndArr.Add(MakeShareable(new FJsonValueNumber(Elem.End.Z)));
        ElemObj->SetArrayField(TEXT("end"), EndArr);

        ElemObj->SetNumberField(TEXT("width"), Elem.Width);
        ElemObj->SetNumberField(TEXT("depth"), Elem.Depth);
        ElemObj->SetStringField(TEXT("material"), Elem.Material);
        ElemObj->SetNumberField(TEXT("stress"), Elem.Stress);
        ElemObj->SetNumberField(TEXT("deflection"), Elem.Deflection);
        ElemObj->SetBoolField(TEXT("failed"), Elem.bFailed);

        ElementsArray.Add(MakeShareable(new FJsonValueObject(ElemObj)));
    }
    JsonObject->SetArrayField(TEXT("elements"), ElementsArray);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObject.ToSharedRef(), Writer);

    return OutputString;
}

bool UArchBuildingLoader::ParseBuilding(const TSharedPtr<FJsonObject>& JsonObject, FArchBuilding& OutBuilding)
{
    OutBuilding.Name = JsonObject->GetStringField(TEXT("name"));

    // Parse elements
    const TArray<TSharedPtr<FJsonValue>>* ElementsArray;
    if (JsonObject->TryGetArrayField(TEXT("elements"), ElementsArray))
    {
        for (const auto& ElemValue : *ElementsArray)
        {
            FArchElement Element;
            if (ParseElement(ElemValue->AsObject(), Element))
            {
                OutBuilding.Elements.Add(Element);
            }
        }
    }

    // Parse wall types
    const TArray<TSharedPtr<FJsonValue>>* WallTypesArray;
    if (JsonObject->TryGetArrayField(TEXT("wallTypes"), WallTypesArray))
    {
        for (const auto& WtValue : *WallTypesArray)
        {
            FArchWallType WallType;
            if (ParseWallType(WtValue->AsObject(), WallType))
            {
                OutBuilding.WallTypes.Add(WallType);
            }
        }
    }

    // Parse parametric walls
    const TArray<TSharedPtr<FJsonValue>>* ParamWallsArray;
    if (JsonObject->TryGetArrayField(TEXT("parametricWalls"), ParamWallsArray))
    {
        for (const auto& PwValue : *ParamWallsArray)
        {
            FArchParametricWall Wall;
            if (ParseParametricWall(PwValue->AsObject(), Wall))
            {
                OutBuilding.ParametricWalls.Add(Wall);
            }
        }
    }

    UE_LOG(LogTemp, Log, TEXT("ArchBuildingLoader: Loaded '%s' with %d elements, %d wall types, %d parametric walls"),
        *OutBuilding.Name, OutBuilding.Elements.Num(), OutBuilding.WallTypes.Num(), OutBuilding.ParametricWalls.Num());

    return true;
}

bool UArchBuildingLoader::ParseElement(const TSharedPtr<FJsonObject>& JsonObject, FArchElement& OutElement)
{
    if (!JsonObject.IsValid()) return false;

    OutElement.Type = static_cast<EArchElementType>(JsonObject->GetIntegerField(TEXT("type")));

    const TArray<TSharedPtr<FJsonValue>>* StartArr;
    if (JsonObject->TryGetArrayField(TEXT("start"), StartArr) && StartArr->Num() >= 3)
    {
        OutElement.Start.X = (*StartArr)[0]->AsNumber();
        OutElement.Start.Y = (*StartArr)[1]->AsNumber();
        OutElement.Start.Z = (*StartArr)[2]->AsNumber();
    }

    const TArray<TSharedPtr<FJsonValue>>* EndArr;
    if (JsonObject->TryGetArrayField(TEXT("end"), EndArr) && EndArr->Num() >= 3)
    {
        OutElement.End.X = (*EndArr)[0]->AsNumber();
        OutElement.End.Y = (*EndArr)[1]->AsNumber();
        OutElement.End.Z = (*EndArr)[2]->AsNumber();
    }

    OutElement.Width = JsonObject->GetNumberField(TEXT("width"));
    OutElement.Depth = JsonObject->GetNumberField(TEXT("depth"));
    OutElement.Material = JsonObject->GetStringField(TEXT("material"));
    OutElement.Stress = JsonObject->GetNumberField(TEXT("stress"));
    OutElement.Deflection = JsonObject->GetNumberField(TEXT("deflection"));
    OutElement.bFailed = JsonObject->GetBoolField(TEXT("failed"));

    // Parse mesh if present
    const TSharedPtr<FJsonObject>* MeshObj;
    if (JsonObject->TryGetObjectField(TEXT("mesh"), MeshObj))
    {
        const TArray<TSharedPtr<FJsonValue>>* VerticesArr;
        if ((*MeshObj)->TryGetArrayField(TEXT("vertices"), VerticesArr))
        {
            for (const auto& VertValue : *VerticesArr)
            {
                const TArray<TSharedPtr<FJsonValue>>& VertArr = VertValue->AsArray();
                if (VertArr.Num() >= 3)
                {
                    OutElement.Mesh.Vertices.Add(FVector(
                        VertArr[0]->AsNumber(),
                        VertArr[1]->AsNumber(),
                        VertArr[2]->AsNumber()
                    ));
                }
            }
        }

        const TArray<TSharedPtr<FJsonValue>>* FacesArr;
        if ((*MeshObj)->TryGetArrayField(TEXT("faces"), FacesArr))
        {
            for (const auto& FaceValue : *FacesArr)
            {
                const TArray<TSharedPtr<FJsonValue>>& FaceArr = FaceValue->AsArray();
                if (FaceArr.Num() >= 3)
                {
                    OutElement.Mesh.Triangles.Add(FaceArr[0]->AsNumber());
                    OutElement.Mesh.Triangles.Add(FaceArr[1]->AsNumber());
                    OutElement.Mesh.Triangles.Add(FaceArr[2]->AsNumber());
                }
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseWallType(const TSharedPtr<FJsonObject>& JsonObject, FArchWallType& OutWallType)
{
    if (!JsonObject.IsValid()) return false;

    OutWallType.Id = JsonObject->GetStringField(TEXT("id"));
    OutWallType.Name = JsonObject->GetStringField(TEXT("name"));

    // Parse intent
    const TSharedPtr<FJsonObject>* IntentObj;
    if (JsonObject->TryGetObjectField(TEXT("intent"), IntentObj))
    {
        OutWallType.Intent.RValueTarget = (*IntentObj)->GetNumberField(TEXT("r_value_target"));
        OutWallType.Intent.StructuralRole = (*IntentObj)->GetStringField(TEXT("structural_role"));
        OutWallType.Intent.ClimateZone = (*IntentObj)->GetStringField(TEXT("climate_zone"));
    }

    // Parse layers
    const TArray<TSharedPtr<FJsonValue>>* LayersArr;
    if (JsonObject->TryGetArrayField(TEXT("layers"), LayersArr))
    {
        for (const auto& LayerValue : *LayersArr)
        {
            FArchWallLayer Layer;
            if (ParseWallLayer(LayerValue->AsObject(), Layer))
            {
                OutWallType.Layers.Add(Layer);
            }
        }
    }

    // Parse constraints
    const TArray<TSharedPtr<FJsonValue>>* ConstraintsArr;
    if (JsonObject->TryGetArrayField(TEXT("constraints"), ConstraintsArr))
    {
        for (const auto& ConstraintValue : *ConstraintsArr)
        {
            FArchConstraint Constraint;
            if (ParseConstraint(ConstraintValue->AsObject(), Constraint))
            {
                OutWallType.Constraints.Add(Constraint);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseWallLayer(const TSharedPtr<FJsonObject>& JsonObject, FArchWallLayer& OutLayer)
{
    if (!JsonObject.IsValid()) return false;

    OutLayer.Name = JsonObject->GetStringField(TEXT("name"));
    OutLayer.Material = JsonObject->GetStringField(TEXT("material"));
    OutLayer.Function = StringToLayerFunction(JsonObject->GetStringField(TEXT("function")));
    OutLayer.Thickness = JsonObject->GetNumberField(TEXT("thickness"));
    OutLayer.RValue = JsonObject->GetNumberField(TEXT("r_value"));

    // Parse color
    const TArray<TSharedPtr<FJsonValue>>* ColorArr;
    if (JsonObject->TryGetArrayField(TEXT("color"), ColorArr) && ColorArr->Num() >= 3)
    {
        OutLayer.Color = FLinearColor(
            (*ColorArr)[0]->AsNumber(),
            (*ColorArr)[1]->AsNumber(),
            (*ColorArr)[2]->AsNumber(),
            1.0f
        );
    }

    // Parse fasteners
    const TArray<TSharedPtr<FJsonValue>>* FastenersArr;
    if (JsonObject->TryGetArrayField(TEXT("fasteners"), FastenersArr))
    {
        for (const auto& FastenerValue : *FastenersArr)
        {
            FArchFastener Fastener;
            if (ParseFastener(FastenerValue->AsObject(), Fastener))
            {
                OutLayer.Fasteners.Add(Fastener);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseFastener(const TSharedPtr<FJsonObject>& JsonObject, FArchFastener& OutFastener)
{
    if (!JsonObject.IsValid()) return false;

    OutFastener.Name = JsonObject->GetStringField(TEXT("name"));
    OutFastener.Type = StringToFastenerType(JsonObject->GetStringField(TEXT("type")));
    OutFastener.Material = JsonObject->GetStringField(TEXT("material"));
    OutFastener.Diameter = JsonObject->GetNumberField(TEXT("diameter"));
    OutFastener.Length = JsonObject->GetNumberField(TEXT("length"));
    OutFastener.FieldSpacing = JsonObject->GetNumberField(TEXT("field_spacing"));
    OutFastener.EdgeSpacing = JsonObject->GetNumberField(TEXT("edge_spacing"));
    OutFastener.CodeReference = JsonObject->GetStringField(TEXT("code_reference"));
    OutFastener.ShearCapacity = JsonObject->GetNumberField(TEXT("shear_capacity"));
    OutFastener.WithdrawalCapacity = JsonObject->GetNumberField(TEXT("withdrawal_capacity"));

    return true;
}

bool UArchBuildingLoader::ParseConstraint(const TSharedPtr<FJsonObject>& JsonObject, FArchConstraint& OutConstraint)
{
    if (!JsonObject.IsValid()) return false;

    OutConstraint.Type = StringToConstraintType(JsonObject->GetStringField(TEXT("type")));
    OutConstraint.Name = JsonObject->GetStringField(TEXT("name"));
    OutConstraint.Value = JsonObject->GetStringField(TEXT("value"));
    OutConstraint.CodeSection = JsonObject->GetStringField(TEXT("code_section"));
    OutConstraint.Description = JsonObject->GetStringField(TEXT("description"));
    OutConstraint.bIsMet = JsonObject->GetBoolField(TEXT("is_met"));

    return true;
}

bool UArchBuildingLoader::ParseParametricWall(const TSharedPtr<FJsonObject>& JsonObject, FArchParametricWall& OutWall)
{
    if (!JsonObject.IsValid()) return false;

    OutWall.Id = JsonObject->GetStringField(TEXT("id"));
    OutWall.WallTypeIndex = JsonObject->GetIntegerField(TEXT("wall_type_index"));
    OutWall.BaseHeight = JsonObject->GetNumberField(TEXT("base_height"));
    OutWall.TopHeight = JsonObject->GetNumberField(TEXT("top_height"));

    const TArray<TSharedPtr<FJsonValue>>* StartArr;
    if (JsonObject->TryGetArrayField(TEXT("start_point"), StartArr) && StartArr->Num() >= 2)
    {
        OutWall.StartPoint.X = (*StartArr)[0]->AsNumber();
        OutWall.StartPoint.Y = (*StartArr)[1]->AsNumber();
    }

    const TArray<TSharedPtr<FJsonValue>>* EndArr;
    if (JsonObject->TryGetArrayField(TEXT("end_point"), EndArr) && EndArr->Num() >= 2)
    {
        OutWall.EndPoint.X = (*EndArr)[0]->AsNumber();
        OutWall.EndPoint.Y = (*EndArr)[1]->AsNumber();
    }

    return true;
}

// Enum converters
EArchElementType UArchBuildingLoader::StringToElementType(const FString& Str)
{
    if (Str == TEXT("beam")) return EArchElementType::Beam;
    if (Str == TEXT("column")) return EArchElementType::Column;
    if (Str == TEXT("floor")) return EArchElementType::Floor;
    if (Str == TEXT("wall")) return EArchElementType::Wall;
    if (Str == TEXT("foundation")) return EArchElementType::Foundation;
    if (Str == TEXT("connection")) return EArchElementType::Connection;
    if (Str == TEXT("door")) return EArchElementType::Door;
    if (Str == TEXT("window")) return EArchElementType::Window;
    if (Str == TEXT("roof")) return EArchElementType::Roof;
    return EArchElementType::Beam;
}

ELayerFunction UArchBuildingLoader::StringToLayerFunction(const FString& Str)
{
    if (Str == TEXT("exterior_finish")) return ELayerFunction::ExteriorFinish;
    if (Str == TEXT("sheathing")) return ELayerFunction::Sheathing;
    if (Str == TEXT("insulation")) return ELayerFunction::Insulation;
    if (Str == TEXT("structure")) return ELayerFunction::Structure;
    if (Str == TEXT("interior_finish")) return ELayerFunction::InteriorFinish;
    if (Str == TEXT("air_gap")) return ELayerFunction::AirGap;
    if (Str == TEXT("membrane")) return ELayerFunction::Membrane;
    return ELayerFunction::Structure;
}

EFastenerType UArchBuildingLoader::StringToFastenerType(const FString& Str)
{
    if (Str == TEXT("nail")) return EFastenerType::Nail;
    if (Str == TEXT("screw")) return EFastenerType::Screw;
    if (Str == TEXT("bolt")) return EFastenerType::Bolt;
    if (Str == TEXT("staple")) return EFastenerType::Staple;
    if (Str == TEXT("anchor")) return EFastenerType::Anchor;
    if (Str == TEXT("strap")) return EFastenerType::Strap;
    if (Str == TEXT("hanger")) return EFastenerType::Hanger;
    if (Str == TEXT("clip")) return EFastenerType::Clip;
    if (Str == TEXT("adhesive")) return EFastenerType::Adhesive;
    return EFastenerType::Nail;
}

EArchConstraintType UArchBuildingLoader::StringToConstraintType(const FString& Str)
{
    if (Str == TEXT("structural_bearing")) return EArchConstraintType::StructuralBearing;
    if (Str == TEXT("fire_rating")) return EArchConstraintType::FireRating;
    if (Str == TEXT("thermal_performance")) return EArchConstraintType::ThermalPerformance;
    if (Str == TEXT("sound_transmission")) return EArchConstraintType::SoundTransmission;
    if (Str == TEXT("moisture_control")) return EArchConstraintType::MoistureControl;
    if (Str == TEXT("air_barrier")) return EArchConstraintType::AirBarrier;
    if (Str == TEXT("wind_resistance")) return EArchConstraintType::WindResistance;
    if (Str == TEXT("seismic_category")) return EArchConstraintType::SeismicCategory;
    if (Str == TEXT("max_span")) return EArchConstraintType::MaxSpan;
    if (Str == TEXT("min_thickness")) return EArchConstraintType::MinThickness;
    if (Str == TEXT("code_section")) return EArchConstraintType::CodeSection;
    return EArchConstraintType::CodeSection;
}

FString UArchBuildingLoader::ElementTypeToString(EArchElementType Type)
{
    switch (Type)
    {
        case EArchElementType::Beam: return TEXT("beam");
        case EArchElementType::Column: return TEXT("column");
        case EArchElementType::Floor: return TEXT("floor");
        case EArchElementType::Wall: return TEXT("wall");
        case EArchElementType::Foundation: return TEXT("foundation");
        case EArchElementType::Connection: return TEXT("connection");
        case EArchElementType::Door: return TEXT("door");
        case EArchElementType::Window: return TEXT("window");
        case EArchElementType::Roof: return TEXT("roof");
        default: return TEXT("beam");
    }
}

FString UArchBuildingLoader::LayerFunctionToString(ELayerFunction Func)
{
    switch (Func)
    {
        case ELayerFunction::ExteriorFinish: return TEXT("exterior_finish");
        case ELayerFunction::Sheathing: return TEXT("sheathing");
        case ELayerFunction::Insulation: return TEXT("insulation");
        case ELayerFunction::Structure: return TEXT("structure");
        case ELayerFunction::InteriorFinish: return TEXT("interior_finish");
        case ELayerFunction::AirGap: return TEXT("air_gap");
        case ELayerFunction::Membrane: return TEXT("membrane");
        default: return TEXT("structure");
    }
}

FString UArchBuildingLoader::FastenerTypeToString(EFastenerType Type)
{
    switch (Type)
    {
        case EFastenerType::Nail: return TEXT("nail");
        case EFastenerType::Screw: return TEXT("screw");
        case EFastenerType::Bolt: return TEXT("bolt");
        case EFastenerType::Staple: return TEXT("staple");
        case EFastenerType::Anchor: return TEXT("anchor");
        case EFastenerType::Strap: return TEXT("strap");
        case EFastenerType::Hanger: return TEXT("hanger");
        case EFastenerType::Clip: return TEXT("clip");
        case EFastenerType::Adhesive: return TEXT("adhesive");
        default: return TEXT("nail");
    }
}

FString UArchBuildingLoader::ConstraintTypeToString(EArchConstraintType Type)
{
    switch (Type)
    {
        case EArchConstraintType::StructuralBearing: return TEXT("structural_bearing");
        case EArchConstraintType::FireRating: return TEXT("fire_rating");
        case EArchConstraintType::ThermalPerformance: return TEXT("thermal_performance");
        case EArchConstraintType::SoundTransmission: return TEXT("sound_transmission");
        case EArchConstraintType::MoistureControl: return TEXT("moisture_control");
        case EArchConstraintType::AirBarrier: return TEXT("air_barrier");
        case EArchConstraintType::WindResistance: return TEXT("wind_resistance");
        case EArchConstraintType::SeismicCategory: return TEXT("seismic_category");
        case EArchConstraintType::MaxSpan: return TEXT("max_span");
        case EArchConstraintType::MinThickness: return TEXT("min_thickness");
        case EArchConstraintType::CodeSection: return TEXT("code_section");
        default: return TEXT("code_section");
    }
}

// ============================================================================
// QBD FORMAT PARSING
// ============================================================================

bool UArchBuildingLoader::ParseQBDBuilding(const TSharedPtr<FJsonObject>& JsonObject, FArchBuilding& OutBuilding)
{
    // Parse top-level building info
    OutBuilding.BuildingId = JsonObject->GetStringField(TEXT("building_id"));
    OutBuilding.Unit = JsonObject->GetStringField(TEXT("unit"));
    OutBuilding.Width = JsonObject->GetNumberField(TEXT("width"));
    OutBuilding.Depth = JsonObject->GetNumberField(TEXT("depth"));
    OutBuilding.SqFt = JsonObject->GetNumberField(TEXT("sqft"));

    // Set building name from QBD data
    OutBuilding.Name = FString::Printf(TEXT("QBD Layout %.0fx%.0f (%.0f sqft)"),
        OutBuilding.Width, OutBuilding.Depth, OutBuilding.SqFt);

    // Parse wall types from JSON if available, otherwise use defaults
    const TArray<TSharedPtr<FJsonValue>>* WallTypesArray;
    if (JsonObject->TryGetArrayField(TEXT("wall_types"), WallTypesArray) && WallTypesArray->Num() > 0)
    {
        for (const auto& WtValue : *WallTypesArray)
        {
            FArchWallType WallType;
            if (ParseQBDWallType(WtValue->AsObject(), WallType))
            {
                OutBuilding.WallTypes.Add(WallType);
            }
        }
        UE_LOG(LogTemp, Log, TEXT("Parsed %d wall types from JSON"), OutBuilding.WallTypes.Num());
    }
    else
    {
        // Create default wall types
        OutBuilding.WallTypes.Add(CreateDefaultExteriorWallType());  // Index 0
        OutBuilding.WallTypes.Add(CreateDefaultInteriorWallType());  // Index 1
        OutBuilding.WallTypes.Add(CreateDefaultWetWallType());       // Index 2
        UE_LOG(LogTemp, Log, TEXT("Using default wall types"));
    }

    // Parse levels
    const TArray<TSharedPtr<FJsonValue>>* LevelsArray;
    if (JsonObject->TryGetArrayField(TEXT("levels"), LevelsArray))
    {
        for (const auto& LevelValue : *LevelsArray)
        {
            FArchLevel Level;
            if (ParseQBDLevel(LevelValue->AsObject(), Level))
            {
                OutBuilding.Levels.Add(Level);
            }
        }
    }

    // Parse rooms (object map: room_id -> room data)
    const TSharedPtr<FJsonObject>* RoomsObject;
    if (JsonObject->TryGetObjectField(TEXT("rooms"), RoomsObject))
    {
        for (const auto& RoomPair : (*RoomsObject)->Values)
        {
            FArchRoom Room;
            if (ParseQBDRoom(RoomPair.Key, RoomPair.Value->AsObject(), Room))
            {
                OutBuilding.Rooms.Add(RoomPair.Key, Room);
            }
        }
    }

    // Parse walls
    const TArray<TSharedPtr<FJsonValue>>* WallsArray;
    if (JsonObject->TryGetArrayField(TEXT("walls_batch"), WallsArray))
    {
        int32 WallIndex = 0;
        int32 SuccessCount = 0;
        for (const auto& WallValue : *WallsArray)
        {
            FArchElement Element;
            FArchParametricWall ParamWall;

            if (ParseQBDWall(WallValue->AsObject(), Element, ParamWall, WallIndex))
            {
                OutBuilding.Elements.Add(Element);
                OutBuilding.ParametricWalls.Add(ParamWall);
                SuccessCount++;
            }
            else
            {
                UE_LOG(LogTemp, Warning, TEXT("Failed to parse wall %d"), WallIndex);
            }
            WallIndex++;
        }
        UE_LOG(LogTemp, Log, TEXT("Parsed %d/%d walls from walls_batch"), SuccessCount, WallsArray->Num());
        if (SuccessCount != WallsArray->Num())
        {
            UE_LOG(LogTemp, Error, TEXT("WARNING: Wall count mismatch! Door/window wall_index will be incorrect!"));
        }
    }

    // Parse doors
    const TArray<TSharedPtr<FJsonValue>>* DoorsArray;
    if (JsonObject->TryGetArrayField(TEXT("doors"), DoorsArray))
    {
        int32 DoorIdx = 0;
        for (const auto& DoorValue : *DoorsArray)
        {
            FArchDoor Door;
            if (ParseQBDDoor(DoorValue->AsObject(), Door))
            {
                UE_LOG(LogTemp, Log, TEXT("Door %d: wall_index=%d, offset=%.1f, width=%.1f"),
                       DoorIdx, Door.WallIndex, Door.Offset, Door.Width);
                OutBuilding.Doors.Add(Door);
            }
            DoorIdx++;
        }
    }

    // Parse windows
    const TArray<TSharedPtr<FJsonValue>>* WindowsArray;
    if (JsonObject->TryGetArrayField(TEXT("windows"), WindowsArray))
    {
        for (const auto& WindowValue : *WindowsArray)
        {
            FArchWindow Window;
            if (ParseQBDWindow(WindowValue->AsObject(), Window))
            {
                OutBuilding.Windows.Add(Window);
            }
        }
    }

    // Parse dimensions
    const TArray<TSharedPtr<FJsonValue>>* DimensionsArray;
    if (JsonObject->TryGetArrayField(TEXT("dimensions"), DimensionsArray))
    {
        for (const auto& DimValue : *DimensionsArray)
        {
            FArchDimension Dimension;
            if (ParseQBDDimension(DimValue->AsObject(), Dimension))
            {
                OutBuilding.Dimensions.Add(Dimension);
            }
        }
    }

    // Parse roofs
    const TArray<TSharedPtr<FJsonValue>>* RoofsArray;
    if (JsonObject->TryGetArrayField(TEXT("roofs"), RoofsArray))
    {
        for (const auto& RoofValue : *RoofsArray)
        {
            FArchRoof Roof;
            if (ParseQBDRoof(RoofValue->AsObject(), Roof))
            {
                OutBuilding.Roofs.Add(Roof);
            }
        }
    }

    // Parse stairs
    const TArray<TSharedPtr<FJsonValue>>* StairsArray;
    if (JsonObject->TryGetArrayField(TEXT("stairs"), StairsArray))
    {
        for (const auto& StairValue : *StairsArray)
        {
            FArchStair Stair;
            if (ParseQBDStair(StairValue->AsObject(), Stair))
            {
                OutBuilding.Stairs.Add(Stair);
            }
        }
    }

    // Parse elevators
    const TArray<TSharedPtr<FJsonValue>>* ElevatorsArray;
    if (JsonObject->TryGetArrayField(TEXT("elevators"), ElevatorsArray))
    {
        for (const auto& ElevatorValue : *ElevatorsArray)
        {
            FArchElevator Elevator;
            if (ParseQBDElevator(ElevatorValue->AsObject(), Elevator))
            {
                OutBuilding.Elevators.Add(Elevator);
            }
        }
    }

    // Parse MEP
    const TSharedPtr<FJsonObject>* MEPObject;
    if (JsonObject->TryGetObjectField(TEXT("mep"), MEPObject))
    {
        ParseQBDMEP(*MEPObject, OutBuilding.MEP);
    }

    // Parse materials
    const TSharedPtr<FJsonObject>* MaterialsObject;
    if (JsonObject->TryGetObjectField(TEXT("materials"), MaterialsObject))
    {
        ParseQBDMaterials(*MaterialsObject, OutBuilding.Materials);
    }

    // Parse annotation sets
    const TArray<TSharedPtr<FJsonValue>>* AnnotationSetsArray;
    if (JsonObject->TryGetArrayField(TEXT("annotation_sets"), AnnotationSetsArray))
    {
        for (const auto& SetVal : *AnnotationSetsArray)
        {
            FArchAnnotationSet Set;
            if (ParseQBDAnnotationSet(SetVal->AsObject(), Set))
            {
                OutBuilding.AnnotationSets.Add(Set);
            }
        }
    }

    // Parse grid lines (building-level)
    const TArray<TSharedPtr<FJsonValue>>* GridLinesArray;
    if (JsonObject->TryGetArrayField(TEXT("grid_lines"), GridLinesArray))
    {
        for (const auto& GridVal : *GridLinesArray)
        {
            FArchGridLine Grid;
            if (ParseQBDGridLine(GridVal->AsObject(), Grid))
            {
                OutBuilding.GridLines.Add(Grid);
            }
        }
    }

    UE_LOG(LogTemp, Log, TEXT("ArchBuildingLoader: Loaded QBD '%s' with %d walls, %d doors, %d windows, %d levels, %d rooms, %d stairs, %d annotation sets"),
        *OutBuilding.Name, OutBuilding.Elements.Num(), OutBuilding.Doors.Num(), OutBuilding.Windows.Num(),
        OutBuilding.Levels.Num(), OutBuilding.Rooms.Num(), OutBuilding.Stairs.Num(), OutBuilding.AnnotationSets.Num());

    return true;
}

bool UArchBuildingLoader::ParseQBDWall(const TSharedPtr<FJsonObject>& JsonObject,
                                        FArchElement& OutElement,
                                        FArchParametricWall& OutParamWall,
                                        int32 WallIndex)
{
    if (!JsonObject.IsValid()) return false;

    // Parse start/end points (QBD format: [x, y, z] in mm, where y is vertical)
    // Convert: mm -> cm (divide by 10), swap Y and Z for Unreal's coordinate system
    const float MmToCm = 0.1f;

    FVector Start(0, 0, 0);
    FVector End(0, 0, 0);

    const TArray<TSharedPtr<FJsonValue>>* StartArr;
    if (JsonObject->TryGetArrayField(TEXT("start"), StartArr) && StartArr->Num() >= 3)
    {
        // QBD: [x, y, z] - pass through directly, KernelToUnreal handles coordinate conversion
        // Only convert mm -> cm here
        Start.X = (*StartArr)[0]->AsNumber() * MmToCm;
        Start.Y = (*StartArr)[1]->AsNumber() * MmToCm;
        Start.Z = (*StartArr)[2]->AsNumber() * MmToCm;
    }

    const TArray<TSharedPtr<FJsonValue>>* EndArr;
    if (JsonObject->TryGetArrayField(TEXT("end"), EndArr) && EndArr->Num() >= 3)
    {
        End.X = (*EndArr)[0]->AsNumber() * MmToCm;
        End.Y = (*EndArr)[1]->AsNumber() * MmToCm;
        End.Z = (*EndArr)[2]->AsNumber() * MmToCm;
    }

    float Height = JsonObject->GetNumberField(TEXT("height")) * MmToCm;
    FString Category = JsonObject->GetStringField(TEXT("category"));

    // Determine wall type index based on category
    int32 WallTypeIndex = 1;  // Default to interior
    float Thickness = 10.0f;  // Default 10cm

    if (Category == TEXT("exterior"))
    {
        WallTypeIndex = 0;
        Thickness = 17.5f;  // 2x6 wall ~7 inches
    }
    else if (Category == TEXT("wet_wall"))
    {
        WallTypeIndex = 2;
        Thickness = 17.5f;
    }
    else
    {
        Thickness = 11.5f;  // 2x4 wall ~4.5 inches
    }

    // Fill FArchElement
    // QBD format: [x, y, z] where Y is up (0 for floor-level), Z is depth
    // Kernel also uses Y-up, so height goes in Y component
    // Start = bottom corner, End = top corner at opposite horizontal end
    OutElement.Type = EArchElementType::Wall;
    OutElement.Start = Start;
    OutElement.End = FVector(End.X, Start.Y + Height, End.Z);
    OutElement.Width = Thickness;
    OutElement.Depth = Thickness;
    OutElement.Material = Category;
    OutElement.Stress = 0.0f;
    OutElement.Deflection = 0.0f;
    OutElement.bFailed = false;
    OutElement.WallIndex = WallIndex;  // Store JSON wall_index for door/window matching

    // Fill FArchParametricWall
    OutParamWall.Id = FString::Printf(TEXT("wall_%d"), WallIndex);
    OutParamWall.WallTypeIndex = WallTypeIndex;
    OutParamWall.StartPoint = FVector2D(Start.X, Start.Y);
    OutParamWall.EndPoint = FVector2D(End.X, End.Y);
    OutParamWall.BaseHeight = Start.Z;
    OutParamWall.TopHeight = Start.Z + Height;

    return true;
}

bool UArchBuildingLoader::ParseQBDDoor(const TSharedPtr<FJsonObject>& JsonObject, FArchDoor& OutDoor)
{
    if (!JsonObject.IsValid()) return false;

    const float MmToCm = 0.1f;

    OutDoor.WallIndex = JsonObject->GetIntegerField(TEXT("wall_index"));
    OutDoor.Offset = JsonObject->GetNumberField(TEXT("offset")) * MmToCm;
    OutDoor.Width = JsonObject->GetNumberField(TEXT("width")) * MmToCm;
    OutDoor.Height = JsonObject->GetNumberField(TEXT("height")) * MmToCm;
    OutDoor.Type = ParseDoorType(JsonObject->GetStringField(TEXT("type")));
    OutDoor.Swing = ParseDoorSwing(JsonObject->GetStringField(TEXT("swing")));
    OutDoor.Room1 = JsonObject->GetStringField(TEXT("room1"));
    OutDoor.Room2 = JsonObject->GetStringField(TEXT("room2"));

    return true;
}

bool UArchBuildingLoader::ParseQBDWindow(const TSharedPtr<FJsonObject>& JsonObject, FArchWindow& OutWindow)
{
    if (!JsonObject.IsValid()) return false;

    const float MmToCm = 0.1f;

    OutWindow.WallIndex = JsonObject->GetIntegerField(TEXT("wall_index"));
    OutWindow.Offset = JsonObject->GetNumberField(TEXT("offset")) * MmToCm;
    OutWindow.Width = JsonObject->GetNumberField(TEXT("width")) * MmToCm;
    OutWindow.Height = JsonObject->GetNumberField(TEXT("height")) * MmToCm;
    OutWindow.SillHeight = JsonObject->GetNumberField(TEXT("sill_height")) * MmToCm;
    OutWindow.Type = ParseWindowType(JsonObject->GetStringField(TEXT("type")));
    OutWindow.Room = JsonObject->GetStringField(TEXT("room"));

    return true;
}

EArchDoorType UArchBuildingLoader::ParseDoorType(const FString& TypeStr)
{
    if (TypeStr == TEXT("swing") || TypeStr == TEXT("door")) return EArchDoorType::Swing;
    if (TypeStr == TEXT("entry")) return EArchDoorType::Entry;
    if (TypeStr == TEXT("pocket")) return EArchDoorType::Pocket;
    if (TypeStr == TEXT("sliding")) return EArchDoorType::Sliding;
    if (TypeStr == TEXT("bifold")) return EArchDoorType::Bifold;
    if (TypeStr == TEXT("french")) return EArchDoorType::French;
    if (TypeStr == TEXT("barn")) return EArchDoorType::Barn;
    return EArchDoorType::Swing;
}

EArchDoorSwing UArchBuildingLoader::ParseDoorSwing(const FString& SwingStr)
{
    if (SwingStr == TEXT("left_in")) return EArchDoorSwing::LeftIn;
    if (SwingStr == TEXT("right_in")) return EArchDoorSwing::RightIn;
    if (SwingStr == TEXT("left_out")) return EArchDoorSwing::LeftOut;
    if (SwingStr == TEXT("right_out")) return EArchDoorSwing::RightOut;
    if (SwingStr == TEXT("left")) return EArchDoorSwing::Left;
    if (SwingStr == TEXT("right")) return EArchDoorSwing::Right;
    return EArchDoorSwing::LeftIn;
}

EArchWindowType UArchBuildingLoader::ParseWindowType(const FString& TypeStr)
{
    if (TypeStr == TEXT("fixed")) return EArchWindowType::Fixed;
    if (TypeStr == TEXT("casement")) return EArchWindowType::Casement;
    if (TypeStr == TEXT("double_hung")) return EArchWindowType::DoubleHung;
    if (TypeStr == TEXT("sliding")) return EArchWindowType::Sliding;
    if (TypeStr == TEXT("awning")) return EArchWindowType::Awning;
    return EArchWindowType::DoubleHung;
}

bool UArchBuildingLoader::ParseQBDWallType(const TSharedPtr<FJsonObject>& JsonObject, FArchWallType& OutWallType)
{
    if (!JsonObject.IsValid()) return false;

    // Parse basic info
    OutWallType.Id = JsonObject->GetStringField(TEXT("id"));
    OutWallType.Name = JsonObject->GetStringField(TEXT("name"));

    // Parse layers
    const TArray<TSharedPtr<FJsonValue>>* LayersArray;
    if (JsonObject->TryGetArrayField(TEXT("layers"), LayersArray))
    {
        const float MmToCm = 0.1f;  // Convert mm to cm for UE

        for (const auto& LayerValue : *LayersArray)
        {
            const TSharedPtr<FJsonObject>& LayerObj = LayerValue->AsObject();
            if (!LayerObj.IsValid()) continue;

            FArchWallLayer Layer;
            Layer.Name = LayerObj->GetStringField(TEXT("name"));
            Layer.Material = LayerObj->GetStringField(TEXT("material"));
            Layer.Thickness = LayerObj->GetNumberField(TEXT("thickness")) * MmToCm;
            Layer.RValue = LayerObj->GetNumberField(TEXT("r_value"));

            // Parse layer function
            FString FuncStr = LayerObj->GetStringField(TEXT("function"));
            Layer.Function = StringToLayerFunction(FuncStr);

            // Parse color [r, g, b, a]
            const TArray<TSharedPtr<FJsonValue>>* ColorArray;
            if (LayerObj->TryGetArrayField(TEXT("color"), ColorArray) && ColorArray->Num() >= 3)
            {
                Layer.Color = FLinearColor(
                    (*ColorArray)[0]->AsNumber(),
                    (*ColorArray)[1]->AsNumber(),
                    (*ColorArray)[2]->AsNumber(),
                    ColorArray->Num() >= 4 ? (*ColorArray)[3]->AsNumber() : 1.0f
                );
            }

            OutWallType.Layers.Add(Layer);
        }
    }

    return OutWallType.Layers.Num() > 0;
}

FArchWallType UArchBuildingLoader::CreateDefaultExteriorWallType()
{
    FArchWallType WallType;
    WallType.Id = TEXT("ext_2x6_r21");
    WallType.Name = TEXT("2x6 Exterior Wall R-21");
    WallType.Intent.RValueTarget = 21.0f;
    WallType.Intent.StructuralRole = TEXT("load_bearing");
    WallType.Intent.ClimateZone = TEXT("Zone 6");

    // Exterior finish
    FArchWallLayer Layer1;
    Layer1.Name = TEXT("Vinyl Siding");
    Layer1.Material = TEXT("vinyl");
    Layer1.Function = ELayerFunction::ExteriorFinish;
    Layer1.Thickness = 0.5f;
    Layer1.RValue = 0.5f;
    Layer1.Color = FLinearColor(0.8f, 0.8f, 0.85f);
    WallType.Layers.Add(Layer1);

    // OSB Sheathing
    FArchWallLayer Layer2;
    Layer2.Name = TEXT("OSB Sheathing");
    Layer2.Material = TEXT("osb");
    Layer2.Function = ELayerFunction::Sheathing;
    Layer2.Thickness = 1.9f;
    Layer2.RValue = 0.5f;
    Layer2.Color = FLinearColor(0.7f, 0.6f, 0.4f);
    WallType.Layers.Add(Layer2);

    // Stud + Insulation
    FArchWallLayer Layer3;
    Layer3.Name = TEXT("2x6 Stud + R-21 Batt");
    Layer3.Material = TEXT("fiberglass");
    Layer3.Function = ELayerFunction::Structure;
    Layer3.Thickness = 14.0f;
    Layer3.RValue = 21.0f;
    Layer3.Color = FLinearColor(1.0f, 0.9f, 0.7f);
    WallType.Layers.Add(Layer3);

    // Vapor Barrier (6 mil polyethylene)
    FArchWallLayer Layer4;
    Layer4.Name = TEXT("6 mil Vapor Barrier");
    Layer4.Material = TEXT("polyethylene");
    Layer4.Function = ELayerFunction::Membrane;
    Layer4.Thickness = 0.15f;  // ~6 mil = 0.15mm
    Layer4.RValue = 0.0f;
    Layer4.Color = FLinearColor(0.2f, 0.5f, 0.9f, 0.7f);  // Blue translucent
    WallType.Layers.Add(Layer4);

    // Drywall
    FArchWallLayer Layer5;
    Layer5.Name = TEXT("1/2\" Drywall");
    Layer5.Material = TEXT("gypsum");
    Layer5.Function = ELayerFunction::InteriorFinish;
    Layer5.Thickness = 1.3f;
    Layer5.RValue = 0.45f;
    Layer5.Color = FLinearColor(0.95f, 0.95f, 0.95f);
    WallType.Layers.Add(Layer5);

    return WallType;
}

FArchWallType UArchBuildingLoader::CreateDefaultInteriorWallType()
{
    FArchWallType WallType;
    WallType.Id = TEXT("int_2x4");
    WallType.Name = TEXT("2x4 Interior Partition");
    WallType.Intent.StructuralRole = TEXT("non_bearing");

    // Drywall (exterior side)
    FArchWallLayer Layer1;
    Layer1.Name = TEXT("1/2\" Drywall");
    Layer1.Material = TEXT("gypsum");
    Layer1.Function = ELayerFunction::InteriorFinish;
    Layer1.Thickness = 1.3f;
    Layer1.RValue = 0.45f;
    Layer1.Color = FLinearColor(0.95f, 0.95f, 0.95f);
    WallType.Layers.Add(Layer1);

    // Stud
    FArchWallLayer Layer2;
    Layer2.Name = TEXT("2x4 Stud");
    Layer2.Material = TEXT("wood");
    Layer2.Function = ELayerFunction::Structure;
    Layer2.Thickness = 8.9f;
    Layer2.RValue = 0.0f;
    Layer2.Color = FLinearColor(0.9f, 0.8f, 0.6f);
    WallType.Layers.Add(Layer2);

    // Drywall (interior side)
    FArchWallLayer Layer3;
    Layer3.Name = TEXT("1/2\" Drywall");
    Layer3.Material = TEXT("gypsum");
    Layer3.Function = ELayerFunction::InteriorFinish;
    Layer3.Thickness = 1.3f;
    Layer3.RValue = 0.45f;
    Layer3.Color = FLinearColor(0.95f, 0.95f, 0.95f);
    WallType.Layers.Add(Layer3);

    return WallType;
}

FArchWallType UArchBuildingLoader::CreateDefaultWetWallType()
{
    FArchWallType WallType;
    WallType.Id = TEXT("wet_2x6");
    WallType.Name = TEXT("2x6 Plumbing Wall");
    WallType.Intent.StructuralRole = TEXT("non_bearing");

    // Cement board (bathroom side)
    FArchWallLayer Layer1;
    Layer1.Name = TEXT("1/2\" Cement Board");
    Layer1.Material = TEXT("cement_board");
    Layer1.Function = ELayerFunction::InteriorFinish;
    Layer1.Thickness = 1.3f;
    Layer1.RValue = 0.2f;
    Layer1.Color = FLinearColor(0.75f, 0.75f, 0.8f);
    WallType.Layers.Add(Layer1);

    // Waterproof membrane (RedGard or similar)
    FArchWallLayer Layer2;
    Layer2.Name = TEXT("Waterproof Membrane");
    Layer2.Material = TEXT("waterproof_membrane");
    Layer2.Function = ELayerFunction::Membrane;
    Layer2.Thickness = 0.3f;  // Applied coating ~0.3mm
    Layer2.RValue = 0.0f;
    Layer2.Color = FLinearColor(0.8f, 0.2f, 0.3f, 0.8f);  // Red (like RedGard)
    WallType.Layers.Add(Layer2);

    // Stud (plumbing chase)
    FArchWallLayer Layer3;
    Layer3.Name = TEXT("2x6 Stud (Plumbing Chase)");
    Layer3.Material = TEXT("wood");
    Layer3.Function = ELayerFunction::Structure;
    Layer3.Thickness = 14.0f;
    Layer3.RValue = 0.0f;
    Layer3.Color = FLinearColor(0.9f, 0.8f, 0.6f);
    WallType.Layers.Add(Layer3);

    // Moisture resistant drywall (opposite side)
    FArchWallLayer Layer4;
    Layer4.Name = TEXT("1/2\" Moisture Resistant Drywall");
    Layer4.Material = TEXT("gypsum");
    Layer4.Function = ELayerFunction::InteriorFinish;
    Layer4.Thickness = 1.3f;
    Layer4.RValue = 0.45f;
    Layer4.Color = FLinearColor(0.9f, 0.95f, 0.9f);
    WallType.Layers.Add(Layer4);

    return WallType;
}

// ============================================================================
// QBD V2.0 NEW TYPE PARSERS
// ============================================================================

bool UArchBuildingLoader::ParseQBDLevel(const TSharedPtr<FJsonObject>& JsonObject, FArchLevel& OutLevel)
{
    if (!JsonObject.IsValid()) return false;

    OutLevel.Id = JsonObject->GetStringField(TEXT("id"));
    OutLevel.Name = JsonObject->GetStringField(TEXT("name"));
    OutLevel.Elevation = JsonObject->GetNumberField(TEXT("elevation"));
    OutLevel.FloorToFloorHeight = JsonObject->GetNumberField(TEXT("floor_to_floor_height"));

    return true;
}

bool UArchBuildingLoader::ParseQBDRoom(const FString& RoomId, const TSharedPtr<FJsonObject>& JsonObject, FArchRoom& OutRoom)
{
    if (!JsonObject.IsValid()) return false;

    OutRoom.Id = RoomId;
    OutRoom.Name = JsonObject->GetStringField(TEXT("name"));
    OutRoom.Level = JsonObject->GetStringField(TEXT("level"));
    OutRoom.Area = JsonObject->GetNumberField(TEXT("area"));
    OutRoom.RoomType = JsonObject->GetStringField(TEXT("room_type"));
    OutRoom.Zone = StringToRoomZone(JsonObject->GetStringField(TEXT("zone")));

    // Parse bounds
    const TSharedPtr<FJsonObject>* BoundsObj;
    if (JsonObject->TryGetObjectField(TEXT("bounds"), BoundsObj))
    {
        OutRoom.Bounds.X = (*BoundsObj)->GetNumberField(TEXT("x"));
        OutRoom.Bounds.Y = (*BoundsObj)->GetNumberField(TEXT("y"));
        OutRoom.Bounds.Width = (*BoundsObj)->GetNumberField(TEXT("width"));
        OutRoom.Bounds.Height = (*BoundsObj)->GetNumberField(TEXT("height"));
    }

    // Parse center
    const TSharedPtr<FJsonObject>* CenterObj;
    if (JsonObject->TryGetObjectField(TEXT("center"), CenterObj))
    {
        OutRoom.Center.X = (*CenterObj)->GetNumberField(TEXT("x"));
        OutRoom.Center.Y = (*CenterObj)->GetNumberField(TEXT("y"));
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDDimension(const TSharedPtr<FJsonObject>& JsonObject, FArchDimension& OutDimension)
{
    if (!JsonObject.IsValid()) return false;

    OutDimension.Id = JsonObject->GetStringField(TEXT("id"));
    OutDimension.Type = StringToDimensionType(JsonObject->GetStringField(TEXT("type")));
    OutDimension.Value = JsonObject->GetNumberField(TEXT("value"));
    OutDimension.Unit = JsonObject->GetStringField(TEXT("unit"));
    OutDimension.Label = JsonObject->GetStringField(TEXT("label"));
    OutDimension.Level = JsonObject->GetStringField(TEXT("level"));

    // Parse point arrays
    const TArray<TSharedPtr<FJsonValue>>* PointArray;
    if (JsonObject->TryGetArrayField(TEXT("start_point"), PointArray) && PointArray->Num() >= 3)
    {
        OutDimension.StartPoint = FVector(
            (*PointArray)[0]->AsNumber(),
            (*PointArray)[1]->AsNumber(),
            (*PointArray)[2]->AsNumber()
        );
    }
    if (JsonObject->TryGetArrayField(TEXT("end_point"), PointArray) && PointArray->Num() >= 3)
    {
        OutDimension.EndPoint = FVector(
            (*PointArray)[0]->AsNumber(),
            (*PointArray)[1]->AsNumber(),
            (*PointArray)[2]->AsNumber()
        );
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDRoof(const TSharedPtr<FJsonObject>& JsonObject, FArchRoof& OutRoof)
{
    if (!JsonObject.IsValid()) return false;

    // Convert mm to cm (same as walls)
    const float MmToCm = 0.1f;

    OutRoof.Id = JsonObject->GetStringField(TEXT("id"));
    OutRoof.Type = StringToRoofType(JsonObject->GetStringField(TEXT("type")));
    OutRoof.Pitch = JsonObject->GetNumberField(TEXT("pitch"));
    OutRoof.Overhang = JsonObject->GetNumberField(TEXT("overhang")) * MmToCm;
    OutRoof.Material = JsonObject->GetStringField(TEXT("material"));
    OutRoof.LevelName = JsonObject->GetStringField(TEXT("level_name"));

    // Parse ridges
    const TArray<TSharedPtr<FJsonValue>>* RidgesArray;
    if (JsonObject->TryGetArrayField(TEXT("ridges"), RidgesArray))
    {
        for (const auto& RidgeValue : *RidgesArray)
        {
            const TSharedPtr<FJsonObject>& RidgeObj = RidgeValue->AsObject();
            FArchRoofRidge Ridge;
            Ridge.Id = RidgeObj->GetStringField(TEXT("id"));
            Ridge.Height = RidgeObj->GetNumberField(TEXT("height")) * MmToCm;

            const TArray<TSharedPtr<FJsonValue>>* PointArray;
            if (RidgeObj->TryGetArrayField(TEXT("start_point"), PointArray) && PointArray->Num() >= 3)
            {
                Ridge.StartPoint = FVector(
                    (*PointArray)[0]->AsNumber() * MmToCm,
                    (*PointArray)[1]->AsNumber() * MmToCm,
                    (*PointArray)[2]->AsNumber() * MmToCm
                );
            }
            if (RidgeObj->TryGetArrayField(TEXT("end_point"), PointArray) && PointArray->Num() >= 3)
            {
                Ridge.EndPoint = FVector(
                    (*PointArray)[0]->AsNumber() * MmToCm,
                    (*PointArray)[1]->AsNumber() * MmToCm,
                    (*PointArray)[2]->AsNumber() * MmToCm
                );
            }

            OutRoof.Ridges.Add(Ridge);
        }
    }

    // Parse surfaces
    const TArray<TSharedPtr<FJsonValue>>* SurfacesArray;
    if (JsonObject->TryGetArrayField(TEXT("surfaces"), SurfacesArray))
    {
        for (const auto& SurfaceValue : *SurfacesArray)
        {
            const TSharedPtr<FJsonObject>& SurfaceObj = SurfaceValue->AsObject();
            FArchRoofSurface Surface;
            Surface.Id = SurfaceObj->GetStringField(TEXT("id"));
            Surface.Pitch = SurfaceObj->GetNumberField(TEXT("pitch"));
            Surface.Orientation = SurfaceObj->GetStringField(TEXT("orientation"));

            const TArray<TSharedPtr<FJsonValue>>* VerticesArray;
            if (SurfaceObj->TryGetArrayField(TEXT("vertices"), VerticesArray))
            {
                for (const auto& VertValue : *VerticesArray)
                {
                    const TArray<TSharedPtr<FJsonValue>>& VertArr = VertValue->AsArray();
                    if (VertArr.Num() >= 3)
                    {
                        // Convert mm to cm (same as walls)
                        Surface.Vertices.Add(FVector(
                            VertArr[0]->AsNumber() * MmToCm,
                            VertArr[1]->AsNumber() * MmToCm,
                            VertArr[2]->AsNumber() * MmToCm
                        ));
                    }
                }
            }

            OutRoof.Surfaces.Add(Surface);
        }
    }

    // Parse dormers
    const TArray<TSharedPtr<FJsonValue>>* DormersArray;
    if (JsonObject->TryGetArrayField(TEXT("dormers"), DormersArray))
    {
        for (const auto& DormerValue : *DormersArray)
        {
            FArchDormer Dormer;
            if (ParseQBDDormer(DormerValue->AsObject(), Dormer))
            {
                OutRoof.Dormers.Add(Dormer);
            }
        }
    }

    // Parse skylights
    const TArray<TSharedPtr<FJsonValue>>* SkylightsArray;
    if (JsonObject->TryGetArrayField(TEXT("skylights"), SkylightsArray))
    {
        for (const auto& SkylightValue : *SkylightsArray)
        {
            FArchSkylight Skylight;
            if (ParseQBDSkylight(SkylightValue->AsObject(), Skylight))
            {
                OutRoof.Skylights.Add(Skylight);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDDormer(const TSharedPtr<FJsonObject>& JsonObject, FArchDormer& OutDormer)
{
    if (!JsonObject.IsValid()) return false;

    // Convert mm to cm (same as walls)
    const float MmToCm = 0.1f;

    OutDormer.Id = JsonObject->GetStringField(TEXT("id"));
    OutDormer.Type = JsonObject->GetStringField(TEXT("type"));
    OutDormer.Width = JsonObject->GetNumberField(TEXT("width")) * MmToCm;
    OutDormer.Height = JsonObject->GetNumberField(TEXT("height")) * MmToCm;
    OutDormer.Depth = JsonObject->GetNumberField(TEXT("depth")) * MmToCm;
    OutDormer.RoofSurfaceId = JsonObject->GetStringField(TEXT("roof_surface_id"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
    {
        OutDormer.Position = FVector(
            (*PosArray)[0]->AsNumber() * MmToCm,
            (*PosArray)[1]->AsNumber() * MmToCm,
            (*PosArray)[2]->AsNumber() * MmToCm
        );
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDSkylight(const TSharedPtr<FJsonObject>& JsonObject, FArchSkylight& OutSkylight)
{
    if (!JsonObject.IsValid()) return false;

    // Convert mm to cm (same as walls)
    const float MmToCm = 0.1f;

    OutSkylight.Id = JsonObject->GetStringField(TEXT("id"));
    OutSkylight.Type = JsonObject->GetStringField(TEXT("type"));
    OutSkylight.Width = JsonObject->GetNumberField(TEXT("width")) * MmToCm;
    OutSkylight.Height = JsonObject->GetNumberField(TEXT("height")) * MmToCm;
    OutSkylight.RoofSurfaceId = JsonObject->GetStringField(TEXT("roof_surface_id"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
    {
        OutSkylight.Position = FVector(
            (*PosArray)[0]->AsNumber() * MmToCm,
            (*PosArray)[1]->AsNumber() * MmToCm,
            (*PosArray)[2]->AsNumber() * MmToCm
        );
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDStair(const TSharedPtr<FJsonObject>& JsonObject, FArchStair& OutStair)
{
    if (!JsonObject.IsValid()) return false;

    OutStair.Id = JsonObject->GetStringField(TEXT("id"));
    OutStair.Type = StringToStairType(JsonObject->GetStringField(TEXT("type")));
    OutStair.FromLevel = JsonObject->GetStringField(TEXT("from_level"));
    OutStair.ToLevel = JsonObject->GetStringField(TEXT("to_level"));
    OutStair.Direction = JsonObject->GetNumberField(TEXT("direction"));
    OutStair.Width = JsonObject->GetNumberField(TEXT("width"));
    OutStair.TotalRise = JsonObject->GetNumberField(TEXT("total_rise"));
    OutStair.TreadDepth = JsonObject->GetNumberField(TEXT("tread_depth"));
    OutStair.RiserHeight = JsonObject->GetNumberField(TEXT("riser_height"));
    OutStair.NumTreads = JsonObject->GetIntegerField(TEXT("num_treads"));
    OutStair.StringerMaterial = JsonObject->GetStringField(TEXT("stringer_material"));
    OutStair.TreadMaterial = JsonObject->GetStringField(TEXT("tread_material"));

    const TArray<TSharedPtr<FJsonValue>>* StartArray;
    if (JsonObject->TryGetArrayField(TEXT("start_point"), StartArray) && StartArray->Num() >= 3)
    {
        OutStair.StartPoint = FVector((*StartArray)[0]->AsNumber(), (*StartArray)[1]->AsNumber(), (*StartArray)[2]->AsNumber());
    }

    // Parse treads
    const TArray<TSharedPtr<FJsonValue>>* TreadsArray;
    if (JsonObject->TryGetArrayField(TEXT("treads"), TreadsArray))
    {
        for (const auto& TreadValue : *TreadsArray)
        {
            const TSharedPtr<FJsonObject>& TreadObj = TreadValue->AsObject();
            FArchStairTread Tread;
            Tread.Index = TreadObj->GetIntegerField(TEXT("index"));
            Tread.Width = TreadObj->GetNumberField(TEXT("width"));
            Tread.Depth = TreadObj->GetNumberField(TEXT("depth"));
            Tread.Thickness = TreadObj->GetNumberField(TEXT("thickness"));
            Tread.Nosing = TreadObj->GetNumberField(TEXT("nosing"));
            Tread.Rotation = TreadObj->GetNumberField(TEXT("rotation"));

            const TArray<TSharedPtr<FJsonValue>>* PosArray;
            if (TreadObj->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
            {
                Tread.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
            }

            OutStair.Treads.Add(Tread);
        }
    }

    // Parse risers
    const TArray<TSharedPtr<FJsonValue>>* RisersArray;
    if (JsonObject->TryGetArrayField(TEXT("risers"), RisersArray))
    {
        for (const auto& RiserValue : *RisersArray)
        {
            const TSharedPtr<FJsonObject>& RiserObj = RiserValue->AsObject();
            FArchStairRiser Riser;
            Riser.Index = RiserObj->GetIntegerField(TEXT("index"));
            Riser.Width = RiserObj->GetNumberField(TEXT("width"));
            Riser.Height = RiserObj->GetNumberField(TEXT("height"));
            Riser.Thickness = RiserObj->GetNumberField(TEXT("thickness"));

            const TArray<TSharedPtr<FJsonValue>>* PosArray;
            if (RiserObj->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
            {
                Riser.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
            }

            OutStair.Risers.Add(Riser);
        }
    }

    // Parse landings
    const TArray<TSharedPtr<FJsonValue>>* LandingsArray;
    if (JsonObject->TryGetArrayField(TEXT("landings"), LandingsArray))
    {
        for (const auto& LandingValue : *LandingsArray)
        {
            const TSharedPtr<FJsonObject>& LandingObj = LandingValue->AsObject();
            FArchLanding Landing;
            Landing.Id = LandingObj->GetStringField(TEXT("id"));
            Landing.Width = LandingObj->GetNumberField(TEXT("width"));
            Landing.Depth = LandingObj->GetNumberField(TEXT("depth"));
            Landing.Thickness = LandingObj->GetNumberField(TEXT("thickness"));
            Landing.Elevation = LandingObj->GetNumberField(TEXT("elevation"));

            const TArray<TSharedPtr<FJsonValue>>* PosArray;
            if (LandingObj->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
            {
                Landing.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
            }

            OutStair.Landings.Add(Landing);
        }
    }

    // Parse guardrails
    const TArray<TSharedPtr<FJsonValue>>* GuardrailsArray;
    if (JsonObject->TryGetArrayField(TEXT("guardrails"), GuardrailsArray))
    {
        for (const auto& GuardrailValue : *GuardrailsArray)
        {
            FArchGuardrail Guardrail;
            if (ParseQBDGuardrail(GuardrailValue->AsObject(), Guardrail))
            {
                OutStair.Guardrails.Add(Guardrail);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDGuardrail(const TSharedPtr<FJsonObject>& JsonObject, FArchGuardrail& OutGuardrail)
{
    if (!JsonObject.IsValid()) return false;

    OutGuardrail.Id = JsonObject->GetStringField(TEXT("id"));
    OutGuardrail.Height = JsonObject->GetNumberField(TEXT("height"));
    OutGuardrail.Side = JsonObject->GetStringField(TEXT("side"));

    const TArray<TSharedPtr<FJsonValue>>* StartArray;
    if (JsonObject->TryGetArrayField(TEXT("start_point"), StartArray) && StartArray->Num() >= 3)
    {
        OutGuardrail.StartPoint = FVector((*StartArray)[0]->AsNumber(), (*StartArray)[1]->AsNumber(), (*StartArray)[2]->AsNumber());
    }
    const TArray<TSharedPtr<FJsonValue>>* EndArray;
    if (JsonObject->TryGetArrayField(TEXT("end_point"), EndArray) && EndArray->Num() >= 3)
    {
        OutGuardrail.EndPoint = FVector((*EndArray)[0]->AsNumber(), (*EndArray)[1]->AsNumber(), (*EndArray)[2]->AsNumber());
    }

    // Parse handrail
    const TSharedPtr<FJsonObject>* HandrailObj;
    if (JsonObject->TryGetObjectField(TEXT("handrail"), HandrailObj))
    {
        OutGuardrail.Handrail.Profile = (*HandrailObj)->GetStringField(TEXT("profile"));
        OutGuardrail.Handrail.Diameter = (*HandrailObj)->GetNumberField(TEXT("diameter"));
        OutGuardrail.Handrail.Height = (*HandrailObj)->GetNumberField(TEXT("height"));
        OutGuardrail.Handrail.Material = (*HandrailObj)->GetStringField(TEXT("material"));
    }

    // Parse baluster
    const TSharedPtr<FJsonObject>* BalusterObj;
    if (JsonObject->TryGetObjectField(TEXT("baluster"), BalusterObj))
    {
        OutGuardrail.Baluster.Style = (*BalusterObj)->GetStringField(TEXT("style"));
        OutGuardrail.Baluster.Width = (*BalusterObj)->GetNumberField(TEXT("width"));
        OutGuardrail.Baluster.Depth = (*BalusterObj)->GetNumberField(TEXT("depth"));
        OutGuardrail.Baluster.Spacing = (*BalusterObj)->GetNumberField(TEXT("spacing"));
        OutGuardrail.Baluster.Material = (*BalusterObj)->GetStringField(TEXT("material"));
    }

    // Parse newel posts
    const TArray<TSharedPtr<FJsonValue>>* NewelsArray;
    if (JsonObject->TryGetArrayField(TEXT("newel_posts"), NewelsArray))
    {
        for (const auto& NewelValue : *NewelsArray)
        {
            const TSharedPtr<FJsonObject>& NewelObj = NewelValue->AsObject();
            FArchNewelPost Newel;
            Newel.Width = NewelObj->GetNumberField(TEXT("width"));
            Newel.Depth = NewelObj->GetNumberField(TEXT("depth"));
            Newel.Height = NewelObj->GetNumberField(TEXT("height"));
            Newel.Style = NewelObj->GetStringField(TEXT("style"));
            Newel.Material = NewelObj->GetStringField(TEXT("material"));

            const TArray<TSharedPtr<FJsonValue>>* PosArray;
            if (NewelObj->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
            {
                Newel.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
            }

            OutGuardrail.NewelPosts.Add(Newel);
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDElevator(const TSharedPtr<FJsonObject>& JsonObject, FArchElevator& OutElevator)
{
    if (!JsonObject.IsValid()) return false;

    OutElevator.Id = JsonObject->GetStringField(TEXT("id"));
    OutElevator.Type = StringToElevatorType(JsonObject->GetStringField(TEXT("type")));
    OutElevator.ShaftWidth = JsonObject->GetNumberField(TEXT("shaft_width"));
    OutElevator.ShaftDepth = JsonObject->GetNumberField(TEXT("shaft_depth"));
    OutElevator.CabWidth = JsonObject->GetNumberField(TEXT("cab_width"));
    OutElevator.CabDepth = JsonObject->GetNumberField(TEXT("cab_depth"));
    OutElevator.CabHeight = JsonObject->GetNumberField(TEXT("cab_height"));
    OutElevator.Capacity = JsonObject->GetIntegerField(TEXT("capacity"));
    OutElevator.DoorWidth = JsonObject->GetNumberField(TEXT("door_width"));
    OutElevator.DoorSide = JsonObject->GetStringField(TEXT("door_side"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("shaft_position"), PosArray) && PosArray->Num() >= 3)
    {
        OutElevator.ShaftPosition = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
    }

    const TArray<TSharedPtr<FJsonValue>>* LevelsArray;
    if (JsonObject->TryGetArrayField(TEXT("served_levels"), LevelsArray))
    {
        for (const auto& LevelValue : *LevelsArray)
        {
            OutElevator.ServedLevels.Add(LevelValue->AsString());
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDMEP(const TSharedPtr<FJsonObject>& JsonObject, FArchMEP& OutMEP)
{
    if (!JsonObject.IsValid()) return false;

    // Parse plumbing fixtures
    const TArray<TSharedPtr<FJsonValue>>* PlumbingArray;
    if (JsonObject->TryGetArrayField(TEXT("plumbing_fixtures"), PlumbingArray))
    {
        for (const auto& FixtureValue : *PlumbingArray)
        {
            FArchPlumbingFixture Fixture;
            if (ParseQBDPlumbingFixture(FixtureValue->AsObject(), Fixture))
            {
                OutMEP.PlumbingFixtures.Add(Fixture);
            }
        }
    }

    // Parse electrical fixtures
    const TArray<TSharedPtr<FJsonValue>>* ElectricalArray;
    if (JsonObject->TryGetArrayField(TEXT("electrical_fixtures"), ElectricalArray))
    {
        for (const auto& FixtureValue : *ElectricalArray)
        {
            FArchElectricalFixture Fixture;
            if (ParseQBDElectricalFixture(FixtureValue->AsObject(), Fixture))
            {
                OutMEP.ElectricalFixtures.Add(Fixture);
            }
        }
    }

    // Parse HVAC fixtures
    const TArray<TSharedPtr<FJsonValue>>* HVACArray;
    if (JsonObject->TryGetArrayField(TEXT("hvac_fixtures"), HVACArray))
    {
        for (const auto& FixtureValue : *HVACArray)
        {
            FArchHVACFixture Fixture;
            if (ParseQBDHVACFixture(FixtureValue->AsObject(), Fixture))
            {
                OutMEP.HVACFixtures.Add(Fixture);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDPlumbingFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchPlumbingFixture& OutFixture)
{
    if (!JsonObject.IsValid()) return false;

    OutFixture.Id = JsonObject->GetStringField(TEXT("id"));
    OutFixture.Type = JsonObject->GetStringField(TEXT("type"));
    OutFixture.Rotation = JsonObject->GetNumberField(TEXT("rotation"));
    OutFixture.Room = JsonObject->GetStringField(TEXT("room"));
    OutFixture.LevelName = JsonObject->GetStringField(TEXT("level_name"));
    OutFixture.WallId = JsonObject->GetStringField(TEXT("wall_id"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
    {
        OutFixture.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
    }

    // Parse rough-ins
    const TArray<TSharedPtr<FJsonValue>>* RoughInsArray;
    if (JsonObject->TryGetArrayField(TEXT("rough_ins"), RoughInsArray))
    {
        for (const auto& RoughInValue : *RoughInsArray)
        {
            const TSharedPtr<FJsonObject>& RoughInObj = RoughInValue->AsObject();
            FArchRoughIn RoughIn;
            RoughIn.ConnectionType = RoughInObj->GetStringField(TEXT("connection_type"));
            RoughIn.Size = RoughInObj->GetNumberField(TEXT("size"));

            const TArray<TSharedPtr<FJsonValue>>* OffsetArray;
            if (RoughInObj->TryGetArrayField(TEXT("offset"), OffsetArray) && OffsetArray->Num() >= 3)
            {
                RoughIn.Offset = FVector((*OffsetArray)[0]->AsNumber(), (*OffsetArray)[1]->AsNumber(), (*OffsetArray)[2]->AsNumber());
            }

            OutFixture.RoughIns.Add(RoughIn);
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDElectricalFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchElectricalFixture& OutFixture)
{
    if (!JsonObject.IsValid()) return false;

    OutFixture.Id = JsonObject->GetStringField(TEXT("id"));
    OutFixture.Type = JsonObject->GetStringField(TEXT("type"));
    OutFixture.Rotation = JsonObject->GetNumberField(TEXT("rotation"));
    OutFixture.Room = JsonObject->GetStringField(TEXT("room"));
    OutFixture.LevelName = JsonObject->GetStringField(TEXT("level_name"));
    OutFixture.MountHeight = JsonObject->GetNumberField(TEXT("mount_height"));
    OutFixture.Circuit = JsonObject->GetIntegerField(TEXT("circuit"));
    OutFixture.Amperage = JsonObject->GetIntegerField(TEXT("amperage"));
    OutFixture.WallId = JsonObject->GetStringField(TEXT("wall_id"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
    {
        OutFixture.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDHVACFixture(const TSharedPtr<FJsonObject>& JsonObject, FArchHVACFixture& OutFixture)
{
    if (!JsonObject.IsValid()) return false;

    OutFixture.Id = JsonObject->GetStringField(TEXT("id"));
    OutFixture.Type = JsonObject->GetStringField(TEXT("type"));
    OutFixture.Rotation = JsonObject->GetNumberField(TEXT("rotation"));
    OutFixture.Room = JsonObject->GetStringField(TEXT("room"));
    OutFixture.LevelName = JsonObject->GetStringField(TEXT("level_name"));
    OutFixture.Width = JsonObject->GetNumberField(TEXT("width"));
    OutFixture.Height = JsonObject->GetNumberField(TEXT("height"));
    OutFixture.CFM = JsonObject->GetIntegerField(TEXT("cfm"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 3)
    {
        OutFixture.Position = FVector((*PosArray)[0]->AsNumber(), (*PosArray)[1]->AsNumber(), (*PosArray)[2]->AsNumber());
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDMaterials(const TSharedPtr<FJsonObject>& JsonObject, FArchMaterials& OutMaterials)
{
    if (!JsonObject.IsValid()) return false;

    // Parse wall assemblies
    const TArray<TSharedPtr<FJsonValue>>* WallAssembliesArray;
    if (JsonObject->TryGetArrayField(TEXT("wall_assemblies"), WallAssembliesArray))
    {
        for (const auto& AssemblyValue : *WallAssembliesArray)
        {
            FArchAssembly Assembly;
            if (ParseQBDAssembly(AssemblyValue->AsObject(), Assembly))
            {
                OutMaterials.WallAssemblies.Add(Assembly);
            }
        }
    }

    // Parse floor assemblies
    const TArray<TSharedPtr<FJsonValue>>* FloorAssembliesArray;
    if (JsonObject->TryGetArrayField(TEXT("floor_assemblies"), FloorAssembliesArray))
    {
        for (const auto& AssemblyValue : *FloorAssembliesArray)
        {
            FArchAssembly Assembly;
            if (ParseQBDAssembly(AssemblyValue->AsObject(), Assembly))
            {
                OutMaterials.FloorAssemblies.Add(Assembly);
            }
        }
    }

    // Parse roof assemblies
    const TArray<TSharedPtr<FJsonValue>>* RoofAssembliesArray;
    if (JsonObject->TryGetArrayField(TEXT("roof_assemblies"), RoofAssembliesArray))
    {
        for (const auto& AssemblyValue : *RoofAssembliesArray)
        {
            FArchAssembly Assembly;
            if (ParseQBDAssembly(AssemblyValue->AsObject(), Assembly))
            {
                OutMaterials.RoofAssemblies.Add(Assembly);
            }
        }
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDAssembly(const TSharedPtr<FJsonObject>& JsonObject, FArchAssembly& OutAssembly)
{
    if (!JsonObject.IsValid()) return false;

    OutAssembly.Id = JsonObject->GetStringField(TEXT("id"));
    OutAssembly.Name = JsonObject->GetStringField(TEXT("name"));
    OutAssembly.AssemblyType = JsonObject->GetStringField(TEXT("assembly_type"));
    OutAssembly.TotalRValue = JsonObject->GetNumberField(TEXT("total_r_value"));
    OutAssembly.TotalCostPerSqFt = JsonObject->GetNumberField(TEXT("total_cost_per_sqft"));
    OutAssembly.FireRating = JsonObject->GetStringField(TEXT("fire_rating"));
    OutAssembly.CodeReference = JsonObject->GetStringField(TEXT("code_reference"));

    // Parse layers
    const TArray<TSharedPtr<FJsonValue>>* LayersArray;
    if (JsonObject->TryGetArrayField(TEXT("layers"), LayersArray))
    {
        for (const auto& LayerValue : *LayersArray)
        {
            const TSharedPtr<FJsonObject>& LayerObj = LayerValue->AsObject();
            FArchMaterialLayer Layer;
            Layer.Name = LayerObj->GetStringField(TEXT("name"));
            Layer.Material = LayerObj->GetStringField(TEXT("material"));
            Layer.Thickness = LayerObj->GetNumberField(TEXT("thickness"));
            Layer.RValue = LayerObj->GetNumberField(TEXT("r_value"));
            Layer.CostPerSqFt = LayerObj->GetNumberField(TEXT("cost_per_sqft"));
            Layer.FireRating = LayerObj->GetStringField(TEXT("fire_rating"));

            const TArray<TSharedPtr<FJsonValue>>* ColorArray;
            if (LayerObj->TryGetArrayField(TEXT("visualization_color"), ColorArray) && ColorArray->Num() >= 3)
            {
                Layer.VisualizationColor = FLinearColor(
                    (*ColorArray)[0]->AsNumber(),
                    (*ColorArray)[1]->AsNumber(),
                    (*ColorArray)[2]->AsNumber(),
                    1.0f
                );
            }

            OutAssembly.Layers.Add(Layer);
        }
    }

    return true;
}

// ============================================================================
// NEW ENUM CONVERTERS
// ============================================================================

EArchRoofType UArchBuildingLoader::StringToRoofType(const FString& Str)
{
    if (Str == TEXT("gable")) return EArchRoofType::Gable;
    if (Str == TEXT("hip")) return EArchRoofType::Hip;
    if (Str == TEXT("flat")) return EArchRoofType::Flat;
    if (Str == TEXT("shed")) return EArchRoofType::Shed;
    if (Str == TEXT("mansard")) return EArchRoofType::Mansard;
    if (Str == TEXT("gambrel")) return EArchRoofType::Gambrel;
    return EArchRoofType::Gable;
}

EArchStairType UArchBuildingLoader::StringToStairType(const FString& Str)
{
    if (Str == TEXT("straight")) return EArchStairType::Straight;
    if (Str == TEXT("l_shaped")) return EArchStairType::LShaped;
    if (Str == TEXT("u_shaped")) return EArchStairType::UShaped;
    if (Str == TEXT("winder")) return EArchStairType::Winder;
    if (Str == TEXT("spiral")) return EArchStairType::Spiral;
    return EArchStairType::Straight;
}

EArchRoomZone UArchBuildingLoader::StringToRoomZone(const FString& Str)
{
    if (Str == TEXT("public")) return EArchRoomZone::Public;
    if (Str == TEXT("private")) return EArchRoomZone::Private;
    if (Str == TEXT("service")) return EArchRoomZone::Service;
    if (Str == TEXT("circulation")) return EArchRoomZone::Circulation;
    return EArchRoomZone::Public;
}

EArchDimensionType UArchBuildingLoader::StringToDimensionType(const FString& Str)
{
    if (Str == TEXT("linear")) return EArchDimensionType::Linear;
    if (Str == TEXT("angular")) return EArchDimensionType::Angular;
    if (Str == TEXT("radial")) return EArchDimensionType::Radial;
    return EArchDimensionType::Linear;
}

EArchElevatorType UArchBuildingLoader::StringToElevatorType(const FString& Str)
{
    if (Str == TEXT("passenger")) return EArchElevatorType::Passenger;
    if (Str == TEXT("freight")) return EArchElevatorType::Freight;
    if (Str == TEXT("residential")) return EArchElevatorType::Residential;
    if (Str == TEXT("dumbwaiter")) return EArchElevatorType::Dumbwaiter;
    return EArchElevatorType::Passenger;
}

EArchPlanType UArchBuildingLoader::StringToPlanType(const FString& Str)
{
    if (Str == TEXT("floor_plan")) return EArchPlanType::FloorPlan;
    if (Str == TEXT("roof_plan")) return EArchPlanType::RoofPlan;
    if (Str == TEXT("reflected_ceiling_plan")) return EArchPlanType::ReflectedCeilingPlan;
    if (Str == TEXT("site_plan")) return EArchPlanType::SitePlan;
    if (Str == TEXT("foundation_plan")) return EArchPlanType::FoundationPlan;
    if (Str == TEXT("framing_plan")) return EArchPlanType::FramingPlan;
    if (Str == TEXT("electrical_plan")) return EArchPlanType::ElectricalPlan;
    if (Str == TEXT("plumbing_plan")) return EArchPlanType::PlumbingPlan;
    if (Str == TEXT("mechanical_plan")) return EArchPlanType::MechanicalPlan;
    if (Str == TEXT("elevation")) return EArchPlanType::Elevation;
    if (Str == TEXT("section")) return EArchPlanType::Section;
    if (Str == TEXT("detail")) return EArchPlanType::Detail;
    return EArchPlanType::FloorPlan;
}

EArchSymbolType UArchBuildingLoader::StringToSymbolType(const FString& Str)
{
    if (Str == TEXT("north_arrow")) return EArchSymbolType::NorthArrow;
    if (Str == TEXT("section_marker")) return EArchSymbolType::SectionMarker;
    if (Str == TEXT("detail_marker")) return EArchSymbolType::DetailMarker;
    if (Str == TEXT("elevation_marker")) return EArchSymbolType::ElevationMarker;
    if (Str == TEXT("door_tag")) return EArchSymbolType::DoorTag;
    if (Str == TEXT("window_tag")) return EArchSymbolType::WindowTag;
    if (Str == TEXT("room_tag")) return EArchSymbolType::RoomTag;
    if (Str == TEXT("column_grid")) return EArchSymbolType::ColumnGrid;
    if (Str == TEXT("level_marker")) return EArchSymbolType::LevelMarker;
    if (Str == TEXT("break_line")) return EArchSymbolType::BreakLine;
    if (Str == TEXT("center_line")) return EArchSymbolType::CenterLine;
    if (Str == TEXT("match_line")) return EArchSymbolType::MatchLine;
    if (Str == TEXT("revision_cloud")) return EArchSymbolType::RevisionCloud;
    return EArchSymbolType::SectionMarker;
}

EArchRoofAnnotationType UArchBuildingLoader::StringToRoofAnnotationType(const FString& Str)
{
    if (Str == TEXT("pitch_indicator")) return EArchRoofAnnotationType::PitchIndicator;
    if (Str == TEXT("drainage_arrow")) return EArchRoofAnnotationType::DrainageArrow;
    if (Str == TEXT("ridge_line")) return EArchRoofAnnotationType::RidgeLine;
    if (Str == TEXT("valley_line")) return EArchRoofAnnotationType::ValleyLine;
    if (Str == TEXT("hip_line")) return EArchRoofAnnotationType::HipLine;
    if (Str == TEXT("eave_line")) return EArchRoofAnnotationType::EaveLine;
    if (Str == TEXT("rake_line")) return EArchRoofAnnotationType::RakeLine;
    if (Str == TEXT("cricket_arrow")) return EArchRoofAnnotationType::CricketArrow;
    if (Str == TEXT("roof_drain")) return EArchRoofAnnotationType::RoofDrain;
    if (Str == TEXT("scupper")) return EArchRoofAnnotationType::Scupper;
    if (Str == TEXT("overflow")) return EArchRoofAnnotationType::Overflow;
    if (Str == TEXT("slope_arrow")) return EArchRoofAnnotationType::SlopeArrow;
    return EArchRoofAnnotationType::PitchIndicator;
}

// ============================================================================
// ANNOTATION PARSERS
// ============================================================================

bool UArchBuildingLoader::ParseQBDTextLabel(const TSharedPtr<FJsonObject>& JsonObject, FArchTextLabel& OutLabel)
{
    if (!JsonObject.IsValid()) return false;

    OutLabel.Id = JsonObject->GetStringField(TEXT("id"));
    OutLabel.Text = JsonObject->GetStringField(TEXT("text"));

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 2)
    {
        OutLabel.Position = FVector(
            (*PosArray)[0]->AsNumber(),
            (*PosArray)[1]->AsNumber(),
            PosArray->Num() > 2 ? (*PosArray)[2]->AsNumber() : 0.0f
        );
    }

    JsonObject->TryGetNumberField(TEXT("rotation"), OutLabel.Rotation);
    JsonObject->TryGetNumberField(TEXT("text_height"), OutLabel.TextHeight);
    JsonObject->TryGetStringField(TEXT("font_style"), OutLabel.FontStyle);
    JsonObject->TryGetStringField(TEXT("justification"), OutLabel.Justification);
    JsonObject->TryGetStringField(TEXT("level"), OutLabel.Level);
    JsonObject->TryGetBoolField(TEXT("show_border"), OutLabel.bShowBorder);
    JsonObject->TryGetBoolField(TEXT("show_background"), OutLabel.bShowBackground);

    return true;
}

bool UArchBuildingLoader::ParseQBDLeader(const TSharedPtr<FJsonObject>& JsonObject, FArchLeader& OutLeader)
{
    if (!JsonObject.IsValid()) return false;

    OutLeader.Id = JsonObject->GetStringField(TEXT("id"));
    OutLeader.Text = JsonObject->GetStringField(TEXT("text"));

    const TArray<TSharedPtr<FJsonValue>>* ArrowArray;
    if (JsonObject->TryGetArrayField(TEXT("arrow_point"), ArrowArray) && ArrowArray->Num() >= 2)
    {
        OutLeader.ArrowPoint = FVector(
            (*ArrowArray)[0]->AsNumber(),
            (*ArrowArray)[1]->AsNumber(),
            ArrowArray->Num() > 2 ? (*ArrowArray)[2]->AsNumber() : 0.0f
        );
    }

    const TArray<TSharedPtr<FJsonValue>>* TextArray;
    if (JsonObject->TryGetArrayField(TEXT("text_position"), TextArray) && TextArray->Num() >= 2)
    {
        OutLeader.TextPosition = FVector(
            (*TextArray)[0]->AsNumber(),
            (*TextArray)[1]->AsNumber(),
            TextArray->Num() > 2 ? (*TextArray)[2]->AsNumber() : 0.0f
        );
    }

    const TArray<TSharedPtr<FJsonValue>>* BendsArray;
    if (JsonObject->TryGetArrayField(TEXT("bend_points"), BendsArray))
    {
        for (const auto& BendVal : *BendsArray)
        {
            const TArray<TSharedPtr<FJsonValue>>* BendCoords = &BendVal->AsArray();
            if (BendCoords && BendCoords->Num() >= 2)
            {
                OutLeader.BendPoints.Add(FVector(
                    (*BendCoords)[0]->AsNumber(),
                    (*BendCoords)[1]->AsNumber(),
                    BendCoords->Num() > 2 ? (*BendCoords)[2]->AsNumber() : 0.0f
                ));
            }
        }
    }

    JsonObject->TryGetNumberField(TEXT("text_height"), OutLeader.TextHeight);
    JsonObject->TryGetStringField(TEXT("arrow_style"), OutLeader.ArrowStyle);
    JsonObject->TryGetStringField(TEXT("level"), OutLeader.Level);

    return true;
}

bool UArchBuildingLoader::ParseQBDSymbol(const TSharedPtr<FJsonObject>& JsonObject, FArchSymbol& OutSymbol)
{
    if (!JsonObject.IsValid()) return false;

    OutSymbol.Id = JsonObject->GetStringField(TEXT("id"));

    FString TypeStr;
    if (JsonObject->TryGetStringField(TEXT("type"), TypeStr))
    {
        OutSymbol.Type = StringToSymbolType(TypeStr);
    }

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 2)
    {
        OutSymbol.Position = FVector(
            (*PosArray)[0]->AsNumber(),
            (*PosArray)[1]->AsNumber(),
            PosArray->Num() > 2 ? (*PosArray)[2]->AsNumber() : 0.0f
        );
    }

    JsonObject->TryGetNumberField(TEXT("rotation"), OutSymbol.Rotation);
    JsonObject->TryGetNumberField(TEXT("scale"), OutSymbol.Scale);
    JsonObject->TryGetStringField(TEXT("label"), OutSymbol.Label);
    JsonObject->TryGetStringField(TEXT("sheet_reference"), OutSymbol.SheetReference);
    JsonObject->TryGetStringField(TEXT("level"), OutSymbol.Level);

    const TArray<TSharedPtr<FJsonValue>>* DirArray;
    if (JsonObject->TryGetArrayField(TEXT("direction"), DirArray) && DirArray->Num() >= 2)
    {
        OutSymbol.Direction = FVector(
            (*DirArray)[0]->AsNumber(),
            (*DirArray)[1]->AsNumber(),
            DirArray->Num() > 2 ? (*DirArray)[2]->AsNumber() : 0.0f
        );
    }

    return true;
}

bool UArchBuildingLoader::ParseQBDRoofAnnotation(const TSharedPtr<FJsonObject>& JsonObject, FArchRoofAnnotation& OutAnnotation)
{
    if (!JsonObject.IsValid()) return false;

    OutAnnotation.Id = JsonObject->GetStringField(TEXT("id"));

    FString TypeStr;
    if (JsonObject->TryGetStringField(TEXT("type"), TypeStr))
    {
        OutAnnotation.Type = StringToRoofAnnotationType(TypeStr);
    }

    const TArray<TSharedPtr<FJsonValue>>* PosArray;
    if (JsonObject->TryGetArrayField(TEXT("position"), PosArray) && PosArray->Num() >= 2)
    {
        OutAnnotation.Position = FVector(
            (*PosArray)[0]->AsNumber(),
            (*PosArray)[1]->AsNumber(),
            PosArray->Num() > 2 ? (*PosArray)[2]->AsNumber() : 0.0f
        );
    }

    const TArray<TSharedPtr<FJsonValue>>* EndArray;
    if (JsonObject->TryGetArrayField(TEXT("end_position"), EndArray) && EndArray->Num() >= 2)
    {
        OutAnnotation.EndPosition = FVector(
            (*EndArray)[0]->AsNumber(),
            (*EndArray)[1]->AsNumber(),
            EndArray->Num() > 2 ? (*EndArray)[2]->AsNumber() : 0.0f
        );
    }

    JsonObject->TryGetNumberField(TEXT("rotation"), OutAnnotation.Rotation);
    JsonObject->TryGetNumberField(TEXT("pitch"), OutAnnotation.Pitch);
    JsonObject->TryGetNumberField(TEXT("slope_percent"), OutAnnotation.SlopePercent);
    JsonObject->TryGetStringField(TEXT("label"), OutAnnotation.Label);
    JsonObject->TryGetStringField(TEXT("roof_surface_id"), OutAnnotation.RoofSurfaceId);

    return true;
}

bool UArchBuildingLoader::ParseQBDGridLine(const TSharedPtr<FJsonObject>& JsonObject, FArchGridLine& OutGridLine)
{
    if (!JsonObject.IsValid()) return false;

    OutGridLine.Id = JsonObject->GetStringField(TEXT("id"));
    OutGridLine.Label = JsonObject->GetStringField(TEXT("label"));

    const TArray<TSharedPtr<FJsonValue>>* StartArray;
    if (JsonObject->TryGetArrayField(TEXT("start_point"), StartArray) && StartArray->Num() >= 2)
    {
        OutGridLine.StartPoint = FVector(
            (*StartArray)[0]->AsNumber(),
            (*StartArray)[1]->AsNumber(),
            StartArray->Num() > 2 ? (*StartArray)[2]->AsNumber() : 0.0f
        );
    }

    const TArray<TSharedPtr<FJsonValue>>* EndArray;
    if (JsonObject->TryGetArrayField(TEXT("end_point"), EndArray) && EndArray->Num() >= 2)
    {
        OutGridLine.EndPoint = FVector(
            (*EndArray)[0]->AsNumber(),
            (*EndArray)[1]->AsNumber(),
            EndArray->Num() > 2 ? (*EndArray)[2]->AsNumber() : 0.0f
        );
    }

    JsonObject->TryGetBoolField(TEXT("is_primary"), OutGridLine.bIsPrimary);
    JsonObject->TryGetBoolField(TEXT("show_bubble"), OutGridLine.bShowBubble);

    return true;
}

bool UArchBuildingLoader::ParseQBDAnnotationSet(const TSharedPtr<FJsonObject>& JsonObject, FArchAnnotationSet& OutSet)
{
    if (!JsonObject.IsValid()) return false;

    OutSet.Id = JsonObject->GetStringField(TEXT("id"));
    OutSet.Name = JsonObject->GetStringField(TEXT("name"));

    FString PlanTypeStr;
    if (JsonObject->TryGetStringField(TEXT("plan_type"), PlanTypeStr))
    {
        OutSet.PlanType = StringToPlanType(PlanTypeStr);
    }

    JsonObject->TryGetStringField(TEXT("level"), OutSet.Level);
    JsonObject->TryGetNumberField(TEXT("scale"), OutSet.Scale);

    // Parse dimensions
    const TArray<TSharedPtr<FJsonValue>>* DimsArray;
    if (JsonObject->TryGetArrayField(TEXT("dimensions"), DimsArray))
    {
        for (const auto& DimVal : *DimsArray)
        {
            FArchDimension Dim;
            if (ParseQBDDimension(DimVal->AsObject(), Dim))
            {
                OutSet.Dimensions.Add(Dim);
            }
        }
    }

    // Parse labels
    const TArray<TSharedPtr<FJsonValue>>* LabelsArray;
    if (JsonObject->TryGetArrayField(TEXT("labels"), LabelsArray))
    {
        for (const auto& LabelVal : *LabelsArray)
        {
            FArchTextLabel Label;
            if (ParseQBDTextLabel(LabelVal->AsObject(), Label))
            {
                OutSet.Labels.Add(Label);
            }
        }
    }

    // Parse leaders
    const TArray<TSharedPtr<FJsonValue>>* LeadersArray;
    if (JsonObject->TryGetArrayField(TEXT("leaders"), LeadersArray))
    {
        for (const auto& LeaderVal : *LeadersArray)
        {
            FArchLeader Leader;
            if (ParseQBDLeader(LeaderVal->AsObject(), Leader))
            {
                OutSet.Leaders.Add(Leader);
            }
        }
    }

    // Parse symbols
    const TArray<TSharedPtr<FJsonValue>>* SymbolsArray;
    if (JsonObject->TryGetArrayField(TEXT("symbols"), SymbolsArray))
    {
        for (const auto& SymbolVal : *SymbolsArray)
        {
            FArchSymbol Symbol;
            if (ParseQBDSymbol(SymbolVal->AsObject(), Symbol))
            {
                OutSet.Symbols.Add(Symbol);
            }
        }
    }

    // Parse roof annotations
    const TArray<TSharedPtr<FJsonValue>>* RoofAnnoArray;
    if (JsonObject->TryGetArrayField(TEXT("roof_annotations"), RoofAnnoArray))
    {
        for (const auto& AnnoVal : *RoofAnnoArray)
        {
            FArchRoofAnnotation Anno;
            if (ParseQBDRoofAnnotation(AnnoVal->AsObject(), Anno))
            {
                OutSet.RoofAnnotations.Add(Anno);
            }
        }
    }

    // Parse grid lines
    const TArray<TSharedPtr<FJsonValue>>* GridArray;
    if (JsonObject->TryGetArrayField(TEXT("grid_lines"), GridArray))
    {
        for (const auto& GridVal : *GridArray)
        {
            FArchGridLine Grid;
            if (ParseQBDGridLine(GridVal->AsObject(), Grid))
            {
                OutSet.GridLines.Add(Grid);
            }
        }
    }

    // Viewport settings
    const TArray<TSharedPtr<FJsonValue>>* CenterArray;
    if (JsonObject->TryGetArrayField(TEXT("viewport_center"), CenterArray) && CenterArray->Num() >= 2)
    {
        OutSet.ViewportCenter = FVector(
            (*CenterArray)[0]->AsNumber(),
            (*CenterArray)[1]->AsNumber(),
            CenterArray->Num() > 2 ? (*CenterArray)[2]->AsNumber() : 0.0f
        );
    }

    JsonObject->TryGetNumberField(TEXT("viewport_width"), OutSet.ViewportWidth);
    JsonObject->TryGetNumberField(TEXT("viewport_height"), OutSet.ViewportHeight);

    return true;
}
