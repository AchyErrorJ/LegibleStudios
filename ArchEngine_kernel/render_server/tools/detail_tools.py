"""
Detail Tools - Detail lines, regions, components, and drafting views

These tools enable creating and managing detail elements including
lines, filled regions, detail components, and drafting views in Revit.
"""

import json
from typing import List, Optional, Union, Dict
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# Import shared helpers
try:
    from .geometry_tools import revit_post, revit_get, format_response
except ImportError:
    from geometry_tools import revit_post, revit_get, format_response


# =============================================================================
# LINE STYLES AND PATTERNS
# =============================================================================

@mcp.tool()
@register_tool
async def list_line_styles(ctx: Context = None) -> str:
    """
    List all available line styles in the model.

    Returns:
        JSON array of line styles with IDs, names, and properties
    """
    response = await revit_get("/list_line_styles/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_line_patterns(ctx: Context = None) -> str:
    """
    List all line patterns in the model.

    Returns:
        JSON array of line patterns with IDs and names
    """
    response = await revit_get("/list_line_patterns/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_fill_patterns(
    pattern_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List all fill patterns in the model.

    Args:
        pattern_type: Optional filter - 'Drafting' or 'Model'

    Returns:
        JSON array of fill patterns with IDs and names
    """
    params = {}
    if pattern_type:
        params["pattern_type"] = pattern_type
    response = await revit_get("/list_fill_patterns/", ctx, params=params)
    return format_response(response)


# =============================================================================
# DETAIL LINES
# =============================================================================

@mcp.tool()
@register_tool
async def create_detail_line(
    view_id: int,
    start_point: List[float],
    end_point: List[float],
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a detail line in a view.

    Args:
        view_id: Element ID of the view
        start_point: Start point [x, y] in view coordinates (feet)
        end_point: End point [x, y] in view coordinates
        line_style: Optional line style name

    Returns:
        JSON with created line info including element ID
    """
    payload = {
        "view_id": view_id,
        "start_point": start_point,
        "end_point": end_point,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_line/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_lines_batch(
    view_id: int,
    lines: List[Dict],
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create multiple detail lines in a single transaction.

    Args:
        view_id: Element ID of the view
        lines: List of line definitions, each containing:
            - start_point: [x, y]
            - end_point: [x, y]
            - line_style: optional str (overrides default)
        line_style: Default line style for all lines

    Returns:
        JSON with created lines info and count
    """
    payload = {
        "view_id": view_id,
        "lines": lines,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_lines_batch/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_arc(
    view_id: int,
    center_point: List[float],
    radius: float,
    start_angle: float,
    end_angle: float,
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a detail arc in a view.

    Args:
        view_id: Element ID of the view
        center_point: Center point [x, y] in view coordinates
        radius: Arc radius in feet
        start_angle: Start angle in degrees
        end_angle: End angle in degrees
        line_style: Optional line style name

    Returns:
        JSON with created arc info
    """
    payload = {
        "view_id": view_id,
        "center_point": center_point,
        "radius": radius,
        "start_angle": start_angle,
        "end_angle": end_angle,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_arc/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_circle(
    view_id: int,
    center_point: List[float],
    radius: float,
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a detail circle in a view.

    Args:
        view_id: Element ID of the view
        center_point: Center point [x, y] in view coordinates
        radius: Circle radius in feet
        line_style: Optional line style name

    Returns:
        JSON with created circle info
    """
    payload = {
        "view_id": view_id,
        "center_point": center_point,
        "radius": radius,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_circle/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_rectangle(
    view_id: int,
    corner1: List[float],
    corner2: List[float],
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a detail rectangle in a view.

    Args:
        view_id: Element ID of the view
        corner1: First corner [x, y]
        corner2: Opposite corner [x, y]
        line_style: Optional line style name

    Returns:
        JSON with created rectangle lines
    """
    payload = {
        "view_id": view_id,
        "corner1": corner1,
        "corner2": corner2,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_rectangle/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_polyline(
    view_id: int,
    points: List[List[float]],
    closed: bool = False,
    line_style: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a detail polyline (connected line segments) in a view.

    Args:
        view_id: Element ID of the view
        points: List of points [[x, y], [x, y], ...]
        closed: True to close the polyline
        line_style: Optional line style name

    Returns:
        JSON with created polyline info
    """
    payload = {
        "view_id": view_id,
        "points": points,
        "closed": closed,
        "line_style": line_style
    }
    response = await revit_post("/create_detail_polyline/", payload, ctx)
    return format_response(response)


# =============================================================================
# FILLED REGIONS
# =============================================================================

@mcp.tool()
@register_tool
async def list_filled_region_types(ctx: Context = None) -> str:
    """
    List all filled region types in the model.

    Returns:
        JSON array of filled region types with IDs and patterns
    """
    response = await revit_get("/list_filled_region_types/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_filled_region(
    view_id: int,
    boundary_points: List[List[float]],
    region_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a filled region in a view.

    Args:
        view_id: Element ID of the view
        boundary_points: List of boundary points [[x, y], ...]
        region_type: Optional filled region type name

    Returns:
        JSON with created region info
    """
    payload = {
        "view_id": view_id,
        "boundary_points": boundary_points,
        "region_type": region_type
    }
    response = await revit_post("/create_filled_region/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_filled_region_with_openings(
    view_id: int,
    outer_boundary: List[List[float]],
    openings: List[List[List[float]]],
    region_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Create a filled region with openings (holes).

    Args:
        view_id: Element ID of the view
        outer_boundary: Outer boundary points [[x, y], ...]
        openings: List of opening boundaries, each as [[x, y], ...]
        region_type: Optional filled region type name

    Returns:
        JSON with created region info
    """
    payload = {
        "view_id": view_id,
        "outer_boundary": outer_boundary,
        "openings": openings,
        "region_type": region_type
    }
    response = await revit_post("/create_filled_region_openings/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_masking_region(
    view_id: int,
    boundary_points: List[List[float]],
    ctx: Context = None
) -> str:
    """
    Create a masking region (white filled region to hide elements).

    Args:
        view_id: Element ID of the view
        boundary_points: List of boundary points [[x, y], ...]

    Returns:
        JSON with created region info
    """
    payload = {
        "view_id": view_id,
        "boundary_points": boundary_points
    }
    response = await revit_post("/create_masking_region/", payload, ctx)
    return format_response(response)


# =============================================================================
# DETAIL COMPONENTS
# =============================================================================

@mcp.tool()
@register_tool
async def list_detail_component_families(ctx: Context = None) -> str:
    """
    List all detail component families loaded in the model.

    Returns:
        JSON array of detail component families with types
    """
    response = await revit_get("/list_detail_component_families/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def place_detail_component(
    view_id: int,
    family_name: str,
    type_name: str,
    location: List[float],
    rotation: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Place a detail component in a view.

    Args:
        view_id: Element ID of the view
        family_name: Detail component family name
        type_name: Type name within the family
        location: Placement point [x, y] in view coordinates
        rotation: Rotation angle in degrees

    Returns:
        JSON with placed component info
    """
    payload = {
        "view_id": view_id,
        "family_name": family_name,
        "type_name": type_name,
        "location": location,
        "rotation": rotation
    }
    response = await revit_post("/place_detail_component/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def place_repeating_detail(
    view_id: int,
    detail_type: str,
    start_point: List[float],
    end_point: List[float],
    ctx: Context = None
) -> str:
    """
    Place a repeating detail along a line.

    Args:
        view_id: Element ID of the view
        detail_type: Repeating detail type name
        start_point: Start point [x, y]
        end_point: End point [x, y]

    Returns:
        JSON with placed repeating detail info
    """
    payload = {
        "view_id": view_id,
        "detail_type": detail_type,
        "start_point": start_point,
        "end_point": end_point
    }
    response = await revit_post("/place_repeating_detail/", payload, ctx)
    return format_response(response)


# =============================================================================
# DRAFTING VIEWS
# =============================================================================

@mcp.tool()
@register_tool
async def list_drafting_views(ctx: Context = None) -> str:
    """
    List all drafting views in the model.

    Returns:
        JSON array of drafting views with IDs, names, and scales
    """
    response = await revit_get("/list_drafting_views/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_drafting_view(
    name: str,
    scale: int = 96,
    ctx: Context = None
) -> str:
    """
    Create a new drafting view.

    Args:
        name: Name for the drafting view
        scale: View scale (e.g., 96 = 1/8" = 1'-0")

    Returns:
        JSON with created view info including element ID
    """
    payload = {
        "name": name,
        "scale": scale
    }
    response = await revit_post("/create_drafting_view/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def import_drafting_view(
    source_file_path: str,
    view_name: str,
    ctx: Context = None
) -> str:
    """
    Import a drafting view from another Revit file.

    Args:
        source_file_path: Path to source Revit file
        view_name: Name of the drafting view to import

    Returns:
        JSON with imported view info
    """
    payload = {
        "source_file_path": source_file_path,
        "view_name": view_name
    }
    response = await revit_post("/import_drafting_view/", payload, ctx)
    return format_response(response)


# =============================================================================
# DETAIL GROUPS
# =============================================================================

@mcp.tool()
@register_tool
async def list_detail_groups(ctx: Context = None) -> str:
    """
    List all detail group types in the model.

    Returns:
        JSON array of detail group types with IDs and names
    """
    response = await revit_get("/list_detail_groups/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_detail_group(
    view_id: int,
    element_ids: List[int],
    group_name: str,
    ctx: Context = None
) -> str:
    """
    Create a detail group from selected detail elements.

    Args:
        view_id: Element ID of the view containing elements
        element_ids: List of detail element IDs to group
        group_name: Name for the new group type

    Returns:
        JSON with created group info
    """
    payload = {
        "view_id": view_id,
        "element_ids": element_ids,
        "group_name": group_name
    }
    response = await revit_post("/create_detail_group/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def place_detail_group(
    view_id: int,
    group_type_name: str,
    location: List[float],
    rotation: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Place an instance of a detail group.

    Args:
        view_id: Element ID of the view
        group_type_name: Name of the detail group type
        location: Placement point [x, y]
        rotation: Rotation angle in degrees

    Returns:
        JSON with placed group info
    """
    payload = {
        "view_id": view_id,
        "group_type_name": group_type_name,
        "location": location,
        "rotation": rotation
    }
    response = await revit_post("/place_detail_group/", payload, ctx)
    return format_response(response)


# =============================================================================
# DETAIL LINE MODIFICATION
# =============================================================================

@mcp.tool()
@register_tool
async def change_line_style(
    element_ids: List[int],
    new_line_style: str,
    ctx: Context = None
) -> str:
    """
    Change the line style of detail lines.

    Args:
        element_ids: List of detail line element IDs
        new_line_style: Name of the new line style

    Returns:
        JSON with updated elements count
    """
    payload = {
        "element_ids": element_ids,
        "new_line_style": new_line_style
    }
    response = await revit_post("/change_line_style/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def offset_detail_line(
    element_id: int,
    offset_distance: float,
    create_copy: bool = False,
    ctx: Context = None
) -> str:
    """
    Offset a detail line.

    Args:
        element_id: Element ID of the detail line
        offset_distance: Offset distance in feet (positive = right side)
        create_copy: True to create a copy, False to move original

    Returns:
        JSON with resulting line info
    """
    payload = {
        "element_id": element_id,
        "offset_distance": offset_distance,
        "create_copy": create_copy
    }
    response = await revit_post("/offset_detail_line/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def trim_extend_detail_lines(
    line_ids: List[int],
    boundary_line_id: int,
    trim_or_extend: str = "trim",
    ctx: Context = None
) -> str:
    """
    Trim or extend detail lines to a boundary.

    Args:
        line_ids: List of line IDs to trim/extend
        boundary_line_id: Line ID to trim/extend to
        trim_or_extend: 'trim' or 'extend'

    Returns:
        JSON with modified lines info
    """
    payload = {
        "line_ids": line_ids,
        "boundary_line_id": boundary_line_id,
        "trim_or_extend": trim_or_extend
    }
    response = await revit_post("/trim_extend_lines/", payload, ctx)
    return format_response(response)


# =============================================================================
# BREAK LINES AND SYMBOLS
# =============================================================================

@mcp.tool()
@register_tool
async def place_break_line(
    view_id: int,
    start_point: List[float],
    end_point: List[float],
    break_line_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Place a break line symbol.

    Args:
        view_id: Element ID of the view
        start_point: Start point [x, y]
        end_point: End point [x, y]
        break_line_type: Optional break line type name

    Returns:
        JSON with placed break line info
    """
    payload = {
        "view_id": view_id,
        "start_point": start_point,
        "end_point": end_point,
        "break_line_type": break_line_type
    }
    response = await revit_post("/place_break_line/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def place_insulation(
    view_id: int,
    path_points: List[List[float]],
    width: float,
    ctx: Context = None
) -> str:
    """
    Place insulation batting symbol.

    Args:
        view_id: Element ID of the view
        path_points: List of points defining the path
        width: Insulation width in feet

    Returns:
        JSON with placed insulation info
    """
    payload = {
        "view_id": view_id,
        "path_points": path_points,
        "width": width
    }
    response = await revit_post("/place_insulation/", payload, ctx)
    return format_response(response)
