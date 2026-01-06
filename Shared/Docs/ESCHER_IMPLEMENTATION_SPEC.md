# Escher UX — Implementation Specification

Technical specification for the gravity triangle and LOD system. Everything agents need to implement the interface.

---

## System Overview

Two independent axes control the view:

1. **Elevation (LOD)** — How abstract. Vertical position above model.
2. **Gravity** — Whose truth. Blend of Design/Client/Build perspectives.

Both affect rendering. Both interpolate smoothly. Both are always active.

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ViewState                                                 │
│   ├── elevation: number (meters above model)               │
│   ├── lod: number (1-5, computed from elevation)           │
│   ├── lod_transition: number (0-1, blend to next LOD)      │
│   └── gravity: GravityState                                │
│       ├── design: number (0-1)                             │
│       ├── client: number (0-1)                             │
│       └── build: number (0-1)                              │
│                                                             │
│   ViewState → RenderEngine → Per-element render properties │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 1: Data Structures

### 1.1 Core Types

```typescript
// Gravity blend state (barycentric coordinates in triangle)
interface GravityState {
  design: number;  // 0.0 - 1.0
  client: number;  // 0.0 - 1.0
  build: number;   // 0.0 - 1.0
  // INVARIANT: design + client + build === 1.0
}

// Complete view state
interface ViewState {
  // Camera position
  elevation: number;           // meters above model origin
  camera_position: Vector3;    // full 3D position
  camera_target: Vector3;      // look-at point
  
  // Computed LOD
  lod: LODLevel;               // 1-5 discrete
  lod_transition: number;      // 0-1 blend to next level
  
  // Gravity
  gravity: GravityState;
}

// LOD levels
enum LODLevel {
  TOPOLOGY = 1,      // Blobs
  WALLS = 2,         // Walls, doors, windows
  FIXTURES = 3,      // Fixtures, annotations
  VIEWPORTS = 4,     // 2D drawing generation
  DOCUMENTATION = 5  // Specs, codes, permits
}

// Element types in the model
enum ElementType {
  BLOB = 'blob',
  RELATIONSHIP = 'relationship',
  WALL = 'wall',
  DOOR = 'door',
  WINDOW = 'window',
  FIXTURE = 'fixture',
  FURNITURE = 'furniture',
  ANNOTATION = 'annotation',
  DIMENSION = 'dimension',
  COORDINATE_MARKER = 'coordinate_marker',
  VIEWPORT = 'viewport',
  SPECIFICATION = 'specification',
  LIGHT_ANALYTICAL = 'light_analytical',
  LIGHT_REALISTIC = 'light_realistic',
  MATERIAL = 'material',
  GRID_LINE = 'grid_line',
  CONTROL_POINT = 'control_point'
}

// Render modes
enum RenderMode {
  HIDDEN = 'hidden',
  WIREFRAME = 'wireframe',
  SOLID = 'solid',
  TEXTURED = 'textured',
  GHOSTED = 'ghosted',
  TAGGED = 'tagged',        // solid with specification labels
  ICON = 'icon'             // simplified symbol
}

// Per-element render properties
interface RenderProperties {
  visible: boolean;
  opacity: number;              // 0.0 - 1.0
  render_mode: RenderMode;
  color_override: Color | null;
  show_label: boolean;
  label_text: string | null;
  show_coordinates: boolean;
  interactive: boolean;         // can select/drag
  highlight_on_hover: boolean;
}

// Element with computed render state
interface RenderableElement {
  id: string;
  type: ElementType;
  geometry: Geometry;           // from shared library
  base_properties: RenderProperties;
  computed_properties: RenderProperties;  // after gravity + LOD applied
}
```

### 1.2 Configuration Tables

```typescript
// Gravity properties per element type
// Values at each corner of the triangle
interface GravityPropertyTable {
  [ElementType.BLOB]: {
    design: RenderProperties;
    client: RenderProperties;
    build: RenderProperties;
  };
  // ... for each element type
}

// LOD visibility per element type
interface LODVisibilityTable {
  [ElementType.BLOB]: {
    [LODLevel.TOPOLOGY]: VisibilityState;
    [LODLevel.WALLS]: VisibilityState;
    // ... for each LOD
  };
  // ... for each element type
}

enum VisibilityState {
  FULL = 'full',           // fully visible
  FADING_IN = 'fading_in', // transitioning to visible
  FADING_OUT = 'fading_out', // transitioning to hidden
  HIDDEN = 'hidden'        // not rendered
}
```

---

## Part 2: Gravity System

### 2.1 Gravity Property Table

Complete table defining render properties at each gravity corner.

```typescript
const GRAVITY_PROPERTIES: GravityPropertyTable = {
  
  [ElementType.BLOB]: {
    design: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.SOLID,
      color_override: null,  // use relationship color
      show_label: true,
      label_text: 'room_name',
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    }
  },

  [ElementType.RELATIONSHIP]: {
    design: {
      visible: true,
      opacity: 0.8,
      render_mode: RenderMode.SOLID,
      color_override: null,  // green/blue/yellow/red by type
      show_label: true,
      label_text: 'relationship_type',
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    }
  },

  [ElementType.WALL]: {
    design: {
      visible: true,
      opacity: 0.7,
      render_mode: RenderMode.WIREFRAME,
      color_override: { r: 100, g: 100, b: 100 },
      show_label: false,
      label_text: null,
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,  // use material
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TAGGED,
      color_override: { r: 200, g: 200, b: 200 },
      show_label: true,
      label_text: 'wall_spec',  // "2x6 @ 406mm OC"
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.DOOR]: {
    design: {
      visible: true,
      opacity: 0.8,
      render_mode: RenderMode.ICON,
      color_override: { r: 50, g: 100, b: 200 },
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.SOLID,
      color_override: { r: 150, g: 100, b: 50 },
      show_label: true,
      label_text: 'door_spec',  // "D01 - 900x2100"
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.WINDOW]: {
    design: {
      visible: true,
      opacity: 0.8,
      render_mode: RenderMode.ICON,
      color_override: { r: 100, g: 200, b: 255 },
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.SOLID,
      color_override: { r: 150, g: 200, b: 255 },
      show_label: true,
      label_text: 'window_spec',  // "W01 - 1200x1500, sill 900"
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.FIXTURE]: {
    design: {
      visible: true,
      opacity: 0.3,
      render_mode: RenderMode.GHOSTED,
      color_override: { r: 150, g: 150, b: 150 },
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: true
    },
    build: {
      visible: true,
      opacity: 0.7,
      render_mode: RenderMode.SOLID,
      color_override: { r: 180, g: 180, b: 180 },
      show_label: true,
      label_text: 'fixture_spec',
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.FURNITURE]: {
    design: {
      visible: true,
      opacity: 0.3,
      render_mode: RenderMode.GHOSTED,
      color_override: { r: 150, g: 150, b: 150 },
      show_label: true,
      label_text: 'furniture_type',
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    },
    build: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    }
  },

  [ElementType.COORDINATE_MARKER]: {
    design: {
      visible: true,
      opacity: 0.8,
      render_mode: RenderMode.ICON,
      color_override: { r: 255, g: 100, b: 100 },
      show_label: true,
      label_text: 'coordinate',
      show_coordinates: true,
      interactive: false,
      highlight_on_hover: true
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.ICON,
      color_override: { r: 255, g: 50, b: 50 },
      show_label: true,
      label_text: 'coordinate',
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.LIGHT_ANALYTICAL]: {
    design: {
      visible: true,
      opacity: 0.6,
      render_mode: RenderMode.ICON,  // arrows showing sun direction
      color_override: { r: 255, g: 200, b: 50 },
      show_label: true,
      label_text: 'direction',
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    }
  },

  [ElementType.MATERIAL]: {
    design: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    client: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TEXTURED,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: true
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.TAGGED,
      color_override: null,
      show_label: true,
      label_text: 'material_spec',
      show_coordinates: false,
      interactive: true,
      highlight_on_hover: true
    }
  },

  [ElementType.GRID_LINE]: {
    design: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 0.5,
      render_mode: RenderMode.WIREFRAME,
      color_override: { r: 100, g: 100, b: 255 },
      show_label: true,
      label_text: 'grid_id',  // "A", "B", "1", "2"
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    }
  },

  [ElementType.CONTROL_POINT]: {
    design: {
      visible: true,
      opacity: 0.6,
      render_mode: RenderMode.ICON,
      color_override: { r: 255, g: 150, b: 0 },
      show_label: false,
      label_text: null,
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    },
    client: {
      visible: false,
      opacity: 0.0,
      render_mode: RenderMode.HIDDEN,
      color_override: null,
      show_label: false,
      label_text: null,
      show_coordinates: false,
      interactive: false,
      highlight_on_hover: false
    },
    build: {
      visible: true,
      opacity: 1.0,
      render_mode: RenderMode.ICON,
      color_override: { r: 255, g: 100, b: 0 },
      show_label: true,
      label_text: 'point_id',  // "A", "B", "C"
      show_coordinates: true,
      interactive: true,
      highlight_on_hover: true
    }
  }
};
```

### 2.2 Gravity Interpolation

```typescript
/**
 * Interpolate render properties based on gravity state
 */
function interpolateGravity(
  elementType: ElementType,
  gravity: GravityState
): RenderProperties {
  
  const props = GRAVITY_PROPERTIES[elementType];
  const d = props.design;
  const c = props.client;
  const b = props.build;
  
  const gd = gravity.design;
  const gc = gravity.client;
  const gb = gravity.build;
  
  return {
    visible: (d.visible && gd > 0.1) || 
             (c.visible && gc > 0.1) || 
             (b.visible && gb > 0.1),
    
    opacity: d.opacity * gd + c.opacity * gc + b.opacity * gb,
    
    render_mode: selectRenderMode(d.render_mode, c.render_mode, b.render_mode, gravity),
    
    color_override: interpolateColor(
      d.color_override, c.color_override, b.color_override, gravity
    ),
    
    show_label: (d.show_label && gd > 0.5) ||
                (c.show_label && gc > 0.5) ||
                (b.show_label && gb > 0.5),
    
    label_text: selectLabelText(d.label_text, c.label_text, b.label_text, gravity),
    
    show_coordinates: (d.show_coordinates && gd > 0.3) ||
                      (b.show_coordinates && gb > 0.3),
    
    interactive: (d.interactive && gd > 0.5) ||
                 (c.interactive && gc > 0.5) ||
                 (b.interactive && gb > 0.5),
    
    highlight_on_hover: (d.highlight_on_hover && gd > 0.3) ||
                        (c.highlight_on_hover && gc > 0.3) ||
                        (b.highlight_on_hover && gb > 0.3)
  };
}

/**
 * Select render mode based on dominant gravity
 * Render modes don't blend - pick the dominant one
 */
function selectRenderMode(
  design: RenderMode,
  client: RenderMode,
  build: RenderMode,
  gravity: GravityState
): RenderMode {
  
  // Find dominant gravity
  if (gravity.design >= gravity.client && gravity.design >= gravity.build) {
    return design;
  } else if (gravity.client >= gravity.build) {
    return client;
  } else {
    return build;
  }
}

/**
 * Interpolate colors
 */
function interpolateColor(
  design: Color | null,
  client: Color | null,
  build: Color | null,
  gravity: GravityState
): Color | null {
  
  const colors: { color: Color; weight: number }[] = [];
  
  if (design && gravity.design > 0) {
    colors.push({ color: design, weight: gravity.design });
  }
  if (client && gravity.client > 0) {
    colors.push({ color: client, weight: gravity.client });
  }
  if (build && gravity.build > 0) {
    colors.push({ color: build, weight: gravity.build });
  }
  
  if (colors.length === 0) return null;
  
  let r = 0, g = 0, b = 0, totalWeight = 0;
  for (const c of colors) {
    r += c.color.r * c.weight;
    g += c.color.g * c.weight;
    b += c.color.b * c.weight;
    totalWeight += c.weight;
  }
  
  return {
    r: Math.round(r / totalWeight),
    g: Math.round(g / totalWeight),
    b: Math.round(b / totalWeight)
  };
}
```

---

## Part 3: LOD System

### 3.1 LOD Thresholds

```typescript
// Elevation thresholds (meters above model origin)
const LOD_THRESHOLDS = {
  LOD_1_MIN: 20,     // above 20m = pure LOD 1
  LOD_1_2_TRANSITION: 15,  // 15-20m = transitioning
  LOD_2_MIN: 10,     // 10-15m = pure LOD 2
  LOD_2_3_TRANSITION: 6,   // 6-10m = transitioning  
  LOD_3_MIN: 3,      // 3-6m = pure LOD 3
  LOD_3_4_TRANSITION: 1.5, // 1.5-3m = transitioning
  LOD_4_MIN: 0.5,    // 0.5-1.5m = pure LOD 4
  LOD_4_5_TRANSITION: 0.2, // below 0.5m = transitioning to LOD 5
};

// For monitor: zoom levels map to these elevations
const ZOOM_TO_ELEVATION = {
  0.1: 50,   // very zoomed out
  0.25: 25,
  0.5: 15,
  1.0: 8,
  2.0: 4,
  4.0: 2,
  8.0: 1,
  16.0: 0.5,
  32.0: 0.2  // very zoomed in
};
```

### 3.2 LOD Calculation

```typescript
interface LODState {
  level: LODLevel;
  transition_to: LODLevel | null;
  transition_progress: number;  // 0-1
}

/**
 * Calculate LOD from elevation
 */
function calculateLOD(elevation: number): LODState {
  
  if (elevation >= LOD_THRESHOLDS.LOD_1_MIN) {
    return { level: LODLevel.TOPOLOGY, transition_to: null, transition_progress: 0 };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_1_2_TRANSITION) {
    const progress = 1 - (elevation - LOD_THRESHOLDS.LOD_1_2_TRANSITION) / 
                         (LOD_THRESHOLDS.LOD_1_MIN - LOD_THRESHOLDS.LOD_1_2_TRANSITION);
    return { 
      level: LODLevel.TOPOLOGY, 
      transition_to: LODLevel.WALLS, 
      transition_progress: progress 
    };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_2_MIN) {
    return { level: LODLevel.WALLS, transition_to: null, transition_progress: 0 };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_2_3_TRANSITION) {
    const progress = 1 - (elevation - LOD_THRESHOLDS.LOD_2_3_TRANSITION) / 
                         (LOD_THRESHOLDS.LOD_2_MIN - LOD_THRESHOLDS.LOD_2_3_TRANSITION);
    return { 
      level: LODLevel.WALLS, 
      transition_to: LODLevel.FIXTURES, 
      transition_progress: progress 
    };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_3_MIN) {
    return { level: LODLevel.FIXTURES, transition_to: null, transition_progress: 0 };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_3_4_TRANSITION) {
    const progress = 1 - (elevation - LOD_THRESHOLDS.LOD_3_4_TRANSITION) / 
                         (LOD_THRESHOLDS.LOD_3_MIN - LOD_THRESHOLDS.LOD_3_4_TRANSITION);
    return { 
      level: LODLevel.FIXTURES, 
      transition_to: LODLevel.VIEWPORTS, 
      transition_progress: progress 
    };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_4_MIN) {
    return { level: LODLevel.VIEWPORTS, transition_to: null, transition_progress: 0 };
  }
  
  if (elevation >= LOD_THRESHOLDS.LOD_4_5_TRANSITION) {
    const progress = 1 - (elevation - LOD_THRESHOLDS.LOD_4_5_TRANSITION) / 
                         (LOD_THRESHOLDS.LOD_4_MIN - LOD_THRESHOLDS.LOD_4_5_TRANSITION);
    return { 
      level: LODLevel.VIEWPORTS, 
      transition_to: LODLevel.DOCUMENTATION, 
      transition_progress: progress 
    };
  }
  
  return { level: LODLevel.DOCUMENTATION, transition_to: null, transition_progress: 0 };
}
```

### 3.3 LOD Visibility Table

```typescript
const LOD_VISIBILITY: Record<ElementType, Record<LODLevel, VisibilityState>> = {
  
  [ElementType.BLOB]: {
    [LODLevel.TOPOLOGY]: VisibilityState.FULL,
    [LODLevel.WALLS]: VisibilityState.FADING_OUT,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.HIDDEN,
    [LODLevel.DOCUMENTATION]: VisibilityState.HIDDEN
  },
  
  [ElementType.RELATIONSHIP]: {
    [LODLevel.TOPOLOGY]: VisibilityState.FULL,
    [LODLevel.WALLS]: VisibilityState.FADING_OUT,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.HIDDEN,
    [LODLevel.DOCUMENTATION]: VisibilityState.HIDDEN
  },
  
  [ElementType.WALL]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.DOOR]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.WINDOW]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.FIXTURE]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.FURNITURE]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.ANNOTATION]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.DIMENSION]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.VIEWPORT]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.SPECIFICATION]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.HIDDEN,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.COORDINATE_MARKER]: {
    [LODLevel.TOPOLOGY]: VisibilityState.FULL,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.CONTROL_POINT]: {
    [LODLevel.TOPOLOGY]: VisibilityState.FULL,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.GRID_LINE]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.HIDDEN,
    [LODLevel.FIXTURES]: VisibilityState.HIDDEN,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  },
  
  [ElementType.LIGHT_ANALYTICAL]: {
    [LODLevel.TOPOLOGY]: VisibilityState.FULL,
    [LODLevel.WALLS]: VisibilityState.FULL,
    [LODLevel.FIXTURES]: VisibilityState.FADING_OUT,
    [LODLevel.VIEWPORTS]: VisibilityState.HIDDEN,
    [LODLevel.DOCUMENTATION]: VisibilityState.HIDDEN
  },
  
  [ElementType.LIGHT_REALISTIC]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.FADING_IN,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.HIDDEN
  },
  
  [ElementType.MATERIAL]: {
    [LODLevel.TOPOLOGY]: VisibilityState.HIDDEN,
    [LODLevel.WALLS]: VisibilityState.FADING_IN,
    [LODLevel.FIXTURES]: VisibilityState.FULL,
    [LODLevel.VIEWPORTS]: VisibilityState.FULL,
    [LODLevel.DOCUMENTATION]: VisibilityState.FULL
  }
};
```

### 3.4 LOD Visibility Calculation

```typescript
/**
 * Calculate visibility modifier from LOD state
 */
function calculateLODVisibility(
  elementType: ElementType,
  lodState: LODState
): number {
  
  const currentVis = LOD_VISIBILITY[elementType][lodState.level];
  
  if (!lodState.transition_to) {
    // No transition, return based on current state
    switch (currentVis) {
      case VisibilityState.FULL: return 1.0;
      case VisibilityState.HIDDEN: return 0.0;
      case VisibilityState.FADING_IN: return 0.5;
      case VisibilityState.FADING_OUT: return 0.5;
    }
  }
  
  // In transition - interpolate between states
  const nextVis = LOD_VISIBILITY[elementType][lodState.transition_to];
  const t = lodState.transition_progress;
  
  const currentValue = visibilityToValue(currentVis);
  const nextValue = visibilityToValue(nextVis);
  
  return currentValue * (1 - t) + nextValue * t;
}

function visibilityToValue(vis: VisibilityState): number {
  switch (vis) {
    case VisibilityState.FULL: return 1.0;
    case VisibilityState.HIDDEN: return 0.0;
    case VisibilityState.FADING_IN: return 0.7;
    case VisibilityState.FADING_OUT: return 0.3;
  }
}
```

---

## Part 4: Combined Render Pipeline

### 4.1 Final Property Calculation

```typescript
/**
 * Calculate final render properties for an element
 * Combines gravity interpolation with LOD visibility
 */
function calculateRenderProperties(
  element: RenderableElement,
  viewState: ViewState
): RenderProperties {
  
  // 1. Get gravity-interpolated properties
  const gravityProps = interpolateGravity(element.type, viewState.gravity);
  
  // 2. Calculate LOD state
  const lodState = calculateLOD(viewState.elevation);
  
  // 3. Get LOD visibility modifier
  const lodVisibility = calculateLODVisibility(element.type, lodState);
  
  // 4. Combine: LOD visibility multiplies opacity
  const finalOpacity = gravityProps.opacity * lodVisibility;
  
  // 5. Visibility threshold
  const isVisible = finalOpacity > 0.05;
  
  return {
    ...gravityProps,
    visible: gravityProps.visible && isVisible,
    opacity: finalOpacity
  };
}

/**
 * Process all elements for rendering
 */
function processSceneForRender(
  elements: RenderableElement[],
  viewState: ViewState
): RenderableElement[] {
  
  return elements.map(element => ({
    ...element,
    computed_properties: calculateRenderProperties(element, viewState)
  }));
}
```

### 4.2 Render Loop Integration

```typescript
/**
 * Main render update - called every frame
 */
function updateRender(
  scene: Scene,
  viewState: ViewState,
  deltaTime: number
): void {
  
  // Process all elements
  const renderableElements = processSceneForRender(scene.elements, viewState);
  
  // Update GPU buffers / scene graph
  for (const element of renderableElements) {
    const props = element.computed_properties;
    
    if (!props.visible) {
      scene.hide(element.id);
      continue;
    }
    
    scene.show(element.id);
    scene.setOpacity(element.id, props.opacity);
    scene.setRenderMode(element.id, props.render_mode);
    
    if (props.color_override) {
      scene.setColor(element.id, props.color_override);
    } else {
      scene.useDefaultColor(element.id);
    }
    
    scene.setLabelVisible(element.id, props.show_label);
    scene.setCoordinatesVisible(element.id, props.show_coordinates);
    scene.setInteractive(element.id, props.interactive);
  }
  
  // Update lighting based on dominant gravity
  updateLighting(scene, viewState.gravity);
}

/**
 * Update scene lighting based on gravity
 */
function updateLighting(scene: Scene, gravity: GravityState): void {
  
  // Analytical lighting (design gravity)
  scene.setAnalyticalLightIntensity(gravity.design);
  
  // Realistic lighting (client gravity)
  scene.setRealisticLightIntensity(gravity.client);
  scene.setShadowsEnabled(gravity.client > 0.3);
  scene.setAmbientOcclusion(gravity.client > 0.5);
  
  // Flat lighting (build gravity)
  scene.setFlatLightIntensity(gravity.build * 0.5);
}
```

---

## Part 5: Gravity Triangle UI

### 5.1 Triangle Component

```typescript
interface GravityTriangleConfig {
  // Screen position (center of triangle)
  position: Vector2;
  
  // Size
  radius: number;  // distance from center to vertex
  
  // Visual
  background_opacity: number;
  vertex_labels: boolean;
  show_puck: boolean;
}

class GravityTriangleUI {
  private config: GravityTriangleConfig;
  private vertices: { design: Vector2; client: Vector2; build: Vector2 };
  private puck_position: Vector2;
  private is_dragging: boolean = false;
  
  constructor(config: GravityTriangleConfig) {
    this.config = config;
    this.calculateVertices();
    this.puck_position = this.getCenter();
  }
  
  private calculateVertices(): void {
    const r = this.config.radius;
    const cx = this.config.position.x;
    const cy = this.config.position.y;
    
    // Equilateral triangle, design at top
    this.vertices = {
      design: { x: cx, y: cy - r },
      client: { x: cx - r * 0.866, y: cy + r * 0.5 },
      build: { x: cx + r * 0.866, y: cy + r * 0.5 }
    };
  }
  
  private getCenter(): Vector2 {
    return {
      x: (this.vertices.design.x + this.vertices.client.x + this.vertices.build.x) / 3,
      y: (this.vertices.design.y + this.vertices.client.y + this.vertices.build.y) / 3
    };
  }
  
  /**
   * Convert screen position to barycentric coordinates
   */
  screenToGravity(screen_pos: Vector2): GravityState {
    const p = screen_pos;
    const a = this.vertices.design;
    const b = this.vertices.client;
    const c = this.vertices.build;
    
    const v0 = { x: c.x - a.x, y: c.y - a.y };
    const v1 = { x: b.x - a.x, y: b.y - a.y };
    const v2 = { x: p.x - a.x, y: p.y - a.y };
    
    const dot00 = v0.x * v0.x + v0.y * v0.y;
    const dot01 = v0.x * v1.x + v0.y * v1.y;
    const dot02 = v0.x * v2.x + v0.y * v2.y;
    const dot11 = v1.x * v1.x + v1.y * v1.y;
    const dot12 = v1.x * v2.x + v1.y * v2.y;
    
    const inv_denom = 1 / (dot00 * dot11 - dot01 * dot01);
    const u = (dot11 * dot02 - dot01 * dot12) * inv_denom;
    const v = (dot00 * dot12 - dot01 * dot02) * inv_denom;
    
    // Clamp to triangle
    let build = Math.max(0, Math.min(1, u));
    let client = Math.max(0, Math.min(1, v));
    let design = Math.max(0, 1 - build - client);
    
    // Normalize
    const sum = design + client + build;
    design /= sum;
    client /= sum;
    build /= sum;
    
    return { design, client, build };
  }
  
  /**
   * Convert barycentric coordinates to screen position
   */
  gravityToScreen(gravity: GravityState): Vector2 {
    return {
      x: gravity.design * this.vertices.design.x +
         gravity.client * this.vertices.client.x +
         gravity.build * this.vertices.build.x,
      y: gravity.design * this.vertices.design.y +
         gravity.client * this.vertices.client.y +
         gravity.build * this.vertices.build.y
    };
  }
  
  /**
   * Handle mouse/touch input
   */
  onPointerDown(pos: Vector2): void {
    if (this.isInsideTriangle(pos)) {
      this.is_dragging = true;
      this.updatePuck(pos);
    }
  }
  
  onPointerMove(pos: Vector2): void {
    if (this.is_dragging) {
      this.updatePuck(pos);
    }
  }
  
  onPointerUp(): void {
    this.is_dragging = false;
  }
  
  private updatePuck(pos: Vector2): void {
    // Clamp to triangle
    const gravity = this.screenToGravity(pos);
    this.puck_position = this.gravityToScreen(gravity);
  }
  
  private isInsideTriangle(pos: Vector2): boolean {
    const gravity = this.screenToGravity(pos);
    return gravity.design >= 0 && gravity.client >= 0 && gravity.build >= 0;
  }
  
  /**
   * Get current gravity state
   */
  getGravity(): GravityState {
    return this.screenToGravity(this.puck_position);
  }
  
  /**
   * Set gravity state (e.g., from preset)
   */
  setGravity(gravity: GravityState): void {
    this.puck_position = this.gravityToScreen(gravity);
  }
  
  /**
   * Render the triangle UI
   */
  render(ctx: RenderContext): void {
    // Background triangle
    ctx.beginPath();
    ctx.moveTo(this.vertices.design.x, this.vertices.design.y);
    ctx.lineTo(this.vertices.client.x, this.vertices.client.y);
    ctx.lineTo(this.vertices.build.x, this.vertices.build.y);
    ctx.closePath();
    ctx.fillStyle = `rgba(50, 50, 50, ${this.config.background_opacity})`;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
    ctx.stroke();
    
    // Vertex labels
    if (this.config.vertex_labels) {
      ctx.fillStyle = 'white';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Design', this.vertices.design.x, this.vertices.design.y - 10);
      ctx.fillText('Client', this.vertices.client.x - 10, this.vertices.client.y + 20);
      ctx.fillText('Build', this.vertices.build.x + 10, this.vertices.build.y + 20);
    }
    
    // Puck
    if (this.config.show_puck) {
      ctx.beginPath();
      ctx.arc(this.puck_position.x, this.puck_position.y, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'white';
      ctx.fill();
      ctx.strokeStyle = 'black';
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }
}
```

### 5.2 Presets

```typescript
const GRAVITY_PRESETS = {
  design: { design: 1.0, client: 0.0, build: 0.0 },
  client: { design: 0.0, client: 1.0, build: 0.0 },
  build: { design: 0.0, client: 0.0, build: 1.0 },
  
  design_client: { design: 0.5, client: 0.5, build: 0.0 },
  client_build: { design: 0.0, client: 0.5, build: 0.5 },
  design_build: { design: 0.5, client: 0.0, build: 0.5 },
  
  balanced: { design: 0.333, client: 0.333, build: 0.334 }
};

// Keyboard shortcuts
const GRAVITY_SHORTCUTS = {
  'KeyD': 'design',
  'KeyC': 'client', 
  'KeyB': 'build',
  'Digit1': 'design',
  'Digit2': 'client',
  'Digit3': 'build',
  'Digit0': 'balanced'
};
```

---

## Part 6: Transition System

### 6.1 Animated Transitions

```typescript
interface Transition<T> {
  from: T;
  to: T;
  duration_ms: number;
  elapsed_ms: number;
  easing: EasingFunction;
}

type EasingFunction = (t: number) => number;

const EASING = {
  linear: (t: number) => t,
  easeInOut: (t: number) => t < 0.5 
    ? 2 * t * t 
    : 1 - Math.pow(-2 * t + 2, 2) / 2,
  easeOut: (t: number) => 1 - Math.pow(1 - t, 2)
};

class TransitionManager {
  private gravity_transition: Transition<GravityState> | null = null;
  private current_gravity: GravityState = GRAVITY_PRESETS.design;
  
  /**
   * Start animated transition to new gravity
   */
  transitionTo(target: GravityState, duration_ms: number = 400): void {
    this.gravity_transition = {
      from: { ...this.current_gravity },
      to: target,
      duration_ms,
      elapsed_ms: 0,
      easing: EASING.easeInOut
    };
  }
  
  /**
   * Set gravity immediately (no animation)
   */
  setImmediate(target: GravityState): void {
    this.current_gravity = target;
    this.gravity_transition = null;
  }
  
  /**
   * Update transition state
   */
  update(delta_ms: number): GravityState {
    if (!this.gravity_transition) {
      return this.current_gravity;
    }
    
    this.gravity_transition.elapsed_ms += delta_ms;
    
    const t = Math.min(1, this.gravity_transition.elapsed_ms / this.gravity_transition.duration_ms);
    const eased_t = this.gravity_transition.easing(t);
    
    this.current_gravity = this.interpolateGravityState(
      this.gravity_transition.from,
      this.gravity_transition.to,
      eased_t
    );
    
    if (t >= 1) {
      this.gravity_transition = null;
    }
    
    return this.current_gravity;
  }
  
  private interpolateGravityState(from: GravityState, to: GravityState, t: number): GravityState {
    return {
      design: from.design + (to.design - from.design) * t,
      client: from.client + (to.client - from.client) * t,
      build: from.build + (to.build - from.build) * t
    };
  }
  
  /**
   * Check if currently transitioning
   */
  isTransitioning(): boolean {
    return this.gravity_transition !== null;
  }
}
```

### 6.2 Transition Timing

```typescript
const TRANSITION_CONFIG = {
  // Gravity changes
  gravity_preset_switch: 400,    // ms - clicking preset button
  gravity_drag: 0,               // ms - dragging puck (immediate)
  gravity_keyboard: 300,         // ms - keyboard shortcut
  
  // LOD changes (zoom-driven, usually smooth)
  lod_scroll_smoothing: 100,     // ms - momentum smoothing
  
  // Element fade in/out
  element_fade_in: 300,          // ms
  element_fade_out: 200,         // ms - slightly faster out
  
  // Minimum visible time (prevent flickering)
  min_visible_duration: 150      // ms
};
```

---

## Part 7: VR Specifics

### 7.1 VR Input Mapping

```typescript
interface VRInputMapping {
  // Movement
  head_position: Vector3;        // direct camera position
  
  // Gravity control options
  gravity_control: 'hand_panel' | 'radial_menu' | 'voice';
  
  // Hand panel: triangle floats near non-dominant hand
  // Radial menu: trigger opens menu, joystick selects
  // Voice: "design mode", "client mode", "build mode"
}

/**
 * Map VR head height to LOD
 */
function vrHeadPositionToLOD(head_y: number, model_origin_y: number): number {
  const elevation = head_y - model_origin_y;
  return elevation;  // direct mapping to elevation
}

/**
 * VR gravity panel - attached to wrist
 */
class VRGravityPanel {
  private triangle: GravityTriangleUI;
  private attached_hand: 'left' | 'right' = 'left';
  private offset: Vector3 = { x: 0.1, y: 0.05, z: -0.1 };
  
  updatePosition(hand_position: Vector3, hand_rotation: Quaternion): void {
    // Position triangle panel relative to hand
    const panel_position = transformPoint(this.offset, hand_position, hand_rotation);
    this.triangle.setWorldPosition(panel_position);
    this.triangle.setWorldRotation(hand_rotation);
  }
  
  onPinch(pinch_position: Vector3): void {
    // Ray from pinch to panel, find intersection
    const local_pos = this.worldToLocal(pinch_position);
    this.triangle.onPointerDown(local_pos);
  }
}
```

### 7.2 VR-Specific Thresholds

```typescript
// VR uses real-world scale
const VR_LOD_THRESHOLDS = {
  // Standing on ground floor = LOD 3 (fixtures)
  // Floating at ceiling height = LOD 2 (walls)
  // Bird's eye (10m+) = LOD 1 (topology)
  
  LOD_1_MIN: 10,      // meters - drone view
  LOD_2_MIN: 3,       // meters - elevated view
  LOD_3_MIN: 0,       // meters - standing inside
  LOD_4_MIN: -0.5,    // meters - crouching / detail view
  LOD_5_MIN: -1       // meters - documentation (sitting at desk metaphor)
};
```

---

## Part 8: Monitor Specifics

### 8.1 Monitor Input Mapping

```typescript
interface MonitorInputMapping {
  // Camera
  scroll: 'zoom',                    // scroll wheel zooms
  middle_drag: 'pan',                // middle mouse pans
  right_drag: 'orbit',               // right mouse orbits
  
  // Gravity
  triangle_click: 'set_gravity',     // click in triangle UI
  keyboard_d: 'preset_design',
  keyboard_c: 'preset_client',
  keyboard_b: 'preset_build',
  
  // Quick toggle
  tab: 'cycle_gravity'               // tab cycles through presets
}

/**
 * Map zoom level to virtual elevation
 */
function zoomToElevation(zoom: number): number {
  // Logarithmic mapping
  // zoom 1.0 = default view ≈ 8m elevation
  // zoom 0.5 = zoomed out ≈ 15m
  // zoom 2.0 = zoomed in ≈ 4m
  
  const base_elevation = 8;
  return base_elevation / zoom;
}
```

### 8.2 Monitor UI Layout

```typescript
const MONITOR_UI_LAYOUT = {
  gravity_triangle: {
    position: 'bottom_right',
    margin: 20,
    radius: 50,
    show_labels: true
  },
  
  lod_indicator: {
    position: 'bottom_right',
    above: 'gravity_triangle',
    margin: 10,
    show_level: true,
    show_name: true  // "Topology", "Walls", etc.
  },
  
  gravity_presets: {
    position: 'bottom_right',
    below: 'gravity_triangle',
    buttons: ['D', 'C', 'B'],
    show_shortcuts: true
  }
};
```

---

## Part 9: Testing & Validation

### 9.1 Unit Tests

```typescript
describe('GravityState', () => {
  it('should always sum to 1.0', () => {
    const state = { design: 0.5, client: 0.3, build: 0.2 };
    expect(state.design + state.client + state.build).toBeCloseTo(1.0);
  });
  
  it('should interpolate correctly at corners', () => {
    const props = interpolateGravity(ElementType.BLOB, { design: 1, client: 0, build: 0 });
    expect(props.opacity).toBe(1.0);
    expect(props.visible).toBe(true);
  });
  
  it('should hide blobs in client gravity', () => {
    const props = interpolateGravity(ElementType.BLOB, { design: 0, client: 1, build: 0 });
    expect(props.opacity).toBe(0.0);
    expect(props.visible).toBe(false);
  });
  
  it('should blend correctly at midpoints', () => {
    const props = interpolateGravity(ElementType.WALL, { design: 0.5, client: 0.5, build: 0 });
    expect(props.opacity).toBeCloseTo(0.85);  // (0.7 + 1.0) / 2
  });
});

describe('LODState', () => {
  it('should return LOD 1 at high elevation', () => {
    const lod = calculateLOD(25);
    expect(lod.level).toBe(LODLevel.TOPOLOGY);
  });
  
  it('should transition between LOD 1 and 2', () => {
    const lod = calculateLOD(17);
    expect(lod.level).toBe(LODLevel.TOPOLOGY);
    expect(lod.transition_to).toBe(LODLevel.WALLS);
    expect(lod.transition_progress).toBeGreaterThan(0);
  });
});

describe('GravityTriangleUI', () => {
  it('should convert screen to barycentric correctly', () => {
    const triangle = new GravityTriangleUI({ 
      position: { x: 100, y: 100 }, 
      radius: 50 
    });
    
    // At design vertex
    const designGravity = triangle.screenToGravity({ x: 100, y: 50 });
    expect(designGravity.design).toBeCloseTo(1.0, 1);
  });
  
  it('should round-trip gravity to screen and back', () => {
    const triangle = new GravityTriangleUI({ 
      position: { x: 100, y: 100 }, 
      radius: 50 
    });
    
    const original = { design: 0.5, client: 0.3, build: 0.2 };
    const screen = triangle.gravityToScreen(original);
    const recovered = triangle.screenToGravity(screen);
    
    expect(recovered.design).toBeCloseTo(original.design, 2);
    expect(recovered.client).toBeCloseTo(original.client, 2);
    expect(recovered.build).toBeCloseTo(original.build, 2);
  });
});
```

### 9.2 Visual Validation Checklist

```markdown
## Manual Testing Checklist

### Gravity Triangle
- [ ] Puck stays inside triangle when dragging
- [ ] Clicking corner snaps to pure gravity
- [ ] Keyboard shortcuts work (D, C, B)
- [ ] Transition animation is smooth (no snapping)
- [ ] Labels visible and readable

### Gravity Blending
- [ ] Design gravity: blobs visible, walls wireframe, no materials
- [ ] Client gravity: blobs hidden, walls textured, realistic light
- [ ] Build gravity: coordinates visible, specifications shown
- [ ] 50/50 blends show both elements appropriately
- [ ] No elements pop in/out suddenly

### LOD Transitions
- [ ] Zooming smoothly transitions between LODs
- [ ] Blobs fade out when transitioning to LOD 2
- [ ] Fixtures fade in when transitioning to LOD 3
- [ ] No flickering during transitions

### Combined
- [ ] LOD and gravity work independently
- [ ] Can be at LOD 1 in any gravity
- [ ] Can be at LOD 3 in any gravity
- [ ] Opacity stacks correctly (gravity × LOD)
```

---

## Summary

Agents have:

1. **Data structures** — GravityState, ViewState, RenderProperties, element types
2. **Gravity property table** — exact values for each element at each gravity corner
3. **LOD visibility table** — what's visible at each LOD
4. **Interpolation functions** — gravity blending, LOD transitions
5. **Triangle UI component** — barycentric math, input handling, rendering
6. **Transition system** — animated state changes with easing
7. **VR specifics** — head position mapping, hand panel
8. **Monitor specifics** — zoom mapping, keyboard shortcuts
9. **Test cases** — unit tests and manual checklist

This is everything needed to implement the Escher UX system.

---

*Document version: 1.0*
