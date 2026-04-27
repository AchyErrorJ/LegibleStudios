"""
Adaptive Orchestrator for Revit MCP
Automatically selects orchestration strategy based on active LLM provider
With Vision support for image-to-layout generation
QBD (Question Based Design) for guided design workflow
"""
from pathlib import Path
import json
import os
import requests
import difflib
import re
import asyncio
import sys
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import templates
import traceback

# QBD Session Management
try:
    from qbd_session import (
        QBDSession, detect_qbd_trigger, is_continue_trigger,
        format_question_for_chat
    )
    QBD_AVAILABLE = True
except ImportError:
    QBD_AVAILABLE = False
    print("⚠️ QBD session module not available")

# Construction Detail Tools
try:
    from detail_tools import (
        create_assembly_wall, create_assembly_wall_batch,
        create_explosion_view, generate_section_detail,
        get_available_assemblies, get_assembly_info,
        detect_detail_template
    )
    DETAIL_TOOLS_AVAILABLE = True
except ImportError:
    DETAIL_TOOLS_AVAILABLE = False
    print("⚠️ Detail tools module not available")

try:
    from floor_plan_tool import generate_floor_plan_walls
except ImportError:
    generate_floor_plan_walls = None
    print("⚠️ floor_plan_tool not found - floor plan generation disabled")

# --- CRITICAL IMPORTS ---
try:
    from tools.data_tools import get_kb
except ImportError:
    try:
        from data_tools import get_kb
    except:
        get_kb = None

try:
    from vision_processor import VisionProcessor
except ImportError:
    VisionProcessor = None

try:
    from photo_to_family_processor import PhotoToFamilyProcessor
except ImportError:
    PhotoToFamilyProcessor = None

try:
    from family_builder import ParametricFamilyBuilder
except ImportError:
    ParametricFamilyBuilder = None

# Tool Mode Management
try:
    from tool_modes import get_mode_manager, COMPLETE_ENDPOINT_MAP, TOOL_MODES
    TOOL_MODES_AVAILABLE = True
except ImportError:
    TOOL_MODES_AVAILABLE = False
    COMPLETE_ENDPOINT_MAP = {}
    TOOL_MODES = {}
    print("Warning: tool_modes not available")

# Smart Tool Selector (for reducing LLM context)
try:
    from tools.tool_selector import select_tools_for_query, get_core_tools
    from tools.registry import TOOL_FUNCTIONS
    TOOL_SELECTOR_AVAILABLE = True
except ImportError:
    try:
        from tool_selector import select_tools_for_query, get_core_tools
        from registry import TOOL_FUNCTIONS
        TOOL_SELECTOR_AVAILABLE = True
    except ImportError:
        TOOL_SELECTOR_AVAILABLE = False
        select_tools_for_query = None
        get_core_tools = None
        TOOL_FUNCTIONS = {}
        print("Warning: tool_selector not available")

# --- CONFIGURATION ---
REVIT_MCP_API_URL = "http://localhost:8001"  # Python server (for /chat endpoint)
REVIT_DIRECT_API_URL = "http://localhost:48884"  # C# Revit API directly (for discovery & commands)
LM_STUDIO_API_URL = "http://localhost:1234/v1"
CONFIG_PATH = os.path.join(
    os.getenv('APPDATA', os.path.expanduser('~')),
    'RevitMCP',
    'llm_config.json'
)


def load_server_config() -> Dict:
    """Load the server configuration to determine active LLM provider"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception:
        return {"llm_provider": "lmstudio"}


# --- LM STUDIO API CLIENT ---
class LMStudioClient:
    """Direct LM Studio API client for plan generation"""

    def __init__(self):
        self.api_url = LM_STUDIO_API_URL
        self.model_name = self._get_model_from_config()

    def _get_model_from_config(self) -> str:
        """Load model name from config file"""
        
        
        config_path = Path(os.getenv('APPDATA', os.path.expanduser('~'))) / 'RevitMCP' / 'models' / 'multi_model_config.json'
        if config_path.exists():
            try:
               
                with open(config_path) as f:
                    config = json.load(f)
                # Use text_aligner model for general LLM tasks
                return config.get("text_aligner", {}).get("model_id", "qwen2.5-0.5b-instruct")
            except:
                pass
        return "qwen2.5-0.5b-instruct"  # Default fallback
    
    async def generate_plan(self, system_prompt: str, user_prompt: str) -> str:
        """Call LM Studio API to generate plan"""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 10000
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            # Strip <think> tags
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content
        except Exception as e:
            print(f"❌ LM Studio API error: {e}")
            return ""


# --- BASE ORCHESTRATOR ---
class BaseOrchestrator(ABC):
    """Abstract base class for orchestrators"""
    
    def __init__(self, provider: str):
        self.provider = provider
        self.server_url = REVIT_MCP_API_URL
    
    @abstractmethod
    async def execute(self, user_query: str, image_data: str = None) -> Dict[str, Any]:
        pass
    
    def send_to_server(self, message: str, history: List[Dict] = None) -> Dict:
        """Send request to the MCP server"""
        if history is None:
            history = []
        
        payload = {"message": message, "history": history}
        
        try:
            response = requests.post(
                f"{self.server_url}/chat",
                json=payload,
                timeout=300
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e), "reply": f"Connection error: {e}"}


# --- PYTHON PLAN EXECUTOR ---
class PlanExecutor:
    """Deterministic Python executor that runs structured plans"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        # Call Revit C# API directly (not through proxy to avoid circular requests)
        self.api_url = REVIT_DIRECT_API_URL
        self.variables = {}

        # Initialize Vector Knowledge Base
        print("   🧠 Loading Knowledge Base...")
        try:
            self.kb = get_kb() if get_kb else None
        except Exception as e:
            print(f"   ⚠️ Could not load Vector Store: {e}")
            self.kb = None

        # Initialize Vision Processor
        print("   👁️ Loading Vision Processor...")
        try:
            self.vision = VisionProcessor() if VisionProcessor else None
        except Exception as e:
            print(f"   ⚠️ Could not load Vision Processor: {e}")
            self.vision = None
    
    def execute_plan(self, plan: List[Dict], discovery_data: Dict = None) -> Dict:
        """Execute a structured plan step by step"""
        
        if discovery_data:
            self._populate_variables_from_discovery(discovery_data)
        
        print(f"📊 Starting with {len(self.variables)} variables: {list(self.variables.keys())}")
        
        results = []
        
        for i, step in enumerate(plan):
            # Normalize step format (handle 'action'/'function' -> 'tool', 'arguments' -> 'args')
            if isinstance(step, dict):
                if 'action' in step and 'tool' not in step:
                    step['tool'] = step['action']
                if 'function' in step and 'tool' not in step:
                    step['tool'] = step['function']
                if 'arguments' in step and 'args' not in step:
                    step['args'] = step['arguments']

            if not isinstance(step, dict) or 'tool' not in step:
                print(f"   ❌ MALFORMED STEP [{i}]: {step}")
                continue
                
            tool_name = step['tool']
            print(f"\n🔧 Step {i+1}/{len(plan)}: {tool_name}")
            
            # Resolve variables in args
            resolved_args = self._resolve_variables(step.get('args', {}))
            
            # Execute the tool
            result = self._execute_tool_direct(tool_name, resolved_args)

            # Handle explicit 'extract' field to store result in variables
            if 'extract' in step:
                var_name = step['extract']
                # Store the result data (handle different result formats)
                if isinstance(result, list):
                    self.variables[var_name] = result
                    print(f"   📦 Extracted {len(result)} items to ${{{var_name}}}")
                elif isinstance(result, dict):
                    if result.get('status') == 'success' and 'bounds' in result:
                        # For analyze_geometry_bounds, store bounds directly
                        self.variables[var_name] = result['bounds']
                        print(f"   📦 Extracted bounds to ${{{var_name}}}")
                    elif 'results' in result:
                        # Batch results
                        self.variables[var_name] = result['results']
                        print(f"   📦 Extracted {len(result['results'])} results to ${{{var_name}}}")
                    else:
                        self.variables[var_name] = result
                        print(f"   📦 Extracted result to ${{{var_name}}}")
                else:
                    self.variables[var_name] = result

            # Extract any new variables from result
            self._extract_variables(tool_name, result)
            
            # Check for errors
            result_str = str(result).lower()
            step_failed = "error" in result_str and "success" not in result_str
            
            results.append({
                "step": i + 1,
                "tool": tool_name,
                "result": result,
                "success": not step_failed
            })
            
            print(f"   {'✅ Complete' if not step_failed else '⚠️ May have issues'}")
        
        success_count = sum(1 for r in results if r["success"])
        return {
            "success": success_count > 0,
            "results": results,
            "variables": self.variables
        }

    def _get_endpoint_map(self, filter_by_mode: bool = False) -> Dict[str, str]:
        """Returns the mapping of tool names to API endpoints

        Args:
            filter_by_mode: If True, only return tools active in current mode
        """
        if TOOL_MODES_AVAILABLE and COMPLETE_ENDPOINT_MAP:
            if filter_by_mode:
                mode_manager = get_mode_manager()
                active_tools = mode_manager.get_active_tools()
                return {k: v for k, v in COMPLETE_ENDPOINT_MAP.items() if k in active_tools}
            return COMPLETE_ENDPOINT_MAP.copy()

        # Fallback to basic endpoint map if tool_modes not available
        return {
            "create_wall": "/revit_mcp/create_wall",
            "create_walls_batch": "/revit_mcp/create_walls_batch",
            "create_floor": "/revit_mcp/create_floor",
            "create_roof_footprint": "/revit_mcp/create_roof",
            "list_levels": "/revit_mcp/list_levels",
            "list_walls": "/revit_mcp/list_walls",
            "get_revit_status": "/revit_mcp/status",
        }

    def _resolve_variables(self, args: Dict) -> Dict:
        """Resolve ${variable} placeholders in arguments"""
        def resolve(value):
            if isinstance(value, str):
                if value.startswith("${") and value.endswith("}"):
                    var_name = value[2:-1]

                    # Handle dot notation like ${bounds.width}
                    if '.' in var_name:
                        parts = var_name.split('.')
                        # First try direct lookup (for pre-flattened variables)
                        val = self.variables.get(var_name)
                        if val is not None:
                            print(f"   🔄 Resolved {value} -> {val}")
                            return val
                        # Then try nested lookup
                        val = self.variables.get(parts[0])
                        if isinstance(val, dict):
                            for part in parts[1:]:
                                val = val.get(part)
                                if val is None:
                                    break
                        if val is not None:
                            print(f"   🔄 Resolved {value} -> {val}")
                            return val
                    else:
                        val = self.variables.get(var_name)
                        if val is not None:
                            print(f"   🔄 Resolved {value} -> {val}")
                            return val
                    return value
                return value
            elif isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            elif isinstance(value, list):
                result = []
                for item in value:
                    resolved = resolve(item)
                    if isinstance(resolved, list):
                        result.extend(resolved)
                    else:
                        result.append(resolved)
                return result
            return value

        return {key: resolve(value) for key, value in args.items()}

    def _execute_tool_direct(self, tool_name: str, args: Dict) -> Any:
        """Execute a tool by calling the appropriate API endpoint"""
        
        # Store current step args for placement tracking
        self._current_step_args = args
        
        # --- VISION: Generate layout from image ---
        if tool_name == "generate_layout_from_image":
            if not self.vision:
                return {"status": "error", "message": "Vision Processor not loaded."}
            
            # Get image data from args or variables
            image_data = args.get("image_base64")
            if not image_data or image_data == "${uploaded_image}":
                image_data = self.variables.get("uploaded_image")
            
            if not image_data:
                return {"status": "error", "message": "No image provided"}
            
            # Default area if not provided
            area = float(args.get("target_area", 500))
            
            print(f"   🧠 Sending to VisionProcessor (target area: {area} sqft)...")
            vision_result = self.vision.process_layout(image_data, area)
            
            if not vision_result:
                return {"status": "error", "message": "Vision model returned no results."}
            
            # Extract components from vision result
            if isinstance(vision_result, dict):
                walls = vision_result.get("walls", [])
                boundary_points = vision_result.get("boundary_points", [])
                discovered_level_name = vision_result.get("level_name")
            else:
                # Handle legacy format (just walls list)
                walls = vision_result
                boundary_points = []
                discovered_level_name = None
            
            if not walls:
                return {"status": "error", "message": "Vision model returned 0 walls."}
            
            print(f"   🔍 Vision returned {len(walls)} walls, {len(boundary_points)} boundary points")
            if discovered_level_name:
                print(f"   🏗️ Vision discovered level: {discovered_level_name}")
            
            # === SCALE CORRECTION ===
            # Add 5% to compensate for typical undershoot
            scale_correction = 1.05  # 5% increase to get closer to target
            for wall in walls:
                sp = wall.get("start_point", [0,0,0])
                ep = wall.get("end_point", [0,0,0])
                wall["start_point"] = [sp[0] * scale_correction, sp[1] * scale_correction, sp[2]]
                wall["end_point"] = [ep[0] * scale_correction, ep[1] * scale_correction, ep[2]]
            
            # Scale boundary points too
            scaled_boundary_points = []
            for point in boundary_points:
                scaled_point = [point[0] * scale_correction, point[1] * scale_correction, point[2] if len(point) > 2 else 0.0]
                scaled_boundary_points.append(scaled_point)
            
            # Use discovered level name if available, otherwise fallback to discovery variables
            if discovered_level_name:
                level_name = discovered_level_name
                level_id = None  # Let Revit find the level ID by name
                # Store discovered level in variables for subsequent floor/roof creation
                self.variables["base_level_name"] = discovered_level_name
                self.variables["vision_level_name"] = discovered_level_name
            else:
                level_id = self.variables.get("level_0_id", "311")
                level_name = self.variables.get("base_level_name", "Level 0")
            
            wall_type = self.variables.get("default_wall_type", "Wall-Partn_12P-70MStd-12P")
            
            # Store boundary points for floor/roof creation
            if scaled_boundary_points:
                self.variables["boundary_points"] = scaled_boundary_points
                print(f"   📦 Stored {len(scaled_boundary_points)} boundary points for floor/roof creation")
            
            print(f"   📋 Using: level_name='{level_name}', wall_type='{wall_type}'")
            
            # Fix each wall - ensure all required fields
            for i, wall in enumerate(walls):
                # Ensure 3D points
                sp = wall.get("start_point", wall.get("start", [0,0,0]))
                ep = wall.get("end_point", wall.get("end", [0,0,0]))
                
                if len(sp) == 2:
                    sp = [float(sp[0]), float(sp[1]), 0.0]
                if len(ep) == 2:
                    ep = [float(ep[0]), float(ep[1]), 0.0]
                
                # Rebuild wall with correct keys
                wall.clear()
                wall["start_point"] = sp
                wall["end_point"] = ep
                wall["height"] = 10.0
                wall["level_name"] = level_name
                wall["wall_type"] = wall_type
                if level_id:
                    wall["level_id"] = level_id
                
                if i == 0:
                    print(f"   🔍 First wall after fix: {wall}")
            
            print(f"   🚀 Sending {len(walls)} walls to Revit...")
            
            # Execute wall creation
            result = self._execute_tool_direct("create_walls_batch", {"walls": walls})
            
            print(f"   📤 REVIT RESPONSE: {result}")
            
            # === AUTOMATIC FLOOR AND ROOF CREATION ===
            # After walls are successfully created, automatically create floor and roof
            if result and result.get("status") == "batch_complete":
                print(f"   🏠 Walls created successfully, now creating floor and roof...")
                
                # Create Floor
                if scaled_boundary_points:
                    floor_args = {
                        "points": scaled_boundary_points,
                        "level_name": level_name
                    }
                    print(f"   🚀 Creating Floor...")
                    floor_result = self._execute_tool_direct("create_floor", floor_args)
                    print(f"      📤 Floor Reply: {floor_result}")
                    
                    # Create Roof - First create a dedicated roof level, then place roof on it
                    wall_height = walls[0].get("height", 10.0) if walls else 10.0
                    
                    # Create roof level at wall height
                    roof_level_name = f"Roof Level"
                    roof_elevation = wall_height  # Place roof level at top of walls
                    
                    print(f"   🏗️ Creating roof level '{roof_level_name}' at {roof_elevation}ft...")
                    level_result = self._execute_tool_direct("create_level", {
                        "name": roof_level_name,
                        "elevation": roof_elevation
                    })
                    print(f"      📤 Level Reply: {level_result}")
                    
                    # Now create roof on the new level (using base points, not elevated)
                    roof_args = {
                        "points": scaled_boundary_points,  # Base points (Z=0 relative to roof level)
                        "level_name": roof_level_name,     # New dedicated roof level
                        "slope_degrees": 0.0
                    }
                    print(f"   🚀 Creating Roof on dedicated level: {roof_level_name}")
                    roof_result = self._execute_tool_direct("create_roof_footprint", roof_args)
                    print(f"      📤 Roof Reply: {roof_result}")
                else:
                    print(f"   ⚠️ No boundary points available for floor/roof creation")
            else:
                print(f"   ⚠️ Wall creation failed, skipping floor/roof creation")
            
            return result

        # --- PHOTO-TO-FAMILY: Create family from photo ---
        if tool_name in ["create_family_from_photo", "photo_to_family", "analyze_photo_for_family"]:
            if not PhotoToFamilyProcessor:
                return {"status": "error", "message": "PhotoToFamilyProcessor not loaded."}

            # Get image data
            image_data = args.get("image_base64") or args.get("image")
            if not image_data or image_data == "${uploaded_image}":
                image_data = self.variables.get("uploaded_image")

            if not image_data:
                return {"status": "error", "message": "No image provided for family creation"}

            family_name = args.get("family_name", "PhotoFamily")
            category = args.get("category", "Generic Models")
            object_hint = args.get("object_hint")
            dimensions = args.get("dimensions")  # Optional user-provided dimensions

            print(f"   📸 Processing photo for family: {family_name}")

            # Initialize processor
            processor = PhotoToFamilyProcessor()

            # Analyze the photo
            images = [{"data": image_data, "view": args.get("view", "front")}]
            analysis = processor.analyze_photos(images, object_hint)

            if not analysis:
                return {"status": "error", "message": "Failed to analyze photo"}

            # If just analyzing (not creating), return analysis
            if tool_name == "analyze_photo_for_family":
                return {
                    "status": "success",
                    "message": "Photo analyzed successfully",
                    "analysis": analysis,
                    "estimated_dimensions": processor.estimate_dimensions(analysis, dimensions)
                }

            # Get dimensions
            if dimensions:
                final_dimensions = dimensions
            else:
                final_dimensions = processor.estimate_dimensions(analysis, dimensions)

            # Generate geometry
            geometry = processor.generate_family_geometry(analysis, final_dimensions)
            geometry["category"] = category

            # Build the family
            if ParametricFamilyBuilder:
                builder = ParametricFamilyBuilder()

                # Store for async execution - return geometry and builder info
                # The actual async build will be handled by the orchestrator
                return {
                    "status": "pending_async",
                    "message": "Family geometry ready for creation",
                    "analysis": analysis,
                    "geometry": geometry,
                    "family_name": family_name,
                    "_builder": builder,
                    "_needs_async_build": True
                }
            else:
                return {
                    "status": "partial",
                    "message": "Photo analyzed but ParametricFamilyBuilder not available",
                    "analysis": analysis,
                    "geometry": geometry
                }

        # --- GEOMETRY ANALYSIS: Analyze bounding box from walls ---
        if tool_name == "analyze_geometry_bounds":
            walls = args.get("walls", [])
            if not walls:
                return {"status": "error", "message": "No wall data provided"}

            print(f"   📐 Analyzing geometry bounds from {len(walls)} walls...")

            # Parse wall coordinates and find bounding box
            all_x = []
            all_y = []

            for wall in walls:
                # Handle different data formats from list_walls
                start = wall.get('start') or wall.get('start_point')
                end = wall.get('end') or wall.get('end_point')

                if isinstance(start, str):
                    # Parse format like "{0.0, 0.0, 0.0}"
                    coords = start.strip('{}').split(',')
                    start_x, start_y = float(coords[0]), float(coords[1])
                elif isinstance(start, dict):
                    start_x, start_y = float(start.get('x', 0)), float(start.get('y', 0))
                elif isinstance(start, list):
                    start_x, start_y = float(start[0]), float(start[1])
                else:
                    continue

                if isinstance(end, str):
                    coords = end.strip('{}').split(',')
                    end_x, end_y = float(coords[0]), float(coords[1])
                elif isinstance(end, dict):
                    end_x, end_y = float(end.get('x', 0)), float(end.get('y', 0))
                elif isinstance(end, list):
                    end_x, end_y = float(end[0]), float(end[1])
                else:
                    continue

                all_x.extend([start_x, end_x])
                all_y.extend([start_y, end_y])

            if not all_x or not all_y:
                return {"status": "error", "message": "Could not parse wall coordinates"}

            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            width = max_x - min_x
            depth = max_y - min_y

            bounds = {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
                "width": width,
                "depth": depth,
                "center_x": (min_x + max_x) / 2,
                "center_y": (min_y + max_y) / 2,
                "area": width * depth
            }

            print(f"   📐 Bounds: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})")
            print(f"   📐 Size: {width:.1f}' x {depth:.1f}' = {width * depth:.0f} sqft")

            # Store bounds in variables for template use
            self.variables["bounds"] = bounds
            self.variables["bounds.min_x"] = min_x
            self.variables["bounds.min_y"] = min_y
            self.variables["bounds.max_x"] = max_x
            self.variables["bounds.max_y"] = max_y
            self.variables["bounds.width"] = width
            self.variables["bounds.depth"] = depth

            return {"status": "success", "bounds": bounds}

        # --- TOOL DISCOVERY: List available tools ---
        if tool_name == "list_available_tools":
            print(f"   📋 Listing available tools...")
            # Dynamically categorize tools from endpoint_map
            all_tools = list(self._get_endpoint_map().keys())

            # Auto-categorize based on tool name prefixes
            categories = {
                "creation": [],
                "placement": [],
                "listing": [],
                "schedules": [],
                "assemblies": [],
                "deletion": [],
                "discovery": [],
                "generation": [],
                "configuration": [],
                "other": []
            }

            for tool in sorted(all_tools):
                if tool.startswith("create_"):
                    if "schedule" in tool:
                        categories["schedules"].append(tool)
                    elif "assembly" in tool or "wall_type" in tool:
                        categories["assemblies"].append(tool)
                    else:
                        categories["creation"].append(tool)
                elif tool.startswith("place_"):
                    categories["placement"].append(tool)
                elif tool.startswith("list_"):
                    if "schedule" in tool:
                        categories["schedules"].append(tool)
                    elif "wall_type" in tool:
                        categories["assemblies"].append(tool)
                    else:
                        categories["listing"].append(tool)
                elif tool.startswith("delete_"):
                    categories["deletion"].append(tool)
                elif tool.startswith("get_") or tool.startswith("analyze_"):
                    if "schedule" in tool:
                        categories["schedules"].append(tool)
                    elif "wall_type" in tool or "assembly" in tool:
                        categories["assemblies"].append(tool)
                    else:
                        categories["discovery"].append(tool)
                elif tool.startswith("set_") or tool.startswith("add_") or tool.startswith("remove_"):
                    if "schedule" in tool:
                        categories["schedules"].append(tool)
                    else:
                        categories["configuration"].append(tool)
                elif tool.startswith("generate_"):
                    categories["generation"].append(tool)
                elif tool.startswith("duplicate_"):
                    categories["assemblies"].append(tool)
                elif tool.startswith("load_"):
                    categories["placement"].append(tool)
                elif tool.startswith("configure_") or tool.startswith("test_"):
                    categories["configuration"].append(tool)
                else:
                    categories["other"].append(tool)

            # Remove empty categories
            categories = {k: v for k, v in categories.items() if v}

            return {
                "status": "success",
                "categories": categories,
                "total_tools": len(all_tools)
            }

        # --- TOOL MODE MANAGEMENT ---
        if tool_name == "set_mode":
            if not TOOL_MODES_AVAILABLE:
                return {"status": "error", "message": "Tool modes not available"}
            mode_name = args.get("mode", "all")
            mode_manager = get_mode_manager()
            result = mode_manager.set_mode(mode_name)
            if result.get("status") == "success":
                print(f"   🔧 Switched to {result.get('name', mode_name)} mode ({result.get('tool_count', 0)} tools)")
            return result

        if tool_name == "list_modes":
            if not TOOL_MODES_AVAILABLE:
                return {"status": "error", "message": "Tool modes not available"}
            mode_manager = get_mode_manager()
            return mode_manager.get_modes()

        if tool_name == "get_current_mode":
            if not TOOL_MODES_AVAILABLE:
                return {"status": "error", "message": "Tool modes not available"}
            mode_manager = get_mode_manager()
            modes_info = mode_manager.get_modes()
            return {
                "status": "success",
                "current_mode": modes_info["current_mode"],
                "active_tool_count": modes_info["active_tool_count"]
            }

        if tool_name == "auto_detect_mode":
            if not TOOL_MODES_AVAILABLE:
                return {"status": "error", "message": "Tool modes not available"}
            mode_manager = get_mode_manager()
            user_message = args.get("message", "")
            return mode_manager.auto_set_mode(user_message)

        # --- MODEL CONFIGURATION ---
        if tool_name == "configure_models":
            print(f"   ⚙️ Model configuration: {args.get('mode', 'show')}")
            try:
                from model_config_tool import configure_models_tool
                return configure_models_tool(**args)
            except ImportError:
                return {"status": "error", "message": "Model config tool not available"}

        # --- AUTO-DIMENSION TOOLS (Python-side orchestration) ---
        if tool_name in ["auto_dimension_walls", "auto_dimension_rooms", "auto_dimension_openings", "auto_dimension_all"]:
            try:
                from tools.auto_dimensions import (
                    auto_dimension_walls, auto_dimension_rooms,
                    auto_dimension_openings, auto_dimension_all
                )
                import asyncio

                def run_async_tool(coro):
                    """Run async coroutine from sync code safely."""
                    try:
                        # Try to get existing loop (will fail if none running)
                        loop = asyncio.get_running_loop()
                        # If we're here, there's a running loop - use thread
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, coro)
                            return future.result(timeout=120)
                    except RuntimeError:
                        # No running loop - safe to use asyncio.run()
                        return asyncio.run(coro)

                level_name = args.get("level_name")
                print(f"   📐 Running {tool_name} on {level_name or 'default level'}...")

                if tool_name == "auto_dimension_walls":
                    result = run_async_tool(
                        auto_dimension_walls(
                            level_name=level_name,
                            include_interior=args.get("include_interior", True),
                            tier_1_offset=args.get("tier_1_offset", 3.0),
                            tier_2_offset=args.get("tier_2_offset", 6.0),
                            tier_3_offset=args.get("tier_3_offset", 9.0)
                        )
                    )
                elif tool_name == "auto_dimension_rooms":
                    result = run_async_tool(
                        auto_dimension_rooms(
                            level_name=level_name,
                            room_ids=args.get("room_ids"),
                            offset=args.get("offset", 1.0)
                        )
                    )
                elif tool_name == "auto_dimension_openings":
                    result = run_async_tool(
                        auto_dimension_openings(
                            level_name=level_name,
                            wall_ids=args.get("wall_ids"),
                            include_doors=args.get("include_doors", True),
                            include_windows=args.get("include_windows", True),
                            offset=args.get("offset", 2.0)
                        )
                    )
                else:  # auto_dimension_all
                    result = run_async_tool(
                        auto_dimension_all(level_name=level_name)
                    )

                # Parse result if it's a JSON string
                if isinstance(result, str):
                    import json
                    try:
                        result = json.loads(result)
                    except:
                        pass

                return result

            except ImportError as e:
                return {"status": "error", "message": f"Auto-dimension tools not available: {e}"}
            except Exception as e:
                return {"status": "error", "message": f"Auto-dimension failed: {e}"}

        # --- CONSTRUCTION DETAIL TOOLS ---
        if tool_name == "list_construction_assemblies":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            return get_available_assemblies()

        if tool_name == "get_assembly_info":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            assembly_key = args.get("assembly_key", args.get("assembly", ""))
            return get_assembly_info(assembly_key)

        if tool_name == "create_assembly_wall":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            return create_assembly_wall(
                assembly_key=args.get("assembly_key", "ext_wall_2x6"),
                start_point=args.get("start_point", [0, 0, 0]),
                end_point=args.get("end_point", [20, 0, 0]),
                height=args.get("height", 10.0),
                level_name=args.get("level_name", "${base_level_name}"),
                core_location=args.get("core_location", "center")
            )

        if tool_name == "create_assembly_wall_batch":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            return create_assembly_wall_batch(
                assembly_key=args.get("assembly_key", "ext_wall_2x6"),
                wall_segments=args.get("walls", args.get("segments", [])),
                height=args.get("height", 10.0),
                level_name=args.get("level_name", "${base_level_name}")
            )

        if tool_name == "create_explosion_view":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            return create_explosion_view(
                assembly_key=args.get("assembly_key", "ext_wall_2x6"),
                start_point=args.get("start_point", [0, 0, 0]),
                end_point=args.get("end_point", [10, 0, 0]),
                height=args.get("height", 10.0),
                level_name=args.get("level_name", "${base_level_name}"),
                separation=args.get("separation", 0.5)
            )

        if tool_name == "generate_section_detail":
            if not DETAIL_TOOLS_AVAILABLE:
                return {"status": "error", "message": "Detail tools not available"}
            return generate_section_detail(
                assembly_key=args.get("assembly_key", "ext_wall_2x6"),
                height=args.get("height", 10.0),
                detail_width=args.get("detail_width", 2.0),
                include_dimensions=args.get("include_dimensions", True),
                include_labels=args.get("include_labels", True)
            )

        # --- SEARCH: Family library search ---
        if tool_name in ["search_family_library", "search_families", "search_library", "find_family"]:
            if not self.kb:
                return {"status": "error", "message": "Knowledge Base not loaded."}
            try:
                results = self.kb.search(args.get("query", ""), limit=5)
                formatted = []
                for r in results:
                    formatted.append(f"- Name: {r['name']} (Path: {r.get('path', '?')})")
                    if not self.variables.get("found_family_name"):
                        self.variables["found_family_name"] = r['name']
                        self.variables["found_family_path"] = r.get('path', '')
                return "\n".join(formatted) if formatted else "No families found."
            except Exception as e:
                return {"status": "error", "message": f"Search failed: {e}"}

        # --- ENDPOINT MAP ---
        endpoint_map = self._get_endpoint_map()

        # Fuzzy match tool name if not found (autocorrect for typos)
        if tool_name not in endpoint_map:
            # More lenient matching: n=3 suggestions, cutoff=0.5
            matches = difflib.get_close_matches(tool_name, endpoint_map.keys(), n=3, cutoff=0.5)
            if matches:
                # Calculate similarity scores for display
                best_match = matches[0]
                similarity = difflib.SequenceMatcher(None, tool_name, best_match).ratio()

                if similarity >= 0.8:
                    # High confidence - auto-correct
                    print(f"   🔄 Auto-corrected '{tool_name}' -> '{best_match}' ({similarity:.0%} match)")
                    tool_name = best_match
                else:
                    # Lower confidence - show suggestions but still use best match
                    suggestions = [f"'{m}'" for m in matches]
                    print(f"   🔄 Fuzzy matched '{tool_name}' -> '{best_match}'")
                    print(f"      Other suggestions: {', '.join(suggestions[1:]) if len(suggestions) > 1 else 'none'}")
                    tool_name = best_match
            else:
                # No matches found - provide helpful error with common tool categories
                common_tools = ["create_wall", "create_walls_batch", "list_walls", "list_levels",
                               "create_floor", "place_family", "get_revit_status"]
                return {
                    "status": "error",
                    "message": f"Unknown tool '{tool_name}'. No similar tools found.\n"
                              f"Common tools: {', '.join(common_tools)}\n"
                              f"Use 'get_server_manifest' to see all available tools."
                }

        endpoint = endpoint_map[tool_name]
        payload = args.copy()

        # --- PAYLOAD FORMATTING ---
        
        # Batch endpoints - C# expects arrays directly
        if tool_name == "create_levels_batch":
            levels = args.get("levels", [])
            payload = []
            for lvl in levels:
                payload.append({
                    "name": lvl.get("name", "Level"),
                    "elevation": lvl.get("elevation", 0.0)
                })
        # --- FLOOR PLAN GENERATION ---
        elif tool_name == "generate_floor_plan_walls":
            if not generate_floor_plan_walls:
                return {"status": "error", "message": "Floor plan tool not loaded."}

            try:
                width = float(args.get("width", 40))
                depth = float(args.get("depth", 30))
                rooms = args.get("rooms", [])
                level_name = args.get("level_name", "Level 1")
                wall_height = float(args.get("wall_height", 10.0))
                exterior_wall_type = args.get("exterior_wall_type")
                interior_wall_type = args.get("interior_wall_type")
                wet_wall_type = args.get("wet_wall_type")
                interior_only = args.get("interior_only", False)
                origin_x = float(args.get("origin_x", 0.0))
                origin_y = float(args.get("origin_y", 0.0))

                mode = "INTERIOR PARTITIONS ONLY" if interior_only else "Full Layout"
                print(f"   🏠 Generating floor plan: {width}' x {depth}' [{mode}]")
                print(f"   📋 Rooms: {len(rooms)}")
                if origin_x != 0 or origin_y != 0:
                    print(f"   📍 Origin offset: ({origin_x}, {origin_y})")

                result = generate_floor_plan_walls(
                    width=width, depth=depth, rooms=rooms,
                    level_name=level_name, wall_height=wall_height,
                    exterior_wall_type=exterior_wall_type,
                    interior_wall_type=interior_wall_type,
                    wet_wall_type=wet_wall_type,
                    interior_only=interior_only,
                    origin_x=origin_x,
                    origin_y=origin_y
                )
                
                if not result.get("success"):
                    return {"status": "error", "message": result.get("error", "Layout generation failed")}
                
                print(f"   ✅ Layout generated: {result['summary']['total_walls']} walls")
                
                # Store room data for follow-up
                self.variables["floor_plan_rooms"] = result.get("rooms", {})
                self.variables["floor_plan_doors"] = result.get("doors", [])
                
                # Create walls in Revit
                walls_batch = result.get("walls_batch", [])
                if walls_batch:
                    print(f"   🚀 Creating {len(walls_batch)} walls in Revit...")
                    wall_creation_result = self._execute_tool_direct("create_walls_batch", {"walls": walls_batch})
                    return {
                        "status": "success",
                        "layout": result["summary"],
                        "rooms": result.get("rooms"),
                        "wall_creation": wall_creation_result
                    }
                return result
            except Exception as e:
                return {"status": "error", "message": f"Floor plan generation failed: {e}"}
        elif tool_name == "create_walls_batch":
            walls = args.get("walls", [])
            payload = []
            print(f"   🧱 Processing {len(walls)} walls for batch creation")
            for i, w in enumerate(walls):
                wall_dict = {
                    "start_point": w.get("start_point") or w.get("start"),
                    "end_point": w.get("end_point") or w.get("end"),
                    "level_name": w.get("level_name") or w.get("level"),
                    "level_id": w.get("level_id"),
                    "height": w.get("height", 10.0),
                    "wall_type": w.get("wall_type") or w.get("type"),
                    "flipped": w.get("flipped", False)
                }

                # Ensure coordinates are floats (they might be strings from variable resolution)
                start = wall_dict["start_point"]
                end = wall_dict["end_point"]
                if start and end:
                    # Convert to float in case they're strings
                    start = [float(x) if isinstance(x, (int, float, str)) else 0.0 for x in start]
                    end = [float(x) if isinstance(x, (int, float, str)) else 0.0 for x in end]
                    wall_dict["start_point"] = start
                    wall_dict["end_point"] = end
                    length = ((end[0]-start[0])**2 + (end[1]-start[1])**2)**0.5
                    print(f"   📏 Wall {i+1}: ({start[0]:.1f},{start[1]:.1f}) → ({end[0]:.1f},{end[1]:.1f}) len={length:.1f}ft level={wall_dict['level_name']}")

                # Auto-flip exterior walls for proper orientation (inside face toward building)
                wall_type = wall_dict.get("wall_type", "")
                if wall_type.startswith("Wall-Ext") and not w.get("flipped_set_manually", False):
                    wall_dict["flipped"] = True
                    print(f"   🔄 Auto-flipping exterior wall for proper orientation")

                payload.append(wall_dict)
        
        elif tool_name == "place_hosted_batch":
            elements = args.get("placements", args.get("elements", []))
            payload = []
            for e in elements:
                payload.append({
                    "host_id": e.get("host_id"),
                    "point": e.get("point", [0, 0, 0]),
                    "family_name": e.get("family_name"),
                    "type_name": e.get("type_name")
                })
            print(f"   🔍 Sending {len(payload)} hosted elements to Revit")
            if payload:
                print(f"   🔍 First element: {payload[0]}")
        
        elif tool_name == "create_sheets_batch":
            payload = args.get("sheets", [])
        
        elif tool_name == "create_grids_batch":
            payload = args.get("grids", [])
        
        elif tool_name == "place_views_batch":
            payload = args.get("placements", [])
        
        elif tool_name == "create_tags_batch":
            payload = args.copy()
            print(f"   🔍 Tagging payload: {payload}")
            element_ids = payload.get("element_ids", [])
            view_id = payload.get("view_id")
            skip_existing = payload.pop("skip_existing", False)
            existing_tags = payload.pop("existing_tags", [])

            # Filter out already-tagged elements if skip_existing is True
            if skip_existing and existing_tags:
                # Extract host element IDs from existing tags
                tagged_element_ids = set()
                for tag in existing_tags:
                    if isinstance(tag, dict):
                        # Tags usually have a host_id or element_id field
                        host_id = tag.get("host_id") or tag.get("element_id") or tag.get("tagged_element_id")
                        if host_id:
                            tagged_element_ids.add(str(host_id))

                # Filter element_ids to exclude already-tagged elements
                original_count = len(element_ids)
                element_ids = [eid for eid in element_ids if str(eid) not in tagged_element_ids]
                filtered_count = original_count - len(element_ids)

                if filtered_count > 0:
                    print(f"   🔍 Skipped {filtered_count} already-tagged elements")

                # Update payload with filtered element_ids
                payload["element_ids"] = element_ids

                # If no elements left to tag, return early
                if not element_ids:
                    print(f"   ✅ All elements already tagged - skipping")
                    return {"status": "success", "message": "All elements already tagged", "skipped": original_count}

            print(f"   🏷️ Tagging {len(element_ids)} elements in view {view_id}")
        
        
        elif tool_name == "create_text_note":
            payload = [args]
        
        elif tool_name == "list_wall_ids":
            payload = {"category_name": "Walls", "level_name": args.get("level_name")}
        
        elif tool_name == "list_door_ids":
            payload = {"category_name": "Doors", "level_name": args.get("level_name")}
        
        elif tool_name == "list_window_ids":
            payload = {"category_name": "Windows", "level_name": args.get("level_name")}
        
        elif tool_name == "list_dimensions":
            payload = {"category_name": "Dimensions"}
        
        elif tool_name in ["create_floor", "create_roof_footprint"]:
            raw_points = payload.get("points", [])
            if raw_points and isinstance(raw_points[0], (int, float)):
                payload["points"] = [raw_points[i:i+3] for i in range(0, len(raw_points), 3)]
        
        elif tool_name in ["delete_element", "delete_elements", "delete_dimensions"]:
            ids = args.get("element_ids") or args.get("dimension_ids") or [args.get("element_id")]
            payload = {"element_ids": ids, "force": args.get("force", False)}

        # --- EXECUTE REQUEST ---
        try:
            url = f"{self.api_url}{endpoint}"
            
            # Debug output for dimension creation
            if tool_name == "create_dimension":
                element_ids = payload.get("element_ids", [])
                print(f"   📏 Creating dimension with {len(element_ids)} elements: {element_ids}")
                if len(element_ids) < 2:
                    print(f"   ⚠️ Warning: Dimensions need at least 2 elements")
            
            # GET for list_ commands (except list_elements which needs POST)
            if tool_name.startswith("list_") and "list_elements" not in endpoint:
                response = requests.get(url, timeout=60)
            else:
                # Longer timeout for create/modify operations
                response = requests.post(url, json=payload, timeout=120)
            
            try:
                result = response.json()
                
                # Log results for debugging
                if tool_name == "place_hosted_batch":
                    print(f"   📤 Revit response: {result}")
                    if isinstance(result, dict) and "status" in result:
                        if result["status"] == "batch_complete":
                            success_count = sum(1 for r in result.get("results", []) 
                                              if r.get("result", {}).get("status") == "success")
                            total_count = len(result.get("results", []))
                            print(f"   📊 Placed {success_count}/{total_count} hosted elements")
                        else:
                            print(f"   ⚠️ Batch status: {result['status']}")
                
                return result
            except:
                return response.text
        except requests.exceptions.Timeout:
            return {"status": "timeout", "message": f"Revit is processing - check Revit window. Tool: {tool_name}"}
        except Exception as e:
            return {"status": "error", "message": f"Connection failed: {e}"}

    def _extract_variables(self, tool_name: str, result: Any):
        """Extract variables from tool results for use in subsequent steps"""
        
        # Handle batch wall creation specifically
        if tool_name == "create_walls_batch" and isinstance(result, dict):
            if result.get("status") == "batch_complete" and "results" in result:
                batch_index = len([k for k in self.variables.keys() if k.startswith("wall_batch_")])
                wall_ids = []
                
                for i, item in enumerate(result["results"]):
                    if isinstance(item, dict) and "result" in item:
                        wall_result = item["result"]
                        if wall_result.get("status") == "success" and "id" in wall_result:
                            wall_id = str(wall_result["id"])
                            wall_ids.append(wall_id)
                            # Create template-style variables: ${wall_batch_0_wall_0}, ${wall_batch_0_wall_1}, etc.
                            self.variables[f"wall_batch_{batch_index}_wall_{i}"] = wall_id
                
                # Also store as a list for other uses
                if wall_ids:
                    self.variables["created_wall_ids"] = wall_ids
                    print(f"   📝 Extracted {len(wall_ids)} wall IDs: {', '.join(wall_ids)}")
                    print(f"   🎯 Template variables: wall_batch_{batch_index}_wall_0 through wall_batch_{batch_index}_wall_{len(wall_ids)-1}")

        # Track door/window placements for dimension calculations
        elif tool_name == "place_hosted_batch" and isinstance(result, dict):
            if result.get("status") == "batch_complete" and "results" in result:
                # Get placements from the original step arguments
                step_args = getattr(self, '_current_step_args', {})
                placements = step_args.get("placements", step_args.get("elements", []))
                placement_data = []
                
                for i, (placement, res) in enumerate(zip(placements, result.get("results", []))):
                    if isinstance(res, dict):
                        # Handle both nested result format and direct format
                        element_result = res.get("result", res)
                        if element_result.get("status") == "success" and "id" in element_result:
                            element_id = str(element_result["id"])
                            placement_info = {
                                "id": element_id,
                                "host_id": str(placement.get("host_id", "")),
                                "point": placement.get("point", [0, 0, 0]),
                                "family_name": placement.get("family_name", ""),
                                "type_name": placement.get("type_name", "")
                            }
                            placement_data.append(placement_info)
                
                if placement_data:
                    # Store placement data for dimension calculations
                    self.variables.setdefault("placement_data", []).extend(placement_data)
                    print(f"   📍 Tracked {len(placement_data)} door/window placements for dimensioning")
        
        # Extract wall IDs for dimension/tagging operations  
        if tool_name in ["list_wall_ids", "list_walls"]:
            if isinstance(result, list):
                wall_ids = []
                for item in result:
                    if isinstance(item, dict) and 'id' in item:
                        wall_ids.append(str(item['id']))
                if wall_ids:
                    self.variables["wall_ids"] = wall_ids
                    self.variables["all_wall_ids"] = wall_ids  # Template expects this name
                    print(f"   📝 Found {len(wall_ids)} walls for tagging")
                    
                    # For dimension templates, calculate proper architectural dimension groups
                    try:
                        # Get the actual wall data with geometry for analysis
                        wall_data_result = self._execute_tool_direct("list_walls", {})
                        
                        if isinstance(wall_data_result, list) and wall_data_result:
                            # Get door and window data from variables (may be empty)
                            door_ids = self.variables.get("door_ids", [])
                            window_ids = self.variables.get("window_ids", [])
                            door_data = self.variables.get("door_data", [])
                            window_data = self.variables.get("window_data", [])

                            # Analyze wall geometry to create proper dimension groups
                            dimension_groups = self._calculate_dimension_groups(
                                wall_data_result, door_ids, window_ids, door_data, window_data
                            )
                            
                            # Set all the dimension variables the template expects
                            for key, value in dimension_groups.items():
                                self.variables[key] = value
                                
                            print(f"   📐 Generated architectural dimension groups with wall geometry analysis")
                        else:
                            # Fallback to basic dimension groups if wall data unavailable
                            self._create_basic_dimension_groups(wall_ids)
                            print(f"   📐 Using basic dimension groups (no wall geometry data)")
                            
                    except Exception as e:
                        print(f"   ⚠️ Dimension calculation failed: {e}")
                        self._create_basic_dimension_groups(wall_ids)
        
        
        elif tool_name == "list_door_ids":
            if isinstance(result, list):
                door_ids = []
                for item in result:
                    if isinstance(item, dict) and 'id' in item:
                        door_ids.append(str(item['id']))
                if door_ids:
                    self.variables["door_ids"] = door_ids
                    self.variables["all_door_ids"] = door_ids  # Template expects this name
                    self.variables["door_data"] = result  # Store full data for dimension calculation
                    print(f"   📝 Found {len(door_ids)} doors for tagging")
        
        elif tool_name == "list_window_ids":
            window_ids = []
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and 'id' in item:
                        window_ids.append(str(item['id']))

            # Always store window data (even if empty)
            self.variables["window_ids"] = window_ids
            self.variables["all_window_ids"] = window_ids
            self.variables["window_data"] = result if isinstance(result, list) else []
            if window_ids:
                print(f"   📝 Found {len(window_ids)} windows for tagging")
            else:
                print(f"   📝 No windows found")

            # CRITICAL: Recalculate dimension groups now that we have doors AND windows
            # This is needed because list_wall_ids runs before list_door_ids/list_window_ids
            # Always recalculate if we have wall data (even if no doors/windows)
            if self.variables.get("wall_ids") or self.variables.get("all_wall_ids"):
                try:
                    wall_data_result = self._execute_tool_direct("list_walls", {})
                    if isinstance(wall_data_result, list) and wall_data_result:
                        door_ids = self.variables.get("door_ids", [])
                        door_data = self.variables.get("door_data", [])
                        window_data = self.variables.get("window_data", [])

                        dimension_groups = self._calculate_dimension_groups(
                            wall_data_result, door_ids, window_ids, door_data, window_data
                        )

                        for key, value in dimension_groups.items():
                            self.variables[key] = value

                        # Count openings included
                        total_openings = len(door_ids) + len(window_ids)
                        print(f"   📐 Recalculated dimension groups with {total_openings} openings (doors: {len(door_ids)}, windows: {len(window_ids)})")
                except Exception as e:
                    print(f"   ⚠️ Dimension recalculation failed: {e}")
        
        elif tool_name == "list_dimensions":
            if isinstance(result, list):
                dimension_ids = []
                for item in result:
                    if isinstance(item, dict) and 'id' in item:
                        dimension_ids.append(str(item['id']))
                if dimension_ids:
                    self.variables["existing_dimension_ids"] = dimension_ids
                    print(f"   📝 Found {len(dimension_ids)} existing dimensions")
                else:
                    self.variables["existing_dimension_ids"] = []
        
        # Generic ID extraction for other tools
        elif "create" in tool_name or "place" in tool_name:
            result_str = str(result)
            id_match = re.search(r"['\"]id['\"]:\s*['\"]?(\d+)['\"]?", result_str)
            if id_match:
                self.variables[f"last_{tool_name}_id"] = id_match.group(1)

    def _populate_variables_from_discovery(self, discovery_data: Dict):
        """Populate variables from discovery phase results"""
        # Default wall types for floor plan generation
        if "default_exterior_wall_type" not in self.variables:
            wall_types = discovery_data.get("list_wall_types", [])
            for wt in wall_types:
                name = wt.get("name", "")
                if "curtain" in name.lower():
                    continue
                if "exterior" in name.lower() or "-ext" in name.lower() or "ext_" in name.lower():
                    self.variables["default_exterior_wall_type"] = name
                    break
        if "default_interior_wall_type" not in self.variables:
            wall_types = discovery_data.get("list_wall_types", [])
            for wt in wall_types:
                name = wt.get("name", "")
                if "interior" in name.lower() or "partition" in name.lower() or "partn" in name.lower():
                    self.variables["default_interior_wall_type"] = name
                    break
            if "default_interior_wall_type" not in self.variables:
                self.variables["default_interior_wall_type"] = self.variables.get("default_wall_type", "")
        
        if "default_wet_wall_type" not in self.variables:
            # Wet walls need thicker partition - try to find 6" or similar
            self.variables["default_wet_wall_type"] = self.variables.get("default_interior_wall_type", "")
        # Levels
        if "list_levels" in discovery_data:
            levels = discovery_data["list_levels"]
            if levels:
                self.variables["base_level_name"] = levels[0].get('name', 'Level 1')
                self.variables["level_0_id"] = str(levels[0].get('id'))
                for i, level in enumerate(levels):
                    self.variables[f"level_{i}_name"] = level.get('name')
                    self.variables[f"level_{i}_id"] = str(level.get('id'))
        
        # Wall types - pick a good default (avoid curtain walls)
        if "list_wall_types" in discovery_data:
            types = discovery_data["list_wall_types"]
            if types:
                # Prefer exterior walls, then interior partition walls, avoid curtain walls
                preferred_order = ["Ext_", "Wall-Ext", "Int_", "Partn", "Wall-"]
                selected = None
                
                for prefix in preferred_order:
                    for t in types:
                        name = t.get('name', '')
                        # Skip curtain walls
                        if 'curtain' in name.lower():
                            continue
                        if prefix.lower() in name.lower():
                            selected = name
                            break
                    if selected:
                        break
                
                # If no preferred match, pick first non-curtain wall
                if not selected:
                    for t in types:
                        name = t.get('name', '')
                        if 'curtain' not in name.lower():
                            selected = name
                            break
                
                if selected:
                    self.variables["default_wall_type"] = selected
                    print(f"    📋 Selected wall type: {selected}")
                else:
                    # Last resort - just use first one
                    self.variables["default_wall_type"] = types[0].get('name')
        
        # Door types
        if "list_door_types" in discovery_data:
            types = discovery_data["list_door_types"]
            if types:
                first_type = types[0]
                self.variables["default_door_type"] = first_type.get('name')
                # Extract family name from the type name (e.g., "Doors_ExtDbl_Flush : 1510x2110mm" -> "Doors_ExtDbl_Flush")
                type_name = first_type.get('name', '')
                if ':' in type_name:
                    family_name = type_name.split(':')[0].strip()
                else:
                    family_name = first_type.get('family_name', 'Single-Flush')
                self.variables["default_door_family"] = family_name
                print(f"    📋 Selected door: family='{family_name}', type='{type_name}'")
        
        # Window types
        if "list_window_types" in discovery_data:
            types = discovery_data["list_window_types"]
            if types:
                first_type = types[0]
                self.variables["default_window_type"] = first_type.get('name')
                # Extract family name from the type name (e.g., "Windows_Sgl_Plain : 1360x1210mm" -> "Windows_Sgl_Plain")
                type_name = first_type.get('name', '')
                if ':' in type_name:
                    family_name = type_name.split(':')[0].strip()
                else:
                    family_name = first_type.get('family_name', 'Fixed')
                self.variables["default_window_family"] = family_name
                print(f"    📋 Selected window: family='{family_name}', type='{type_name}'")
        
        # Views - prioritize floor plan views for dimensions/tagging
        if "list_views" in discovery_data:
            views = discovery_data["list_views"]
            floor_plan_view_found = False
            
            for i, view in enumerate(views):
                self.variables[f"view_{i}_id"] = str(view.get('id'))
                self.variables[f"view_{i}_name"] = view.get('name')
                
                # Prioritize floor plan views for dimensions/tagging
                view_type = view.get('type', '').lower()
                if 'floorplan' in view_type or 'floor' in view_type:
                    if not floor_plan_view_found:
                        # Make the first floor plan view the primary view (view_0)
                        self.variables["view_0_id"] = str(view.get('id'))
                        self.variables["view_0_name"] = view.get('name')
                        self.variables["floor_plan_view_id"] = str(view.get('id'))
                        floor_plan_view_found = True
                        print(f"    📋 Selected floor plan view: {view.get('name')} (ID: {view.get('id')})")
            
            # If no floor plan view found, use the first view but warn
            if not floor_plan_view_found and views:
                print(f"    ⚠️ No floor plan view found, using: {views[0].get('name')} (may not be suitable for dimensions)")
        
        # === FALLBACK DEFAULTS ===
        # If discovery failed, use reasonable defaults so vision can still work
        if not self.variables.get("base_level_name"):
            self.variables["base_level_name"] = "Level 0"
            self.variables["level_0_id"] = "311"
            print("    ⚠️ Using fallback: base_level_name = 'Level 0', level_0_id = '311'")
        if not self.variables.get("default_wall_type"):
            # Use a common interior partition wall type
            self.variables["default_wall_type"] = "Wall-Partn_12P-70MStd-12P"
            print("    ⚠️ Using fallback: default_wall_type = 'Wall-Partn_12P-70MStd-12P'")
        
        # Add fallback dimension variables if discovery failed completely
        if not any(key.startswith(('wall_ids', 'door_ids', 'window_ids')) for key in self.variables.keys()):
            print("    ⚠️ Discovery failed - creating empty dimension variables")
            # Create empty dimension groups so templates don't break
            dimension_vars = [
                "wall_ids", "all_wall_ids", "door_ids", "all_door_ids", "window_ids", "all_window_ids",
                "horiz_west_detail", "horiz_east_detail", "horiz_dim_walls", "horiz_dim_overall",
                "vert_south_detail", "vert_north_detail", "vert_dim_walls", "vert_dim_overall",
                "existing_dimension_ids"
            ]
            for var in dimension_vars:
                self.variables[var] = []

    def _calculate_dimension_groups(self, walls_data, door_ids=None, window_ids=None, door_data=None, window_data=None):
        """Calculate proper architectural dimension groups including doors and windows.

        Groups doors/windows by their host wall orientation for proper architectural dimensioning.
        """
        door_ids = door_ids or []
        window_ids = window_ids or []
        door_data = door_data or []
        window_data = window_data or []

        # Helper to safely parse coordinates
        def parse_coords(coord):
            try:
                if isinstance(coord, str):
                    parts = coord.strip('{}[]').split(',')
                    return float(parts[0].strip()), float(parts[1].strip()) if len(parts) > 1 else 0.0
                elif isinstance(coord, dict):
                    return float(coord.get('x', 0)), float(coord.get('y', 0))
                elif isinstance(coord, (list, tuple)) and len(coord) >= 2:
                    return float(coord[0]), float(coord[1])
            except (ValueError, IndexError, TypeError):
                pass
            return 0.0, 0.0

        # Categorize walls by orientation
        horizontal_walls = []  # Walls that run east-west (for vertical dimensions)
        vertical_walls = []    # Walls that run north-south (for horizontal dimensions)

        # Calculate bounds for dynamic positioning
        all_x = []
        all_y = []

        for wall in walls_data:
            start = wall.get('start', {})
            end = wall.get('end', {})

            start_x, start_y = parse_coords(start)
            end_x, end_y = parse_coords(end)

            all_x.extend([start_x, end_x])
            all_y.extend([start_y, end_y])

            # Determine orientation based on which coordinate changes more
            dx = abs(end_x - start_x)
            dy = abs(end_y - start_y)

            if dx > dy:  # Horizontal wall (runs east-west)
                horizontal_walls.append({
                    'id': str(wall.get('id')),
                    'start_x': start_x, 'start_y': start_y,
                    'end_x': end_x, 'end_y': end_y,
                    'y_pos': start_y,
                })
            else:  # Vertical wall (runs north-south)
                vertical_walls.append({
                    'id': str(wall.get('id')),
                    'start_x': start_x, 'start_y': start_y,
                    'end_x': end_x, 'end_y': end_y,
                    'x_pos': start_x,
                })

        # Calculate building bounds
        if all_x and all_y:
            min_x, max_x = min(all_x), max(all_x)
            min_y, max_y = min(all_y), max(all_y)
            mid_x = (min_x + max_x) / 2
            mid_y = (min_y + max_y) / 2
        else:
            min_x, max_x, min_y, max_y = 0, 40, 0, 30
            mid_x, mid_y = 20, 15

        # Group doors/windows by their host wall orientation
        south_openings = []  # Openings on south wall (low Y)
        north_openings = []  # Openings on north wall (high Y)
        west_openings = []   # Openings on west wall (low X)
        east_openings = []   # Openings on east wall (high X)

        # Process door data to group by wall
        for door in door_data:
            door_id = str(door.get('id', ''))
            if not door_id:
                continue
            location = door.get('location', door.get('point', {}))
            loc_x, loc_y = parse_coords(location)

            # Determine which wall this door is on
            if abs(loc_y - min_y) < 2:  # Near south wall
                south_openings.append(door_id)
            elif abs(loc_y - max_y) < 2:  # Near north wall
                north_openings.append(door_id)
            elif abs(loc_x - min_x) < 2:  # Near west wall
                west_openings.append(door_id)
            elif abs(loc_x - max_x) < 2:  # Near east wall
                east_openings.append(door_id)

        # Process window data to group by wall
        for window in window_data:
            window_id = str(window.get('id', ''))
            if not window_id:
                continue
            location = window.get('location', window.get('point', {}))
            loc_x, loc_y = parse_coords(location)

            # Determine which wall this window is on
            if abs(loc_y - min_y) < 2:  # Near south wall
                south_openings.append(window_id)
            elif abs(loc_y - max_y) < 2:  # Near north wall
                north_openings.append(window_id)
            elif abs(loc_x - min_x) < 2:  # Near west wall
                west_openings.append(window_id)
            elif abs(loc_x - max_x) < 2:  # Near east wall
                east_openings.append(window_id)

        # Sort walls for logical dimensioning
        horizontal_walls.sort(key=lambda w: w['y_pos'])  # South to north
        vertical_walls.sort(key=lambda w: w['x_pos'])    # West to east

        groups = {}

        # HORIZONTAL DIMENSIONS (measuring east-west, using vertical walls as references)
        if len(vertical_walls) >= 2:
            west_wall = vertical_walls[0]   # Westernmost wall
            east_wall = vertical_walls[-1]  # Easternmost wall

            # South wall dimension: West wall → openings on south wall → East wall
            groups["horiz_south_detail"] = [west_wall['id']] + south_openings + [east_wall['id']]
            # North wall dimension: West wall → openings on north wall → East wall
            groups["horiz_north_detail"] = [west_wall['id']] + north_openings + [east_wall['id']]

            # Template compatibility
            groups["horiz_west_detail"] = groups["horiz_south_detail"]
            groups["horiz_east_detail"] = groups["horiz_north_detail"]

            # All walls dimension (wall centerlines only)
            groups["horiz_dim_walls"] = [w['id'] for w in vertical_walls]

            # Overall dimension (outer walls only)
            groups["horiz_dim_overall"] = [west_wall['id'], east_wall['id']]
        else:
            groups.update({
                "horiz_west_detail": [], "horiz_east_detail": [],
                "horiz_south_detail": [], "horiz_north_detail": [],
                "horiz_dim_walls": [], "horiz_dim_overall": []
            })

        # VERTICAL DIMENSIONS (measuring north-south, using horizontal walls as references)
        if len(horizontal_walls) >= 2:
            south_wall = horizontal_walls[0]   # Southernmost wall
            north_wall = horizontal_walls[-1]  # Northernmost wall

            # West wall dimension: South wall → openings on west wall → North wall
            groups["vert_west_detail"] = [south_wall['id']] + west_openings + [north_wall['id']]
            # East wall dimension: South wall → openings on east wall → North wall
            groups["vert_east_detail"] = [south_wall['id']] + east_openings + [north_wall['id']]

            # Template compatibility
            groups["vert_south_detail"] = groups["vert_west_detail"]
            groups["vert_north_detail"] = groups["vert_east_detail"]

            # All walls dimension (wall centerlines only)
            groups["vert_dim_walls"] = [w['id'] for w in horizontal_walls]

            # Overall dimension (outer walls only)
            groups["vert_dim_overall"] = [south_wall['id'], north_wall['id']]
        else:
            groups.update({
                "vert_south_detail": [], "vert_north_detail": [],
                "vert_west_detail": [], "vert_east_detail": [],
                "vert_dim_walls": [], "vert_dim_overall": []
            })

        # Log what we created
        total_openings = len(south_openings) + len(north_openings) + len(west_openings) + len(east_openings)
        print(f"   📐 Dimension groups: {len(horizontal_walls)} horiz walls, {len(vertical_walls)} vert walls, {total_openings} openings")

        return groups

    def _create_basic_dimension_groups(self, wall_ids: list):
        """Fallback basic dimension grouping"""
        if len(wall_ids) >= 2:
            self.variables["horiz_west_detail"] = wall_ids[:2]
            self.variables["horiz_east_detail"] = wall_ids[-2:]
            self.variables["horiz_dim_walls"] = wall_ids
            self.variables["horiz_dim_overall"] = [wall_ids[0], wall_ids[-1]]
            self.variables["vert_south_detail"] = wall_ids[:2]
            self.variables["vert_north_detail"] = wall_ids[-2:]
            self.variables["vert_dim_walls"] = wall_ids
            self.variables["vert_dim_overall"] = [wall_ids[0], wall_ids[-1]]
        else:
            empty_groups = ["horiz_west_detail", "horiz_east_detail", "horiz_dim_walls", "horiz_dim_overall",
                          "vert_south_detail", "vert_north_detail", "vert_dim_walls", "vert_dim_overall"]
            for group in empty_groups:
                self.variables[group] = []


# --- LOCAL ORCHESTRATOR ---
class LocalOrchestrator(BaseOrchestrator):
    """Orchestrator for local LLMs (LM Studio) using planner-executor pattern"""

    # Active QBD session (if any)
    active_qbd_session: Optional['QBDSession'] = None

    PLANNER_SYSTEM_PROMPT = """You are an expert Revit planning agent.
Create a JSON execution plan. Respond ONLY with valid JSON array.

CRITICAL RULES:
1. IF the user provides an image or asks to "sketch/draw/layout from image", YOU MUST USE 'generate_layout_from_image'.
   - Pass "${uploaded_image}" as the 'image_base64' argument.
2. IF the user asks to "create family from photo" or "build family from image", USE 'create_family_from_photo'.
   - Pass "${uploaded_image}" as 'image_base64', provide family_name, category, and optional dimensions.
3. Use ${variable_name} for discovered IDs (e.g., ${level_0_id}, ${default_wall_type}).
4. FOR WALLS: Include "wall_type": "${default_wall_type}".
5. Output ONLY the JSON array, no explanation.

Example for floor plan from image:
[{"tool": "generate_layout_from_image", "args": {"image_base64": "${uploaded_image}", "target_area": 500}}]

Example for family from photo:
[{"tool": "create_family_from_photo", "args": {"image_base64": "${uploaded_image}", "family_name": "MyTable", "category": "Furniture", "object_hint": "table"}}]

Example for walls:
[{"tool": "create_walls_batch", "args": {"walls": [{"level_name": "Level 0", "start_point": [0,0,0], "end_point": [20,0,0], "height": 10, "wall_type": "${default_wall_type}"}]}}]
"""
    
    def __init__(self, provider: str):
        super().__init__(provider)
        self.variables = {}
        self.executor = PlanExecutor(REVIT_MCP_API_URL)
        self.lm_client = LMStudioClient()

    def _detect_direct_command(self, user_query: str) -> Optional[List[Dict]]:
        """Detect simple single-tool commands that don't need LLM planning"""
        query_lower = user_query.lower().strip()
        
        direct_commands = {
            "status": {"tool": "get_revit_status", "args": {}},
            "revit status": {"tool": "get_revit_status", "args": {}},
            "model info": {"tool": "get_revit_model_info", "args": {}},
            "manifest": {"tool": "get_server_manifest", "args": {}},
            "list walls": {"tool": "list_walls", "args": {}},
            "list levels": {"tool": "list_levels", "args": {}},
            "list views": {"tool": "list_views", "args": {}},
            "list sheets": {"tool": "list_sheets", "args": {}},
            "list wall types": {"tool": "list_wall_types", "args": {}},
            "list door types": {"tool": "list_door_types", "args": {}},
            "list window types": {"tool": "list_window_types", "args": {}},
            "list floor types": {"tool": "list_floor_types", "args": {}},
            "list roof types": {"tool": "list_roof_types", "args": {}},
            "list families": {"tool": "list_families", "args": {}},
            "list schedules": {"tool": "list_schedules", "args": {}},
            "get selection": {"tool": "get_selected_elements", "args": {}},
            "what is selected": {"tool": "get_selected_elements", "args": {}},
            "list tools": {"tool": "list_available_tools", "args": {}},
            "list all tools": {"tool": "list_available_tools", "args": {}},
            "available tools": {"tool": "list_available_tools", "args": {}},
            "what tools": {"tool": "list_available_tools", "args": {}},
            "show tools": {"tool": "list_available_tools", "args": {}},
            # System info (fast response for meta queries)
            "how many tools": {"tool": "get_system_info", "args": {}},
            "tool count": {"tool": "get_system_info", "args": {}},
            "system info": {"tool": "get_system_info", "args": {}},
            "capabilities": {"tool": "get_system_info", "args": {}},
            "what can you do": {"tool": "list_tool_categories", "args": {}},
            "list categories": {"tool": "list_tool_categories", "args": {}},
            "help": {"tool": "list_tool_categories", "args": {}},
            # Mode commands
            "list modes": {"tool": "list_modes", "args": {}},
            "show modes": {"tool": "list_modes", "args": {}},
            "what modes": {"tool": "list_modes", "args": {}},
            "current mode": {"tool": "get_current_mode", "args": {}},
        }

        # Check for mode switching commands
        mode_patterns = [
            (r"(?:switch|set|change|use)\s+(?:to\s+)?(\w+)\s+mode", "set_mode"),
            (r"(\w+)\s+mode\s+(?:please|now)?", "set_mode"),
            (r"enable\s+all\s+tools", "set_mode_all"),
        ]

        for pattern, action in mode_patterns:
            match = re.search(pattern, query_lower)
            if match:
                if action == "set_mode_all":
                    return [{"tool": "set_mode", "args": {"mode": "all"}}]
                elif action == "set_mode":
                    mode_name = match.group(1)
                    return [{"tool": "set_mode", "args": {"mode": mode_name}}]

        for trigger, tool_call in direct_commands.items():
            if trigger in query_lower:
                return [tool_call]

        return None

    async def _process_async_results(self, result: Dict) -> Dict:
        """Process results that need async execution (like family building)"""
        if not isinstance(result, dict):
            return result

        # Check if there are any pending async builds in the results
        results_list = result.get("results", [])
        for step_result in results_list:
            if isinstance(step_result, dict):
                step_data = step_result.get("result", step_result)
                if isinstance(step_data, dict) and step_data.get("_needs_async_build"):
                    print("   🏗️ Executing async family build...")
                    builder = step_data.get("_builder")
                    geometry = step_data.get("geometry")
                    family_name = step_data.get("family_name")

                    if builder and geometry and family_name:
                        try:
                            build_result = await builder.build_family(geometry, family_name)
                            # Update the step result with actual build result
                            step_result["result"] = build_result
                            print(f"   ✅ Family build complete: {build_result.get('status')}")
                        except Exception as e:
                            step_result["result"] = {
                                "status": "error",
                                "message": f"Async family build failed: {str(e)}"
                            }
                            print(f"   ❌ Family build failed: {e}")

        return result

    async def execute(self, user_query: str, image_data: str = None) -> Dict[str, Any]:
        print(f"\n🖥️ Using LOCAL orchestration ({self.provider.upper()})")
        print("=" * 60)

        # Reset variables
        self.variables = {}
        self.executor.variables = {}

        # Store image if provided
        if image_data:
            self.variables["uploaded_image"] = image_data
            self.executor.variables["uploaded_image"] = image_data
            print("   📸 Image stored in memory for processing")

        # STEP 0: Check for QBD (Question Based Design) interaction
        if QBD_AVAILABLE:
            qbd_result = await self._handle_qbd(user_query)
            if qbd_result:
                return qbd_result

        # STEP 1: Check for direct command
        direct_plan = self._detect_direct_command(user_query)
        if direct_plan:
            print(f"   ⚡ Direct Command Detected")
            result = self.executor.execute_plan(direct_plan)
            result = await self._process_async_results(result)
            return {"success": True, "strategy": "direct", "execution_results": result}

        # STEP 2: Quick discovery
        print("\n📊 PHASE 1: Discovery")
        discovery_data = await self._quick_discovery()

        # STEP 3: Check for template match
        template = self._detect_template(user_query)

        if template:
            # Check if template needs user input first
            if template.get("needs_input"):
                print(f"\n❓ Template needs user input: '{template['name']}'")
                question = template.get("question", "Please specify:")
                options = template.get("options", [])
                options_text = "\n".join([f"- {opt}" for opt in options])
                return {
                    "success": True,
                    "strategy": "needs_input",
                    "template_name": template["name"],
                    "question": question,
                    "options": options,
                    "reply": f"**{template['name']}**\n\n{question}\n\n{options_text}"
                }

            print(f"\n⚡ FAST PATH: Using template '{template['name']}'")
            self.executor._populate_variables_from_discovery(discovery_data)
            result = self.executor.execute_plan(template["plan"], discovery_data)
            result = await self._process_async_results(result)
            return {
                "success": True,
                "strategy": "template",
                "template_name": template["name"],
                "execution_results": result
            }

        # STEP 4: LLM planning
        print("\n🧠 PHASE 2: LLM Plan Creation")
        plan = await self._try_get_structured_plan(user_query, discovery_data)

        if plan:
            print("\n🚀 PHASE 3: Execution")
            result = self.executor.execute_plan(plan, discovery_data)
            result = await self._process_async_results(result)
            return {
                "success": True,
                "strategy": "llm_plan",
                "execution_results": result
            }

        # STEP 5: Fallback
        print("\n🔄 Fallback to LLM-guided execution")
        return await self._llm_guided_execution(user_query, discovery_data)

    async def _try_get_structured_plan(self, user_query: str, discovery_data: Dict) -> Optional[List[Dict]]:
        """Try to get structured plan from LLM using smart tool selection"""

        self.executor._populate_variables_from_discovery(discovery_data)

        # Build context string
        variables_str = "\n".join([
            f"- ${{ {k} }}: {v}"
            for k, v in self.executor.variables.items()
            if "id" in k or "type" in k or "name" in k
        ])

        # Use tool selector to find relevant tools (reduces context significantly)
        tools_list = []
        if TOOL_SELECTOR_AVAILABLE and select_tools_for_query:
            tool_names = select_tools_for_query(user_query, max_tools=15)
            for tool_name in tool_names:
                if tool_name in TOOL_FUNCTIONS:
                    func = TOOL_FUNCTIONS[tool_name]
                    doc = func.__doc__ or "No description"
                    first_line = doc.strip().split('\n')[0]
                    tools_list.append(f"- {tool_name}: {first_line}")
            print(f"   🔧 Planning with {len(tools_list)} relevant tools")

        tools_str = "\n".join(tools_list) if tools_list else "Use any appropriate Revit tool."

        planning_prompt = f"""
User Request: {user_query}

Available Tools:
{tools_str}

Available Variables (USE THESE EXACTLY):
{variables_str}

Create a JSON plan using only the tools listed above. Use variables like ${{level_0_id}} for IDs.
Your JSON plan (ONLY the JSON array):
"""

        reply = await self.lm_client.generate_plan(self.PLANNER_SYSTEM_PROMPT, planning_prompt)
        
        # Extract JSON
        try:
            json_match = re.search(r'\[[\s\S]*\]', reply)
            if json_match:
                plan = json.loads(json_match.group())
                if isinstance(plan, list) and len(plan) > 0:
                    if all(isinstance(s, dict) and "tool" in s for s in plan):
                        print(f"   ✅ Got structured plan with {len(plan)} steps")
                        return plan
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error: {e}")
        
        print("   ⚠️ Could not parse structured plan")
        return None

    async def _llm_guided_execution(self, user_query: str, discovery_data: Dict) -> Dict:
        """
        Fallback execution - calls LLM directly for conversational response.
        Uses smart tool selector to reduce context and avoid infinite loops.
        """
        print("   📝 Getting conversational response from LLM...")

        # Use tool selector to find relevant tools (reduces context significantly)
        relevant_tools = []
        if TOOL_SELECTOR_AVAILABLE and select_tools_for_query:
            tool_names = select_tools_for_query(user_query, max_tools=10)
            for tool_name in tool_names:
                if tool_name in TOOL_FUNCTIONS:
                    func = TOOL_FUNCTIONS[tool_name]
                    doc = func.__doc__ or "No description"
                    first_line = doc.strip().split('\n')[0]
                    relevant_tools.append(f"- {tool_name}: {first_line}")
            print(f"   🔧 Selected {len(relevant_tools)} relevant tools")

        # Build variables context
        variables_str = ""
        if discovery_data:
            self.executor._populate_variables_from_discovery(discovery_data)
            var_items = [
                f"- {k}: {v}"
                for k, v in self.executor.variables.items()
                if "id" in k or "type" in k or "name" in k
            ]
            variables_str = "\n".join(var_items[:15])  # Limit to 15 variables

        # Build tools context
        tools_str = "\n".join(relevant_tools) if relevant_tools else "No specific tools selected."

        # Conversational system prompt (not planning prompt)
        conv_system_prompt = f"""You are AriA, a friendly and knowledgeable Revit AI assistant.

Your personality:
- Warm and professional - greet users naturally when they say hello
- Proactive - suggest what you can help with when the conversation starts
- Focused - keep conversations on-track toward Revit tasks without being rigid

When users greet you or ask what's up:
- Respond warmly and ask what they'd like to work on today
- Mention 2-3 things you can help with (creating walls, placing doors, generating floor plans, etc.)

Available tools for this query:
{tools_str}

Current Revit model data:
{variables_str}

Guidelines:
- For task requests, describe what you'll do and use appropriate tools
- For unclear requests, ask friendly clarifying questions
- Keep responses concise but helpful
- If you can't help with something, suggest alternatives"""

        user_prompt = f"User: {user_query}"

        try:
            # Call LLM directly (not through /chat to avoid loop)
            reply = await self.lm_client.generate_plan(conv_system_prompt, user_prompt)

            if reply and reply.strip():
                print(f"   ✅ Got LLM response ({len(reply)} chars)")
                return {
                    "success": True,
                    "strategy": "llm_guided",
                    "reply": reply.strip()
                }
            else:
                return {
                    "success": False,
                    "strategy": "llm_guided",
                    "reply": "I couldn't process that request. Please try rephrasing or ask for 'help' to see available commands."
                }
        except Exception as e:
            print(f"   ❌ LLM fallback error: {e}")
            return {
                "success": False,
                "strategy": "llm_guided",
                "reply": f"Sorry, I encountered an error: {str(e)}. Try 'status' or 'list tools' for available commands."
            }

    async def _quick_discovery(self) -> Dict:
        """Fast discovery of essential info"""
        discovery_data = {}
        endpoints = {
            "list_levels": "/revit_mcp/list_levels",
            "list_wall_types": "/revit_mcp/list_wall_types",
            "list_door_types": "/revit_mcp/list_door_types",
            "list_window_types": "/revit_mcp/list_window_types",
            "list_views": "/revit_mcp/list_views"
        }
        
        for name, endpoint in endpoints.items():
            try:
                # Increased timeout for busy Revit sessions
                response = requests.get(f"{self.executor.api_url}{endpoint}", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    discovery_data[name] = data
                    print(f"    ✅ {name}: Found {len(data)} items")
                else:
                    print(f"    ⚠️ {name}: HTTP {response.status_code}")
                    discovery_data[name] = []
            except requests.exceptions.Timeout:
                print(f"    ⏳ {name}: Timeout - Revit may be busy")
                discovery_data[name] = []
            except Exception as e:
                print(f"    ⚠️ {name}: Error - {str(e)[:50]}...")
                discovery_data[name] = []
        
        return discovery_data

    def _detect_template(self, user_query: str) -> Optional[Dict]:
        """Detect template using external templates module"""

        print(f"   🔎 Checking templates for: '{user_query[:50]}...'")

        # Try the main detect_template function first
        try:
            result = templates.detect_template(user_query, self.executor.variables)
            if result:
                print(f"   ✅ Template matched: {result.get('name', 'unknown')}")
            else:
                print(f"   ❌ No template matched")
            return result
        except Exception as e:
            print(f"   ⚠️ Template detection error: {e}")
            
            traceback.print_exc()

        # Fallback to detect_house_template if that's what's available
        try:
            return templates.detect_house_template(user_query.lower(), self.executor.variables)
        except AttributeError:
            pass

        return None

    async def _handle_qbd(self, user_query: str) -> Optional[Dict[str, Any]]:
        """Handle QBD (Question Based Design) interactions"""
        query_lower = user_query.lower().strip()

        # Check if this is a QBD trigger
        if not detect_qbd_trigger(query_lower):
            # Check if there's an active session and the answer looks like a selection
            if self.active_qbd_session:
                # Check if it's a number (option selection) or option value
                if query_lower.isdigit() or len(query_lower) < 30:
                    return await self._process_qbd_answer(query_lower)
            return None

        print(f"\n🎯 QBD Mode Activated")

        # Check if continuing existing session
        if is_continue_trigger(query_lower):
            session = QBDSession.get_latest()
            if session:
                self.active_qbd_session = session
                print(f"   📂 Resuming session: {session.session_id}")
                question = session.get_current_question()
                return {
                    "success": True,
                    "strategy": "qbd",
                    "qbd_state": "question",
                    "question": question,
                    "reply": format_question_for_chat(question),
                    "session_id": session.session_id
                }
            else:
                # No session to continue, start new
                print(f"   📝 No existing session, starting new")

        # Start new QBD session
        self.active_qbd_session = QBDSession()
        self.active_qbd_session.save()
        print(f"   🆕 New session: {self.active_qbd_session.session_id}")

        question = self.active_qbd_session.get_current_question()
        return {
            "success": True,
            "strategy": "qbd",
            "qbd_state": "question",
            "question": question,
            "reply": format_question_for_chat(question),
            "session_id": self.active_qbd_session.session_id
        }

    async def _process_qbd_answer(self, answer: str) -> Optional[Dict[str, Any]]:
        """Process an answer to a QBD question"""
        if not self.active_qbd_session:
            return None

        # Parse answer - could be a number (1, 2, 3) or the actual value
        current_q = self.active_qbd_session.get_current_question()
        options = current_q.get("options", [])

        # If it's a number, map to option value
        if answer.isdigit():
            idx = int(answer) - 1
            if 0 <= idx < len(options):
                answer = options[idx].get("value", answer)

        # Check if answer matches any option value or label
        matched_value = None
        for opt in options:
            if answer == opt.get("value") or answer.lower() == opt.get("label", "").lower():
                matched_value = opt.get("value")
                break

        if matched_value:
            answer = matched_value

        print(f"   📝 QBD Answer: {answer}")

        # Process the answer
        result = self.active_qbd_session.process_answer(answer)

        if result.get("complete"):
            # Design is complete, execute the plan
            if result.get("action") == "generate":
                print(f"   🚀 QBD Complete - Executing generated plan")
                plan = result.get("plan", [])
                summary = result.get("summary", "")

                # Run discovery first
                discovery_data = await self._quick_discovery()
                self.executor._populate_variables_from_discovery(discovery_data)

                # Execute the plan
                exec_result = self.executor.execute_plan(plan, discovery_data)
                exec_result = await self._process_async_results(exec_result)

                # Clear active session
                self.active_qbd_session = None

                return {
                    "success": True,
                    "strategy": "qbd_complete",
                    "summary": summary,
                    "execution_results": exec_result,
                    "reply": f"**Design Generated!**\n\n{summary}\n\nCheck Revit for your new floor plan."
                }
            elif result.get("action") == "saved":
                self.active_qbd_session = None
                return {
                    "success": True,
                    "strategy": "qbd",
                    "qbd_state": "saved",
                    "reply": result.get("message")
                }
        else:
            # More questions to ask
            question = result
            return {
                "success": True,
                "strategy": "qbd",
                "qbd_state": "question",
                "question": question,
                "reply": format_question_for_chat(question),
                "session_id": self.active_qbd_session.session_id
            }

        return None


# --- FACTORY FUNCTION ---
def create_orchestrator() -> BaseOrchestrator:
    """Factory to create the correct orchestrator based on config"""
    config = load_server_config()
    provider = config.get("provider", "lmstudio").lower()
    return LocalOrchestrator(provider)


async def execute_query(user_query: str, image_data: str = None) -> Dict[str, Any]:
    """Execute a query through the orchestrator"""
    orchestrator = create_orchestrator()
    return await orchestrator.execute(user_query, image_data)


# --- CLI ---
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ADAPTIVE REVIT ORCHESTRATOR")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        print("\nEnter command (or Enter for example):")
        query = input("> ").strip()
        if not query:
            query = "get status"
            print(f"Using: {query}")
    
    print(f"\n📝 Query: {query}\n")
    
    result = asyncio.run(execute_query(query))
    
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    
    if result.get("strategy") == "direct" and result.get("response"):
        print(f"\n📋 {result.get('tool')} response:\n")
        response_data = result["response"]
        if isinstance(response_data, (dict, list)):
            print(json.dumps(response_data, indent=2, default=str))
        else:
            print(response_data)
    else:
        print(json.dumps(result, indent=2, default=str))