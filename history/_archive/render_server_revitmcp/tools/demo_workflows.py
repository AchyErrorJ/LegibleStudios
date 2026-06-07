"""
Demo Workflow Tools for RevitMCP
=================================
High-level one-command tools for marketing demos.
These tools showcase the power of RevitMCP with simple commands.

Tools:
- create_floor_plan_from_description: NL description -> complete floor plan
- document_view: View -> dimensioned sheet placement
- create_room_sections: Generate sections through all rooms
"""

import httpx
import json
import re
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

REVIT_API_URL = "http://localhost:48884/revit_mcp"


async def revit_get(endpoint: str) -> dict:
    """GET request to Revit server."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


async def revit_post(endpoint: str, payload: Any) -> dict:
    """POST request to Revit server."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=60.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}


def format_response(response: Any) -> str:
    """Standard formatter for tool output."""
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)


def parse_description(description: str) -> Dict:
    """Parse natural language description into room requirements."""
    desc_lower = description.lower()

    # Parse bedroom count
    bed_match = re.search(r'(\d+)\s*(?:bed|bedroom|br)', desc_lower)
    bedrooms = int(bed_match.group(1)) if bed_match else 3

    # Parse bathroom count
    bath_match = re.search(r'(\d+)\s*(?:bath|bathroom|ba)', desc_lower)
    bathrooms = int(bath_match.group(1)) if bath_match else 2

    # Parse size
    size_match = re.search(r'(\d+)\s*(?:sqft|sq\s*ft|square\s*feet)', desc_lower)
    if size_match:
        target_sqft = int(size_match.group(1))
    else:
        # Estimate based on bedrooms
        target_sqft = 1200 + (bedrooms * 300)

    # Calculate dimensions (roughly 1.3:1 ratio)
    import math
    depth = int(math.sqrt(target_sqft / 1.3))
    width = int(target_sqft / depth)

    # Check for specific rooms
    has_garage = "garage" in desc_lower
    has_office = "office" in desc_lower or "study" in desc_lower
    open_concept = "open" in desc_lower

    return {
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "width": width,
        "depth": depth,
        "target_sqft": target_sqft,
        "has_garage": has_garage,
        "has_office": has_office,
        "open_concept": open_concept
    }


def generate_rooms(parsed: Dict) -> List[Dict]:
    """Generate room list from parsed description."""
    rooms = []
    total_area = parsed["width"] * parsed["depth"]

    # Core rooms
    rooms.append({"type": "entry", "min_area": max(40, int(total_area * 0.04))})
    rooms.append({"type": "living", "min_area": max(150, int(total_area * 0.18))})
    rooms.append({"type": "kitchen", "min_area": max(100, int(total_area * 0.12))})

    if not parsed["open_concept"]:
        rooms.append({"type": "dining", "min_area": max(80, int(total_area * 0.08))})

    # Bedrooms
    if parsed["bedrooms"] > 0:
        rooms.append({"type": "primary_bedroom", "min_area": max(140, int(total_area * 0.14))})
        for i in range(1, parsed["bedrooms"]):
            rooms.append({"type": "bedroom", "min_area": max(100, int(total_area * 0.10)), "name": f"Bedroom {i+1}"})

    # Bathrooms
    if parsed["bathrooms"] > 0:
        rooms.append({"type": "primary_bath", "min_area": max(50, int(total_area * 0.05))})
        for i in range(1, parsed["bathrooms"]):
            rooms.append({"type": "bathroom", "min_area": max(40, int(total_area * 0.04)), "name": f"Bathroom {i+1}"})

    # Optional rooms
    if parsed["has_office"]:
        rooms.append({"type": "office", "min_area": max(80, int(total_area * 0.08))})
    if parsed["has_garage"]:
        rooms.append({"type": "garage", "min_area": max(200, int(total_area * 0.15))})

    # Utility rooms
    rooms.append({"type": "hallway", "min_area": max(40, int(total_area * 0.05))})
    rooms.append({"type": "laundry", "min_area": max(30, int(total_area * 0.03))})

    return rooms


# =============================================================================
# DEMO TOOL 1: Create Floor Plan from Description
# =============================================================================

@mcp.tool()
@register_tool
async def create_floor_plan_from_description(
    description: str,
    ctx: Context = None
) -> str:
    """
    Create a complete floor plan from a natural language description.

    One command to create walls, doors, rooms, floor, roof, and dimensions!

    Examples:
    - "3 bedroom 2 bath house"
    - "2 bedroom apartment with open kitchen"
    - "4 bedroom house with garage and office, 2500 sqft"

    Args:
        description: Natural language description of the desired floor plan

    Returns:
        Complete floor plan creation summary
    """
    results = {
        "success": True,
        "description": description,
        "parsed": {},
        "steps_completed": [],
        "errors": []
    }

    # Step 1: Parse description
    parsed = parse_description(description)
    results["parsed"] = parsed
    rooms = generate_rooms(parsed)
    results["rooms_generated"] = len(rooms)

    width = parsed["width"]
    depth = parsed["depth"]
    wall_height = 10.0

    # Step 2: Create levels
    levels_result = await revit_post("/create_levels_batch", {
        "levels": [
            {"name": "Level 1", "elevation": 0.0},
            {"name": "Top of Wall", "elevation": wall_height}
        ]
    })
    results["steps_completed"].append("levels")

    # Step 3: Generate floor plan walls (uses solver)
    walls_result = await revit_post("/generate_floor_plan_walls", {
        "width": width,
        "depth": depth,
        "rooms": rooms,
        "level_name": "Level 1",
        "wall_height": wall_height
    })

    if walls_result.get("success"):
        results["walls_created"] = walls_result.get("summary", {}).get("total_walls", 0)
        results["rooms_placed"] = walls_result.get("summary", {}).get("rooms_placed", 0)
        results["steps_completed"].append("walls")

        # Step 4: Create floor
        floor_result = await revit_post("/create_floor", {
            "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
            "level_name": "Level 1"
        })
        results["steps_completed"].append("floor")

        # Step 5: Create roof
        roof_result = await revit_post("/create_roof_footprint", {
            "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
            "level_name": "Top of Wall",
            "slope_degrees": 0.0
        })
        results["steps_completed"].append("roof")

        # Step 6: Create doors from layout
        doors = walls_result.get("doors", [])
        if doors:
            doors_result = await revit_post("/create_doors_batch", {
                "doors": doors,
                "level_name": "Level 1"
            })
            results["doors_created"] = len(doors)
            results["steps_completed"].append("doors")

        # Step 7: Create floor plan view
        view_result = await revit_post("/create_floor_plan", {
            "level_name": "Level 1",
            "view_name": "Level 1 - Floor Plan"
        })
        results["steps_completed"].append("view")

        # Step 8: Auto-dimension everything
        from .auto_dimensions import auto_dimension_all
        dim_result = await auto_dimension_all(level_name="Level 1", ctx=ctx)
        dim_data = json.loads(dim_result) if isinstance(dim_result, str) else dim_result
        results["dimensions_created"] = dim_data.get("total_dimensions", 0)
        results["steps_completed"].append("dimensions")

    else:
        results["errors"].append(walls_result.get("error", "Wall generation failed"))
        results["success"] = False

    results["summary"] = (
        f"Created {parsed['bedrooms']} bed / {parsed['bathrooms']} bath floor plan "
        f"({width}x{depth} ft, {width*depth} sqft) with "
        f"{results.get('walls_created', 0)} walls, "
        f"{results.get('doors_created', 0)} doors, "
        f"{results.get('dimensions_created', 0)} dimensions"
    )

    return format_response(results)


# =============================================================================
# DEMO TOOL 2: Document View
# =============================================================================

@mcp.tool()
@register_tool
async def document_view(
    view_name: str,
    sheet_number: str = "A101",
    add_dimensions: bool = True,
    ctx: Context = None
) -> str:
    """
    One command to fully document a view: dimensions, tags, sheet placement.

    Takes a view and creates a complete documentation package.

    Args:
        view_name: Name of the view to document
        sheet_number: Sheet number to create (default: A101)
        add_dimensions: Whether to add dimensions (default: True)

    Returns:
        Documentation summary
    """
    results = {
        "success": True,
        "view_name": view_name,
        "steps_completed": [],
        "errors": []
    }

    # Step 1: Find the view
    views_response = await revit_get("/list_views")
    views = views_response if isinstance(views_response, list) else views_response.get("views", [])
    target_view = None
    for view in views:
        if view_name.lower() in view.get("name", "").lower():
            target_view = view
            break

    if not target_view:
        return format_response({
            "success": False,
            "error": f"View '{view_name}' not found"
        })

    view_id = target_view.get("id")
    level_name = target_view.get("level_name", "Level 1")
    results["view_id"] = view_id

    # Step 2: Add dimensions if requested
    if add_dimensions:
        from .auto_dimensions import auto_dimension_all
        dim_result = await auto_dimension_all(level_name=level_name, ctx=ctx)
        dim_data = json.loads(dim_result) if isinstance(dim_result, str) else dim_result
        results["dimensions_created"] = dim_data.get("total_dimensions", 0)
        results["steps_completed"].append("dimensions")

    # Step 3: Tag rooms
    rooms_tag = await revit_post("/tag_elements_batch", {
        "category": "Rooms",
        "level_name": level_name,
        "view_id": view_id
    })
    results["steps_completed"].append("room_tags")

    # Step 4: Tag doors
    doors_tag = await revit_post("/tag_elements_batch", {
        "category": "Doors",
        "level_name": level_name,
        "view_id": view_id
    })
    results["steps_completed"].append("door_tags")

    # Step 5: Create sheet
    sheet_result = await revit_post("/create_sheet", {
        "name": view_name,
        "number": sheet_number
    })
    sheet_id = sheet_result.get("sheet_id") or sheet_result.get("id")
    results["sheet_id"] = sheet_id
    results["steps_completed"].append("sheet")

    # Step 6: Place view on sheet
    place_result = await revit_post("/place_view_on_sheet", {
        "sheet_id": sheet_id,
        "view_id": view_id,
        "point": [1.5, 1.0, 0]
    })
    results["steps_completed"].append("placement")

    results["summary"] = (
        f"Documented '{view_name}' on sheet {sheet_number} "
        f"with {results.get('dimensions_created', 0)} dimensions"
    )

    return format_response(results)


# =============================================================================
# DEMO TOOL 3: Create Room Sections
# =============================================================================

@mcp.tool()
@register_tool
async def create_room_sections(
    level_name: Optional[str] = None,
    room_names: Optional[List[str]] = None,
    all_rooms: bool = False,
    ctx: Context = None
) -> str:
    """
    Generate section views through rooms automatically.

    Creates section cuts through the center of each room.

    Args:
        level_name: Level to get rooms from (default: lowest level)
        room_names: Specific room names to create sections for
        all_rooms: If True, create sections for all rooms (default: False)

    Returns:
        Summary of sections created
    """
    results = {
        "success": True,
        "level": level_name,
        "sections_created": [],
        "errors": []
    }

    # Step 1: Get level
    if not level_name:
        levels_response = await revit_get("/list_levels")
        levels = levels_response if isinstance(levels_response, list) else levels_response.get("levels", [])
        if levels:
            sorted_levels = sorted(levels, key=lambda x: x.get("elevation", 0))
            level_name = sorted_levels[0].get("name", "Level 1")
            results["level"] = level_name

    # Step 2: Get rooms
    rooms_response = await revit_post("/list_elements", {
        "category_name": "Rooms",
        "level_name": level_name
    })

    room_list = rooms_response if isinstance(rooms_response, list) else rooms_response.get("elements", [])

    if room_names:
        room_list = [r for r in room_list if r.get("name") in room_names]
    elif not all_rooms:
        # Default to first 5 rooms if not all_rooms
        room_list = room_list[:5]

    results["rooms_found"] = len(room_list)

    # Step 3: Create section for each room
    for room in room_list:
        room_name = room.get("name", f"Room {room.get('id')}")
        boundary = room.get("boundary") or room.get("bounding_box")

        if not boundary:
            # Try to get detailed info
            detail = await revit_post("/get_element_info", {"element_id": room.get("id")})
            boundary = detail.get("boundary") or detail.get("bounding_box")

        if boundary:
            # Calculate center point
            if isinstance(boundary, dict):
                min_pt = boundary.get("min", [0, 0, 0])
                max_pt = boundary.get("max", [0, 0, 0])
            else:
                xs = [p[0] for p in boundary]
                ys = [p[1] for p in boundary]
                min_pt = [min(xs), min(ys), 0]
                max_pt = [max(xs), max(ys), 0]

            center_x = (min_pt[0] + max_pt[0]) / 2
            center_y = (min_pt[1] + max_pt[1]) / 2

            # Create section (east-west cut through center)
            section_result = await revit_post("/create_section", {
                "start_point": [min_pt[0] - 2, center_y, 0],
                "end_point": [max_pt[0] + 2, center_y, 0],
                "height": 12.0,
                "view_name": f"Section - {room_name}"
            })

            if section_result.get("status") != "error":
                results["sections_created"].append({
                    "room_name": room_name,
                    "section_id": section_result.get("view_id") or section_result.get("id")
                })

    results["total_sections"] = len(results["sections_created"])
    results["summary"] = f"Created {results['total_sections']} section views through rooms on {level_name}"

    return format_response(results)
