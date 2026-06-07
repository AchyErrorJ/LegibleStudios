import httpx
import json
import sys
import os
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# Import channel_extractor from parent directory
try:
    from channel_extractor import render_channels as extract_channels
except ImportError:
    # Fallback: add parent to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from channel_extractor import render_channels as extract_channels

REVIT_API_URL = "http://localhost:48884/revit_mcp"

async def revit_post(endpoint: str, payload: dict, ctx: Context = None) -> dict:
    """Standard helper to send POST requests."""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"): url += "/"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=60.0)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

def format_response(response: dict) -> str:
    return json.dumps(response, indent=2)


@mcp.tool()
@register_tool
async def export_view_for_channels(
    view_id: str,
    format: str = "fbx",
    ctx: Context = None
) -> str:
    """
    Exports a Revit 3D view's geometry and camera data for channel-based rendering.
    """
    payload = {
        "view_id": view_id,
        "format": format
    }
    response = await revit_post("/export_view_for_channels", payload, ctx)
    return format_response(response)


@mcp.tool()
@register_tool
async def render_channels_from_view(
    view_id: str,
    output_dir: str,
    channels: list[str] = None,
    resolution_width: int = 3840,
    resolution_height: int = 2160,
    format: str = "fbx",
    ctx: Context = None
) -> str:
    """
    Full pipeline: exports Revit view and extracts render channels for AI processing.
    """
    # Step 1: Export from Revit
    payload = {
        "view_id": view_id,
        "format": format
    }
    export_response = await revit_post("/export_view_for_channels", payload, ctx)
    
    if isinstance(export_response, str):
        export_response = json.loads(export_response)
    
    if export_response.get("status") == "error":
        return format_response(export_response)
    
    # Step 2: Extract channels
    if channels is None:
        channels = ["depth", "normals", "material_id", "edges"]
    
    channel_paths = await extract_channels(
        view_export_data=export_response,
        output_dir=output_dir,
        channels=channels,
        resolution=(resolution_width, resolution_height)
    )
    
    return format_response({
        "status": "success",
        "export": export_response,
        "channels": channel_paths
    })

@mcp.tool()
@register_tool
async def enhance_render(
    depth_path: str,
    prompt: str,
    output_path: str,
    material_path: str = None, # Added for Multi-ControlNet
    strength: float = 0.8,     # Renamed from guidance for clarity
    steps: int = 30,
    ctx: Context = None
) -> str:
    """
    Runs AI enhancement on a rendered depth map (and optional material map).
    """
    ctx.info(f"Starting AI enhancement for: {prompt}")
    
    result = await enhance_with_ai(
        depth_path=depth_path,
        material_path=material_path, # Pass the material map
        prompt=prompt,
        output_path=output_path,
        steps=steps,
        control_strength=strength
    )
    
    return format_response(result)

@mcp.tool()
@register_tool
async def run_visual_pipeline(
    view_id: str,
    output_dir: str,
    prompt: str,
    resolution_width: int = 1024, # Increased default for AI
    resolution_height: int = 1024,
    ctx: Context = None
) -> str:
    """
    End-to-end pipeline: Exports Revit view -> Extracts Channels -> AI Enhancement.
    """
    # 1. Export & Extract
    ctx.info("Step 1: Exporting from Revit and extracting channels...")
    
    # Define channels needed for Multi-ControlNet
    channels = ["depth", "material_id", "normals"]
    
    # Export from Revit
    payload = {"view_id": view_id, "format": "fbx"}
    export_resp = await revit_post("/export_view_for_channels", payload, ctx)
    if isinstance(export_resp, str): export_resp = json.loads(export_resp)
    
    if export_resp.get("status") == "error":
        return format_response(export_resp)
        
    # Extract Channels
    channel_paths = await extract_channels(
        view_export_data=export_resp,
        output_dir=output_dir,
        channels=channels,
        resolution=(resolution_width, resolution_height)
    )
    
    # 2. AI Enhancement
    ctx.info("Step 2: Running AI Enhancement...")
    output_image = os.path.join(output_dir, "final_render.png")
    
    ai_result = await enhance_with_ai(
        depth_path=channel_paths["depth"],
        material_path=channel_paths["material_id"],
        prompt=prompt,
        output_path=output_image,
        steps=30,
        control_strength=0.9
    )
    
    return format_response({
        "status": "success",
        "pipeline": "complete",
        "channels": channel_paths,
        "final_render": output_image
    })