"""
Site Definition Dialog
=======================
First step in building design - define the site before generating the building.
Import topography, set boundaries, identify road, views, and constraints.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.terrain import generate_terrain_from_site, TerrainMesh

# Google Maps integration disabled due to QWebEngine crashes
# Using custom site editor widget instead
HAS_GOOGLE_MAPS_WIDGET = False
GoogleMapsWidget = None

# Embedded map widget - lazy import to avoid crashes
HAS_EMBEDDED_MAP = True  # Will check on actual use

# Import static map widget (satellite imagery with drawing, no QWebEngine)
try:
    from widgets.static_map_widget import StaticMapWidget
    HAS_STATIC_MAP = True
    print("[SiteDialog] Static map widget imported successfully")
except ImportError as e:
    HAS_STATIC_MAP = False
    print(f"[SiteDialog] Static map widget not available: {e}")

# Import site editor widget
try:
    from widgets.site_editor_widget import SiteEditorWidget
    HAS_SITE_EDITOR = True
except ImportError:
    HAS_SITE_EDITOR = False
    print("[SiteDialog] Site editor widget not available")

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QPushButton, QGroupBox,
    QFormLayout, QTabWidget, QWidget, QFileDialog, QMessageBox,
    QGridLayout, QCheckBox, QTextEdit, QSlider, QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSettings
from PyQt6.QtGui import QDoubleValidator
from pathlib import Path
import json
import os
import requests


# Sample sites for testing
SAMPLE_SITES = {
    "Suburban Family Lot": {
        "property_width_ft": 100,
        "property_depth_ft": 120,
        "road_location": "Front (South)",
        "road_width_ft": 30,
        "driveway_required": True,
        "setback_front_ft": 20,
        "setback_rear_ft": 25,
        "setback_side_ft": 10,
        "max_coverage_percent": 40,
        "max_height_ft": 35,
        "slope": "Flat (0-5%)",
        "elevation_change_ft": 2,
        "solar_orientation": "South-facing (optimal)",
        "solar_access": True,
        "views": {"north": False, "east": False, "south": True, "west": False},
        "feature_notes": "Flat suburban lot with mature oak tree in rear. Neighbors on both sides.",
        "imported_files": {"survey": "No survey loaded", "topography": "No topography loaded", "map": "No map loaded", "cad": "No CAD file loaded"},
    },
    "Urban Corner Lot": {
        "property_width_ft": 50,
        "property_depth_ft": 80,
        "road_location": "Corner Lot",
        "road_width_ft": 40,
        "driveway_required": False,
        "setback_front_ft": 15,
        "setback_rear_ft": 20,
        "setback_side_ft": 5,
        "max_coverage_percent": 60,
        "max_height_ft": 45,
        "slope": "Flat (0-5%)",
        "elevation_change_ft": 0,
        "solar_orientation": "Southeast-facing",
        "solar_access": False,
        "views": {"north": True, "east": True, "south": False, "west": False},
        "feature_notes": "Urban infill lot. Two street frontages. Adjacent to commercial mixed-use to the east.",
        "imported_files": {"survey": "No survey loaded", "topography": "No topography loaded", "map": "No map loaded", "cad": "No CAD file loaded"},
    },
    "Sloped Rural Lot": {
        "property_width_ft": 200,
        "property_depth_ft": 300,
        "road_location": "Front (North)",
        "road_width_ft": 20,
        "driveway_required": True,
        "setback_front_ft": 50,
        "setback_rear_ft": 50,
        "setback_side_ft": 25,
        "max_coverage_percent": 20,
        "max_height_ft": 35,
        "slope": "Moderate Slope (15-25%)",
        "elevation_change_ft": 40,
        "solar_orientation": "South-facing (optimal)",
        "solar_access": True,
        "views": {"north": False, "east": False, "south": True, "west": True},
        "feature_notes": "Sloped lot with mountain views to south and west. Creek at rear property line. Requires walkout basement design.",
        "imported_files": {"survey": "No survey loaded", "topography": "No topography loaded", "map": "No map loaded", "cad": "No CAD file loaded"},
    },
    "Lakeside Property": {
        "property_width_ft": 80,
        "property_depth_ft": 150,
        "road_location": "Rear (North)",
        "road_width_ft": 25,
        "driveway_required": True,
        "setback_front_ft": 20,
        "setback_rear_ft": 10,
        "setback_side_ft": 10,
        "max_coverage_percent": 35,
        "max_height_ft": 30,
        "slope": "Gentle Slope (5-15%)",
        "elevation_change_ft": 8,
        "solar_orientation": "Southwest-facing",
        "solar_access": True,
        "views": {"north": False, "east": False, "south": True, "west": False},
        "feature_notes": "Waterfront property on south side. Lake views from all main rooms. Wetlands setback on east side.",
        "imported_files": {"survey": "No survey loaded", "topography": "No topography loaded", "map": "No map loaded", "cad": "No CAD file loaded"},
    },
}


class ElevationFetcher(QThread):
    """Background thread for fetching elevation data from Google Maps API."""

    progress = pyqtSignal(str)  # Progress updates
    finished = pyqtSignal(dict)  # Results: {lat: {lng: elevation}}
    error = pyqtSignal(str)  # Error message

    def __init__(self, lat_center, lng_center, lat_span, lng_span, api_key, grid_points=10):
        super().__init__()
        self.lat_center = lat_center
        self.lng_center = lng_center
        self.lat_span = lat_span  # Degrees to span (property depth)
        self.lng_span = lng_span  # Degrees to span (property width)
        self.api_key = api_key
        self.grid_points = grid_points  # Points per side (10x10 = 100 points)

    def run(self):
        """Fetch elevation grid from Google Maps API."""
        try:
            self.progress.emit("Initializing elevation grid...")

            # Calculate grid bounds
            lat_start = self.lat_center - (self.lat_span / 2)
            lat_end = self.lat_center + (self.lat_span / 2)
            lng_start = self.lng_center - (self.lng_span / 2)
            lng_end = self.lng_center + (self.lng_span / 2)

            # Calculate step size
            lat_step = self.lat_span / (self.grid_points - 1)
            lng_step = self.lng_span / (self.grid_points - 1)

            # Generate elevation grid
            elevation_data = {}
            points_to_fetch = []

            # Build list of points
            for i in range(self.grid_points):
                lat = lat_start + (i * lat_step)
                for j in range(self.grid_points):
                    lng = lng_start + (j * lng_step)
                    points_to_fetch.append((lat, lng))

            # Google Maps Elevation API allows up to 512 points per request
            # However, GET requests have URL length limits (8192 chars typically)
            # We use a conservative batch size to avoid issues
            batch_size = 100  # Safe limit for GET requests with lat,lng locations
            total_batches = (len(points_to_fetch) + batch_size - 1) // batch_size

            self.progress.emit(f"Fetching {len(points_to_fetch)} elevation points...")

            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(points_to_fetch))
                batch = points_to_fetch[start_idx:end_idx]

                # Prepare request
                locations = "|".join([f"{lat},{lng}" for lat, lng in batch])

                url = f"https://maps.googleapis.com/maps/api/elevation/json"
                params = {
                    "locations": locations,
                    "key": self.api_key
                }

                # Debug: print request info
                print(f"[ElevationAPI] Request URL: {url}")
                print(f"[ElevationAPI] Locations count: {len(batch)}")
                print(f"[ElevationAPI] First location: {batch[0]}")

                # Make request
                response = requests.get(url, params=params, timeout=30)

                # Debug: print response info
                print(f"[ElevationAPI] Batch {batch_num + 1}/{total_batches}")
                print(f"[ElevationAPI] Response status: {response.status_code}")
                print(f"[ElevationAPI] URL length: {len(response.url)} chars")

                # Check for HTTP errors before processing
                if response.status_code != 200:
                    error_text = response.text[:500]
                    print(f"[ElevationAPI] Error response: {error_text}")
                    self.error.emit(
                        f"HTTP {response.status_code} - Bad Request\n\n"
                        f"This usually means:\n"
                        f"• Invalid API key\n"
                        f"• Elevation API not enabled\n"
                        f"• URL too long (try reducing grid density)\n"
                        f"• API quota exceeded"
                    )
                    return

                data = response.json()

                # Process results
                if data["status"] == "OK":
                    for idx, result in enumerate(data["results"]):
                        lat, lng = batch[idx]
                        elevation_m = result["elevation"]
                        elevation_ft = elevation_m * 3.28084  # Convert to feet
                        elevation_data[f"{lat:.6f},{lng:.6f}"] = {
                            "lat": lat,
                            "lng": lng,
                            "elevation_m": elevation_m,
                            "elevation_ft": elevation_ft,
                            "resolution": result.get("resolution", 0)
                        }
                else:
                    error_msg = data.get('error_message', data['status'])
                    status = data.get('status', 'UNKNOWN')
                    self.error.emit(f"API Error ({status}): {error_msg}")
                    return

                # Progress update
                progress_pct = int(((batch_num + 1) / total_batches) * 100)
                self.progress.emit(f"Fetching elevation data... {progress_pct}%")

            self.progress.emit(f"Complete! Retrieved {len(elevation_data)} elevation points.")
            self.finished.emit(elevation_data)

        except requests.exceptions.HTTPError as e:
            # Get response body for more details
            response_text = ""
            if hasattr(e.response, 'text'):
                response_text = e.response.text[:500]
            self.error.emit(f"HTTP {e.response.status_code}: {response_text}")
        except requests.exceptions.Timeout as e:
            self.error.emit(f"Request timeout - server took too long to respond.\nTry reducing the grid density.")
        except requests.exceptions.ConnectionError as e:
            self.error.emit(f"Connection error - check your internet connection.")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {str(e)}")
        except KeyError as e:
            self.error.emit(f"Invalid API response format - missing key: {e}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(f"Error fetching elevation: {str(e)}")


class SiteDialog(QDialog):
    """
    Dialog for defining site characteristics before building design.

    Site information collected:
    - Dimensions and boundaries
    - Road location and access
    - Topography and terrain
    - Solar orientation
    - Views and features
    - Setbacks and constraints
    """

    # Signal emitted when site is defined
    site_defined = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Define Site - Step 1 of 2")
        self.setMinimumSize(700, 650)

        self.site_data = {}
        self._elevation_data = {}  # Store elevation grid from Google Maps
        self._elevation_fetcher = None  # Background thread
        self._map_boundary = None  # Boundary drawn on map
        self._existing_site = self._load_existing_site()

        # Google Maps disabled - manual inputs only
        self._has_google_maps = False
        self._map_widget = None
        self._map_placeholder = None
        self._site_editor = None  # Will be created in UI
        self._site_size_label = None  # Will be created in UI
        self._open_editor_btn = None  # Will be created in UI
        self._webview_map = None  # WebView2 map widget
        self._static_map = None  # Static map widget

        self._setup_ui()
        self._connect_signals()

        # Load existing site if found
        if self._existing_site:
            self._load_site_to_ui(self._existing_site)
            self.setWindowTitle("Edit Site - Step 1 of 2")

        # Load saved API key (defer until after UI is created)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._load_api_key_from_settings)

    def _check_google_maps_available(self):
        """Check if Google Maps widget is available (lazy import)."""
        # Try to import, but don't fail if it doesn't work
        try:
            _init_google_maps()
        except Exception as e:
            print(f"[SiteDialog] Google Maps check failed: {e}")
            global HAS_GOOGLE_MAPS_WIDGET
            HAS_GOOGLE_MAPS_WIDGET = False

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        header = QLabel("Define Your Site")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3;")
        layout.addWidget(header)

        subtitle = QLabel(
            "Import site data and define boundaries before designing your building. "
            "This ensures the design responds to its location."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(subtitle)

        # Tab widget for different site aspects
        tabs = QTabWidget()
        tabs.addTab(self._create_boundary_tab(), "Boundaries")
        tabs.addTab(self._create_terrain_tab(), "Terrain & Features")
        tabs.addTab(self._create_import_tab(), "Import Data")
        layout.addWidget(tabs)

        # Site preview
        preview_group = QGroupBox("Site Preview")
        preview_layout = QVBoxLayout()
        self._preview_label = QLabel(
            "No site data yet. Fill in the form above to see preview."
        )
        self._preview_label.setStyleSheet(
            "background: #f5f5f5; padding: 15px; border-radius: 4px; "
            "color: #666; font-size: 11px;"
        )
        self._preview_label.setWordWrap(True)
        self._preview_label.setMinimumHeight(80)
        preview_layout.addWidget(self._preview_label)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.back_btn = QPushButton("← Back")
        self.back_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next: Design Building →")
        self.next_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; "
            "padding: 10px 20px; font-weight: bold;"
        )
        self.next_btn.clicked.connect(self._on_next)
        button_layout.addWidget(self.next_btn)

        layout.addLayout(button_layout)

    def _get_site_file_path(self):
        """Get the path to the site data file."""
        config_dir = Path.home() / ".archengine"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "site.json"

    def _load_existing_site(self):
        """Load existing site data from file if it exists."""
        site_file = self._get_site_file_path()
        if site_file.exists():
            try:
                with open(site_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[SiteDialog] Error loading site: {e}")
        return None

    def _save_site(self, site_data):
        """Save site data to file for future use."""
        site_file = self._get_site_file_path()
        try:
            with open(site_file, 'w') as f:
                json.dump(site_data, f, indent=2)
            print(f"[SiteDialog] Site saved to {site_file}")
        except Exception as e:
            print(f"[SiteDialog] Error saving site: {e}")

    def _load_site_to_ui(self, site_data):
        """Populate UI fields from existing site data."""
        # Block signals to prevent triggering updates during load
        self.blockSignals(True)

        try:
            self._width_input.setValue(site_data.get("property_width_ft", 100))
            self._depth_input.setValue(site_data.get("property_depth_ft", 120))

            road_loc = site_data.get("road_location", "Front (South)")
            idx = self._road_side_combo.findText(road_loc)
            if idx >= 0:
                self._road_side_combo.setCurrentIndex(idx)

            self._road_width_input.setValue(site_data.get("road_width_ft", 30))
            self._driveway_check.setChecked(site_data.get("driveway_required", True))
            self._front_setback.setValue(site_data.get("setback_front_ft", 20))
            self._rear_setback.setValue(site_data.get("setback_rear_ft", 25))
            self._side_setback.setValue(site_data.get("setback_side_ft", 10))
            self._max_coverage.setValue(site_data.get("max_coverage_percent", 40))
            self._max_height.setValue(site_data.get("max_height_ft", 35))

            slope = site_data.get("slope", "Flat (0-5%)")
            idx = self._slope_combo.findText(slope)
            if idx >= 0:
                self._slope_combo.setCurrentIndex(idx)

            self._elevation_change.setValue(site_data.get("elevation_change_ft", 0))

            orientation = site_data.get("solar_orientation", "South-facing (optimal)")
            idx = self._orientation_combo.findText(orientation)
            if idx >= 0:
                self._orientation_combo.setCurrentIndex(idx)

            self._solar_access.setChecked(site_data.get("solar_access", True))

            views = site_data.get("views", {})
            self._view_north.setChecked(views.get("north", False))
            self._view_east.setChecked(views.get("east", False))
            self._view_south.setChecked(views.get("south", False))
            self._view_west.setChecked(views.get("west", False))

            self._feature_notes.setPlainText(site_data.get("feature_notes", ""))

            # Load Google Maps data if available
            google_maps = site_data.get("google_maps", {})
            if google_maps:
                self._api_key_input.setText(google_maps.get("api_key", ""))
                self._lat_input.setValue(google_maps.get("latitude", 45.4215))
                self._lng_input.setValue(google_maps.get("longitude", -75.6972))
                self._elevation_data = google_maps.get("elevation_grid", {})

                # Show elevation summary if data exists
                if self._elevation_data:
                    elevations_ft = [pt["elevation_ft"] for pt in self._elevation_data.values()]
                    min_elev = min(elevations_ft)
                    max_elev = max(elevations_ft)
                    self._elevation_results.setText(
                        f"✓ Loaded {len(self._elevation_data)} elevation points\n"
                        f"  Elevation range: {min_elev:.1f}' to {max_elev:.1f}'"
                    )

            self._update_preview()

        finally:
            self.blockSignals(False)

    def _create_boundary_tab(self):
        """Create the boundary/property tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Property dimensions
        dim_group = QGroupBox("Property Dimensions")
        dim_layout = QFormLayout()

        self._width_input = QDoubleSpinBox()
        self._width_input.setRange(10, 1000)
        self._width_input.setValue(100)  # 100 ft default
        self._width_input.setSuffix(" ft")
        self._width_input.setSingleStep(5)
        dim_layout.addRow("Property Width:", self._width_input)

        self._depth_input = QDoubleSpinBox()
        self._depth_input.setRange(10, 1000)
        self._depth_input.setValue(120)  # 120 ft default
        self._depth_input.setSuffix(" ft")
        self._depth_input.setSingleStep(5)
        dim_layout.addRow("Property Depth:", self._depth_input)

        dim_group.setLayout(dim_layout)
        layout.addWidget(dim_group)

        # Road location
        road_group = QGroupBox("Road & Access")
        road_layout = QFormLayout()

        self._road_side_combo = QComboBox()
        self._road_side_combo.addItems([
            "Front (South)",
            "Front (North)",
            "Front (East)",
            "Front (West)",
            "Rear (South)",
            "Rear (North)",
            "Rear (East)",
            "Rear (West)",
            "Left Side",
            "Right Side",
            "Corner Lot"
        ])
        road_layout.addRow("Road Location:", self._road_side_combo)

        self._road_width_input = QDoubleSpinBox()
        self._road_width_input.setRange(10, 100)
        self._road_width_input.setValue(30)
        self._road_width_input.setSuffix(" ft")
        road_layout.addRow("Road Width:", self._road_width_input)

        self._driveway_check = QCheckBox("Driveway required")
        self._driveway_check.setChecked(True)
        road_layout.addRow("", self._driveway_check)

        road_group.setLayout(road_layout)
        layout.addWidget(road_group)

        # Setbacks
        setback_group = QGroupBox("Setbacks (from property lines)")
        setback_layout = QGridLayout()

        self._front_setback = QDoubleSpinBox()
        self._front_setback.setRange(0, 100)
        self._front_setback.setValue(20)
        self._front_setback.setSuffix(" ft")
        setback_layout.addWidget(QLabel("Front:"), 0, 0)
        setback_layout.addWidget(self._front_setback, 0, 1)

        self._rear_setback = QDoubleSpinBox()
        self._rear_setback.setRange(0, 100)
        self._rear_setback.setValue(25)
        self._rear_setback.setSuffix(" ft")
        setback_layout.addWidget(QLabel("Rear:"), 0, 2)
        setback_layout.addWidget(self._rear_setback, 0, 3)

        self._side_setback = QDoubleSpinBox()
        self._side_setback.setRange(0, 100)
        self._side_setback.setValue(10)
        self._side_setback.setSuffix(" ft")
        setback_layout.addWidget(QLabel("Side:"), 1, 0)
        setback_layout.addWidget(self._side_setback, 1, 1)

        setback_group.setLayout(setback_layout)
        layout.addWidget(setback_group)

        # Building area constraints
        area_group = QGroupBox("Building Area Limits")
        area_layout = QFormLayout()

        self._max_coverage = QSpinBox()
        self._max_coverage.setRange(10, 100)
        self._max_coverage.setValue(40)
        self._max_coverage.setSuffix(" %")
        area_layout.addRow("Max Lot Coverage:", self._max_coverage)

        self._max_height = QSpinBox()
        self._max_height.setRange(10, 100)
        self._max_height.setValue(35)
        self._max_height.setSuffix(" ft")
        area_layout.addRow("Max Building Height:", self._max_height)

        area_group.setLayout(area_layout)
        layout.addWidget(area_group)

        layout.addStretch()
        return widget

    def _create_terrain_tab(self):
        """Create the terrain/features tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Topography
        topo_group = QGroupBox("Topography")
        topo_layout = QFormLayout()

        self._slope_combo = QComboBox()
        self._slope_combo.addItems([
            "Flat (0-5%)",
            "Gentle Slope (5-15%)",
            "Moderate Slope (15-25%)",
            "Steep Slope (25%+)"
        ])
        topo_layout.addRow("Terrain Slope:", self._slope_combo)

        self._elevation_change = QDoubleSpinBox()
        self._elevation_change.setRange(0, 200)
        self._elevation_change.setValue(0)
        self._elevation_change.setSuffix(" ft")
        topo_layout.addRow("Elevation Change:", self._elevation_change)

        topo_group.setLayout(topo_layout)
        layout.addWidget(topo_group)

        # Solar orientation
        solar_group = QGroupBox("Solar Orientation")
        solar_layout = QFormLayout()

        self._orientation_combo = QComboBox()
        self._orientation_combo.addItems([
            "South-facing (optimal)",
            "Southeast-facing",
            "Southwest-facing",
            "East-facing (morning sun)",
            "West-facing (afternoon sun)",
            "North-facing (least sun)"
        ])
        solar_layout.addRow("Primary Orientation:", self._orientation_combo)

        self._solar_access = QCheckBox("Good solar access (no shading)")
        self._solar_access.setChecked(True)
        solar_layout.addRow("", self._solar_access)

        solar_group.setLayout(solar_layout)
        layout.addWidget(solar_group)

        # Views
        view_group = QGroupBox("Views & Features")
        view_layout = QVBoxLayout()

        view_label = QLabel("Select desirable view directions:")
        view_layout.addWidget(view_label)

        view_check_layout = QHBoxLayout()
        self._view_north = QCheckBox("North")
        self._view_east = QCheckBox("East")
        self._view_south = QCheckBox("South")
        self._view_west = QCheckBox("West")
        view_check_layout.addWidget(self._view_north)
        view_check_layout.addWidget(self._view_east)
        view_check_layout.addWidget(self._view_south)
        view_check_layout.addWidget(self._view_west)
        view_layout.addLayout(view_check_layout)

        self._feature_notes = QTextEdit()
        self._feature_notes.setPlaceholderText(
            "Note any important site features:\n"
            "- Trees to preserve\n"
            "- Water features\n"
            "- Neighboring buildings\n"
            "- Noise sources\n"
            "- prevailing winds\n"
            "- etc."
        )
        self._feature_notes.setMaximumHeight(100)
        view_layout.addWidget(QLabel("Site Features Notes:"))
        view_layout.addWidget(self._feature_notes)

        view_group.setLayout(view_layout)
        layout.addWidget(view_group)

        layout.addStretch()
        return widget

    def _create_import_tab(self):
        """Create the import data tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)

        # Import description
        desc = QLabel(
            "Import site data from survey files, CAD drawings, or GIS data. "
            "This helps accurately represent the site for building design."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc)

        # Import buttons
        import_group = QGroupBox("Import Site Data")
        import_layout = QVBoxLayout()

        # Survey import
        survey_layout = QHBoxLayout()
        survey_btn = QPushButton("Import Survey...")
        survey_btn.clicked.connect(self._on_import_survey)
        survey_layout.addWidget(survey_btn)
        self._survey_label = QLabel("No survey loaded")
        self._survey_label.setStyleSheet("color: #999; font-style: italic;")
        survey_layout.addWidget(self._survey_label)
        survey_layout.addStretch()
        import_layout.addLayout(survey_layout)

        # Topography import
        topo_layout = QHBoxLayout()
        topo_btn = QPushButton("Import Topography...")
        topo_btn.clicked.connect(self._on_import_topo)
        topo_layout.addWidget(topo_btn)
        self._topo_label = QLabel("No topography loaded")
        self._topo_label.setStyleSheet("color: #999; font-style: italic;")
        topo_layout.addWidget(self._topo_label)
        topo_layout.addStretch()
        import_layout.addLayout(topo_layout)

        # Map import
        map_layout = QHBoxLayout()
        map_btn = QPushButton("Import Map/Satellite...")
        map_btn.clicked.connect(self._on_import_map)
        map_layout.addWidget(map_btn)
        self._map_label = QLabel("No map loaded")
        self._map_label.setStyleSheet("color: #999; font-style: italic;")
        map_layout.addWidget(self._map_label)
        map_layout.addStretch()
        import_layout.addLayout(map_layout)

        # CAD import
        cad_layout = QHBoxLayout()
        cad_btn = QPushButton("Import CAD/DWG...")
        cad_btn.clicked.connect(self._on_import_cad)
        cad_layout.addWidget(cad_btn)
        self._cad_label = QLabel("No CAD file loaded")
        self._cad_label.setStyleSheet("color: #999; font-style: italic;")
        cad_layout.addWidget(self._cad_label)
        cad_layout.addStretch()
        import_layout.addLayout(cad_layout)

        import_group.setLayout(import_layout)
        layout.addWidget(import_group)

        # Sample sites (for testing)
        sample_group = QGroupBox("Load Sample Site (for testing)")
        sample_layout = QVBoxLayout()

        sample_desc = QLabel(
            "Load a pre-configured sample site to quickly test the building generator. "
            "Choose a site type that matches your project."
        )
        sample_desc.setWordWrap(True)
        sample_desc.setStyleSheet("color: #666; font-size: 10px;")
        sample_layout.addWidget(sample_desc)

        sample_combo_layout = QHBoxLayout()
        sample_combo_layout.addWidget(QLabel("Sample Site:"))
        self._sample_combo = QComboBox()
        self._sample_combo.addItems(list(SAMPLE_SITES.keys()))
        sample_combo_layout.addWidget(self._sample_combo)
        sample_layout.addLayout(sample_combo_layout)

        load_sample_btn = QPushButton("Load Sample Site")
        load_sample_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 8px;")
        load_sample_btn.clicked.connect(self._on_load_sample_site)
        sample_layout.addWidget(load_sample_btn)

        sample_group.setLayout(sample_layout)
        layout.addWidget(sample_group)

        # Google Maps with Elevation API
        google_group = QGroupBox("Google Maps: Location & Elevation")
        google_layout = QVBoxLayout()

        # Instructions with "Get API Key" button
        instructions_layout = QHBoxLayout()

        google_desc = QLabel(
            "<b>Steps:</b> "
            "<span style='color:#2196F3'>1)</span> Get a free Google Maps API key &nbsp; "
            "<span style='color:#2196F3'>2)</span> Enter it below &nbsp; "
            "<span style='color:#2196F3'>3)</span> Search/click map &nbsp; "
            "<span style='color:#2196F3'>4)</span> Draw boundary &nbsp; "
            "<span style='color:#2196F3'>5)</span> Fetch elevation"
        )
        google_desc.setWordWrap(True)
        google_desc.setStyleSheet("color: #666; font-size: 10px;")
        instructions_layout.addWidget(google_desc, 1)

        get_api_btn = QPushButton("Get API Key")
        get_api_btn.setMaximumWidth(100)
        get_api_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 5px 10px;")
        get_api_btn.setToolTip("Open Google Cloud Console to create an API key")
        get_api_btn.clicked.connect(self._on_get_api_key)
        instructions_layout.addWidget(get_api_btn)

        google_layout.addLayout(instructions_layout)

        # Info box explaining what's needed
        info_text = QLabel(
            "<i>Required APIs: Maps JavaScript API + Maps Elevation API (free tier: $200 credit/month)</i>"
        )
        info_text.setStyleSheet("color: #FF9800; font-size: 9px; padding: 5px; background: #FFF3E0; border-radius: 3px;")
        info_text.setWordWrap(True)
        google_layout.addWidget(info_text)

        # API key input row
        api_row = QHBoxLayout()
        api_row.addWidget(QLabel("API Key:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("Enter your Google Maps API key (starts with AIza...)")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_row.addWidget(self._api_key_input)

        verify_btn = QPushButton("Verify")
        verify_btn.setMaximumWidth(80)
        verify_btn.setToolTip("Test if your API key works")
        verify_btn.clicked.connect(self._on_verify_api_key)
        api_row.addWidget(verify_btn)

        google_layout.addLayout(api_row)

        self._api_key_status = QLabel("API key not verified")
        self._api_key_status.setStyleSheet("color: #999; font-size: 10px; font-style: italic;")
        google_layout.addWidget(self._api_key_status)

        # Interactive Map Widget - OpenStreetMap with drawing
        print(f"[SiteDialog] Creating Interactive Map section...")
        map_group = QGroupBox("Interactive Map (draw property boundary)")
        map_layout = QVBoxLayout()

        # Controls row
        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Zoom:"))
        self._map_zoom_spin = QSpinBox()
        self._map_zoom_spin.setRange(15, 21)
        self._map_zoom_spin.setValue(18)
        self._map_zoom_spin.setSuffix("x")
        self._map_zoom_spin.valueChanged.connect(self._on_map_zoom_changed)
        controls_row.addWidget(self._map_zoom_spin)

        self._clear_map_btn = QPushButton("Clear Boundary")
        self._clear_map_btn.clicked.connect(self._on_clear_map_boundary)
        controls_row.addWidget(self._clear_map_btn)

        controls_row.addStretch()
        map_layout.addLayout(controls_row)

        # Open map button
        self._open_map_btn = QPushButton("Open Interactive Map")
        self._open_map_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-size: 12px;")
        self._open_map_btn.clicked.connect(self._on_open_interactive_map)
        map_layout.addWidget(self._open_map_btn)

        # Boundary info label
        self._map_boundary_info = QLabel("Click 'Open Interactive Map' to define property boundary")
        self._map_boundary_info.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        self._map_boundary_info.setWordWrap(True)
        map_layout.addWidget(self._map_boundary_info)

        # Instructions
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "1. Click 'Open Interactive Map' to launch the map in a new window<br>"
            "2. Pan and zoom to find your property<br>"
            "3. Click 'Start Drawing' and click on map to place polygon points<br>"
            "4. Click 'Finish' to complete the polygon<br>"
            "5. Click 'Save & Close' - the dimensions will populate below"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #333; font-size: 10px; padding: 5px; background-color: #f5f5f5; border-radius: 4px;")
        map_layout.addWidget(instructions)

        map_group.setLayout(map_layout)
        google_layout.addWidget(map_group)

        # Manual location input
        coords_group = QGroupBox("Location Coordinates")
        coords_layout = QFormLayout()

        self._lat_input = QDoubleSpinBox()
        self._lat_input.setRange(-90, 90)
        self._lat_input.setValue(45.4215)
        self._lat_input.setDecimals(6)
        self._lat_input.setSingleStep(0.0001)
        self._lat_input.setSuffix("°")
        coords_layout.addRow("Latitude:", self._lat_input)

        self._lng_input = QDoubleSpinBox()
        self._lng_input.setRange(-180, 180)
        self._lng_input.setValue(-75.6972)
        self._lng_input.setDecimals(6)
        self._lng_input.setSingleStep(0.0001)
        self._lng_input.setSuffix("°")
        coords_layout.addRow("Longitude:", self._lng_input)

        coords_group.setLayout(coords_layout)
        google_layout.addWidget(coords_group)

        # Grid density and fetch button row
        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Grid Density:"))
        self._grid_density_combo = QComboBox()
        self._grid_density_combo.addItem("10x10 (100 points)", 10)
        self._grid_density_combo.addItem("15x15 (225 points)", 15)
        self._grid_density_combo.addItem("20x20 (400 points)", 20)
        self._grid_density_combo.addItem("25x25 (625 points)", 25)
        self._grid_density_combo.setCurrentIndex(1)  # Default to 15x15
        controls_row.addWidget(self._grid_density_combo)
        controls_row.addStretch()

        self._fetch_elevation_btn = QPushButton("Fetch Elevation Data")
        self._fetch_elevation_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self._fetch_elevation_btn.clicked.connect(self._on_fetch_elevation)
        controls_row.addWidget(self._fetch_elevation_btn)

        google_layout.addLayout(controls_row)

        # Progress bar
        self._elevation_progress = QProgressBar()
        self._elevation_progress.setVisible(False)
        self._elevation_progress.setTextVisible(True)
        google_layout.addWidget(self._elevation_progress)

        # Results label
        self._elevation_results = QLabel("No elevation data fetched yet.")
        self._elevation_results.setWordWrap(True)
        self._elevation_results.setStyleSheet("color: #666; font-size: 10px;")
        google_layout.addWidget(self._elevation_results)

        google_group.setLayout(google_layout)
        layout.addWidget(google_group)

        # Loaded files summary
        files_group = QGroupBox("Loaded Site Files")
        files_layout = QVBoxLayout()
        self._files_summary = QLabel("No site files imported yet.")
        self._files_summary.setWordWrap(True)
        self._files_summary.setStyleSheet("color: #666; font-size: 10px;")
        files_layout.addWidget(self._files_summary)
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)

        layout.addStretch()
        return widget

    def _connect_signals(self):
        """Connect signals."""
        # Update preview when any value changes
        self._width_input.valueChanged.connect(self._update_preview)
        self._depth_input.valueChanged.connect(self._update_preview)
        self._road_side_combo.currentTextChanged.connect(self._update_preview)
        self._front_setback.valueChanged.connect(self._update_preview)
        self._rear_setback.valueChanged.connect(self._update_preview)
        self._side_setback.valueChanged.connect(self._update_preview)

    def _update_preview(self):
        """Update the site preview text."""
        width = self._width_input.value()
        depth = self._depth_input.value()
        road = self._road_side_combo.currentText()
        front_setback = self._front_setback.value()
        rear_setback = self._rear_setback.value()
        side_setback = self._side_setback.value()

        # Calculate buildable area
        buildable_width = width - (2 * side_setback)
        buildable_depth = depth - (front_setback + rear_setback)
        max_building_area = (buildable_width * buildable_depth)

        preview_text = f"""
<b>Site:</b> {width:.0f}' × {depth:.0f}' ({width * depth:.0f} sq ft)
<b>Road:</b> {road}
<b>Buildable Area:</b> {buildable_width:.0f}' × {buildable_depth:.0f}' ({max_building_area:.0f} sq ft)
<b>Max Coverage:</b> {self._max_coverage.value()}% = {max_building_area * self._max_coverage.value() / 100:.0f} sq ft building footprint
"""
        self._preview_label.setText(preview_text)

    def _on_import_survey(self):
        """Import survey data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Survey", "", "Survey Files (*.pdf *.dxf *.dwg);;All Files (*)"
        )
        if file_path:
            self._survey_label.setText(Path(file_path).name)
            self._survey_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self._update_files_summary()

    def _on_import_topo(self):
        """Import topography data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Topography", "", "Topo Files (*.txt *.csv *.xyz *.dxf);;All Files (*)"
        )
        if file_path:
            self._topo_label.setText(Path(file_path).name)
            self._topo_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self._update_files_summary()

    def _on_import_map(self):
        """Import map/satellite imagery."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Map", "", "Image Files (*.png *.jpg *.jpeg *.tif);;All Files (*)"
        )
        if file_path:
            self._map_label.setText(Path(file_path).name)
            self._map_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self._update_files_summary()

    def _on_import_cad(self):
        """Import CAD drawing."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import CAD", "", "CAD Files (*.dxf *.dwg);;All Files (*)"
        )
        if file_path:
            self._cad_label.setText(Path(file_path).name)
            self._cad_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self._update_files_summary()

    def _update_files_summary(self):
        """Update the loaded files summary."""
        files = []
        if self._survey_label.text() != "No survey loaded":
            files.append(f"• Survey: {self._survey_label.text()}")
        if self._topo_label.text() != "No topography loaded":
            files.append(f"• Topography: {self._topo_label.text()}")
        if self._map_label.text() != "No map loaded":
            files.append(f"• Map: {self._map_label.text()}")
        if self._cad_label.text() != "No CAD file loaded":
            files.append(f"• CAD: {self._cad_label.text()}")

        if files:
            self._files_summary.setText("\n".join(files))
        else:
            self._files_summary.setText("No site files imported yet.")

    def _on_load_sample_site(self):
        """Load a sample site for testing."""
        sample_name = self._sample_combo.currentText()
        if sample_name in SAMPLE_SITES:
            sample_data = SAMPLE_SITES[sample_name]
            self._load_site_to_ui(sample_data)
            print(f"[SiteDialog] Loaded sample site: {sample_name}")

    def _on_get_api_key(self):
        """Open Google Cloud Console to help user create an API key."""
        import webbrowser
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton

        # Create dialog with instructions
        dialog = QDialog(self)
        dialog.setWindowTitle("How to Get a Google Maps API Key")
        dialog.setMinimumSize(600, 500)

        layout = QVBoxLayout(dialog)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setHtml("""
        <h2>Getting Your Free Google Maps API Key</h2>

        <ol>
        <li><b>Create a Google Cloud Project</b>
            <ul>
            <li>Go to <a href="https://console.cloud.google.com/">Google Cloud Console</a></li>
            <li>Click the project dropdown and select "New Project"</li>
            <li>Enter a project name (e.g., "ArchEngine") and click "Create"</li>
            </ul>
        </li>

        <li><b>Enable Required APIs</b>
            <ul>
            <li>Go to <a href="https://console.cloud.google.com/apis/library">APIs & Services → Library</a></li>
            <li>Search for and enable: <b>Maps JavaScript API</b></li>
            <li>Search for and enable: <b>Maps Elevation API</b></li>
            </ul>
        </li>

        <li><b>Create API Key</b>
            <ul>
            <li>Go to <a href="https://console.cloud.google.com/apis/credentials">APIs & Services → Credentials</a></li>
            <li>Click "Create Credentials" → "API Key"</li>
            <li>Copy the API key (starts with "AIza...")</li>
            </ul>
        </li>

        <li><b>Configure API Key</b>
            <ul>
            <li>Click the edit icon (pencil) next to your API key</li>
            <li>Under "Application restrictions", select <b>None</b></li>
            <li>Under "API restrictions", select:
                <ul>
                <li>Maps JavaScript API</li>
                <li>Maps Elevation API</li>
                </ul>
            </li>
            <li>Click "Save"</li>
            </ul>
        </li>
        </ol>

        <h3>Important Notes:</h3>
        <ul>
        <li>Google provides <b>$200 free credit/month</b> - more than enough for personal use</li>
        <li>Keep your API key private - don't share it publicly</li>
        <li>The key will be saved locally on your computer</li>
        <li>Both APIs must be enabled for the feature to work</li>
        </ul>
        """)
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        open_console_btn = QPushButton("Open Google Cloud Console")
        open_console_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 16px;")
        open_console_btn.clicked.connect(lambda: webbrowser.open("https://console.cloud.google.com/apis/credentials"))
        button_layout.addWidget(open_console_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        dialog.exec()

    def _on_verify_api_key(self):
        """Verify the Google Maps API key by making a test request."""
        api_key = self._api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Required",
                "Please enter your Google Maps API key first.")
            return

        self._api_key_status.setText("Verifying...")
        self._api_key_status.setStyleSheet("color: #FFA500; font-size: 10px;")
        QApplication.processEvents()

        try:
            # Test request to Elevation API with a single location
            url = "https://maps.googleapis.com/maps/api/elevation/json"
            params = {
                "locations": "45.4215,-75.6972",  # Ottawa
                "key": api_key
            }

            response = requests.get(url, params=params, timeout=10)

            print(f"[VerifyAPI] Status: {response.status_code}")
            print(f"[VerifyAPI] Response: {response.text[:200]}")

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK":
                    elevation = data["results"][0]["elevation"]
                    self._api_key_status.setText(
                        f"✓ API key verified! Elevation: {elevation:.1f}m"
                    )
                    self._api_key_status.setStyleSheet(
                        "color: #4CAF50; font-size: 10px; font-weight: bold;"
                    )
                    QMessageBox.information(self, "API Key Verified",
                        f"Your API key is working!\n\n"
                        f"Test elevation (Ottawa): {elevation:.1f}m ({elevation * 3.28:.1f} ft)\n\n"
                        f"You can now fetch elevation data for your site.")
                else:
                    error_msg = data.get('error_message', data.get('status', 'Unknown error'))
                    self._api_key_status.setText(f"✗ API error: {error_msg}")
                    self._api_key_status.setStyleSheet("color: #f44336; font-size: 10px;")
                    QMessageBox.critical(self, "API Error",
                        f"API returned an error:\n\n{error_msg}\n\n"
                        f"Common fixes:\n"
                        f"• Enable 'Maps Elevation API' in Google Cloud Console\n"
                        f"• Check API restrictions (set to 'None' for testing)\n"
                        f"• Ensure billing is enabled")
            else:
                self._api_key_status.setText(f"✗ HTTP {response.status_code}")
                self._api_key_status.setStyleSheet("color: #f44336; font-size: 10px;")
                QMessageBox.critical(self, "HTTP Error",
                    f"Server returned HTTP {response.status_code}\n\n"
                    f"{response.text[:200]}")

        except requests.exceptions.RequestException as e:
            self._api_key_status.setText("✗ Network error")
            self._api_key_status.setStyleSheet("color: #f44336; font-size: 10px;")
            QMessageBox.critical(self, "Network Error",
                f"Could not connect to Google Maps API:\n\n{str(e)}\n\n"
                f"Please check your internet connection.")
        except Exception as e:
            self._api_key_status.setText("✗ Error")
            self._api_key_status.setStyleSheet("color: #f44336; font-size: 10px;")
            QMessageBox.critical(self, "Error",
                f"Unexpected error:\n\n{str(e)}")

    def _on_api_key_changed(self, text: str):
        """Update map widget when API key changes."""
        print(f"[SiteDialog] API key changed, length: {len(text.strip())}")
        if self._map_widget and text.strip():
            print(f"[SiteDialog] Calling set_api_key on map widget...")
            self._map_widget.set_api_key(text.strip())
        else:
            print(f"[SiteDialog] Map widget exists: {self._map_widget is not None}, text is empty: {not text.strip()}")

        # Save API key to settings for next time
        self._save_api_key_to_settings()

    def _on_open_site_editor(self):
        """Open site editor in a popup dialog."""
        if not HAS_SITE_EDITOR:
            QMessageBox.warning(self, "Not Available",
                "Site editor widget is not available.")
            return

        try:
            # Create a dialog for the site editor
            editor_dialog = QDialog(self)
            editor_dialog.setWindowTitle("Draw Site Boundary")
            editor_dialog.setMinimumSize(600, 500)

            layout = QVBoxLayout(editor_dialog)

            # Instructions
            instructions = QLabel(
                "Drag the corners to set your property size. "
                "Click OK when done."
            )
            instructions.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
            layout.addWidget(instructions)

            # Create site editor widget
            site_editor = SiteEditorWidget()
            site_editor.setMinimumHeight(400)

            # Set initial size if already set
            try:
                if hasattr(self, '_width_input') and self._width_input:
                    initial_width = self._width_input.value()
                else:
                    initial_width = 100

                if hasattr(self, '_depth_input') and self._depth_input:
                    initial_depth = self._depth_input.value()
                else:
                    initial_depth = 120

                site_editor.set_size_ft(initial_width, initial_depth)
            except Exception as e:
                print(f"[SiteDialog] Error setting initial size: {e}")
                site_editor.set_size_ft(100, 120)

            layout.addWidget(site_editor)

            # Buttons
            button_row = QHBoxLayout()
            button_row.addStretch()

            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(editor_dialog.reject)
            button_row.addWidget(cancel_btn)

            ok_btn = QPushButton("OK")
            ok_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
            ok_btn.clicked.connect(editor_dialog.accept)
            button_row.addWidget(ok_btn)

            layout.addLayout(button_row)

            # Show dialog
            result = editor_dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                # Get the size from the editor
                width_ft, depth_ft = site_editor.get_size_ft()

                # Update the width/depth inputs if they exist
                try:
                    if hasattr(self, '_width_input') and self._width_input:
                        self._width_input.blockSignals(True)
                        self._width_input.setValue(int(width_ft))
                        self._width_input.blockSignals(False)

                    if hasattr(self, '_depth_input') and self._depth_input:
                        self._depth_input.blockSignals(True)
                        self._depth_input.setValue(int(depth_ft))
                        self._depth_input.blockSignals(False)
                except Exception as e:
                    print(f"[SiteDialog] Error updating width/depth inputs: {e}")

                # Update label
                area_sqft = width_ft * depth_ft
                if self._site_size_label:
                    self._site_size_label.setText(
                        f"Current size: {width_ft:.0f}' × {depth_ft:.0f}' = {area_sqft:.0f} sq ft"
                    )

                print(f"[SiteDialog] Site size set to {width_ft:.0f}' x {depth_ft:.0f}'")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                f"Could not open site editor:\n\n{str(e)}")
            print(f"[SiteDialog] Error opening site editor: {e}")

    def _on_clear_map_boundary(self):
        """Clear the boundary on the static map."""
        if hasattr(self, '_static_map') and self._static_map:
            self._static_map.clear_boundary()
        if hasattr(self, '_webview_map') and self._webview_map:
            self._webview_map.clear_boundary()

        self._map_boundary = None
        if hasattr(self, '_map_boundary_info'):
            self._map_boundary_info.setText("Click 'Open Interactive Map' to define property boundary")
        print(f"[SiteDialog] Map boundary cleared")

    def _on_open_interactive_map(self):
        """Open the interactive OpenStreetMap/Leaflet map."""
        lat = self._lat_input.value()
        lng = self._lng_input.value()
        zoom = self._map_zoom_spin.value()

        print(f"[SiteDialog] Opening interactive map at ({lat}, {lng}), zoom {zoom}")

        try:
            # Lazy import to avoid startup crashes
            from widgets.embedded_map_widget import EmbeddedMapWidget
            print("[SiteDialog] EmbeddedMapWidget imported")

            # Create embedded map widget as a dialog (so it shows properly)
            from PyQt6.QtWidgets import QDialog
            map_dialog = QDialog(self)
            map_dialog.setWindowTitle("Property Boundary Map")
            map_dialog.setMinimumSize(400, 100)

            layout = QVBoxLayout(map_dialog)

            # Create embedded map widget
            self._embedded_map = EmbeddedMapWidget(lat, lng, zoom)
            layout.addWidget(self._embedded_map)

            print("[SiteDialog] EmbeddedMapWidget created")

            # Connect boundary changed signal
            self._embedded_map.boundary_changed.connect(self._on_map_boundary_changed_with_dims)
            print("[SiteDialog] Boundary signal connected")

            # Show the dialog (non-modal so user can interact with main app too)
            map_dialog.show()
            print("[SiteDialog] Map dialog shown")

            QMessageBox.information(self, "Map Opened",
                f"A map window has opened!\n\n"
                f"1. Draw your property boundary\n"
                f"2. Click 'Save & Close'\n"
                f"3. The dimensions will populate below")

        except ImportError as e:
            QMessageBox.warning(self, "Not Available",
                f"Interactive map is not available.\n\n"
                f"Error: {str(e)}\n\n"
                f"Please install pywebview:\n"
                f"pip install pywebview")
            print(f"[SiteDialog] Cannot import embedded map: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error",
                f"Could not open map:\n{str(e)}")
            print(f"[SiteDialog] Error opening map: {e}")
            import traceback
            traceback.print_exc()

    def _on_map_boundary_changed_with_dims(self, lat_min, lat_max, lng_min, lng_max, width_ft, depth_ft):
        """Handle boundary changed with dimensions."""
        print(f"[SiteDialog] Boundary received: {width_ft:.0f}' x {depth_ft:.0f}'")

        # Update UI with dimensions
        self._width_input.setValue(int(width_ft))
        self._depth_input.setValue(int(depth_ft))

        # Update info label
        if hasattr(self, '_map_boundary_info'):
            lat_center = (lat_min + lat_max) / 2
            lng_center = (lng_min + lng_max) / 2
            self._map_boundary_info.setText(
                f"Boundary set: {width_ft:.0f}' x {depth_ft:.0f}' at "
                f"({lat_center:.4f}, {lng_center:.4f})"
            )

        # Store boundary for elevation fetching
        self._map_boundary = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lng_min': lng_min,
            'lng_max': lng_max,
            'width_ft': width_ft,
            'depth_ft': depth_ft
        }

        # Show confirmation
        QMessageBox.information(self, "Boundary Received",
            f"Property boundary set!\n\n"
            f"Width: {width_ft:.0f}'\n"
            f"Depth: {depth_ft:.0f}'\n\n"
            f"The dimensions have been populated in the form.")

    def _on_navigate_to_location(self):
        """Navigate the map to the current coordinates."""
        if hasattr(self, '_webview_map') and self._webview_map:
            lat = self._lat_input.value()
            lng = self._lng_input.value()
            zoom = self._map_zoom_spin.value()
            self._webview_map.set_location(lat, lng, zoom)
            print(f"[SiteDialog] Navigating map to ({lat}, {lng}), zoom {zoom}")

    def _on_map_zoom_changed(self, value):
        """Handle zoom level change."""
        if hasattr(self, '_webview_map') and self._webview_map:
            self._webview_map.set_zoom(value)

    def _on_map_boundary_changed(self, lat_min, lat_max, lng_min, lng_max):
        """Handle boundary drawn on the interactive map."""
        # Calculate width and depth from lat/lng bounds
        # Approximate: 1 degree latitude ≈ 69 miles, 1 degree longitude ≈ 69 miles * cos(latitude)
        lat_center = (lat_min + lat_max) / 2
        lat_deg_to_ft = 364000  # Approximate feet per degree latitude
        lng_deg_to_ft = 364000 * 0.7071  # Approximate feet per degree longitude at 45° latitude

        width_ft = abs(lng_max - lng_min) * lng_deg_to_ft
        depth_ft = abs(lat_max - lat_min) * lat_deg_to_ft

        # Update UI
        self._width_input.setValue(int(width_ft))
        self._depth_input.setValue(int(depth_ft))

        # Update info label
        if hasattr(self, '_map_boundary_info'):
            self._map_boundary_info.setText(
                f"Boundary set: {width_ft:.0f}' x {depth_ft:.0f}' at "
                f"({lat_center:.4f}, {(lng_min + lng_max)/2:.4f})"
            )

        # Store boundary for elevation fetching
        self._map_boundary = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lng_min': lng_min,
            'lng_max': lng_max,
            'width_ft': width_ft,
            'depth_ft': depth_ft
        }

        print(f"[SiteDialog] Map boundary changed: {width_ft:.0f}' x {depth_ft:.0f}'")

    def _load_api_key_from_settings(self):
        """Load API key from QSettings if previously saved."""
        settings = QSettings("ArchEngine", "CAD")
        saved_key = settings.value("google_maps_api_key", "", str)
        if saved_key and hasattr(self, '_api_key_input'):
            self._api_key_input.setText(saved_key)
            print(f"[SiteDialog] Loaded saved API key (length: {len(saved_key)})")

    def _save_api_key_to_settings(self):
        """Save API key to QSettings for future use."""
        if not hasattr(self, '_api_key_input'):
            return
        api_key = self._api_key_input.text().strip()
        settings = QSettings("ArchEngine", "CAD")
        settings.setValue("google_maps_api_key", api_key)
        print(f"[SiteDialog] Saved API key to settings (length: {len(api_key)})")

    def _on_boundary_drawn(self, boundary: dict):
        """Handle boundary drawn on map - auto-populate width/depth."""
        if not boundary:
            return

        # Auto-populate width/depth from boundary
        width_ft = boundary.get('width_ft', 0)
        depth_ft = boundary.get('depth_ft', 0)

        if width_ft > 0 and depth_ft > 0:
            self._width_input.setValue(int(width_ft))
            self._depth_input.setValue(int(depth_ft))
            print(f"[SiteDialog] Auto-populated dimensions from map: {width_ft:.0f}' x {depth_ft:.0f}'")

        # Store boundary data for elevation fetching
        self._map_boundary = boundary

    def _on_site_boundary_changed(self, lat_min, lat_max, lng_min, lng_max):
        """Handle boundary changed from site editor."""
        # Site editor disabled - this method is no longer used
        pass

    def _on_fetch_elevation(self):
        """Fetch elevation data from Google Maps API."""
        api_key = self._api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Required",
                "Please enter your Google Maps API key.\n\n"
                "Get one at: https://console.cloud.google.com/\n"
                "Enable 'Maps JavaScript API' and 'Maps Elevation API'")
            return

        # Use boundary coordinates if available from map widget
        if self._map_widget and hasattr(self, '_map_boundary') and self._map_boundary:
            boundary = self._map_boundary
            lat = (boundary['lat_min'] + boundary['lat_max']) / 2
            lng = (boundary['lng_min'] + boundary['lng_max']) / 2
            lat_span_deg = boundary['lat_max'] - boundary['lat_min']
            lng_span_deg = boundary['lng_max'] - boundary['lng_min']
            print(f"[SiteDialog] Using map boundary for elevation: {lat:.4f}, {lng:.4f}")
        else:
            # Fallback to manual inputs
            if hasattr(self, '_lat_input'):
                lat = self._lat_input.value()
                lng = self._lng_input.value()
            elif self._map_widget:
                lat, lng = self._map_widget.get_coordinates()
            else:
                QMessageBox.warning(self, "Location Required",
                    "Please select a location on the map or enter coordinates.")
                return

            width_ft = self._width_input.value()
            depth_ft = self._depth_input.value()

            # Convert property dimensions to degrees (approximate)
            # 1 degree latitude ≈ 69 miles (364,000 ft)
            # 1 degree longitude varies by latitude
            lat_span_deg = (depth_ft / 364000.0)
            lng_span_deg = (width_ft / 364000.0) / max(0.01, abs(lat))

        grid_points = self._grid_density_combo.currentData()
        total_points = grid_points * grid_points
        estimated_batches = (total_points + 99) // 100  # 100 point batch size

        print(f"[SiteDialog] Fetching elevation: {total_points} points in ~{estimated_batches} batches")

        # Warn user if using very high density
        if total_points > 400:
            reply = QMessageBox.question(
                self,
                "Large Grid Warning",
                f"You're about to fetch {total_points} elevation points.\n\n"
                f"This will make ~{estimated_batches} API requests and may take a while.\n\n"
                f"Would you like to use a smaller grid (15x15 or less) for faster results?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._grid_density_combo.setCurrentIndex(1)  # Switch to 15x15
                grid_points = 15
                total_points = 225

        # Disable button and show progress
        self._fetch_elevation_btn.setEnabled(False)
        self._elevation_progress.setVisible(True)
        self._elevation_progress.setRange(0, 100)  # Indeterminate
        self._elevation_progress.setValue(0)
        self._elevation_results.setText("Initializing...")

        # Start background fetcher
        self._elevation_fetcher = ElevationFetcher(
            lat, lng, lat_span_deg, lng_span_deg, api_key, grid_points
        )
        self._elevation_fetcher.progress.connect(self._on_elevation_progress)
        self._elevation_fetcher.finished.connect(self._on_elevation_finished)
        self._elevation_fetcher.error.connect(self._on_elevation_error)
        self._elevation_fetcher.start()

    def _on_elevation_progress(self, message):
        """Handle elevation fetch progress updates."""
        self._elevation_results.setText(message)
        self._elevation_progress.setValue(self._elevation_progress.value() + 1)

    def _on_elevation_finished(self, elevation_data):
        """Handle successful elevation fetch."""
        self._elevation_data = elevation_data

        # Calculate statistics
        elevations_ft = [pt["elevation_ft"] for pt in elevation_data.values()]
        min_elev = min(elevations_ft)
        max_elev = max(elevations_ft)
        elev_change = max_elev - min_elev

        # Determine slope category
        if elev_change < 2:
            slope = "Flat (0-5%)"
        elif elev_change < 10:
            slope = "Gentle Slope (5-15%)"
        elif elev_change < 25:
            slope = "Moderate Slope (15-25%)"
        else:
            slope = "Steep Slope (25%+)"

        # Update UI with results
        self._elevation_results.setText(
            f"✓ Fetched {len(elevation_data)} elevation points\n"
            f"  Elevation range: {min_elev:.1f}' to {max_elev:.1f}' (change: {elev_change:.1f}')\n"
            f"  Terrain: {slope}"
        )
        self._elevation_progress.setValue(100)
        self._fetch_elevation_btn.setEnabled(True)

        # Auto-update terrain tab with fetched data
        self._elevation_change.setValue(int(elev_change))
        idx = self._slope_combo.findText(slope)
        if idx >= 0:
            self._slope_combo.setCurrentIndex(idx)

        # Store in site data
        print(f"[SiteDialog] Elevation data fetched: {len(elevation_data)} points")
        print(f"[SiteDialog]   Min: {min_elev:.1f}', Max: {max_elev:.1f}', Change: {elev_change:.1f}'")

        # Generate terrain mesh
        print("[SiteDialog] Generating terrain mesh...")
        try:
            # Create temporary site dict for terrain generation
            temp_site = {
                "property_width_ft": self._width_input.value(),
                "property_depth_ft": self._depth_input.value(),
                "google_maps": {
                    "elevation_grid": self._elevation_data
                }
            }

            mesh = generate_terrain_from_site(temp_site)
            if mesh:
                self._terrain_mesh = mesh
                print(f"[SiteDialog] Terrain mesh generated: {len(mesh.vertices)} vertices, {len(mesh.indices)//3} triangles")
                self._elevation_results.setText(
                    self._elevation_results.text() + f"\n  ✓ 3D mesh generated ({len(mesh.vertices)} vertices)"
                )
        except Exception as e:
            print(f"[SiteDialog] Error generating terrain mesh: {e}")
            import traceback
            traceback.print_exc()

    def _on_elevation_error(self, error_msg):
        """Handle elevation fetch error."""
        self._elevation_results.setText(f"Error: {error_msg}")
        self._elevation_progress.setVisible(False)
        self._fetch_elevation_btn.setEnabled(True)
        QMessageBox.critical(self, "Elevation Fetch Failed",
            f"Could not fetch elevation data:\n{error_msg}\n\n"
            "Please check:\n"
            "• API key is correct\n"
            "• Elevation API is enabled\n"
            "• Internet connection is active")

    def _on_next(self):
        """Handle Next button - validate and emit site data."""
        # Validate
        if self._width_input.value() <= 0 or self._depth_input.value() <= 0:
            QMessageBox.warning(self, "Invalid Dimensions", "Please enter valid property dimensions.")
            return

        # Collect site data
        self.site_data = {
            "property_width_ft": self._width_input.value(),
            "property_depth_ft": self._depth_input.value(),
            "road_location": self._road_side_combo.currentText(),
            "road_width_ft": self._road_width_input.value(),
            "driveway_required": self._driveway_check.isChecked(),
            "setback_front_ft": self._front_setback.value(),
            "setback_rear_ft": self._rear_setback.value(),
            "setback_side_ft": self._side_setback.value(),
            "max_coverage_percent": self._max_coverage.value(),
            "max_height_ft": self._max_height.value(),
            "slope": self._slope_combo.currentText(),
            "elevation_change_ft": self._elevation_change.value(),
            "solar_orientation": self._orientation_combo.currentText(),
            "solar_access": self._solar_access.isChecked(),
            "views": {
                "north": self._view_north.isChecked(),
                "east": self._view_east.isChecked(),
                "south": self._view_south.isChecked(),
                "west": self._view_west.isChecked(),
            },
            "feature_notes": self._feature_notes.toPlainText(),
            "imported_files": {
                "survey": self._survey_label.text(),
                "topography": self._topo_label.text(),
                "map": self._map_label.text(),
                "cad": self._cad_label.text(),
            }
        }

        # Calculate buildable area
        buildable_width = (self._width_input.value() -
                          2 * self._side_setback.value())
        buildable_depth = (self._depth_input.value() -
                          (self._front_setback.value() + self._rear_setback.value()))
        self.site_data["buildable_width_ft"] = buildable_width
        self.site_data["buildable_depth_ft"] = buildable_depth
        self.site_data["buildable_area_sqft"] = buildable_width * buildable_depth
        self.site_data["max_building_footprint_sqft"] = (
            buildable_width * buildable_depth * self._max_coverage.value() / 100
        )

        # Add Google Maps data
        google_maps_data = {
            "api_key": self._api_key_input.text().strip(),
            "elevation_grid": self._elevation_data if self._elevation_data else {}
        }

        # Add coordinates (from map widget or manual input)
        if self._map_widget:
            lat, lng = self._map_widget.get_coordinates()
            google_maps_data["latitude"] = lat
            google_maps_data["longitude"] = lng
        elif hasattr(self, '_lat_input'):
            google_maps_data["latitude"] = self._lat_input.value()
            google_maps_data["longitude"] = self._lng_input.value()

        # Add boundary data if drawn on map
        if hasattr(self, '_map_boundary') and self._map_boundary:
            google_maps_data["boundary"] = {
                "lat_min": self._map_boundary["lat_min"],
                "lat_max": self._map_boundary["lat_max"],
                "lng_min": self._map_boundary["lng_min"],
                "lng_max": self._map_boundary["lng_max"],
                "width_ft": self._map_boundary.get("width_ft", 0),
                "depth_ft": self._map_boundary.get("depth_ft", 0)
            }

        self.site_data["google_maps"] = google_maps_data

        # Add terrain mesh if generated
        if hasattr(self, '_terrain_mesh') and self._terrain_mesh:
            self.site_data["terrain_mesh"] = self._terrain_mesh.to_dict()
            print(f"[SiteDialog] Terrain mesh saved to site data")

        # Save site for future use
        self._save_site(self.site_data)

        # Emit signal and accept
        self.site_defined.emit(self.site_data)
        self.accept()


def show_site_dialog(parent=None):
    """
    Show the site definition dialog and return site data.

    Returns:
        dict: Site data if user clicked Next, None if cancelled
    """
    dialog = SiteDialog(parent)
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        return dialog.site_data
    return None
