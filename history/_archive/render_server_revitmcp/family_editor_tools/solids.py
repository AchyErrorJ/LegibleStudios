# -*- coding: utf-8 -*-
from mcp.server.fastmcp import Context
from tools.utils import format_response  # Import the fixed utility
from typing import List

def register_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register geometry creation tools for Family Editor."""

    @mcp.tool()
    async def create_family_extrusion(
        points: List[List[float]],
        height: float,
        category_name: str = "Generic Models",
        base_offset: float = 0.0,
        ctx: Context = None
    ) -> str:
        """
        PRIMARY tool for creating 3D geometry in the Family Editor.
        Use this to create boxes, furniture parts, or components.
        
        CRITICAL RULES:
        1. DO NOT use 'create_wall' or 'create_level' inside the Family Editor.
        2. If the user asks for a "box", "shape", or "mass" in Family Mode, use THIS tool.
        3. No 'Level' is required; geometry is placed at the origin (Z=0) by default.
        
        Args:
            points: List of [x, y] coordinates forming a CLOSED loop.
            height: Vertical height in Feet.
        """
                
        # 1. Sanitize Points (Handle 2D inputs by adding Z=0)
        safe_points = []
        for p in points:
            x = float(p[0])
            y = float(p[1])
            z = float(p[2]) if len(p) > 2 else 0.0
            safe_points.append([x, y, z])

        payload = {
            "points": safe_points,
            "height": float(height),
            "category_name": str(category_name),
            "base_offset": float(base_offset)
        }
        
        # 2. Call Revit (using the route that worked in your logs)
        response = await revit_post("/family/create_extrusion/", payload, ctx)
        
        # 3. Format Response (Using the fixed utils.py)
        return format_response(response)