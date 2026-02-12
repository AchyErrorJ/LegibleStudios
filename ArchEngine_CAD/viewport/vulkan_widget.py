"""
VulkanViewportWidget - Qt widget embedding the Vulkan renderer.

Uses ctypes to call into ArchEngineLib.dll for real-time 3D visualization
of the building model directly in the CAD application.
"""

import ctypes
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor


# ctypes structure matching ArchRoomData in arch_api.h
class ArchRoomData(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char * 64),
        ("name", ctypes.c_char * 128),
        ("room_type", ctypes.c_char * 64),
        ("bounds_x", ctypes.c_float),
        ("bounds_y", ctypes.c_float),
        ("bounds_width", ctypes.c_float),
        ("bounds_height", ctypes.c_float),
        ("center_x", ctypes.c_float),
        ("center_y", ctypes.c_float),
        ("area", ctypes.c_float),
        ("zone", ctypes.c_int),
    ]


# Find the DLL
def _find_dll() -> Optional[Path]:
    """Search for ArchEngineLib.dll - prioritize local worktree."""
    search_paths = [
        # Primary: Relative paths from CAD app (same worktree)
        Path(__file__).parent.parent.parent / "ArchEngine_kernel" / "build" / "Release",
        Path(__file__).parent.parent.parent / "ArchEngine_kernel" / "build" / "Debug",
        # UE5 worktree paths (explicit)
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Debug"),
        # Kernel worktree (fallback)
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Debug"),
    ]

    for path in search_paths:
        dll_path = path / "ArchEngineLib.dll"
        if dll_path.exists():
            return dll_path

    return None


class VulkanViewportWidget(QWidget):
    """
    Qt widget that embeds the Vulkan renderer.

    Usage:
        viewport = VulkanViewportWidget()
        layout.addWidget(viewport)

        # Load building data
        viewport.load_json(building_data)

        # Or load from file
        viewport.load_file("path/to/building.json")
    """

    # Signals
    initialized = pyqtSignal()
    load_complete = pyqtSignal(int)  # element count
    rooms_loaded = pyqtSignal(list)  # list of room dicts
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lib: Optional[ctypes.CDLL] = None
        self._initialized = False
        self._render_timer: Optional[QTimer] = None

        # Camera state for mouse interaction
        self._camera_yaw = 0.5
        self._camera_pitch = 0.4
        self._camera_distance = 60.0
        self._camera_target = [20.0, 10.0, 15.0]  # x, y, z target point
        self._last_mouse_pos = None
        self._dragging = False
        self._panning = False  # True for pan, False for orbit

        self._rendering = False  # Prevent concurrent renders
        self._loading = False    # Prevent concurrent loads
        self._api_lock = threading.Lock()  # Prevent load during render

        # Section drag state
        self._section_mode = False  # Press 'S' to toggle
        self._section_dragging = False

        # Selection manager for Python-side picking + Tab cycling
        self._selection_manager: Optional[SelectionManager] = None
        self._document = None  # Set via set_document()
        self._last_pick_pos = (0, 0)  # For Tab cycling detection

        # Hover state for visual feedback
        self._hovered_element: Optional[tuple] = None  # (element_type, element_id)
        self._hover_update_timer = None  # Throttle hover updates

        # Navigation overlay (optional, may be set later)
        self._nav_overlay = None

        # Widget setup
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Load the library
        self._load_library()

    def _load_library(self):
        """Load ArchEngineLib.dll and set up function signatures."""
        dll_path = _find_dll()
        if dll_path is None:
            print("[VulkanWidget] ArchEngineLib.dll not found")
            return

        try:
            self._lib = ctypes.CDLL(str(dll_path))

            # Define function signatures
            self._lib.arch_init.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            self._lib.arch_init.restype = ctypes.c_int

            self._lib.arch_shutdown.argtypes = []
            self._lib.arch_shutdown.restype = None

            self._lib.arch_is_initialized.argtypes = []
            self._lib.arch_is_initialized.restype = ctypes.c_int

            self._lib.arch_load_json.argtypes = [ctypes.c_char_p]
            self._lib.arch_load_json.restype = ctypes.c_int

            self._lib.arch_load_file.argtypes = [ctypes.c_char_p]
            self._lib.arch_load_file.restype = ctypes.c_int

            self._lib.arch_render_frame.argtypes = []
            self._lib.arch_render_frame.restype = ctypes.c_int

            self._lib.arch_resize.argtypes = [ctypes.c_int, ctypes.c_int]
            self._lib.arch_resize.restype = None

            self._lib.arch_set_camera.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
            self._lib.arch_set_camera.restype = None

            self._lib.arch_set_camera_target.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
            self._lib.arch_set_camera_target.restype = None

            self._lib.arch_reset_camera.argtypes = []
            self._lib.arch_reset_camera.restype = None

            self._lib.arch_set_viz_mode.argtypes = [ctypes.c_int]
            self._lib.arch_set_viz_mode.restype = None

            self._lib.arch_select_element.argtypes = [ctypes.c_int]
            self._lib.arch_select_element.restype = None

            self._lib.arch_get_element_count.argtypes = []
            self._lib.arch_get_element_count.restype = ctypes.c_int

            self._lib.arch_get_error.argtypes = []
            self._lib.arch_get_error.restype = ctypes.c_char_p

            # Section clipping API
            self._lib.arch_set_clipping_enabled.argtypes = [ctypes.c_int]
            self._lib.arch_set_clipping_enabled.restype = None

            self._lib.arch_get_clipping_enabled.argtypes = []
            self._lib.arch_get_clipping_enabled.restype = ctypes.c_int

            self._lib.arch_set_clip_axis.argtypes = [ctypes.c_int]
            self._lib.arch_set_clip_axis.restype = None

            self._lib.arch_get_clip_axis.argtypes = []
            self._lib.arch_get_clip_axis.restype = ctypes.c_int

            self._lib.arch_set_clip_height.argtypes = [ctypes.c_float]
            self._lib.arch_set_clip_height.restype = None

            self._lib.arch_get_clip_height.argtypes = []
            self._lib.arch_get_clip_height.restype = ctypes.c_float

            self._lib.arch_set_clip_flipped.argtypes = [ctypes.c_int]
            self._lib.arch_set_clip_flipped.restype = None

            self._lib.arch_get_clip_flipped.argtypes = []
            self._lib.arch_get_clip_flipped.restype = ctypes.c_int

            self._lib.arch_set_section_floor_plan.argtypes = [ctypes.c_float]
            self._lib.arch_set_section_floor_plan.restype = None

            self._lib.arch_set_section_elevation.argtypes = [ctypes.c_int, ctypes.c_float]
            self._lib.arch_set_section_elevation.restype = None

            # Material style API
            self._lib.arch_set_material_style.argtypes = [ctypes.c_int]
            self._lib.arch_set_material_style.restype = None

            self._lib.arch_get_material_style.argtypes = []
            self._lib.arch_get_material_style.restype = ctypes.c_int

            print(f"[VulkanWidget] Loaded {dll_path}")

            # Try to load extended post-processing API (may not be in older DLLs)
            try:
                # Shadows & Lighting API
                self._lib.arch_set_shadows_enabled.argtypes = [ctypes.c_int]
                self._lib.arch_set_shadows_enabled.restype = None

                self._lib.arch_get_shadows_enabled.argtypes = []
                self._lib.arch_get_shadows_enabled.restype = ctypes.c_int

                self._lib.arch_set_light_direction.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float]
                self._lib.arch_set_light_direction.restype = None

                self._lib.arch_get_light_direction.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float)
                ]
                self._lib.arch_get_light_direction.restype = None

                # SSAO API
                self._lib.arch_set_ssao_enabled.argtypes = [ctypes.c_int]
                self._lib.arch_set_ssao_enabled.restype = None

                self._lib.arch_get_ssao_enabled.argtypes = []
                self._lib.arch_get_ssao_enabled.restype = ctypes.c_int

                self._lib.arch_set_ssao_radius.argtypes = [ctypes.c_float]
                self._lib.arch_set_ssao_radius.restype = None

                self._lib.arch_get_ssao_radius.argtypes = []
                self._lib.arch_get_ssao_radius.restype = ctypes.c_float

                self._lib.arch_set_ssao_intensity.argtypes = [ctypes.c_float]
                self._lib.arch_set_ssao_intensity.restype = None

                self._lib.arch_get_ssao_intensity.argtypes = []
                self._lib.arch_get_ssao_intensity.restype = ctypes.c_float

                # Bloom API
                self._lib.arch_set_bloom_enabled.argtypes = [ctypes.c_int]
                self._lib.arch_set_bloom_enabled.restype = None

                self._lib.arch_get_bloom_enabled.argtypes = []
                self._lib.arch_get_bloom_enabled.restype = ctypes.c_int

                self._lib.arch_set_bloom_threshold.argtypes = [ctypes.c_float]
                self._lib.arch_set_bloom_threshold.restype = None

                self._lib.arch_get_bloom_threshold.argtypes = []
                self._lib.arch_get_bloom_threshold.restype = ctypes.c_float

                self._lib.arch_set_bloom_intensity.argtypes = [ctypes.c_float]
                self._lib.arch_set_bloom_intensity.restype = None

                self._lib.arch_get_bloom_intensity.argtypes = []
                self._lib.arch_get_bloom_intensity.restype = ctypes.c_float

                # Tonemapping & Exposure API
                self._lib.arch_set_exposure.argtypes = [ctypes.c_float]
                self._lib.arch_set_exposure.restype = None

                self._lib.arch_get_exposure.argtypes = []
                self._lib.arch_get_exposure.restype = ctypes.c_float

                self._lib.arch_set_tonemap_mode.argtypes = [ctypes.c_int]
                self._lib.arch_set_tonemap_mode.restype = None

                self._lib.arch_get_tonemap_mode.argtypes = []
                self._lib.arch_get_tonemap_mode.restype = ctypes.c_int

                # Camera view settings API
                self._lib.arch_set_camera_fov.argtypes = [ctypes.c_float]
                self._lib.arch_set_camera_fov.restype = None

                self._lib.arch_get_camera_fov.argtypes = []
                self._lib.arch_get_camera_fov.restype = ctypes.c_float

                self._lib.arch_set_orthographic.argtypes = [ctypes.c_int]
                self._lib.arch_set_orthographic.restype = None

                self._lib.arch_get_orthographic.argtypes = []
                self._lib.arch_get_orthographic.restype = ctypes.c_int

                print("[VulkanWidget] Extended post-processing API loaded")
            except AttributeError as e:
                print(f"[VulkanWidget] Extended API not available: {e}")

        except Exception as e:
            print(f"[VulkanWidget] Failed to load library: {e}")
            self._lib = None

    def showEvent(self, event):
        """Initialize renderer when widget is first shown."""
        super().showEvent(event)

        if not self._initialized and self._lib is not None:
            # Defer initialization to allow window to be fully created
            QTimer.singleShot(100, self._initialize_renderer)

    def _initialize_renderer(self):
        """Initialize the Vulkan renderer with our window handle."""
        if self._initialized or self._lib is None:
            return

        try:
            # Get native window handle
            hwnd = int(self.winId())
            width = self.width()
            height = self.height()

            print(f"[VulkanWidget] Initializing renderer: HWND={hwnd}, size={width}x{height}")

            result = self._lib.arch_init(ctypes.c_void_p(hwnd), width, height)
            if result != 0:
                error = self._lib.arch_get_error()
                if error:
                    error = error.decode('utf-8')
                else:
                    error = "Unknown error"
                print(f"[VulkanWidget] Init failed: {error}")
                self.error_occurred.emit(f"Init failed: {error}")
                return

            self._initialized = True
            print("[VulkanWidget] Renderer initialized")

            # Start render loop - slow rate for stability
            self._render_timer = QTimer(self)
            self._render_timer.timeout.connect(self._render_frame)
            self._render_timer.start(100)  # 10 FPS for stability

            # Don't render immediately - wait for load_json to provide data first

            self.initialized.emit()
        except Exception as e:
            print(f"[VulkanWidget] Initialization exception: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"Init exception: {e}")

    def _render_frame(self):
        """Render a single frame."""
        if not self._initialized or self._lib is None:
            return

        # Skip if no data loaded yet (prevents depth buffer issues on empty scene)
        if not getattr(self, '_has_data', False):
            return

        # Skip if already rendering
        if self._rendering:
            return

        # Skip if widget not visible
        if not self.isVisible():
            return

        # Try to acquire lock (non-blocking) - skip frame if load_json is running
        if not self._api_lock.acquire(blocking=False):
            return

        # Track render count for diagnostics
        if not hasattr(self, '_render_count'):
            self._render_count = 0
        self._render_count += 1

        try:
            self._rendering = True

            # Update camera
            self._lib.arch_set_camera(
                ctypes.c_float(self._camera_yaw),
                ctypes.c_float(self._camera_pitch),
                ctypes.c_float(self._camera_distance)
            )

            # Render
            result = self._lib.arch_render_frame()
            if result != 0:
                # Render failed - stop the render loop
                print("[VulkanWidget] Render failed, stopping render loop")
                if self._render_timer:
                    self._render_timer.stop()
                self._initialized = False
                return

            # Log occasionally to confirm render loop is running
            if self._render_count % 300 == 0:  # Every ~10 seconds at 30fps
                print(f"[VulkanWidget] Rendered {self._render_count} frames")
        except Exception as e:
            print(f"[VulkanWidget] Render exception: {e}")
            import traceback
            traceback.print_exc()
            if self._render_timer:
                self._render_timer.stop()
            self._initialized = False
            return
        finally:
            self._rendering = False
            self._api_lock.release()

    def resizeEvent(self, event):
        """Handle widget resize."""
        super().resizeEvent(event)

        # Only resize if data is loaded (prevents depth buffer issues on empty scene)
        if self._initialized and self._lib is not None and getattr(self, '_has_data', False):
            with self._api_lock:
                self._lib.arch_resize(event.size().width(), event.size().height())

    def closeEvent(self, event):
        """Cleanup on close."""
        self._shutdown()
        super().closeEvent(event)

    def _shutdown(self):
        """Shutdown the renderer."""
        if self._render_timer:
            self._render_timer.stop()
            self._render_timer = None

        if self._initialized and self._lib is not None:
            try:
                print("[VulkanWidget] Shutting down renderer...")
                self._lib.arch_shutdown()
                print("[VulkanWidget] Renderer shutdown complete")
            except Exception as e:
                print(f"[VulkanWidget] Shutdown error: {e}")
            finally:
                self._initialized = False

    # =========================================================================
    # Public API
    # =========================================================================

    def load_json(self, data: dict) -> bool:
        """
        Load building data from a dictionary.

        Args:
            data: Building data in QBD JSON format

        Returns:
            True on success
        """
        if not self._initialized or self._lib is None:
            return False

        # Skip if already loading (prevents queue buildup)
        if self._loading:
            return False

        self._loading = True

        # Stop render timer and acquire lock to ensure no rendering during geometry update
        if self._render_timer:
            self._render_timer.stop()

        try:
            with self._api_lock:
                json_str = json.dumps(data).encode('utf-8')
                result = self._lib.arch_load_json(json_str)

                if result == 0:
                    count = self._lib.arch_get_element_count()
                    print(f"[VulkanWidget] Loaded {count} elements")

                    # Force a sync render to process new geometry before resuming render loop
                    # This helps prevent crashes from stale GPU state
                    self._lib.arch_render_frame()

                    # Enable render loop now that we have data
                    self._has_data = True

                    # Get rooms while we have the lock, but emit signal AFTER releasing lock
                    rooms_to_emit = self.get_rooms()
                    success = True
                else:
                    error = self._lib.arch_get_error().decode('utf-8')
                    print(f"[VulkanWidget] Load failed: {error}")
                    self.error_occurred.emit(error)
                    return False
        finally:
            self._loading = False
            # Restart render timer after a delay to let GPU finish processing new geometry
            if self._render_timer and self._initialized:
                QTimer.singleShot(100, lambda: self._render_timer.start(33) if self._initialized else None)

    def load_file(self, file_path: str) -> bool:
        """
        Load building data from a file.

        Args:
            file_path: Path to JSON file

        Returns:
            True on success
        """
        if not self._initialized or self._lib is None:
            return False

        # Acquire lock to prevent render during load
        with self._api_lock:
            path_bytes = file_path.encode('utf-8')
            result = self._lib.arch_load_file(path_bytes)

            if result == 0:
                count = self._lib.arch_get_element_count()
                print(f"[VulkanWidget] Loaded {count} elements from {file_path}")
                self.load_complete.emit(count)
                return True
            else:
                error = self._lib.arch_get_error().decode('utf-8')
                print(f"[VulkanWidget] Load failed: {error}")
                self.error_occurred.emit(error)
                return False

    def reset_camera(self):
        """Reset camera to fit the building."""
        if self._initialized and self._lib:
            self._lib.arch_reset_camera()

    def set_visualization_mode(self, mode: int):
        """
        Set visualization mode.

        Args:
            mode: 0=Structural, 1=Thermal, 2=Lighting, 3=Acoustic, 4=Material, 5=Wireframe
        """
        if self._initialized and self._lib:
            self._lib.arch_set_viz_mode(mode)

    def select_element(self, index: int):
        """Select an element by index (-1 to clear)."""
        if self._initialized and self._lib:
            self._lib.arch_select_element(index)

    @property
    def element_count(self) -> int:
        """Get number of elements in current building."""
        if self._initialized and self._lib:
            return self._lib.arch_get_element_count()
        return 0

    @property
    def is_initialized(self) -> bool:
        """Check if renderer is ready."""
        return self._initialized

    def get_rooms(self) -> list:
        """Get room data from the renderer via DLL."""
        if not self._initialized or self._lib is None:
            return []

        try:
            room_count = self._lib.arch_get_room_count()
            if room_count <= 0:
                return []

            rooms_array = (ArchRoomData * room_count)()
            result = self._lib.arch_get_all_rooms(rooms_array, room_count)
            if result <= 0:
                return []

            rooms = []
            for i in range(result):
                r = rooms_array[i]
                rooms.append({
                    'id': r.id.decode('utf-8', errors='ignore').rstrip('\x00'),
                    'name': r.name.decode('utf-8', errors='ignore').rstrip('\x00'),
                    'room_type': r.room_type.decode('utf-8', errors='ignore').rstrip('\x00'),
                    'bounds': {
                        'x': r.bounds_x,
                        'y': r.bounds_y,
                        'width': r.bounds_width,
                        'height': r.bounds_height,
                    },
                    'center': {'x': r.center_x, 'y': r.center_y},
                    'area': r.area,
                })
            return rooms
        except Exception as e:
            print(f"[VulkanWidget] get_rooms error: {e}")
            return []

    # =========================================================================
    # Section Clipping
    # =========================================================================

    def set_clipping_enabled(self, enabled: bool):
        """Enable or disable section clipping."""
        if self._initialized and self._lib:
            self._lib.arch_set_clipping_enabled(1 if enabled else 0)

    def get_clipping_enabled(self) -> bool:
        """Check if clipping is enabled."""
        if self._initialized and self._lib:
            return self._lib.arch_get_clipping_enabled() != 0
        return False

    def set_clip_axis(self, axis: int):
        """Set clipping axis (0=X, 1=Y, 2=Z)."""
        if self._initialized and self._lib:
            self._lib.arch_set_clip_axis(axis)

    def get_clip_axis(self) -> int:
        """Get current clipping axis."""
        if self._initialized and self._lib:
            return self._lib.arch_get_clip_axis()
        return 1

    def set_clip_height(self, height: float):
        """Set clipping plane position in feet."""
        if self._initialized and self._lib:
            self._lib.arch_set_clip_height(ctypes.c_float(height))

    def get_clip_height(self) -> float:
        """Get current clipping height in feet."""
        if self._initialized and self._lib:
            return self._lib.arch_get_clip_height()
        return 0.0

    def set_clip_flipped(self, flipped: bool):
        """Flip clipping direction."""
        if self._initialized and self._lib:
            self._lib.arch_set_clip_flipped(1 if flipped else 0)

    def get_clip_flipped(self) -> bool:
        """Check if clipping is flipped."""
        if self._initialized and self._lib:
            return self._lib.arch_get_clip_flipped() != 0
        return False

    def set_section_floor_plan(self, y_height: float):
        """Set up floor plan section at specified height."""
        if self._initialized and self._lib:
            self._lib.arch_set_section_floor_plan(ctypes.c_float(y_height))

    def set_section_elevation(self, axis: int, position: float):
        """Set up elevation section (axis 0=X, 2=Z)."""
        if self._initialized and self._lib:
            self._lib.arch_set_section_elevation(axis, ctypes.c_float(position))

    # =========================================================================
    # Material Style
    # =========================================================================

    def set_material_style(self, style: int):
        """
        Set material rendering style.

        Args:
            style: 0=Realistic, 1=Clean, 2=Schematic, 3=Blueprint
        """
        if self._initialized and self._lib:
            self._lib.arch_set_material_style(style)

    def get_material_style(self) -> int:
        """Get current material style (0-3)."""
        if self._initialized and self._lib:
            return self._lib.arch_get_material_style()
        return 1  # Default: Clean

    # =========================================================================
    # Shadows & Lighting
    # =========================================================================

    def set_shadows_enabled(self, enabled: bool):
        """Enable or disable shadow mapping."""
        if self._initialized and self._lib:
            self._lib.arch_set_shadows_enabled(1 if enabled else 0)

    def get_shadows_enabled(self) -> bool:
        """Check if shadows are enabled."""
        if self._initialized and self._lib:
            return self._lib.arch_get_shadows_enabled() != 0
        return True

    def set_light_direction(self, x: float, y: float, z: float):
        """Set sun/light direction (normalized)."""
        if self._initialized and self._lib:
            self._lib.arch_set_light_direction(
                ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(z)
            )

    def get_light_direction(self) -> tuple:
        """Get current light direction as (x, y, z)."""
        if self._initialized and self._lib:
            x = ctypes.c_float()
            y = ctypes.c_float()
            z = ctypes.c_float()
            self._lib.arch_get_light_direction(
                ctypes.byref(x), ctypes.byref(y), ctypes.byref(z)
            )
            return (x.value, y.value, z.value)
        return (-0.5, -0.8, -0.3)

    # =========================================================================
    # SSAO (Screen Space Ambient Occlusion)
    # =========================================================================

    def set_ssao_enabled(self, enabled: bool):
        """Enable or disable SSAO."""
        if self._initialized and self._lib:
            self._lib.arch_set_ssao_enabled(1 if enabled else 0)

    def get_ssao_enabled(self) -> bool:
        """Check if SSAO is enabled."""
        if self._initialized and self._lib:
            return self._lib.arch_get_ssao_enabled() != 0
        return True

    def set_ssao_radius(self, radius: float):
        """Set SSAO sample radius."""
        if self._initialized and self._lib:
            self._lib.arch_set_ssao_radius(ctypes.c_float(radius))

    def get_ssao_radius(self) -> float:
        """Get SSAO radius."""
        if self._initialized and self._lib:
            return self._lib.arch_get_ssao_radius()
        return 0.5

    def set_ssao_intensity(self, intensity: float):
        """Set SSAO intensity."""
        if self._initialized and self._lib:
            self._lib.arch_set_ssao_intensity(ctypes.c_float(intensity))

    def get_ssao_intensity(self) -> float:
        """Get SSAO intensity."""
        if self._initialized and self._lib:
            return self._lib.arch_get_ssao_intensity()
        return 1.0

    # =========================================================================
    # Bloom
    # =========================================================================

    def set_bloom_enabled(self, enabled: bool):
        """Enable or disable bloom effect."""
        if self._initialized and self._lib:
            self._lib.arch_set_bloom_enabled(1 if enabled else 0)

    def get_bloom_enabled(self) -> bool:
        """Check if bloom is enabled."""
        if self._initialized and self._lib:
            return self._lib.arch_get_bloom_enabled() != 0
        return True

    def set_bloom_threshold(self, threshold: float):
        """Set bloom brightness threshold."""
        if self._initialized and self._lib:
            self._lib.arch_set_bloom_threshold(ctypes.c_float(threshold))

    def get_bloom_threshold(self) -> float:
        """Get bloom threshold."""
        if self._initialized and self._lib:
            return self._lib.arch_get_bloom_threshold()
        return 1.0

    def set_bloom_intensity(self, intensity: float):
        """Set bloom intensity."""
        if self._initialized and self._lib:
            self._lib.arch_set_bloom_intensity(ctypes.c_float(intensity))

    def get_bloom_intensity(self) -> float:
        """Get bloom intensity."""
        if self._initialized and self._lib:
            return self._lib.arch_get_bloom_intensity()
        return 0.5

    # =========================================================================
    # Tonemapping & Exposure
    # =========================================================================

    def set_exposure(self, exposure: float):
        """Set camera exposure."""
        if self._initialized and self._lib:
            self._lib.arch_set_exposure(ctypes.c_float(exposure))

    def get_exposure(self) -> float:
        """Get current exposure."""
        if self._initialized and self._lib:
            return self._lib.arch_get_exposure()
        return 1.0

    def set_tonemap_mode(self, mode: int):
        """
        Set tonemapping operator.

        Args:
            mode: 0=Reinhard, 1=ACES, 2=Uncharted2
        """
        if self._initialized and self._lib:
            self._lib.arch_set_tonemap_mode(mode)

    def get_tonemap_mode(self) -> int:
        """Get current tonemap mode (0-2)."""
        if self._initialized and self._lib:
            return self._lib.arch_get_tonemap_mode()
        return 1  # Default: ACES

    # =========================================================================
    # Camera View Settings
    # =========================================================================

    def set_camera_fov(self, fov: float):
        """Set camera field of view in degrees (10-120)."""
        if self._initialized and self._lib:
            try:
                self._lib.arch_set_camera_fov(ctypes.c_float(fov))
            except AttributeError:
                pass

    def get_camera_fov(self) -> float:
        """Get current camera FOV in degrees."""
        if self._initialized and self._lib:
            try:
                return self._lib.arch_get_camera_fov()
            except AttributeError:
                pass
        return 45.0

    def set_orthographic(self, enabled: bool):
        """Enable orthographic projection mode."""
        if self._initialized and self._lib:
            try:
                self._lib.arch_set_orthographic(1 if enabled else 0)
            except AttributeError:
                pass

    def get_orthographic(self) -> bool:
        """Check if orthographic mode is enabled."""
        if self._initialized and self._lib:
            try:
                return self._lib.arch_get_orthographic() != 0
            except AttributeError:
                pass
        return False

    # =========================================================================
    # Mouse interaction
    # =========================================================================

    def _route_overlay_mouse(self, event) -> bool:
        """Route mouse event to navigation overlay if present. Returns True if consumed."""
        if self._nav_overlay and hasattr(self._nav_overlay, 'handle_mouse'):
            return self._nav_overlay.handle_mouse(event)
        return False

    def mousePressEvent(self, event):
        """Handle mouse press for camera control."""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Middle mouse = orbit
            self._dragging = True
            self._panning = False
            self._last_mouse_pos = event.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right mouse = pan
            self._dragging = True
            self._panning = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for camera orbit/pan."""
        if self._dragging and self._last_mouse_pos is not None:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()

            if self._panning:
                # Pan: move camera target in screen space
                import math
                # Calculate right and up vectors based on camera orientation
                pan_speed = self._camera_distance * 0.002

                # Right vector (perpendicular to view direction in XZ plane)
                right_x = math.cos(self._camera_yaw)
                right_z = math.sin(self._camera_yaw)

                # Up vector (world Y for now, could be more sophisticated)
                up_y = 1.0

                # Move target
                self._camera_target[0] -= dx * pan_speed * right_x
                self._camera_target[2] -= dx * pan_speed * right_z
                self._camera_target[1] += dy * pan_speed * up_y

                # Update camera target in renderer
                if self._initialized and self._lib:
                    self._lib.arch_set_camera_target(
                        ctypes.c_float(self._camera_target[0]),
                        ctypes.c_float(self._camera_target[1]),
                        ctypes.c_float(self._camera_target[2])
                    )
            else:
                # Orbit: rotate camera around target
                self._camera_yaw -= dx * 0.005
                self._camera_pitch -= dy * 0.005
                self._camera_pitch = max(-1.4, min(1.4, self._camera_pitch))

            self._last_mouse_pos = event.pos()

        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom centered on cursor."""
        import math
        delta = event.angleDelta().y() / 120.0

        if abs(delta) < 0.01:
            super().wheelEvent(event)
            return

        # Get cursor position relative to widget center (normalized -1 to 1)
        cursor_pos = event.position()
        ndc_x = (cursor_pos.x() / self.width()) * 2.0 - 1.0
        ndc_y = 1.0 - (cursor_pos.y() / self.height()) * 2.0  # Flip Y

        # Calculate zoom
        zoom_factor = 0.15
        old_distance = self._camera_distance
        new_distance = old_distance * (1.0 - delta * zoom_factor)
        new_distance = max(5.0, min(500.0, new_distance))

        # How much the distance changed
        distance_delta = old_distance - new_distance

        # Calculate camera vectors
        cos_yaw = math.cos(self._camera_yaw)
        sin_yaw = math.sin(self._camera_yaw)
        cos_pitch = math.cos(self._camera_pitch)
        sin_pitch = math.sin(self._camera_pitch)

        # Camera right vector (in XZ plane)
        right_x = cos_yaw
        right_z = sin_yaw

        # Camera up vector (simplified - just Y for architectural views)
        up_y = 1.0

        # Move target toward cursor position proportional to zoom amount
        # The FOV determines how much screen space maps to world space
        fov_factor = math.tan(math.radians(45.0 / 2.0))  # Approximate FOV
        world_scale = distance_delta * fov_factor

        # Shift target based on cursor offset from center
        self._camera_target[0] += ndc_x * world_scale * right_x
        self._camera_target[2] += ndc_x * world_scale * right_z
        self._camera_target[1] += ndc_y * world_scale * cos_pitch

        # Apply the zoom
        self._camera_distance = new_distance

        # Update camera target in renderer
        if self._initialized and self._lib:
            self._lib.arch_set_camera_target(
                ctypes.c_float(self._camera_target[0]),
                ctypes.c_float(self._camera_target[1]),
                ctypes.c_float(self._camera_target[2])
            )

        super().wheelEvent(event)

    def paintEngine(self):
        """Return None to indicate we're handling our own painting."""
        return None
