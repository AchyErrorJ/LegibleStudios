"""
UE5 Standalone Launcher for ArchEngine CAD

Manages spawning and controlling the UE5 standalone renderer process.
"""
import subprocess
import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


@dataclass
class UE5LaunchConfig:
    """Configuration for launching UE5 standalone."""
    # Path to packaged executable or project
    executable_path: Optional[Path] = None
    project_path: Optional[Path] = None

    # Window settings
    resolution: tuple = (1920, 1080)
    windowed: bool = True
    borderless: bool = False

    # Rendering
    vsync: bool = True
    max_fps: int = 60

    # Map to load
    map_name: str = "test1"

    # Logging
    log_file: Optional[Path] = None
    verbose: bool = False


class UE5Launcher(QObject):
    """
    Launches and manages UE5 standalone process.

    Signals:
        started: UE5 process started
        stopped: UE5 process stopped
        error: Error occurred (message)
        ready: UE5 is ready for connections

    Usage:
        launcher = UE5Launcher()
        launcher.config.executable_path = Path("path/to/ArchEngine.exe")
        launcher.start()

        # Wait for ready signal, then connect viewport
        launcher.ready.connect(lambda: viewport.connect_to_ue5())
    """

    started = pyqtSignal()
    stopped = pyqtSignal()
    error = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = UE5LaunchConfig()
        self._process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stopping = False

        # Timer to check for readiness
        self._ready_timer = QTimer(self)
        self._ready_timer.timeout.connect(self._check_ready)
        self._ready_check_attempts = 0

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def find_ue5_paths(self) -> dict:
        """Find UE5 installation and project paths."""
        paths = {
            'editor': None,
            'project': None,
            'packaged': None
        }

        # Check for project in expected location
        project_candidates = [
            Path("X:/ARCH/Software/ArchEngine_suite_ue5/ArchEngine_Viewer/ArchEngine/ArchEngine.uproject"),
            Path(__file__).parent.parent.parent / "ArchEngine_Viewer" / "ArchEngine" / "ArchEngine.uproject",
        ]

        for p in project_candidates:
            if p.exists():
                paths['project'] = p
                break

        # Check for packaged build
        packaged_candidates = [
            Path("X:/ARCH/Software/ArchEngine_suite_ue5/ArchEngine_Viewer/ArchEngine/Binaries/Win64/ArchEngine.exe"),
            Path(__file__).parent.parent.parent / "ArchEngine_Viewer" / "Binaries" / "ArchEngine.exe",
        ]

        for p in packaged_candidates:
            if p.exists():
                paths['packaged'] = p
                break

        # Find UE5 editor
        ue5_candidates = [
            Path("A:/Applications/Epic Games/UE_5.3/Engine/Binaries/Win64/UnrealEditor.exe"),
            Path("C:/Program Files/Epic Games/UE_5.3/Engine/Binaries/Win64/UnrealEditor.exe"),
        ]

        for p in ue5_candidates:
            if p.exists():
                paths['editor'] = p
                break

        return paths

    def start(self) -> bool:
        """Start UE5 process."""
        if self.is_running:
            print("[UE5Launcher] Already running")
            return True

        # Build command line
        cmd = self._build_command()
        if not cmd:
            self.error.emit("Failed to build launch command - check paths")
            return False

        print(f"[UE5Launcher] Starting: {' '.join(str(c) for c in cmd)}")

        try:
            # Start process
            self._stopping = False
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if self.config.verbose else subprocess.DEVNULL,
                stderr=subprocess.PIPE if self.config.verbose else subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )

            # Start monitor thread
            self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
            self._monitor_thread.start()

            # Start ready check
            self._ready_check_attempts = 0
            self._ready_timer.start(500)  # Check every 500ms

            self.started.emit()
            return True

        except Exception as e:
            self.error.emit(f"Failed to start UE5: {e}")
            return False

    def stop(self):
        """Stop UE5 process."""
        if not self.is_running:
            return

        print("[UE5Launcher] Stopping UE5...")
        self._stopping = True
        self._ready_timer.stop()

        try:
            # Try graceful shutdown first
            if os.name == 'nt':
                self._process.terminate()
            else:
                self._process.send_signal(subprocess.signal.SIGTERM)

            # Wait up to 5 seconds
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("[UE5Launcher] Force killing...")
                self._process.kill()
                self._process.wait()

        except Exception as e:
            print(f"[UE5Launcher] Error stopping: {e}")

        self._process = None
        self.stopped.emit()

    def _build_command(self) -> list:
        """Build the command line for launching UE5."""
        cmd = []

        # Determine executable
        if self.config.executable_path and self.config.executable_path.exists():
            # Use packaged build
            cmd.append(str(self.config.executable_path))
        elif self.config.project_path and self.config.project_path.exists():
            # Use editor with project
            paths = self.find_ue5_paths()
            if not paths['editor']:
                print("[UE5Launcher] UE5 editor not found")
                return []

            cmd.append(str(paths['editor']))
            cmd.append(str(self.config.project_path))
            cmd.append("-game")  # Run as game, not editor
        else:
            # Try to find paths automatically
            paths = self.find_ue5_paths()
            if paths['packaged']:
                cmd.append(str(paths['packaged']))
            elif paths['project'] and paths['editor']:
                cmd.append(str(paths['editor']))
                cmd.append(str(paths['project']))
                cmd.append("-game")
            else:
                print("[UE5Launcher] No UE5 executable or project found")
                return []

        # Window settings
        if self.config.windowed:
            cmd.append("-windowed")
            if self.config.borderless:
                cmd.append("-borderless")
        else:
            cmd.append("-fullscreen")

        # Resolution
        cmd.append(f"-ResX={self.config.resolution[0]}")
        cmd.append(f"-ResY={self.config.resolution[1]}")

        # Rendering
        if self.config.vsync:
            cmd.append("-vsync")
        if self.config.max_fps > 0:
            cmd.append(f"-fps={self.config.max_fps}")

        # Map
        if self.config.map_name:
            cmd.append(f"/Game/{self.config.map_name}")

        # Logging
        if self.config.log_file:
            cmd.append(f"-LOG={self.config.log_file}")
        if not self.config.verbose:
            cmd.append("-nosplash")
            cmd.append("-silent")

        return cmd

    def _monitor_process(self):
        """Monitor thread to watch for process exit."""
        if self._process:
            self._process.wait()

        if not self._stopping:
            print("[UE5Launcher] Process exited unexpectedly")
            QTimer.singleShot(0, self.stopped.emit)

    def _check_ready(self):
        """Check if UE5 is ready for connections."""
        self._ready_check_attempts += 1

        # Try to connect to the named pipe
        if os.name == 'nt':
            pipe_path = r"\\.\pipe\ArchEngine_Viewport"
            try:
                import ctypes
                handle = ctypes.windll.kernel32.CreateFileW(
                    pipe_path,
                    0x80000000,  # GENERIC_READ
                    0,
                    None,
                    3,  # OPEN_EXISTING
                    0,
                    None
                )
                if handle != -1:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    print("[UE5Launcher] UE5 ready (pipe available)")
                    self._ready_timer.stop()
                    self.ready.emit()
                    return
            except:
                pass

        # Timeout after 30 seconds
        if self._ready_check_attempts > 60:
            print("[UE5Launcher] Timeout waiting for UE5 ready")
            self._ready_timer.stop()
            # Still emit ready - might work anyway
            self.ready.emit()


# Global launcher instance
_launcher_instance: Optional[UE5Launcher] = None


def get_ue5_launcher() -> UE5Launcher:
    """Get or create the global UE5 launcher instance."""
    global _launcher_instance
    if _launcher_instance is None:
        _launcher_instance = UE5Launcher()
    return _launcher_instance
