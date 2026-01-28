#!/usr/bin/env python3
"""
ArchEngine 2D CAD Application
Main entry point
"""
import sys
from pathlib import Path

# Add the package directory to path for imports
_package_dir = Path(__file__).parent
if str(_package_dir) not in sys.path:
    sys.path.insert(0, str(_package_dir))

# CRITICAL: Initialize Qt WebEngine BEFORE QApplication
# Importing QtWebEngineWidgets triggers initialization (must happen before QApplication)
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    print("[Main] Qt WebEngine available and initialized")
    HAS_WEBENGINE = True
except ImportError as e:
    print(f"[Main] PyQt6-WebEngine not available: {e}")
    HAS_WEBENGINE = False

# Now import QApplication and other Qt modules
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.application import ArchEngineApplication
from app.config import Config


def main():
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("ArchEngine CAD")
    app.setOrganizationName("ArchEngine")
    app.setOrganizationDomain("archengine.dev")

    # Set default font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Load configuration
    config = Config()

    # Load stylesheet if exists
    style_path = Path(__file__).parent / "resources" / "styles" / "archengine.qss"
    if style_path.exists():
        app.setStyleSheet(style_path.read_text())

    # Create main application window
    arch_app = ArchEngineApplication(config)
    arch_app.show()

    # Load project from command line or last opened
    if len(sys.argv) > 1:
        arch_app.open_project(Path(sys.argv[1]))
    # TEMPORARILY DISABLED - don't auto-open last project
    # elif config.last_project and Path(config.last_project).exists():
    #     arch_app.open_project(Path(config.last_project))

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
