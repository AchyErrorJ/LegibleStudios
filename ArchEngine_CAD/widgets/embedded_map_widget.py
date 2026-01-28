"""
Embedded OpenStreetMap Widget for PyQt6
========================================
Simple map widget using QProcess to launch webview.
"""

import sys
import os
import json
import tempfile
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QLabel, QPushButton
from PyQt6.QtCore import QObject, pyqtSignal, QProcess, QTimer


class EmbeddedMapWidget(QWidget):
    """
    Qt widget that launches an interactive OpenStreetMap using webview.
    The map runs in a separate process and communicates via temp file.
    """

    boundary_changed = pyqtSignal(float, float, float, float, float, float)  # lat_min, lat_max, lng_min, lng_max, width_ft, depth_ft

    def __init__(self, lat=45.4215, lng=-75.6972, zoom=16, parent=None):
        super().__init__(parent)
        self._lat = lat
        self._lng = lng
        self._zoom = zoom
        self._process = None
        self._temp_file = None
        self._poll_timer = None

        # Setup UI
        layout = QVBoxLayout(self)

        # Info label
        self._info_label = QLabel("Opening map window...")
        layout.addWidget(self._info_label)

        # Start the map
        self._start_map()

    def _start_map(self):
        """Start the webview map process."""
        try:
            # Create temp file for boundary data
            self._temp_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False)
            self._temp_file.close()

            # Get path to webview launcher
            launcher_script = os.path.join(os.path.dirname(__file__), 'webview_map_launcher.py')

            # Launch the webview map
            self._process = QProcess(self)
            self._process.finished.connect(self._on_process_finished)

            args = [
                sys.executable,
                launcher_script,
                '--api-key', '',  # Not used for OpenStreetMap
                '--lat', str(self._lat),
                '--lng', str(self._lng),
                '--zoom', str(self._zoom),
                '--output', self._temp_file.name
            ]

            print(f"[EmbeddedMap] Launching: {' '.join(args)}")
            self._process.start(sys.executable, [launcher_script, '--api-key', '',
                                                  '--lat', str(self._lat), '--lng', str(self._lng),
                                                  '--zoom', str(self._zoom),
                                                  '--output', self._temp_file.name])

            self._info_label.setText("Map window opened. Draw boundary and click Save & Close.")

            # Start polling for the boundary file
            self._poll_timer = QTimer()
            self._poll_timer.timeout.connect(self._check_boundary_file)
            self._poll_timer.start(500)  # Check every 500ms

        except Exception as e:
            self._info_label.setText(f"Error: {e}")
            print(f"[EmbeddedMap] Error: {e}")
            import traceback
            traceback.print_exc()

    def _check_boundary_file(self):
        """Poll for boundary data file."""
        if not self._temp_file:
            return

        if not os.path.exists(self._temp_file.name):
            # File doesn't exist yet, keep waiting
            return

        # Check file size - wait until it has content
        try:
            file_size = os.path.getsize(self._temp_file.name)
            if file_size < 10:
                # File is too small, probably being written, wait longer
                return
        except:
            return

        print(f"[EmbeddedMap] File exists with size: {file_size}")

        try:
            # Read with a small delay to ensure write is complete
            import time
            time.sleep(0.1)  # Wait 100ms for file write to complete

            with open(self._temp_file.name, 'r') as f:
                content = f.read()
                if not content or len(content) < 10:
                    # Empty file, keep waiting
                    return

                print(f"[EmbeddedMap] File content: {content[:200]}")
                data = json.loads(content)
                boundary = data.get('boundary', {})

                if boundary and 'lat_min' in boundary:
                    print(f"[EmbeddedMap] Boundary found: {boundary}")

                    # Stop polling
                    if self._poll_timer:
                        self._poll_timer.stop()
                        self._poll_timer = None

                    # Clean up temp file (ignore errors if still in use)
                    try:
                        os.unlink(self._temp_file.name)
                    except:
                        pass
                    self._temp_file = None

                    # Emit signal with boundary data
                    print(f"[EmbeddedMap] Emitting boundary_changed signal")
                    self.boundary_changed.emit(
                        boundary['lat_min'],
                        boundary['lat_max'],
                        boundary['lng_min'],
                        boundary['lng_max'],
                        boundary['width_ft'],
                        boundary['depth_ft']
                    )

                    self._info_label.setText(f"Boundary received: {boundary['width_ft']:.0f}' x {boundary['depth_ft']:.0f}'")
                else:
                    print(f"[EmbeddedMap] No valid boundary in file")

        except json.JSONDecodeError as e:
            # JSON parsing error - file probably still being written
            print(f"[EmbeddedMap] JSON decode error, file still being written: {e}")
            pass
        except Exception as e:
            print(f"[EmbeddedMap] Error reading boundary: {e}")
            import traceback
            traceback.print_exc()

    def _on_process_finished(self, exit_code, exit_status):
        """Handle process completion."""
        print(f"[EmbeddedMap] Process finished with exit code {exit_code}")

    def closeEvent(self, event):
        """Clean up when widget is closed."""
        if self._poll_timer:
            self._poll_timer.stop()
        if self._process:
            self._process.terminate()
        event.accept()
