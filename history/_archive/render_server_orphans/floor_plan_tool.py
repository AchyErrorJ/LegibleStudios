"""
Floor Plan Generation Tool for RevitMCP
========================================
This tool generates floor plan layouts and outputs wall data
formatted for the /revit_mcp/create_walls_batch endpoint.

Supports two solver versions:
- v2: Original solver (room_layout_solver_v2_fixed.py)
- v3: Advanced CSP-based solver with partial solutions (room_layout_solver_v3.py)
"""

import json
from typing import Dict, List, Any, Optional

# V2 Solver imports
from room_layout_solver_v2_fixed import RoomLayoutSolver
from layout_to_walls import convert_layout_to_walls, WALL_TYPE_EXTERIOR, WALL_TYPE_INTERIOR, WALL_TYPE_WET_WALL

# V3 Solver imports
try:
    from room_layout_solver_v3 import (
        RoomLayoutSolverV3,
        BuildingShape,
        LayoutSolution,
        solution_to_walls
    )
    V3_AVAILABLE = True
except ImportError:
    V3_AVAILABLE = False


def generate_floor_plan_walls(
    width: float,
    depth: float,
    rooms: List[Dict[str, Any]],
    level_name: str = "Level 1",
    wall_height: float = 10.0,
    exterior_wall_type: str = None,
    interior_wall_type: str = None,
    wet_wall_type: str = None,
    entry_x: Optional[float] = None,
    entry_y: float = 0,
    interior_only: bool = False,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
    solver_version: str = "v3",
    allow_partial: bool = True
) -> Dict[str, Any]:
    """
    Generate a floor plan and format wall data for create_walls_batch.

    This is the main MCP tool function.

    Args:
        width: Footprint width in feet
        depth: Footprint depth in feet
        rooms: List of room specs [{"type": "living", "min_area": 200}, ...]
        level_name: Revit level name
        wall_height: Wall height in feet
        exterior_wall_type: Revit wall type name for exterior walls
        interior_wall_type: Revit wall type name for interior partitions
        wet_wall_type: Revit wall type name for plumbing walls (thicker)
        entry_x: X position of entry (default: center)
        entry_y: Y position of entry (default: 0 = south)
        interior_only: If True, only generate interior partition walls (no exterior)
        origin_x: X offset for placing layout within existing geometry
        origin_y: Y offset for placing layout within existing geometry
        solver_version: "v2" for original solver, "v3" for advanced CSP solver (default)
        allow_partial: If True and using v3, return partial solutions when not all rooms fit

    Returns:
        Dict with:
            - success: bool
            - walls_batch: Array formatted for /revit_mcp/create_walls_batch
            - room_data: Room boundaries for reference
            - doors: Door locations (for future door placement)
            - summary: Wall counts
            - is_partial: bool (v3 only) - True if not all rooms were placed
            - unplaced_rooms: List of room specs that couldn't fit (v3 only)
            - error: Error message if failed
    """
    try:
        if entry_x is None:
            entry_x = width / 2

        # Determine which solver to use
        use_v3 = solver_version == "v3" and V3_AVAILABLE

        if use_v3:
            # ============= V3 SOLVER (Advanced CSP) =============
            building = BuildingShape.rectangle(width, depth, entry_x=entry_x)
            solver = RoomLayoutSolverV3(building, grid_size=2.0)

            # Add rooms
            for room_spec in rooms:
                room_type = room_spec.get("type", "room")
                min_area = room_spec.get("min_area", 100)
                name = room_spec.get("name")
                solver.add_room(room_type, min_area=min_area, name=name)

            # Solve with partial solution support
            solution = solver.solve(max_nodes=100000, return_partial=allow_partial)

            # Check if we got a solution
            if not solution or solution.placed_count == 0:
                total_requested = sum(r.get("min_area", 100) for r in rooms)
                total_available = width * depth
                utilization = total_requested / total_available * 100 if total_available > 0 else 0
                return {
                    "success": False,
                    "error": f"Could not place any rooms in {width}x{depth} ({total_available:.0f} sqft). "
                            f"Requested: {total_requested:.0f} sqft ({utilization:.0f}% utilization). "
                            f"Try: larger footprint or smaller room sizes.",
                    "solver_version": "v3"
                }

            # Convert to wall data using v3's converter
            wall_data = solution_to_walls(solution, building)

            # Check if partial solution
            is_partial = not solution.is_complete

        else:
            # ============= V2 SOLVER (Original) =============
            solver = RoomLayoutSolver(width=width, depth=depth, grid_size=2)
            solver.set_entry_location(entry_x, entry_y)
            solver.set_zone_split(public=1.0, private=0.0)

            if interior_only:
                solver.set_interior_only(True)

            # Add rooms
            for room_spec in rooms:
                room_type = room_spec.get("type", "room")
                min_area = room_spec.get("min_area", 100)
                name = room_spec.get("name")

                kwargs = {"min_area": min_area}
                if name:
                    kwargs["name"] = name

                solver.add_room(room_type, **kwargs)

            # Solve layout
            solutions = solver.solve(max_solutions=1, timeout_nodes=50000)

            if not solutions:
                total_requested = sum(r.get("min_area", 100) for r in rooms)
                total_available = width * depth
                utilization = total_requested / total_available * 100 if total_available > 0 else 0

                room_summary = ", ".join([f"{r.get('type', 'room')}({r.get('min_area', 100)}sqft)" for r in rooms[:5]])
                if len(rooms) > 5:
                    room_summary += f", +{len(rooms)-5} more"

                return {
                    "success": False,
                    "error": f"Could not fit all {len(rooms)} rooms in {width}x{depth} ({total_available:.0f} sqft). "
                            f"Requested: {total_requested:.0f} sqft ({utilization:.0f}% utilization). "
                            f"Rooms: {room_summary}. "
                            f"Try: larger footprint, fewer rooms, or smaller room sizes.",
                    "solver_version": "v2",
                    "debug": {
                        "rooms_requested": len(rooms),
                        "total_area_requested": total_requested,
                        "total_area_available": total_available,
                        "utilization_percent": utilization,
                        "rooms": rooms
                    }
                }

            solution = solutions[0]
            wall_data = convert_layout_to_walls(solution, width, depth)
            is_partial = False
        
        # 5. Format for create_walls_batch endpoint
        walls_batch = []
        exterior_count = 0

        # Exterior walls (skip if interior_only mode)
        if not interior_only:
            for wall in wall_data["walls"]["exterior"]:
                walls_batch.append({
                    "start": [wall["start"]["x"] + origin_x, wall["start"]["y"] + origin_y],
                    "end": [wall["end"]["x"] + origin_x, wall["end"]["y"] + origin_y],
                    "level_name": level_name,
                    "height": wall_height,
                    "wall_type": exterior_wall_type,
                    "category": "exterior",
                    "notes": wall.get("notes", "")
                })
                exterior_count += 1

        # Interior walls (standard partition)
        for wall in wall_data["walls"]["interior"]:
            walls_batch.append({
                "start": [wall["start"]["x"] + origin_x, wall["start"]["y"] + origin_y],
                "end": [wall["end"]["x"] + origin_x, wall["end"]["y"] + origin_y],
                "level_name": level_name,
                "height": wall_height,
                "wall_type": interior_wall_type,
                "category": "interior",
                "rooms": wall.get("rooms", []),
                "has_door": wall.get("has_door", False)
            })

        # Wet walls (thicker partition for plumbing)
        for wall in wall_data["walls"]["wet_wall"]:
            walls_batch.append({
                "start": [wall["start"]["x"] + origin_x, wall["start"]["y"] + origin_y],
                "end": [wall["end"]["x"] + origin_x, wall["end"]["y"] + origin_y],
                "level_name": level_name,
                "height": wall_height,
                "wall_type": wet_wall_type or interior_wall_type,  # Fallback to interior
                "category": "wet_wall",
                "rooms": wall.get("rooms", []),
                "notes": "Wet wall - plumbing"
            })
        
        # 6. Build response
        response = {
            "success": True,
            "layout_score": solution.score,
            "walls_batch": walls_batch,
            "rooms": wall_data["rooms"],
            "doors": wall_data["doors"],
            "interior_only": interior_only,
            "origin": {"x": origin_x, "y": origin_y},
            "solver_version": "v3" if use_v3 else "v2",
            "summary": {
                "total_walls": len(walls_batch),
                "exterior_walls": exterior_count,
                "interior_walls": len(wall_data["walls"]["interior"]),
                "wet_walls": len(wall_data["walls"]["wet_wall"]),
                "doors": len(wall_data["doors"]),
                "rooms_placed": len(wall_data["rooms"]),
                "rooms_requested": len(rooms)
            },
            "wall_type_requirements": {
                "exterior": "Requires exterior wall type" if not interior_only else "Skipped (interior_only mode)",
                "interior": "Standard interior partition (4-5\")",
                "wet_wall": "Thicker partition for plumbing (6\"+)"
            }
        }

        # Add v3-specific partial solution info
        if use_v3:
            response["is_partial"] = is_partial
            if is_partial:
                unplaced = [{"type": r.room_type.value, "name": r.name, "min_area": r.min_area}
                           for r in solution.unplaced_rooms]
                response["unplaced_rooms"] = unplaced
                response["warning"] = (f"Partial solution: placed {solution.placed_count}/{solution.total_rooms} rooms. "
                                      f"Could not fit: {', '.join(r['name'] for r in unplaced)}")

        return response
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# =============================================================================
# MCP TOOL SCHEMA (for registering in your MCP server)
# =============================================================================

TOOL_SCHEMA = {
    "name": "generate_floor_plan_walls",
    "description": """Generate a complete floor plan layout and return wall data ready for Revit creation.
    
This tool:
1. Takes room specifications (type and minimum area)
2. Generates an optimized layout solving adjacency constraints
3. Returns walls grouped by type (exterior, interior, wet_wall)
4. Output is formatted for direct use with create_walls_batch

Wall types needed:
- exterior: Use an exterior wall type (structural, weather barrier)
- interior: Standard interior partition (4-5" typical)
- wet_wall: Thicker partition for plumbing walls (6"+) - between kitchen/bath/laundry

Call list_wall_types first to get available wall type names.""",
    
    "input_schema": {
        "type": "object",
        "properties": {
            "width": {
                "type": "number",
                "description": "Footprint width in feet"
            },
            "depth": {
                "type": "number",
                "description": "Footprint depth in feet"
            },
            "rooms": {
                "type": "array",
                "description": "List of room specifications",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "entry", "living", "dining", "kitchen",
                                "bedroom", "primary_bedroom", 
                                "bathroom", "primary_bath",
                                "hallway", "closet", "office",
                                "laundry", "mechanical", "utility", "garage"
                            ],
                            "description": "Room type"
                        },
                        "min_area": {
                            "type": "number",
                            "description": "Minimum area in square feet"
                        },
                        "name": {
                            "type": "string",
                            "description": "Optional custom name (e.g., 'Bedroom 2')"
                        }
                    },
                    "required": ["type", "min_area"]
                }
            },
            "level_name": {
                "type": "string",
                "description": "Revit level name (default: 'Level 1')"
            },
            "wall_height": {
                "type": "number",
                "description": "Wall height in feet (default: 10)"
            },
            "exterior_wall_type": {
                "type": "string",
                "description": "Revit wall type name for exterior walls"
            },
            "interior_wall_type": {
                "type": "string",
                "description": "Revit wall type name for interior partitions"
            },
            "wet_wall_type": {
                "type": "string",
                "description": "Revit wall type name for plumbing walls (thicker)"
            }
        },
        "required": ["width", "depth", "rooms", "exterior_wall_type", "interior_wall_type"]
    }
}


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    test_rooms = [
        {"type": "entry", "min_area": 50},
        {"type": "living", "min_area": 200},
        {"type": "dining", "min_area": 80},
        {"type": "kitchen", "min_area": 100},
        {"type": "primary_bedroom", "min_area": 150},
        {"type": "bedroom", "min_area": 100, "name": "Bedroom 2"},
        {"type": "bathroom", "min_area": 40},
        {"type": "laundry", "min_area": 35},
    ]

    # Test V3 Solver
    print("=" * 60)
    print("FLOOR PLAN TOOL TEST - V3 SOLVER")
    print("=" * 60)

    result = generate_floor_plan_walls(
        width=40,
        depth=30,
        rooms=test_rooms,
        level_name="Level 1",
        wall_height=10.0,
        exterior_wall_type="Generic - 8\" Masonry",
        interior_wall_type="Interior - 4 7/8\" Partition",
        wet_wall_type="Interior - 6 1/8\" Partition",
        solver_version="v3"
    )

    if result["success"]:
        print(f"\n[OK] Layout generated with {result.get('solver_version', 'v2')} solver!")
        print(f"   Score: {result['layout_score']:.1f}")

        if result.get("is_partial"):
            print(f"\n[PARTIAL] Warning: {result.get('warning', 'Some rooms not placed')}")

        print(f"\nSummary:")
        for k, v in result["summary"].items():
            print(f"   {k}: {v}")

        print(f"\nWalls batch preview (first 3):")
        for i, wall in enumerate(result["walls_batch"][:3]):
            print(f"   {i+1}. {wall['category']}: ({wall['start'][0]}, {wall['start'][1]}) -> ({wall['end'][0]}, {wall['end'][1]})")

        print(f"\nwalls_batch ready for /revit_mcp/create_walls_batch")
        print(f"   Total walls: {len(result['walls_batch'])}")

        # Show the JSON that would be sent to create_walls_batch
        print(f"\nSample payload for create_walls_batch:")
        sample = [w for w in result["walls_batch"] if w["wall_type"]][:2]
        print(json.dumps(sample, indent=2))

    else:
        print(f"[ERROR] {result['error']}")

    # Test V2 Solver for comparison
    print("\n" + "=" * 60)
    print("FLOOR PLAN TOOL TEST - V2 SOLVER (comparison)")
    print("=" * 60)

    result_v2 = generate_floor_plan_walls(
        width=40,
        depth=30,
        rooms=test_rooms,
        level_name="Level 1",
        wall_height=10.0,
        exterior_wall_type="Generic - 8\" Masonry",
        interior_wall_type="Interior - 4 7/8\" Partition",
        wet_wall_type="Interior - 6 1/8\" Partition",
        solver_version="v2"
    )

    if result_v2["success"]:
        print(f"\n[OK] V2 Layout generated!")
        print(f"   Score: {result_v2['layout_score']:.1f}")
        print(f"   Rooms: {result_v2['summary']['rooms_placed']}/{result_v2['summary']['rooms_requested']}")
    else:
        print(f"[ERROR] V2: {result_v2['error']}")