# tool_modes.py
# Dynamic tool loading system for local LLM optimization
# Loads only relevant tools based on current task context

from typing import Dict, List, Set, Optional
import re

# =============================================================================
# TOOL MODE DEFINITIONS
# =============================================================================

TOOL_MODES = {
    "geometry": {
        "name": "Geometry Mode",
        "description": "Create walls, floors, roofs, rooms, and place elements",
        "icon": "cube",
        "tools": [
            # Creation
            "create_wall", "create_walls_batch", "create_floor", "create_roof",
            "create_roof_footprint", "create_room", "create_rooms_batch",
            "create_level", "create_levels_batch", "create_directshape_mass",
            # Placement
            "place_family", "place_door", "place_window", "place_hosted_batch",
            "load_family",
            # Listing (geometry related)
            "list_levels", "list_walls", "list_wall_types", "list_door_types",
            "list_window_types", "list_floor_types", "list_roof_types",
            "list_families", "list_furniture_types", "list_ceiling_types",
            # Discovery
            "analyze_geometry_bounds", "list_elements_by_category",
            "get_selected_elements", "select_elements",
            # Generation
            "generate_floor_plan_walls", "generate_layout_from_image",
        ],
        "triggers": [
            r"create.*(wall|floor|roof|room|house|building|layout)",
            r"place.*(door|window|furniture|family)",
            r"build.*",
            r"model.*",
            r"\d+\s*x\s*\d+",  # dimensions like "40x40"
            r"add.*(wall|floor|roof|room)",
        ]
    },

    "annotation": {
        "name": "Annotation Mode",
        "description": "Add dimensions, tags, text notes, and grids",
        "icon": "ruler",
        "tools": [
            # Dimensions & Tags
            "create_dimension", "create_dimensions_batch",
            "create_tag", "create_tags_batch", "tag_elements",
            "create_text_note",
            # Grids & Reference
            "create_grids_batch", "create_reference_plane",
            "create_room_separation_lines",
            # Listing
            "list_walls", "list_elements_by_category",
            "get_selected_elements", "select_elements",
        ],
        "triggers": [
            r"dimension", r"tag", r"annotate", r"label",
            r"grid", r"text.*note", r"add.*note",
        ]
    },

    "documentation": {
        "name": "Documentation Mode",
        "description": "Create views, sheets, and schedules",
        "icon": "file-text",
        "tools": [
            # Views
            "list_views", "create_floor_plan", "create_ceiling_plan",
            "create_section", "create_elevation",
            # Sheets
            "list_sheets", "create_sheet", "create_sheets_batch",
            "place_view_on_sheet", "place_views_batch",
            # Schedules
            "create_schedule", "list_schedules", "get_schedulable_fields",
            "add_schedule_fields", "set_schedule_filter", "set_schedule_grouping",
            "set_schedule_sorting", "get_schedule_data", "remove_schedule_field",
            "delete_schedule",
            # Export
            "export_camera",
        ],
        "triggers": [
            r"schedule", r"sheet", r"view", r"plan",
            r"section", r"elevation", r"document",
            r"export", r"print",
        ]
    },

    "assemblies": {
        "name": "Assembly Mode",
        "description": "Create and modify wall types, assemblies, and layer structures",
        "icon": "layers",
        "tools": [
            # Wall Types
            "list_wall_types", "list_wall_type_layers", "get_wall_type_layers",
            "create_wall_type", "duplicate_wall_type",
            # Assembly Views
            "create_assembly_view",
            # Parameters
            "get_element_parameters", "set_element_parameter",
            "change_type",
        ],
        "triggers": [
            r"wall.*type", r"assembly", r"layer",
            r"compound.*structure", r"duplicate.*type",
        ]
    },

    "physics": {
        "name": "Physics/Analysis Mode",
        "description": "Structural, thermal, acoustic, and lighting analysis",
        "icon": "zap",
        "tools": [
            # Structural
            "analyze_beam", "analyze_column", "analyze_floor_system",
            # Thermal
            "analyze_thermal_assembly", "calculate_heat_loss",
            # Lighting
            "analyze_daylighting", "calculate_electric_lighting",
            # Acoustic
            "analyze_wall_stc", "calculate_reverberation_time",
            # Materials & Assemblies
            "list_assembly_presets", "get_assembly_details",
            "list_materials", "estimate_fasteners",
            # IFC
            "check_ifc_support", "import_ifc_assemblies_tool",
        ],
        "triggers": [
            r"analy[sz]e", r"structural", r"thermal", r"heat.*loss",
            r"acoustic", r"stc", r"lighting", r"daylight",
            r"beam", r"column", r"joist", r"r-value",
        ]
    },

    "family_editor": {
        "name": "Family Editor Mode",
        "description": "Create and edit Revit families",
        "icon": "box",
        "tools": [
            # Family Management
            "list_family_templates", "create_new_family_document",
            "load_family_into_project", "open_family_file",
            "save_family", "get_family_document_status", "verify_family_document",
            # Geometry
            "create_family_extrusion", "create_family_void",
            "cut_solid_with_void", "create_family_blend",
            # Parameters
            "create_family_parameter", "set_family_parameter_value",
            "list_family_parameters",
            # Types
            "create_family_type", "list_family_types", "set_current_family_type",
            # Reference & Constraints
            "create_reference_plane_family", "create_family_dimension",
            "bind_dimension_to_parameter", "align_elements",
            "list_reference_planes",
            # Photo to Family
            "analyze_photo_for_family", "create_parametric_family_from_photo",
            "analyze_multiple_photos_for_family", "create_family_from_photo",
        ],
        "triggers": [
            r"family", r"create.*from.*photo", r"extrusion",
            r"parameter", r"template", r"\.rfa",
        ]
    },

    "data": {
        "name": "Data/Query Mode",
        "description": "Query model information, search, and status",
        "icon": "database",
        "tools": [
            # Status
            "get_revit_status", "get_status", "get_revit_model_info",
            "get_model_info", "get_server_manifest", "get_manifest",
            # Listing (all)
            "list_levels", "list_walls", "list_wall_types", "list_door_types",
            "list_window_types", "list_floor_types", "list_roof_types",
            "list_families", "list_views", "list_sheets", "list_elements",
            "list_elements_by_category", "list_schedules",
            # Selection
            "get_selected_elements", "select_elements",
            # Search
            "search_family_library", "index_family_library",
            # Parameters
            "get_element_parameters",
            # Documentation
            "get_tool_documentation", "list_documentation_topics",
            "list_available_tools",
        ],
        "triggers": [
            r"list", r"show", r"what", r"get", r"status",
            r"search", r"find", r"query",
        ]
    },

    "delete": {
        "name": "Delete Mode",
        "description": "Delete elements from the model",
        "icon": "trash",
        "tools": [
            "delete_element", "delete_elements", "delete_dimensions",
            "delete_schedule",
            # Need listing to find what to delete
            "list_elements_by_category", "get_selected_elements",
        ],
        "triggers": [
            r"delete", r"remove", r"clear",
        ]
    },
}

# Core tools always available in every mode
CORE_TOOLS = {
    "get_revit_status", "get_status", "list_levels",
    "list_available_tools", "get_server_manifest",
}


# =============================================================================
# MODE MANAGER CLASS
# =============================================================================

class ToolModeManager:
    """Manages tool visibility based on current mode"""

    def __init__(self):
        self.current_mode: Optional[str] = None
        self.active_tools: Set[str] = set()
        self._load_all_tools()

    def _load_all_tools(self):
        """Load all tools (default state)"""
        self.active_tools = set()
        for mode_config in TOOL_MODES.values():
            self.active_tools.update(mode_config["tools"])
        self.active_tools.update(CORE_TOOLS)

    def set_mode(self, mode_name: str) -> Dict:
        """Set the active tool mode"""
        if mode_name == "all":
            self._load_all_tools()
            self.current_mode = None
            return {
                "status": "success",
                "mode": "all",
                "message": "All tools enabled",
                "tool_count": len(self.active_tools)
            }

        if mode_name not in TOOL_MODES:
            return {
                "status": "error",
                "message": f"Unknown mode: {mode_name}",
                "available_modes": list(TOOL_MODES.keys())
            }

        mode_config = TOOL_MODES[mode_name]
        self.current_mode = mode_name
        self.active_tools = set(mode_config["tools"]) | CORE_TOOLS

        return {
            "status": "success",
            "mode": mode_name,
            "name": mode_config["name"],
            "description": mode_config["description"],
            "tool_count": len(self.active_tools),
            "tools": sorted(list(self.active_tools))
        }

    def add_mode(self, mode_name: str) -> Dict:
        """Add a mode's tools to current active tools (stacking)"""
        if mode_name not in TOOL_MODES:
            return {"status": "error", "message": f"Unknown mode: {mode_name}"}

        mode_config = TOOL_MODES[mode_name]
        self.active_tools.update(mode_config["tools"])

        return {
            "status": "success",
            "message": f"Added {mode_config['name']} tools",
            "tool_count": len(self.active_tools)
        }

    def detect_mode(self, user_message: str) -> Optional[str]:
        """Detect appropriate mode from user message"""
        message_lower = user_message.lower()

        # Check each mode's triggers
        mode_scores = {}
        for mode_name, mode_config in TOOL_MODES.items():
            score = 0
            for trigger in mode_config.get("triggers", []):
                if re.search(trigger, message_lower):
                    score += 1
            if score > 0:
                mode_scores[mode_name] = score

        if mode_scores:
            # Return mode with highest score
            best_mode = max(mode_scores, key=mode_scores.get)
            return best_mode

        return None

    def auto_set_mode(self, user_message: str) -> Dict:
        """Automatically detect and set mode based on user message"""
        detected_mode = self.detect_mode(user_message)

        if detected_mode:
            result = self.set_mode(detected_mode)
            result["auto_detected"] = True
            return result

        # No specific mode detected - use all tools
        self._load_all_tools()
        return {
            "status": "success",
            "mode": "all",
            "message": "No specific mode detected, all tools available",
            "auto_detected": True,
            "tool_count": len(self.active_tools)
        }

    def is_tool_active(self, tool_name: str) -> bool:
        """Check if a tool is currently active"""
        return tool_name in self.active_tools

    def get_active_tools(self) -> List[str]:
        """Get list of currently active tools"""
        return sorted(list(self.active_tools))

    def get_modes(self) -> Dict:
        """Get all available modes with their info"""
        modes = {}
        for mode_name, mode_config in TOOL_MODES.items():
            modes[mode_name] = {
                "name": mode_config["name"],
                "description": mode_config["description"],
                "icon": mode_config.get("icon", "tool"),
                "tool_count": len(mode_config["tools"]),
                "is_active": self.current_mode == mode_name
            }
        return {
            "current_mode": self.current_mode or "all",
            "modes": modes,
            "active_tool_count": len(self.active_tools)
        }

    def get_mode_tools(self, mode_name: str) -> List[str]:
        """Get tools for a specific mode"""
        if mode_name not in TOOL_MODES:
            return []
        return TOOL_MODES[mode_name]["tools"]


# =============================================================================
# COMPLETE ENDPOINT MAP (ALL 113 TOOLS)
# =============================================================================

COMPLETE_ENDPOINT_MAP = {
    # === GEOMETRY TOOLS ===
    "create_wall": "/revit_mcp/create_wall",
    "create_walls_batch": "/revit_mcp/create_walls_batch",
    "create_floor": "/revit_mcp/create_floor",
    "create_roof": "/revit_mcp/create_roof",
    "create_roof_footprint": "/revit_mcp/create_roof",
    "create_room": "/revit_mcp/create_room",
    "create_rooms_batch": "/revit_mcp/create_rooms_batch",
    "create_level": "/revit_mcp/create_level",
    "create_levels_batch": "/revit_mcp/create_levels_batch",
    "create_directshape_mass": "/revit_mcp/create_directshape_mass",
    "place_family": "/revit_mcp/place_family",
    "place_door": "/revit_mcp/place_door",
    "place_window": "/revit_mcp/place_window",
    "place_hosted_batch": "/revit_mcp/place_hosted_batch",
    "load_family": "/revit_mcp/load_family",

    # === DATA/LISTING TOOLS ===
    "list_levels": "/revit_mcp/list_levels",
    "list_walls": "/revit_mcp/list_walls",
    "list_wall_types": "/revit_mcp/list_wall_types",
    "list_door_types": "/revit_mcp/list_door_types",
    "list_window_types": "/revit_mcp/list_window_types",
    "list_floor_types": "/revit_mcp/list_floor_types",
    "list_roof_types": "/revit_mcp/list_roof_types",
    "list_families": "/revit_mcp/list_families",
    "list_ceiling_types": "/revit_mcp/list_ceiling_types",
    "list_furniture_types": "/revit_mcp/list_furniture_types",
    "list_views": "/revit_mcp/list_views",
    "list_sheets": "/revit_mcp/list_sheets",
    "list_elements": "/revit_mcp/list_elements",
    "list_elements_by_category": "/revit_mcp/list_elements",
    "list_wall_ids": "/revit_mcp/list_elements",
    "list_door_ids": "/revit_mcp/list_elements",
    "list_window_ids": "/revit_mcp/list_elements",
    "list_dimensions": "/revit_mcp/list_elements",

    # === STATUS/INFO TOOLS ===
    "get_status": "/revit_mcp/status",
    "get_revit_status": "/revit_mcp/status",
    "get_revit_model_info": "/revit_mcp/model_info",
    "get_model_info": "/revit_mcp/model_info",
    "get_server_manifest": "/revit_mcp/manifest",
    "get_manifest": "/revit_mcp/manifest",
    "get_selected_elements": "/revit_mcp/get_selection",
    "select_elements": "/revit_mcp/select_elements",
    "get_element_parameters": "/revit_mcp/get_element_parameters",
    "set_element_parameter": "/revit_mcp/set_parameter",
    "change_type": "/revit_mcp/change_type",

    # === ANNOTATION TOOLS ===
    "create_tag": "/revit_mcp/create_tags_batch",
    "create_tags_batch": "/revit_mcp/create_tags_batch",
    "tag_elements": "/revit_mcp/create_tags_batch",
    "create_text_note": "/revit_mcp/create_text_notes_batch",
    "create_dimension": "/revit_mcp/create_dimension",
    "create_dimensions_batch": "/revit_mcp/create_dimensions_batch",
    "create_grids_batch": "/revit_mcp/create_grids_batch",
    "create_reference_plane": "/revit_mcp/create_reference_plane",
    "create_room_separation_lines": "/revit_mcp/create_room_separation_lines",

    # === VIEW TOOLS ===
    "create_floor_plan": "/revit_mcp/create_floor_plan",
    "create_ceiling_plan": "/revit_mcp/create_ceiling_plan",
    "create_section": "/revit_mcp/create_section",
    "create_elevation": "/revit_mcp/create_elevation",

    # === SHEET TOOLS ===
    "create_sheet": "/revit_mcp/create_sheet",
    "create_sheets_batch": "/revit_mcp/create_sheets_batch",
    "place_view_on_sheet": "/revit_mcp/place_view_on_sheet",
    "place_views_batch": "/revit_mcp/place_views_batch",

    # === SCHEDULE TOOLS ===
    "create_schedule": "/revit_mcp/create_schedule",
    "list_schedules": "/revit_mcp/list_schedules",
    "get_schedulable_fields": "/revit_mcp/get_schedulable_fields",
    "add_schedule_fields": "/revit_mcp/add_schedule_field",
    "set_schedule_filter": "/revit_mcp/set_schedule_filter",
    "set_schedule_grouping": "/revit_mcp/set_schedule_grouping",
    "set_schedule_sorting": "/revit_mcp/set_schedule_sorting",
    "get_schedule_data": "/revit_mcp/get_schedule_data",
    "remove_schedule_field": "/revit_mcp/remove_schedule_field",
    "delete_schedule": "/revit_mcp/delete_schedule",

    # === ASSEMBLY/WALL TYPE TOOLS ===
    "list_wall_type_layers": "/revit_mcp/get_wall_type_layers",
    "get_wall_type_layers": "/revit_mcp/get_wall_type_layers",
    "create_wall_type": "/revit_mcp/create_wall_type",
    "duplicate_wall_type": "/revit_mcp/duplicate_wall_type",
    "create_assembly_view": "/revit_mcp/create_assembly_view",

    # === DELETE TOOLS ===
    "delete_element": "/revit_mcp/delete_elements",
    "delete_elements": "/revit_mcp/delete_elements",
    "delete_dimensions": "/revit_mcp/delete_elements",

    # === GENERATION TOOLS ===
    "generate_floor_plan_walls": "/revit_mcp/generate_floor_plan_walls",

    # === CAMERA/EXPORT ===
    "export_camera": "/revit_mcp/export_camera",

    # === FAMILY EDITOR TOOLS ===
    "list_family_templates": "/revit_mcp/family/list_templates",
    "create_new_family_document": "/revit_mcp/family/create_new",
    "create_family_extrusion": "/revit_mcp/family/create_extrusion",
    "load_family_into_project": "/revit_mcp/family/load_into_project",
    "create_reference_plane_family": "/revit_mcp/family/create_ref_plane",
    "create_family_parameter": "/revit_mcp/family/create_parameter",
    "set_family_parameter_value": "/revit_mcp/family/set_parameter_value",
    "list_family_parameters": "/revit_mcp/family/list_parameters",
    "create_family_type": "/revit_mcp/family/create_type",
    "list_family_types": "/revit_mcp/family/list_types",
    "set_current_family_type": "/revit_mcp/family/set_current_type",
    "create_family_void": "/revit_mcp/family/create_void",
    "cut_solid_with_void": "/revit_mcp/family/cut_solid",
    "create_family_blend": "/revit_mcp/family/create_blend",
    "create_family_dimension": "/revit_mcp/family/create_dimension",
    "bind_dimension_to_parameter": "/revit_mcp/family/bind_dimension",
    "align_elements": "/revit_mcp/family/align_elements",
    "list_reference_planes": "/revit_mcp/family/list_ref_planes",
    "open_family_file": "/revit_mcp/family/open",
    "get_family_document_status": "/revit_mcp/family/document_status",
    "verify_family_document": "/revit_mcp/family/verify",
    "save_family": "/revit_mcp/family/save",

    # === PHYSICS/ANALYSIS TOOLS (handled internally, no C# endpoint) ===
    # These are computed in Python, not routed to C#

    # === SEARCH/LIBRARY TOOLS ===
    "search_family_library": "/revit_mcp/search_family_library",
    "index_family_library": "/revit_mcp/index_family_library",
}


# Global instance
_mode_manager = None

def get_mode_manager() -> ToolModeManager:
    """Get or create the global mode manager instance"""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = ToolModeManager()
    return _mode_manager
