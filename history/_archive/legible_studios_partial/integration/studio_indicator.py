"""
Studio Indicator Widget - Visual indicator for active constraint studio.

Similar to LODIndicatorWidget but for constraint domains.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from ..core.studio_manager import StudioManager, StudioLevel, STUDIO_INFO


class StudioIndicatorWidget(QWidget):
    """
    Visual indicator showing current constraint studio.
    
    Displays as a horizontal bar with 5 segments, highlighting the current studio.
    """

    studio_changed = pyqtSignal(int, float)  # level, transition

    def __init__(self, studio_manager: StudioManager = None, parent=None):
        super().__init__(parent)

        self.studio_manager = studio_manager or StudioManager()
        self._current_focus = 0.5

        self.setMinimumSize(200, 60)
        self.setMaximumSize(400, 80)

        self.setToolTip(
            "Constraint Studios\n"
            "Interpret geometry through different lenses:\n"
            "1. Climate - Thermal, wind, solar\n"
            "2. Structural - Loads, spans\n"
            "3. Code - Egress, accessibility\n"
            "4. Cost - Budget, constructability\n"
            "5. Acoustic - Sound, isolation"
        )

    def set_focus(self, focus: float):
        """Update studio based on focus value (0-1)."""
        self._current_focus = focus
        new_studio = self.studio_manager.get_dominant_studio(focus)
        
        # Calculate transition to next studio
        opacities = self.studio_manager.calculate_all_opacities(focus)
        current_opacity = opacities[new_studio]
        
        # If not fully visible, we're transitioning
        transition = 1.0 - current_opacity if current_opacity < 1.0 else 0.0
        
        self.studio_changed.emit(int(new_studio), transition)
        self.update()

    def set_studio_level(self, level: int):
        """Set studio level directly."""
        if 1 <= level <= 5:
            studio_level = StudioLevel(level)
            self.studio_manager.set_studio_override(studio_level)
            self.studio_changed.emit(level, 0.0)
            self.update()

    def paintEvent(self, event):
        """Draw the studio indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Layout
        bar_height = 20
        bar_y = 25
        segment_width = (w - 40) / 5

        # Draw title
        painter.setPen(QPen(QColor(200, 200, 200)))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(0, 0, w, 20, Qt.AlignmentFlag.AlignCenter, "Constraint Studios")

        # Get current opacities
        opacities = self.studio_manager.calculate_all_opacities(self._current_focus)

        # Draw segments
        for i, level in enumerate(StudioLevel):
            x = 20 + i * segment_width
            info = STUDIO_INFO[level]
            color = QColor(*info.color)
            opacity = opacities[level]

            # Determine if this is the dominant studio
            is_dominant = opacity > 0.5

            # Draw segment
            if is_dominant:
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(color.lighter(120), 2))
            else:
                dim_color = QColor(color)
                dim_color.setAlpha(60)
                painter.setBrush(QBrush(dim_color))
                painter.setPen(QPen(QColor(80, 80, 80), 1))

            painter.drawRoundedRect(
                int(x), int(bar_y), int(segment_width - 4), int(bar_height), 3, 3
            )

            # Draw icon
            painter.setPen(QPen(QColor(220, 220, 220) if is_dominant else QColor(120, 120, 120)))
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                int(x), int(bar_y), int(segment_width - 4), int(bar_height),
                Qt.AlignmentFlag.AlignCenter,
                info.icon
            )

        # Draw current studio name
        dominant = self.studio_manager.get_dominant_studio(self._current_focus)
        info = STUDIO_INFO[dominant]
        painter.setPen(QPen(QColor(*info.color)))
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            0, h - 15, w, 15,
            Qt.AlignmentFlag.AlignCenter,
            f"{info.icon} {info.name}"
        )


class StudioControlWidget(QWidget):
    """Combined studio display with indicator and controls."""

    studio_changed = pyqtSignal(int, float)

    def __init__(self, studio_manager: StudioManager = None, parent=None):
        super().__init__(parent)

        self.studio_manager = studio_manager or StudioManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Studio indicator
        self.indicator = StudioIndicatorWidget(self.studio_manager)
        self.indicator.studio_changed.connect(self._on_studio_changed)
        layout.addWidget(self.indicator, alignment=Qt.AlignmentFlag.AlignCenter)

        # Info label
        self.info_label = QLabel("Environmental topology")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #888; font-size: 9px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # Constraint intensity slider
        intensity_layout = QHBoxLayout()
        intensity_layout.addWidget(QLabel("Intensity:"))
        self.intensity_label = QLabel("50%")
        intensity_layout.addWidget(self.intensity_label)
        layout.addLayout(intensity_layout)

    def _on_studio_changed(self, level: int, transition: float):
        """Handle studio change."""
        studio = StudioLevel(level)
        info = STUDIO_INFO[studio]
        self.info_label.setText(info.description)
        self.studio_changed.emit(level, transition)

    def set_focus(self, focus: float):
        """Update from focus value."""
        self.indicator.set_focus(focus)

    def set_studio_level(self, level: int):
        """Set studio level directly."""
        self.indicator.set_studio_level(level)

    def set_intensity(self, intensity: float):
        """Set constraint intensity."""
        self.studio_manager.constraint_intensity = intensity
        self.intensity_label.setText(f"{int(intensity * 100)}%")
