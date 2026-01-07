"""
Export Tools - DWG, PDF, IFC, and image export functionality

These tools enable exporting Revit views and models to various formats
for coordination, documentation, and delivery.
"""

import json
import os
from typing import List, Optional, Union
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# Import shared helpers
try:
    from .geometry_tools import revit_post, revit_get, format_response
except ImportError:
    from geometry_tools import revit_post, revit_get, format_response


# =============================================================================
# DWG EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_dwg(
    view_ids: List[int],
    output_folder: str,
    dwg_version: str = "AutoCAD2018",
    export_settings: Optional[str] = None,
    file_naming: str = "view_name",
    ctx: Context = None
) -> str:
    """
    Export views to DWG format.

    Args:
        view_ids: List of view element IDs to export
        output_folder: Destination folder path
        dwg_version: DWG version (AutoCAD2018, AutoCAD2013, AutoCAD2010, AutoCAD2007)
        export_settings: Name of saved DWG export setup (optional)
        file_naming: How to name files - 'view_name', 'sheet_number', or 'custom'

    Returns:
        JSON with export results and file paths
    """
    payload = {
        "view_ids": view_ids,
        "output_folder": output_folder,
        "dwg_version": dwg_version,
        "export_settings": export_settings,
        "file_naming": file_naming
    }
    response = await revit_post("/export_dwg/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_dwg_sheets(
    sheet_ids: List[int],
    output_folder: str,
    dwg_version: str = "AutoCAD2018",
    include_xrefs: bool = True,
    ctx: Context = None
) -> str:
    """
    Export sheets to DWG format with all placed views.

    Args:
        sheet_ids: List of sheet element IDs to export
        output_folder: Destination folder path
        dwg_version: DWG version
        include_xrefs: Whether to include external references

    Returns:
        JSON with export results
    """
    payload = {
        "sheet_ids": sheet_ids,
        "output_folder": output_folder,
        "dwg_version": dwg_version,
        "include_xrefs": include_xrefs
    }
    response = await revit_post("/export_dwg_sheets/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def list_dwg_export_setups(ctx: Context = None) -> str:
    """
    List available DWG export setups/configurations.

    Returns:
        JSON array of export setup names
    """
    response = await revit_get("/list_dwg_export_setups/", ctx)
    return format_response(response)


# =============================================================================
# PDF EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_pdf(
    view_ids: List[int],
    output_path: str,
    combine_into_single: bool = True,
    paper_size: str = "Letter",
    orientation: str = "Auto",
    color_mode: str = "Color",
    raster_quality: str = "Medium",
    ctx: Context = None
) -> str:
    """
    Export views to PDF format.

    Args:
        view_ids: List of view element IDs to export
        output_path: Output file path (for combined) or folder (for separate)
        combine_into_single: True to create one PDF, False for separate files
        paper_size: Paper size (Letter, Legal, Tabloid, ARCH_D, A4, A3, A2, A1, A0)
        orientation: Portrait, Landscape, or Auto
        color_mode: Color, Grayscale, or BlackWhite
        raster_quality: Low, Medium, High, or Presentation

    Returns:
        JSON with export results and file paths
    """
    payload = {
        "view_ids": view_ids,
        "output_path": output_path,
        "combine_into_single": combine_into_single,
        "paper_size": paper_size,
        "orientation": orientation,
        "color_mode": color_mode,
        "raster_quality": raster_quality
    }
    response = await revit_post("/export_pdf/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_sheets_to_pdf(
    sheet_ids: List[int],
    output_folder: str,
    combine_into_single: bool = False,
    naming_pattern: str = "{sheet_number}_{sheet_name}",
    ctx: Context = None
) -> str:
    """
    Export sheets to PDF with automatic naming.

    Args:
        sheet_ids: List of sheet element IDs (use list_sheets to get IDs)
        output_folder: Destination folder path
        combine_into_single: True for one PDF, False for one per sheet
        naming_pattern: Pattern for file names using {sheet_number}, {sheet_name}, {date}

    Returns:
        JSON with export results
    """
    payload = {
        "sheet_ids": sheet_ids,
        "output_folder": output_folder,
        "combine_into_single": combine_into_single,
        "naming_pattern": naming_pattern
    }
    response = await revit_post("/export_sheets_to_pdf/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def print_to_pdf(
    sheet_ids: List[int],
    output_folder: str,
    printer_name: str = "Microsoft Print to PDF",
    ctx: Context = None
) -> str:
    """
    Print sheets to PDF using system print dialog.

    Args:
        sheet_ids: List of sheet element IDs
        output_folder: Destination folder
        printer_name: PDF printer name

    Returns:
        JSON with print results
    """
    payload = {
        "sheet_ids": sheet_ids,
        "output_folder": output_folder,
        "printer_name": printer_name
    }
    response = await revit_post("/print_to_pdf/", payload, ctx)
    return format_response(response)


# =============================================================================
# IFC EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_ifc(
    output_path: str,
    ifc_version: str = "IFC4",
    export_base_quantities: bool = True,
    split_walls_by_level: bool = True,
    include_steel_elements: bool = True,
    export_bounding_box: bool = False,
    ctx: Context = None
) -> str:
    """
    Export model to IFC format for BIM coordination.

    Args:
        output_path: Output IFC file path
        ifc_version: IFC2x3 or IFC4
        export_base_quantities: Include quantity takeoff data
        split_walls_by_level: Split walls at level boundaries
        include_steel_elements: Include structural steel
        export_bounding_box: Export bounding box geometry

    Returns:
        JSON with export results
    """
    payload = {
        "output_path": output_path,
        "ifc_version": ifc_version,
        "export_base_quantities": export_base_quantities,
        "split_walls_by_level": split_walls_by_level,
        "include_steel_elements": include_steel_elements,
        "export_bounding_box": export_bounding_box
    }
    response = await revit_post("/export_ifc/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_ifc_with_mapping(
    output_path: str,
    mapping_file: Optional[str] = None,
    ifc_version: str = "IFC4",
    ctx: Context = None
) -> str:
    """
    Export to IFC with custom property mapping.

    Args:
        output_path: Output IFC file path
        mapping_file: Path to IFC mapping file (.txt)
        ifc_version: IFC2x3 or IFC4

    Returns:
        JSON with export results
    """
    payload = {
        "output_path": output_path,
        "mapping_file": mapping_file,
        "ifc_version": ifc_version
    }
    response = await revit_post("/export_ifc_mapping/", payload, ctx)
    return format_response(response)


# =============================================================================
# IMAGE EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_image(
    view_id: int,
    output_path: str,
    image_format: str = "PNG",
    resolution: int = 150,
    pixel_size: Optional[List[int]] = None,
    ctx: Context = None
) -> str:
    """
    Export a view to an image file.

    Args:
        view_id: View element ID to export
        output_path: Output file path
        image_format: PNG, JPEG, BMP, or TIFF
        resolution: DPI resolution (72, 150, 300, 600)
        pixel_size: Optional [width, height] in pixels

    Returns:
        JSON with export results
    """
    payload = {
        "view_id": view_id,
        "output_path": output_path,
        "image_format": image_format,
        "resolution": resolution,
        "pixel_size": pixel_size
    }
    response = await revit_post("/export_image/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_images_batch(
    view_ids: List[int],
    output_folder: str,
    image_format: str = "PNG",
    resolution: int = 150,
    ctx: Context = None
) -> str:
    """
    Export multiple views to images.

    Args:
        view_ids: List of view element IDs
        output_folder: Destination folder
        image_format: PNG, JPEG, BMP, or TIFF
        resolution: DPI resolution

    Returns:
        JSON with export results
    """
    payload = {
        "view_ids": view_ids,
        "output_folder": output_folder,
        "image_format": image_format,
        "resolution": resolution
    }
    response = await revit_post("/export_images_batch/", payload, ctx)
    return format_response(response)


# =============================================================================
# 3D MODEL EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_fbx(
    view_id: int,
    output_path: str,
    include_linked: bool = False,
    ctx: Context = None
) -> str:
    """
    Export 3D view to FBX format for rendering software.

    Args:
        view_id: 3D view element ID
        output_path: Output FBX file path
        include_linked: Include linked models

    Returns:
        JSON with export results
    """
    payload = {
        "view_id": view_id,
        "output_path": output_path,
        "include_linked": include_linked
    }
    response = await revit_post("/export_fbx/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_sat(
    element_ids: List[int],
    output_path: str,
    ctx: Context = None
) -> str:
    """
    Export elements to SAT (ACIS) format.

    Args:
        element_ids: List of element IDs to export
        output_path: Output SAT file path

    Returns:
        JSON with export results
    """
    payload = {
        "element_ids": element_ids,
        "output_path": output_path
    }
    response = await revit_post("/export_sat/", payload, ctx)
    return format_response(response)


# =============================================================================
# SCHEDULE EXPORT
# =============================================================================

@mcp.tool()
@register_tool
async def export_schedule_to_csv(
    schedule_id: int,
    output_path: str,
    include_headers: bool = True,
    ctx: Context = None
) -> str:
    """
    Export a schedule to CSV format.

    Args:
        schedule_id: Schedule element ID
        output_path: Output CSV file path
        include_headers: Include column headers

    Returns:
        JSON with export results
    """
    payload = {
        "schedule_id": schedule_id,
        "output_path": output_path,
        "include_headers": include_headers
    }
    response = await revit_post("/export_schedule_csv/", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def export_schedule_to_excel(
    schedule_id: int,
    output_path: str,
    ctx: Context = None
) -> str:
    """
    Export a schedule to Excel format.

    Args:
        schedule_id: Schedule element ID
        output_path: Output XLSX file path

    Returns:
        JSON with export results
    """
    payload = {
        "schedule_id": schedule_id,
        "output_path": output_path
    }
    response = await revit_post("/export_schedule_excel/", payload, ctx)
    return format_response(response)
