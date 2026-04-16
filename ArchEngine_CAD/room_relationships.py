"""
Room Relationships - Spatial graph for room adjacency and relationships

Models room relationships as a graph for solver consumption.
This is the bridge between CAD document model and solver algorithms.
"""
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math


class Zone(Enum):
    """Room zone types for grouping."""
    PUBLIC = "public"
    PRIVATE = "private"
    SERVICE = "service"
    CIRCULATION = "circulation"
    TRANSITION = "transition"
    OUTDOOR = "outdoor"


class RelationType(Enum):
    """Types of spatial relationships between rooms."""
    CONNECTS_TO = "connects_to"
    ACCESSED_VIA = "accessed_via"
    ADJACENT_TO = "adjacent_to"
    ATTACHED_TO = "attached_to"
    OPEN_TO = "open_to"
    PARTIAL_WALL = "partial_wall"
    ISOLATED_FROM = "isolated_from"
    BUFFERED_FROM = "buffered_from"
    GROUPED_WITH = "grouped_with"
    SAME_ZONE = "same_zone"


class WallType(Enum):
    """Types of walls."""
    NONE = "none"
    FULL = "full"
    PARTIAL = "partial"
    EXTERIOR = "exterior"
    WET = "wet"


class ExteriorRequirement(Enum):
    """Exterior wall requirements."""
    REQUIRED = "required"
    PREFERRED = "preferred"
    NONE = "none"
    INTERIOR_ONLY = "interior"


@dataclass
class Relationship:
    """Relationship between two rooms."""
    from_room: str  # Source room ID
    to_room: str    # Target room ID
    relation_type: RelationType = RelationType.CONNECTS_TO
    # opening_type, wall_type use forward references since they're defined later
    opening_type: "OpeningType" = None  # type: ignore
    wall_type: "WallType" = None  # type: ignore
    opening_width: float = 3.0  # feet
    priority: int = 50
    bidirectional: bool = True
    weight: float = 1.0

    def __post_init__(self):
        """Set default values for opening_type and wall_type."""
        if self.opening_type is None:
            self.opening_type = OpeningType.DOOR
        if self.wall_type is None:
            self.wall_type = WallType.FULL

    @property
    def implies_separation(self) -> bool:
        """Does this relationship require rooms to NOT be adjacent?"""
        return self.relation_type in {
            RelationType.ISOLATED_FROM,
            RelationType.BUFFERED_FROM
        }

    @property
    def implies_wall(self) -> bool:
        """Does this relationship imply a wall between rooms?"""
        return self.relation_type in {
            RelationType.CONNECTS_TO,
            RelationType.ADJACENT_TO,
            RelationType.ATTACHED_TO,
            RelationType.PARTIAL_WALL,
        }

    @property
    def implies_opening(self) -> bool:
        """Does this relationship require an opening?"""
        return self.relation_type in {
            RelationType.CONNECTS_TO,
            RelationType.ATTACHED_TO,
            RelationType.OPEN_TO,
            RelationType.PARTIAL_WALL,
        }

    @property
    def implies_no_wall(self) -> bool:
        """Does this relationship mean no wall?"""
        return self.relation_type == RelationType.OPEN_TO

    def get_wall_result(self) -> Tuple["WallType", "OpeningType"]:
        """Get the wall and opening type implied by this relationship."""
        if self.relation_type == RelationType.OPEN_TO:
            return WallType.NONE, OpeningType.CASED_OPENING
        elif self.relation_type == RelationType.PARTIAL_WALL:
            return WallType.PARTIAL, OpeningType.NONE
        elif self.relation_type == RelationType.CONNECTS_TO:
            return WallType.FULL, self.opening_type
        elif self.relation_type == RelationType.ATTACHED_TO:
            return WallType.FULL, self.opening_type
        elif self.relation_type == RelationType.ADJACENT_TO:
            return self.wall_type, OpeningType.NONE
        else:
            return WallType.NONE, OpeningType.NONE


class OpeningType(Enum):
    """Door/window opening types."""
    NONE = "none"
    DOOR = "door"
    DOOR_SWING = "door_swing"
    DOOR_SLIDING = "door_sliding"
    DOOR_BIFOLD = "door_bifold"
    DOUBLE_DOOR = "double_door"
    CASED_OPENING = "cased_opening"
    ARCHWAY = "archway"
    POCKET_DOOR = "pocket_door"
    BARN_DOOR = "barn_door"
    FRENCH_DOOR = "french_door"
    WINDOW = "window"
    WINDOW_FIXED = "window_fixed"
    WINDOW_SLIDING = "window_sliding"
    WINDOW_CASEMENT = "window_casement"


@dataclass
class RoomTypeSpec:
    """Specification for a room type with default properties (QBD compatibility)."""
    name: str
    zone: Zone
    exterior: ExteriorRequirement
    is_wet: bool = False
    min_area: int = 50
    typical_ratio: float = 0.75
    default_connections: List[str] = field(default_factory=list)
    default_adjacencies: List[str] = field(default_factory=list)
    default_groupings: List[str] = field(default_factory=list)


# Room type templates (QBD compatible)
ROOM_TYPES: Dict[str, RoomTypeSpec] = {
    'living': RoomTypeSpec('Living Room', Zone.PUBLIC, ExteriorRequirement.PREFERRED, min_area=180),
    'kitchen': RoomTypeSpec('Kitchen', Zone.PUBLIC, ExteriorRequirement.PREFERRED, min_area=100),
    'dining': RoomTypeSpec('Dining Room', Zone.PUBLIC, ExteriorRequirement.PREFERRED, min_area=120),
    'entry': RoomTypeSpec('Entry', Zone.TRANSITION, ExteriorRequirement.REQUIRED, min_area=40),
    'bedroom': RoomTypeSpec('Bedroom', Zone.PRIVATE, ExteriorRequirement.REQUIRED, min_area=120),
    'primary_bedroom': RoomTypeSpec('Primary Bedroom', Zone.PRIVATE, ExteriorRequirement.REQUIRED, min_area=180),
    'guest_bedroom': RoomTypeSpec('Guest Bedroom', Zone.PRIVATE, ExteriorRequirement.PREFERRED, min_area=140),
    'bathroom': RoomTypeSpec('Bathroom', Zone.PRIVATE, ExteriorRequirement.INTERIOR_ONLY, is_wet=True, min_area=40),
    'primary_bath': RoomTypeSpec('Primary Bath', Zone.PRIVATE, ExteriorRequirement.INTERIOR_ONLY, is_wet=True, min_area=100),
    'closet': RoomTypeSpec('Closet', Zone.PRIVATE, ExteriorRequirement.INTERIOR_ONLY, min_area=25),
    'walk_in_closet': RoomTypeSpec('Walk-in Closet', Zone.PRIVATE, ExteriorRequirement.INTERIOR_ONLY, min_area=50),
    'garage': RoomTypeSpec('Garage', Zone.SERVICE, ExteriorRequirement.REQUIRED, min_area=400),
    'office': RoomTypeSpec('Office', Zone.PUBLIC, ExteriorRequirement.PREFERRED, min_area=100),
    'laundry': RoomTypeSpec('Laundry', Zone.SERVICE, ExteriorRequirement.INTERIOR_ONLY, is_wet=True, min_area=50),
    'workshop': RoomTypeSpec('Workshop', Zone.SERVICE, ExteriorRequirement.INTERIOR_ONLY, min_area=200),
    'gym': RoomTypeSpec('Gym', Zone.PRIVATE, ExteriorRequirement.INTERIOR_ONLY, min_area=200),
    'library': RoomTypeSpec('Library', Zone.PUBLIC, ExteriorRequirement.PREFERRED, min_area=120),
    'mudroom': RoomTypeSpec('Mudroom', Zone.TRANSITION, ExteriorRequirement.REQUIRED, min_area=40),
    'porch': RoomTypeSpec('Porch', Zone.OUTDOOR, ExteriorRequirement.REQUIRED, min_area=80),
    'deck': RoomTypeSpec('Deck', Zone.OUTDOOR, ExteriorRequirement.REQUIRED, min_area=150),
}


@dataclass
class RoomNode:
    """A room node in the spatial graph."""
    id: str
    room_type: str
    name: str = ""  # Display name for the room
    min_area: float = 10.0  # m²
    target_area: float = 15.0  # m²
    max_area: float = 50.0  # m²
    min_width: float = 2.5  # meters
    min_depth: float = 2.5  # meters
    preferred_aspect_ratio: float = 1.0  # 1.0 = square
    zone: Zone = Zone.PRIVATE
    floor: int = 0

    # Adjacency preferences (room_id -> weight)
    adjacency_preferences: Dict[str, float] = field(default_factory=dict)

    # Position constraints (optional)
    must_adjoin: Optional[str] = None  # Must be adjacent to this room
    avoid_adjoining: List[str] = field(default_factory=list)

    # External access requirements
    needs_exterior_window: bool = False
    needs_exterior_door: bool = False
    exterior_requirement: ExteriorRequirement = ExteriorRequirement.NONE

    # Room type spec (for QBD generator compatibility)
    spec: Optional[Any] = None

    # Wet room flag (for plumbing walls)
    is_wet: bool = False

    # Relationships (for QBD generator compatibility)
    relationships: List['Relationship'] = field(default_factory=list)

    @property
    def effective_min_area(self) -> float:
        """Effective minimum area (considers room type spec if available)."""
        if self.spec and hasattr(self.spec, 'min_area'):
            return max(self.min_area, self.spec.min_area)
        return self.min_area


@dataclass
class Point:
    """2D point."""
    x: float
    y: float


@dataclass
class Rect:
    """2D rectangle."""
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def intersects(self, other: 'Rect') -> bool:
        """Check if this rect intersects another."""
        return not (
            self.x2 <= other.x or other.x2 <= self.x or
            self.y2 <= other.y or other.y2 <= self.y
        )

    def touches(self, other: 'Rect', tolerance: float = 0.1) -> bool:
        """Check if this rect touches or is adjacent to another."""
        # Expand by tolerance to catch near-adjacent
        expanded = Rect(
            self.x - tolerance,
            self.y - tolerance,
            self.width + 2 * tolerance,
            self.height + 2 * tolerance
        )
        return expanded.intersects(other)

    def contains(self, point: Point) -> bool:
        """Check if rect contains point."""
        return (self.x <= point.x <= self.x2 and
                self.y <= point.y <= self.y2)

    def distance_to(self, other: 'Rect') -> float:
        """Calculate minimum distance between rects."""
        dx = max(0, max(self.x - other.x2, other.x - self.x2))
        dy = max(0, max(self.y - other.y2, other.y - self.y2))
        return math.sqrt(dx * dx + dy * dy)


@dataclass
class PlacedRoom:
    """A room with placement information."""
    node: RoomNode
    rect: Rect

    @property
    def area(self) -> float:
        return self.rect.area

    @property
    def is_valid(self) -> bool:
        """Check if placement meets minimum requirements."""
        return (self.rect.width >= self.node.min_width and
                self.rect.height >= self.node.min_depth and
                self.area >= self.node.min_area)


@dataclass
class PlacedLayout:
    """A complete layout of rooms."""
    rooms: Dict[str, PlacedRoom] = field(default_factory=dict)
    score: float = 0.0
    is_complete: bool = False
    iterations: int = 0
    solve_time_ms: float = 0.0

    def add_room(self, room: PlacedRoom):
        """Add a placed room to the layout."""
        self.rooms[room.node.id] = room

    def get_room(self, room_id: str) -> Optional[PlacedRoom]:
        """Get a room by ID."""
        return self.rooms.get(room_id)

    def has_overlaps(self) -> bool:
        """Check if any rooms overlap."""
        room_list = list(self.rooms.values())
        for i, r1 in enumerate(room_list):
            for r2 in room_list[i+1:]:
                if r1.rect.intersects(r2.rect):
                    return True
        return False

    def get_overlaps(self) -> List[Tuple[str, str]]:
        """Get all overlapping room pairs."""
        overlaps = []
        room_list = list(self.rooms.values())
        for i, r1 in enumerate(room_list):
            for r2 in room_list[i+1:]:
                if r1.rect.intersects(r2.rect):
                    overlaps.append((r1.node.id, r2.node.id))
        return overlaps

    def total_area(self) -> float:
        """Get total area of all rooms."""
        return sum(r.area for r in self.rooms.values())

    def coverage(self, bounds_width: float, bounds_depth: float) -> float:
        """Calculate coverage percentage of bounds."""
        if bounds_width <= 0 or bounds_depth <= 0:
            return 0.0
        return self.total_area() / (bounds_width * bounds_depth)

    def are_adjacent(self, room_a: str, room_b: str) -> bool:
        """Check if two rooms are adjacent."""
        ra = self.rooms.get(room_a)
        rb = self.rooms.get(room_b)
        if not ra or not rb:
            return False

        # Two rects are adjacent if they intersect or are very close
        return ra.rect.intersects(rb.rect) or ra.rect.distance_to(rb.rect) < 0.1


class SpatialGraph:
    """
    Spatial graph of room relationships.

    Manages room nodes and their adjacency requirements.
    Used by solvers to generate valid layouts.
    """

    def __init__(self):
        self.rooms: Dict[str, RoomNode] = {}
        self.adjacencies: Dict[str, Set[str]] = {}
        self.constraints: List[Dict] = []
        self.entry_room: str = "entry"  # Default entry room ID
        self.entry_edge: str = "south"  # Default entry edge

    def add_room(self, room_id: str, room_type: str = "room",
                 min_area: float = 10.0, **kwargs) -> RoomNode:
        """Add a room to the graph."""
        node = RoomNode(
            id=room_id,
            room_type=room_type,
            min_area=min_area,
            **kwargs
        )
        self.rooms[room_id] = node
        self.adjacencies[room_id] = set()
        return node

    def get_room(self, room_id: str) -> Optional[RoomNode]:
        """Get a room node by ID."""
        return self.rooms.get(room_id)

    def connect(self, room_a: str, room_b: str, opening_or_weight = 1.0, weight: float = 1.0, relation: RelationType = RelationType.CONNECTS_TO):
        """Add adjacency requirement between two rooms.

        Args:
            room_a: First room ID
            room_b: Second room ID
            opening_or_weight: Either an OpeningType or weight (for backward compat)
            weight: Connection weight (if opening_or_weight is OpeningType)
            relation: Type of relationship
        """
        if room_a not in self.rooms or room_b not in self.rooms:
            return

        # Handle both signatures: connect(a, b, OpeningType) and connect(a, b, weight)
        if isinstance(opening_or_weight, (int, float)):
            actual_weight = opening_or_weight
            opening = None
        else:
            # It's an OpeningType - use the weight parameter
            opening = opening_or_weight
            actual_weight = weight

        self.adjacencies[room_a].add(room_b)
        self.adjacencies[room_b].add(room_a)

        # Update preferences
        self.rooms[room_a].adjacency_preferences[room_b] = actual_weight
        self.rooms[room_b].adjacency_preferences[room_a] = actual_weight

        # Add Relationship objects (for QBD generator compatibility)
        opening_type = opening if opening else OpeningType.DOOR
        rel = Relationship(room_a, room_b, relation, opening_type, WallType.FULL, 3.0, 50, True, actual_weight)
        self.rooms[room_a].relationships.append(rel)

    def open_to(self, room_a: str, room_b: str):
        """Mark two rooms as open to each other (no wall)."""
        self.connect(room_a, room_b, relation=RelationType.OPEN_TO)

    def accessed_via(self, room_a: str, room_b: str):
        """Mark room_a as accessed via room_b."""
        self.connect(room_a, room_b, relation=RelationType.ACCESSED_VIA)

    def attached(self, room_a: str, room_b: str):
        """Mark room_a as attached to room_b (e.g., ensuite bathroom)."""
        self.connect(room_a, room_b, relation=RelationType.ATTACHED_TO)

    def isolate(self, room_a: str, room_b: str):
        """Mark room_a as isolated from room_b (cannot share wall)."""
        # Store as a negative constraint
        if room_a in self.rooms:
            self.rooms[room_a].avoid_adjoining.append(room_b)
        if room_b in self.rooms:
            self.rooms[room_b].avoid_adjoining.append(room_a)

    def group(self, *room_ids: str):
        """Mark rooms as grouped together (should be near each other)."""
        for i, room_a in enumerate(room_ids):
            for room_b in room_ids[i+1:]:
                if room_a in self.rooms and room_b in self.rooms:
                    self.connect(room_a, room_b, relation=RelationType.GROUPED_WITH)

    def adjacent(self, room_a: str, room_b: str):
        """Shorthand: rooms share a wall but no door."""
        self.connect(room_a, room_b, relation=RelationType.ADJACENT_TO)

    def get_wet_rooms(self) -> List[str]:
        """Get all wet rooms (need plumbing)."""
        return [r.id for r in self.rooms.values() if r.is_wet]

    def get_separation_requirements(self) -> Dict[str, Set[str]]:
        """Get which rooms must NOT be adjacent."""
        sep = {room_id: set() for room_id in self.rooms}

        for room in self.rooms.values():
            for rel in room.relationships:
                if rel.relation_type in (RelationType.ISOLATED_FROM, RelationType.BUFFERED_FROM):
                    sep[room.id].add(rel.to_room)
                    sep[rel.to_room].add(room.id)

        return sep

    def disconnect(self, room_a: str, room_b: str):
        """Remove adjacency requirement."""
        if room_a in self.adjacencies:
            self.adjacencies[room_a].discard(room_b)
        if room_b in self.adjacencies:
            self.adjacencies[room_b].discard(room_a)

    def get_neighbors(self, room_id: str) -> Set[str]:
        """Get adjacent rooms."""
        return self.adjacencies.get(room_id, set())

    def add_constraint(self, constraint_type: str, **params):
        """Add a layout constraint."""
        self.constraints.append({
            "type": constraint_type,
            **params
        })

    def get_rooms_by_zone(self, zone: Zone) -> List[RoomNode]:
        """Get all rooms in a zone."""
        return [r for r in self.rooms.values() if r.zone == zone]

    def get_rooms_by_type(self, room_type: str) -> List[RoomNode]:
        """Get all rooms of a specific type."""
        return [r for r in self.rooms.values() if r.room_type == room_type]

    def get_adjacency_score(self, layout: PlacedLayout) -> float:
        """
        Calculate how well a layout satisfies adjacency requirements.
        Returns score 0.0-1.0.
        """
        if not self.adjacencies:
            return 1.0

        satisfied = 0
        total = 0

        for room_id, neighbors in self.adjacencies.items():
            for neighbor_id in neighbors:
                total += 1
                if layout.are_adjacent(room_id, neighbor_id):
                    satisfied += 1

        return satisfied / total if total > 0 else 1.0

    def get_area_score(self, layout: PlacedLayout) -> float:
        """
        Calculate how well room areas meet requirements.
        Returns score 0.0-1.0.
        """
        if not self.rooms:
            return 1.0

        scores = []
        for room_id, room_node in self.rooms.items():
            placed = layout.rooms.get(room_id)
            if not placed:
                scores.append(0.0)
                continue

            area = placed.area
            if area < room_node.min_area:
                # Penalty for too small
                scores.append(max(0.0, area / room_node.min_area))
            elif area > room_node.max_area:
                # Penalty for too large
                scores.append(max(0.0, room_node.max_area / area))
            else:
                # Ideal range
                scores.append(1.0)

        return sum(scores) / len(scores) if scores else 1.0

    def validate(self, *args, **kwargs) -> List[str]:
        """Validate graph configuration."""
        errors = []

        # Check for rooms with invalid constraints
        for room_id, room in self.rooms.items():
            if room.min_area <= 0:
                errors.append(f"Room {room_id}: min_area must be positive")
            if room.min_width <= 0 or room.min_depth <= 0:
                errors.append(f"Room {room_id}: min dimensions must be positive")

            # Check must_adjoin references valid room
            if room.must_adjoin and room.must_adjoin not in self.rooms:
                errors.append(f"Room {room_id}: must_adjoin references unknown room {room.must_adjoin}")

        return errors

    def to_dict(self) -> Dict:
        """Serialize graph to dict."""
        return {
            "rooms": {
                rid: {
                    "id": r.id,
                    "room_type": r.room_type,
                    "min_area": r.min_area,
                    "target_area": r.target_area,
                    "min_width": r.min_width,
                    "min_depth": r.min_depth,
                    "zone": r.zone.value,
                    "floor": r.floor,
                }
                for rid, r in self.rooms.items()
            },
            "adjacencies": {
                rid: list(neighbors)
                for rid, neighbors in self.adjacencies.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'SpatialGraph':
        """Create graph from dict."""
        graph = cls()

        for rid, rdata in data.get("rooms", {}).items():
            graph.add_room(
                room_id=rid,
                room_type=rdata.get("room_type", "room"),
                min_area=rdata.get("min_area", 10.0),
                target_area=rdata.get("target_area", 15.0),
                min_width=rdata.get("min_width", 2.5),
                min_depth=rdata.get("min_depth", 2.5),
                zone=Zone(rdata.get("zone", "private")),
                floor=rdata.get("floor", 0),
            )

        for rid, neighbors in data.get("adjacencies", {}).items():
            for neighbor in neighbors:
                graph.connect(rid, neighbor)

        return graph


# Default room type templates
ROOM_TEMPLATES = {
    "bedroom": {"min_area": 10, "target_area": 12, "min_width": 3.0, "zone": Zone.PRIVATE},
    "master_bedroom": {"min_area": 14, "target_area": 18, "min_width": 3.5, "zone": Zone.PRIVATE},
    "living": {"min_area": 15, "target_area": 25, "min_width": 4.0, "zone": Zone.PUBLIC},
    "dining": {"min_area": 12, "target_area": 15, "min_width": 3.5, "zone": Zone.PUBLIC},
    "kitchen": {"min_area": 8, "target_area": 12, "min_width": 2.5, "zone": Zone.SERVICE},
    "bathroom": {"min_area": 4, "target_area": 6, "min_width": 2.0, "zone": Zone.PRIVATE},
    "hallway": {"min_area": 6, "target_area": 8, "min_width": 1.2, "zone": Zone.CIRCULATION},
    "entry": {"min_area": 4, "target_area": 6, "min_width": 2.0, "zone": Zone.CIRCULATION},
    "closet": {"min_area": 2, "target_area": 3, "min_width": 1.0, "zone": Zone.PRIVATE},
    "garage": {"min_area": 20, "target_area": 30, "min_width": 3.0, "zone": Zone.SERVICE},
}


def create_room_node(room_type: str, room_id: str, **overrides) -> RoomNode:
    """Create a room node from a template."""
    template = ROOM_TEMPLATES.get(room_type, ROOM_TEMPLATES["bedroom"]).copy()
    template.update(overrides)
    return RoomNode(
        id=room_id,
        room_type=room_type,
        **template
    )
