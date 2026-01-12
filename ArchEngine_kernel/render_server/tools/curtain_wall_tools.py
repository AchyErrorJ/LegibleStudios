"""
Curtain Wall Tools - Curtain wall, panel, and mullion functionality

These tools enable creating and modifying curtain walls, curtain systems,
curtain panels, and mullions in Revit.
"""

import json
from typing import List, Optional, Union
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# Import shared helpers
try:
    from .geometry_tools import revit_post, revit_get, format_response
except ImportError:
    from geometry_tools import revit_post, revit_get, format_response


# =============================================================================
# CURTAIN WALL TYPES AND DISCOVERY
# =============================================================================

@mcp.tool()
@register_tool
async def list_curtain_wall_types(ctx: Context = None) -> str:
    """
    List all available curtain wall types in the model.

    Returns:
        JSON array of curtain wall types with IDs, names, and grid patterns
    """
    response = await revit_get("/list_curtain_wall_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_curtain_panel_types(ctx: Context = None) -> str:
    """
    List all available curtain panel types in the model.

    Returns:
        JSON array of panel types (system panels, doors, etc.)
    """
    response = await revit_get("/list_curtain_panel_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_mullion_types(ctx: Context = None) -> str:
    """
    List all available mullion types in the model.

    Returns:
        JSON array of mullion types with IDs, names, and profiles
    """
    response = await revit_get("/list_mullion_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_curtain_walls(
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List all curtain walls in the model.

    Args:
        level_name: Optional level to filter by

    Returns:
        JSON array of curtain walls with IDs and properties
    """
    params = {}
    if level_name:
        params["level_name"] = level_name
    response = await revit_get("/list_curtain_walls/", ctx, params=params)
    return format_response(response)


# =============================================================================
# CURTAIN WALL CREATION
# =============================================================================

@mcp.tool()
@register_tool
async def create_curtain_wall(
    start_point: List[float],
    end_point: List[float],
    level_name: str,
    height: Optional[float] = None,
    curtain_wall_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a linear curtain wall.

    Args:
        start_point: Start point [x, y, z] in feet
        end_point: End point [x, y, z] in feet
        level_name: Name of the base level
        height: Wall height in feet (None = level-to-level)
        curtain_wall_type: Optional curtain wall type name

    Returns:
        JSON with created curtain wall info including element ID
    """
    payload = {
        "start_point": start_point,
        "end_point": end_point,
        "level_name": level_name,
        "height": height,
        "curtain_wall_type": curtain_wall_type
    }
    response = await revit_post("/create_curtain_wall/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_curtain_wall_by_profile(
    profile_points: List[List[float]],
    level_name: str,
    curtain_wall_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a curtain wall from a profile (non-rectangular shape).

    Args:
        profile_points: List of points defining the wall profile
        level_name: Name of the base level
        curtain_wall_type: Optional curtain wall type name

    Returns:
        JSON with created curtain wall info
    """
    payload = {
        "profile_points": profile_points,
        "level_name": level_name,
        "curtain_wall_type": curtain_wall_type
    }
    response = await revit_post("/create_curtain_wall_profile/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_curved_curtain_wall(
    center_point: List[float],
    radius: float,
    start_angle: float,
    end_angle: float,
    level_name: str,
    height: float,
    curtain_wall_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a curved curtain wall (arc segment).

    Args:
        center_point: Center of the arc [x, y, z] in feet
        radius: Radius of the arc in feet
        start_angle: Start angle in degrees
        end_angle: End angle in degrees
        level_name: Name of the base level
        height: Wall height in feet
        curtain_wall_type: Optional curtain wall type name

    Returns:
        JSON with created curtain wall info
    """
    payload = {
        "center_point": center_point,
        "radius": radius,
        "start_angle": start_angle,
        "end_angle": end_angle,
        "level_name": level_name,
        "height": height,
        "curtain_wall_type": curtain_wall_type
    }
    response = await revit_post("/create_curved_curtain_wall/", payload, ctx)
    return format_response(response)


# =============================================================================
# CURTAIN SYSTEM (SLOPED GLAZING)
# =============================================================================

@mcp.tool()
@register_tool
async def create_curtain_system_by_face(
    face_reference_ids: List[int],
    curtain_system_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a curtain system on selected faces (for skylights, sloped glazing).

    Args:
        face_reference_ids: List of face reference IDs
        curtain_system_type: Optional curtain system type name

    Returns:
        JSON with created curtain system info
    """
    payload = {
        "face_reference_ids": face_reference_ids,
        "curtain_system_type": curtain_system_type
    }
    response = await revit_post("/create_curtain_system_face/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_curtain_system_by_extrusion(
    profile_points: List[List[float]],
    extrusion_vector: List[float],
    level_name: str,
    curtain_system_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a curtain system by extruding a profile.

    Args:
        profile_points: List of points defining the base profile
        extrusion_vector: Direction and length of extrusion [x, y, z]
        level_name: Name of the base level
        curtain_system_type: Optional curtain system type name

    Returns:
        JSON with created curtain system info
    """
    payload = {
        "profile_points": profile_points,
        "extrusion_vector": extrusion_vector,
        "level_name": level_name,
        "curtain_system_type": curtain_system_type
    }
    response = await revit_post("/create_curtain_system_extrusion/", payload, ctx)
    return format_response(response)


# =============================================================================
# CURTAIN GRID OPERATIONS
# =============================================================================

@mcp.tool()
@register_tool
async def add_curtain_grid_line(
    curtain_wall_id: int,
    direction: str,
    position: float,
    ctx: Context = None
) -> str:
    """
    Add a grid line to a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall
        direction: 'horizontal' or 'vertical'
        position: Position along wall (0.0-1.0 as ratio, or absolute feet)

    Returns:
        JSON with created grid line info
    """
    payload = {
        "curtain_wall_id": curtain_wall_id,
        "direction": direction,
        "position": position
    }
    response = await revit_post("/add_curtain_grid/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def add_curtain_grid_lines_evenly(
    curtain_wall_id: int,
    direction: str,
    count: int,
    ctx: Context = None
) -> str:
    """
    Add evenly spaced grid lines to a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall
        direction: 'horizontal' or 'vertical'
        count: Number of grid lines to add

    Returns:
        JSON with created grid lines info
    """
    payload = {
        "curtain_wall_id": curtain_wall_id,
        "direction": direction,
        "count": count
    }
    response = await revit_post("/add_curtain_grid_even/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_curtain_grid_pattern(
    curtain_wall_id: int,
    horizontal_spacing: Optional[float] = None,
    vertical_spacing: Optional[float] = None,
    horizontal_justification: str = "Center",
    vertical_justification: str = "Center",
    ctx: Context = None
) -> str:
    """
    Set the grid pattern for a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall
        horizontal_spacing: Horizontal grid spacing in feet (None = no horizontal grids)
        vertical_spacing: Vertical grid spacing in feet (None = no vertical grids)
        horizontal_justification: 'Beginning', 'Center', or 'End'
        vertical_justification: 'Beginning', 'Center', or 'End'

    Returns:
        JSON with updated grid pattern
    """
    payload = {
        "curtain_wall_id": curtain_wall_id,
        "horizontal_spacing": horizontal_spacing,
        "vertical_spacing": vertical_spacing,
        "horizontal_justification": horizontal_justification,
        "vertical_justification": vertical_justification
    }
    response = await revit_post("/set_curtain_grid_pattern/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def delete_curtain_grid_line(
    grid_line_id: int,
    ctx: Context = None
) -> str:
    """
    Delete a curtain grid line.

    Args:
        grid_line_id: Element ID of the grid line

    Returns:
        JSON with deletion result
    """
    payload = {"grid_line_id": grid_line_id}
    response = await revit_post("/delete_curtain_grid/", payload, ctx)
    return format_response(response)


# =============================================================================
# CURTAIN PANEL OPERATIONS
# =============================================================================

@mcp.tool()
@register_tool
async def list_curtain_panels(
    curtain_wall_id: int,
    ctx: Context = None
) -> str:
    """
    List all panels in a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall

    Returns:
        JSON array of panels with IDs, types, and locations
    """
    payload = {"curtain_wall_id": curtain_wall_id}
    response = await revit_post("/list_curtain_panels/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def change_curtain_panel_type(
    panel_id: int,
    new_panel_type: str,
    ctx: Context = None
) -> str:
    """
    Change the type of a curtain panel.

    Args:
        panel_id: Element ID of the panel
        new_panel_type: Name of the new panel type

    Returns:
        JSON with updated panel info
    """
    payload = {
        "panel_id": panel_id,
        "new_panel_type": new_panel_type
    }
    response = await revit_post("/change_curtain_panel/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def replace_panel_with_door(
    panel_id: int,
    door_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Replace a curtain panel with a curtain wall door.

    Args:
        panel_id: Element ID of the panel to replace
        door_type: Optional curtain wall door type name

    Returns:
        JSON with new door info
    """
    payload = {
        "panel_id": panel_id,
        "door_type": door_type
    }
    response = await revit_post("/replace_panel_door/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_panel_transparency(
    panel_id: int,
    transparency: int,
    ctx: Context = None
) -> str:
    """
    Set the transparency of a curtain panel material.

    Args:
        panel_id: Element ID of the panel
        transparency: Transparency value 0-100

    Returns:
        JSON with updated panel info
    """
    payload = {
        "panel_id": panel_id,
        "transparency": transparency
    }
    response = await revit_post("/set_panel_transparency/", payload, ctx)
    return format_response(response)


# =============================================================================
# MULLION OPERATIONS
# =============================================================================

@mcp.tool()
@register_tool
async def add_mullion(
    grid_line_id: int,
    mullion_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Add a mullion to a curtain grid line.

    Args:
        grid_line_id: Element ID of the grid line
        mullion_type: Optional mullion type name

    Returns:
        JSON with created mullion info
    """
    payload = {
        "grid_line_id": grid_line_id,
        "mullion_type": mullion_type
    }
    response = await revit_post("/add_mullion/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def add_all_mullions(
    curtain_wall_id: int,
    horizontal_mullion_type: Optional[str] = None,
    vertical_mullion_type: Optional[str] = None,
    border_mullion_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Add mullions to all grid lines in a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall
        horizontal_mullion_type: Type for horizontal mullions
        vertical_mullion_type: Type for vertical mullions
        border_mullion_type: Type for border mullions (perimeter)

    Returns:
        JSON with created mullions info
    """
    payload = {
        "curtain_wall_id": curtain_wall_id,
        "horizontal_mullion_type": horizontal_mullion_type,
        "vertical_mullion_type": vertical_mullion_type,
        "border_mullion_type": border_mullion_type
    }
    response = await revit_post("/add_all_mullions/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def change_mullion_type(
    mullion_id: int,
    new_mullion_type: str,
    ctx: Context = None
) -> str:
    """
    Change the type of a mullion.

    Args:
        mullion_id: Element ID of the mullion
        new_mullion_type: Name of the new mullion type

    Returns:
        JSON with updated mullion info
    """
    payload = {
        "mullion_id": mullion_id,
        "new_mullion_type": new_mullion_type
    }
    response = await revit_post("/change_mullion_type/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def delete_mullion(
    mullion_id: int,
    ctx: Context = None
) -> str:
    """
    Delete a mullion from a curtain wall.

    Args:
        mullion_id: Element ID of the mullion

    Returns:
        JSON with deletion result
    """
    payload = {"mullion_id": mullion_id}
    response = await revit_post("/delete_mullion/", payload, ctx)
    return format_response(response)


# =============================================================================
# CURTAIN WALL INFO
# =============================================================================

@mcp.tool()
@register_tool
async def get_curtain_wall_info(
    curtain_wall_id: int,
    ctx: Context = None
) -> str:
    """
    Get detailed information about a curtain wall.

    Args:
        curtain_wall_id: Element ID of the curtain wall

    Returns:
        JSON with curtain wall properties including:
        - Dimensions (length, height, area)
        - Grid pattern and spacing
        - Panel count and types
        - Mullion count and types
        - Base/top constraints
    """
    payload = {"curtain_wall_id": curtain_wall_id}
    response = await revit_post("/get_curtain_wall_info/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_curtain_wall_schedule_data(
    curtain_wall_ids: Optional[List[int]] = None,
    ctx: Context = None
) -> str:
    """
    Get schedule data for curtain walls (panel areas, mullion lengths).

    Args:
        curtain_wall_ids: Optional list of curtain wall IDs (None = all)

    Returns:
        JSON with schedule data:
        - Total glazing area
        - Panel breakdown by type
        - Mullion lengths by type
        - Spandrel panel areas
    """
    payload = {"curtain_wall_ids": curtain_wall_ids}
    response = await revit_post("/curtain_wall_schedule_data/", payload, ctx)
    return format_response(response)
