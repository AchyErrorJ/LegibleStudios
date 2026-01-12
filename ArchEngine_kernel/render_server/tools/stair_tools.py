"""
Stair Tools - Stair and railing creation functionality

These tools enable creating stairs, landings, and railings in Revit.
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

# Import validation
try:
    from .validation import (
        validate_point, validate_level_name, validate_positive,
        with_validation, ValidationError
    )
except ImportError:
    from validation import (
        validate_point, validate_level_name, validate_positive,
        with_validation, ValidationError
    )


# =============================================================================
# STAIR TYPES AND DISCOVERY
# =============================================================================

@mcp.tool()
@register_tool
async def list_stair_types(ctx: Context = None) -> str:
    """
    List all available stair types in the model.

    Returns:
        JSON array of stair types with IDs and names
    """
    response = await revit_get("/list_stair_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_railing_types(ctx: Context = None) -> str:
    """
    List all available railing types in the model.

    Returns:
        JSON array of railing types with IDs and names
    """
    response = await revit_get("/list_railing_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_stairs(
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List all stairs in the model, optionally filtered by level.

    Args:
        level_name: Optional level to filter by

    Returns:
        JSON array of stairs with IDs and properties
    """
    params = {}
    if level_name:
        params["level_name"] = level_name
    response = await revit_get("/list_stairs/", ctx, params=params)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_railings(
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List all railings in the model, optionally filtered by level.

    Args:
        level_name: Optional level to filter by

    Returns:
        JSON array of railings with IDs and properties
    """
    params = {}
    if level_name:
        params["level_name"] = level_name
    response = await revit_get("/list_railings/", ctx, params=params)
    return format_response(response)


# =============================================================================
# STAIR CREATION
# =============================================================================

@mcp.tool()
@register_tool
@with_validation
async def create_stair_by_run(
    base_level_name: str,
    top_level_name: str,
    start_point: List[float],
    end_point: List[float],
    width: float = 3.0,
    stair_type_name: Optional[str] = None,
    include_railing: bool = True,
    ctx: Context = None
) -> str:
    """
    Create a straight-run stair between two levels.

    Args:
        base_level_name: Name of the base level
        top_level_name: Name of the top level
        start_point: Starting point [x, y, z] in feet at base level
        end_point: Ending point [x, y, z] direction of run
        width: Stair width in feet (default 3.0)
        stair_type_name: Optional stair type name
        include_railing: Whether to add railings (default True)

    Returns:
        JSON with created stair info including element ID
    """
    # Validate inputs
    base_level = validate_level_name(base_level_name, "base_level_name")
    top_level = validate_level_name(top_level_name, "top_level_name")
    start = validate_point(start_point, "start_point")
    end = validate_point(end_point, "end_point")
    w = validate_positive(width, "width")

    payload = {
        "base_level_name": base_level,
        "top_level_name": top_level,
        "start_point": start,
        "end_point": end,
        "width": w,
        "stair_type_name": stair_type_name,
        "include_railing": include_railing
    }
    response = await revit_post("/create_stair_by_run/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_stair_by_sketch(
    base_level_name: str,
    top_level_name: str,
    boundary_points: List[List[float]],
    riser_lines: List[List[List[float]]],
    stair_type_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a stair from sketch lines (boundary and risers).

    Args:
        base_level_name: Name of the base level
        top_level_name: Name of the top level
        boundary_points: Boundary profile as list of [x, y, z] points
        riser_lines: List of riser lines, each as [[start], [end]]
        stair_type_name: Optional stair type name

    Returns:
        JSON with created stair info
    """
    payload = {
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "boundary_points": boundary_points,
        "riser_lines": riser_lines,
        "stair_type_name": stair_type_name
    }
    response = await revit_post("/create_stair_by_sketch/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_u_shaped_stair(
    base_level_name: str,
    top_level_name: str,
    start_point: List[float],
    first_run_direction: str = "X",
    width: float = 3.0,
    landing_length: float = 4.0,
    stair_type_name: Optional[str] = None,
    include_railing: bool = True,
    ctx: Context = None
) -> str:
    """
    Create a U-shaped stair with landing.

    Args:
        base_level_name: Name of the base level
        top_level_name: Name of the top level
        start_point: Starting point [x, y, z] in feet
        first_run_direction: Direction of first run - 'X', '-X', 'Y', or '-Y'
        width: Stair width in feet (default 3.0)
        landing_length: Landing length in feet (default 4.0)
        stair_type_name: Optional stair type name
        include_railing: Whether to add railings

    Returns:
        JSON with created stair info
    """
    payload = {
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "start_point": start_point,
        "first_run_direction": first_run_direction,
        "width": width,
        "landing_length": landing_length,
        "stair_type_name": stair_type_name,
        "include_railing": include_railing
    }
    response = await revit_post("/create_u_shaped_stair/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_l_shaped_stair(
    base_level_name: str,
    top_level_name: str,
    start_point: List[float],
    first_run_direction: str = "X",
    turn_direction: str = "left",
    width: float = 3.0,
    stair_type_name: Optional[str] = None,
    include_railing: bool = True,
    ctx: Context = None
) -> str:
    """
    Create an L-shaped stair with corner landing.

    Args:
        base_level_name: Name of the base level
        top_level_name: Name of the top level
        start_point: Starting point [x, y, z] in feet
        first_run_direction: Direction of first run - 'X', '-X', 'Y', or '-Y'
        turn_direction: 'left' or 'right' turn at landing
        width: Stair width in feet (default 3.0)
        stair_type_name: Optional stair type name
        include_railing: Whether to add railings

    Returns:
        JSON with created stair info
    """
    payload = {
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "start_point": start_point,
        "first_run_direction": first_run_direction,
        "turn_direction": turn_direction,
        "width": width,
        "stair_type_name": stair_type_name,
        "include_railing": include_railing
    }
    response = await revit_post("/create_l_shaped_stair/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_spiral_stair(
    base_level_name: str,
    top_level_name: str,
    center_point: List[float],
    radius: float,
    clockwise: bool = True,
    start_angle: float = 0.0,
    stair_type_name: Optional[str] = None,
    include_railing: bool = True,
    ctx: Context = None
) -> str:
    """
    Create a spiral/curved stair.

    Args:
        base_level_name: Name of the base level
        top_level_name: Name of the top level
        center_point: Center point [x, y, z] in feet
        radius: Outer radius in feet
        clockwise: True for clockwise, False for counter-clockwise
        start_angle: Starting angle in degrees (0 = East)
        stair_type_name: Optional stair type name
        include_railing: Whether to add railings

    Returns:
        JSON with created stair info
    """
    payload = {
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "center_point": center_point,
        "radius": radius,
        "clockwise": clockwise,
        "start_angle": start_angle,
        "stair_type_name": stair_type_name,
        "include_railing": include_railing
    }
    response = await revit_post("/create_spiral_stair/", payload, ctx)
    return format_response(response)


# =============================================================================
# STAIR MODIFICATION
# =============================================================================

@mcp.tool()
@register_tool
async def modify_stair_properties(
    stair_id: int,
    width: Optional[float] = None,
    riser_height: Optional[float] = None,
    tread_depth: Optional[float] = None,
    nosing_length: Optional[float] = None,
    ctx: Context = None
) -> str:
    """
    Modify properties of an existing stair.

    Args:
        stair_id: Element ID of the stair
        width: New width in feet
        riser_height: New riser height in inches
        tread_depth: New tread depth in inches
        nosing_length: New nosing length in inches

    Returns:
        JSON with updated stair properties
    """
    payload = {
        "stair_id": stair_id,
        "width": width,
        "riser_height": riser_height,
        "tread_depth": tread_depth,
        "nosing_length": nosing_length
    }
    response = await revit_post("/modify_stair_properties/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_stair_info(
    stair_id: int,
    ctx: Context = None
) -> str:
    """
    Get detailed information about a stair.

    Args:
        stair_id: Element ID of the stair

    Returns:
        JSON with stair properties including:
        - Number of risers and treads
        - Total rise and run
        - Width, riser height, tread depth
        - Base and top levels
        - Associated railings
    """
    payload = {"stair_id": stair_id}
    response = await revit_post("/get_stair_info/", payload, ctx)
    return format_response(response)


# =============================================================================
# RAILING CREATION
# =============================================================================

@mcp.tool()
@register_tool
async def create_railing(
    path_points: List[List[float]],
    level_name: str,
    railing_type_name: Optional[str] = None,
    host_stair_id: Optional[int] = None,
    ctx: Context = None
) -> str:
    """
    Create a railing along a path.

    Args:
        path_points: List of points [[x,y,z], ...] defining the railing path
        level_name: Name of the level
        railing_type_name: Optional railing type name
        host_stair_id: Optional stair ID to host the railing

    Returns:
        JSON with created railing info
    """
    payload = {
        "path_points": path_points,
        "level_name": level_name,
        "railing_type_name": railing_type_name,
        "host_stair_id": host_stair_id
    }
    response = await revit_post("/create_railing/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_railing_on_floor_edge(
    floor_id: int,
    edge_index: Optional[int] = None,
    railing_type_name: Optional[str] = None,
    offset: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Create a railing on the edge of a floor.

    Args:
        floor_id: Element ID of the floor
        edge_index: Optional specific edge index (None = all edges)
        railing_type_name: Optional railing type name
        offset: Offset from edge in feet

    Returns:
        JSON with created railing info
    """
    payload = {
        "floor_id": floor_id,
        "edge_index": edge_index,
        "railing_type_name": railing_type_name,
        "offset": offset
    }
    response = await revit_post("/create_railing_on_floor/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def modify_railing(
    railing_id: int,
    height: Optional[float] = None,
    offset: Optional[float] = None,
    railing_type_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Modify properties of an existing railing.

    Args:
        railing_id: Element ID of the railing
        height: New top rail height in feet
        offset: New offset from path in feet
        railing_type_name: New railing type name

    Returns:
        JSON with updated railing properties
    """
    payload = {
        "railing_id": railing_id,
        "height": height,
        "offset": offset,
        "railing_type_name": railing_type_name
    }
    response = await revit_post("/modify_railing/", payload, ctx)
    return format_response(response)


# =============================================================================
# STAIR LANDING
# =============================================================================

@mcp.tool()
@register_tool
async def add_stair_landing(
    stair_id: int,
    at_riser_number: int,
    landing_length: float = 4.0,
    ctx: Context = None
) -> str:
    """
    Add a landing to an existing stair at a specific riser.

    Args:
        stair_id: Element ID of the stair
        at_riser_number: Riser number where landing should be added
        landing_length: Landing length in feet

    Returns:
        JSON with updated stair info
    """
    payload = {
        "stair_id": stair_id,
        "at_riser_number": at_riser_number,
        "landing_length": landing_length
    }
    response = await revit_post("/add_stair_landing/", payload, ctx)
    return format_response(response)


# =============================================================================
# STAIR CODE COMPLIANCE
# =============================================================================

@mcp.tool()
@register_tool
async def check_stair_code_compliance(
    stair_id: int,
    code: str = "IBC2021",
    occupancy: str = "residential",
    ctx: Context = None
) -> str:
    """
    Check if a stair meets building code requirements.

    Args:
        stair_id: Element ID of the stair
        code: Building code to check against (IBC2021, IBC2018, IRC)
        occupancy: Occupancy type (residential, commercial, assembly)

    Returns:
        JSON with compliance results:
        - compliant: bool
        - violations: list of violations if any
        - warnings: list of warnings
        - measurements: actual vs required values
    """
    payload = {
        "stair_id": stair_id,
        "code": code,
        "occupancy": occupancy
    }
    response = await revit_post("/check_stair_code/", payload, ctx)
    return format_response(response)
