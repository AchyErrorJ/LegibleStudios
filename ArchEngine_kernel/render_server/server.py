import uvicorn
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import httpx  # <--- NEW: Needed to talk to Revit
import json

# Connect to your Orchestrator
from client_orchestrator import create_orchestrator

# Import all registered MCP tools
from tools import TOOL_FUNCTIONS

# Import QBD Interview for design conversations
from qbd_interview import QBDInterview, InterviewPhase


# =============================================================================
# CHAT RESPONSE FORMATTING
# =============================================================================

def format_results_for_chat(execution_results: Dict) -> Dict:
    """
    Format execution results for chat display.
    Returns summary text and structured data for expandable display.
    """
    if not execution_results:
        return {"summary": "No results", "items": [], "has_data": False}

    results = execution_results.get("results", [])
    variables = execution_results.get("variables", {})

    summary_parts = []
    all_items = []

    for step_result in results:
        tool_name = step_result.get("tool", "unknown")
        result_data = step_result.get("result", {})
        success = step_result.get("success", False)

        # Handle list_available_tools specially (before generic list_ check)
        if tool_name == "list_available_tools":
            if isinstance(result_data, dict) and result_data.get("status") == "success":
                categories = result_data.get("categories", {})
                total = result_data.get("total_tools", 0)
                summary_parts.append(f"Available Tools: {total} total")
                for cat_name, tools in categories.items():
                    all_items.append({
                        "type": "tool_category",
                        "name": cat_name,
                        "tools": tools,
                        "count": len(tools)
                    })

        # Handle mode commands
        elif tool_name == "list_modes":
            if isinstance(result_data, dict):
                current = result_data.get("current_mode", "all")
                modes = result_data.get("modes", {})
                active_count = result_data.get("active_tool_count", 0)
                summary_parts.append(f"Tool Modes (current: {current}, {active_count} tools active)")
                for mode_name, mode_info in modes.items():
                    all_items.append({
                        "type": "mode",
                        "name": mode_name,
                        "display_name": mode_info.get("name", mode_name),
                        "description": mode_info.get("description", ""),
                        "tool_count": mode_info.get("tool_count", 0),
                        "is_active": mode_info.get("is_active", False)
                    })

        elif tool_name == "set_mode":
            if isinstance(result_data, dict) and result_data.get("status") == "success":
                mode_name = result_data.get("name", result_data.get("mode", "unknown"))
                tool_count = result_data.get("tool_count", 0)
                summary_parts.append(f"Switched to {mode_name} ({tool_count} tools)")
                if result_data.get("tools"):
                    all_items.append({
                        "type": "mode_tools",
                        "mode": mode_name,
                        "tools": result_data.get("tools", [])[:20]  # Limit display
                    })

        # Handle list operations - these should show data
        elif tool_name.startswith("list_"):
            items = format_list_result(tool_name, result_data)
            if items:
                all_items.extend(items)
                summary_parts.append(f"Found {len(items)} {tool_name.replace('list_', '').replace('_', ' ')}")

        # Handle creation operations
        elif "create" in tool_name or "place" in tool_name:
            if isinstance(result_data, dict):
                if result_data.get("status") == "batch_complete":
                    count = len(result_data.get("results", []))
                    summary_parts.append(f"Created {count} {tool_name.replace('create_', '').replace('_batch', 's')}")
                elif result_data.get("status") == "success":
                    element_id = result_data.get("id", "?")
                    summary_parts.append(f"Created {tool_name.replace('create_', '')} (ID: {element_id})")

        # Handle discovery/analysis
        elif tool_name == "analyze_geometry_bounds":
            if isinstance(result_data, dict) and result_data.get("status") == "success":
                bounds = result_data.get("bounds", {})
                width = bounds.get("width", 0)
                depth = bounds.get("depth", 0)
                area = bounds.get("area", 0)
                summary_parts.append(f"Bounds: {width:.1f}' x {depth:.1f}' ({area:.0f} sqft)")
                all_items.append({
                    "type": "bounds",
                    "data": bounds
                })

        # Handle status
        elif tool_name in ["get_revit_status", "get_status"]:
            if isinstance(result_data, dict):
                status = result_data.get("status", "unknown")
                model = result_data.get("model_name", result_data.get("document", ""))
                summary_parts.append(f"Revit: {status}" + (f" - {model}" if model else ""))
                all_items.append({
                    "type": "status",
                    "data": result_data
                })

    # Build final summary
    if summary_parts:
        summary = " | ".join(summary_parts)
    else:
        success_count = sum(1 for r in results if r.get("success"))
        summary = f"Executed {len(results)} steps ({success_count} successful)"

    return {
        "summary": summary,
        "items": all_items,
        "has_data": len(all_items) > 0,
        "variables": {k: v for k, v in variables.items() if not k.startswith("_")}
    }


def format_list_result(tool_name: str, result_data: Any) -> List[Dict]:
    """Format list operation results into displayable items"""
    items = []

    if not isinstance(result_data, list):
        return items

    for item in result_data:
        if isinstance(item, dict):
            formatted = {
                "id": str(item.get("id", "")),
                "name": item.get("name", item.get("type_name", "")),
            }

            # Add type-specific fields
            if tool_name == "list_levels":
                formatted["elevation"] = item.get("elevation", 0)
                formatted["type"] = "level"
            elif tool_name == "list_walls":
                formatted["start"] = item.get("start", "")
                formatted["end"] = item.get("end", "")
                formatted["type"] = "wall"
            elif tool_name in ["list_wall_types", "list_door_types", "list_window_types"]:
                formatted["type"] = tool_name.replace("list_", "").replace("_types", "")
            elif tool_name == "list_views":
                formatted["view_type"] = item.get("type", "")
                formatted["type"] = "view"
            elif tool_name == "list_families":
                formatted["category"] = item.get("category", "")
                formatted["type"] = "family"

            items.append(formatted)

    return items


def format_items_as_markdown(items: List[Dict], item_type: str = "") -> str:
    """Format items as markdown for chat display"""
    if not items:
        return ""

    lines = []

    # Group by type if mixed
    for item in items[:30]:  # Limit to 30 items
        if item.get("type") == "level":
            lines.append(f"- **{item['name']}** (ID: {item['id']}) - Elevation: {item.get('elevation', 0):.1f}'")
        elif item.get("type") == "wall":
            lines.append(f"- Wall {item['id']}: {item.get('start', '')} → {item.get('end', '')}")
        elif item.get("type") == "view":
            lines.append(f"- **{item['name']}** ({item.get('view_type', '')}) - ID: {item['id']}")
        elif item.get("type") == "family":
            lines.append(f"- **{item['name']}** [{item.get('category', '')}]")
        elif item.get("type") == "tool_category":
            cat_name = item.get("name", "unknown").replace("_", " ").title()
            tools = item.get("tools", [])
            lines.append(f"\n**{cat_name}** ({len(tools)})")
            for tool in tools:
                lines.append(f"  - {tool}")
        elif item.get("type") == "mode":
            mode_name = item.get("display_name", item.get("name", "unknown"))
            desc = item.get("description", "")
            count = item.get("tool_count", 0)
            active = " [ACTIVE]" if item.get("is_active") else ""
            lines.append(f"- **{mode_name}**{active} ({count} tools)")
            if desc:
                lines.append(f"  {desc}")
        elif item.get("type") == "mode_tools":
            tools = item.get("tools", [])
            lines.append(f"\nActive tools ({len(tools)} shown):")
            for tool in tools[:15]:
                lines.append(f"  - {tool}")
            if len(tools) > 15:
                lines.append(f"  ... and {len(tools) - 15} more")
        else:
            name = item.get("name", item.get("id", "?"))
            if "id" in item:
                lines.append(f"- {name} (ID: {item['id']})")
            else:
                lines.append(f"- {name}")

    if len(items) > 30:
        lines.append(f"... and {len(items) - 30} more")

    return "\n".join(lines)

app = FastAPI()

# --- 1. NEW: Global Log Queue ---
# This holds messages waiting to be sent to the UI
log_queue = asyncio.Queue()

async def broadcast_log(message: str, type: str = "info"):
    """Push a log message to the UI"""
    payload = json.dumps({"type": type, "message": message})
    await log_queue.put(f"data: {payload}\n\n")

    # Also print to terminal so you don't lose that visibility
    print(f"[{type.upper()}] {message}")

# 1. CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

# Initialize the Brain
print(" Initializing Orchestrator...")
orchestrator = create_orchestrator()

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, Any]]] = []
    image: Optional[str] = None

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"\n[UI Request]: {request.message}")
    if request.image:
         print(f"   📎 Image attached ({len(request.image)} bytes)")

    try:
        # Pass the image data to execute
        result = await orchestrator.execute(request.message, image_data=request.image)

        # Format response with summary + data
        if result.get("success"):
            # Check if this is a conversational response (has reply but no execution_results)
            if result.get("reply") and not result.get("execution_results"):
                return {
                    "reply": result["reply"],
                    "data": [],
                    "strategy": result.get("strategy", "conversational"),
                    "success": True
                }

            execution_results = result.get("execution_results", {})
            display_data = format_results_for_chat(execution_results)

            # Build reply with summary and optional detailed data
            reply_parts = []

            if result.get("strategy") == "template":
                reply_parts.append(f"**{result.get('template_name', 'Template')}**")
            elif result.get("strategy") == "llm_plan":
                reply_parts.append("**Plan Executed**")
            elif result.get("strategy") == "direct":
                reply_parts.append("**Direct Command**")

            # Add summary
            if display_data.get("summary"):
                reply_parts.append(display_data["summary"])

            # Add formatted data if available
            if display_data.get("has_data") and display_data.get("items"):
                markdown_data = format_items_as_markdown(display_data["items"])
                if markdown_data:
                    reply_parts.append("\n" + markdown_data)

            reply = "\n\n".join(reply_parts) if reply_parts else "Command executed."

            return {
                "reply": reply,
                "data": display_data.get("items", []),
                "strategy": result.get("strategy"),
                "success": True
            }
        else:
            # Check for error reply from LLM fallback
            if result.get("reply"):
                return {
                    "reply": result["reply"],
                    "data": [],
                    "strategy": result.get("strategy", "error"),
                    "success": False
                }
            return {
                "reply": f"**Error:** {result.get('error', 'Unknown failure')}",
                "success": False
            }

    except Exception as e:
        print(f" Server Error: {e}")
        import traceback
        traceback.print_exc()
        return {"reply": f"Critical Server Error: {str(e)}", "success": False}

# =============================================================================
# TOOL DISCOVERY ENDPOINT
# =============================================================================

TOOL_REGISTRY = {
    "categories": {
        "creation": {
            "description": "Create geometry and elements",
            "tools": [
                {"name": "create_wall", "description": "Create a single wall"},
                {"name": "create_walls_batch", "description": "Create multiple walls at once"},
                {"name": "create_floor", "description": "Create a floor from boundary points"},
                {"name": "create_roof_footprint", "description": "Create a roof from boundary"},
                {"name": "create_level", "description": "Create a new level"},
                {"name": "create_levels_batch", "description": "Create multiple levels"},
                {"name": "create_room", "description": "Create a room"},
                {"name": "create_dimension", "description": "Create a dimension"},
                {"name": "create_tag", "description": "Create element tags"},
            ]
        },
        "placement": {
            "description": "Place families and hosted elements",
            "tools": [
                {"name": "place_family", "description": "Place a family instance"},
                {"name": "place_door", "description": "Place a door in a wall"},
                {"name": "place_window", "description": "Place a window in a wall"},
                {"name": "place_hosted_batch", "description": "Place multiple hosted elements"},
                {"name": "load_family", "description": "Load a family into the project"},
            ]
        },
        "listing": {
            "description": "Query model information",
            "tools": [
                {"name": "list_levels", "description": "List all levels"},
                {"name": "list_walls", "description": "List all walls with geometry"},
                {"name": "list_wall_types", "description": "List available wall types"},
                {"name": "list_door_types", "description": "List available door types"},
                {"name": "list_window_types", "description": "List available window types"},
                {"name": "list_views", "description": "List all views"},
                {"name": "list_families", "description": "List loaded families"},
                {"name": "list_elements", "description": "List elements by category"},
            ]
        },
        "discovery": {
            "description": "Analyze and discover geometry",
            "tools": [
                {"name": "analyze_geometry_bounds", "description": "Calculate bounding box from walls"},
                {"name": "get_revit_status", "description": "Check Revit connection status"},
                {"name": "get_revit_model_info", "description": "Get current model information"},
            ]
        },
        "generation": {
            "description": "Generate complex layouts",
            "tools": [
                {"name": "generate_floor_plan_walls", "description": "Generate room layout with walls"},
                {"name": "generate_layout_from_image", "description": "Create layout from sketch image"},
                {"name": "create_family_from_photo", "description": "Create family from photo"},
            ]
        },
        "deletion": {
            "description": "Remove elements",
            "tools": [
                {"name": "delete_element", "description": "Delete a single element"},
                {"name": "delete_elements", "description": "Delete multiple elements"},
            ]
        },
        "schedules": {
            "description": "Create and manage schedules",
            "tools": [
                {"name": "create_schedule", "description": "Create a new schedule"},
                {"name": "list_schedules", "description": "List all schedules in project"},
                {"name": "get_schedulable_fields", "description": "Get available fields for a schedule"},
                {"name": "add_schedule_fields", "description": "Add columns to a schedule"},
                {"name": "set_schedule_filter", "description": "Filter schedule by field value"},
                {"name": "set_schedule_grouping", "description": "Group schedule by field"},
                {"name": "set_schedule_sorting", "description": "Sort schedule by field"},
                {"name": "get_schedule_data", "description": "Get all rows from schedule"},
                {"name": "remove_schedule_field", "description": "Remove a column from schedule"},
                {"name": "delete_schedule", "description": "Delete a schedule"},
            ]
        },
        "assemblies": {
            "description": "Wall types and assembly views",
            "tools": [
                {"name": "list_wall_types", "description": "List available wall types"},
                {"name": "list_wall_type_layers", "description": "Get layer structure of wall type"},
                {"name": "create_wall_type", "description": "Create new wall type with layers"},
                {"name": "duplicate_wall_type", "description": "Duplicate wall type with modifications"},
                {"name": "create_assembly_view", "description": "Generate assembly views for element"},
            ]
        },
        "physics_structural": {
            "description": "Structural analysis - beams, columns, floors",
            "tools": [
                {"name": "analyze_beam", "description": "Analyze beam for bending/deflection"},
                {"name": "analyze_column", "description": "Analyze column for buckling"},
                {"name": "analyze_floor_system", "description": "Analyze floor joist system"},
            ]
        },
        "physics_thermal": {
            "description": "Thermal analysis - R-values, heat loss, condensation",
            "tools": [
                {"name": "analyze_thermal_assembly", "description": "Get R-value, U-factor, condensation risk"},
                {"name": "calculate_heat_loss", "description": "Calculate building heat loss (Manual J)"},
                {"name": "list_assembly_presets", "description": "List wall/floor/roof assembly presets"},
                {"name": "get_assembly_details", "description": "Get layer-by-layer assembly breakdown"},
            ]
        },
        "physics_lighting": {
            "description": "Lighting analysis - daylighting, electric lighting",
            "tools": [
                {"name": "analyze_daylighting", "description": "Calculate daylight factor"},
                {"name": "calculate_electric_lighting", "description": "Calculate fixture requirements"},
            ]
        },
        "physics_acoustic": {
            "description": "Acoustic analysis - STC, reverberation",
            "tools": [
                {"name": "analyze_wall_stc", "description": "Estimate wall STC rating"},
                {"name": "calculate_reverberation_time", "description": "Calculate room RT60"},
            ]
        },
        "physics_materials": {
            "description": "Materials and construction takeoff",
            "tools": [
                {"name": "list_materials", "description": "List material thermal properties"},
                {"name": "estimate_fasteners", "description": "Estimate fastener quantities"},
                {"name": "check_ifc_support", "description": "Check IFC import availability"},
            ]
        }
    }
}


@app.get("/list-tools")
async def list_tools():
    """Return all available tools organized by category"""
    # Combine static registry with dynamically registered tools
    result = dict(TOOL_REGISTRY)

    # Add all MCP tools count
    result["mcp_tools_count"] = len(TOOL_FUNCTIONS)
    result["mcp_tools"] = sorted(TOOL_FUNCTIONS.keys())

    return result


@app.get("/tools/{category}")
async def list_tools_by_category(category: str):
    """Return tools for a specific category"""
    cat_data = TOOL_REGISTRY["categories"].get(category)
    if not cat_data:
        return {"error": f"Unknown category: {category}", "available": list(TOOL_REGISTRY["categories"].keys())}
    return cat_data


# =============================================================================
# TOOL MODE ENDPOINTS
# =============================================================================

try:
    from tool_modes import get_mode_manager, TOOL_MODES
    MODES_AVAILABLE = True
except ImportError:
    MODES_AVAILABLE = False

@app.get("/modes")
async def get_modes():
    """Get all available tool modes"""
    if not MODES_AVAILABLE:
        return {"error": "Tool modes not available"}
    return get_mode_manager().get_modes()

@app.post("/modes/{mode_name}")
async def set_mode(mode_name: str):
    """Set the active tool mode"""
    if not MODES_AVAILABLE:
        return {"error": "Tool modes not available"}
    return get_mode_manager().set_mode(mode_name)

@app.get("/modes/current")
async def get_current_mode():
    """Get the current active mode"""
    if not MODES_AVAILABLE:
        return {"error": "Tool modes not available"}
    modes = get_mode_manager().get_modes()
    return {
        "current_mode": modes["current_mode"],
        "active_tool_count": modes["active_tool_count"]
    }

@app.get("/modes/{mode_name}/tools")
async def get_mode_tools(mode_name: str):
    """Get tools for a specific mode"""
    if not MODES_AVAILABLE:
        return {"error": "Tool modes not available"}
    if mode_name not in TOOL_MODES:
        return {"error": f"Unknown mode: {mode_name}", "available": list(TOOL_MODES.keys())}
    return {
        "mode": mode_name,
        "tools": TOOL_MODES[mode_name]["tools"],
        "count": len(TOOL_MODES[mode_name]["tools"])
    }


# =============================================================================
# MCP TOOL ENDPOINTS
# =============================================================================

class MCPToolRequest(BaseModel):
    """Request model for MCP tool calls"""
    tool_name: str
    arguments: Dict[str, Any] = {}


@app.post("/mcp/call")
async def call_mcp_tool(request: MCPToolRequest):
    """Call an MCP tool directly"""
    tool_name = request.tool_name
    arguments = request.arguments

    if tool_name not in TOOL_FUNCTIONS:
        return {
            "status": "error",
            "message": f"Unknown tool: {tool_name}",
            "available_tools": sorted(TOOL_FUNCTIONS.keys())
        }

    try:
        tool_func = TOOL_FUNCTIONS[tool_name]
        # Call the async tool function
        result = await tool_func(**arguments)
        return {
            "status": "success",
            "tool": tool_name,
            "result": json.loads(result) if isinstance(result, str) else result
        }
    except Exception as e:
        return {
            "status": "error",
            "tool": tool_name,
            "message": str(e)
        }


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List all MCP tools with their docstrings"""
    tools = {}
    for name, func in TOOL_FUNCTIONS.items():
        tools[name] = {
            "name": name,
            "description": (func.__doc__ or "").split("\n")[0].strip()
        }
    return {
        "count": len(tools),
        "tools": tools
    }


# --- 3. UPDATED: Real Log Stream ---
@app.get("/log-stream")
async def log_stream():
    async def event_generator():
        while True:
            # Wait for a new message in the queue
            data = await log_queue.get()
            yield data
            # No sleep needed here; queue.get() waits automatically
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- 🛑 THE FIX: PROXY ROUTE ---
# This catches ANY request to /revit_mcp/... and forwards it to port 48884
# Replace the old proxy_to_revit function with this one:
#@app.api_route("/revit_mcp/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
#async def proxy_to_revit(path_name: str, request: Request):
#    
#    # 1. Build the destination URL (Revit Port 48884)
#    revit_url = f"http://localhost:48884/revit_mcp/{path_name}"
#    
#    # 2. Grab the original Method (e.g., POST) and Body (Raw Data)
#    method = request.method
#    body = await request.body()
#    
#    print(f"   🔄 Proxying {method} request to: {revit_url}")
#    
#    async with httpx.AsyncClient() as client:
#        try:
#            # 3. Forward the request exactly as is (Wait up to 90 seconds)
#            resp = await client.request(
#                method=method,
#                url=revit_url,
#                content=body,
#                timeout=90.0
#           )
#            
#            # Check for errors from Revit
#            if resp.status_code != 200:
#                print(f"   ⚠️ Revit Error {resp.status_code}: {resp.text}")
#                
#            return resp.json()
#           
#        except httpx.ReadTimeout:
#             print(f"   ⏳ Revit timed out (it might be busy processing geometry).")
#             # We return a fake success to stop the UI from crashing, 
#             # assuming Revit is just slow but working.
#             return {"status": "processing", "message": "Revit is taking a long time, check the window."}
#             
#        except Exception as e:
#             print(f"   ❌ Proxy Connection Error: {e}")
#             return {"error": str(e)}


# =============================================================================
# INTERVIEW ENDPOINTS - Design conversation through chat
# =============================================================================

# In-memory session storage (simple dict for now)
interview_sessions: Dict[str, QBDInterview] = {}


class InterviewAnswerRequest(BaseModel):
    answer: str


@app.post("/interview/start")
async def start_interview():
    """Start a new design interview session"""
    interview = QBDInterview()
    greeting = interview.start()

    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    interview_sessions[session_id] = interview

    await broadcast_log(f"Started design interview: {session_id}", "info")

    return {
        "session_id": session_id,
        "message": greeting,
        "phase": interview.context.phase.value,
        "progress": 0,
        "requirements": {}
    }


@app.post("/interview/{session_id}/answer")
async def process_interview_answer(session_id: str, request: InterviewAnswerRequest):
    """Process an answer in the interview"""
    interview = interview_sessions.get(session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Process the answer
    response = interview.process_input(request.answer)

    # Calculate progress (rough estimate based on phase)
    phase_progress = {
        InterviewPhase.GREETING: 0,
        InterviewPhase.BUILDING_TYPE: 15,
        InterviewPhase.SIZE_SCOPE: 30,
        InterviewPhase.ROOM_REQUIREMENTS: 50,
        InterviewPhase.SPECIAL_FEATURES: 65,
        InterviewPhase.STYLE_PREFERENCES: 80,
        InterviewPhase.REVIEW: 90,
        InterviewPhase.GENERATING: 95,
        InterviewPhase.COMPLETE: 100,
    }
    progress = phase_progress.get(interview.context.phase, 50)

    # Get current requirements
    req = interview.context.requirements
    requirements = {
        "building_type": req.building_type,
        "sqft": req.target_sqft,
        "bedrooms": req.bedrooms,
        "bathrooms": req.bathrooms,
        "garage": req.garage,
        "style": req.style,
    }

    return {
        "session_id": session_id,
        "message": response,
        "phase": interview.context.phase.value,
        "progress": progress,
        "requirements": requirements,
        "is_complete": interview.context.phase == InterviewPhase.COMPLETE
    }


@app.get("/interview/{session_id}/state")
async def get_interview_state(session_id: str):
    """Get current interview state"""
    interview = interview_sessions.get(session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found")

    req = interview.context.requirements
    return {
        "session_id": session_id,
        "phase": interview.context.phase.value,
        "requirements": {
            "building_type": req.building_type,
            "sqft": req.target_sqft,
            "bedrooms": req.bedrooms,
            "bathrooms": req.bathrooms,
            "garage": req.garage,
            "style": req.style,
            "special_rooms": req.special_rooms,
        },
        "history": interview.context.history
    }


@app.post("/interview/{session_id}/generate")
async def generate_from_interview(session_id: str, creative_mode: bool = False):
    """Generate floor plan from completed interview"""
    interview = interview_sessions.get(session_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found")

    # Get QBD answers from interview
    from qbd_layout_generator import generate_floor_plan_from_qbd, OutputFormat

    answers = interview.context.requirements.to_qbd_answers()

    await broadcast_log(f"Generating floor plan from interview {session_id}", "info")

    try:
        result = generate_floor_plan_from_qbd(
            answers,
            output_format=OutputFormat.ARCHENGINE,
            creative_mode=creative_mode
        )

        if result["success"]:
            await broadcast_log(
                f"Generated {result['summary']['rooms_placed']}/{result['summary']['rooms_requested']} rooms",
                "success"
            )
        else:
            await broadcast_log(f"Generation failed: {result.get('error', 'Unknown')}", "error")

        return result

    except Exception as e:
        await broadcast_log(f"Generation error: {str(e)}", "error")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/interview/{session_id}")
async def end_interview(session_id: str):
    """End and cleanup an interview session"""
    if session_id in interview_sessions:
        del interview_sessions[session_id]
        return {"status": "ended", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Interview session not found")


if __name__ == "__main__":
    print("\n Revit AI Server Running on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)