"""
Sheet Manager Panel - Drawing sheet tree view and management.

Provides a tree view of all drawing sheets organized by category,
with context menus for common operations.
"""
from typing import Optional, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMenu, QToolButton, QLabel, QLineEdit, QComboBox,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QFont

from sheets.models import SheetType, SheetConfig, SHEET_DEFAULTS
from sheets.sheet_registry import SheetRegistry


class SheetManagerPanel(QWidget):
    """
    Panel for managing drawing sheets.

    Shows sheets in a tree organized by category, with controls for
    regeneration, adding sheets, and changing settings.
    """

    # Signals
    sheet_selected = pyqtSignal(str)           # sheet_id
    sheet_double_clicked = pyqtSignal(str)     # sheet_id (opens in tab)
    regenerate_requested = pyqtSignal(str)     # sheet_id (empty = all)

    def __init__(self, registry: SheetRegistry, parent=None):
        super().__init__(parent)
        self._registry = registry
        self._category_items: Dict[str, QTreeWidgetItem] = {}
        self._sheet_items: Dict[str, QTreeWidgetItem] = {}

        self._setup_ui()
        self._connect_signals()
        self._refresh_tree()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header with title and buttons
        header = QHBoxLayout()
        header.setSpacing(4)

        title = QLabel("Sheets")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header.addWidget(title)

        header.addStretch()

        # Regenerate all button
        self._regen_btn = QToolButton()
        self._regen_btn.setText("⟳")
        self._regen_btn.setToolTip("Regenerate All Sheets")
        self._regen_btn.clicked.connect(lambda: self.regenerate_requested.emit(""))
        header.addWidget(self._regen_btn)

        # Add sheet button
        self._add_btn = QToolButton()
        self._add_btn.setText("+")
        self._add_btn.setToolTip("Add Sheet")
        self._add_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._add_btn.setMenu(self._create_add_menu())
        header.addWidget(self._add_btn)

        layout.addLayout(header)

        # Prefix input
        prefix_layout = QHBoxLayout()
        prefix_layout.setSpacing(4)
        prefix_label = QLabel("Prefix:")
        prefix_label.setStyleSheet("color: #666; font-size: 11px;")
        prefix_layout.addWidget(prefix_label)

        self._prefix_edit = QLineEdit(self._registry.prefix)
        self._prefix_edit.setMaximumWidth(60)
        self._prefix_edit.setPlaceholderText("A-")
        self._prefix_edit.editingFinished.connect(self._on_prefix_changed)
        prefix_layout.addWidget(self._prefix_edit)

        prefix_layout.addStretch()

        layout.addLayout(prefix_layout)

        # Tree widget
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree)

        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setMaximumHeight(16)
        self._progress.hide()
        layout.addWidget(self._progress)

        # Auto-regenerate toggle
        auto_layout = QHBoxLayout()
        auto_layout.setSpacing(4)

        from PyQt6.QtWidgets import QCheckBox
        self._auto_check = QCheckBox("Auto-regenerate")
        self._auto_check.setChecked(self._registry.auto_regenerate)
        self._auto_check.setStyleSheet("font-size: 11px; color: #666;")
        self._auto_check.toggled.connect(self._on_auto_toggled)
        auto_layout.addWidget(self._auto_check)

        auto_layout.addStretch()

        layout.addLayout(auto_layout)

    def _create_add_menu(self) -> QMenu:
        """Create the add sheet menu."""
        menu = QMenu(self)

        for sheet_type in SheetType:
            defaults = SHEET_DEFAULTS.get(sheet_type, {})
            title = defaults.get('title', sheet_type.value)
            action = menu.addAction(title)
            action.setData(sheet_type)
            action.triggered.connect(lambda checked, st=sheet_type: self._add_sheet(st))

        return menu

    def _connect_signals(self):
        """Connect registry signals."""
        self._registry.sheet_added.connect(self._on_sheet_added)
        self._registry.sheet_removed.connect(self._on_sheet_removed)
        self._registry.sheet_updated.connect(self._on_sheet_updated)
        self._registry.sheet_content_changed.connect(self._on_sheet_content_changed)
        self._registry.drawing_set_loaded.connect(self._refresh_tree)
        self._registry.prefix_changed.connect(self._on_prefix_changed_external)

    def _refresh_tree(self):
        """Rebuild the entire tree."""
        self._tree.clear()
        self._category_items.clear()
        self._sheet_items.clear()

        # Get categories
        categories = self._registry.get_categories()

        for category in categories:
            # Create category item
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            self._tree.addTopLevelItem(cat_item)
            self._category_items[category] = cat_item

            # Add sheets in category
            sheets = self._registry.get_sheets_by_category(category)
            for sheet in sheets:
                self._add_sheet_item(cat_item, sheet)

            cat_item.setExpanded(True)

    def _add_sheet_item(self, parent: QTreeWidgetItem, sheet: SheetConfig):
        """Add a sheet item to the tree."""
        text = f"{sheet.number} - {sheet.title}"
        item = QTreeWidgetItem([text])
        item.setData(0, Qt.ItemDataRole.UserRole, sheet.id)

        # Set status indicator
        if not sheet.enabled:
            item.setForeground(0, Qt.GlobalColor.gray)
        elif sheet.has_content:
            item.setForeground(0, Qt.GlobalColor.darkGreen)
        else:
            item.setForeground(0, Qt.GlobalColor.darkRed)

        parent.addChild(item)
        self._sheet_items[sheet.id] = item

    def _update_sheet_item(self, sheet_id: str):
        """Update a sheet item in the tree."""
        item = self._sheet_items.get(sheet_id)
        sheet = self._registry.get_sheet(sheet_id)

        if item and sheet:
            text = f"{sheet.number} - {sheet.title}"
            item.setText(0, text)

            # Update status indicator
            if not sheet.enabled:
                item.setForeground(0, Qt.GlobalColor.gray)
            elif sheet.has_content:
                item.setForeground(0, Qt.GlobalColor.darkGreen)
            else:
                item.setForeground(0, Qt.GlobalColor.darkRed)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click."""
        sheet_id = item.data(0, Qt.ItemDataRole.UserRole)
        if sheet_id:
            self.sheet_selected.emit(sheet_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item double-click."""
        sheet_id = item.data(0, Qt.ItemDataRole.UserRole)
        if sheet_id:
            self.sheet_double_clicked.emit(sheet_id)

    def _show_context_menu(self, pos):
        """Show context menu for items."""
        item = self._tree.itemAt(pos)
        if not item:
            return

        sheet_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not sheet_id:
            return

        sheet = self._registry.get_sheet(sheet_id)
        if not sheet:
            return

        menu = QMenu(self)

        # Open in tab
        open_action = menu.addAction("Open in Tab")
        open_action.triggered.connect(lambda: self.sheet_double_clicked.emit(sheet_id))

        menu.addSeparator()

        # Regenerate
        regen_action = menu.addAction("Regenerate")
        regen_action.triggered.connect(lambda: self.regenerate_requested.emit(sheet_id))

        menu.addSeparator()

        # Enable/disable
        if sheet.enabled:
            disable_action = menu.addAction("Disable Auto-Regenerate")
            disable_action.triggered.connect(
                lambda: self._registry.update_sheet(sheet_id, enabled=False)
            )
        else:
            enable_action = menu.addAction("Enable Auto-Regenerate")
            enable_action.triggered.connect(
                lambda: self._registry.update_sheet(sheet_id, enabled=True)
            )

        menu.addSeparator()

        # Remove
        remove_action = menu.addAction("Remove Sheet")
        remove_action.triggered.connect(lambda: self._registry.remove_sheet(sheet_id))

        menu.exec(self._tree.mapToGlobal(pos))

    def _add_sheet(self, sheet_type: SheetType):
        """Add a new sheet."""
        self._registry.add_sheet(sheet_type)

    def _on_prefix_changed(self):
        """Handle prefix change from input."""
        new_prefix = self._prefix_edit.text().strip()
        if new_prefix and new_prefix != self._registry.prefix:
            self._registry.prefix = new_prefix

    def _on_prefix_changed_external(self, new_prefix: str):
        """Handle prefix changed externally."""
        self._prefix_edit.setText(new_prefix)
        self._refresh_tree()

    def _on_auto_toggled(self, checked: bool):
        """Handle auto-regenerate toggle."""
        self._registry.auto_regenerate = checked

    def _on_sheet_added(self, sheet_id: str):
        """Handle sheet added."""
        sheet = self._registry.get_sheet(sheet_id)
        if not sheet:
            return

        category = sheet.category
        cat_item = self._category_items.get(category)

        if not cat_item:
            # Create category item
            cat_item = QTreeWidgetItem([category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            self._tree.addTopLevelItem(cat_item)
            self._category_items[category] = cat_item
            cat_item.setExpanded(True)

        self._add_sheet_item(cat_item, sheet)

    def _on_sheet_removed(self, sheet_id: str):
        """Handle sheet removed."""
        item = self._sheet_items.pop(sheet_id, None)
        if item:
            parent = item.parent()
            if parent:
                parent.removeChild(item)
                # Remove empty category
                if parent.childCount() == 0:
                    index = self._tree.indexOfTopLevelItem(parent)
                    if index >= 0:
                        self._tree.takeTopLevelItem(index)
                        # Find and remove from category items
                        for cat, cat_item in list(self._category_items.items()):
                            if cat_item is parent:
                                del self._category_items[cat]
                                break

    def _on_sheet_updated(self, sheet_id: str):
        """Handle sheet updated."""
        self._update_sheet_item(sheet_id)

    def _on_sheet_content_changed(self, sheet_id: str):
        """Handle sheet content changed."""
        self._update_sheet_item(sheet_id)

    # =========================================================================
    # Progress
    # =========================================================================

    def show_progress(self, current: int, total: int):
        """Show generation progress."""
        if total > 0:
            self._progress.setMaximum(total)
            self._progress.setValue(current)
            self._progress.show()
        else:
            self._progress.hide()

    def hide_progress(self):
        """Hide progress bar."""
        self._progress.hide()
