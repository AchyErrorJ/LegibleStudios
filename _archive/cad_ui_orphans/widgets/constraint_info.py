"""
Constraint Info Widget - Displays constraints for selected/hovered elements

Shows why elements are positioned where they are, enabling
intent-driven editing instead of manual geometry manipulation.
"""
from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen

from core.constraints import (
    ConstraintSystem, Constraint, ConstraintType,
    ConstraintStrength, CONSTRAINT_COLORS, STRENGTH_STYLES
)


class ConstraintBadge(QLabel):
    """A small badge showing a constraint type"""
    def __init__(self, constraint: Constraint, parent=None):
        super().__init__(parent)
        self.constraint = constraint
        self._update_display()

    def _update_display(self):
        color = CONSTRAINT_COLORS.get(self.constraint.type, "#888")
        strength = STRENGTH_STYLES.get(self.constraint.strength, "○")

        self.setText(f"{strength} {str(self.constraint)}")
        self.setStyleSheet(f"""
            QLabel {{
                background: {color}22;
                border: 1px solid {color};
                border-radius: 4px;
                padding: 4px 8px;
                color: {color};
                font-size: 10px;
            }}
        """)


class ConstraintInfoPanel(QWidget):
    """
    Floating panel showing constraints for selected/hovered element.

    Displays:
    - Element name and type
    - All constraints with descriptions
    - Color-coded by constraint type
    - Strength indicators (hard/soft/suggested)
    """
    edit_constraint = pyqtSignal(str, object)  # element_id, constraint

    def __init__(self, constraint_system: ConstraintSystem, parent=None):
        super().__init__(parent)
        self.constraint_system = constraint_system
        self._current_element_id: Optional[str] = None
        self._setup_ui()

        # Follow selection/constraint changes
        constraint_system.changed.connect(self._on_constraints_changed)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header = QLabel("Constraints")
        self.header.setStyleSheet("""
            QLabel {
                background: #2a2a2a;
                color: #ddd;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
        """)
        layout.addWidget(self.header)

        # Content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        layout.addWidget(self.content)

        # Style the panel
        self.setStyleSheet("""
            QWidget {
                background: #1e1e1e;
                border: 1px solid #444;
                border-radius: 6px;
            }
        """)

    def show_element_constraints(self, element_id: str, element_name: str = ""):
        """Show constraints for an element"""
        self._current_element_id = element_id

        # Update header
        display_name = element_name.replace("_", " ").title()
        self.header.setText(f"{display_name} - Constraints")

        # Clear and rebuild content
        self._clear_content()

        element_constraints = self.constraint_system.get_element_constraints(element_id)

        if not element_constraints.constraints:
            self._add_message("No constraints defined")
            return

        # Group constraints by type
        grouped = self._group_constraints(element_constraints.constraints)

        # Display grouped constraints
        for group_name, constraints in grouped.items():
            self._add_constraint_group(group_name, constraints)

        # Add "related elements" section
        related = self.constraint_system.get_all_related(element_id)
        if related:
            self._add_related_section(related)

        self.content_layout.addStretch()
        self.show()

    def _group_constraints(self, constraints: List[Constraint]) -> dict:
        """Group constraints by category"""
        groups = {
            "Connections": [],
            "Separation": [],
            "Size": [],
            "Position": [],
            "Other": []
        }

        for c in constraints:
            if c.type in [ConstraintType.CONNECTS_TO, ConstraintType.ATTACHED_TO, ConstraintType.OPEN_TO]:
                groups["Connections"].append(c)
            elif c.type in [ConstraintType.ISOLATED_FROM, ConstraintType.BUFFERED_FROM]:
                groups["Separation"].append(c)
            elif c.type in [ConstraintType.MIN_AREA, ConstraintType.MAX_AREA, ConstraintType.MIN_WIDTH, ConstraintType.MIN_DEPTH]:
                groups["Size"].append(c)
            elif c.type in [ConstraintType.FIXED_POSITION, ConstraintType.FIXED_SIZE]:
                groups["Position"].append(c)
            else:
                groups["Other"].append(c)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def _add_constraint_group(self, title: str, constraints: List[Constraint]):
        """Add a group of constraints"""
        if not constraints:
            return

        # Group header
        header = QLabel(title)
        header.setStyleSheet("color: #888; font-size: 9px; font-weight: bold;")
        self.content_layout.addWidget(header)

        # Constraints
        for c in constraints:
            badge = ConstraintBadge(c)
            self.content_layout.addWidget(badge)

    def _add_related_section(self, related: List[str]):
        """Add section showing related elements"""
        header = QLabel("Related To")
        header.setStyleSheet("color: #888; font-size: 9px; font-weight: bold; margin-top: 8px;")
        self.content_layout.addWidget(header)

        for rel_id in related[:10]:  # Limit to 10
            label = QLabel(rel_id.replace("_", " ").title())
            label.setStyleSheet("color: #6baaff; font-size: 10px; padding: 2px 8px;")
            self.content_layout.addWidget(label)

    def _add_message(self, message: str):
        """Add a message when no constraints"""
        label = QLabel(message)
        label.setStyleSheet("color: #666; font-style: italic; padding: 8px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(label)

    def _clear_content(self):
        """Clear all content"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_constraints_changed(self):
        """Handle constraint system changes"""
        if self._current_element_id:
            # Refresh display
            pass

    def clear(self):
        """Clear the display"""
        self._current_element_id = None
        self._clear_content()
        self.header.setText("Constraints")
        self.hide()


class ConstraintTooltip(QWidget):
    """
    Lightweight tooltip showing constraints on hover.

    Less intrusive than the full panel, shows quick info.
    """
    def __init__(self, constraint_system: ConstraintSystem, parent=None):
        super().__init__(parent)
        self.constraint_system = constraint_system
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._title = QLabel()
        self._title.setStyleSheet("font-weight: bold; color: #ddd;")
        layout.addWidget(self._title)

        self._constraints_label = QLabel()
        self._constraints_label.setWordWrap(True)
        self._constraints_label.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(self._constraints_label)

        # Style
        self.setStyleSheet("""
            QWidget {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)

    def show_constraints(self, element_id: str, element_name: str):
        """Show constraints for an element"""
        self._title.setText(element_name.replace("_", " ").title())

        element_constraints = self.constraint_system.get_element_constraints(element_id)

        if not element_constraints.constraints:
            self._constraints_label.setText("No constraints")
        else:
            # Show first few constraints
            text = "\n".join(str(c) for c in element_constraints.constraints[:5])
            if len(element_constraints.constraints) > 5:
                text += f"\n+ {len(element_constraints.constraints) - 5} more"
            self._constraints_label.setText(text)

        self.adjustSize()
        self.show()
