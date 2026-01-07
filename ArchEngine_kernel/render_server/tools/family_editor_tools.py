import httpx
import json
from typing import List, Optional, Union, Any
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# --- Configuration ---
REVIT_API_URL = "http://localhost:48884/revit_mcp"

# --- Helper Functions ---
async def revit_post(endpoint: str, payload: Any, ctx: Context = None) -> dict:
    """Standard helper to send requests to the C# Revit Server."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"  # Ensure trailing slash for consistency
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=60.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed to {endpoint}: {str(e)}"}

def format_response(response: Any) -> str:
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)

# --- FAMILY EDITOR TOOLS ---

@mcp.tool()
@register_tool
async def list_family_templates(ctx: Context = None) -> str:
    """
    Lists the available Family Templates (.rft files) installed on the system.
    
    Use this FIRST to find the correct template path before creating a new family.
    """
    # Note: Using POST here because your C# router handles everything via the main handler usually, 
    # but if your C# logic for this is GET, change to client.get(). 
    # Based on your router, it's under the main switch, so POST is safer.
    response = await revit_post("/family/list_templates", {}, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_new_family_document(
    template_name: str,
    family_name: str,
    category_name: str = "Generic Models",
    ctx: Context = None
) -> str:
    """
    Creates a NEW Family Document (.rfa) from a template.
    
    Args:
        template_name: The file name of the template (e.g., "Metric Generic Model.rft").
                       Use 'list_family_templates' to find this.
        family_name: The name to save the new family as (e.g., "CustomTable").
        category_name: The Revit Category (e.g., "Furniture", "Doors").
    """
    payload = {
        "template_name": template_name,
        "family_name": family_name,
        "category_name": category_name
    }
    response = await revit_post("/family/create_new", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_family_extrusion(
    points: List[List[float]],
    height: float,
    ctx: Context = None
) -> str:
    """
    Creates a solid Extrusion form inside the current Family Document.
    
    WARNING: This tool ONLY works when a Family Document is active. 
    Do not use in a Project (.rvt).
    
    Args:
        points: List of [x, y, z] defining the 2D profile loop on the Reference Level.
        height: The extrusion height (positive or negative).
    """
    payload = {
        "points": points,
        "height": height
    }
    response = await revit_post("/family/create_extrusion", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def load_family_into_project(
    family_name: str,
    ctx: Context = None
) -> str:
    """
    Loads the currently open Family Document into the active Project.
    
    Args:
        family_name: The name of the family to load/overwrite.
    """
    payload = {"family_name": family_name}
    response = await revit_post("/load_family", payload, ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def create_reference_plane_family(
    start_point: List[float],
    end_point: List[float],
    name: str = "Ref Plane",
    is_strong: bool = False,
    ctx: Context = None
) -> str:
    """
    Creates a Reference Plane inside a Family Document.
    
    Args:
        start_point: [x,y,z]
        end_point: [x,y,z]
        name: Name of the reference (e.g., "Left Offset").
        is_strong: If True, defines the origin or structural reference.
    """
    payload = {
        "start_point": start_point,
        "end_point": end_point,
        "name": name,
        "is_strong": is_strong
    }
    # Matches C# route: /revit_mcp/family/create_ref_plane
    response = await revit_post("/family/create_ref_plane", payload, ctx)
    return format_response(response)


# =========================================================
# FAMILY PARAMETERS
# =========================================================

@mcp.tool()
@register_tool
async def create_family_parameter(
    param_name: str,
    param_type: str = "Length",
    group: str = "Dimensions",
    is_instance: bool = False,
    ctx: Context = None
) -> str:
    """
    Creates a new Family Parameter.

    Args:
        param_name: Name of the parameter (e.g., "Width", "Height", "Depth").
        param_type: Type of parameter: "Length", "Number", "Angle", "Text", "YesNo", "Material".
        group: Parameter group: "Dimensions", "Identity", "Constraints", "Materials", "Other".
        is_instance: If True, creates instance parameter; if False, creates type parameter.
    """
    payload = {
        "param_name": param_name,
        "param_type": param_type,
        "group": group,
        "is_instance": is_instance
    }
    response = await revit_post("/family/create_parameter", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_family_parameter_value(
    param_name: str,
    value: Union[float, int, str, bool],
    ctx: Context = None
) -> str:
    """
    Sets the value of a Family Parameter for the current type.

    Args:
        param_name: Name of the parameter.
        value: Value to set (number for Length/Number, string for Text, etc.).
    """
    payload = {
        "param_name": param_name,
        "value": value
    }
    response = await revit_post("/family/set_parameter_value", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_family_parameters(ctx: Context = None) -> str:
    """
    Lists all parameters in the current Family Document.

    Returns information about each parameter including name, type, and current value.
    """
    response = await revit_post("/family/list_parameters", {}, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_family_type(
    type_name: str,
    ctx: Context = None
) -> str:
    """
    Creates a new Family Type in the current Family Document.

    Args:
        type_name: Name for the new type (e.g., "Large", "Small", "Standard").
    """
    payload = {"type_name": type_name}
    response = await revit_post("/family/create_type", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_family_types(ctx: Context = None) -> str:
    """
    Lists all types in the current Family Document.
    """
    response = await revit_post("/family/list_types", {}, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_current_family_type(
    type_name: str,
    ctx: Context = None
) -> str:
    """
    Sets the current active family type.

    Args:
        type_name: Name of the type to set as current.
    """
    payload = {"type_name": type_name}
    response = await revit_post("/family/set_current_type", payload, ctx)
    return format_response(response)


# =========================================================
# FAMILY VOIDS & ADVANCED GEOMETRY
# =========================================================

@mcp.tool()
@register_tool
async def create_family_void(
    points: List[List[float]],
    height: float,
    base_offset: float = 0.0,
    ctx: Context = None
) -> str:
    """
    Creates a VOID (cut) Extrusion inside the current Family Document.

    Use this to cut holes or openings in solid geometry.

    Args:
        points: List of [x, y, z] defining the 2D void profile.
        height: The extrusion height (depth of cut).
        base_offset: Optional vertical offset for the void base.
    """
    payload = {
        "points": points,
        "height": height,
        "base_offset": base_offset
    }
    response = await revit_post("/family/create_void", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def cut_solid_with_void(
    solid_id: int,
    void_id: int,
    ctx: Context = None
) -> str:
    """
    Applies a void cut to a solid element.

    Args:
        solid_id: Element ID of the solid extrusion.
        void_id: Element ID of the void extrusion.
    """
    payload = {
        "solid_id": solid_id,
        "void_id": void_id
    }
    response = await revit_post("/family/cut_solid", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def create_family_blend(
    bottom_profile: List[List[float]],
    top_profile: List[List[float]],
    top_offset: float,
    is_solid: bool = True,
    ctx: Context = None
) -> str:
    """
    Creates a Blend (lofted shape between two profiles) in the Family.

    Args:
        bottom_profile: List of [x, y] points for the bottom profile.
        top_profile: List of [x, y] points for the top profile.
        top_offset: Height offset for the top profile.
        is_solid: If True creates solid, if False creates void.
    """
    payload = {
        "bottom_profile": bottom_profile,
        "top_profile": top_profile,
        "top_offset": top_offset,
        "is_solid": is_solid
    }
    response = await revit_post("/family/create_blend", payload, ctx)
    return format_response(response)


# =========================================================
# FAMILY CONSTRAINTS & DIMENSIONS
# =========================================================

@mcp.tool()
@register_tool
async def create_family_dimension(
    ref_plane_1: str,
    ref_plane_2: str,
    param_name: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Creates a dimension between two reference planes and optionally binds it to a parameter.

    This is how you make families parametric - dimensions control geometry.

    Args:
        ref_plane_1: Name of first reference plane.
        ref_plane_2: Name of second reference plane.
        param_name: Optional parameter name to bind dimension to. If provided, dimension
                   controls will be driven by this parameter.
    """
    payload = {
        "ref_plane_1": ref_plane_1,
        "ref_plane_2": ref_plane_2,
        "param_name": param_name
    }
    response = await revit_post("/family/create_dimension", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def bind_dimension_to_parameter(
    dimension_id: int,
    param_name: str,
    ctx: Context = None
) -> str:
    """
    Binds an existing dimension to a family parameter.

    Args:
        dimension_id: Element ID of the dimension.
        param_name: Parameter name to bind to (will be created if doesn't exist).
    """
    payload = {
        "dimension_id": dimension_id,
        "param_name": param_name
    }
    response = await revit_post("/family/bind_dimension", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def align_elements(
    element_1_id: int,
    element_2_id: int,
    ctx: Context = None
) -> str:
    """
    Creates an alignment constraint between two elements.

    Args:
        element_1_id: Element ID of first element.
        element_2_id: Element ID of second element.
    """
    payload = {
        "element_1_id": element_1_id,
        "element_2_id": element_2_id
    }
    response = await revit_post("/family/align_elements", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_reference_planes(ctx: Context = None) -> str:
    """
    Lists all reference planes in the current Family Document.

    Returns name, ID, and position of each reference plane.
    """
    response = await revit_post("/family/list_ref_planes", {}, ctx)
    return format_response(response)


# =========================================================
# FAMILY DOCUMENT MANAGEMENT
# =========================================================

@mcp.tool()
@register_tool
async def open_family_file(
    path: str,
    ctx: Context = None
) -> str:
    """
    Opens a family file (.rfa) and makes it the active document.

    Args:
        path: Full path to the .rfa file.

    Returns:
        Result with document info and is_family_document status.
    """
    payload = {"path": path}
    response = await revit_post("/family/open", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def get_family_document_status(ctx: Context = None) -> str:
    """
    Gets the status of the currently active document.

    Use this to verify you're in a Family Editor context before performing
    family operations. Returns document name, type, category, and state.
    """
    response = await revit_post("/family/document_status", {}, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def verify_family_document(ctx: Context = None) -> str:
    """
    Verifies the active document is a family document.

    Returns detailed error with helpful hints if not in family context.
    Use this before any family editing operations.
    """
    response = await revit_post("/family/verify", {}, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def save_family(
    path: Optional[str] = None,
    overwrite: bool = True,
    ctx: Context = None
) -> str:
    """
    Saves the current family document to disk.

    Args:
        path: Optional path to save the family. If not provided, saves to
              the current location or generates a default path.
        overwrite: Whether to overwrite if file exists (default: True).

    Returns:
        Result with saved file path and family name.
    """
    payload = {
        "path": path,
        "overwrite": overwrite
    }
    response = await revit_post("/family/save", payload, ctx)
    return format_response(response)


# =========================================================
# PHOTO-TO-FAMILY TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def analyze_photo_for_family(
    image_base64: str,
    object_hint: Optional[str] = None,
    view: str = "front",
    ctx: Context = None
) -> str:
    """
    Analyzes a photo of an object to extract geometry for family creation.

    Use this to understand an object's shape, proportions, and suggested dimensions
    before creating a parametric family.

    Args:
        image_base64: Base64-encoded image data.
        object_hint: Optional hint about object type (e.g., "table", "chair", "cabinet").
        view: Which view this photo represents: "front", "side", or "top".

    Returns:
        Analysis with object_type, category, proportions, solids, voids, and features.
    """
    # Import here to avoid circular imports
    from ..photo_to_family_processor import PhotoToFamilyProcessor

    processor = PhotoToFamilyProcessor()
    images = [{"data": image_base64, "view": view}]

    analysis = processor.analyze_photos(images, object_hint)

    return format_response(analysis)


@mcp.tool()
@register_tool
async def create_parametric_family_from_photo(
    image_base64: str,
    family_name: str,
    category: str = "Generic Models",
    dimensions: Optional[dict] = None,
    object_hint: Optional[str] = None,
    template: str = "Metric Generic Model.rft",
    ctx: Context = None
) -> str:
    """
    Creates a complete parametric family from a photo of an object.

    This is the main tool for photo-to-family workflow. It:
    1. Analyzes the photo to understand the object's geometry
    2. Estimates dimensions (or uses provided ones)
    3. Creates a parametric family with Width, Height, Depth parameters
    4. Creates reference planes and constrains geometry to parameters

    Args:
        image_base64: Base64-encoded image of the object.
        family_name: Name for the new family.
        category: Revit category (Furniture, Casework, Generic Models, etc.).
        dimensions: Optional dict with exact dimensions {"Width": 3.0, "Height": 2.5, "Depth": 2.0}.
                   If not provided, dimensions are estimated from the photo.
        object_hint: Optional hint about object type for better analysis.
        template: Family template to use.

    Returns:
        Result with family creation status and created element IDs.
    """
    # Import here to avoid circular imports
    from ..photo_to_family_processor import PhotoToFamilyProcessor
    from ..family_builder import ParametricFamilyBuilder
    import asyncio

    # Step 1: Analyze photo
    processor = PhotoToFamilyProcessor()
    images = [{"data": image_base64, "view": "front"}]

    analysis = processor.analyze_photos(images, object_hint)

    if not analysis:
        return format_response({"status": "error", "message": "Failed to analyze photo"})

    # Step 2: Get dimensions (provided or estimated)
    if dimensions:
        final_dimensions = dimensions
    else:
        final_dimensions = processor.estimate_dimensions(analysis)

    # Step 3: Generate geometry
    geometry = processor.generate_family_geometry(analysis, final_dimensions)
    geometry["category"] = category

    # Step 4: Build family
    builder = ParametricFamilyBuilder()
    result = await builder.build_family(geometry, family_name)

    return format_response(result)


@mcp.tool()
@register_tool
async def analyze_multiple_photos_for_family(
    front_image: str,
    side_image: Optional[str] = None,
    top_image: Optional[str] = None,
    object_hint: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Analyzes multiple views of an object for more accurate family geometry.

    Providing front + side views gives better depth estimation.
    Adding a top view improves footprint accuracy.

    Args:
        front_image: Base64-encoded front view image (required).
        side_image: Optional base64-encoded side view image.
        top_image: Optional base64-encoded top view image.
        object_hint: Optional hint about object type.

    Returns:
        Combined analysis from all views with improved accuracy.
    """
    from ..photo_to_family_processor import PhotoToFamilyProcessor

    processor = PhotoToFamilyProcessor()

    images = [{"data": front_image, "view": "front"}]

    if side_image:
        images.append({"data": side_image, "view": "side"})

    if top_image:
        images.append({"data": top_image, "view": "top"})

    analysis = processor.analyze_photos(images, object_hint)

    return format_response(analysis)
