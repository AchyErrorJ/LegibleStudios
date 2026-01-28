"""
Google Maps Widget for PyQt6
=============================
Embedded Google Maps view with coordinate picking and boundary drawing.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QFormLayout, QDoubleSpinBox, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import pyqtSignal, QUrl, QObject, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel


class WebEnginePage(QWebEnginePage):
    """Custom WebEngine page to capture JavaScript console messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.console_messages = []

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        """Capture JavaScript console messages."""
        msg_str = f"[JS Console] {level.name}: {message} (line {line_number})"
        print(msg_str)
        self.console_messages.append(msg_str)


class GoogleMapsWidget(QWidget):
    """Embedded Google Maps view with coordinate picking and boundary drawing."""

    # Signals
    coordinates_picked = pyqtSignal(float, float)  # lat, lng
    boundary_drawn = pyqtSignal(dict)  # {lat_min, lat_max, lng_min, lng_max, width_ft, depth_ft}
    location_changed = pyqtSignal(str)  # formatted address

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lat = 45.4215  # Default: Montreal
        self._lng = -75.6972
        self._zoom = 17
        self._api_key = ""

        self._drawing_mode = False
        self._boundary_set = False

        self._setup_ui()
        self._setup_bridge()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Controls toolbar
        toolbar = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search location (e.g., '123 Main St, Montreal')...")
        self._search_input.returnPressed.connect(self._on_search)
        toolbar.addWidget(QLabel("Search:"))
        toolbar.addWidget(self._search_input)

        search_btn = QPushButton("Go")
        search_btn.clicked.connect(self._on_search)
        toolbar.addWidget(search_btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # Drawing controls
        draw_toolbar = QHBoxLayout()

        self._draw_btn = QPushButton("📐 Draw Site Boundary")
        self._draw_btn.setCheckable(True)
        self._draw_btn.clicked.connect(self._toggle_draw_mode)
        draw_toolbar.addWidget(self._draw_btn)

        self._clear_btn = QPushButton("Clear Boundary")
        self._clear_btn.clicked.connect(self._clear_boundary)
        self._clear_btn.setEnabled(False)
        draw_toolbar.addWidget(self._clear_btn)

        draw_toolbar.addStretch()

        self._coords_label = QLabel("Click map to center")
        self._coords_label.setStyleSheet("color: #666; font-size: 11px;")
        draw_toolbar.addWidget(self._coords_label)

        layout.addLayout(draw_toolbar)

        # Boundary info (shown after drawing)
        self._boundary_info = QLabel("")
        self._boundary_info.setStyleSheet("color: #4CAF50; font-size: 12px; padding: 4px; background: #f0f8ff; border-radius: 4px;")
        self._boundary_info.setVisible(False)
        layout.addWidget(self._boundary_info)

        # Web view with Google Maps
        self._web_view = QWebEngineView()
        # Use custom page to capture JavaScript console messages
        self._web_view.setPage(WebEnginePage(self._web_view))
        self._web_view.setMinimumHeight(400)
        layout.addWidget(self._web_view)

        # Load initial map
        self._load_map()

        # JavaScript bridge for coordinate updates
        self._web_view.page().loadFinished.connect(self._on_map_loaded)

    def _setup_bridge(self):
        """Setup JavaScript bridge for two-way communication."""
        self._channel = QWebChannel()
        self._web_view.page().setWebChannel(self._channel)

        # Register the bridge object
        self._bridge = MapBridge(self)
        self._channel.registerObject("bridge", self._bridge)

    def _load_map(self):
        """Load Google Maps with JavaScript API."""
        html = self._get_map_html(self._api_key)
        print(f"[GoogleMapsWidget] Loading map, HTML length: {len(html)}")
        print(f"[GoogleMapsWidget] API key set: {bool(self._api_key)}")
        # Set a proper base URL so external scripts load correctly
        from PyQt6.QtCore import QUrl
        base_url = QUrl("https://maps.googleapis.com")
        self._web_view.setHtml(html, base_url)
        print("[GoogleMapsWidget] HTML set with base URL, waiting for page to load...")

    def _on_map_loaded(self, success: bool):
        """Called when map finishes loading."""
        print(f"[GoogleMapsWidget] Page loaded: {success}")
        # Test if Google Maps API loaded
        js_test = """
        (function() {
            if (typeof google === 'undefined') {
                console.error('Google Maps API not loaded - google object is undefined');
                return 'API_NOT_LOADED';
            } else if (typeof google.maps === 'undefined') {
                console.error('Google Maps API not loaded - google.maps is undefined');
                return 'MAPS_NOT_LOADED';
            } else if (typeof map === 'undefined') {
                console.error('Map object not initialized');
                return 'MAP_NOT_INITIALIZED';
            } else {
                console.log('Google Maps loaded successfully!');
                return 'OK';
            }
        })();
        """
        self._web_view.page().runJavaScript(js_test, self._on_api_test_result)

    def _on_api_test_result(self, result):
        """Handle Google Maps API test result."""
        print(f"[GoogleMapsWidget] API Test Result: {result}")
        if result != 'OK':
            print(f"[GoogleMapsWidget] WARNING: Google Maps may not be working properly")

    def _toggle_draw_mode(self):
        """Toggle boundary drawing mode."""
        self._drawing_mode = self._draw_btn.isChecked()

        if self._drawing_mode:
            self._draw_btn.setText("Cancel Drawing")
            self._web_view.page().runJavaScript("startDrawing();")
        else:
            self._draw_btn.setText("📐 Draw Property Boundary")
            self._web_view.page().runJavaScript("cancelDrawing();")

    def _clear_boundary(self):
        """Clear the drawn boundary."""
        self._boundary_set = False
        self._clear_btn.setEnabled(False)
        self._boundary_info.setVisible(False)
        self._web_view.page().runJavaScript("clearBoundary();")

    def _on_search(self):
        """Search for a location."""
        query = self._search_input.text().strip()
        if query:
            # Escape single quotes for JavaScript
            query_escaped = query.replace("'", "\\'")
            js = f"searchLocation('{query_escaped}');"
            self._web_view.page().runJavaScript(js)

    def set_api_key(self, api_key: str):
        """Set the Google Maps JavaScript API key."""
        print(f"[GoogleMapsWidget] set_api_key called with key length: {len(api_key)}")
        self._api_key = api_key
        html = self._get_map_html(api_key)
        print(f"[GoogleMapsWidget] Reloading map with API key, HTML length: {len(html)}")
        # Set a proper base URL so external scripts load correctly
        from PyQt6.QtCore import QUrl
        base_url = QUrl("https://maps.googleapis.com")
        self._web_view.setHtml(html, base_url)
        print("[GoogleMapsWidget] Map reloaded with new API key")

    def set_coordinates(self, lat: float, lng: float, zoom: int = None):
        """Set map coordinates."""
        self._lat = lat
        self._lng = lng
        if zoom:
            self._zoom = zoom

        self._coords_label.setText(f"{lat:.6f}, {lng:.6f}")

        js = f"setCenter({lat}, {lng}, {zoom or self._zoom});"
        self._web_view.page().runJavaScript(js)

    def get_coordinates(self) -> tuple[float, float]:
        """Get current map center coordinates."""
        return self._lat, self._lng

    def get_boundary(self) -> dict:
        """Get the drawn boundary data."""
        if not self._boundary_set:
            return None

        # Return cached boundary data
        return getattr(self, '_boundary_data', None)

    def _on_coordinates_changed(self, lat: float, lng: float):
        """Handle coordinate change from map."""
        self._lat = lat
        self._lng = lng
        self._coords_label.setText(f"Center: {lat:.6f}, {lng:.6f}")
        self.coordinates_picked.emit(lat, lng)

    def _on_location_changed(self, address: str):
        """Handle location change from search."""
        self._search_input.setStyleSheet("")
        self.location_changed.emit(address)

    def _on_search_failed(self, message: str):
        """Handle search failure."""
        self._search_input.setStyleSheet("border: 1px solid red;")
        self._coords_label.setText("Search failed")
        self._coords_label.setStyleSheet("color: red;")

    def _on_boundary_completed(self, bounds: dict):
        """Handle completed boundary drawing."""
        self._boundary_set = True
        self._boundary_data = bounds
        self._clear_btn.setEnabled(True)

        # Calculate approximate width/depth in feet
        # 1 degree latitude ≈ 364,000 ft
        # 1 degree longitude ≈ 364,000 ft * cos(latitude)
        lat_ft_per_deg = 364000
        lng_ft_per_deg = 364000 * (3.14159 / 180) * (6371000 / 0.3048) * abs(3.14159 / 180)

        width_deg = bounds['lng_max'] - bounds['lng_min']
        depth_deg = bounds['lat_max'] - bounds['lat_min']

        width_ft = width_deg * lng_ft_per_deg * abs(3.14159 / 180) * 6371000 / 0.3048 * (bounds['lat_min'] + bounds['lat_max']) / 2 * 3.14159 / 180
        depth_ft = depth_deg * lat_ft_per_deg

        # More accurate calculation
        import math
        lat_center = (bounds['lat_min'] + bounds['lat_max']) / 2
        lat_radius = 6371000 / 0.3048  # Earth radius in feet

        depth_ft = (bounds['lat_max'] - bounds['lat_min']) * math.pi / 180 * lat_radius
        width_ft = (bounds['lng_max'] - bounds['lng_min']) * math.pi / 180 * lat_radius * math.cos(lat_center * math.pi / 180)

        self._boundary_data['width_ft'] = round(width_ft, 1)
        self._boundary_data['depth_ft'] = round(depth_ft, 1)

        # Show boundary info
        self._boundary_info.setText(
            f"✓ Boundary: {self._boundary_data['width_ft']:.0f}' × {self._boundary_data['depth_ft']:.0f}' "
            f"({bounds['lat_min']:.4f} to {bounds['lat_max']:.4f}, "
            f"{bounds['lng_min']:.4f} to {bounds['lng_max']:.4f})"
        )
        self._boundary_info.setVisible(True)

        # Emit signal
        self.boundary_drawn.emit(self._boundary_data)

    def _get_map_html(self, api_key: str = "") -> str:
        """Get the HTML for loading Google Maps."""
        key = api_key or "YOUR_API_KEY"
        # Full version with QWebChannel for Python communication
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: #e0e0e0; }}
        #map {{ width: 100%; height: 100vh; position: absolute; top: 0; left: 0; }}
        #status {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            max-width: 450px;
            z-index: 1000;
        }}
        .error {{ color: #d32f2f; background: #ffebee; }}
        .loading {{ color: #1976d2; }}
        .success {{ color: #388e3c; }}
        .info-window {{ padding: 10px; font-family: Arial, sans-serif; font-size: 14px; }}
    </style>
</head>
<body>
    <div id="status">
        <div class="loading">
            <h3>Loading Google Maps...</h3>
            <p>Please wait while the map initializes.</p>
        </div>
    </div>
    <div id="map"></div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        let map;
        let centerMarker;
        let boundaryRect;
        let drawingMode = false;
        let startPoint = null;
        let bridge = null;

        function showStatus(message, type) {{
            const statusDiv = document.getElementById('status');
            const mapDiv = document.getElementById('map');
            if (type === 'success') {{
                statusDiv.style.display = 'none';
                mapDiv.style.display = 'block';
            }} else {{
                statusDiv.className = type;
                statusDiv.innerHTML = '<h3>' + (type === 'error' ? 'Error' : 'Loading') + '</h3><p>' + message + '</p>';
                statusDiv.style.display = 'block';
            }}
        }}

        function initMap() {{
            console.log('initMap() called!');
            const defaultPos = {{lat: {self._lat}, lng: {self._lng}}};

            try {{
                map = new google.maps.Map(document.getElementById("map"), {{
                    center: defaultPos,
                    zoom: {self._zoom},
                    mapTypeId: google.maps.MapTypeId.HYBRID,
                    tilt: 0,
                    mapTypeControl: true,
                    streetViewControl: false,
                    fullscreenControl: false,
                    keyboardShortcuts: false
                }});

                centerMarker = new google.maps.Marker({{
                    position: defaultPos,
                    map: map,
                    draggable: true,
                    title: "Site Location - Drag to move, or use Draw Boundary to set property area"
                }});

                centerMarker.addListener("dragend", function() {{
                    const pos = centerMarker.getPosition();
                    updateCoordinates(pos.lat(), pos.lng());
                }});

                map.addListener("click", function(e) {{
                    if (drawingMode) {{
                        handleDrawingClick(e.latLng);
                    }} else {{
                        centerMarker.setPosition(e.latLng);
                        updateCoordinates(e.latLng.lat(), e.latLng.lng());
                    }}
                }});

                showStatus('Map loaded successfully!', 'success');
                console.log('Map initialized successfully!');

            }} catch (error) {{
                showStatus('Error creating map: ' + error.message, 'error');
                console.error('Map initialization error:', error);
            }}
        }}

        function updateCoordinates(lat, lng) {{
            if (bridge) {{
                bridge.onCoordinatesChanged(parseFloat(lat), parseFloat(lng));
            }}
        }}

        function setCenter(lat, lng, zoom) {{
            const pos = {{lat: lat, lng: lng}};
            centerMarker.setPosition(pos);
            map.setCenter(pos);
            if (zoom) map.setZoom(zoom);
        }}

        function searchLocation(query) {{
            const geocoder = new google.maps.Geocoder();
            geocoder.geocode({{address: query}}, function(results, status) {{
                if (status === "OK" && results[0]) {{
                    const loc = results[0].geometry.location;
                    setCenter(loc.lat(), loc.lng(), 17);
                    if (bridge) {{
                        bridge.onLocationChanged(results[0].formatted_address || query);
                    }}
                }} else if (bridge) {{
                    bridge.onSearchFailed("Not found: " + query);
                }}
            }});
        }}

        // Boundary drawing
        function startDrawing() {{
            drawingMode = true;
            startPoint = null;
            if (boundaryRect) {{
                boundaryRect.setMap(null);
                boundaryRect = null;
            }}
            map.setOptions({{draggableCursor: 'crosshair'}});
        }}

        function cancelDrawing() {{
            drawingMode = false;
            startPoint = null;
            map.setOptions({{draggableCursor: null}});
        }}

        function clearBoundary() {{
            if (boundaryRect) {{
                boundaryRect.setMap(null);
                boundaryRect = null;
            }}
        }}

        function handleDrawingClick(latLng) {{
            if (!startPoint) {{
                startPoint = latLng;
                boundaryRect = new google.maps.Rectangle({{
                    map: map,
                    bounds: {{
                        north: latLng.lat(),
                        south: latLng.lat(),
                        east: latLng.lng(),
                        west: latLng.lng()
                    }},
                    editable: true,
                    draggable: true,
                    fillColor: '#00ff00',
                    fillOpacity: 0.2,
                    strokeColor: '#00ff00',
                    strokeWeight: 2
                }});

                const infoWindow = new google.maps.InfoWindow({{
                    position: latLng,
                    content: '<div class="info-window">Click opposite corner to complete boundary</div>'
                }});
                infoWindow.open(map);
                setTimeout(() => infoWindow.close(), 3000);

            }} else {{
                const bounds = {{
                    north: Math.max(startPoint.lat(), latLng.lat()),
                    south: Math.min(startPoint.lat(), latLng.lat()),
                    east: Math.max(startPoint.lng(), latLng.lng()),
                    west: Math.min(startPoint.lng(), latLng.lng())
                }};

                boundaryRect.setBounds(bounds);

                if (bridge) {{
                    bridge.onBoundaryCompleted(
                        bounds.south, bounds.north,
                        bounds.west, bounds.east
                    );
                }}

                drawingMode = false;
                startPoint = null;
                map.setOptions({{draggableCursor: null}});
            }}
        }}

        // Load Google Maps API
        const script = document.createElement("script");
        const apiKey = '{key}';
        script.src = "https://maps.googleapis.com/maps/api/js?key=" + apiKey + "&callback=initMap";
        script.async = true;

        console.log('Loading Google Maps API...');
        console.log('API Key provided:', apiKey.length > 0 && apiKey !== 'YOUR_API_KEY' ? 'Yes (' + apiKey.length + ' chars)' : 'No');

        script.onerror = function() {{
            console.error('Script onerror triggered');
            showStatus('Network error loading Google Maps API.<br><br>Check your internet connection.', 'error');
        }};

        setTimeout(function() {{
            if (typeof google === 'undefined') {{
                console.error('google object is undefined after timeout');
                showStatus('Google Maps API failed to load.<br><br>API Key: ' + (apiKey.length > 0 && apiKey !== 'YOUR_API_KEY' ? 'Set' : 'Not set'), 'error');
            }}
        }}, 15000);

        document.head.appendChild(script);

        // Initialize QWebChannel
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            bridge = channel.objects.bridge;
            console.log('QWebChannel connected');
        }});
    </script>
</body>
</html>
        """


class MapBridge(QObject):
    """Bridge object for JavaScript to Python communication."""

    # Signals
    coordinatesChanged = pyqtSignal(float, float)
    locationChanged = pyqtSignal(str)
    searchFailed = pyqtSignal(str)
    boundaryCompleted = pyqtSignal(float, float, float, float)  # lat_min, lat_max, lng_min, lng_max

    def __init__(self, widget: GoogleMapsWidget):
        super().__init__(widget)
        self._widget = widget
        # Internal signal handlers
        self.coordinatesChanged.connect(self._widget._on_coordinates_changed)
        self.locationChanged.connect(self._widget._on_location_changed)
        self.searchFailed.connect(self._widget._on_search_failed)
        self.boundaryCompleted.connect(self._on_boundary_completed_internal)

    def _on_boundary_completed_internal(self, lat_min: float, lat_max: float, lng_min: float, lng_max: float):
        """Handle boundary completed from JavaScript signal."""
        bounds = {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lng_min': lng_min,
            'lng_max': lng_max
        }
        self._widget._on_boundary_completed(bounds)

    # Slots callable from JavaScript
    @pyqtSlot(float, float)
    def onCoordinatesChanged(self, lat: float, lng: float):
        """Called from JavaScript when coordinates change."""
        self.coordinatesChanged.emit(lat, lng)

    @pyqtSlot(str)
    def onLocationChanged(self, address: str):
        """Called from JavaScript when location is found."""
        self.locationChanged.emit(address)

    @pyqtSlot(str)
    def onSearchFailed(self, message: str):
        """Called from JavaScript when search fails."""
        self.searchFailed.emit(message)

    @pyqtSlot(float, float, float, float)
    def onBoundaryCompleted(self, lat_min: float, lat_max: float, lng_min: float, lng_max: float):
        """Called from JavaScript when boundary drawing completes."""
        self.boundaryCompleted.emit(lat_min, lat_max, lng_min, lng_max)
