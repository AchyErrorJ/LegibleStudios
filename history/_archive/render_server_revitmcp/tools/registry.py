
# tools/registry.py
from mcp.server.fastmcp import FastMCP

# --- 1. Initialize the MCP Server Instance (MISSING LINE) ---
# This object is required by all your tool files (@mcp.tool)
mcp = FastMCP("RevitMCP")

# This is the master dictionary
TOOL_FUNCTIONS = {}

def register_tool(func):
    """Decorator to register a function as a tool."""
    TOOL_FUNCTIONS[func.__name__] = func
    return func
