"""
Layout to Walls Converter
=========================
Converts room layout solutions into wall creation commands for Revit MCP tools.

Output format is designed to work with existing MCP tools:
- create_wall(start, end, wall_type, level)
- get_wall_types()
- get_level()

Wall Types:
- Exterior: Exterior wall type (thicker, structural)
- Interior: Standard interior partition
- Wet Wall: Thicker interior partition for plumbing walls (bathroom/kitchen adjacencies)
"""

from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_WALL_HEIGHT = 9.0  # feet

# Wall type hints for MCP tool selection
WALL_TYPE_EXTERIOR = "exterior"      # Use exterior wall type
WALL_TYPE_INTERIOR = "interior"      # Standard interior partition  
WALL_TYPE_WET_WALL = "wet_wall"      # Thicker partition for plumbing

# Wet room types (rooms with plumbing)
WET_ROOMS = {"kitchen", "bathroom", "primary_bath", "laundry", "utility"}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class WallCommand:
    """A wall creation command for MCP tools"""
    start: Tuple[float, float]  # (x, y) in feet
    end: Tuple[float, float]    # (x, y) in feet
    wall_type: str              # "exterior", "interior", or "wet_wall"
    height: float = DEFAULT_WALL_HEIGHT
    rooms: List[str] = field(default_factory=list)  # Adjacent rooms
    has_door: bool = False
    notes: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "start": {"x": self.start[0], "y": self.start[1]},
            "end": {"x": self.end[0], "y": self.end[1]},
            "wall_type": self.wall_type,
            "height": self.height,
            "rooms": self.rooms,
            "has_door": self.has_door,
            "notes": self.notes
        }


@dataclass
class DoorLocation:
    """A door placement location"""
    position: Tuple[float, float]  # (x, y) center point
    width: float = 3.0  # 36" standard
    rooms: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "position": {"x": self.position[0], "y": self.position[1]},
            "width": self.width,
            "rooms": self.rooms
        }


# =============================================================================
# LAYOUT TO WALLS CONVERTER
# =============================================================================

class LayoutToWallsConverter:
    """
    Converts a room layout solution into wall commands for Revit.
    
    Usage:
        converter = LayoutToWallsConverter(width=40, depth=30)
        walls, doors = converter.convert(solution)
        
        # walls is a list of WallCommand objects
        # doors is a list of DoorLocation objects
    """
    
    def __init__(self, width: float, depth: float):
        self.width = width
        self.depth = depth
        self.tolerance = 0.1
    
    def convert(self, solution) -> Tuple[List[WallCommand], List[DoorLocation]]:
        """
        Convert a LayoutSolution to wall commands.
        
        Args:
            solution: LayoutSolution from RoomLayoutSolver
            
        Returns:
            Tuple of (wall_commands, door_locations)
        """
        walls = []
        doors = []
        
        # 1. Exterior walls (4 walls around perimeter)
        walls.extend(self._create_exterior_walls())
        
        # 2. Interior walls from room adjacencies
        interior_walls, interior_doors = self._create_interior_walls(solution)
        walls.extend(interior_walls)
        doors.extend(interior_doors)
        
        return walls, doors
    
    def _create_exterior_walls(self) -> List[WallCommand]:
        """Create the 4 exterior perimeter walls"""
        return [
            WallCommand(
                start=(0, 0), end=(self.width, 0),
                wall_type=WALL_TYPE_EXTERIOR,
                notes="South exterior wall"
            ),
            WallCommand(
                start=(self.width, 0), end=(self.width, self.depth),
                wall_type=WALL_TYPE_EXTERIOR,
                notes="East exterior wall"
            ),
            WallCommand(
                start=(self.width, self.depth), end=(0, self.depth),
                wall_type=WALL_TYPE_EXTERIOR,
                notes="North exterior wall"
            ),
            WallCommand(
                start=(0, self.depth), end=(0, 0),
                wall_type=WALL_TYPE_EXTERIOR,
                notes="West exterior wall"
            ),
        ]
    
    def _create_interior_walls(self, solution) -> Tuple[List[WallCommand], List[DoorLocation]]:
        """Create interior walls between rooms"""
        walls = []
        doors = []
        processed = set()
        
        rooms = list(solution.rooms.values())
        
        for i, room1 in enumerate(rooms):
            for room2 in rooms[i+1:]:
                # Find shared edge
                edge = self._get_shared_edge(room1, room2)
                if edge is None:
                    continue
                
                # Avoid duplicates
                edge_key = self._edge_key(edge)
                if edge_key in processed:
                    continue
                processed.add(edge_key)
                
                # Determine wall type
                room1_type = room1.definition.room_type
                room2_type = room2.definition.room_type
                
                # Use wet wall if EITHER room is a wet room (kitchen, bathroom, laundry)
                is_wet_wall = (room1_type in WET_ROOMS or room2_type in WET_ROOMS)
                wall_type = WALL_TYPE_WET_WALL if is_wet_wall else WALL_TYPE_INTERIOR
                
                # Determine if door needed
                has_door = self._should_have_door(room1, room2)
                
                # Create wall command
                notes = ""
                if is_wet_wall:
                    notes = "Wet wall - use thicker partition for plumbing"
                
                wall = WallCommand(
                    start=edge['start'],
                    end=edge['end'],
                    wall_type=wall_type,
                    rooms=[room1.definition.name, room2.definition.name],
                    has_door=has_door,
                    notes=notes
                )
                walls.append(wall)
                
                # Create door if needed
                if has_door:
                    door_pos = (
                        (edge['start'][0] + edge['end'][0]) / 2,
                        (edge['start'][1] + edge['end'][1]) / 2
                    )
                    doors.append(DoorLocation(
                        position=door_pos,
                        rooms=[room1.definition.name, room2.definition.name]
                    ))
        
        return walls, doors
    
    def _get_shared_edge(self, room1, room2) -> Optional[Dict]:
        """Find the shared edge between two adjacent rooms"""
        tol = self.tolerance
        
        # Vertical edge (left-right neighbors)
        if abs(room1.x2 - room2.x) < tol:
            y_start = max(room1.y, room2.y)
            y_end = min(room1.y2, room2.y2)
            if y_end > y_start + tol:
                return {'start': (room1.x2, y_start), 'end': (room1.x2, y_end)}
        
        if abs(room1.x - room2.x2) < tol:
            y_start = max(room1.y, room2.y)
            y_end = min(room1.y2, room2.y2)
            if y_end > y_start + tol:
                return {'start': (room1.x, y_start), 'end': (room1.x, y_end)}
        
        # Horizontal edge (top-bottom neighbors)
        if abs(room1.y2 - room2.y) < tol:
            x_start = max(room1.x, room2.x)
            x_end = min(room1.x2, room2.x2)
            if x_end > x_start + tol:
                return {'start': (x_start, room1.y2), 'end': (x_end, room1.y2)}
        
        if abs(room1.y - room2.y2) < tol:
            x_start = max(room1.x, room2.x)
            x_end = min(room1.x2, room2.x2)
            if x_end > x_start + tol:
                return {'start': (x_start, room1.y), 'end': (x_end, room1.y)}
        
        return None
    
    def _edge_key(self, edge: Dict) -> Tuple:
        """Create hashable key for edge deduplication"""
        start = (round(edge['start'][0], 1), round(edge['start'][1], 1))
        end = (round(edge['end'][0], 1), round(edge['end'][1], 1))
        return tuple(sorted([start, end]))
    
    def _should_have_door(self, room1, room2) -> bool:
        """Check if two rooms should have a door between them"""
        type1 = room1.definition.room_type
        type2 = room2.definition.room_type
        
        # No door if in share_wall_only
        if type2 in room1.definition.share_wall_only:
            return False
        if type1 in room2.definition.share_wall_only:
            return False
        
        # Door if connection is allowed
        allowed1 = set(room1.definition.must_connect) | set(room1.definition.can_connect)
        allowed2 = set(room2.definition.must_connect) | set(room2.definition.can_connect)
        
        return type2 in allowed1 or type1 in allowed2
    
    def to_mcp_format(self, solution) -> Dict:
        """
        Convert solution to MCP-ready format.
        
        Returns a dict that can be used directly with MCP wall creation tools.
        """
        walls, doors = self.convert(solution)
        
        # Group walls by type for easier processing
        exterior_walls = [w for w in walls if w.wall_type == WALL_TYPE_EXTERIOR]
        interior_walls = [w for w in walls if w.wall_type == WALL_TYPE_INTERIOR]
        wet_walls = [w for w in walls if w.wall_type == WALL_TYPE_WET_WALL]
        
        # Get room data
        room_data = {}
        for name, room in solution.rooms.items():
            room_data[name] = {
                "bounds": {
                    "x": room.x,
                    "y": room.y,
                    "width": room.width,
                    "height": room.height
                },
                "area_sqft": room.area,
                "type": room.definition.room_type,
                "is_wet_room": room.definition.room_type in WET_ROOMS
            }
        
        return {
            "footprint": {
                "width": self.width,
                "depth": self.depth,
                "area_sqft": self.width * self.depth
            },
            "walls": {
                "exterior": [w.to_dict() for w in exterior_walls],
                "interior": [w.to_dict() for w in interior_walls],
                "wet_wall": [w.to_dict() for w in wet_walls]
            },
            "doors": [d.to_dict() for d in doors],
            "rooms": room_data,
            "summary": {
                "total_walls": len(walls),
                "exterior_walls": len(exterior_walls),
                "interior_walls": len(interior_walls),
                "wet_walls": len(wet_walls),
                "doors": len(doors),
                "rooms": len(room_data)
            },
            "wall_type_guide": {
                "exterior": "Use exterior wall type (e.g., 'Generic - 6\" Masonry' or similar)",
                "interior": "Use standard interior partition (e.g., 'Interior - 4 7/8\" Partition')",
                "wet_wall": "Use thicker interior partition for plumbing (e.g., 'Interior - 6\" Partition' or add note)"
            }
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def convert_layout_to_walls(solution, width: float, depth: float) -> Dict:
    """
    Convert a layout solution to wall data for Revit MCP.
    
    Args:
        solution: LayoutSolution from RoomLayoutSolver
        width: Footprint width in feet
        depth: Footprint depth in feet
        
    Returns:
        Dict with wall commands grouped by type, ready for MCP tools
    """
    converter = LayoutToWallsConverter(width, depth)
    return converter.to_mcp_format(solution)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    from room_layout_solver_v2_fixed import RoomLayoutSolver
    
    print("=" * 60)
    print("LAYOUT TO WALLS CONVERTER")
    print("=" * 60)
    
    # Create layout
    solver = RoomLayoutSolver(width=40, depth=30, grid_size=2)
    solver.set_entry_location(20, 0)
    solver.set_zone_split(public=1.0, private=0.0)
    
    solver.add_room("entry", min_area=50)
    solver.add_room("living", min_area=200)
    solver.add_room("dining", min_area=80)
    solver.add_room("kitchen", min_area=100)
    solver.add_room("primary_bedroom", min_area=150)
    solver.add_room("bedroom", min_area=100, name="Bedroom 2")
    solver.add_room("bathroom", min_area=40)
    solver.add_room("laundry", min_area=35)
    solver.add_room("mechanical", min_area=30)
    solver.add_room("hallway", min_area=24)
    
    print("\nGenerating layout...")
    solutions = solver.solve(max_solutions=1, timeout_nodes=10000)
    
    if solutions:
        solution = solutions[0]
        print(f"Layout score: {solution.score:.1f}")
        
        # Convert to walls
        print("\nConverting to walls...")
        result = convert_layout_to_walls(solution, 40, 30)
        
        # Print summary
        print(f"\n📊 Summary:")
        for key, value in result['summary'].items():
            print(f"   {key}: {value}")
        
        # Print walls by type
        print(f"\n🧱 EXTERIOR WALLS ({len(result['walls']['exterior'])}):")
        print("   Use: Exterior wall type")
        for w in result['walls']['exterior']:
            start, end = w['start'], w['end']
            print(f"   ({start['x']:.0f}, {start['y']:.0f}) -> ({end['x']:.0f}, {end['y']:.0f})")
        
        print(f"\n🧱 INTERIOR WALLS ({len(result['walls']['interior'])}):")
        print("   Use: Standard interior partition")
        for w in result['walls']['interior']:
            start, end = w['start'], w['end']
            rooms = ' <-> '.join(w['rooms'])
            door = " 🚪" if w['has_door'] else ""
            print(f"   ({start['x']:.0f}, {start['y']:.0f}) -> ({end['x']:.0f}, {end['y']:.0f}) | {rooms}{door}")
        
        print(f"\n🚿 WET WALLS ({len(result['walls']['wet_wall'])}):")
        print("   Use: Thicker partition for plumbing")
        for w in result['walls']['wet_wall']:
            start, end = w['start'], w['end']
            rooms = ' <-> '.join(w['rooms'])
            print(f"   ({start['x']:.0f}, {start['y']:.0f}) -> ({end['x']:.0f}, {end['y']:.0f}) | {rooms}")
            if w['notes']:
                print(f"      Note: {w['notes']}")
        
        print(f"\n🚪 DOORS ({len(result['doors'])}):")
        for d in result['doors']:
            pos = d['position']
            rooms = ' <-> '.join(d['rooms'])
            print(f"   ({pos['x']:.1f}, {pos['y']:.1f}) | {rooms}")
        
        # Save JSON
        with open('/home/claude/walls_for_revit.json', 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved: walls_for_revit.json")
        
    else:
        print("No solution found!")
