"""
ArchEngine CAD Main Application Window
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QIcon, QKeySequence

from app.config import Config
from core.document import ArchDocument
from core.events import event_bus


class ArchEngineApplication(QMainWindow):
    """
    Main application window.
    Central hub for all views and panels.
    """

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.document = ArchDocument(self)

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

        # View menu
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.action_zoom_in)
        view_menu.addAction(self.action_zoom_out)
        view_menu.addAction(self.action_zoom_fit)
        view_menu.addSeparator()
        view_menu.addAction(self.action_grid)

        # Draw menu
        draw_menu = menubar.addMenu("&Draw")
        draw_menu.addAction(self.action_wall)
        draw_menu.addAction(self.action_door)
        draw_menu.addAction(self.action_window)

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
        self.addToolBar(main_toolbar)

        # Tools toolbar
        tools_toolbar = QToolBar("Tools")
        tools_toolbar.setObjectName("tools_toolbar")
        tools_toolbar.addAction(self.action_select)
        tools_toolbar.addAction(self.action_wall)
        tools_toolbar.addAction(self.action_door)
        tools_toolbar.addAction(self.action_window)
        self.addToolBar(tools_toolbar)

        # Options toolbar
        options_toolbar = QToolBar("Options")
        options_toolbar.setObjectName("options_toolbar")
        options_toolbar.addAction(self.action_ortho)
        options_toolbar.addAction(self.action_grid)
        options_toolbar.addAction(self.action_snap)
        self.addToolBar(options_toolbar)

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
        # Placeholder widget for now
        properties_widget = QWidget()
        properties_widget.setMinimumWidth(250)
        self.properties_dock.setWidget(properties_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.window_menu.addAction(self.properties_dock.toggleViewAction())

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

    def _create_central_widget(self):
        """Create the central plan view widget."""
        from views.plan_view import PlanView
        from tools.tool_manager import ToolManager
        from tools.base_tool import ToolType
        from tools.wall_tool import WallTool

        self.plan_view = PlanView(self.document, self.config, self)
        self.setCentralWidget(self.plan_view)

        # Create tool manager
        self.tool_manager = ToolManager(self.plan_view, self.document, self)
        self.plan_view.set_tool_manager(self.tool_manager)

        # Register additional tools
        wall_tool = WallTool(self.plan_view, self.document, self.config)
        self.tool_manager.register_tool(ToolType.WALL, wall_tool)

        # Connect tool actions
        self.action_select.triggered.connect(lambda: self._set_tool(ToolType.SELECT))
        self.action_wall.triggered.connect(lambda: self._set_tool(ToolType.WALL))

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

    def _connect_signals(self):
        """Connect document and event signals."""
        self.document.document_changed.connect(self._update_title)
        event_bus.document_loaded.connect(self._on_document_loaded)
        event_bus.document_modified.connect(self._on_document_modified)

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

    def _show_status_message(self, message: str, timeout: int):
        """Show message in status bar."""
        self.status_bar.showMessage(message, timeout)

    def closeEvent(self, event):
        """Handle window close."""
        if self._check_save():
            self._save_state()
            self.config.save()
            event.accept()
        else:
            event.ignore()
