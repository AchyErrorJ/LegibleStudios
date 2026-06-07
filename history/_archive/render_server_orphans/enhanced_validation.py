"""
Enhanced Validation System for QBD Algebra

Provides:
- Contradiction detection
- Explicit constraint propagation  
- Conflict resolution suggestions
- Feasibility checking
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
import math

from room_relationships import (
    SpatialGraph, Room, RoomTypeSpec, ROOM_TYPES,
    RelationType, Zone, ExteriorRequirement
)


# =============================================================================
# CONFLICT TYPES
# =============================================================================

class ConflictType(Enum):
    """Types of conflicts that can occur in a design state."""
    CONTRADICTION = auto()      # Direct opposition (adjacent + separate)
    UNSATISFIABLE = auto()      # Constraints cannot all be met
    UNDERDETERMINED = auto()    # Not enough information to solve
    CIRCULAR_DEPENDENCY = auto()  # Dependency cycle
    MISSING_DEPENDENCY = auto()   # Required entity doesn't exist
    CAPACITY_EXCEEDED = auto()    # Sum of parts exceeds whole


@dataclass
class Conflict:
    """A detected conflict in the design state."""
    
    type: ConflictType
    message: str
    entities_involved: List[str] = field(default_factory=list)
    fragments_involved: List[str] = field(default_factory=list)
    
    # Resolution options
    resolution_options: List[Dict] = field(default_factory=list)
    
    # Severity
    severity: str = "error"  # "error" | "warning"
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.name,
            "message": self.message,
            "entities": self.entities_involved,
            "fragments": self.fragments_involved,
            "resolutions": self.resolution_options,
            "severity": self.severity
        }


# =============================================================================
# CONSTRAINT PROPAGATION
# =============================================================================

@dataclass
class PropagatedConstraint:
    """A constraint derived from other constraints."""
    
    target: str  # Entity property path
    operator: str  # "<", "<=", "=", ">=", ">"
    value: Any
    source: str  # What derived this constraint
    explanation: str


class ConstraintPropagator:
    """
    Propagates constraints to reduce search space.
    
    Given explicit constraints, derives implicit ones.
    """
    
    def __init__(self, graph: SpatialGraph):
        self.graph = graph
        self.propagated: List[PropagatedConstraint] = []
    
    def propagate(self) -> List[PropagatedConstraint]:
        """
        Run constraint propagation.
        
        Derives implicit constraints from explicit ones.
        """
        self.propagated = []
        
        # Rule 1: Adjacency implies shared boundary
        self._propagate_adjacency()
        
        # Rule 2: Separation implies no shared boundary
        self._propagate_separation()
        
        # Rule 3: Furniture implies room size
        self._propagate_furniture_size()
        
        # Rule 4: Wet rooms imply plumbing walls
        self._propagate_wet_rooms()
        
        # Rule 5: Exterior requirements imply wall type
        self._propagate_exterior_requirements()
        
        # Rule 6: Area sum implies footprint
        self._propagate_area_sum()
        
        return self.propagated
    
    def _propagate_adjacency(self):
        """If A adjacent to B, they must share a wall segment."""
        for adj in self.graph.adjacencies:
            if adj.strength == "required":
                # Both rooms must have at least one exterior wall
                # (or interior wall between them)
                self.propagated.append(PropagatedConstraint(
                    target=f"{adj.room_a}.must_share_wall_with",
                    operator="=",
                    value=adj.room_b,
                    source=f"adjacency:{adj.room_a}-{adj.room_b}",
                    explanation=f"{adj.room_a} must share wall with {adj.room_b} due to required adjacency"
                ))
    
    def _propagate_separation(self):
        """If A separated from B, they cannot share a wall."""
        for sep in self.graph.separations:
            if sep.strength == "required":
                self.propagated.append(PropagatedConstraint(
                    target=f"{sep.room_a}.cannot_share_wall_with",
                    operator="=",
                    value=sep.room_b,
                    source=f"separation:{sep.room_a}-{sep.room_b}",
                    explanation=f"{sep.room_a} cannot share wall with {sep.room_b} due to required separation"
                ))
    
    def _propagate_furniture_size(self):
        """Room size must accommodate furniture plus clearances."""
        for room_id, room in self.graph.rooms.items():
            if room.furniture:
                # Calculate required area from furniture
                total_furniture_area = 0
                total_clearance = 0
                
                for furniture in room.furniture:
                    width = furniture.get("width", 0)
                    length = furniture.get("length", 0)
                    total_furniture_area += width * length
                    
                    # Add clearances
                    clearance = furniture.get("clearance", {})
                    total_clearance += sum(clearance.values()) * 100  # Approximate
                
                # Buffer factor based on room type
                buffer = 1.15 if room.type in ["bedroom", "living"] else 1.10
                required_area = (total_furniture_area + total_clearance) * buffer
                
                if room.min_area is None or required_area > room.min_area:
                    self.propagated.append(PropagatedConstraint(
                        target=f"{room_id}.min_area",
                        operator=">=",
                        value=required_area,
                        source=f"furniture:{room_id}",
                        explanation=f"Room must be at least {required_area:.0f} sqft to accommodate furniture"
                    ))
    
    def _propagate_wet_rooms(self):
        """Wet rooms should be clustered for plumbing efficiency."""
        wet_rooms = [
            room_id for room_id, room in self.graph.rooms.items()
            if room.is_wet or room.type in ["kitchen", "bathroom", "laundry", "powder_room"]
        ]
        
        if len(wet_rooms) >= 2:
            # All wet rooms should be adjacent to at least one other wet room
            for room_id in wet_rooms:
                others = [r for r in wet_rooms if r != room_id]
                self.propagated.append(PropagatedConstraint(
                    target=f"{room_id}.should_be_adjacent_to",
                    operator="in",
                    value=others,
                    source="wet_room_clustering",
                    explanation=f"{room_id} should be near other wet rooms for plumbing efficiency"
                ))
    
    def _propagate_exterior_requirements(self):
        """Rooms requiring exterior walls must be on perimeter."""
        for room_id, room in self.graph.rooms.items():
            room_type_spec = ROOM_TYPES.get(room.type)
            if room_type_spec:
                if room_type_spec.exterior == ExteriorRequirement.REQUIRED:
                    self.propagated.append(PropagatedConstraint(
                        target=f"{room_id}.must_have_exterior_wall",
                        operator="=",
                        value=True,
                        source=f"room_type:{room.type}",
                        explanation=f"{room.type} requires exterior wall (egress/natural light)"
                    ))
                elif room_type_spec.exterior == ExteriorRequirement.INTERIOR_ONLY:
                    self.propagated.append(PropagatedConstraint(
                        target=f"{room_id}.must_be_interior",
                        operator="=",
                        value=True,
                        source=f"room_type:{room.type}",
                        explanation=f"{room.type} should be interior (privacy/climate)"
                    ))
    
    def _propagate_area_sum(self):
        """Sum of room areas must fit in footprint."""
        total_min_area = sum(
            r.min_area or 0 for r in self.graph.rooms.values()
        )
        
        # Add circulation factor
        num_rooms = len(self.graph.rooms)
        circulation_factor = 1.15 if num_rooms > 3 else 1.10
        total_required = total_min_area * circulation_factor
        
        self.propagated.append(PropagatedConstraint(
            target="footprint.min_area",
            operator=">=",
            value=total_required,
            source="area_sum",
            explanation=f"Total program requires at least {total_required:.0f} sqft including circulation"
        ))


# =============================================================================
# CONTRADICTION DETECTION
# =============================================================================

class ContradictionDetector:
    """Detects logical contradictions in the design state."""
    
    def __init__(self, graph: SpatialGraph):
        self.graph = graph
        self.propagator = ConstraintPropagator(graph)
    
    def detect_all(self) -> List[Conflict]:
        """Detect all conflicts in the current state."""
        conflicts = []
        
        # Run propagation first (may reveal conflicts)
        propagated = self.propagator.propagate()
        
        # Check for contradictions
        conflicts.extend(self._detect_adjacency_separation_contradiction())
        conflicts.extend(self._detect_circular_dependencies())
        conflicts.extend(self._detect_missing_dependencies())
        conflicts.extend(self._detect_area_exceeded(propagated))
        conflicts.extend(self._detect_exterior_interior_conflict())
        
        return conflicts
    
    def _detect_adjacency_separation_contradiction(self) -> List[Conflict]:
        """Detect rooms that are both adjacent and separated."""
        conflicts = []
        
        # Build sets for quick lookup
        adjacency_pairs = defaultdict(list)
        for adj in self.graph.adjacencies:
            pair = tuple(sorted([adj.room_a, adj.room_b]))
            adjacency_pairs[pair].append(adj.strength)
        
        separation_pairs = defaultdict(list)
        for sep in self.graph.separations:
            pair = tuple(sorted([sep.room_a, sep.room_b]))
            separation_pairs[pair].append(sep.strength)
        
        # Find overlaps
        for pair in set(adjacency_pairs.keys()) & set(separation_pairs.keys()):
            adj_strengths = adjacency_pairs[pair]
            sep_strengths = separation_pairs[pair]
            
            # Check for required contradiction
            has_required_adj = "required" in adj_strengths
            has_required_sep = "required" in sep_strengths
            
            if has_required_adj and has_required_sep:
                conflicts.append(Conflict(
                    type=ConflictType.CONTRADICTION,
                    message=f"{pair[0]} and {pair[1]} are both required to be adjacent AND separated",
                    entities_involved=list(pair),
                    resolution_options=[
                        {
                            "action": "remove_adjacency",
                            "description": f"Remove adjacency requirement between {pair[0]} and {pair[1]}",
                            "effect": f"Rooms will not be required to share a wall"
                        },
                        {
                            "action": "remove_separation",
                            "description": f"Remove separation requirement between {pair[0]} and {pair[1]}",
                            "effect": f"Rooms may share a wall"
                        },
                        {
                            "action": "weaken_both",
                            "description": f"Change both to 'preferred' instead of 'required'",
                            "effect": f"System will try to satisfy both but can trade off"
                        }
                    ]
                ))
        
        return conflicts
    
    def _detect_circular_dependencies(self) -> List[Conflict]:
        """Detect circular access requirements."""
        conflicts = []
        
        # Build access graph
        access_graph = defaultdict(set)
        for adj in self.graph.adjacencies:
            if adj.type == RelationType.ACCESSED_VIA:
                access_graph[adj.room_a].add(adj.room_b)
        
        # Find cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node, path):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in access_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, path + [neighbor]):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    conflicts.append(Conflict(
                        type=ConflictType.CIRCULAR_DEPENDENCY,
                        message=f"Circular access dependency: {' -> '.join(cycle)}",
                        entities_involved=cycle,
                        resolution_options=[
                            {
                                "action": "break_cycle",
                                "description": "Remove one access requirement to break the cycle",
                                "effect": "All rooms will have valid access paths"
                            }
                        ]
                    ))
                    return True
            
            rec_stack.remove(node)
            return False
        
        for room in self.graph.rooms:
            if room not in visited:
                has_cycle(room, [room])
        
        return conflicts
    
    def _detect_missing_dependencies(self) -> List[Conflict]:
        """Detect references to non-existent entities."""
        conflicts = []
        
        existing_rooms = set(self.graph.rooms.keys())
        
        # Check adjacencies
        for adj in self.graph.adjacencies:
            if adj.room_a not in existing_rooms:
                conflicts.append(Conflict(
                    type=ConflictType.MISSING_DEPENDENCY,
                    message=f"Adjacency references non-existent room: {adj.room_a}",
                    entities_involved=[adj.room_a],
                    resolution_options=[
                        {
                            "action": "create_room",
                            "description": f"Create room '{adj.room_a}'",
                            "effect": "Room will be added with default properties"
                        },
                        {
                            "action": "remove_adjacency",
                            "description": f"Remove adjacency referencing {adj.room_a}",
                            "effect": "Invalid adjacency will be removed"
                        }
                    ]
                ))
            if adj.room_b not in existing_rooms:
                conflicts.append(Conflict(
                    type=ConflictType.MISSING_DEPENDENCY,
                    message=f"Adjacency references non-existent room: {adj.room_b}",
                    entities_involved=[adj.room_b],
                    resolution_options=[
                        {
                            "action": "create_room",
                            "description": f"Create room '{adj.room_b}'",
                            "effect": "Room will be added with default properties"
                        },
                        {
                            "action": "remove_adjacency",
                            "description": f"Remove adjacency referencing {adj.room_b}",
                            "effect": "Invalid adjacency will be removed"
                        }
                    ]
                ))
        
        return conflicts
    
    def _detect_area_exceeded(
        self,
        propagated: List[PropagatedConstraint]
    ) -> List[Conflict]:
        """Detect when required area exceeds available footprint."""
        conflicts = []
        
        # Find footprint constraint
        footprint_min = None
        for pc in propagated:
            if pc.target == "footprint.min_area":
                footprint_min = pc.value
        
        if footprint_min is None:
            return conflicts
        
        # TODO: Compare to actual footprint constraint when available
        # For now, just note if it's very large
        if footprint_min > 10000:  # 10,000 sqft threshold
            conflicts.append(Conflict(
                type=ConflictType.CAPACITY_EXCEEDED,
                message=f"Program requires {footprint_min:.0f} sqft - verify this fits your site",
                entities_involved=list(self.graph.rooms.keys()),
                severity="warning",
                resolution_options=[
                    {
                        "action": "reduce_room_sizes",
                        "description": "Reduce minimum room sizes by 10%",
                        "effect": f"Required area would be {footprint_min * 0.9:.0f} sqft"
                    },
                    {
                        "action": "remove_rooms",
                        "description": "Remove lowest priority rooms",
                        "effect": "Select rooms to remove"
                    }
                ]
            ))
        
        return conflicts
    
    def _detect_exterior_interior_conflict(self) -> List[Conflict]:
        """Detect rooms required to be both exterior and interior."""
        conflicts = []
        
        for room_id, room in self.graph.rooms.items():
            room_type_spec = ROOM_TYPES.get(room.type)
            if not room_type_spec:
                continue
            
            # Check if room type requires exterior
            needs_exterior = room_type_spec.exterior == ExteriorRequirement.REQUIRED
            needs_interior = room_type_spec.exterior == ExteriorRequirement.INTERIOR_ONLY
            
            # Check for explicit constraints that conflict
            # (This would need explicit constraint storage)
            
        return conflicts


# =============================================================================
# FEASIBILITY CHECKER
# =============================================================================

class FeasibilityChecker:
    """Checks if the current state can produce a valid layout."""
    
    def __init__(self, graph: SpatialGraph):
        self.graph = graph
        self.detector = ContradictionDetector(graph)
    
    def check(self) -> Tuple[bool, List[Conflict]]:
        """
        Check if state is feasible.
        
        Returns:
            (is_feasible, list_of_blocking_conflicts)
        """
        conflicts = self.detector.detect_all()
        
        # Filter to blocking conflicts only
        blocking = [
            c for c in conflicts
            if c.severity == "error" and c.type in [
                ConflictType.CONTRADICTION,
                ConflictType.CIRCULAR_DEPENDENCY,
                ConflictType.MISSING_DEPENDENCY
            ]
        ]
        
        is_feasible = len(blocking) == 0
        
        return is_feasible, blocking
    
    def check_solvability(
        self,
        width: float,
        depth: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if layout is solvable given dimensions.
        
        Returns:
            (is_solvable, error_message_or_none)
        """
        # Check area
        total_min_area = sum(
            r.min_area or 0 for r in self.graph.rooms.values()
        )
        available_area = width * depth * 0.85  # 85% efficiency
        
        if total_min_area > available_area:
            return False, (
                f"Program requires {total_min_area:.0f} sqft, "
                f"but {width:.0f}x{depth:.0f} only provides {available_area:.0f} sqft usable"
            )
        
        # Check for required exterior walls
        exterior_required = sum(
            1 for r in self.graph.rooms.values()
            if ROOM_TYPES.get(r.type, RoomTypeSpec("", Zone.PUBLIC, ExteriorRequirement.NONE)).exterior == ExteriorRequirement.REQUIRED
        )
        
        # Rough perimeter estimate
        perimeter = 2 * (width + depth)
        max_exterior_rooms = int(perimeter / 10)  # Assume 10ft min room width
        
        if exterior_required > max_exterior_rooms:
            return False, (
                f"{exterior_required} rooms require exterior walls, "
                f"but perimeter can only accommodate ~{max_exterior_rooms}"
            )
        
        return True, None


# =============================================================================
# SURGICAL REDUCTION
# =============================================================================

@dataclass
class ReductionOption:
    """An option for resolving UNSATISFIABLE state."""
    
    action: str
    description: str
    impact: str  # Human-readable impact description
    area_saved: float  # Square feet saved
    priority_impact: Dict[str, float]  # How this affects each priority


class SurgicalReduction:
    """
    Generates options for resolving unsatisfiable constraints.
    
    When the design cannot be realized, suggests targeted reductions.
    """
    
    def __init__(self, graph: SpatialGraph):
        self.graph = graph
    
    def generate_options(
        self,
        target_reduction: float,
        priorities: Dict[str, int]
    ) -> List[ReductionOption]:
        """
        Generate reduction options to meet constraints.
        
        Args:
            target_reduction: Required area reduction in sqft
            priorities: Current priority weights
        
        Returns:
            List of reduction options sorted by priority alignment
        """
        options = []
        
        # Option 1: Reduce all rooms proportionally
        total_area = sum(r.min_area or 0 for r in self.graph.rooms.values())
        reduction_ratio = 1 - (target_reduction / total_area)
        
        options.append(ReductionOption(
            action="reduce_all_proportional",
            description=f"Reduce all room sizes by {(1-reduction_ratio)*100:.0f}%",
            impact="All rooms slightly smaller, relationships preserved",
            area_saved=target_reduction,
            priority_impact={"space": -0.2, "comfort": -0.1}
        ))
        
        # Option 2: Remove lowest priority room
        # Priority: special rooms > secondary bedrooms > primary suite features
        removable = [
            (room_id, room) for room_id, room in self.graph.rooms.items()
            if room.type in ["office", "guest_room", "media", "gym", "workshop"]
        ]
        
        for room_id, room in removable:
            area_saved = room.min_area or 100
            options.append(ReductionOption(
                action=f"remove_room:{room_id}",
                description=f"Remove {room_id}",
                impact=f"Lose {room_id} but preserve all other rooms",
                area_saved=area_saved,
                priority_impact={"functionality": -0.3, "space": 0.1}
            ))
        
        # Option 3: Reduce bedroom sizes
        bedrooms = [
            (room_id, room) for room_id, room in self.graph.rooms.items()
            if "bedroom" in room.type
        ]
        
        if bedrooms:
            bedroom_area = sum(r.min_area or 0 for _, r in bedrooms)
            reduction_per_room = target_reduction / len(bedrooms)
            
            options.append(ReductionOption(
                action="reduce_bedrooms",
                description=f"Reduce each bedroom by {reduction_per_room:.0f} sqft",
                impact="Bedrooms smaller but still functional",
                area_saved=target_reduction,
                priority_impact={"comfort": -0.2, "space": 0.0}
            ))
        
        # Option 4: Remove garage
        if any(r.type == "garage" for r in self.graph.rooms.values()):
            options.append(ReductionOption(
                action="remove_garage",
                description="Remove garage (convert to carport or street parking)",
                impact="Lose covered parking, gain significant space",
                area_saved=400,  # Typical 2-car garage
                priority_impact={"convenience": -0.4, "space": 0.3}
            ))
        
        # Sort by alignment with priorities
        def priority_score(option: ReductionOption) -> float:
            score = 0
            for factor, impact in option.priority_impact.items():
                weight = priorities.get(factor, 5) / 10
                score += impact * weight
            return score
        
        options.sort(key=priority_score, reverse=True)
        
        return options


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def validate_state(graph: SpatialGraph) -> Tuple[bool, List[Conflict]]:
    """Validate a design state."""
    checker = FeasibilityChecker(graph)
    return checker.check()


def get_resolution_options(
    graph: SpatialGraph,
    target_reduction: float,
    priorities: Dict[str, int]
) -> List[ReductionOption]:
    """Get options for resolving unsatisfiable constraints."""
    reducer = SurgicalReduction(graph)
    return reducer.generate_options(target_reduction, priorities)


def propagate_constraints(graph: SpatialGraph) -> List[PropagatedConstraint]:
    """Propagate constraints in a graph."""
    propagator = ConstraintPropagator(graph)
    return propagator.propagate()


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ENHANCED VALIDATION SYSTEM TEST")
    print("=" * 60)
    
    from room_relationships import SpatialGraph
    
    # Test 1: Valid state
    print("\n--- Test 1: Valid State ---")
    graph = SpatialGraph()
    graph.add_room("living", "living", min_area=200)
    graph.add_room("kitchen", "kitchen", min_area=150)
    graph.connect("living", "kitchen")
    
    is_valid, conflicts = validate_state(graph)
    print(f"Valid: {is_valid}")
    print(f"Conflicts: {len(conflicts)}")
    
    # Test 2: Contradiction
    print("\n--- Test 2: Adjacency + Separation Contradiction ---")
    graph2 = SpatialGraph()
    graph2.add_room("bedroom", "bedroom", min_area=150)
    graph2.add_room("living", "living", min_area=200)
    graph2.connect("bedroom", "living")  # Adjacent
    graph2.isolate("bedroom", "living")  # Also separated
    
    is_valid, conflicts = validate_state(graph2)
    print(f"Valid: {is_valid}")
    for c in conflicts:
        print(f"  Conflict: {c.message}")
        for opt in c.resolution_options[:2]:
            print(f"    - {opt['description']}")
    
    # Test 3: Constraint Propagation
    print("\n--- Test 3: Constraint Propagation ---")
    graph3 = SpatialGraph()
    graph3.add_room("kitchen", "kitchen", min_area=100)
    graph3.add_room("bath", "bathroom", min_area=50)
    graph3.add_room("laundry", "laundry", min_area=40)
    
    propagated = propagate_constraints(graph3)
    print(f"Propagated constraints: {len(propagated)}")
    for pc in propagated[:5]:
        print(f"  {pc.target} {pc.operator} {pc.value}")
        print(f"    ({pc.explanation})")
    
    # Test 4: Surgical Reduction
    print("\n--- Test 4: Surgical Reduction Options ---")
    graph4 = SpatialGraph()
    graph4.add_room("living", "living", min_area=200)
    graph4.add_room("kitchen", "kitchen", min_area=150)
    graph4.add_room("bedroom1", "bedroom", min_area=150)
    graph4.add_room("bedroom2", "bedroom", min_area=150)
    graph4.add_room("office", "office", min_area=120)
    graph4.add_room("garage", "garage", min_area=400)
    
    priorities = {"space": 8, "comfort": 6, "functionality": 7, "convenience": 5}
    options = get_resolution_options(graph4, target_reduction=300, priorities=priorities)
    
    print(f"Reduction options (need 300 sqft):")
    for opt in options:
        print(f"  {opt.description}")
        print(f"    Saves: {opt.area_saved:.0f} sqft")
        print(f"    Impact: {opt.impact}")
    
    # Test 5: Solvability check
    print("\n--- Test 5: Solvability Check ---")
    checker = FeasibilityChecker(graph4)
    solvable, error = checker.check_solvability(width=40, depth=30)
    print(f"Solvable in 40x30: {solvable}")
    if error:
        print(f"  Error: {error}")
    
    solvable, error = checker.check_solvability(width=20, depth=20)
    print(f"Solvable in 20x20: {solvable}")
    if error:
        print(f"  Error: {error}")
