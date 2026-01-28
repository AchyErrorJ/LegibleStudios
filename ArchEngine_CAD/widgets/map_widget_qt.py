"""
Map Widget for PyQt6 - C++ Backend
====================================
Wraps the C++ MapWidgetLib DLL that provides Google Maps integration.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
import ctypes
from ctypes import c_void_p, c_int, c_double, c_char_p

class MapWidgetQt(QWidget):
    """Qt widget that wraps the C++ map widget DLL."""

    # Signals
    boundary_changed = pyqtSignal(float, float, float, float)  # lat_min, lat_max, lng_min, lng_max

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dll = None
        self._initialized = False
        self._setup_ui()
        self._load_dll()
        self._init_map()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _load_dll(self):
        """Load the MapWidgetLib DLL."""
        dll_path = os.path.join(os.path.dirname(__file__), '..', 'dll', 'MapWidgetLib.dll')

        if not os.path.exists(dll_path):
            print(f"[MapWidgetQt] DLL not found at: {dll_path}")
            return

        try:
            self._dll = ctypes.CDLL(dll_path)
            print(f"[MapWidgetQt] Loaded MapWidgetLib.dll")

            # Setup function signatures
            self._dll.map_init.argtypes = [c_void_p, c_int, c_int]
            self._dll.map_init.restype = c_int

            self._dll.map_set_api_key.argtypes = [c_char_p]
            self._dll.map_set_api_key.restype = None

            self._dll.map_set_location.argtypes = [c_double, c_double, c_int]
            self._dll.map_set_location.restype = None

            self._dll.map_get_boundary.argtypes = [c_void_p, c_void_p, c_void_p, c_void_p]
            self._dll.map_get_boundary.restype = c_int

            self._dll.map_clear_boundary.argtypes = []
            self._dll.map_clear_boundary.restype = None

            self._dll.map_resize.argtypes = [c_int, c_int]
            self._dll.map_resize.restype = None

            self._dll.map_shutdown.argtypes = []
            self._dll.map_shutdown.restype = None

        except Exception as e:
            print(f"[MapWidgetQt] Error loading DLL: {e}")
            self._dll = None

    def _init_map(self):
        """Initialize the map widget."""
        if not self._dll:
            return

        try:
            # Get the window handle (HWND)
            hwnd = int(self.winId())

            # Initialize map
            result = self._dll.map_init(hwnd, self.width(), self.height())
            if result == 0:
                self._initialized = True
                print(f"[MapWidgetQt] Map initialized successfully")
            else:
                print(f"[MapWidgetQt] Map initialization failed with code: {result}")

        except Exception as e:
            print(f"[MapWidgetQt] Error initializing map: {e}")

    def set_api_key(self, api_key: str):
        """Set the Google Maps API key."""
        if self._dll and self._initialized:
            try:
                self._dll.map_set_api_key(api_key.encode('utf-8'))
                print(f"[MapWidgetQt] API key set")
            except Exception as e:
                print(f"[MapWidgetQt] Error setting API key: {e}")

    def set_location(self, lat: float, lng: float, zoom: int = 18):
        """Set the map center and zoom level."""
        if self._dll and self._initialized:
            try:
                self._dll.map_set_location(lat, lng, zoom)
            except Exception as e:
                print(f"[MapWidgetQt] Error setting location: {e}")

    def get_boundary(self):
        """Get the current boundary coordinates."""
        if self._dll and self._initialized:
            try:
                lat_min = c_double()
                lat_max = c_double()
                lng_min = c_double()
                lng_max = c_double()

                result = self._dll.map_get_boundary(
                    ctypes.byref(lat_min),
                    ctypes.byref(lat_max),
                    ctypes.byref(lng_min),
                    ctypes.byref(lng_max)
                )

                if result:
                    return {
                        'lat_min': lat_min.value,
                        'lat_max': lat_max.value,
                        'lng_min': lng_min.value,
                        'lng_max': lng_max.value
                    }
            except Exception as e:
                print(f"[MapWidgetQt] Error getting boundary: {e}")

        return None

    def clear_boundary(self):
        """Clear the drawn boundary."""
        if self._dll and self._initialized:
            try:
                self._dll.map_clear_boundary()
            except Exception as e:
                print(f"[MapWidgetQt] Error clearing boundary: {e}")

    def resizeEvent(self, event):
        """Handle resize events."""
        super().resizeEvent(event)
        if self._dll and self._initialized:
            try:
                self._dll.map_resize(self.width(), self.height())
            except Exception as e:
                print(f"[MapWidgetQt] Error resizing: {e}")

    def closeEvent(self, event):
        """Handle cleanup on close."""
        if self._dll:
            try:
                self._dll.map_shutdown()
            except:
                pass
        super().closeEvent(event)
