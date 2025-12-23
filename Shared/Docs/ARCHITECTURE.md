# ArchEngine Suite - System Architecture

## Overview

ArchEngine is an architectural visualization and building design system consisting of three main components that work together to enable real-time building design, validation, and 3D visualization.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ArchEngine Suite                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐    JSON     ┌──────────────────┐    WebSocket         │
│  │  ArchEngine      │◄──────────►│  2D Plan Editor  │◄────────────┐        │
│  │  Kernel (C++)    │  (file)    │  (Python/Tk)     │             │        │
│  └────────┬─────────┘            └──────────────────┘             │        │
│           │                                                        │        │
│           │ Vulkan                                                 │        │
│           ▼                                                        ▼        │
│  ┌──────────────────┐            ┌──────────────────────────────────┐       │
│  │  Native Viewer   │            │  UE5 Viewer (ArchEngine_Viewer)  │       │
│  │  (Vulkan/ImGui)  │            │  - AArchBuildingActor            │       │
│  └──────────────────┘            │  - UArchBuildingLoader           │       │
│                                  │  - UArchLiveSyncComponent        │       │
│                                  └──────────────────────────────────┘       │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  text_to_json.py │─────► JSON ────────────────────────────────►          │
│  │  (NLP Generator) │       (generated_building.json)                       │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. ArchEngine Kernel (C++)

**Location:** `ArchEngine_kernel/src/`

The kernel is a native C++ application that provides the core computational engine for building analysis, validation, and visualization.

### Source Files

| File | Purpose |
|------|---------|
| `main.cpp` | Application entry point, QBD testing, ray picking |
| `vulkan_context.cpp` | Vulkan graphics initialization and management |
| `renderer.cpp` | 3D rendering pipeline |
| `window.cpp` | GLFW window management |
| `mesh.cpp` | Mesh data structures and manipulation |
| `csg.cpp` | Constructive Solid Geometry operations |
| `pipeline.cpp` | Vulkan shader pipeline configuration |
| `memory.cpp` | Vulkan memory allocation |
| `imgui_layer.cpp` | Dear ImGui integration for UI |
| `geometry_loader.cpp` | Load geometry from files |
| `qbd_interface.cpp` | QBD JSON parsing and validation |
| `obc_engine.cpp` | Ontario Building Code validation engine |
| `slicer_2d.cpp` | 2D plan/section generation |
| `physics_bridge.cpp` | Physics simulation bridge |

### Dependencies

- **Vulkan** - Graphics API
- **GLFW** - Window/input management
- **GLM** - Math library
- **Dear ImGui** - Immediate mode GUI
- **nlohmann/json** - JSON parsing

### Key Features

- Real-time 3D visualization with Vulkan
- Building code validation (OBC - Ontario Building Code)
- Structural element picking and selection
- QBD (Quick Building Data) format support

---

## 2. Python Scripts (Kernel Tools)

**Location:** `ArchEngine_kernel/scripts/`

### text_to_json.py - Natural Language Building Generator

Converts plain text descriptions into structured building JSON.

```python
# Usage
result = text_to_json("3 bedroom 2 bath house 1800 sqft")
```

**Features:**
- Parses room counts, square footage, style keywords
- Auto-generates floor plan layout with room placement
- Creates walls, doors, windows based on room adjacency
- Generates roof geometry (gable, hip, flat, shed)
- Outputs wall type assemblies with layer definitions

**Room Types Supported:**
- Living, Kitchen, Dining, Bedroom, Bathroom
- Master Bedroom/Bath, Office, Laundry
- Garage, Mudroom, Pantry, Closet
- Hallway, Foyer, Great Room, Family Room

### plan_editor_2d.py - Interactive Floor Plan Editor

A Tkinter-based 2D editor with real-time sync to UE5.

**Features:**
- Visual wall editing (move, extend, trim)
- Joint/corner detection and snapping
- Door and window placement
- Room labeling and bounds editing
- WebSocket server for live sync to UE5

**Edit Modes:**
- SELECT - Pick and inspect elements
- MOVE_WALL - Translate entire walls
- MOVE_ENDPOINT - Adjust wall endpoints
- TRIM_EXTEND - Modify wall lengths
- ADD_WALL/DOOR/WINDOW - Create new elements

### Other Scripts

| Script | Purpose |
|--------|---------|
| `generate_plans.py` | Generate SVG/DXF floor plans |
| `ifc_import.py` | Import IFC (Industry Foundation Classes) files |
| `physics_bridge.py` | Python physics simulation interface |
| `text_to_json_gui.py` | GUI wrapper for text_to_json |

---

## 3. UE5 Viewer (ArchEngine_Viewer)

**Location:** `ArchEngine_Viewer/ArchEngine/Source/ArchEngine/`

An Unreal Engine 5 plugin for high-fidelity architectural visualization.

### Core Classes

#### AArchBuildingActor (`Actors/ArchBuildingActor.h/.cpp`)

The main actor that represents a complete building in the UE5 scene.

**Properties:**
```cpp
FArchBuilding BuildingData;           // Complete building data
EVisualizationMode VisualizationMode; // Structural, Thermal, etc.
ESectionViewMode SectionViewMode;     // Solid, SectionCut, Exploded
float ScaleFactor;                    // Coordinate scale (default 1.0)
FString JsonFilePath;                 // Path to building JSON
bool bWatchFileForChanges;            // Hot-reload on file change
```

**Key Methods:**
- `LoadFromFile()` - Load building from JSON
- `RebuildMeshes()` - Regenerate all procedural geometry
- `SetSectionViewMode()` - Switch between view modes
- `GenerateWallMesh()` - Create wall geometry with openings
- `GenerateRoofMesh()` - Create roof surfaces with fascia
- `GenerateStairMesh()` - Create stairs with treads/risers

**Mesh Generation:**
- Uses `UProceduralMeshComponent` for runtime geometry
- Supports walls, doors, windows, roofs, stairs, elevators
- Handles door/window cutouts in walls
- Section view shows individual wall layers

#### UArchBuildingLoader (`Loaders/ArchBuildingLoader.h/.cpp`)

Static utility class for JSON parsing.

**Capabilities:**
- Parses QBD format JSON (from text_to_json.py)
- Parses standard ArchEngine format
- Converts mm coordinates to cm (UE units)
- Creates wall type assemblies from layer definitions

**Key Parse Functions:**
```cpp
ParseQBDBuilding()    // Main building parser
ParseQBDWall()        // Wall geometry + type
ParseQBDWallType()    // Wall assembly with layers
ParseQBDRoof()        // Roof surfaces and ridges
ParseQBDDoor/Window() // Openings
ParseQBDStair()       // Stair geometry
```

#### UArchLiveSyncComponent (`Components/ArchLiveSyncComponent.h/.cpp`)

WebSocket client for real-time sync with 2D editor.

**Properties:**
```cpp
FString ServerUrl = "ws://localhost:8765";
bool bAutoConnect = true;
bool bAutoReconnect = true;
float ReconnectInterval = 2.0f;
```

**Events:**
- `OnBuildingDataReceived` - Fires when JSON received from editor

### Data Types (`Types/ArchTypes.h`)

Comprehensive type definitions for building elements:

```
FArchBuilding
├── TArray<FArchElement>         // Structural elements (beams, columns, walls)
├── TArray<FArchWallType>        // Wall assembly definitions
│   └── TArray<FArchWallLayer>   // Individual layers with thickness/material
├── TArray<FArchParametricWall>  // Wall instances
├── TArray<FArchDoor>            // Door openings
├── TArray<FArchWindow>          // Window openings
├── TArray<FArchRoof>            // Roof structures
│   ├── TArray<FArchRoofSurface> // Roof face polygons
│   ├── TArray<FArchRoofRidge>   // Ridge lines
│   ├── TArray<FArchDormer>      // Dormers
│   └── TArray<FArchSkylight>    // Skylights
├── TArray<FArchStair>           // Stairs with treads/risers
├── TArray<FArchElevator>        // Elevator shafts
├── TArray<FArchLevel>           // Floor levels
├── TMap<FString, FArchRoom>     // Room definitions
├── FArchMEP                     // MEP fixtures
│   ├── Plumbing (toilets, sinks, etc.)
│   ├── Electrical (outlets, panels)
│   └── HVAC (registers, thermostats)
└── TArray<FArchAnnotationSet>   // Drawing annotations
```

---

## 4. Shared Data (JSON Schema)

**Location:** `Shared/`

### Directory Structure

```
Shared/
├── Schemas/
│   ├── building.schema.json      # Full building schema
│   ├── assembly.schema.json      # Wall assembly schema
│   ├── qbd_output.schema.json    # QBD format schema
│   └── samples/
│       └── exterior_wall_2x6.json
├── TestData/
│   ├── output/
│   │   ├── generated_building.json  # Current building data
│   │   ├── floor_plan.svg           # Generated floor plan
│   │   ├── roof_plan_generated.svg  # Generated roof plan
│   │   └── validation_report.txt    # OBC validation results
│   └── sample_qbd_output.json
└── Docs/
    └── ARCHITECTURE.md           # This document
```

### JSON Format (QBD Output)

```json
{
  "building_id": "abc123",
  "width": 14482.0,           // mm
  "depth": 16895.0,           // mm
  "sqft": 1800,
  "unit": "mm",

  "walls_batch": [
    {
      "start": [0, 0, 0],
      "end": [14482, 0, 0],
      "height": 2700,
      "wall_type": "ext_2x6_r21",
      "category": "exterior",
      "rooms": ["exterior", "living"]
    }
  ],

  "wall_types": [
    {
      "id": "ext_2x6_r21",
      "name": "Exterior 2x6 R-21",
      "layers": [
        {"name": "Siding", "thickness": 6, "function": "exterior_finish"},
        {"name": "OSB Sheathing", "thickness": 11, "function": "sheathing"},
        {"name": "2x6 Stud + R-21", "thickness": 140, "function": "structure"},
        {"name": "Drywall", "thickness": 13, "function": "interior_finish"}
      ]
    }
  ],

  "doors": [...],
  "windows": [...],
  "rooms": {...},
  "roofs": [...],
  "levels": [...]
}
```

---

## 5. Coordinate Systems

### Kernel Coordinates (mm)
```
     Y (up/height)
     │
     │
     └────── X (width)
    /
   Z (depth)
```

### Unreal Coordinates (cm)
```
     Z (up/height)
     │
     │
     └────── X (forward)
    /
   Y (right)
```

### Conversion
```cpp
FVector KernelToUnreal(const FVector& K) const {
    return FVector(K.Z, K.X, K.Y) * ScaleFactor;
}
```

- Kernel X (width) → Unreal Y
- Kernel Y (height) → Unreal Z
- Kernel Z (depth) → Unreal X
- mm → cm: multiply by 0.1 (done in loader)
- ScaleFactor: typically 1.0 (data already in cm after loader conversion)

---

## 6. Data Flow

### 1. Text Input to 3D Model

```
User Input: "3 bedroom 2 bath house 1800 sqft"
        │
        ▼
┌─────────────────────┐
│  text_to_json.py    │  Parse NLP, generate layout
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ generated_building  │  JSON file with all building data
│      .json          │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ UArchBuildingLoader │  Parse JSON, convert units
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ AArchBuildingActor  │  Generate procedural meshes
└─────────┬───────────┘
          │
          ▼
    3D Visualization
```

### 2. Live Editing Flow

```
┌─────────────────────┐
│  plan_editor_2d.py  │  User edits floor plan
└─────────┬───────────┘
          │ WebSocket (port 8765)
          ▼
┌─────────────────────┐
│ UArchLiveSyncComponent │  Receives JSON updates
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ AArchBuildingActor  │  RebuildMeshes()
└─────────────────────┘
```

### 3. File Watch Flow

```
┌─────────────────────┐
│ External Editor     │  Modify JSON file
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ AArchBuildingActor  │  Tick() detects file change
│  (bWatchFileForChanges)
└─────────┬───────────┘
          │
          ▼
     ReloadFromFile()
```

---

## 7. Section View System

The section view allows visualization of wall construction layers.

### View Modes

1. **Solid** - Normal 3D view, single-color walls
2. **SectionCut** - Show layers at a cutting plane
3. **Exploded** - Separate layers with gaps between them

### Layer Functions

| Function | Description | Default Color |
|----------|-------------|---------------|
| ExteriorFinish | Siding, stucco, brick | Light gray |
| Sheathing | OSB, plywood | Tan/brown |
| Insulation | Fiberglass, foam | Yellow/pink |
| Structure | Studs, framing | Wood color |
| AirGap | Ventilation space | Transparent |
| Membrane | Vapor barrier, house wrap | White |
| InteriorFinish | Drywall, plaster | Off-white |

---

## 8. Roof System

### Roof Types
- **Gable** - Two sloped surfaces meeting at ridge
- **Hip** - Four sloped surfaces, no vertical gable ends
- **Flat** - Single horizontal surface
- **Shed** - Single sloped surface
- **Mansard** - Four-sided with double slopes
- **Gambrel** - Barn-style with two slopes per side

### Roof Components
- **Surfaces** - Polygon faces defined by vertices
- **Ridges** - Peak lines with height data
- **Fascia** - Trim board at eave edges
- **Soffit** - Underside of overhang
- **Dormers** - Roof protrusions with windows
- **Skylights** - Roof window openings

### Geometry Generation
1. Parse surface vertices from JSON
2. Apply RoofLift to align soffit with wall tops
3. Generate top surface (fan triangulation)
4. Generate bottom surface (vertical offset for thickness)
5. Generate eave edge faces (horizontal edges only)
6. Add fascia boards at eave edges

---

## 9. Build & Run

### Kernel (CMake)
```bash
cd ArchEngine_kernel
mkdir build && cd build
cmake ..
cmake --build .
./ArchEngine
```

### UE5 Viewer
1. Open `ArchEngine_Viewer/ArchEngine/ArchEngine.uproject`
2. Build for Development Editor
3. Place `AArchBuildingActor` in level
4. Set `JsonFilePath` to building JSON
5. Play in editor

### Python Tools
```bash
cd ArchEngine_kernel/scripts

# Generate building from text
python text_to_json.py "3 bed 2 bath 1800 sqft"

# Launch 2D editor with live sync
python plan_editor_2d.py
```

---

## 10. Future Considerations

- **IFC Export** - Export to Industry Foundation Classes format
- **Structural Analysis** - Integrate with FEA solvers
- **Energy Modeling** - Thermal performance simulation
- **Cost Estimation** - Material takeoffs and pricing
- **VR Support** - Immersive walkthrough mode
- **Multi-story** - Enhanced vertical circulation
- **Terrain Integration** - Site grading and foundation
