import httpx
import json
import logging
from typing import List, Optional, Union, Any
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# --- Configuration ---
# Port 48884 matches your Revit C# Server
REVIT_API_URL = "http://localhost:48884/revit_mcp"

# --- HELPER FUNCTIONS ---
async def revit_post(endpoint: str, payload: Any, ctx: Context = None) -> dict:
    """Standard helper to send POST requests."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"): url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=60.0)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

async def revit_get(endpoint: str, ctx: Context = None) -> dict:
    """Standard helper to send GET requests (Required for Listing types)."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"): url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

def format_response(response: Any) -> str:
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)

# =========================================================
# 1. DISCOVERY TOOLS - Moved to data_tools.py to avoid duplicates
# =========================================================
# list_wall_types, list_floor_types, list_roof_types, list_levels
# are now defined in data_tools.py (with caching support)

# =========================================================
# 2. CREATION TOOLS (Single & Batch)
# =========================================================

@mcp.tool()
@register_tool
async def create_level(elevation: float, name: str, ctx: Context = None) -> str:
    """Creates a new Level at a specific elevation."""
    payload = {"elevation": elevation, "name": name}
    response = await revit_post("/create_level/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_levels_batch(levels: List[dict], ctx: Context = None) -> str:
    """Creates MULTIPLE Levels in one transaction."""
    response = await revit_post("/create_levels_batch/", levels, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_wall(
    start_point: List[float],
    end_point: List[float],
    level_name: str,
    height: float = 10.0,
    wall_type: Optional[str] = None,
    flipped: bool = False,
    ctx: Context = None,
    **kwargs
) -> str:
    """Creates a SINGLE straight Wall."""
    # Arg Normalization
    final_type = wall_type or kwargs.get("type") or kwargs.get("family_symbol")
    
    payload = {
        "start_point": start_point, "end_point": end_point, 
        "level_name": level_name, "height": height, 
        "flipped": flipped, "wall_type": final_type
    }
    response = await revit_post("/create_wall/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_walls_batch(walls: List[dict], ctx: Context = None) -> str:
    """
    Creates MULTIPLE Walls in one transaction.
    Args: walls = [{"start_point": [0,0,0], "end_point": [10,0,0], "level_name": "L1", "height": 10}, ...]
    """
    clean_walls = []
    for w in walls:
        start = w.get("start_point") or w.get("start")
        end = w.get("end_point") or w.get("end")
        lvl = w.get("level_name") or w.get("level")
        
        if not start or not end or not lvl: continue
            
        clean_walls.append({
            "start_point": start, "end_point": end, "level_name": lvl,
            "height": w.get("height", 10.0),
            "wall_type": w.get("wall_type") or w.get("type"),
            "flipped": w.get("flipped", False)
        })

    if not clean_walls:
        return "Error: No valid walls found."

    response = await revit_post("/create_walls_batch/", clean_walls, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_floor(
    points: List[List[float]],
    level_name: str = None,
    floor_type: Optional[str] = None,
    ctx: Context = None,
    **kwargs
) -> str:
    """Creates a Floor from a list of boundary points."""
    # 🛡️ ARGUMENT REPAIR
    real_level = level_name or kwargs.get("level") or kwargs.get("host_level")
    real_type = floor_type or kwargs.get("type") or kwargs.get("floorType")
    
    if not real_level:
        return "Error: Missing 'level_name'. Please specify which level to place the floor on."

    payload = {"points": points, "level_name": real_level, "floor_type": real_type}
    response = await revit_post("/create_floor/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_roof(
    points: List[List[float]],
    level_name: str = None,
    roof_type: Optional[str] = None,
    slope_degrees: float = 0.0,
    ctx: Context = None,
    **kwargs
) -> str:
    """Creates a Roof from a footprint boundary."""
    # 🛡️ ARGUMENT REPAIR
    real_level = level_name or kwargs.get("level") or kwargs.get("base_level")
    real_type = roof_type or kwargs.get("type")
    
    if not real_level:
        return "Error: Missing 'level_name'."

    payload = {"points": points, "level_name": real_level, "roof_type": real_type, "slope_degrees": slope_degrees}
    response = await revit_post("/create_roof/", payload, ctx)
    return format_response(response)

# =========================================================
# 3. ROOMS (Single & Batch)
# =========================================================

@mcp.tool()
@register_tool
async def create_room(
    level_name: str,
    point: List[float],
    name: str = "Room",
    number: Optional[str] = None,
    auto_tag: bool = True,
    ctx: Context = None
) -> str:
    """Creates a Room object at a specific point."""
    payload = {
        "level_name": level_name, "point": point, 
        "name": name, "number": number, "auto_tag": auto_tag
    }
    response = await revit_post("/create_room/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_rooms_batch(rooms: List[dict], ctx: Context = None) -> str:
    """Creates MULTIPLE Rooms in one transaction."""
    response = await revit_post("/create_rooms_batch/", rooms, ctx)
    return format_response(response)

# =========================================================
# 4. ADVANCED MASSING
# =========================================================

@mcp.tool()
@register_tool
async def create_directshape_mass(
    points: List[List[float]],
    height: float,
    category_name: str = "Generic Models",
    base_offset: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Creates a 3D mass by extruding a 2D profile vertically.
    points: 2D base profile ONLY (Z=0).
    """
    payload = {
        "points": points, "height": height,
        "category_name": str(category_name), "base_offset": base_offset
    }
    response = await revit_post("/create_directshape_mass/", payload, ctx)
    return format_response(response)

# =========================================================
# 5. PLACEMENT TOOLS (Single & Batch)
# =========================================================

@mcp.tool()
@register_tool
async def place_family(
    family_name: str,
    type_name: str,
    point: List[float],
    level_name: str = None,
    ctx: Context = None,
    **kwargs
) -> str:
    """Places a FREESTANDING family instance (e.g., Furniture)."""
    real_level = level_name or kwargs.get("level") or kwargs.get("host")
    
    payload = {
        "family_name": family_name, "type_name": type_name,
        "point": point, "level_name": real_level
    }
    response = await revit_post("/place_family/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def place_door(
    host_id: int,
    point: List[float],
    family_name: str,
    type_name: str,
    ctx: Context = None
) -> str:
    """Places a DOOR hosted on a specific Wall."""
    payload = {
        "host_id": host_id, "point": point,
        "family_name": family_name, "type_name": type_name
    }
    response = await revit_post("/place_door/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def place_window(
    host_id: int,
    point: List[float],
    family_name: str,
    type_name: str,
    ctx: Context = None
) -> str:
    """Places a WINDOW hosted on a specific Wall."""
    payload = {
        "host_id": host_id, "point": point,
        "family_name": family_name, "type_name": type_name
    }
    response = await revit_post("/place_window/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def place_hosted_batch(elements: List[dict], ctx: Context = None) -> str:
    """
    Places MULTIPLE hosted elements (doors/windows) in one transaction.
    Args: elements = [{"host_id": 123, "point": [0,0,0], "family_name": "Single-Flush", ...}]
    """
    response = await revit_post("/place_hosted_batch/", elements, ctx)
    return format_response(response)


# =============================================================================
# ASSEMBLY TOOLS - Wall Type Creation and Assembly Views
# =============================================================================

@mcp.tool()
@register_tool
async def create_wall_type(
    name: str,
    layers: List[dict],
    ctx: Context = None
) -> str:
    """
    Creates a new wall type with specified layers.

    Args:
        name: Name for the new wall type
        layers: List of layer definitions, each with:
            - function: 'Structure', 'Thermal', 'Finish', 'Substrate', 'Membrane'
            - material: Material name (e.g., 'Wood - Stud', 'Gypsum Wall Board')
            - thickness: Thickness in feet (or use decimal inches / 12)

    Example:
        create_wall_type("Custom 2x6 Exterior", [
            {"function": "Finish", "material": "Gypsum Wall Board", "thickness": 0.0417},
            {"function": "Structure", "material": "Wood - Stud", "thickness": 0.4583},
            {"function": "Thermal", "material": "Batt Insulation", "thickness": 0.4583},
            {"function": "Finish", "material": "Exterior Sheathing", "thickness": 0.0625}
        ])
    """
    payload = {
        "name": name,
        "layers": layers
    }
    response = await revit_post("/create_wall_type/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_assembly_view(
    element_id: int,
    view_types: List[str] = None,
    ctx: Context = None
) -> str:
    """
    Creates assembly views for a wall or other compound element.

    Args:
        element_id: ID of the wall/floor/roof element
        view_types: List of view types to create - 'detail', 'section', 'plan', '3d'
                   Default: ['detail', 'section']

    Returns:
        Created assembly and view IDs
    """
    if view_types is None:
        view_types = ["detail", "section"]

    payload = {
        "element_id": element_id,
        "view_types": view_types
    }
    response = await revit_post("/create_assembly_view/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_wall_type_layers(wall_type_name: str, ctx: Context = None) -> str:
    """
    Gets the layer structure of an existing wall type.

    Args:
        wall_type_name: Name of the wall type to inspect

    Returns:
        List of layers with function, material, and thickness
    """
    payload = {"wall_type_name": wall_type_name}
    response = await revit_post("/get_wall_type_layers/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def duplicate_wall_type(
    source_name: str,
    new_name: str,
    layer_overrides: List[dict] = None,
    ctx: Context = None
) -> str:
    """
    Duplicates an existing wall type with optional layer modifications.

    Args:
        source_name: Name of wall type to copy
        new_name: Name for the new wall type
        layer_overrides: Optional list of layer modifications:
            - index: Layer index (0-based from exterior)
            - thickness: New thickness in feet
            - material: New material name

    Example:
        duplicate_wall_type("Basic Wall", "Thicker Basic Wall", [
            {"index": 1, "thickness": 0.5}  # Make structure layer thicker
        ])
    """
    payload = {
        "source_name": source_name,
        "new_name": new_name,
        "layer_overrides": layer_overrides or []
    }
    response = await revit_post("/duplicate_wall_type/", payload, ctx)
    return format_response(response)


    # --- Manual Registration to Server Registry ---
    mcp.tools_map["place_family"] = place_family
    mcp.tools_map["place_door"] = place_door
    mcp.tools_map["place_window"] = place_window
    mcp.tools_map["place_hosted_batch"] = place_hosted_batch
    mcp.tools_map["create_wall_type"] = create_wall_type
    mcp.tools_map["create_assembly_view"] = create_assembly_view
    mcp.tools_map["list_wall_type_layers"] = list_wall_type_layers
    mcp.tools_map["duplicate_wall_type"] = duplicate_wall_type
    mcp.tools_map["place_doors_batch"] = place_doors_batch
    mcp.tools_map["place_windows_batch"] = place_windows_batch
    mcp.tools_map["create_floor"] = create_floor
    mcp.tools_map["create_level"] = create_level
    mcp.tools_map["create_levels_batch"] = create_levels_batch
    mcp.tools_map["create_directshape_mass"] = create_directshape_mass
    mcp.tools_map["create_roof_footprint"] = create_roof_footprint
    mcp.tools_map["create_room"] = create_room
    mcp.tools_map["create_rooms_batch"] = create_rooms_batch
    mcp.tools_map["create_wall"] = create_wall
    mcp.tools_map["create_walls_batch"] = create_walls_batch