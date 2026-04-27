# progress_state.py
"""Thread-safe progress state management for AI operations with SSE notification."""

import threading
import time
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum


class OperationType(Enum):
    ENHANCE = "enhance"
    UPSCALE = "upscale"
    INPAINT = "inpaint"
    SEGMENT = "segment"
    IDLE = "idle"


@dataclass
class ProgressState:
    """Thread-safe progress tracking for AI operations."""

    operation: OperationType = OperationType.IDLE
    stage: str = ""  # e.g., "Loading model", "Diffusion", "Saving"
    current_step: int = 0
    total_steps: int = 0
    current_tile: int = 0
    total_tiles: int = 0
    message: str = ""
    started_at: float = 0.0
    error: Optional[str] = None

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _subscribers: List[Callable] = field(default_factory=list, repr=False)

    def start(self, operation: OperationType, total_steps: int = 0, stage: str = "Starting"):
        """Start a new operation."""
        with self._lock:
            self.operation = operation
            self.stage = stage
            self.current_step = 0
            self.total_steps = total_steps
            self.current_tile = 0
            self.total_tiles = 0
            self.message = ""
            self.started_at = time.time()
            self.error = None
        self._notify()

    def update_step(self, step: int, message: str = ""):
        """Update current step progress."""
        with self._lock:
            self.current_step = step
            if message:
                self.message = message
        self._notify()

    def update_stage(self, stage: str, message: str = ""):
        """Update current stage name."""
        with self._lock:
            self.stage = stage
            if message:
                self.message = message
        self._notify()

    def update_tile(self, tile: int, total: int):
        """Update tile progress for upscaling."""
        with self._lock:
            self.current_tile = tile
            self.total_tiles = total
            self.message = f"Tile {tile}/{total}"
        self._notify()

    def set_total_steps(self, total: int):
        """Set total steps (useful when not known at start)."""
        with self._lock:
            self.total_steps = total
        self._notify()

    def complete(self, message: str = "Complete") -> float:
        """Mark operation as complete, returns elapsed time."""
        with self._lock:
            self.current_step = self.total_steps
            self.stage = "Complete"
            self.message = message
            elapsed = time.time() - self.started_at
        self._notify()
        return elapsed

    def fail(self, error: str):
        """Mark operation as failed."""
        with self._lock:
            self.error = error
            self.stage = "Error"
        self._notify()

    def reset(self):
        """Reset to idle state."""
        with self._lock:
            self.operation = OperationType.IDLE
            self.stage = ""
            self.current_step = 0
            self.total_steps = 0
            self.current_tile = 0
            self.total_tiles = 0
            self.message = ""
            self.error = None
        self._notify()

    def to_dict(self) -> Dict[str, Any]:
        """Get current state as dictionary."""
        with self._lock:
            elapsed = time.time() - self.started_at if self.started_at else 0
            percent = 0
            if self.total_steps > 0:
                percent = round(self.current_step / self.total_steps * 100)
            elif self.total_tiles > 0:
                percent = round(self.current_tile / self.total_tiles * 100)

            return {
                "operation": self.operation.value,
                "stage": self.stage,
                "step": self.current_step,
                "total_steps": self.total_steps,
                "tile": self.current_tile,
                "total_tiles": self.total_tiles,
                "message": self.message,
                "elapsed": round(elapsed, 1),
                "error": self.error,
                "percent": percent
            }

    def subscribe(self, callback: Callable):
        """Add a subscriber for progress updates."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable):
        """Remove a subscriber."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify(self):
        """Notify all subscribers of state change."""
        data = self.to_dict()
        for callback in self._subscribers[:]:  # Copy list to avoid mutation during iteration
            try:
                callback(data)
            except Exception:
                pass  # Don't let subscriber errors break progress


# Global singleton instance
progress = ProgressState()


def create_step_callback(total_steps: int):
    """Create a callback for diffusers pipeline progress.

    Compatible with diffusers callback_on_step_end signature.
    """
    def callback(pipe, step_index, timestep, callback_kwargs):
        progress.update_step(
            step_index + 1,
            f"Step {step_index + 1}/{total_steps}"
        )
        return callback_kwargs
    return callback


def create_simple_callback():
    """Create a simple step callback for progress reporting.

    Returns a function that takes (current, total) arguments.
    """
    def callback(current: int, total: int):
        progress.update_step(current, f"Step {current}/{total}")
    return callback


print("=== PROGRESS STATE MODULE LOADED ===")
