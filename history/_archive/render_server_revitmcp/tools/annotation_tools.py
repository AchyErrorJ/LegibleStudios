import httpx
import json
from typing import List, Optional, Union, Dict, Any
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# --- Configuration ---
REVIT_API_URL = "http://localhost:48884/revit_mcp"

# --- Helper: Standardized Request Function ---
async def revit_post(endpoint: str, payload: Any, ctx: Context = None) -> dict:
    """Standard helper to send requests to the C# Revit Server."""
    url = f"{REVIT_API_URL}{endpoint}"
    # Ensure URL ends with / if your C# server expects it
    if not url.endswith("/"):
        url += "/"
        
    async with httpx.AsyncClient() as client:
        try:
            # We assume payload is already a dict or list; if not, json=payload handles serialization
            resp = await client.post(url, json=payload, timeout=45.0)
            resp.raise_for_status()
            return resp.json() # Return parsed JSON
        except Exception as e:
            return {"status": "error", "message": f"Connection failed to {endpoint}: {str(e)}"}

def format_response(response: Any) -> str:
    """Standard formatter for tool output."""
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)

# --- 1. Grid & Datum Tools ---

@mcp.tool()
@register_tool
async def create_grids_batch(grids: Union[List[dict], str], ctx: Context = None) -> str:
    """
    Creates MULTIPLE Grid lines in the Revit project.

    Args:
        grids: A LIST of objects. Each object must have:
               - "start_point": [x, y, z]
               - "end_point": [x, y, z]
               - "name": (Optional) String for the bubble name (e.g., "A", "1").
    
    Example:
        [{"start_point": [0,0,0], "end_point": [0,10,0], "name": "1"}]
    """
    # Defensive Parsing: Handle if LLM sends a stringified JSON
    if isinstance(grids, str):
        try:
            grids = json.loads(grids)
        except:
            return "Error: 'grids' argument must be a valid JSON list, not a malformed string."
    
    # Defensive Check: Handle flat lists
    if grids and isinstance(grids, list) and len(grids) > 0 and not isinstance(grids[0], dict):
        return "Error: 'grids' must be a list of OBJECTS (dictionaries), not a flat list of numbers."
    
    validated_grids = []
    for i, grid in enumerate(grids):
        if not isinstance(grid, dict): 
            continue
        if "start_point" not in grid or "end_point" not in grid:
            return f"Error: grid at index {i} is missing 'start_point' or 'end_point'."
        
        validated_grids.append({
            "name": grid.get("name", str(i + 1)),
            "start_point": grid["start_point"],
            "end_point": grid["end_point"]
        })
    
    response = await revit_post("/create_grids_batch/", validated_grids, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_reference_plane(
    start_point: List[float],
    end_point: List[float],
    name: str = "Ref Plane",
    view_id: Optional[int] = None,
    ctx: Context = None
) -> str:
    """
    Creates a Reference Plane.
    
    Args:
        start_point: [x, y, z] coordinates.
        end_point: [x, y, z] coordinates.
        name: Name of the reference plane.
        view_id: (Optional) ID of the view if creating in a specific context.
    """
    payload = {
        "start_point": start_point, 
        "end_point": end_point, 
        "name": name, 
        "view_id": view_id
    }
    response = await revit_post("/create_reference_plane/", payload, ctx)
    return format_response(response)

# --- 2. View Creation Tools ---

@mcp.tool()
@register_tool
async def list_views(ctx: Context = None) -> str:
    """
    Lists all Views in the project. Returns ID, Name, and Type.
    Use this to find 'view_id' for other tools.
    """
    # GET request example
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{REVIT_API_URL}/list_views/", timeout=30.0)
            return format_response(resp.json())
        except Exception as e:
            return f"Error listing views: {e}"

@mcp.tool()
@register_tool
async def create_floor_plan(level_name: str, view_name: Optional[str] = None, ctx: Context = None) -> str:
    """Creates a Floor Plan view based on an existing Level Name."""
    payload = {"level_name": level_name, "view_name": view_name}
    response = await revit_post("/create_floor_plan/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_ceiling_plan(level_name: str, view_name: Optional[str] = None, ctx: Context = None) -> str:
    """Creates a Reflected Ceiling Plan (RCP) based on an existing Level Name."""
    payload = {"level_name": level_name, "view_name": view_name}
    response = await revit_post("/create_rcp/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_section(
    start_point: List[float], 
    end_point: List[float], 
    height: float = 10.0, 
    view_name: Optional[str] = None, 
    ctx: Context = None
) -> str:
    """
    Creates a Section View.
    
    Args:
        start_point: The start of the section cut line [x, y, z].
        end_point: The end of the section cut line [x, y, z].
        height: The vertical height of the section view crop box.
    """
    payload = {
        "start_point": start_point, 
        "end_point": end_point, 
        "height": height, 
        "view_name": view_name
    }
    response = await revit_post("/create_section/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_elevation(
    point: List[float], 
    view_name: Optional[str] = None, 
    scale: int = 100, 
    ctx: Context = None
) -> str:
    """
    Creates an Elevation Marker and View at a specific point.
    
    Args:
        point: [x, y, z] location for the marker.
        scale: View scale (e.g., 100 for 1:100, 48 for 1/4" = 1').
    """
    payload = {"point": point, "view_name": view_name, "scale": scale}
    response = await revit_post("/create_elevation/", payload, ctx)
    return format_response(response)

# --- 3. Sheet & Documentation Tools ---

@mcp.tool()
@register_tool
async def list_sheets(ctx: Context = None) -> str:
    """Lists all Sheets (ID, Number, Name)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{REVIT_API_URL}/list_sheets/", timeout=30.0)
            return format_response(resp.json())
        except Exception as e:
            return f"Error listing sheets: {e}"

@mcp.tool()
@register_tool
async def create_sheet(
    name: str, 
    number: str, 
    titleblock: Optional[str] = None, 
    ctx: Context = None
) -> str:
    """
    Creates a SINGLE new Sheet.
    
    Args:
        name: The name of the sheet (e.g., "Floor Plans").
        number: The sheet number (e.g., "A101").
        titleblock: (Optional) Name of the titleblock family to use.
    """
    payload = {"name": name, "number": number, "titleblock": titleblock}
    response = await revit_post("/create_sheet/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_sheets_batch(sheets: Union[List[dict], str], ctx: Context = None) -> str:
    """
    Creates MULTIPLE Sheets in one transaction.
    
    Args:
        sheets: List of objects: [{"name": "First", "number": "A101"}, ...]
    """
    if isinstance(sheets, str):
        try: sheets = json.loads(sheets)
        except: return "Error: sheets must be a list."

    response = await revit_post("/create_sheets_batch/", sheets, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def place_view_on_sheet(
    sheet_id: int, 
    view_id: int, 
    point: List[float] = [1.5, 1.5, 0], 
    ctx: Context = None
) -> str:
    """
    Places a SINGLE View onto a Sheet.
    
    Args:
        sheet_id: Integer ID of the Sheet (use list_sheets).
        view_id: Integer ID of the View (use list_views).
        point: [x, y, z] location on the sheet (in paper space units, usually feet).
    """
    payload = {"sheet_id": sheet_id, "view_id": view_id, "point": point}
    response = await revit_post("/place_view_on_sheet/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def place_views_batch(placements: Union[List[dict], str], ctx: Context = None) -> str:
    """
    Places MULTIPLE views on sheets.
    Args: placements = [{"sheet_id": 123, "view_id": 456, "point": [0,0,0]}, ...]
    """
    if isinstance(placements, str):
        try: placements = json.loads(placements)
        except: return "Error: placements must be a list."

    validated = []
    for p in placements:
        if not isinstance(p, dict): continue
        validated.append({
            "sheet_id": int(p["sheet_id"]),
            "view_id": int(p["view_id"]),
            "point": p.get("point", [0,0,0])
        })
    
    response = await revit_post("/place_views_batch/", validated, ctx)
    return format_response(response)

# --- 4. Annotation Tools ---

@mcp.tool()
@register_tool
async def create_text_note(
    text: str, 
    point: List[float], 
    view_id: Optional[int] = None, 
    ctx: Context = None
) -> str:
    """Creates a SINGLE Text Note at 'point' [x,y,z]."""
    # Wrap in list to reuse the batch endpoint which is usually more stable
    payload = [{"text": text, "point": point, "view_id": view_id}]
    response = await revit_post("/create_text_notes_batch/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_tag(
    element_id: int, 
    point: Optional[List[float]] = None, 
    view_id: Optional[int] = None, 
    ctx: Context = None
) -> str:
    """
    Tags a SINGLE element in a view.
    
    Args:
        element_id: The ID of the wall/door/window to tag.
        point: (Optional) [x,y,z] for tag head location.
    """
    payload = [{"element_id": element_id, "point": point, "view_id": view_id}]
    response = await revit_post("/create_tags_batch/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_dimension(
    element_ids: List[int],
    start_point: List[float],
    end_point: List[float],
    view_id: Optional[int] = None,
    ctx: Context = None
) -> str:
    """
    Creates a linear dimension line.
    
    Args:
        element_ids: List of 2 Reference IDs (e.g. two wall IDs) to dimension between.
        start_point: Line start [x,y,z].
        end_point: Line end [x,y,z].
    """
    payload = {
        "element_ids": element_ids, 
        "start_point": start_point, 
        "end_point": end_point, 
        "view_id": view_id
    }
    response = await revit_post("/create_dimension/", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_room_separation_lines(
    lines: Union[List[dict], str],
    level_name: str,
    ctx: Context = None
) -> str:
    """
    Creates room separation lines.
    Args: lines = [{"start_point": [x,y,z], "end_point": [x,y,z]}, ...]
    """
    if isinstance(lines, str):
        try: lines = json.loads(lines)
        except: return "Error parsing lines JSON."
        
    validated = []
    for line in lines:
        if isinstance(line, dict) and "start_point" in line and "end_point" in line:
            validated.append(line)
            
    payload = {"lines": validated, "level_name": level_name}
    response = await revit_post("/create_separation_lines/", payload, ctx)
    return format_response(response)

    # --- Manual Registration to Server Registry ---
    mcp.tools_map["create_grids_batch"] = create_grids_batch
    mcp.tools_map["create_reference_plane"] = create_reference_plane
    mcp.tools_map["create_room_separation_lines"] = create_room_separation_lines
    mcp.tools_map["list_sheets"] = list_sheets
    mcp.tools_map["create_sheet"] = create_sheet
    mcp.tools_map["create_sheets_batch"] = create_sheets_batch
    mcp.tools_map["place_view_on_sheet"] = place_view_on_sheet
    mcp.tools_map["place_views_batch"] = place_views_batch
    mcp.tools_map["list_views"] = list_views
    mcp.tools_map["create_floor_plan"] = create_floor_plan
    mcp.tools_map["create_ceiling_plan"] = create_ceiling_plan
    mcp.tools_map["create_section"] = create_section
    mcp.tools_map["create_elevation"] = create_elevation
    mcp.tools_map["create_dimension"] = create_dimension
    mcp.tools_map["create_text_note"] = create_text_note
    mcp.tools_map["create_text_notes_batch"] = create_text_notes_batch
    mcp.tools_map["create_tag"] = create_tag
    mcp.tools_map["create_tags_batch"] = create_tags_batch