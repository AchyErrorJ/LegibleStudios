"""
View Filter Tools - View filters, visibility/graphics overrides

These tools enable creating and managing view filters, visibility/graphics
overrides, and view templates in Revit.
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
# VIEW FILTER DISCOVERY
# =============================================================================

@mcp.tool()
@register_tool
async def list_view_filters(ctx: Context = None) -> str:
    """
    List all view filters defined in the model.

    Returns:
        JSON array of filters with IDs, names, and categories
    """
    response = await revit_get("/list_view_filters/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_filter_details(
    filter_id: int,
    ctx: Context = None
) -> str:
    """
    Get detailed information about a view filter.

    Args:
        filter_id: Element ID of the filter

    Returns:
        JSON with filter details:
        - Name
        - Categories it applies to
        - Filter rules/criteria
    """
    payload = {"filter_id": filter_id}
    response = await revit_post("/get_filter_details/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_filters_in_view(
    view_id: int,
    ctx: Context = None
) -> str:
    """
    List all filters applied to a specific view.

    Args:
        view_id: Element ID of the view

    Returns:
        JSON array of filters with visibility and override settings
    """
    payload = {"view_id": view_id}
    response = await revit_post("/list_filters_in_view/", payload, ctx)
    return format_response(response)


# =============================================================================
# VIEW FILTER CREATION
# =============================================================================

@mcp.tool()
@register_tool
async def create_selection_filter(
    name: str,
    element_ids: List[int],
    ctx: Context = None
) -> str:
    """
    Create a selection-based filter from selected elements.

    Args:
        name: Name for the new filter
        element_ids: List of element IDs to include in filter

    Returns:
        JSON with created filter info
    """
    payload = {
        "name": name,
        "element_ids": element_ids
    }
    response = await revit_post("/create_selection_filter/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_rule_filter(
    name: str,
    categories: List[str],
    rules: List[Dict],
    ctx: Context = None
) -> str:
    """
    Create a rule-based filter.

    Args:
        name: Name for the new filter
        categories: List of category names to filter (e.g., ['Walls', 'Floors'])
        rules: List of filter rules, each containing:
            - parameter: Parameter name
            - operator: 'equals', 'contains', 'greater_than', 'less_than', 'begins_with', 'ends_with'
            - value: Value to compare against

    Example:
        create_rule_filter(
            name="Exterior Walls",
            categories=["Walls"],
            rules=[{"parameter": "Function", "operator": "equals", "value": "Exterior"}]
        )

    Returns:
        JSON with created filter info
    """
    payload = {
        "name": name,
        "categories": categories,
        "rules": rules
    }
    response = await revit_post("/create_rule_filter/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_parameter_filter(
    name: str,
    categories: List[str],
    parameter_name: str,
    operator: str,
    value: Union[str, int, float],
    ctx: Context = None
) -> str:
    """
    Create a simple parameter-based filter (single rule).

    Args:
        name: Name for the new filter
        categories: List of category names to filter
        parameter_name: Name of the parameter to filter by
        operator: 'equals', 'not_equals', 'greater_than', 'less_than', 'contains', 'begins_with', 'ends_with'
        value: Value to compare against

    Returns:
        JSON with created filter info
    """
    payload = {
        "name": name,
        "categories": categories,
        "parameter_name": parameter_name,
        "operator": operator,
        "value": value
    }
    response = await revit_post("/create_parameter_filter/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def delete_filter(
    filter_id: int,
    ctx: Context = None
) -> str:
    """
    Delete a view filter from the model.

    Args:
        filter_id: Element ID of the filter

    Returns:
        JSON with deletion result
    """
    payload = {"filter_id": filter_id}
    response = await revit_post("/delete_filter/", payload, ctx)
    return format_response(response)


# =============================================================================
# FILTER APPLICATION
# =============================================================================

@mcp.tool()
@register_tool
async def add_filter_to_view(
    view_id: int,
    filter_id: int,
    visibility: bool = True,
    ctx: Context = None
) -> str:
    """
    Add a filter to a view.

    Args:
        view_id: Element ID of the view
        filter_id: Element ID of the filter
        visibility: Initial visibility setting (True = visible)

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "filter_id": filter_id,
        "visibility": visibility
    }
    response = await revit_post("/add_filter_to_view/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def remove_filter_from_view(
    view_id: int,
    filter_id: int,
    ctx: Context = None
) -> str:
    """
    Remove a filter from a view.

    Args:
        view_id: Element ID of the view
        filter_id: Element ID of the filter

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "filter_id": filter_id
    }
    response = await revit_post("/remove_filter_from_view/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_filter_visibility(
    view_id: int,
    filter_id: int,
    visible: bool,
    ctx: Context = None
) -> str:
    """
    Set filter visibility in a view.

    Args:
        view_id: Element ID of the view
        filter_id: Element ID of the filter
        visible: True to show filtered elements, False to hide

    Returns:
        JSON with updated settings
    """
    payload = {
        "view_id": view_id,
        "filter_id": filter_id,
        "visible": visible
    }
    response = await revit_post("/set_filter_visibility/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_filter_overrides(
    view_id: int,
    filter_id: int,
    projection_color: Optional[List[int]] = None,
    surface_color: Optional[List[int]] = None,
    cut_color: Optional[List[int]] = None,
    projection_pattern: Optional[str] = None,
    surface_pattern: Optional[str] = None,
    cut_pattern: Optional[str] = None,
    transparency: Optional[int] = None,
    halftone: Optional[bool] = None,
    ctx: Context = None
) -> str:
    """
    Set graphic overrides for a filter in a view.

    Args:
        view_id: Element ID of the view
        filter_id: Element ID of the filter
        projection_color: RGB color [R, G, B] for projection lines (0-255)
        surface_color: RGB color for surface/fill patterns
        cut_color: RGB color for cut lines
        projection_pattern: Pattern name for projection lines
        surface_pattern: Pattern name for surface fills
        cut_pattern: Pattern name for cut fills
        transparency: Transparency 0-100
        halftone: True to apply halftone

    Returns:
        JSON with updated settings
    """
    payload = {
        "view_id": view_id,
        "filter_id": filter_id,
        "projection_color": projection_color,
        "surface_color": surface_color,
        "cut_color": cut_color,
        "projection_pattern": projection_pattern,
        "surface_pattern": surface_pattern,
        "cut_pattern": cut_pattern,
        "transparency": transparency,
        "halftone": halftone
    }
    response = await revit_post("/set_filter_overrides/", payload, ctx)
    return format_response(response)


# =============================================================================
# VISIBILITY/GRAPHICS OVERRIDES
# =============================================================================

@mcp.tool()
@register_tool
async def get_category_visibility(
    view_id: int,
    category_name: str,
    ctx: Context = None
) -> str:
    """
    Get visibility settings for a category in a view.

    Args:
        view_id: Element ID of the view
        category_name: Name of the category (e.g., 'Walls', 'Doors')

    Returns:
        JSON with visibility and override settings
    """
    payload = {
        "view_id": view_id,
        "category_name": category_name
    }
    response = await revit_post("/get_category_visibility/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_category_visibility(
    view_id: int,
    category_name: str,
    visible: bool,
    ctx: Context = None
) -> str:
    """
    Set category visibility in a view.

    Args:
        view_id: Element ID of the view
        category_name: Name of the category
        visible: True to show, False to hide

    Returns:
        JSON with updated visibility
    """
    payload = {
        "view_id": view_id,
        "category_name": category_name,
        "visible": visible
    }
    response = await revit_post("/set_category_visibility/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_category_overrides(
    view_id: int,
    category_name: str,
    projection_color: Optional[List[int]] = None,
    surface_color: Optional[List[int]] = None,
    cut_color: Optional[List[int]] = None,
    projection_line_weight: Optional[int] = None,
    cut_line_weight: Optional[int] = None,
    transparency: Optional[int] = None,
    halftone: Optional[bool] = None,
    detail_level: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Set graphic overrides for a category in a view.

    Args:
        view_id: Element ID of the view
        category_name: Name of the category
        projection_color: RGB color [R, G, B] for projection lines
        surface_color: RGB color for surfaces
        cut_color: RGB color for cut lines
        projection_line_weight: Line weight 1-16
        cut_line_weight: Line weight 1-16
        transparency: Transparency 0-100
        halftone: True to apply halftone
        detail_level: 'Coarse', 'Medium', 'Fine'

    Returns:
        JSON with updated settings
    """
    payload = {
        "view_id": view_id,
        "category_name": category_name,
        "projection_color": projection_color,
        "surface_color": surface_color,
        "cut_color": cut_color,
        "projection_line_weight": projection_line_weight,
        "cut_line_weight": cut_line_weight,
        "transparency": transparency,
        "halftone": halftone,
        "detail_level": detail_level
    }
    response = await revit_post("/set_category_overrides/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def reset_category_overrides(
    view_id: int,
    category_name: str,
    ctx: Context = None
) -> str:
    """
    Reset category overrides to default in a view.

    Args:
        view_id: Element ID of the view
        category_name: Name of the category

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "category_name": category_name
    }
    response = await revit_post("/reset_category_overrides/", payload, ctx)
    return format_response(response)


# =============================================================================
# ELEMENT OVERRIDES
# =============================================================================

@mcp.tool()
@register_tool
async def set_element_override(
    view_id: int,
    element_id: int,
    projection_color: Optional[List[int]] = None,
    surface_color: Optional[List[int]] = None,
    transparency: Optional[int] = None,
    halftone: Optional[bool] = None,
    ctx: Context = None
) -> str:
    """
    Set graphic overrides for a specific element in a view.

    Args:
        view_id: Element ID of the view
        element_id: Element ID to override
        projection_color: RGB color for projection lines
        surface_color: RGB color for surfaces
        transparency: Transparency 0-100
        halftone: True to apply halftone

    Returns:
        JSON with updated settings
    """
    payload = {
        "view_id": view_id,
        "element_id": element_id,
        "projection_color": projection_color,
        "surface_color": surface_color,
        "transparency": transparency,
        "halftone": halftone
    }
    response = await revit_post("/set_element_override/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def hide_elements_in_view(
    view_id: int,
    element_ids: List[int],
    ctx: Context = None
) -> str:
    """
    Hide specific elements in a view.

    Args:
        view_id: Element ID of the view
        element_ids: List of element IDs to hide

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "element_ids": element_ids
    }
    response = await revit_post("/hide_elements/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def unhide_elements_in_view(
    view_id: int,
    element_ids: List[int],
    ctx: Context = None
) -> str:
    """
    Unhide specific elements in a view.

    Args:
        view_id: Element ID of the view
        element_ids: List of element IDs to unhide

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "element_ids": element_ids
    }
    response = await revit_post("/unhide_elements/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def isolate_elements_in_view(
    view_id: int,
    element_ids: List[int],
    ctx: Context = None
) -> str:
    """
    Isolate specific elements in a view (hide everything else).

    Args:
        view_id: Element ID of the view
        element_ids: List of element IDs to isolate

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "element_ids": element_ids
    }
    response = await revit_post("/isolate_elements/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def reset_temporary_hide_isolate(
    view_id: int,
    ctx: Context = None
) -> str:
    """
    Reset temporary hide/isolate in a view.

    Args:
        view_id: Element ID of the view

    Returns:
        JSON with result
    """
    payload = {"view_id": view_id}
    response = await revit_post("/reset_hide_isolate/", payload, ctx)
    return format_response(response)


# =============================================================================
# VIEW TEMPLATES
# =============================================================================

@mcp.tool()
@register_tool
async def list_view_templates(
    view_type: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List all view templates in the model.

    Args:
        view_type: Optional filter - 'FloorPlan', 'CeilingPlan', 'Section', 'Elevation', '3D'

    Returns:
        JSON array of templates with IDs and names
    """
    params = {}
    if view_type:
        params["view_type"] = view_type
    response = await revit_get("/list_view_templates/", ctx, params=params)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_view_template_from_view(
    view_id: int,
    template_name: str,
    ctx: Context = None
) -> str:
    """
    Create a view template from an existing view.

    Args:
        view_id: Element ID of the source view
        template_name: Name for the new template

    Returns:
        JSON with created template info
    """
    payload = {
        "view_id": view_id,
        "template_name": template_name
    }
    response = await revit_post("/create_view_template/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def apply_view_template(
    view_id: int,
    template_id: int,
    ctx: Context = None
) -> str:
    """
    Apply a view template to a view.

    Args:
        view_id: Element ID of the target view
        template_id: Element ID of the template

    Returns:
        JSON with result
    """
    payload = {
        "view_id": view_id,
        "template_id": template_id
    }
    response = await revit_post("/apply_view_template/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def remove_view_template(
    view_id: int,
    ctx: Context = None
) -> str:
    """
    Remove view template assignment from a view.

    Args:
        view_id: Element ID of the view

    Returns:
        JSON with result
    """
    payload = {"view_id": view_id}
    response = await revit_post("/remove_view_template/", payload, ctx)
    return format_response(response)


# =============================================================================
# WORKSET VISIBILITY
# =============================================================================

@mcp.tool()
@register_tool
async def list_worksets(ctx: Context = None) -> str:
    """
    List all worksets in the model.

    Returns:
        JSON array of worksets with IDs and names
    """
    response = await revit_get("/list_worksets/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_workset_visibility(
    view_id: int,
    workset_name: str,
    visible: bool,
    ctx: Context = None
) -> str:
    """
    Set workset visibility in a view.

    Args:
        view_id: Element ID of the view
        workset_name: Name of the workset
        visible: True to show, False to hide

    Returns:
        JSON with updated visibility
    """
    payload = {
        "view_id": view_id,
        "workset_name": workset_name,
        "visible": visible
    }
    response = await revit_post("/set_workset_visibility/", payload, ctx)
    return format_response(response)
