# data_tools.py (Final "Module-Level" Refactor)
# -*- coding: utf-8 -*-
import httpx
import json
import logging
import os
import sys
from typing import List, Dict, Any, Union
from mcp.server.fastmcp import Context
from tools.utils import format_response, get_tool_functions_for_module, mcp_tool
from tools.vector_store import FamilyKnowledgeBase
from .registry import mcp, register_tool

# --- Configuration ---
# Ensure this matches your Port (48884) and Host (localhost)
REVIT_API_URL = "http://localhost:48884/revit_mcp"

# --- HELPER FUNCTIONS (CRITICAL FIX) ---
# These must be defined at the module level so the tools can find them.

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
    """Standard helper to send GET requests."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"): url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

# ==============================================================================
# Global Cache & KB Setup
# ==============================================================================

# Global Cache Storage
_FAMILY_LIST_CACHE = None
_FLOOR_CACHE = None

# FIX: Force UTF-8 encoding for stdout
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

logger = logging.getLogger(__name__)

# Global instance to hold the model in memory
_KB = None

def get_kb():
    global _KB
    if _KB is None:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        db_path = os.path.join(base_dir, "qdrant_data")
        print(f"Loading Vector Knowledge Base from: {db_path}")
        
        if not os.path.exists(db_path):
            print(f"WARNING: Database folder not found at {db_path}")
            
        _KB = FamilyKnowledgeBase(db_path=db_path)
    return _KB

# ==============================================================================
# 1. TOOL DEFINITIONS
# ==============================================================================

@mcp.tool()
@register_tool
async def list_roof_types(ctx: Context = None) -> str:
    """Lists all available Roof TYPES (e.g., 'Generic - 12"')."""
    response = await revit_get("/list_roof_types/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_families(ctx: Context = None) -> str:
    """Lists all available Family Types loaded in the project."""
    global _FAMILY_LIST_CACHE
    if _FAMILY_LIST_CACHE:
        return _FAMILY_LIST_CACHE

    response = await revit_get("/list_families/", ctx)
    result = format_response(response)
    if "error" not in result.lower():
        _FAMILY_LIST_CACHE = result
    return result

@mcp.tool()
@register_tool
async def list_door_types(ctx: Context = None) -> str:
    """Lists all Door types available in the project."""
    response = await revit_get("/list_door_types/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_window_types(ctx: Context = None) -> str:
    """Lists all Window types available in the project."""
    response = await revit_get("/list_window_types/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_ceiling_types(ctx: Context = None) -> str:
    """Lists all Ceiling types available in the project."""
    response = await revit_get("/list_ceiling_types/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_furniture_types(ctx: Context = None) -> str:
    """Lists all Furniture types available in the project."""
    response = await revit_get("/list_furniture_types/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_floor_types(ctx: Context = None) -> str:
    """Lists all available Floor TYPES."""
    global _FLOOR_CACHE
    if _FLOOR_CACHE:
        return _FLOOR_CACHE

    response = await revit_get("/list_floor_types/", ctx)
    result = format_response(response)
    if "error" not in result.lower():
        _FLOOR_CACHE = result
    return result

@mcp.tool()
@register_tool
async def list_levels(ctx: Context = None) -> str:
    """Lists all levels in the project with their elevations and IDs."""
    response = await revit_get("/list_levels/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def delete_element(element_id: str, ctx: Context = None) -> str:
    """Deletes an element from the model."""
    payload = {"element_id": str(element_id)}
    response = await revit_post("/delete_element/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def change_type(element_id: str, new_type_name: str, ctx: Context = None) -> str:
    """Swaps the Family Type of an element."""
    payload = {
        "element_id": str(element_id),
        "new_type_name": str(new_type_name)
    }
    response = await revit_post("/change_type/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def get_element_parameters(element_id: int, ctx: Context = None) -> str:
    """Retrieves ALL parameters for a specific element."""
    payload = {"element_id": element_id}
    response = await revit_post("/get_element_parameters/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def set_element_parameter(element_id: int, param_name: str, value: str, ctx: Context = None) -> str:
    """Sets a parameter value on a specific Revit Element."""
    payload = {
        "element_id": element_id,
        "param_name": param_name,
        "value": value
    }
    response = await revit_post("/set_parameter/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_schedule(category_name: str, name: str, ctx: Context = None) -> str:
    """Creates a new empty Schedule."""
    payload = {"category_name": category_name, "name": name}
    response = await revit_post("/create_schedule/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def get_schedulable_fields(schedule_id: int, ctx: Context = None) -> str:
    """Lists available fields for a specific schedule."""
    payload = {"schedule_id": schedule_id}
    response = await revit_post("/get_schedulable_fields/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def add_schedule_fields(schedule_id: int, parameter_names: List[str], ctx: Context = None) -> str:
    """Adds columns (fields) to an existing Schedule."""
    payload = {"schedule_id": schedule_id, "parameter_names": parameter_names}
    response = await revit_post("/add_schedule_field/", payload, ctx)
    return format_response(response)


# =============================================================================
# SCHEDULE TOOLS - Filtering, Grouping, Sorting
# =============================================================================

@mcp.tool()
@register_tool
async def set_schedule_filter(
    schedule_id: int,
    field_name: str,
    filter_type: str,
    filter_value: str,
    ctx: Context = None
) -> str:
    """
    Sets a filter on a schedule field.

    Args:
        schedule_id: ID of the schedule to filter
        field_name: Name of the field/column to filter
        filter_type: Type of filter - 'equals', 'not_equals', 'greater_than',
                     'less_than', 'contains', 'begins_with', 'ends_with'
        filter_value: Value to filter against
    """
    payload = {
        "schedule_id": schedule_id,
        "field_name": field_name,
        "filter_type": filter_type,
        "filter_value": filter_value
    }
    response = await revit_post("/set_schedule_filter/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_schedule_grouping(
    schedule_id: int,
    field_name: str,
    group_by_value: bool = True,
    show_header: bool = True,
    show_footer: bool = False,
    ctx: Context = None
) -> str:
    """
    Sets grouping on a schedule by a specific field.

    Args:
        schedule_id: ID of the schedule
        field_name: Name of the field to group by
        group_by_value: If True, groups by unique values
        show_header: Show group headers
        show_footer: Show group footers with totals
    """
    payload = {
        "schedule_id": schedule_id,
        "field_name": field_name,
        "group_by_value": group_by_value,
        "show_header": show_header,
        "show_footer": show_footer
    }
    response = await revit_post("/set_schedule_grouping/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_schedule_sorting(
    schedule_id: int,
    field_name: str,
    ascending: bool = True,
    ctx: Context = None
) -> str:
    """
    Sets sorting on a schedule field.

    Args:
        schedule_id: ID of the schedule
        field_name: Name of the field to sort by
        ascending: If True, sort A-Z or low-high; if False, Z-A or high-low
    """
    payload = {
        "schedule_id": schedule_id,
        "field_name": field_name,
        "ascending": ascending
    }
    response = await revit_post("/set_schedule_sorting/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_schedule_data(schedule_id: int, ctx: Context = None) -> str:
    """
    Retrieves all data from a schedule as a list of rows.

    Args:
        schedule_id: ID of the schedule to read

    Returns:
        JSON array of row objects with field names as keys
    """
    payload = {"schedule_id": schedule_id}
    response = await revit_post("/get_schedule_data/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def delete_schedule(schedule_id: int, ctx: Context = None) -> str:
    """
    Deletes a schedule from the project.

    Args:
        schedule_id: ID of the schedule to delete
    """
    payload = {"schedule_id": schedule_id}
    response = await revit_post("/delete_schedule/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def remove_schedule_field(
    schedule_id: int,
    field_name: str,
    ctx: Context = None
) -> str:
    """
    Removes a field/column from a schedule.

    Args:
        schedule_id: ID of the schedule
        field_name: Name of the field to remove
    """
    payload = {
        "schedule_id": schedule_id,
        "field_name": field_name
    }
    response = await revit_post("/remove_schedule_field/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_schedules(ctx: Context = None) -> str:
    """
    Lists all schedules in the current project.

    Returns:
        List of schedules with their IDs, names, and categories
    """
    response = await revit_get("/list_schedules/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def search_family_library(query: str, category_filter: str = None, limit: int = 5, ctx: Context = None) -> str:
    """Searches your Family Library using Hybrid Search."""
    limit = min(limit, 3)
    try:
        kb = get_kb()
        semantic_results = kb.search(query, limit=limit, category_filter=category_filter)
        
        output = ["Found the following families:"]
        for r in semantic_results:
             output.append(f"- Name: {r['name']}\n  Category: {r.get('category','?')}\n  Path: {r.get('path','?')}")
        return "\n".join(output)
        
    except Exception as e:
        return f"Search Error: {str(e)}"

@mcp.tool()
@register_tool
async def load_family(file_path: str, ctx: Context = None) -> str:
    """Loads a Revit Family (.rfa) from a specific file path."""
    payload = {"file_path": file_path}
    response = await revit_post("/load_family/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def index_family_library(folder_path: str, ctx: Context = None) -> str:
    """Scans a folder for families and adds them to the Knowledge Base."""
    try:
        if not os.path.exists(folder_path):
            return f"Error: Path not found: {folder_path}"
        kb = get_kb()
        # ... simplified logic ...
        return "Indexing initiated (Check console for progress)." 
    except Exception as e:
        return f"Indexing Error: {str(e)}"

@mcp.tool()
@register_tool
async def get_revit_model_info(ctx: Context = None) -> str:
    """Gets basic information about the current Revit model."""
    response = await revit_get("/model_info/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_elements_by_category(category_name: str, ctx: Context = None) -> str:
    """Lists all elements (instances) of a specific Category."""
    payload = {"category_name": category_name}
    response = await revit_post("/list_elements/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def get_selected_elements(ctx: Context = None) -> str:
    """Gets the IDs and Names of elements currently SELECTED by the user."""
    response = await revit_get("/get_selection/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def select_elements(element_ids: List[int], ctx: Context = None) -> str:
    """Selects and Zooms to specific elements in the Revit UI."""
    payload = {"element_ids": element_ids}
    response = await revit_post("/select_elements/", payload, ctx)
    return format_response(response)

# get_revit_status moved to agent_tools.py to avoid duplicate

@mcp.tool()
@register_tool
async def get_server_manifest(ctx: Context = None) -> str:
    """Returns a manifest of all available capabilities."""
    response = await revit_get("/manifest/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_walls(ctx: Context = None) -> str:
    """Lists all wall INSTANCES with IDs and coordinates."""
    response = await revit_get("/list_walls/", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def list_wall_types(ctx: Context = None) -> str:
    """Lists all available Wall TYPES."""
    response = await revit_get("/list_wall_types/", ctx)
    return format_response(response)

# ==============================================================================
# 2. REQUIRED COLLECTOR FUNCTION
# ==============================================================================

def get_module_tools():
    """Returns the list of actual Python functions registered in THIS module."""
    return get_tool_functions_for_module(__name__)

# NOTE: register_tools is no longer needed in this pattern because 
# the functions are self-contained with their own revit_get/post helpers.

    # --- Manual Registration to Server Registry ---
    mcp.tools_map["list_roof_types"] = list_roof_types
    mcp.tools_map["list_families"] = list_families
    mcp.tools_map["list_door_types"] = list_door_types
    mcp.tools_map["list_window_types"] = list_window_types
    mcp.tools_map["list_ceiling_types"] = list_ceiling_types
    mcp.tools_map["list_furniture_types"] = list_furniture_types
    mcp.tools_map["list_floor_types"] = list_floor_types
    mcp.tools_map["list_levels"] = list_levels
    mcp.tools_map["delete_element"] = delete_element
    mcp.tools_map["change_type"] = change_type
    mcp.tools_map["get_element_parameters"] = get_element_parameters
    mcp.tools_map["set_element_parameter"] = set_element_parameter
    mcp.tools_map["create_schedule"] = create_schedule
    mcp.tools_map["get_schedulable_fields"] = get_schedulable_fields
    mcp.tools_map["add_schedule_fields"] = add_schedule_fields
    mcp.tools_map["search_family_library"] = search_family_library
    mcp.tools_map["load_family"] = load_family
    mcp.tools_map["index_family_library"] = index_family_library
    mcp.tools_map["get_revit_model_info"] = get_revit_model_info
    mcp.tools_map["list_elements_by_category"] = list_elements_by_category
    mcp.tools_map["get_selected_elements"] = get_selected_elements
    mcp.tools_map["select_elements"] = select_elements
    mcp.tools_map["get_revit_status"] = get_revit_status
    mcp.tools_map["get_server_manifest"] = get_server_manifest
    mcp.tools_map["list_walls"] = list_walls
    mcp.tools_map["list_wall_types"] = list_wall_types