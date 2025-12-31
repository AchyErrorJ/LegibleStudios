"""
Plan View - Main 2D floor plan editor
"""
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import math

from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsLineItem,
    QGraphicsTextItem, QGraphicsEllipseItem
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont

from views.base_view import BaseView
from core.document import ArchDocument, Wall, Door, Window, Room
from core.events import event_bus
from app.config import Config


# =============================================================================
# Snap System
# =============================================================================

class SnapType(Enum):
    """Types of snap points."""
    ENDPOINT = "endpoint"
    MIDPOINT = "midpoint"
    PERPENDICULAR = "perpendicular"
    PARALLEL = "parallel"
    EXTENSION = "extension"
    ANGULAR = "angular"  # 45°, 30°, 60° etc
    INTERSECTION = "intersection"


@dataclass
class SnapPoint:
    """Represents a potential snap target."""
    x: float
    y: float
    snap_type: SnapType
    source_wall_idx: int = -1  # Index of wall this snap comes from
    angle: float = 0.0  # Angle in degrees (for perpendicular snaps)

    @property
    def point(self) -> QPointF:
        return QPointF(self.x, self.y)


class SnapIndicator(QGraphicsItem):
    """Visual indicator for active snap point."""

    SIZE = 200  # mm

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snap_type: Optional[SnapType] = None
        self._angle: float = 0.0
        self._font = QFont("Arial", 120)
        self.setZValue(3000)  # Above grips
        self.hide()

    def set_snap(self, point: QPointF, snap_type: SnapType, angle: float = 0.0):
        """Show snap indicator at point."""
        self.setPos(point)
        self._snap_type = snap_type
        self._angle = angle
        self.show()
        self.update()

    def clear(self):
        """Hide snap indicator."""
        self.hide()
        self._snap_type = None
        self._angle = 0.0

    def boundingRect(self) -> QRectF:
        s = self.SIZE
        return QRectF(-s * 2, -s * 2, s * 4, s * 4)

    def paint(self, painter: QPainter, option, widget):
        if not self._snap_type:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.SIZE

        if self._snap_type == SnapType.ENDPOINT:
            # Square for endpoints
            pen = QPen(QColor(0, 255, 0), 20)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-s/2, -s/2, s, s))

        elif self._snap_type == SnapType.MIDPOINT:
            # Triangle for midpoints
            pen = QPen(QColor(0, 255, 255), 20)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(0, -s/2)
            path.lineTo(-s/2, s/2)
            path.lineTo(s/2, s/2)
            path.closeSubpath()
            painter.drawPath(path)

        elif self._snap_type == SnapType.PERPENDICULAR:
            # Right angle symbol for perpendicular
            pen = QPen(QColor(255, 128, 0), 20)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(-s/2, 0), QPointF(0, 0))
            painter.drawLine(QPointF(0, 0), QPointF(0, -s/2))

            # Draw angle text
            painter.setFont(self._font)
            angle_text = f"{self._angle:.4f}°"
            painter.drawText(QPointF(s/2 + 50, s/2), angle_text)

        elif self._snap_type == SnapType.PARALLEL:
            # Two parallel lines symbol
            pen = QPen(QColor(0, 200, 255), 20)
            painter.setPen(pen)
            painter.drawLine(QPointF(-s/2, -s/4), QPointF(s/2, -s/4))
            painter.drawLine(QPointF(-s/2, s/4), QPointF(s/2, s/4))

        elif self._snap_type == SnapType.EXTENSION:
            # Dashed line extending symbol
            pen = QPen(QColor(255, 200, 0), 20, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
            # Small square at snap point
            pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(QRectF(-s/4, -s/4, s/2, s/2))

        elif self._snap_type == SnapType.ANGULAR:
            # Arc symbol for angular snap
            pen = QPen(QColor(200, 100, 255), 20)
            painter.setPen(pen)
            painter.drawArc(QRectF(-s/2, -s/2, s, s), 0, int(self._angle * 16))
            # Draw angle text
            painter.setFont(self._font)
            painter.drawText(QPointF(s/2 + 50, 0), f"{self._angle:.0f}°")

        elif self._snap_type == SnapType.INTERSECTION:
            # X for intersections
            pen = QPen(QColor(255, 0, 255), 20)
            painter.setPen(pen)
            painter.drawLine(QPointF(-s/2, -s/2), QPointF(s/2, s/2))
            painter.drawLine(QPointF(-s/2, s/2), QPointF(s/2, -s/2))


class SnapManager:
    """Manages snap points and snapping logic."""

    SNAP_TOLERANCE = 500  # mm - distance within which to snap

    def __init__(self, document: ArchDocument, config: Config = None):
        self.document = document
        self.config = config
        self._snap_points: List[SnapPoint] = []
        self._excluded_wall_idx: int = -1  # Wall being edited (exclude from snapping)

    def set_excluded_wall(self, wall_idx: int):
        """Set wall to exclude from snap point collection."""
        self._excluded_wall_idx = wall_idx

    def collect_snap_points(self):
        """Collect all snap points from document."""
        self._snap_points.clear()

        for i, wall in enumerate(self.document.walls):
            if i == self._excluded_wall_idx:
                continue

            x1, z1 = wall.start[0], wall.start[2]
            x2, z2 = wall.end[0], wall.end[2]
            cx, cz = (x1 + x2) / 2, (z1 + z2) / 2

            # Endpoints (if enabled)
            if not self.config or self.config.snap_endpoint:
                self._snap_points.append(SnapPoint(x1, z1, SnapType.ENDPOINT, i))
                self._snap_points.append(SnapPoint(x2, z2, SnapType.ENDPOINT, i))

            # Midpoint (if enabled)
            if not self.config or self.config.snap_midpoint:
                self._snap_points.append(SnapPoint(cx, cz, SnapType.MIDPOINT, i))

    def find_perpendicular_snap(self, point: QPointF, from_point: Optional[QPointF] = None,
                                  fixed_point: Optional[QPointF] = None) -> Optional[SnapPoint]:
        """
        Find perpendicular snap point.

        If fixed_point is provided: Find position where the line from fixed_point to
        the snap position would be perpendicular to a target wall (makes your wall ⊥ to another).

        Otherwise (legacy): Find where a 90° line from from_point hits a wall.
        """
        # New behavior: make wall perpendicular to another wall
        if fixed_point:
            return self._find_make_wall_perpendicular(point, fixed_point)

        # Legacy behavior
        if not from_point:
            return None

        best_snap = None
        best_dist = self.SNAP_TOLERANCE

        for i, wall in enumerate(self.document.walls):
            if i == self._excluded_wall_idx:
                continue

            x1, z1 = wall.start[0], wall.start[2]
            x2, z2 = wall.end[0], wall.end[2]

            wall_dx = x2 - x1
            wall_dz = z2 - z1
            wall_len = math.sqrt(wall_dx**2 + wall_dz**2)
            if wall_len < 1:
                continue

            wall_ux = wall_dx / wall_len
            wall_uz = wall_dz / wall_len
            perp_ux = -wall_uz
            perp_uz = wall_ux

            denom = perp_ux * wall_uz - perp_uz * wall_ux
            if abs(denom) < 0.0001:
                continue

            dx = x1 - from_point.x()
            dz = z1 - from_point.y()

            t = (dx * wall_uz - dz * wall_ux) / denom
            s = (dx * perp_uz - dz * perp_ux) / denom

            if s < -0.01 or s > wall_len + 0.01:
                continue

            snap_x = from_point.x() + t * perp_ux
            snap_z = from_point.y() + t * perp_uz

            dist = self._distance(point.x(), point.y(), snap_x, snap_z)
            if dist < best_dist:
                best_dist = dist
                best_snap = SnapPoint(snap_x, snap_z, SnapType.PERPENDICULAR, i, 90.0)

        return best_snap

    def _find_make_wall_perpendicular(self, point: QPointF, fixed_point: QPointF) -> Optional[SnapPoint]:
        """
        Find snap position where the wall being edited becomes perpendicular to another wall.

        fixed_point: The other endpoint of the wall being edited (stays fixed)
        point: Current drag position

        Returns snap position where fixed_point → snap_pos is ⊥ to a target wall.
        """
        best_snap = None
        best_dist = self.SNAP_TOLERANCE

        # Current distance from fixed point (we keep the same length)
        dx = point.x() - fixed_point.x()
        dz = point.y() - fixed_point.y()
        current_len = math.sqrt(dx * dx + dz * dz)

        if current_len < 10:
            return None  # Too close to fixed point

        for i, wall in enumerate(self.document.walls):
            if i == self._excluded_wall_idx:
                continue

            x1, z1 = wall.start[0], wall.start[2]
            x2, z2 = wall.end[0], wall.end[2]

            # Target wall direction
            wall_dx = x2 - x1
            wall_dz = z2 - z1
            wall_len = math.sqrt(wall_dx * wall_dx + wall_dz * wall_dz)
            if wall_len < 1:
                continue

            # Normalized target wall direction
            wall_ux = wall_dx / wall_len
            wall_uz = wall_dz / wall_len

            # Two perpendicular directions to the target wall
            perp_dirs = [
                (-wall_uz, wall_ux),   # +90°
                (wall_uz, -wall_ux),   # -90°
            ]

            for perp_ux, perp_uz in perp_dirs:
                # Snap position: fixed_point + current_len * perp_dir
                snap_x = fixed_point.x() + current_len * perp_ux
                snap_z = fixed_point.y() + current_len * perp_uz

                # Check if this is close to where user is dragging
                dist = self._distance(point.x(), point.y(), snap_x, snap_z)
                if dist < best_dist:
                    best_dist = dist
                    best_snap = SnapPoint(snap_x, snap_z, SnapType.PERPENDICULAR, i, 90.0)

        return best_snap

    def find_parallel_snap(self, point: QPointF, fixed_point: Optional[QPointF] = None) -> Optional[SnapPoint]:
        """
        Find snap position where the wall being edited becomes parallel to another wall.
        Similar to perpendicular but at 0° instead of 90°.
        """
        if not fixed_point:
            return None

        best_snap = None
        best_dist = self.SNAP_TOLERANCE

        # Current distance from fixed point
        dx = point.x() - fixed_point.x()
        dz = point.y() - fixed_point.y()
        current_len = math.sqrt(dx * dx + dz * dz)

        if current_len < 10:
            return None

        for i, wall in enumerate(self.document.walls):
            if i == self._excluded_wall_idx:
                continue

            x1, z1 = wall.start[0], wall.start[2]
            x2, z2 = wall.end[0], wall.end[2]

            wall_dx = x2 - x1
            wall_dz = z2 - z1
            wall_len = math.sqrt(wall_dx * wall_dx + wall_dz * wall_dz)
            if wall_len < 1:
                continue

            # Normalized target wall direction (parallel directions)
            wall_ux = wall_dx / wall_len
            wall_uz = wall_dz / wall_len

            # Two parallel directions (same as wall, or opposite)
            parallel_dirs = [
                (wall_ux, wall_uz),    # Same direction
                (-wall_ux, -wall_uz),  # Opposite direction
            ]

            for par_ux, par_uz in parallel_dirs:
                snap_x = fixed_point.x() + current_len * par_ux
                snap_z = fixed_point.y() + current_len * par_uz

                dist = self._distance(point.x(), point.y(), snap_x, snap_z)
                if dist < best_dist:
                    best_dist = dist
                    best_snap = SnapPoint(snap_x, snap_z, SnapType.PARALLEL, i, 0.0)

        return best_snap

    def find_extension_snap(self, point: QPointF) -> Optional[SnapPoint]:
        """
        Find snap to extension lines of existing walls.
        Snaps to where wall centerlines would extend beyond their endpoints.
        """
        best_snap = None
        best_dist = self.SNAP_TOLERANCE

        for i, wall in enumerate(self.document.walls):
            if i == self._excluded_wall_idx:
                continue

            x1, z1 = wall.start[0], wall.start[2]
            x2, z2 = wall.end[0], wall.end[2]

            wall_dx = x2 - x1
            wall_dz = z2 - z1
            wall_len = math.sqrt(wall_dx * wall_dx + wall_dz * wall_dz)
            if wall_len < 1:
                continue

            wall_ux = wall_dx / wall_len
            wall_uz = wall_dz / wall_len

            # Project point onto the infinite line of this wall
            # Vector from wall start to point
            px = point.x() - x1
            pz = point.y() - z1

            # Parameter t along wall direction
            t = (px * wall_ux + pz * wall_uz)

            # Only snap if in extension zone (before start or after end)
            if 0 <= t <= wall_len:
                continue  # Point is alongside the wall, not in extension

            # Calculate snap point on the extension line
            snap_x = x1 + t * wall_ux
            snap_z = z1 + t * wall_uz

            # Check perpendicular distance to extension line
            perp_dist = abs(px * (-wall_uz) + pz * wall_ux)
            if perp_dist > self.SNAP_TOLERANCE:
                continue

            dist = self._distance(point.x(), point.y(), snap_x, snap_z)
            if dist < best_dist:
                best_dist = dist
                best_snap = SnapPoint(snap_x, snap_z, SnapType.EXTENSION, i, 0.0)

        return best_snap

    def find_angular_snap(self, point: QPointF, fixed_point: Optional[QPointF] = None) -> Optional[SnapPoint]:
        """
        Snap to common architectural angles: 30°, 45°, 60° (and their multiples).
        """
        if not fixed_point:
            return None

        dx = point.x() - fixed_point.x()
        dz = point.y() - fixed_point.y()
        current_len = math.sqrt(dx * dx + dz * dz)

        if current_len < 10:
            return None

        # Current angle in degrees
        current_angle = math.degrees(math.atan2(dz, dx))

        # Common angles to snap to (excluding 0, 90, 180, -90 which are handled by ortho)
        snap_angles = [30, 45, 60, 120, 135, 150, -30, -45, -60, -120, -135, -150]

        best_snap = None
        best_diff = 10  # degrees tolerance for angular snap

        for target_angle in snap_angles:
            diff = abs(current_angle - target_angle)
            if diff > 180:
                diff = 360 - diff

            if diff < best_diff:
                best_diff = diff
                rad = math.radians(target_angle)
                snap_x = fixed_point.x() + current_len * math.cos(rad)
                snap_z = fixed_point.y() + current_len * math.sin(rad)
                best_snap = SnapPoint(snap_x, snap_z, SnapType.ANGULAR, -1, abs(target_angle))

        return best_snap

    def _project_point_to_line(self, point: QPointF, x1: float, y1: float, x2: float, y2: float) -> Optional[Tuple[float, float]]:
        """Project point onto line segment, return None if outside segment."""
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq < 1:  # Degenerate line
            return None

        # Parameter t for projection onto infinite line
        t = ((point.x() - x1) * dx + (point.y() - y1) * dy) / length_sq

        # Only snap if projection is on the segment (with small margin)
        if t < -0.01 or t > 1.01:
            return None

        # Clamp to segment
        t = max(0, min(1, t))

        proj_x = x1 + t * dx
        proj_y = y1 + t * dy

        return (proj_x, proj_y)

    def find_nearest_snap(self, point: QPointF, include_perpendicular: bool = True,
                          from_point: Optional[QPointF] = None,
                          fixed_point: Optional[QPointF] = None) -> Optional[SnapPoint]:
        """
        Find nearest snap point within tolerance.

        fixed_point: For perpendicular/parallel/angular snaps, the fixed endpoint of the wall being edited.
        """
        # Check if snapping is globally enabled
        if self.config and not self.config.snap_enabled:
            return None

        best_snap = None
        best_dist = self.SNAP_TOLERANCE

        # Priority 1: Check collected snap points (endpoints, midpoints) - highest priority
        # These are already filtered in collect_snap_points based on config
        for snap in self._snap_points:
            dist = self._distance(point.x(), point.y(), snap.x, snap.y)
            if dist < best_dist:
                best_dist = dist
                best_snap = snap

        # Priority 2: Extension snaps (align to wall extensions)
        if not self.config or self.config.snap_extension:
            ext_snap = self.find_extension_snap(point)
            if ext_snap:
                dist = self._distance(point.x(), point.y(), ext_snap.x, ext_snap.y)
                if dist < best_dist:
                    best_dist = dist
                    best_snap = ext_snap

        # Priority 3: Perpendicular snaps (make wall ⊥ to another)
        if (not self.config or self.config.snap_perpendicular) and include_perpendicular and fixed_point:
            perp_snap = self.find_perpendicular_snap(point, from_point, fixed_point)
            if perp_snap:
                dist = self._distance(point.x(), point.y(), perp_snap.x, perp_snap.y)
                if dist < best_dist:
                    best_dist = dist
                    best_snap = perp_snap

        # Priority 4: Parallel snaps (make wall ∥ to another)
        if (not self.config or self.config.snap_parallel) and fixed_point:
            par_snap = self.find_parallel_snap(point, fixed_point)
            if par_snap:
                dist = self._distance(point.x(), point.y(), par_snap.x, par_snap.y)
                if dist < best_dist:
                    best_dist = dist
                    best_snap = par_snap

        # Priority 5: Angular snaps (30°, 45°, 60° etc) - lowest priority geometry snap
        if (not self.config or self.config.snap_angular) and fixed_point:
            ang_snap = self.find_angular_snap(point, fixed_point)
            if ang_snap:
                dist = self._distance(point.x(), point.y(), ang_snap.x, ang_snap.y)
                if dist < best_dist:
                    best_snap = ang_snap

        return best_snap

    def _distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Calculate distance between two points."""
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


# =============================================================================
# Grip Items for interactive editing
# =============================================================================

class GripItem(QGraphicsEllipseItem):
    """Draggable grip for editing geometry."""

    GRIP_SIZE = 150  # mm - visual size (small, subtle)
    HIT_SIZE = 800   # mm - clickable area (large, easy to grab)

    def __init__(self, grip_type: str, parent_item, callback, snap_manager=None, snap_indicator=None, wall_idx: int = -1, config=None, on_drag_start=None, on_drag_end=None, parent=None):
        size = self.GRIP_SIZE
        super().__init__(-size/2, -size/2, size, size, parent)
        self.grip_type = grip_type  # 'start', 'end', 'center'
        self.parent_item = parent_item
        self.callback = callback
        self.snap_manager = snap_manager
        self.snap_indicator = snap_indicator
        self.wall_idx = wall_idx  # Index of wall this grip belongs to
        self.config = config  # For ortho mode
        self.on_drag_start = on_drag_start  # Callback when drag starts
        self.on_drag_end = on_drag_end  # Callback when drag ends

        # Appearance - blue fill, white border
        self.setBrush(QBrush(QColor(50, 150, 255)))
        self.setPen(QPen(QColor(255, 255, 255), 15))
        self.setZValue(2000)  # Always on top

        # Behavior - movable but NOT selectable (so parent item stays selected)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        self._dragging = False
        self._current_snap: Optional[SnapPoint] = None
        self._drag_start: Optional[QPointF] = None  # For ortho mode

    def boundingRect(self) -> QRectF:
        """Return larger bounding rect for easier clicking."""
        hit = self.HIT_SIZE
        return QRectF(-hit/2, -hit/2, hit, hit)

    def shape(self) -> QPainterPath:
        """Return larger shape for hit testing."""
        path = QPainterPath()
        hit = self.HIT_SIZE
        path.addEllipse(-hit/2, -hit/2, hit, hit)
        return path

    def paint(self, painter: QPainter, option, widget):
        """Paint the visible grip (smaller than hit area)."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = self.GRIP_SIZE
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawEllipse(QRectF(-size/2, -size/2, size, size))

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor(255, 200, 0)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor(0, 150, 255)))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        self._dragging = True
        self._current_snap = None
        self._drag_start = self.pos()  # Store start position for ortho

        # Notify drag start
        if self.on_drag_start:
            self.on_drag_start(self.grip_type)

        # Select the parent item (wall) if it's selectable
        if self.parent_item and hasattr(self.parent_item, 'setSelected'):
            self.parent_item.setSelected(True)

        # Prepare snap manager
        if self.snap_manager:
            self.snap_manager.set_excluded_wall(self.wall_idx)
            self.snap_manager.collect_snap_points()

        event.accept()  # Stop event propagation to items underneath
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging = False

        # Apply final snap if active
        if self._current_snap:
            # Move to exact snap position
            self._dragging = False  # Prevent callback during setPos
            super().setPos(self._current_snap.x, self._current_snap.y)
            # Now trigger callback with snapped position
            if self.callback:
                self.callback(self.grip_type, QPointF(self._current_snap.x, self._current_snap.y))

        # Clear snap indicator
        if self.snap_indicator:
            self.snap_indicator.clear()

        # Notify drag end (for undo command creation)
        if self.on_drag_end:
            self.on_drag_end(self.grip_type)

        self._current_snap = None
        super().mouseReleaseEvent(event)

    def _get_fixed_point(self) -> Optional[QPointF]:
        """Get the fixed endpoint of the wall (the one NOT being dragged)."""
        if not self.parent_item or not hasattr(self.parent_item, 'wall'):
            return None
        wall = self.parent_item.wall
        if self.grip_type == 'start':
            # Dragging start, so end is fixed
            return QPointF(wall.end[0], wall.end[2])
        elif self.grip_type == 'end':
            # Dragging end, so start is fixed
            return QPointF(wall.start[0], wall.start[2])
        else:
            # Center grip - no fixed point
            return None

    def itemChange(self, change, value):
        # Use ItemPositionChange to modify position BEFORE it's applied
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._dragging and self._drag_start:
                new_pos = value

                # Check for snap points first
                snap_found = False
                if self.snap_manager:
                    # Get the fixed point for perpendicular snaps
                    fixed_point = self._get_fixed_point()
                    snap = self.snap_manager.find_nearest_snap(new_pos, from_point=self._drag_start, fixed_point=fixed_point)
                    if snap:
                        self._current_snap = snap
                        # Show snap indicator
                        if self.snap_indicator:
                            self.snap_indicator.set_snap(snap.point, snap.snap_type, snap.angle)
                        # Use snapped position
                        new_pos = snap.point
                        snap_found = True
                    else:
                        self._current_snap = None
                        if self.snap_indicator:
                            self.snap_indicator.clear()

                # Apply ortho as a SOFT snap (only if no other snap found)
                if not snap_found and self.config and self.config.ortho_mode:
                    dx = new_pos.x() - self._drag_start.x()
                    dy = new_pos.y() - self._drag_start.y()
                    dist = math.sqrt(dx*dx + dy*dy)

                    if dist > 10:  # Only snap if moved a bit
                        # Calculate angle from start (0 = right, 90 = down, etc)
                        angle = math.degrees(math.atan2(dy, dx))

                        # Snap to ortho if within tolerance of H/V
                        ortho_tolerance = 15  # degrees
                        snapped_angle = None

                        # Check each cardinal direction with proper wraparound
                        for target in [0, 90, -90, 180]:
                            diff = abs(angle - target)
                            # Handle wraparound at ±180
                            if diff > 180:
                                diff = 360 - diff
                            if diff < ortho_tolerance:
                                snapped_angle = target
                                break

                        if snapped_angle is not None:
                            # Snap to ortho
                            rad = math.radians(snapped_angle)
                            new_pos = QPointF(
                                self._drag_start.x() + dist * math.cos(rad),
                                self._drag_start.y() + dist * math.sin(rad)
                            )
                            # Show ortho indicator
                            if self.snap_indicator:
                                self.snap_indicator.set_snap(new_pos, SnapType.PERPENDICULAR, 90.0)

                # Trigger callback with final position
                if self.callback:
                    self.callback(self.grip_type, new_pos)

                return new_pos

        return super().itemChange(change, value)

    def setPos(self, *args):
        """Override setPos to not trigger callback."""
        was_dragging = self._dragging
        self._dragging = False
        super().setPos(*args)
        self._dragging = was_dragging


class RoomLabelItem(QGraphicsItem):
    """Text label for room names."""

    def __init__(self, room: Room, parent=None):
        super().__init__(parent)
        self.room = room
        self._font = QFont("Arial", 200)  # Large font for mm scale
        self._color = QColor(200, 200, 200, 180)

        # Position at room center
        if room.center:
            self.setPos(room.center.get('x', 0), room.center.get('y', 0))
        elif room.bounds:
            cx = room.bounds.get('x', 0) + room.bounds.get('width', 0) / 2
            cy = room.bounds.get('y', 0) + room.bounds.get('height', 0) / 2
            self.setPos(cx, cy)

    def boundingRect(self) -> QRectF:
        return QRectF(-2000, -500, 4000, 1000)

    def paint(self, painter: QPainter, option, widget):
        painter.setFont(self._font)
        painter.setPen(QPen(self._color))

        # Draw room name centered
        name = self.room.name or self.room.room_type
        rect = self.boundingRect()
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name)


class WallLayerItem(QGraphicsItem):
    """
    Graphics item representing a single layer of a wall.
    Each layer can be selected and edited independently.
    """

    def __init__(self, wall, layer_index: int, layer_data, offset_from_center: float,
                 document=None, parent_wall_item=None, parent=None):
        super().__init__(parent)
        self.wall = wall
        self.layer_index = layer_index
        self.layer_data = layer_data  # WallLayer dataclass
        self.offset_from_center = offset_from_center  # Offset to layer center from wall centerline
        self.document = document
        self.parent_wall_item = parent_wall_item

        # Layer-specific extension adjustments (user can override)
        self.start_extension = 0.0  # mm to extend/retract at start
        self.end_extension = 0.0    # mm to extend/retract at end

        # Grips
        self._grips: List[GripItem] = []
        self._selected = False

        # Colors
        r, g, b, a = layer_data.color
        self._fill_color = QColor(int(r * 255), int(g * 255), int(b * 255), int(a * 255))
        self._selection_color = QColor("#00ffff")

        # Layers are non-selectable - clicks pass through to parent wall
        # But they enable precise hover detection for grips
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)  # Pass clicks through
        self.setZValue(100 + layer_index)  # Outer layers on top

    def _get_geometry(self) -> Tuple[QPointF, QPointF, QPointF, QPointF]:
        """Calculate the four corner points of this layer."""
        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]

        dx = x2 - x1
        dz = z2 - z1
        length = math.sqrt(dx**2 + dz**2)
        if length < 1:
            return None

        # Unit vectors
        ux, uz = dx / length, dz / length
        px, pz = -uz, ux

        # Layer edges (offset from centerline)
        half_thick = self.layer_data.thickness / 2
        outer_offset = self.offset_from_center + half_thick
        inner_offset = self.offset_from_center - half_thick

        # Apply extensions
        ext_start = self.start_extension
        ext_end = self.end_extension

        # Corner points
        p1 = QPointF(x1 + px * outer_offset - ux * ext_start, z1 + pz * outer_offset - uz * ext_start)
        p2 = QPointF(x1 + px * inner_offset - ux * ext_start, z1 + pz * inner_offset - uz * ext_start)
        p3 = QPointF(x2 + px * inner_offset + ux * ext_end, z2 + pz * inner_offset + uz * ext_end)
        p4 = QPointF(x2 + px * outer_offset + ux * ext_end, z2 + pz * outer_offset + uz * ext_end)

        return (p1, p2, p3, p4)

    def boundingRect(self) -> QRectF:
        geom = self._get_geometry()
        if not geom:
            return QRectF()
        p1, p2, p3, p4 = geom
        min_x = min(p1.x(), p2.x(), p3.x(), p4.x()) - 100
        max_x = max(p1.x(), p2.x(), p3.x(), p4.x()) + 100
        min_y = min(p1.y(), p2.y(), p3.y(), p4.y()) - 100
        max_y = max(p1.y(), p2.y(), p3.y(), p4.y()) + 100
        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def shape(self) -> QPainterPath:
        # Minimal shape for layers - they're visual only
        # Mouse events should pass to parent wall
        geom = self._get_geometry()
        if not geom:
            return QPainterPath()
        p1, p2, p3, p4 = geom
        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget):
        geom = self._get_geometry()
        if not geom:
            return

        p1, p2, p3, p4 = geom

        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.closeSubpath()

        painter.fillPath(path, QBrush(self._fill_color))

        # Edge lines
        pen = QPen(Qt.GlobalColor.darkGray)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        # Selection highlight
        if self.isSelected():
            pen = QPen(self._selection_color)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def _create_grips(self):
        """Layer grips disabled - use wall grips instead."""
        pass

    def _remove_grips(self):
        """Layer grips disabled."""
        for grip in self._grips:
            if grip.scene():
                grip.scene().removeItem(grip)
        self._grips.clear()

    def hoverEnterEvent(self, event):
        """Forward hover to parent wall to show grips."""
        if self.parent_wall_item:
            # Show grips on parent wall when hovering any layer
            if not self.parent_wall_item._grips:
                self.parent_wall_item._create_grips()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Check if we should hide parent wall grips."""
        if self.parent_wall_item:
            # Only hide grips if parent wall isn't selected and no grip is being dragged
            if not self.parent_wall_item.isSelected():
                dragging = any(grip._dragging for grip in self.parent_wall_item._grips) if self.parent_wall_item._grips else False
                # Check if another layer of the same wall is being hovered
                other_layer_hovered = any(
                    layer.isUnderMouse() for layer in self.parent_wall_item._layer_items
                    if layer is not self
                )
                # Check if parent wall itself or a grip is under mouse
                parent_hovered = self.parent_wall_item.isUnderMouse()
                grip_hovered = any(grip.isUnderMouse() for grip in self.parent_wall_item._grips) if self.parent_wall_item._grips else False

                if not dragging and not other_layer_hovered and not parent_hovered and not grip_hovered:
                    self.parent_wall_item._remove_grips()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        return super().itemChange(change, value)


class WallItem(QGraphicsItem):
    """Graphics item representing a wall."""

    def __init__(self, wall: Wall, thickness: float = 150, document=None, snap_manager=None, snap_indicator=None, config=None, parent=None):
        super().__init__(parent)
        self.wall = wall
        self.thickness = thickness
        self.document = document
        self.snap_manager = snap_manager
        self.snap_indicator = snap_indicator
        self.config = config
        self._selected = False

        # Layer items (for individual layer editing)
        self._layer_items: List[WallLayerItem] = []

        # Colors
        self._color_exterior = QColor("#e0e0e0")
        self._color_interior = QColor("#a0a0a0")
        self._color_wet = QColor("#8080ff")
        self._color_selection = QColor("#ffff00")

        # Grips
        self._grips: List[GripItem] = []

        # Undo tracking - stores wall state at drag start
        self._drag_old_start: Optional[tuple] = None
        self._drag_old_end: Optional[tuple] = None
        self._drag_grip_type: Optional[str] = None

        # Enable selection
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

    def _create_grips(self):
        """Create grip items for this wall."""
        self._remove_grips()

        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]
        cx, cz = (x1 + x2) / 2, (z1 + z2) / 2

        wall_idx = self.wall.index

        # Start grip
        start_grip = GripItem('start', self, self._on_grip_moved,
                              self.snap_manager, self.snap_indicator, wall_idx, self.config,
                              on_drag_start=self._on_drag_start, on_drag_end=self._on_drag_end)
        start_grip.setPos(x1, z1)
        self.scene().addItem(start_grip)
        self._grips.append(start_grip)

        # End grip
        end_grip = GripItem('end', self, self._on_grip_moved,
                            self.snap_manager, self.snap_indicator, wall_idx, self.config,
                            on_drag_start=self._on_drag_start, on_drag_end=self._on_drag_end)
        end_grip.setPos(x2, z2)
        self.scene().addItem(end_grip)
        self._grips.append(end_grip)

        # Center grip
        center_grip = GripItem('center', self, self._on_grip_moved,
                               self.snap_manager, self.snap_indicator, wall_idx, self.config,
                               on_drag_start=self._on_drag_start, on_drag_end=self._on_drag_end)
        center_grip.setPos(cx, cz)
        self.scene().addItem(center_grip)
        self._grips.append(center_grip)

    def _remove_grips(self):
        """Remove all grips."""
        for grip in self._grips:
            if grip.scene():
                grip.scene().removeItem(grip)
        self._grips.clear()

    def create_layer_items(self, scene):
        """Create individual WallLayerItem for each layer of this wall."""
        self.remove_layer_items()

        wall_type = None
        if self.document and self.wall.wall_type:
            wall_type = self.document.get_wall_type(self.wall.wall_type)

        if not wall_type or not wall_type.layers:
            return

        total_thickness = wall_type.total_thickness
        current_offset = -total_thickness / 2

        for i, layer in enumerate(wall_type.layers):
            layer_center = current_offset + layer.thickness / 2
            layer_item = WallLayerItem(
                self.wall, i, layer, layer_center,
                document=self.document, parent_wall_item=self
            )
            scene.addItem(layer_item)
            self._layer_items.append(layer_item)
            current_offset += layer.thickness

    def remove_layer_items(self):
        """Remove all layer items."""
        for item in self._layer_items:
            if item._grips:
                item._remove_grips()
            if item.scene():
                item.scene().removeItem(item)
        self._layer_items.clear()

    def update_layer_items(self):
        """Update layer item positions after wall geometry changes."""
        for layer_item in self._layer_items:
            layer_item.prepareGeometryChange()
            layer_item.update()

    def _on_drag_start(self, grip_type: str):
        """Called when grip drag starts - store original positions for undo."""
        self._drag_old_start = self.wall.start
        self._drag_old_end = self.wall.end
        self._drag_grip_type = grip_type

    def _on_drag_end(self, grip_type: str):
        """Called when grip drag ends - create undo command."""
        if self._drag_old_start is None or self._drag_old_end is None:
            return

        # Check if position actually changed
        if (self._drag_old_start == self.wall.start and
            self._drag_old_end == self.wall.end):
            return  # No change, no undo needed

        # Create undo command
        if self.document:
            from core.commands import MoveWallCommand
            cmd = MoveWallCommand(
                self.document,
                self.wall.index,
                grip_type,
                self._drag_old_start,
                self._drag_old_end,
                self.wall.start,
                self.wall.end
            )
            self.document.undo_stack.push(cmd)
            # Notify 3D viewport of change
            self.document.document_changed.emit()

        # Clear tracking
        self._drag_old_start = None
        self._drag_old_end = None
        self._drag_grip_type = None

    def _on_grip_moved(self, grip_type: str, new_pos: QPointF):
        """Handle grip movement (visual feedback, no undo yet)."""
        x, z = new_pos.x(), new_pos.y()

        if grip_type == 'start':
            new_start = (x, self.wall.start[1], z)
            if self.document:
                # Use direct modify (no undo) during drag
                self.document.modify_wall(self.wall.index, start=new_start)
        elif grip_type == 'end':
            new_end = (x, self.wall.end[1], z)
            if self.document:
                self.document.modify_wall(self.wall.index, end=new_end)
        elif grip_type == 'center':
            # Move both endpoints by delta
            old_cx = (self.wall.start[0] + self.wall.end[0]) / 2
            old_cz = (self.wall.start[2] + self.wall.end[2]) / 2
            dx = x - old_cx
            dz = z - old_cz
            new_start = (self.wall.start[0] + dx, self.wall.start[1], self.wall.start[2] + dz)
            new_end = (self.wall.end[0] + dx, self.wall.end[1], self.wall.end[2] + dz)
            if self.document:
                self.document.modify_wall(self.wall.index, start=new_start, end=new_end)

        self.update()

    def hoverEnterEvent(self, event):
        """Show grips when hovering over wall."""
        if not self._grips:  # Only create if not already showing
            self._create_grips()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Hide grips when leaving wall (unless selected, dragging, or hovering layer)."""
        # Don't remove grips if any grip is being dragged
        dragging = any(grip._dragging for grip in self._grips) if self._grips else False
        # Check if any layer is currently being hovered
        layer_hovered = any(layer.isUnderMouse() for layer in self._layer_items) if self._layer_items else False
        if not self.isSelected() and not dragging and not layer_hovered:
            self._remove_grips()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """Handle selection changes to show/hide grips."""
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                # Selected - ensure grips are visible
                if not self._grips:
                    self._create_grips()
            else:
                # Deselected - remove grips (hover will recreate if still hovering)
                self._remove_grips()
        return super().itemChange(change, value)

    HIT_MARGIN = 400  # mm - extra clickable area around wall

    def _get_total_thickness(self) -> float:
        """Get total wall thickness including all layers."""
        if self.document and self.wall.wall_type:
            wall_type = self.document.get_wall_type(self.wall.wall_type)
            if wall_type:
                return wall_type.total_thickness
        return self.thickness

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        margin = max(self.HIT_MARGIN, self._get_total_thickness() / 2 + 50)
        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]

        return QRectF(
            min(x1, x2) - margin,
            min(z1, z2) - margin,
            abs(x2 - x1) + margin * 2,
            abs(z2 - z1) + margin * 2
        )

    def shape(self) -> QPainterPath:
        """Return larger shape for easier clicking."""
        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]

        dx = x2 - x1
        dz = z2 - z1
        length = (dx**2 + dz**2) ** 0.5

        if length < 1:
            # Very short wall - use a circle for hit area
            path = QPainterPath()
            path.addEllipse(QPointF(x1, z1), self.HIT_MARGIN, self.HIT_MARGIN)
            return path

        # Perpendicular unit vector
        px = -dz / length
        pz = dx / length

        # Use larger hit margin for clickable area
        half_hit = max(self.HIT_MARGIN, self._get_total_thickness() / 2 + 100)

        # Hit area polygon (wider than visual)
        p1 = QPointF(x1 + px * half_hit, z1 + pz * half_hit)
        p2 = QPointF(x1 - px * half_hit, z1 - pz * half_hit)
        p3 = QPointF(x2 - px * half_hit, z2 - pz * half_hit)
        p4 = QPointF(x2 + px * half_hit, z2 + pz * half_hit)

        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)
        path.closeSubpath()
        return path

    def _get_butt_joint_points(self, my_endpoint: str, other_wall, other_endpoint: str,
                                 layer_outer_offset: float, layer_inner_offset: float,
                                 total_thickness: float) -> Tuple[QPointF, QPointF]:
        """
        Calculate corner points for a layer using butt joint (realistic construction).

        The secondary wall (this wall if other has lower index) butts into the primary wall's face.
        Primary wall continues with square cut, secondary wall terminates at primary's face.

        Args:
            my_endpoint: 'start' or 'end' of this wall
            other_wall: The connected wall
            other_endpoint: 'start' or 'end' of the other wall
            layer_outer_offset: Distance from wall centerline to layer outer edge
            layer_inner_offset: Distance from wall centerline to layer inner edge
            total_thickness: Total wall thickness

        Returns:
            (outer_point, inner_point) or None if this wall is primary (no change needed)
        """
        # Determine which wall is primary (continues through) vs secondary (butts in)
        # Lower index = primary, or if same type, longer wall = primary
        i_am_primary = self.wall.index < other_wall.index

        if i_am_primary:
            # I'm primary - my layers continue with square cut, no modification needed
            return None

        # I'm secondary - my layers butt into the primary wall's face

        # Get my wall geometry
        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]
        dx = x2 - x1
        dz = z2 - z1
        length = math.sqrt(dx**2 + dz**2)
        if length < 1:
            return None

        # My unit vectors
        ux, uz = dx / length, dz / length  # Along wall
        px, pz = -uz, ux  # Perpendicular

        # Get primary (other) wall geometry
        ox1, oz1 = other_wall.start[0], other_wall.start[2]
        ox2, oz2 = other_wall.end[0], other_wall.end[2]
        odx = ox2 - ox1
        odz = oz2 - oz1
        olength = math.sqrt(odx**2 + odz**2)
        if olength < 1:
            return None

        # Primary wall perpendicular (its face direction)
        opx, opz = -odz / olength, odx / olength

        # Get primary wall's thickness
        other_wall_type = None
        if self.document and other_wall.wall_type:
            other_wall_type = self.document.get_wall_type(other_wall.wall_type)
        other_thickness = other_wall_type.total_thickness if other_wall_type else total_thickness
        other_half = other_thickness / 2

        # Corner point (where wall centerlines meet)
        if my_endpoint == 'start':
            corner_x, corner_z = x1, z1
        else:
            corner_x, corner_z = x2, z2

        # Determine which face of the primary wall we butt into
        # Check which side of the primary wall our wall is approaching from
        # by seeing which direction we're coming from relative to primary wall's perpendicular

        # Direction we're approaching the corner from
        if my_endpoint == 'start':
            approach_x, approach_z = -ux, -uz  # Coming from our interior toward start
        else:
            approach_x, approach_z = ux, uz  # Coming from our interior toward end

        # Dot product with primary's perpendicular tells us which side
        dot = approach_x * opx + approach_z * opz

        # The face we butt into
        if dot > 0:
            # We approach from the positive perp side - butt into negative face
            face_offset = -other_half
        else:
            # We approach from negative perp side - butt into positive face
            face_offset = other_half

        # The primary wall's face line passes through:
        face_x = corner_x + opx * face_offset
        face_z = corner_z + opz * face_offset

        # Primary wall direction
        oux, ouz = odx / olength, odz / olength

        # Find where my layer edges intersect the primary wall's face
        # Face line: (face_x, face_z) + t * (oux, ouz)
        # My outer edge: corner + px*layer_outer_offset, going in direction (ux, uz)
        # My inner edge: corner + px*layer_inner_offset, going in direction (ux, uz)

        # For outer edge intersection
        outer_start_x = corner_x + px * layer_outer_offset
        outer_start_z = corner_z + pz * layer_outer_offset

        # For inner edge intersection
        inner_start_x = corner_x + px * layer_inner_offset
        inner_start_z = corner_z + pz * layer_inner_offset

        # Find intersection with face line
        # Line: start + t * (ux, uz) intersects face_pt + s * (oux, ouz)
        denom = ux * ouz - uz * oux
        if abs(denom) < 0.001:
            # Parallel walls - shouldn't happen at a corner, but handle gracefully
            return None

        # Outer edge intersection
        t_outer = ((face_x - outer_start_x) * ouz - (face_z - outer_start_z) * oux) / denom
        outer_pt = QPointF(outer_start_x + t_outer * ux, outer_start_z + t_outer * uz)

        # Inner edge intersection
        t_inner = ((face_x - inner_start_x) * ouz - (face_z - inner_start_z) * oux) / denom
        inner_pt = QPointF(inner_start_x + t_inner * ux, inner_start_z + t_inner * uz)

        return (outer_pt, inner_pt)

    def paint(self, painter: QPainter, option, widget):
        """Paint the wall with layers if wall type is defined."""
        # Get wall endpoints
        x1, z1 = self.wall.start[0], self.wall.start[2]
        x2, z2 = self.wall.end[0], self.wall.end[2]

        # Calculate perpendicular offset for thickness
        dx = x2 - x1
        dz = z2 - z1
        length = (dx**2 + dz**2) ** 0.5
        if length == 0:
            return

        # Unit vectors
        ux, uz = dx / length, dz / length  # Along wall
        px, pz = -dz / length, dx / length  # Perpendicular

        # Get wall type for layers
        wall_type = None
        if self.document and self.wall.wall_type:
            wall_type = self.document.get_wall_type(self.wall.wall_type)

        # Find connected walls at each endpoint for corner processing
        start_connections = []
        end_connections = []
        if self.document:
            # Check start endpoint
            start_walls = self.document.get_walls_at_point(x1, z1, tolerance=50)
            for wall_idx, endpoint in start_walls:
                if wall_idx != self.wall.index:
                    other_wall = self.document.walls[wall_idx]
                    start_connections.append((other_wall, endpoint))

            # Check end endpoint
            end_walls = self.document.get_walls_at_point(x2, z2, tolerance=50)
            for wall_idx, endpoint in end_walls:
                if wall_idx != self.wall.index:
                    other_wall = self.document.walls[wall_idx]
                    end_connections.append((other_wall, endpoint))

        if wall_type and wall_type.layers and self._layer_items:
            # Layers are drawn by individual WallLayerItem objects
            # WallItem only draws selection highlight (below)
            pass
        elif wall_type and wall_type.layers:
            # Fallback: Draw layers directly (shouldn't happen normally)
            total_thickness = wall_type.total_thickness
            current_offset = -total_thickness / 2

            for layer in wall_type.layers:
                layer_start = current_offset
                layer_end = current_offset + layer.thickness

                p1 = QPointF(x1 + px * layer_end, z1 + pz * layer_end)
                p2 = QPointF(x1 + px * layer_start, z1 + pz * layer_start)
                p3 = QPointF(x2 + px * layer_start, z2 + pz * layer_start)
                p4 = QPointF(x2 + px * layer_end, z2 + pz * layer_end)

                path = QPainterPath()
                path.moveTo(p1)
                path.lineTo(p2)
                path.lineTo(p3)
                path.lineTo(p4)
                path.closeSubpath()

                r, g, b, a = layer.color
                fill_color = QColor(int(r * 255), int(g * 255), int(b * 255), int(a * 255))
                painter.fillPath(path, QBrush(fill_color))

                pen = QPen(Qt.GlobalColor.darkGray)
                pen.setWidth(1)
                painter.setPen(pen)
                painter.drawPath(path)

                current_offset = layer_end
        else:
            # Fallback: simple single-color wall
            half_thick = self.thickness / 2
            p1 = QPointF(x1 + px * half_thick, z1 + pz * half_thick)
            p2 = QPointF(x1 - px * half_thick, z1 - pz * half_thick)
            p3 = QPointF(x2 - px * half_thick, z2 - pz * half_thick)
            p4 = QPointF(x2 + px * half_thick, z2 + pz * half_thick)

            path = QPainterPath()
            path.moveTo(p1)
            path.lineTo(p2)
            path.lineTo(p3)
            path.lineTo(p4)
            path.closeSubpath()

            # Choose color based on category
            if self.wall.category == "exterior":
                fill_color = self._color_exterior
            elif self.wall.category == "wet_wall":
                fill_color = self._color_wet
            else:
                fill_color = self._color_interior

            painter.fillPath(path, QBrush(fill_color))

            pen = QPen(Qt.GlobalColor.black)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawPath(path)

        # Draw selection highlight
        if self.isSelected():
            # Draw outer boundary highlight
            total_thick = wall_type.total_thickness if wall_type else self.thickness
            half = total_thick / 2
            p1 = QPointF(x1 + px * half, z1 + pz * half)
            p2 = QPointF(x1 - px * half, z1 - pz * half)
            p3 = QPointF(x2 - px * half, z2 - pz * half)
            p4 = QPointF(x2 + px * half, z2 + pz * half)

            sel_path = QPainterPath()
            sel_path.moveTo(p1)
            sel_path.lineTo(p2)
            sel_path.lineTo(p3)
            sel_path.lineTo(p4)
            sel_path.closeSubpath()

            pen = QPen(self._color_selection)
            pen.setWidth(3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(sel_path)


class DoorItem(QGraphicsItem):
    """Graphics item representing a door."""

    def __init__(self, door: Door, walls: List[Wall], document=None, parent=None):
        super().__init__(parent)
        self.door = door
        self.walls = walls
        self.document = document
        self._wall: Optional[Wall] = None
        self._grips: List[GripItem] = []

        if 0 <= door.wall_index < len(walls):
            self._wall = walls[door.wall_index]

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def _create_grips(self):
        """Create center grip for moving door along wall."""
        self._remove_grips()
        pos = self._get_position()

        grip = GripItem('center', self, self._on_grip_moved)
        grip.setPos(pos)
        self.scene().addItem(grip)
        self._grips.append(grip)

    def _remove_grips(self):
        for grip in self._grips:
            if grip.scene():
                grip.scene().removeItem(grip)
        self._grips.clear()

    def _on_grip_moved(self, grip_type: str, new_pos: QPointF):
        """Move door along wall based on grip position."""
        if not self._wall:
            return

        # Project new position onto wall line
        x1, z1 = self._wall.start[0], self._wall.start[2]
        x2, z2 = self._wall.end[0], self._wall.end[2]
        wall_len = self._wall.length

        # Vector from wall start to new pos
        vx, vz = new_pos.x() - x1, new_pos.y() - z1
        # Wall direction
        dx, dz = x2 - x1, z2 - z1

        # Project onto wall (dot product / length)
        new_offset = (vx * dx + vz * dz) / wall_len if wall_len > 0 else 0
        new_offset = max(0, min(wall_len, new_offset))

        if self.document:
            self.document.modify_door(self.door.index, offset=new_offset)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                self._create_grips()
            else:
                self._remove_grips()
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        if not self._wall:
            return QRectF()

        pos = self._get_position()
        margin = 200
        return QRectF(pos.x() - margin, pos.y() - margin, margin * 2, margin * 2)

    def _get_position(self) -> QPointF:
        """Calculate door position along wall."""
        if not self._wall:
            return QPointF(0, 0)

        x1, z1 = self._wall.start[0], self._wall.start[2]
        x2, z2 = self._wall.end[0], self._wall.end[2]

        # Parametric position along wall
        t = self.door.offset / self._wall.length if self._wall.length > 0 else 0
        x = x1 + (x2 - x1) * t
        z = z1 + (z2 - z1) * t

        return QPointF(x, z)

    def paint(self, painter: QPainter, option, widget):
        """Paint the door."""
        if not self._wall:
            return

        pos = self._get_position()

        # Calculate wall direction
        dx = self._wall.end[0] - self._wall.start[0]
        dz = self._wall.end[2] - self._wall.start[2]
        length = (dx**2 + dz**2) ** 0.5
        if length == 0:
            return

        # Unit vectors
        ux, uz = dx / length, dz / length  # Along wall
        px, pz = -uz, ux  # Perpendicular

        # Door opening (gap in wall)
        half_width = self.door.width / 2

        # Draw door opening as white rectangle (gap)
        pen = QPen(QColor("#1a1a2e"))  # Background color
        pen.setWidth(160)  # Wall thickness
        painter.setPen(pen)
        painter.drawLine(
            QPointF(pos.x() - ux * half_width, pos.y() - uz * half_width),
            QPointF(pos.x() + ux * half_width, pos.y() + uz * half_width)
        )

        # Draw door swing arc
        pen = QPen(Qt.GlobalColor.cyan if self.isSelected() else Qt.GlobalColor.darkGray)
        pen.setWidth(2)
        painter.setPen(pen)

        # Door panel line
        swing_dir = 1 if "left" in self.door.swing else -1
        panel_end = QPointF(
            pos.x() + px * self.door.width * swing_dir,
            pos.y() + pz * self.door.width * swing_dir
        )
        painter.drawLine(pos, panel_end)

        # Swing arc
        painter.drawArc(
            QRectF(
                pos.x() - self.door.width,
                pos.y() - self.door.width,
                self.door.width * 2,
                self.door.width * 2
            ),
            0, 90 * 16  # Start angle, span (in 1/16 degree units)
        )


class WindowItem(QGraphicsItem):
    """Graphics item representing a window."""

    def __init__(self, window: Window, walls: List[Wall], document=None, parent=None):
        super().__init__(parent)
        self.window = window
        self.walls = walls
        self.document = document
        self._wall: Optional[Wall] = None
        self._grips: List[GripItem] = []

        if 0 <= window.wall_index < len(walls):
            self._wall = walls[window.wall_index]

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def _create_grips(self):
        """Create center grip for moving window along wall."""
        self._remove_grips()
        pos = self._get_position()

        grip = GripItem('center', self, self._on_grip_moved)
        grip.setPos(pos)
        self.scene().addItem(grip)
        self._grips.append(grip)

    def _remove_grips(self):
        for grip in self._grips:
            if grip.scene():
                grip.scene().removeItem(grip)
        self._grips.clear()

    def _on_grip_moved(self, grip_type: str, new_pos: QPointF):
        """Move window along wall based on grip position."""
        if not self._wall:
            return

        x1, z1 = self._wall.start[0], self._wall.start[2]
        x2, z2 = self._wall.end[0], self._wall.end[2]
        wall_len = self._wall.length

        vx, vz = new_pos.x() - x1, new_pos.y() - z1
        dx, dz = x2 - x1, z2 - z1

        new_offset = (vx * dx + vz * dz) / wall_len if wall_len > 0 else 0
        new_offset = max(0, min(wall_len, new_offset))

        if self.document:
            self.document.modify_window(self.window.index, offset=new_offset)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                self._create_grips()
            else:
                self._remove_grips()
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle."""
        if not self._wall:
            return QRectF()

        pos = self._get_position()
        margin = 200
        return QRectF(pos.x() - margin, pos.y() - margin, margin * 2, margin * 2)

    def _get_position(self) -> QPointF:
        """Calculate window position along wall."""
        if not self._wall:
            return QPointF(0, 0)

        x1, z1 = self._wall.start[0], self._wall.start[2]
        x2, z2 = self._wall.end[0], self._wall.end[2]

        t = self.window.offset / self._wall.length if self._wall.length > 0 else 0
        x = x1 + (x2 - x1) * t
        z = z1 + (z2 - z1) * t

        return QPointF(x, z)

    def paint(self, painter: QPainter, option, widget):
        """Paint the window."""
        if not self._wall:
            return

        pos = self._get_position()

        # Calculate wall direction
        dx = self._wall.end[0] - self._wall.start[0]
        dz = self._wall.end[2] - self._wall.start[2]
        length = (dx**2 + dz**2) ** 0.5
        if length == 0:
            return

        ux, uz = dx / length, dz / length
        px, pz = -uz, ux

        half_width = self.window.width / 2
        thickness = 80

        # Draw window opening (gap)
        pen = QPen(QColor("#1a1a2e"))
        pen.setWidth(160)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(pos.x() - ux * half_width, pos.y() - uz * half_width),
            QPointF(pos.x() + ux * half_width, pos.y() + uz * half_width)
        )

        # Draw window frame (two parallel lines)
        pen = QPen(Qt.GlobalColor.cyan if self.isSelected() else QColor("#4080ff"))
        pen.setWidth(3)
        painter.setPen(pen)

        # Glass lines
        for side in [-1, 1]:
            offset = thickness * 0.3 * side
            p1 = QPointF(
                pos.x() - ux * half_width + px * offset,
                pos.y() - uz * half_width + pz * offset
            )
            p2 = QPointF(
                pos.x() + ux * half_width + px * offset,
                pos.y() + uz * half_width + pz * offset
            )
            painter.drawLine(p1, p2)


class PlanView(BaseView):
    """
    Main 2D floor plan view.
    Central editing workspace.
    """

    selection_changed = pyqtSignal(list)  # List of selected item indices

    def __init__(self, document: ArchDocument, config: Config, parent=None):
        super().__init__(document, config, parent)

        # Item collections
        self._wall_items: List[WallItem] = []
        self._door_items: List[DoorItem] = []
        self._window_items: List[WindowItem] = []
        self._room_labels: List[RoomLabelItem] = []

        # Snap system
        self._snap_manager = SnapManager(document, config)
        self._snap_indicator = SnapIndicator()
        self.scene.addItem(self._snap_indicator)

        # Tool manager (created after view is ready)
        self._tool_manager = None

        # Connect to document changes
        self.document.document_changed.connect(self.refresh)
        event_bus.element_modified.connect(self._on_element_modified)

        # Set large scene rect for unlimited panning
        self.scene.setSceneRect(-1000000, -1000000, 2000000, 2000000)

        # Initial scale (1mm = 0.05 pixels by default, inverted)
        self.scale(config.default_scale, config.default_scale)
        self._zoom = config.default_scale

        # Enable mouse tracking for tool preview
        self.setMouseTracking(True)

    def set_tool_manager(self, tool_manager):
        """Set the tool manager."""
        self._tool_manager = tool_manager

    @property
    def tool_manager(self):
        """Get tool manager."""
        return self._tool_manager

    def refresh(self):
        """Rebuild the entire view from document data."""
        # Clear existing items
        for item in self._wall_items:
            # Remove layer items first
            if hasattr(item, 'remove_layer_items'):
                item.remove_layer_items()
            # Remove grips
            if hasattr(item, '_remove_grips'):
                item._remove_grips()
            self.scene.removeItem(item)
        for item in self._door_items:
            if hasattr(item, '_remove_grips'):
                item._remove_grips()
            self.scene.removeItem(item)
        for item in self._window_items:
            if hasattr(item, '_remove_grips'):
                item._remove_grips()
            self.scene.removeItem(item)
        for item in self._room_labels:
            self.scene.removeItem(item)

        self._wall_items.clear()
        self._door_items.clear()
        self._window_items.clear()
        self._room_labels.clear()

        # Add walls
        for wall in self.document.walls:
            item = WallItem(wall, document=self.document,
                           snap_manager=self._snap_manager,
                           snap_indicator=self._snap_indicator,
                           config=self.config)
            self.scene.addItem(item)
            self._wall_items.append(item)

            # Create individual layer items for this wall
            item.create_layer_items(self.scene)

        # Add doors
        for door in self.document.doors:
            item = DoorItem(door, self.document.walls, document=self.document)
            self.scene.addItem(item)
            self._door_items.append(item)

        # Add windows
        for window in self.document.windows:
            item = WindowItem(window, self.document.walls, document=self.document)
            self.scene.addItem(item)
            self._window_items.append(item)

        # Add room labels
        for room_id, room in self.document.rooms.items():
            label = RoomLabelItem(room)
            self.scene.addItem(label)
            self._room_labels.append(label)

        self.viewport().update()

    def _on_element_modified(self, element_type: str, element_id: str, changes: dict):
        """Handle element modification."""
        idx = int(element_id) if element_id.isdigit() else -1

        if element_type == "wall" and 0 <= idx < len(self._wall_items):
            wall_item = self._wall_items[idx]
            # Update grip positions if selected
            if wall_item.isSelected() and wall_item._grips:
                x1, z1 = wall_item.wall.start[0], wall_item.wall.start[2]
                x2, z2 = wall_item.wall.end[0], wall_item.wall.end[2]
                cx, cz = (x1 + x2) / 2, (z1 + z2) / 2
                for grip in wall_item._grips:
                    if grip.grip_type == 'start':
                        grip.setPos(x1, z1)
                    elif grip.grip_type == 'end':
                        grip.setPos(x2, z2)
                    elif grip.grip_type == 'center':
                        grip.setPos(cx, cz)
            wall_item.prepareGeometryChange()
            wall_item.update()

        elif element_type == "door" and 0 <= idx < len(self._door_items):
            door_item = self._door_items[idx]
            door_item.prepareGeometryChange()
            door_item.update()
            # Update grip position
            if door_item.isSelected() and door_item._grips:
                pos = door_item._get_position()
                for grip in door_item._grips:
                    grip.setPos(pos)

        elif element_type == "window" and 0 <= idx < len(self._window_items):
            window_item = self._window_items[idx]
            window_item.prepareGeometryChange()
            window_item.update()
            if window_item.isSelected() and window_item._grips:
                pos = window_item._get_position()
                for grip in window_item._grips:
                    grip.setPos(pos)

        self.scene.update()
        self.viewport().update()

    def get_selected_walls(self) -> List[int]:
        """Get indices of selected walls."""
        return [
            i for i, item in enumerate(self._wall_items)
            if item.isSelected()
        ]

    def get_selected_doors(self) -> List[int]:
        """Get indices of selected doors."""
        return [
            i for i, item in enumerate(self._door_items)
            if item.isSelected()
        ]

    def get_selected_windows(self) -> List[int]:
        """Get indices of selected windows."""
        return [
            i for i, item in enumerate(self._window_items)
            if item.isSelected()
        ]

    # =========================================================================
    # Mouse Event Forwarding to Tools
    # =========================================================================

    def mousePressEvent(self, event):
        """Forward mouse press to active tool."""
        # Check for middle button pan first
        if event.button() == Qt.MouseButton.MiddleButton:
            super().mousePressEvent(event)
            return

        scene_pos = self.mapToScene(event.position().toPoint())

        # Check if clicking on a grip - let QGraphicsView handle it
        item = self.scene.itemAt(scene_pos, self.transform())
        if isinstance(item, GripItem):
            super().mousePressEvent(event)
            return

        # For non-grip items, let QGraphicsView handle selection first
        super().mousePressEvent(event)

        # Then also notify tool (for custom handling)
        if self._tool_manager and self._tool_manager.active_tool:
            self._tool_manager.active_tool.mouse_press(event, scene_pos)

    def mouseMoveEvent(self, event):
        """Forward mouse move to active tool."""
        # Check for panning first
        if self._panning:
            super().mouseMoveEvent(event)
            return

        # Check if a grip is being dragged - let Qt handle it
        grabber = self.scene.mouseGrabberItem()
        if isinstance(grabber, GripItem):
            super().mouseMoveEvent(event)
            # Still update status bar
            scene_pos = self.mapToScene(event.position().toPoint())
            event_bus.status_message.emit(
                f"X: {scene_pos.x():.0f}mm  Y: {scene_pos.y():.0f}mm",
                0
            )
            return

        # Forward to tool
        if self._tool_manager and self._tool_manager.active_tool:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._tool_manager.active_tool.mouse_move(event, scene_pos)

        # Update status bar with coordinates
        scene_pos = self.mapToScene(event.position().toPoint())
        event_bus.status_message.emit(
            f"X: {scene_pos.x():.0f}mm  Y: {scene_pos.y():.0f}mm",
            0
        )

    def mouseReleaseEvent(self, event):
        """Forward mouse release to active tool."""
        if event.button() == Qt.MouseButton.MiddleButton:
            super().mouseReleaseEvent(event)
            return

        # Check if a grip was being dragged - let Qt handle it
        grabber = self.scene.mouseGrabberItem()
        if isinstance(grabber, GripItem):
            super().mouseReleaseEvent(event)
            return

        # Check if click was on a grip
        scene_pos = self.mapToScene(event.position().toPoint())
        item = self.scene.itemAt(scene_pos, self.transform())
        if isinstance(item, GripItem):
            super().mouseReleaseEvent(event)
            return

        if self._tool_manager and self._tool_manager.active_tool:
            self._tool_manager.active_tool.mouse_release(event, scene_pos)
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Forward double click to active tool."""
        if self._tool_manager and self._tool_manager.active_tool:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._tool_manager.active_tool.mouse_double_click(event, scene_pos)
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Forward key press to active tool."""
        if self._tool_manager and self._tool_manager.active_tool:
            self._tool_manager.active_tool.key_press(event)

            # Check if tool handled escape
            if event.key() == Qt.Key.Key_Escape:
                return

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Forward key release to active tool."""
        if self._tool_manager and self._tool_manager.active_tool:
            self._tool_manager.active_tool.key_release(event)
        super().keyReleaseEvent(event)
