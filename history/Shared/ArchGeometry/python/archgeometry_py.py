"""
ArchGeometry Pure Python Implementation

This module provides a pure Python implementation of the archgeometry API.
It serves as:
1. Fallback when C++ bindings aren't built
2. Reference implementation for the API
3. Immediate usability without compilation

Usage:
    try:
        import archgeometry  # C++ bindings
    except ImportError:
        from archgeometry_py import *  # Pure Python fallback
"""

import json
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

__version__ = "1.0.0"


# =============================================================================
# Basic Types
# =============================================================================

@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __iter__(self):
        return iter([self.x, self.y, self.z])

    def normalized(self) -> 'Vec3':
        length = math.sqrt(self.x**2 + self.y**2 + self.z**2)
        if length < 0.0001:
            return Vec3(0, 0, 0)
        return Vec3(self.x/length, self.y/length, self.z/length)


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)

    def perpendicular(self) -> 'Vec2':
        return Vec2(-self.y, self.x)

    def normalized(self) -> 'Vec2':
        l = self.length()
        if l < 0.0001:
            return Vec2(0, 0)
        return Vec2(self.x/l, self.y/l)


@dataclass
class Point2D:
    x: float = 0.0
    y: float = 0.0  # Note: In plan view, this represents Z in 3D


# =============================================================================
# Schema Types
# =============================================================================

@dataclass
class WallLayer:
    name: str = ""
    material: str = ""
    thickness: float = 0.0
    function: str = ""
    r_value: float = 0.0
    color: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)


@dataclass
class WallType:
    id: str = ""
    name: str = ""
    layers: List[WallLayer] = field(default_factory=list)

    def total_thickness(self) -> float:
        return sum(layer.thickness for layer in self.layers)


@dataclass
class SchemaWall:
    start: Vec3 = field(default_factory=Vec3)
    end: Vec3 = field(default_factory=Vec3)
    height: float = 2700.0
    wall_type: str = ""
    category: str = "interior"
    level_name: str = "Level 1"
    rooms: Tuple[str, str] = ("", "")
    is_pinned: bool = False
    locked_properties: List[str] = field(default_factory=list)

    def length(self) -> float:
        dx = self.end.x - self.start.x
        dz = self.end.z - self.start.z
        return math.sqrt(dx**2 + dz**2)

    def direction(self) -> Vec2:
        dx = self.end.x - self.start.x
        dz = self.end.z - self.start.z
        length = math.sqrt(dx**2 + dz**2)
        if length < 0.001:
            return Vec2(1, 0)
        return Vec2(dx/length, dz/length)


@dataclass
class SchemaFloor:
    start: Vec3 = field(default_factory=Vec3)
    end: Vec3 = field(default_factory=Vec3)
    thickness: float = 150.0
    level_name: str = "Level 1"
    room: str = ""
    material: str = "concrete"


@dataclass
class SchemaDoor:
    wall_index: int = 0
    offset: float = 0.0
    width: float = 914.0
    height: float = 2134.0
    type: str = "swing"
    swing: str = "left_in"
    room1: str = ""
    room2: str = ""
    is_pinned: bool = False


@dataclass
class SchemaWindow:
    wall_index: int = 0
    offset: float = 0.0
    width: float = 1200.0
    height: float = 1200.0
    sill_height: float = 900.0
    type: str = "double_hung"
    room: str = ""
    is_pinned: bool = False


@dataclass
class RoofRidge:
    id: str = ""
    start_point: Vec3 = field(default_factory=Vec3)
    end_point: Vec3 = field(default_factory=Vec3)
    height: float = 0.0


@dataclass
class RoofSurface:
    id: str = ""
    pitch: float = 0.0
    orientation: str = ""
    vertices: List[Vec3] = field(default_factory=list)


@dataclass
class SchemaRoof:
    id: str = ""
    type: str = "gable"
    pitch: float = 6.0
    overhang: float = 600.0
    material: str = "asphalt_shingle"
    level_name: str = "Roof Level"
    ridges: List[RoofRidge] = field(default_factory=list)
    surfaces: List[RoofSurface] = field(default_factory=list)


@dataclass
class RoomBounds:
    x: float = 0.0
    y: float = 0.0  # Note: This is Z in 3D space!
    width: float = 0.0
    height: float = 0.0  # Note: This is Z extent (depth)!


@dataclass
class RoomCenter:
    x: float = 0.0
    y: float = 0.0  # Note: This is Z in 3D space!


@dataclass
class SchemaRoom:
    id: str = ""
    name: str = ""
    room_type: str = ""
    zone: str = ""
    level: str = "Level 1"
    bounds: RoomBounds = field(default_factory=RoomBounds)
    center: Optional[RoomCenter] = None
    area: float = 0.0
    is_pinned: bool = False
    locked_properties: List[str] = field(default_factory=list)


@dataclass
class SchemaLevel:
    name: str = "Level 1"
    elevation: float = 0.0
    height: float = 2700.0


@dataclass
class QBDAnswers:
    description: str = ""
    building_type: str = "residential"
    style: str = "traditional"
    stories: int = 1
    garage: str = ""
    roof_type: str = "gable"
    roof_pitch: float = 6.0
    roof_material: str = "asphalt_shingle"
    sqft: int = 0
    bedrooms: int = 0
    bathrooms: int = 0


@dataclass
class DocumentSummary:
    total_walls: int = 0
    exterior_walls: int = 0
    interior_walls: int = 0
    doors_count: int = 0
    windows_count: int = 0
    rooms_placed: int = 0


@dataclass
class SchemaDocument:
    version: str = "1.0.0"
    building_id: str = ""
    width: float = 0.0
    depth: float = 0.0
    sqm: float = 0.0
    sqft: float = 0.0
    unit: str = "mm"
    walls: List[SchemaWall] = field(default_factory=list)
    floors: List[SchemaFloor] = field(default_factory=list)
    doors: List[SchemaDoor] = field(default_factory=list)
    windows: List[SchemaWindow] = field(default_factory=list)
    roofs: List[SchemaRoof] = field(default_factory=list)
    rooms: Dict[str, SchemaRoom] = field(default_factory=dict)
    levels: List[SchemaLevel] = field(default_factory=list)
    wall_types: Dict[str, WallType] = field(default_factory=dict)
    qbd_answers: QBDAnswers = field(default_factory=QBDAnswers)
    summary: DocumentSummary = field(default_factory=DocumentSummary)


# =============================================================================
# Geometry Output Types (simplified for Python)
# =============================================================================

@dataclass
class Polygon2D:
    layer: str = ""
    points: List[Point2D] = field(default_factory=list)
    closed: bool = True
    fill_pattern: str = "solid"
    fill_color: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)

    def get_points_as_tuples(self) -> List[Tuple[float, float]]:
        return [(p.x, p.y) for p in self.points]


@dataclass
class RoomBoundary:
    room_id: str = ""
    room_name: str = ""
    room_type: str = ""
    polygon: Polygon2D = field(default_factory=Polygon2D)
    area: float = 0.0
    centroid: Point2D = field(default_factory=Point2D)


# =============================================================================
# Parser
# =============================================================================

class ParseError(Exception):
    def __init__(self, message: str, line: int = -1, column: int = -1):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(message)


def _parse_vec3(data) -> Vec3:
    if isinstance(data, (list, tuple)) and len(data) >= 3:
        return Vec3(float(data[0]), float(data[1]), float(data[2]))
    return Vec3()


def _parse_wall_layer(data: dict) -> WallLayer:
    color = data.get('color', [0.5, 0.5, 0.5, 1.0])
    if len(color) < 4:
        color = list(color) + [1.0] * (4 - len(color))
    return WallLayer(
        name=data.get('name', ''),
        material=data.get('material', ''),
        thickness=data.get('thickness', 0.0),
        function=data.get('function', ''),
        r_value=data.get('r_value', 0.0),
        color=tuple(color[:4])
    )


def _parse_wall_type(data: dict) -> WallType:
    layers = [_parse_wall_layer(l) for l in data.get('layers', [])]
    return WallType(
        id=data.get('id', ''),
        name=data.get('name', ''),
        layers=layers
    )


def _parse_wall(data: dict) -> SchemaWall:
    rooms = data.get('rooms', ['', ''])
    if len(rooms) < 2:
        rooms = list(rooms) + [''] * (2 - len(rooms))
    return SchemaWall(
        start=_parse_vec3(data.get('start', [0, 0, 0])),
        end=_parse_vec3(data.get('end', [0, 0, 0])),
        height=data.get('height', 2700.0),
        wall_type=data.get('wall_type', ''),
        category=data.get('category', 'interior'),
        level_name=data.get('level_name', 'Level 1'),
        rooms=(rooms[0] if rooms[0] else '', rooms[1] if len(rooms) > 1 and rooms[1] else ''),
        is_pinned=data.get('is_pinned', False),
        locked_properties=data.get('locked_properties', [])
    )


def _parse_floor(data: dict) -> SchemaFloor:
    return SchemaFloor(
        start=_parse_vec3(data.get('start', [0, 0, 0])),
        end=_parse_vec3(data.get('end', [0, 0, 0])),
        thickness=data.get('thickness', 150.0),
        level_name=data.get('level_name', 'Level 1'),
        room=data.get('room', ''),
        material=data.get('material', 'concrete')
    )


def _parse_door(data: dict) -> SchemaDoor:
    return SchemaDoor(
        wall_index=data.get('wall_index', 0),
        offset=data.get('offset', 0.0),
        width=data.get('width', 914.0),
        height=data.get('height', 2134.0),
        type=data.get('type', 'swing'),
        swing=data.get('swing', 'left_in'),
        room1=data.get('room1', ''),
        room2=data.get('room2', ''),
        is_pinned=data.get('is_pinned', False)
    )


def _parse_window(data: dict) -> SchemaWindow:
    return SchemaWindow(
        wall_index=data.get('wall_index', 0),
        offset=data.get('offset', 0.0),
        width=data.get('width', 1200.0),
        height=data.get('height', 1200.0),
        sill_height=data.get('sill_height', 900.0),
        type=data.get('type', 'double_hung'),
        room=data.get('room', ''),
        is_pinned=data.get('is_pinned', False)
    )


def _parse_roof_ridge(data: dict) -> RoofRidge:
    return RoofRidge(
        id=data.get('id', ''),
        start_point=_parse_vec3(data.get('start_point', [0, 0, 0])),
        end_point=_parse_vec3(data.get('end_point', [0, 0, 0])),
        height=data.get('height', 0.0)
    )


def _parse_roof_surface(data: dict) -> RoofSurface:
    vertices = [_parse_vec3(v) for v in data.get('vertices', [])]
    return RoofSurface(
        id=data.get('id', ''),
        pitch=data.get('pitch', 0.0),
        orientation=data.get('orientation', ''),
        vertices=vertices
    )


def _parse_roof(data: dict) -> SchemaRoof:
    ridges = [_parse_roof_ridge(r) for r in data.get('ridges', [])]
    surfaces = [_parse_roof_surface(s) for s in data.get('surfaces', [])]
    return SchemaRoof(
        id=data.get('id', ''),
        type=data.get('type', 'gable'),
        pitch=data.get('pitch', 6.0),
        overhang=data.get('overhang', 600.0),
        material=data.get('material', 'asphalt_shingle'),
        level_name=data.get('level_name', 'Roof Level'),
        ridges=ridges,
        surfaces=surfaces
    )


def _parse_room(room_id: str, data: dict) -> SchemaRoom:
    bounds_data = data.get('bounds', {})
    bounds = RoomBounds(
        x=bounds_data.get('x', 0.0),
        y=bounds_data.get('y', 0.0),  # This is Z in 3D!
        width=bounds_data.get('width', 0.0),
        height=bounds_data.get('height', 0.0)  # This is Z extent!
    )
    center_data = data.get('center')
    center = None
    if center_data:
        center = RoomCenter(
            x=center_data.get('x', 0.0),
            y=center_data.get('y', center_data.get('z', 0.0))  # Handle both conventions
        )
    return SchemaRoom(
        id=room_id,
        name=data.get('name', ''),
        room_type=data.get('room_type', ''),
        zone=data.get('zone', ''),
        level=data.get('level', 'Level 1'),
        bounds=bounds,
        center=center,
        area=data.get('area', 0.0),
        is_pinned=data.get('is_pinned', False),
        locked_properties=data.get('locked_properties', [])
    )


def _parse_level(data: dict) -> SchemaLevel:
    return SchemaLevel(
        name=data.get('name', 'Level 1'),
        elevation=data.get('elevation', 0.0),
        height=data.get('height', 2700.0)
    )


def _parse_qbd_answers(data: dict) -> QBDAnswers:
    return QBDAnswers(
        description=data.get('description', ''),
        building_type=data.get('building_type', 'residential'),
        style=data.get('style', 'traditional'),
        stories=data.get('stories', 1),
        garage=data.get('garage', ''),
        roof_type=data.get('roof_type', 'gable'),
        roof_pitch=data.get('roof_pitch', 6.0),
        roof_material=data.get('roof_material', 'asphalt_shingle'),
        sqft=data.get('sqft', 0),
        bedrooms=data.get('bedrooms', 0),
        bathrooms=data.get('bathrooms', 0)
    )


def parse_json(json_string: str) -> SchemaDocument:
    """Parse JSON string into SchemaDocument."""
    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ParseError(f"JSON parse error: {e}", e.lineno, e.colno)

    doc = SchemaDocument()
    doc.version = data.get('version', '1.0.0')
    doc.building_id = data.get('building_id', '')
    doc.width = data.get('width', 0.0)
    doc.depth = data.get('depth', 0.0)
    doc.sqm = data.get('sqm', 0.0)
    doc.sqft = data.get('sqft', 0.0)
    doc.unit = data.get('unit', 'mm')

    # Parse wall types
    for wt_data in data.get('wall_types', []):
        wt = _parse_wall_type(wt_data)
        if wt.id:
            doc.wall_types[wt.id] = wt

    # Parse walls
    doc.walls = [_parse_wall(w) for w in data.get('walls_batch', [])]

    # Parse floors
    doc.floors = [_parse_floor(f) for f in data.get('floors_batch', [])]

    # Parse doors
    doc.doors = [_parse_door(d) for d in data.get('doors', [])]

    # Parse windows
    doc.windows = [_parse_window(w) for w in data.get('windows', [])]

    # Parse roofs
    doc.roofs = [_parse_roof(r) for r in data.get('roofs', [])]

    # Parse rooms
    for room_id, room_data in data.get('rooms', {}).items():
        doc.rooms[room_id] = _parse_room(room_id, room_data)

    # Parse levels
    doc.levels = [_parse_level(l) for l in data.get('levels', [])]

    # Parse QBD answers
    if 'qbd_answers' in data:
        doc.qbd_answers = _parse_qbd_answers(data['qbd_answers'])

    # Parse summary
    if 'summary' in data:
        s = data['summary']
        doc.summary = DocumentSummary(
            total_walls=s.get('total_walls', len(doc.walls)),
            exterior_walls=s.get('exterior_walls', 0),
            interior_walls=s.get('interior_walls', 0),
            doors_count=s.get('doors', len(doc.doors)),
            windows_count=s.get('windows', len(doc.windows)),
            rooms_placed=s.get('rooms_placed', len(doc.rooms))
        )

    return doc


def parse_file(file_path: str) -> SchemaDocument:
    """Parse JSON file into SchemaDocument."""
    path = Path(file_path)
    if not path.exists():
        raise ParseError(f"File not found: {file_path}")
    with open(path, 'r', encoding='utf-8') as f:
        return parse_json(f.read())


# =============================================================================
# Query API
# =============================================================================

class QueryAPI:
    """Query interface for schema document."""

    def __init__(self, doc: SchemaDocument):
        self._doc = doc

    def get_walls(self) -> List[SchemaWall]:
        return self._doc.walls

    def get_wall_by_index(self, index: int) -> Optional[SchemaWall]:
        if 0 <= index < len(self._doc.walls):
            return self._doc.walls[index]
        return None

    def get_room_by_id(self, room_id: str) -> Optional[SchemaRoom]:
        return self._doc.rooms.get(room_id)

    def get_level_by_name(self, name: str) -> Optional[SchemaLevel]:
        for level in self._doc.levels:
            if level.name == name:
                return level
        return None

    def get_wall_type_by_id(self, type_id: str) -> Optional[WallType]:
        return self._doc.wall_types.get(type_id)

    def get_walls_on_level(self, level_name: str) -> List[SchemaWall]:
        return [w for w in self._doc.walls if w.level_name == level_name]

    def get_rooms_on_level(self, level_name: str) -> List[SchemaRoom]:
        return [r for r in self._doc.rooms.values() if r.level == level_name]

    def get_walls_for_room(self, room_id: str) -> List[SchemaWall]:
        return [w for w in self._doc.walls if room_id in w.rooms]

    def get_doors_for_wall(self, wall_index: int) -> List[SchemaDoor]:
        return [d for d in self._doc.doors if d.wall_index == wall_index]

    def get_windows_for_wall(self, wall_index: int) -> List[SchemaWindow]:
        return [w for w in self._doc.windows if w.wall_index == wall_index]

    def get_adjacent_rooms(self, room_id: str) -> List[SchemaRoom]:
        adjacent_ids = set()
        for wall in self._doc.walls:
            if wall.rooms[0] == room_id and wall.rooms[1]:
                adjacent_ids.add(wall.rooms[1])
            elif wall.rooms[1] == room_id and wall.rooms[0]:
                adjacent_ids.add(wall.rooms[0])
        return [self._doc.rooms[rid] for rid in adjacent_ids if rid in self._doc.rooms]

    def get_room_area(self, room_id: str) -> float:
        room = self.get_room_by_id(room_id)
        if room:
            if room.area > 0:
                return room.area
            return room.bounds.width * room.bounds.height
        return 0.0

    def get_wall_length(self, wall_index: int) -> float:
        wall = self.get_wall_by_index(wall_index)
        if wall:
            return wall.length()
        return 0.0

    def get_wall_thickness(self, wall_index: int) -> float:
        wall = self.get_wall_by_index(wall_index)
        if wall:
            wt = self.get_wall_type_by_id(wall.wall_type)
            if wt:
                return wt.total_thickness()
        return 150.0  # Default

    def get_building_bounds_min(self) -> Vec3:
        if not self._doc.walls:
            return Vec3(0, 0, 0)
        min_x = min(min(w.start.x, w.end.x) for w in self._doc.walls)
        min_y = min(w.start.y for w in self._doc.walls)
        min_z = min(min(w.start.z, w.end.z) for w in self._doc.walls)
        return Vec3(min_x, min_y, min_z)

    def get_building_bounds_max(self) -> Vec3:
        if not self._doc.walls:
            return Vec3(0, 0, 0)
        max_x = max(max(w.start.x, w.end.x) for w in self._doc.walls)
        max_y = max(w.start.y + w.height for w in self._doc.walls)
        max_z = max(max(w.start.z, w.end.z) for w in self._doc.walls)
        return Vec3(max_x, max_y, max_z)

    def get_wall_count(self) -> int:
        return len(self._doc.walls)

    def get_room_count(self) -> int:
        return len(self._doc.rooms)

    def get_floor_count(self) -> int:
        return len(self._doc.floors)

    def get_door_count(self) -> int:
        return len(self._doc.doors)

    def get_window_count(self) -> int:
        return len(self._doc.windows)

    def get_exterior_wall_count(self) -> int:
        return sum(1 for w in self._doc.walls if w.category == 'exterior')

    def get_interior_wall_count(self) -> int:
        return sum(1 for w in self._doc.walls if w.category in ('interior', 'wet_wall'))

    def get_total_exterior_wall_length(self) -> float:
        return sum(w.length() for w in self._doc.walls if w.category == 'exterior')

    def get_total_window_area(self) -> float:
        return sum(w.width * w.height for w in self._doc.windows)


# =============================================================================
# Geometry Helpers
# =============================================================================

class FloorGeometryGenerator:
    """Floor geometry generation utilities."""

    @staticmethod
    def get_width(floor: SchemaFloor) -> float:
        """Get floor width (X dimension)."""
        return abs(floor.end.x - floor.start.x)

    @staticmethod
    def get_depth(floor: SchemaFloor) -> float:
        """Get floor depth (Z dimension) - NOT thickness!"""
        return abs(floor.end.z - floor.start.z)

    @staticmethod
    def get_elevation(floor: SchemaFloor) -> float:
        """Get floor elevation (Y coordinate)."""
        return floor.start.y

    @staticmethod
    def get_area(floor: SchemaFloor) -> float:
        """Get floor area in square mm."""
        return FloorGeometryGenerator.get_width(floor) * FloorGeometryGenerator.get_depth(floor)


class RoomGeometryGenerator:
    """Room geometry generation utilities."""

    @staticmethod
    def get_center(bounds: RoomBounds) -> Point2D:
        """
        Get room center from bounds.

        CORRECT INTERPRETATION:
        - bounds.y is Z coordinate in plan view
        - Return Point2D where x = center X, y = center Z
        """
        return Point2D(
            bounds.x + bounds.width / 2.0,
            bounds.y + bounds.height / 2.0  # This represents Z center
        )

    @staticmethod
    def get_area(bounds: RoomBounds) -> float:
        """Calculate room area from bounds in square mm."""
        return bounds.width * bounds.height

    @staticmethod
    def contains_point(point: Point2D, room: SchemaRoom) -> bool:
        """Check if point is inside room bounds (2D)."""
        b = room.bounds
        return (b.x <= point.x <= b.x + b.width and
                b.y <= point.y <= b.y + b.height)

    @staticmethod
    def generate_boundary(room: SchemaRoom) -> RoomBoundary:
        """Generate room boundary polygon."""
        b = room.bounds
        poly = Polygon2D(
            layer="rooms",
            points=[
                Point2D(b.x, b.y),
                Point2D(b.x + b.width, b.y),
                Point2D(b.x + b.width, b.y + b.height),
                Point2D(b.x, b.y + b.height)
            ],
            closed=True
        )
        return RoomBoundary(
            room_id=room.id,
            room_name=room.name,
            room_type=room.room_type,
            polygon=poly,
            area=RoomGeometryGenerator.get_area(b),
            centroid=RoomGeometryGenerator.get_center(b)
        )


class WallGeometryGenerator:
    """Wall geometry generation utilities."""

    @staticmethod
    def get_thickness(wall_type: WallType) -> float:
        """Get total wall thickness from wall type."""
        return wall_type.total_thickness()

    @staticmethod
    def get_length(wall: SchemaWall) -> float:
        """Get wall length."""
        return wall.length()

    @staticmethod
    def get_direction(wall: SchemaWall) -> Vec2:
        """Get wall direction (normalized)."""
        return wall.direction()

    @staticmethod
    def get_centerline(wall: SchemaWall) -> Tuple[Vec3, Vec3]:
        """Get wall centerline (start, end)."""
        return (wall.start, wall.end)

    @staticmethod
    def get_perpendicular_offset(wall: SchemaWall, distance: float) -> Vec3:
        """Get offset vector perpendicular to wall."""
        d = wall.direction()
        perp = d.perpendicular()
        return Vec3(perp.x * distance, 0.0, perp.y * distance)


# =============================================================================
# Version
# =============================================================================

def version() -> str:
    return __version__
