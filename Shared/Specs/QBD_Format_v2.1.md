# QBD Building Format Specification v2.1

## Overview

This specification extends the QBD (Quick Building Data) JSON format with:
- Version control and edit tracking
- Coordinate system metadata
- Parametric roof definitions tied to wall bounds
- Scene objects with anchor references
- Global building transform

These additions ensure spatial coherence when editing across multiple applications.

---

## 1. Root Metadata

### 1.1 Format Version

```json
{
  "format_version": "2.1",
  "format_name": "qbd",
  ...
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `format_version` | string | Yes | Semantic version of format spec |
| `format_name` | string | Yes | Always "qbd" |

### 1.2 Edit Tracking

```json
{
  "edit_history": {
    "created": {
      "timestamp": "2025-12-23T10:30:00Z",
      "application": "archengine_kernel",
      "version": "1.0.0"
    },
    "last_modified": {
      "timestamp": "2025-12-23T14:45:00Z",
      "application": "cad_editor",
      "version": "2.1.0"
    },
    "revision": 3
  },
  ...
}
```

| Field | Type | Description |
|-------|------|-------------|
| `created.timestamp` | ISO 8601 | When file was first created |
| `created.application` | string | Application that created the file |
| `created.version` | string | Version of creating application |
| `last_modified.*` | - | Same fields for last edit |
| `revision` | integer | Incremented on each save |

---

## 2. Coordinate System

### 2.1 Definition

```json
{
  "coordinate_system": {
    "origin": [0, 0, 0],
    "up_axis": "Y",
    "forward_axis": "Z",
    "handedness": "right",
    "unit": "mm"
  },
  ...
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `origin` | [x,y,z] | [0,0,0] | World origin for building |
| `up_axis` | "X"\|"Y"\|"Z" | "Y" | Vertical axis |
| `forward_axis` | "X"\|"Y"\|"Z" | "Z" | Forward/depth axis |
| `handedness` | "left"\|"right" | "right" | Coordinate handedness |
| `unit` | string | "mm" | Linear unit (mm, cm, m, in, ft) |

### 2.2 Axis Convention

Standard QBD coordinate system:
- **X**: Width (left-right)
- **Y**: Height (up-down)
- **Z**: Depth (front-back)
- **Handedness**: Right-handed
- **Origin**: Southwest corner at ground level

```
        Y (up)
        |
        |
        +------ X (width)
       /
      /
     Z (depth)
```

---

## 3. Building Transform

### 3.1 Global Transform

All building elements inherit from this transform. External applications should modify this rather than individual element coordinates.

```json
{
  "building_transform": {
    "position": [0, 0, 0],
    "rotation": [0, 0, 0],
    "scale": 1.0
  },
  ...
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `position` | [x,y,z] | [0,0,0] | World position offset |
| `rotation` | [rx,ry,rz] | [0,0,0] | Euler rotation in degrees (applied Y,X,Z order) |
| `scale` | float | 1.0 | Uniform scale factor |

### 3.2 Transform Application

When rendering or exporting:
1. Compute local element positions
2. Apply `building_transform` to all positions
3. Scene objects with anchors resolve anchors first, then apply building transform

---

## 4. Wall Bounds Reference

### 4.1 Computed Bounds

Viewers/editors compute wall bounds from `walls_batch`:

```
wall_bounds = {
  min_x: minimum X of all exterior wall endpoints,
  max_x: maximum X of all exterior wall endpoints,
  min_z: minimum Z of all exterior wall endpoints,
  max_z: maximum Z of all exterior wall endpoints,
  width: max_x - min_x,
  depth: max_z - min_z,
  center: [(min_x + max_x) / 2, 0, (min_z + max_z) / 2]
}
```

Only walls with `category: "exterior"` are used for bounds calculation.

### 4.2 Named Anchors

Pre-defined anchor points derived from wall bounds:

| Anchor Name | Position |
|-------------|----------|
| `wall_bounds.center` | Center of bounding box |
| `wall_bounds.sw` | Southwest corner (min_x, 0, min_z) |
| `wall_bounds.se` | Southeast corner (max_x, 0, min_z) |
| `wall_bounds.nw` | Northwest corner (min_x, 0, max_z) |
| `wall_bounds.ne` | Northeast corner (max_x, 0, max_z) |
| `wall_bounds.s` | South center (center_x, 0, min_z) |
| `wall_bounds.n` | North center (center_x, 0, max_z) |
| `wall_bounds.e` | East center (max_x, 0, center_z) |
| `wall_bounds.w` | West center (min_x, 0, center_z) |

---

## 5. Parametric Roofs

### 5.1 Bound-Relative Roof Definition

Instead of absolute vertex coordinates, roofs can be defined parametrically:

```json
{
  "roofs": [
    {
      "id": "roof_1",
      "type": "hip",
      "definition": "parametric",

      "base_reference": "wall_bounds",
      "base_elevation": 2700,
      "overhang": 600,
      "pitch": 6,

      "ridge": {
        "axis": "Z",
        "offset_ratio": 0.5,
        "start_ratio": 0.3,
        "end_ratio": 0.7
      },

      "material": "asphalt_shingle",
      "level_name": "Roof Level"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `definition` | "parametric"\|"explicit" | How roof is defined |
| `base_reference` | string | Reference for base shape ("wall_bounds") |
| `base_elevation` | float | Y height of eave line |
| `overhang` | float | Distance past wall bounds |
| `pitch` | int | Roof pitch (rise per 12 run) |
| `ridge.axis` | "X"\|"Z" | Ridge runs along this axis |
| `ridge.offset_ratio` | float | 0-1, position across perpendicular axis |
| `ridge.start_ratio` | float | 0-1, where ridge starts along axis |
| `ridge.end_ratio` | float | 0-1, where ridge ends along axis |

### 5.2 Explicit Roof Definition (Legacy)

For complex roofs or manual edits, explicit vertices are still supported:

```json
{
  "roofs": [
    {
      "id": "roof_1",
      "type": "hip",
      "definition": "explicit",

      "surfaces": [
        {
          "id": "surface_west",
          "vertices": [
            [-600, 2700, -600],
            [7241, 6924, 7241],
            ...
          ],
          "pitch": 6,
          "orientation": "west"
        }
      ],
      ...
    }
  ]
}
```

### 5.3 Roof Computation (Parametric)

For `definition: "parametric"` with `type: "hip"`:

```python
# Compute base rectangle
base = {
  min_x: wall_bounds.min_x - overhang,
  max_x: wall_bounds.max_x + overhang,
  min_z: wall_bounds.min_z - overhang,
  max_z: wall_bounds.max_z + overhang
}

# Compute ridge
if ridge.axis == "Z":
  ridge_x = base.min_x + (base.max_x - base.min_x) * ridge.offset_ratio
  ridge_start = base.min_z + (base.max_z - base.min_z) * ridge.start_ratio
  ridge_end = base.min_z + (base.max_z - base.min_z) * ridge.end_ratio

# Compute ridge height from pitch
run = (wall_bounds.width / 2) + overhang
rise = run * (pitch / 12)
ridge_y = base_elevation + rise

# Generate 4 surfaces for hip roof
# ... vertex generation from base corners and ridge endpoints
```

---

## 6. Scene Objects

### 6.1 Object Definition

```json
{
  "scene_objects": [
    {
      "id": "tree_001",
      "type": "tree",
      "subtype": "deciduous_large",

      "anchor": {
        "reference": "wall_bounds.sw",
        "offset": [-3000, 0, 2000]
      },

      "transform": {
        "rotation": [0, 45, 0],
        "scale": 1.2
      },

      "properties": {
        "species": "oak",
        "height": 8000,
        "canopy_radius": 4000
      }
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `type` | string | Object category (tree, shrub, path, fence, etc.) |
| `subtype` | string | Specific variant |
| `anchor.reference` | string | Named anchor point or element ID |
| `anchor.offset` | [x,y,z] | Offset from anchor in local coords |
| `transform` | object | Local rotation/scale (position from anchor) |
| `properties` | object | Type-specific properties |

### 6.2 Anchor References

Valid anchor references:

| Pattern | Example | Description |
|---------|---------|-------------|
| `wall_bounds.*` | `wall_bounds.ne` | Corner/edge of building bounds |
| `door_N` | `door_0` | Nth door position |
| `window_N` | `window_3` | Nth window position |
| `wall_N.start` | `wall_2.start` | Start point of Nth wall |
| `wall_N.end` | `wall_5.end` | End point of Nth wall |
| `wall_N.center` | `wall_0.center` | Midpoint of Nth wall |
| `room_ID.center` | `room_living.center` | Center of named room |

### 6.3 Path Objects

Paths are defined as polylines with anchor references:

```json
{
  "id": "walkway_001",
  "type": "path",
  "subtype": "concrete_walkway",

  "anchor": {
    "reference": "door_0",
    "offset": [0, 0, 0]
  },

  "points": [
    [0, 0, 0],
    [0, 0, -1500],
    [-2000, 0, -3000],
    [-2000, 0, -6000]
  ],

  "properties": {
    "width": 1200,
    "material": "concrete"
  }
}
```

Points are relative to the resolved anchor position. When building rotates, anchor rotates, and path follows.

---

## 7. Backward Compatibility

### 7.1 Version Detection

Parsers should check `format_version`:
- Missing or < "2.0": Legacy format, absolute coordinates
- "2.0": Added coordinate_system and building_transform
- "2.1": Added parametric roofs and scene_objects

### 7.2 Legacy Roof Handling

If `roofs[].definition` is missing, treat as `"explicit"` and use `surfaces[].vertices` directly.

### 7.3 Missing Metadata

Default values when fields are missing:

```json
{
  "format_version": "1.0",
  "coordinate_system": {
    "origin": [0, 0, 0],
    "up_axis": "Y",
    "forward_axis": "Z",
    "handedness": "right",
    "unit": "mm"
  },
  "building_transform": {
    "position": [0, 0, 0],
    "rotation": [0, 0, 0],
    "scale": 1.0
  }
}
```

---

## 8. Example: Complete v2.1 File

```json
{
  "format_version": "2.1",
  "format_name": "qbd",

  "edit_history": {
    "created": {
      "timestamp": "2025-12-23T10:30:00Z",
      "application": "archengine_kernel",
      "version": "1.0.0"
    },
    "last_modified": {
      "timestamp": "2025-12-23T14:45:00Z",
      "application": "cad_editor",
      "version": "2.1.0"
    },
    "revision": 3
  },

  "coordinate_system": {
    "origin": [0, 0, 0],
    "up_axis": "Y",
    "forward_axis": "Z",
    "handedness": "right",
    "unit": "mm"
  },

  "building_transform": {
    "position": [0, 0, 0],
    "rotation": [0, 0, 0],
    "scale": 1.0
  },

  "building_id": "abc123",
  "width": 14482,
  "depth": 16896,

  "walls_batch": [
    {
      "start": [0, 0, 0],
      "end": [14482, 0, 0],
      "height": 2700,
      "category": "exterior",
      "wall_type": "ext_2x6_r21"
    }
  ],

  "roofs": [
    {
      "id": "roof_1",
      "type": "hip",
      "definition": "parametric",
      "base_reference": "wall_bounds",
      "base_elevation": 2700,
      "overhang": 600,
      "pitch": 6,
      "ridge": {
        "axis": "Z",
        "offset_ratio": 0.5,
        "start_ratio": 0.3,
        "end_ratio": 0.7
      },
      "material": "asphalt_shingle"
    }
  ],

  "scene_objects": [
    {
      "id": "tree_front_left",
      "type": "tree",
      "subtype": "deciduous_medium",
      "anchor": {
        "reference": "wall_bounds.sw",
        "offset": [-4000, 0, -3000]
      },
      "properties": {
        "height": 6000
      }
    },
    {
      "id": "walkway_main",
      "type": "path",
      "subtype": "concrete",
      "anchor": {
        "reference": "door_0",
        "offset": [0, 0, 0]
      },
      "points": [
        [0, 0, 0],
        [0, 0, -2000],
        [0, 0, -5000]
      ],
      "properties": {
        "width": 1200
      }
    }
  ],

  "doors": [],
  "windows": [],
  "rooms": {},
  "wall_types": [],
  "levels": []
}
```

---

## 9. Implementation Notes

### 9.1 For Kernel (Generator)
- Always output `format_version: "2.1"`
- Include `coordinate_system` and `building_transform`
- Generate parametric roofs by default
- Set `edit_history.created` on generation

### 9.2 For UE5 Viewer
- Compute `wall_bounds` from exterior walls on load
- Resolve parametric roofs to explicit vertices for rendering
- Apply `building_transform` to all geometry
- Resolve scene object anchors before applying transform

### 9.3 For External CAD Apps
- Update `edit_history.last_modified` on save
- Increment `revision`
- Modify `building_transform.rotation` instead of rotating individual elements
- Preserve `coordinate_system` - don't change handedness or axes

---

## 10. Migration Guide

### From v1.x to v2.1

1. Add metadata fields with defaults
2. Keep existing `roofs[].surfaces` as `definition: "explicit"`
3. No changes needed to walls, doors, windows, rooms

### Converting Explicit Roof to Parametric

1. Compute wall_bounds from exterior walls
2. Determine overhang from surface vertices vs wall_bounds
3. Calculate pitch from vertex heights
4. Determine ridge axis and position ratios
5. Replace `surfaces` array with parametric fields
