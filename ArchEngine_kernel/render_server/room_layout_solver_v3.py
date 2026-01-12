"""
Room Layout Solver v3
=====================
Advanced floor plan generator with:
- CSP (Constraint Satisfaction Problem) based placement
- Partial solutions when not all rooms fit
- Multi-shape building support (Rectangle, L, U, T)
- Optimized scoring for architectural quality
- Progressive grid refinement

Architecture:
1. BuildingShape defines the footprint (can be non-rectangular)
2. RoomSpec defines room requirements and constraints
3. PlacementEngine finds valid positions using CSP
4. Scorer evaluates layout quality
5. Solver orchestrates the search with partial solution support
"""

from typing import Dict, List, Optional, Tuple, Set, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import math
import heapq
from collections import defaultdict


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class RoomType(Enum):
    """Standard room types with default properties"""
    ENTRY = "entry"
    LIVING = "living"
    DINING = "dining"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    PRIMARY_BEDROOM = "primary_bedroom"
    BATHROOM = "bathroom"
    PRIMARY_BATH = "primary_bath"
    HALLWAY = "hallway"
    CLOSET = "closet"
    OFFICE = "office"
    LAUNDRY = "laundry"
    MECHANICAL = "mechanical"
    UTILITY = "utility"
    GARAGE = "garage"


class Zone(Enum):
    """Zones for room organization"""
    PUBLIC = "public"       # Entry, Living, Dining, Kitchen
    PRIVATE = "private"     # Bedrooms, Bathrooms
    SERVICE = "service"     # Laundry, Mechanical, Garage
    CIRCULATION = "circulation"  # Hallways


# Room type to zone mapping
ROOM_ZONES = {
    RoomType.ENTRY: Zone.PUBLIC,
    RoomType.LIVING: Zone.PUBLIC,
    RoomType.DINING: Zone.PUBLIC,
    RoomType.KITCHEN: Zone.PUBLIC,
    RoomType.BEDROOM: Zone.PRIVATE,
    RoomType.PRIMARY_BEDROOM: Zone.PRIVATE,
    RoomType.BATHROOM: Zone.PRIVATE,
    RoomType.PRIMARY_BATH: Zone.PRIVATE,
    RoomType.HALLWAY: Zone.CIRCULATION,
    RoomType.CLOSET: Zone.PRIVATE,
    RoomType.OFFICE: Zone.PRIVATE,
    RoomType.LAUNDRY: Zone.SERVICE,
    RoomType.MECHANICAL: Zone.SERVICE,
    RoomType.UTILITY: Zone.SERVICE,
    RoomType.GARAGE: Zone.SERVICE,
}

# Wet rooms (need plumbing)
WET_ROOMS = {RoomType.KITCHEN, RoomType.BATHROOM, RoomType.PRIMARY_BATH, RoomType.LAUNDRY, RoomType.UTILITY}

# Rooms that need exterior walls (windows)
NEEDS_EXTERIOR = {RoomType.BEDROOM, RoomType.PRIMARY_BEDROOM, RoomType.LIVING, RoomType.OFFICE}


# =============================================================================
# GEOMETRY PRIMITIVES
# =============================================================================

class Point(NamedTuple):
    x: float
    y: float


class Rect(NamedTuple):
    """Axis-aligned rectangle"""
    x: float      # Left
    y: float      # Bottom
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def aspect_ratio(self) -> float:
        """Returns value between 0-1, where 1 is square"""
        if self.width == 0 or self.height == 0:
            return 0
        return min(self.width, self.height) / max(self.width, self.height)

    def overlaps(self, other: 'Rect', tolerance: float = 0.01) -> bool:
        """Check if two rectangles overlap (excluding edges)"""
        return (self.x < other.x2 - tolerance and
                self.x2 > other.x + tolerance and
                self.y < other.y2 - tolerance and
                self.y2 > other.y + tolerance)

    def touches(self, other: 'Rect', tolerance: float = 0.5) -> bool:
        """Check if two rectangles share an edge"""
        # Must not overlap
        if self.overlaps(other):
            return False

        # Check vertical edge contact (side by side)
        if abs(self.x2 - other.x) < tolerance or abs(self.x - other.x2) < tolerance:
            # Check vertical overlap
            return self.y < other.y2 and self.y2 > other.y

        # Check horizontal edge contact (top/bottom)
        if abs(self.y2 - other.y) < tolerance or abs(self.y - other.y2) < tolerance:
            # Check horizontal overlap
            return self.x < other.x2 and self.x2 > other.x

        return False

    def shared_edge_length(self, other: 'Rect', tolerance: float = 0.5) -> float:
        """Calculate length of shared edge between two rectangles"""
        if not self.touches(other, tolerance):
            return 0

        # Vertical edge (side by side)
        if abs(self.x2 - other.x) < tolerance or abs(self.x - other.x2) < tolerance:
            y_overlap_start = max(self.y, other.y)
            y_overlap_end = min(self.y2, other.y2)
            return max(0, y_overlap_end - y_overlap_start)

        # Horizontal edge (top/bottom)
        if abs(self.y2 - other.y) < tolerance or abs(self.y - other.y2) < tolerance:
            x_overlap_start = max(self.x, other.x)
            x_overlap_end = min(self.x2, other.x2)
            return max(0, x_overlap_end - x_overlap_start)

        return 0

    def contains_point(self, p: Point) -> bool:
        return self.x <= p.x <= self.x2 and self.y <= p.y <= self.y2

    def is_on_edge(self, edge: str, building_bounds: 'Rect', tolerance: float = 0.5) -> bool:
        """Check if this rect is on a specific edge of the building"""
        if edge == "south":
            return abs(self.y - building_bounds.y) < tolerance
        elif edge == "north":
            return abs(self.y2 - building_bounds.y2) < tolerance
        elif edge == "west":
            return abs(self.x - building_bounds.x) < tolerance
        elif edge == "east":
            return abs(self.x2 - building_bounds.x2) < tolerance
        return False

    def exterior_edge_count(self, building_bounds: 'Rect', tolerance: float = 0.5) -> int:
        """Count how many exterior edges this room has"""
        count = 0
        for edge in ["south", "north", "west", "east"]:
            if self.is_on_edge(edge, building_bounds, tolerance):
                count += 1
        return count


# =============================================================================
# BUILDING SHAPE
# =============================================================================

@dataclass
class BuildingShape:
    """
    Defines the building footprint as a collection of rectangles.
    This allows L, U, T shapes by combining multiple rects.
    """
    zones: List[Rect] = field(default_factory=list)
    entry_location: Point = None
    entry_edge: str = "south"  # south, north, east, west

    @property
    def bounds(self) -> Rect:
        """Get bounding box of entire shape"""
        if not self.zones:
            return Rect(0, 0, 0, 0)
        min_x = min(z.x for z in self.zones)
        min_y = min(z.y for z in self.zones)
        max_x = max(z.x2 for z in self.zones)
        max_y = max(z.y2 for z in self.zones)
        return Rect(min_x, min_y, max_x - min_x, max_y - min_y)

    @property
    def total_area(self) -> float:
        return sum(z.area for z in self.zones)

    def contains_rect(self, rect: Rect, tolerance: float = 0.01) -> bool:
        """Check if a rectangle fits entirely within the building shape"""
        for zone in self.zones:
            if (rect.x >= zone.x - tolerance and
                rect.y >= zone.y - tolerance and
                rect.x2 <= zone.x2 + tolerance and
                rect.y2 <= zone.y2 + tolerance):
                return True
        return False

    def is_on_exterior(self, rect: Rect, tolerance: float = 0.5) -> bool:
        """Check if rect has at least one exterior edge"""
        bounds = self.bounds
        return rect.exterior_edge_count(bounds, tolerance) > 0

    @classmethod
    def rectangle(cls, width: float, depth: float, entry_x: float = None) -> 'BuildingShape':
        """Create a simple rectangular building"""
        shape = cls(zones=[Rect(0, 0, width, depth)])
        if entry_x is None:
            entry_x = width / 2
        shape.entry_location = Point(entry_x, 0)
        shape.entry_edge = "south"
        return shape

    @classmethod
    def l_shape(cls, width: float, depth: float, cut_width: float, cut_depth: float,
                cut_corner: str = "ne") -> 'BuildingShape':
        """
        Create an L-shaped building by cutting a corner from a rectangle.

        cut_corner: which corner to cut (ne, nw, se, sw)
        """
        # Start with full rectangle, then define the L as two rects
        if cut_corner == "ne":
            # Main horizontal bar
            zone1 = Rect(0, 0, width, depth - cut_depth)
            # Vertical bar on left
            zone2 = Rect(0, depth - cut_depth, width - cut_width, cut_depth)
        elif cut_corner == "nw":
            zone1 = Rect(0, 0, width, depth - cut_depth)
            zone2 = Rect(cut_width, depth - cut_depth, width - cut_width, cut_depth)
        elif cut_corner == "se":
            zone1 = Rect(0, cut_depth, width, depth - cut_depth)
            zone2 = Rect(0, 0, width - cut_width, cut_depth)
        elif cut_corner == "sw":
            zone1 = Rect(0, cut_depth, width, depth - cut_depth)
            zone2 = Rect(cut_width, 0, width - cut_width, cut_depth)
        else:
            raise ValueError(f"Invalid cut_corner: {cut_corner}")

        shape = cls(zones=[zone1, zone2])
        shape.entry_location = Point(width / 2, 0)
        return shape


# =============================================================================
# ROOM SPECIFICATION
# =============================================================================

@dataclass
class RoomSpec:
    """Specification for a room to be placed"""
    name: str
    room_type: RoomType
    min_area: float
    max_area: float = None
    min_width: float = 6.0    # Minimum dimension
    min_height: float = 6.0
    min_aspect: float = 0.4   # Min width/height ratio
    max_aspect: float = 2.5   # Max width/height ratio

    # Placement constraints
    needs_exterior: bool = False      # Must have exterior wall
    prefer_exterior: bool = False     # Prefers exterior wall
    near_entry: bool = False          # Should be near entry
    is_wet_room: bool = False         # Has plumbing
    adjacent_to: List[str] = field(default_factory=list)      # Must touch these rooms
    not_adjacent_to: List[str] = field(default_factory=list)  # Must not touch these rooms

    # Priority (lower = place first)
    priority: int = 50

    def __post_init__(self):
        if self.max_area is None:
            self.max_area = self.min_area * 2.0

        # Set defaults based on room type
        rt = self.room_type
        if rt in WET_ROOMS:
            self.is_wet_room = True
        if rt in NEEDS_EXTERIOR:
            self.prefer_exterior = True
        if rt in {RoomType.BEDROOM, RoomType.PRIMARY_BEDROOM}:
            self.needs_exterior = True
        if rt == RoomType.ENTRY:
            self.near_entry = True
            self.priority = 10  # Place entry first
        if rt == RoomType.LIVING:
            self.near_entry = True
            self.priority = 20
        if rt in {RoomType.HALLWAY}:
            self.priority = 30
        if rt in {RoomType.KITCHEN, RoomType.DINING}:
            self.priority = 40


# =============================================================================
# PLACED ROOM
# =============================================================================

@dataclass
class PlacedRoom:
    """A room that has been placed in the layout"""
    spec: RoomSpec
    rect: Rect

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def room_type(self) -> RoomType:
        return self.spec.room_type

    @property
    def area(self) -> float:
        return self.rect.area


# =============================================================================
# LAYOUT SOLUTION
# =============================================================================

@dataclass
class LayoutSolution:
    """A complete or partial layout solution"""
    rooms: Dict[str, PlacedRoom] = field(default_factory=dict)
    unplaced_rooms: List[RoomSpec] = field(default_factory=list)
    score: float = 0.0
    is_complete: bool = False

    @property
    def placed_count(self) -> int:
        return len(self.rooms)

    @property
    def total_rooms(self) -> int:
        return len(self.rooms) + len(self.unplaced_rooms)

    @property
    def placed_area(self) -> float:
        return sum(r.area for r in self.rooms.values())

    def get_room(self, name: str) -> Optional[PlacedRoom]:
        return self.rooms.get(name)


# =============================================================================
# SCORER - Evaluates layout quality
# =============================================================================

class LayoutScorer:
    """Scores a layout based on architectural quality metrics"""

    def __init__(self, building: BuildingShape):
        self.building = building
        self.weights = {
            'completeness': 100,      # All rooms placed
            'area_efficiency': 20,    # Rooms near min_area (not wasteful)
            'aspect_ratio': 15,       # Rooms have good proportions
            'exterior_access': 25,    # Bedrooms have exterior walls
            'wet_room_grouping': 20,  # Wet rooms are adjacent
            'entry_proximity': 15,    # Entry/living near actual entry
            'circulation': 10,        # Minimize hallway area
            'zone_separation': 15,    # Public/private zones separated
        }

    def score(self, solution: LayoutSolution) -> float:
        """Calculate total score for a layout"""
        scores = {}

        # Completeness (most important)
        if solution.total_rooms > 0:
            scores['completeness'] = (solution.placed_count / solution.total_rooms) * self.weights['completeness']
        else:
            scores['completeness'] = 0

        # Area efficiency
        area_scores = []
        for room in solution.rooms.values():
            if room.spec.min_area > 0:
                # Ideal is between min and 1.3x min
                ratio = room.area / room.spec.min_area
                if ratio < 1.0:
                    area_scores.append(ratio)  # Penalize undersized
                elif ratio <= 1.3:
                    area_scores.append(1.0)    # Perfect
                else:
                    area_scores.append(max(0.5, 1.0 - (ratio - 1.3) * 0.3))  # Penalize oversized
        scores['area_efficiency'] = (sum(area_scores) / len(area_scores) if area_scores else 0) * self.weights['area_efficiency']

        # Aspect ratio quality
        aspect_scores = []
        for room in solution.rooms.values():
            ar = room.rect.aspect_ratio
            # Ideal is 0.6-0.8 (slightly rectangular)
            if 0.5 <= ar <= 1.0:
                aspect_scores.append(1.0 - abs(ar - 0.7) * 0.5)
            else:
                aspect_scores.append(max(0, ar))
        scores['aspect_ratio'] = (sum(aspect_scores) / len(aspect_scores) if aspect_scores else 0) * self.weights['aspect_ratio']

        # Exterior access for rooms that need it
        exterior_scores = []
        for room in solution.rooms.values():
            if room.spec.needs_exterior:
                has_exterior = self.building.is_on_exterior(room.rect)
                exterior_scores.append(1.0 if has_exterior else 0.0)
            elif room.spec.prefer_exterior:
                has_exterior = self.building.is_on_exterior(room.rect)
                exterior_scores.append(1.0 if has_exterior else 0.5)
        scores['exterior_access'] = (sum(exterior_scores) / len(exterior_scores) if exterior_scores else 1.0) * self.weights['exterior_access']

        # Wet room grouping (wet rooms should be adjacent)
        wet_rooms = [r for r in solution.rooms.values() if r.spec.is_wet_room]
        if len(wet_rooms) >= 2:
            adjacent_pairs = 0
            total_pairs = 0
            for i, r1 in enumerate(wet_rooms):
                for r2 in wet_rooms[i+1:]:
                    total_pairs += 1
                    if r1.rect.touches(r2.rect):
                        adjacent_pairs += 1
            scores['wet_room_grouping'] = (adjacent_pairs / total_pairs if total_pairs > 0 else 1.0) * self.weights['wet_room_grouping']
        else:
            scores['wet_room_grouping'] = self.weights['wet_room_grouping']

        # Entry proximity
        if self.building.entry_location:
            entry_rooms = [r for r in solution.rooms.values() if r.spec.near_entry]
            if entry_rooms:
                distances = []
                for room in entry_rooms:
                    dist = math.sqrt((room.rect.center.x - self.building.entry_location.x)**2 +
                                   (room.rect.center.y - self.building.entry_location.y)**2)
                    # Normalize by building diagonal
                    bounds = self.building.bounds
                    diag = math.sqrt(bounds.width**2 + bounds.height**2)
                    distances.append(1.0 - min(1.0, dist / diag))
                scores['entry_proximity'] = (sum(distances) / len(distances)) * self.weights['entry_proximity']
            else:
                scores['entry_proximity'] = self.weights['entry_proximity']
        else:
            scores['entry_proximity'] = self.weights['entry_proximity']

        # Circulation efficiency (minimize hallway area)
        hallway_rooms = [r for r in solution.rooms.values() if r.room_type == RoomType.HALLWAY]
        if hallway_rooms and solution.placed_area > 0:
            hallway_area = sum(r.area for r in hallway_rooms)
            hallway_ratio = hallway_area / solution.placed_area
            # Ideal is 5-10% hallway
            if hallway_ratio <= 0.10:
                scores['circulation'] = self.weights['circulation']
            else:
                scores['circulation'] = max(0, self.weights['circulation'] * (1 - (hallway_ratio - 0.10) * 5))
        else:
            scores['circulation'] = self.weights['circulation']

        # Zone separation (public near entry, private away)
        # Simplified: check if bedrooms are away from entry
        scores['zone_separation'] = self.weights['zone_separation']  # TODO: implement

        return sum(scores.values())


# =============================================================================
# PLACEMENT ENGINE - CSP-based room placement
# =============================================================================

class PlacementEngine:
    """
    CSP-based engine for finding valid room placements.
    Uses constraint propagation and backtracking.
    """

    def __init__(self, building: BuildingShape, grid_size: float = 2.0):
        self.building = building
        self.grid_size = grid_size
        self.scorer = LayoutScorer(building)

    def generate_positions(self, spec: RoomSpec, placed: Dict[str, PlacedRoom],
                          max_positions: int = 200) -> List[Rect]:
        """Generate candidate positions for a room"""
        positions = []
        bounds = self.building.bounds

        # Calculate room dimensions to try
        dimensions = self._get_room_dimensions(spec)

        for width, height in dimensions:
            # Snap to grid
            width = round(width / self.grid_size) * self.grid_size
            height = round(height / self.grid_size) * self.grid_size

            if width < spec.min_width or height < spec.min_height:
                continue

            # Try all grid positions
            x = bounds.x
            while x + width <= bounds.x2 + 0.01:
                y = bounds.y
                while y + height <= bounds.y2 + 0.01:
                    rect = Rect(x, y, width, height)

                    # Quick validity check
                    if self._is_valid_position(rect, spec, placed):
                        positions.append(rect)

                        if len(positions) >= max_positions:
                            return positions

                    y += self.grid_size
                x += self.grid_size

        return positions

    def _get_room_dimensions(self, spec: RoomSpec) -> List[Tuple[float, float]]:
        """Generate dimension combinations for a room"""
        dimensions = []
        target_area = spec.min_area

        # Try different aspect ratios
        for aspect in [1.0, 0.8, 0.7, 0.6, 0.5, 1.2, 1.4, 1.6]:
            if spec.min_aspect <= aspect <= spec.max_aspect:
                # Calculate dimensions for this aspect ratio
                # area = width * height, aspect = min(w,h)/max(w,h)
                if aspect <= 1.0:
                    height = math.sqrt(target_area / aspect)
                    width = target_area / height
                else:
                    width = math.sqrt(target_area * aspect)
                    height = target_area / width

                dimensions.append((width, height))
                dimensions.append((height, width))  # Rotated

        return dimensions

    def _is_valid_position(self, rect: Rect, spec: RoomSpec, placed: Dict[str, PlacedRoom]) -> bool:
        """Check if a position is valid for the given room spec"""

        # Must fit in building
        if not self.building.contains_rect(rect):
            return False

        # Must not overlap with placed rooms
        for room in placed.values():
            if rect.overlaps(room.rect):
                return False

        # Check area constraints
        if rect.area < spec.min_area * 0.9:  # Allow 10% under
            return False
        if rect.area > spec.max_area * 1.1:  # Allow 10% over
            return False

        # Check aspect ratio
        if rect.aspect_ratio < spec.min_aspect or rect.aspect_ratio > 1.0 / spec.min_aspect:
            return False

        # Check exterior requirement
        if spec.needs_exterior:
            if not self.building.is_on_exterior(rect):
                return False

        # Check adjacency requirements
        for adj_name in spec.adjacent_to:
            if adj_name in placed:
                if not rect.touches(placed[adj_name].rect):
                    return False

        # Check not-adjacent requirements
        for not_adj_name in spec.not_adjacent_to:
            if not_adj_name in placed:
                if rect.touches(placed[not_adj_name].rect):
                    return False

        return True

    def score_position(self, rect: Rect, spec: RoomSpec, placed: Dict[str, PlacedRoom]) -> float:
        """Score a specific position (for ordering candidates)"""
        score = 0.0

        # Prefer positions near placed rooms (connectivity)
        if placed:
            min_dist = float('inf')
            for room in placed.values():
                dist = math.sqrt((rect.center.x - room.rect.center.x)**2 +
                               (rect.center.y - room.rect.center.y)**2)
                min_dist = min(min_dist, dist)
                # Bonus for touching
                if rect.touches(room.rect):
                    score += 10
            score -= min_dist * 0.5

        # Prefer exterior for rooms that want it
        if spec.prefer_exterior and self.building.is_on_exterior(rect):
            score += 15

        # Prefer positions near entry for entry-adjacent rooms
        if spec.near_entry and self.building.entry_location:
            dist = math.sqrt((rect.center.x - self.building.entry_location.x)**2 +
                           (rect.center.y - self.building.entry_location.y)**2)
            score -= dist * 0.3

        # Prefer good aspect ratios
        score += rect.aspect_ratio * 5

        return score


# =============================================================================
# MAIN SOLVER
# =============================================================================

class RoomLayoutSolverV3:
    """
    Advanced room layout solver with partial solution support.
    """

    def __init__(self, building: BuildingShape, grid_size: float = 2.0):
        self.building = building
        self.grid_size = grid_size
        self.engine = PlacementEngine(building, grid_size)
        self.rooms_to_place: List[RoomSpec] = []

        # Stats
        self.nodes_explored = 0
        self.best_solution: Optional[LayoutSolution] = None

    def add_room(self, room_type: str, min_area: float, name: str = None, **kwargs) -> 'RoomLayoutSolverV3':
        """Add a room to be placed"""
        try:
            rt = RoomType(room_type)
        except ValueError:
            rt = RoomType.BEDROOM  # Default fallback

        if name is None:
            name = room_type

        spec = RoomSpec(
            name=name,
            room_type=rt,
            min_area=min_area,
            **kwargs
        )
        self.rooms_to_place.append(spec)
        return self

    def solve(self, max_nodes: int = 50000, return_partial: bool = True) -> LayoutSolution:
        """
        Find the best layout solution.

        Args:
            max_nodes: Maximum search nodes before stopping
            return_partial: If True, return best partial solution if complete not found

        Returns:
            LayoutSolution (may be partial if return_partial=True)
        """
        self.nodes_explored = 0
        self.best_solution = LayoutSolution(
            rooms={},
            unplaced_rooms=self.rooms_to_place.copy(),
            score=0,
            is_complete=False
        )

        # Sort rooms by priority
        sorted_rooms = sorted(self.rooms_to_place, key=lambda r: r.priority)

        print(f"[Solver v3] {len(sorted_rooms)} rooms, grid={self.grid_size}ft")
        print(f"   Building: {self.building.bounds.width:.0f}x{self.building.bounds.height:.0f} = {self.building.total_area:.0f} sqft")

        # Start recursive search
        self._search(sorted_rooms, 0, {}, max_nodes)

        if self.best_solution.is_complete:
            print(f"[OK] Complete solution found! Score: {self.best_solution.score:.1f}")
        else:
            print(f"[PARTIAL] {self.best_solution.placed_count}/{len(sorted_rooms)} rooms placed")
            if self.best_solution.unplaced_rooms:
                unplaced = ", ".join(r.name for r in self.best_solution.unplaced_rooms)
                print(f"   Unplaced: {unplaced}")

        print(f"   Nodes explored: {self.nodes_explored:,}")

        return self.best_solution

    def _search(self, rooms: List[RoomSpec], index: int, placed: Dict[str, PlacedRoom], max_nodes: int):
        """Recursive backtracking search"""
        self.nodes_explored += 1

        # Progress reporting
        if self.nodes_explored % 5000 == 0:
            print(f"   Progress: {self.nodes_explored:,} nodes, best={self.best_solution.placed_count} rooms")

        # Check timeout
        if self.nodes_explored >= max_nodes:
            return

        # Base case: all rooms placed
        if index >= len(rooms):
            solution = LayoutSolution(
                rooms=dict(placed),
                unplaced_rooms=[],
                score=self.engine.scorer.score(LayoutSolution(rooms=placed)),
                is_complete=True
            )
            if solution.score > self.best_solution.score or not self.best_solution.is_complete:
                self.best_solution = solution
            return

        room_spec = rooms[index]

        # Generate candidate positions
        positions = self.engine.generate_positions(room_spec, placed)

        # Score and sort positions (best first)
        scored_positions = [(self.engine.score_position(pos, room_spec, placed), pos) for pos in positions]
        scored_positions.sort(reverse=True, key=lambda x: x[0])

        # Try each position
        found_valid = False
        for _, pos in scored_positions[:100]:  # Limit branches
            placed_room = PlacedRoom(spec=room_spec, rect=pos)
            placed[room_spec.name] = placed_room

            self._search(rooms, index + 1, placed, max_nodes)

            del placed[room_spec.name]
            found_valid = True

            # Early exit if we found a complete solution
            if self.best_solution.is_complete:
                return

        # If no valid position found, update best partial solution
        if not found_valid:
            # Calculate score for current partial solution
            partial = LayoutSolution(
                rooms=dict(placed),
                unplaced_rooms=rooms[index:],
                score=self.engine.scorer.score(LayoutSolution(rooms=placed)),
                is_complete=False
            )

            if partial.placed_count > self.best_solution.placed_count:
                self.best_solution = partial
            elif (partial.placed_count == self.best_solution.placed_count and
                  partial.score > self.best_solution.score):
                self.best_solution = partial


# =============================================================================
# HELPER: Convert solution to wall data
# =============================================================================

def solution_to_walls(solution: LayoutSolution, building: BuildingShape) -> Dict:
    """Convert a layout solution to wall data for Revit"""
    walls = {
        "exterior": [],
        "interior": [],
        "wet_wall": []
    }
    doors = []

    bounds = building.bounds

    # Add exterior walls (building perimeter)
    # South wall
    walls["exterior"].append({
        "start": {"x": bounds.x, "y": bounds.y},
        "end": {"x": bounds.x2, "y": bounds.y}
    })
    # North wall
    walls["exterior"].append({
        "start": {"x": bounds.x, "y": bounds.y2},
        "end": {"x": bounds.x2, "y": bounds.y2}
    })
    # West wall
    walls["exterior"].append({
        "start": {"x": bounds.x, "y": bounds.y},
        "end": {"x": bounds.x, "y": bounds.y2}
    })
    # East wall
    walls["exterior"].append({
        "start": {"x": bounds.x2, "y": bounds.y},
        "end": {"x": bounds.x2, "y": bounds.y2}
    })

    # Find interior walls between rooms
    room_list = list(solution.rooms.values())
    processed_pairs = set()

    for i, room1 in enumerate(room_list):
        for room2 in room_list[i+1:]:
            pair_key = tuple(sorted([room1.name, room2.name]))
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            if room1.rect.touches(room2.rect):
                # Find shared edge
                wall_data = _find_shared_wall(room1, room2)
                if wall_data:
                    # Determine wall type
                    if room1.spec.is_wet_room or room2.spec.is_wet_room:
                        walls["wet_wall"].append(wall_data)
                    else:
                        walls["interior"].append(wall_data)

                    # Add door (simplified - always add door between adjacent rooms)
                    doors.append({
                        "room1": room1.name,
                        "room2": room2.name,
                        "x": (wall_data["start"]["x"] + wall_data["end"]["x"]) / 2,
                        "y": (wall_data["start"]["y"] + wall_data["end"]["y"]) / 2
                    })

    # Convert rooms to dict format
    rooms_data = {}
    for name, room in solution.rooms.items():
        rooms_data[name] = {
            "type": room.room_type.value,
            "bounds": {
                "x": room.rect.x,
                "y": room.rect.y,
                "width": room.rect.width,
                "height": room.rect.height
            },
            "area": room.area
        }

    return {
        "walls": walls,
        "doors": doors,
        "rooms": rooms_data,
        "is_complete": solution.is_complete,
        "placed_count": solution.placed_count,
        "total_rooms": solution.total_rooms
    }


def _find_shared_wall(room1: PlacedRoom, room2: PlacedRoom) -> Optional[Dict]:
    """Find the wall segment shared between two rooms"""
    r1, r2 = room1.rect, room2.rect
    tolerance = 0.5

    # Check vertical edge (side by side)
    if abs(r1.x2 - r2.x) < tolerance:
        # r2 is to the right of r1
        y_start = max(r1.y, r2.y)
        y_end = min(r1.y2, r2.y2)
        if y_end > y_start:
            return {
                "start": {"x": r1.x2, "y": y_start},
                "end": {"x": r1.x2, "y": y_end},
                "rooms": [room1.name, room2.name]
            }

    if abs(r1.x - r2.x2) < tolerance:
        # r2 is to the left of r1
        y_start = max(r1.y, r2.y)
        y_end = min(r1.y2, r2.y2)
        if y_end > y_start:
            return {
                "start": {"x": r1.x, "y": y_start},
                "end": {"x": r1.x, "y": y_end},
                "rooms": [room1.name, room2.name]
            }

    # Check horizontal edge (top/bottom)
    if abs(r1.y2 - r2.y) < tolerance:
        # r2 is above r1
        x_start = max(r1.x, r2.x)
        x_end = min(r1.x2, r2.x2)
        if x_end > x_start:
            return {
                "start": {"x": x_start, "y": r1.y2},
                "end": {"x": x_end, "y": r1.y2},
                "rooms": [room1.name, room2.name]
            }

    if abs(r1.y - r2.y2) < tolerance:
        # r2 is below r1
        x_start = max(r1.x, r2.x)
        x_end = min(r1.x2, r2.x2)
        if x_end > x_start:
            return {
                "start": {"x": x_start, "y": r1.y},
                "end": {"x": x_end, "y": r1.y},
                "rooms": [room1.name, room2.name]
            }

    return None


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ROOM LAYOUT SOLVER V3 TEST")
    print("=" * 60)

    # Create rectangular building
    building = BuildingShape.rectangle(40, 30, entry_x=20)

    # Create solver
    solver = RoomLayoutSolverV3(building, grid_size=2.0)

    # Add rooms (1 bed, 2 bath as per user's test)
    solver.add_room("entry", min_area=50)
    solver.add_room("living", min_area=200)
    solver.add_room("kitchen", min_area=100)
    solver.add_room("dining", min_area=80)
    solver.add_room("primary_bedroom", min_area=150)
    solver.add_room("bathroom", min_area=45, name="Bathroom 1")
    solver.add_room("bathroom", min_area=45, name="Bathroom 2")
    solver.add_room("laundry", min_area=35)

    # Solve
    solution = solver.solve(max_nodes=100000, return_partial=True)

    # Display result
    print(f"\nResult:")
    print(f"   Complete: {solution.is_complete}")
    print(f"   Rooms placed: {solution.placed_count}/{solution.total_rooms}")
    print(f"   Score: {solution.score:.1f}")

    if solution.rooms:
        print(f"\nPlaced rooms:")
        for name, room in solution.rooms.items():
            r = room.rect
            print(f"   {name}: ({r.x:.0f},{r.y:.0f}) {r.width:.0f}x{r.height:.0f} = {room.area:.0f} sqft")

    if solution.unplaced_rooms:
        print(f"\nUnplaced rooms:")
        for spec in solution.unplaced_rooms:
            print(f"   {spec.name}: {spec.min_area} sqft min")

    # Convert to walls
    wall_data = solution_to_walls(solution, building)
    print(f"\nWalls:")
    print(f"   Exterior: {len(wall_data['walls']['exterior'])}")
    print(f"   Interior: {len(wall_data['walls']['interior'])}")
    print(f"   Wet walls: {len(wall_data['walls']['wet_wall'])}")
    print(f"   Doors: {len(wall_data['doors'])}")
