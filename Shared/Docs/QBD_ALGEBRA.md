
# QBD Algebra: Formal System Specification

The mathematical foundation of Question Based Design. This document defines the rules, structures, and operations that turn natural language into valid building designs.

---

## Overview

QBD Algebra is the formal system that sits between the LLM and the output schema. It guarantees consistency, validity, and determinism — things the LLM cannot guarantee on its own.

```
LLM (translator) → Fragments → QBD Algebra (brain) → Valid Schema
```

**The LLM proposes. The formal system validates and solves.**

---

## Core Principles

1. **Template-driven:** JSON structure is fixed; LLM fills values, not structure
2. **Deterministic:** Same inputs always produce same outputs
3. **Validated:** Every state change is checked; invalid states are rejected
4. **Traceable:** Every output value traces back to an input
5. **Explainable:** Conflicts and tradeoffs are reported in structured form

---

## Part 1: JSON Template Structure

The schema template defines all possible structure. The LLM can only:
- Fill `null` values
- Append to arrays
- Cannot add new keys
- Cannot change structure

### Master Template

```json
{
  "version": "1.0.0",
  "metadata": {
    "project_name": null,
    "project_type": null,
    "units": "metric",
    "code_jurisdiction": null
  },
  "site": {
    "width": null,
    "depth": null,
    "setbacks": {
      "front": null,
      "rear": null,
      "left": null,
      "right": null
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
    "outdoor_connection": 5,
    "views": 5,
    "minimize_hallways": 5,
    "compact_footprint": 5
  },
  "constraints": {
    "footprint_max": null,
    "footprint_min": null,
    "stories_max": null,
    "budget_max": null,
    "accessibility": "none"
  },
  "character": {
    "style": null,
    "keywords": [],
    "avoid": []
  },
  "extensions": {}
}
```

### Room Template

When a room is added, it uses this structure:

```json
{
  "id": null,
  "name": null,
  "type": null,
  "level": null,
  "area_min": null,
  "area_max": null,
  "width_min": null,
  "width_max": null,
  "length_min": null,
  "length_max": null,
  "ceiling_height": null,
  "furniture": [],
  "features": [],
  "window_preferences": {
    "orientation": null,
    "priority": "normal"
  },
  "constraints": {
    "pinned": false,
    "locked_properties": []
  }
}
```

### Furniture Template

```json
{
  "type": null,
  "size": null,
  "width": null,
  "length": null,
  "clearance": {
    "front": null,
    "back": null,
    "left": null,
    "right": null
  },
  "placement": null
}
```

### Adjacency Template

```json
{
  "room_a": null,
  "room_b": null,
  "strength": "required",
  "connection_type": "open"
}
```

### Separation Template

```json
{
  "room_a": null,
  "room_b": null,
  "strength": "required",
  "buffer": null
}
```

### Site Feature Template

```json
{
  "type": null,
  "location": {"x": null, "y": null},
  "dimensions": {},
  "protect": false,
  "notes": null
}
```

### View Template

```json
{
  "direction": null,
  "quality": null,
  "description": null
}
```

---

## Part 2: Fragment Types

Fragments are atomic actions the LLM emits. Each fragment modifies state in one specific way.

### Room Fragments

**add_room**
```json
{
  "action": "add_room",
  "room": {
    "name": "Kitchen",
    "type": "kitchen"
  }
}
```
- Creates new room entry from template
- Generates unique ID
- Applies type defaults

**remove_room**
```json
{
  "action": "remove_room",
  "room_id": "room-kitchen-001"
}
```
- Removes room and all references to it
- Cascades to adjacencies/separations

**update_room**
```json
{
  "action": "update_room",
  "room_id": "room-kitchen-001",
  "updates": {
    "area_min": 180,
    "area_max": 220
  }
}
```
- Modifies existing room properties
- Only specified fields change

### Furniture Fragments

**add_furniture**
```json
{
  "action": "add_furniture",
  "room_id": "room-bedroom-001",
  "furniture": {
    "type": "bed",
    "size": "queen",
    "clearance": {"left": 36, "right": 36, "foot": 36}
  }
}
```
- Adds furniture to room
- Triggers room size derivation

**remove_furniture**
```json
{
  "action": "remove_furniture",
  "room_id": "room-bedroom-001",
  "furniture_index": 0
}
```

### Relationship Fragments

**set_adjacency**
```json
{
  "action": "set_adjacency",
  "room_a": "room-kitchen-001",
  "room_b": "room-living-001",
  "strength": "required",
  "connection_type": "open"
}
```
- Strength: "required" | "preferred" | "optional"
- Connection type: "open" | "door" | "visual"

**remove_adjacency**
```json
{
  "action": "remove_adjacency",
  "room_a": "room-kitchen-001",
  "room_b": "room-living-001"
}
```

**set_separation**
```json
{
  "action": "set_separation",
  "room_a": "room-bedroom-001",
  "room_b": "room-living-001",
  "strength": "preferred"
}
```

### Site Fragments

**set_site**
```json
{
  "action": "set_site",
  "updates": {
    "width": 60,
    "depth": 120,
    "setbacks": {"front": 25, "rear": 20, "left": 5, "right": 5},
    "orientation": {"front_faces": "south"}
  }
}
```

**add_site_feature**
```json
{
  "action": "add_site_feature",
  "feature": {
    "type": "existing_tree",
    "location": {"x": 45, "y": 80},
    "dimensions": {"radius": 15},
    "protect": true
  }
}
```

**add_view**
```json
{
  "action": "add_view",
  "view": {
    "direction": "north",
    "quality": "good",
    "description": "Mountain view"
  }
}
```

### Constraint Fragments

**set_constraint**
```json
{
  "action": "set_constraint",
  "target": "footprint_max",
  "value": 2000
}
```

**set_priority**
```json
{
  "action": "set_priority",
  "factor": "natural_light",
  "value": 9
}
```

### Character Fragments

**set_style**
```json
{
  "action": "set_style",
  "style": "modern",
  "keywords": ["clean", "minimal"],
  "avoid": ["busy rooflines"]
}
```

### Control Fragments

**pin_room**
```json
{
  "action": "pin_room",
  "room_id": "room-living-001",
  "locked_properties": ["position", "dimensions"]
}
```

**unpin_room**
```json
{
  "action": "unpin_room",
  "room_id": "room-living-001"
}
```

---

## Part 3: Validation Rules

Every state change triggers validation. Invalid states are rejected with explanation.

### Structural Validation

| Rule | Check | Error |
|------|-------|-------|
| Required fields | Room must have name and type | "Room missing required field: {field}" |
| Valid references | Adjacency rooms must exist | "Adjacency references unknown room: {id}" |
| Valid enums | Strength must be required/preferred/optional | "Invalid strength value: {value}" |
| Valid ranges | area_min <= area_max | "Invalid area range: min > max" |
| Unique IDs | No duplicate room IDs | "Duplicate room ID: {id}" |

### Logical Validation

| Rule | Check | Error |
|------|-------|-------|
| No self-reference | Room cannot be adjacent to itself | "Room cannot be adjacent to itself" |
| No contradiction | Cannot have both adjacency and separation between same rooms | "Contradiction: {a} and {b} are both adjacent and separated" |
| Dependency | Ensuite requires parent bedroom | "Ensuite {id} has no parent bedroom" |

### Feasibility Validation

| Rule | Check | Warning/Error |
|------|-------|---------------|
| Area sum | sum(room_min_areas) <= footprint_max | "Program exceeds footprint by {x} m²" |
| Buildable rooms | room dimensions >= minimum buildable | "Room {id} too small to build: {x} m²" |
| Site fit | building footprint fits in setbacks | "Building exceeds buildable area" |

### Validation Response

```json
{
  "valid": false,
  "errors": [
    {
      "type": "contradiction",
      "message": "Kitchen and Living Room are both adjacent and separated",
      "fragments_involved": ["set_adjacency:3", "set_separation:7"],
      "resolution_options": [
        "Remove adjacency requirement",
        "Remove separation requirement"
      ]
    }
  ],
  "warnings": [
    {
      "type": "tight_fit",
      "message": "Program is 95% of footprint limit, circulation may be tight"
    }
  ]
}
```

---

## Part 4: Derivation Rules

Derivations compute implied values from inputs. They run after validation, before solving.

### Room Size from Furniture

```
room.area_min = sum(furniture.bounds) + sum(furniture.clearances) + buffer

where:
  furniture.bounds = furniture.width * furniture.length
  buffer = room.type.default_buffer (10-20% depending on type)
```

**Example:**
```
Queen bed: 1525mm x 2030mm = 3.1 m²
Clearances: 900mm left + 900mm right + 900mm foot = 3.3 m²
Dresser: 500mm x 1500mm = 0.75 m² + 900mm front clearance = 1.2 m²
Buffer: 15%

room.area_min = (3.1 + 3.3 + 1.2) * 1.15 = 8.7 m²
→ rounds to 9 m² or ~3m x 3m
```

### Room Dimensions from Area

```
if room.width_min and room.length_min:
  use specified
else:
  derive from area using aspect ratio rules:
    - bedrooms: 1:1 to 1:1.3
    - living rooms: 1:1.2 to 1:1.6
    - kitchens: 1:1 to 1:2
    - bathrooms: 1:1 to 1:2
```

### Circulation Factor

```
total_area_required = sum(room.area_min) * circulation_factor

where circulation_factor:
  - open_plan high: 1.10 (minimal hallways)
  - balanced: 1.15
  - defined_rooms high: 1.20 (more hallways)
```

### Window Orientation Priority

```
for each room:
  if room.window_preferences.orientation specified:
    use specified
  else if room.type in [bedroom]:
    prefer east (morning light)
  else if room.type in [living, kitchen]:
    prefer south/west (afternoon light)
  
  weight by priorities.natural_light
```

### Adjacency Graph

Build graph of relationships:

```
Nodes: rooms
Edges: 
  - adjacency (required) = must share wall
  - adjacency (preferred) = should share wall, can sacrifice
  - separation (required) = must not share wall
  - separation (preferred) = should not share wall, can sacrifice
```

This graph feeds the solver.

---

## Part 5: Conflict Types

When the system cannot proceed, it reports the conflict type and options.

### Contradiction

Two inputs directly oppose each other.

```json
{
  "type": "contradiction",
  "description": "Cannot satisfy both constraints",
  "constraint_a": "adjacent(Kitchen, Living Room)",
  "constraint_b": "separate(Kitchen, Living Room)",
  "resolution": "User must remove one constraint"
}
```

### Unsatisfiable

Constraints cannot all be met simultaneously.

```json
{
  "type": "unsatisfiable",
  "description": "Program does not fit in footprint",
  "details": {
    "program_required": 205,
    "footprint_max": 185,
    "overage": 20
  },
  "resolution_options": [
    {"action": "increase_footprint", "to": 205},
    {"action": "reduce_room", "room": "Bedroom 3", "by": 9},
    {"action": "reduce_room", "room": "Living Room", "by": 9},
    {"action": "remove_room", "room": "Office"}
  ]
}
```

Note: All area values in m².

### Underdetermined

Not enough information to produce unique solution.

```json
{
  "type": "underdetermined",
  "description": "Cannot determine room sizes",
  "missing": [
    "No furniture or area specified for: Living Room, Kitchen",
    "No site dimensions specified"
  ],
  "resolution": "Provide furniture lists or area ranges for rooms"
}
```

### Tradeoff

Multiple valid solutions exist; priorities don't clearly decide.

```json
{
  "type": "tradeoff",
  "description": "Kitchen and Office both prefer southeast corner",
  "options": [
    {
      "id": "option_a",
      "description": "Kitchen gets SE corner",
      "sacrifice": "Office gets north-facing window",
      "priority_score": 7.2
    },
    {
      "id": "option_b", 
      "description": "Office gets SE corner",
      "sacrifice": "Kitchen gets north-facing window",
      "priority_score": 6.8
    }
  ],
  "resolution": "User selects preferred option or adjusts priorities"
}
```

---

## Part 6: Solver Stages

The solver turns validated state into a placed layout.

### Stage 1: Constraint Propagation

Eliminate impossible configurations before searching.

**Operations:**
- If `separate(A, B)` required → A and B cannot share edge
- If `adjacent(A, B)` required → A and B must share edge
- If room needs east window → room must be on east side of building
- If room area > X → room cannot fit in corner less than X

**Output:** Reduced possibility space for each room

### Stage 2: Search

Generate candidate layouts within reduced space.

**Approaches:**
- Grid-based placement (snap rooms to grid)
- Constraint satisfaction (backtracking search)
- Generative (propose placements, check validity)

**For each candidate:**
- Check all adjacency requirements met
- Check all separation requirements met
- Check rooms fit in footprint
- Check setbacks respected

**Output:** Set of valid candidate layouts

### Stage 3: Optimization

Score candidates against priorities.

**Scoring function:**
```
score = sum(priority_weight[i] * satisfaction[i])

where satisfaction is 0-1 for each factor:
  - natural_light: how well are window preferences met?
  - privacy: are private rooms away from street?
  - circulation_efficiency: how short are paths between related rooms?
  - views: are rooms with view preference on view side?
  - etc.
```

**Output:** Ranked candidates

### Stage 4: Selection

Pick best candidate or present options.

**If clear winner (score gap > threshold):**
- Return best layout

**If close scores:**
- Return top 2-3 as options with tradeoff explanation

**If no valid candidates:**
- Return unsatisfiable error with diagnosis

### Solver Output

```json
{
  "status": "solved",
  "layout": {
    "rooms": [
      {
        "id": "room-kitchen-001",
        "position": {"x": 0, "y": 0},
        "dimensions": {"width": 12, "length": 15},
        "rotation": 0
      }
    ],
    "building_footprint": {...},
    "circulation": [...]
  },
  "score": 8.2,
  "score_breakdown": {
    "natural_light": 0.9,
    "privacy": 0.8,
    "circulation_efficiency": 0.7
  },
  "tradeoffs_made": [
    "Office placed north side to give kitchen south exposure"
  ]
}
```

---

## Part 7: State Lifecycle

State progresses through defined stages.

```
EMPTY → ACCUMULATING → COMPLETE → SOLVED → LOCKED
```

### EMPTY

Initial state. Template with all nulls.

**Allowed:** Any fragment
**Not allowed:** Solve

### ACCUMULATING

Fragments being added. Not yet complete enough to solve.

**Allowed:** Any fragment
**Triggers:** Validation after each fragment
**Not allowed:** Solve (underdetermined)

### COMPLETE

Minimum required inputs present. Can attempt solve.

**Requirements for COMPLETE:**
- At least one room defined
- Site dimensions specified (for new construction)
- Or existing conditions captured (for renovation)

**Allowed:** Any fragment, Solve
**Triggers:** Validation, Derivation

### SOLVED

Valid layout produced.

**Contains:** Full layout with positions and dimensions
**Allowed:** Fragments (triggers re-solve), Lock
**Not allowed:** Nothing

### LOCKED

Design confirmed. Changes require explicit unlock.

**Allowed:** View only, Export
**Not allowed:** Fragments without unlock
**Unlock:** Creates new version, moves to SOLVED state

### Version History

Each solve creates a version:

```json
{
  "versions": [
    {
      "version": 1,
      "timestamp": "2024-01-15T10:30:00Z",
      "state": "SOLVED",
      "fragments_count": 23,
      "score": 7.8
    },
    {
      "version": 2,
      "timestamp": "2024-01-15T11:45:00Z",
      "state": "LOCKED",
      "fragments_count": 26,
      "score": 8.2,
      "changes_from_previous": ["Added office", "Increased kitchen size"]
    }
  ]
}
```

---

## Part 8: Error Responses

Standardized error format for all failure modes.

### Error Structure

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_FAILED",
    "type": "contradiction",
    "message": "Human readable description",
    "details": {...},
    "fragment_id": "fragment-042",
    "resolution_options": [...],
    "help": "Explanation of what went wrong and how to fix"
  }
}
```

### Error Codes

| Code | Meaning |
|------|---------|
| INVALID_FRAGMENT | Fragment doesn't match expected structure |
| VALIDATION_FAILED | State would be invalid after applying fragment |
| CONTRADICTION | Two constraints directly conflict |
| UNSATISFIABLE | Constraints cannot all be met |
| UNDERDETERMINED | Not enough information to solve |
| SOLVER_FAILED | Solver could not find valid layout |
| LOCKED_STATE | Cannot modify locked design |
| UNKNOWN_REFERENCE | Fragment references non-existent entity |

### LLM Translation Guide

For each error type, how the LLM should present it:

**CONTRADICTION:**
> "There's a conflict in your requirements — you asked for the kitchen to be open to the living room, but also separate from it. Which do you prefer?"

**UNSATISFIABLE:**
> "The rooms you've described add up to about 205 square metres, but you set a 185 square metre limit. We could either increase the limit, make some rooms smaller, or remove a room. What would you like to do?"

**UNDERDETERMINED:**
> "I need a bit more information before I can generate a layout. Could you tell me about the furniture in your living room, or give me a rough size for that space?"

---

## Part 9: Defaults

When values aren't specified, use sensible defaults.

### Room Type Defaults

| Type | Default Area | Default Features | Default Adjacencies |
|------|--------------|------------------|---------------------|
| bedroom | 11 m² | closet | bathroom (preferred) |
| primary_bedroom | 19 m² | closet, ensuite | ensuite (required) |
| bathroom | 5 m² | toilet, sink, tub/shower | - |
| ensuite | 6 m² | toilet, sink, shower | parent bedroom (required) |
| powder_room | 2.5 m² | toilet, sink | entry (preferred) |
| kitchen | 14 m² | sink, stove, fridge | living (preferred), dining (preferred) |
| living | 23 m² | seating | entry (preferred) |
| dining | 11 m² | table | kitchen (preferred) |
| office | 9 m² | desk | - |
| laundry | 4 m² | washer, dryer | - |
| garage_1car | 22 m² | - | entry (preferred) |
| garage_2car | 41 m² | - | entry (preferred) |
| mudroom | 5 m² | hooks, bench | entry (required), garage (preferred) |

### Furniture Defaults

| Furniture | Size (mm) | Clearances (mm) |
|-----------|-----------|-----------------|
| twin_bed | 965 x 1905 | 900 sides, 900 foot |
| full_bed | 1370 x 1905 | 900 sides, 900 foot |
| queen_bed | 1525 x 2030 | 900 sides, 900 foot |
| king_bed | 1930 x 2030 | 900 sides, 900 foot |
| sofa_2seat | 1525 x 915 | 900 front, 0 back |
| sofa_3seat | 2135 x 915 | 900 front, 0 back |
| sectional | 3050 x 2440 | 900 front, 0 back |
| dining_4 | 1220 x 915 | 900 all sides |
| dining_6 | 1830 x 915 | 900 all sides |
| dining_8 | 2440 x 1065 | 900 all sides |
| desk | 1525 x 760 | 900 front, 600 sides |
| dresser | 1525 x 510 | 900 front |
| toilet | 760 x 510 | 450 sides, 600 front |
| vanity_single | 915 x 560 | 760 front |
| vanity_double | 1525 x 560 | 760 front |
| tub | 1525 x 815 | 760 access side |
| shower | 915 x 915 | 760 entry |

### Priority Defaults

All priorities default to 5 (neutral) on 1-10 scale.

### Constraint Defaults

| Constraint | Default |
|------------|---------|
| footprint_max | none (unlimited) |
| stories_max | 2 |
| accessibility | none |
| ceiling_height | 2.44m (8') |
| code_jurisdiction | user locale |

### Regional Defaults

System can adjust defaults by region:

**Canada:**
- Units: metric
- Setbacks: 7.5m front, 6m rear, 1.5m sides (varies by jurisdiction)
- Ceiling height: 2.44m

**Europe:**
- Units: metric  
- Setbacks: varies significantly
- Ceiling height: 2.5m

**United States:**
- Units: imperial (can override to metric)
- Setbacks: 7.5m front, 6m rear, 1.5m sides (varies by jurisdiction)
- Ceiling height: 2.44m

---

## Summary

QBD Algebra is:

1. **Template-driven:** Fixed structure, LLM fills values
2. **Fragment-based:** Atomic actions modify state
3. **Validated:** Every change checked for consistency
4. **Derived:** Implied values computed automatically
5. **Solved:** Search + optimization produces layout
6. **Explainable:** Conflicts and tradeoffs reported clearly
7. **Generative:** Questions produced dynamically from state

The LLM is the interface. The formal system is the authority.

---

## Part 10: Question Generation

The question generator is the inverse of fragment processing. Instead of taking answers and updating state, it reads state and produces the next best questions to ask.

### The Feedback Loop

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Questions ←──── Question Generator ←───┐                 │
│       │                                   │                 │
│       ▼                                   │                 │
│   User Answers                            │                 │
│       │                                   │                 │
│       ▼                                   │                 │
│   LLM translates to Fragments             │                 │
│       │                                   │                 │
│       ▼                                   │                 │
│   Fragment Processor                      │                 │
│   (validate, derive, accumulate)          │                 │
│       │                                   │                 │
│       ▼                                   │                 │
│   State (schema in progress) ─────────────┘                 │
│       │                                                     │
│       ▼                                                     │
│   Solver (when state is COMPLETE)                          │
│       │                                                     │
│       ▼                                                     │
│   Design Output                                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

The system asks what it needs to know. No predefined rounds — questions emerge from the state.

### Question Properties

Each potential question has:

```json
{
  "id": "q_bed_size_primary",
  "text": "What size bed in the primary bedroom?",
  "text_fr": "Quelle taille de lit dans la chambre principale?",
  "category": "rooms",
  "target_field": "rooms[primary_bedroom].furniture[bed].size",
  "dependencies": ["rooms[primary_bedroom] exists"],
  "impact": {
    "fields_resolved": ["rooms[primary_bedroom].area_min"],
    "solver_unblocked": true,
    "priority_affected": ["space"]
  },
  "options": [
    {"value": "twin", "label": "Twin / Simple"},
    {"value": "full", "label": "Full / Double"},
    {"value": "queen", "label": "Queen"},
    {"value": "king", "label": "King"}
  ],
  "default": "queen",
  "follow_ups": ["q_bed_clearance", "q_dresser"]
}
```

### Question Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| **household** | Who lives here | Adults, kids, pets, accessibility |
| **program** | What rooms needed | Bedrooms, office, guest room |
| **rooms** | Room specifics | Furniture, size, features |
| **relationships** | How rooms connect | Adjacencies, separations, zones |
| **site** | Where it goes | Orientation, lot, setbacks |
| **priorities** | What matters most | Light, privacy, space, cost |
| **character** | How it feels | Style, ceiling height, openness |
| **details** | Specific decisions | Closet type, outlet placement |

### Generation Algorithm

```python
def generate_questions(state, max_questions=10):
    
    # 1. Get all possible questions
    all_questions = get_question_pool()
    
    # 2. Filter by dependencies
    available = [q for q in all_questions 
                 if dependencies_met(q, state)]
    
    # 3. Filter out already answered
    unanswered = [q for q in available 
                  if not already_answered(q, state)]
    
    # 4. Score each question
    scored = []
    for q in unanswered:
        score = calculate_score(q, state)
        scored.append((q, score))
    
    # 5. Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    # 6. Balance categories (don't ask 10 kitchen questions)
    balanced = balance_categories(scored, max_questions)
    
    # 7. Return top questions
    return balanced[:max_questions]
```

### Scoring Function

Questions are scored by how valuable the answer would be:

```python
def calculate_score(question, state):
    score = 0
    
    # Solver blocking (highest weight)
    if blocks_solver(question, state):
        score += 100
    
    # High impact on design
    impact = estimate_impact(question, state)
    score += impact * 50  # 0-1 scale
    
    # Resolves ambiguity
    if reduces_solution_space(question, state):
        score += 30
    
    # Related to recent answers (conversational flow)
    if related_to_recent(question, state):
        score += 20
    
    # No good default available
    if not has_good_default(question):
        score += 15
    
    # User indicated interest in this area
    if user_expressed_interest(question, state):
        score += 10
    
    return score
```

### Blocking Detection

A question blocks the solver if the solver cannot proceed without it:

```python
def blocks_solver(question, state):
    # Simulate state without this answer
    # Try to run solver
    # If solver fails with UNDERDETERMINED, it's blocking
    
    required_for_solve = [
        "rooms[*] exists",           # Need at least one room
        "constraints.footprint_max OR site.dimensions",  # Need size boundary
        "rooms[*].area_min derivable"  # Need room sizes
    ]
    
    return question.target_field in required_for_solve
```

### Impact Estimation

How much does this answer change the design?

```python
def estimate_impact(question, state):
    # High impact questions
    high_impact = [
        "constraints.stories_max",      # 1 vs 2 story changes everything
        "priorities.open_plan",         # Affects all adjacencies
        "rooms[primary_bedroom].area",  # Largest room
        "site.orientation"              # Affects all window placement
    ]
    
    # Medium impact
    medium_impact = [
        "rooms[*].furniture",           # Sizes one room
        "adjacencies[*]",               # Affects placement
        "priorities.*"                  # Shifts optimization
    ]
    
    # Low impact
    low_impact = [
        "rooms[*].features",            # Nice to have
        "character.*"                   # Aesthetic only
    ]
    
    if question.target_field matches high_impact:
        return 1.0
    elif question.target_field matches medium_impact:
        return 0.5
    else:
        return 0.2
```

### Category Balancing

Don't overwhelm with questions from one category:

```python
def balance_categories(scored_questions, max_questions):
    result = []
    category_counts = {}
    max_per_category = max(2, max_questions // 4)
    
    for question, score in scored_questions:
        cat = question.category
        if category_counts.get(cat, 0) < max_per_category:
            result.append(question)
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        if len(result) >= max_questions:
            break
    
    return result
```

### Adaptive Follow-ups

When a user answers, the system may immediately surface related questions:

```python
def get_follow_ups(answered_question, answer, state):
    follow_ups = []
    
    # Direct follow-ups defined on question
    for fq_id in answered_question.follow_ups:
        follow_ups.append(get_question(fq_id))
    
    # Conditional follow-ups based on answer
    if answered_question.id == "q_work_from_home":
        if answer == "yes_with_clients":
            follow_ups.append(get_question("q_office_entrance"))
            follow_ups.append(get_question("q_waiting_area"))
    
    if answered_question.id == "q_kids_count":
        if answer >= 2:
            follow_ups.append(get_question("q_jack_and_jill"))
            follow_ups.append(get_question("q_playroom"))
    
    return follow_ups
```

### Skipping and Defaults

Every question can be skipped:

```python
def handle_skip(question, state):
    # Apply default value
    default_value = question.default
    
    # Mark as assumption in audit trail
    state.assumptions.append({
        "question": question.id,
        "default_used": default_value,
        "timestamp": now(),
        "can_revisit": True
    })
    
    # Apply the default as a fragment
    fragment = create_fragment_from_default(question, default_value)
    process_fragment(fragment, state)
    
    # May ask again later with more context
    state.skipped_questions.append(question.id)
```

### Revisiting Assumptions

Later, the system may revisit skipped questions:

```python
def should_revisit(question, state):
    # More context now available
    if has_more_context(question, state):
        return True
    
    # Design is nearly complete, confirming assumptions
    if state.lifecycle == "COMPLETE":
        return True
    
    # User is in related area of design
    if user_focus_matches(question, state):
        return True
    
    return False
```

Example:
- Round 1: "How many cars?" → Skipped → Default: 2
- Round 4: "Your design has a 2-car garage. Keep it, or change?"

### Question Generation by State

| State | Question Focus |
|-------|----------------|
| EMPTY | Household, basic program |
| ACCUMULATING (early) | Room needs, relationships |
| ACCUMULATING (mid) | Site, priorities |
| ACCUMULATING (late) | Filling gaps, resolving ambiguity |
| COMPLETE | Confirming assumptions, details |
| SOLVED | Refinements, "is this right?" |
| LOCKED | No questions (design frozen) |

### Output Format

Questions presented to user:

```json
{
  "round": 3,
  "questions": [
    {
      "id": "q_bed_size_primary",
      "text": "What size bed in the primary bedroom?",
      "why": "This determines the minimum room size",
      "options": ["Twin", "Full", "Queen", "King"],
      "default": "Queen",
      "can_skip": true,
      "impact": "high"
    },
    {
      "id": "q_open_plan",
      "text": "Open plan kitchen/living, or separate rooms?",
      "why": "This affects how spaces connect",
      "options": ["Open plan", "Separate", "Partial (island divider)"],
      "default": "Open plan",
      "can_skip": true,
      "impact": "high"
    }
  ],
  "minimum_to_answer": 5,
  "design_preview_available": true
}
```

### Integration with LLM

The LLM can rephrase questions conversationally:

**System question:**
```json
{
  "id": "q_bed_clearance",
  "text": "Bed accessible from both sides, or one side against wall?"
}
```

**LLM to user:**
> "Do you and your partner both need to get in and out of bed easily, or is it okay if one side is against the wall?"

**User response:**
> "We both get up at different times, so both sides."

**LLM translates to fragment:**
```json
{
  "action": "add_furniture",
  "room_id": "room-primary-bedroom",
  "furniture": {
    "type": "bed",
    "size": "queen",
    "clearance": {"left": 900, "right": 900, "foot": 900}
  }
}
```

### Minimum Viable Questions

To generate *any* design, minimum answers needed:

| Question | Why Required |
|----------|--------------|
| Who lives here? (or bedroom count) | Room count |
| Site size OR budget OR footprint max | Size boundary |
| One story or two? | Stacking vs spreading |

Everything else has derivable defaults. With just these 3 answers, the system can generate a starter design.

### The "Just Show Me Something" Path

User can say "just generate something" at any point:

```python
def generate_with_defaults(state):
    # Apply all defaults for unanswered questions
    for question in get_unanswered(state):
        apply_default(question, state)
    
    # Mark all as assumptions
    state.assumptions_bulk = True
    
    # Run solver
    return solve(state)
```

Result: A complete design built on assumptions. User can then react: "Make the kitchen bigger" triggers questions about kitchen specifically.

---

## Next Steps

- [ ] Implement template structures
- [ ] Build fragment parser and validator
- [ ] Implement derivation rules
- [ ] Prototype constraint propagation
- [ ] Prototype search algorithm
- [ ] Implement scoring/optimization
- [ ] Build error response system
- [ ] Build question generator
- [ ] Implement question scoring algorithm
- [ ] Test with sample projects
- [ ] Iterate based on team review
