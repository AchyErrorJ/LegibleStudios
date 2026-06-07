# Smart Panel System — Specification

Panels that respond to context. They appear when relevant, fade when not. No manual show/hide. The interface emerges from the state.

---

## Overview

Panel visibility is computed from:

1. **Workflow stage** — LegiQBD, LegiCAD, LegiDoc
2. **LOD level** — What abstraction level you're at
3. **Gravity** — Whose lens (Design/Client/Build)
4. **Selection** — What's currently selected
5. **State** — Schema completeness, solver status
6. **Task** — Active operation (dragging, editing, etc.)

```
Panel.opacity = evaluate_conditions(workflow, lod, gravity, selection, state, task)
```

Panels don't pop. They fade. Same transition system as geometry.

---

## Data Structures

### Panel Definition

```typescript
interface PanelDefinition {
  id: string;
  name: string;
  
  // Position & layout
  default_position: PanelPosition;
  size: PanelSize;
  can_resize: boolean;
  can_move: boolean;
  can_minimize: boolean;
  
  // Visibility conditions
  conditions: PanelConditions;
  
  // Content
  component: ComponentType;  // React/Vue/Svelte component
  props_from_context: string[];  // which context values to pass as props
}

interface PanelPosition {
  anchor: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center' | 'left' | 'right';
  offset: Vector2;
  z_index: number;
}

interface PanelSize {
  width: number | 'auto' | 'fill';
  height: number | 'auto' | 'fill';
  min_width?: number;
  min_height?: number;
  max_width?: number;
  max_height?: number;
}

interface PanelConditions {
  // Workflow
  workflow_stages: WorkflowStage[] | 'all';
  
  // LOD
  lod_min: number;       // 1-5
  lod_max: number;       // 1-5
  
  // Gravity thresholds (show when gravity component exceeds threshold)
  gravity: {
    design_min?: number;   // 0-1, panel shows when design >= this
    design_max?: number;   // 0-1, panel hides when design > this
    client_min?: number;
    client_max?: number;
    build_min?: number;
    build_max?: number;
  } | null;  // null = gravity agnostic
  
  // Selection
  selection: {
    required: boolean;
    element_types?: ElementType[];  // show only when these types selected
    min_count?: number;
    max_count?: number;
  } | null;  // null = no selection requirement
  
  // State
  state: {
    schema_states?: SchemaState[];  // EMPTY, ACCUMULATING, COMPLETE, SOLVED, LOCKED
    requires_unsaved_changes?: boolean;
    requires_conflicts?: boolean;
  } | null;
  
  // Task
  task: {
    during?: TaskType[];     // show during these tasks
    not_during?: TaskType[]; // hide during these tasks
  } | null;
  
  // Custom condition function (escape hatch)
  custom?: (context: PanelContext) => number;  // returns 0-1 opacity modifier
}

enum WorkflowStage {
  LEGI_QBD = 'legi_qbd',
  LEGI_CAD = 'legi_cad',
  LEGI_DOC = 'legi_doc'
}

enum SchemaState {
  EMPTY = 'empty',
  ACCUMULATING = 'accumulating',
  COMPLETE = 'complete',
  SOLVED = 'solved',
  LOCKED = 'locked'
}

enum TaskType {
  IDLE = 'idle',
  DRAGGING_BLOB = 'dragging_blob',
  DRAGGING_WALL = 'dragging_wall',
  DRAGGING_OPENING = 'dragging_opening',
  DRAGGING_FIXTURE = 'dragging_fixture',
  EDITING_TEXT = 'editing_text',
  PLACING_VIEWPORT = 'placing_viewport',
  MEASURING = 'measuring',
  CHATTING = 'chatting'
}
```

### Panel State

```typescript
interface PanelState {
  id: string;
  
  // Computed visibility
  base_opacity: number;      // from conditions (0-1)
  user_minimized: boolean;   // user manually minimized
  final_opacity: number;     // base * (minimized ? 0 : 1), animated
  
  // Current position (may shift to avoid overlap)
  current_position: Vector2;
  current_size: Vector2;
  
  // Animation
  opacity_transition: Transition<number> | null;
  position_transition: Transition<Vector2> | null;
}

interface PanelContext {
  // Current application state
  workflow_stage: WorkflowStage;
  lod: LODState;
  gravity: GravityState;
  selection: Selection;
  schema_state: SchemaState;
  active_task: TaskType;
  
  // Convenience accessors
  selected_elements: RenderableElement[];
  selected_types: ElementType[];
  has_selection: boolean;
  selection_count: number;
}
```

---

## Panel Definitions

### Core Panels (Always Available)

```typescript
const PANEL_CHAT: PanelDefinition = {
  id: 'chat',
  name: 'Chat',
  
  default_position: {
    anchor: 'right',
    offset: { x: -20, y: 0 },
    z_index: 100
  },
  size: {
    width: 360,
    height: 'fill',
    min_width: 300,
    max_width: 500
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: 'all',
    lod_min: 1,
    lod_max: 5,
    gravity: null,  // always visible regardless of gravity
    selection: null,
    state: null,
    task: null
  },
  
  component: ChatPanel,
  props_from_context: ['schema_state', 'selection']
};

const PANEL_GRAVITY_TRIANGLE: PanelDefinition = {
  id: 'gravity_triangle',
  name: 'Gravity',
  
  default_position: {
    anchor: 'bottom-right',
    offset: { x: -20, y: -20 },
    z_index: 200
  },
  size: {
    width: 120,
    height: 140
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: 'all',
    lod_min: 1,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: null
  },
  
  component: GravityTrianglePanel,
  props_from_context: ['gravity']
};

const PANEL_LOD_INDICATOR: PanelDefinition = {
  id: 'lod_indicator',
  name: 'Level of Detail',
  
  default_position: {
    anchor: 'bottom-right',
    offset: { x: -20, y: -170 },
    z_index: 199
  },
  size: {
    width: 120,
    height: 40
  },
  can_resize: false,
  can_move: false,
  can_minimize: false,
  
  conditions: {
    workflow_stages: 'all',
    lod_min: 1,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: null
  },
  
  component: LODIndicatorPanel,
  props_from_context: ['lod']
};
```

### LegiQBD Panels

```typescript
const PANEL_QUESTIONS: PanelDefinition = {
  id: 'questions',
  name: 'Questions',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 0 },
    z_index: 90
  },
  size: {
    width: 400,
    height: 'auto',
    max_height: 600
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_QBD],
    lod_min: 1,
    lod_max: 2,
    gravity: null,
    selection: null,
    state: {
      schema_states: [SchemaState.EMPTY, SchemaState.ACCUMULATING, SchemaState.COMPLETE]
    },
    task: null
  },
  
  component: QuestionsPanel,
  props_from_context: ['schema_state']
};

const PANEL_BLOB_PALETTE: PanelDefinition = {
  id: 'blob_palette',
  name: 'Rooms',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 80
  },
  size: {
    width: 200,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_QBD],
    lod_min: 1,
    lod_max: 1,
    gravity: {
      design_min: 0.3  // needs some design gravity to show
    },
    selection: null,
    state: null,
    task: {
      not_during: [TaskType.CHATTING]
    }
  },
  
  component: BlobPalettePanel,
  props_from_context: []
};

const PANEL_RELATIONSHIP_TOOLS: PanelDefinition = {
  id: 'relationship_tools',
  name: 'Relationships',
  
  default_position: {
    anchor: 'bottom-left',
    offset: { x: 20, y: -20 },
    z_index: 85
  },
  size: {
    width: 250,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_QBD],
    lod_min: 1,
    lod_max: 1,
    gravity: {
      design_min: 0.3
    },
    selection: {
      required: true,
      element_types: [ElementType.BLOB, ElementType.RELATIONSHIP],
      min_count: 1
    },
    state: null,
    task: null
  },
  
  component: RelationshipToolsPanel,
  props_from_context: ['selection', 'selected_elements']
};

const PANEL_SCORE: PanelDefinition = {
  id: 'score',
  name: 'Design Score',
  
  default_position: {
    anchor: 'top-right',
    offset: { x: -20, y: 20 },
    z_index: 75
  },
  size: {
    width: 200,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_QBD, WorkflowStage.LEGI_CAD],
    lod_min: 1,
    lod_max: 3,
    gravity: {
      design_min: 0.2
    },
    selection: null,
    state: {
      schema_states: [SchemaState.ACCUMULATING, SchemaState.COMPLETE, SchemaState.SOLVED]
    },
    task: null
  },
  
  component: ScorePanel,
  props_from_context: ['schema_state']
};
```

### LegiCAD Panels

```typescript
const PANEL_WALL_TOOLS: PanelDefinition = {
  id: 'wall_tools',
  name: 'Wall',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 80
  },
  size: {
    width: 220,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD],
    lod_min: 2,
    lod_max: 4,
    gravity: null,  // works in any gravity
    selection: {
      required: true,
      element_types: [ElementType.WALL]
    },
    state: null,
    task: null
  },
  
  component: WallToolsPanel,
  props_from_context: ['selection', 'selected_elements', 'gravity']
};

const PANEL_OPENING_TOOLS: PanelDefinition = {
  id: 'opening_tools',
  name: 'Opening',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 80
  },
  size: {
    width: 220,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD],
    lod_min: 2,
    lod_max: 4,
    gravity: null,
    selection: {
      required: true,
      element_types: [ElementType.DOOR, ElementType.WINDOW]
    },
    state: null,
    task: null
  },
  
  component: OpeningToolsPanel,
  props_from_context: ['selection', 'selected_elements', 'gravity']
};

const PANEL_FIXTURE_PALETTE: PanelDefinition = {
  id: 'fixture_palette',
  name: 'Fixtures',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 80
  },
  size: {
    width: 250,
    height: 400
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD],
    lod_min: 3,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: {
      not_during: [TaskType.DRAGGING_FIXTURE]
    }
  },
  
  component: FixturePalettePanel,
  props_from_context: []
};

const PANEL_FIXTURE_PROPERTIES: PanelDefinition = {
  id: 'fixture_properties',
  name: 'Fixture Properties',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 81
  },
  size: {
    width: 250,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD],
    lod_min: 3,
    lod_max: 5,
    gravity: null,
    selection: {
      required: true,
      element_types: [ElementType.FIXTURE, ElementType.FURNITURE]
    },
    state: null,
    task: null
  },
  
  component: FixturePropertiesPanel,
  props_from_context: ['selection', 'selected_elements', 'gravity']
};

const PANEL_MATERIAL_PICKER: PanelDefinition = {
  id: 'material_picker',
  name: 'Materials',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 300 },
    z_index: 70
  },
  size: {
    width: 280,
    height: 350
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD],
    lod_min: 2,
    lod_max: 5,
    gravity: {
      client_min: 0.4  // only when client gravity is significant
    },
    selection: {
      required: true,
      element_types: [ElementType.WALL, ElementType.FIXTURE, ElementType.FURNITURE]
    },
    state: null,
    task: null
  },
  
  component: MaterialPickerPanel,
  props_from_context: ['selection', 'selected_elements']
};

const PANEL_COORDINATES: PanelDefinition = {
  id: 'coordinates',
  name: 'Coordinates',
  
  default_position: {
    anchor: 'bottom-left',
    offset: { x: 20, y: -20 },
    z_index: 60
  },
  size: {
    width: 200,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD, WorkflowStage.LEGI_DOC],
    lod_min: 2,
    lod_max: 5,
    gravity: {
      build_min: 0.3  // shows when build gravity is present
    },
    selection: {
      required: true,
      element_types: [ElementType.WALL, ElementType.CONTROL_POINT, ElementType.COORDINATE_MARKER]
    },
    state: null,
    task: null
  },
  
  component: CoordinatesPanel,
  props_from_context: ['selection', 'selected_elements']
};

const PANEL_SPEC_EDITOR: PanelDefinition = {
  id: 'spec_editor',
  name: 'Specifications',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 200 },
    z_index: 65
  },
  size: {
    width: 300,
    height: 'auto'
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_CAD, WorkflowStage.LEGI_DOC],
    lod_min: 3,
    lod_max: 5,
    gravity: {
      build_min: 0.5  // needs significant build gravity
    },
    selection: {
      required: true,
      element_types: [ElementType.WALL, ElementType.DOOR, ElementType.WINDOW, ElementType.FIXTURE]
    },
    state: null,
    task: null
  },
  
  component: SpecEditorPanel,
  props_from_context: ['selection', 'selected_elements']
};
```

### LegiDoc Panels

```typescript
const PANEL_VIEWPORT_TOOLS: PanelDefinition = {
  id: 'viewport_tools',
  name: 'Viewports',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 100 },
    z_index: 80
  },
  size: {
    width: 220,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_DOC],
    lod_min: 4,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: null
  },
  
  component: ViewportToolsPanel,
  props_from_context: []
};

const PANEL_SHEET_MANAGER: PanelDefinition = {
  id: 'sheet_manager',
  name: 'Sheets',
  
  default_position: {
    anchor: 'left',
    offset: { x: 20, y: 250 },
    z_index: 75
  },
  size: {
    width: 250,
    height: 400
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_DOC],
    lod_min: 4,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: null
  },
  
  component: SheetManagerPanel,
  props_from_context: []
};

const PANEL_CODE_CHECKLIST: PanelDefinition = {
  id: 'code_checklist',
  name: 'Code Compliance',
  
  default_position: {
    anchor: 'right',
    offset: { x: -380, y: 20 },  // beside chat
    z_index: 85
  },
  size: {
    width: 300,
    height: 500
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_DOC],
    lod_min: 5,
    lod_max: 5,
    gravity: {
      build_min: 0.3
    },
    selection: null,
    state: null,
    task: null
  },
  
  component: CodeChecklistPanel,
  props_from_context: []
};

const PANEL_SCHEDULE_GENERATOR: PanelDefinition = {
  id: 'schedule_generator',
  name: 'Schedules',
  
  default_position: {
    anchor: 'left',
    offset: { x: 280, y: 100 },
    z_index: 70
  },
  size: {
    width: 350,
    height: 'auto'
  },
  can_resize: true,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_DOC],
    lod_min: 5,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: null,
    task: null
  },
  
  component: ScheduleGeneratorPanel,
  props_from_context: []
};

const PANEL_SIGNOFF: PanelDefinition = {
  id: 'signoff',
  name: 'Sign Off',
  
  default_position: {
    anchor: 'bottom-right',
    offset: { x: -150, y: -20 },
    z_index: 95
  },
  size: {
    width: 250,
    height: 'auto'
  },
  can_resize: false,
  can_move: true,
  can_minimize: true,
  
  conditions: {
    workflow_stages: [WorkflowStage.LEGI_DOC],
    lod_min: 5,
    lod_max: 5,
    gravity: null,
    selection: null,
    state: {
      schema_states: [SchemaState.SOLVED, SchemaState.LOCKED]
    },
    task: null
  },
  
  component: SignoffPanel,
  props_from_context: ['schema_state']
};
```

---

## Panel Registry

```typescript
const PANEL_REGISTRY: PanelDefinition[] = [
  // Core
  PANEL_CHAT,
  PANEL_GRAVITY_TRIANGLE,
  PANEL_LOD_INDICATOR,
  
  // LegiQBD
  PANEL_QUESTIONS,
  PANEL_BLOB_PALETTE,
  PANEL_RELATIONSHIP_TOOLS,
  PANEL_SCORE,
  
  // LegiCAD
  PANEL_WALL_TOOLS,
  PANEL_OPENING_TOOLS,
  PANEL_FIXTURE_PALETTE,
  PANEL_FIXTURE_PROPERTIES,
  PANEL_MATERIAL_PICKER,
  PANEL_COORDINATES,
  PANEL_SPEC_EDITOR,
  
  // LegiDoc
  PANEL_VIEWPORT_TOOLS,
  PANEL_SHEET_MANAGER,
  PANEL_CODE_CHECKLIST,
  PANEL_SCHEDULE_GENERATOR,
  PANEL_SIGNOFF
];
```

---

## Visibility Calculation

### Evaluate Conditions

```typescript
function evaluatePanelVisibility(
  panel: PanelDefinition,
  context: PanelContext
): number {
  
  let opacity = 1.0;
  
  // Workflow stage check (hard gate)
  if (panel.conditions.workflow_stages !== 'all') {
    if (!panel.conditions.workflow_stages.includes(context.workflow_stage)) {
      return 0;
    }
  }
  
  // LOD check (hard gate)
  const currentLOD = context.lod.level;
  if (currentLOD < panel.conditions.lod_min || currentLOD > panel.conditions.lod_max) {
    // Check if we're transitioning into valid range
    if (context.lod.transition_to) {
      const targetLOD = context.lod.transition_to;
      if (targetLOD >= panel.conditions.lod_min && targetLOD <= panel.conditions.lod_max) {
        // Fading in
        opacity *= context.lod.transition_progress;
      } else {
        return 0;
      }
    } else {
      return 0;
    }
  } else if (context.lod.transition_to) {
    const targetLOD = context.lod.transition_to;
    if (targetLOD < panel.conditions.lod_min || targetLOD > panel.conditions.lod_max) {
      // Fading out
      opacity *= (1 - context.lod.transition_progress);
    }
  }
  
  // Gravity check (soft fade)
  if (panel.conditions.gravity) {
    const g = panel.conditions.gravity;
    const cg = context.gravity;
    
    let gravityOpacity = 1.0;
    
    // Design gravity
    if (g.design_min !== undefined && cg.design < g.design_min) {
      gravityOpacity *= cg.design / g.design_min;
    }
    if (g.design_max !== undefined && cg.design > g.design_max) {
      gravityOpacity *= 1 - ((cg.design - g.design_max) / (1 - g.design_max));
    }
    
    // Client gravity
    if (g.client_min !== undefined && cg.client < g.client_min) {
      gravityOpacity *= cg.client / g.client_min;
    }
    if (g.client_max !== undefined && cg.client > g.client_max) {
      gravityOpacity *= 1 - ((cg.client - g.client_max) / (1 - g.client_max));
    }
    
    // Build gravity
    if (g.build_min !== undefined && cg.build < g.build_min) {
      gravityOpacity *= cg.build / g.build_min;
    }
    if (g.build_max !== undefined && cg.build > g.build_max) {
      gravityOpacity *= 1 - ((cg.build - g.build_max) / (1 - g.build_max));
    }
    
    opacity *= Math.max(0, Math.min(1, gravityOpacity));
  }
  
  // Selection check (hard gate with fade)
  if (panel.conditions.selection && panel.conditions.selection.required) {
    const sel = panel.conditions.selection;
    
    if (!context.has_selection) {
      return 0;
    }
    
    if (sel.element_types) {
      const hasMatchingType = context.selected_types.some(t => 
        sel.element_types!.includes(t)
      );
      if (!hasMatchingType) {
        return 0;
      }
    }
    
    if (sel.min_count && context.selection_count < sel.min_count) {
      return 0;
    }
    
    if (sel.max_count && context.selection_count > sel.max_count) {
      return 0;
    }
  }
  
  // State check (hard gate)
  if (panel.conditions.state) {
    const s = panel.conditions.state;
    
    if (s.schema_states && !s.schema_states.includes(context.schema_state)) {
      return 0;
    }
    
    // Add other state checks as needed
  }
  
  // Task check (hard gate)
  if (panel.conditions.task) {
    const t = panel.conditions.task;
    
    if (t.during && !t.during.includes(context.active_task)) {
      return 0;
    }
    
    if (t.not_during && t.not_during.includes(context.active_task)) {
      return 0;
    }
  }
  
  // Custom condition
  if (panel.conditions.custom) {
    opacity *= panel.conditions.custom(context);
  }
  
  return Math.max(0, Math.min(1, opacity));
}
```

### Panel Manager

```typescript
class PanelManager {
  private panels: Map<string, PanelState> = new Map();
  private definitions: Map<string, PanelDefinition> = new Map();
  
  constructor(registry: PanelDefinition[]) {
    for (const def of registry) {
      this.definitions.set(def.id, def);
      this.panels.set(def.id, {
        id: def.id,
        base_opacity: 0,
        user_minimized: false,
        final_opacity: 0,
        current_position: this.calculatePosition(def),
        current_size: { x: def.size.width as number, y: def.size.height as number },
        opacity_transition: null,
        position_transition: null
      });
    }
  }
  
  /**
   * Update all panels based on context
   */
  update(context: PanelContext, delta_ms: number): void {
    for (const [id, state] of this.panels) {
      const def = this.definitions.get(id)!;
      
      // Calculate target opacity
      const targetOpacity = evaluatePanelVisibility(def, context);
      
      // Start transition if changed significantly
      if (Math.abs(targetOpacity - state.base_opacity) > 0.01) {
        state.opacity_transition = {
          from: state.base_opacity,
          to: targetOpacity,
          duration_ms: targetOpacity > state.base_opacity ? 300 : 200, // fade in slower
          elapsed_ms: 0,
          easing: EASING.easeInOut
        };
      }
      
      // Update transition
      if (state.opacity_transition) {
        state.opacity_transition.elapsed_ms += delta_ms;
        const t = Math.min(1, state.opacity_transition.elapsed_ms / state.opacity_transition.duration_ms);
        const eased = state.opacity_transition.easing(t);
        
        state.base_opacity = state.opacity_transition.from + 
          (state.opacity_transition.to - state.opacity_transition.from) * eased;
        
        if (t >= 1) {
          state.base_opacity = state.opacity_transition.to;
          state.opacity_transition = null;
        }
      }
      
      // Apply user minimized state
      state.final_opacity = state.user_minimized ? 0 : state.base_opacity;
    }
    
    // Resolve overlaps
    this.resolveOverlaps();
  }
  
  /**
   * Toggle user minimize
   */
  toggleMinimize(panelId: string): void {
    const state = this.panels.get(panelId);
    if (state) {
      state.user_minimized = !state.user_minimized;
    }
  }
  
  /**
   * Get visible panels for rendering
   */
  getVisiblePanels(): Array<{ definition: PanelDefinition; state: PanelState }> {
    const visible: Array<{ definition: PanelDefinition; state: PanelState }> = [];
    
    for (const [id, state] of this.panels) {
      if (state.final_opacity > 0.01) {
        visible.push({
          definition: this.definitions.get(id)!,
          state
        });
      }
    }
    
    // Sort by z-index
    visible.sort((a, b) => 
      a.definition.default_position.z_index - b.definition.default_position.z_index
    );
    
    return visible;
  }
  
  /**
   * Resolve overlapping panels
   */
  private resolveOverlaps(): void {
    const visible = this.getVisiblePanels();
    
    // Simple overlap resolution: push panels that overlap
    for (let i = 0; i < visible.length; i++) {
      for (let j = i + 1; j < visible.length; j++) {
        const a = visible[i].state;
        const b = visible[j].state;
        
        if (this.panelsOverlap(a, b)) {
          // Push the lower z-index panel
          // (This is simplified - real implementation would be smarter)
          b.current_position.y += 10;
        }
      }
    }
  }
  
  private panelsOverlap(a: PanelState, b: PanelState): boolean {
    return !(
      a.current_position.x + a.current_size.x < b.current_position.x ||
      b.current_position.x + b.current_size.x < a.current_position.x ||
      a.current_position.y + a.current_size.y < b.current_position.y ||
      b.current_position.y + b.current_size.y < a.current_position.y
    );
  }
  
  private calculatePosition(def: PanelDefinition): Vector2 {
    // Convert anchor + offset to absolute position
    // This would use screen size in real implementation
    const screenWidth = 1920;  // placeholder
    const screenHeight = 1080;
    
    let x = def.default_position.offset.x;
    let y = def.default_position.offset.y;
    
    switch (def.default_position.anchor) {
      case 'top-left':
        break;
      case 'top-right':
        x = screenWidth + x;
        break;
      case 'bottom-left':
        y = screenHeight + y;
        break;
      case 'bottom-right':
        x = screenWidth + x;
        y = screenHeight + y;
        break;
      case 'center':
        x = screenWidth / 2 + x;
        y = screenHeight / 2 + y;
        break;
      case 'left':
        y = screenHeight / 2 + y;
        break;
      case 'right':
        x = screenWidth + x;
        y = screenHeight / 2 + y;
        break;
    }
    
    return { x, y };
  }
}
```

---

## Panel Rendering

```typescript
interface PanelRenderer {
  render(panels: Array<{ definition: PanelDefinition; state: PanelState }>): void;
}

class DOMPanelRenderer implements PanelRenderer {
  private container: HTMLElement;
  private panelElements: Map<string, HTMLElement> = new Map();
  
  constructor(container: HTMLElement) {
    this.container = container;
  }
  
  render(panels: Array<{ definition: PanelDefinition; state: PanelState }>): void {
    // Create/update panel elements
    for (const { definition, state } of panels) {
      let element = this.panelElements.get(definition.id);
      
      if (!element) {
        element = this.createPanelElement(definition);
        this.panelElements.set(definition.id, element);
        this.container.appendChild(element);
      }
      
      // Update styles
      element.style.opacity = String(state.final_opacity);
      element.style.transform = `translate(${state.current_position.x}px, ${state.current_position.y}px)`;
      element.style.zIndex = String(definition.default_position.z_index);
      element.style.pointerEvents = state.final_opacity > 0.5 ? 'auto' : 'none';
      element.style.display = state.final_opacity > 0.01 ? 'block' : 'none';
    }
    
    // Hide panels not in visible list
    for (const [id, element] of this.panelElements) {
      if (!panels.find(p => p.definition.id === id)) {
        element.style.display = 'none';
      }
    }
  }
  
  private createPanelElement(definition: PanelDefinition): HTMLElement {
    const element = document.createElement('div');
    element.className = 'smart-panel';
    element.id = `panel-${definition.id}`;
    
    // Add header
    const header = document.createElement('div');
    header.className = 'smart-panel-header';
    header.innerHTML = `
      <span class="panel-title">${definition.name}</span>
      ${definition.can_minimize ? '<button class="panel-minimize">−</button>' : ''}
    `;
    element.appendChild(header);
    
    // Add content container (component mounts here)
    const content = document.createElement('div');
    content.className = 'smart-panel-content';
    element.appendChild(content);
    
    // Set initial size
    if (typeof definition.size.width === 'number') {
      element.style.width = `${definition.size.width}px`;
    }
    if (typeof definition.size.height === 'number') {
      element.style.height = `${definition.size.height}px`;
    }
    
    return element;
  }
}
```

---

## CSS

```css
.smart-panel {
  position: absolute;
  background: rgba(30, 30, 35, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  transition: opacity 0.2s ease-out;
  overflow: hidden;
}

.smart-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  cursor: move;
  user-select: none;
}

.panel-title {
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.panel-minimize {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
}

.panel-minimize:hover {
  color: rgba(255, 255, 255, 0.9);
}

.smart-panel-content {
  padding: 12px;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
}

/* Gravity-aware panel styling */
.smart-panel[data-gravity="design"] {
  border-color: rgba(100, 150, 255, 0.3);
}

.smart-panel[data-gravity="client"] {
  border-color: rgba(100, 255, 150, 0.3);
}

.smart-panel[data-gravity="build"] {
  border-color: rgba(255, 150, 100, 0.3);
}
```

---

## Integration with Main Loop

```typescript
class Application {
  private panelManager: PanelManager;
  private panelRenderer: PanelRenderer;
  private viewState: ViewState;
  private selection: Selection;
  private schemaState: SchemaState;
  private activeTask: TaskType;
  
  constructor() {
    this.panelManager = new PanelManager(PANEL_REGISTRY);
    this.panelRenderer = new DOMPanelRenderer(document.getElementById('panel-container')!);
    // ... init other state
  }
  
  update(delta_ms: number): void {
    // Build panel context
    const context: PanelContext = {
      workflow_stage: this.getWorkflowStage(),
      lod: calculateLOD(this.viewState.elevation),
      gravity: this.viewState.gravity,
      selection: this.selection,
      schema_state: this.schemaState,
      active_task: this.activeTask,
      
      // Convenience
      selected_elements: this.getSelectedElements(),
      selected_types: this.getSelectedTypes(),
      has_selection: this.selection.count > 0,
      selection_count: this.selection.count
    };
    
    // Update panel visibility
    this.panelManager.update(context, delta_ms);
    
    // Render panels
    this.panelRenderer.render(this.panelManager.getVisiblePanels());
  }
  
  private getWorkflowStage(): WorkflowStage {
    const lod = calculateLOD(this.viewState.elevation).level;
    
    if (lod === LODLevel.TOPOLOGY) {
      return WorkflowStage.LEGI_QBD;
    } else if (lod <= LODLevel.FIXTURES) {
      return WorkflowStage.LEGI_CAD;
    } else {
      return WorkflowStage.LEGI_DOC;
    }
  }
}
```

---

## Summary

**Panels emerge from context.** No manual show/hide.

**Conditions checked:**
1. Workflow stage (hard gate)
2. LOD range (hard gate with fade at edges)
3. Gravity thresholds (soft fade)
4. Selection requirements (hard gate)
5. Schema state (hard gate)
6. Active task (hard gate)
7. Custom logic (escape hatch)

**All panels defined declaratively.** Add a new panel = add a definition to the registry.

**Transitions are smooth.** Same system as geometry fading.

**Overlap resolution.** Panels push each other to avoid stacking.

---

*Document version: 1.0*
