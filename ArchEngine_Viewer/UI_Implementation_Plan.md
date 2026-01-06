# ArchEngine Viewer - UI Implementation Plan

## Target Layout

```
+------------------+-------------------------+------------------+
|                  |                         |                  |
|   PROPERTIES     |      MAIN 3D            |    PROJECT       |
|   PANEL          |      VIEWPORT           |    ORGANIZER     |
|                  |                         |                  |
|   - Element      |   [Orbit/Pan/Zoom]      |   - Building     |
|     details      |                         |     hierarchy    |
|   - Materials    |   [Click to select]     |   - Levels       |
|   - Constraints  |                         |   - Rooms        |
|   - Dimensions   |   [Dimension tool]      |   - Elements     |
|                  |                         |   - Visibility   |
|                  |                         |     toggles      |
+------------------+-------------------------+------------------+
|  [Structural]  |  [Thermal]  |  [Acoustic]  |  [Material]  |  [Wireframe]  |
|    View 1      |   View 2    |    View 3    |   View 4     |    View 5     |
+-----------------------------------------------------------------------------+
```

---

## Phase 1: Core Infrastructure (Foundation)

### 1.1 Camera Controller
**Files to create:**
- `Source/ArchEngine/Framework/ArchViewerPawn.h/.cpp`
- `Source/ArchEngine/Framework/ArchViewerController.h/.cpp`

**Features:**
- Orbit camera (right-click drag)
- Pan (middle-click drag)
- Zoom (scroll wheel)
- Focus on selection (F key)
- View presets (Top, Front, Right, Isometric)

### 1.2 Game Mode & HUD
**Files to create:**
- `Source/ArchEngine/Framework/ArchViewerGameMode.h/.cpp`
- `Source/ArchEngine/Framework/ArchViewerHUD.h/.cpp`

**Features:**
- Initialize UI on game start
- Manage viewport layout
- Handle input routing

### 1.3 Selection System
**Files to create:**
- `Source/ArchEngine/Framework/ArchSelectionManager.h/.cpp`

**Features:**
- Ray cast click-to-select
- Multi-select (Ctrl+click)
- Selection highlighting
- Selection changed delegate

### 1.4 Main UI Container
**Files to create:**
- `Source/ArchEngine/UI/ArchMainWidget.h/.cpp`

**Features:**
- Root canvas for all UI
- Docking panel framework
- Splitter panels for resizing
- Layout save/load

---

## Phase 2: Essential Panels

### 2.1 Properties Panel (Left)
**Files to create:**
- `Source/ArchEngine/UI/Panels/ArchPropertiesPanel.h/.cpp`

**Features:**
- Element name and type
- Transform (position, rotation)
- Material layers (for walls)
- Thermal properties (R-value)
- Structural data (load, deflection)
- Constraint compliance
- Custom properties

**Data binding:**
- Listen to SelectionManager
- Query ArchBuildingActor for element data
- Update on selection change

### 2.2 Project Organizer (Right)
**Files to create:**
- `Source/ArchEngine/UI/Panels/ArchProjectPanel.h/.cpp`

**Features:**
- Tree view hierarchy:
  ```
  Building
  ├── Level 1
  │   ├── Rooms
  │   │   ├── Living Room
  │   │   ├── Kitchen
  │   │   └── ...
  │   ├── Walls (12)
  │   ├── Doors (4)
  │   └── Windows (8)
  ├── Level 2
  └── Roof
  ```
- Visibility toggles (eye icon)
- Selection from tree
- Filter by type
- Search box

### 2.3 Multi-View Strip (Bottom)
**Files to create:**
- `Source/ArchEngine/UI/Panels/ArchViewStrip.h/.cpp`
- `Source/ArchEngine/Rendering/ArchRenderTarget.h/.cpp`

**Features:**
- 5 viewport thumbnails
- Each shows different visualization mode
- Click to apply mode to main viewport
- Real-time preview updates
- Mode labels (Structural, Thermal, etc.)

---

## Phase 3: Dimensioning System

### 3.1 Dimension Tool
**Files to create:**
- `Source/ArchEngine/Tools/ArchDimensionTool.h/.cpp`
- `Source/ArchEngine/Tools/ArchToolManager.h/.cpp`

**Features:**
- Click two points to measure
- Display distance in mm/ft
- Snap to vertices/edges
- Temporary dimension (while measuring)
- Persistent dimensions (saved to building)

### 3.2 Dimension Rendering
**Files to create:**
- `Source/ArchEngine/Rendering/ArchDimensionRenderer.h/.cpp`

**Features:**
- 3D dimension lines with arrows
- Text labels with distance
- Leader lines
- Chainable dimensions
- Angular dimensions

### 3.3 Dimension Panel (in Properties)
**Features:**
- List of placed dimensions
- Edit dimension text
- Delete dimensions
- Show/hide all dimensions

---

## Phase 4: Toolbar & Menu

### 4.1 Toolbar
**Files to create:**
- `Source/ArchEngine/UI/ArchToolbar.h/.cpp`

**Buttons:**
- Select tool
- Dimension tool
- Section cut tool
- View presets dropdown
- Visualization mode dropdown
- Exploded view toggle
- Layer visibility dropdown

### 4.2 Menu Bar
**Files to create:**
- `Source/ArchEngine/UI/ArchMenuBar.h/.cpp`

**Menus:**
- File: Open, Save, Export, Recent Files
- Edit: Undo, Redo, Preferences
- View: Panels, Render Mode, Reset Layout
- Tools: Dimension, Section, Measure
- Help: Documentation, About

---

## Phase 5: Polish & Settings

### 5.1 Settings Panel
- Units (metric/imperial)
- Default render mode
- Camera sensitivity
- Grid settings
- Theme (dark/light)

### 5.2 Status Bar
- Current tool
- Selection count
- Coordinates
- Zoom level

### 5.3 Keyboard Shortcuts
- F: Focus on selection
- 1-5: Render mode presets
- D: Dimension tool
- S: Section tool
- Escape: Cancel tool
- Delete: Delete dimension

---

## File Structure (Final)

```
Source/ArchEngine/
├── Actors/
│   └── ArchBuildingActor.h/.cpp          [EXISTS]
├── Components/
│   └── ArchLiveSyncComponent.h/.cpp      [EXISTS]
├── Loaders/
│   └── ArchBuildingLoader.h/.cpp         [EXISTS]
├── Types/
│   └── ArchTypes.h                       [EXISTS]
├── Framework/                            [NEW]
│   ├── ArchViewerGameMode.h/.cpp
│   ├── ArchViewerPawn.h/.cpp
│   ├── ArchViewerController.h/.cpp
│   ├── ArchViewerHUD.h/.cpp
│   └── ArchSelectionManager.h/.cpp
├── UI/                                   [NEW]
│   ├── ArchMainWidget.h/.cpp
│   ├── ArchToolbar.h/.cpp
│   ├── ArchMenuBar.h/.cpp
│   ├── ArchStatusBar.h/.cpp
│   └── Panels/
│       ├── ArchPropertiesPanel.h/.cpp
│       ├── ArchProjectPanel.h/.cpp
│       └── ArchViewStrip.h/.cpp
├── Tools/                                [NEW]
│   ├── ArchToolManager.h/.cpp
│   ├── ArchDimensionTool.h/.cpp
│   └── ArchSectionTool.h/.cpp
└── Rendering/                            [NEW]
    ├── ArchRenderTarget.h/.cpp
    └── ArchDimensionRenderer.h/.cpp
```

---

## Implementation Order

| Order | Component | Dependencies | Effort |
|-------|-----------|--------------|--------|
| 1 | Camera Controller (Pawn + Controller) | None | 2 days |
| 2 | GameMode + HUD | Camera | 1 day |
| 3 | Main Widget Container | HUD | 2 days |
| 4 | Selection Manager | Camera | 2 days |
| 5 | Properties Panel | Selection, Widget | 3 days |
| 6 | Project Organizer | Widget, Building data | 3 days |
| 7 | Multi-View Strip | Widget, Render targets | 4 days |
| 8 | Tool Manager | Selection | 1 day |
| 9 | Dimension Tool | Tool Manager | 3 days |
| 10 | Dimension Renderer | Dimension Tool | 2 days |
| 11 | Toolbar | Widget, Tools | 2 days |
| 12 | Menu Bar | Widget | 2 days |
| 13 | Settings & Polish | All | 3 days |

**Total Estimate: ~30 days of focused development**

---

## Quick Start: First Milestone

**Goal:** Orbit camera + click-to-select + basic properties panel

**Files needed:**
1. `ArchViewerPawn.h/.cpp` - Orbit camera
2. `ArchViewerController.h/.cpp` - Input handling
3. `ArchViewerGameMode.h/.cpp` - Wire it up
4. `ArchSelectionManager.h/.cpp` - Click to select
5. `ArchPropertiesPanel.h/.cpp` - Show selected element info

**Result:** You can orbit around the building, click on elements, and see their properties in a panel.

---

## Notes

- All UI uses UMG (Unreal Motion Graphics) via C++ UUserWidget classes
- Render targets for multi-view strip (SceneCaptureComponent2D)
- Selection uses line trace with collision on procedural meshes
- Dimension tool stores data in FArchDimension structs (already in ArchTypes.h)
- Layout state saved to .ini or JSON for persistence
