"""
example_integration.py - Example showing UE5 viewport integration in PyQt6

Run this to test the viewport widget standalone:
    python -m viewport.example_integration

Or integrate into your CAD app:
    from viewport import UE5ViewportWidget
    viewport = UE5ViewportWidget()
    layout.addWidget(viewport)
    viewport.connect_to_ue5("ArchEngine_Viewport")
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStatusBar, QSplitter, QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt

from viewport import UE5ViewportWidget


class ViewportTestWindow(QMainWindow):
    """Test window demonstrating UE5 viewport integration."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ArchEngine - UE5 Viewport Integration Test")
        self.setMinimumSize(1280, 720)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left panel - Controls
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)

        # Center - UE5 Viewport
        self.viewport = UE5ViewportWidget()
        self.viewport.connected.connect(self._on_connected)
        self.viewport.disconnected.connect(self._on_disconnected)
        self.viewport.texture_ready.connect(self._on_texture_ready)
        self.viewport.frame_updated.connect(self._on_frame_updated)
        splitter.addWidget(self.viewport)

        # Right panel - Info
        right_panel = self._create_info_panel()
        splitter.addWidget(right_panel)

        # Set splitter sizes (20% - 60% - 20%)
        splitter.setSizes([250, 780, 250])

        # Status bar
        self.statusBar().showMessage("Ready - Click 'Connect' to connect to UE5")

        # Frame counter
        self._frame_count = 0

    def _create_control_panel(self) -> QWidget:
        """Create the control panel."""
        panel = QGroupBox("Controls")
        layout = QVBoxLayout(panel)

        # Connection controls
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)

        self.pipe_name = QComboBox()
        self.pipe_name.setEditable(True)
        self.pipe_name.addItems([
            "ArchEngine_Viewport",
            "ArchEngine_Viewport_1",
            "ArchEngine_Viewport_2"
        ])
        conn_layout.addWidget(QLabel("Pipe Name:"))
        conn_layout.addWidget(self.pipe_name)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        conn_layout.addWidget(self.connect_btn)

        layout.addWidget(conn_group)

        # Info
        info_group = QGroupBox("Status")
        info_layout = QVBoxLayout(info_group)

        self.status_label = QLabel("Disconnected")
        self.resolution_label = QLabel("Resolution: -")
        self.fps_label = QLabel("FPS: -")

        info_layout.addWidget(self.status_label)
        info_layout.addWidget(self.resolution_label)
        info_layout.addWidget(self.fps_label)

        layout.addWidget(info_group)

        layout.addStretch()

        return panel

    def _create_info_panel(self) -> QWidget:
        """Create the info panel."""
        panel = QGroupBox("Information")
        layout = QVBoxLayout(panel)

        info_text = """
<h3>UE5 Viewport Integration</h3>

<p>This widget displays the UE5 rendered viewport
using shared GPU textures.</p>

<h4>Features:</h4>
<ul>
<li>Zero-copy GPU texture sharing</li>
<li>Up to 8K resolution support</li>
<li>TSR/DLSS/FSR upscaling</li>
<li>Full input forwarding</li>
</ul>

<h4>Usage:</h4>
<ol>
<li>Start UE5 with ArchTextureShareComponent</li>
<li>Click 'Connect' to establish connection</li>
<li>Interact with the 3D viewport</li>
</ol>

<h4>Controls:</h4>
<ul>
<li><b>RMB Drag:</b> Orbit camera</li>
<li><b>MMB Drag:</b> Pan camera</li>
<li><b>Scroll:</b> Zoom</li>
<li><b>LMB:</b> Select</li>
</ul>
"""
        label = QLabel(info_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(label)

        layout.addStretch()

        return panel

    def _toggle_connection(self):
        """Toggle connection to UE5."""
        if self.viewport.is_connected:
            self.viewport.disconnect_from_ue5()
        else:
            pipe_name = self.pipe_name.currentText()
            if self.viewport.connect_to_ue5(pipe_name):
                self.statusBar().showMessage(f"Connecting to {pipe_name}...")
            else:
                self.statusBar().showMessage("Failed to initiate connection")

    def _on_connected(self):
        """Handle connection established."""
        self.connect_btn.setText("Disconnect")
        self.status_label.setText("Connected")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.statusBar().showMessage("Connected to UE5")

    def _on_disconnected(self):
        """Handle disconnection."""
        self.connect_btn.setText("Connect")
        self.status_label.setText("Disconnected")
        self.status_label.setStyleSheet("color: red;")
        self.resolution_label.setText("Resolution: -")
        self.fps_label.setText("FPS: -")
        self.statusBar().showMessage("Disconnected from UE5")
        self._frame_count = 0

    def _on_texture_ready(self, width: int, height: int):
        """Handle texture ready."""
        self.resolution_label.setText(f"Resolution: {width}x{height}")
        self.statusBar().showMessage(f"Texture ready: {width}x{height}")

    def _on_frame_updated(self):
        """Handle frame update."""
        self._frame_count += 1
        if self._frame_count % 60 == 0:
            # Update FPS display every 60 frames
            self.fps_label.setText(f"Frames: {self._frame_count}")


def main():
    """Run the test application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ViewportTestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
