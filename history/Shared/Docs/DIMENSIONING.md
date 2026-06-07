# Dimensioning Logic for Plan Generators

Working document to hash out dimensioning approach.

---

## Core Principle

Corners and intersections are computed by the shared library, not stored in the schema. Dimensioning is a presentation layer concern — deciding which computed points to show and how to format them.

**Key insight:** Dimension the *decision* (where things go), not the *consequence* (how big spaces end up). Centerlines are the decision. Face-to-face and clear dimensions are computed consequences.

---

## Two Output Modes

### Paper Output (Plan Generator)
- Traditional dimension chains
- Formatted strings ("12'-6"", "3.81m")
- Leaders, ticks, dimension lines
- Selective — can't show everything

### VR/AR Layout
- Raw coordinates relative to site datum
- Headset places points in real space
- Potentially show all corners
- No formatting needed — just positions

---

## Reference Points (Contextual by Phase)

| Construction Phase | Reference Point |
|-------------------|-----------------|
| Survey / Site Prep | GPS coordinates or property pins |
| Foundation / Footing | Property corner |
| Wall Layout / Framing | Building corner |
| Interior Partitions | Building corner or grid |

The system should support multiple reference points — the relevant one depends on what's being built.

### GPS Precision Note

- Standard GPS: ~3-5 meter accuracy (not usable for layout)
- RTK GPS: 1-2 cm (~1/2 inch) accuracy
- Survey-grade RTK: sub-centimeter possible
- 1/4 inch precision requires RTK equipment or local positioning (total station, UWB beacons)

For VR on-site layout, assume RTK or local positioning system, not phone GPS.

---

## Dimension Strategy: Centerlines First

### What Gets Dimensioned (Stored/Shown)
- Centerline locations of exterior walls (structural centerline)
- Centerline locations of interior partitions
- Centerline locations of openings (doors, windows)
- Reference to origin (property corner or building corner)

### What Gets Computed on Demand
- Face positions (centerline ± half thickness)
- Face-to-face / clear dimensions
- Room areas and sizes
- Clearances (accessibility, appliance fit, etc.)

### Why Centerlines
- Centerline is the *decision* — where the wall goes
- Face-to-face is a *consequence* — derived from centerline + thickness
- Framers snap lines to centerlines
- Non-redundant — one source of truth, everything else computed
- Thickness is already in schema, no need to dimension it twice

---

## Dimension Groups

Dimensions are organized by what's being located:

### 1. Exterior Walls
- Dimensioned to structural centerline (center of stud, not sheathing)
- Referenced from building corner or property line
- Shows overall building footprint and wall positions

### 2. Interior Partitions
- Dimensioned to centerline
- Referenced from building corner or exterior wall
- Grouped by area or zone

### 3. Openings
- Doors and windows dimensioned to centerline
- Referenced from nearest wall end or corner
- Grouped by wall or by type

---

## Computed Data Available

The shared library provides:

```
getCenterline(wall_id) → centerline coordinates
getOpeningCenterline(opening_id) → opening center position
getFacePosition(wall_id, side) → computed from centerline + thickness
getClearDimension(room_id, direction) → face-to-face of finishes
getRoomArea(room_id) → computed from boundaries
getCorners() → all corner coordinates (for VR)
getIntersections() → wall/wall intersections
```

All coordinates relative to current reference point (configurable).

---

## LOD Rules (Revised)

| LOD | What Gets Dimensioned |
|-----|----------------------|
| 1 (Schematic) | Overall building extents only |
| 2 (Design Dev) | Overall + major partition centerlines |
| 3 (Construction) | All centerlines, all openings |
| 4 (Detail) | Everything + specific clearances, tolerances |
| 5 (Assembly) | Fastener locations, material specifics |

Room sizes shown as area labels, not face-to-face dimensions.

---

## Query Examples

User asks "how wide is the hallway?" →
- LLM queries: `getClearDimension("room-hallway", "width")`
- Shared library computes: finds walls, gets centerlines, subtracts half-thickness each side, subtracts finish thickness
- Returns: "3'-6" clear"

User asks "where does this door go?" →
- Dimension on drawing shows: centerline is 4'-0" from corner
- Framer knows exactly where to mark

---

## Rough Algorithm (Paper Output)

```
1. Get LOD level from viewport scale
2. Get current reference point (property corner, building corner)
3. For each dimension group (exterior, partitions, openings):
   a. Query shared library for centerlines
   b. Build dimension chains (group by wall run, by zone)
   c. Calculate dimension values from reference
   d. Format strings per project units
4. Place dimension graphics:
   a. Exterior dims outside building
   b. Interior dims grouped logically
   c. Opening dims on wall or nearby
5. Output to drawing
```

---

## Rough Algorithm (VR Layout)

```
1. Determine construction phase → select reference point
2. Query shared library for relevant centerlines/corners
3. Transform to site coordinate system (RTK GPS, local grid)
4. Filter by current task (foundation corners? wall centerlines? opening locations?)
5. Pass coordinates to VR system
6. VR places markers at each point
7. Worker snaps lines / sets forms / frames to markers
```

---

## Open Questions (Remaining)

### 1. Dimension Chain Grouping
- How to determine which walls form a chain?
- By wall run (continuous exterior)? By zone? By room adjacency?

### 2. Automatic Placement
- Where do dimension lines go? How far offset?
- Stacking multiple chains?
- Collision avoidance with annotations?

### 3. Units and Precision
- Imperial: feet-inches, fractions (1/2", 1/4", 1/8")?
- Metric: mm? cm? m?
- Per-project setting in schema metadata

### 4. Phase-Based Filtering
- Does the system know what construction phase you're in?
- Or does user select "foundation dims" vs "framing dims"?

---

## Summary

- **Dimension centerlines**, not faces
- **Compute everything else** from centerline + thickness
- **Reference point changes by phase** (property → building)
- **VR layout needs RTK precision**, not phone GPS
- **Dimensions locate things**, area labels size rooms
- **Shared library is the source** — plan generator and VR both query it

---

## Next Steps

- [ ] Define dimension chain grouping logic
- [ ] Finalize LOD mapping with centerline approach
- [ ] Prototype auto-placement algorithm
- [ ] Define phase-based reference point switching
- [ ] Test with sample project
