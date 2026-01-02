"""
ArchEngine CAD Main Application Window
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout,
    QSplitter, QLabel, QTabWidget
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from app.config import Config
from core.document import ArchDocument
from core.events import event_bus

# Sheet system imports
from sheets.sheet_registry import SheetRegistry
from panels.sheet_manager import SheetManagerPanel
from panels.chat_panel import ChatPanel
from generators.generator_service import GeneratorService

# Optional viewport imports
try:
    from viewport import UE5ViewportWidget
    HAS_UE5_VIEWPORT = True
except ImportError:
    HAS_UE5_VIEWPORT = False

try:
    from viewport import VulkanViewportWidget, HAS_VULKAN_WIDGET
    HAS_VIEWPORT = HAS_VULKAN_WIDGET
except ImportError:
    HAS_VIEWPORT = False
    HAS_VULKAN_WIDGET = False

# Optional LiveSync import
try:
    from sync import get_livesync_server, HAS_LIVESYNC
except ImportError:
    HAS_LIVESYNC = False

# Optional VulkanSync import
try:
    from sync import get_vulkan_sync_client, HAS_VULKAN_SYNC
except ImportError:
    HAS_VULKAN_SYNC = False


class ArchEngineApplication(QMainWindow):
    """
    Main application window.
    Central hub for all views and panels.
    """

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.document = ArchDocument(self)

        # Initialize LiveSync server for UE5 connection
        self._livesync_server = None
        if HAS_LIVESYNC:
            try:
                self._livesync_server = get_livesync_server()
                self._livesync_server.start()
                self.document.document_changed.connect(self._on_document_changed_livesync)
            except Exception as e:
                print(f"[App] LiveSync init failed: {e}")

        # Initialize VulkanSync client for Vulkan renderer connection
        self._vulkan_sync = None
        if HAS_VULKAN_SYNC:
            try:
                self._vulkan_sync = get_vulkan_sync_client()
                self._vulkan_sync.connected.connect(self._on_vulkan_connected)
                self._vulkan_sync.disconnected.connect(self._on_vulkan_disconnected)
                self.document.document_changed.connect(self._on_document_changed_vulkan)
                self._vulkan_sync.connect_to_renderer()
            except Exception as e:
                print(f"[App] VulkanSync init failed: {e}")

        # Throttle timer for 3D viewport updates (prevents lag during dragging)
        self._viewport_update_timer = QTimer(self)
        self._viewport_update_timer.setSingleShot(True)
        self._viewport_update_timer.setInterval(50)  # 50ms debounce
        self._viewport_update_timer.timeout.connect(self._do_viewport_update)

        # Initialize sheet system
        self._sheet_registry = SheetRegistry(self)
        self._generator_service = GeneratorService(
            self._sheet_registry,
            lambda: self.document.to_dict(),
            self
        )

        self._setup_window()
        self._create_actions()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_dock_widgets()
        self._create_central_widget()
        self._connect_signals()
        self._restore_state()

    def _setup_window(self):
        """Configure main window properties."""
        self.setWindowTitle("ArchEngine CAD")
        self.setMinimumSize(1200, 800)
        self.setDockNestingEnabled(True)

    def _create_actions(self):
        """Create all actions."""
        # File actions
        self.action_new = QAction("&New", self)
        self.action_new.setShortcut(QKeySequence.StandardKey.New)
        self.action_new.triggered.connect(self._on_new)

        self.action_open = QAction("&Open...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.triggered.connect(self._on_open)

        self.action_save = QAction("&Save", self)
        self.action_save.setShortcut(QKeySequence.StandardKey.Save)
        self.action_save.triggered.connect(self._on_save)

        self.action_save_as = QAction("Save &As...", self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self._on_save_as)

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_exit.triggered.connect(self.close)

        # Edit actions
        self.action_undo = QAction("&Undo", self)
        self.action_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.action_undo.triggered.connect(self._on_undo)

        self.action_redo = QAction("&Redo", self)
        self.action_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.action_redo.triggered.connect(self._on_redo)

        self.action_delete = QAction("&Delete", self)
        self.action_delete.setShortcut(QKeySequence.StandardKey.Delete)
        self.action_delete.triggered.connect(self._on_delete)

        # View actions
        self.action_zoom_in = QAction("Zoom &In", self)
        self.action_zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)

        self.action_zoom_out = QAction("Zoom &Out", self)
        self.action_zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)

        self.action_zoom_fit = QAction("&Home (Zoom to Fit)", self)
        self.action_zoom_fit.setShortcut(QKeySequence("H"))

        # Tool actions
        self.action_select = QAction("&Select", self)
        self.action_select.setCheckable(True)
        self.action_select.setChecked(True)
        self.action_select.setShortcut(QKeySequence("V"))

        self.action_wall = QAction("&Wall", self)
        self.action_wall.setCheckable(True)
        self.action_wall.setShortcut(QKeySequence("W"))

        self.action_door = QAction("&Door", self)
        self.action_door.setCheckable(True)
        self.action_door.setShortcut(QKeySequence("D"))

        self.action_window = QAction("W&indow", self)
        self.action_window.setCheckable(True)
        self.action_window.setShortcut(QKeySequence("I"))

        self.action_room = QAction("&Room", self)
        self.action_room.setCheckable(True)
        self.action_room.setShortcut(QKeySequence("R"))

        # Sheet actions
        self.action_regenerate_sheets = QAction("Regenerate Sheets", self)
        self.action_regenerate_sheets.setShortcut(QKeySequence("F4"))
        self.action_regenerate_sheets.triggered.connect(lambda: self._on_regenerate_sheet(""))

        # Toggle actions
        self.action_ortho = QAction("&Ortho", self)
        self.action_ortho.setCheckable(True)
        self.action_ortho.setChecked(self.config.ortho_mode)
        self.action_ortho.setShortcut(QKeySequence("F8"))
        self.action_ortho.triggered.connect(self._toggle_ortho)

        self.action_grid = QAction("&Grid", self)
        self.action_grid.setCheckable(True)
        self.action_grid.setChecked(self.config.grid_visible)
        self.action_grid.setShortcut(QKeySequence("F7"))
        self.action_grid.triggered.connect(self._toggle_grid)

        self.action_snap = QAction("&Snap", self)
        self.action_snap.setCheckable(True)
        self.action_snap.setChecked(self.config.snap_enabled)
        self.action_snap.setShortcut(QKeySequence("F9"))
        self.action_snap.triggered.connect(self._toggle_snap)

        # Individual snap type toggles
        self.action_snap_endpoint = QAction("&Endpoint", self)
        self.action_snap_endpoint.setCheckable(True)
        self.action_snap_endpoint.setChecked(self.config.snap_endpoint)
        self.action_snap_endpoint.triggered.connect(lambda: self._toggle_snap_type('endpoint'))

        self.action_snap_midpoint = QAction("&Midpoint", self)
        self.action_snap_midpoint.setCheckable(True)
        self.action_snap_midpoint.setChecked(self.config.snap_midpoint)
        self.action_snap_midpoint.triggered.connect(lambda: self._toggle_snap_type('midpoint'))

        self.action_snap_perpendicular = QAction("Per&pendicular", self)
        self.action_snap_perpendicular.setCheckable(True)
        self.action_snap_perpendicular.setChecked(self.config.snap_perpendicular)
        self.action_snap_perpendicular.triggered.connect(lambda: self._toggle_snap_type('perpendicular'))

        self.action_snap_parallel = QAction("Para&llel", self)
        self.action_snap_parallel.setCheckable(True)
        self.action_snap_parallel.setChecked(self.config.snap_parallel)
        self.action_snap_parallel.triggered.connect(lambda: self._toggle_snap_type('parallel'))

        self.action_snap_extension = QAction("E&xtension", self)
        self.action_snap_extension.setCheckable(True)
        self.action_snap_extension.setChecked(self.config.snap_extension)
        self.action_snap_extension.triggered.connect(lambda: self._toggle_snap_type('extension'))

        self.action_snap_angular = QAction("&Angular", self)
        self.action_snap_angular.setCheckable(True)
        self.action_snap_angular.setChecked(self.config.snap_angular)
        self.action_snap_angular.triggered.connect(lambda: self._toggle_snap_type('angular'))

        # Pin action for LLM workflow
        self.action_pin = QAction("Pin", self)
        self.action_pin.setCheckable(True)
        self.action_pin.setToolTip("Pin selected elements (protected from LLM changes)")
        self.action_pin.setShortcut(QKeySequence("P"))
        self.action_pin.toggled.connect(self._on_pin_toggle)

        # 3D Viewport actions (only if viewport module available)
        if HAS_VIEWPORT:
            self.action_reset_camera = QAction("&Reset Camera", self)
            self.action_reset_camera.setShortcut(QKeySequence("F5"))
            self.action_reset_camera.triggered.connect(self._reset_viewport_camera)

            self.action_toggle_3d_view = QAction("&3D Viewport", self)
            self.action_toggle_3d_view.setCheckable(True)
            self.action_toggle_3d_view.setChecked(True)  # Default on
            self.action_toggle_3d_view.setShortcut(QKeySequence("F6"))
            self.action_toggle_3d_view.triggered.connect(self._toggle_3d_view)

            self.action_3d_split = QAction("Split View (2D | 3D)", self)
            self.action_3d_split.setCheckable(True)
            self.action_3d_split.triggered.connect(self._toggle_split_view)

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.action_new)
        file_menu.addAction(self.action_open)
        file_menu.addSeparator()
        file_menu.addAction(self.action_save)
        file_menu.addAction(self.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(self.action_undo)
        edit_menu.addAction(self.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.action_delete)

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.action_zoom_in)
        view_menu.addAction(self.action_zoom_out)
        view_menu.addAction(self.action_zoom_fit)
        view_menu.addSeparator()
        view_menu.addAction(self.action_grid)
        view_menu.addSeparator()
        view_menu.addAction(self.action_regenerate_sheets)

        # Draw menu
        draw_menu = menubar.addMenu("&Draw")
        draw_menu.addAction(self.action_wall)
        draw_menu.addAction(self.action_door)
        draw_menu.addAction(self.action_window)
        draw_menu.addAction(self.action_room)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        tools_menu.addAction(self.action_select)

        # Snap menu
        snap_menu = menubar.addMenu("&Snap")
        snap_menu.addAction(self.action_snap)
        snap_menu.addSeparator()
        snap_menu.addAction(self.action_snap_endpoint)
        snap_menu.addAction(self.action_snap_midpoint)
        snap_menu.addAction(self.action_snap_extension)
        snap_menu.addSeparator()
        snap_menu.addAction(self.action_snap_perpendicular)
        snap_menu.addAction(self.action_snap_parallel)
        snap_menu.addAction(self.action_snap_angular)

        # Window menu
        self.window_menu = menubar.addMenu("&Window")

        # 3D menu (only if viewport module available)
        if HAS_VIEWPORT:
            view_3d_menu = menubar.addMenu("&3D")
            view_3d_menu.addAction(self.action_reset_camera)
            view_3d_menu.addSeparator()
            view_3d_menu.addAction(self.action_toggle_3d_view)
            view_3d_menu.addAction(self.action_3d_split)

    def _create_toolbars(self):
        """Create toolbars."""
        # Main toolbar
        main_toolbar = QToolBar("Main")
        main_toolbar.setObjectName("main_toolbar")
        main_toolbar.addAction(self.action_new)
        main_toolbar.addAction(self.action_open)
        main_toolbar.addAction(self.action_save)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self.action_undo)
        main_toolbar.addAction(self.action_redo)
        main_toolbar.addSeparator()
        main_toolbar.addAction(self.action_regenerate_sheets)
        self.addToolBar(main_toolbar)

        # Tools toolbar
        tools_toolbar = QToolBar("Tools")
        tools_toolbar.setObjectName("tools_toolbar")
        tools_toolbar.addAction(self.action_select)
        tools_toolbar.addAction(self.action_wall)
        tools_toolbar.addAction(self.action_door)
        tools_toolbar.addAction(self.action_window)
        tools_toolbar.addAction(self.action_room)
        self.addToolBar(tools_toolbar)

        # Options toolbar
        options_toolbar = QToolBar("Options")
        options_toolbar.setObjectName("options_toolbar")
        options_toolbar.addAction(self.action_ortho)
        options_toolbar.addAction(self.action_grid)
        options_toolbar.addAction(self.action_snap)
        options_toolbar.addSeparator()
        options_toolbar.addAction(self.action_pin)
        self.addToolBar(options_toolbar)

        # 3D Viewport toolbar (only if viewport module available)
        if HAS_VIEWPORT:
            viewport_toolbar = QToolBar("3D Viewport")
            viewport_toolbar.setObjectName("viewport_toolbar")
            viewport_toolbar.addAction(self.action_reset_camera)
            viewport_toolbar.addAction(self.action_toggle_3d_view)
            viewport_toolbar.addAction(self.action_3d_split)
            self.addToolBar(viewport_toolbar)

    def _create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Connect status message event
        event_bus.status_message.connect(self._show_status_message)

    def _create_dock_widgets(self):
        """Create dockable panels."""
        from panels.version_history import VersionHistoryPanel
        from panels.properties_panel import PropertiesPanel

        # Project Browser dock (left side)
        self.project_dock = QDockWidget("Project Browser", self)
        self.project_dock.setObjectName("project_dock")
        self.project_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        # Placeholder widget for now
        project_widget = QWidget()
        project_widget.setMinimumWidth(200)
        self.project_dock.setWidget(project_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)
        self.window_menu.addAction(self.project_dock.toggleViewAction())

        # Properties dock (right side)
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_dock.setObjectName("properties_dock")
        self.properties_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.properties_panel = PropertiesPanel(self.document)
        self.properties_panel.setMinimumWidth(250)
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.window_menu.addAction(self.properties_dock.toggleViewAction())

        # Sheet Manager dock (left side, tabbed with project browser)
        self.sheets_dock = QDockWidget("Sheets", self)
        self.sheets_dock.setObjectName("sheets_dock")
        self.sheets_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.sheet_manager = SheetManagerPanel(self._sheet_registry, self)
        self.sheet_manager.setMinimumWidth(200)
        self.sheet_manager.regenerate_requested.connect(self._on_regenerate_sheet)
        self.sheet_manager.sheet_double_clicked.connect(self._on_open_sheet)
        self.sheets_dock.setWidget(self.sheet_manager)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sheets_dock)
        self.tabifyDockWidget(self.project_dock, self.sheets_dock)
        self.sheets_dock.raise_()  # Show sheets dock by default
        self.window_menu.addAction(self.sheets_dock.toggleViewAction())

        # Connect generator service signals
        self._generator_service.generation_started.connect(
            lambda sid: self.status_bar.showMessage(f"Generating {sid}...")
        )
        self._generator_service.generation_completed.connect(
            lambda sid: self.status_bar.showMessage(f"Generated {sid}", 3000)
        )
        self._generator_service.generation_failed.connect(
            lambda sid, err: self.status_bar.showMessage(f"Generation failed: {err}", 5000)
        )
        self._generator_service.progress_updated.connect(self.sheet_manager.show_progress)
        self._generator_service.all_generation_completed.connect(self.sheet_manager.hide_progress)

        # Version History dock (right side, tabbed with properties)
        self.history_dock = QDockWidget("Version History", self)
        self.history_dock.setObjectName("history_dock")
        self.history_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.history_panel = VersionHistoryPanel(self.document)
        self.history_panel.setMinimumWidth(250)
        self.history_dock.setWidget(self.history_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.history_dock)
        # Tab it with properties dock
        self.tabifyDockWidget(self.properties_dock, self.history_dock)
        self.window_menu.addAction(self.history_dock.toggleViewAction())

        # Chat panel dock (right side, tabbed with properties)
        self.chat_dock = QDockWidget("Design Chat", self)
        self.chat_dock.setObjectName("chat_dock")
        self.chat_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.chat_panel = ChatPanel(self.document)
        self.chat_panel.setMinimumWidth(280)
        self.chat_panel.message_sent.connect(self._on_chat_message)
        self.chat_panel.schema_updated.connect(self._on_schema_updated)
        self.chat_dock.setWidget(self.chat_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.chat_dock)
        # Tab it with properties dock
        self.tabifyDockWidget(self.properties_dock, self.chat_dock)
        self.window_menu.addAction(self.chat_dock.toggleViewAction())

        # 3D Viewport dock (Vulkan renderer)
        if HAS_VIEWPORT:
            self.viewport_dock = QDockWidget("3D Viewport", self)
            self.viewport_dock.setObjectName("viewport_dock")
            self.viewport_dock.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea |
                Qt.DockWidgetArea.RightDockWidgetArea |
                Qt.DockWidgetArea.BottomDockWidgetArea
            )
            # Create the Vulkan viewport widget
            self.viewport_3d = VulkanViewportWidget()
            self.viewport_3d.setMinimumSize(400, 300)
            self.viewport_3d.initialized.connect(self._on_viewport_initialized)
            self.viewport_3d.load_complete.connect(self._on_viewport_load_complete)
            self.viewport_3d.error_occurred.connect(self._on_viewport_error)
            self.viewport_dock.setWidget(self.viewport_3d)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.viewport_dock)
            self.viewport_dock.show()  # Show 3D viewport by default
            self.window_menu.addAction(self.viewport_dock.toggleViewAction())

            # Connect document changes to viewport
            self.document.document_changed.connect(self._on_document_changed_viewport)

    def _create_central_widget(self):
        """Create the central tabbed widget with plan view and sheet views."""
        from views.plan_view import PlanView
        from tools.tool_manager import ToolManager
        from tools.base_tool import ToolType
        from tools.wall_tool import WallTool
        from tools.door_tool import DoorTool
        from tools.window_tool import WindowTool
        from tools.room_tool import RoomTool

        # Create central tab widget
        self.central_tabs = QTabWidget(self)
        self.central_tabs.setTabsClosable(True)
        self.central_tabs.setMovable(True)
        self.central_tabs.tabCloseRequested.connect(self._on_tab_close_requested)

        # Create the main plan view
        self.plan_view = PlanView(self.document, self.config, self)

        # Create split view container (for 2D | 3D side-by-side mode)
        self._split_mode = False
        self._split_viewport: Optional[VulkanViewportWidget] = None

        # Disable split viewport for now to simplify (use dock viewport only)
        self.central_tabs.addTab(self.plan_view, "Editor")

        # Don't allow closing the Editor tab
        self.central_tabs.tabBar().setTabButton(0, self.central_tabs.tabBar().ButtonPosition.RightSide, None)

        self.setCentralWidget(self.central_tabs)

        # Track open sheet tabs
        self._sheet_tabs: dict = {}  # sheet_id -> tab index

        # Create tool manager
        self.tool_manager = ToolManager(self.plan_view, self.document, self)
        self.plan_view.set_tool_manager(self.tool_manager)

        # Register additional tools
        wall_tool = WallTool(self.plan_view, self.document, self.config)
        self.tool_manager.register_tool(ToolType.WALL, wall_tool)

        door_tool = DoorTool(self.plan_view, self.document, self.config)
        self.tool_manager.register_tool(ToolType.DOOR, door_tool)

        window_tool = WindowTool(self.plan_view, self.document, self.config)
        self.tool_manager.register_tool(ToolType.WINDOW, window_tool)

        room_tool = RoomTool(self.plan_view, self.document, self.config)
        self.tool_manager.register_tool(ToolType.ROOM, room_tool)

        # Connect tool actions
        self.action_select.triggered.connect(lambda: self._set_tool(ToolType.SELECT))
        self.action_wall.triggered.connect(lambda: self._set_tool(ToolType.WALL))
        self.action_door.triggered.connect(lambda: self._set_tool(ToolType.DOOR))
        self.action_window.triggered.connect(lambda: self._set_tool(ToolType.WINDOW))
        self.action_room.triggered.connect(lambda: self._set_tool(ToolType.ROOM))

        # Connect zoom actions
        self.action_zoom_in.triggered.connect(self.plan_view.zoom_in)
        self.action_zoom_out.triggered.connect(self.plan_view.zoom_out)
        self.action_zoom_fit.triggered.connect(self.plan_view.zoom_fit)

        # Update tool action states when tool changes
        self.tool_manager.tool_changed.connect(self._on_tool_changed)

    def _set_tool(self, tool_type):
        """Switch to a tool."""
        from tools.base_tool import ToolType
        self.tool_manager.set_tool(tool_type)

    def _on_tool_changed(self, tool_name: str):
        """Update action check states when tool changes."""
        self.action_select.setChecked(tool_name == "SelectTool")
        self.action_wall.setChecked(tool_name == "WallTool")
        self.action_door.setChecked(tool_name == "DoorTool")
        self.action_window.setChecked(tool_name == "WindowTool")
        self.action_room.setChecked(tool_name == "RoomTool")

    def _connect_signals(self):
        """Connect document and event signals."""
        self.document.document_changed.connect(self._update_title)
        event_bus.document_loaded.connect(self._on_document_loaded)
        event_bus.document_modified.connect(self._on_document_modified)
        event_bus.selection_changed.connect(self._on_selection_changed)

        # Connect generator service to document changes (disabled by default to avoid blocking)
        # Users can enable auto-regenerate in the sheets panel
        self._sheet_registry.auto_regenerate = False
        self._generator_service.connect_to_document(self.document)

    def _on_selection_changed(self, selected_items):
        """Handle selection change - update pin button state."""
        if not selected_items:
            self.action_pin.setChecked(False)
            self.action_pin.setEnabled(False)
            return

        self.action_pin.setEnabled(True)

        # Check if any selected item is pinned
        any_pinned = False
        for item in selected_items:
            item_type = type(item).__name__
            if item_type == "WallItem" and hasattr(item, 'wall') and item.wall.is_pinned:
                any_pinned = True
                break
            elif item_type == "DoorItem" and hasattr(item, 'door') and item.door.is_pinned:
                any_pinned = True
                break
            elif item_type == "WindowItem" and hasattr(item, 'window') and item.window.is_pinned:
                any_pinned = True
                break
            elif item_type == "RoomItem" and hasattr(item, 'room') and item.room.is_pinned:
                any_pinned = True
                break

        # Block signal to prevent triggering toggle while updating
        self.action_pin.blockSignals(True)
        self.action_pin.setChecked(any_pinned)
        self.action_pin.blockSignals(False)

    def _restore_state(self):
        """Restore window geometry and state."""
        settings = QSettings("ArchEngine", "CAD")
        geometry = settings.value("geometry")
        state = settings.value("state")

        if geometry:
            self.restoreGeometry(geometry)
        if state:
            self.restoreState(state)

    def _save_state(self):
        """Save window geometry and state."""
        settings = QSettings("ArchEngine", "CAD")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())

    # =========================================================================
    # File Operations
    # =========================================================================

    def _on_new(self):
        """Create new document."""
        if not self._check_save():
            return
        self.document.new()

    def _on_open(self):
        """Open existing document."""
        if not self._check_save():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self.open_project(Path(file_path))

    def open_project(self, file_path: Path):
        """Open a project file."""
        if self.document.load(file_path):
            self.config.add_recent_file(file_path)
            self.status_bar.showMessage(f"Loaded: {file_path.name}", 5000)
        else:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not load file: {file_path}"
            )

    def _on_save(self):
        """Save current document."""
        if self.document.file_path:
            self.document.save()
            self.status_bar.showMessage("Saved", 3000)
        else:
            self._on_save_as()

    def _on_save_as(self):
        """Save document with new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            if self.document.save(Path(file_path)):
                self.config.add_recent_file(Path(file_path))
                self.status_bar.showMessage(f"Saved: {Path(file_path).name}", 5000)

    def _check_save(self) -> bool:
        """Check if document should be saved. Returns False to cancel."""
        if not self.document.modified:
            return True

        result = QMessageBox.question(
            self,
            "Save Changes?",
            "The document has been modified. Save changes?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Save:
            self._on_save()
            return True
        elif result == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    # =========================================================================
    # Edit Operations
    # =========================================================================

    def _on_undo(self):
        """Undo last action."""
        self.document.undo_stack.undo()

    def _on_redo(self):
        """Redo last undone action."""
        self.document.undo_stack.redo()

    def _on_delete(self):
        """Delete selected elements."""
        if self.tool_manager and self.tool_manager.current_tool:
            tool = self.tool_manager.current_tool
            if hasattr(tool, '_delete_selected'):
                tool._delete_selected()

    # =========================================================================
    # Toggle Operations
    # =========================================================================

    def _toggle_ortho(self, checked: bool):
        """Toggle orthographic mode."""
        self.config.ortho_mode = checked
        self.config.save()
        self.status_bar.showMessage(f"Ortho: {'On' if checked else 'Off'}", 2000)

    def _toggle_grid(self, checked: bool):
        """Toggle grid visibility."""
        self.config.grid_visible = checked
        self.config.save()
        if hasattr(self, 'plan_view'):
            self.plan_view.set_grid_visible(checked)
        self.status_bar.showMessage(f"Grid: {'On' if checked else 'Off'}", 2000)

    def _toggle_snap(self, checked: bool):
        """Toggle snap mode."""
        self.config.snap_enabled = checked
        self.config.save()
        self.status_bar.showMessage(f"Snap: {'On' if checked else 'Off'}", 2000)

    def _toggle_snap_type(self, snap_type: str):
        """Toggle individual snap type."""
        attr_name = f'snap_{snap_type}'
        action_name = f'action_snap_{snap_type}'

        if hasattr(self.config, attr_name) and hasattr(self, action_name):
            action = getattr(self, action_name)
            new_value = action.isChecked()
            setattr(self.config, attr_name, new_value)
            self.config.save()

            # Update snap manager's cached snap points if endpoint/midpoint changed
            if snap_type in ('endpoint', 'midpoint') and hasattr(self, 'plan_view'):
                self.plan_view._snap_manager.collect_snap_points()

            self.status_bar.showMessage(f"Snap {snap_type.title()}: {'On' if new_value else 'Off'}", 2000)

    # =========================================================================
    # Pin/LLM Operations
    # =========================================================================

    def _on_pin_toggle(self, checked: bool):
        """Toggle pin state on selected elements."""
        selected = self.plan_view.scene.selectedItems() if hasattr(self, 'plan_view') else []
        if not selected:
            self.status_bar.showMessage("No elements selected to pin", 2000)
            return

        count = 0
        for item in selected:
            item_type = type(item).__name__

            if item_type == "WallItem" and hasattr(item, 'wall'):
                self.document.pin_element("wall", str(item.wall.index), checked)
                count += 1
            elif item_type == "DoorItem" and hasattr(item, 'door'):
                self.document.pin_element("door", str(item.door.index), checked)
                count += 1
            elif item_type == "WindowItem" and hasattr(item, 'window'):
                self.document.pin_element("window", str(item.window.index), checked)
                count += 1
            elif item_type == "RoomItem" and hasattr(item, 'room'):
                self.document.pin_element("room", item.room.id, checked)
                count += 1

        if count > 0:
            action = "Pinned" if checked else "Unpinned"
            self.status_bar.showMessage(f"{action} {count} element(s)", 2000)
            # Refresh view to show pin indicators
            if hasattr(self, 'plan_view'):
                self.plan_view.refresh()

    def _on_chat_message(self, message: str):
        """Handle chat message from chat panel."""
        # This is called when user sends a message
        # The chat panel handles LLM integration internally
        self.status_bar.showMessage(f"Processing: {message[:30]}...", 2000)

    def _on_schema_updated(self, schema: dict):
        """Handle schema update from LLM."""
        # Refresh all views
        if hasattr(self, 'plan_view'):
            self.plan_view.refresh()

        # Update 3D viewport
        if HAS_VIEWPORT and hasattr(self, 'viewport_3d'):
            if self.viewport_3d.is_initialized:
                self.viewport_3d.load_json(schema)

        self.status_bar.showMessage("Design updated by LLM", 3000)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _update_title(self):
        """Update window title based on document state."""
        title = "ArchEngine CAD"
        if self.document.file_path:
            title = f"{self.document.file_path.name} - {title}"
        if self.document.modified:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _on_document_loaded(self, path: str):
        """Handle document loaded event."""
        self._update_title()
        if hasattr(self, 'plan_view'):
            self.plan_view.refresh()

    def _on_document_modified(self):
        """Handle document modified event."""
        self._update_title()

    def _on_document_changed_livesync(self):
        """Send document changes to UE5 via LiveSync."""
        if self._livesync_server and self._livesync_server.client_count > 0:
            data = self.document.get_data()
            self._livesync_server.send_building_data(data)

    def _on_document_changed_vulkan(self):
        """Send document changes to Vulkan renderer via VulkanSync."""
        if self._vulkan_sync and self._vulkan_sync.is_connected:
            data = self.document.get_data()
            self._vulkan_sync.send_building_data(data)

    def _on_vulkan_connected(self):
        """Handle Vulkan renderer connection."""
        self.status_bar.showMessage("Connected to Vulkan renderer", 5000)
        # Send current building data immediately
        data = self.document.get_data()
        if data:
            self._vulkan_sync.send_building_data(data)

    def _on_vulkan_disconnected(self):
        """Handle Vulkan renderer disconnection."""
        self.status_bar.showMessage("Vulkan renderer disconnected", 3000)

    def _on_document_changed_viewport(self):
        """Schedule throttled update to embedded Vulkan viewport(s)."""
        if HAS_VIEWPORT:
            # Restart timer - only update after 50ms of no changes (prevents lag during dragging)
            self._viewport_update_timer.start()

    def _do_viewport_update(self):
        """Actually send data to viewport(s) (called by throttle timer)."""
        if not HAS_VIEWPORT:
            return

        data = self.document.get_data() if hasattr(self.document, 'get_data') else self.document._data
        if not data:
            return

        # Update dock viewport
        if hasattr(self, 'viewport_3d') and self.viewport_3d.is_initialized:
            self.viewport_3d.load_json(data)

        # Update split viewport if in split mode
        if self._split_viewport and self._split_viewport.is_initialized:
            self._split_viewport.load_json(data)

    def _on_viewport_initialized(self):
        """Handle viewport initialization complete."""
        self.status_bar.showMessage("3D Viewport ready", 3000)
        # Load current document data if available
        data = self.document.get_data() if hasattr(self.document, 'get_data') else self.document._data
        if data:
            # Update whichever viewport just initialized
            if hasattr(self, 'viewport_3d') and self.viewport_3d.is_initialized:
                self.viewport_3d.load_json(data)
            if self._split_viewport and self._split_viewport.is_initialized:
                self._split_viewport.load_json(data)

    def _on_viewport_load_complete(self, element_count: int):
        """Handle viewport loaded building data."""
        self.status_bar.showMessage(f"3D View: {element_count} elements", 3000)

    def _on_viewport_error(self, error: str):
        """Handle viewport error."""
        self.status_bar.showMessage(f"3D Viewport Error: {error}", 5000)

    def _show_status_message(self, message: str, timeout: int):
        """Show message in status bar."""
        self.status_bar.showMessage(message, timeout)

    def closeEvent(self, event):
        """Handle window close."""
        if self._check_save():
            self._save_state()
            self.config.save()
            # Stop LiveSync server
            if self._livesync_server:
                self._livesync_server.stop()
            # Disconnect from Vulkan renderer
            if self._vulkan_sync:
                self._vulkan_sync.disconnect()
            # Disconnect from UE5 if connected
            if HAS_VIEWPORT:
                if hasattr(self, 'viewport_3d') and self.viewport_3d.is_connected:
                    self.viewport_3d.disconnect_from_ue5()
                if self._split_viewport and self._split_viewport.is_connected:
                    self._split_viewport.disconnect_from_ue5()
            event.accept()
        else:
            event.ignore()

    # =========================================================================
    # UE5 3D Viewport Operations
    # =========================================================================

    def _reset_viewport_camera(self):
        """Reset the 3D viewport camera to fit the building."""
        if not HAS_VIEWPORT:
            return

        viewport = self._get_active_viewport()
        if viewport and viewport.is_initialized:
            viewport.reset_camera()
            self.status_bar.showMessage("Camera reset to fit building", 2000)

    def _toggle_3d_view(self, checked: bool):
        """Toggle 3D viewport dock visibility."""
        if not HAS_VIEWPORT:
            return

        if hasattr(self, 'viewport_dock'):
            self.viewport_dock.setVisible(checked)
            if checked:
                self.status_bar.showMessage("3D Viewport visible", 2000)
                # Load document data if viewport just became visible
                if self.viewport_3d.is_initialized and self.document._data:
                    self.viewport_3d.load_json(self.document._data)

    def _toggle_split_view(self, checked: bool):
        """Toggle split view mode (2D | 3D side-by-side)."""
        if not HAS_VIEWPORT or not self._split_viewport:
            return

        self._split_mode = checked
        if checked:
            self._split_viewport.show()
            # Set equal split
            total_width = self.central_splitter.width()
            self.central_splitter.setSizes([total_width // 2, total_width // 2])
            self.status_bar.showMessage("Split view enabled (2D | 3D)", 3000)
            # Load current document into split viewport
            if self._split_viewport.is_initialized and self.document._data:
                self._split_viewport.load_json(self.document._data)
        else:
            self._split_viewport.hide()
            self.central_splitter.setSizes([1, 0])
            self.status_bar.showMessage("Split view disabled", 3000)

    def _get_active_viewport(self) -> Optional['VulkanViewportWidget']:
        """Get the currently active/visible viewport."""
        if not HAS_VIEWPORT:
            return None

        # Prefer split viewport if in split mode
        if self._split_mode and self._split_viewport and self._split_viewport.isVisible():
            return self._split_viewport

        # Otherwise use dock viewport if visible
        if hasattr(self, 'viewport_3d') and hasattr(self, 'viewport_dock'):
            if self.viewport_dock.isVisible():
                return self.viewport_3d

        # Fallback to split viewport even if not visible
        if self._split_viewport:
            return self._split_viewport

        return getattr(self, 'viewport_3d', None)

    # =========================================================================
    # Sheet Operations
    # =========================================================================

    def _on_regenerate_sheet(self, sheet_id: str):
        """Handle sheet regeneration request."""
        if sheet_id:
            # Regenerate single sheet
            self._generator_service.generate_sheet(sheet_id)
        else:
            # Regenerate all sheets
            self._generator_service.generate_all()

    def _on_open_sheet(self, sheet_id: str):
        """Open a sheet in a new tab in the central area."""
        from views.sheet_view import SheetViewContainer

        sheet = self._sheet_registry.get_sheet(sheet_id)
        if not sheet:
            return

        # Check if already open - switch to that tab
        if sheet_id in self._sheet_tabs:
            tab_index = self._sheet_tabs[sheet_id]
            if tab_index < self.central_tabs.count():
                self.central_tabs.setCurrentIndex(tab_index)
                return

        # Generate if needed
        if not sheet.has_content:
            self._generator_service.generate_sheet(sheet_id)

        # Create sheet view container
        view_container = SheetViewContainer(self.config, self)
        view_container.set_sheet(sheet)

        # Add as new tab
        tab_title = f"{sheet.number}"
        tab_index = self.central_tabs.addTab(view_container, tab_title)
        self.central_tabs.setTabToolTip(tab_index, f"{sheet.number} - {sheet.title}")
        self._sheet_tabs[sheet_id] = tab_index

        # Switch to the new tab
        self.central_tabs.setCurrentIndex(tab_index)

    def _on_tab_close_requested(self, index: int):
        """Handle tab close request."""
        # Don't close the Editor tab (index 0)
        if index == 0:
            return

        # Find and remove from sheet_tabs tracking
        widget = self.central_tabs.widget(index)
        for sheet_id, tab_idx in list(self._sheet_tabs.items()):
            if tab_idx == index:
                del self._sheet_tabs[sheet_id]
                break

        # Update indices for tabs after the removed one
        for sheet_id, tab_idx in self._sheet_tabs.items():
            if tab_idx > index:
                self._sheet_tabs[sheet_id] = tab_idx - 1

        # Remove the tab
        self.central_tabs.removeTab(index)
