# file: family_editor_tools/datums.py
from mcp.server.fastmcp import Context
from tools.utils import format_response

def register_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register datum tools (Reference Planes/Lines)."""

    @mcp.tool()
    async def create_reference_plane(
        start_point: list[float],
        end_point: list[float],
        name: str = "",
        ctx: Context = None
    ) -> str:
        """
        Creates a Reference Plane in the Family Editor.
        Use this instead of 'Levels' or 'Grids' when working in a Family.
        
        Args:
            start_point: [x, y] or [x, y, z]
            end_point: [x, y] or [x, y, z]
            name: Optional name for the plane.
        """
        
        # --- CRITICAL FIX: FORCE 3D POINTS ---
        # If input is [0, 10], this turns it into [0, 10, 0.0]
        sp = start_point if len(start_point) >= 3 else [start_point[0], start_point[1], 0.0]
        ep = end_point if len(end_point) >= 3 else [end_point[0], end_point[1], 0.0]

        payload = {
            "start_point": sp,
            "end_point": ep,
            "name": name
        }
        
        response = await revit_post("/family/create_ref_plane", payload, ctx)
        return format_response(response)