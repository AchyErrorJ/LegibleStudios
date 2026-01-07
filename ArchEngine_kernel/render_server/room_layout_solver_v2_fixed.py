"""
Room Layout Solver v2 (Patched)
===============================
Zone-based floor plan generator with circulation spine.

PATCHES APPLIED:
- Capped candidate positions to 500 per room
- Added progress reporting every 1000 nodes

The algorithm:
1. Split footprint into ZONES (Public, Circulation, Private)
2. Place rooms within their designated zones
3. Circulation (hallway) acts as spine connecting zones
4. Rooms connect to circulation OR to adjacent rooms in same zone

Layout Pattern:
┌────────────────────────────────────────────┐
│              PRIVATE ZONE                   │
│   (Master, Bedrooms, Bathrooms)            │
├──────────── CIRCULATION ───────────────────┤
│   (Hallway - connects all private rooms)   │
├────────────────────────────────────────────┤
│              PUBLIC ZONE                    │
│   (Entry, Living, Dining, Kitchen)         │
└────────────────────────────────────────────┘
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import math
import copy


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class Zone(Enum):
    """Room zones for high-level organization"""
    PUBLIC = "public"          # Entry, Living, Dining, Kitchen
    CIRCULATION = "circulation" # Hallway connecting zones
    PRIVATE = "private"        # Bedrooms, Bathrooms
    SERVICE = "service"        # Utility, Garage, Storage


# =============================================================================
# PERFORMANCE CONSTANTS
# =============================================================================

MAX_POSITIONS_PER_ROOM = 500  # Cap candidate positions to prevent explosion
PROGRESS_REPORT_INTERVAL = 1000  # Report progress every N nodes


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RoomDefinition:
    """Definition of a room's requirements and constraints"""
    
    name: str
    room_type: str
    min_area: float  # Square feet
    max_area: float = None  # Optional max
    zone: str = "public"  # public, private, circulation, service
    
    # Adjacency constraints
    must_connect: List[str] = field(default_factory=list)  # Required neighbors (with door)
    can_connect: List[str] = field(default_factory=list)   # Allowed neighbors (with door)
    cannot_connect: List[str] = field(default_factory=list)  # Forbidden neighbors (no touching at all)
    share_wall_only: List[str] = field(default_factory=list)  # Can share wall but NO DOOR (plumbing adjacency)
    
    # Placement preferences
    prefer_exterior: bool = False  # Wants windows
    require_exterior: bool = False  # MUST have exterior wall (code requirement)
    prefer_corner: bool = False    # Wants corner position
    near_entry: bool = False       # Should be close to entry
    connects_to_circulation: bool = False  # Must touch hallway
    
    # Wet wall / plumbing constraints
    is_wet_room: bool = False  # Has plumbing (bathroom, kitchen, utility)
    needs_wet_wall: bool = False  # Must share wall with another wet room
    
    # Privacy level (1=public, 2=semi-private, 3=private)
    privacy_level: int = 1
    
    # Can this room be a pass-through to other rooms?
    allow_pass_through: bool = False  # Only closets/ensuites should be True
    
    # Is this an ensuite (private to one bedroom)?
    is_ensuite: bool = False
    
    # Priority (lower = place first)
    priority: int = 50
    
    # Aspect ratio constraints
    min_aspect: float = 0.5  # Minimum width/height ratio
    max_aspect: float = 2.0  # Maximum width/height ratio
    
    def __post_init__(self):
        if self.max_area is None:
            self.max_area = self.min_area * 1.5


@dataclass
class PlacedRoom:
    """A room that has been placed in the layout"""
    
    definition: RoomDefinition
    x: float  # Bottom-left corner X
    y: float  # Bottom-left corner Y
    width: float
    height: float
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height
    
    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x2, self.y2)
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width/2, self.y + self.height/2)
    
    @property
    def aspect_ratio(self) -> float:
        """1.0 = square, lower = more elongated"""
        return min(self.width, self.height) / max(self.width, self.height)
    
    def touches(self, other: 'PlacedRoom', tolerance: float = 0.1) -> bool:
        """Check if this room shares an edge with another"""
        # Check if they share a vertical edge (left-right neighbors)
        vertical_touch = (
            (abs(self.x2 - other.x) < tolerance or abs(self.x - other.x2) < tolerance) and
            self.y < other.y2 and self.y2 > other.y
        )
        # Check if they share a horizontal edge (top-bottom neighbors)
        horizontal_touch = (
            (abs(self.y2 - other.y) < tolerance or abs(self.y - other.y2) < tolerance) and
            self.x < other.x2 and self.x2 > other.x
        )
        return vertical_touch or horizontal_touch
    
    def overlaps(self, other: 'PlacedRoom', tolerance: float = 0.1) -> bool:
        """Check if this room overlaps with another"""
        return not (
            self.x2 <= other.x + tolerance or
            self.x >= other.x2 - tolerance or
            self.y2 <= other.y + tolerance or
            self.y >= other.y2 - tolerance
        )
    
    def shared_edge(self, other: 'PlacedRoom', tolerance: float = 0.1) -> Optional[Dict]:
        """Get the shared edge between two rooms if they touch"""
        if not self.touches(other, tolerance):
            return None
        
        # Check vertical edge (rooms are left-right)
        if abs(self.x2 - other.x) < tolerance:
            # Self is left of other
            y_start = max(self.y, other.y)
            y_end = min(self.y2, other.y2)
            if y_end > y_start:
                return {
                    'start': [self.x2, y_start, 0],
                    'end': [self.x2, y_end, 0],
                    'direction': 'vertical',
                    'length': y_end - y_start
                }
        
        if abs(self.x - other.x2) < tolerance:
            # Self is right of other
            y_start = max(self.y, other.y)
            y_end = min(self.y2, other.y2)
            if y_end > y_start:
                return {
                    'start': [self.x, y_start, 0],
                    'end': [self.x, y_end, 0],
                    'direction': 'vertical',
                    'length': y_end - y_start
                }
        
        # Check horizontal edge (rooms are top-bottom)
        if abs(self.y2 - other.y) < tolerance:
            # Self is below other
            x_start = max(self.x, other.x)
            x_end = min(self.x2, other.x2)
            if x_end > x_start:
                return {
                    'start': [x_start, self.y2, 0],
                    'end': [x_end, self.y2, 0],
                    'direction': 'horizontal',
                    'length': x_end - x_start
                }
        
        if abs(self.y - other.y2) < tolerance:
            # Self is above other
            x_start = max(self.x, other.x)
            x_end = min(self.x2, other.x2)
            if x_end > x_start:
                return {
                    'start': [x_start, self.y, 0],
                    'end': [x_end, self.y, 0],
                    'direction': 'horizontal',
                    'length': x_end - x_start
                }
        
        return None


@dataclass
class LayoutSolution:
    """A complete layout solution"""
    rooms: Dict[str, PlacedRoom]
    score: float
    walls: List[Dict] = field(default_factory=list)
    doors: List[Dict] = field(default_factory=list)


# =============================================================================
# DEFAULT ROOM DEFINITIONS (Architectural Best Practices)
# =============================================================================

# Hallway width: 40 inches = 3.33 feet
HALLWAY_WIDTH = 3.33  # 40 inches in feet

DEFAULT_ROOM_LIBRARY = {
    # === PUBLIC ZONE (privacy_level=1) ===
    "entry": RoomDefinition(
        name="Entry",
        room_type="entry",
        min_area=40,
        max_area=80,
        zone="public",
        must_connect=["exterior"],
        can_connect=["living", "hallway", "dining", "office", "garage"],
        prefer_exterior=True,
        require_exterior=True,
        privacy_level=1,
        priority=1
    ),
    "living": RoomDefinition(
        name="Living Room",
        room_type="living",
        min_area=200,
        zone="public",
        must_connect=["entry"],
        can_connect=["dining", "kitchen", "hallway", "primary_bedroom", "bedroom", "office"],
        prefer_exterior=True,
        privacy_level=1,
        allow_pass_through=False,
        priority=5
    ),
    "dining": RoomDefinition(
        name="Dining Room",
        room_type="dining",
        min_area=100,
        zone="public",
        can_connect=["living", "kitchen", "entry", "hallway"],
        cannot_connect=["bathroom", "primary_bath"],  # No bathroom door to dining
        prefer_exterior=True,
        privacy_level=1,
        priority=10
    ),
    "kitchen": RoomDefinition(
        name="Kitchen",
        room_type="kitchen",
        min_area=100,
        zone="public",
        can_connect=["dining", "living", "utility", "hallway", "garage", "laundry"],
        cannot_connect=["bathroom", "primary_bath", "bedroom", "primary_bedroom"],  # No direct bedroom access
        share_wall_only=["laundry"],  # Plumbing adjacency
        is_wet_room=True,  # Has plumbing
        privacy_level=1,
        priority=15
    ),
    "office": RoomDefinition(
        name="Office",
        room_type="office",
        min_area=100,
        zone="public",
        can_connect=["entry", "hallway", "living"],
        near_entry=True,
        prefer_exterior=True,
        privacy_level=2,  # Semi-private
        priority=18
    ),
    
    # === HALLWAY (40 inches = 3.33 ft wide) ===
    "hallway": RoomDefinition(
        name="Hallway",
        room_type="hallway",
        min_area=20,  # Minimal: ~3.3ft x 6ft
        max_area=100,
        zone="circulation",
        # Hallway can connect to almost anything - it's the universal connector
        can_connect=["living", "kitchen", "dining", "entry", "bedroom", "primary_bedroom", 
                     "bathroom", "primary_bath", "closet", "office", "utility", "laundry", 
                     "mechanical", "garage"],
        privacy_level=2,
        allow_pass_through=True,  # Hallways ARE pass-throughs
        min_aspect=0.12,  # Can be long and narrow (40in / 25ft = 0.13)
        max_aspect=8.0,
        priority=70  # Place hallway LAST - only use if needed
    ),
    
    # === PRIVATE ZONE (privacy_level=3) ===
    "primary_bedroom": RoomDefinition(
        name="Primary Bedroom",
        room_type="primary_bedroom",
        min_area=180,
        zone="private",
        can_connect=["hallway", "living", "primary_bath", "closet", "bedroom"],  # Added bedroom
        cannot_connect=["kitchen", "entry"],  # Removed dining, bathroom - now soft preference
        share_wall_only=["dining", "bathroom"],  # Can share wall but no door
        prefer_exterior=True,
        require_exterior=True,  # Code: bedroom needs egress window
        privacy_level=3,
        priority=30
    ),
    "primary_bath": RoomDefinition(
        name="Primary Bath",
        room_type="primary_bath",
        min_area=60,
        zone="private",
        must_connect=["primary_bedroom"],  # Ensuite
        can_connect=["closet"],
        cannot_connect=["living", "kitchen", "dining", "entry", "bedroom"],
        is_wet_room=True,
        needs_wet_wall=False,  # CHANGED: Now a soft constraint (scoring only)
        is_ensuite=True,
        privacy_level=3,
        priority=35
    ),
    "bedroom": RoomDefinition(
        name="Bedroom",
        room_type="bedroom",
        min_area=70,  # Code minimum for egress
        zone="private",
        can_connect=["hallway", "living", "bathroom", "closet", "primary_bedroom"],  # Added primary_bedroom
        cannot_connect=["kitchen", "entry"],  # Removed dining - now soft preference
        share_wall_only=["dining"],  # Can share wall but no door
        prefer_exterior=True,
        require_exterior=True,  # Code: bedroom needs egress window
        privacy_level=3,
        priority=40
    ),
    "bathroom": RoomDefinition(
        name="Bathroom",
        room_type="bathroom",
        min_area=35,  # Minimum functional size
        zone="private",
        # Door access from these rooms only - ADDED bedroom for jack-and-jill style
        can_connect=["hallway", "living", "bedroom", "primary_bedroom"],
        # Can share wall for plumbing but NO DOOR
        share_wall_only=["kitchen", "utility"],  # Plumbing adjacency without door
        # No contact at all with these
        cannot_connect=["dining", "entry", "primary_bath"],
        is_wet_room=True,
        needs_wet_wall=False,  # CHANGED: Now a soft constraint (scoring only)
        is_ensuite=False,  # Shared bathroom
        privacy_level=3,
        priority=45
    ),
    "closet": RoomDefinition(
        name="Walk-in Closet",
        room_type="closet",
        min_area=25,
        zone="private",
        can_connect=["primary_bedroom", "bedroom", "hallway", "primary_bath"],
        allow_pass_through=True,  # Can walk through closet to ensuite
        privacy_level=3,
        priority=50
    ),
    
    # === SERVICE ZONE ===
    "utility": RoomDefinition(
        name="Utility Room",
        room_type="utility",
        min_area=40,
        zone="service",
        can_connect=["kitchen", "garage", "hallway", "bathroom", "primary_bath", "laundry", "mechanical"],
        is_wet_room=True,  # Laundry has plumbing
        privacy_level=2,
        priority=55
    ),
    "laundry": RoomDefinition(
        name="Laundry",
        room_type="laundry",
        min_area=35,  # Minimum functional laundry
        max_area=60,
        zone="service",
        can_connect=["kitchen", "hallway", "utility", "garage", "bathroom", "mechanical"],
        cannot_connect=["living", "dining", "bedroom", "primary_bedroom"],  # Keep away from living spaces
        share_wall_only=["bathroom", "kitchen"],  # Plumbing adjacency
        is_wet_room=True,  # Has washer/dryer hookups
        needs_wet_wall=False,  # Soft preference via scoring
        privacy_level=2,
        priority=52
    ),
    "mechanical": RoomDefinition(
        name="Mechanical Room",
        room_type="mechanical",
        min_area=30,  # HVAC, water heater, electrical panel
        max_area=50,
        zone="service",
        can_connect=["garage", "hallway", "utility", "laundry", "closet"],
        cannot_connect=["living", "dining", "bedroom", "primary_bedroom", "kitchen"],  # Noise/safety
        prefer_exterior=False,  # Can be interior
        privacy_level=2,
        priority=58
    ),
    "garage": RoomDefinition(
        name="Garage",
        room_type="garage",
        min_area=200,
        zone="service",
        must_connect=["exterior"],
        can_connect=["utility", "entry", "kitchen", "laundry", "mechanical", "hallway"],  # Mud room flow
        prefer_exterior=True,
        require_exterior=True,
        privacy_level=1,
        priority=60
    )
}

# Wet rooms for plumbing adjacency checks
WET_ROOM_TYPES = {"kitchen", "bathroom", "primary_bath", "utility"}


# =============================================================================
# ROOM LAYOUT SOLVER
# =============================================================================

class RoomLayoutSolver:
    """
    Zone-based room layout solver with minimal circulation.
    
    Design Principles:
    1. Minimize hallway/circulation space (wasted space)
    2. Public zone at entry, Private zone away from entry
    3. Hallway only added if needed to connect private rooms
    4. Rooms should connect directly when possible
    
    Layout Pattern:
    ┌────────────────────────────────────────────┐
    │              PRIVATE ZONE                   │
    │   (Master, Bedrooms, Bathrooms)            │
    │   - Connected via minimal hallway OR       │
    │   - Direct access from public zone         │
    ├────────────────────────────────────────────┤
    │              PUBLIC ZONE                    │
    │   (Entry, Living, Dining, Kitchen)         │
    └────────────────────────────────────────────┘
    """
    
    def __init__(self, width: float, depth: float, grid_size: float = 2.0):
        """
        Args:
            width: Footprint width (X direction) in feet
            depth: Footprint depth (Y direction) in feet
            grid_size: Grid cell size for discretization (smaller = more precise, slower)
        """
        self.width = width
        self.depth = depth
        self.total_area = width * depth
        self.grid_size = grid_size
        
        # Grid dimensions
        self.grid_cols = int(math.ceil(width / grid_size))
        self.grid_rows = int(math.ceil(depth / grid_size))
        
        # Rooms to place
        self.rooms_to_place: List[RoomDefinition] = []
        
        # Entry door location (default: center of south wall)
        self.entry_location = (width / 2, 0)
        
        # Zone split: just public (near entry) and private (away from entry)
        # No dedicated circulation zone - hallway is placed only if needed
        self.zone_split = {
            'public_depth_ratio': 0.50,   # Public zone: 0 to 50% of depth
            'private_depth_ratio': 0.50   # Private zone: 50% to 100% of depth
        }
        
        # Solutions found
        self.solutions: List[LayoutSolution] = []

        # Interior-only mode: skip exterior wall requirements
        # Used when placing partitions within an existing shell
        self.interior_only = False

        # Search statistics
        self.nodes_explored = 0
        self.backtracks = 0
    
    def set_zone_split(self, public: float = 0.5, private: float = 0.5) -> 'RoomLayoutSolver':
        """
        Customize zone proportions.
        
        Args:
            public: Ratio of depth for public zone (0.0 - 1.0)
            private: Ratio of depth for private zone
        """
        total = public + private
        self.zone_split = {
            'public_depth_ratio': public / total,
            'private_depth_ratio': private / total
        }
        return self

    def set_interior_only(self, interior_only: bool = True) -> 'RoomLayoutSolver':
        """
        Enable interior-only mode for placing partitions within an existing shell.

        When enabled, exterior wall requirements (require_exterior) are skipped.
        This is used when creating room partitions inside existing exterior walls.

        Args:
            interior_only: Whether to enable interior-only mode

        Returns:
            self for chaining
        """
        self.interior_only = interior_only
        return self

    def _get_zone_bounds(self, zone: str) -> Tuple[float, float, float, float]:
        """Get (x1, y1, x2, y2) bounds for a zone"""
        public_depth = self.depth * self.zone_split['public_depth_ratio']
        private_ratio = self.zone_split['private_depth_ratio']
        
        # If a zone has 0 ratio, use full footprint (zone constraints disabled)
        if self.zone_split['public_depth_ratio'] >= 0.99:
            # Public zone is effectively everything - all zones use full footprint
            return (0, 0, self.width, self.depth)
        
        if zone == "public":
            return (0, 0, self.width, public_depth)
        elif zone == "private":
            if private_ratio < 0.01:
                # Private zone disabled - use full footprint
                return (0, 0, self.width, self.depth)
            return (0, public_depth, self.width, self.depth)
        elif zone == "circulation":
            # Circulation is at the boundary between public and private
            # It's a thin strip, not a full zone
            corridor_width = 4.0  # Standard corridor width
            return (0, public_depth - corridor_width/2, self.width, public_depth + corridor_width/2)
        else:  # service - use public zone
            return (0, 0, self.width, public_depth if public_depth > 0 else self.depth)
    
    def add_room(self, room_type: str, **overrides) -> 'RoomLayoutSolver':
        """
        Add a room to the program.
        
        Args:
            room_type: Type from DEFAULT_ROOM_LIBRARY or custom
            **overrides: Override default properties (min_area, name, etc.)
        
        Returns:
            self for chaining
        """
        if room_type in DEFAULT_ROOM_LIBRARY:
            # Copy default and apply overrides
            default = DEFAULT_ROOM_LIBRARY[room_type]
            room = RoomDefinition(
                name=overrides.get('name', default.name),
                room_type=room_type,
                min_area=overrides.get('min_area', default.min_area),
                max_area=overrides.get('max_area', default.max_area),
                zone=overrides.get('zone', default.zone),
                must_connect=overrides.get('must_connect', default.must_connect.copy()),
                can_connect=overrides.get('can_connect', default.can_connect.copy()),
                cannot_connect=overrides.get('cannot_connect', default.cannot_connect.copy()),
                share_wall_only=overrides.get('share_wall_only', default.share_wall_only.copy()),
                prefer_exterior=overrides.get('prefer_exterior', default.prefer_exterior),
                require_exterior=overrides.get('require_exterior', default.require_exterior),
                prefer_corner=overrides.get('prefer_corner', default.prefer_corner),
                near_entry=overrides.get('near_entry', default.near_entry),
                connects_to_circulation=overrides.get('connects_to_circulation', default.connects_to_circulation),
                is_wet_room=overrides.get('is_wet_room', default.is_wet_room),
                needs_wet_wall=overrides.get('needs_wet_wall', default.needs_wet_wall),
                privacy_level=overrides.get('privacy_level', default.privacy_level),
                allow_pass_through=overrides.get('allow_pass_through', default.allow_pass_through),
                is_ensuite=overrides.get('is_ensuite', default.is_ensuite),
                priority=overrides.get('priority', default.priority),
                min_aspect=overrides.get('min_aspect', default.min_aspect),
                max_aspect=overrides.get('max_aspect', default.max_aspect)
            )
        else:
            # Custom room type
            room = RoomDefinition(
                name=overrides.get('name', room_type.title()),
                room_type=room_type,
                min_area=overrides.get('min_area', 100),
                zone=overrides.get('zone', 'public'),
                must_connect=overrides.get('must_connect', []),
                can_connect=overrides.get('can_connect', []),
                cannot_connect=overrides.get('cannot_connect', []),
                share_wall_only=overrides.get('share_wall_only', []),
                prefer_exterior=overrides.get('prefer_exterior', False),
                require_exterior=overrides.get('require_exterior', False),
                is_wet_room=overrides.get('is_wet_room', False),
                needs_wet_wall=overrides.get('needs_wet_wall', False),
                privacy_level=overrides.get('privacy_level', 1),
                priority=overrides.get('priority', 50)
            )
        
        self.rooms_to_place.append(room)
        return self
    
    def set_entry_location(self, x: float, y: float) -> 'RoomLayoutSolver':
        """Set where the main entry door is located"""
        self.entry_location = (x, y)
        return self
    
    def solve(self, max_solutions: int = 5, timeout_nodes: int = 10000) -> List[LayoutSolution]:
        """
        Find valid room layouts.
        
        Args:
            max_solutions: Stop after finding this many solutions
            timeout_nodes: Stop after exploring this many nodes
        
        Returns:
            List of solutions, sorted by score (best first)
        """
        self.solutions = []
        self.nodes_explored = 0
        self.backtracks = 0
        
        # Sort rooms by priority
        sorted_rooms = sorted(self.rooms_to_place, key=lambda r: r.priority)
        
        # Validate total area
        total_required = sum(r.min_area for r in sorted_rooms)
        if total_required > self.total_area:
            print(f"[Warning] Rooms require {total_required} sqft but footprint is only {self.total_area} sqft")

        print(f"[Search] Starting: {len(sorted_rooms)} rooms, {self.grid_cols}x{self.grid_rows} grid")
        print(f"   Max positions per room: {MAX_POSITIONS_PER_ROOM}")
        print(f"   Progress reporting every {PROGRESS_REPORT_INTERVAL} nodes")

        # Start recursive search
        self._search(
            rooms=sorted_rooms,
            index=0,
            placed={},
            max_solutions=max_solutions,
            timeout_nodes=timeout_nodes
        )

        print(f"[Done] {len(self.solutions)} solutions, {self.nodes_explored} nodes, {self.backtracks} backtracks")
        
        # Sort by score
        self.solutions.sort(key=lambda s: s.score, reverse=True)
        
        return self.solutions
    
    def _search(self, rooms: List[RoomDefinition], index: int, placed: Dict[str, PlacedRoom],
                max_solutions: int, timeout_nodes: int):
        """Recursive backtracking search"""
        
        self.nodes_explored += 1
        
        # === PROGRESS REPORTING ===
        if self.nodes_explored % PROGRESS_REPORT_INTERVAL == 0:
            rooms_placed = len(placed)
            rooms_total = len(rooms)
            current_room = rooms[index].room_type if index < len(rooms) else "done"
            print(f"   Progress: {self.nodes_explored:,} nodes | "
                  f"{len(self.solutions)} solutions | "
                  f"{rooms_placed}/{rooms_total} placed | "
                  f"trying: {current_room}")

        # Check termination conditions
        if len(self.solutions) >= max_solutions:
            return
        if self.nodes_explored >= timeout_nodes:
            print(f"[Timeout] at {timeout_nodes:,} nodes")
            return

        # Base case: all rooms placed
        if index >= len(rooms):
            solution = self._create_solution(placed)
            self.solutions.append(solution)
            print(f"   [Found] solution #{len(self.solutions)} (score: {solution.score:.1f})")
            return
        
        room = rooms[index]
        
        # Find valid positions for this room
        positions = self._find_valid_positions(room, placed)
        
        if not positions:
            self.backtracks += 1
            return
        
        # Track valid positions found for diagnostics
        valid_count = 0
        
        # Try each position
        for pos in positions:
            placed_room = PlacedRoom(
                definition=room,
                x=pos['x'],
                y=pos['y'],
                width=pos['width'],
                height=pos['height']
            )
            
            # Check if valid
            if self._is_valid_placement(placed_room, placed):
                valid_count += 1
                # Place room and recurse
                placed[room.room_type] = placed_room
                self._search(rooms, index + 1, placed, max_solutions, timeout_nodes)
                del placed[room.room_type]
                
                # Early exit if we found enough solutions
                if len(self.solutions) >= max_solutions:
                    return
        
        # Only count as backtrack if NO valid positions found
        if valid_count == 0:
            self.backtracks += 1
    
    def _find_valid_positions(self, room: RoomDefinition, placed: Dict[str, PlacedRoom]) -> List[Dict]:
        """Find candidate positions for a room within its designated zone"""
        
        positions = []
        
        # Get zone bounds for this room
        zone_bounds = self._get_zone_bounds(room.zone)
        zone_x1, zone_y1, zone_x2, zone_y2 = zone_bounds
        zone_width = zone_x2 - zone_x1
        zone_height = zone_y2 - zone_y1
        
        # Get aspect ratio limits
        min_aspect = getattr(room, 'min_aspect', 0.5)
        max_aspect = getattr(room, 'max_aspect', 2.0)
        
        # Try different aspect ratios
        aspect_ratios = [1.0, 1.33, 1.5, 2.0, 0.75, 0.67, 0.5]
        
        # Try larger sizes first to maximize space usage
        # size_mult of 1.4 means try 40% larger than min_area first
        size_multipliers = [1.4, 1.3, 1.2, 1.1, 1.0]
        
        for size_mult in size_multipliers:
            # === EARLY EXIT IF CAP REACHED ===
            if len(positions) >= MAX_POSITIONS_PER_ROOM:
                break
                
            target_area = room.min_area * size_mult
            
            for aspect in aspect_ratios:
                # === EARLY EXIT IF CAP REACHED ===
                if len(positions) >= MAX_POSITIONS_PER_ROOM:
                    break
                    
                # Skip aspects outside room's limits
                if aspect < min_aspect or aspect > max_aspect:
                    continue
                    
                width = math.sqrt(target_area * aspect)
                height = target_area / width
                
                # Snap to grid
                width = max(self.grid_size, round(width / self.grid_size) * self.grid_size)
                height = max(self.grid_size, round(height / self.grid_size) * self.grid_size)
                
                # Skip if room doesn't fit in zone
                if width > zone_width or height > zone_height:
                    continue
                
                # Generate positions within zone
                if not placed:
                    # First room - special handling for entry
                    if "exterior" in room.must_connect or room.room_type == "entry":
                        entry_x, entry_y = self.entry_location
                        
                        # For entry room, prioritize position centered on entry_location
                        if room.room_type == "entry":
                            # Try centered on entry location first
                            centered_x = entry_x - width / 2
                            centered_x = max(0, min(self.width - width, centered_x))
                            centered_x = round(centered_x / self.grid_size) * self.grid_size
                            
                            if entry_y == 0:  # South wall entry
                                positions.append({'x': centered_x, 'y': 0, 'width': width, 'height': height})
                            elif entry_y >= self.depth - 1:  # North wall entry
                                positions.append({'x': centered_x, 'y': self.depth - height, 'width': width, 'height': height})
                        
                        # Then try all other exterior wall positions (sorted by distance from entry)
                        other_positions = []
                        for x in self._grid_range(zone_x1, zone_x2 - width):
                            # South wall (if zone touches it)
                            if zone_y1 == 0:
                                other_positions.append({'x': x, 'y': 0, 'width': width, 'height': height})
                            # North wall (if zone touches it)
                            if zone_y2 >= self.depth - 0.1:
                                other_positions.append({'x': x, 'y': self.depth - height, 'width': width, 'height': height})
                        for y in self._grid_range(zone_y1, zone_y2 - height):
                            # West wall
                            if zone_x1 == 0:
                                other_positions.append({'x': 0, 'y': y, 'width': width, 'height': height})
                            # East wall
                            if zone_x2 >= self.width - 0.1:
                                other_positions.append({'x': self.width - width, 'y': y, 'width': width, 'height': height})
                        
                        # Sort by distance to entry location (closest first)
                        other_positions.sort(key=lambda p: abs(p['x'] + p['width']/2 - entry_x) + abs(p['y'] + p['height']/2 - entry_y))
                        positions.extend(other_positions)
                    else:
                        # No exterior constraint - try all positions in zone
                        for x in self._grid_range(zone_x1, zone_x2 - width):
                            if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                break
                            for y in self._grid_range(zone_y1, zone_y2 - height):
                                if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                    break
                                positions.append({'x': x, 'y': y, 'width': width, 'height': height})
                else:
                    # Find rooms this must connect to
                    must_connect = room.must_connect.copy()
                    if "exterior" in must_connect:
                        must_connect.remove("exterior")
                    
                    # Special: hallway must span width and connect zones
                    if room.room_type == "hallway":
                        # Try full-width hallway positions
                        hallway_y = zone_y1
                        positions.append({
                            'x': 0,
                            'y': hallway_y,
                            'width': self.width,  # Full width
                            'height': height
                        })
                        # Also try partial width
                        for x in self._grid_range(0, self.width - width):
                            if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                break
                            positions.append({'x': x, 'y': hallway_y, 'width': width, 'height': height})
                    
                    # Get positions adjacent to required neighbors
                    elif must_connect:
                        found_any = False
                        for required in must_connect:
                            if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                break
                            if required in placed:
                                found_any = True
                                neighbor = placed[required]
                                adj_positions = self._get_adjacent_positions(neighbor, width, height)
                                # Filter to only positions within zone
                                for pos in adj_positions:
                                    if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                        break
                                    if self._position_in_zone(pos, zone_bounds):
                                        positions.append(pos)
                        
                        # If required room not placed yet, try all zone positions
                        if not found_any:
                            for x in self._grid_range(zone_x1, zone_x2 - width):
                                if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                    break
                                for y in self._grid_range(zone_y1, zone_y2 - height):
                                    if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                        break
                                    positions.append({'x': x, 'y': y, 'width': width, 'height': height})
                    else:
                        # No must_connect - try adjacent to any placed room
                        # Prioritize based on room constraints:
                        # 1. Wet rooms need wet wall adjacency (bathroom near kitchen)
                        # 2. Shared bathrooms need common area access (near living/hallway)
                        # 3. Rooms requiring exterior need exterior positions
                        
                        priority_positions = []  # Best positions (wet wall + accessible)
                        wet_room_positions = []  # Good for plumbing
                        accessible_positions = []  # Good for access
                        other_positions = []  # Everything else
                        
                        # If room REQUIRES exterior, generate exterior positions FIRST
                        if room.require_exterior:
                            ext_positions = self._get_exterior_positions(width, height, placed)
                            # Filter to only those touching an allowed room
                            for pos in ext_positions:
                                if len(priority_positions) >= MAX_POSITIONS_PER_ROOM:
                                    break
                                test = PlacedRoom(
                                    definition=room,
                                    x=pos['x'],
                                    y=pos['y'],
                                    width=pos['width'],
                                    height=pos['height']
                                )
                                # Check if touches any placed room
                                touches_any = any(test.touches(p) for p in placed.values())
                                if touches_any:
                                    priority_positions.append(pos)
                        
                        # Also try adjacent to placed rooms
                        for _, neighbor in placed.items():
                            if len(positions) + len(priority_positions) + len(wet_room_positions) + len(accessible_positions) + len(other_positions) >= MAX_POSITIONS_PER_ROOM:
                                break
                            adj_positions = self._get_adjacent_positions(neighbor, width, height)
                            for pos in adj_positions:
                                is_wet_neighbor = neighbor.definition.is_wet_room
                                is_accessible = neighbor.definition.room_type in ["living", "hallway"]
                                
                                # Categorize positions for bathrooms
                                if room.needs_wet_wall or room.room_type == "bathroom":
                                    if is_wet_neighbor and is_accessible:
                                        priority_positions.append(pos)  # Best: both!
                                    elif is_wet_neighbor:
                                        wet_room_positions.append(pos)
                                    elif is_accessible:
                                        accessible_positions.append(pos)
                                    else:
                                        other_positions.append(pos)
                                else:
                                    other_positions.append(pos)
                        
                        # Add positions in priority order
                        positions.extend(priority_positions)
                        positions.extend(wet_room_positions)
                        positions.extend(accessible_positions)
                        positions.extend(other_positions)
                        
                        # Also try exterior positions if room requires OR prefers exterior
                        if (room.require_exterior or room.prefer_exterior) and len(positions) < MAX_POSITIONS_PER_ROOM:
                            ext_positions = self._get_exterior_positions(width, height, placed)
                            for pos in ext_positions:
                                if len(positions) >= MAX_POSITIONS_PER_ROOM:
                                    break
                                positions.append(pos)
        
        # Remove duplicates and invalid positions
        seen = set()
        valid_positions = []
        for pos in positions:
            if len(valid_positions) >= MAX_POSITIONS_PER_ROOM:
                break
            key = (pos['x'], pos['y'], pos['width'], pos['height'])
            if key not in seen:
                seen.add(key)
                if self._position_in_bounds(pos):
                    valid_positions.append(pos)
        
        return valid_positions
    
    def _get_adjacent_positions(self, neighbor: PlacedRoom, width: float, height: float) -> List[Dict]:
        """Get positions adjacent to a placed room"""
        positions = []
        
        # Right of neighbor
        positions.append({
            'x': neighbor.x2,
            'y': neighbor.y,
            'width': width,
            'height': height
        })
        
        # Left of neighbor
        positions.append({
            'x': neighbor.x - width,
            'y': neighbor.y,
            'width': width,
            'height': height
        })
        
        # Above neighbor
        positions.append({
            'x': neighbor.x,
            'y': neighbor.y2,
            'width': width,
            'height': height
        })
        
        # Below neighbor
        positions.append({
            'x': neighbor.x,
            'y': neighbor.y - height,
            'width': width,
            'height': height
        })
        
        # Also try aligned variations
        for offset in self._grid_range(-width + self.grid_size, neighbor.width):
            positions.append({
                'x': neighbor.x + offset,
                'y': neighbor.y2,
                'width': width,
                'height': height
            })
            positions.append({
                'x': neighbor.x + offset,
                'y': neighbor.y - height,
                'width': width,
                'height': height
            })
        
        return positions
    
    def _position_in_zone(self, pos: Dict, zone_bounds: Tuple[float, float, float, float]) -> bool:
        """Check if a position is within zone bounds (with tolerance)"""
        tolerance = 0.1
        zone_x1, zone_y1, zone_x2, zone_y2 = zone_bounds
        
        return (
            pos['x'] >= zone_x1 - tolerance and
            pos['y'] >= zone_y1 - tolerance and
            pos['x'] + pos['width'] <= zone_x2 + tolerance and
            pos['y'] + pos['height'] <= zone_y2 + tolerance
        )
    
    def _get_exterior_positions(self, width: float, height: float, placed: Dict[str, PlacedRoom]) -> List[Dict]:
        """Get positions along exterior walls"""
        positions = []
        
        # South wall
        for x in self._grid_range(0, self.width - width):
            positions.append({'x': x, 'y': 0, 'width': width, 'height': height})
        
        # North wall
        for x in self._grid_range(0, self.width - width):
            positions.append({'x': x, 'y': self.depth - height, 'width': width, 'height': height})
        
        # West wall
        for y in self._grid_range(0, self.depth - height):
            positions.append({'x': 0, 'y': y, 'width': width, 'height': height})
        
        # East wall
        for y in self._grid_range(0, self.depth - height):
            positions.append({'x': self.width - width, 'y': y, 'width': width, 'height': height})
        
        return positions
    
    def _grid_range(self, start: float, end: float) -> List[float]:
        """Generate grid-aligned values in range"""
        values = []
        current = start
        while current <= end:
            values.append(current)
            current += self.grid_size
        return values
    
    def _position_in_bounds(self, pos: Dict) -> bool:
        """Check if position is within footprint"""
        return (
            pos['x'] >= 0 and
            pos['y'] >= 0 and
            pos['x'] + pos['width'] <= self.width + 0.01 and
            pos['y'] + pos['height'] <= self.depth + 0.01
        )
    
    def _is_valid_placement(self, room: PlacedRoom, placed: Dict[str, PlacedRoom]) -> bool:
        """Check if a room placement satisfies all constraints"""
        
        # Check overlap with existing rooms
        for name, other in placed.items():
            if room.overlaps(other):
                return False
        
        # === CONNECTIVITY CHECK ===
        # Room must touch at least one placed room (ensures connected graph)
        if placed:
            touches_any = any(room.touches(other) for other in placed.values())
            if not touches_any:
                return False
        
        # === EXTERIOR WALL REQUIREMENT ===
        # Bedrooms MUST have exterior walls (egress code)
        # Skip in interior_only mode (placing partitions within existing shell)
        if not self.interior_only:
            if room.definition.require_exterior:
                if not self._touches_exterior(room):
                    return False

            # Check must_connect constraints (must have door to these)
            for required in room.definition.must_connect:
                if required == "exterior":
                    if not self._touches_exterior(room):
                        return False
                    break  # Only check exterior once
        else:
            # In interior_only mode, still check non-exterior must_connect
            pass

        # Check must_connect constraints (non-exterior)
        for required in room.definition.must_connect:
            if required == "exterior":
                continue  # Already handled above
            elif required in placed:
                if not room.touches(placed[required]):
                    return False
            # If required room not placed yet, we'll check when it is
        
        # Check cannot_connect constraints (cannot touch at all)
        for forbidden in room.definition.cannot_connect:
            if forbidden in placed:
                if room.touches(placed[forbidden]):
                    return False
        
        # === DOOR PLACEMENT VALIDATION ===
        # Check that room only has doors to allowed rooms
        # share_wall_only rooms can touch but shouldn't count as "connected" (no door)
        allowed_doors = set(room.definition.must_connect) | set(room.definition.can_connect)
        allowed_walls = set(room.definition.share_wall_only)  # Can touch but no door
        allowed_doors.discard("exterior")
        
        for name, other in placed.items():
            if room.touches(other):
                other_type = other.definition.room_type
                
                # If this room is in share_wall_only, touching is OK (but no door)
                if other_type in allowed_walls:
                    continue  # Wall sharing OK
                
                # If not in allowed_doors, check if other room allows us
                if other_type not in allowed_doors:
                    other_allowed = set(other.definition.must_connect) | set(other.definition.can_connect)
                    other_walls = set(other.definition.share_wall_only)
                    
                    # If other room has us in share_wall_only, that's OK
                    if room.definition.room_type in other_walls:
                        continue
                    
                    # Otherwise, check if other room allows door to us
                    if room.definition.room_type not in other_allowed:
                        return False
        
        # === WET WALL CONSTRAINT ===
        # Bathrooms should share a wall with another wet room (plumbing efficiency)
        if room.definition.needs_wet_wall:
            has_wet_neighbor = False
            for name, other in placed.items():
                if room.touches(other) and other.definition.is_wet_room:
                    has_wet_neighbor = True
                    break
            # Soft constraint - handled in scoring
        
        return True
    
    def _check_wet_wall_adjacency(self, room: PlacedRoom, placed: Dict[str, PlacedRoom]) -> bool:
        """Check if a wet room has proper plumbing adjacency"""
        if not room.definition.needs_wet_wall:
            return True
        
        for name, other in placed.items():
            if room.touches(other) and other.definition.is_wet_room:
                return True
        return False
    
    def _touches_exterior(self, room: PlacedRoom) -> bool:
        """Check if room touches an exterior wall"""
        tolerance = 0.1
        return (
            room.x < tolerance or  # West wall
            room.y < tolerance or  # South wall
            room.x2 > self.width - tolerance or  # East wall
            room.y2 > self.depth - tolerance  # North wall
        )
    
    def _create_solution(self, placed: Dict[str, PlacedRoom]) -> LayoutSolution:
        """Create a complete solution from placed rooms"""
        
        # Deep copy the placed rooms
        rooms = {name: copy.deepcopy(room) for name, room in placed.items()}
        
        # Calculate score
        score = self._score_layout(rooms)
        
        # Generate walls
        walls = self._generate_walls(rooms)
        
        # Generate doors
        doors = self._generate_doors(rooms)
        
        return LayoutSolution(
            rooms=rooms,
            score=score,
            walls=walls,
            doors=doors
        )
    
    def _score_layout(self, placed: Dict[str, PlacedRoom]) -> float:
        """
        Score a layout (higher = better)
        
        Architectural principles reflected in scoring:
        1. Minimize circulation/hallway space
        2. Bedrooms MUST have exterior walls (windows)
        3. Wet rooms should share walls (plumbing efficiency)
        4. Privacy gradient respected
        5. Efficient use of space
        6. Good room proportions
        7. Shared bathrooms must be accessible from common areas
        """
        score = 100.0  # Base score
        
        for name, room in placed.items():
            # === ASPECT RATIO ===
            # Bonus for good aspect ratio (closer to square)
            score += room.aspect_ratio * 10
            
            # === EXTERIOR WALL PREFERENCES ===
            if room.definition.require_exterior:
                if self._touches_exterior(room):
                    score += 20  # Required and has it
                else:
                    score -= 100  # Required but missing - BIG penalty
            elif room.definition.prefer_exterior:
                if self._touches_exterior(room):
                    score += 15  # Preferred and has it
            
            # Interior rooms on exterior = slight penalty (wasted window potential)
            if room.definition.room_type in ['bathroom', 'closet', 'utility']:
                if self._touches_exterior(room):
                    score -= 5
            
            # === NEAR ENTRY ===
            if room.definition.near_entry:
                entry_x, entry_y = self.entry_location
                dist = math.sqrt((room.center[0] - entry_x)**2 + (room.center[1] - entry_y)**2)
                score += max(0, 20 - dist)
            
            # === HALLWAY PENALTIES ===
            if room.definition.room_type == "hallway":
                score -= 10  # Penalty for hallway existing
                if room.area > 40:
                    score -= (room.area - 40) * 0.5  # Extra penalty for large hallways
            
            # === WET WALL SCORING (SOFT CONSTRAINT) ===
            # Reward wet rooms that are adjacent to other wet rooms (plumbing efficiency)
            if room.definition.is_wet_room:
                has_wet_neighbor = any(
                    room.touches(other) and other.definition.is_wet_room and other != room
                    for other in placed.values()
                )
                if has_wet_neighbor:
                    score += 20  # Good plumbing adjacency bonus
            
            # Legacy support: if needs_wet_wall is still set, apply stronger scoring
            if room.definition.needs_wet_wall:
                has_wet_neighbor = any(
                    room.touches(other) and other.definition.is_wet_room
                    for other in placed.values()
                )
                if has_wet_neighbor:
                    score += 25  # Additional bonus for required wet wall
                else:
                    score -= 40  # Penalty for missing required wet wall
            
            # === PRIVACY GRADIENT ===
            # Check if private rooms are too close to entry
            if room.definition.privacy_level == 3:  # Private room
                entry_x, entry_y = self.entry_location
                dist_to_entry = math.sqrt((room.center[0] - entry_x)**2 + (room.center[1] - entry_y)**2)
                if dist_to_entry < 10:
                    score -= 10  # Private room too close to entry
                else:
                    score += 5  # Good privacy separation
        
        # === NO HALLWAY BONUS ===
        if "hallway" not in placed:
            score += 25  # Big bonus for no circulation waste
        
        # === SPACE EFFICIENCY ===
        used_area = sum(r.area for r in placed.values())
        efficiency = used_area / self.total_area
        score += efficiency * 30  # Up to 30 points for 100% efficiency
        
        if efficiency < 0.75:
            score -= (0.75 - efficiency) * 50  # Penalty for <75% efficiency
        
        # === SHARED BATHROOM ACCESSIBILITY (CRITICAL) ===
        # Shared bathrooms MUST be accessible from hallway or living, NOT just through a bedroom
        bathrooms = [r for r in placed.values() 
                     if r.definition.room_type == "bathroom" and not r.definition.is_ensuite]
        
        for bath in bathrooms:
            # Find what rooms the bathroom touches
            touching_rooms = [
                other for other in placed.values()
                if bath.touches(other)
            ]
            
            # Check if accessible from common area (hallway or living)
            accessible_from_common = any(
                other.definition.room_type in ["hallway", "living"]
                for other in touching_rooms
            )
            
            # Check if ONLY accessible through a bedroom
            only_touches_bedrooms = all(
                other.definition.room_type in ["bedroom", "primary_bedroom", "closet"]
                for other in touching_rooms
            )
            
            if accessible_from_common:
                score += 30  # Excellent - shared bathroom properly accessible
            elif only_touches_bedrooms:
                score -= 60  # BAD - shared bathroom only through bedroom (basically ensuite)
            else:
                score -= 20  # Not ideal accessibility
        
        # === ENSUITE VALIDATION ===
        # Ensuites should ONLY connect to their bedroom (and maybe closet)
        ensuites = [r for r in placed.values() if r.definition.is_ensuite]
        for ensuite in ensuites:
            touching_rooms = [
                other for other in placed.values()
                if ensuite.touches(other)
            ]
            # Should touch primary_bedroom
            touches_primary = any(
                other.definition.room_type == "primary_bedroom"
                for other in touching_rooms
            )
            if touches_primary:
                score += 15  # Good ensuite placement
            else:
                score -= 30  # Ensuite not connected to primary bedroom
        
        return score
    
    def _generate_walls(self, placed: Dict[str, PlacedRoom]) -> List[Dict]:
        """Generate interior wall segments"""
        walls = []
        
        # Find all shared edges between rooms
        room_list = list(placed.values())
        
        for i, room1 in enumerate(room_list):
            for room2 in room_list[i+1:]:
                edge = room1.shared_edge(room2)
                if edge:
                    walls.append({
                        'start_point': edge['start'],
                        'end_point': edge['end'],
                        'rooms': [room1.definition.name, room2.definition.name],
                        'type': 'interior'
                    })
        
        # Find edges against empty space (walls needed to enclose rooms)
        # This is more complex - skip for now, exterior walls handle boundary
        
        return walls
    
    def _generate_doors(self, placed: Dict[str, PlacedRoom]) -> List[Dict]:
        """Generate door locations at room connections (excluding share_wall_only)"""
        doors = []
        
        room_list = list(placed.values())
        
        for i, room1 in enumerate(room_list):
            for room2 in room_list[i+1:]:
                edge = room1.shared_edge(room2)
                if edge:
                    # Check if this is a share_wall_only connection (no door)
                    room1_type = room1.definition.room_type
                    room2_type = room2.definition.room_type
                    
                    # Skip if either room has the other in share_wall_only
                    if room2_type in room1.definition.share_wall_only:
                        continue
                    if room1_type in room2.definition.share_wall_only:
                        continue
                    
                    # Place door at center of shared edge
                    start = edge['start']
                    end = edge['end']
                    center = [
                        (start[0] + end[0]) / 2,
                        (start[1] + end[1]) / 2,
                        0
                    ]
                    
                    doors.append({
                        'point': center,
                        'rooms': [room1.definition.name, room2.definition.name],
                        'width': 3.0  # Standard door width
                    })
        
        return doors


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def print_ascii_layout(solution: LayoutSolution, width: float, depth: float, scale: float = 1.0):
    """Print an ASCII representation of the layout"""
    
    cols = int(width * scale)
    rows = int(depth * scale)
    
    # Initialize grid
    grid = [['.' for _ in range(cols)] for _ in range(rows)]
    
    # Draw rooms
    for name, room in solution.rooms.items():
        x1 = int(room.x * scale)
        y1 = int(room.y * scale)
        x2 = int(room.x2 * scale)
        y2 = int(room.y2 * scale)
        
        char = name[0].upper()
        
        for y in range(max(0, y1), min(rows, y2)):
            for x in range(max(0, x1), min(cols, x2)):
                grid[y][x] = char
    
    # Print
    print("\n" + "=" * (cols + 2))
    for row in reversed(grid):  # Reverse so Y increases upward
        print("|" + "".join(row) + "|")
    print("=" * (cols + 2))
    
    # Legend
    print("\nLegend:")
    for name, room in solution.rooms.items():
        print(f"  {name[0].upper()} = {room.definition.name} ({room.area:.0f} sqft)")


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("🏠 Room Layout Solver v2 (Fixed) - Zone Constraints Disabled\n")
    print(f"⚡ Performance settings:")
    print(f"   Max positions per room: {MAX_POSITIONS_PER_ROOM}")
    print(f"   Progress report interval: {PROGRESS_REPORT_INTERVAL} nodes\n")
    
    # Create solver for 40x30 footprint
    solver = RoomLayoutSolver(width=40, depth=30, grid_size=2)
    
    # Set entry location to CENTER of south wall
    solver.set_entry_location(20, 0)  # Center of 40ft wide south wall
    
    # DISABLE ZONE CONSTRAINTS - let rooms go anywhere
    # By setting public to 100%, all rooms use the full footprint
    solver.set_zone_split(public=1.0, private=0.0)
    
    # Print zone info
    print("📐 Layout Settings:")
    print(f"   Footprint: {solver.width}' x {solver.depth}' = {solver.total_area} sqft")
    print(f"   Entry Location: {solver.entry_location} (center of south wall)")
    print(f"   Zone constraints: DISABLED (all rooms use full footprint)")
    print()
    
    # Add rooms (order doesn't matter - sorted by priority)
    # PUBLIC ZONE
    solver.add_room("entry", min_area=50)
    solver.add_room("living", min_area=200)
    solver.add_room("dining", min_area=80)
    solver.add_room("kitchen", min_area=100)
    
    # PRIVATE ZONE
    solver.add_room("primary_bedroom", min_area=150)
    solver.add_room("bedroom", min_area=100, name="Bedroom 2")
    solver.add_room("bathroom", min_area=40)
    
    # SERVICE ZONE
    solver.add_room("laundry", min_area=35)
    solver.add_room("mechanical", min_area=30)
    
    # CIRCULATION (added last - only used if needed for connectivity)
    solver.add_room("hallway", min_area=24)
    
    # Solve
    solutions = solver.solve(max_solutions=10, timeout_nodes=100000)
    
    # Display best solution
    if solutions:
        best = solutions[0]
        print(f"\n🏆 Best Solution (score: {best.score:.1f}):")
        print_ascii_layout(best, 40, 30, scale=0.5)
        
        # Check architectural constraints
        print("\n📋 Architectural Analysis:")
        
        # Hallway check
        has_hallway = "hallway" in best.rooms
        print(f"   🚶 Circulation: {'Hallway needed' if has_hallway else 'NO HALLWAY - Direct connections!'}")
        
        # Exterior wall check for bedrooms
        print("\n   🪟 Exterior Walls (Egress):")
        for name, room in best.rooms.items():
            if room.definition.require_exterior:
                has_ext = solver._touches_exterior(room)
                status = "✅" if has_ext else "❌"
                print(f"      {status} {room.definition.name}: {'HAS exterior wall' if has_ext else 'MISSING exterior wall'}")
        
        # Wet wall check
        print("\n   🚿 Wet Wall Adjacency (Plumbing):")
        wet_rooms = [(n, r) for n, r in best.rooms.items() if r.definition.needs_wet_wall]
        for name, room in wet_rooms:
            has_wet = solver._check_wet_wall_adjacency(room, best.rooms)
            # Find which wet room it touches
            wet_neighbors = [
                other.definition.name for other in best.rooms.values()
                if room.touches(other) and other.definition.is_wet_room
            ]
            status = "✅" if has_wet else "⚠️"
            if wet_neighbors:
                print(f"      {status} {room.definition.name}: shares wall with {', '.join(wet_neighbors)}")
            else:
                print(f"      {status} {room.definition.name}: NO wet wall neighbor (needs kitchen/utility)")
        
        # Bathroom accessibility
        print("\n   🚽 Bathroom Accessibility:")
        bathrooms = [(n, r) for n, r in best.rooms.items() 
                     if r.definition.room_type == "bathroom" and not r.definition.is_ensuite]
        for name, bath in bathrooms:
            touching = [
                other.definition.name for other in best.rooms.values()
                if bath.touches(other)
            ]
            accessible_from_common = any(
                other.definition.room_type in ["hallway", "living"]
                for other in best.rooms.values()
                if bath.touches(other)
            )
            if accessible_from_common:
                print(f"      ✅ {bath.definition.name}: accessible from common area")
                print(f"         Connects to: {', '.join(touching)}")
            else:
                print(f"      ❌ {bath.definition.name}: NOT accessible from hallway/living")
                print(f"         Only connects to: {', '.join(touching)}")
        
        print(f"\n🧱 Interior Walls: {len(best.walls)}")
        for wall in best.walls:
            print(f"   {wall['rooms'][0]} <-> {wall['rooms'][1]}")
        
        print(f"\n🚪 Doors: {len(best.doors)}")
        for door in best.doors:
            print(f"   {door['rooms'][0]} <-> {door['rooms'][1]} at {door['point']}")
        
        # Calculate efficiency
        total_room_area = sum(r.area for r in best.rooms.values())
        print(f"\n📊 Space Efficiency: {total_room_area:.0f} sqft used / {solver.total_area:.0f} sqft total ({total_room_area/solver.total_area*100:.0f}%)")
        
        # Show all solutions scores
        print(f"\n📈 All Solutions Scores:")
        for i, sol in enumerate(solutions):
            print(f"   Solution {i+1}: {sol.score:.1f}")
    else:
        print("❌ No solutions found")