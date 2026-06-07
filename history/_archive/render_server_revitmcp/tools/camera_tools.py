import httpx
import json
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

REVIT_API_URL = "http://localhost:48884/revit_mcp"

async def revit_get(endpoint: str, ctx: Context = None) -> dict:
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

def format_response(response: dict) -> str:
    return json.dumps(response, indent=2)


@mcp.tool()
@register_tool
async def export_camera(output_path: str = None, ctx: Context = None) -> str:
    """
    Exports the camera from the active Revit 3D view to camera.json.
    
    This allows the Channel Extractor UI to render from the exact same viewpoint as Revit.
    
    Workflow:
    1. In Revit, open a 3D view and orbit to your desired angle
    2. Call this tool to export the camera
    3. In the Channel Extractor UI, click "Load from Revit" to sync the camera
    4. Extract channels - they will match your Revit view exactly
    
    Args:
        output_path: Optional custom path. Default: C:\\Users\\jerro\\Desktop\\channel_test\\camera.json
    """
    endpoint = "/export_camera"
    if output_path:
        endpoint += f"?outputPath={output_path}"
    
    response = await revit_get(endpoint, ctx)
    return format_response(response)