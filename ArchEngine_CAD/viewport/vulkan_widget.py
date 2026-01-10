"""
VulkanViewportWidget - Qt widget embedding the Vulkan renderer.

Uses ctypes to call into ArchEngineLib.dll for real-time 3D visualization
of the building model directly in the CAD application.
"""

import ctypes
import math
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QSizeF, QPointF, QRectF, QEvent, QCoreApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont, QMouseEvent, QWheelEvent

class TetraNavOverlay(QWidget):
    """Floating tetrahedron-style navigation control for gravity + LOD + mode."""

    gravity_changed = pyqtSignal(float, float, float)  # design, client, build
    lod_changed = pyqtSignal(int, float)  # level, transition
    mode_changed = pyqtSignal(str)  # mode name: vision, budget, craft, reality

    # Corner colors
    DESIGN_COLOR = QColor(100, 149, 237)  # Cornflower blue
    CLIENT_COLOR = QColor(144, 238, 144)  # Light green
    BUILD_COLOR = QColor(255, 165, 0)     # Orange
    APEX_COLOR = QColor(200, 180, 255)    # Light purple (Concept/Integration)

    # Mode definitions: name, description, color, excluded vertex
    MODES = {
        "vision": ("Vision", "Design + Client focus", QColor(80, 100, 160), "build"),
        "budget": ("Budget", "Client + Build focus", QColor(100, 140, 80), "design"),
        "craft": ("Craft", "Build + Design focus", QColor(160, 100, 60), "client"),
        "reality": ("Reality", "All constraints", QColor(100, 100, 110), "apex"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._design = 0.33
        self._client = 0.33
        self._build = 0.34
        self._lod = 2
        self._dragging = False
        self._rotating = False
        self._puck_radius = 6
        self._padding = 14
        self._rot_x = -25.0
        self._rot_y = 35.0
        self._last_mouse_pos = None
        self._current_mode = "reality"  # Default to base/reality mode

        self.setFixedSize(190, 190)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    def set_gravity(self, design: float, client: float, build: float):
        self._design, self._client, self._build = self._clamp(design, client, build)
        self.update()

    def set_lod_level(self, level: int):
        self._lod = max(1, min(5, int(level)))
        self.update()

    def _projected_base_triangle(self):
        points = self._projected_points()
        return points["top"], points["bl"], points["br"]

    def _barycentric_to_point(self, design: float, client: float, build: float) -> QPointF:
        top, bl, br = self._projected_base_triangle()
        x = design * top.x() + client * bl.x() + build * br.x()
        y = design * top.y() + client * bl.y() + build * br.y()
        return QPointF(x, y)

    def _point_to_barycentric(self, point: QPointF):
        top, bl, br = self._projected_base_triangle()
        v0x = br.x() - bl.x()
        v0y = br.y() - bl.y()
        v1x = top.x() - bl.x()
        v1y = top.y() - bl.y()
        v2x = point.x() - bl.x()
        v2y = point.y() - bl.y()

        dot00 = v0x * v0x + v0y * v0y
        dot01 = v0x * v1x + v0y * v1y
        dot02 = v0x * v2x + v0y * v2y
        dot11 = v1x * v1x + v1y * v1y
        dot12 = v1x * v2x + v1y * v2y

        denom = dot00 * dot11 - dot01 * dot01
        if abs(denom) < 1e-6:
            return 0.33, 0.33, 0.34

        inv = 1.0 / denom
        build = (dot11 * dot02 - dot01 * dot12) * inv
        design = (dot00 * dot12 - dot01 * dot02) * inv
        client = 1.0 - design - build
        return design, client, build

    def _clamp(self, design: float, client: float, build: float):
        design = max(0.0, min(1.0, design))
        client = max(0.0, min(1.0, client))
        build = max(0.0, min(1.0, build))
        total = design + client + build
        if total <= 0:
            return 0.33, 0.33, 0.34
        return design / total, client / total, build / total

    def _emit_gravity(self):
        self.gravity_changed.emit(self._design, self._client, self._build)

    def _cross(self, a, b):
        """Cross product of two 3D vectors."""
        return (
            a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]
        )

    def _sub(self, a, b):
        """Subtract two 3D vectors."""
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def _face_normal(self, v0, v1, v2):
        """Calculate face normal from three vertices (counter-clockwise)."""
        edge1 = self._sub(v1, v0)
        edge2 = self._sub(v2, v0)
        normal = self._cross(edge1, edge2)
        # Normalize
        length = math.sqrt(normal[0]**2 + normal[1]**2 + normal[2]**2)
        if length < 1e-6:
            return (0, 0, 1)
        return (normal[0]/length, normal[1]/length, normal[2]/length)

    def _detect_forward_face(self) -> str:
        """Determine which face is most forward-facing based on rotation."""
        # 3D vertices (before rotation)
        apex = (0.0, 1.0, 0.0)
        v_design = (0.0, 0.0, 1.0)
        v_client = (-1.0, 0.0, -0.7)
        v_build = (1.0, 0.0, -0.7)

        # Rotate all vertices
        r_apex = self._rotate(*apex)
        r_design = self._rotate(*v_design)
        r_client = self._rotate(*v_client)
        r_build = self._rotate(*v_build)

        # Define faces: (name, v0, v1, v2) - vertices in CCW order when viewed from outside
        faces = [
            ("vision", r_design, r_client, r_apex),   # Excludes Build
            ("budget", r_client, r_build, r_apex),    # Excludes Design
            ("craft", r_build, r_design, r_apex),     # Excludes Client
            ("reality", r_design, r_build, r_client), # Base - excludes Apex
        ]

        # Find face with normal pointing most toward viewer (positive Z)
        best_face = "reality"
        best_z = -999

        for name, v0, v1, v2 in faces:
            normal = self._face_normal(v0, v1, v2)
            # Z component of normal (positive = facing viewer)
            if normal[2] > best_z:
                best_z = normal[2]
                best_face = name

        return best_face

    def _update_mode(self):
        """Check if mode changed and emit signal if so."""
        new_mode = self._detect_forward_face()
        if new_mode != self._current_mode:
            self._current_mode = new_mode
            self.mode_changed.emit(new_mode)

    def get_current_mode(self) -> str:
        """Get the current active mode."""
        return self._current_mode

    def _lerp_point(self, a: QPointF, b: QPointF, t: float) -> QPointF:
        return QPointF(a.x() + (b.x() - a.x()) * t, a.y() + (b.y() - a.y()) * t)

    def _rotate(self, x: float, y: float, z: float):
        rx = math.radians(self._rot_x)
        ry = math.radians(self._rot_y)

        # Rotate around X
        cy = math.cos(rx)
        sy = math.sin(rx)
        y2 = y * cy - z * sy
        z2 = y * sy + z * cy

        # Rotate around Y
        cx = math.cos(ry)
        sx = math.sin(ry)
        x3 = x * cx + z2 * sx
        z3 = -x * sx + z2 * cx
        return x3, y2, z3

    def _project(self, x: float, y: float, z: float):
        w = self.width()
        h = self.height()
        scale = min(w, h) * 0.35
        sx = x * scale + w * 0.5
        sy = -y * scale + h * 0.58
        return QPointF(sx, sy)

    def _projected_points(self):
        # 3D vertices
        apex = (0.0, 1.0, 0.0)
        v_top = (0.0, 0.0, 1.0)     # Design
        v_bl = (-1.0, 0.0, -0.7)    # Client
        v_br = (1.0, 0.0, -0.7)     # Build

        def proj(v):
            x, y, z = self._rotate(*v)
            return self._project(x, y, z), z

        p_apex, z_apex = proj(apex)
        p_top, z_top = proj(v_top)
        p_bl, z_bl = proj(v_bl)
        p_br, z_br = proj(v_br)

        return {
            "apex": p_apex,
            "top": p_top,
            "bl": p_bl,
            "br": p_br,
            "z": {"apex": z_apex, "top": z_top, "bl": z_bl, "br": z_br},
        }

    def _triangle_at(self, t: float):
        points = self._projected_points()
        apex = points["apex"]
        top, bl, br = points["top"], points["bl"], points["br"]
        return (
            self._lerp_point(top, apex, t),
            self._lerp_point(bl, apex, t),
            self._lerp_point(br, apex, t),
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 20, 25, 190))
        painter.drawRoundedRect(bg, 10, 10)

        points = self._projected_points()
        top, bl, br = points["top"], points["bl"], points["br"]
        apex = points["apex"]

        # Get current mode info
        mode_info = self.MODES.get(self._current_mode, self.MODES["reality"])
        mode_name, mode_desc, mode_color, excluded = mode_info

        # Face definitions with semantic names
        # Each face excludes one vertex - highlight the active face
        face_defs = [
            ("vision", [apex, top, bl], "build"),    # Vision: Design-Client-Apex, excludes Build
            ("craft", [apex, br, top], "client"),    # Craft: Build-Design-Apex, excludes Client
            ("budget", [apex, bl, br], "design"),    # Budget: Client-Build-Apex, excludes Design
            ("reality", [top, bl, br], "apex"),      # Reality: base triangle, excludes Apex
        ]

        # Assign colors - highlight active face
        faces = []
        for name, pts, excl in face_defs:
            if name == self._current_mode:
                # Active face - brighter, use mode color
                color = QColor(mode_color)
                color.setAlpha(200)
            else:
                # Inactive face - dim
                color = QColor(50, 50, 60, 100)
            faces.append((name, pts, color))  # pts are already QPointF from points dict

        def face_depth(face_pts):
            return sum(p.y() for p in face_pts) / len(face_pts)

        faces.sort(key=lambda f: face_depth(f[1]))

        for _, pts, color in faces:
            path = QPainterPath()
            path.moveTo(pts[0])
            path.lineTo(pts[1])
            path.lineTo(pts[2])
            path.closeSubpath()
            painter.fillPath(path, color)

        # Tetrahedron edges
        edge_color = QColor(150, 150, 160)
        painter.setPen(QPen(edge_color, 1.5))
        painter.drawLine(apex, bl)
        painter.drawLine(apex, br)
        painter.drawLine(apex, top)
        painter.drawLine(top, bl)
        painter.drawLine(bl, br)
        painter.drawLine(br, top)

        # Corner markers - dim the excluded vertex
        corners = [
            (top, self.DESIGN_COLOR, "design"),
            (bl, self.CLIENT_COLOR, "client"),
            (br, self.BUILD_COLOR, "build"),
            (apex, self.APEX_COLOR, "apex"),
        ]

        for pos, color, name in corners:
            if name == excluded:
                # Excluded vertex - dim and smaller
                dim_color = QColor(color)
                dim_color.setAlpha(80)
                painter.setBrush(dim_color)
                painter.setPen(QPen(dim_color.darker(120), 1))
                painter.drawEllipse(pos, 4, 4)
            else:
                # Active vertex - bright
                painter.setBrush(color)
                painter.setPen(QPen(color.darker(120), 2))
                painter.drawEllipse(pos, 6, 6)

        # Gravity puck (on base triangle)
        puck = self._barycentric_to_point(self._design, self._client, self._build)
        painter.setBrush(QColor(240, 240, 245))
        painter.setPen(QPen(QColor(30, 30, 30), 1))
        painter.drawEllipse(puck, self._puck_radius, self._puck_radius)

        # Mode badge (bottom)
        mode_badge = QRectF(6, self.height() - 30, self.width() - 12, 24)
        badge_color = QColor(mode_color)
        badge_color.setAlpha(180)
        painter.setBrush(badge_color)
        painter.setPen(QPen(mode_color.lighter(120), 1))
        painter.drawRoundedRect(mode_badge, 6, 6)
        painter.setPen(QColor(240, 240, 250))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(mode_badge, Qt.AlignmentFlag.AlignCenter, mode_name)

        # LOD badge (top right)
        lod_badge = QRectF(self.width() - 44, 6, 38, 22)
        painter.setBrush(QColor(30, 30, 35, 200))
        painter.setPen(QPen(QColor(100, 100, 110), 1))
        painter.drawRoundedRect(lod_badge, 5, 5)
        painter.setPen(QColor(200, 200, 210))
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(lod_badge, Qt.AlignmentFlag.AlignCenter, f"LOD {self._lod}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_mouse_pos = event.position()
            self._update_from_pos(event.position())
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._rotating = True
            self._last_mouse_pos = event.position()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._update_from_pos(event.position())
            event.accept()
            return
        if self._rotating and self._last_mouse_pos is not None:
            delta = event.position() - self._last_mouse_pos
            self._rot_y = (self._rot_y + delta.x() * 0.4) % 360.0
            self._rot_x = (self._rot_x + delta.y() * 0.4) % 360.0  # Allow full rotation
            self._last_mouse_pos = event.position()
            self._update_mode()  # Check if rotation changed the active face
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._rotating = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            if delta > 0:
                self._lod = max(1, self._lod - 1)
            else:
                self._lod = min(5, self._lod + 1)
            self.lod_changed.emit(self._lod, 0.0)
            self.update()
            event.accept()
            return
        super().wheelEvent(event)

    def _update_from_pos(self, pos):
        design, client, build = self._point_to_barycentric(QPointF(pos))
        self._design, self._client, self._build = self._clamp(design, client, build)
        self._emit_gravity()
        self.update()

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


# Room data structure matching ArchRoomData in arch_api.h
class ArchRoomData(ctypes.Structure):
    """ctypes structure for room data from the Vulkan renderer."""
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
    rooms_loaded = pyqtSignal(list)  # room data list
    error_occurred = pyqtSignal(str)
    camera_distance_changed = pyqtSignal(float)  # distance from target
    lod_level_changed = pyqtSignal(int)  # LOD level 1-5 (shift+scroll)
    gravity_changed = pyqtSignal(float, float, float)  # design, client, build
    lod_changed = pyqtSignal(int, float)  # level, transition

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

        # LOD state (independent of camera distance)
        self._lod_level = 2  # Default: Walls (1-5 range)

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

        # Floating tetrahedron navigation overlay (tool window parented to main window)
        # Must be top-level because child widgets can't render over WA_PaintOnScreen
        # Parent will be set when main window is available
        self._nav_overlay = TetraNavOverlay()
        self._nav_overlay.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint
        )
        self._nav_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._nav_overlay.gravity_changed.connect(self.gravity_changed.emit)
        self._nav_overlay.lod_changed.connect(self.lod_changed.emit)
        self._nav_overlay.hide()
        self._nav_overlay_parented_to_window = False

        self._nav_follow_timer = QTimer(self)
        self._nav_follow_timer.setInterval(16)
        self._nav_follow_timer.timeout.connect(self._position_nav_overlay)
        self._nav_follow_timer.stop()
        self._nav_event_filter_installed = False
        self._nav_parented = False
        self._nav_parenting_enabled = True
        self._nav_mouse_captured = False
        self._nav_stop_timer = QTimer(self)
        self._nav_stop_timer.setSingleShot(True)
        self._nav_stop_timer.timeout.connect(self._nav_follow_timer.stop)
        QTimer.singleShot(0, self._install_nav_event_filter)

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

                # Room export API
                self._lib.arch_get_room_count.argtypes = []
                self._lib.arch_get_room_count.restype = ctypes.c_int

                self._lib.arch_get_room_data.argtypes = [ctypes.c_int, ctypes.POINTER(ArchRoomData)]
                self._lib.arch_get_room_data.restype = ctypes.c_int

                self._lib.arch_get_all_rooms.argtypes = [ctypes.POINTER(ArchRoomData), ctypes.c_int]
                self._lib.arch_get_all_rooms.restype = ctypes.c_int

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

        # Show navigation overlay when widget becomes visible
        QTimer.singleShot(150, self._position_nav_overlay)

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
        if hasattr(self, "_nav_overlay") and self._nav_overlay:
            self._nav_overlay.close()
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

    def _overlay_hit_test(self, global_pos: QPointF) -> bool:
        if not self._nav_overlay or not self._nav_overlay.isVisible():
            return False
        local_pos = self._nav_overlay.mapFromGlobal(global_pos.toPoint())
        rect = QRectF(0, 0, self._nav_overlay.width(), self._nav_overlay.height())
        return rect.contains(QPointF(local_pos))

    def _route_overlay_mouse(self, event: QMouseEvent) -> bool:
        if not self._nav_overlay or not self._nav_overlay.isVisible():
            return False
        global_pos = event.globalPosition()
        if event.type() == QEvent.Type.MouseButtonPress:
            if not self._overlay_hit_test(global_pos):
                return False
            self._nav_mouse_captured = True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if not self._nav_mouse_captured and not self._overlay_hit_test(global_pos):
                return False
            self._nav_mouse_captured = False
        else:
            if not self._nav_mouse_captured and not self._overlay_hit_test(global_pos):
                return False
        local_pos = self._nav_overlay.mapFromGlobal(global_pos.toPoint())
        routed = QMouseEvent(
            event.type(),
            QPointF(local_pos),
            QPointF(local_pos),
            global_pos,
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QCoreApplication.sendEvent(self._nav_overlay, routed)
        event.accept()
        return True

    def _route_overlay_wheel(self, event: QWheelEvent) -> bool:
        if not self._nav_overlay or not self._nav_overlay.isVisible():
            return False
        global_pos = event.globalPosition()
        if not self._overlay_hit_test(global_pos):
            return False
        local_pos = self._nav_overlay.mapFromGlobal(global_pos.toPoint())
        routed = QWheelEvent(
            QPointF(local_pos),
            global_pos,
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )
        QCoreApplication.sendEvent(self._nav_overlay, routed)
        event.accept()
        return True

    def _position_nav_overlay(self):
        """Position the overlay in the top-right corner of the viewport."""
        if not self._nav_overlay:
            return
        if not self.isVisible():
            self._nav_overlay.hide()
            return

        # Parent to main window once available (so it stays with app, not above other apps)
        if not self._nav_overlay_parented_to_window:
            main_win = self.window()
            if main_win:
                self._nav_overlay.setParent(main_win)
                self._nav_overlay.setWindowFlags(
                    Qt.WindowType.Tool |
                    Qt.WindowType.FramelessWindowHint
                )
                self._nav_overlay_parented_to_window = True

        margin = 12
        # Position relative to self (the viewport widget), converted to global
        my_size = self.size()
        target_size = min(190, max(140, int(min(my_size.width(), my_size.height()) * 0.22)))
        if self._nav_overlay.width() != target_size:
            self._nav_overlay.setFixedSize(target_size, target_size)
        # Calculate position in viewport coordinates, then convert to global
        local_x = my_size.width() - self._nav_overlay.width() - margin
        local_y = margin
        global_pos = self.mapToGlobal(QPointF(local_x, local_y).toPoint())
        self._nav_overlay.move(global_pos)
        self._nav_overlay.raise_()
        self._nav_overlay.show()

    def _install_nav_event_filter(self):
        if self._nav_event_filter_installed:
            return
        self.installEventFilter(self)
        window = self.window()
        if window:
            window.installEventFilter(self)
        self._nav_event_filter_installed = True
        self._position_nav_overlay()

    def eventFilter(self, obj, event):
        if obj in (self, self.window()):
            if event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange):
                if not self._nav_follow_timer.isActive():
                    self._nav_follow_timer.start()
                self._nav_stop_timer.start(250)
                QTimer.singleShot(0, self._position_nav_overlay)
        return super().eventFilter(obj, event)

    def _ensure_overlay_parented(self):
        # Top-level window, no parenting needed - just track state
        if not self._nav_parented:
            self._nav_parented = True

    def _move_overlay_native(self, x: int, y: int):
        return

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_nav_overlay()

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

                    # Emit rooms after load
                    rooms = self.get_rooms()
                    if rooms:
                        self.rooms_loaded.emit(rooms)

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

                # Emit rooms after load
                rooms = self.get_rooms()
                if rooms:
                    self.rooms_loaded.emit(rooms)

                return True
            else:
                error = self._lib.arch_get_error().decode('utf-8')
                print(f"[VulkanWidget] Load failed: {error}")
                self.error_occurred.emit(error)
                return False

    def get_rooms(self) -> list:
        """
        Get room data from the Vulkan renderer.

        Returns:
            List of room dictionaries with id, name, room_type, bounds, center, area, zone
        """
        print(f"[VulkanWidget] get_rooms called, initialized={self._initialized}, lib={self._lib is not None}", flush=True)
        if not self._initialized or self._lib is None:
            return []

        try:
            room_count = self._lib.arch_get_room_count()
            print(f"[VulkanWidget] room_count = {room_count}", flush=True)
            if room_count <= 0:
                return []

            # Allocate array for all rooms
            rooms_array = (ArchRoomData * room_count)()
            filled = self._lib.arch_get_all_rooms(rooms_array, room_count)

            rooms = []
            for i in range(filled):
                r = rooms_array[i]
                rooms.append({
                    'id': r.id.decode('utf-8', errors='ignore'),
                    'name': r.name.decode('utf-8', errors='ignore'),
                    'room_type': r.room_type.decode('utf-8', errors='ignore'),
                    'bounds': {
                        'x': r.bounds_x,
                        'y': r.bounds_y,
                        'width': r.bounds_width,
                        'height': r.bounds_height,
                    },
                    'center': {'x': r.center_x, 'z': r.center_y},
                    'area': r.area,
                    'zone': r.zone,  # 0=Public, 1=Private, 2=Service, 3=Circulation
                })

            print(f"[VulkanWidget] Retrieved {len(rooms)} rooms from renderer")
            return rooms

        except Exception as e:
            print(f"[VulkanWidget] Failed to get rooms: {e}")
            return []

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

    def mousePressEvent(self, event):
        """Handle mouse press for camera control."""
        if self._route_overlay_mouse(event):
            return
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
        if self._route_overlay_mouse(event):
            return
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for camera orbit/pan."""
        if self._route_overlay_mouse(event):
            return
        if self._dragging and self._last_mouse_pos is not None:
            dx = event.pos().x() - self._last_mouse_pos.x()
            dy = event.pos().y() - self._last_mouse_pos.y()

            if self._panning:
                # Pan: move camera target so cursor tracks 1:1 with world
                import math

                # Calculate world units per pixel based on camera distance and FOV
                # This gives us 1:1 cursor tracking
                fov_rad = math.radians(45.0)  # Approximate FOV
                viewport_height = self.height()

                # World height visible at the target distance
                world_height = 2.0 * self._camera_distance * math.tan(fov_rad / 2.0)
                world_per_pixel = world_height / viewport_height

                # Right vector (perpendicular to view direction in XZ plane)
                right_x = math.cos(self._camera_yaw)
                right_z = math.sin(self._camera_yaw)

                # Calculate pan in world units (negative dx moves target right, so view pans left)
                pan_x = -dx * world_per_pixel
                pan_y = dy * world_per_pixel  # Positive dy moves target up

                # Move target along right vector (horizontal pan)
                self._camera_target[0] += pan_x * right_x
                self._camera_target[2] += pan_x * right_z

                # Move target along up vector (vertical pan)
                self._camera_target[1] += pan_y

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
        """Handle mouse wheel for zoom (normal) or LOD change (shift+scroll)."""
        if self._route_overlay_wheel(event):
            return
        import math
        delta = event.angleDelta().y() / 120.0

        if abs(delta) < 0.01:
            super().wheelEvent(event)
            return

        # Check for shift modifier - LOD change
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            # Shift+scroll = change LOD level
            if delta > 0:
                # Scroll up = decrease LOD (more abstract, farther view)
                self._lod_level = max(1, self._lod_level - 1)
            else:
                # Scroll down = increase LOD (more detail, closer view)
                self._lod_level = min(5, self._lod_level + 1)

            self.lod_level_changed.emit(self._lod_level)
            super().wheelEvent(event)
            return

        # Normal scroll = zoom
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
