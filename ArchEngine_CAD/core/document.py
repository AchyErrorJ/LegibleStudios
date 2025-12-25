"""
ArchDocument - Central document model

Single source of truth for building data.
Wraps JSON building data with change tracking and signals.
"""
import json
import copy
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QUndoStack

from core.events import event_bus
from core.version_control import VersionControl


@dataclass
class Wall:
    """Wall data structure."""
    index: int
    start: Tuple[float, float, float]  # x, y, z
    end: Tuple[float, float, float]
    height: float = 2700
    category: str = "interior"  # exterior, interior, wet_wall
    wall_type: str = ""

    @property
    def start_2d(self) -> Tuple[float, float]:
        """Get 2D start point (X, Z)."""
        return (self.start[0], self.start[2])

    @property
    def end_2d(self) -> Tuple[float, float]:
        """Get 2D end point (X, Z)."""
        return (self.end[0], self.end[2])

    @property
    def length(self) -> float:
        """Calculate wall length."""
        dx = self.end[0] - self.start[0]
        dz = self.end[2] - self.start[2]
        return (dx**2 + dz**2) ** 0.5


@dataclass
class Door:
    """Door data structure."""
    index: int
    wall_index: int
    offset: float
    width: float = 914
    height: float = 2134
    door_type: str = "swing"
    swing: str = "left_in"


@dataclass
class Window:
    """Window data structure."""
    index: int
    wall_index: int
    offset: float
    width: float = 1200
    height: float = 1200
    sill_height: float = 900


@dataclass
class WallLayer:
    """Single layer of a wall assembly."""
    name: str
    material: str
    thickness: float  # mm
    function: str  # exterior_finish, membrane, sheathing, structure, insulation, interior_finish
    color: Tuple[float, float, float, float]  # RGBA 0-1
    r_value: float = 0.0


@dataclass
class WallType:
    """Wall type definition with layers."""
    id: str
    name: str
    layers: List[WallLayer]
    total_thickness: float = 0.0

    def __post_init__(self):
        self.total_thickness = sum(layer.thickness for layer in self.layers)


@dataclass
class Room:
    """Room data structure."""
    id: str
    name: str
    room_type: str
    bounds: Dict[str, float]  # x, y, width, height
    area: float = 0
    center: Optional[Dict[str, float]] = None


class ArchDocument(QObject):
    """
    Central document model - single source of truth.
    Wraps the JSON building data with change tracking.
    """

    # Signals
    document_changed = pyqtSignal()
    element_added = pyqtSignal(str, str)      # element_type, element_id
    element_modified = pyqtSignal(str, str)   # element_type, element_id
    element_removed = pyqtSignal(str, str)    # element_type, element_id

    def __init__(self, parent=None):
        super().__init__(parent)

        # Raw JSON data
        self._data: Dict[str, Any] = {}

        # File path
        self._file_path: Optional[Path] = None

        # Modified flag
        self._modified: bool = False

        # Undo stack
        self._undo_stack = QUndoStack(self)

        # Parsed elements (cached)
        self._walls: List[Wall] = []
        self._doors: List[Door] = []
        self._windows: List[Window] = []
        self._rooms: Dict[str, Room] = {}
        self._wall_types: Dict[str, WallType] = {}

        # Version control (git-based)
        self._version_control: Optional[VersionControl] = None

    @property
    def file_path(self) -> Optional[Path]:
        """Get current file path."""
        return self._file_path

    @property
    def modified(self) -> bool:
        """Check if document has unsaved changes."""
        return self._modified

    @property
    def undo_stack(self) -> QUndoStack:
        """Get undo stack."""
        return self._undo_stack

    @property
    def data(self) -> Dict[str, Any]:
        """Get raw JSON data."""
        return self._data

    @property
    def walls(self) -> List[Wall]:
        """Get parsed walls."""
        return self._walls

    @property
    def doors(self) -> List[Door]:
        """Get parsed doors."""
        return self._doors

    @property
    def windows(self) -> List[Window]:
        """Get parsed windows."""
        return self._windows

    @property
    def rooms(self) -> Dict[str, Room]:
        """Get parsed rooms."""
        return self._rooms

    @property
    def wall_types(self) -> Dict[str, WallType]:
        """Get parsed wall types."""
        return self._wall_types

    def get_wall_type(self, type_id: str) -> Optional[WallType]:
        """Get wall type by ID."""
        return self._wall_types.get(type_id)

    @property
    def building_width(self) -> float:
        """Get building width."""
        return self._data.get('width', 10000)

    @property
    def building_depth(self) -> float:
        """Get building depth."""
        return self._data.get('depth', 10000)

    # =========================================================================
    # File I/O
    # =========================================================================

    def new(self):
        """Create a new empty document."""
        self._data = {
            'building_id': 'new_building',
            'width': 10000,
            'depth': 10000,
            'building_type': 'residential',
            'walls_batch': [],
            'doors': [],
            'windows': [],
            'rooms': {},
            'roofs': [],
            'wall_types': []
        }
        self._file_path = None
        self._modified = False
        self._parse_data()
        self.document_changed.emit()
        event_bus.document_loaded.emit("")

    def load(self, file_path: Path) -> bool:
        """
        Load document from JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self._data = json.load(f)

            self._file_path = Path(file_path)
            self._modified = False
            self._parse_data()
            self._undo_stack.clear()

            # Initialize version control
            self._version_control = VersionControl(self._file_path)
            self._version_control.init()

            self.document_changed.emit()
            event_bus.document_loaded.emit(str(file_path))

            return True

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading file: {e}")
            return False

    def save(self, file_path: Optional[Path] = None) -> bool:
        """
        Save document to JSON file with git versioning.

        Args:
            file_path: Path to save to (uses current path if None)

        Returns:
            True if successful, False otherwise
        """
        save_path = Path(file_path) if file_path else self._file_path
        if not save_path:
            return False

        try:
            # Update data from parsed elements
            self._update_data()

            # Convert to JSON string
            content = json.dumps(self._data, indent=2)

            # Show changes summary before saving
            if self._version_control:
                summary = self._version_control.get_changes_summary(content)
                if summary:
                    changes = []
                    if summary['walls_modified']:
                        changes.append(f"{summary['walls_modified']} walls modified")
                    if summary['walls_added']:
                        changes.append(f"{summary['walls_added']} walls added")
                    if summary['walls_removed']:
                        changes.append(f"{summary['walls_removed']} walls removed")
                    if summary['doors_changed']:
                        changes.append(f"{summary['doors_changed']} doors changed")
                    if summary['windows_changed']:
                        changes.append(f"{summary['windows_changed']} windows changed")
                    if changes:
                        print(f"Saving changes: {', '.join(changes)}")

            # Write to file
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)

            # Commit to version control
            if self._version_control:
                self._version_control.commit(content)

            self._file_path = save_path
            self._modified = False

            event_bus.document_saved.emit(str(save_path))

            return True

        except IOError as e:
            print(f"Error saving file: {e}")
            return False

    def get_history(self) -> List[Dict]:
        """Get version history of current file."""
        if self._version_control:
            return self._version_control.get_history()
        return []

    def revert_to_version(self, commit_hash: str) -> bool:
        """Revert to a previous version."""
        if self._version_control:
            if self._version_control.revert_to(commit_hash):
                # Reload the file
                return self.load(self._file_path)
        return False

    # =========================================================================
    # Data Parsing
    # =========================================================================

    def _parse_data(self):
        """Parse JSON data into typed objects."""
        self._walls.clear()
        self._doors.clear()
        self._windows.clear()
        self._rooms.clear()
        self._wall_types.clear()

        # Parse wall types first (needed for wall thickness)
        for wt in self._data.get('wall_types', []):
            layers = []
            for layer_data in wt.get('layers', []):
                layer = WallLayer(
                    name=layer_data.get('name', ''),
                    material=layer_data.get('material', ''),
                    thickness=layer_data.get('thickness', 0),
                    function=layer_data.get('function', ''),
                    color=tuple(layer_data.get('color', [0.5, 0.5, 0.5, 1.0])),
                    r_value=layer_data.get('r_value', 0)
                )
                layers.append(layer)

            wall_type = WallType(
                id=wt.get('id', ''),
                name=wt.get('name', ''),
                layers=layers
            )
            self._wall_types[wall_type.id] = wall_type

        # Parse walls
        for i, w in enumerate(self._data.get('walls_batch', [])):
            wall = Wall(
                index=i,
                start=tuple(w.get('start', [0, 0, 0])),
                end=tuple(w.get('end', [0, 0, 0])),
                height=w.get('height', 2700),
                category=w.get('category', 'interior'),
                wall_type=w.get('wall_type', '')
            )
            self._walls.append(wall)

        # Parse doors
        for i, d in enumerate(self._data.get('doors', [])):
            door = Door(
                index=i,
                wall_index=d.get('wall_index', 0),
                offset=d.get('offset', 0),
                width=d.get('width', 914),
                height=d.get('height', 2134),
                door_type=d.get('type', 'swing'),
                swing=d.get('swing', 'left_in')
            )
            self._doors.append(door)

        # Parse windows
        for i, w in enumerate(self._data.get('windows', [])):
            window = Window(
                index=i,
                wall_index=w.get('wall_index', 0),
                offset=w.get('offset', 0),
                width=w.get('width', 1200),
                height=w.get('height', 1200),
                sill_height=w.get('sill_height', 900)
            )
            self._windows.append(window)

        # Parse rooms
        for room_id, r in self._data.get('rooms', {}).items():
            room = Room(
                id=room_id,
                name=r.get('name', room_id),
                room_type=r.get('room_type', 'room'),
                bounds=r.get('bounds', {'x': 0, 'y': 0, 'width': 0, 'height': 0}),
                area=r.get('area', 0),
                center=r.get('center')
            )
            self._rooms[room_id] = room

    def _update_data(self):
        """Update JSON data from parsed objects, preserving original fields."""
        # Update walls - preserve original data, only update modified fields
        original_walls = self._data.get('walls_batch', [])
        walls_batch = []
        for i, wall in enumerate(self._walls):
            # Start with original data if available (preserves extra fields)
            if i < len(original_walls):
                wall_data = copy.copy(original_walls[i])
            else:
                wall_data = {}
            # Update fields from our Wall dataclass
            wall_data['start'] = list(wall.start)
            wall_data['end'] = list(wall.end)
            wall_data['height'] = wall.height
            wall_data['category'] = wall.category
            wall_data['wall_type'] = wall.wall_type
            walls_batch.append(wall_data)
        self._data['walls_batch'] = walls_batch

        # Update doors - preserve original data
        original_doors = self._data.get('doors', [])
        doors = []
        for i, door in enumerate(self._doors):
            if i < len(original_doors):
                door_data = copy.copy(original_doors[i])
            else:
                door_data = {}
            door_data['wall_index'] = door.wall_index
            door_data['offset'] = door.offset
            door_data['width'] = door.width
            door_data['height'] = door.height
            door_data['type'] = door.door_type
            door_data['swing'] = door.swing
            doors.append(door_data)
        self._data['doors'] = doors

        # Update windows - preserve original data
        original_windows = self._data.get('windows', [])
        windows = []
        for i, window in enumerate(self._windows):
            if i < len(original_windows):
                window_data = copy.copy(original_windows[i])
            else:
                window_data = {}
            window_data['wall_index'] = window.wall_index
            window_data['offset'] = window.offset
            window_data['width'] = window.width
            window_data['height'] = window.height
            window_data['sill_height'] = window.sill_height
            windows.append(window_data)
        self._data['windows'] = windows

        # Update rooms
        rooms = {}
        for room_id, room in self._rooms.items():
            rooms[room_id] = {
                'name': room.name,
                'room_type': room.room_type,
                'bounds': room.bounds,
                'area': room.area,
                'center': room.center
            }
        self._data['rooms'] = rooms

    # =========================================================================
    # Element Modification
    # =========================================================================

    def set_modified(self, modified: bool = True):
        """Set modified flag."""
        self._modified = modified
        if modified:
            event_bus.document_modified.emit()

    def modify_wall(self, index: int, **changes):
        """
        Modify a wall's properties (direct, no undo).

        Args:
            index: Wall index
            **changes: Properties to change (start, end, height, category, etc.)
        """
        if 0 <= index < len(self._walls):
            wall = self._walls[index]

            for key, value in changes.items():
                if hasattr(wall, key):
                    setattr(wall, key, value)

            self.set_modified(True)
            self.element_modified.emit('wall', str(index))
            event_bus.element_modified.emit('wall', str(index), changes)

    def modify_wall_undoable(self, index: int, **changes):
        """
        Modify a wall's properties with undo support.

        Args:
            index: Wall index
            **changes: Properties to change
        """
        from core.commands import ModifyWallCommand

        if 0 <= index < len(self._walls):
            wall = self._walls[index]

            # Capture old values
            old_values = {}
            for key in changes:
                if hasattr(wall, key):
                    old_values[key] = getattr(wall, key)

            # Apply changes directly
            for key, value in changes.items():
                if hasattr(wall, key):
                    setattr(wall, key, value)

            self.set_modified(True)
            self.element_modified.emit('wall', str(index))
            event_bus.element_modified.emit('wall', str(index), changes)

            # Push command to undo stack
            cmd = ModifyWallCommand(self, index, old_values, changes)
            self._undo_stack.push(cmd)

    def move_wall_undoable(self, index: int, grip_type: str,
                           old_start: tuple, old_end: tuple,
                           new_start: tuple, new_end: tuple):
        """
        Move a wall with undo support (merges consecutive moves).
        """
        from core.commands import MoveWallCommand

        if 0 <= index < len(self._walls):
            wall = self._walls[index]
            wall.start = new_start
            wall.end = new_end

            self.set_modified(True)
            self.element_modified.emit('wall', str(index))
            event_bus.element_modified.emit('wall', str(index),
                                           {'start': new_start, 'end': new_end})

            # Push command (will merge with previous if same wall)
            cmd = MoveWallCommand(self, index, grip_type,
                                  old_start, old_end, new_start, new_end)
            self._undo_stack.push(cmd)

    def add_wall_undoable(self, wall_data: Dict) -> int:
        """Add a wall with undo support. Returns wall index."""
        from core.commands import AddWallCommand

        cmd = AddWallCommand(self, wall_data)
        self._undo_stack.push(cmd)
        return len(self._walls) - 1

    def delete_wall_undoable(self, index: int):
        """Delete a wall with undo support."""
        from core.commands import DeleteWallCommand

        if 0 <= index < len(self._walls):
            cmd = DeleteWallCommand(self, index)
            self._undo_stack.push(cmd)

    def modify_door(self, index: int, **changes):
        """Modify a door's properties (direct, no undo)."""
        if 0 <= index < len(self._doors):
            door = self._doors[index]

            for key, value in changes.items():
                if hasattr(door, key):
                    setattr(door, key, value)

            self.set_modified(True)
            self.element_modified.emit('door', str(index))

    def modify_door_undoable(self, index: int, **changes):
        """Modify a door's properties with undo support."""
        from core.commands import ModifyDoorCommand

        if 0 <= index < len(self._doors):
            door = self._doors[index]

            old_values = {}
            for key in changes:
                if hasattr(door, key):
                    old_values[key] = getattr(door, key)

            for key, value in changes.items():
                if hasattr(door, key):
                    setattr(door, key, value)

            self.set_modified(True)
            self.element_modified.emit('door', str(index))

            cmd = ModifyDoorCommand(self, index, old_values, changes)
            self._undo_stack.push(cmd)

    def modify_window(self, index: int, **changes):
        """Modify a window's properties (direct, no undo)."""
        if 0 <= index < len(self._windows):
            window = self._windows[index]

            for key, value in changes.items():
                if hasattr(window, key):
                    setattr(window, key, value)

            self.set_modified(True)
            self.element_modified.emit('window', str(index))

    def modify_window_undoable(self, index: int, **changes):
        """Modify a window's properties with undo support."""
        from core.commands import ModifyWindowCommand

        if 0 <= index < len(self._windows):
            window = self._windows[index]

            old_values = {}
            for key in changes:
                if hasattr(window, key):
                    old_values[key] = getattr(window, key)

            for key, value in changes.items():
                if hasattr(window, key):
                    setattr(window, key, value)

            self.set_modified(True)
            self.element_modified.emit('window', str(index))

            cmd = ModifyWindowCommand(self, index, old_values, changes)
            self._undo_stack.push(cmd)

    def get_wall_types(self) -> List[Dict]:
        """Get available wall types."""
        return self._data.get('wall_types', [])

    def get_project_info(self) -> Dict:
        """Get project information."""
        qbd = self._data.get('qbd_answers', {})
        return {
            'name': qbd.get('description', 'Untitled Project'),
            'building_type': self._data.get('building_type', 'residential'),
            'width': self.building_width,
            'depth': self.building_depth,
            'sqft': self._data.get('sqft', 0)
        }

    def get_walls_at_point(self, x: float, z: float, tolerance: float = 50) -> List[Tuple[int, str]]:
        """
        Find walls that have an endpoint near the given point.

        Args:
            x: X coordinate
            z: Z coordinate (plan view Y)
            tolerance: Distance tolerance for matching

        Returns:
            List of (wall_index, endpoint) tuples where endpoint is 'start' or 'end'
        """
        import math
        result = []

        for wall in self._walls:
            # Check start
            sx, sz = wall.start[0], wall.start[2]
            dist_start = math.sqrt((sx - x) ** 2 + (sz - z) ** 2)
            if dist_start <= tolerance:
                result.append((wall.index, 'start'))

            # Check end
            ex, ez = wall.end[0], wall.end[2]
            dist_end = math.sqrt((ex - x) ** 2 + (ez - z) ** 2)
            if dist_end <= tolerance:
                result.append((wall.index, 'end'))

        return result
