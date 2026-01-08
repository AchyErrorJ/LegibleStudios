# QBD Algebra: Formal System Specification (v2.0)

The mathematical foundation of Question Based Design. This document defines the rules, structures, and operations that turn natural language into valid building designs.

---

## Overview

QBD Algebra is the formal system that sits between the LLM and the output schema. It guarantees consistency, validity, and determinism — things the LLM cannot guarantee on its own.

LLM (translator) → Fragments → QBD Algebra (brain) → Valid Schema

**The LLM proposes. The formal system validates and solves.**

---

## Core Principles

1. **Template-driven:** JSON structure is fixed; LLM fills values, not structure.
2. **Deterministic:** Same inputs always produce same outputs.
3. **Validated:** Every state change is checked; invalid states are rejected.
4. **Traceable:** Every output value traces back to an input.
5. **Explainable:** Conflicts and tradeoffs are reported in structured form.

---

## Part 1: JSON Template Structure

The schema template defines all possible structure. The LLM fills values but cannot change the core structure.

### Master Template (v2.0)


json
{
  "version": "2.0.0",
  "metadata": {
    "project_name": null,
    "branch_id": "main",
    "parent_version_id": null,
    "units": "metric",
    "code_jurisdiction": null
  },
  "site": {
    "width": null,
    "depth": null,
    "setbacks": {
      "front": null, "rear": null, "left": null, "right": null
    },
    "zoning": {
      "max_coverage": null,
      "max_far": null,
      "max_height": null
    },
    "orientation": {
      "front_faces": null
    },
    "features": [],
    "views": []
  },
  "rooms": [],
  "adjacencies": [],
  "separations": [],
  "priorities": {
    "natural_light": 5,
    "privacy": 5,
    "open_plan": 5,
    "circulation_efficiency": 5,
    "mep_clustering": 5,
    "structural_simplicity": 5
  },
  "constraints": {
    "footprint_max": null,
    "footprint_min": null,
    "stories_max": 2,
    "budget_max": null,
    "accessibility": "none"
  },
  "character": {
    "style": null,
    "keywords": [],
    "avoid": []
  }
}
`

Room Template

When a room is added, it uses this structure:
JSON

{
  "id": null,
  "name": null,
  "type": null,
  "level": null,
  "area_min": null,
  "area_max": null,
  "aspect_ratio": {"min": 1.0, "max": 2.5},
  "furniture": [],
  "features": [],
  "constraints": {
    "pinned": false,
    "locked_properties": []
  }
}

Adjacency Template (Refined)
JSON

{
  "room_a": null,
  "room_b": null,
  "strength": "required",
  "connection_type": "open",
  "axis": "horizontal" 
}

Note: axis supports horizontal (same floor) or vertical (stacked rooms).
Part 2: Fragment Types

Fragments are atomic actions emitted by the LLM to modify state.
Core Fragments

    add_room / remove_room / update_room: Standard room management.

    add_furniture: Triggers room size derivation.

    set_adjacency / set_separation: Defines spatial relationships.

Advanced Fragments (v2.0)

    pin_element: {"action": "pin_element", "type": "wall", "coordinates": [...]}. Used for renovations to lock existing structures.

    mark_demo: Marks existing site features or walls for removal.

    surgical_reduction: System-generated fragments to resolve UNSATISFIABLE states by applying targeted area reductions.

Part 3: Validation Rules

Every state change triggers validation. Invalid states are rejected with structured feedback.
Regulatory Validation (v2.0)
Rule	Check	Error Code
Lot Coverage	(Footprint / Site Area) <= Max Coverage	ZONING_LIMIT_COVERAGE
FAR	(Total Floor Area / Site Area) <= FAR Limit	ZONING_LIMIT_FAR
Height Envelope	(Stories * Ceiling Height) <= Max Height	ZONING_LIMIT_HEIGHT
Structural & Logical Validation
Rule	Check	Error
No contradiction	Cannot be both adjacent and separated	CONTRADICTION
Load Path	2nd floor heavy walls must align with support below	STRUCTURAL_INVALID_PATH
Area sum	sum(room_min_areas) <= footprint_max	PROGRAM_EXCEEDS_FOOTPRINT
Part 4: Derivation Rules

Derivations compute implied values from inputs.
Room Area Requirement (Amin​)

Derived from furniture footprints and required clearances:
Amin​=(1+β)⋅i=1∑n​(Bi​+Ci​)

    β: Buffer factor (0.10 - 0.20 based on room type).

    Bi​: Bounding box area of furniture item i.

    Ci​: Required clearance area for item i.

Circulation Topology & Efficiency (Ec​)

The system calculates a "Circulation Graph" where every room must have a valid path to the Entry node.
Ec​=Total Building Area∑Room Areas​

    Ec​>0.90: High efficiency (minimal hallways).

    Ec​<0.75: Low efficiency (triggers warning).

Part 5: Conflict Resolution
Unsatisfiable (Surgical Reductions)

When the program exceeds the footprint or budget, the system generates alternatives:

    Option A: Reduce all Bedrooms by 12% (Saves X m²).

    Option B: Remove lowest priority room (e.g., "Guest Room").

Tradeoffs

Occur when multiple valid solutions exist but satisfy different priorities (e.g., Kitchen vs Office for south light).
Part 6: Solver Stages

The solver turns the validated state into a placed layout.
Stage 1: Constraint Propagation

Eliminate impossible configurations (e.g., room area > corner space).
Stage 2: Advanced Search

    Wave Function Collapse (WFC): Treats the floor plan as a grid of possibilities that collapse based on adjacency logic.

    Rectangular Duals: Converts the adjacency graph into a floor plan of rectangles to guarantee required connections.

Stage 3: Optimization & MEP Clustering

The scoring function now includes MEP Clustering (Cwet​):

    High priority for clustering "wet" rooms (Kitchen, Bath, Laundry) horizontally or vertically (stacking) to minimize plumbing costs.

Part 7: State Lifecycle (Branching)

EMPTY → ACCUMULATING → COMPLETE → SOLVED 
                                    │
                                    └───► FORKED (Branch A / B)
                                             │
                                             └───► LOCKED (Confirmed)

    FORKED: Occurs when exploring tradeoffs without losing current state.

    LOCKED: Design is frozen; changes require an explicit versioned unlock.

Part 8: Structural Algebra

The solver enforces physical feasibility through span constraints (Lspan​):

    Max Span: If a room width exceeds a standard structural span (e.g., 6m for timber), the system must insert an internal support node (beam/column).

    Vertical Alignment: Points are awarded when 2nd-floor walls align with 1st-floor structural supports.

Part 9: Question Generation

Questions emerge dynamically from the state to resolve blocking issues or high-impact ambiguities.
Critical Questions (Minimum Viable Design)
Question	Why Required
Bedroom count/Household	Initial room count
Site size / Budget	Size boundary
One story or two?	Stacking vs Spreading
Zoning/FAR Limits	Legal feasibility
Part 10: Defaults (v2.0 Regional)
Region	Units	Ceiling Height	Typical Setbacks (F/R/S)
North America	Imperial/Metric	2.44m (8')	7.5m / 6m / 1.5m
Europe	Metric	2.50m	Variable by jurisdiction
Summary

QBD Algebra v2.0 is a feasibility engine that ensures what the LLM proposes is buildable, legal, and cost-effective. It bridges the gap between natural language desire and architectural reality.
