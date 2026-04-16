"""
Solver Suite - Base classes and basic solvers for room layout generation

Provides multiple algorithms for generating room layouts from spatial graphs:
- Grid: Simple grid-based placement
- Wave Collapse: Constraint-based WFC algorithm
- Tree: Recursive subdivision
- Perfect Adjacency: Optimizes for adjacency requirements
- Constraint: CSP-based solving
- Hybrid: Combines multiple approaches
"""
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
import math
import random
import time

from room_relationships import (
    SpatialGraph, RoomNode, PlacedRoom, PlacedLayout,
    Rect, Point, Zone
)


class SolverType(Enum):
    """Available solver algorithms."""
    GRID = "grid"
    WAVE_COLLAPSE = "wave_collapse"
    TREE = "tree"
    PERFECT_ADJACENCY = "perfect_adjacency"
    CONSTRAINT = "constraint"
    NORMALIZED_CONSTRAINT = "normalized_constraint"
    HYBRID = "hybrid"
    GENETIC = "genetic"
    ANNEALING = "annealing"
    FORCE_DIRECTED = "force_directed"
    SPACE_COLONIZATION = "space_colonization"


@dataclass
class SolverMetadata:
    """Metadata describing a solver algorithm."""
    name: str
    description: str
    speed: str  # 'fast', 'medium', 'slow'
    reliability: str  # 'high', 'medium', 'low'
    best_for: List[str]
    characteristics: Dict[str, str] = field(default_factory=dict)


# Solver metadata registry
SOLVER_INFO = {
    SolverType.GRID: SolverMetadata(
        name="Grid Solver",
        description="Simple grid-based placement with left-to-right, top-to-bottom ordering",
        speed="fast",
        reliability="high",
        best_for=["Quick layouts", "Rectangular buildings", "Regular grids"],
        characteristics={
            "Deterministic": "Yes - same result every time",
            "Adjacency": "Respects strong preferences only",
            "Efficiency": "Fast but may waste space",
        }
    ),
    SolverType.WAVE_COLLAPSE: SolverMetadata(
        name="Wave Function Collapse",
        description="Constraint-based solver using WFC algorithm",
        speed="medium",
        reliability="medium",
        best_for=["Complex constraints", "Organic layouts", "Mixed room sizes"],
        characteristics={
            "Deterministic": "No - random seed affects result",
            "Adjacency": "Strong constraint satisfaction",
            "Efficiency": "Good space utilization",
        }
    ),
    SolverType.TREE: SolverMetadata(
        name="Tree Subdivision",
        description="Recursive space subdivision like a BSP tree",
        speed="fast",
        reliability="high",
        best_for=["Hierarchical layouts", "Architectural plans", "Zone separation"],
        characteristics={
            "Deterministic": "Yes with same input",
            "Adjacency": "Creates natural adjacencies",
            "Efficiency": "Very efficient space use",
        }
    ),
    SolverType.PERFECT_ADJACENCY: SolverMetadata(
        name="Perfect Adjacency",
        description="Optimizes primarily for adjacency satisfaction",
        speed="slow",
        reliability="medium",
        best_for=["Adjacency-heavy requirements", "Social graphs", "Access patterns"],
        characteristics={
            "Deterministic": "No - uses randomization",
            "Adjacency": "Maximum adjacency satisfaction",
            "Efficiency": "May sacrifice space efficiency",
        }
    ),
    SolverType.CONSTRAINT: SolverMetadata(
        name="Constraint Solver",
        description="CSP-based solver with backtracking",
        speed="slow",
        reliability="high",
        best_for=["Hard constraints", "Small buildings", "Exact requirements"],
        characteristics={
            "Deterministic": "Yes - exhaustive search",
            "Adjacency": "All constraints satisfied or fails",
            "Efficiency": "May be slow for large problems",
        }
    ),
    SolverType.HYBRID: SolverMetadata(
        name="Hybrid Solver",
        description="Combines multiple algorithms for best results",
        speed="slow",
        reliability="high",
        best_for=["Production use", "Unknown requirements", "Best quality"],
        characteristics={
            "Deterministic": "No - runs multiple strategies",
            "Adjacency": "Optimizes across all metrics",
            "Efficiency": "Best overall results",
        }
    ),
    SolverType.GENETIC: SolverMetadata(
        name="Genetic Algorithm",
        description="Evolutionary optimization with crossover and mutation",
        speed="slow",
        reliability="medium",
        best_for=["Global optimization", "Escaping local minima", "Complex fitness"],
        characteristics={
            "Deterministic": "No - evolutionary process",
            "Adjacency": "Evolves toward good solutions",
            "Efficiency": "Good with sufficient generations",
        }
    ),
    SolverType.ANNEALING: SolverMetadata(
        name="Simulated Annealing",
        description="Thermodynamic-inspired optimization with cooling schedule",
        speed="medium",
        reliability="medium",
        best_for=["Local optimization", "Refinement", "Avoiding local minima"],
        characteristics={
            "Deterministic": "No - probabilistic",
            "Adjacency": "Improves over time",
            "Efficiency": "Can produce tight layouts",
        }
    ),
    SolverType.FORCE_DIRECTED: SolverMetadata(
        name="Force-Directed",
        description="Physics simulation with spring and repulsion forces",
        speed="medium",
        reliability="low",
        best_for=["Organic layouts", "Clustering", "Visual appeal"],
        characteristics={
            "Deterministic": "No - physics simulation",
            "Adjacency": "Springs pull adjacent rooms together",
            "Efficiency": "Variable - may need tuning",
        }
    ),
    SolverType.SPACE_COLONIZATION: SolverMetadata(
        name="Space Colonization",
        description="Growth-based organic layout algorithm",
        speed="slow",
        reliability="low",
        best_for=["Organic forms", "Natural layouts", "Experimental"],
        characteristics={
            "Deterministic": "No - growth process",
            "Adjacency": "Emergent from growth",
            "Efficiency": "Can create unique layouts",
        }
    ),
}


class BaseSolver(ABC):
    """Abstract base class for all solvers."""

    def __init__(self, graph: SpatialGraph, width: float, depth: float, grid_size: float = 2.0):
        self.graph = graph
        self.width = width
        self.depth = depth
        self.grid_size = grid_size
        self._start_time = 0.0
        self.iterations = 0

    @property
    @abstractmethod
    def solver_type(self) -> SolverType:
        """Return the solver type enum value."""
        pass

    @abstractmethod
    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Execute the solver and return a layout."""
        pass

    def _start_timer(self):
        """Start timing the solve operation."""
        self._start_time = time.time()

    def _elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (time.time() - self._start_time) * 1000

    def _elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self._start_time

    def _create_layout(self) -> PlacedLayout:
        """Create a new empty layout with timer set."""
        layout = PlacedLayout()
        layout.solve_time_ms = self._elapsed_ms()
        return layout

    def score_layout(self, layout: PlacedLayout) -> float:
        """
        Calculate overall score for a layout.
        Returns value 0.0-1.0.
        """
        if not layout.rooms:
            return 0.0

        # Adjacency score
        adj_score = self.graph.get_adjacency_score(layout)

        # Area score
        area_score = self.graph.get_area_score(layout)

        # Overlap penalty
        overlap_penalty = len(layout.get_overlaps()) * 0.2

        # Coverage score (prefer good space utilization)
        coverage = layout.coverage(self.width, self.depth)
        coverage_score = 1.0 - abs(coverage - 0.75)  # Optimal around 75% coverage

        # Combine scores
        total = (
            adj_score * 0.35 +
            area_score * 0.30 +
            coverage_score * 0.20 +
            max(0.0, 1.0 - overlap_penalty) * 0.15
        )

        return max(0.0, min(1.0, total))

    def snap_to_grid(self, value: float) -> float:
        """Snap a coordinate to the grid."""
        return round(value / self.grid_size) * self.grid_size


# =============================================================================
# GRID SOLVER
# =============================================================================

class GridSolver(BaseSolver):
    """
    Simple grid-based solver.
    Places rooms left-to-right, top-to-bottom in a grid.
    Includes overlap detection and resolution.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.GRID

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Generate grid-based layout with no overlaps."""
        self._start_timer()
        layout = PlacedLayout()

        cols = int(math.ceil(math.sqrt(len(self.graph.rooms))))
        col_width = self.width / cols

        x, y = 0.0, 0.0
        row_height = 0.0
        col = 0

        placed_rects = []  # Track placed rectangles for overlap checking

        for room_id, room_node in self.graph.rooms.items():
            # Calculate dimensions
            area = room_node.target_area
            width = max(room_node.min_width, math.sqrt(area))
            depth = area / width

            # Snap to grid
            width = self.snap_to_grid(width)
            depth = self.snap_to_grid(depth)

            # Check bounds
            if x + width > self.width:
                x = 0.0
                y += row_height
                row_height = 0.0
                col = 0

            if y + depth > self.depth:
                # Scale down to fit
                scale = (self.depth - y) / depth if y < self.depth else 0.5
                width *= scale
                depth *= scale

            # Find non-overlapping position
            rect = self._find_non_overlapping_position(
                x, y, width, depth, row_height, placed_rects
            )

            placed = PlacedRoom(room_node, rect)
            layout.add_room(placed)
            placed_rects.append(rect)

            # Update position for next room
            x = rect.x + rect.width
            row_height = max(row_height, rect.height)
            col += 1

        # Final overlap cleanup pass
        self._resolve_overlaps(layout)

        layout.iterations = len(self.graph.rooms)
        layout.solve_time_ms = self._elapsed_ms()
        layout.score = self.score_layout(layout)
        layout.is_complete = len(layout.rooms) == len(self.graph.rooms)

        return layout

    def _find_non_overlapping_position(self, x, y, width, depth, row_height, placed_rects):
        """Find a position that doesn't overlap with existing rooms."""
        rect = Rect(x, y, width, depth)

        # Check for overlaps and adjust position if needed
        max_attempts = 100
        for _ in range(max_attempts):
            overlap_found = False
            for placed in placed_rects:
                if rect.intersects(placed):
                    overlap_found = True
                    # Move to the right of the overlapping room
                    rect.x = placed.x + placed.width
                    # Check if we need to wrap to next row
                    if rect.x + rect.width > self.width:
                        rect.x = 0.0
                        rect.y = max(rect.y + row_height, placed.y + placed.height)
                    break

            if not overlap_found:
                break

        return rect

    def _resolve_overlaps(self, layout: PlacedLayout):
        """Resolve any remaining overlaps by pushing rooms apart."""
        for _ in range(100):
            overlaps_found = False
            rooms = list(layout.rooms.values())

            for i, r1 in enumerate(rooms):
                for r2 in rooms[i+1:]:
                    if r1.rect.intersects(r2.rect):
                        overlaps_found = True
                        # Calculate separation vector
                        dx = r1.rect.center.x - r2.rect.center.x
                        dy = r1.rect.center.y - r2.rect.center.y
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001

                        # Minimum separation
                        sep = 0.5
                        sep_x = (dx / dist) * sep
                        sep_y = (dy / dist) * sep

                        # Move rooms apart
                        r1.rect.x = max(0, min(r1.rect.x + sep_x, self.width - r1.rect.width))
                        r1.rect.y = max(0, min(r1.rect.y + sep_y, self.depth - r1.rect.height))
                        r2.rect.x = max(0, min(r2.rect.x - sep_x, self.width - r2.rect.width))
                        r2.rect.y = max(0, min(r2.rect.y - sep_y, self.depth - r2.rect.height))

            if not overlaps_found:
                break


class GridSolverWrapper(GridSolver):
    """Wrapper for consistency with naming."""
    pass


# =============================================================================
# WAVE COLLAPSE SOLVER
# =============================================================================

class WaveCollapseSolver(BaseSolver):
    """
    Wave Function Collapse solver.
    Uses constraint propagation to place rooms.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.WAVE_COLLAPSE

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Generate layout using WFC algorithm."""
        self._start_timer()
        layout = PlacedLayout()

        # Sort rooms by constraint level (most constrained first)
        rooms_to_place = sorted(
            self.graph.rooms.values(),
            key=lambda r: len(self.graph.get_neighbors(r.id)),
            reverse=True
        )

        occupied = []

        for room_node in rooms_to_place:
            best_rect = self._find_best_position(room_node, occupied)

            if best_rect:
                placed = PlacedRoom(room_node, best_rect)
                layout.add_room(placed)
                occupied.append(best_rect)

            self.iterations += 1
            if self.iterations >= max_iterations:
                break

        layout.iterations = self.iterations
        layout.solve_time_ms = self._elapsed_ms()
        layout.score = self.score_layout(layout)
        layout.is_complete = len(layout.rooms) == len(self.graph.rooms)

        return layout

    def _find_best_position(self, room: RoomNode, occupied: List[Rect]) -> Optional[Rect]:
        """Find best position for a room using WFC-style selection."""
        area = room.target_area
        width = max(room.min_width, math.sqrt(area))
        depth = room.target_area / width

        width = self.snap_to_grid(width)
        depth = self.snap_to_grid(depth)

        # Generate candidate positions
        candidates = []

        # Grid-based candidates
        for gx in range(0, int(self.width - width), int(self.grid_size * 2)):
            for gy in range(0, int(self.depth - depth), int(self.grid_size * 2)):
                rect = Rect(float(gx), float(gy), width, depth)

                # Check overlap
                if any(rect.intersects(o) for o in occupied):
                    continue

                # Score this position
                score = self._score_position(room, rect, occupied)
                candidates.append((rect, score))

        if not candidates:
            return None

        # Select from best candidates (WFC-style)
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:max(1, len(candidates) // 4)]
        return random.choice(top_candidates)[0]

    def _score_position(self, room: RoomNode, rect: Rect, occupied: List[Rect]) -> float:
        """Score a potential position."""
        score = 1.0

        # Prefer positions near preferred neighbors
        for neighbor_id, weight in room.adjacency_preferences.items():
            # Find if neighbor is already placed
            for o in occupied:
                # Simple proximity check
                dist = rect.distance_to(o)
                if dist < 1.0:
                    score += weight

        # Penalize positions far from center
        cx, cy = rect.center.x, rect.center.y
        center_dist = math.sqrt((cx - self.width/2)**2 + (cy - self.depth/2)**2)
        score -= center_dist / self.width * 0.1

        return score


# =============================================================================
# TREE SOLVER
# =============================================================================

class TreeSolver(BaseSolver):
    """
    Recursive subdivision solver.
    Divides space like a BSP tree.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.TREE

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Generate layout using recursive subdivision with backtracking."""
        self._start_timer()
        layout = PlacedLayout()

        rooms = list(self.graph.rooms.values())
        if not rooms:
            return layout

        # Sort by zone (public first, then private, etc)
        zone_order = {Zone.PUBLIC: 0, Zone.CIRCULATION: 1, Zone.SERVICE: 2, Zone.PRIVATE: 3}
        rooms.sort(key=lambda r: zone_order.get(r.zone, 4))

        # Try multiple starting configurations
        best_layout = PlacedLayout()

        for _ in range(5):  # Multiple attempts with slight variations
            layout = PlacedLayout()
            bounds = Rect(0, 0, self.width, self.depth)

            # Shuffle slightly to get different results
            random.shuffle(rooms[:min(3, len(rooms))])

            success = self._subdivide(layout, rooms, bounds, 0)

            if len(layout.rooms) > len(best_layout.rooms):
                best_layout = layout

            if len(best_layout.rooms) == len(rooms):
                break  # All rooms placed

        best_layout.iterations = self.iterations
        best_layout.solve_time_ms = self._elapsed_ms()
        best_layout.score = self.score_layout(best_layout)
        best_layout.is_complete = len(best_layout.rooms) == len(self.graph.rooms)

        return best_layout

    def _subdivide(self, layout: PlacedLayout, rooms: List[RoomNode],
                   bounds: Rect, depth: int):
        """Recursively subdivide space with backtracking support."""
        if not rooms:
            return True  # All rooms placed successfully

        if depth > 50:  # Increased depth limit
            return False

        room = rooms[0]
        remaining = rooms[1:]

        # Calculate room dimensions with bounds checking
        area = min(room.target_area, bounds.width * bounds.height * 0.9)
        area = max(area, room.min_area)

        aspect = room.preferred_aspect_ratio

        # Try both orientations
        orientations = []

        # Horizontal orientation
        room_width = min(bounds.width * 0.7, max(room.min_width, math.sqrt(area * aspect)))
        room_depth = area / room_width if room_width > 0 else 0
        if room_depth > 0 and room_depth <= bounds.height and room_depth >= room.min_depth:
            orientations.append((room_width, room_depth, 'h'))

        # Vertical orientation
        room_depth2 = min(bounds.height * 0.7, max(room.min_depth, math.sqrt(area / aspect)))
        room_width2 = area / room_depth2 if room_depth2 > 0 else 0
        if room_width2 > 0 and room_width2 <= bounds.width and room_width2 >= room.min_width:
            orientations.append((room_width2, room_depth2, 'v'))

        # Try square-ish if both failed
        if not orientations:
            side = min(bounds.width, bounds.height, math.sqrt(area))
            if side >= room.min_width and side >= room.min_depth:
                orientations.append((side, side, 's'))

        # Try each orientation
        for rw, rd, orient in orientations:
            rw = self.snap_to_grid(rw)
            rd = self.snap_to_grid(rd)

            # Ensure minimums
            rw = max(rw, room.min_width)
            rd = max(rd, room.min_depth)

            # Try multiple positions within bounds
            positions = [
                (bounds.x, bounds.y),  # Corner
                (bounds.x, bounds.y + bounds.height - rd),  # Bottom-left
                (bounds.x + bounds.width - rw, bounds.y),  # Top-right
            ]

            for px, py in positions:
                if px + rw > bounds.x + bounds.width or py + rd > bounds.y + bounds.height:
                    continue

                rect = Rect(px, py, rw, rd)
                placed = PlacedRoom(room, rect)
                layout.add_room(placed)

                # Calculate remaining spaces (L-shaped division)
                success = False

                # Try horizontal remaining space
                if bounds.width - rw > 1.0:
                    new_bounds_h = Rect(
                        px + rw, bounds.y,
                        bounds.x + bounds.width - px - rw, bounds.height
                    )
                    if self._subdivide(layout, remaining, new_bounds_h, depth + 1):
                        success = True

                # Try vertical remaining space
                if not success and bounds.height - rd > 1.0:
                    new_bounds_v = Rect(
                        bounds.x, py + rd,
                        bounds.width, bounds.y + bounds.height - py - rd
                    )
                    if self._subdivide(layout, remaining, new_bounds_v, depth + 1):
                        success = True

                if success:
                    return True

                # Backtrack
                del layout.rooms[room.id]

        self.iterations += 1
        return False


# =============================================================================
# PERFECT ADJACENCY SOLVER
# =============================================================================

class PerfectAdjacencySolver(BaseSolver):
    """
    Solver optimized for adjacency satisfaction.
    Uses force-directed-like approach with adjacency springs.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.PERFECT_ADJACENCY

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Generate layout optimizing for adjacency."""
        self._start_timer()
        layout = PlacedLayout()

        # Start with random valid positions
        for room_id, room_node in self.graph.rooms.items():
            rect = self._random_position(room_node)
            placed = PlacedRoom(room_node, rect)
            layout.add_room(placed)

        # Iterative improvement
        for i in range(min(max_iterations, 1000)):
            improved = self._improve_step(layout)
            self.iterations += 1
            if not improved:
                break

        # Final overlap cleanup
        self._final_cleanup(layout)

        layout.iterations = self.iterations
        layout.solve_time_ms = self._elapsed_ms()
        layout.score = self.score_layout(layout)
        layout.is_complete = len(layout.rooms) == len(self.graph.rooms)

        return layout

    def _final_cleanup(self, layout: PlacedLayout):
        """Resolve any remaining overlaps after main solving."""
        for iteration in range(200):
            overlaps_found = False
            max_overlap_depth = 0
            room_list = list(layout.rooms.values())
            for i, r1 in enumerate(room_list):
                for r2 in room_list[i+1:]:
                    if r1.rect.intersects(r2.rect):
                        overlaps_found = True
                        # Calculate overlap amount
                        overlap_left = max(r1.rect.x, r2.rect.x)
                        overlap_right = min(r1.rect.x2, r2.rect.x2)
                        overlap_top = max(r1.rect.y, r2.rect.y)
                        overlap_bottom = min(r1.rect.y2, r2.rect.y2)
                        overlap_width = overlap_right - overlap_left
                        overlap_height = overlap_bottom - overlap_top
                        overlap_area = overlap_width * overlap_height
                        max_overlap_depth = max(max_overlap_depth, overlap_area)

                        dx = r1.rect.center.x - r2.rect.center.x
                        dy = r1.rect.center.y - r2.rect.center.y
                        dist = math.sqrt(dx*dx + dy*dy) + 0.001

                        # Stronger separation for deeper overlaps
                        sep_amount = 0.5 + min(overlap_width, overlap_height) * 0.5
                        sep_x = (dx / dist) * sep_amount
                        sep_y = (dy / dist) * sep_amount

                        r1.rect.x = max(0, min(r1.rect.x + sep_x, self.width - r1.rect.width))
                        r1.rect.y = max(0, min(r1.rect.y + sep_y, self.depth - r1.rect.height))
                        r2.rect.x = max(0, min(r2.rect.x - sep_x, self.width - r2.rect.width))
                        r2.rect.y = max(0, min(r2.rect.y - sep_y, self.depth - r2.rect.height))

            if not overlaps_found:
                break

    def _random_position(self, room: RoomNode) -> Rect:
        """Generate a random valid position."""
        area = room.target_area
        width = max(room.min_width, math.sqrt(area))
        depth = area / width

        x = random.uniform(0, max(0, self.width - width))
        y = random.uniform(0, max(0, self.depth - depth))

        return Rect(x, y, width, depth)

    def _improve_step(self, layout: PlacedLayout) -> bool:
        """Perform one improvement step. Returns True if improved."""
        improved = False

        # First pass: resolve overlaps
        for room_id, placed in layout.rooms.items():
            for other_id, other in layout.rooms.items():
                if room_id >= other_id:
                    continue

                if placed.rect.intersects(other.rect):
                    # Calculate separation vector
                    dx = placed.rect.center.x - other.rect.center.x
                    dy = placed.rect.center.y - other.rect.center.y
                    dist = math.sqrt(dx*dx + dy*dy) + 0.001

                    # Minimum separation needed
                    min_sep = 0.5
                    sep_x = (dx / dist) * min_sep
                    sep_y = (dy / dist) * min_sep

                    # Move both rooms apart
                    new_x1 = max(0, min(placed.rect.x + sep_x, self.width - placed.rect.width))
                    new_y1 = max(0, min(placed.rect.y + sep_y, self.depth - placed.rect.height))
                    new_x2 = max(0, min(other.rect.x - sep_x, self.width - other.rect.width))
                    new_y2 = max(0, min(other.rect.y - sep_y, self.depth - other.rect.height))

                    if abs(sep_x) > 0.01 or abs(sep_y) > 0.01:
                        placed.rect.x = new_x1
                        placed.rect.y = new_y1
                        other.rect.x = new_x2
                        other.rect.y = new_y2
                        improved = True

        # Second pass: adjacency attraction
        for room_id, placed in layout.rooms.items():
            neighbors = self.graph.get_neighbors(room_id)
            if not neighbors:
                continue

            tx, ty = 0.0, 0.0
            count = 0

            for neighbor_id in neighbors:
                neighbor = layout.rooms.get(neighbor_id)
                if neighbor:
                    tx += neighbor.rect.center.x
                    ty += neighbor.rect.center.y
                    count += 1

            if count > 0:
                tx /= count
                ty /= count

                cx, cy = placed.rect.center.x, placed.rect.center.y
                dx = (tx - cx) * 0.05
                dy = (ty - cy) * 0.05

                new_x = self.snap_to_grid(placed.rect.x + dx)
                new_y = self.snap_to_grid(placed.rect.y + dy)

                new_x = max(0, min(new_x, self.width - placed.rect.width))
                new_y = max(0, min(new_y, self.depth - placed.rect.height))

                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    placed.rect.x = new_x
                    placed.rect.y = new_y
                    improved = True

        return improved


# =============================================================================
# CONSTRAINT SOLVER
# =============================================================================

class ConstraintSolver(BaseSolver):
    """
    CSP-based solver with backtracking.
    For small problems, guarantees constraint satisfaction.
    Includes timeout to prevent hanging on large problems.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.CONSTRAINT

    def solve(self, max_iterations: int = 10000, timeout_ms: float = 5000) -> PlacedLayout:
        """Solve using backtracking CSP with timeout.

        Args:
            max_iterations: Maximum backtracking iterations
            timeout_ms: Maximum time in milliseconds (default 5 seconds)
        """
        import time
        self._start_timer()
        self._start_time = time.time()
        self._timeout_sec = timeout_ms / 1000.0
        layout = PlacedLayout()

        rooms = list(self.graph.rooms.values())

        # Limit candidates for large problems to prevent explosion
        max_candidates = 20 if len(rooms) > 10 else 50

        # Try to place all rooms with backtracking
        success = self._backtrack(layout, rooms, [], 0, max_iterations, max_candidates)

        layout.iterations = self.iterations
        layout.solve_time_ms = self._elapsed_ms()
        layout.score = self.score_layout(layout)
        layout.is_complete = success

        return layout

    def _backtrack(self, layout: PlacedLayout, rooms: List[RoomNode],
                   occupied: List[Rect], index: int, max_iter: int, max_candidates: int) -> bool:
        """Recursive backtracking placement with timeout."""
        # Check timeout
        if time.time() - self._start_time > self._timeout_sec:
            return False

        if index >= len(rooms):
            return True

        if self.iterations >= max_iter:
            return False

        self.iterations += 1
        room = rooms[index]

        # Generate candidate positions (limited)
        candidates = self._generate_candidates(room, occupied, max_candidates)

        for rect in candidates:
            # Try this position
            placed = PlacedRoom(room, rect)
            layout.add_room(placed)
            occupied.append(rect)

            # Recurse
            if self._backtrack(layout, rooms, occupied, index + 1, max_iter, max_candidates):
                return True

            # Backtrack
            del layout.rooms[room.id]
            occupied.pop()

        return False

    def _generate_candidates(self, room: RoomNode, occupied: List[Rect], max_candidates: int = 50) -> List[Rect]:
        """Generate candidate positions for a room."""
        candidates = []

        area = room.target_area
        width = max(room.min_width, math.sqrt(area))
        depth = area / width

        width = self.snap_to_grid(width)
        depth = self.snap_to_grid(depth)

        # Grid-based candidates
        step = max(width, depth, self.grid_size)

        for x in [i * step for i in range(int(self.width / step) + 1)]:
            for y in [i * step for i in range(int(self.depth / step) + 1)]:
                if x + width > self.width or y + depth > self.depth:
                    continue

                rect = Rect(x, y, width, depth)

                # Check overlap
                if any(rect.intersects(o) for o in occupied):
                    continue

                candidates.append(rect)

                # Early exit if we have enough candidates
                if len(candidates) >= max_candidates * 2:
                    break
            if len(candidates) >= max_candidates * 2:
                break

        # Sort by proximity to center
        center = Point(self.width / 2, self.depth / 2)
        candidates.sort(key=lambda r: abs(r.center.x - center.x) + abs(r.center.y - center.y))

        return candidates[:max_candidates]  # Limit candidates


# =============================================================================
# HYBRID SOLVER
# =============================================================================

class HybridSolver(BaseSolver):
    """
    Hybrid solver that combines multiple approaches.
    Runs multiple solvers and selects the best result.
    """

    @property
    def solver_type(self) -> SolverType:
        return SolverType.HYBRID

    def solve(self, max_iterations: int = 10000) -> PlacedLayout:
        """Run multiple solvers and return best result."""
        self._start_timer()

        solvers = [
            TreeSolver(self.graph, self.width, self.depth, self.grid_size),
            GridSolver(self.graph, self.width, self.depth, self.grid_size),
            WaveCollapseSolver(self.graph, self.width, self.depth, self.grid_size),
        ]

        best_layout = None
        best_score = 0.0

        iterations_per_solver = max_iterations // len(solvers)

        for solver in solvers:
            try:
                layout = solver.solve(iterations_per_solver)
                score = self.score_layout(layout)

                if score > best_score:
                    best_score = score
                    best_layout = layout
            except Exception as e:
                print(f"Solver {solver.solver_type.value} failed: {e}")

        if best_layout is None:
            # Fallback to grid
            best_layout = GridSolver(self.graph, self.width, self.depth, self.grid_size).solve()

        best_layout.solve_time_ms = self._elapsed_ms()
        return best_layout


if __name__ == "__main__":
    # Test the solvers
    print("Solver Suite Test")
    print("=================\n")

    # Create test graph
    graph = SpatialGraph()
    graph.add_room("living", "living", min_area=20, target_area=25)
    graph.add_room("kitchen", "kitchen", min_area=10, target_area=12)
    graph.add_room("bedroom", "bedroom", min_area=12, target_area=15)
    graph.add_room("bathroom", "bathroom", min_area=5, target_area=6)

    graph.connect("living", "kitchen", 2.0)
    graph.connect("living", "bedroom", 1.0)
    graph.connect("bedroom", "bathroom", 2.0)

    print(f"Graph: {len(graph.rooms)} rooms, {sum(len(n) for n in graph.adjacencies.values()) // 2} connections\n")

    # Test each solver
    for solver_type, info in SOLVER_INFO.items():
        if solver_type == SolverType.HYBRID:
            continue  # Skip hybrid for simple test

        solver_class = {
            SolverType.GRID: GridSolver,
            SolverType.WAVE_COLLAPSE: WaveCollapseSolver,
            SolverType.TREE: TreeSolver,
            SolverType.PERFECT_ADJACENCY: PerfectAdjacencySolver,
            SolverType.CONSTRAINT: ConstraintSolver,
        }.get(solver_type)

        if solver_class:
            print(f"\n{info.name}:")
            solver = solver_class(graph, 15, 12, 0.5)
            layout = solver.solve(1000)
            print(f"  Rooms: {len(layout.rooms)}, Score: {layout.score:.2f}, "
                  f"Time: {layout.solve_time_ms:.1f}ms, Overlaps: {len(layout.get_overlaps())}")
