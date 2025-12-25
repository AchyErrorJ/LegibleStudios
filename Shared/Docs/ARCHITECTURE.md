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
| `ifc_import.py` | Import IFC (Industry Foundation Classes) files |
| `physics_bridge.py` | Python physics simulation interface |
| `text_to_json_gui.py` | GUI wrapper for text_to_json |

---

## 3. Drawing Generator Suite

**Location:** `ArchEngine_kernel/scripts/`

A comprehensive suite for generating construction-quality architectural drawings from building JSON data. Produces SVG drawings and professional PDF output with precise line weights.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Drawing Generator Pipeline                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │ generated_       │                                                   │
│  │ building.json    │                                                   │
│  └────────┬─────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                         │
│  │ schema_validator │────►│ Validation       │                         │
│  │      .py         │     │ Report           │                         │
│  └────────┬─────────┘     └──────────────────┘                         │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                         │
│  │ roof_generator   │────►│ Enriched JSON    │                         │
│  │ wall_types       │     │ (+ roofs, types) │                         │
│  └────────┬─────────┘     └──────────────────┘                         │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    generate_all.py (Master)                      │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │   │
│  │  │ generate_  │ │ generate_  │ │ generate_  │ │ generate_  │   │   │
│  │  │ plans.py   │ │ elevations │ │ sections   │ │ details    │   │   │
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘   │   │
│  │        │              │              │              │          │   │
│  │        ▼              ▼              ▼              ▼          │   │
│  │   floor_plan.svg elevation_*.svg section_*.svg details.svg    │   │
│  │   roof_plan.svg                                schedules.svg   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           ▼                                                             │
│  ┌──────────────────┐     ┌──────────────────┐                         │
│  │   pdf_export.py  │────►│ drawing_set.pdf  │  (ARCH D, vector)       │
│  └──────────────────┘     │ + individual PDFs│                         │
│                           └──────────────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Modules

#### generate_all.py - Master Generator

Unified pipeline that runs all generators and produces a complete drawing set.

```bash
# Basic usage
python generate_all.py building.json -o output/

# With PDF export
python generate_all.py building.json -o output/ --pdf --sheet-size arch_d

# Skip specific generators
python generate_all.py building.json -o output/ --skip details,schedules
```

**Features:**
- Validates input JSON against schema
- Enriches data with roof geometry and wall types
- Runs all drawing generators in sequence
- Generates HTML index page for viewing
- Optional PDF export with title blocks
- Progress logging with timing

#### Drawing Generators

| Script | Output | Description |
|--------|--------|-------------|
| `generate_plans.py` | `floor_plan.svg`, `roof_plan.svg` | Floor plan with walls, doors, windows, room labels; Roof plan with slopes and ridges |
| `generate_elevations.py` | `elevation_*.svg` (4 files) | South, North, East, West building elevations with roof profiles |
| `generate_sections.py` | `section_a.svg`, `section_b.svg` | Building cross-sections showing wall layers and interior |
| `generate_details.py` | `details.svg` | Construction details: wall section, eave, window/door jambs |
| `generate_schedules.py` | `schedules.svg` | Door schedule, window schedule, room finish schedule |

### Support Modules

#### wall_types.py - Wall Assembly Definitions

Defines 15+ standard wall assemblies with layer-by-layer specifications.

```python
from wall_types import get_wall_type, get_all_wall_types, WallCategory

# Get a specific wall type
ext_wall = get_wall_type('ext_2x6_r21')
print(ext_wall.total_thickness)  # 189mm
print(ext_wall.total_r_value)    # 21.5

# Get default for category
default = get_default_wall_type('exterior')
```

**Wall Categories:**
| Category | Example Types |
|----------|---------------|
| Exterior | 2x4 R-13, 2x6 R-21, Brick Veneer, Stucco |
| Interior | 2x4 Standard, 2x4 Soundproof |
| Wet Wall | 2x6 Plumbing Wall |
| Fire-Rated | 1-Hour, 2-Hour Assemblies |
| Garage | CMU, Insulated |
| Basement | ICF, Poured Concrete |

**Layer Properties:**
- `name` - Layer description
- `thickness` - mm
- `material` - wood_frame, fiberglass, gypsum, osb, etc.
- `function` - structure, insulation, sheathing, vapor_barrier, etc.
- `r_value` - Thermal resistance (optional)
- `fire_rating` - Minutes (optional)

#### roof_generator.py - Roof Geometry Generation

Generates roof geometry from building footprint.

```python
from roof_generator import generate_gable_roof, generate_hip_roof, add_roof_to_building

# Generate specific roof type
roof = generate_gable_roof(
    width=12000,      # mm
    depth=9000,       # mm
    wall_height=2700, # mm
    pitch=4.0,        # rise/run ratio
    overhang=600      # mm
)

# Auto-add roof based on building style
building_data = add_roof_to_building(building_json)
```

**Supported Roof Types:**
- Gable (2 surfaces, 1 ridge)
- Hip (4 surfaces, 1 ridge + 4 hips)
- Shed (1 sloped surface)
- Flat (1 horizontal surface)

**Output Format:**
```json
{
  "type": "gable",
  "pitch": 4,
  "overhang": 600,
  "ridge_height": 4200,
  "surfaces": [
    {
      "name": "West Slope",
      "vertices": [[x,y,z], ...],
      "normal": [nx, ny, nz],
      "slope": 18.43
    }
  ],
  "edges": [
    {"type": "ridge", "start": [...], "end": [...], "length": 10200},
    {"type": "eave", ...},
    {"type": "rake", ...}
  ]
}
```

#### schema_validator.py - JSON Schema Validation

Validates building JSON against expected structure.

```python
from schema_validator import validate_building_data, ValidationResult

result = validate_building_data(building_json, strict=False)

if result.is_valid:
    print(f"Valid with {result.warnings_count} warnings")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

**Validates:**
- Required fields (width, depth, walls_batch)
- Wall geometry (start/end coordinates, height)
- Door/window placement within walls
- Room bounds and labels
- Roof surface vertices

#### pdf_export.py - Professional PDF Output

Generates construction-quality PDF drawings with precise line weights.

```python
from pdf_export import batch_convert_svg_to_pdf, SheetSize, generate_single_sheet_pdf

# Convert all SVGs to PDF
batch_convert_svg_to_pdf(
    svg_dir='output/',
    output_dir='output/',
    sheet_size=SheetSize.ARCH_D,
    project_name='Sample House',
    create_set=True  # Creates combined drawing_set.pdf
)
```

**Sheet Sizes:**
| Type | Sizes |
|------|-------|
| US Architectural | ARCH A (9"×12") through ARCH E (36"×48") |
| ISO | A4 through A0 |
| ANSI | Letter through E-size |

**Line Weights (ISO 128):**
| Weight | Size | Use |
|--------|------|-----|
| Hairline | 0.13mm | Dimensions, hatching |
| Fine | 0.18mm | Text, annotations |
| Light | 0.25mm | Minor details |
| Medium | 0.35mm | Object lines |
| Heavy | 0.50mm | Section cuts |
| Extra Heavy | 0.70mm | Borders |
| Border | 1.00mm | Sheet border |

**Features:**
- Vector output (no rasterization)
- Professional title blocks
- Drawing scales (1:1 to 1:200, imperial)
- Multi-page drawing sets with bookmarks
- SVG to PDF conversion via svglib

#### generator_base.py - Common Utilities

Base utilities shared by all generators.

```python
from generator_base import (
    load_building_json,
    write_svg,
    handle_errors,
    create_base_parser,
    svg_header,
    svg_footer
)

@handle_errors
def main():
    data = load_building_json('building.json', validate=True)
    # ... generate drawing ...
    write_svg(svg_content, 'output.svg')
```

**Provides:**
- Error handling decorators
- JSON loading with validation
- SVG file writing
- Command-line argument parsing
- SVG header/footer generation
- Building dimension extraction

#### logging_config.py - Logging Infrastructure

Centralized logging with colored console output.

```python
from logging_config import setup_logging, get_logger, log_section, log_step

logger = setup_logging(name='generator', level=logging.INFO, colors=True)

with log_section("Generating Plans"):
    with log_step("Floor plan"):
        # ... work ...
        logger.success("Floor plan complete")  # Custom SUCCESS level
```

**Features:**
- Color-coded log levels (ERROR=red, WARNING=yellow, SUCCESS=green)
- Section/step context managers
- File + console output
- Progress tracking

### Usage

#### Full Pipeline

```bash
cd ArchEngine_kernel/scripts

# Install dependencies
pip install -r requirements.txt

# Run full pipeline
python generate_all.py ../../Shared/TestData/sample_building_complete.json \
    -o ../../Shared/TestData/output \
    --pdf \
    --sheet-size arch_d \
    -v
```

#### Individual Generators

```bash
# Floor and roof plans only
python generate_plans.py building.json -o output/

# Elevations only
python generate_elevations.py building.json -o output/

# Sections only
python generate_sections.py building.json -o output/
```

### Dependencies

```
# requirements.txt
reportlab>=4.0.0    # PDF generation
svglib>=1.5.0       # SVG to PDF conversion
Pillow>=10.0.0      # Image handling
lxml>=4.9.0         # XML parsing
```

### Output Structure

```
output/
├── floor_plan.svg
├── roof_plan.svg
├── elevation_south.svg
├── elevation_north.svg
├── elevation_east.svg
├── elevation_west.svg
├── section_a.svg
├── section_b.svg
├── details.svg
├── schedules.svg
├── enriched_building.json
├── index.html              # HTML viewer
├── floor_plan.pdf          # Individual PDFs
├── elevation_south.pdf
├── ...
└── drawing_set.pdf         # Combined multi-page PDF
```

---

## 4. UE5 Viewer (ArchEngine_Viewer)

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

## 5. Shared Data (JSON Schema)

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
│   ├── output/                      # Generated drawings
│   │   ├── generated_building.json  # Current building data
│   │   ├── enriched_building.json   # Data with roofs/wall types added
│   │   ├── floor_plan.svg           # Floor plan drawing
│   │   ├── roof_plan.svg            # Roof plan drawing
│   │   ├── elevation_*.svg          # 4 elevation drawings
│   │   ├── section_*.svg            # Section drawings
│   │   ├── details.svg              # Construction details
│   │   ├── schedules.svg            # Door/window/finish schedules
│   │   ├── index.html               # HTML viewer
│   │   ├── *.pdf                    # PDF exports (optional)
│   │   └── drawing_set.pdf          # Combined PDF set
│   ├── sample_building_complete.json # Complete test building
│   └── sample_qbd_output.json
├── Specs/
│   └── QBD_Format_v2.1.md        # QBD format specification
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

## 6. Coordinate Systems

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

## 7. Data Flow

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

## 8. Section View System

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

## 9. Roof System

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

## 10. Build & Run

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

## 11. Future Considerations

- **IFC Export** - Export to Industry Foundation Classes format
- **Structural Analysis** - Integrate with FEA solvers
- **Energy Modeling** - Thermal performance simulation
- **Cost Estimation** - Material takeoffs and pricing
- **VR Support** - Immersive walkthrough mode
- **Multi-story** - Enhanced vertical circulation
- **Terrain Integration** - Site grading and foundation
