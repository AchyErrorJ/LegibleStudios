"""
Coordinate Solver
=================
Places rooms in space and generates wall coordinates.

Input: LayoutSpec (wall graph + constraints + room areas)
Output: PlacedLayout (rooms with coordinates, walls with coordinates)

Algorithm:
1. Build adjacency graph from constraints
2. Use priority-based placement (entry first, then connected rooms)
3. Grid-based positioning with constraint checking
4. Generate wall coordinates from room boundaries
"""

from typing import Dict, List, Optional, Set, Tuple, NamedTuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import math
import heapq

from room_relationships import (
    SpatialGraph, Zone, ExteriorRequirement, ROOM_TYPES
)
from wall_graph import (
    WallGraph, WallSegment, WallOpening, LayoutSpec,
    AdjacencyConstraints, RoomAreaSpec, OpeningType, WallType
)


# =============================================================================
# GEOMETRY PRIMITIVES
# =============================================================================

class Point(NamedTuple):
    x: float
    y: float


class Rect(NamedTuple):
    """Axis-aligned rectangle"""
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
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point:
        return Point(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def aspect(self) -> float:
        if self.width == 0 or self.height == 0:
            return 0
        return min(self.width, self.height) / max(self.width, self.height)

    def overlaps(self, other: 'Rect', tolerance: float = 0.01) -> bool:
        return (self.x < other.x2 - tolerance and
                self.x2 > other.x + tolerance and
                self.y < other.y2 - tolerance and
                self.y2 > other.y + tolerance)

    def touches(self, other: 'Rect', tolerance: float = 0.5) -> bool:
        """Check if rectangles share an edge (adjacent but not overlapping)"""
        if self.overlaps(other):
            return False

        # Vertical adjacency (side by side)
        if abs(self.x2 - other.x) < tolerance or abs(self.x - other.x2) < tolerance:
            return self.y < other.y2 and self.y2 > other.y

        # Horizontal adjacency (top/bottom)
        if abs(self.y2 - other.y) < tolerance or abs(self.y - other.y2) < tolerance:
            return self.x < other.x2 and self.x2 > other.x

        return False

    def shared_edge(self, other: 'Rect', tolerance: float = 0.5) -> Optional[Tuple[Point, Point]]:
        """Get the shared edge between two touching rectangles"""
        if not self.touches(other, tolerance):
            return None

        # Right edge of self touches left edge of other
        if abs(self.x2 - other.x) < tolerance:
            y1 = max(self.y, other.y)
            y2 = min(self.y2, other.y2)
            if y2 > y1:
                return (Point(self.x2, y1), Point(self.x2, y2))

        # Left edge of self touches right edge of other
        if abs(self.x - other.x2) < tolerance:
            y1 = max(self.y, other.y)
            y2 = min(self.y2, other.y2)
            if y2 > y1:
                return (Point(self.x, y1), Point(self.x, y2))

        # Top edge of self touches bottom edge of other
        if abs(self.y2 - other.y) < tolerance:
            x1 = max(self.x, other.x)
            x2 = min(self.x2, other.x2)
            if x2 > x1:
                return (Point(x1, self.y2), Point(x2, self.y2))

        # Bottom edge of self touches top edge of other
        if abs(self.y - other.y2) < tolerance:
            x1 = max(self.x, other.x)
            x2 = min(self.x2, other.x2)
            if x2 > x1:
                return (Point(x1, self.y), Point(x2, self.y))

        return None

    def is_on_boundary(self, bounds: 'Rect', edge: str, tolerance: float = 0.5) -> bool:
        """Check if this rect touches a specific edge of bounds"""
        if edge == "south":
            return abs(self.y - bounds.y) < tolerance
        elif edge == "north":
            return abs(self.y2 - bounds.y2) < tolerance
        elif edge == "west":
            return abs(self.x - bounds.x) < tolerance
        elif edge == "east":
            return abs(self.x2 - bounds.x2) < tolerance
        return False

    def touches_any_boundary(self, bounds: 'Rect', tolerance: float = 0.5) -> bool:
        """Check if this rect touches any edge of bounds"""
        return any(self.is_on_boundary(bounds, edge, tolerance)
                   for edge in ["south", "north", "east", "west"])


# =============================================================================
# PLACED ROOM
# =============================================================================

@dataclass
class PlacedRoom:
    """A room with its position"""
    room_id: str
    rect: Rect

    @property
    def area(self) -> float:
        return self.rect.area

    @property
    def center(self) -> Point:
        return self.rect.center


# =============================================================================
# WALL COORDINATE
# =============================================================================

@dataclass
class WallCoordinate:
    """A wall with its coordinates"""
    wall_id: str
    start: Point
    end: Point
    wall_type: WallType
    room1: str
    room2: str
    openings: List[Tuple[Point, Point, OpeningType]] = field(default_factory=list)

    @property
    def length(self) -> float:
        return math.sqrt((self.end.x - self.start.x)**2 + (self.end.y - self.start.y)**2)

    @property
    def is_horizontal(self) -> bool:
        return abs(self.end.y - self.start.y) < 0.1

    @property
    def is_vertical(self) -> bool:
        return abs(self.end.x - self.start.x) < 0.1

    def to_dict(self) -> Dict:
        """Convert to dict for JSON output"""
        return {
            "wall_id": self.wall_id,
            "start": {"x": self.start.x, "y": self.start.y},
            "end": {"x": self.end.x, "y": self.end.y},
            "wall_type": self.wall_type.value,
            "room1": self.room1,
            "room2": self.room2,
            "length": self.length,
            "openings": [
                {"start": {"x": s.x, "y": s.y}, "end": {"x": e.x, "y": e.y}, "type": t.value}
                for s, e, t in self.openings
            ]
        }


# =============================================================================
# PLACED LAYOUT (Output)
# =============================================================================

@dataclass
class PlacedLayout:
    """Complete layout with coordinates"""
    rooms: Dict[str, PlacedRoom] = field(default_factory=dict)
    walls: List[WallCoordinate] = field(default_factory=list)
    building_bounds: Rect = None

    # Metrics
    is_complete: bool = False
    unplaced_rooms: List[str] = field(default_factory=list)
    score: float = 0.0

    def get_room(self, room_id: str) -> Optional[PlacedRoom]:
        return self.rooms.get(room_id)

    def get_walls_for_room(self, room_id: str) -> List[WallCoordinate]:
        return [w for w in self.walls if w.room1 == room_id or w.room2 == room_id]

    def get_exterior_walls(self) -> List[WallCoordinate]:
        return [w for w in self.walls if w.room1 == "exterior" or w.room2 == "exterior"]

    def get_interior_walls(self) -> List[WallCoordinate]:
        return [w for w in self.walls if w.room1 != "exterior" and w.room2 != "exterior"]

    def to_dict(self) -> Dict:
        """Convert to dict for JSON output"""
        return {
            "rooms": {
                room_id: {
                    "x": room.rect.x,
                    "y": room.rect.y,
                    "width": room.rect.width,
                    "height": room.rect.height,
                    "area": room.area
                }
                for room_id, room in self.rooms.items()
            },
            "walls": [w.to_dict() for w in self.walls],
            "building_bounds": {
                "x": self.building_bounds.x,
                "y": self.building_bounds.y,
                "width": self.building_bounds.width,
                "height": self.building_bounds.height
            } if self.building_bounds else None,
            "is_complete": self.is_complete,
            "unplaced_rooms": self.unplaced_rooms,
            "score": self.score
        }

    def summary(self) -> str:
        """Get text summary"""
        lines = [
            f"Placed Layout: {len(self.rooms)} rooms, {len(self.walls)} walls",
            f"Complete: {self.is_complete}",
            f"Score: {self.score:.1f}",
        ]
        if self.unplaced_rooms:
            lines.append(f"Unplaced: {self.unplaced_rooms}")

        lines.append("\nRooms:")
        for room_id, room in self.rooms.items():
            r = room.rect
            lines.append(f"  {room_id}: ({r.x:.0f},{r.y:.0f}) {r.width:.0f}x{r.height:.0f} = {room.area:.0f}sqft")

        return "\n".join(lines)


# =============================================================================
# COORDINATE SOLVER
# =============================================================================

class CoordinateSolver:
    """
    Solves for room positions and generates wall coordinates.

    Improved algorithm:
    1. Topological ordering based on must-touch dependencies
    2. Strategic position generation near all placed rooms
    3. Tiered constraint relaxation (hard/soft/preference)
    4. Increased branching for constrained rooms
    """

    def __init__(self, layout_spec: LayoutSpec, grid_size: float = 2.0,
                 allow_extensions: bool = True, max_extension: float = 0.3,
                 creative_mode: bool = False):
        """
        Initialize the coordinate solver.

        Args:
            layout_spec: Room areas and constraints
            grid_size: Placement grid size (default 2.0 ft)
            allow_extensions: Allow rooms to extend beyond initial bounds
            max_extension: Maximum extension as fraction of building size
            creative_mode: If True, use organic growth with liberal dead space
                          to create interesting non-rectangular floor plans
        """
        self.spec = layout_spec
        self.grid = grid_size
        self.initial_bounds = Rect(0, 0, layout_spec.building_width, layout_spec.building_depth)
        self.bounds = self.initial_bounds  # Current bounds (may expand)

        # Extension settings
        self.allow_extensions = allow_extensions
        self.max_extension = max_extension  # Max 30% extension in any direction

        # Creative mode - organic growth with liberal dead space
        self.creative_mode = creative_mode

        # Track placement state
        self.placed: Dict[str, PlacedRoom] = {}
        self.best_partial: Dict[str, PlacedRoom] = {}
        self.nodes_explored = 0

        # Constraint relaxation state
        self.relaxed_constraints: Set[str] = set()  # Rooms with relaxed must-touch
        self.exterior_relaxed: Set[str] = set()  # Rooms with relaxed exterior requirement

    def solve(self, max_nodes: int = 50000) -> PlacedLayout:
        """Solve for room positions and generate wall coordinates"""

        mode = "creative" if self.creative_mode else "standard"
        print(f"[Solver] Starting ({mode}): {len(self.spec.room_areas)} rooms in {self.spec.building_width}x{self.spec.building_depth}")

        # Get placement order (prioritized)
        order = self._get_placement_order()
        print(f"[Solver] Placement order: {[r for r in order]}")

        # Place rooms - use creative mode if enabled
        if self.creative_mode:
            self._place_rooms_creative(order, max_nodes)
        else:
            self._place_rooms(order, max_nodes)

        # Use best partial if no complete solution found
        if not self.placed and self.best_partial:
            self.placed = self.best_partial
            print(f"[Solver] Using best partial solution: {len(self.placed)} rooms")

        # Generate wall coordinates from placed rooms
        walls = self._generate_wall_coordinates()

        # Get actual building bounds (may be larger than initial if extended)
        actual_bounds = self._get_current_bounds()

        # Build result
        layout = PlacedLayout(
            rooms=dict(self.placed),
            walls=walls,
            building_bounds=actual_bounds,
            is_complete=len(self.placed) == len(self.spec.room_areas),
            unplaced_rooms=[r for r in self.spec.room_areas if r not in self.placed],
            score=self._calculate_score()
        )

        print(f"[Solver] Done: {len(self.placed)}/{len(self.spec.room_areas)} rooms placed")
        print(f"[Solver] Nodes explored: {self.nodes_explored}")

        return layout

    def _get_placement_order(self) -> List[str]:
        """
        Get rooms in order of placement priority.

        Key insight: Rooms with BOTH exterior requirements AND must-touch
        constraints (like bedroom_2) need higher priority than rooms that
        only have must-touch constraints (like primary_bath).

        Priority levels:
        0: Entry (anchor point)
        1: Living/great room (main public space)
        2: Hallway (circulation hub)
        3: Kitchen/dining (connected to living)
        4: ALL bedrooms together (need exterior + hallway access)
        5: Garage (needs large exterior)
        6: Attached rooms without exterior needs (primary_bath, closets)
        7: Service rooms (laundry, utility)
        """
        all_rooms = list(self.spec.room_areas.keys())

        # Count how many rooms each room connects to (hub score)
        connection_counts = {}
        for room_id in all_rooms:
            must_touch = self.spec.constraints.must_touch.get(room_id, set())
            connection_counts[room_id] = len(must_touch)

        def get_priority(room_id: str) -> Tuple[int, int, int, int]:
            """Calculate priority tuple (lower = earlier placement)"""
            # Handle room types correctly - primary_bedroom is a single key
            if room_id in ROOM_TYPES:
                room_spec = ROOM_TYPES[room_id]
                room_type = room_id
            else:
                room_type = room_id.split("_")[0]  # "bedroom_2" -> "bedroom"
                room_spec = ROOM_TYPES.get(room_type, ROOM_TYPES.get("bedroom"))

            # Check if room needs exterior
            needs_exterior = room_id in self.spec.constraints.must_have_exterior
            prefers_exterior = room_id in self.spec.constraints.prefer_exterior

            # Level 1: Core rooms (entry, living, hallway)
            if room_id == "entry":
                level = 0
            elif room_type in ["living", "foyer", "great_room"]:
                level = 1
            elif room_type == "hallway":
                level = 2
            elif room_type in ["dining", "kitchen"]:
                level = 3
            # Level 3.5: Garage needs large exterior + entry adjacency
            # Place BEFORE bedrooms to ensure enough exterior space
            elif room_id == "garage":
                level = 3.5  # Garage before bedrooms (needs large contiguous exterior)
            # Level 4: ALL bedrooms together (primary and secondary)
            # This ensures bedroom_2 is placed while exterior space exists
            elif room_id == "primary_bedroom" or room_type == "bedroom":
                level = 4  # All bedrooms at same priority
            # Level 3: Attached rooms without exterior requirements
            elif room_id in ["primary_bath", "primary_closet"]:
                level = 6  # Primary suite attachments (no exterior needed)
            elif room_type in ["closet", "walk_in_closet"]:
                level = 7
            elif room_type in ["bathroom", "powder_room"]:
                level = 7
            elif room_type == "laundry":
                level = 8  # Service rooms last
            else:
                # Level by zone
                zone_level = {
                    Zone.PUBLIC: 4,
                    Zone.CIRCULATION: 5,
                    Zone.PRIVATE: 6,
                    Zone.SERVICE: 8
                }.get(room_spec.zone, 8)
                level = zone_level

            # Sub-priority: rooms with exterior requirements placed earlier
            exterior_priority = 0
            if needs_exterior:
                exterior_priority = -10
            elif prefers_exterior:
                exterior_priority = -5

            # Tertiary: larger rooms first (by min_area)
            area_spec = self.spec.room_areas.get(room_id)
            size_priority = -(area_spec.min_area if area_spec else 0)

            # Quaternary: hub rooms (more connections) placed earlier
            hub_priority = -connection_counts.get(room_id, 0)

            return (level, exterior_priority, size_priority, hub_priority)

        # Sort all rooms by priority
        all_rooms.sort(key=get_priority)

        return all_rooms

    def _place_rooms(self, order: List[str], max_nodes: int):
        """Place rooms using backtracking search with constraint relaxation"""

        # Reorder to place attached rooms immediately after their parents
        order = self._interleave_attached_rooms(order)

        # Track dead space count for unique IDs
        self.dead_space_count = 0

        # First pass: strict constraints, allow skipping for faster search
        self._search(order, 0, max_nodes, relaxed=False, allow_skip=True)

        # Second pass: use dead space to extend circulation toward stuck rooms
        if len(self.placed) < len(order):
            remaining = [r for r in order if r not in self.placed]
            print(f"[Solver] Pass 2: Growing circulation with dead space for {remaining}...")
            dead_space_before = self.dead_space_count

            for room_id in list(remaining):
                if room_id in self.placed:
                    continue  # Already placed in retry
                if self._try_place_with_dead_space(room_id):
                    print(f"[Solver] Placed {room_id} using dead space bridge")
                    # Dead space grew - re-evaluate all other unplaced rooms
                    if self.dead_space_count > dead_space_before:
                        still_unplaced = [r for r in remaining if r not in self.placed]
                        retry_count = self._retry_unplaced_after_dead_space(still_unplaced)
                        if retry_count > 0:
                            print(f"[Solver] Re-evaluation placed {retry_count} more rooms")
                        dead_space_before = self.dead_space_count

        # Third pass: relax exterior requirements for remaining rooms
        if len(self.placed) < len(order):
            print(f"[Solver] Pass 3: Relaxing exterior requirements...")
            remaining = [r for r in order if r not in self.placed]
            for room_id in remaining:
                self.exterior_relaxed.add(room_id)
            self._search(remaining, 0, max_nodes // 2, relaxed=False, allow_skip=True)

        # Fourth pass: fully relaxed
        if len(self.placed) < len(order):
            print(f"[Solver] Pass 4: Full constraint relaxation...")
            remaining = [r for r in order if r not in self.placed]
            self._search(remaining, 0, max_nodes // 2, relaxed=True, allow_skip=True)

    def _place_rooms_creative(self, order: List[str], max_nodes: int):
        """
        Creative mode placement - organic growth with liberal dead space.

        Instead of fitting rooms into a rectangle, this mode:
        1. Places entry as anchor, then grows outward organically
        2. Proactively adds dead space to create interesting circulation
        3. Allows non-rectangular building footprints (L, T, U shapes)
        4. Scores positions on constraint satisfaction + visual interest
        """
        self.dead_space_count = 0
        ds_size = max(self.grid, 3.0)

        print("[Creative] Growing building organically...")

        for room_id in order:
            if room_id in self.placed:
                continue

            area_spec = self.spec.room_areas.get(room_id)
            if not area_spec:
                continue

            # Try to place room normally first
            placed = self._try_place_single_creative(room_id, area_spec)

            if not placed:
                # Grow dead space to create new placement options
                placed = self._grow_creative_path(room_id, area_spec)

            if placed:
                # After placing a room, consider adding creative dead space
                # to create interesting hallway patterns
                self._add_creative_circulation()

        # Final pass: place any remaining rooms with relaxed constraints
        remaining = [r for r in order if r not in self.placed]
        if remaining:
            print(f"[Creative] Relaxed pass for: {remaining}")
            for room_id in remaining:
                self.exterior_relaxed.add(room_id)
                self.relaxed_constraints.add(room_id)
            self._search(remaining, 0, max_nodes // 2, relaxed=True, allow_skip=True)

        actual_rooms = len([r for r in self.placed if not r.startswith('dead_space_')])
        dead_spaces = len([r for r in self.placed if r.startswith('dead_space_')])
        print(f"[Creative] Result: {actual_rooms} rooms, {dead_spaces} circulation cells")

    def _try_place_single_creative(self, room_id: str, area_spec) -> bool:
        """Try to place a single room in creative mode with interest scoring."""
        candidates = self._generate_candidates(room_id, area_spec, relaxed=False)

        if not candidates:
            # Try with relaxed exterior for creative placement
            candidates = self._generate_candidates(room_id, area_spec, relaxed=True)

        if candidates:
            # Score with creative bonus for interesting positions
            scored = []
            for rect in candidates:
                base_score = self._score_position(room_id, rect, relaxed=False)
                creative_bonus = self._score_creative_interest(room_id, rect)
                scored.append((base_score + creative_bonus, rect))

            scored.sort(reverse=True, key=lambda x: x[0])

            for score, rect in scored[:30]:
                if score >= -50:  # More lenient in creative mode
                    self.placed[room_id] = PlacedRoom(room_id, rect)
                    return True

        return False

    def _score_creative_interest(self, room_id: str, rect: Rect) -> float:
        """Score how 'interesting' a position is for creative layouts."""
        score = 0.0

        # Bonus for positions that create non-rectangular footprint
        current_bounds = self._get_current_bounds()
        if self.placed:
            # Check if this position extends the building in an interesting way
            if rect.x < current_bounds.x or rect.x2 > current_bounds.x2:
                score += 15  # Extends width
            if rect.y < current_bounds.y or rect.y2 > current_bounds.y2:
                score += 15  # Extends depth

            # Bonus for L-shape or T-shape potential
            if self._creates_interesting_shape(rect):
                score += 25

        # Bonus for positions adjacent to dead space (uses circulation creatively)
        for placed_id, placed_room in self.placed.items():
            if placed_id.startswith('dead_space_') and rect.touches(placed_room.rect):
                score += 10

        # Slight penalty for perfectly aligned grid positions (too orderly)
        if rect.x % (self.grid * 3) == 0 and rect.y % (self.grid * 3) == 0:
            score -= 5

        return score

    def _creates_interesting_shape(self, rect: Rect) -> bool:
        """Check if adding this rect creates an L, T, or U shape."""
        if len(self.placed) < 3:
            return False

        # Get current building outline
        all_rects = [p.rect for p in self.placed.values()]
        all_rects.append(rect)

        # Calculate bounding box
        min_x = min(r.x for r in all_rects)
        max_x = max(r.x2 for r in all_rects)
        min_y = min(r.y for r in all_rects)
        max_y = max(r.y2 for r in all_rects)

        bounding_area = (max_x - min_x) * (max_y - min_y)
        actual_area = sum(r.area for r in all_rects)

        # If actual area is significantly less than bounding box, it's non-rectangular
        fill_ratio = actual_area / bounding_area if bounding_area > 0 else 1.0
        return fill_ratio < 0.85  # Less than 85% fill = interesting shape

    def _grow_creative_path(self, room_id: str, area_spec) -> bool:
        """Grow dead space creatively to find placement for a room."""
        ds_size = max(self.grid, 3.0)
        max_attempts = 15

        # Get all current room edges as potential growth points
        growth_points = []
        for placed_id, placed_room in self.placed.items():
            pr = placed_room.rect
            # Add midpoints of each edge
            growth_points.extend([
                (pr.x + pr.width/2, pr.y2, 'north'),  # Top edge
                (pr.x + pr.width/2, pr.y, 'south'),   # Bottom edge
                (pr.x2, pr.y + pr.height/2, 'east'),  # Right edge
                (pr.x, pr.y + pr.height/2, 'west'),   # Left edge
            ])

        import random
        random.shuffle(growth_points)  # Randomize for variety

        for attempt in range(max_attempts):
            if not growth_points:
                break

            # Pick a growth point
            gx, gy, direction = growth_points.pop(0)

            # Calculate dead space position
            if direction == 'north':
                ds_rect = Rect(gx - ds_size/2, gy, ds_size, ds_size)
            elif direction == 'south':
                ds_rect = Rect(gx - ds_size/2, gy - ds_size, ds_size, ds_size)
            elif direction == 'east':
                ds_rect = Rect(gx, gy - ds_size/2, ds_size, ds_size)
            else:
                ds_rect = Rect(gx - ds_size, gy - ds_size/2, ds_size, ds_size)

            # Snap to grid
            ds_rect = Rect(
                round(ds_rect.x / self.grid) * self.grid,
                round(ds_rect.y / self.grid) * self.grid,
                ds_size, ds_size
            )

            # Check if valid (allow extensions in creative mode)
            if self._is_dead_space_valid(ds_rect, inside_bounds_only=False):
                # Place dead space
                ds_id = f"dead_space_{self.dead_space_count}"
                self.dead_space_count += 1
                self.placed[ds_id] = PlacedRoom(ds_id, ds_rect)

                # Try to place target room
                if self._try_place_single_creative(room_id, area_spec):
                    return True

                # Add new growth points from this dead space
                growth_points.append((ds_rect.x + ds_size/2, ds_rect.y2, 'north'))
                growth_points.append((ds_rect.x + ds_size/2, ds_rect.y, 'south'))
                growth_points.append((ds_rect.x2, ds_rect.y + ds_size/2, 'east'))
                growth_points.append((ds_rect.x, ds_rect.y + ds_size/2, 'west'))

        return False

    def _add_creative_circulation(self):
        """Proactively add dead space to create interesting circulation patterns."""
        ds_size = max(self.grid, 3.0)

        # Only add creative circulation sometimes (for variety)
        import random
        if random.random() > 0.3:  # 30% chance to add creative circulation
            return

        # Find corners and junctions where dead space would be interesting
        circulation_rooms = [
            r for r in self.placed.keys()
            if r in ['hallway', 'entry'] or r.startswith('dead_space_')
        ]

        if not circulation_rooms:
            return

        # Pick a random circulation room and extend it
        circ_id = random.choice(circulation_rooms)
        circ_rect = self.placed[circ_id].rect

        # Try each direction
        directions = ['north', 'south', 'east', 'west']
        random.shuffle(directions)

        for direction in directions:
            if direction == 'north':
                ds_rect = Rect(circ_rect.x, circ_rect.y2, ds_size, ds_size)
            elif direction == 'south':
                ds_rect = Rect(circ_rect.x, circ_rect.y - ds_size, ds_size, ds_size)
            elif direction == 'east':
                ds_rect = Rect(circ_rect.x2, circ_rect.y, ds_size, ds_size)
            else:
                ds_rect = Rect(circ_rect.x - ds_size, circ_rect.y, ds_size, ds_size)

            if self._is_dead_space_valid(ds_rect, inside_bounds_only=False):
                ds_id = f"dead_space_{self.dead_space_count}"
                self.dead_space_count += 1
                self.placed[ds_id] = PlacedRoom(ds_id, ds_rect)
                break  # Only add one per room placement

    def _try_place_with_dead_space(self, room_id: str) -> bool:
        """
        Try to place a room by growing dead space (circulation) toward it.

        Dead space extends circulation (hallway) into new areas, enabling
        rooms that need hallway adjacency to be placed in otherwise
        unreachable positions. Works for:
        - Rooms needing exterior + hallway (bedrooms, garage)
        - Rooms needing only hallway (laundry, utility)
        - Any room that can't find valid position near existing circulation
        """
        area_spec = self.spec.room_areas.get(room_id)
        if not area_spec:
            return False

        must_touch = self.spec.constraints.must_touch.get(room_id, set())
        needs_exterior = room_id in self.spec.constraints.must_have_exterior

        # Dead space helps any room that needs circulation adjacency
        needs_circulation = any(r in must_touch for r in ['hallway', 'entry'])
        if not needs_circulation:
            return False  # Only helps rooms that need hallway/entry

        # Find the circulation rooms (hallway, entry, or existing dead space)
        circulation_rooms = [
            r for r in self.placed.keys()
            if r in ['hallway', 'entry'] or r.startswith('dead_space_')
        ]

        if not circulation_rooms:
            return False

        # Strategy depends on whether room needs exterior
        if needs_exterior:
            # First try growing toward exterior edges from circulation
            for edge in ['north', 'south', 'east', 'west']:
                if self._grow_to_edge(circulation_rooms, edge, room_id, area_spec):
                    return True

            # If that fails, try a more aggressive approach:
            # Grow dead space from the boundary of ANY room toward unused exterior
            if self._grow_to_unused_exterior(room_id, area_spec):
                return True
        else:
            # Room just needs circulation - grow in any direction with space
            if self._grow_circulation_outward(circulation_rooms, room_id, area_spec):
                return True

        return False

    def _grow_to_edge(self, circulation_rooms: List[str], edge: str,
                      target_room: str, area_spec) -> bool:
        """
        Grow dead space from circulation toward an edge, then try placing target room.

        Key improvement: Only grow toward edges with actual free space (inside bounds).
        """
        max_dead_spaces = 10  # Limit growth

        for _ in range(max_dead_spaces):
            # Find the circulation room closest to the target edge
            best_circ = None
            best_dist = float('inf')

            for circ_id in circulation_rooms:
                circ_rect = self.placed[circ_id].rect

                if edge == 'north':
                    dist = self.initial_bounds.height - circ_rect.y2
                elif edge == 'south':
                    dist = circ_rect.y
                elif edge == 'east':
                    dist = self.initial_bounds.width - circ_rect.x2
                else:  # west
                    dist = circ_rect.x

                # Only consider if there's space toward this edge (inside bounds)
                if dist > self.grid and dist < best_dist:
                    best_dist = dist
                    best_circ = circ_id

            if best_circ is None or best_dist < self.grid:
                # Already at edge or no space, try placing the room
                break

            # Try to add dead space adjacent to best_circ toward the edge
            circ_rect = self.placed[best_circ].rect
            ds_size = max(self.grid, 3.0)  # At least 3x3 (1m x 1m minimum hallway)

            if edge == 'north':
                ds_rect = Rect(circ_rect.x, circ_rect.y2, ds_size, ds_size)
            elif edge == 'south':
                ds_rect = Rect(circ_rect.x, circ_rect.y - ds_size, ds_size, ds_size)
            elif edge == 'east':
                ds_rect = Rect(circ_rect.x2, circ_rect.y, ds_size, ds_size)
            else:  # west
                ds_rect = Rect(circ_rect.x - ds_size, circ_rect.y, ds_size, ds_size)

            # Check if dead space position is valid AND inside original bounds
            if not self._is_dead_space_valid(ds_rect, inside_bounds_only=True):
                break  # Can't grow in this direction

            # Place the dead space
            ds_id = f"dead_space_{self.dead_space_count}"
            self.dead_space_count += 1
            self.placed[ds_id] = PlacedRoom(ds_id, ds_rect)
            circulation_rooms.append(ds_id)

        # Now try to place the target room (it should be able to touch circulation AND have exterior)
        candidates = self._generate_candidates(target_room, area_spec, relaxed=False)

        if candidates:
            scored = [(self._score_position(target_room, rect, False), rect) for rect in candidates]
            scored.sort(reverse=True, key=lambda x: x[0])

            for score, rect in scored[:50]:
                if score >= 0:
                    self.placed[target_room] = PlacedRoom(target_room, rect)
                    return True

        return False

    def _grow_circulation_outward(self, circulation_rooms: List[str],
                                   target_room: str, area_spec) -> bool:
        """
        Grow dead space outward from circulation to find placement for a room
        that needs hallway adjacency but not exterior access.

        Tries each direction from each circulation room to extend reach.
        """
        max_dead_spaces = 8  # Limit total growth
        directions = [
            ('north', 0, 1),
            ('south', 0, -1),
            ('east', 1, 0),
            ('west', -1, 0),
        ]

        spaces_added = 0

        for _ in range(max_dead_spaces):
            placed_any = False

            # Try growing from each circulation room in each direction
            for circ_id in list(circulation_rooms):
                if spaces_added >= max_dead_spaces:
                    break

                circ_rect = self.placed[circ_id].rect
                ds_size = max(self.grid, 3.0)  # 3x3 minimum (1m hallway)

                for dir_name, dx, dy in directions:
                    # Calculate dead space position
                    if dx > 0:  # east
                        ds_rect = Rect(circ_rect.x2, circ_rect.y, ds_size, ds_size)
                    elif dx < 0:  # west
                        ds_rect = Rect(circ_rect.x - ds_size, circ_rect.y, ds_size, ds_size)
                    elif dy > 0:  # north
                        ds_rect = Rect(circ_rect.x, circ_rect.y2, ds_size, ds_size)
                    else:  # south
                        ds_rect = Rect(circ_rect.x, circ_rect.y - ds_size, ds_size, ds_size)

                    # Stay inside original bounds for circulation growth
                    if self._is_dead_space_valid(ds_rect, inside_bounds_only=True):
                        # Place the dead space
                        ds_id = f"dead_space_{self.dead_space_count}"
                        self.dead_space_count += 1
                        self.placed[ds_id] = PlacedRoom(ds_id, ds_rect)
                        circulation_rooms.append(ds_id)
                        spaces_added += 1
                        placed_any = True

                        # Try to place target room now
                        candidates = self._generate_candidates(target_room, area_spec, relaxed=False)
                        if candidates:
                            scored = [(self._score_position(target_room, rect, False), rect) for rect in candidates]
                            scored.sort(reverse=True, key=lambda x: x[0])
                            for score, rect in scored[:30]:
                                if score >= 0:
                                    self.placed[target_room] = PlacedRoom(target_room, rect)
                                    return True

            if not placed_any:
                break  # No more space to grow

        return False

    def _grow_to_unused_exterior(self, target_room: str, area_spec) -> bool:
        """
        Grow dead space from ANY placed room's edge toward unused exterior.

        This handles cases where circulation is landlocked but there's unused
        exterior space that can be reached by extending from other rooms.
        """
        ds_size = max(self.grid, 3.0)
        max_dead_spaces = 12

        # Find which exterior edges have free space
        edges_with_space = []
        for edge in ['north', 'south', 'east', 'west']:
            if self._has_free_exterior_space(edge, area_spec.min_area):
                edges_with_space.append(edge)

        if not edges_with_space:
            return False

        # For each edge with space, try to build a path from existing rooms
        for target_edge in edges_with_space:
            # Find rooms closest to this edge
            rooms_near_edge = []
            for room_id, placed_room in self.placed.items():
                pr = placed_room.rect
                if target_edge == 'north':
                    dist = self.initial_bounds.height - pr.y2
                elif target_edge == 'south':
                    dist = pr.y
                elif target_edge == 'east':
                    dist = self.initial_bounds.width - pr.x2
                else:
                    dist = pr.x

                if dist > 0:  # Has space toward edge
                    rooms_near_edge.append((dist, room_id, pr))

            rooms_near_edge.sort(key=lambda x: x[0])  # Closest first

            # Try to grow dead space from these rooms toward the edge
            for dist, room_id, pr in rooms_near_edge[:3]:  # Top 3 closest
                circulation_path = [room_id]  # Track the path

                for _ in range(max_dead_spaces):
                    # Get the current frontier room
                    frontier_id = circulation_path[-1]
                    frontier_rect = self.placed[frontier_id].rect

                    # Create dead space toward target edge
                    if target_edge == 'north':
                        ds_rect = Rect(frontier_rect.x, frontier_rect.y2, ds_size, ds_size)
                    elif target_edge == 'south':
                        ds_rect = Rect(frontier_rect.x, frontier_rect.y - ds_size, ds_size, ds_size)
                    elif target_edge == 'east':
                        ds_rect = Rect(frontier_rect.x2, frontier_rect.y, ds_size, ds_size)
                    else:
                        ds_rect = Rect(frontier_rect.x - ds_size, frontier_rect.y, ds_size, ds_size)

                    if not self._is_dead_space_valid(ds_rect, inside_bounds_only=True):
                        break

                    # Place dead space
                    ds_id = f"dead_space_{self.dead_space_count}"
                    self.dead_space_count += 1
                    self.placed[ds_id] = PlacedRoom(ds_id, ds_rect)
                    circulation_path.append(ds_id)

                    # Check if we can place the target room now
                    candidates = self._generate_candidates(target_room, area_spec, relaxed=False)
                    if candidates:
                        scored = [(self._score_position(target_room, rect, False), rect) for rect in candidates]
                        scored.sort(reverse=True, key=lambda x: x[0])
                        for score, rect in scored[:30]:
                            if score >= 0:
                                self.placed[target_room] = PlacedRoom(target_room, rect)
                                return True

        return False

    def _has_free_exterior_space(self, edge: str, min_area: float) -> bool:
        """Check if an exterior edge has enough free space for a room."""
        min_dim = math.sqrt(min_area) * 0.7  # Rough minimum dimension

        if edge == 'north':
            y = self.initial_bounds.height - min_dim
            for x in range(0, int(self.initial_bounds.width - min_dim), int(self.grid)):
                test_rect = Rect(x, y, min_dim, min_dim)
                if not any(test_rect.overlaps(p.rect) for p in self.placed.values()):
                    return True
        elif edge == 'south':
            for x in range(0, int(self.initial_bounds.width - min_dim), int(self.grid)):
                test_rect = Rect(x, 0, min_dim, min_dim)
                if not any(test_rect.overlaps(p.rect) for p in self.placed.values()):
                    return True
        elif edge == 'east':
            x = self.initial_bounds.width - min_dim
            for y in range(0, int(self.initial_bounds.height - min_dim), int(self.grid)):
                test_rect = Rect(x, y, min_dim, min_dim)
                if not any(test_rect.overlaps(p.rect) for p in self.placed.values()):
                    return True
        else:  # west
            for y in range(0, int(self.initial_bounds.height - min_dim), int(self.grid)):
                test_rect = Rect(0, y, min_dim, min_dim)
                if not any(test_rect.overlaps(p.rect) for p in self.placed.values()):
                    return True

        return False

    def _retry_unplaced_after_dead_space(self, unplaced: List[str]) -> int:
        """
        After dead space grows, re-evaluate all unplaced rooms.
        Returns number of newly placed rooms.
        """
        placed_count = 0
        for room_id in list(unplaced):
            if room_id in self.placed:
                continue

            area_spec = self.spec.room_areas.get(room_id)
            if not area_spec:
                continue

            # Try placing with current constraints (now have more circulation)
            candidates = self._generate_candidates(room_id, area_spec, relaxed=False)
            if candidates:
                scored = [(self._score_position(room_id, rect, False), rect) for rect in candidates]
                scored.sort(reverse=True, key=lambda x: x[0])
                for score, rect in scored[:30]:
                    if score >= 0:
                        self.placed[room_id] = PlacedRoom(room_id, rect)
                        placed_count += 1
                        break

        return placed_count

    def _is_dead_space_valid(self, rect: Rect, inside_bounds_only: bool = False) -> bool:
        """Check if a dead space position is valid (no overlap, within bounds)

        Args:
            rect: The proposed dead space rectangle
            inside_bounds_only: If True, only allow positions inside original bounds
                               (no extensions). Used when growing toward edges.
        """
        if inside_bounds_only:
            # Strict: must be within original building bounds
            if rect.x < 0 or rect.y < 0:
                return False
            if rect.x2 > self.initial_bounds.width:
                return False
            if rect.y2 > self.initial_bounds.height:
                return False
        elif self.allow_extensions:
            # Allow extensions outside original bounds
            ext = self.initial_bounds.width * self.max_extension
            if rect.x < -ext or rect.y < -ext:
                return False
            if rect.x2 > self.initial_bounds.width + ext:
                return False
            if rect.y2 > self.initial_bounds.height + ext:
                return False
        else:
            if rect.x < 0 or rect.y < 0:
                return False
            if rect.x2 > self.initial_bounds.width:
                return False
            if rect.y2 > self.initial_bounds.height:
                return False

        # Must not overlap with placed rooms
        for placed in self.placed.values():
            if rect.overlaps(placed.rect):
                return False

        return True

    def _interleave_attached_rooms(self, order: List[str]) -> List[str]:
        """
        Reorder to place closets immediately after their parent bedroom.

        Important: Only interleave closets, NOT bathrooms. This allows:
        - All bedrooms to be placed first (they need exterior walls)
        - Closets placed immediately after their bedroom
        - Bathrooms placed later (they don't need exterior walls)
        """
        # Only closet pairs - NOT bathrooms (they can go later)
        closet_pairs = {
            "primary_bedroom": ["primary_closet"],
            "bedroom_2": ["closet_2"],
            "bedroom_3": ["closet_3"],
            "bedroom_4": ["closet_4"],
        }

        # Build new order with closets following their parent bedrooms
        new_order = []
        added = set()

        for room_id in order:
            if room_id in added:
                continue

            new_order.append(room_id)
            added.add(room_id)

            # Add closet immediately after bedroom
            if room_id in closet_pairs:
                for closet in closet_pairs[room_id]:
                    if closet in self.spec.room_areas and closet not in added:
                        new_order.append(closet)
                        added.add(closet)

        # Add any remaining rooms not yet added
        for room_id in order:
            if room_id not in added:
                new_order.append(room_id)
                added.add(room_id)

        return new_order

    def _search(self, order: List[str], index: int, max_nodes: int,
                relaxed: bool = False, allow_skip: bool = True) -> bool:
        """
        Recursive backtracking search with improved branching.

        Args:
            order: Room placement order
            index: Current room index
            max_nodes: Maximum search nodes
            relaxed: Whether constraints are relaxed
            allow_skip: Whether skipping rooms is allowed (False = force backtrack)
        """
        self.nodes_explored += 1

        # Track best partial solution
        if len(self.placed) > len(self.best_partial):
            self.best_partial = dict(self.placed)

        if self.nodes_explored >= max_nodes:
            return False

        # All rooms placed
        if index >= len(order):
            return True

        room_id = order[index]
        area_spec = self.spec.room_areas[room_id]

        # Calculate branch limit based on constraints
        must_touch = self.spec.constraints.must_touch.get(room_id, set())
        needs_exterior = room_id in self.spec.constraints.must_have_exterior
        is_constrained = bool(must_touch) or needs_exterior

        # More branches for constrained rooms
        branch_limit = 150 if is_constrained else 80

        # Check if this is an "attached" room (must touch a specific parent)
        is_attached = self._is_attached_room(room_id)

        # Generate candidate positions
        candidates = self._generate_candidates(room_id, area_spec, relaxed=relaxed)

        if not candidates and not relaxed:
            # Try with relaxed constraints for this room
            self.relaxed_constraints.add(room_id)
            if needs_exterior:
                self.exterior_relaxed.add(room_id)
            candidates = self._generate_candidates(room_id, area_spec, relaxed=True)

        if not candidates:
            if is_attached or not allow_skip:
                # Force backtracking to try different earlier positions
                return False
            else:
                # Skip this room (only in later passes)
                return self._search(order, index + 1, max_nodes, relaxed, allow_skip)

        # Score and sort candidates
        scored = [(self._score_position(room_id, rect, relaxed), rect) for rect in candidates]
        scored.sort(reverse=True, key=lambda x: x[0])

        # Try each candidate up to branch limit
        for score, rect in scored[:branch_limit]:
            if score < 0:
                continue  # Invalid position

            # Place room
            self.placed[room_id] = PlacedRoom(room_id, rect)

            # Recurse
            if self._search(order, index + 1, max_nodes, relaxed, allow_skip):
                return True

            # Backtrack
            del self.placed[room_id]

        # Couldn't place with any candidate
        if is_attached or not allow_skip:
            # Force backtrack
            return False
        else:
            # Skip this room (only in later passes)
            return self._search(order, index + 1, max_nodes, relaxed, allow_skip)

    def _is_attached_room(self, room_id: str) -> bool:
        """Check if a room is attached (must be adjacent to specific parent)"""
        attached_to_parent = {
            "primary_bath": "primary_bedroom",
            "primary_closet": "primary_bedroom",
            "closet_2": "bedroom_2",
            "closet_3": "bedroom_3",
            "closet_4": "bedroom_4",
        }
        parent = attached_to_parent.get(room_id)
        return parent is not None and parent in self.placed

    def _generate_candidates(self, room_id: str, area_spec: RoomAreaSpec,
                             relaxed: bool = False) -> List[Rect]:
        """
        Generate candidate rectangles for a room.

        Args:
            room_id: Room to place
            area_spec: Area requirements
            relaxed: If True, relax must-touch and exterior constraints
        """
        candidates = []
        min_area = area_spec.min_area

        # Try multiple area sizes in relaxed mode
        area_multipliers = [1.1, 1.0, 0.9] if relaxed else [1.1]

        # More aspect ratios for better fitting
        aspect_ratios = [0.8, 0.7, 0.6, 1.0, 0.5] if relaxed else [0.8, 0.6, 1.0]

        for area_mult in area_multipliers:
            area = min_area * area_mult

            for aspect in aspect_ratios:
                if aspect < area_spec.aspect_min:
                    continue

                # Calculate dimensions
                height = math.sqrt(area / aspect)
                width = area / height

                # Snap to grid
                width = round(width / self.grid) * self.grid
                height = round(height / self.grid) * self.grid

                if width < 6 or height < 6:
                    continue

                # Get strategic positions
                positions = self._get_strategic_positions(room_id, width, height, relaxed)

                for x, y in positions:
                    rect = Rect(x, y, width, height)
                    if self._is_valid_position(room_id, rect, relaxed):
                        candidates.append(rect)

                    # Also try rotated
                    if abs(width - height) > 1:
                        rect_rot = Rect(x, y, height, width)
                        if self._is_valid_position(room_id, rect_rot, relaxed):
                            candidates.append(rect_rot)

        return candidates

    def _get_strategic_positions(self, room_id: str, width: float, height: float,
                                   relaxed: bool = False) -> List[Tuple[float, float]]:
        """
        Get strategic positions to try (near placed rooms or on edges).

        Improvements:
        1. Always generate positions near ALL placed rooms
        2. Prioritize must-touch rooms in scoring, not filtering
        3. Add boundary positions for exterior-required rooms
        4. More comprehensive edge scanning
        """
        positions = []
        grid = int(self.grid)

        # Check if this room needs/prefers exterior
        needs_exterior = room_id in self.spec.constraints.must_have_exterior
        prefers_exterior = room_id in self.spec.constraints.prefer_exterior

        if not self.placed:
            # First room: try entry edge positions
            self._add_entry_edge_positions(positions, width, height)
            return positions

        # IMPROVEMENT: Generate positions near ALL placed rooms
        # Score by must-touch later, don't filter here
        must_touch = self.spec.constraints.must_touch.get(room_id, set())
        placed_must_touch = [r for r in must_touch if r in self.placed]

        # Generate positions adjacent to all placed rooms
        for placed_id, placed_room in self.placed.items():
            pr = placed_room.rect
            self._add_adjacent_positions(positions, pr, width, height)

        # IMPROVEMENT: Add boundary positions for rooms needing exterior
        if needs_exterior or prefers_exterior or relaxed:
            self._add_boundary_positions(positions, width, height)

        # IMPROVEMENT: If we have must-touch constraints and none satisfied,
        # also add diagonal and nearby positions (not just adjacent)
        if must_touch and not placed_must_touch:
            for placed_id, placed_room in self.placed.items():
                pr = placed_room.rect
                self._add_nearby_positions(positions, pr, width, height)

        # Remove duplicates
        return list(set(positions))

    def _add_entry_edge_positions(self, positions: List, width: float, height: float):
        """Add positions along the entry edge for the first room"""
        grid = int(self.grid)

        if self.spec.entry_edge == "south":
            for x in range(0, int(self.bounds.width - width) + 1, grid):
                positions.append((float(x), 0.0))
        elif self.spec.entry_edge == "north":
            for x in range(0, int(self.bounds.width - width) + 1, grid):
                positions.append((float(x), self.bounds.height - height))
        elif self.spec.entry_edge == "west":
            for y in range(0, int(self.bounds.height - height) + 1, grid):
                positions.append((0.0, float(y)))
        else:  # east
            for y in range(0, int(self.bounds.height - height) + 1, grid):
                positions.append((self.bounds.width - width, float(y)))

    def _add_adjacent_positions(self, positions: List, placed_rect: Rect,
                                width: float, height: float):
        """Add positions adjacent to a placed room"""
        grid = int(self.grid)
        pr = placed_rect

        # Right of placed room
        x = pr.x2
        if x + width <= self.bounds.width:
            y_start = max(0, int(pr.y - height + grid))
            y_end = min(int(self.bounds.height - height), int(pr.y2 - grid)) + 1
            for y in range(y_start, y_end, grid):
                positions.append((x, float(y)))

        # Left of placed room
        x = pr.x - width
        if x >= 0:
            y_start = max(0, int(pr.y - height + grid))
            y_end = min(int(self.bounds.height - height), int(pr.y2 - grid)) + 1
            for y in range(y_start, y_end, grid):
                positions.append((x, float(y)))

        # Above placed room
        y = pr.y2
        if y + height <= self.bounds.height:
            x_start = max(0, int(pr.x - width + grid))
            x_end = min(int(self.bounds.width - width), int(pr.x2 - grid)) + 1
            for x in range(x_start, x_end, grid):
                positions.append((float(x), y))

        # Below placed room
        y = pr.y - height
        if y >= 0:
            x_start = max(0, int(pr.x - width + grid))
            x_end = min(int(self.bounds.width - width), int(pr.x2 - grid)) + 1
            for x in range(x_start, x_end, grid):
                positions.append((float(x), y))

    def _add_boundary_positions(self, positions: List, width: float, height: float):
        """Add positions along all building boundaries (including extensions)"""
        grid = int(self.grid)
        bounds = self._get_current_bounds()

        # Calculate extension limits
        if self.allow_extensions:
            ext_x = self.initial_bounds.width * self.max_extension
            ext_y = self.initial_bounds.height * self.max_extension
            min_x = -ext_x
            min_y = -ext_y
            max_x = self.initial_bounds.width + ext_x
            max_y = self.initial_bounds.height + ext_y
        else:
            min_x, min_y = 0, 0
            max_x = bounds.width
            max_y = bounds.height

        # South edge (y = min_y for extensions, y = 0 for normal)
        for x in range(int(min_x), int(max_x - width) + 1, grid):
            positions.append((float(x), min_y))
            if min_y < 0:
                positions.append((float(x), 0.0))  # Also add at y=0

        # North edge
        for x in range(int(min_x), int(max_x - width) + 1, grid):
            positions.append((float(x), max_y - height))
            if max_y > bounds.height:
                positions.append((float(x), bounds.height - height))

        # West edge
        for y in range(int(min_y), int(max_y - height) + 1, grid):
            positions.append((min_x, float(y)))
            if min_x < 0:
                positions.append((0.0, float(y)))

        # East edge
        for y in range(int(min_y), int(max_y - height) + 1, grid):
            positions.append((max_x - width, float(y)))
            if max_x > bounds.width:
                positions.append((bounds.width - width, float(y)))

    def _add_nearby_positions(self, positions: List, placed_rect: Rect,
                              width: float, height: float):
        """Add positions near (but not necessarily touching) a placed room"""
        grid = int(self.grid)
        pr = placed_rect
        gap = grid * 2  # One grid cell gap

        # Positions with a gap (for rooms that might connect through hallway)
        for offset in [gap, gap * 2]:
            # Right with gap
            x = pr.x2 + offset
            if x + width <= self.bounds.width:
                for y in range(0, int(self.bounds.height - height) + 1, grid * 2):
                    positions.append((x, float(y)))

            # Left with gap
            x = pr.x - width - offset
            if x >= 0:
                for y in range(0, int(self.bounds.height - height) + 1, grid * 2):
                    positions.append((x, float(y)))

            # Above with gap
            y = pr.y2 + offset
            if y + height <= self.bounds.height:
                for x in range(0, int(self.bounds.width - width) + 1, grid * 2):
                    positions.append((float(x), y))

            # Below with gap
            y = pr.y - height - offset
            if y >= 0:
                for x in range(0, int(self.bounds.width - width) + 1, grid * 2):
                    positions.append((float(x), y))

    def _is_valid_position(self, room_id: str, rect: Rect, relaxed: bool = False) -> bool:
        """
        Check if a position is valid with tiered constraint checking.

        Constraint Tiers:
        - Tier 1 (HARD): Boundary, overlap - never relaxed
        - Tier 2 (SOFT): Must-touch - relaxed to "nearby" in relaxed mode
        - Tier 3 (PREFERENCE): Exterior - can be fully relaxed

        Extensions: If allow_extensions is True, rooms can extend beyond the
        initial bounds to create L-shaped or complex footprints.
        """
        # TIER 1: HARD CONSTRAINTS (never relax)

        # Calculate extended bounds for extension mode
        if self.allow_extensions:
            ext_x = self.initial_bounds.width * self.max_extension
            ext_y = self.initial_bounds.height * self.max_extension
            extended_bounds = Rect(
                -ext_x, -ext_y,
                self.initial_bounds.width + 2 * ext_x,
                self.initial_bounds.height + 2 * ext_y
            )
        else:
            extended_bounds = self.initial_bounds

        # Must fit in bounds (or extended bounds)
        if rect.x < extended_bounds.x - 0.01 or rect.y < extended_bounds.y - 0.01:
            return False
        if rect.x2 > extended_bounds.x2 + 0.01:
            return False
        if rect.y2 > extended_bounds.y2 + 0.01:
            return False

        # If extending beyond initial bounds, must be adjacent to placed room
        is_extension = (rect.x < -0.01 or rect.y < -0.01 or
                       rect.x2 > self.initial_bounds.width + 0.01 or
                       rect.y2 > self.initial_bounds.height + 0.01)

        if is_extension and self.placed:
            # Must touch at least one placed room to maintain connectivity
            touches_any_placed = any(
                rect.touches(p.rect) for p in self.placed.values()
            )
            if not touches_any_placed:
                return False

        # Must not overlap with placed rooms
        for placed in self.placed.values():
            if rect.overlaps(placed.rect):
                return False

        # TIER 1b: Must-not-touch constraints (always strict)
        must_not = self.spec.constraints.must_not_touch.get(room_id, set())
        for other_id in must_not:
            if other_id in self.placed:
                if rect.touches(self.placed[other_id].rect):
                    return False

        # TIER 2: SOFT CONSTRAINTS (relax in relaxed mode)

        must_touch = self.spec.constraints.must_touch.get(room_id, set())
        placed_must_touch = [other_id for other_id in must_touch if other_id in self.placed]

        # Dead space counts as circulation - if room needs hallway, dead_space works too
        dead_space_rooms = [r for r in self.placed.keys() if r.startswith('dead_space_')]
        if 'hallway' in must_touch and dead_space_rooms:
            placed_must_touch.extend(dead_space_rooms)

        if placed_must_touch:
            if relaxed or room_id in self.relaxed_constraints:
                # Relaxed: just need to be "nearby" (within 1 grid cell gap)
                nearby_threshold = self.grid * 2  # Stricter: 1 grid cell gap
                is_nearby = any(
                    self._is_nearby(rect, self.placed[other_id].rect, nearby_threshold)
                    for other_id in placed_must_touch
                )
                if not is_nearby:
                    return False
            else:
                # Strict: must touch at least ONE of the placed must-touch rooms
                touches_any = any(
                    rect.touches(self.placed[other_id].rect)
                    for other_id in placed_must_touch
                )
                if not touches_any:
                    return False

        # TIER 3: PREFERENCE CONSTRAINTS (fully relaxable)

        # For exterior requirement, check against actual bounds (which may extend)
        current_bounds = self._get_current_bounds()

        if room_id in self.spec.constraints.must_have_exterior:
            if relaxed or room_id in self.exterior_relaxed:
                # Relaxed: exterior not required, just preferred
                pass
            else:
                # Strict: must touch building boundary (or be an extension)
                if not rect.touches_any_boundary(current_bounds) and not is_extension:
                    return False

        return True

    def _get_current_bounds(self) -> Rect:
        """Get the current building bounds (may be larger than initial if extended)"""
        if not self.placed:
            return self.initial_bounds

        min_x = min(r.rect.x for r in self.placed.values())
        min_y = min(r.rect.y for r in self.placed.values())
        max_x = max(r.rect.x2 for r in self.placed.values())
        max_y = max(r.rect.y2 for r in self.placed.values())

        # Expand to include initial bounds
        min_x = min(min_x, 0)
        min_y = min(min_y, 0)
        max_x = max(max_x, self.initial_bounds.width)
        max_y = max(max_y, self.initial_bounds.height)

        return Rect(min_x, min_y, max_x - min_x, max_y - min_y)

    def _is_nearby(self, rect1: Rect, rect2: Rect, threshold: float) -> bool:
        """Check if two rectangles are within threshold distance"""
        # Calculate minimum distance between rectangles
        dx = max(0, max(rect1.x - rect2.x2, rect2.x - rect1.x2))
        dy = max(0, max(rect1.y - rect2.y2, rect2.y - rect1.y2))
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= threshold

    def _score_position(self, room_id: str, rect: Rect, relaxed: bool = False) -> float:
        """
        Score a candidate position (higher = better).

        Improved scoring:
        1. Bonus for touching must-touch rooms
        2. Bonus for exterior when required/preferred
        3. Better aspect ratio scoring
        4. Penalty for constraint violations in relaxed mode
        5. Penalty for extensions beyond initial bounds
        """
        if not self._is_valid_position(room_id, rect, relaxed):
            return -1

        score = 100.0

        # EXTENSION PENALTY: Prefer staying within initial bounds
        is_extension = (rect.x < -0.01 or rect.y < -0.01 or
                       rect.x2 > self.initial_bounds.width + 0.01 or
                       rect.y2 > self.initial_bounds.height + 0.01)
        if is_extension:
            # Calculate how much extends beyond
            ext_area = 0
            if rect.x < 0:
                ext_area += abs(rect.x) * rect.height
            if rect.y < 0:
                ext_area += abs(rect.y) * rect.width
            if rect.x2 > self.initial_bounds.width:
                ext_area += (rect.x2 - self.initial_bounds.width) * rect.height
            if rect.y2 > self.initial_bounds.height:
                ext_area += (rect.y2 - self.initial_bounds.height) * rect.width
            # Penalize proportional to extension area
            score -= ext_area * 0.5

        # MUST-TOUCH BONUS: Very strong preference for touching required rooms
        must_touch = self.spec.constraints.must_touch.get(room_id, set())
        for other_id in must_touch:
            if other_id in self.placed:
                if rect.touches(self.placed[other_id].rect):
                    score += 80  # Very strong bonus for satisfying must-touch
                elif self._is_nearby(rect, self.placed[other_id].rect, self.grid * 2):
                    score += 20  # Smaller bonus for being nearby
                else:
                    score -= 30  # Penalty for being far from must-touch room

        # CONNECTIVITY: Prefer touching any placed rooms
        touches_count = sum(1 for p in self.placed.values() if rect.touches(p.rect))
        score += touches_count * 15

        # ASPECT RATIO: Prefer rooms that are not too narrow
        score += rect.aspect * 10

        # ENTRY POSITIONING
        current_bounds = self._get_current_bounds()
        if room_id == "entry":
            if rect.is_on_boundary(self.initial_bounds, self.spec.entry_edge):
                score += 50
            # Near entry position
            if self.spec.entry_edge == "south":
                dist = abs(rect.center.x - self.initial_bounds.width * self.spec.entry_position)
                score -= dist * 2
            elif self.spec.entry_edge == "north":
                dist = abs(rect.center.x - self.initial_bounds.width * self.spec.entry_position)
                score -= dist * 2
            elif self.spec.entry_edge == "west":
                dist = abs(rect.center.y - self.initial_bounds.height * self.spec.entry_position)
                score -= dist * 2
            else:  # east
                dist = abs(rect.center.y - self.initial_bounds.height * self.spec.entry_position)
                score -= dist * 2

        # EXTERIOR PREFERENCE
        needs_exterior = room_id in self.spec.constraints.must_have_exterior
        prefers_exterior = room_id in self.spec.constraints.prefer_exterior

        if needs_exterior or prefers_exterior:
            # Extensions count as exterior (they create new exterior walls)
            if rect.touches_any_boundary(current_bounds) or is_extension:
                score += 30 if needs_exterior else 15
            elif needs_exterior and relaxed:
                # In relaxed mode, penalize but don't reject
                score -= 20

        # CORNER PLACEMENT: Good for small rooms
        area_spec = self.spec.room_areas[room_id]
        if area_spec.min_area < 50:  # Small room
            corner_dist = min(
                max(0, rect.x), max(0, self.initial_bounds.width - rect.x2),
                max(0, rect.y), max(0, self.initial_bounds.height - rect.y2)
            )
            if corner_dist < 1:
                score += 10

        # SPACE EFFICIENCY: Prefer positions that leave usable space
        # Penalize creating narrow strips (within initial bounds)
        gaps = [
            max(0, rect.x),  # Left gap
            max(0, self.initial_bounds.width - rect.x2),  # Right gap
            max(0, rect.y),  # Bottom gap
            max(0, self.initial_bounds.height - rect.y2)  # Top gap
        ]
        for gap in gaps:
            if 0 < gap < 6:  # Too narrow to be useful
                score -= 5

        return score

    def _generate_wall_coordinates(self) -> List[WallCoordinate]:
        """Generate wall coordinates from placed rooms"""

        walls = []
        processed_pairs = set()

        # Interior walls: between adjacent placed rooms
        for room_id, room in self.placed.items():
            for other_id, other in self.placed.items():
                if room_id >= other_id:  # Avoid duplicates
                    continue

                pair = (room_id, other_id)
                if pair in processed_pairs:
                    continue

                if room.rect.touches(other.rect):
                    processed_pairs.add(pair)

                    # Get shared edge
                    edge = room.rect.shared_edge(other.rect)
                    if edge:
                        start, end = edge

                        # Find wall segment from wall graph
                        wall_seg = self.spec.wall_graph.get_wall(room_id, other_id)
                        if wall_seg and not wall_seg.is_open:
                            # Create wall coordinate
                            wall_coord = WallCoordinate(
                                wall_id=wall_seg.id,
                                start=start,
                                end=end,
                                wall_type=wall_seg.wall_type,
                                room1=room_id,
                                room2=other_id
                            )

                            # Add openings
                            for opening in wall_seg.openings:
                                opening_coords = self._calculate_opening(start, end, opening)
                                if opening_coords:
                                    wall_coord.openings.append(opening_coords)

                            walls.append(wall_coord)

        # Exterior walls: around the building perimeter
        walls.extend(self._generate_exterior_walls())

        return walls

    def _calculate_opening(self, wall_start: Point, wall_end: Point,
                          opening: WallOpening) -> Optional[Tuple[Point, Point, OpeningType]]:
        """Calculate opening coordinates along a wall"""

        length = math.sqrt((wall_end.x - wall_start.x)**2 + (wall_end.y - wall_start.y)**2)
        if length < opening.width:
            return None

        # Direction vector
        dx = (wall_end.x - wall_start.x) / length
        dy = (wall_end.y - wall_start.y) / length

        # Opening center
        center_dist = length * opening.position
        center_x = wall_start.x + dx * center_dist
        center_y = wall_start.y + dy * center_dist

        # Opening start/end
        half_width = opening.width / 2
        open_start = Point(center_x - dx * half_width, center_y - dy * half_width)
        open_end = Point(center_x + dx * half_width, center_y + dy * half_width)

        return (open_start, open_end, opening.opening_type)

    def _generate_exterior_walls(self) -> List[WallCoordinate]:
        """Generate exterior wall coordinates"""

        walls = []
        wall_counter = 1000  # Start high to avoid ID conflicts

        # Collect all room edges that touch the boundary
        # For simplicity, create 4 perimeter walls

        edges = {
            "south": (Point(0, 0), Point(self.bounds.width, 0)),
            "east": (Point(self.bounds.width, 0), Point(self.bounds.width, self.bounds.height)),
            "north": (Point(self.bounds.width, self.bounds.height), Point(0, self.bounds.height)),
            "west": (Point(0, self.bounds.height), Point(0, 0))
        }

        for edge_name, (start, end) in edges.items():
            # Find rooms on this edge
            rooms_on_edge = [
                room_id for room_id, room in self.placed.items()
                if room.rect.is_on_boundary(self.bounds, edge_name)
            ]

            wall_coord = WallCoordinate(
                wall_id=f"ext_{edge_name}",
                start=start,
                end=end,
                wall_type=WallType.EXTERIOR,
                room1="exterior",
                room2=rooms_on_edge[0] if rooms_on_edge else "unassigned"
            )

            # Add front door to entry edge
            if edge_name == self.spec.entry_edge and "entry" in rooms_on_edge:
                # Find entry room and add door
                entry_room = self.placed.get("entry")
                if entry_room:
                    door_x = entry_room.rect.center.x
                    door_y = entry_room.rect.y if edge_name == "south" else entry_room.rect.y2
                    half_door = 1.5

                    if edge_name in ["south", "north"]:
                        door_start = Point(door_x - half_door, door_y)
                        door_end = Point(door_x + half_door, door_y)
                    else:
                        door_start = Point(door_x, door_y - half_door)
                        door_end = Point(door_x, door_y + half_door)

                    wall_coord.openings.append((door_start, door_end, OpeningType.DOOR))

            walls.append(wall_coord)

        return walls

    def _calculate_score(self) -> float:
        """Calculate layout quality score"""

        if not self.placed:
            return 0

        score = 0

        # Completeness
        completeness = len(self.placed) / len(self.spec.room_areas)
        score += completeness * 100

        # Area efficiency
        for room_id, room in self.placed.items():
            area_spec = self.spec.room_areas.get(room_id)
            if area_spec:
                ratio = room.area / area_spec.min_area
                if 1.0 <= ratio <= 1.3:
                    score += 5
                elif ratio < 1.0:
                    score -= 10

        # Adjacency satisfaction
        for room_id, must_touch in self.spec.constraints.must_touch.items():
            if room_id not in self.placed:
                continue
            room = self.placed[room_id]
            for other_id in must_touch:
                if other_id in self.placed:
                    if room.rect.touches(self.placed[other_id].rect):
                        score += 3

        return score


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def solve_layout(spatial_graph: SpatialGraph,
                width: float, depth: float,
                grid_size: float = 2.0,
                max_nodes: int = 50000,
                creative_mode: bool = False) -> PlacedLayout:
    """
    Convenience function to solve a layout from a spatial graph.

    Args:
        spatial_graph: Room relationships
        width: Building width
        depth: Building depth
        grid_size: Grid snap size
        max_nodes: Max search nodes
        creative_mode: If True, use organic growth with liberal dead space
                      for interesting non-rectangular building shapes

    Returns:
        PlacedLayout with room and wall coordinates
    """
    spec = LayoutSpec.from_spatial_graph(spatial_graph, width, depth)
    solver = CoordinateSolver(spec, grid_size, creative_mode=creative_mode)
    return solver.solve(max_nodes)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("COORDINATE SOLVER TEST - SIMPLE")
    print("=" * 60)

    # Very simple test: just 4 rooms
    spatial = SpatialGraph()
    spatial.add_room("entry", "entry", min_area=50)
    spatial.add_room("living", "living", min_area=200)
    spatial.add_room("kitchen", "kitchen", min_area=120)
    spatial.add_room("bedroom", "bedroom", min_area=150)

    # Simple relationships
    spatial.connect("entry", "living")
    spatial.adjacent("living", "kitchen")
    spatial.connect("living", "bedroom")

    # Solve
    layout = solve_layout(spatial, width=40, depth=30, grid_size=4.0, max_nodes=10000)

    # Summary
    print("\n" + layout.summary())

    # Wall coordinates
    print("\nWall Coordinates:")
    for wall in layout.walls:
        print(f"  {wall.wall_id}: ({wall.start.x:.0f},{wall.start.y:.0f}) -> ({wall.end.x:.0f},{wall.end.y:.0f}) [{wall.wall_type.value}]")
        for start, end, otype in wall.openings:
            print(f"    Opening: ({start.x:.1f},{start.y:.1f}) -> ({end.x:.1f},{end.y:.1f}) [{otype.value}]")
