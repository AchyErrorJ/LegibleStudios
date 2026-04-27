"""
Structural Tools - Beams, columns, bracing, and foundations

These tools enable creating and modifying structural framing elements
including beams, columns, braces, and foundations in Revit.
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
        validate_element_id, with_validation, ValidationError
    )
except ImportError:
    from validation import (
        validate_point, validate_level_name, validate_positive,
        validate_element_id, with_validation, ValidationError
    )


# =============================================================================
# STRUCTURAL TYPE DISCOVERY
# =============================================================================

@mcp.tool()
@register_tool
async def list_beam_types(ctx: Context = None) -> str:
    """
    List all available structural framing (beam) types.

    Returns:
        JSON array of beam types with IDs, names, and section properties
    """
    response = await revit_get("/list_beam_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_column_types(ctx: Context = None) -> str:
    """
    List all available structural column types.

    Returns:
        JSON array of column types with IDs, names, and section properties
    """
    response = await revit_get("/list_column_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_brace_types(ctx: Context = None) -> str:
    """
    List all available structural brace types.

    Returns:
        JSON array of brace types with IDs and names
    """
    response = await revit_get("/list_brace_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_foundation_types(ctx: Context = None) -> str:
    """
    List all available foundation types (isolated, wall, slab).

    Returns:
        JSON array of foundation types with IDs and names
    """
    response = await revit_get("/list_foundation_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_structural_elements(
    category: Optional[str] = None,
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List structural elements in the model.

    Args:
        category: Optional filter - 'beams', 'columns', 'braces', 'foundations'
        level_name: Optional level filter

    Returns:
        JSON array of structural elements with IDs and properties
    """
    params = {}
    if category:
        params["category"] = category
    if level_name:
        params["level_name"] = level_name
    response = await revit_get("/list_structural_elements/", ctx, params=params)
    return format_response(response)


# =============================================================================
# BEAM CREATION
# =============================================================================

@mcp.tool()
@register_tool
@with_validation
async def create_beam(
    start_point: List[float],
    end_point: List[float],
    level_name: str,
    beam_type: Optional[str] = None,
    structural_usage: str = "Girder",
    ctx: Context = None
) -> str:
    """
    Create a structural beam between two points.

    Args:
        start_point: Start point [x, y, z] in feet
        end_point: End point [x, y, z] in feet
        level_name: Reference level name
        beam_type: Optional beam type name (e.g., "W12x26", "2x10")
        structural_usage: 'Girder', 'Joist', 'Purlin', or 'Other'

    Returns:
        JSON with created beam info including element ID
    """
    # Validate inputs
    start = validate_point(start_point, "start_point")
    end = validate_point(end_point, "end_point")
    level = validate_level_name(level_name)

    payload = {
        "start_point": start,
        "end_point": end,
        "level_name": level,
        "beam_type": beam_type,
        "structural_usage": structural_usage
    }
    response = await revit_post("/create_beam/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_beams_batch(
    beams: List[dict],
    ctx: Context = None
) -> str:
    """
    Create multiple beams in a single transaction.

    Args:
        beams: List of beam definitions, each containing:
            - start_point: [x, y, z]
            - end_point: [x, y, z]
            - level_name: str
            - beam_type: optional str
            - structural_usage: optional str

    Returns:
        JSON with created beams info and count
    """
    payload = {"beams": beams}
    response = await revit_post("/create_beams_batch/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_beam_system(
    boundary_points: List[List[float]],
    level_name: str,
    beam_type: str,
    direction_point: List[float],
    spacing: float,
    ctx: Context = None
) -> str:
    """
    Create a beam system (joists) within a boundary.

    Args:
        boundary_points: List of points defining the boundary
        level_name: Reference level name
        beam_type: Beam type for joists
        direction_point: Point indicating beam direction
        spacing: Spacing between beams in feet

    Returns:
        JSON with created beam system info
    """
    payload = {
        "boundary_points": boundary_points,
        "level_name": level_name,
        "beam_type": beam_type,
        "direction_point": direction_point,
        "spacing": spacing
    }
    response = await revit_post("/create_beam_system/", payload, ctx)
    return format_response(response)


# =============================================================================
# COLUMN CREATION
# =============================================================================

@mcp.tool()
@register_tool
@with_validation
async def create_column(
    location: List[float],
    base_level_name: str,
    top_level_name: Optional[str] = None,
    height: Optional[float] = None,
    column_type: Optional[str] = None,
    rotation: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Create a structural column.

    Args:
        location: Column location [x, y, z] in feet
        base_level_name: Base level name
        top_level_name: Top level name (if None, uses height)
        height: Column height in feet (if top_level not specified)
        column_type: Optional column type name (e.g., "W10x49", "HSS6x6x1/4")
        rotation: Rotation angle in degrees

    Returns:
        JSON with created column info including element ID
    """
    # Validate inputs
    loc = validate_point(location, "location")
    base_level = validate_level_name(base_level_name, "base_level_name")
    if height is not None:
        height = validate_positive(height, "height")

    payload = {
        "location": loc,
        "base_level_name": base_level,
        "top_level_name": top_level_name,
        "height": height,
        "column_type": column_type,
        "rotation": rotation
    }
    response = await revit_post("/create_column/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_columns_batch(
    columns: List[dict],
    ctx: Context = None
) -> str:
    """
    Create multiple columns in a single transaction.

    Args:
        columns: List of column definitions, each containing:
            - location: [x, y, z]
            - base_level_name: str
            - top_level_name: optional str
            - height: optional float
            - column_type: optional str
            - rotation: optional float

    Returns:
        JSON with created columns info and count
    """
    payload = {"columns": columns}
    response = await revit_post("/create_columns_batch/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_columns_at_grids(
    grid_intersections: bool = True,
    base_level_name: str = None,
    top_level_name: str = None,
    column_type: Optional[str] = None,
    grid_names: Optional[List[str]] = None,
    ctx: Context = None
) -> str:
    """
    Create columns at grid intersections.

    Args:
        grid_intersections: If True, place at intersections; if False, along grids
        base_level_name: Base level name
        top_level_name: Top level name
        column_type: Optional column type name
        grid_names: Optional list of specific grid names (None = all grids)

    Returns:
        JSON with created columns info
    """
    payload = {
        "grid_intersections": grid_intersections,
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "column_type": column_type,
        "grid_names": grid_names
    }
    response = await revit_post("/create_columns_at_grids/", payload, ctx)
    return format_response(response)


# =============================================================================
# BRACE CREATION
# =============================================================================

@mcp.tool()
@register_tool
async def create_brace(
    start_point: List[float],
    end_point: List[float],
    level_name: str,
    brace_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a structural brace.

    Args:
        start_point: Start point [x, y, z] in feet
        end_point: End point [x, y, z] in feet
        level_name: Reference level name
        brace_type: Optional brace type name

    Returns:
        JSON with created brace info including element ID
    """
    payload = {
        "start_point": start_point,
        "end_point": end_point,
        "level_name": level_name,
        "brace_type": brace_type
    }
    response = await revit_post("/create_brace/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_x_bracing(
    bay_start: List[float],
    bay_end: List[float],
    base_level_name: str,
    top_level_name: str,
    brace_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create X-bracing in a structural bay.

    Args:
        bay_start: One corner of the bay [x, y, z]
        bay_end: Opposite corner of the bay [x, y, z]
        base_level_name: Base level name
        top_level_name: Top level name
        brace_type: Optional brace type name

    Returns:
        JSON with created braces info
    """
    payload = {
        "bay_start": bay_start,
        "bay_end": bay_end,
        "base_level_name": base_level_name,
        "top_level_name": top_level_name,
        "brace_type": brace_type
    }
    response = await revit_post("/create_x_bracing/", payload, ctx)
    return format_response(response)


# =============================================================================
# FOUNDATION CREATION
# =============================================================================

@mcp.tool()
@register_tool
async def create_isolated_foundation(
    location: List[float],
    level_name: str,
    foundation_type: Optional[str] = None,
    host_column_id: Optional[int] = None,
    ctx: Context = None
) -> str:
    """
    Create an isolated (spread) foundation.

    Args:
        location: Foundation location [x, y, z] in feet
        level_name: Level name for the foundation
        foundation_type: Optional foundation type name
        host_column_id: Optional column ID to host under

    Returns:
        JSON with created foundation info
    """
    payload = {
        "location": location,
        "level_name": level_name,
        "foundation_type": foundation_type,
        "host_column_id": host_column_id
    }
    response = await revit_post("/create_isolated_foundation/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_wall_foundation(
    wall_id: int,
    foundation_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a wall foundation (continuous footing) under an existing wall.

    Args:
        wall_id: Element ID of the wall
        foundation_type: Optional wall foundation type name

    Returns:
        JSON with created foundation info
    """
    payload = {
        "wall_id": wall_id,
        "foundation_type": foundation_type
    }
    response = await revit_post("/create_wall_foundation/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_slab_foundation(
    boundary_points: List[List[float]],
    level_name: str,
    slab_type: Optional[str] = None,
    slope_arrow: Optional[dict] = None,
    ctx: Context = None
) -> str:
    """
    Create a foundation slab (mat foundation).

    Args:
        boundary_points: List of points defining the slab boundary
        level_name: Level name for the slab
        slab_type: Optional structural floor type name
        slope_arrow: Optional slope definition {"start": [x,y,z], "end": [x,y,z], "slope": 0.02}

    Returns:
        JSON with created slab info
    """
    payload = {
        "boundary_points": boundary_points,
        "level_name": level_name,
        "slab_type": slab_type,
        "slope_arrow": slope_arrow
    }
    response = await revit_post("/create_slab_foundation/", payload, ctx)
    return format_response(response)


# =============================================================================
# STRUCTURAL MODIFICATION
# =============================================================================

@mcp.tool()
@register_tool
async def modify_beam(
    beam_id: int,
    start_offset: Optional[float] = None,
    end_offset: Optional[float] = None,
    z_offset: Optional[float] = None,
    rotation: Optional[float] = None,
    beam_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Modify properties of an existing beam.

    Args:
        beam_id: Element ID of the beam
        start_offset: Offset from start in feet
        end_offset: Offset from end in feet
        z_offset: Vertical offset in feet
        rotation: Cross-section rotation in degrees
        beam_type: New beam type name

    Returns:
        JSON with updated beam properties
    """
    payload = {
        "beam_id": beam_id,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "z_offset": z_offset,
        "rotation": rotation,
        "beam_type": beam_type
    }
    response = await revit_post("/modify_beam/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def modify_column(
    column_id: int,
    base_offset: Optional[float] = None,
    top_offset: Optional[float] = None,
    rotation: Optional[float] = None,
    column_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Modify properties of an existing column.

    Args:
        column_id: Element ID of the column
        base_offset: Offset from base level in feet
        top_offset: Offset from top level in feet
        rotation: Column rotation in degrees
        column_type: New column type name

    Returns:
        JSON with updated column properties
    """
    payload = {
        "column_id": column_id,
        "base_offset": base_offset,
        "top_offset": top_offset,
        "rotation": rotation,
        "column_type": column_type
    }
    response = await revit_post("/modify_column/", payload, ctx)
    return format_response(response)


# =============================================================================
# STRUCTURAL CONNECTIONS
# =============================================================================

@mcp.tool()
@register_tool
async def create_beam_to_column_connection(
    beam_id: int,
    column_id: int,
    connection_type: str = "moment",
    ctx: Context = None
) -> str:
    """
    Create a connection between a beam and column.

    Args:
        beam_id: Element ID of the beam
        column_id: Element ID of the column
        connection_type: 'moment', 'shear', or 'pinned'

    Returns:
        JSON with connection info
    """
    payload = {
        "beam_id": beam_id,
        "column_id": column_id,
        "connection_type": connection_type
    }
    response = await revit_post("/create_beam_column_connection/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_beam_to_beam_connection(
    primary_beam_id: int,
    secondary_beam_id: int,
    connection_type: str = "cope",
    ctx: Context = None
) -> str:
    """
    Create a connection between two beams.

    Args:
        primary_beam_id: Element ID of the primary (supporting) beam
        secondary_beam_id: Element ID of the secondary (supported) beam
        connection_type: 'cope', 'notch', 'hanger', or 'welded'

    Returns:
        JSON with connection info
    """
    payload = {
        "primary_beam_id": primary_beam_id,
        "secondary_beam_id": secondary_beam_id,
        "connection_type": connection_type
    }
    response = await revit_post("/create_beam_beam_connection/", payload, ctx)
    return format_response(response)


# =============================================================================
# STRUCTURAL INFO
# =============================================================================

@mcp.tool()
@register_tool
async def get_structural_element_info(
    element_id: int,
    ctx: Context = None
) -> str:
    """
    Get detailed information about a structural element.

    Args:
        element_id: Element ID of the structural element

    Returns:
        JSON with properties including:
        - Section properties (area, moment of inertia, etc.)
        - Material properties
        - Geometry (length, height, rotation)
        - Connections
        - Analytical model info
    """
    payload = {"element_id": element_id}
    response = await revit_post("/get_structural_element_info/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_framing_schedule_data(
    category: Optional[str] = None,
    level_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Get structural framing schedule data.

    Args:
        category: Optional filter - 'beams', 'columns', 'braces'
        level_name: Optional level filter

    Returns:
        JSON with schedule data:
        - Element counts by type
        - Total lengths/weights
        - Section breakdown
    """
    payload = {
        "category": category,
        "level_name": level_name
    }
    response = await revit_post("/get_framing_schedule/", payload, ctx)
    return format_response(response)


# =============================================================================
# ANALYTICAL MODEL
# =============================================================================

@mcp.tool()
@register_tool
async def enable_analytical_model(
    element_id: int,
    ctx: Context = None
) -> str:
    """
    Enable the analytical model for a structural element.

    Args:
        element_id: Element ID of the structural element

    Returns:
        JSON with analytical model status
    """
    payload = {"element_id": element_id}
    response = await revit_post("/enable_analytical_model/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_analytical_model_geometry(
    element_id: int,
    ctx: Context = None
) -> str:
    """
    Get the analytical model geometry for a structural element.

    Args:
        element_id: Element ID of the structural element

    Returns:
        JSON with analytical geometry:
        - Start/end nodes
        - Member curve
        - Releases
        - Rigid zones
    """
    payload = {"element_id": element_id}
    response = await revit_post("/get_analytical_geometry/", payload, ctx)
    return format_response(response)
