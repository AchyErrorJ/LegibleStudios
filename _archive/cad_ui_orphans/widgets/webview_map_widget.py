"""
WebView2 Google Maps Launcher for PyQt6
==========================================
Launches Google Maps in a separate WebView2 window.
Runs as a subprocess to avoid threading issues.
"""

import sys
import os
import json
import subprocess
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtCore import QObject, pyqtSignal, QProcess


class WebViewMapWidget(QObject):
    """
    Launches OpenStreetMap/Leaflet in a separate process using WebView2.
    This avoids threading issues with pywebview.
    No API key required for OpenStreetMap.
    """

    boundary_changed = pyqtSignal(float, float, float, float)  # lat_min, lat_max, lng_min, lng_max

    def __init__(self, api_key: str = "", lat: float = 45.4215, lng: float = -75.6972, zoom: int = 16, parent=None):
        super().__init__(parent)
        self._api_key = api_key  # Not used for OpenStreetMap, kept for compatibility
        self._lat = lat
        self._lng = lng
        self._zoom = zoom
        self._process = None
        self._temp_file = None

    def show(self):
        """Show the map window in a separate process."""
        # Create temporary file for boundary data
        self._temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
        self._temp_file.close()

        # Get the path to the map launcher script
        script_dir = os.path.dirname(__file__)
        launcher_script = os.path.join(script_dir, 'webview_map_launcher.py')

        # Launch the map in a separate process
        self._process = QProcess(self)
        self._process.finished.connect(self._on_process_finished)

        args = [
            sys.executable,
            launcher_script,
            '--api-key', self._api_key,
            '--lat', str(self._lat),
            '--lng', str(self._lng),
            '--zoom', str(self._zoom),
            '--output', self._temp_file.name
        ]

        print(f"[WebViewMap] Launching map process: {' '.join(args)}")
        self._process.start(sys.executable, [launcher_script, '--api-key', self._api_key,
                                              '--lat', str(self._lat), '--lng', str(self._lng),
                                              '--zoom', str(self._zoom),
                                              '--output', self._temp_file.name])

    def _on_process_finished(self, exit_code, exit_status):
        """Handle process completion."""
        print(f"[WebViewMap] Process finished with exit code {exit_code}, status {exit_status}")

        # Read boundary data from temp file
        try:
            if self._temp_file and os.path.exists(self._temp_file.name):
                print(f"[WebViewMap] Reading boundary from: {self._temp_file.name}")
                with open(self._temp_file.name, 'r') as f:
                    content = f.read()
                    print(f"[WebViewMap] File content ({len(content)} bytes): {content[:200]}")

                with open(self._temp_file.name, 'r') as f:
                    data = json.load(f)
                    if 'boundary' in data:
                        boundary = data['boundary']
                        print(f"[WebViewMap] Boundary received: {boundary}")
                        self.boundary_changed.emit(
                            boundary['lat_min'],
                            boundary['lat_max'],
                            boundary['lng_min'],
                            boundary['lng_max']
                        )
                # Clean up temp file
                os.unlink(self._temp_file.name)
            else:
                print(f"[WebViewMap] Temp file not found: {self._temp_file.name if self._temp_file else 'None'}")
        except Exception as e:
            import traceback
            print(f"[WebViewMap] Error reading boundary data: {e}")
            traceback.print_exc()

    def set_location(self, lat: float, lng: float, zoom: int):
        """Set the map center and zoom level (not supported in separate process mode)."""
        print(f"[WebViewMap] set_location called but not supported in subprocess mode")

    def set_zoom(self, zoom: int):
        """Set the zoom level (not supported)."""
        pass

    def clear_boundary(self):
        """Clear the drawn boundary (not supported)."""
        pass

    def close(self):
        """Close the map window."""
        if self._process:
            self._process.terminate()
