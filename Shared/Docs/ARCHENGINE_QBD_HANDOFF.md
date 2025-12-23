# ArchEngine QBD Schema Handoff

**Version:** 3.0
**Last Updated:** 2025-12-20
**Schema:** `Shared/Schemas/qbd_output.schema.json`

This document is the **source of truth** for the QBD output format and the corresponding ArchEngine UE5 viewer implementation.

---

## Overview

The QBD (Question Based Design) system outputs structured building data including:
- **Walls** - Wall geometry with level association (required)
- **Doors** - Door placements with type and swing direction
- **Windows** - Window placements on walls
- **Rooms** - Room definitions with level association (required)
- **Levels** - Building floor/level definitions
- **Dimensions** - Dimension annotations for the layout
- **Building ID** - Unique identifier for each generated building
- **Unit** - Unit of measurement (mm for ArchEngine, feet for Revit)

---

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | boolean | Yes | Whether layout generation succeeded |
| `building_id` | string | No | UUID (8 chars) for the building |
| `width` | number | Yes | Building width |
| `depth` | number | Yes | Building depth |
| `sqft` | number | Yes | Total square footage |
| `output_format` | string | No | "archengine" or "revit" |
| `unit` | string | No | "mm" or "feet" - all dimensions use this unit |
| `walls_batch` | array | No | Wall definitions |
| `doors` | array | No | Door placements |
| `windows` | array | No | Window placements |
| `rooms` | object | No | Map of room_id to room data |
| `levels` | array | No | Level definitions |
| `dimensions` | array | No | Dimension annotations |
| `summary` | object | No | Count summary |

---

## Walls Array

Each wall object in `walls_batch`:

```json
{
  "start": [0, 0, 0],
  "end": [12000, 0, 0],
  "height": 2743.2,
  "wall_type": "exterior_2x6",
  "category": "exterior",
  "level_name": "Level 1",
  "rooms": ["living", "exterior"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | [x, y, z] | Yes | Start point in 3D space |
| `end` | [x, y, z] | Yes | End point in 3D space |
| `height` | number | Yes | Wall height |
| `wall_type` | string | Yes | Wall type identifier |
| `category` | string | Yes | "exterior", "interior", or "wet_wall" |
| `level_name` | string | **Yes** | Level name (REQUIRED) |
| `rooms` | [string, string] | No | Room IDs on each side |

---

## Doors Array

Each door object:

```json
{
  "wall_index": 2,
  "offset": 1524.0,
  "width": 914.4,
  "height": 2133.6,
  "type": "door",
  "swing": "left_in",
  "room1": "living",
  "room2": "hallway",
  "level_name": "Level 1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wall_index` | int | No | Index into walls_batch array |
| `x` | number | Yes | Door center X coordinate |
| `y` | number | Yes | Door center Y coordinate |
| `offset` | number | No | Distance along wall from start point |
| `width` | number | Yes | Door width |
| `height` | number | No | Door height |
| `type` | string | Yes | "door", "double_door", "pocket_door", "barn_door", "french_door", "sliding_door" |
| `swing` | string | No | "left_in", "left_out", "right_in", "right_out", "double", "sliding", "none" |
| `room1` | string | No | Room on one side |
| `room2` | string | No | Room on other side |
| `level_name` | string | No | Level name |

---

## Windows Array

Each window object:

```json
{
  "wall_index": 4,
  "offset": 1524.0,
  "width": 914.4,
  "height": 1219.2,
  "sill_height": 914.4,
  "type": "double_hung",
  "room": "living",
  "level_name": "Level 1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wall_index` | int | Yes | Index into walls_batch array |
| `offset` | number | Yes | Distance along wall from start point |
| `width` | number | Yes | Window width |
| `height` | number | Yes | Window height |
| `sill_height` | number | No | Height from floor to window sill |
| `type` | string | No | "fixed", "casement", "double_hung", "sliding", "awning" |
| `room` | string | No | Room ID this window belongs to |
| `level_name` | string | No | Level name |

---

## Rooms Object

Map of room_id to room data:

```json
{
  "living": {
    "name": "Living Room",
    "level": "Level 1",
    "bounds": {"x": 0, "y": 0, "width": 4572, "height": 3657.6},
    "area": 180,
    "center": {"x": 2286, "y": 1828.8},
    "room_type": "living",
    "zone": "public"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Room display name |
| `level` | string | **Yes** | Level this room is on (REQUIRED) |
| `bounds` | object | Yes | {x, y, width, height} bounding box |
| `area` | number | Yes | Room area in sqft |
| `center` | object | Yes | {x, y} center point |
| `room_type` | string | No | Room type (kitchen, bedroom, etc.) |
| `zone` | string | No | "public", "private", "service", "circulation" |

---

## Levels Array

Each level object:

```json
{
  "id": "level_1",
  "name": "Level 1",
  "elevation": 0,
  "floor_to_floor_height": 3048.0
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Level identifier |
| `name` | string | Yes | Display name |
| `elevation` | number | Yes | Elevation from ground |
| `floor_to_floor_height` | number | No | Height to next level |

---

## Dimensions Array

Each dimension object:

```json
{
  "id": "dim_0",
  "type": "linear",
  "start_point": [0, 0, 0],
  "end_point": [12496.8, 0, 0],
  "value": 12496.8,
  "unit": "mm",
  "label": "Overall Width",
  "level": "Level 1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | No | Dimension identifier |
| `type` | string | Yes | "linear", "angular", or "radial" |
| `start_point` | [x, y, z] | No | Start point in 3D space |
| `end_point` | [x, y, z] | No | End point in 3D space |
| `value` | number | Yes | Dimension value |
| `unit` | string | No | "mm" or "feet" (must match building unit) |
| `label` | string | No | Display label |
| `level` | string | No | Level this dimension belongs to |

---

## Summary Object

```json
{
  "total_walls": 8,
  "exterior_walls": 4,
  "interior_walls": 2,
  "wet_walls": 2,
  "doors": 3,
  "windows": 5,
  "rooms_placed": 8,
  "rooms_requested": 11
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_walls` | int | Total wall count |
| `exterior_walls` | int | Exterior wall count |
| `interior_walls` | int | Interior wall count |
| `wet_walls` | int | Wet wall count (plumbing) |
| `doors` | int | Door count |
| `windows` | int | Window count |
| `rooms_placed` | int | Rooms successfully placed |
| `rooms_requested` | int | Rooms originally requested |

---

## Complete Example

```json
{
  "success": true,
  "building_id": "e8f217e9",
  "width": 12496.8,
  "depth": 8839.2,
  "sqft": 1200,
  "output_format": "archengine",
  "unit": "mm",
  "walls_batch": [
    {
      "start": [0, 0, 0],
      "end": [12496.8, 0, 0],
      "height": 2743.2,
      "wall_type": "exterior_2x6",
      "category": "exterior",
      "level_name": "Level 1",
      "rooms": ["living", "exterior"]
    }
  ],
  "doors": [
    {
      "wall_index": 2,
      "x": 6096,
      "y": 0,
      "offset": 3048,
      "width": 914.4,
      "height": 2133.6,
      "type": "door",
      "swing": "left_in",
      "room1": "living",
      "room2": "hallway",
      "level_name": "Level 1"
    }
  ],
  "windows": [
    {
      "wall_index": 0,
      "offset": 2209.8,
      "width": 914.4,
      "height": 1219.2,
      "sill_height": 914.4,
      "type": "double_hung",
      "room": "living",
      "level_name": "Level 1"
    }
  ],
  "rooms": {
    "living": {
      "name": "Living Room",
      "level": "Level 1",
      "bounds": {"x": 0, "y": 0, "width": 4572, "height": 3657.6},
      "area": 180,
      "center": {"x": 2286, "y": 1828.8},
      "room_type": "living",
      "zone": "public"
    }
  },
  "levels": [
    {
      "id": "level_1",
      "name": "Level 1",
      "elevation": 0,
      "floor_to_floor_height": 3048.0
    },
    {
      "id": "roof_level",
      "name": "Roof Level",
      "elevation": 3048.0,
      "floor_to_floor_height": 0
    }
  ],
  "dimensions": [
    {
      "id": "dim_0",
      "type": "linear",
      "start_point": [0, 0, 0],
      "end_point": [12496.8, 0, 0],
      "value": 12496.8,
      "unit": "mm",
      "label": "Overall Width",
      "level": "Level 1"
    }
  ],
  "summary": {
    "total_walls": 8,
    "exterior_walls": 4,
    "interior_walls": 2,
    "wet_walls": 2,
    "doors": 3,
    "windows": 5,
    "rooms_placed": 8,
    "rooms_requested": 11
  }
}
```

---

## Required C++ Changes (ArchEngine Viewer)

### 1. ArchTypes.h - Add New Structs

```cpp
// Level struct
USTRUCT(BlueprintType)
struct FArchLevel
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Name;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Elevation;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float FloorToFloorHeight;
};

// Dimension struct
USTRUCT(BlueprintType)
struct FArchDimension
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Id;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Type;  // "linear", "angular", "radial"

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector StartPoint;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FVector EndPoint;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Value;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Unit;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Label;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FString Level;
};
```

### 2. ArchTypes.h - Update Existing Structs

**FArchWindow** - Add LevelName field:
```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite)
FString LevelName;
```

**FArchBuilding** - Add new fields:
```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite)
FString BuildingId;

UPROPERTY(EditAnywhere, BlueprintReadWrite)
FString Unit;  // "mm" or "feet"

UPROPERTY(EditAnywhere, BlueprintReadWrite)
TArray<FArchLevel> Levels;

UPROPERTY(EditAnywhere, BlueprintReadWrite)
TArray<FArchDimension> Dimensions;
```

### 3. ArchBuildingLoader - Add Parsers

```cpp
// In header - add declarations:
static bool ParseQBDLevel(const TSharedPtr<FJsonObject>& JsonObject, FArchLevel& OutLevel);
static bool ParseQBDDimension(const TSharedPtr<FJsonObject>& JsonObject, FArchDimension& OutDimension);

// In cpp - implement:
bool UArchBuildingLoader::ParseQBDLevel(const TSharedPtr<FJsonObject>& JsonObject, FArchLevel& OutLevel)
{
    if (!JsonObject.IsValid()) return false;
    OutLevel.Id = JsonObject->GetStringField(TEXT("id"));
    OutLevel.Name = JsonObject->GetStringField(TEXT("name"));
    OutLevel.Elevation = JsonObject->GetNumberField(TEXT("elevation"));
    OutLevel.FloorToFloorHeight = JsonObject->GetNumberField(TEXT("floor_to_floor_height"));
    return true;
}

bool UArchBuildingLoader::ParseQBDDimension(const TSharedPtr<FJsonObject>& JsonObject, FArchDimension& OutDimension)
{
    if (!JsonObject.IsValid()) return false;
    OutDimension.Id = JsonObject->GetStringField(TEXT("id"));
    OutDimension.Type = JsonObject->GetStringField(TEXT("type"));
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
```

---

## Roofs Array

Each roof object:

```json
{
  "id": "roof_1",
  "type": "gable",
  "pitch": 6,
  "overhang": 609.6,
  "material": "asphalt_shingle",
  "level_name": "Roof Level",
  "ridges": [
    {
      "id": "ridge_1",
      "start_point": [0, 3048, 6096],
      "end_point": [12496.8, 3048, 6096],
      "height": 3048
    }
  ],
  "surfaces": [
    {
      "id": "surface_1",
      "vertices": [[0, 0, 3048], [12496.8, 0, 3048], [12496.8, 3048, 6096], [0, 3048, 6096]],
      "pitch": 6,
      "orientation": "south"
    }
  ],
  "dormers": [],
  "skylights": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Roof identifier |
| `type` | string | Yes | "gable", "hip", "flat", "shed", "mansard", "gambrel" |
| `pitch` | number | No | Rise over 12" run (e.g., 6 for 6:12) |
| `overhang` | number | No | Eave overhang distance |
| `material` | string | No | "asphalt_shingle", "metal", "tile", "slate" |
| `level_name` | string | No | Level this roof sits on |
| `ridges` | array | No | Ridge line definitions |
| `surfaces` | array | No | Roof surface polygons |
| `dormers` | array | No | Dormer definitions |
| `skylights` | array | No | Skylight definitions |

### Dormer Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Dormer identifier |
| `type` | string | "gable", "shed", "hip" |
| `position` | [x, y, z] | Position on roof surface |
| `width` | number | Dormer width |
| `height` | number | Dormer height |
| `depth` | number | Dormer depth |
| `roof_surface_id` | string | Which roof surface this is on |

### Skylight Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Skylight identifier |
| `type` | string | "fixed", "venting", "tubular" |
| `position` | [x, y, z] | Position on roof surface |
| `width` | number | Skylight width |
| `height` | number | Skylight height |
| `roof_surface_id` | string | Which roof surface this is on |

---

## Stairs Array

Each stair object:

```json
{
  "id": "stair_1",
  "type": "straight",
  "from_level": "Level 1",
  "to_level": "Level 2",
  "start_point": [3048, 0, 0],
  "direction": 0,
  "width": 914.4,
  "total_rise": 2743.2,
  "tread_depth": 254,
  "riser_height": 177.8,
  "num_treads": 14,
  "stringer_material": "wood",
  "tread_material": "oak",
  "treads": [],
  "risers": [],
  "landings": [],
  "guardrails": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Stair identifier |
| `type` | string | Yes | "straight", "l_shaped", "u_shaped", "winder", "spiral" |
| `from_level` | string | Yes | Starting level |
| `to_level` | string | Yes | Ending level |
| `start_point` | [x, y, z] | No | Bottom of first riser |
| `direction` | number | No | Rotation in degrees |
| `width` | number | No | Stair width (36" min per code) |
| `total_rise` | number | No | Floor to floor height |
| `tread_depth` | number | No | Tread depth (10" min per code) |
| `riser_height` | number | No | Riser height (7" max per code) |
| `num_treads` | int | No | Number of treads |
| `guardrails` | array | No | Guardrail definitions |

### Guardrail Object

```json
{
  "id": "guardrail_1",
  "start_point": [3048, 0, 0],
  "end_point": [3048, 0, 2743.2],
  "height": 1066.8,
  "side": "right",
  "handrail": {
    "profile": "round",
    "diameter": 38.1,
    "height": 863.6,
    "material": "oak"
  },
  "baluster": {
    "style": "square",
    "width": 31.75,
    "depth": 31.75,
    "spacing": 101.6,
    "material": "oak"
  },
  "newel_posts": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Guardrail identifier |
| `start_point` | [x, y, z] | Start of guardrail run |
| `end_point` | [x, y, z] | End of guardrail run |
| `height` | number | 42" per code for guards |
| `side` | string | "left", "right", "both" |
| `handrail` | object | Handrail details (profile, diameter, height, material) |
| `baluster` | object | Baluster details (style, width, depth, spacing, material) |
| `newel_posts` | array | Newel post positions and details |

---

## Elevators Array

Each elevator object:

```json
{
  "id": "elevator_1",
  "type": "residential",
  "shaft_position": [1524, 0, 0],
  "shaft_width": 1828.8,
  "shaft_depth": 1828.8,
  "cab_width": 1524,
  "cab_depth": 1524,
  "cab_height": 2438.4,
  "served_levels": ["Level 1", "Level 2"],
  "capacity": 750,
  "door_width": 914.4,
  "door_side": "front"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Elevator identifier |
| `type` | string | Yes | "passenger", "freight", "residential", "dumbwaiter" |
| `shaft_position` | [x, y, z] | No | Shaft corner position |
| `shaft_width` | number | No | Shaft width |
| `shaft_depth` | number | No | Shaft depth |
| `cab_width` | number | No | Cab interior width |
| `cab_depth` | number | No | Cab interior depth |
| `cab_height` | number | No | Cab interior height |
| `served_levels` | array | No | Level names this elevator serves |
| `capacity` | int | No | Capacity in lbs |
| `door_width` | number | No | Door width |
| `door_side` | string | No | "front", "rear", "side", "through" |

---

## MEP Object

MEP (Mechanical, Electrical, Plumbing) fixture definitions:

```json
{
  "plumbing_fixtures": [...],
  "electrical_fixtures": [...],
  "hvac_fixtures": [...]
}
```

### Plumbing Fixture

```json
{
  "id": "toilet_1",
  "type": "toilet",
  "position": [1524, 304.8, 0],
  "rotation": 0,
  "room": "bathroom_1",
  "level_name": "Level 1",
  "wall_id": "wall_5",
  "rough_ins": [
    {"connection_type": "cold", "offset": [0, 152.4, 0], "size": 12.7},
    {"connection_type": "drain", "offset": [0, 0, 0], "size": 76.2}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Fixture identifier |
| `type` | string | Yes | "toilet", "sink", "shower", "tub", "water_heater", "washer", "dishwasher" |
| `position` | [x, y, z] | Yes | Fixture center position |
| `rotation` | number | No | Rotation in degrees |
| `room` | string | No | Room this fixture is in |
| `level_name` | string | No | Level name |
| `wall_id` | string | No | For wall-mounted fixtures |
| `rough_ins` | array | No | Rough-in connection points |

### Electrical Fixture

```json
{
  "id": "outlet_1",
  "type": "outlet",
  "position": [1524, 457.2, 0],
  "rotation": 0,
  "room": "living",
  "level_name": "Level 1",
  "mount_height": 457.2,
  "circuit": 1,
  "amperage": 15,
  "wall_id": "wall_2"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Fixture identifier |
| `type` | string | Yes | "outlet", "switch", "panel", "light", "smoke_detector", "thermostat", "gfci" |
| `position` | [x, y, z] | Yes | Fixture position |
| `mount_height` | number | No | Height from floor (0 = ceiling mount) |
| `circuit` | int | No | Circuit number |
| `amperage` | int | No | Circuit amperage |

### HVAC Fixture

```json
{
  "id": "supply_1",
  "type": "supply_register",
  "position": [3048, 2438.4, 0],
  "rotation": 0,
  "room": "living",
  "level_name": "Level 1",
  "width": 304.8,
  "height": 152.4,
  "cfm": 150
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Fixture identifier |
| `type` | string | Yes | "supply_register", "return_grille", "thermostat", "exhaust_fan", "range_hood" |
| `position` | [x, y, z] | Yes | Fixture position |
| `width` | number | No | Register/grille width |
| `height` | number | No | Register/grille height |
| `cfm` | int | No | Cubic feet per minute |

---

## Materials Object

Material assembly definitions for cost estimation and code compliance:

```json
{
  "wall_assemblies": [...],
  "floor_assemblies": [...],
  "roof_assemblies": [...]
}
```

### Assembly Object

```json
{
  "id": "ext_2x6_r21",
  "name": "2x6 Exterior Wall R-21",
  "assembly_type": "wall",
  "layers": [
    {
      "name": "Vinyl Siding",
      "material": "vinyl",
      "thickness": 12.7,
      "r_value": 0.5,
      "cost_per_sqft": 2.50,
      "fire_rating": "",
      "visualization_color": [0.8, 0.8, 0.85]
    }
  ],
  "total_r_value": 21.95,
  "total_cost_per_sqft": 12.50,
  "fire_rating": "1-hour",
  "code_reference": "IRC R302.1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Assembly identifier |
| `name` | string | Yes | Assembly display name |
| `assembly_type` | string | No | "wall", "floor", "roof", "ceiling" |
| `layers` | array | Yes | Layer definitions (exterior to interior) |
| `total_r_value` | number | No | Total assembly R-value |
| `total_cost_per_sqft` | number | No | Total cost per square foot |
| `fire_rating` | string | No | "1-hour", "2-hour", etc. |
| `code_reference` | string | No | IRC/IBC section reference |

### Material Layer Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Layer name |
| `material` | string | Yes | Material type |
| `thickness` | number | Yes | Thickness in mm |
| `r_value` | number | No | Layer R-value |
| `cost_per_sqft` | number | No | Cost per square foot |
| `fire_rating` | string | No | Fire rating |
| `visualization_color` | [r, g, b] | No | RGB values 0-1 for visualization |

---

## Validation Rules

1. **Units must be consistent** - All dimensions in the file use the same unit specified in `unit` field
2. **Level references must exist** - Any `level_name` or `level` field must reference a level defined in the `levels` array
3. **Wall indices must be valid** - `wall_index` in doors/windows must be valid index into `walls_batch`
4. **Required fields** - See tables above for required vs optional fields
5. **Stair code compliance** - Tread depth minimum 10", riser height maximum 7", guardrail height minimum 42"
6. **MEP fixture placement** - Fixtures referencing wall_id must have valid wall index

---

## Files Reference

| File | Purpose |
|------|---------|
| `Shared/Schemas/qbd_output.schema.json` | JSON Schema definition |
| `Shared/docs/ARCHENGINE_QBD_HANDOFF.md` | This document (source of truth) |
| `ArchEngine_Viewer/.../Types/ArchTypes.h` | C++ type definitions |
| `ArchEngine_Viewer/.../Loaders/ArchBuildingLoader.h` | Parser declarations |
| `ArchEngine_Viewer/.../Loaders/ArchBuildingLoader.cpp` | Parser implementations |

---

---

## Plan Generator Integration

The Python plan generator (`ArchEngine_kernel/scripts/generate_plans.py`) reads the QBD JSON and outputs annotated SVG floor plans.

### Required Fields for Plan Generation

| Field | Used For |
|-------|----------|
| `width`, `depth` | ViewBox sizing, overall dimensions |
| `walls_batch` | Wall geometry (exterior/interior/wet_wall) |
| `doors` | Door symbols with swing arcs |
| `windows` | Window symbols on walls |
| `rooms` | Room labels and area calculations |

### How to Use

```bash
# Generate floor plan from QBD output
python ArchEngine_kernel/scripts/generate_plans.py path/to/qbd_output.json

# Output saved to: Shared/TestData/output/floor_plan_generated.svg
```

### Integration Flow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  QBD Interview  │───▶│  Layout Logic   │───▶│  JSON Output    │
│  (questions)    │    │  (room sizing,  │    │  (qbd_output)   │
│                 │    │   placement)    │    │                 │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                       ┌─────────────────┐             │
                       │  Plan Generator │◀────────────┘
                       │  (SVG output)   │
                       └────────┬────────┘
                                │
                       ┌────────▼────────┐
                       │  Annotated SVG  │
                       │  - Door symbols │
                       │  - Dimensions   │
                       │  - Room labels  │
                       └─────────────────┘
```

### Python Layout Logic → JSON

The layout logic agent should output JSON matching this structure:

```python
# Example output from layout logic
output = {
    "success": True,
    "width": 12000,      # mm
    "depth": 9000,       # mm
    "unit": "mm",
    "walls_batch": [
        {
            "start": [0, 0, 0],
            "end": [12000, 0, 0],
            "height": 2700,
            "category": "exterior",
            "level_name": "Level 1"
        }
        # ... more walls
    ],
    "doors": [
        {
            "wall_index": 0,      # Index into walls_batch
            "offset": 2000,       # Distance along wall from start
            "width": 900,
            "height": 2100,
            "type": "door",
            "swing": "left_in"
        }
    ],
    "windows": [
        {
            "wall_index": 0,
            "offset": 8000,
            "width": 1800,
            "height": 1500,
            "sill_height": 900
        }
    ],
    "rooms": {
        "living": {
            "name": "Living Room",
            "level": "Level 1",
            "bounds": {"x": 0, "y": 0, "width": 6000, "height": 4500},
            "area": 27000000,  # mm² (or sqft if using feet)
            "center": {"x": 3000, "y": 2250}
        }
    }
}

# Save to JSON
import json
with open("Shared/TestData/sample_qbd_output.json", "w") as f:
    json.dump(output, f, indent=2)
```

### Calling Plan Generator from Python

```python
from pathlib import Path
import subprocess

# After saving JSON, generate plans
json_path = "Shared/TestData/sample_qbd_output.json"
subprocess.run(["python", "ArchEngine_kernel/scripts/generate_plans.py", json_path])

# Or import directly
from ArchEngine_kernel.scripts.generate_plans import PlanGenerator

generator = PlanGenerator(json_path)
svg_content = generator.generate_floor_plan_svg()
```

---

## Python Files for ArchEngine Integration

These files from `RevitMCP-roomlayout/server/` should be migrated to ArchEngine:

| File | Purpose |
|------|---------|
| `coordinate_solver.py` | Room placement algorithm with creative mode, dead space circulation |
| `qbd_layout_generator.py` | Converts layout to QBD JSON output (walls, doors, windows, rooms) |
| `qbd_interview.py` | Natural language conversation layer for design requirements |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-12-20 | 3.2 | Added Python files reference for ArchEngine integration |
| 2025-12-20 | 3.1 | Added Plan Generator integration section |
| 2025-12-20 | 3.0 | Added roofs (with dormers/skylights), stairs (with guardrails), elevators, MEP fixtures, materials assemblies |
| 2024-12-20 | 2.0 | Added room.level (required), wall.level_name (required), windows in summary, simplified dimension units |
| 2024-12-19 | 1.0 | Initial schema with windows, levels, dimensions |
