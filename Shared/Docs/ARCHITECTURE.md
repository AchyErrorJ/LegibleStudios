# Legible Studio — Architecture Guide

## Company Vision

**Legible Computer Assisted Decision Making**

Design decisions you can read. Every line traces back to a decision, every decision traces back to a question. The audit trail isn't reconstructed—it's baked in from the start.

---

## Design Philosophy

### Intent Driven Design

Legible Studio captures design intent, not geometry. The system stores parameters, constraints, and relationships — downstream tools compute the actual shapes.

Traditional CAD is geometry-first: you manipulate vertices, edges, and faces until it looks right. Intent driven design is meaning-first: you express what you want and why, and the system figures out the how.

This means:
- The schema stays lean (parameters, not meshes)
- Changes propagate intelligently (adjust one parameter, related geometry updates)
- The design intent is readable and queryable, not buried in coordinates

### Question Based Design

You design through conversation. Describe what you need, ask questions, get answers, refine.

The system also asks *you* questions when it needs clarity:
- "You said 10% max grade but the terrain is steep here. Switchbacks or tunnel?"
- "The setback you requested conflicts with the lot line. Reduce building width or request a variance?"

This is fundamentally different from direct manipulation. The dialogue *is* the design tool. Geometry is a byproduct, not the interface.

### First Try Design

Enforced by the software itself. You can't skip the thinking because the tools to skip don't exist until you've done the work.

If you can't describe it, it's not design — it's preference. The system demands clarity upfront and generates optimal solutions from complete inputs.

---

## Core Principle

Legible Studio uses a single source of truth — a JSON-based schema generated through conversation with an LLM. The user describes what they want, the LLM produces the canonical schema, and downstream tools consume it.

---

## Product Architecture

### Legible Studio

One application with an emerging UI. Three modes that appear as your design matures:

| Phase | Mode | Function |
|-------|------|----------|
| 1 | **LegiQBD** | Questions, constraints, intent capture. Solver generates options. Canvas is sparse, focused on decisions. |
| 2 | **LegiCAD** | Geometry tools emerge because now you have geometry. Walls, openings, annotations. Refining what the solver gave you. Rendering built in. |
| 3 | **LegiDoc** | Sheet tools, titleblocks, schedules. Permit checklists tied to design. Signoff workflows. Audit trail complete. |

The UI grows around the user. Tools appear when meaningful, not before. No cold start into CAD—you reach it by doing the work first.

### Field Products

| Product | Description |
|---------|-------------|
| **LegiSite** | Motorized tracking station + phone app. Hardware purchase, free app. Replaces robotic total station for layout. Works out of the box—no desktop software required. |
| **LegiView** | Tethered XR safety glasses. Hardware for job site AR. |
| **LegiLens** | XR software layer. Runs on LegiView, but also third-party glasses, tablets, phones. Hardware-agnostic. |

### Engine

**Archengine** — The underlying kernel. Vulkan renderer, QBD Algebra, shared geometry library. Powers everything, invisible to end users.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Legible Studio                          │
│  ┌───────────────┬───────────────┬───────────────┐         │
│  │    LegiQBD    │    LegiCAD    │    LegiDoc    │         │
│  │   (intent)    │   (geometry)  │   (output)    │         │
│  └───────┬───────┴───────┬───────┴───────┬───────┘         │
│          │               │               │                  │
│  ┌───────▼───────────────▼───────────────▼───────┐         │
│  │                  Archengine                    │         │
│  │  ┌─────────────────────────────────────────┐  │         │
│  │  │            QBD Algebra                  │  │         │
│  │  │  - JSON Templates    - Validation       │  │         │
│  │  │  - Fragments         - Derivation       │  │         │
│  │  │  - State Lifecycle   - Solver           │  │         │
│  │  └─────────────────────────────────────────┘  │         │
│  │  ┌─────────────────────────────────────────┐  │         │
│  │  │       Shared Geometry Library (C++)     │  │         │
│  │  │  Parameters → Geometry (single truth)   │  │         │
│  │  └─────────────────────────────────────────┘  │         │
│  │  ┌─────────────────────────────────────────┐  │         │
│  │  │           Vulkan Kernel                 │  │         │
│  │  │  - Rendering        - Structural sim    │  │         │
│  │  │  - LOD system       - Thermal sim       │  │         │
│  │  │  - Visual styles    - Acoustic sim      │  │         │
│  │  └─────────────────────────────────────────┘  │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌──────────┐     ┌──────────┐     ┌──────────┐
    │ LegiSite │     │ LegiView │     │ LegiLens │
    │  (app)   │     │ (glasses)│     │(XR layer)│
    └──────────┘     └──────────┘     └──────────┘
          │
          ▼
    ┌──────────┐
    │ LegiSite │
    │(station) │
    └──────────┘
```

---

## Data Flow

```
LegiQBD (intent/decisions)
    ↓
QBD Algebra (validates, derives, solves)
    ↓
JSON Schema (source of truth)
    ↓
LegiCAD (geometry/coordinates via Shared Library)
    ↓
LegiDoc (documentation/permits)
    ↓
LegiSite phone app (consumes points from schema)
    ↓
LegiSite station (field layout)
    ↓
LegiView + LegiLens (XR verification)
    ↓
LegiDoc (as-built, signoff, audit trail)
```

**Traceability is complete.** A point on the job site traces back through the station, through the app, through the schema, through QBD Algebra, to the original question that placed that wall.

---

## Mode Transitions & State Lifecycle

The UI phases map directly to QBD Algebra state:

| State | Mode Available | Why |
|-------|----------------|-----|
| EMPTY | LegiQBD only | No data yet |
| ACCUMULATING | LegiQBD only | Answering questions, not enough to solve |
| COMPLETE | LegiQBD only | Can solve, but hasn't yet |
| SOLVED | LegiQBD + LegiCAD | Geometry exists, can now refine |
| LOCKED | LegiQBD + LegiCAD + LegiDoc | Design confirmed, ready for documentation |

Tools don't appear until they're meaningful. You can't skip to CAD because there's nothing to draw until the solver runs.

---

## Three-Layer Architecture

### Layer 1: LLM (Intent & Parameters)

The LLM handles:
- Interpreting user intent from conversation
- Generating and modifying schema parameters
- Design decisions and spatial relationships
- Calling compute services for quantitative answers
- Responding to changes made in LegiCAD

The LLM does NOT:
- Generate detailed geometry (vertices, meshes, curves)
- Perform heavy calculations (volumes, cut/fill, slope stability)
- Store state between conversations (the schema is the state)

### Layer 2: Schema (Contract)

The JSON schema is the single source of truth. It contains:
- Parameters and constraints (not computed geometry)
- Design intent that downstream tools interpret
- Enough information for any consumer to generate what it needs
- Complete audit trail — every value traces to a decision

Example — a bench is stored as parameters:
```json
{
  "id": "bench-015",
  "elevation": -15,
  "berm_width": 8,
  "face_angle": 70
}
```

Not as geometry. LegiCAD computes the actual surface from these parameters plus terrain data.

### Layer 3: Compute + Geometry

Heavy lifting lives here:
- **LegiCAD** — generates and displays geometry from parameters, allows refinement, writes changes back to schema
- **LegiDoc** — generates sheets, schedules, permit checklists from schema
- **Compute Services** — calculations the LLM can call (volumes, strip ratios, grades, sight lines, costs)
- **LegiSite** — consumes coordinates for field layout

### Round-Trip Flow

```
User: "Add a bench at -30m"
         ↓
LLM updates schema with bench parameters (fragment)
         ↓
QBD Algebra validates and re-solves
         ↓
LegiCAD regenerates geometry from new schema
         ↓
User adjusts bench edge in LegiCAD
         ↓
LegiCAD updates schema with new parameters (fragment)
         ↓
LLM sees change: "I see you widened the berm to 10m — want me to apply that to all benches?"
```

### Compute Service Pattern

For quantitative questions, the LLM calls external compute:

```
User: "What's my strip ratio?"
         ↓
LLM calls: compute.strip_ratio(pit_geometry)
         ↓
Compute returns: { "strip_ratio": 3.2, "waste_m3": 4800000, "ore_m3": 1500000 }
         ↓
LLM responds: "Strip ratio is 3.2:1 — 4.8M m³ waste to 1.5M m³ ore"
```

This keeps the LLM fast and accurate for numerical answers.

---

## Shared Geometry Library

### The Problem

Multiple consumers interpret the same schema. If they interpret it differently, you get drift — the CAD shows one thing, the plan generator draws another, the kernel simulates a third. Debugging these mismatches is painful and never-ending.

### The Solution

One canonical C++ library that turns parameters into geometry. Every consumer calls this library. No consumer interprets schema parameters on its own.

```
Schema (parameters)
       ↓
Shared Library (C++)
       ↓
Geometry (vertices, faces, curves)
       ↓
Consumers (LegiCAD, LegiDoc, Kernel, LegiSite)
```

### What the Library Does

- Reads schema JSON
- Computes geometry from parameters (walls, floors, roofs, terrain, benches, roads)
- Returns geometry in a standard format all consumers can use
- Handles all parameter interpretation (what does "wall thickness: 6 inches" actually mean spatially?)
- Provides query functions (give me all walls on level 2, what's the area of this room)

### What the Library Does NOT Do

- Rendering (that's the kernel)
- User interaction (that's LegiCAD)
- 2D drawing production (that's LegiDoc)
- Simulation (that's the kernel's physics layer)

The library is the geometry truth. Consumers handle presentation and interaction.

### Language Bindings

C++ is the source of truth. Other languages bind to it:

```
┌─────────────────────────────────────┐
│      Shared Geometry Library        │
│              (C++)                  │
└─────────────────────────────────────┘
        ↑           ↑           ↑
   Python       C#/.NET       Direct
   bindings     bindings      linking
      ↓            ↓            ↓
   Scripts     LegiCAD UI    Kernel
   Tools       (if C#)       LegiDoc
```

Bindings are thin wrappers. All real logic lives in C++.

### Development Rule

**New schema features don't exist until the C++ library handles them.**

If you add a new parameter type to the schema, the implementation order is:

1. C++ library interprets it and produces geometry
2. Tests verify the geometry is correct
3. Consumers can now use it (via bindings or direct linking)

This prevents parallel implementations and interpretation drift.

### Migration Path

Current state: some interpretation logic lives in individual consumers.

Target state: all interpretation in C++ library.

Migration:
1. Build library with core types (walls, floors, openings)
2. Consumers start calling library for those types
3. Add types incrementally, moving logic out of consumers
4. Eventually consumers have zero interpretation logic

### Testing Strategy

- Unit tests: each parameter type produces expected geometry
- Round-trip tests: schema → geometry → back to parameters (where applicable)
- Cross-consumer tests: all consumers produce identical results from same schema
- Golden file tests: known schemas produce known geometry (regression protection)

### Performance Considerations

The library may be called frequently (real-time editing in CAD). Consider:

- Incremental updates (only recompute what changed)
- Caching computed geometry
- LOD support (quick rough geometry vs. precise final geometry)
- Async computation for heavy operations

---

## Design Goals

- **Extensibility over optimization** — Design for mine-scale projects even while building residential tools
- **Loose coupling** — Each consumer is independent; they share the schema, not each other's implementations
- **LLM-native** — The schema should be easy for an LLM to generate and reason about
- **Storage agnostic** — The schema and access patterns should work whether backed by a single JSON file, chunked files, SQLite, or a future API

---

## Schema Design

### Structure

Keep the schema modular with logically separable top-level sections:

```json
{
  "version": "1.0.0",
  "metadata": { },
  "site": { },
  "buildings": [ ],
  "levels": [ ],
  "rooms": [ ],
  "elements": [ ]
}
```

Each section should be independently loadable in future storage implementations.

### Versioning

- Include `version` at the root level from day one
- Use semantic versioning (major.minor.patch)
- Major version changes indicate breaking schema changes
- Document migration paths between versions

### Extension Pattern

Use namespaced extensions for tool-specific data:

```json
{
  "id": "element-001",
  "type": "wall",
  "geometry": { },
  "extensions": {
    "revit": { },
    "ue5": { },
    "generator": { }
  }
}
```

Tools ignore namespaces they don't recognize.

---

## Access Layer

### Interface-First Design

Translators and consumers should not directly read/write files. Define an interface:

```
getProjectMetadata()
getElementsByType(type)
getElementById(id)
getElementsInBounds(bbox)
saveElement(element)
saveProject()
```

Today these functions read a JSON file. Tomorrow they could query SQLite or hit an API. Consumers don't care about storage implementation.

### Reference Implementation

Build one canonical reader/writer library that all translators use or wrap. When storage changes, update one place.

Recommended: TypeScript or Python for cross-platform compatibility.

---

## Consumer Consistency

Since the LLM generates the schema directly, there's no translator drift problem at the input layer. The focus shifts to ensuring consumers interpret the schema consistently.

### Validation Layer

All consumers must validate against the schema:

- Schema validation (structure correctness)
- Semantic validation (business rules)
- Report errors clearly so the LLM can correct the output

### Consumer Testing Strategy

- Unit tests for each consumer's schema parsing
- Golden file tests for known good outputs
- Round-trip testing: LegiCAD saves should produce identical schema

---

## Future Storage Paths

When single-file JSON is outgrown:

### Chunked Files
- Manifest file points to sub-files
- Spatial or logical chunking (by building, by level, by zone)
- Maintains git-friendliness

### SQLite + JSON
- Tables for indexing and queries
- JSON blobs for complex nested data
- Single file, no server, queryable

### API Layer
- Local REST/GraphQL service wrapping storage
- Required for real-time collaboration
- Multi-user concurrent access

The access layer abstraction makes this migration transparent to consumers.

---

## Implementation Checklist

When building new consumers or updating existing ones:

- [ ] Does it use the access layer interface (not direct file I/O)?
- [ ] Does it handle schema versioning?
- [ ] Does tool-specific data go in the `extensions` namespace?
- [ ] Does it validate the schema before processing?
- [ ] Does it gracefully ignore unknown schema sections?
- [ ] Does it report errors in a way the LLM can understand and correct?

---

## Current State

- Storage: Single JSON file
- Reference implementation: TBD
- Schema version: 1.0.0
- Input: LLM conversation via LegiQBD
- Active consumers: LegiCAD, LegiDoc, Vulkan Kernel
- Field products: In development

---

## Version Roadmap

### Version 1 — Core Product (Legible Studio)

Focus: Get the intent driven design loop working end-to-end.

**Includes:**
- LegiQBD → Schema → LegiCAD (full loop)
- QBD Algebra (validation, derivation, solver)
- Vulkan kernel as primary renderer
- Integrated sims (structural, thermal, sound)
- LegiCAD for viewing/refining schema
- LegiDoc for 2D output and documentation
- Shared C++ geometry library

**Does NOT include:**
- VR support
- 4K / photorealistic rendering
- LegiSite hardware
- LegiView/LegiLens

**Why:** Ship a tight, focused product. No external dependencies blocking release. Visual fidelity matters less than responsiveness for design exploration.

### Version 2 — Pro Features & Field Products

Focus: Polish, immersive visualization, and field deployment.

**Adds:**
- 4K quality rendering in Vulkan kernel
- VR support (native Vulkan)
- Enhanced materials and lighting
- Client presentation mode
- LegiSite phone app (consumes schema coordinates)
- LegiSite hardware (ships when app is proven)

### Version 3 — Extended Reality

**Adds:**
- LegiView hardware
- LegiLens XR software layer
- As-built verification workflows
- Full field-to-office audit trail

---

## Level of Detail System

### Philosophy

Everything exists in the schema. LOD isn't about hiding information — it's about presenting what's meaningful at your current level of focus.

This is not CAD (consciously setting scale, making drawings). This is not BIM (same detail level everywhere, always too much or too little). This is the design breathing as you explore it.

---

## LegiCAD: Review, Refine & Constrain

### Philosophy

LegiCAD emerges when you have geometry to work with. It's not a blank canvas — it's a refinement tool for what QBD Algebra solved.

The conversation remains the primary design tool. LegiCAD is for:
- Reviewing what the solver produced
- Refining details the solver couldn't know
- Constraining elements you want to preserve
- Querying the design

### Core Actions

**Navigate**
- Move through the model
- Change views (plan, elevation, section, 3D)
- Zoom triggers LOD transitions

**Select**
- Click to identify elements
- Selection provides context for conversation ("make *this* room bigger")
- Multi-select for group operations

**Refine**
- Adjust geometry the solver produced
- Move walls, resize openings, adjust positions
- Every edit becomes a fragment in QBD Algebra
- Constraints are respected — pinned elements stay fixed

**Pin / Lock**
- Mark elements or relationships as solved
- Pinned elements are constraints the solver must respect on regeneration
- "I like this, don't change it"

**Annotate**
- Mark up the model with feedback
- Notes provide context for the LLM ("this doesn't work because...")
- Could be voice, text, or sketch

**Query**
- "How far is this from that?"
- "What's the area of this room?"
- LLM or compute layer answers

### UI Principles

- Tools appear as they become relevant
- No tool palettes on first launch — you're in LegiQBD
- Geometry tools emerge when SOLVED state is reached
- Chat always visible or accessible
- Voice input available

### Constraint Schema

Pins and locks write back to the schema:

```json
{
  "id": "room-living",
  "type": "room",
  "constraints": {
    "pinned": true,
    "locked_properties": ["position", "dimensions"],
    "notes": "Client approved this layout"
  }
}
```

The solver reads these constraints and respects them during regeneration.

---

### Continuous, Not Discrete

LOD transitions are smooth. Elements fade in and resolve as you zoom, like focus pulling on a camera. No jarring switches, no mode changes.

The experience should feel magical — you move through the design and it reveals itself.

### Resolution Order

What appears first at each LOD communicates hierarchy:

1. **Structure** — the bones snap in first
2. **Enclosure** — walls, floors, roofs resolve
3. **Systems** — MEP, fixtures fade in
4. **Annotations** — dimensions, notes, symbols last

The order tells a story: function before finish, relationships before details.

### LOD Levels

Tied to scale ranges, but transitions are smooth between them:

| Scale Range | LOD | What's Visible |
|-------------|-----|----------------|
| 1:500+ | 1 | Massing, room names, major dimensions |
| 1:200 - 1:100 | 2 | Wall thickness, doors/windows, key dimensions |
| 1:100 - 1:50 | 3 | Fixtures, openings detailed, full annotations |
| 1:50 - 1:20 | 4 | Construction detail, materials, specs |
| 1:20 and closer | 5 | Assembly details, fasteners, tolerances |

### Implementation

**LegiDoc (Plan Generation):**
- Determines what elements to include based on current scale
- Controls annotation density and symbol complexity
- Manages which dimensions appear

**Kernel (Rendering):**
- Handles fade/resolve transitions
- Controls timing and easing of element appearance
- Easter egg: Star Wars hologram flicker on resolve (optional/subtle)

**Schema:**
- Contains all information at all times
- LOD is purely a presentation concern
- Elements may have LOD hints (e.g., "don't show until LOD 3")

### Mixed LOD in Single View

A view can have different LOD in different regions:

- Overall plan at LOD 2
- Detail bubble drops an area to LOD 4
- Everything outside the bubble stays at LOD 2 but dims slightly

Focus follows attention.

### The Goal

The user never thinks about LOD. They explore, and the design responds. Zoom out to understand relationships. Zoom in to understand construction. The representation serves the question you're asking right now.
