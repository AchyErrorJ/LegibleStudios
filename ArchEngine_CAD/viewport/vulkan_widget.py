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

# Diagnostics
try:
    from core.diagnostics import get_diagnostics, diag_log
    HAS_DIAGNOSTICS = True
except ImportError:
    HAS_DIAGNOSTICS = False
    def get_diagnostics(): return None
    def diag_log(msg): pass

# Selection manager for Python-side picking
try:
    from core.selection import get_selection_manager, SelectionManager
    HAS_SELECTION = True
except ImportError:
    HAS_SELECTION = False
    def get_selection_manager(): return None

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QPainter, QColor

# Find the DLL
def _find_dll() -> Optional[Path]:
    """Search for ArchEngineLib.dll - prioritize local/updated DLL first."""
    cad_root = Path(__file__).parent.parent  # ArchEngine_CAD folder
    suite_root = cad_root.parent  # ArchEngine_Suite_UE5 folder

    search_paths = [
        # 1. Direct DLL override (for testing new builds)
        cad_root / "dll",  # ArchEngine_CAD/dll/
        cad_root / "bin",  # ArchEngine_CAD/bin/

        # 2. Local kernel directory (same worktree - most common)
        suite_root / "ArchEngine_kernel" / "build" / "Release",
        suite_root / "ArchEngine_kernel" / "build" / "Debug",

        # 3. Kernel branch worktree (for latest kernel features)
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_Suite_Kernel\ArchEngine_kernel\build\Debug"),

        # 4. UE5 worktree paths (explicit fallback)
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Release"),
        Path(r"X:\ARCH\Software\ArchEngine_suite_ue5\ArchEngine_kernel\build\Debug"),
    ]

    for path in search_paths:
        dll_path = path / "ArchEngineLib.dll"
        if dll_path.exists():
            print(f"[DLL] Found: {dll_path}")
            return dll_path

    print("[DLL] ArchEngineLib.dll not found in any search path")
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
    camera_distance_changed = pyqtSignal(float)  # distance from target
    lod_level_changed = pyqtSignal(int)  # LOD level 1-5 (shift+scroll)
    gravity_changed = pyqtSignal(float, float, float)  # design, client, build
    lod_changed = pyqtSignal(int, float)  # level, transition
    section_changed = pyqtSignal(bool, int, float, bool)  # enabled, axis, height, flipped
    element_selected = pyqtSignal(int)  # element index (-1 for deselect)
    element_hovered = pyqtSignal(str, object)  # element_type, element_id (None for no hover)
    rooms_loaded = pyqtSignal(list)  # list of room data dicts

    def __init__(self, parent=None):
        super().__init__(parent)

        self._lib: Optional[ctypes.CDLL] = None
        self._initialized = False
        self._render_timer: Optional[QTimer] = None

        # Camera state for mouse interaction (distances in FEET - C++ converts mm to ft)
        self._camera_yaw = 0.5
        self._camera_pitch = 0.4
        self._camera_distance = 60.0  # 60 feet from target
        self._camera_target = [26.0, 10.0, 20.0]  # Building center approx (feet)
        self._free_look_mode = False  # Toggle with Spacebar
        self._free_look_cam_pos = None  # Stored camera position in free look mode
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

        # Navigation overlay (optional)
        self._nav_overlay = None

        # Widget setup
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, True)
        self.setMouseTracking(True)  # Enable hover detection without button press
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

            self._lib.arch_set_camera_pose.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_float,
                                                       ctypes.c_float, ctypes.c_float, ctypes.c_float]
            self._lib.arch_set_camera_pose.restype = None

            self._lib.arch_reset_camera.argtypes = []
            self._lib.arch_reset_camera.restype = None

            self._lib.arch_get_camera_state.argtypes = [
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float),
                ctypes.POINTER(ctypes.c_float)
            ]
            self._lib.arch_get_camera_state.restype = None

            self._lib.arch_set_viz_mode.argtypes = [ctypes.c_int]
            self._lib.arch_set_viz_mode.restype = None

            self._lib.arch_get_error.argtypes = []
            self._lib.arch_get_error.restype = ctypes.c_char_p

            # Selection API (optional - may not be in all DLL versions)
            try:
                self._lib.arch_select_element.argtypes = [ctypes.c_int]
                self._lib.arch_select_element.restype = None

                self._lib.arch_get_element_count.argtypes = []
                self._lib.arch_get_element_count.restype = ctypes.c_int

                self._lib.arch_get_selected_element.argtypes = []
                self._lib.arch_get_selected_element.restype = ctypes.c_int

                self._lib.arch_pick_element.argtypes = [ctypes.c_int, ctypes.c_int]
                self._lib.arch_pick_element.restype = ctypes.c_int
            except AttributeError:
                print("[VulkanWidget] Selection API not available in this DLL")

            print(f"[VulkanWidget] Loaded {dll_path}")

            # Section clipping API (optional)
            try:
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
            except AttributeError:
                print("[VulkanWidget] Section clipping API not available")

            # Material style API (optional)
            try:
                self._lib.arch_set_material_style.argtypes = [ctypes.c_int]
                self._lib.arch_set_material_style.restype = None

                self._lib.arch_get_material_style.argtypes = []
                self._lib.arch_get_material_style.restype = ctypes.c_int
            except AttributeError:
                print("[VulkanWidget] Material style API not available")

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

                # Room export API
                self._lib.arch_get_room_count.argtypes = []
                self._lib.arch_get_room_count.restype = ctypes.c_int

                # TODO: Define ArchRoomData ctypes Structure to enable these APIs
                # self._lib.arch_get_room_data.argtypes = [ctypes.c_int, ctypes.POINTER(ArchRoomData)]
                # self._lib.arch_get_room_data.restype = ctypes.c_int
                # self._lib.arch_get_all_rooms.argtypes = [ctypes.POINTER(ArchRoomData), ctypes.c_int]
                # self._lib.arch_get_all_rooms.restype = ctypes.c_int

                # Material settings API
                self._lib.arch_set_uv_scale.argtypes = [ctypes.c_float, ctypes.c_float]
                self._lib.arch_set_uv_scale.restype = None

                self._lib.arch_get_uv_scale.argtypes = [
                    ctypes.POINTER(ctypes.c_float),
                    ctypes.POINTER(ctypes.c_float)
                ]
                self._lib.arch_get_uv_scale.restype = None

                self._lib.arch_set_roughness_multiplier.argtypes = [ctypes.c_float]
                self._lib.arch_set_roughness_multiplier.restype = None

                self._lib.arch_get_roughness_multiplier.argtypes = []
                self._lib.arch_get_roughness_multiplier.restype = ctypes.c_float

                self._lib.arch_set_metallic_multiplier.argtypes = [ctypes.c_float]
                self._lib.arch_set_metallic_multiplier.restype = None

                self._lib.arch_get_metallic_multiplier.argtypes = []
                self._lib.arch_get_metallic_multiplier.restype = ctypes.c_float

                self._lib.arch_set_ao_strength.argtypes = [ctypes.c_float]
                self._lib.arch_set_ao_strength.restype = None

                self._lib.arch_get_ao_strength.argtypes = []
                self._lib.arch_get_ao_strength.restype = ctypes.c_float

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

            # Change to DLL directory so shaders can be found
            dll_dir = Path(__file__).parent.parent / "dll"
            original_cwd = os.getcwd()
            if dll_dir.exists():
                os.chdir(dll_dir)
                print(f"[VulkanWidget] Changed to DLL dir: {dll_dir}")

            result = self._lib.arch_init(ctypes.c_void_p(hwnd), width, height)

            # Restore original working directory
            os.chdir(original_cwd)
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

        # Log first few frames after restart for debugging
        if not hasattr(self, '_frames_since_load'):
            self._frames_since_load = 0
        self._frames_since_load += 1
        if self._frames_since_load <= 3:
            print(f"[VulkanWidget] Render frame {self._frames_since_load} after load", flush=True)

        try:
            self._rendering = True

            # Start frame timing
            diag = get_diagnostics()
            if diag:
                diag.frame_start()

            # Update camera
            # Only call arch_set_camera if NOT in free look mode (free look uses arch_set_camera_pose directly)
            if not self._free_look_mode:
                self._lib.arch_set_camera(
                    ctypes.c_float(self._camera_yaw),
                    ctypes.c_float(self._camera_pitch),
                    ctypes.c_float(self._camera_distance)
                )

            # Render
            result = self._lib.arch_render_frame()

            # End frame timing
            if diag:
                frame_time = diag.frame_end()

            if result != 0:
                # Render failed - stop the render loop
                print("[VulkanWidget] Render failed, stopping render loop")
                if self._render_timer:
                    self._render_timer.stop()
                self._initialized = False
                return

            # Log occasionally to confirm render loop is running
            if self._render_count % 300 == 0:  # Every ~10 seconds at 30fps
                fps = diag.get_fps() if diag else 0
                print(f"[VulkanWidget] Rendered {self._render_count} frames, FPS: {fps:.1f}")
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
        self._frames_since_load = 0  # Reset frame counter for debug

        # Stop render timer and acquire lock to ensure no rendering during geometry update
        if self._render_timer:
            self._render_timer.stop()

        rooms_to_emit = None
        load_count = 0
        success = False

        try:
            with self._api_lock:
                # Debug: Check if terrain_mesh is in data
                if 'terrain_mesh' in data:
                    tm = data['terrain_mesh']
                    print(f"[VulkanWidget] terrain_mesh found in JSON: {list(tm.keys())}")
                    print(f"[VulkanWidget] terrain_mesh has vertices: {'vertices' in tm}")
                    print(f"[VulkanWidget] terrain_mesh vertex count: {tm.get('vertex_count', 'N/A')}")
                else:
                    print(f"[VulkanWidget] ERROR: No terrain_mesh in JSON!")
                    print(f"[VulkanWidget] Available keys: {list(data.keys())}")

                json_str = json.dumps(data).encode('utf-8')
                result = self._lib.arch_load_json(json_str)

                if result == 0:
                    load_count = self._lib.arch_get_element_count()
                    print(f"[VulkanWidget] Loaded {load_count} elements")

                    # Check if terrain was loaded
                    terrain_count = self._lib.arch_has_terrain()
                    print(f"[VulkanWidget] Terrain loaded: {terrain_count}")

                    # Force a sync render to process new geometry before resuming render loop
                    # This helps prevent crashes from stale GPU state
                    self._lib.arch_render_frame()

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
                print("[VulkanWidget] Scheduling render timer restart in 100ms", flush=True)
                QTimer.singleShot(100, self._restart_render_timer)

        # Emit signals AFTER releasing the lock to prevent deadlock/re-entrancy
        if success:
            print("[VulkanWidget] Emitting load_complete signal", flush=True)
            self.load_complete.emit(load_count)
            if rooms_to_emit:
                print("[VulkanWidget] Emitting rooms_loaded signal", flush=True)
                self.rooms_loaded.emit(rooms_to_emit)
            print("[VulkanWidget] load_json complete, returning True", flush=True)
            return True
        return False

    def _restart_render_timer(self):
        """Restart the render timer after load completes."""
        print("[VulkanWidget] Restarting render timer", flush=True)
        if self._initialized and self._render_timer:
            self._render_timer.start(33)
            print("[VulkanWidget] Render timer started", flush=True)

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
        """Reset camera to fit the building - uses C++ calculated values."""
        if self._initialized and self._lib:
            # Let C++ calculate proper camera position from building bounds
            self._lib.arch_reset_camera()

            # Get actual values calculated by C++ from building bounds
            try:
                tx, ty, tz, dist = ctypes.c_float(), ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
                self._lib.arch_get_camera_state(
                    ctypes.byref(tx), ctypes.byref(ty), ctypes.byref(tz), ctypes.byref(dist)
                )
                self._camera_target = [tx.value, ty.value, tz.value]
                self._camera_distance = dist.value
                print(f"[Viewport] Camera reset: target=[{tx.value:.0f}, {ty.value:.0f}, {tz.value:.0f}], distance={dist.value:.0f}mm")
            except Exception as e:
                print(f"[Viewport] Could not get camera state: {e}")
                self._camera_distance = 15000.0
                self._camera_target = [8000.0, 3000.0, 6000.0]

            self._camera_yaw = 0.5
            self._camera_pitch = 0.4
            self._free_look_cam_pos = None  # Clear free look camera position
            self.update()  # Trigger repaint

    def set_visualization_mode(self, mode: int):
        """
        Set visualization mode.

        Args:
            mode: 0=Structural, 1=Thermal, 2=Lighting, 3=Acoustic, 4=Material, 5=Wireframe
        """
        if self._initialized and self._lib:
            self._lib.arch_set_viz_mode(mode)

    def set_document(self, document):
        """Set document reference for Python-side picking."""
        self._document = document
        if HAS_SELECTION:
            self._selection_manager = get_selection_manager()
            self._selection_manager.set_document(document)
            self._update_selection_camera()

    def _update_selection_camera(self):
        """Update selection manager with current camera parameters."""
        if self._selection_manager:
            self._selection_manager.set_camera(
                self._camera_yaw * 57.2958,  # Convert to degrees
                self._camera_pitch * 57.2958,
                self._camera_distance  # Already in mm
            )
            self._selection_manager.set_viewport_size(self.width(), self.height())

    def select_element(self, index: int):
        """Select an element by index (-1 to clear)."""
        if self._initialized and self._lib:
            self._lib.arch_select_element(index)
            if index >= 0:
                self.element_selected.emit(index)

    def get_selected_element(self) -> int:
        """Get currently selected element index (-1 if none)."""
        if self._initialized and self._lib:
            return self._lib.arch_get_selected_element()
        return -1

    def get_rooms(self) -> list:
        """Get room data from renderer. Returns empty list if not available."""
        # Room data APIs are not yet fully implemented
        # TODO: Implement when ArchRoomData ctypes structure is defined
        return []

    def pick_element(self, screen_x: int, screen_y: int) -> int:
        """
        Pick element at screen coordinates.

        First tries DLL-based picking, then falls back to Python-side ray casting.

        Args:
            screen_x: X coordinate in widget pixels
            screen_y: Y coordinate in widget pixels

        Returns:
            Element index at that position, or -1 if no hit
        """
        # Try DLL picking first
        result = -1
        if self._initialized and self._lib:
            try:
                result = self._lib.arch_pick_element(screen_x, screen_y)
            except Exception:
                pass  # DLL function may not exist

        # Fall back to Python picking if DLL returns -1 and we have selection manager
        if result < 0 and self._selection_manager and self._document:
            self._update_selection_camera()
            hit = self._selection_manager.pick_and_select(screen_x, screen_y, add=False)
            if hit:
                # Convert element type and id to index for compatibility
                result = self._get_element_index(hit.element_type, hit.element_id)
                self._last_pick_pos = (screen_x, screen_y)

        return result

    def pick_all_at(self, screen_x: int, screen_y: int) -> list:
        """
        Pick all elements at screen coordinates (for Tab cycling).

        Returns list of (element_type, element_id, distance) tuples.
        """
        if self._selection_manager and self._document:
            self._update_selection_camera()
            hits = self._selection_manager.pick_at_screen(screen_x, screen_y)
            return [(h.element_type, h.element_id, h.distance) for h in hits]
        return []

    def cycle_selection(self, forward: bool = True) -> bool:
        """
        Cycle through overlapping elements at last pick position.

        Returns True if cycling succeeded, False if no elements to cycle.
        """
        if self._selection_manager:
            hit = self._selection_manager.cycle_selection(forward)
            if hit:
                index = self._get_element_index(hit.element_type, hit.element_id)
                if index >= 0:
                    self.select_element(index)
                current, total = self._selection_manager.get_cycle_info()
                print(f"[Viewport] Selection cycle: {current}/{total} - {hit.element_type} {hit.element_id}")
                return True
        return False

    def _get_element_index(self, element_type: str, element_id) -> int:
        """Convert element type/id to a linear index for the renderer."""
        if not self._document:
            return -1

        # Build index mapping - order matches renderer's element ordering
        offset = 0

        # Walls first
        if element_type == 'wall':
            return element_id if isinstance(element_id, int) else offset
        offset += len(self._document.walls)

        # Then rooms
        if element_type == 'room':
            room_ids = list(self._document._rooms.keys())
            if element_id in room_ids:
                return offset + room_ids.index(element_id)
            return offset
        offset += len(self._document._rooms)

        # Then doors
        if element_type == 'door':
            return offset + (element_id if isinstance(element_id, int) else 0)
        offset += len(self._document.doors)

        # Then windows
        if element_type == 'window':
            return offset + (element_id if isinstance(element_id, int) else 0)

        return -1

    def get_selection_cycle_info(self) -> tuple:
        """Get current selection cycle info (current_index, total_count)."""
        if self._selection_manager:
            return self._selection_manager.get_cycle_info()
        return (0, 0)

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
    # Material Settings (UV, roughness, metallic, AO)
    # =========================================================================

    def set_uv_scale(self, scale_u: float, scale_v: float = None):
        """
        Set UV/texture tiling scale.

        Args:
            scale_u: Horizontal tiling (1.0 = original, 2.0 = 2x repetition)
            scale_v: Vertical tiling (defaults to scale_u if not specified)
        """
        if scale_v is None:
            scale_v = scale_u
        if self._initialized and self._lib:
            self._lib.arch_set_uv_scale(ctypes.c_float(scale_u), ctypes.c_float(scale_v))

    def get_uv_scale(self) -> tuple:
        """Get current UV scale as (u, v)."""
        if self._initialized and self._lib:
            u = ctypes.c_float()
            v = ctypes.c_float()
            self._lib.arch_get_uv_scale(ctypes.byref(u), ctypes.byref(v))
            return (u.value, v.value)
        return (1.0, 1.0)

    def set_roughness_multiplier(self, multiplier: float):
        """
        Set roughness multiplier.

        Args:
            multiplier: 1.0 = default, < 1.0 = smoother/shinier, > 1.0 = rougher/matter
        """
        if self._initialized and self._lib:
            self._lib.arch_set_roughness_multiplier(ctypes.c_float(multiplier))

    def get_roughness_multiplier(self) -> float:
        """Get current roughness multiplier."""
        if self._initialized and self._lib:
            return self._lib.arch_get_roughness_multiplier()
        return 1.0

    def set_metallic_multiplier(self, multiplier: float):
        """
        Set metallic multiplier.

        Args:
            multiplier: 1.0 = default, < 1.0 = less metallic, > 1.0 = more metallic
        """
        if self._initialized and self._lib:
            self._lib.arch_set_metallic_multiplier(ctypes.c_float(multiplier))

    def get_metallic_multiplier(self) -> float:
        """Get current metallic multiplier."""
        if self._initialized and self._lib:
            return self._lib.arch_get_metallic_multiplier()
        return 1.0

    def set_ao_strength(self, strength: float):
        """
        Set ambient occlusion strength.

        Args:
            strength: 0.0 = no AO, 1.0 = full AO
        """
        if self._initialized and self._lib:
            self._lib.arch_set_ao_strength(ctypes.c_float(strength))

    def get_ao_strength(self) -> float:
        """Get current AO strength."""
        if self._initialized and self._lib:
            return self._lib.arch_get_ao_strength()
        return 1.0

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

    def _route_overlay_mouse(self, event):
        """Route mouse event to overlay if active. Returns True if handled."""
        # Stub - no overlay handling for now
        return False

    def mousePressEvent(self, event):
        """Handle mouse press for camera control, section dragging, or element selection."""
        # Ensure widget has focus for keyboard shortcuts
        self.setFocus()
        if self._route_overlay_mouse(event):
            return
        if event.button() == Qt.MouseButton.LeftButton and self._section_mode:
            # Left mouse in section mode = drag section plane
            self._section_dragging = True
            self._last_mouse_pos = event.pos()
            # Enable clipping if not already enabled
            if not self.get_clipping_enabled():
                self.set_clipping_enabled(True)
                self.set_section_floor_plan(4.0)  # Default to floor plan
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self._section_mode:
            # Left click = pick/select element
            pos = event.pos()
            element_idx = self.pick_element(pos.x(), pos.y())
            if element_idx >= 0:
                self.select_element(element_idx)
                # Show info about overlapping elements
                current, total = self.get_selection_cycle_info()
                if total > 1:
                    print(f"[Viewport] Selected element {element_idx} ({current}/{total} overlapping - press Tab to cycle)")
                else:
                    print(f"[Viewport] Selected element {element_idx}")
            else:
                # Click on empty space = deselect
                self.select_element(-1)
                self.element_selected.emit(-1)
                # Clear selection manager state
                if self._selection_manager:
                    self._selection_manager.clear_selection()
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            # Middle mouse = pan
            self._dragging = True
            self._panning = True
            self._last_mouse_pos = event.pos()
            event.accept()
            return
        elif event.button() == Qt.MouseButton.RightButton:
            # Right mouse = orbit
            self._dragging = True
            self._panning = False
            self._last_mouse_pos = event.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if self._route_overlay_mouse(event):
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._section_dragging = False
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for camera orbit/pan or section dragging."""
        if self._route_overlay_mouse(event):
            return

        # Section plane dragging
        if self._section_dragging and self._last_mouse_pos is not None:
            dy = event.pos().y() - self._last_mouse_pos.y()
            # Vertical mouse movement adjusts clip height
            # Negative dy (move up) = increase height
            current_height = self.get_clip_height()
            new_height = current_height - dy * 0.05  # Scale factor for sensitivity
            new_height = max(-10.0, min(50.0, new_height))  # Clamp to reasonable range
            self.set_clip_height(new_height)
            self._last_mouse_pos = event.pos()
            # Emit signal for panel sync
            self.section_changed.emit(
                self.get_clipping_enabled(),
                self.get_clip_axis(),
                new_height,
                self.get_clip_flipped()
            )
            event.accept()
            return

        if self._dragging and self._last_mouse_pos is not None:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()

            if self._panning:
                # Pan: move camera in screen space
                import math
                # Pan speed in feet - scale with distance for consistent feel
                base_pan_speed = 0.1  # 0.1 feet per pixel at base distance
                pan_speed = base_pan_speed * (self._camera_distance / 60.0)  # Scale with zoom

                # Right vector (perpendicular to view direction in XZ plane)
                right_x = math.cos(self._camera_yaw)
                right_z = math.sin(self._camera_yaw)

                # Up vector (world Y for now, could be more sophisticated)
                up_y = 1.0

                if self._free_look_mode and self._free_look_cam_pos is not None:
                    # Free look: move BOTH camera position and target together
                    move_x = -dx * pan_speed * right_x
                    move_z = -dx * pan_speed * right_z
                    move_y = dy * pan_speed * up_y

                    # Move camera position
                    self._free_look_cam_pos[0] += move_x
                    self._free_look_cam_pos[1] += move_y
                    self._free_look_cam_pos[2] += move_z

                    # Move target by same amount
                    self._camera_target[0] += move_x
                    self._camera_target[1] += move_y
                    self._camera_target[2] += move_z

                    # Update camera pose in renderer
                    if self._initialized and self._lib:
                        self._lib.arch_set_camera_pose(
                            ctypes.c_float(self._free_look_cam_pos[0]),
                            ctypes.c_float(self._free_look_cam_pos[1]),
                            ctypes.c_float(self._free_look_cam_pos[2]),
                            ctypes.c_float(self._camera_target[0]),
                            ctypes.c_float(self._camera_target[1]),
                            ctypes.c_float(self._camera_target[2])
                        )
                else:
                    # Orbit mode: only move target
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
                # Camera rotation
                if self._free_look_mode:
                    # Free look: first time entering, calculate camera position
                    import math
                    if self._free_look_cam_pos is None:
                        cos_yaw = math.cos(self._camera_yaw)
                        sin_yaw = math.sin(self._camera_yaw)
                        cos_pitch = math.cos(self._camera_pitch)
                        sin_pitch = math.sin(self._camera_pitch)
                        # Camera position from current orbit state
                        cam_x = self._camera_target[0] - self._camera_distance * sin_yaw * cos_pitch
                        cam_y = self._camera_target[1] - self._camera_distance * sin_pitch
                        cam_z = self._camera_target[2] - self._camera_distance * cos_yaw * cos_pitch
                        self._free_look_cam_pos = [cam_x, cam_y, cam_z]

                    # Update viewing angles (camera stays fixed)
                    self._camera_yaw -= dx * 0.005  # Faster for free look
                    self._camera_pitch -= dy * 0.005
                    self._camera_pitch = max(-1.57, min(1.57, self._camera_pitch))

                    # Calculate new target from fixed camera position
                    cam_x, cam_y, cam_z = self._free_look_cam_pos
                    cos_yaw_new = math.cos(self._camera_yaw)
                    sin_yaw_new = math.sin(self._camera_yaw)
                    cos_pitch_new = math.cos(self._camera_pitch)
                    sin_pitch_new = math.sin(self._camera_pitch)

                    # target = camera + distance * direction
                    self._camera_target[0] = cam_x + self._camera_distance * sin_yaw_new * cos_pitch_new
                    self._camera_target[1] = cam_y + self._camera_distance * sin_pitch_new
                    self._camera_target[2] = cam_z + self._camera_distance * cos_yaw_new * cos_pitch_new

                    # Update camera using direct pose API
                    if self._initialized and self._lib:
                        self._lib.arch_set_camera_pose(
                            ctypes.c_float(cam_x),
                            ctypes.c_float(cam_y),
                            ctypes.c_float(cam_z),
                            ctypes.c_float(self._camera_target[0]),
                            ctypes.c_float(self._camera_target[1]),
                            ctypes.c_float(self._camera_target[2])
                        )
                else:
                    # Orbit: rotate camera around target (slower, smoother)
                    self._camera_yaw -= dx * 0.002
                    self._camera_pitch -= dy * 0.002
                    self._camera_pitch = max(-1.4, min(1.4, self._camera_pitch))
                    # Clear free look camera position when switching back to orbit
                    self._free_look_cam_pos = None

            self._last_mouse_pos = event.pos()
            event.accept()
            return

        # Hover detection when not dragging
        if not self._dragging and self._selection_manager and self._document:
            try:
                self._update_hover(event.pos().x(), event.pos().y())
            except Exception as e:
                pass  # Ignore hover errors to prevent crashes

        super().mouseMoveEvent(event)

    def _update_hover(self, x: int, y: int):
        """Update hover state based on mouse position."""
        self._update_selection_camera()
        hits = self._selection_manager.pick_at_screen(x, y)

        if hits:
            # Get top hit (highest priority)
            top_hit = hits[0]
            new_hover = (top_hit.element_type, top_hit.element_id)

            if new_hover != self._hovered_element:
                self._hovered_element = new_hover
                self.element_hovered.emit(top_hit.element_type, top_hit.element_id)
                # Change cursor to indicate selectable
                self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            if self._hovered_element is not None:
                self._hovered_element = None
                self.element_hovered.emit('', None)
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        """Clear hover when mouse leaves widget."""
        if self._hovered_element is not None:
            self._hovered_element = None
            self.element_hovered.emit('', None)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def enterEvent(self, event):
        """Grab focus when mouse enters viewport for keyboard shortcuts."""
        self.setFocus()
        super().enterEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel for zoom (orbit mode) or movement (free look mode)."""
        import math
        delta = event.angleDelta().y() / 120.0

        if abs(delta) < 0.01:
            super().wheelEvent(event)
            return

        if self._free_look_mode:
            # Free look mode: scroll moves camera forward/backward
            # Calculate forward direction from yaw and pitch
            cos_yaw = math.cos(self._camera_yaw)
            sin_yaw = math.sin(self._camera_yaw)
            cos_pitch = math.cos(self._camera_pitch)
            sin_pitch = math.sin(self._camera_pitch)

            # Forward vector (direction camera is looking)
            forward_x = sin_yaw * cos_pitch
            forward_y = sin_pitch
            forward_z = cos_yaw * cos_pitch

            # Movement speed - scroll up (positive delta) = forward, scroll down = backward
            # Camera system uses FEET - scale speed with distance
            # Far away: move faster, close up: move slower
            base_speed = 0.05  # 5% of distance per scroll tick
            move_speed = max(0.5, self._camera_distance * base_speed)  # Min 0.5 feet
            move_delta = delta * move_speed

            # Update camera position
            if self._free_look_cam_pos is None:
                # Initialize if not set
                self._free_look_cam_pos = [
                    self._camera_target[0] - self._camera_distance * forward_x,
                    self._camera_target[1] - self._camera_distance * forward_y,
                    self._camera_target[2] - self._camera_distance * forward_z
                ]

            self._free_look_cam_pos[0] += move_delta * forward_x
            self._free_look_cam_pos[1] += move_delta * forward_y
            self._free_look_cam_pos[2] += move_delta * forward_z

            # Update target to maintain same distance from camera
            self._camera_target[0] = self._free_look_cam_pos[0] + self._camera_distance * forward_x
            self._camera_target[1] = self._free_look_cam_pos[1] + self._camera_distance * forward_y
            self._camera_target[2] = self._free_look_cam_pos[2] + self._camera_distance * forward_z

            # Update camera in renderer
            if self._initialized and self._lib:
                self._lib.arch_set_camera_pose(
                    ctypes.c_float(self._free_look_cam_pos[0]),
                    ctypes.c_float(self._free_look_cam_pos[1]),
                    ctypes.c_float(self._free_look_cam_pos[2]),
                    ctypes.c_float(self._camera_target[0]),
                    ctypes.c_float(self._camera_target[1]),
                    ctypes.c_float(self._camera_target[2])
                )
        else:
            # Orbit mode: zoom centered on cursor
            # Get cursor position relative to widget center (normalized -1 to 1)
            cursor_pos = event.position()
            ndc_x = (cursor_pos.x() / self.width()) * 2.0 - 1.0
            ndc_y = 1.0 - (cursor_pos.y() / self.height()) * 2.0  # Flip Y

            # Calculate zoom - faster zoom, closer minimum
            zoom_factor = 0.15  # Faster zoom for quicker navigation
            old_distance = self._camera_distance
            new_distance = old_distance * (1.0 - delta * zoom_factor)
            # Allow getting very close (1 foot) to 300 feet out (units are FEET)
            new_distance = max(1.0, min(300.0, new_distance))

            # Debug: print when hitting limits
            if new_distance <= 1.0 or new_distance >= 300.0:
                print(f"[Viewport] Zoom limit hit: distance={new_distance:.1f}ft")

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

    def keyPressEvent(self, event):
        """Handle key press for section mode toggle, Tab cycling, and other shortcuts."""
        from PyQt6.QtCore import Qt

        # Tab = cycle through overlapping elements
        if event.key() == Qt.Key.Key_Tab:
            forward = not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if self.cycle_selection(forward):
                event.accept()
                return

        if event.key() == Qt.Key.Key_S and not event.modifiers():
            # 'S' key toggles section mode
            self._section_mode = not self._section_mode
            if self._section_mode:
                print("[Viewport] Section mode ON - drag to adjust section plane")
                # Change cursor to indicate section mode
                self.setCursor(Qt.CursorShape.SplitVCursor)
            else:
                print("[Viewport] Section mode OFF")
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Escape:
            # Escape exits section mode
            if self._section_mode:
                self._section_mode = False
                self._section_dragging = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                print("[Viewport] Section mode OFF")
                event.accept()
                return
        elif event.key() == Qt.Key.Key_C and self._section_mode:
            # 'C' cycles axis when in section mode
            current_axis = self.get_clip_axis()
            new_axis = (current_axis + 1) % 3
            self.set_clip_axis(new_axis)
            axis_names = ["X (Left/Right)", "Y (Up/Down)", "Z (Front/Back)"]
            print(f"[Viewport] Section axis: {axis_names[new_axis]}")
            self.section_changed.emit(
                self.get_clipping_enabled(),
                new_axis,
                self.get_clip_height(),
                self.get_clip_flipped()
            )
            event.accept()
            return
        elif event.key() == Qt.Key.Key_F and self._section_mode:
            # 'F' flips section direction
            flipped = not self.get_clip_flipped()
            self.set_clip_flipped(flipped)
            print(f"[Viewport] Section flipped: {flipped}")
            self.section_changed.emit(
                self.get_clipping_enabled(),
                self.get_clip_axis(),
                self.get_clip_height(),
                flipped
            )
            event.accept()
            return
        elif event.key() == Qt.Key.Key_H:
            # 'H' key resets camera to home/default view (ignore modifiers for reliability)
            self._free_look_mode = False  # Exit free look mode
            self._free_look_cam_pos = None  # Clear free look state
            self.reset_camera()
            print("[Viewport] Camera reset to home view (H key)")
            event.accept()
            return
        elif event.key() == Qt.Key.Key_Space and not event.modifiers():
            # Spacebar toggles free look mode - always reset to home view first
            self._free_look_mode = not self._free_look_mode
            mode = "FREE LOOK" if self._free_look_mode else "ORBIT"

            # Reset camera to home position when switching modes
            self.reset_camera()
            self._free_look_cam_pos = None  # Clear free look state

            # If entering free look mode, initialize camera position from home
            if self._free_look_mode:
                import math
                cos_yaw = math.cos(self._camera_yaw)
                sin_yaw = math.sin(self._camera_yaw)
                cos_pitch = math.cos(self._camera_pitch)
                sin_pitch = math.sin(self._camera_pitch)
                cam_x = self._camera_target[0] - self._camera_distance * sin_yaw * cos_pitch
                cam_y = self._camera_target[1] - self._camera_distance * sin_pitch
                cam_z = self._camera_target[2] - self._camera_distance * cos_yaw * cos_pitch
                self._free_look_cam_pos = [cam_x, cam_y, cam_z]

            print(f"[Viewport] Camera mode: {mode} (reset to home)")
            self.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def set_nav_gravity(self, design: float, client: float, build: float):
        """Update the overlay gravity weights."""
        if self._nav_overlay:
            self._nav_overlay.set_gravity(design, client, build)

    def set_nav_lod(self, level: int):
        """Update the overlay LOD display."""
        if self._nav_overlay:
            self._nav_overlay.set_lod_level(level)

    def paintEngine(self):
        """Return None to indicate we're handling our own painting."""
        return None
