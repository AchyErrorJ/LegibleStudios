"""
Materials Panel - Assign materials/textures to building elements.

Provides UI for selecting and assigning materials from the material library
to walls, floors, roofs, and other building elements.
"""
import json
from pathlib import Path
from typing import Optional, Dict, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QPushButton, QGroupBox, QScrollArea, QFrame,
    QListWidget, QListWidgetItem, QSplitter, QTabWidget,
    QSlider, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QColor


# Material categories
MATERIAL_CATEGORIES = {
    "Exterior Walls": [
        "brick_red_01", "brick_brown_01", "brick_gray_01", "brick_old_01",
        "brick_buff_01", "brick_white_01", "brick_red_dark",
        "siding_vinyl_light", "siding_vinyl_dark", "siding_vinyl_slate",
        "siding_wood_cedar", "siding_wood_clapboard", "siding_wood_shingle",
        "siding_fiber_cement_smooth", "siding_fiber_cement_woodgrain",
    ],
    "Interior Walls": [
        "paint_white_flat", "paint_offwhite_matte", "paint_gray_eggshell",
        "paint_beige_satin",
    ],
    "Roofing": [
        "roof_shingle_asphalt_gray", "roof_shingle_asphalt_brown", "roof_shingle_asphalt_black",
        "roof_shingle_cedar_fresh", "roof_shingle_cedar_weathered",
        "roof_metal_standing_seam", "roof_metal_corrugated", "roof_metal_ribbed_galv",
    ],
    "Flooring": [
        "wood_floor_oak", "wood_floor_maple", "wood_floor_walnut",
    ],
    "Metal": [
        "metal_brushed", "metal_galvanized",
    ],
    "Structural": [
        "wood_structural_fir", "wood_structural_oak",
    ],
}


class MaterialPreviewWidget(QLabel):
    """Widget showing a material preview thumbnail."""

    clicked = pyqtSignal(str)  # material_id

    def __init__(self, material_id: str, material_name: str, parent=None):
        super().__init__(parent)
        self.material_id = material_id
        self.material_name = material_name

        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px solid #444;
                border-radius: 4px;
                background-color: #333;
            }
            QLabel:hover {
                border-color: #0af;
            }
        """)
        self.setToolTip(material_name)

        # Try to load preview image
        self._load_preview()

    def _load_preview(self):
        """Load material preview thumbnail."""
        # Look for albedo texture in materials directory
        materials_dir = Path(__file__).parent.parent / "materials"

        # Try different image formats
        for ext in ["png", "jpg", "jpeg"]:
            preview_path = materials_dir / self.material_id / f"albedo.{ext}"
            if preview_path.exists():
                pixmap = QPixmap(str(preview_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        60, 60,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.setPixmap(scaled)
                    return

        # Fallback: show material name abbreviation
        abbrev = self.material_name[:3].upper()
        self.setText(abbrev)
        self.setStyleSheet(self.styleSheet() + "color: #888; font-weight: bold;")

    def mousePressEvent(self, event):
        """Handle click to select material."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.material_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        """Update selection visual state."""
        if selected:
            self.setStyleSheet("""
                QLabel {
                    border: 2px solid #0af;
                    border-radius: 4px;
                    background-color: #335;
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    border: 2px solid #444;
                    border-radius: 4px;
                    background-color: #333;
                }
                QLabel:hover {
                    border-color: #0af;
                }
            """)


class MaterialsPanel(QWidget):
    """
    Panel for assigning materials to building elements.
    """

    # Signals
    material_assigned = pyqtSignal(str, str)  # element_type, material_id
    default_material_changed = pyqtSignal(str, str)  # category, material_id
    uv_scale_changed = pyqtSignal(float)  # scale value
    roughness_changed = pyqtSignal(float)  # multiplier
    metallic_changed = pyqtSignal(float)  # multiplier
    ao_strength_changed = pyqtSignal(float)  # strength

    def __init__(self, parent=None):
        super().__init__(parent)
        self._viewport = None
        self._document = None
        self._selected_material = None
        self._material_map = {}
        self._category_defaults = {}

        self._load_material_map()
        self._setup_ui()

    def _load_material_map(self):
        """Load material definitions from material_map.json."""
        materials_dir = Path(__file__).parent.parent / "materials"
        map_path = materials_dir / "material_map.json"

        if map_path.exists():
            try:
                with open(map_path, 'r') as f:
                    data = json.load(f)
                    self._material_map = data.get('materials', {})
                    self._category_defaults = data.get('category_defaults', {})
            except Exception as e:
                print(f"[MaterialsPanel] Failed to load material_map.json: {e}")

    def _setup_ui(self):
        """Set up the panel UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(8)

        # Header
        header = QLabel("Materials")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        content_layout.addWidget(header)

        # Selected material display
        self._create_selected_display(content_layout)

        # Default materials section
        self._create_defaults_group(content_layout)

        # Material browser tabs
        self._create_browser_tabs(content_layout)

        # Apply buttons
        self._create_apply_buttons(content_layout)

        # Material settings (UV scale, roughness, etc.)
        self._create_material_settings(content_layout)

        content_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _create_selected_display(self, parent_layout):
        """Create the selected material display section."""
        group = QGroupBox("Selected Material")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        # Preview
        self.selected_preview = QLabel()
        self.selected_preview.setFixedSize(48, 48)
        self.selected_preview.setStyleSheet("""
            border: 1px solid #555;
            border-radius: 4px;
            background-color: #333;
        """)
        self.selected_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_preview.setText("--")
        layout.addWidget(self.selected_preview)

        # Info
        info_layout = QVBoxLayout()
        self.selected_name = QLabel("No material selected")
        self.selected_name.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.selected_name)

        self.selected_type = QLabel("")
        self.selected_type.setStyleSheet("color: #888; font-size: 10px;")
        info_layout.addWidget(self.selected_type)

        layout.addLayout(info_layout, 1)

        parent_layout.addWidget(group)

    def _create_defaults_group(self, parent_layout):
        """Create default materials section."""
        group = QGroupBox("Default Materials")
        layout = QFormLayout(group)
        layout.setSpacing(5)

        # Exterior walls default
        self.ext_wall_combo = QComboBox()
        self.ext_wall_combo.addItems([self._get_material_name(m) for m in MATERIAL_CATEGORIES["Exterior Walls"]])
        self.ext_wall_combo.currentIndexChanged.connect(lambda i: self._on_default_changed("Walls_Exterior", i))
        layout.addRow("Ext. Walls:", self.ext_wall_combo)

        # Interior walls default
        self.int_wall_combo = QComboBox()
        self.int_wall_combo.addItems([self._get_material_name(m) for m in MATERIAL_CATEGORIES["Interior Walls"]])
        self.int_wall_combo.currentIndexChanged.connect(lambda i: self._on_default_changed("Walls_Interior", i))
        layout.addRow("Int. Walls:", self.int_wall_combo)

        # Roof default
        self.roof_combo = QComboBox()
        self.roof_combo.addItems([self._get_material_name(m) for m in MATERIAL_CATEGORIES["Roofing"]])
        self.roof_combo.currentIndexChanged.connect(lambda i: self._on_default_changed("Roofs", i))
        layout.addRow("Roofs:", self.roof_combo)

        # Floor default
        self.floor_combo = QComboBox()
        self.floor_combo.addItems([self._get_material_name(m) for m in MATERIAL_CATEGORIES["Flooring"]])
        self.floor_combo.currentIndexChanged.connect(lambda i: self._on_default_changed("Floors_Wood", i))
        layout.addRow("Floors:", self.floor_combo)

        parent_layout.addWidget(group)

    def _create_browser_tabs(self, parent_layout):
        """Create material browser with category tabs."""
        group = QGroupBox("Material Browser")
        layout = QVBoxLayout(group)

        self.browser_tabs = QTabWidget()
        self.browser_tabs.setStyleSheet("QTabWidget::pane { border: none; }")

        self._material_widgets = {}

        for category, materials in MATERIAL_CATEGORIES.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(5, 5, 5, 5)

            # Grid of material previews
            grid_widget = QWidget()
            grid_layout = QHBoxLayout(grid_widget)
            grid_layout.setSpacing(5)
            grid_layout.setContentsMargins(0, 0, 0, 0)

            # Create flow layout effect with wrapping
            flow_widget = QWidget()
            from PyQt6.QtWidgets import QGridLayout
            flow_layout = QGridLayout(flow_widget)
            flow_layout.setSpacing(5)

            row, col = 0, 0
            max_cols = 4

            for mat_id in materials:
                mat_name = self._get_material_name(mat_id)
                preview = MaterialPreviewWidget(mat_id, mat_name)
                preview.clicked.connect(self._on_material_clicked)
                flow_layout.addWidget(preview, row, col)
                self._material_widgets[mat_id] = preview

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            tab_layout.addWidget(flow_widget)
            tab_layout.addStretch()

            # Short tab name
            short_name = category.split()[0][:6]
            self.browser_tabs.addTab(tab, short_name)

        layout.addWidget(self.browser_tabs)
        parent_layout.addWidget(group)

    def _create_apply_buttons(self, parent_layout):
        """Create apply buttons section."""
        group = QGroupBox("Apply Material")
        layout = QVBoxLayout(group)
        layout.setSpacing(5)

        # Apply to selection button
        self.apply_selection_btn = QPushButton("Apply to Selected")
        self.apply_selection_btn.setEnabled(False)
        self.apply_selection_btn.clicked.connect(self._apply_to_selection)
        layout.addWidget(self.apply_selection_btn)

        # Apply to all of type buttons
        type_row = QHBoxLayout()

        self.apply_all_ext_btn = QPushButton("All Ext")
        self.apply_all_ext_btn.setToolTip("Apply to all exterior walls")
        self.apply_all_ext_btn.setEnabled(False)
        self.apply_all_ext_btn.clicked.connect(lambda: self._apply_to_type("exterior_wall"))
        type_row.addWidget(self.apply_all_ext_btn)

        self.apply_all_int_btn = QPushButton("All Int")
        self.apply_all_int_btn.setToolTip("Apply to all interior walls")
        self.apply_all_int_btn.setEnabled(False)
        self.apply_all_int_btn.clicked.connect(lambda: self._apply_to_type("interior_wall"))
        type_row.addWidget(self.apply_all_int_btn)

        self.apply_all_roof_btn = QPushButton("All Roof")
        self.apply_all_roof_btn.setToolTip("Apply to all roofs")
        self.apply_all_roof_btn.setEnabled(False)
        self.apply_all_roof_btn.clicked.connect(lambda: self._apply_to_type("roof"))
        type_row.addWidget(self.apply_all_roof_btn)

        layout.addLayout(type_row)

        parent_layout.addWidget(group)

    def _create_material_settings(self, parent_layout):
        """Create material settings section (UV scale, roughness, etc.)."""
        group = QGroupBox("Material Settings")
        layout = QFormLayout(group)
        layout.setSpacing(5)

        # UV Scale slider
        uv_layout = QHBoxLayout()
        self.uv_scale_spin = QDoubleSpinBox()
        self.uv_scale_spin.setRange(0.1, 250.0)
        self.uv_scale_spin.setValue(1.0)
        self.uv_scale_spin.setSingleStep(1.0)
        self.uv_scale_spin.setDecimals(1)
        self.uv_scale_spin.valueChanged.connect(self._on_uv_scale_changed)
        uv_layout.addWidget(self.uv_scale_spin)

        self.uv_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.uv_scale_slider.setRange(1, 250)  # 1 to 250
        self.uv_scale_slider.setValue(1)
        self.uv_scale_slider.valueChanged.connect(
            lambda v: self.uv_scale_spin.setValue(float(v))
        )
        uv_layout.addWidget(self.uv_scale_slider, 1)
        layout.addRow("UV Scale:", uv_layout)

        # Roughness multiplier
        rough_layout = QHBoxLayout()
        self.roughness_spin = QDoubleSpinBox()
        self.roughness_spin.setRange(0.0, 2.0)
        self.roughness_spin.setValue(1.0)
        self.roughness_spin.setSingleStep(0.05)
        self.roughness_spin.setDecimals(2)
        self.roughness_spin.valueChanged.connect(self._on_roughness_changed)
        rough_layout.addWidget(self.roughness_spin)

        self.roughness_slider = QSlider(Qt.Orientation.Horizontal)
        self.roughness_slider.setRange(0, 200)  # 0.0 to 2.0 (x100)
        self.roughness_slider.setValue(100)
        self.roughness_slider.valueChanged.connect(
            lambda v: self.roughness_spin.setValue(v / 100.0)
        )
        rough_layout.addWidget(self.roughness_slider, 1)
        layout.addRow("Roughness:", rough_layout)

        # Metallic multiplier
        metal_layout = QHBoxLayout()
        self.metallic_spin = QDoubleSpinBox()
        self.metallic_spin.setRange(0.0, 2.0)
        self.metallic_spin.setValue(1.0)
        self.metallic_spin.setSingleStep(0.05)
        self.metallic_spin.setDecimals(2)
        self.metallic_spin.valueChanged.connect(self._on_metallic_changed)
        metal_layout.addWidget(self.metallic_spin)

        self.metallic_slider = QSlider(Qt.Orientation.Horizontal)
        self.metallic_slider.setRange(0, 200)  # 0.0 to 2.0 (x100)
        self.metallic_slider.setValue(100)
        self.metallic_slider.valueChanged.connect(
            lambda v: self.metallic_spin.setValue(v / 100.0)
        )
        metal_layout.addWidget(self.metallic_slider, 1)
        layout.addRow("Metallic:", metal_layout)

        # AO Strength
        ao_layout = QHBoxLayout()
        self.ao_spin = QDoubleSpinBox()
        self.ao_spin.setRange(0.0, 1.0)
        self.ao_spin.setValue(1.0)
        self.ao_spin.setSingleStep(0.05)
        self.ao_spin.setDecimals(2)
        self.ao_spin.valueChanged.connect(self._on_ao_changed)
        ao_layout.addWidget(self.ao_spin)

        self.ao_slider = QSlider(Qt.Orientation.Horizontal)
        self.ao_slider.setRange(0, 100)  # 0.0 to 1.0 (x100)
        self.ao_slider.setValue(100)
        self.ao_slider.valueChanged.connect(
            lambda v: self.ao_spin.setValue(v / 100.0)
        )
        ao_layout.addWidget(self.ao_slider, 1)
        layout.addRow("AO Strength:", ao_layout)

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_material_settings)
        layout.addRow("", reset_btn)

        parent_layout.addWidget(group)

    def _on_uv_scale_changed(self, value: float):
        """Handle UV scale change."""
        self.uv_scale_slider.blockSignals(True)
        self.uv_scale_slider.setValue(int(value))
        self.uv_scale_slider.blockSignals(False)
        self.uv_scale_changed.emit(value)
        if self._viewport:
            self._viewport.set_uv_scale(value)

    def _on_roughness_changed(self, value: float):
        """Handle roughness change."""
        self.roughness_slider.blockSignals(True)
        self.roughness_slider.setValue(int(value * 100))
        self.roughness_slider.blockSignals(False)
        self.roughness_changed.emit(value)
        if self._viewport:
            self._viewport.set_roughness_multiplier(value)

    def _on_metallic_changed(self, value: float):
        """Handle metallic change."""
        self.metallic_slider.blockSignals(True)
        self.metallic_slider.setValue(int(value * 100))
        self.metallic_slider.blockSignals(False)
        self.metallic_changed.emit(value)
        if self._viewport:
            self._viewport.set_metallic_multiplier(value)

    def _on_ao_changed(self, value: float):
        """Handle AO strength change."""
        self.ao_slider.blockSignals(True)
        self.ao_slider.setValue(int(value * 100))
        self.ao_slider.blockSignals(False)
        self.ao_strength_changed.emit(value)
        if self._viewport:
            self._viewport.set_ao_strength(value)

    def _reset_material_settings(self):
        """Reset all material settings to defaults."""
        self.uv_scale_spin.setValue(1.0)
        self.roughness_spin.setValue(1.0)
        self.metallic_spin.setValue(1.0)
        self.ao_spin.setValue(1.0)

    def _get_material_name(self, material_id: str) -> str:
        """Get display name for a material."""
        if material_id in self._material_map:
            return self._material_map[material_id].get('name', material_id)
        # Convert ID to title case
        return material_id.replace('_', ' ').title()

    def _on_material_clicked(self, material_id: str):
        """Handle material selection."""
        # Update selection state
        if self._selected_material:
            old_widget = self._material_widgets.get(self._selected_material)
            if old_widget:
                old_widget.set_selected(False)

        self._selected_material = material_id
        new_widget = self._material_widgets.get(material_id)
        if new_widget:
            new_widget.set_selected(True)

        # Update selected display
        name = self._get_material_name(material_id)
        self.selected_name.setText(name)
        self.selected_type.setText(material_id)

        # Try to load preview
        materials_dir = Path(__file__).parent.parent / "materials"
        for ext in ["png", "jpg", "jpeg"]:
            preview_path = materials_dir / material_id / f"albedo.{ext}"
            if preview_path.exists():
                pixmap = QPixmap(str(preview_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        44, 44,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.selected_preview.setPixmap(scaled)
                    break
        else:
            self.selected_preview.setText(name[:3].upper())

        # Enable apply buttons
        self.apply_selection_btn.setEnabled(True)
        self.apply_all_ext_btn.setEnabled(True)
        self.apply_all_int_btn.setEnabled(True)
        self.apply_all_roof_btn.setEnabled(True)

    def _on_default_changed(self, category: str, index: int):
        """Handle default material change."""
        # Map category to material list
        category_map = {
            "Walls_Exterior": MATERIAL_CATEGORIES["Exterior Walls"],
            "Walls_Interior": MATERIAL_CATEGORIES["Interior Walls"],
            "Roofs": MATERIAL_CATEGORIES["Roofing"],
            "Floors_Wood": MATERIAL_CATEGORIES["Flooring"],
        }

        materials = category_map.get(category, [])
        if 0 <= index < len(materials):
            material_id = materials[index]
            self.default_material_changed.emit(category, material_id)

    def _apply_to_selection(self):
        """Apply selected material to currently selected elements."""
        if not self._selected_material:
            return

        # This would be connected to the document/viewport
        self.material_assigned.emit("selection", self._selected_material)

    def _apply_to_type(self, element_type: str):
        """Apply selected material to all elements of a type."""
        if not self._selected_material:
            return

        self.material_assigned.emit(element_type, self._selected_material)

    def set_viewport(self, viewport):
        """Connect to viewport widget."""
        self._viewport = viewport

    def set_document(self, document):
        """Connect to document."""
        self._document = document

    def get_selected_material(self) -> Optional[str]:
        """Get currently selected material ID."""
        return self._selected_material
