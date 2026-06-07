"""
Import Tools - CAD, DWG, image, and point cloud import functionality

These tools enable importing external files into Revit including
CAD files, images, point clouds, and other formats.
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
# CAD IMPORT (DWG, DXF, DGN)
# =============================================================================

@mcp.tool()
@register_tool
async def import_cad(
    file_path: str,
    view_id: int,
    import_units: str = "Auto",
    positioning: str = "Center",
    placement_point: Optional[List[float]] = None,
    current_view_only: bool = True,
    ctx: Context = None
) -> str:
    """
    Import a CAD file (DWG, DXF, DGN) into a view.

    Args:
        file_path: Path to the CAD file
        view_id: Element ID of the target view
        import_units: 'Auto', 'Feet', 'Inches', 'Meters', 'Millimeters', etc.
        positioning: 'Origin', 'Center', 'Manual'
        placement_point: Optional [x, y, z] for manual positioning
        current_view_only: True to import in current view only

    Returns:
        JSON with import result including element ID
    """
    payload = {
        "file_path": file_path,
        "view_id": view_id,
        "import_units": import_units,
        "positioning": positioning,
        "placement_point": placement_point,
        "current_view_only": current_view_only
    }
    response = await revit_post("/import_cad/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def link_cad(
    file_path: str,
    view_id: int,
    import_units: str = "Auto",
    positioning: str = "Center",
    placement_point: Optional[List[float]] = None,
    current_view_only: bool = False,
    ctx: Context = None
) -> str:
    """
    Link a CAD file (maintains connection to source file).

    Args:
        file_path: Path to the CAD file
        view_id: Element ID of the target view
        import_units: 'Auto', 'Feet', 'Inches', 'Meters', 'Millimeters', etc.
        positioning: 'Origin', 'Center', 'Manual'
        placement_point: Optional [x, y, z] for manual positioning
        current_view_only: True to show in current view only

    Returns:
        JSON with link result including element ID
    """
    payload = {
        "file_path": file_path,
        "view_id": view_id,
        "import_units": import_units,
        "positioning": positioning,
        "placement_point": placement_point,
        "current_view_only": current_view_only
    }
    response = await revit_post("/link_cad/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_linked_cad(ctx: Context = None) -> str:
    """
    List all linked CAD files in the model.

    Returns:
        JSON array of linked CAD files with IDs, paths, and status
    """
    response = await revit_get("/list_linked_cad/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_imported_cad(ctx: Context = None) -> str:
    """
    List all imported CAD instances in the model.

    Returns:
        JSON array of imported CAD instances with IDs and locations
    """
    response = await revit_get("/list_imported_cad/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def reload_cad_link(
    link_id: int,
    new_path: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Reload a linked CAD file.

    Args:
        link_id: Element ID of the CAD link
        new_path: Optional new file path for repathing

    Returns:
        JSON with reload result
    """
    payload = {
        "link_id": link_id,
        "new_path": new_path
    }
    response = await revit_post("/reload_cad_link/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def unload_cad_link(
    link_id: int,
    ctx: Context = None
) -> str:
    """
    Unload a linked CAD file (keeps link definition).

    Args:
        link_id: Element ID of the CAD link

    Returns:
        JSON with unload result
    """
    payload = {"link_id": link_id}
    response = await revit_post("/unload_cad_link/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def remove_cad_link(
    link_id: int,
    ctx: Context = None
) -> str:
    """
    Remove a CAD link from the model.

    Args:
        link_id: Element ID of the CAD link

    Returns:
        JSON with removal result
    """
    payload = {"link_id": link_id}
    response = await revit_post("/remove_cad_link/", payload, ctx)
    return format_response(response)


# =============================================================================
# CAD LAYER CONTROL
# =============================================================================

@mcp.tool()
@register_tool
async def get_cad_layers(
    cad_id: int,
    ctx: Context = None
) -> str:
    """
    Get list of layers in an imported/linked CAD file.

    Args:
        cad_id: Element ID of the CAD import/link

    Returns:
        JSON array of layers with names, visibility, and colors
    """
    payload = {"cad_id": cad_id}
    response = await revit_post("/get_cad_layers/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_cad_layer_visibility(
    cad_id: int,
    layer_name: str,
    visible: bool,
    ctx: Context = None
) -> str:
    """
    Set visibility of a CAD layer.

    Args:
        cad_id: Element ID of the CAD import/link
        layer_name: Name of the layer
        visible: True to show, False to hide

    Returns:
        JSON with updated layer status
    """
    payload = {
        "cad_id": cad_id,
        "layer_name": layer_name,
        "visible": visible
    }
    response = await revit_post("/set_cad_layer_visibility/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def hide_all_cad_layers_except(
    cad_id: int,
    layer_names: List[str],
    ctx: Context = None
) -> str:
    """
    Hide all CAD layers except specified ones.

    Args:
        cad_id: Element ID of the CAD import/link
        layer_names: List of layer names to keep visible

    Returns:
        JSON with updated visibility status
    """
    payload = {
        "cad_id": cad_id,
        "layer_names": layer_names
    }
    response = await revit_post("/hide_cad_layers_except/", payload, ctx)
    return format_response(response)


# =============================================================================
# IMAGE IMPORT
# =============================================================================

@mcp.tool()
@register_tool
async def import_image(
    file_path: str,
    view_id: int,
    placement_point: List[float],
    width: Optional[float] = None,
    height: Optional[float] = None,
    lock_proportions: bool = True,
    ctx: Context = None
) -> str:
    """
    Import an image file into a view.

    Args:
        file_path: Path to the image file (JPG, PNG, BMP, TIFF)
        view_id: Element ID of the target view
        placement_point: [x, y, z] placement point in feet
        width: Optional width in feet
        height: Optional height in feet
        lock_proportions: Keep aspect ratio when resizing

    Returns:
        JSON with import result including element ID
    """
    payload = {
        "file_path": file_path,
        "view_id": view_id,
        "placement_point": placement_point,
        "width": width,
        "height": height,
        "lock_proportions": lock_proportions
    }
    response = await revit_post("/import_image/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_images(ctx: Context = None) -> str:
    """
    List all imported images in the model.

    Returns:
        JSON array of images with IDs, paths, and dimensions
    """
    response = await revit_get("/list_images/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def modify_image(
    image_id: int,
    width: Optional[float] = None,
    height: Optional[float] = None,
    draw_layer: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Modify properties of an imported image.

    Args:
        image_id: Element ID of the image
        width: New width in feet
        height: New height in feet
        draw_layer: 'Foreground' or 'Background'

    Returns:
        JSON with updated image properties
    """
    payload = {
        "image_id": image_id,
        "width": width,
        "height": height,
        "draw_layer": draw_layer
    }
    response = await revit_post("/modify_image/", payload, ctx)
    return format_response(response)


# =============================================================================
# POINT CLOUD IMPORT
# =============================================================================

@mcp.tool()
@register_tool
async def link_point_cloud(
    file_path: str,
    positioning: str = "Auto",
    placement_point: Optional[List[float]] = None,
    ctx: Context = None
) -> str:
    """
    Link a point cloud file (RCP, RCS, E57).

    Args:
        file_path: Path to the point cloud file
        positioning: 'Auto', 'Origin', 'Center', or 'Manual'
        placement_point: Optional [x, y, z] for manual positioning

    Returns:
        JSON with link result including element ID
    """
    payload = {
        "file_path": file_path,
        "positioning": positioning,
        "placement_point": placement_point
    }
    response = await revit_post("/link_point_cloud/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_point_clouds(ctx: Context = None) -> str:
    """
    List all linked point clouds in the model.

    Returns:
        JSON array of point clouds with IDs, paths, and status
    """
    response = await revit_get("/list_point_clouds/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_point_cloud_visibility(
    point_cloud_id: int,
    view_id: int,
    visible: bool,
    ctx: Context = None
) -> str:
    """
    Set point cloud visibility in a specific view.

    Args:
        point_cloud_id: Element ID of the point cloud
        view_id: Element ID of the view
        visible: True to show, False to hide

    Returns:
        JSON with updated visibility status
    """
    payload = {
        "point_cloud_id": point_cloud_id,
        "view_id": view_id,
        "visible": visible
    }
    response = await revit_post("/set_point_cloud_visibility/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def set_point_cloud_color_mode(
    point_cloud_id: int,
    view_id: int,
    color_mode: str,
    ctx: Context = None
) -> str:
    """
    Set point cloud color mode in a view.

    Args:
        point_cloud_id: Element ID of the point cloud
        view_id: Element ID of the view
        color_mode: 'NoOverride', 'SingleColor', 'Elevation', 'Intensity', 'Normals'

    Returns:
        JSON with updated color mode
    """
    payload = {
        "point_cloud_id": point_cloud_id,
        "view_id": view_id,
        "color_mode": color_mode
    }
    response = await revit_post("/set_point_cloud_color/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def crop_point_cloud_to_view(
    point_cloud_id: int,
    view_id: int,
    ctx: Context = None
) -> str:
    """
    Crop point cloud to match view crop region.

    Args:
        point_cloud_id: Element ID of the point cloud
        view_id: Element ID of the view with crop region

    Returns:
        JSON with crop result
    """
    payload = {
        "point_cloud_id": point_cloud_id,
        "view_id": view_id
    }
    response = await revit_post("/crop_point_cloud/", payload, ctx)
    return format_response(response)


# =============================================================================
# REVIT LINK
# =============================================================================

@mcp.tool()
@register_tool
async def link_revit(
    file_path: str,
    positioning: str = "Origin",
    shared_coordinates: bool = True,
    ctx: Context = None
) -> str:
    """
    Link another Revit model.

    Args:
        file_path: Path to the Revit file (.rvt)
        positioning: 'Origin', 'SharedCoordinates', or 'Manual'
        shared_coordinates: Use shared coordinates if available

    Returns:
        JSON with link result including element ID
    """
    payload = {
        "file_path": file_path,
        "positioning": positioning,
        "shared_coordinates": shared_coordinates
    }
    response = await revit_post("/link_revit/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_revit_links(ctx: Context = None) -> str:
    """
    List all linked Revit models.

    Returns:
        JSON array of Revit links with IDs, paths, and status
    """
    response = await revit_get("/list_revit_links/", ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def reload_revit_link(
    link_id: int,
    new_path: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    Reload a linked Revit model.

    Args:
        link_id: Element ID of the Revit link
        new_path: Optional new file path for repathing

    Returns:
        JSON with reload result
    """
    payload = {
        "link_id": link_id,
        "new_path": new_path
    }
    response = await revit_post("/reload_revit_link/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def unload_revit_link(
    link_id: int,
    ctx: Context = None
) -> str:
    """
    Unload a linked Revit model.

    Args:
        link_id: Element ID of the Revit link

    Returns:
        JSON with unload result
    """
    payload = {"link_id": link_id}
    response = await revit_post("/unload_revit_link/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def copy_monitor_elements(
    link_id: int,
    element_types: List[str],
    ctx: Context = None
) -> str:
    """
    Copy/Monitor elements from a linked model.

    Args:
        link_id: Element ID of the Revit link
        element_types: Types to copy/monitor - 'Levels', 'Grids', 'Columns', 'Walls', 'Floors'

    Returns:
        JSON with copy/monitor result
    """
    payload = {
        "link_id": link_id,
        "element_types": element_types
    }
    response = await revit_post("/copy_monitor_elements/", payload, ctx)
    return format_response(response)


# =============================================================================
# IFC IMPORT
# =============================================================================

@mcp.tool()
@register_tool
async def import_ifc(
    file_path: str,
    import_as: str = "Link",
    ctx: Context = None
) -> str:
    """
    Import an IFC file.

    Args:
        file_path: Path to the IFC file
        import_as: 'Link' or 'Open' (Open creates new Revit model)

    Returns:
        JSON with import result
    """
    payload = {
        "file_path": file_path,
        "import_as": import_as
    }
    response = await revit_post("/import_ifc/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_ifc_links(ctx: Context = None) -> str:
    """
    List all linked IFC files.

    Returns:
        JSON array of IFC links with IDs, paths, and status
    """
    response = await revit_get("/list_ifc_links/", ctx)
    return format_response(response)


# =============================================================================
# GBXML IMPORT
# =============================================================================

@mcp.tool()
@register_tool
async def import_gbxml(
    file_path: str,
    ctx: Context = None
) -> str:
    """
    Import a gbXML file for energy analysis.

    Args:
        file_path: Path to the gbXML file

    Returns:
        JSON with import result
    """
    payload = {"file_path": file_path}
    response = await revit_post("/import_gbxml/", payload, ctx)
    return format_response(response)
