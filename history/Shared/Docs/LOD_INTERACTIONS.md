# Level of Detail — Interaction Model

How the design evolves through LOD levels. Each level adds fidelity and shifts what the user can do.

---

## Overview

| LOD | What Emerges | What You Do | Dimensions | Mode |
|-----|--------------|-------------|------------|------|
| LOD 1 | Blobs | Drag, overlap, set relationships | None | LegiQBD |
| LOD 2 | Walls, doors, windows | Slide openings along walls | None | LegiCAD |
| LOD 3 | Fixtures, annotations | Place fixtures, verify | On demand | LegiCAD |
| LOD 4 | 2D viewports | Snap orthographic views to model | Computed | LegiCAD → LegiDoc |
| LOD 5 | Specifications | Code compliance, permits, schedules | Formal strings | LegiDoc |

---

## LOD 1 — Topology

**What you see:** Blobs representing rooms. No walls, no geometry. Just shapes with names.

**What emerges:** Room blobs generated from questionnaire answers or added manually.

**Interactions:**

| Action | Result |
|--------|--------|
| Drag blob | Move room, relationships stretch |
| Resize blob | Change relative size |
| Overlap blobs | Creates relationship at overlap |
| Pull blobs apart | Breaks relationship |
| Click overlap | Cycle relationship type |

**Overlap colors (relationship types):**

| Color | Relationship | Meaning |
|-------|--------------|---------|
| Green | Open | No wall, spaces flow together |
| Blue | Door | Wall with door connection |
| Yellow | Visual | Wall with window/opening |
| Red | Conflict | Separation required but touching |

**Rules:**

- Blobs snap to each other, not to grid
- Entry blob is anchor — everything positions relative to it
- L-shapes can emerge
- System scores and warns, doesn't block
- Position is relative (topology), not absolute (coordinates)

**What's captured:**

- Room exists
- Relative size (bigger/smaller)
- Adjacency relationships
- Rough topology
- Entry sequence

**What's NOT captured:**

- Exact dimensions
- Precise coordinates
- Wall locations
- Door swings

**Scoring:**

Real-time score updates as you drag. Factors:
- Light (are living spaces on the right side?)
- Flow (is circulation efficient?)
- Privacy (are bedrooms away from public spaces?)
- Relationships (are required adjacencies met?)

Warnings appear but don't block. You can make a bad plan if you want.

---

## LOD 2 — Walls

**What you see:** Walls appear at blob boundaries. Doors and windows appear at overlaps based on relationship type.

**What emerges:** Geometry derived from LOD 1 topology.

- Open relationship → no wall
- Door relationship → wall with door
- Visual relationship → wall with opening
- No overlap → wall, circulation connects

**Interactions:**

| Action | Result |
|--------|--------|
| Drag door | Slides along wall |
| Drag window | Slides along wall |
| Drag wall | Moves wall, intersections auto-merge |
| Adjust corner | L-shapes reshape |

**Tools:**

- **Move** — drag item, intersections auto-merge/rejoin
- **Extend/Trim** — automatic, system handles intersection cleanup

**Rules:**

- If relationships are set correctly in LOD 1, walls are already right
- No manual wall drawing — walls are consequences of relationships
- Openings slide along walls, don't get placed from scratch
- Intersections merge and rejoin automatically

**What's captured:**

- Wall positions (derived from topology)
- Opening positions along walls
- Room shapes (L, rectangle, etc.)

**What's NOT captured:**

- Dimensions (still no numbers)
- Fixtures
- Annotations

---

## LOD 3 — Fixtures

**What you see:** Fixtures appear in rooms. Toilets, sinks, tubs, appliances, furniture. Annotations available on demand.

**What emerges:** Fixtures placed based on room type and furniture specified in questionnaire.

**Interactions:**

| Action | Result |
|--------|--------|
| Drag fixture | Reposition within room |
| Swap fixture | Change type (tub ↔ shower) |
| Query | "How far is this from that?" |
| Hover | Shows dimension to nearby elements |

**Annotations:**

- Not always visible
- Appear on hover or query
- Computed from model, not drawn

**Coordinate system:**

```
Corner A: (0, 0)
Corner B: (6000, 0)
Opening C: center (3000, 0), width 900
Fixture D: center (1500, 2000)
```

Coordinates are the data. Dimensions are computed views.

**What's captured:**

- Fixture positions
- Opening dimensions (width, height)
- Coordinates for all corners and intersections
- Everything needed for LOD 4 and LegiSite

---

## LOD 4 — 2D Viewports

**What you see:** Traditional 2D drawings — plans, sections, elevations — generated from the 3D model.

**What emerges:** Viewports that snap to the model with orthographic projection.

**View types:**

| View | What It Shows |
|------|---------------|
| Plan | Horizontal cut at 1200mm (typical) |
| Section | Vertical cut at specified location |
| Elevation | Orthographic view from specified face |
| Detail | Zoomed view of specific area |

**Interactions:**

| Action | Result |
|--------|--------|
| Place plan viewport | Snaps to level, cuts at 1200mm |
| Place section line | Generates section view |
| Place elevation marker | Generates elevation view |
| Adjust cut height | Re-cuts the plan |
| Add detail bubble | Creates zoomed viewport |

**Rules:**

- You don't draw the plan — you place a camera
- Viewports are live — model changes, drawings update
- Dimension strings computed for the viewport
- Annotations can be added to viewports

**Pivot point:**

LOD 4 is the transition from design to documentation. You're not designing anymore — you're representing the design.

**What's captured:**

- Viewport definitions (location, type, scale)
- Cut planes
- Annotation overrides (if any)

---

## LOD 5 — Documentation (LegiDoc)

**What you see:** Complete permit and construction document package.

**What emerges:** Specifications, schedules, code compliance, signoff workflows.

**Components:**

| Component | Description |
|-----------|-------------|
| Specifications | Materials, products, installation requirements |
| Schedules | Door, window, finish, fixture schedules |
| Code compliance | Checklist by jurisdiction |
| Permit package | Drawings required for submission |
| Title blocks | Project info, revision tracking |
| Signoff | Approval workflows |

**Interactions:**

| Action | Result |
|--------|--------|
| Select jurisdiction | Loads code requirements |
| Run compliance check | Flags issues |
| Generate schedule | Extracts from model |
| Add revision | Tracks changes |
| Sign off | Locks section, logs approval |

**Audit trail complete:**

Every line in the permit drawing traces back:
- Drawing → Viewport → Model → Schema → Fragment → Question → User answer

**What's captured:**

- All documentation
- Compliance status
- Revision history
- Signoff log

---

## LOD Transitions

### LOD 1 → LOD 2

**Trigger:** Zoom in, or explicit "finalize topology"

**What happens:**
1. Topology locks (or prompts "finalize layout?")
2. System generates walls from relationships
3. Doors placed at door-relationship overlaps
4. Windows placed at visual-relationship overlaps
5. Circulation generated for non-adjacent rooms

**Can you go back?** Yes, but regenerates walls.

### LOD 2 → LOD 3

**Trigger:** Zoom in, or explicit "add fixtures"

**What happens:**
1. Wall positions lock (editable but stable)
2. Fixtures placed based on room type
3. Coordinates computed for all corners/intersections
4. Annotations available on demand

**Can you go back?** Yes, fixtures reposition if walls move.

### LOD 3 → LOD 4

**Trigger:** Switch to documentation mode, or "generate drawings"

**What happens:**
1. Model considered complete for documentation
2. Viewport tools appear
3. Plan/section/elevation generation available
4. Dimension strings computed

**Can you go back?** Yes, viewports update from model.

### LOD 4 → LOD 5

**Trigger:** Switch to LegiDoc, or "prepare permits"

**What happens:**
1. Drawings pulled into permit package
2. Schedules generated
3. Code compliance checked
4. Signoff workflows activated

**Can you go back?** Yes, but may invalidate signoffs.

---

## Mode Mapping

| LOD Range | Primary Mode | Activity |
|-----------|--------------|----------|
| LOD 1 | LegiQBD | Intent capture, topology |
| LOD 2-3 | LegiCAD | Geometry refinement |
| LOD 4 | LegiCAD → LegiDoc | Drawing generation |
| LOD 5 | LegiDoc | Documentation, compliance |

The UI emerges with the LOD. You don't see fixture tools at LOD 1. You don't see viewport tools at LOD 2.

---

## Dimension Philosophy

**Traditional:** Dimensions are the deliverable. Draw them, print them, builder reads them.

**Legible Studio:** Coordinates are the data. Dimensions are computed views.

| LOD | Dimensions |
|-----|------------|
| LOD 1 | None |
| LOD 2 | None |
| LOD 3 | On demand (hover, query) |
| LOD 4 | Computed for viewports |
| LOD 5 | Formal strings for permits |

**LegiSite receives coordinates, not dimensions.**

Builder doesn't read a dimension string. Station marks corner A, marks corner B. Connect the dots.

**Dimensions are a legacy output** — generated for permits, for clients who want paper, for jurisdictions that require it. Not the source of truth.

---

## Summary

```
LOD 1: What rooms, how they relate (topology)
        ↓
LOD 2: Where the walls go (geometry from intent)
        ↓
LOD 3: What's in the rooms (fixtures, coordinates)
        ↓
LOD 4: How to represent it (2D from 3D)
        ↓
LOD 5: How to document it (specs, permits, codes)
```

Each level: you express intent, system generates output.

You never draw a wall. You never place a door from scratch. You say "these rooms connect with a door" and the door appears where it makes sense.

---

*Document version: 1.0*
