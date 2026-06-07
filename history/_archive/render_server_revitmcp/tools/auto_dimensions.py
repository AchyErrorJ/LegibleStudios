"""
Auto-Dimension Tools for RevitMCP
==================================
Single-command dimension tools that internally execute multiple steps
to create professional architectural dimensions.

Tools:
- auto_dimension_walls: 3-tier wall dimensioning
- auto_dimension_rooms: Room boundary dimensions
- auto_dimension_openings: Door/window position dimensions
- auto_dimension_all: Complete dimensioning in one command
"""

import httpx
import json
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool
from .error_helpers import format_error_response, ErrorCategory

REVIT_API_URL = "http://localhost:48884/revit_mcp"


async def revit_get(endpoint: str) -> dict:
    """GET request to Revit server with improved error handling."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError as e:
            return format_error_response(e, f"GET {endpoint}")
        except httpx.TimeoutException as e:
            return format_error_response(e, f"GET {endpoint} (timeout)")
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def revit_post(endpoint: str, payload: Any) -> dict:
    """POST request to Revit server with improved error handling."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=45.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError as e:
            return format_error_response(e, f"POST {endpoint}")
        except httpx.TimeoutException as e:
            return format_error_response(e, f"POST {endpoint} (timeout)")
        except Exception as e:
            return {"status": "error", "message": str(e)}


def format_response(response: Any) -> str:
    """Standard formatter for tool output."""
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def group_walls_by_orientation(walls: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group walls into horizontal (runs along X) and vertical (runs along Y).

    Returns:
        {
            "horizontal": [wall_data, ...],  # Walls along X axis
            "vertical": [wall_data, ...]     # Walls along Y axis
        }
    """
    horizontal = []
    vertical = []

    for wall in walls:
        start = wall.get("start_point", wall.get("start", [0, 0, 0]))
        end = wall.get("end_point", wall.get("end", [0, 0, 0]))

        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])

        wall_data = {
            "id": wall.get("id") or wall.get("element_id"),
            "start": start,
            "end": end,
            "is_exterior": wall.get("is_exterior", False)
        }

        if dx > dy:
            # Horizontal wall (runs along X)
            wall_data["y_pos"] = (start[1] + end[1]) / 2
            horizontal.append(wall_data)
        else:
            # Vertical wall (runs along Y)
            wall_data["x_pos"] = (start[0] + end[0]) / 2
            vertical.append(wall_data)

    # Sort for consistent dimensioning
    horizontal.sort(key=lambda w: w["y_pos"])
    vertical.sort(key=lambda w: w["x_pos"])

    return {"horizontal": horizontal, "vertical": vertical}


def calculate_dimension_extents(walls: List[Dict]) -> Dict[str, float]:
    """Calculate the bounding box of walls for dimension line placement."""
    if not walls:
        return {"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}

    all_points = []
    for wall in walls:
        start = wall.get("start_point", wall.get("start", [0, 0, 0]))
        end = wall.get("end_point", wall.get("end", [0, 0, 0]))
        all_points.extend([start, end])

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys)
    }


async def get_or_create_floor_plan_view(level_name: str) -> Optional[int]:
    """
    Get existing floor plan view for level, or create one if it doesn't exist.

    Returns:
        View ID if found/created, None otherwise
    """
    # First, try to find an existing floor plan for this level
    views_response = await revit_get("/list_views")

    # Handle list response
    views = views_response if isinstance(views_response, list) else views_response.get("views", [])

    # Look for a FloorPlan view matching the level name (strict matching)
    level_lower = level_name.lower().strip()

    # First pass: exact match
    for view in views:
        view_type = view.get("type", "").lower()
        view_name = view.get("name", "").lower().strip()
        if "floorplan" in view_type.replace(" ", "") or view_type == "floorplan":
            # Exact match or view name equals level name
            if view_name == level_lower:
                print(f"   [DIM] Found exact view match: {view.get('name')} (ID: {view.get('id')})")
                return view.get("id")

    # Second pass: level name at word boundary (avoid "Level 1" matching "Level 10")
    import re
    level_pattern = re.compile(r'\b' + re.escape(level_lower) + r'\b', re.IGNORECASE)
    for view in views:
        view_type = view.get("type", "").lower()
        view_name = view.get("name", "")
        if "floorplan" in view_type.replace(" ", "") or view_type == "floorplan":
            if level_pattern.search(view_name):
                print(f"   [DIM] Found view: {view.get('name')} (ID: {view.get('id')})")
                return view.get("id")

    # No existing view found, create one
    print(f"   [DIM] Creating new floor plan view for {level_name}")
    create_response = await revit_post("/create_floor_plan", {
        "level_name": level_name,
        "view_name": f"{level_name} - Auto Dimensions"
    })

    if create_response.get("status") == "error":
        print(f"   [DIM] ERROR creating view: {create_response.get('message')}")
        return None

    view_id = create_response.get("view_id") or create_response.get("id")
    print(f"   [DIM] Created view ID: {view_id}")
    return view_id


# =============================================================================
# AUTO-DIMENSION WALLS
# =============================================================================

@mcp.tool()
@register_tool
async def auto_dimension_walls(
    level_name: Optional[str] = None,
    include_interior: bool = True,
    tier_1_offset: float = 3.0,
    tier_2_offset: float = 6.0,
    tier_3_offset: float = 9.0,
    ctx: Context = None
) -> str:
    """
    Automatically dimensions ALL walls on a level with professional 3-tier layout.

    Creates:
    - Tier 1 (3ft): Detail dimensions - all wall centerlines + openings
    - Tier 2 (6ft): Wall dimensions - all wall centerlines
    - Tier 3 (9ft): Overall dimensions - exterior walls only

    Args:
        level_name: Level to dimension (default: lowest level)
        include_interior: Include interior walls in Tier 1/2 (default: True)
        tier_1_offset: Detail dimension offset in feet (default: 3.0)
        tier_2_offset: Wall centerline offset in feet (default: 6.0)
        tier_3_offset: Overall dimension offset in feet (default: 9.0)

    Returns:
        Summary of dimensions created with element IDs
    """
    results = {
        "success": True,
        "level": level_name,
        "dimensions_created": [],
        "errors": []
    }

    # Step 1: Get level info if not specified
    if not level_name:
        levels_response = await revit_get("/list_levels")
        levels = levels_response if isinstance(levels_response, list) else levels_response.get("levels", [])
        if levels:
            # Get lowest level by elevation
            sorted_levels = sorted(levels, key=lambda x: x.get("elevation", 0))
            level_name = sorted_levels[0].get("name", "Level 1")
            results["level"] = level_name

    # Step 2: Get all walls and filter by level
    walls_response = await revit_get("/list_walls")

    # Handle both list and dict responses
    if isinstance(walls_response, list):
        all_walls = walls_response
    elif walls_response.get("status") == "error":
        return format_response({"success": False, "error": f"Could not get walls: {walls_response.get('message')}"})
    else:
        all_walls = walls_response.get("walls", [])

    # Filter walls by level (case-insensitive match)
    level_lower = level_name.lower().strip()
    walls = []
    for wall in all_walls:
        wall_level = wall.get("level", wall.get("level_name", "")).lower().strip()
        if wall_level == level_lower or level_lower in wall_level:
            walls.append(wall)

    print(f"   [DIM] Filtered {len(walls)} walls on '{level_name}' from {len(all_walls)} total walls")

    if not walls:
        return format_response({"success": False, "error": f"No walls found on {level_name}"})

    results["walls_found"] = len(walls)

    # Step 3: Get or create floor plan view
    view_id = await get_or_create_floor_plan_view(level_name)
    if not view_id:
        return format_response({"success": False, "error": f"Could not get or create floor plan view for {level_name}"})

    results["view_id"] = view_id

    # Step 4: Group walls by orientation
    grouped = group_walls_by_orientation(walls)
    extents = calculate_dimension_extents(walls)

    # Step 5: Get doors and windows for detail dimensions
    doors_response = await revit_post("/list_elements", {"category_name": "Doors", "level_name": level_name})
    windows_response = await revit_post("/list_elements", {"category_name": "Windows", "level_name": level_name})

    print(f"   [DIM] Doors response type: {type(doors_response).__name__}")
    print(f"   [DIM] Windows response type: {type(windows_response).__name__}")

    # Handle list or dict responses
    if isinstance(doors_response, list):
        doors = doors_response
    elif isinstance(doors_response, dict):
        doors = doors_response.get("elements", doors_response.get("doors", []))
        if doors_response.get("status") == "error":
            print(f"   [DIM] Doors error: {doors_response.get('message')}")
            doors = []
    else:
        doors = []

    if isinstance(windows_response, list):
        windows = windows_response
    elif isinstance(windows_response, dict):
        windows = windows_response.get("elements", windows_response.get("windows", []))
        if windows_response.get("status") == "error":
            print(f"   [DIM] Windows error: {windows_response.get('message')}")
            windows = []
    else:
        windows = []

    print(f"   [DIM] Found {len(doors)} doors, {len(windows)} windows")

    door_ids = [d.get("id") or d.get("element_id") for d in doors if d.get("id") or d.get("element_id")]
    window_ids = [w.get("id") or w.get("element_id") for w in windows if w.get("id") or w.get("element_id")]

    print(f"   [DIM] Door IDs: {door_ids}")
    print(f"   [DIM] Window IDs: {window_ids}")

    # Step 6: Create horizontal dimensions (below south wall)
    horiz_walls = grouped["horizontal"]
    vert_walls = grouped["vertical"]

    print(f"   [DIM] Found {len(horiz_walls)} horizontal walls, {len(vert_walls)} vertical walls")

    if vert_walls:
        # Get wall IDs for vertical walls
        vert_ids = [w["id"] for w in vert_walls if w.get("id")]
        exterior_vert_ids = [w["id"] for w in vert_walls if w.get("is_exterior") and w.get("id")]

        # Fallback: if no exterior walls, use outermost walls for overall dimension
        if len(exterior_vert_ids) < 2 and len(vert_ids) >= 2:
            print(f"   [DIM] No exterior walls found, using outermost walls for overall dimension")
            # Use first and last wall (sorted by x_pos)
            exterior_vert_ids = [vert_walls[0]["id"], vert_walls[-1]["id"]]

        # Tier 3: Overall (exterior/outermost) - furthest from building
        if len(exterior_vert_ids) >= 2:
            print(f"   [DIM] Creating horizontal overall dimension with {len(exterior_vert_ids)} walls")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": exterior_vert_ids,
                "start_point": [extents["min_x"] - 10, extents["min_y"] - tier_3_offset, 0],
                "end_point": [extents["max_x"] + 10, extents["min_y"] - tier_3_offset, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating overall dim: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"horizontal_overall: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "horizontal_overall",
                    "tier": 3,
                    "offset": tier_3_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

        # Tier 2: All walls
        if include_interior and len(vert_ids) >= 2:
            print(f"   [DIM] Creating horizontal walls dimension with {len(vert_ids)} walls")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": vert_ids,
                "start_point": [extents["min_x"] - 10, extents["min_y"] - tier_2_offset, 0],
                "end_point": [extents["max_x"] + 10, extents["min_y"] - tier_2_offset, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating walls dim: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"horizontal_walls: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "horizontal_walls",
                    "tier": 2,
                    "offset": tier_2_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

        # Tier 1: Walls + openings (detail)
        detail_ids = vert_ids + door_ids + window_ids
        if len(detail_ids) >= 2:
            print(f"   [DIM] Creating horizontal detail dimension with {len(detail_ids)} elements")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": detail_ids,
                "start_point": [extents["min_x"] - 10, extents["min_y"] - tier_1_offset, 0],
                "end_point": [extents["max_x"] + 10, extents["min_y"] - tier_1_offset, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating detail dim: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"horizontal_detail: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "horizontal_detail",
                    "tier": 1,
                    "offset": tier_1_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

    # Step 7: Create vertical dimensions (left of west wall)
    if horiz_walls:
        horiz_ids = [w["id"] for w in horiz_walls if w.get("id")]
        exterior_horiz_ids = [w["id"] for w in horiz_walls if w.get("is_exterior") and w.get("id")]

        # Fallback: if no exterior walls, use outermost walls
        if len(exterior_horiz_ids) < 2 and len(horiz_ids) >= 2:
            print(f"   [DIM] No exterior horizontal walls, using outermost walls")
            exterior_horiz_ids = [horiz_walls[0]["id"], horiz_walls[-1]["id"]]

        # Tier 3: Overall (exterior/outermost)
        if len(exterior_horiz_ids) >= 2:
            print(f"   [DIM] Creating vertical overall dimension with {len(exterior_horiz_ids)} walls")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": exterior_horiz_ids,
                "start_point": [extents["min_x"] - tier_3_offset, extents["min_y"] - 10, 0],
                "end_point": [extents["min_x"] - tier_3_offset, extents["max_y"] + 10, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating vertical overall: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"vertical_overall: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "vertical_overall",
                    "tier": 3,
                    "offset": tier_3_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

        # Tier 2: All walls
        if include_interior and len(horiz_ids) >= 2:
            print(f"   [DIM] Creating vertical walls dimension with {len(horiz_ids)} walls")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": horiz_ids,
                "start_point": [extents["min_x"] - tier_2_offset, extents["min_y"] - 10, 0],
                "end_point": [extents["min_x"] - tier_2_offset, extents["max_y"] + 10, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating vertical walls: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"vertical_walls: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "vertical_walls",
                    "tier": 2,
                    "offset": tier_2_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

        # Tier 1: Walls + openings
        detail_ids = horiz_ids + door_ids + window_ids
        if len(detail_ids) >= 2:
            print(f"   [DIM] Creating vertical detail dimension with {len(detail_ids)} elements")
            dim_result = await revit_post("/create_dimension", {
                "element_ids": detail_ids,
                "start_point": [extents["min_x"] - tier_1_offset, extents["min_y"] - 10, 0],
                "end_point": [extents["min_x"] - tier_1_offset, extents["max_y"] + 10, 0],
                "view_id": view_id
            })
            if dim_result.get("status") == "error":
                print(f"   [DIM] ERROR creating vertical detail: {dim_result.get('message', dim_result.get('error'))}")
                results["errors"].append(f"vertical_detail: {dim_result.get('message', dim_result.get('error'))}")
            else:
                results["dimensions_created"].append({
                    "type": "vertical_detail",
                    "tier": 1,
                    "offset": tier_1_offset,
                    "id": dim_result.get("dimension", {}).get("id") or dim_result.get("dimension_id")
                })

    results["total_dimensions"] = len(results["dimensions_created"])
    results["summary"] = f"Created {results['total_dimensions']} dimension strings on {level_name}"

    return format_response(results)


# =============================================================================
# AUTO-DIMENSION ROOMS
# =============================================================================

@mcp.tool()
@register_tool
async def auto_dimension_rooms(
    level_name: Optional[str] = None,
    room_ids: Optional[List[int]] = None,
    offset: float = 1.0,
    ctx: Context = None
) -> str:
    """
    Automatically dimensions room boundaries (width and depth for each room).

    Args:
        level_name: Level to dimension (default: lowest level)
        room_ids: Specific room IDs to dimension (default: all rooms on level)
        offset: Distance inside room boundary for dimension lines (default: 1.0 ft)

    Returns:
        Summary of room dimensions created
    """
    results = {
        "success": True,
        "level": level_name,
        "rooms_dimensioned": [],
        "errors": []
    }

    # Step 1: Get level info if not specified
    if not level_name:
        levels = await revit_get("/list_levels")
        if levels.get("levels"):
            sorted_levels = sorted(levels["levels"], key=lambda x: x.get("elevation", 0))
            level_name = sorted_levels[0].get("name", "Level 1")
            results["level"] = level_name

    # Step 2: Get rooms on level
    rooms_response = await revit_post("/list_elements", {
        "category_name": "Rooms",
        "level_name": level_name
    })

    # Handle list or dict responses
    rooms = rooms_response if isinstance(rooms_response, list) else rooms_response.get("elements", [])
    if room_ids:
        rooms = [r for r in rooms if r.get("id") in room_ids]

    if not rooms:
        return format_response({"success": False, "error": f"No rooms found on {level_name}"})

    results["rooms_found"] = len(rooms)

    # Step 3: Get or create floor plan view
    view_id = await get_or_create_floor_plan_view(level_name)

    # Step 4: Dimension each room
    for room in rooms:
        room_id = room.get("id")
        room_name = room.get("name", f"Room {room_id}")

        # Get room boundary (bounding box or boundary segments)
        boundary = room.get("boundary") or room.get("bounding_box")
        if not boundary:
            # Try to get detailed room info
            room_detail = await revit_post("/get_element_info", {"element_id": room_id})
            boundary = room_detail.get("boundary") or room_detail.get("bounding_box")

        if boundary:
            # Extract min/max from boundary
            if isinstance(boundary, dict):
                min_pt = boundary.get("min", [0, 0, 0])
                max_pt = boundary.get("max", [0, 0, 0])
            else:
                # Assume list of points
                xs = [p[0] for p in boundary]
                ys = [p[1] for p in boundary]
                min_pt = [min(xs), min(ys), 0]
                max_pt = [max(xs), max(ys), 0]

            # Create width dimension (horizontal)
            width_dim = await revit_post("/create_dimension", {
                "element_ids": [room_id],  # Room reference
                "start_point": [min_pt[0], min_pt[1] + offset, 0],
                "end_point": [max_pt[0], min_pt[1] + offset, 0],
                "view_id": view_id
            })

            # Create depth dimension (vertical)
            depth_dim = await revit_post("/create_dimension", {
                "element_ids": [room_id],
                "start_point": [min_pt[0] + offset, min_pt[1], 0],
                "end_point": [min_pt[0] + offset, max_pt[1], 0],
                "view_id": view_id
            })

            results["rooms_dimensioned"].append({
                "room_id": room_id,
                "room_name": room_name,
                "width_dim_id": width_dim.get("dimension_id"),
                "depth_dim_id": depth_dim.get("dimension_id")
            })

    results["total_rooms_dimensioned"] = len(results["rooms_dimensioned"])
    results["summary"] = f"Dimensioned {results['total_rooms_dimensioned']} rooms on {level_name}"

    return format_response(results)


# =============================================================================
# AUTO-DIMENSION OPENINGS
# =============================================================================

@mcp.tool()
@register_tool
async def auto_dimension_openings(
    level_name: Optional[str] = None,
    wall_ids: Optional[List[int]] = None,
    include_doors: bool = True,
    include_windows: bool = True,
    offset: float = 2.0,
    ctx: Context = None
) -> str:
    """
    Automatically dimensions door and window positions from wall ends.

    Creates chain dimensions showing opening positions relative to wall endpoints.

    Args:
        level_name: Level to dimension (default: lowest level)
        wall_ids: Specific walls to dimension openings for (default: all walls)
        include_doors: Include door dimensions (default: True)
        include_windows: Include window dimensions (default: True)
        offset: Dimension line offset from wall (default: 2.0 ft)

    Returns:
        Summary of opening dimensions created
    """
    results = {
        "success": True,
        "level": level_name,
        "openings_dimensioned": [],
        "errors": []
    }

    # Step 1: Get level info if not specified
    if not level_name:
        levels = await revit_get("/list_levels")
        if levels.get("levels"):
            sorted_levels = sorted(levels["levels"], key=lambda x: x.get("elevation", 0))
            level_name = sorted_levels[0].get("name", "Level 1")
            results["level"] = level_name

    # Step 2: Get walls and filter by level
    walls_response = await revit_get("/list_walls")
    if isinstance(walls_response, list):
        all_walls = walls_response
    else:
        all_walls = walls_response.get("walls", [])

    # Filter by level
    level_lower = level_name.lower().strip()
    walls = []
    for wall in all_walls:
        wall_level = wall.get("level", wall.get("level_name", "")).lower().strip()
        if wall_level == level_lower or level_lower in wall_level:
            walls.append(wall)

    print(f"   [DIM-OPEN] Filtered {len(walls)} walls on '{level_name}' from {len(all_walls)} total")

    if wall_ids:
        walls = [w for w in walls if w.get("id") in wall_ids]

    if not walls:
        return format_response({"success": False, "error": f"No walls found on {level_name}"})

    # Step 3: Get view
    view_id = await get_or_create_floor_plan_view(level_name)

    # Step 4: Get openings
    openings = []

    if include_doors:
        doors_response = await revit_post("/list_elements", {
            "category_name": "Doors",
            "level_name": level_name
        })
        print(f"   [DIM-OPEN] Doors response: {type(doors_response).__name__}")
        if isinstance(doors_response, list):
            doors_list = doors_response
        elif isinstance(doors_response, dict):
            doors_list = doors_response.get("elements", doors_response.get("doors", []))
        else:
            doors_list = []
        print(f"   [DIM-OPEN] Found {len(doors_list)} doors")
        for door in doors_list:
            door["opening_type"] = "door"
            openings.append(door)

    if include_windows:
        windows_response = await revit_post("/list_elements", {
            "category_name": "Windows",
            "level_name": level_name
        })
        print(f"   [DIM-OPEN] Windows response: {type(windows_response).__name__}")
        if isinstance(windows_response, list):
            windows_list = windows_response
        elif isinstance(windows_response, dict):
            windows_list = windows_response.get("elements", windows_response.get("windows", []))
        else:
            windows_list = []
        print(f"   [DIM-OPEN] Found {len(windows_list)} windows")
        for window in windows_list:
            window["opening_type"] = "window"
            openings.append(window)

    results["openings_found"] = len(openings)
    print(f"   [DIM-OPEN] Total openings: {len(openings)}")

    # Step 5: Group openings by host wall
    wall_openings = {}
    for opening in openings:
        host_id = opening.get("host_id") or opening.get("wall_id") or opening.get("host")
        opening_id = opening.get("id") or opening.get("element_id")
        print(f"   [DIM-OPEN] Opening {opening_id}: host_id={host_id}, keys={list(opening.keys())}")
        if host_id:
            if host_id not in wall_openings:
                wall_openings[host_id] = []
            wall_openings[host_id].append(opening)

    print(f"   [DIM-OPEN] Openings grouped by {len(wall_openings)} walls")

    # Step 6: Create chain dimensions for each wall with openings
    for wall in walls:
        wall_id = wall.get("id")
        if wall_id not in wall_openings:
            continue

        # Get wall endpoints
        start = wall.get("start_point", wall.get("start", [0, 0, 0]))
        end = wall.get("end_point", wall.get("end", [0, 0, 0]))

        # Determine wall orientation
        dx = abs(end[0] - start[0])
        dy = abs(end[1] - start[1])
        is_horizontal = dx > dy

        # Build element ID list: wall start + openings + wall end
        opening_ids = [o.get("id") for o in wall_openings[wall_id] if o.get("id")]
        element_ids = [wall_id] + opening_ids

        # Calculate dimension line position
        if is_horizontal:
            # Horizontal wall - dimension line below
            y_offset = min(start[1], end[1]) - offset
            dim_start = [min(start[0], end[0]) - 2, y_offset, 0]
            dim_end = [max(start[0], end[0]) + 2, y_offset, 0]
        else:
            # Vertical wall - dimension line to left
            x_offset = min(start[0], end[0]) - offset
            dim_start = [x_offset, min(start[1], end[1]) - 2, 0]
            dim_end = [x_offset, max(start[1], end[1]) + 2, 0]

        # Create dimension
        dim_result = await revit_post("/create_dimension", {
            "element_ids": element_ids,
            "start_point": dim_start,
            "end_point": dim_end,
            "view_id": view_id
        })

        if dim_result.get("status") != "error":
            results["openings_dimensioned"].append({
                "wall_id": wall_id,
                "opening_count": len(opening_ids),
                "dimension_id": dim_result.get("dimension_id")
            })

    results["walls_with_openings_dimensioned"] = len(results["openings_dimensioned"])
    results["summary"] = f"Created opening dimensions for {results['walls_with_openings_dimensioned']} walls"

    return format_response(results)


# =============================================================================
# AUTO-DIMENSION ALL
# =============================================================================

@mcp.tool()
@register_tool
async def auto_dimension_all(
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Complete one-command dimensioning: walls, rooms, and openings.

    Executes:
    1. auto_dimension_walls (3-tier professional layout)
    2. auto_dimension_rooms (room width/depth)
    3. auto_dimension_openings (door/window positions)

    Args:
        level_name: Level to dimension (default: lowest level)

    Returns:
        Combined summary of all dimensions created
    """
    results = {
        "success": True,
        "level": level_name,
        "wall_dimensions": None,
        "room_dimensions": None,
        "opening_dimensions": None,
        "total_dimensions": 0
    }

    # Step 1: Auto-dimension walls
    walls_result = await auto_dimension_walls(level_name=level_name, ctx=ctx)
    walls_data = json.loads(walls_result) if isinstance(walls_result, str) else walls_result
    results["wall_dimensions"] = walls_data
    results["level"] = walls_data.get("level", level_name)

    if walls_data.get("success"):
        results["total_dimensions"] += walls_data.get("total_dimensions", 0)

    # Step 2: Auto-dimension rooms
    rooms_result = await auto_dimension_rooms(level_name=results["level"], ctx=ctx)
    rooms_data = json.loads(rooms_result) if isinstance(rooms_result, str) else rooms_result
    results["room_dimensions"] = rooms_data

    if rooms_data.get("success"):
        results["total_dimensions"] += rooms_data.get("total_rooms_dimensioned", 0) * 2  # Width + depth

    # Step 3: Auto-dimension openings
    openings_result = await auto_dimension_openings(level_name=results["level"], ctx=ctx)
    openings_data = json.loads(openings_result) if isinstance(openings_result, str) else openings_result
    results["opening_dimensions"] = openings_data

    if openings_data.get("success"):
        results["total_dimensions"] += openings_data.get("walls_with_openings_dimensioned", 0)

    results["summary"] = (
        f"Complete dimensioning on {results['level']}: "
        f"{walls_data.get('total_dimensions', 0)} wall dims, "
        f"{rooms_data.get('total_rooms_dimensioned', 0)} rooms, "
        f"{openings_data.get('walls_with_openings_dimensioned', 0)} opening chains"
    )

    return format_response(results)
