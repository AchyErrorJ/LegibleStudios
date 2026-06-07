"""
Static Map Widget for PyQt6
============================
Fetches satellite imagery from Google Maps Static API and displays it
with drawing capability - no QWebEngine required.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QBrush, QPen, QColor, QFont, QMouseEvent, QPixmap, QImage
import requests
from io import BytesIO


class StaticMapWidget(QWidget):
    """Widget for displaying satellite imagery with drawing capability."""

    # Signals
    boundary_changed = pyqtSignal(float, float, float, float)  # lat_min, lat_max, lng_min, lng_max

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(400)

        # Map state
        self._center_lat = 45.4215
        self._center_lng = -75.6972
        self._zoom = 18
        self._map_size = 640  # pixels
        self._api_key = ""

        # Map image
        self._map_pixmap = None
        self._loading = False

        # Drawing state
        self._drawing = False
        self._points = []  # List of QPointF for boundary
        self._closed = False

        # Corner handles for editing
        self._corner_size = 10
        self._dragging_point = None  # Index of point being dragged
        self._dragging_corner = None  # For resizing entire boundary

    def set_api_key(self, api_key: str):
        """Set Google Maps API key."""
        self._api_key = api_key
        self._fetch_map()

    def set_location(self, lat: float, lng: float, zoom: int = 18):
        """Set map center and zoom level."""
        self._center_lat = lat
        self._center_lng = lng
        self._zoom = zoom
        self._fetch_map()

    def clear_boundary(self):
        """Clear the drawn boundary."""
        self._points = []
        self._closed = False
        self.update()

    def paintEvent(self, event):
        """Paint the map and boundary."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        if self._map_pixmap:
            # Scale map to fit widget
            scaled_pixmap = self._map_pixmap.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            x_offset = (self.width() - scaled_pixmap.width()) // 2
            y_offset = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
            self._map_rect = QRectF(x_offset, y_offset, scaled_pixmap.width(), scaled_pixmap.height())
        else:
            painter.fillRect(self.rect(), QColor(220, 220, 220))
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("Arial", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Enter API key and location above\nClick 'Load Map' to fetch satellite imagery")

        # Draw boundary if we have points
        if self._points:
            # Convert points to screen coordinates
            screen_points = self._latlng_to_screen(self._points)

            if len(screen_points) >= 2:
                # Draw polygon
                painter.setPen(QPen(QColor(34, 139, 34), 2))
                painter.setBrush(QBrush(QColor(76, 175, 80, 50)))

                if self._closed:
                    painter.drawPolygon(*screen_points)
                else:
                    for i in range(len(screen_points) - 1):
                        painter.drawLine(screen_points[i], screen_points[i + 1])

                # Draw corner handles
                painter.setPen(QPen(QColor(33, 150, 243), 2))
                painter.setBrush(QBrush(QColor(255, 255, 255)))

                for point in screen_points:
                    handle = QRectF(
                        point.x() - self._corner_size / 2,
                        point.y() - self._corner_size / 2,
                        self._corner_size,
                        self._corner_size
                    )
                    painter.drawRect(handle)

        # Draw loading indicator
        if self._loading:
            painter.setPen(QColor(66, 66, 66))
            painter.setFont(QFont("Arial", 12))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Loading map...")

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - start drawing or dragging."""
        if not self._map_pixmap:
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()

            # Check if clicking on existing point
            screen_points = self._latlng_to_screen(self._points)
            for i, sp in enumerate(screen_points):
                if (pos - sp).manhattanLength() < self._corner_size * 1.5:
                    self._dragging_point = i
                    return

            # If not clicking on point and boundary is closed, start new boundary
            if self._closed:
                self._points = []
                self._closed = False
                self._update_boundary()

            # Add new point
            latlng = self._screen_to_latlng(pos)
            self._points.append(latlng)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move - drag point."""
        if not self._map_pixmap:
            return

        if self._dragging_point is not None and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.position()
            latlng = self._screen_to_latlng(pos)
            self._points[self._dragging_point] = latlng
            self._update_boundary()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release - stop dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_point = None

    def _fetch_map(self):
        """Fetch map from Google Maps Static API."""
        if not self._api_key:
            self._loading = False
            self.update()
            return

        self._loading = True
        self.update()

        # Build URL for Google Maps Static API
        url = f"https://maps.googleapis.com/maps/api/staticmap"
        params = {
            "center": f"{self._center_lat},{self._center_lng}",
            "zoom": self._zoom,
            "size": f"{self._map_size}x{self._map_size}",
            "maptype": "satellite",
            "key": self._api_key
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                # Load image from response
                image_data = BytesIO(response.content)
                self._map_pixmap = QPixmap.fromImage(QImage.fromData(image_data.read()))
                print(f"[StaticMapWidget] Map loaded successfully")
            else:
                print(f"[StaticMapWidget] Error loading map: HTTP {response.status_code}")
                self._map_pixmap = None

        except Exception as e:
            print(f"[StaticMapWidget] Error loading map: {e}")
            self._map_pixmap = None

        self._loading = False
        self.update()

    def _latlng_to_screen(self, points):
        """Convert lat/lng points to screen coordinates."""
        if not self._map_pixmap or not hasattr(self, '_map_rect'):
            return points

        screen_points = []
        for lat, lng in points:
            # Calculate pixel position in map image
            # This is approximate - for precise conversion we'd need proper projection math
            x_ratio = (lng - self._center_lng) / (360 / 2**self._zoom)
            y_ratio = (self._center_lat - lat) / (360 / 2**self._zoom)

            x = self._map_rect.center().x() + x_ratio * self._map_rect.width()
            y = self._map_rect.center().y() + y_ratio * self._map_rect.height()

            screen_points.append(QPointF(x, y))

        return screen_points

    def _screen_to_latlng(self, pos):
        """Convert screen coordinates to lat/lng."""
        if not self._map_pixmap or not hasattr(self, '_map_rect'):
            return (self._center_lat, self._center_lng)

        # Calculate ratio from center
        x_ratio = (pos.x() - self._map_rect.center().x()) / self._map_rect.width()
        y_ratio = (pos.y() - self._map_rect.center().y()) / self._map_rect.height()

        lng = self._center_lng + x_ratio * (360 / 2**self._zoom)
        lat = self._center_lat - y_ratio * (360 / 2**self._zoom)

        return (lat, lng)

    def _update_boundary(self):
        """Emit boundary changed signal."""
        if len(self._points) >= 2:
            lats = [p[0] for p in self._points]
            lngs = [p[1] for p in self._points]
            self.boundary_changed.emit(min(lats), max(lats), min(lngs), max(lngs))

    def get_boundary(self):
        """Get the current boundary coordinates."""
        if len(self._points) >= 2:
            lats = [p[0] for p in self._points]
            lngs = [p[1] for p in self._points]
            return {
                'lat_min': min(lats),
                'lat_max': max(lats),
                'lng_min': min(lngs),
                'lng_max': max(lngs),
                'points': self._points
            }
        return None
