# Archengine Implementation Specification

This document defines what an agent needs to build to implement the Archengine system. Use this to cross-reference existing work and identify gaps.

---

## System Overview

Archengine is an intent driven, question based design system. Users design through conversation with an LLM. The LLM generates a JSON schema containing design parameters. Downstream consumers interpret the schema to produce geometry, drawings, and simulations.

**Core principle:** The conversation is the design tool. Geometry is a byproduct.

---

## Component Checklist

### 1. Schema Definition

The JSON schema is the single source of truth.

**Required elements:**

- [ ] Version field (`"version": "1.0.0"`)
- [ ] Metadata (project name, type, coordinate system, units)
- [ ] Site definition (bounds, terrain reference)
- [ ] Buildings array
- [ ] Levels array
- [ ] Rooms array (with relationships, adjacencies)
- [ ] Elements array (walls, doors, windows, floors, roofs)
- [ ] Constraints object (pinned elements, locked properties, notes)
- [ ] Extensions namespace (for consumer-specific data)

**Schema design rules:**

- [ ] Parameters only, no computed geometry
- [ ] Modular structure (each section independently loadable)
- [ ] Relationships expressed as IDs/references
- [ ] Extensible without breaking existing consumers

**Example minimal schema:**

```json
{
  "version": "1.0.0",
  "metadata": {
    "project": "Example House",
    "type": "residential",
    "units": "imperial"
  },
  "site": {
    "bounds": { "width": 100, "length": 150 }
  },
  "buildings": [
    { "id": "building-001", "levels": ["level-001", "level-002"] }
  ],
  "levels": [
    { "id": "level-001", "elevation": 0, "height": 9, "name": "First Floor" }
  ],
  "rooms": [
    {
      "id": "room-living",
      "name": "Living Room",
      "level": "level-001",
      "area_target": 400,
      "adjacencies": ["room-kitchen", "room-entry"],
      "constraints": {
        "pinned": false,
        "locked_properties": []
      }
    }
  ],
  "elements": [
    {
      "id": "wall-001",
      "type": "wall",
      "subtype": "exterior",
      "thickness": 6,
      "height": 9,
      "rooms": ["room-living", null],
      "openings": ["door-001"]
    },
    {
      "id": "door-001",
      "type": "door",
      "width": 36,
      "height": 80,
      "wall": "wall-001"
    }
  ],
  "extensions": {
    "kernel": {},
    "plan_generator": {}
  }
}
```

---

### 2. Shared Geometry Library (C++)

The canonical interpreter. All consumers use this library.

**Required capabilities:**

- [ ] JSON parser (read schema)
- [ ] Schema validation (structure and semantic)
- [ ] Parameter → geometry conversion for all element types:
  - [ ] Walls (from room relationships and constraints)
  - [ ] Floors (from room boundaries)
  - [ ] Roofs (from building footprint and parameters)
  - [ ] Doors/windows (from wall references and positions)
  - [ ] Stairs (from level connections)
  - [ ] Terrain (from site data)
- [ ] Geometry output format (vertices, faces, curves)
- [ ] Query functions:
  - [ ] `getElementsByType(type)`
  - [ ] `getElementById(id)`
  - [ ] `getElementsOnLevel(level_id)`
  - [ ] `getElementsInBounds(bbox)`
  - [ ] `getRoomBoundary(room_id)`
  - [ ] `getAdjacentRooms(room_id)`
- [ ] Constraint handling (respect pinned/locked elements)
- [ ] Incremental updates (recompute only what changed)
- [ ] LOD hints (which elements appear at which detail level)

**Language bindings:**

- [ ] C++ core (source of truth)
- [ ] Python bindings (for scripting, LLM integration)
- [ ] Other bindings as needed

**Testing:**

- [ ] Unit tests for each element type
- [ ] Golden file tests (known schema → known geometry)
- [ ] Round-trip tests where applicable

---

### 3. Vulkan Kernel (archengine_kernel)

Primary renderer and simulation engine.

**Rendering requirements:**

- [ ] Reads schema via shared library
- [ ] 3D rendering of all geometry types
- [ ] Multiple visual styles:
  - [ ] Wireframe
  - [ ] Materials/shaded
  - [ ] Simulation overlays (structural, thermal, acoustic)
- [ ] LOD system:
  - [ ] Smooth fade/resolve transitions (not discrete jumps)
  - [ ] Scale-based LOD triggers
  - [ ] Resolution order (structure → enclosure → systems → annotations)
  - [ ] Easter egg: Star Wars hologram flicker on resolve (optional)
- [ ] Viewport system:
  - [ ] Orthographic views (plan, elevation, section)
  - [ ] Perspective 3D view
  - [ ] Section cuts with clip planes
  - [ ] All views into same 3D model
- [ ] Shadows
- [ ] Basic lighting

**Simulation requirements:**

- [ ] Structural simulation
- [ ] Thermal simulation
- [ ] Acoustic simulation
- [ ] Results readable by LLM (via compute service pattern)

**Performance:**

- [ ] Real-time for interactive editing
- [ ] Incremental updates when schema changes

**Future (v2):**

- [ ] 4K quality rendering
- [ ] VR support
- [ ] Enhanced materials and lighting

---

### 4. CAD Viewer

Review and constraint tool. NOT a geometry editor.

**Navigation:**

- [ ] Pan, zoom, orbit
- [ ] View switching (plan, elevation, section, 3D)
- [ ] Smooth transitions between views
- [ ] Zoom triggers LOD transitions
- [ ] Orbital map (3D thumbnail for orientation)

**Selection:**

- [ ] Click to select elements
- [ ] Multi-select
- [ ] Selection highlights in all views
- [ ] Selected element info displayed

**Constraints:**

- [ ] Pin/lock toggle on selected elements
- [ ] Visual indicator for pinned/locked elements
- [ ] Writes constraints back to schema
- [ ] Lock specific properties (position, dimensions, etc.)

**Annotation:**

- [ ] Add notes to elements or locations
- [ ] Notes stored in schema
- [ ] Notes provide context for LLM

**Query:**

- [ ] Distance measurement
- [ ] Area query
- [ ] Element properties inspection
- [ ] Results can come from shared library or LLM

**UI:**

- [ ] Minimal interface (no tool palettes)
- [ ] Chat always visible or accessible
- [ ] Voice input available
- [ ] Clear feedback on current mode/selection

**What it does NOT do (v1):**

- [ ] Direct geometry manipulation (move, stretch, rotate)
- [ ] Drawing/drafting tools
- [ ] Manual dimensioning

---

### 5. Plan Generator

Produces 2D drawings from schema.

**Output types:**

- [ ] Floor plans
- [ ] Elevations
- [ ] Sections
- [ ] Site plan

**LOD-based content:**

| LOD | Content |
|-----|---------|
| 1 | Room names, overall dimensions, walls as lines, simple door symbols |
| 2 | Wall thickness, door swings, key dimensions |
| 3 | Fixtures, detailed symbols, full annotations |
| 4 | Construction detail, materials, specs |
| 5 | Assembly details, fasteners, tolerances |

**Requirements:**

- [ ] Reads schema via shared library
- [ ] Scale-appropriate output
- [ ] Annotation placement (dimensions, labels, notes)
- [ ] Symbol library (doors, windows, fixtures, etc.)
- [ ] Output format (PDF, SVG, DXF, or similar)
- [ ] Sheet layout for printing

---

### 6. LLM Integration Layer

Connects conversation to schema and compute.

**Conversation → Schema:**

- [ ] Natural language input
- [ ] Intent parsing
- [ ] Schema generation (new projects)
- [ ] Schema modification (changes to existing)
- [ ] Respect constraints (pinned/locked elements)
- [ ] Validation of generated schema

**Compute service access:**

- [ ] Call simulations (structural, thermal, acoustic)
- [ ] Call query functions (area, distance, etc.)
- [ ] Parse and present results in conversation

**Context awareness:**

- [ ] Knows current selection in CAD viewer
- [ ] Sees annotations/notes
- [ ] Understands what user is looking at
- [ ] Can reference specific elements by ID or description

**Error handling:**

- [ ] Invalid schema detection
- [ ] Clear error messages back to user
- [ ] Suggestion for fixes

---

### 7. Voice Interface

Accessibility and natural interaction.

**Requirements:**

- [ ] Speech to text input
- [ ] Text to speech output (optional)
- [ ] Wake word or push-to-talk activation
- [ ] Works alongside typed chat
- [ ] Commands for navigation ("show me the south elevation")
- [ ] Commands for constraints ("lock this room")
- [ ] Design conversation ("make the kitchen bigger")

---

## Integration Points

### Schema ↔ Shared Library

- Library reads JSON schema
- Library validates schema
- Library produces geometry
- Library answers queries

### Shared Library ↔ Kernel

- Kernel calls library for geometry
- Kernel calls library for LOD hints
- Kernel renders geometry

### Shared Library ↔ Plan Generator

- Plan generator calls library for 2D geometry
- Plan generator calls library for element data

### Shared Library ↔ CAD Viewer

- Viewer calls library for display geometry
- Viewer calls library for queries
- Viewer writes constraints back to schema (library or direct)

### LLM ↔ Schema

- LLM generates/modifies schema JSON
- LLM reads schema for context

### LLM ↔ Compute (via kernel)

- LLM calls simulation endpoints
- Kernel returns structured results
- LLM presents results in conversation

### CAD Viewer ↔ LLM

- Selection state passed to LLM
- Annotations passed to LLM
- LLM responses trigger schema updates → viewer refreshes

---

## File Structure (suggested)

```
archengine/
├── schema/
│   ├── schema.json          # JSON schema definition
│   ├── examples/            # Example project files
│   └── validation/          # Schema validation rules
├── shared_lib/
│   ├── src/                 # C++ source
│   ├── include/             # Headers
│   ├── bindings/            # Python/other bindings
│   └── tests/               # Unit and golden tests
├── kernel/
│   ├── src/                 # Vulkan renderer
│   ├── shaders/             # GLSL/SPIR-V shaders
│   ├── sims/                # Simulation modules
│   └── tests/
├── viewer/
│   ├── src/                 # CAD viewer application
│   └── ui/                  # UI components
├── plan_generator/
│   ├── src/
│   ├── symbols/             # Symbol library
│   └── templates/           # Sheet templates
├── llm_integration/
│   ├── src/
│   ├── prompts/             # System prompts
│   └── tests/
└── docs/
    ├── ARCHITECTURE.md
    └── IMPLEMENTATION_SPEC.md
```

---

## Development Order (suggested)

### Phase 1: Foundation

1. Schema definition (finalize structure)
2. Shared library core (JSON parsing, basic geometry)
3. Kernel basic rendering (display geometry from library)

### Phase 2: Design Loop

4. LLM integration (generate schema from conversation)
5. CAD viewer (navigation, selection)
6. Round-trip working (conversation → schema → display)

### Phase 3: Constraints & Feedback

7. Pin/lock system in viewer
8. Constraints respected by LLM
9. Annotations flow to LLM

### Phase 4: Output

10. Plan generator (basic plans)
11. LOD system in viewer and generator
12. Simulations callable from LLM

### Phase 5: Polish

13. Voice interface
14. Smooth LOD transitions (fade/resolve)
15. UI refinement
16. Testing and validation

---

## Questions to Answer During Implementation

1. **Schema:** What's the minimum schema that supports a residential project end-to-end?
2. **Geometry:** How does the shared library determine wall positions from room relationships?
3. **Constraints:** How granular are locks? (whole element, specific properties, relationships?)
4. **LLM:** What model? Local or API? How is context managed for long design sessions?
5. **Performance:** What's the target for regeneration time after a conversation turn?
6. **Output:** What file formats for plan generator output?
7. **Deployment:** Desktop app? Web? Both?

---

## Success Criteria

The system is working when:

- [ ] User can describe a house in conversation
- [ ] Schema is generated automatically
- [ ] Geometry appears in viewer without manual intervention
- [ ] User can navigate and inspect the design
- [ ] User can pin elements they like
- [ ] User can request changes, pinned elements stay fixed
- [ ] Plans can be generated at appropriate LOD
- [ ] Simulations answer questions in conversation
- [ ] The experience feels like designing through dialogue, not operating software
