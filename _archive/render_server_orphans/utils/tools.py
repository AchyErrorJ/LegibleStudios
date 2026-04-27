
import asyncio
import json
from typing import Dict, Any

# This will be set by server.py
registry = None

TOOL_ALIASES = {
    "get_current_document": "get_revit_model_info",
    "place_furniture": "place_family",
    "place_revit_door": "place_door",
    "place_revit_window": "place_window"
}
registry = None


def set_registry(reg):
    """Set the tool registry"""
    global registry
    registry = reg

async def execute_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Execute a tool with timeout"""
    tool_name = TOOL_ALIASES.get(tool_name, tool_name)
    
    # Fix common parameter mistakes
    param_fixes = {
        "level_id": "level_name",
        "wall_type_name": "wall_type",
        "wall_id": "host_id",
        "location": "point",
        "door_type": "type_name",
        "window_type": "type_name"
    }
    tool_input = {param_fixes.get(k, k): v for k, v in tool_input.items()}
    
    if not registry or tool_name not in registry.tools_map:
        
        available = list(registry.tools_map.keys()) if registry else []
        print(f"❌ Tool '{tool_name}' not found!")
        print(f"   Registry exists: {registry is not None}")
        print(f"   Available tools: {available[:5]}...")
       
        
        return f"Error: Tool {tool_name} not found."
    
    try:
        func = registry.tools_map[tool_name]
        print(f"🛠️ Executing {tool_name} with args: {tool_input}")
        result = await asyncio.wait_for(func(**tool_input), timeout=30.0)
        print(f"✅ {tool_name} completed successfully")
        return str(result)
    except asyncio.TimeoutError:
        print(f"⏰ {tool_name} timed out")
        return f"Error: {tool_name} timed out"
    except Exception as e:
        print(f"❌ Error executing {tool_name}: {e}")
        return f"Error: {str(e)}"

def summarize_tool_result(result: str, max_length: int = 500) -> str:
    """Summarize verbose tool results to reduce token usage"""
    if len(result) <= max_length:
        return result
    
    try:
        data = json.loads(result)
        if isinstance(data, list):
            count = len(data)
            if count > 3:
                return json.dumps({"count": count, "sample": data[:3]})
            return json.dumps(data)
        if isinstance(data, dict):
            if "error" in data:
                return result[:max_length]
            return json.dumps(data)
    except:
        pass
    
    return result[:max_length] + "...[truncated]"
