"""
Base view class for all 2D views
"""
from abc import abstractmethod

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen

from core.document import ArchDocument
from app.config import Config


class BaseView(QGraphicsView):
    """
    Base class for all 2D views (plan, elevation, section).
    Provides common functionality like zoom, pan, grid.
    """

    def __init__(self, document: ArchDocument, config: Config, parent=None):
        super().__init__(parent)
        self.document = document
        self.config = config

        # Create scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # View settings
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # State
        self._zoom = 1.0
        self._min_zoom = 0.01
        self._max_zoom = 10.0
        self._panning = False
        self._last_pan_point = None
        self._grid_visible = config.grid_visible

        # Colors
        self._bg_color = QColor(self.config.background_color)
        self._grid_color = QColor(self.config.grid_color)

        self.setBackgroundBrush(self._bg_color)

    @property
    def zoom_level(self) -> float:
        """Get current zoom level."""
        return self._zoom

    def set_grid_visible(self, visible: bool):
        """Set grid visibility."""
        self._grid_visible = visible
        self.viewport().update()

    def zoom_in(self):
        """Zoom in by 25%."""
        self._zoom_by(1.25)

    def zoom_out(self):
        """Zoom out by 25%."""
        self._zoom_by(0.8)

    def zoom_fit(self):
        """Zoom to fit all content (items bounding rect)."""
        # Get bounding rect of all items, not the scene rect
        items_rect = self.scene.itemsBoundingRect()
        if items_rect.isNull() or items_rect.isEmpty():
            # No items, center on origin
            items_rect = QRectF(-5000, -5000, 10000, 10000)
        else:
            # Add some margin
            margin = min(items_rect.width(), items_rect.height()) * 0.1
            items_rect.adjust(-margin, -margin, margin, margin)

        self.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def _zoom_by(self, factor: float, center_on_mouse: bool = False, mouse_pos=None):
        """Zoom by a factor, optionally centering on mouse position."""
        new_zoom = self._zoom * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            if center_on_mouse and mouse_pos is not None:
                # Get scene position under cursor before zoom
                old_scene_pos = self.mapToScene(mouse_pos)

                # Apply zoom
                self._zoom = new_zoom
                self.scale(factor, factor)

                # Get new position of that scene point
                new_pos = self.mapFromScene(old_scene_pos)

                # Calculate delta and adjust scroll
                delta = new_pos - mouse_pos
                self.horizontalScrollBar().setValue(
                    self.horizontalScrollBar().value() + int(delta.x())
                )
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value() + int(delta.y())
                )
            else:
                self._zoom = new_zoom
                self.scale(factor, factor)

    @abstractmethod
    def refresh(self):
        """Refresh the view contents. Must be implemented by subclasses."""
        pass

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw background with optional grid."""
        # Fill background
        painter.fillRect(rect, self._bg_color)

        # Draw grid if visible
        if self._grid_visible:
            self._draw_grid(painter, rect)

    def _draw_grid(self, painter: QPainter, rect: QRectF):
        """Draw grid lines."""
        grid_size = self.config.grid_size

        # Get visible area
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)

        # Grid pen
        pen = QPen(self._grid_color)
        pen.setWidth(0)  # Cosmetic pen (1px regardless of zoom)
        painter.setPen(pen)

        # Draw vertical lines
        x = left
        while x <= rect.right():
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += grid_size

        # Draw horizontal lines
        y = top
        while y <= rect.bottom():
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += grid_size

    # =========================================================================
    # Mouse Events
    # =========================================================================

    def wheelEvent(self, event):
        """Handle mouse wheel for zooming - centers on cursor position."""
        mouse_pos = event.position().toPoint()
        if event.angleDelta().y() > 0:
            self._zoom_by(1.15, center_on_mouse=True, mouse_pos=mouse_pos)
        else:
            self._zoom_by(0.87, center_on_mouse=True, mouse_pos=mouse_pos)

    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Use Qt's built-in drag mode for smooth panning
            self._panning = True
            self._last_pan_point = event.position()
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Fake a left button press for the drag mode
            fake_event = type(event)(
                event.type(),
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mousePressEvent(fake_event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if self._panning:
            # Forward to Qt's drag handler
            super().mouseMoveEvent(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            # Fake a left button release for the drag mode
            fake_event = type(event)(
                event.type(),
                event.position(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mouseReleaseEvent(fake_event)
            self._panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            super().mouseReleaseEvent(event)
