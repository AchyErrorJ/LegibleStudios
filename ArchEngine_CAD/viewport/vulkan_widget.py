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

# Find the DLL
def _find_dll() -> Optional[Path]:
    """Search for ArchEngineLib.dll - prioritize kernel worktree."""
    search_paths = [
        # Primary: Kernel worktree (dedicated engine development)
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Debug"),
        # Relative paths from CAD app
        Path(__file__).parent.parent.parent / "ArchEngine_kernel" / "build" / "Release",
        Path(__file__).parent.parent.parent / "ArchEngine_kernel" / "build" / "Debug",
        # UE5 worktree paths
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Debug"),
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
        self._last_mouse_pos = None
        self._dragging = False
        self._rendering = False  # Prevent concurrent renders
        self._loading = False    # Prevent concurrent loads
        self._api_lock = threading.Lock()  # Prevent load during render

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

            print(f"[VulkanWidget] Loaded {dll_path}")

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

            # Start render loop
            self._render_timer = QTimer(self)
            self._render_timer.timeout.connect(self._render_frame)
            self._render_timer.start(33)  # ~30 FPS

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

        if self._initialized and self._lib is not None:
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
            self._lib.arch_shutdown()
            self._initialized = False
            print("[VulkanWidget] Renderer shutdown")

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

                    self.load_complete.emit(count)
                    return True
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

    # =========================================================================
    # Mouse interaction
    # =========================================================================

    def mousePressEvent(self, event):
        """Handle mouse press for camera control."""
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._dragging = True
            self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for camera orbit."""
        if self._dragging and self._last_mouse_pos is not None:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()

            self._camera_yaw -= dx * 0.005
            self._camera_pitch -= dy * 0.005
            self._camera_pitch = max(-1.4, min(1.4, self._camera_pitch))

            self._last_mouse_pos = event.pos()

        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom."""
        delta = event.angleDelta().y() / 120.0
        self._camera_distance -= delta * self._camera_distance * 0.1
        self._camera_distance = max(10.0, min(500.0, self._camera_distance))
        super().wheelEvent(event)

    def paintEngine(self):
        """Return None to indicate we're handling our own painting."""
        return None
