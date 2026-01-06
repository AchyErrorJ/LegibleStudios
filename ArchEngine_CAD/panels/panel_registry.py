"""
Panel Registry - Defines all smart panels and their visibility conditions.

Each panel is defined with:
- ID and name
- Widget class to instantiate
- Visibility conditions (workflow, LOD, gravity, selection, etc.)
"""
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox
)
from PyQt6.QtCore import Qt

from panels.smart_panels import (
    PanelDefinition, PanelConditions, GravityCondition,
    SelectionCondition, StateCondition, TaskCondition,
    WorkflowStage, SchemaState, TaskType, ElementType, LODLevel
)


# =============================================================================
# Placeholder Panel Widgets
# =============================================================================

class PlaceholderPanel(QWidget):
    """Base placeholder panel for development."""

    def __init__(self, title: str, description: str, color: str = "#4a4a55", parent=None):
        super().__init__(parent)
        self._setup_ui(title, description, color)

    def _setup_ui(self, title: str, description: str, color: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-weight: bold; color: {color}; font-size: 11px;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #888; font-size: 10px;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Placeholder content
        placeholder = QLabel("[Panel Content]")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            f"background: {color}22; border: 1px dashed {color}; "
            "border-radius: 4px; padding: 20px; color: #666;"
        )
        layout.addWidget(placeholder)

        layout.addStretch()


class BlobPalettePanel(PlaceholderPanel):
    """Room/blob palette for LegiQBD."""
    def __init__(self, parent=None):
        super().__init__(
            "Rooms",
            "Drag room types onto the canvas",
            "#6495ED",  # Cornflower blue (Design)
            parent
        )


class RelationshipToolsPanel(PlaceholderPanel):
    """Relationship editing tools for LegiQBD."""
    def __init__(self, parent=None):
        super().__init__(
            "Relationships",
            "Define how rooms connect",
            "#6495ED",
            parent
        )


class ScorePanel(PlaceholderPanel):
    """Design score/feedback panel."""
    def __init__(self, parent=None):
        super().__init__(
            "Design Score",
            "How well does this meet requirements?",
            "#6495ED",
            parent
        )


class WallToolsPanel(PlaceholderPanel):
    """Wall editing tools for LegiCAD."""
    def __init__(self, parent=None):
        super().__init__(
            "Wall Properties",
            "Edit wall type, thickness, materials",
            "#90EE90",  # Light green (Client-ish)
            parent
        )


class OpeningToolsPanel(PlaceholderPanel):
    """Door/window editing tools."""
    def __init__(self, parent=None):
        super().__init__(
            "Opening Properties",
            "Edit door/window size and type",
            "#90EE90",
            parent
        )


class FixturePalettePanel(PlaceholderPanel):
    """Fixture library panel."""
    def __init__(self, parent=None):
        super().__init__(
            "Fixtures",
            "Drag fixtures onto the floor plan",
            "#90EE90",
            parent
        )


class MaterialPickerPanel(PlaceholderPanel):
    """Material selection panel."""
    def __init__(self, parent=None):
        super().__init__(
            "Materials",
            "Select materials for surfaces",
            "#90EE90",
            parent
        )


class CoordinatesPanel(PlaceholderPanel):
    """Coordinate display for Build gravity."""
    def __init__(self, parent=None):
        super().__init__(
            "Coordinates",
            "Element positions and dimensions",
            "#FFA500",  # Orange (Build)
            parent
        )


class SpecEditorPanel(PlaceholderPanel):
    """Specification editing panel."""
    def __init__(self, parent=None):
        super().__init__(
            "Specifications",
            "Edit construction specs and notes",
            "#FFA500",
            parent
        )


class ViewportToolsPanel(PlaceholderPanel):
    """Viewport creation tools for LegiDoc."""
    def __init__(self, parent=None):
        super().__init__(
            "Viewports",
            "Create plan, section, elevation views",
            "#9370DB",  # Medium purple
            parent
        )


class SheetManagerPanel(PlaceholderPanel):
    """Sheet management for LegiDoc."""
    def __init__(self, parent=None):
        super().__init__(
            "Sheets",
            "Manage drawing sheets",
            "#9370DB",
            parent
        )


class CodeChecklistPanel(PlaceholderPanel):
    """Code compliance checklist."""
    def __init__(self, parent=None):
        super().__init__(
            "Code Compliance",
            "Building code requirements",
            "#FFA500",
            parent
        )


# =============================================================================
# Core Panel Widgets (Always Visible or Special)
# =============================================================================

class NavigationPanel(QWidget):
    """
    Navigation panel - combines Gravity Triangle and LOD indicator.
    Always visible - this is the core navigation for the entire app.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        from panels.gravity_triangle import GravityTriangleWidget
        from panels.lod_indicator import LODIndicatorWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Title
        title = QLabel("Navigation")
        title.setStyleSheet("font-weight: bold; font-size: 12px; color: #ddd;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Gravity Triangle
        self.gravity_triangle = GravityTriangleWidget()
        layout.addWidget(self.gravity_triangle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Quick preset buttons for gravity
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(3)

        btn_design = QPushButton("D")
        btn_design.setFixedSize(28, 22)
        btn_design.setToolTip("Design Focus")
        btn_design.setStyleSheet("font-size: 10px; font-weight: bold; color: #6495ED;")
        btn_design.clicked.connect(self.gravity_triangle.set_design)
        btn_layout.addWidget(btn_design)

        btn_client = QPushButton("C")
        btn_client.setFixedSize(28, 22)
        btn_client.setToolTip("Client Focus")
        btn_client.setStyleSheet("font-size: 10px; font-weight: bold; color: #90EE90;")
        btn_client.clicked.connect(self.gravity_triangle.set_client)
        btn_layout.addWidget(btn_client)

        btn_build = QPushButton("B")
        btn_build.setFixedSize(28, 22)
        btn_build.setToolTip("Build Focus")
        btn_build.setStyleSheet("font-size: 10px; font-weight: bold; color: #FFA500;")
        btn_build.clicked.connect(self.gravity_triangle.set_build)
        btn_layout.addWidget(btn_build)

        layout.addLayout(btn_layout)

        # LOD Indicator
        self.lod_indicator = LODIndicatorWidget()
        layout.addWidget(self.lod_indicator)

        layout.addStretch()


class DesignChatPanel(QWidget):
    """
    Design Chat panel wrapper for smart panel system.
    Always visible - core communication tool.
    Uses a placeholder until connected to the app document.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.chat_widget = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title
        title = QLabel("Design Chat")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #9370DB;")
        layout.addWidget(title)

        # Placeholder chat interface
        self._chat_display = QLabel("Chat with AI to design your building.\n\nType a description below...")
        self._chat_display.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._chat_display.setWordWrap(True)
        self._chat_display.setStyleSheet(
            "background: rgba(147, 112, 219, 0.1); "
            "border: 1px solid rgba(147, 112, 219, 0.3); "
            "border-radius: 4px; padding: 10px; color: #aaa;"
        )
        self._chat_display.setMinimumHeight(100)
        layout.addWidget(self._chat_display, 1)

        # Input area
        from PyQt6.QtWidgets import QLineEdit
        self._input = QLineEdit()
        self._input.setPlaceholderText("Describe your building...")
        self._input.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); "
            "border: 1px solid rgba(147, 112, 219, 0.5); "
            "border-radius: 4px; padding: 8px; color: #ddd;"
        )
        layout.addWidget(self._input)

    def set_document(self, document):
        """Connect to the application document for real chat functionality."""
        # This can be called later to enable full chat
        pass


class SelectionPropertiesPanel(QWidget):
    """
    Properties panel - shows when elements are selected.
    Context-aware based on selection type.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel("Properties")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #90EE90;")
        layout.addWidget(title)

        # Placeholder - in production, embed PropertiesPanel
        self.content = QLabel("Select an element\nto view properties")
        self.content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content.setStyleSheet(
            "color: #666; padding: 20px; "
            "background: rgba(144, 238, 144, 0.1); "
            "border: 1px dashed #90EE90; border-radius: 4px;"
        )
        layout.addWidget(self.content)
        layout.addStretch()


# =============================================================================
# Panel Definitions
# =============================================================================

# Core panels (always visible - no workflow/LOD/gravity restrictions)
PANEL_NAVIGATION = PanelDefinition(
    id='navigation',
    name='Navigation',
    widget_class=NavigationPanel,
    conditions=PanelConditions(
        # No restrictions - always visible
        lod_min=1,
        lod_max=5,
    ),
    z_index=100,  # Highest priority - always on top
    can_minimize=False,  # Cannot be minimized
)

PANEL_CHAT = PanelDefinition(
    id='chat',
    name='Design Chat',
    widget_class=DesignChatPanel,
    conditions=PanelConditions(
        # No restrictions - always visible
        lod_min=1,
        lod_max=5,
    ),
    z_index=95,
    can_minimize=True,
)

PANEL_PROPERTIES = PanelDefinition(
    id='properties',
    name='Properties',
    widget_class=SelectionPropertiesPanel,
    conditions=PanelConditions(
        lod_min=1,
        lod_max=5,
        selection=SelectionCondition(
            required=True,  # Only show when something is selected
        ),
    ),
    z_index=90,
)

# LegiQBD Panels
PANEL_BLOB_PALETTE = PanelDefinition(
    id='blob_palette',
    name='Rooms',
    widget_class=BlobPalettePanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_QBD],
        lod_min=1,
        lod_max=1,
        gravity=GravityCondition(design_min=0.3),
    ),
    z_index=80
)

PANEL_RELATIONSHIP_TOOLS = PanelDefinition(
    id='relationship_tools',
    name='Relationships',
    widget_class=RelationshipToolsPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_QBD],
        lod_min=1,
        lod_max=1,
        gravity=GravityCondition(design_min=0.3),
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.BLOB, ElementType.RELATIONSHIP]
        ),
    ),
    z_index=85
)

PANEL_SCORE = PanelDefinition(
    id='score',
    name='Design Score',
    widget_class=ScorePanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_QBD, WorkflowStage.LEGI_CAD],
        lod_min=1,
        lod_max=3,
        gravity=GravityCondition(design_min=0.2),
        state=StateCondition(
            schema_states=[SchemaState.ACCUMULATING, SchemaState.COMPLETE, SchemaState.SOLVED]
        ),
    ),
    z_index=75
)

# LegiCAD Panels
PANEL_WALL_TOOLS = PanelDefinition(
    id='wall_tools',
    name='Wall',
    widget_class=WallToolsPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD],
        lod_min=2,
        lod_max=4,
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.WALL]
        ),
    ),
    z_index=80
)

PANEL_OPENING_TOOLS = PanelDefinition(
    id='opening_tools',
    name='Opening',
    widget_class=OpeningToolsPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD],
        lod_min=2,
        lod_max=4,
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.DOOR, ElementType.WINDOW]
        ),
    ),
    z_index=80
)

PANEL_FIXTURE_PALETTE = PanelDefinition(
    id='fixture_palette',
    name='Fixtures',
    widget_class=FixturePalettePanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD],
        lod_min=3,
        lod_max=5,
        task=TaskCondition(not_during=[TaskType.DRAGGING_FIXTURE]),
    ),
    z_index=80
)

PANEL_MATERIAL_PICKER = PanelDefinition(
    id='material_picker',
    name='Materials',
    widget_class=MaterialPickerPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD],
        lod_min=2,
        lod_max=5,
        gravity=GravityCondition(client_min=0.4),
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.WALL, ElementType.FIXTURE, ElementType.FURNITURE]
        ),
    ),
    z_index=70
)

PANEL_COORDINATES = PanelDefinition(
    id='coordinates',
    name='Coordinates',
    widget_class=CoordinatesPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD, WorkflowStage.LEGI_DOC],
        lod_min=2,
        lod_max=5,
        gravity=GravityCondition(build_min=0.3),
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.WALL, ElementType.CONTROL_POINT, ElementType.COORDINATE_MARKER]
        ),
    ),
    z_index=60
)

PANEL_SPEC_EDITOR = PanelDefinition(
    id='spec_editor',
    name='Specifications',
    widget_class=SpecEditorPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_CAD, WorkflowStage.LEGI_DOC],
        lod_min=3,
        lod_max=5,
        gravity=GravityCondition(build_min=0.5),
        selection=SelectionCondition(
            required=True,
            element_types=[ElementType.WALL, ElementType.DOOR, ElementType.WINDOW, ElementType.FIXTURE]
        ),
    ),
    z_index=65
)

# LegiDoc Panels
PANEL_VIEWPORT_TOOLS = PanelDefinition(
    id='viewport_tools',
    name='Viewports',
    widget_class=ViewportToolsPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_DOC],
        lod_min=4,
        lod_max=5,
    ),
    z_index=80
)

PANEL_SHEET_MANAGER = PanelDefinition(
    id='sheet_manager',
    name='Sheets',
    widget_class=SheetManagerPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_DOC],
        lod_min=4,
        lod_max=5,
    ),
    z_index=75
)

PANEL_CODE_CHECKLIST = PanelDefinition(
    id='code_checklist',
    name='Code Compliance',
    widget_class=CodeChecklistPanel,
    conditions=PanelConditions(
        workflow_stages=[WorkflowStage.LEGI_DOC],
        lod_min=5,
        lod_max=5,
        gravity=GravityCondition(build_min=0.3),
    ),
    z_index=85
)


# =============================================================================
# Panel Registry
# =============================================================================

PANEL_REGISTRY: List[PanelDefinition] = [
    # Note: Navigation and Chat are now separate dock widgets (not in smart panels)

    # Properties (shows when element selected)
    PANEL_PROPERTIES,

    # LegiQBD
    PANEL_BLOB_PALETTE,
    PANEL_RELATIONSHIP_TOOLS,
    PANEL_SCORE,

    # LegiCAD
    PANEL_WALL_TOOLS,
    PANEL_OPENING_TOOLS,
    PANEL_FIXTURE_PALETTE,
    PANEL_MATERIAL_PICKER,
    PANEL_COORDINATES,
    PANEL_SPEC_EDITOR,

    # LegiDoc
    PANEL_VIEWPORT_TOOLS,
    PANEL_SHEET_MANAGER,
    PANEL_CODE_CHECKLIST,
]


def get_panel_registry() -> List[PanelDefinition]:
    """Get the full panel registry."""
    return PANEL_REGISTRY.copy()
