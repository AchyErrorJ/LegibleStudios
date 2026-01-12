"""
Smart Tool Selector - Reduces context for local LLMs

Instead of loading all 278 tools, this module:
1. Maintains a lightweight tool index with keywords
2. Analyzes user queries to find relevant tools
3. Returns only matching tool schemas

Usage:
    from tools.tool_selector import select_tools_for_query, get_core_tools

    # Get tools relevant to a query
    tools = select_tools_for_query("create a beam between columns")
    # Returns: ['create_beam', 'list_beam_types', 'create_column', ...]

    # Get the always-loaded core tools
    core = get_core_tools()
"""

import json
from typing import List, Dict, Set, Optional
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool, TOOL_FUNCTIONS

# =============================================================================
# TOOL INDEX - Keywords mapped to tool names
# =============================================================================

TOOL_INDEX = {
    # GEOMETRY - Walls
    "wall": ["create_wall", "create_walls_batch", "list_walls", "list_wall_types", "modify_wall"],
    "walls": ["create_wall", "create_walls_batch", "list_walls", "list_wall_types"],

    # GEOMETRY - Floors
    "floor": ["create_floor", "create_floor_opening", "list_floors", "list_floor_types"],
    "slab": ["create_floor", "list_floor_types"],

    # GEOMETRY - Roofs
    "roof": ["create_roof", "list_roof_types", "create_roof_opening"],

    # GEOMETRY - Levels
    "level": ["create_level", "create_levels_batch", "list_levels"],
    "elevation": ["create_level", "list_levels", "create_elevation"],

    # DOORS & WINDOWS
    "door": ["place_door", "list_door_types", "list_doors"],
    "window": ["place_window", "list_window_types", "list_windows"],
    "opening": ["place_door", "place_window", "create_floor_opening", "create_wall_opening"],

    # STRUCTURAL
    "beam": ["create_beam", "create_beams_batch", "create_beam_system", "list_beam_types", "modify_beam"],
    "column": ["create_column", "create_columns_batch", "create_columns_at_grids", "list_column_types"],
    "brace": ["create_brace", "create_x_bracing", "list_brace_types"],
    "structural": ["create_beam", "create_column", "create_brace", "list_structural_elements", "analyze_beam"],
    "framing": ["create_beam", "create_beam_system", "list_beam_types"],
    "joist": ["create_beam_system", "create_beam"],
    "foundation": ["create_isolated_foundation", "create_wall_foundation", "create_slab_foundation", "list_foundation_types"],
    "footing": ["create_isolated_foundation", "create_wall_foundation", "list_foundation_types"],

    # STAIRS & RAILINGS
    "stair": ["create_stair_by_run", "create_u_shaped_stair", "create_l_shaped_stair", "create_spiral_stair", "list_stair_types", "list_stairs"],
    "stairs": ["create_stair_by_run", "create_u_shaped_stair", "create_l_shaped_stair", "list_stair_types"],
    "railing": ["create_railing", "create_railing_on_floor_edge", "list_railing_types", "list_railings"],
    "handrail": ["create_railing", "list_railing_types"],

    # CURTAIN WALLS
    "curtain": ["create_curtain_wall", "create_curved_curtain_wall", "list_curtain_wall_types", "list_curtain_walls"],
    "curtain wall": ["create_curtain_wall", "add_curtain_grid_line", "add_all_mullions", "list_curtain_wall_types"],
    "mullion": ["add_mullion", "add_all_mullions", "change_mullion_type", "list_mullion_types"],
    "panel": ["change_curtain_panel_type", "replace_panel_with_door", "list_curtain_panel_types"],
    "storefront": ["create_curtain_wall", "list_curtain_wall_types"],
    "glazing": ["create_curtain_wall", "create_curtain_system_by_face"],

    # EXPORT
    "export": ["export_dwg", "export_pdf", "export_ifc", "export_image", "export_fbx"],
    "dwg": ["export_dwg", "export_dwg_sheets", "list_dwg_export_setups"],
    "pdf": ["export_pdf", "export_sheets_to_pdf", "print_to_pdf"],
    "ifc": ["export_ifc", "export_ifc_with_mapping"],
    "image": ["export_image", "export_images_batch"],
    "png": ["export_image"],
    "render": ["export_image", "export_fbx"],

    # IMPORT
    "import": ["import_cad", "link_cad", "import_image", "import_ifc"],
    "cad": ["import_cad", "link_cad", "list_linked_cad", "reload_cad_link", "get_cad_layers"],
    "dwg import": ["import_cad", "link_cad"],
    "link": ["link_cad", "link_revit", "link_point_cloud", "list_revit_links"],
    "point cloud": ["link_point_cloud", "list_point_clouds", "set_point_cloud_visibility"],
    "xref": ["link_cad", "link_revit"],

    # VIEWS
    "view": ["list_views", "create_floor_plan", "create_section", "create_elevation", "create_3d_view"],
    "plan": ["create_floor_plan", "list_views"],
    "section": ["create_section", "list_views"],
    "3d": ["create_3d_view", "export_fbx"],
    "perspective": ["create_3d_view"],

    # SHEETS
    "sheet": ["create_sheet", "create_sheets_batch", "list_sheets", "place_view_on_sheet"],
    "titleblock": ["create_sheet", "list_titleblocks"],

    # SCHEDULES
    "schedule": ["create_schedule", "add_schedule_fields", "set_schedule_sorting", "list_schedules", "export_schedule_to_csv"],
    "takeoff": ["create_schedule", "export_schedule_to_csv", "export_schedule_to_excel"],
    "quantity": ["create_schedule", "export_schedule_to_csv"],

    # ANNOTATION
    "dimension": ["create_dimension", "auto_dimension_all", "create_aligned_dimension"],
    "tag": ["tag_element", "tag_all_in_view", "list_tag_types"],
    "text": ["create_text_note", "list_text_types"],
    "annotation": ["create_dimension", "tag_element", "create_text_note"],

    # VIEW FILTERS
    "filter": ["create_rule_filter", "create_parameter_filter", "add_filter_to_view", "list_view_filters", "set_filter_overrides"],
    "visibility": ["set_category_visibility", "hide_elements_in_view", "isolate_elements_in_view"],
    "override": ["set_filter_overrides", "set_category_overrides", "set_element_override"],
    "hide": ["hide_elements_in_view", "set_category_visibility"],
    "isolate": ["isolate_elements_in_view"],
    "template": ["list_view_templates", "apply_view_template", "create_view_template_from_view"],

    # DETAIL
    "detail": ["create_detail_line", "create_detail_arc", "create_filled_region", "place_detail_component", "create_drafting_view"],
    "detail line": ["create_detail_line", "create_detail_lines_batch", "create_detail_polyline"],
    "filled region": ["create_filled_region", "create_filled_region_with_openings", "list_filled_region_types"],
    "drafting": ["create_drafting_view", "list_drafting_views"],
    "line style": ["list_line_styles", "change_line_style"],

    # GRIDS
    "grid": ["create_grid", "create_grids_batch", "list_grids"],

    # ROOMS & AREAS
    "room": ["create_room", "list_rooms", "get_room_boundaries"],
    "area": ["create_area", "list_areas"],

    # PARAMETERS
    "parameter": ["get_element_parameters", "set_element_parameter", "list_parameters"],
    "property": ["get_element_parameters", "set_element_parameter"],

    # ANALYSIS
    "analyze": ["analyze_beam", "analyze_column", "analyze_thermal_assembly", "calculate_heat_loss"],
    "thermal": ["analyze_thermal_assembly", "calculate_heat_loss", "get_assembly_details"],
    "structural analysis": ["analyze_beam", "analyze_column", "estimate_fasteners"],
    "heat loss": ["calculate_heat_loss"],
    "r-value": ["analyze_thermal_assembly", "get_assembly_details"],

    # FAMILIES & FURNITURE
    "family": ["search_family_library", "load_family", "place_family", "list_families", "list_family_types"],
    "load": ["load_family"],
    "type": ["list_wall_types", "list_door_types", "list_window_types", "list_floor_types"],
    "furniture": ["list_furniture_types", "search_family_library", "place_family"],
    "bed": ["list_furniture_types", "search_family_library", "place_family"],
    "chair": ["list_furniture_types", "search_family_library", "place_family"],
    "desk": ["list_furniture_types", "search_family_library", "place_family"],
    "table": ["list_furniture_types", "search_family_library", "place_family"],
    "sofa": ["list_furniture_types", "search_family_library", "place_family"],
    "couch": ["list_furniture_types", "search_family_library", "place_family"],
    "cabinet": ["list_furniture_types", "search_family_library", "place_family"],
    "appliance": ["list_furniture_types", "search_family_library", "place_family"],
    "fixture": ["list_furniture_types", "search_family_library", "place_family"],
    "place": ["place_family", "place_door", "place_window"],

    # META / SYSTEM INFO
    "how many": ["get_system_info"],
    "tools": ["get_system_info", "select_tools", "list_tool_categories"],
    "status": ["get_system_info", "get_revit_status"],
    "info": ["get_system_info"],
    "help": ["get_system_info", "list_tool_categories"],
    "capabilities": ["get_system_info", "list_tool_categories"],
    "what can": ["get_system_info", "list_tool_categories"],

    # GENERAL
    "delete": ["delete_elements", "delete_element"],
    "move": ["move_element", "move_elements"],
    "copy": ["copy_element", "copy_elements"],
    "rotate": ["rotate_element"],
    "select": ["get_selected_elements", "select_elements"],
    "undo": ["undo_last"],
}

# =============================================================================
# CORE TOOLS - Always loaded for local LLM mode
# =============================================================================

CORE_TOOLS = [
    # System info - always available for meta questions
    "get_system_info",
    "select_tools",
    "list_tool_categories",

    # Discovery - essential for understanding the model
    "list_levels",
    "list_walls",
    "list_views",
    "list_wall_types",
    "list_door_types",
    "list_window_types",
    "list_floor_types",
    "list_families",
    "get_element_parameters",
    "get_revit_status",

    # Basic creation - most common operations
    "create_wall",
    "create_floor",
    "create_level",
    "place_door",
    "place_window",
]

# =============================================================================
# CATEGORY DEFINITIONS
# =============================================================================

TOOL_CATEGORIES = {
    "geometry": "Walls, floors, roofs, levels, openings",
    "structural": "Beams, columns, braces, foundations",
    "stairs": "Stairs, railings, landings",
    "curtain_walls": "Curtain walls, mullions, panels, grids",
    "doors_windows": "Doors, windows, hosted elements",
    "views": "Floor plans, sections, elevations, 3D views",
    "sheets": "Sheets, titleblocks, view placement",
    "annotation": "Dimensions, tags, text notes",
    "schedules": "Schedules, quantities, takeoffs",
    "export": "DWG, PDF, IFC, image export",
    "import": "CAD, point cloud, Revit links",
    "filters": "View filters, visibility, overrides",
    "detail": "Detail lines, filled regions, drafting",
    "analysis": "Structural analysis, thermal analysis",
    "parameters": "Element parameters, properties",
}


# =============================================================================
# SELECTOR FUNCTIONS
# =============================================================================

def select_tools_for_query(query: str, max_tools: int = 15) -> List[str]:
    """
    Analyze a query and return relevant tool names.

    Args:
        query: User's natural language query
        max_tools: Maximum number of tools to return

    Returns:
        List of tool names relevant to the query
    """
    query_lower = query.lower()
    matched_tools: Set[str] = set()

    # Check each keyword
    for keyword, tools in TOOL_INDEX.items():
        if keyword in query_lower:
            matched_tools.update(tools)

    # If no matches, return core tools
    if not matched_tools:
        return CORE_TOOLS[:max_tools]

    # Prioritize and limit
    result = list(matched_tools)[:max_tools]
    return result


def get_core_tools() -> List[str]:
    """Return the list of always-loaded core tools."""
    return CORE_TOOLS.copy()


def get_tools_by_category(category: str) -> List[str]:
    """Get all tools in a category."""
    category_keywords = {
        "geometry": ["wall", "floor", "roof", "level"],
        "structural": ["beam", "column", "brace", "foundation"],
        "stairs": ["stair", "railing"],
        "curtain_walls": ["curtain", "mullion", "panel"],
        "doors_windows": ["door", "window"],
        "views": ["view", "plan", "section", "elevation"],
        "sheets": ["sheet", "titleblock"],
        "annotation": ["dimension", "tag", "text"],
        "schedules": ["schedule"],
        "export": ["export", "dwg", "pdf", "ifc"],
        "import": ["import", "cad", "link"],
        "filters": ["filter", "visibility", "override"],
        "detail": ["detail", "drafting"],
        "analysis": ["analyze", "thermal"],
        "parameters": ["parameter", "property"],
    }

    tools: Set[str] = set()
    for keyword in category_keywords.get(category, []):
        if keyword in TOOL_INDEX:
            tools.update(TOOL_INDEX[keyword])

    return list(tools)


# =============================================================================
# MCP TOOLS - Exposed to LLM
# =============================================================================

@mcp.tool()
@register_tool
async def get_system_info(ctx: Context = None) -> str:
    """
    Get quick info about RevitMCP - tool count, categories, status.

    Use this for questions like:
    - "How many tools are there?"
    - "What can you do?"
    - "System status"

    Returns:
        JSON with tool count, categories, and core tools
    """
    return json.dumps({
        "total_tools": len(TOOL_FUNCTIONS),
        "categories": len(TOOL_CATEGORIES),
        "core_tools": len(CORE_TOOLS),
        "category_list": list(TOOL_CATEGORIES.keys()),
        "message": f"RevitMCP has {len(TOOL_FUNCTIONS)} tools across {len(TOOL_CATEGORIES)} categories. Use select_tools() to find specific tools."
    }, indent=2)


@mcp.tool()
@register_tool
async def select_tools(
    query: str,
    max_tools: int = 15,
    ctx: Context = None
) -> str:
    """
    Smart tool selector - finds relevant tools for your task.

    Use this FIRST when you need tools beyond the core set.
    Describe what you want to do, and this returns the right tools.

    Args:
        query: Description of what you want to do (e.g., "create structural beams")
        max_tools: Maximum tools to return (default 15)

    Returns:
        JSON with relevant tool names and their descriptions

    Examples:
        select_tools("export floor plans to PDF")
        select_tools("add curtain wall with mullions")
        select_tools("structural beam analysis")
    """
    tools = select_tools_for_query(query, max_tools)

    # Get descriptions for matched tools
    result = []
    for tool_name in tools:
        if tool_name in TOOL_FUNCTIONS:
            func = TOOL_FUNCTIONS[tool_name]
            doc = func.__doc__ or "No description"
            # Get first line of docstring
            first_line = doc.strip().split('\n')[0]
            result.append({
                "name": tool_name,
                "description": first_line
            })

    return json.dumps({
        "query": query,
        "tools_found": len(result),
        "tools": result
    }, indent=2)


@mcp.tool()
@register_tool
async def list_tool_categories(ctx: Context = None) -> str:
    """
    List all available tool categories.

    Use this to understand what types of tools are available,
    then use select_tools() to get specific tools from a category.

    Returns:
        JSON with category names and descriptions
    """
    result = []
    for cat, desc in TOOL_CATEGORIES.items():
        tools = get_tools_by_category(cat)
        result.append({
            "category": cat,
            "description": desc,
            "tool_count": len(tools)
        })

    return json.dumps({
        "categories": result,
        "total_categories": len(result)
    }, indent=2)


@mcp.tool()
@register_tool
async def get_tools_in_category(
    category: str,
    ctx: Context = None
) -> str:
    """
    Get all tools in a specific category.

    Args:
        category: Category name (use list_tool_categories to see options)

    Returns:
        JSON with tool names and descriptions in that category
    """
    tools = get_tools_by_category(category.lower())

    result = []
    for tool_name in tools:
        if tool_name in TOOL_FUNCTIONS:
            func = TOOL_FUNCTIONS[tool_name]
            doc = func.__doc__ or "No description"
            first_line = doc.strip().split('\n')[0]
            result.append({
                "name": tool_name,
                "description": first_line
            })

    return json.dumps({
        "category": category,
        "tools_found": len(result),
        "tools": result
    }, indent=2)
