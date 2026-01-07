import httpx
import json
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# --- Configuration ---
REVIT_API_URL = "http://localhost:48884/revit_mcp"

# --- 1. DEFINE THE HELPER FUNCTION (Crucial Fix) ---
async def revit_get(endpoint: str, ctx: Context = None) -> dict:
    """Standard helper to send GET requests to the C# Revit Server."""
    url = f"{REVIT_API_URL}{endpoint}"
    # Ensure URL ends with / if your C# server expects it
    if not url.endswith("/"):
        url += "/"
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            # We assume JSON response
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {str(e)}"}

def format_response(response: dict) -> str:
    return json.dumps(response, indent=2)

# --- 2. SYSTEM / AGENT TOOLS ---

@mcp.tool()
@register_tool
async def get_revit_status(ctx: Context = None) -> str:
    """
    Checks the connection status of the Revit API server.
    Use this if tools are failing or to verify the server is running.
    """
    response = await revit_get("/status", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def get_manifest(ctx: Context = None) -> str:
    """
    Retrieves the manifest of available Revit commands/routes.
    """
    response = await revit_get("/manifest", ctx)
    return format_response(response)

@mcp.tool()
@register_tool
async def get_model_info(ctx: Context = None) -> str:
    """
    Gets basic information about the active Revit project (Title, Version, Path).
    """
    response = await revit_get("/model_info", ctx)
    return format_response(response)