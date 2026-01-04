"""Constraint solver for QBD Algebra.

Turns validated state into a placed layout.
Stages: Constraint Propagation → Search → Optimization → Selection
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from copy import deepcopy
import math
import random

from .state import QBDState, StateLifecycle
from .errors import (
    ValidationResult, QBDError, QBDWarning, ErrorCode, ErrorType,
    unsatisfiable_error, underdetermined_error
)
from .deriver import derive_values, apply_derived_to_state
from .validator import validate_state
from .defaults import BUILDING_DEFAULTS, m_to_mm


@dataclass
class PlacedRoom:
    """A room with solved position and dimensions."""
    id: str
    name: str
    room_type: str
    x: int  # mm, position
    z: int  # mm, position
    width: int  # mm
    length: int  # mm
    rotation: int = 0  # degrees

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Return (x_min, z_min, x_max, z_max)."""
        return (self.x, self.z, self.x + self.width, self.z + self.length)

    @property
    def area_sqm(self) -> float:
        """Return area in square meters."""
        return (self.width * self.length) / 1_000_000

    def overlaps(self, other: "PlacedRoom") -> bool:
        """Check if this room overlaps with another."""
        ax1, az1, ax2, az2 = self.bounds
        bx1, bz1, bx2, bz2 = other.bounds
        return not (ax2 <= bx1 or bx2 <= ax1 or az2 <= bz1 or bz2 <= az1)

    def shares_edge(self, other: "PlacedRoom") -> bool:
        """Check if rooms share an edge (are adjacent)."""
        ax1, az1, ax2, az2 = self.bounds
        bx1, bz1, bx2, bz2 = other.bounds

        # Check horizontal adjacency
        if ax2 == bx1 or bx2 == ax1:
            # Check vertical overlap
            if not (az2 <= bz1 or bz2 <= az1):
                return True

        # Check vertical adjacency
        if az2 == bz1 or bz2 == az1:
            # Check horizontal overlap
            if not (ax2 <= bx1 or bx2 <= ax1):
                return True

        return False


@dataclass
class SolverCandidate:
    """A candidate layout solution."""
    rooms: List[PlacedRoom]
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    satisfied_adjacencies: int = 0
    satisfied_separations: int = 0
    tradeoffs: List[str] = field(default_factory=list)


@dataclass
class SolverResult:
    """Result from the solver."""
    status: str  # "solved", "failed", "underdetermined"
    layout: Optional[Dict[str, Any]] = None
    candidates: List[SolverCandidate] = field(default_factory=list)
    errors: List[QBDError] = field(default_factory=list)
    warnings: List[QBDWarning] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status,
            "layout": self.layout,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }
        if self.candidates:
            result["candidates_count"] = len(self.candidates)
            result["best_score"] = self.candidates[0].score if self.candidates else None
        return result


class QBDSolver:
    """Constraint solver for room layouts."""

    def __init__(self, state: QBDState):
        self.state = state
        self.grid_size = 100  # mm snap grid

    def solve(self) -> SolverResult:
        """Run the solver pipeline."""

        # Stage 0: Pre-check
        if self.state.lifecycle == StateLifecycle.EMPTY:
            return SolverResult(
                status="underdetermined",
                errors=[underdetermined_error(
                    "Cannot solve empty state",
                    ["At least one room is required"]
                )]
            )

        # Run validation first
        validation = validate_state(self.state)
        if not validation.valid:
            return SolverResult(
                status="failed",
                errors=validation.errors,
                warnings=validation.warnings
            )

        # Run derivation
        derived = derive_values(self.state)
        apply_derived_to_state(self.state, derived)

        # Check if complete enough to solve
        if not self._is_solvable():
            return SolverResult(
                status="underdetermined",
                errors=[underdetermined_error(
                    "Not enough information to solve",
                    self._get_missing_info()
                )]
            )

        # Stage 1: Constraint propagation
        constraints = self._propagate_constraints()

        # Stage 2: Search for candidates
        candidates = self._search(constraints)

        if not candidates:
            return SolverResult(
                status="failed",
                errors=[QBDError(
                    code=ErrorCode.SOLVER_FAILED,
                    error_type=ErrorType.FEASIBILITY,
                    message="Could not find valid layout"
                )]
            )

        # Stage 3: Optimization (score candidates)
        for candidate in candidates:
            self._score_candidate(candidate)

        # Sort by score
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Stage 4: Selection
        best = candidates[0]
        layout = self._candidate_to_layout(best)

        # Store in state
        self.state._solved_layout = layout
        self.state._lifecycle = StateLifecycle.SOLVED

        return SolverResult(
            status="solved",
            layout=layout,
            candidates=candidates[:3],  # Return top 3
            warnings=validation.warnings
        )

    def _is_solvable(self) -> bool:
        """Check if state has enough info to solve."""
        rooms = self.state.rooms
        if not rooms:
            return False

        # Need at least some size info
        has_size_info = False
        for room in rooms:
            if room.get("area_min") or room.get("width_min"):
                has_size_info = True
                break

        if not has_size_info:
            return False

        # Need footprint or site dimensions
        constraints = self.state.constraints
        site = self.state.site

        has_bounds = (
            constraints.get("footprint_max") is not None or
            (site.get("width") is not None and site.get("depth") is not None)
        )

        return has_bounds

    def _get_missing_info(self) -> List[str]:
        """Get list of missing information."""
        missing = []

        if not self.state.rooms:
            missing.append("No rooms defined")

        rooms_without_size = [
            r.get("name") for r in self.state.rooms
            if not r.get("area_min") and not r.get("furniture")
        ]
        if rooms_without_size:
            missing.append(f"Room sizes needed for: {', '.join(rooms_without_size[:3])}")

        if (self.state.constraints.get("footprint_max") is None and
            self.state.site.get("width") is None):
            missing.append("Footprint limit or site dimensions needed")

        return missing

    # =========================================================================
    # Stage 1: Constraint Propagation
    # =========================================================================

    def _propagate_constraints(self) -> Dict[str, Any]:
        """Propagate constraints to reduce search space."""
        constraints = {
            "room_domains": {},  # room_id -> possible positions/sizes
            "must_adjacent": [],  # pairs that must share edge
            "must_separate": [],  # pairs that must not share edge
        }

        # Get required adjacencies
        for adj in self.state.adjacencies:
            if adj.get("strength") == "required":
                constraints["must_adjacent"].append(
                    (adj.get("room_a"), adj.get("room_b"))
                )

        # Get required separations
        for sep in self.state.separations:
            if sep.get("strength") == "required":
                constraints["must_separate"].append(
                    (sep.get("room_a"), sep.get("room_b"))
                )

        return constraints

    # =========================================================================
    # Stage 2: Search
    # =========================================================================

    def _search(self, constraints: Dict[str, Any]) -> List[SolverCandidate]:
        """Search for valid layout candidates."""
        candidates = []

        # Get target footprint
        footprint_max = self.state.constraints.get("footprint_max")
        site = self.state.site

        if site.get("width") and site.get("depth"):
            setbacks = site.get("setbacks", {})
            max_width = site["width"] - (setbacks.get("left", 0) + setbacks.get("right", 0))
            max_depth = site["depth"] - (setbacks.get("front", 0) + setbacks.get("rear", 0))
        elif footprint_max:
            # Assume roughly square
            side = int(math.sqrt(footprint_max * 1_000_000))
            max_width = side
            max_depth = side
        else:
            max_width = 20000  # 20m default
            max_depth = 20000

        # Try multiple layout strategies
        strategies = [
            self._strategy_linear,
            self._strategy_l_shape,
            self._strategy_grid,
        ]

        for strategy in strategies:
            candidate = strategy(max_width, max_depth, constraints)
            if candidate and self._validate_candidate(candidate, constraints):
                candidates.append(candidate)

        return candidates

    def _strategy_linear(
        self,
        max_width: int,
        max_depth: int,
        constraints: Dict
    ) -> Optional[SolverCandidate]:
        """Linear layout strategy - rooms in a row."""
        placed = []
        x = 0

        for room in self.state.rooms:
            width = room.get("width_min") or int(m_to_mm(math.sqrt(room.get("area_min", 12))))
            length = room.get("length_min") or width

            # Snap to grid
            width = (width // self.grid_size) * self.grid_size
            length = (length // self.grid_size) * self.grid_size

            placed.append(PlacedRoom(
                id=room.get("id"),
                name=room.get("name"),
                room_type=room.get("type"),
                x=x,
                z=0,
                width=max(width, 2400),
                length=max(length, 2400),
            ))
            x += width

        if x > max_width:
            return None  # Doesn't fit

        return SolverCandidate(rooms=placed)

    def _strategy_l_shape(
        self,
        max_width: int,
        max_depth: int,
        constraints: Dict
    ) -> Optional[SolverCandidate]:
        """L-shape layout strategy."""
        rooms = self.state.rooms
        if len(rooms) < 3:
            return self._strategy_linear(max_width, max_depth, constraints)

        placed = []

        # Split rooms into two wings
        mid = len(rooms) // 2 + 1
        wing1 = rooms[:mid]
        wing2 = rooms[mid:]

        # Place wing 1 horizontally
        x = 0
        for room in wing1:
            width = room.get("width_min") or int(m_to_mm(math.sqrt(room.get("area_min", 12))))
            length = room.get("length_min") or width
            width = max((width // self.grid_size) * self.grid_size, 2400)
            length = max((length // self.grid_size) * self.grid_size, 2400)

            placed.append(PlacedRoom(
                id=room.get("id"),
                name=room.get("name"),
                room_type=room.get("type"),
                x=x,
                z=0,
                width=width,
                length=length,
            ))
            x += width

        # Place wing 2 vertically from the end
        if placed:
            start_x = placed[-1].x
            z = placed[-1].length

            for room in wing2:
                width = room.get("width_min") or int(m_to_mm(math.sqrt(room.get("area_min", 12))))
                length = room.get("length_min") or width
                width = max((width // self.grid_size) * self.grid_size, 2400)
                length = max((length // self.grid_size) * self.grid_size, 2400)

                placed.append(PlacedRoom(
                    id=room.get("id"),
                    name=room.get("name"),
                    room_type=room.get("type"),
                    x=start_x,
                    z=z,
                    width=width,
                    length=length,
                ))
                z += length

        return SolverCandidate(rooms=placed)

    def _strategy_grid(
        self,
        max_width: int,
        max_depth: int,
        constraints: Dict
    ) -> Optional[SolverCandidate]:
        """Grid layout strategy - 2 columns."""
        rooms = self.state.rooms
        if len(rooms) < 4:
            return self._strategy_linear(max_width, max_depth, constraints)

        placed = []

        # Calculate column width
        col_width = max_width // 2

        # Place rooms in 2 columns
        z_left = 0
        z_right = 0

        for i, room in enumerate(rooms):
            width = room.get("width_min") or int(m_to_mm(math.sqrt(room.get("area_min", 12))))
            length = room.get("length_min") or width
            width = min(max((width // self.grid_size) * self.grid_size, 2400), col_width)
            length = max((length // self.grid_size) * self.grid_size, 2400)

            if i % 2 == 0:  # Left column
                placed.append(PlacedRoom(
                    id=room.get("id"),
                    name=room.get("name"),
                    room_type=room.get("type"),
                    x=0,
                    z=z_left,
                    width=col_width,
                    length=length,
                ))
                z_left += length
            else:  # Right column
                placed.append(PlacedRoom(
                    id=room.get("id"),
                    name=room.get("name"),
                    room_type=room.get("type"),
                    x=col_width,
                    z=z_right,
                    width=col_width,
                    length=length,
                ))
                z_right += length

        return SolverCandidate(rooms=placed)

    def _validate_candidate(
        self,
        candidate: SolverCandidate,
        constraints: Dict
    ) -> bool:
        """Validate a candidate against constraints."""
        rooms = candidate.rooms

        # Check no overlaps
        for i, room_a in enumerate(rooms):
            for room_b in rooms[i+1:]:
                if room_a.overlaps(room_b):
                    return False

        # Check required adjacencies
        for room_a_id, room_b_id in constraints.get("must_adjacent", []):
            room_a = next((r for r in rooms if r.id == room_a_id), None)
            room_b = next((r for r in rooms if r.id == room_b_id), None)
            if room_a and room_b:
                if room_a.shares_edge(room_b):
                    candidate.satisfied_adjacencies += 1

        # Check required separations
        for room_a_id, room_b_id in constraints.get("must_separate", []):
            room_a = next((r for r in rooms if r.id == room_a_id), None)
            room_b = next((r for r in rooms if r.id == room_b_id), None)
            if room_a and room_b:
                if not room_a.shares_edge(room_b):
                    candidate.satisfied_separations += 1

        return True

    # =========================================================================
    # Stage 3: Optimization
    # =========================================================================

    def _score_candidate(self, candidate: SolverCandidate):
        """Score a candidate layout."""
        priorities = self.state.priorities
        scores = {}

        # Adjacency satisfaction
        total_adj = len(self.state.adjacencies)
        if total_adj > 0:
            scores["adjacencies"] = candidate.satisfied_adjacencies / total_adj
        else:
            scores["adjacencies"] = 1.0

        # Separation satisfaction
        total_sep = len(self.state.separations)
        if total_sep > 0:
            scores["separations"] = candidate.satisfied_separations / total_sep
        else:
            scores["separations"] = 1.0

        # Compactness (minimize total footprint)
        footprint = self._calculate_footprint(candidate)
        footprint_max = self.state.constraints.get("footprint_max")
        if footprint_max:
            scores["compactness"] = max(0, 1 - (footprint - footprint_max * 0.8) / (footprint_max * 0.2))
        else:
            scores["compactness"] = 0.5

        # Natural light (placeholder - would need orientation data)
        scores["natural_light"] = 0.7

        # Privacy (bedrooms away from entry)
        scores["privacy"] = self._score_privacy(candidate)

        # Calculate weighted total
        weights = {
            "adjacencies": 2.0,  # High priority
            "separations": 2.0,
            "compactness": priorities.get("compact_footprint", 5) / 10,
            "natural_light": priorities.get("natural_light", 5) / 10,
            "privacy": priorities.get("privacy", 5) / 10,
        }

        total = sum(scores[k] * weights.get(k, 1.0) for k in scores)
        max_possible = sum(weights.values())

        candidate.score = (total / max_possible) * 10  # Scale to 0-10
        candidate.score_breakdown = scores

    def _calculate_footprint(self, candidate: SolverCandidate) -> float:
        """Calculate total footprint in m²."""
        if not candidate.rooms:
            return 0

        x_max = max(r.x + r.width for r in candidate.rooms)
        z_max = max(r.z + r.length for r in candidate.rooms)

        return (x_max * z_max) / 1_000_000

    def _score_privacy(self, candidate: SolverCandidate) -> float:
        """Score privacy (bedrooms away from entry)."""
        entry = next((r for r in candidate.rooms if r.room_type == "entry"), None)
        if not entry:
            return 0.5

        bedrooms = [r for r in candidate.rooms if "bedroom" in r.room_type]
        if not bedrooms:
            return 1.0

        # Calculate average distance from entry
        total_dist = 0
        for bedroom in bedrooms:
            dx = (bedroom.x + bedroom.width/2) - (entry.x + entry.width/2)
            dz = (bedroom.z + bedroom.length/2) - (entry.z + entry.length/2)
            dist = math.sqrt(dx*dx + dz*dz)
            total_dist += dist

        avg_dist = total_dist / len(bedrooms)

        # Normalize (assume 10m is good separation)
        return min(1.0, avg_dist / 10000)

    # =========================================================================
    # Stage 4: Output
    # =========================================================================

    def _candidate_to_layout(self, candidate: SolverCandidate) -> Dict[str, Any]:
        """Convert candidate to layout dictionary."""
        rooms = []
        for placed in candidate.rooms:
            rooms.append({
                "id": placed.id,
                "position": {"x": placed.x, "z": placed.z},
                "dimensions": {"width": placed.width, "length": placed.length},
                "rotation": placed.rotation,
            })

        # Calculate building footprint
        x_max = max(r.x + r.width for r in candidate.rooms) if candidate.rooms else 0
        z_max = max(r.z + r.length for r in candidate.rooms) if candidate.rooms else 0

        return {
            "status": "solved",
            "rooms": rooms,
            "building_footprint": {
                "width": x_max,
                "depth": z_max,
                "area": (x_max * z_max) / 1_000_000,
            },
            "walls": [],  # Would be generated from room positions
            "doors": [],
            "windows": [],
            "circulation": [],
            "score": round(candidate.score, 2),
            "score_breakdown": {k: round(v, 2) for k, v in candidate.score_breakdown.items()},
            "tradeoffs_made": candidate.tradeoffs,
        }


def solve_state(state: QBDState) -> SolverResult:
    """Convenience function to solve a state."""
    solver = QBDSolver(state)
    return solver.solve()
