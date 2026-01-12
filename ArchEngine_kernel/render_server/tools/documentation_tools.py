import json
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# =========================================================
# KNOWLEDGE BASE: Correct Usage Examples
# =========================================================
TOOL_DOCS = {
    "walls": """
### HOW TO CREATE WALLS
Tool: create_wall OR create_walls_batch

ARGUMENTS:
- start_point: [x, y, z] (e.g. [0, 0, 0])
- end_point: [x, y, z]   (e.g. [10, 0, 0])
- level_name: String name of the level (e.g. "Level 1"). DO NOT use 'level' or IDs.
- height: Float (e.g. 12.0)
- wall_type: String name from 'list_wall_types' (e.g. "Generic - 200mm")

EXAMPLE JSON:
{
  "start_point": [0, 0, 0],
  "end_point": [20, 0, 0],
  "level_name": "Level 1",
  "height": 15.0,
  "wall_type": "Exterior - Brick on CMU"
}
""",

    "floors": """
### HOW TO CREATE FLOORS
Tool: create_floor

ARGUMENTS:
- points: A LIST of [x,y,z] points forming a CLOSED loop.
- level_name: String name (e.g. "Level 1").
- floor_type: Optional string from 'list_floor_types'.

CRITICAL FORMATTING:
You must provide a list of lists.
Correct: "points": [[0,0,0], [10,0,0], [10,10,0], [0,10,0]]
Incorrect: "points": [0,0,0, 10,0,0...]

EXAMPLE JSON:
{
  "points": [
    [0, 0, 0],
    [20, 0, 0],
    [20, 15, 0],
    [0, 15, 0]
  ],
  "level_name": "Level 1",
  "floor_type": "Generic - 12\""
}
""",

    "roofs": """
### HOW TO CREATE ROOFS
Tool: create_roof

ARGUMENTS:
- points: A LIST of [x,y,z] points forming the perimeter.
- level_name: The base level for the roof.
- slope_degrees: Float (0 = Flat, 30 = Standard Pitch).
- roof_type: Optional string from 'list_roof_types'.

EXAMPLE JSON:
{
  "points": [[0,0,20], [20,0,20], [20,20,20], [0,20,20]],
  "level_name": "Level 2",
  "slope_degrees": 25.0
}
""",

    "levels": """
### HOW TO CREATE LEVELS
Tool: create_level

ARGUMENTS:
- elevation: Float height (Z value).
- name: String unique name (e.g. "Roof").

EXAMPLE JSON:
{
  "elevation": 12.0,
  "name": "Level 2"
}
""",

    "families": """
### HOW TO PLACE FAMILIES (Furniture, Columns, etc.)
Tool: place_family

ARGUMENTS:
- family_name: The file name (e.g. "Desk").
- type_name: The specific type (e.g. "60in x 30in").
- point: [x, y, z] location.
- level_name: The host level.

Prerequisite: Run 'list_families' first to get exact names.
"""
}

# =========================================================
# TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def get_tool_documentation(topic: str, ctx: Context = None) -> str:
    """
    Retrieves the official usage guide and JSON examples for a specific topic.
    
    Args:
        topic: One of ['walls', 'floors', 'roofs', 'levels', 'families'].
    """
    topic_key = topic.lower().strip()
    
    # Fuzzy match handling
    if "wall" in topic_key: topic_key = "walls"
    elif "floor" in topic_key: topic_key = "floors"
    elif "roof" in topic_key: topic_key = "roofs"
    elif "level" in topic_key: topic_key = "levels"
    elif "family" in topic_key or "furniture" in topic_key: topic_key = "families"
    
    if topic_key in TOOL_DOCS:
        return TOOL_DOCS[topic_key]
    else:
        return f"Documentation not found for '{topic}'. Available topics: {list(TOOL_DOCS.keys())}"

@mcp.tool()
@register_tool
async def list_documentation_topics(ctx: Context = None) -> str:
    """Lists the available 'How-To' guides for Revit tools."""
    return f"Available Guides: {list(TOOL_DOCS.keys())}"