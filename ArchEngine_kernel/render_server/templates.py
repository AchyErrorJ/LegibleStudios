"""
Revit MCP Templates
===================
Pre-built execution templates for common Revit operations.
"""

import re
from typing import Dict, List, Any, Optional


# =============================================================================
# TEMPLATE DETECTION
# =============================================================================

def detect_template(user_query: str, variables: Dict = None) -> Optional[Dict]:
    """
    Detect which template matches the user query.
    Returns template dict with 'name' and 'plan', or None if no match.

    Template order is critical - most specific triggers first to avoid false matches.
    """
    query_lower = user_query.lower()

    # === META QUERIES (check first) ===
    template = detect_help_template(query_lower, variables)
    if template:
        return template

    template = detect_model_config_template(query_lower, variables)
    if template:
        return template

    template = detect_status_template(query_lower, variables)
    if template:
        return template

    # === SCHEDULES (very specific triggers) ===
    template = detect_material_schedule_template(query_lower, variables)
    if template:
        return template

    template = detect_opening_schedule_template(query_lower, variables)
    if template:
        return template

    template = detect_room_finish_schedule_template(query_lower, variables)
    if template:
        return template

    # === ANALYSIS (very specific triggers) ===
    template = detect_structural_analysis_template(query_lower, variables)
    if template:
        return template

    template = detect_thermal_analysis_template(query_lower, variables)
    if template:
        return template

    template = detect_lighting_analysis_template(query_lower, variables)
    if template:
        return template

    template = detect_acoustic_analysis_template(query_lower, variables)
    if template:
        return template

    # === TYPE DISCOVERY ===
    template = detect_type_discovery_template(query_lower, variables)
    if template:
        return template

    # === ROOM CREATION ===
    template = detect_room_creation_template(query_lower, variables)
    if template:
        return template

    # === RENDER PIPELINE ===
    template = detect_render_pipeline_template(query_lower, variables)
    if template:
        return template

    # === DOCUMENTATION ===
    template = detect_cd_set_template(query_lower, variables)
    if template:
        return template

    template = detect_detail_template(query_lower, variables)
    if template:
        return template

    # === GEOMETRY CREATION ===
    template = detect_foundation_template(query_lower, variables)
    if template:
        return template

    template = detect_interior_fitout_template(query_lower, variables)
    if template:
        return template

    template = detect_geometry_discovery_template(query_lower, variables)
    if template:
        return template

    # === ELEMENT DISCOVERY ===
    template = detect_window_geometry_template(query_lower, variables)
    if template:
        return template

    template = detect_window_discovery_template(query_lower, variables)
    if template:
        return template

    template = detect_door_discovery_template(query_lower, variables)
    if template:
        return template

    # === VISION PROCESSING ===
    template = detect_family_from_photo_template(query_lower, variables)
    if template:
        return template

    template = detect_sketch_to_walls_template(query_lower, variables)
    if template:
        return template

    # === DIMENSIONING ===
    template = detect_elevation_dimension_template(query_lower, variables)
    if template:
        return template

    # === ROOM/HOUSE CREATION ===
    template = detect_room_layout_template(query_lower, variables)
    if template:
        return template

    # REMOVED: detect_floor_plan_template - redundant with room_layout

    template = detect_house_template(query_lower, variables)
    if template:
        return template

    # === ANNOTATION (catch-all, check last) ===
    template = detect_dimension_template(query_lower, variables)
    if template:
        return template

    template = detect_tagging_template(query_lower, variables)
    if template:
        return template

    template = detect_annotation_template(query_lower, variables)
    if template:
        return template

    return None


# =============================================================================
# TEMPLATE 1: HOUSE / STRUCTURE
# =============================================================================

def detect_house_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect and build house/room template"""
    
    triggers = ["house", "building", "structure"]
    if not any(t in query_lower for t in triggers):
        return None

    # 1. Try to find explicit dimensions
    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)
    
    if size_match:
        width = int(size_match.group(1))
        depth = int(size_match.group(2))
    else:
        # 🛑 FIX: Default to 20x20 if no size specified
        print("   ⚠️ No dimensions found, defaulting to 20x20")
        width = 20
        depth = 20
    
    # Extract options
    wall_height = 10  # Default feet
    height_match = re.search(r'(\d+)\s*(?:foot|feet|ft)', query_lower)
    if height_match:
        wall_height = int(height_match.group(1))
    
    stories = 1
    stories_match = re.search(r'(\d+)\s*(?:stor|floor|level)', query_lower)
    if stories_match:
        stories = int(stories_match.group(1))
    
    print(f"   🎯 House Template: {width}x{depth}, {wall_height}ft walls, {stories} story")
    
    plan = build_house_plan(width, depth, wall_height, stories)
    
    return {
        "name": f"{width}x{depth} structure with {stories} story",
        "plan": plan
    }


def build_house_plan(width: int, depth: int, wall_height: int, stories: int) -> List[Dict]:
    """Build the execution plan for a house"""
    
    plan = []
    
    # Elevations in feet (Revit internal units)
    base_elevation = 0.0
    top_elevation = float(wall_height)
    
    # Step 1: Create levels
    plan.append({
        "tool": "create_levels_batch",
        "args": {
            "levels": [
                {"name": "Ground Floor", "elevation": base_elevation},
                {"name": "Top of Wall", "elevation": top_elevation}
            ]
        }
    })
    
    # Step 2: Create walls
    plan.append({
        "tool": "create_walls_batch",
        "args": {
            "walls": [
                {"start_point": [0, 0, 0], "end_point": [width, 0, 0],
                 "height": wall_height, "level_name": "Ground Floor", "wall_type": "${default_wall_type}"},
                {"start_point": [width, 0, 0], "end_point": [width, depth, 0],
                 "height": wall_height, "level_name": "Ground Floor", "wall_type": "${default_wall_type}"},
                {"start_point": [width, depth, 0], "end_point": [0, depth, 0],
                 "height": wall_height, "level_name": "Ground Floor", "wall_type": "${default_wall_type}"},
                {"start_point": [0, depth, 0], "end_point": [0, 0, 0],
                 "height": wall_height, "level_name": "Ground Floor", "wall_type": "${default_wall_type}"}
            ]
        }
    })
    
    # Step 3: Create floor
    plan.append({
        "tool": "create_floor",
        "args": {
            "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
            "level_name": "Ground Floor"
        }
    })
    
    # Step 4: Create roof
    plan.append({
        "tool": "create_roof_footprint",
        "args": {
            "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
            "level_name": "Top of Wall",
            "slope_degrees": 0.0
        }
    })
    
    # Step 5: Place doors and windows
    door_height = 0.0
    window_height = 3.0
    window_spacing = width / 4
    
    plan.append({
        "tool": "place_hosted_batch",
        "args": {
            "placements": [
                # Door on south wall
                {
                    "host_id": "${wall_batch_0_wall_0}",
                    "point": [width / 2, 0, door_height],
                    "family_name": "${default_door_family}",
                    "type_name": "${default_door_type}"
                },
                # Windows on south wall
                {
                    "host_id": "${wall_batch_0_wall_0}",
                    "point": [window_spacing, 0, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                {
                    "host_id": "${wall_batch_0_wall_0}",
                    "point": [width - window_spacing, 0, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                # Windows on east wall
                {
                    "host_id": "${wall_batch_0_wall_1}",
                    "point": [width, depth / 4, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                {
                    "host_id": "${wall_batch_0_wall_1}",
                    "point": [width, depth * 3 / 4, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                # Windows on north wall
                {
                    "host_id": "${wall_batch_0_wall_2}",
                    "point": [window_spacing, depth, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                {
                    "host_id": "${wall_batch_0_wall_2}",
                    "point": [width / 2, depth, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                {
                    "host_id": "${wall_batch_0_wall_2}",
                    "point": [width - window_spacing, depth, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                # Windows on west wall
                {
                    "host_id": "${wall_batch_0_wall_3}",
                    "point": [0, depth / 4, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                },
                {
                    "host_id": "${wall_batch_0_wall_3}",
                    "point": [0, depth * 3 / 4, window_height],
                    "family_name": "${default_window_family}",
                    "type_name": "${default_window_type}"
                }
            ]
        }
    })
    
    return plan


# =============================================================================
# FOUNDATION TEMPLATE
# =============================================================================

def detect_foundation_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect foundation creation requests"""

    triggers = ["foundation", "footing", "weeping tile", "foundation wall"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse dimensions if specified
    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)

    if size_match:
        width = int(size_match.group(1))
        depth = int(size_match.group(2))
    else:
        # Use building perimeter - will be determined from existing walls
        width = None
        depth = None

    # Parse foundation height (depth below grade)
    # Default: 5'6" to top of footing
    footing_top_elevation = -5.5  # 5'6" below grade (negative)
    # Match patterns like "8' deep", "8 feet deep", "5'6\" deep", "5 foot 6 inch deep"
    # Format: {feet}'{inches}" deep OR {feet} feet {inches} inch deep
    height_patterns = [
        r'(\d+)\s*(?:\'|feet?|ft)\s*(\d+)?\s*(?:\"|inch|in)?\s*(?:deep|depth|below)',  # 5'6" deep, 8 feet deep
        r'(\d+)\s*(?:deep|depth|below)',  # Simple "8 deep" fallback
    ]
    for pattern in height_patterns:
        height_match = re.search(pattern, query_lower)
        if height_match:
            feet = int(height_match.group(1))
            inches = int(height_match.group(2)) if height_match.lastindex >= 2 and height_match.group(2) else 0
            footing_top_elevation = -(feet + inches / 12.0)
            break

    # Parse footing width
    # Default: 24" (2 feet)
    footing_width = 2.0
    width_match = re.search(r'(\d+)\s*(?:\"|in|inch)?\s*(?:wide|width)', query_lower)
    if width_match:
        footing_width = int(width_match.group(1)) / 12.0  # Convert inches to feet

    print(f"   [Foundation] Template: Footing @ {footing_top_elevation}ft, Width: {footing_width}ft")

    plan = build_foundation_plan(width, depth, footing_top_elevation, footing_width)

    return {
        "name": f"Foundation with footing @ {footing_top_elevation}ft",
        "plan": plan
    }


def build_foundation_plan(width: Optional[int], depth: Optional[int],
                         footing_top_elevation: float, footing_width: float) -> List[Dict]:
    """
    Build execution plan for foundation system.

    Creates:
    1. Foundation walls around building perimeter
    2. Footing slab at base
    3. Weeping tile as sweep at footing height

    Args:
        width: Building width (None = use existing geometry)
        depth: Building depth (None = use existing geometry)
        footing_top_elevation: Elevation of top of footing (negative = below grade)
        footing_width: Width of footing in feet
    """

    plan = []

    # Foundation wall height (from top of footing to grade)
    foundation_height = abs(footing_top_elevation)

    # Footing thickness (typical 12" = 1 foot)
    footing_thickness = 1.0
    footing_bottom_elevation = footing_top_elevation - footing_thickness

    # Step 1: Get existing geometry if width/depth not specified
    use_geometry = width is None or depth is None
    if use_geometry:
        plan.append({
            "tool": "list_walls",
            "description": "Get existing walls to find building perimeter",
            "args": {},
            "extract": "walls_data"
        })
        plan.append({
            "tool": "analyze_geometry_bounds",
            "description": "Calculate building bounds from walls",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        })

    # Step 2: Create foundation levels
    plan.append({
        "tool": "create_levels_batch",
        "args": {
            "levels": [
                {"name": "Foundation Bottom", "elevation": footing_bottom_elevation},
                {"name": "Top of Footing", "elevation": footing_top_elevation},
                {"name": "Grade", "elevation": 0.0}
            ]
        }
    })

    # Step 3: Create foundation walls around perimeter
    # Foundation walls go from top of footing to grade
    # When using geometry bounds, use max_x/max_y directly instead of arithmetic
    if use_geometry:
        # Use bounds variables - no arithmetic needed
        corner_min_x = "${bounds.min_x}"
        corner_min_y = "${bounds.min_y}"
        corner_max_x = "${bounds.max_x}"
        corner_max_y = "${bounds.max_y}"
    else:
        # User specified dimensions - start at origin
        corner_min_x = 0
        corner_min_y = 0
        corner_max_x = width
        corner_max_y = depth

    plan.append({
        "tool": "create_walls_batch",
        "args": {
            "walls": [
                # South wall
                {
                    "start_point": [corner_min_x, corner_min_y, footing_top_elevation],
                    "end_point": [corner_max_x, corner_min_y, footing_top_elevation],
                    "height": foundation_height,
                    "level_name": "Top of Footing",
                    "wall_type": "Foundation - 12\" Concrete"
                },
                # East wall
                {
                    "start_point": [corner_max_x, corner_min_y, footing_top_elevation],
                    "end_point": [corner_max_x, corner_max_y, footing_top_elevation],
                    "height": foundation_height,
                    "level_name": "Top of Footing",
                    "wall_type": "Foundation - 12\" Concrete"
                },
                # North wall
                {
                    "start_point": [corner_max_x, corner_max_y, footing_top_elevation],
                    "end_point": [corner_min_x, corner_max_y, footing_top_elevation],
                    "height": foundation_height,
                    "level_name": "Top of Footing",
                    "wall_type": "Foundation - 12\" Concrete"
                },
                # West wall
                {
                    "start_point": [corner_min_x, corner_max_y, footing_top_elevation],
                    "end_point": [corner_min_x, corner_min_y, footing_top_elevation],
                    "height": foundation_height,
                    "level_name": "Top of Footing",
                    "wall_type": "Foundation - 12\" Concrete"
                }
            ]
        }
    })

    # Step 4: Create footing slab
    # Footing extends at the foundation wall corners (offset handled by floor type)
    plan.append({
        "tool": "create_floor",
        "args": {
            "points": [
                [corner_min_x, corner_min_y, footing_top_elevation],
                [corner_max_x, corner_min_y, footing_top_elevation],
                [corner_max_x, corner_max_y, footing_top_elevation],
                [corner_min_x, corner_max_y, footing_top_elevation]
            ],
            "level_name": "Top of Footing",
            "floor_type": "Concrete Footing"
        }
    })

    # Step 5: Create weeping tile as generic sweep at footing height
    # Weeping tile runs around perimeter at footing level
    # Using model lines to represent weeping tile (placement at corners, offset in line style)
    plan.append({
        "tool": "create_model_lines_batch",
        "args": {
            "lines": [
                # South side
                {
                    "start": [corner_min_x, corner_min_y, footing_top_elevation],
                    "end": [corner_max_x, corner_min_y, footing_top_elevation],
                    "line_style": "Weeping Tile"
                },
                # East side
                {
                    "start": [corner_max_x, corner_min_y, footing_top_elevation],
                    "end": [corner_max_x, corner_max_y, footing_top_elevation],
                    "line_style": "Weeping Tile"
                },
                # North side
                {
                    "start": [corner_max_x, corner_max_y, footing_top_elevation],
                    "end": [corner_min_x, corner_max_y, footing_top_elevation],
                    "line_style": "Weeping Tile"
                },
                # West side
                {
                    "start": [corner_min_x, corner_max_y, footing_top_elevation],
                    "end": [corner_min_x, corner_min_y, footing_top_elevation],
                    "line_style": "Weeping Tile"
                }
            ]
        }
    })

    return plan


def detect_geometry_discovery_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to discover/analyze existing geometry - useful for LLMs to understand the model"""

    triggers = ["analyze geometry", "discover geometry", "find geometry",
                "what geometry", "existing geometry", "model bounds",
                "footprint size", "building footprint", "existing walls"]

    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Geometry Discovery Template")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get all walls in the model",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate bounding box from walls",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        }
    ]

    return {
        "name": "Geometry Discovery",
        "plan": plan
    }


def detect_window_discovery_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to find windows for dimensioning - groups wall + window data"""

    triggers = ["find windows", "window locations", "list windows",
                "discover windows", "window positions", "windows for dimension",
                "dimension windows", "window discovery"]

    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Window Discovery Template")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get all walls to identify hosts",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "list_window_ids",
            "description": "Get all window IDs and locations",
            "args": {},
            "extract": "window_data"
        },
        {
            "step": 3,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate building bounds for reference",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        }
    ]

    return {
        "name": "Window Discovery",
        "plan": plan
    }


def detect_door_discovery_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to find doors for dimensioning"""

    triggers = ["find doors", "door locations", "list doors",
                "discover doors", "door positions", "doors for dimension",
                "dimension doors", "door discovery"]

    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Door Discovery Template")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get all walls to identify hosts",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "list_door_ids",
            "description": "Get all door IDs and locations",
            "args": {},
            "extract": "door_data"
        },
        {
            "step": 3,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate building bounds for reference",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        }
    ]

    return {
        "name": "Door Discovery",
        "plan": plan
    }


def detect_partition_within_existing_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create partitions within existing geometry"""

    # Triggers: "partition existing", "within existing walls", "inside current", "subdivide"
    triggers = ["within existing", "inside existing", "partition existing",
                "subdivide", "within current", "inside current", "within the"]

    if not any(t in query_lower for t in triggers):
        return None

    # Must have bed/bath to know what rooms to create
    bed_match = re.search(r'(\d+)\s*(?:bed|bedroom|br)', query_lower)
    bath_match = re.search(r'(\d+)\s*(?:bath|bathroom|ba)', query_lower)

    if not bed_match and not bath_match:
        return None

    bedrooms = int(bed_match.group(1)) if bed_match else 1
    bathrooms = int(bath_match.group(1)) if bath_match else 1

    print(f"   🎯 Partition Within Existing: {bedrooms} bed, {bathrooms} bath")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get existing walls to find bounding geometry",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate bounding box from walls",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        },
        {
            "step": 3,
            "tool": "generate_floor_plan_walls",
            "description": "Generate interior partitions within bounds",
            "args": {
                "width": "${bounds.width}",
                "depth": "${bounds.depth}",
                "rooms": [
                    {"type": "bedroom", "count": bedrooms},
                    {"type": "bathroom", "count": bathrooms}
                ],
                "level_name": "${base_level_name}",
                "wall_height": 10.0,
                "interior_wall_type": "${default_interior_wall_type}",
                "wet_wall_type": "${default_wet_wall_type}",
                "interior_only": True,
                "origin_x": "${bounds.min_x}",
                "origin_y": "${bounds.min_y}"
            }
        }
    ]

    return {
        "name": f"Partition existing geometry: {bedrooms} bed {bathrooms} bath",
        "plan": plan
    }


def detect_room_layout_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect room layout commands - supports both detailed and simple 'X bed Y bath' format"""

    print(f"   🔍 Room layout detection checking: '{query_lower[:50]}...'")

    # First check for "within existing" pattern
    existing_template = detect_partition_within_existing_template(query_lower, variables)
    if existing_template:
        return existing_template

    # Parse dimensions first
    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)
    if size_match:
        width = int(size_match.group(1))
        depth = int(size_match.group(2))
        print(f"   📐 Found dimensions: {width}x{depth}")
    else:
        width, depth = 40, 30
        print(f"   📐 Using default dimensions: {width}x{depth}")

    # Check for interior-only mode
    interior_only_triggers = ["interior only", "partition only", "partitions only",
                              "within existing", "inside existing", "interior partitions",
                              "partitions with"]
    interior_only = any(t in query_lower for t in interior_only_triggers)

    rooms = []

    # Method 1: Detailed room list "room layout: entry (40 sqft), ..."
    if "room layout:" in query_lower or "with rooms:" in query_lower:
        print(f"   📋 Trying detailed room parsing...")
        rooms = parse_detailed_rooms(query_lower)
        print(f"   📋 Detailed parsing found {len(rooms)} rooms")

    # Method 2: Simple "X bed Y bath" format
    if not rooms:
        print(f"   📋 Trying smart room generation...")
        rooms = generate_smart_rooms(query_lower, width, depth)
        print(f"   📋 Smart generation found {len(rooms)} rooms")

    if not rooms:
        print(f"   ❌ No rooms detected - template not matched")
        return None

    wall_height = 10.0

    mode_str = "INTERIOR ONLY" if interior_only else "Full"
    print(f"   🎯 Room Layout Template: {width}x{depth}, {len(rooms)} rooms [{mode_str}]")
    for r in rooms:
        print(f"      - {r.get('name', r['type'])}: {r['min_area']} sqft")

    if interior_only:
        plan = build_interior_only_plan(width, depth, rooms, wall_height)
    else:
        plan = build_floor_plan_plan(width, depth, rooms, wall_height)

    return {
        "name": f"{width}x{depth} {'interior partitions' if interior_only else 'room layout'} with {len(rooms)} rooms",
        "plan": plan
    }


def _parse_room_count(query: str, pattern: str) -> int:
    """Parse room count with typo tolerance and word-to-number conversion.

    Handles:
    - Digits: "1 bedroom", "2 bath"
    - Words: "one bedroom", "two bathrooms"
    - Common typos: "i bedroom" (i→1), "l bedroom" (l→1)
    """
    # Skip furniture placement queries - "place a bed" is NOT "1 bedroom"
    furniture_indicators = ['place', 'add', 'put', 'insert', 'drop']
    if any(word in query for word in furniture_indicators):
        return 0

    # Word to number mapping
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
        'a': 1, 'an': 1, 'single': 1,
        # Common typos
        'i': 1, 'l': 1, 'ii': 2, 'll': 2,
    }

    # Try digit match first
    digit_match = re.search(rf'(\d+)\s*{pattern}', query)
    if digit_match:
        return int(digit_match.group(1))

    # Try word match
    word_pattern = rf'(\w+)\s+{pattern}'
    word_match = re.search(word_pattern, query)
    if word_match:
        word = word_match.group(1).lower()
        if word in word_to_num:
            return word_to_num[word]

    # Check if pattern exists without number (assume 1)
    # BUT skip this if the query is about placing/adding furniture (not room layout)
    furniture_indicators = ['place', 'add', 'put', 'insert', 'drop']
    is_furniture_query = any(word in query for word in furniture_indicators)
    
    if not is_furniture_query and re.search(pattern, query):
        # "bedroom" alone means 1 bedroom for layout queries
        return 1

    return 0


def generate_smart_rooms(query_lower: str, width: float, depth: float) -> List[Dict]:
    """Generate room list from simple 'X bed Y bath' style input with smart defaults"""

    # Parse bedroom count with typo tolerance
    bedrooms = _parse_room_count(query_lower, r'(?:bed|bedroom|br)s?')

    # Parse bathroom count with typo tolerance
    bathrooms = _parse_room_count(query_lower, r'(?:bath|bathroom|ba)s?')

    # Report what was parsed
    print(f"   📊 Parsed: {bedrooms} bedroom(s), {bathrooms} bathroom(s)")

    # Must have at least bedrooms or bathrooms mentioned to use this
    if bedrooms == 0 and bathrooms == 0:
        print(f"   ⚠️ No bedroom/bathroom count detected in query")
        return []

    # Calculate total area and allocate rooms proportionally
    total_area = width * depth
    rooms = []

    # === ALWAYS PRESENT: Core rooms ===
    # Entry: ~5% of area, min 30 sqft
    entry_area = max(30, int(total_area * 0.05))
    rooms.append({"type": "entry", "min_area": entry_area})

    # Living: ~20% of area
    living_area = max(120, int(total_area * 0.20))
    rooms.append({"type": "living", "min_area": living_area})

    # Kitchen: ~10% of area
    kitchen_area = max(60, int(total_area * 0.10))
    rooms.append({"type": "kitchen", "min_area": kitchen_area})

    # Dining: ~8% of area (skip for very small units)
    if total_area > 600:
        dining_area = max(50, int(total_area * 0.08))
        rooms.append({"type": "dining", "min_area": dining_area})

    # Hallway: ~5% of area (skip for studios)
    if bedrooms > 0:
        hallway_area = max(30, int(total_area * 0.05))
        rooms.append({"type": "hallway", "min_area": hallway_area})

    # === BEDROOMS ===
    if bedrooms > 0:
        # Primary bedroom: ~15% of area
        primary_area = max(100, int(total_area * 0.15))
        rooms.append({"type": "primary_bedroom", "min_area": primary_area})

        # Additional bedrooms: ~10% each
        for i in range(bedrooms - 1):
            bed_area = max(80, int(total_area * 0.10))
            rooms.append({"type": "bedroom", "min_area": bed_area, "name": f"Bedroom {i+2}"})

    # === BATHROOMS ===
    if bathrooms > 0:
        # Primary bath (if has bedroom): ~5% of area
        if bedrooms > 0:
            bath_area = max(40, int(total_area * 0.05))
            rooms.append({"type": "primary_bath", "min_area": bath_area})
            bathrooms -= 1

        # Additional bathrooms
        for i in range(bathrooms):
            bath_area = max(35, int(total_area * 0.04))
            name = f"Bathroom {i+2}" if bedrooms > 0 else "Bathroom"
            rooms.append({"type": "bathroom", "min_area": bath_area, "name": name})

    # === UTILITY ROOMS ===
    # For small units (<800 sqft): combine laundry with mechanical
    # For larger units: separate laundry
    if total_area < 800:
        # Combined mechanical/laundry
        mech_area = max(25, int(total_area * 0.04))
        rooms.append({"type": "mechanical", "min_area": mech_area, "name": "Utility"})
    else:
        # Separate laundry and mechanical
        laundry_area = max(25, int(total_area * 0.03))
        rooms.append({"type": "laundry", "min_area": laundry_area})
        mech_area = max(20, int(total_area * 0.02))
        rooms.append({"type": "mechanical", "min_area": mech_area})

    # Closets: one per bedroom
    for i in range(bedrooms):
        closet_area = max(15, int(total_area * 0.02))
        rooms.append({"type": "closet", "min_area": closet_area})

    return rooms


def build_interior_only_plan(width: int, depth: int, rooms: List[Dict], wall_height: float) -> List[Dict]:
    """Build execution plan for interior partitions only (within existing geometry)"""
    return [
        # Step 1: Generate interior partition walls
        {
            "tool": "generate_floor_plan_walls",
            "args": {
                "width": width,
                "depth": depth,
                "rooms": rooms,
                "level_name": "${base_level_name}",
                "wall_height": wall_height,
                "exterior_wall_type": "${default_exterior_wall_type}",
                "interior_wall_type": "${default_interior_wall_type}",
                "wet_wall_type": "${default_wet_wall_type}",
                "interior_only": True,
                "origin_x": 0.0,
                "origin_y": 0.0
            }
        },
        # Step 2: Create doors between rooms
        {
            "tool": "create_doors_batch",
            "args": {
                "doors": "${generate_floor_plan_walls_doors}",
                "level_name": "${base_level_name}"
            }
        },
        # Step 3: Auto-dimension the partitions
        {
            "tool": "auto_dimension_walls",
            "args": {
                "level_name": "${base_level_name}",
                "include_interior": True
            }
        }
    ]


def parse_detailed_rooms(query_lower: str) -> List[Dict]:
    """Parse detailed room specifications like 'Entry (50 sqft), Living Room (200 sqft)'"""
    rooms = []

    # Find the room list portion after "room layout:" or "with rooms:"
    room_section = ""
    for marker in ["room layout:", "with rooms:"]:
        if marker in query_lower:
            room_section = query_lower.split(marker, 1)[1]
            break

    if not room_section:
        return rooms

    # Room type mapping (case-insensitive) - includes underscore variants
    type_mapping = {
        'entry': 'entry',
        'living room': 'living', 'living': 'living',
        'dining room': 'dining', 'dining': 'dining',
        'kitchen': 'kitchen',
        'primary bedroom': 'primary_bedroom', 'primary_bedroom': 'primary_bedroom',
        'master bedroom': 'primary_bedroom',
        'bedroom': 'bedroom',
        'bathroom': 'bathroom', 'bath': 'bathroom',
        'primary bath': 'primary_bath', 'primary_bath': 'primary_bath',
        'master bath': 'primary_bath',
        'hallway': 'hallway', 'hall': 'hallway',
        'closet': 'closet',
        'laundry': 'laundry',
        'office': 'office', 'study': 'office',
        'mechanical': 'mechanical', 'utility': 'mechanical',
        'garage': 'garage'
    }

    # Parse each room entry - allow letters, spaces, underscores, and trailing numbers
    # e.g., "entry (40 sqft)", "primary_bedroom (140 sqft)", "Bedroom 2 (100 sqft)"
    pattern = r'([a-z_\s]+\d*)\s*\((\d+)\s*(?:sqft|sq\s*ft|sf)?\)'
    matches = re.findall(pattern, room_section)

    for name_raw, area_str in matches:
        name = name_raw.strip()
        area = int(area_str)

        # Normalize underscores to spaces for lookup, but keep original for type match
        name_normalized = name.replace('_', ' ')
        name_base = re.sub(r'\s*\d+$', '', name_normalized)  # Remove trailing number

        # Find the room type
        room_type = None
        for key, value in type_mapping.items():
            if name_base == key or name == key or name_normalized == key:
                room_type = value
                break

        if room_type:
            room = {"type": room_type, "min_area": area}
            # Add custom name if it's numbered (e.g., "Bedroom 2")
            if re.search(r'\d+$', name):
                room["name"] = name.replace('_', ' ').title()
            rooms.append(room)

    return rooms


def detect_floor_plan_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect and build floor plan template with room layouts"""

    # First check for detailed room layout from UI
    detailed = detect_room_layout_template(query_lower, variables)
    if detailed:
        return detailed

    if "floor plan" not in query_lower:
        return None

    # Must mention rooms to differentiate from view creation
    room_keywords = ["room", "bedroom", "bathroom", "kitchen", "living", "dining",
                     "entry", "laundry", "office", "garage", "mechanical"]
    if not any(r in query_lower for r in room_keywords):
        return None

    # Parse dimensions
    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)
    if size_match:
        width = int(size_match.group(1))
        depth = int(size_match.group(2))
    else:
        width, depth = 40, 30

    rooms = parse_rooms_from_query(query_lower)
    wall_height = 10.0

    print(f"   🎯 Floor Plan Template: {width}x{depth}, {len(rooms)} rooms")

    plan = build_floor_plan_plan(width, depth, rooms, wall_height)

    return {
        "name": f"{width}x{depth} floor plan with {len(rooms)} rooms",
        "plan": plan
    }


def parse_rooms_from_query(query_lower: str) -> List[Dict]:
    """Parse room specifications from natural language"""
    rooms = []
    
    bed_match = re.search(r'(\d+)\s*(?:bed(?:room)?s?)', query_lower)
    bath_match = re.search(r'(\d+)\s*(?:bath(?:room)?s?)', query_lower)
    
    num_beds = int(bed_match.group(1)) if bed_match else 0
    num_baths = int(bath_match.group(1)) if bath_match else 0
    
    rooms.append({"type": "entry", "min_area": 50})
    
    if "living" in query_lower or num_beds > 0:
        rooms.append({"type": "living", "min_area": 200})
    
    if "kitchen" in query_lower or num_beds > 0:
        rooms.append({"type": "kitchen", "min_area": 120})
    
    if "dining" in query_lower:
        rooms.append({"type": "dining", "min_area": 100})
    
    if num_beds > 0:
        rooms.append({"type": "primary_bedroom", "min_area": 180})
        for i in range(1, num_beds):
            rooms.append({"type": "bedroom", "min_area": 120, "name": f"Bedroom {i+1}"})
    elif "bedroom" in query_lower:
        rooms.append({"type": "primary_bedroom", "min_area": 180})
    
    if num_baths > 0:
        for _ in range(num_baths):
            rooms.append({"type": "bathroom", "min_area": 50})
    elif "bath" in query_lower:
        rooms.append({"type": "bathroom", "min_area": 50})
    
    if "laundry" in query_lower:
        rooms.append({"type": "laundry", "min_area": 40})
    if "mechanical" in query_lower:
        rooms.append({"type": "mechanical", "min_area": 35})
    
    return rooms


def build_floor_plan_plan(width: int, depth: int, rooms: List[Dict], wall_height: float) -> List[Dict]:
    """Build execution plan for floor plan with rooms"""
    return [
        {
            "tool": "create_levels_batch",
            "args": {
                "levels": [
                    {"name": "Level 1", "elevation": 0.0},
                    {"name": "Top of Wall", "elevation": wall_height}
                ]
            }
        },
        {
            "tool": "generate_floor_plan_walls",
            "args": {
                "width": width,
                "depth": depth,
                "rooms": rooms,
                "level_name": "Level 1",
                "wall_height": wall_height,
                "exterior_wall_type": "${default_exterior_wall_type}",
                "interior_wall_type": "${default_interior_wall_type}",
                "wet_wall_type": "${default_wet_wall_type}"
            }
        },
        {
            "tool": "create_floor",
            "args": {
                "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
                "level_name": "Level 1"
            }
        },
        {
            "tool": "create_roof_footprint",
            "args": {
                "points": [[0, 0, 0], [width, 0, 0], [width, depth, 0], [0, depth, 0]],
                "level_name": "Top of Wall",
                "slope_degrees": 0.0
            }
        },
        # Step 5: Create doors from layout
        {
            "tool": "create_doors_batch",
            "args": {
                "doors": "${generate_floor_plan_walls_doors}",
                "level_name": "Level 1"
            }
        },
        # Step 6: Create floor plan view
        {
            "tool": "create_floor_plan",
            "args": {
                "level_name": "Level 1",
                "view_name": "Level 1 - Floor Plan"
            }
        },
        # Step 7: Auto-dimension everything
        {
            "tool": "auto_dimension_all",
            "args": {
                "level_name": "Level 1"
            }
        }
    ]


def detect_tagging_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """
    Detects requests like "Tag everything on Level 0" or "Annotate Ground Floor".
    Now checks for existing tags to avoid duplicates.
    """
    triggers = ["tag", "annotate", "label"]
    if not any(t in query_lower for t in triggers):
        return None

    # Don't trigger on "dimension" - that's a different template
    if "dimension" in query_lower and "tag" not in query_lower:
        return None

    # 1. Extract Level Name (Defaults to 'Level 0' if not found)
    level_name = "Level 0"
    # Simple regex to catch "Level 1", "Ground Floor", etc.
    match = re.search(r'(?:on|for)\s+(?:level\s+)?["\']?([^"\']+)', query_lower)
    if match:
        level_name = match.group(1).strip().title()

    # 2. Check for specific element types to tag
    tag_walls = "wall" in query_lower or "all" in query_lower or not any(x in query_lower for x in ["door", "window", "room"])
    tag_doors = "door" in query_lower or "all" in query_lower
    tag_windows = "window" in query_lower or "all" in query_lower
    tag_rooms = "room" in query_lower or "all" in query_lower

    # 3. Check for "force" or "retag" to skip existing check
    force_retag = any(x in query_lower for x in ["force", "retag", "again", "redo"])

    print(f"   🎯 Template Detected: Auto-Tagging for {level_name}")
    print(f"      Walls: {tag_walls}, Doors: {tag_doors}, Windows: {tag_windows}, Rooms: {tag_rooms}")
    print(f"      Skip existing tags: {not force_retag}")

    plan = [
        # STEP 1: Find the Floor Plan View
        {
            "step": 1,
            "tool": "list_views",
            "description": f"Find floor plan view for {level_name}",
            "args": {
                "level_name": level_name,
                "view_type": "FloorPlan"
            },
            "extract": "views"
        },
        # STEP 2: Get existing tags in this view (to avoid duplicates)
        {
            "step": 2,
            "tool": "list_elements",
            "description": "Get existing tags to check for duplicates",
            "args": {
                "category_name": "Tags",
                "view_id": "${view_0_id}"
            },
            "extract": "existing_tags"
        },
    ]

    step_num = 3

    # STEP 3+: Get element IDs for each category
    if tag_walls:
        plan.append({
            "step": step_num,
            "tool": "list_wall_ids",
            "description": "Get wall IDs to tag",
            "args": {"level_name": level_name},
            "extract": "wall_ids"
        })
        step_num += 1

    if tag_doors:
        plan.append({
            "step": step_num,
            "tool": "list_door_ids",
            "description": "Get door IDs to tag",
            "args": {"level_name": level_name},
            "extract": "door_ids"
        })
        step_num += 1

    if tag_windows:
        plan.append({
            "step": step_num,
            "tool": "list_window_ids",
            "description": "Get window IDs to tag",
            "args": {"level_name": level_name},
            "extract": "window_ids"
        })
        step_num += 1

    if tag_rooms:
        plan.append({
            "step": step_num,
            "tool": "list_elements",
            "description": "Get room IDs to tag",
            "args": {
                "category_name": "Rooms",
                "level_name": level_name
            },
            "extract": "room_ids"
        })
        step_num += 1

    # STEP N: Execute batch tagging with skip_existing flag
    if tag_walls:
        plan.append({
            "step": step_num,
            "tool": "create_tags_batch",
            "description": "Tag walls",
            "args": {
                "view_id": "${view_0_id}",
                "element_ids": "${all_wall_ids}",
                "tag_orientation": "Horizontal",
                "skip_existing": not force_retag,
                "existing_tags": "${existing_tags}"
            }
        })
        step_num += 1

    if tag_doors:
        plan.append({
            "step": step_num,
            "tool": "create_tags_batch",
            "description": "Tag doors",
            "args": {
                "view_id": "${view_0_id}",
                "element_ids": "${all_door_ids}",
                "tag_orientation": "Horizontal",
                "skip_existing": not force_retag,
                "existing_tags": "${existing_tags}"
            }
        })
        step_num += 1

    if tag_windows:
        plan.append({
            "step": step_num,
            "tool": "create_tags_batch",
            "description": "Tag windows",
            "args": {
                "view_id": "${view_0_id}",
                "element_ids": "${all_window_ids}",
                "tag_orientation": "Horizontal",
                "skip_existing": not force_retag,
                "existing_tags": "${existing_tags}"
            }
        })
        step_num += 1

    if tag_rooms:
        plan.append({
            "step": step_num,
            "tool": "create_tags_batch",
            "description": "Tag rooms",
            "args": {
                "view_id": "${view_0_id}",
                "element_ids": "${all_room_ids}",
                "tag_orientation": "Horizontal",
                "tag_type": "Room Tag",
                "skip_existing": not force_retag,
                "existing_tags": "${existing_tags}"
            }
        })

    elements_to_tag = []
    if tag_walls: elements_to_tag.append("walls")
    if tag_doors: elements_to_tag.append("doors")
    if tag_windows: elements_to_tag.append("windows")
    if tag_rooms: elements_to_tag.append("rooms")

    return {
        "name": f"Auto-Tag {', '.join(elements_to_tag)} on {level_name}",
        "plan": plan,
        "skip_existing": not force_retag
    }

# =============================================================================
# TEMPLATE 2: ANNOTATION / FLOOR PLAN DOCUMENTATION
# =============================================================================

def detect_annotation_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect and build annotation/documentation template for floor plans.

    NOTE: This is a catch-all template. More specific triggers are handled by:
    - detect_cd_set_template: "cd set", "construction documents", "drawing set"
    - detect_tagging_template: "tag", "label"
    - detect_dimension_template: "dimension", "dim", "measure"
    """

    # More specific triggers to avoid overlap with tagging template
    doc_triggers = ["document floor", "floor plan documentation", "annotate floor",
                    "document level", "document the floor", "annotate the floor"]
    has_doc_trigger = any(t in query_lower for t in doc_triggers)

    # Also catch generic "document" but only if combined with level/floor context
    if not has_doc_trigger:
        if "document" in query_lower and ("level" in query_lower or "floor" in query_lower):
            has_doc_trigger = True

    if not has_doc_trigger:
        return None
    
    # Extract level name
    level_match = re.search(r'(?:for|on|of)\s+(?:level\s+)?["\']?([^"\']+)["\']?', query_lower)
    if level_match:
        level_name = level_match.group(1).strip().title()
    else:
        level_name = "Ground Floor"
    
    print(f"   🎯 Annotation Template: Floor plan for '{level_name}'")
    
    plan = build_annotation_plan(level_name)
    
    return {
        "name": f"Floor plan documentation for {level_name}",
        "plan": plan
    }


def build_annotation_plan(level_name: str) -> List[Dict]:
    """Build the execution plan for floor plan documentation"""

    plan = []

    # Step 1: Create floor plan view
    plan.append({
        "tool": "create_floor_plan",
        "args": {
            "level_name": level_name,
            "view_name": f"{level_name} - Annotated"
        }
    })

    # Step 2: Auto-dimension all walls, rooms, and openings
    plan.append({
        "tool": "auto_dimension_all",
        "args": {
            "level_name": level_name
        }
    })

    # Step 3: Tag all rooms
    plan.append({
        "tool": "tag_elements_batch",
        "args": {
            "category": "Rooms",
            "level_name": level_name,
            "view_id": "${last_create_floor_plan_id}"
        }
    })

    # Step 4: Tag all doors
    plan.append({
        "tool": "tag_elements_batch",
        "args": {
            "category": "Doors",
            "level_name": level_name,
            "view_id": "${last_create_floor_plan_id}"
        }
    })

    # Step 5: Create a sheet
    plan.append({
        "tool": "create_sheet",
        "args": {
            "name": f"{level_name} Floor Plan",
            "number": "A101"
        }
    })

    # Step 6: Place view on sheet (centered)
    plan.append({
        "tool": "place_view_on_sheet",
        "args": {
            "sheet_id": "${last_create_sheet_id}",
            "view_id": "${last_create_floor_plan_id}",
            "point": [1.5, 1.0, 0]
        }
    })

    return plan


# =============================================================================
# TEMPLATE 3: DIMENSIONS
# =============================================================================

def detect_dimension_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect and build dimension template with proper architectural dimensioning"""

    dim_triggers = ["dimension", "dim", "measure"]
    if not any(t in query_lower for t in dim_triggers):
        return None

    # Extract level name or default to lowest
    level_name = None  # Will use ${base_level_name} from discovery
    level_match = re.search(r'(?:level|on)\s+(\d+)', query_lower, re.IGNORECASE)
    if level_match:
        level_name = f"Level {level_match.group(1)}"

    # Check what to dimension
    dim_walls = "wall" in query_lower or "all" in query_lower or not any(x in query_lower for x in ["room", "opening", "door", "window"])
    dim_rooms = "room" in query_lower or "all" in query_lower
    dim_openings = any(x in query_lower for x in ["opening", "door", "window"]) or "all" in query_lower

    print(f"   🎯 Dimension Template: level={level_name or 'base'}, walls={dim_walls}, rooms={dim_rooms}, openings={dim_openings}")

    # Build plan based on what user wants to dimension
    plan = []

    if dim_walls and dim_rooms and dim_openings:
        # Full dimensioning - use auto_dimension_all
        plan.append({
            "tool": "auto_dimension_all",
            "args": {
                "level_name": level_name or "${base_level_name}"
            }
        })
    else:
        # Selective dimensioning
        if dim_walls:
            plan.append({
                "tool": "auto_dimension_walls",
                "args": {
                    "level_name": level_name or "${base_level_name}",
                    "include_interior": True
                }
            })
        if dim_rooms:
            plan.append({
                "tool": "auto_dimension_rooms",
                "args": {
                    "level_name": level_name or "${base_level_name}"
                }
            })
        if dim_openings:
            plan.append({
                "tool": "auto_dimension_openings",
                "args": {
                    "level_name": level_name or "${base_level_name}"
                }
            })

    return {
        "name": f"Architectural dimensions for {level_name or 'base level'}",
        "plan": plan
    }


def detect_status_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect status/info queries"""

    status_triggers = ["status", "info", "model info", "revit status", "connection", "health", "check"]

    if any(t in query_lower for t in status_triggers):
        print(f"   🎯 Status Template: Revit connection check")
        return {
            "name": "Revit Status Check",
            "plan": [
                {"tool": "get_revit_status", "args": {}}
            ]
        }

    return None


# =============================================================================
# HELP / TOOL DISCOVERY TEMPLATE
# =============================================================================

def detect_help_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect help/capabilities queries"""

    help_triggers = ["what can you do", "list tools", "available tools", "help",
                     "capabilities", "what tools", "show tools", "list commands",
                     "available commands", "what commands"]

    if any(t in query_lower for t in help_triggers):
        print(f"   🎯 Help Template: Tool Discovery")
        return {
            "name": "Tool Discovery",
            "display_in_chat": True,
            "plan": [
                {"tool": "list_available_tools", "args": {}}
            ]
        }

    return None


# =============================================================================
# MODEL CONFIGURATION TEMPLATE
# =============================================================================

def detect_model_config_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect model configuration queries"""

    # Show current config
    if any(t in query_lower for t in ["show models", "model config", "model configuration",
                                       "configured models", "vision models", "list models"]):
        print(f"   🎯 Model Config Template: Show Configuration")
        return {
            "name": "Show Model Configuration",
            "display_in_chat": True,
            "plan": [
                {"tool": "configure_models", "args": {"mode": "show"}}
            ]
        }

    # Test models
    if any(t in query_lower for t in ["test models", "check models", "model status",
                                       "are models online", "model health"]):
        print(f"   🎯 Model Config Template: Test Models")
        return {
            "name": "Test Model Endpoints",
            "display_in_chat": True,
            "plan": [
                {"tool": "configure_models", "args": {"mode": "test"}}
            ]
        }

    # LM Studio auto-detect
    if any(t in query_lower for t in ["detect lm studio", "lm studio", "auto detect models",
                                       "find models", "discover models", "detect models"]):
        print(f"   🎯 Model Config Template: LM Studio Auto-Detect")
        return {
            "name": "Auto-Detect LM Studio Models",
            "display_in_chat": True,
            "plan": [
                {"tool": "configure_models", "args": {"mode": "lmstudio"}}
            ]
        }

    # Scan for model servers
    if any(t in query_lower for t in ["scan for models", "scan ports", "find servers"]):
        print(f"   🎯 Model Config Template: Scan Ports")
        return {
            "name": "Scan for Model Servers",
            "display_in_chat": True,
            "plan": [
                {"tool": "configure_models", "args": {"mode": "scan"}}
            ]
        }

    # Configure models - needs input
    if any(t in query_lower for t in ["configure models", "setup models", "set models",
                                       "model setup", "configure vision"]):
        print(f"   🎯 Model Config Template: Configure Models")

        # Check if using same server pattern
        if "same server" in query_lower or "single server" in query_lower:
            return {
                "name": "Configure Models (Same Server)",
                "needs_input": True,
                "question": "Please provide the server details:",
                "inputs": [
                    {"name": "api_url", "prompt": "Server URL (e.g., http://localhost:1234)"},
                    {"name": "vision_model", "prompt": "Vision model ID (e.g., qwen-3-vl-4b)"},
                    {"name": "text_model", "prompt": "Text model ID (e.g., qwen-0.5b)"}
                ],
                "plan": []  # Will be built after input
            }

        return {
            "name": "Model Configuration",
            "needs_input": True,
            "question": "How would you like to configure the models?",
            "options": [
                "Same server for all models (easiest)",
                "Show current configuration",
                "Test model endpoints",
                "Reset to defaults"
            ],
            "plan": []
        }

    return None


# =============================================================================
# FAMILY FROM PHOTO TEMPLATE
# =============================================================================

def detect_family_from_photo_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """
    Detect requests to create a Revit family from an image/photo.
    Routes to the photo-to-family workflow.
    """
    has_image_keyword = any(t in query_lower for t in [
        "image", "photo", "picture", "photograph"
    ])
    has_family_keyword = any(t in query_lower for t in [
        "family", "component", "furniture", "object", "element"
    ])
    has_create_keyword = any(t in query_lower for t in [
        "create", "make", "build", "generate", "from"
    ])

    if has_image_keyword and has_family_keyword and has_create_keyword:
        # Check if we have an uploaded image
        has_image = variables and variables.get("uploaded_image")

        if not has_image:
            print(f"   [!] Family-from-photo template matched but no image uploaded")
            return None

        print(f"   [OK] Family-from-Photo Template: Creating family from image")

        return {
            "name": "Family from Photo",
            "plan": [
                {
                    "tool": "create_family_from_photo",
                    "args": {
                        "image_base64": "${uploaded_image}",
                        "family_name": "PhotoFamily",
                        "category": "Generic Models",
                        "object_hint": None
                    }
                }
            ]
        }

    return None


# =============================================================================
# SKETCH TO WALLS TEMPLATE (Vision Processing)
# =============================================================================

def detect_sketch_to_walls_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """
    Detect requests to create walls from a sketch/image.
    Triggers the vision processor to analyze the image.
    """
    # Exclude family-related queries - those go to family-from-photo template
    if any(t in query_lower for t in ["family", "component", "furniture", "object"]):
        return None

    # Check for sketch/image + walls keywords
    has_image_keyword = any(t in query_lower for t in [
        "sketch", "image", "drawing", "photo", "picture", "draw", "traced"
    ])
    has_wall_keyword = any(t in query_lower for t in [
        "wall", "layout", "floor plan", "floorplan", "outline", "boundary"
    ])
    has_create_keyword = any(t in query_lower for t in [
        "create", "make", "build", "generate", "from", "trace"
    ])

    if has_image_keyword and (has_wall_keyword or has_create_keyword):
        # Check if we have an uploaded image
        has_image = variables and variables.get("uploaded_image")

        if not has_image:
            print(f"   [!] Sketch template matched but no image uploaded")
            return None

        print(f"   [OK] Sketch-to-Walls Template: Processing image with vision model")

        # Extract target area if mentioned
        target_area = 500  # Default
        import re
        area_match = re.search(r'(\d+)\s*(?:sq\s*ft|sqft|square feet)', query_lower)
        if area_match:
            target_area = int(area_match.group(1))

        return {
            "name": "Sketch to Walls (Vision Processing)",
            "plan": [
                {
                    "tool": "generate_layout_from_image",
                    "args": {
                        "image_base64": "${uploaded_image}",
                        "target_area": target_area
                    }
                }
            ],
            "display_in_chat": True,
        }

    return None


# =============================================================================
# CONSTRUCTION DETAIL TEMPLATES
# =============================================================================

def detect_detail_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect construction detail and assembly queries"""

    # List assemblies
    if any(t in query_lower for t in ["list assemblies", "available assemblies",
                                       "show assemblies", "construction assemblies",
                                       "wall assemblies", "assembly types"]):
        print(f"   🎯 Detail Template: List Assemblies")
        return {
            "name": "List Construction Assemblies",
            "plan": [{"tool": "list_construction_assemblies", "args": {}}],
            "display_in_chat": True,
        }

    # Explosion view
    if any(t in query_lower for t in ["explosion view", "explode wall", "exploded view",
                                       "show layers", "layer breakdown", "explode assembly"]):
        # Try to detect which assembly
        assembly_key = None
        if "exterior" in query_lower or "ext" in query_lower:
            assembly_key = "ext_wall_2x6"
        elif "interior" in query_lower or "int" in query_lower or "partition" in query_lower:
            assembly_key = "int_wall_2x4"
        elif "floor" in query_lower:
            assembly_key = "floor_wood"
        elif "roof" in query_lower:
            assembly_key = "roof_shingle"

        if assembly_key:
            print(f"   🎯 Detail Template: Explosion View - {assembly_key}")
            return {
                "name": f"Assembly Explosion View - {assembly_key}",
                "plan": [{
                    "tool": "create_explosion_view",
                    "args": {
                        "assembly_key": assembly_key,
                        "start_point": [0, 0, 0],
                        "end_point": [10, 0, 0],
                        "height": 10.0,
                        "separation": 0.5
                    }
                }],
                "display_in_chat": True,
            }
        else:
            print(f"   🎯 Detail Template: Explosion View - needs input")
            return {
                "name": "Assembly Explosion View",
                "needs_input": True,
                "question": "Which assembly would you like to explode?",
                "options": [
                    "Exterior Wall (2x6 frame with rain screen)",
                    "Interior Partition (2x4 frame)",
                    "Wood Floor Assembly",
                    "Shingle Roof Assembly"
                ],
                "plan": [],
            }

    # Section detail
    if any(t in query_lower for t in ["section detail", "wall section", "assembly detail",
                                       "construction detail", "detail section"]):
        assembly_key = None
        if "exterior" in query_lower or "ext" in query_lower:
            assembly_key = "ext_wall_2x6"
        elif "interior" in query_lower or "int" in query_lower:
            assembly_key = "int_wall_2x4"
        elif "floor" in query_lower:
            assembly_key = "floor_wood"
        elif "roof" in query_lower:
            assembly_key = "roof_shingle"

        if assembly_key:
            print(f"   🎯 Detail Template: Section Detail - {assembly_key}")
            return {
                "name": f"Section Detail - {assembly_key}",
                "plan": [{
                    "tool": "generate_section_detail",
                    "args": {
                        "assembly_key": assembly_key,
                        "include_dimensions": True,
                        "include_labels": True
                    }
                }],
                "display_in_chat": True,
            }
        else:
            print(f"   🎯 Detail Template: Section Detail - needs input")
            return {
                "name": "Generate Section Detail",
                "needs_input": True,
                "question": "Which assembly do you want a section detail for?",
                "options": [
                    "Exterior Wall (2x6 frame)",
                    "Interior Partition (2x4)",
                    "Wood Floor",
                    "Shingle Roof"
                ],
                "plan": [],
            }

    # Assembly info
    if "assembly info" in query_lower or ("info" in query_lower and "assembly" in query_lower):
        print(f"   🎯 Detail Template: Assembly Info")
        return {
            "name": "Assembly Information",
            "needs_input": True,
            "question": "Which assembly do you want information about?",
            "options": [
                "ext_wall_2x6 - Exterior 2x6 Frame",
                "int_wall_2x4 - Interior Partition",
                "floor_wood - Wood Floor",
                "roof_shingle - Shingle Roof"
            ],
            "plan": [],
        }

    # Create assembly wall
    if any(t in query_lower for t in ["assembly wall", "detailed wall", "layered wall",
                                       "wall with layers", "construction wall"]):
        print(f"   🎯 Detail Template: Create Assembly Wall")
        return {
            "name": "Create Assembly Wall",
            "needs_input": True,
            "question": "Which wall assembly type?",
            "options": [
                "Exterior Wall (2x6 frame with rain screen)",
                "Interior Partition (2x4 frame)"
            ],
            "plan": [],
        }

    return None


# =============================================================================
# ENHANCED WINDOW GEOMETRY TEMPLATE
# =============================================================================

def detect_window_geometry_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for detailed window geometry - more comprehensive than basic discovery"""

    # More specific triggers than basic window discovery
    triggers = ["window geometry", "window details", "detailed windows",
                "window sill", "window head", "window heights",
                "window dimensions for", "measure windows"]

    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Enhanced Window Geometry Template")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get all walls to identify host walls",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "list_window_ids",
            "description": "Get all window IDs",
            "args": {},
            "extract": "window_ids"
        },
        {
            "step": 3,
            "tool": "list_elements",
            "description": "Get detailed window data including geometry",
            "args": {
                "category_name": "Windows",
                "include_geometry": True
            },
            "extract": "window_geometry"
        },
        {
            "step": 4,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate building bounds for reference",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        }
    ]

    return {
        "name": "Enhanced Window Geometry Discovery",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# ELEVATION DIMENSIONING TEMPLATE
# =============================================================================

def detect_elevation_dimension_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for elevation/vertical dimensioning.

    NOTE: Uses specific triggers to avoid overlap with general dimension template.
    "vertical dimensions" removed as too generic - use "elevation dims" instead.
    """

    triggers = ["dimension elevation", "elevation dims", "dimension the elevation",
                "elevation dimension", "dim elevation", "add elevation dims",
                "dims on elevation", "dimension north", "dimension south",
                "dimension east", "dimension west"]

    if not any(t in query_lower for t in triggers):
        return None

    # Try to extract which elevation from query
    elevation = None
    for direction in ["north", "south", "east", "west"]:
        if direction in query_lower:
            elevation = direction.title()
            break

    if not elevation:
        # Return a "needs_input" response to ask user
        print(f"   🎯 Elevation Dimension Template - needs user input")
        return {
            "name": "Elevation Dimensioning",
            "needs_input": True,
            "question": "Which elevation would you like to dimension?",
            "options": ["North", "South", "East", "West", "All"],
            "plan": []  # Plan will be built after user selection
        }

    print(f"   🎯 Elevation Dimension Template: {elevation}")
    return build_elevation_dimension_plan(elevation)


def build_elevation_dimension_plan(elevation: str) -> Dict:
    """Build the execution plan for elevation dimensioning"""

    # Determine view name pattern based on elevation
    view_name_pattern = f"{elevation}" if elevation != "All" else ""

    plan = [
        {
            "step": 1,
            "tool": "list_views",
            "description": f"Find {elevation} elevation view(s)",
            "args": {
                "view_type": "Elevation"
            },
            "extract": "elevation_views"
        },
        {
            "step": 2,
            "tool": "list_levels",
            "description": "Get all levels for floor-to-floor dimensions",
            "args": {},
            "extract": "levels_data"
        },
        {
            "step": 3,
            "tool": "list_elements",
            "description": "Get windows for sill/head dimensions",
            "args": {
                "category_name": "Windows"
            },
            "extract": "window_elements"
        },
        {
            "step": 4,
            "tool": "list_elements",
            "description": "Get doors for head dimensions",
            "args": {
                "category_name": "Doors"
            },
            "extract": "door_elements"
        }
    ]

    # Add dimension creation steps
    # Floor-to-floor dimensions using levels
    plan.append({
        "step": 5,
        "tool": "create_dimensions_batch",
        "description": "Create floor-to-floor vertical dimensions",
        "args": {
            "view_id": "${elevation_view_0_id}",
            "element_ids": "${level_ids}",
            "dimension_type": "vertical",
            "offset": -3.0  # Offset left of building
        }
    })

    return {
        "name": f"Elevation Dimensioning - {elevation}",
        "plan": plan,
        "elevation": elevation
    }

def build_dimension_plan_for_house(width: float, depth: float, variables: Dict) -> List[Dict]:
    """
    Build dimension plan for a rectangular house with known geometry.
    
    Wall layout (from house template):
    - Wall 0: South (0,0) to (width,0) - horizontal
    - Wall 1: East (width,0) to (width,depth) - vertical  
    - Wall 2: North (width,depth) to (0,depth) - horizontal
    - Wall 3: West (0,depth) to (0,0) - vertical
    
    Dimension strategy:
    - South side: Detail dim (all walls) + Overall dim
    - West side: Detail dim (all walls) + Overall dim
    """
    
    plan = []
    offset = 5.0  # Offset from building in feet
    
    # Step 1: Create floor plan view
    plan.append({
        "tool": "create_floor_plan",
        "args": {
            "level_name": "Ground Floor",
            "view_name": "Ground Floor - Dimensions"
        }
    })
    
    # Step 2: Horizontal dimensions (along X axis, below south wall)
    # Detail dimension - all vertical walls (west and east)
    plan.append({
        "tool": "create_dimension",
        "args": {
            "element_ids": [
            "${wall_3_id}",
            # Spread operator equivalent - these will be flattened
            "${all_door_ids}",
            "${all_window_ids}",
            "${wall_1_id}"
        ],
        "start_point": [0, -offset, 0],
        "end_point": [100, -offset, 0],
        "view_id": "${view_0_id}"
        }
    })
    
    # Overall dimension - same walls but further offset
    plan.append({
        "tool": "create_dimension",
        "args": {
            "element_ids": ["${wall_batch_0_wall_3}", "${wall_batch_0_wall_1}"],
            "start_point": [0, -offset * 2, 0],
            "end_point": [width, -offset * 2, 0],
            "view_id": "${last_create_floor_plan_id}"
        }
    })
    
    # Step 3: Vertical dimensions (along Y axis, left of west wall)
    # Detail dimension - all horizontal walls (south and north)
    plan.append({
        "tool": "create_dimension",
        "args": {
            "element_ids": ["${wall_batch_0_wall_0}", "${wall_batch_0_wall_2}"],
            "start_point": [-offset, 0, 0],
            "end_point": [-offset, depth, 0],
            "view_id": "${last_create_floor_plan_id}"
        }
    })
    
    # Overall dimension - same walls but further offset
    plan.append({
        "tool": "create_dimension",
        "args": {
            "element_ids": ["${wall_batch_0_wall_0}", "${wall_batch_0_wall_2}"],
            "start_point": [-offset * 2, 0, 0],
            "end_point": [-offset * 2, depth, 0],
            "view_id": "${last_create_floor_plan_id}"
        }
    })
    
    return plan


# =============================================================================
# DIMENSION CALCULATION HELPERS
# =============================================================================

class DimensionCalculator:
    """
    Calculates dimension line positions for walls.
    
    Logic:
    - Group walls by orientation (horizontal vs vertical)
    - For each group, create dimension lines perpendicular to walls
    - Line 1 (Detail): Through centers of ALL walls in group
    - Line 2 (Overall): Between outermost walls only
    """
    
    def __init__(self, walls: List[Dict]):
        """
        Args:
            walls: List of wall data with 'id', 'start_point', 'end_point'
        """
        self.walls = walls
        self.horizontal_walls = []  # Walls running along X axis
        self.vertical_walls = []    # Walls running along Y axis
        self._classify_walls()
    
    def _classify_walls(self):
        """Classify walls as horizontal or vertical"""
        for wall in self.walls:
            start = wall.get('start_point', [0, 0, 0])
            end = wall.get('end_point', [0, 0, 0])
            
            dx = abs(end[0] - start[0])
            dy = abs(end[1] - start[1])
            
            # Calculate center
            center_x = (start[0] + end[0]) / 2
            center_y = (start[1] + end[1]) / 2
            
            wall_data = {
                'id': wall.get('id'),
                'start': start,
                'end': end,
                'center': [center_x, center_y, 0],
                'length': max(dx, dy)
            }
            
            if dx > dy:
                # Horizontal wall (runs along X)
                wall_data['y_pos'] = start[1]  # Y position for sorting
                self.horizontal_walls.append(wall_data)
            else:
                # Vertical wall (runs along Y)
                wall_data['x_pos'] = start[0]  # X position for sorting
                self.vertical_walls.append(wall_data)
    
    def get_horizontal_dimensions(self, offset: float = 3.0) -> List[Dict]:
        """
        Get dimension data for horizontal walls.
        Dimension line runs vertically (perpendicular to walls).
        
        Args:
            offset: Distance from outermost wall to dimension line (in feet)
        
        Returns:
            List of dimension definitions
        """
        if len(self.horizontal_walls) < 2:
            return []
        
        # Sort by Y position
        sorted_walls = sorted(self.horizontal_walls, key=lambda w: w['y_pos'])
        
        # Get X range (for dimension line length)
        all_x = []
        for wall in sorted_walls:
            all_x.extend([wall['start'][0], wall['end'][0]])
        min_x = min(all_x)
        max_x = max(all_x)
        mid_x = (min_x + max_x) / 2
        
        # Outermost Y positions
        min_y = sorted_walls[0]['y_pos']
        max_y = sorted_walls[-1]['y_pos']
        
        dimensions = []
        
        # Detail dimension: All wall centers
        # Dimension line below the bottom wall
        dim_line_y = min_y - offset
        
        detail_refs = [wall['id'] for wall in sorted_walls]
        dimensions.append({
            "type": "detail",
            "description": "All horizontal wall centers",
            "element_ids": detail_refs,
            "start_point": [mid_x, dim_line_y, 0],
            "end_point": [mid_x, max_y + offset, 0],
            "reference_points": [wall['center'] for wall in sorted_walls]
        })
        
        # Overall dimension: Outer walls only
        # Dimension line further below
        overall_line_y = min_y - (offset * 2)
        
        dimensions.append({
            "type": "overall",
            "description": "Overall depth (outer walls)",
            "element_ids": [sorted_walls[0]['id'], sorted_walls[-1]['id']],
            "start_point": [mid_x, overall_line_y, 0],
            "end_point": [mid_x, max_y + offset, 0],
            "reference_points": [sorted_walls[0]['center'], sorted_walls[-1]['center']]
        })
        
        return dimensions
    
    def get_vertical_dimensions(self, offset: float = 3.0) -> List[Dict]:
        """
        Get dimension data for vertical walls.
        Dimension line runs horizontally (perpendicular to walls).
        
        Args:
            offset: Distance from outermost wall to dimension line (in feet)
        
        Returns:
            List of dimension definitions
        """
        if len(self.vertical_walls) < 2:
            return []
        
        # Sort by X position
        sorted_walls = sorted(self.vertical_walls, key=lambda w: w['x_pos'])
        
        # Get Y range (for dimension line length)
        all_y = []
        for wall in sorted_walls:
            all_y.extend([wall['start'][1], wall['end'][1]])
        min_y = min(all_y)
        max_y = max(all_y)
        mid_y = (min_y + max_y) / 2
        
        # Outermost X positions
        min_x = sorted_walls[0]['x_pos']
        max_x = sorted_walls[-1]['x_pos']
        
        dimensions = []
        
        # Detail dimension: All wall centers
        # Dimension line to the left of the leftmost wall
        dim_line_x = min_x - offset
        
        detail_refs = [wall['id'] for wall in sorted_walls]
        dimensions.append({
            "type": "detail",
            "description": "All vertical wall centers",
            "element_ids": detail_refs,
            "start_point": [dim_line_x, mid_y, 0],
            "end_point": [max_x + offset, mid_y, 0],
            "reference_points": [wall['center'] for wall in sorted_walls]
        })
        
        # Overall dimension: Outer walls only
        # Dimension line further to the left
        overall_line_x = min_x - (offset * 2)
        
        dimensions.append({
            "type": "overall",
            "description": "Overall width (outer walls)",
            "element_ids": [sorted_walls[0]['id'], sorted_walls[-1]['id']],
            "start_point": [overall_line_x, mid_y, 0],
            "end_point": [max_x + offset, mid_y, 0],
            "reference_points": [sorted_walls[0]['center'], sorted_walls[-1]['center']]
        })
        
        return dimensions
    
    def get_all_dimensions(self, offset: float = 3.0) -> Dict[str, List[Dict]]:
        """Get all dimension data organized by direction"""
        return {
            "horizontal": self.get_horizontal_dimensions(offset),
            "vertical": self.get_vertical_dimensions(offset)
        }


def calculate_dimension_plan_from_walls(walls: List[Dict], view_id: str = None) -> List[Dict]:
    """
    Given a list of walls with geometry, calculate and return dimension tool calls.
    
    Args:
        walls: List of wall dicts with 'id', 'start_point', 'end_point'
        view_id: Optional view ID to place dimensions in
    
    Returns:
        List of tool call dicts for create_dimension
    """
    calc = DimensionCalculator(walls)
    all_dims = calc.get_all_dimensions(offset=3.0)
    
    plan = []
    
    # Create dimensions for horizontal walls (dimension line runs vertically)
    for dim in all_dims["horizontal"]:
        plan.append({
            "tool": "create_dimension",
            "args": {
                "element_ids": dim["element_ids"],
                "start_point": dim["start_point"],
                "end_point": dim["end_point"],
                "view_id": view_id
            }
        })
    
    # Create dimensions for vertical walls (dimension line runs horizontally)
    for dim in all_dims["vertical"]:
        plan.append({
            "tool": "create_dimension",
            "args": {
                "element_ids": dim["element_ids"],
                "start_point": dim["start_point"],
                "end_point": dim["end_point"],
                "view_id": view_id
            }
        })
    
    return plan


# =============================================================================
# SCHEDULE TEMPLATES
# =============================================================================

def detect_material_schedule_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create a material schedule/takeoff"""

    triggers = ["material schedule", "material takeoff", "materials list", "material quantities",
                "list materials", "materials schedule"]
    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Material Schedule Template")

    plan = [
        {
            "step": 1,
            "tool": "create_schedule",
            "description": "Create material schedule",
            "args": {
                "category_name": "Materials",
                "name": "Material Takeoff"
            },
            "extract": "schedule_id"
        },
        {
            "step": 2,
            "tool": "add_schedule_fields",
            "description": "Add material fields",
            "args": {
                "schedule_id": "${schedule_id}",
                "parameter_names": ["Name", "Description", "Area", "Volume", "Cost"]
            }
        },
        {
            "step": 3,
            "tool": "set_schedule_sorting",
            "description": "Sort by material name",
            "args": {
                "schedule_id": "${schedule_id}",
                "field_name": "Name",
                "ascending": True
            }
        },
        {
            "step": 4,
            "tool": "get_schedule_data",
            "description": "Get schedule data",
            "args": {
                "schedule_id": "${schedule_id}"
            }
        }
    ]

    return {
        "name": "Material Schedule/Takeoff",
        "plan": plan,
        "display_in_chat": True
    }


def detect_opening_schedule_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create door/window schedules"""

    triggers = ["door schedule", "window schedule", "opening schedule",
                "doors and windows schedule", "openings schedule"]
    if not any(t in query_lower for t in triggers):
        return None

    # Determine which type(s) of schedule to create
    include_doors = "door" in query_lower or "opening" in query_lower
    include_windows = "window" in query_lower or "opening" in query_lower

    print(f"   🎯 Opening Schedule Template: doors={include_doors}, windows={include_windows}")

    plan = []
    step_num = 1

    if include_doors:
        plan.extend([
            {
                "step": step_num,
                "tool": "create_schedule",
                "description": "Create door schedule",
                "args": {
                    "category_name": "Doors",
                    "name": "Door Schedule"
                },
                "extract": "door_schedule_id"
            },
            {
                "step": step_num + 1,
                "tool": "add_schedule_fields",
                "description": "Add door fields",
                "args": {
                    "schedule_id": "${door_schedule_id}",
                    "parameter_names": ["Mark", "Type", "Width", "Height", "Level", "Frame Type", "Fire Rating"]
                }
            },
            {
                "step": step_num + 2,
                "tool": "set_schedule_grouping",
                "description": "Group doors by level",
                "args": {
                    "schedule_id": "${door_schedule_id}",
                    "field_name": "Level",
                    "show_header": True
                }
            },
            {
                "step": step_num + 3,
                "tool": "set_schedule_sorting",
                "description": "Sort doors by mark",
                "args": {
                    "schedule_id": "${door_schedule_id}",
                    "field_name": "Mark",
                    "ascending": True
                }
            }
        ])
        step_num += 4

    if include_windows:
        plan.extend([
            {
                "step": step_num,
                "tool": "create_schedule",
                "description": "Create window schedule",
                "args": {
                    "category_name": "Windows",
                    "name": "Window Schedule"
                },
                "extract": "window_schedule_id"
            },
            {
                "step": step_num + 1,
                "tool": "add_schedule_fields",
                "description": "Add window fields",
                "args": {
                    "schedule_id": "${window_schedule_id}",
                    "parameter_names": ["Mark", "Type", "Width", "Height", "Sill Height", "Level", "Glazing"]
                }
            },
            {
                "step": step_num + 2,
                "tool": "set_schedule_grouping",
                "description": "Group windows by level",
                "args": {
                    "schedule_id": "${window_schedule_id}",
                    "field_name": "Level",
                    "show_header": True
                }
            },
            {
                "step": step_num + 3,
                "tool": "set_schedule_sorting",
                "description": "Sort windows by mark",
                "args": {
                    "schedule_id": "${window_schedule_id}",
                    "field_name": "Mark",
                    "ascending": True
                }
            }
        ])

    schedule_types = []
    if include_doors:
        schedule_types.append("Door")
    if include_windows:
        schedule_types.append("Window")

    return {
        "name": f"{' & '.join(schedule_types)} Schedule",
        "plan": plan,
        "display_in_chat": True
    }


def detect_room_finish_schedule_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create a room finish schedule"""

    triggers = ["finish schedule", "room finishes", "room finish schedule",
                "finishes schedule", "finish legend"]
    if not any(t in query_lower for t in triggers):
        return None

    print(f"   🎯 Room Finish Schedule Template")

    plan = [
        {
            "step": 1,
            "tool": "create_schedule",
            "description": "Create room finish schedule",
            "args": {
                "category_name": "Rooms",
                "name": "Room Finish Schedule"
            },
            "extract": "schedule_id"
        },
        {
            "step": 2,
            "tool": "add_schedule_fields",
            "description": "Add finish fields",
            "args": {
                "schedule_id": "${schedule_id}",
                "parameter_names": ["Number", "Name", "Level", "Floor Finish", "Wall Finish",
                                   "Ceiling Finish", "Base Finish", "Area"]
            }
        },
        {
            "step": 3,
            "tool": "set_schedule_grouping",
            "description": "Group by level",
            "args": {
                "schedule_id": "${schedule_id}",
                "field_name": "Level",
                "show_header": True,
                "show_footer": True
            }
        },
        {
            "step": 4,
            "tool": "set_schedule_sorting",
            "description": "Sort by room number",
            "args": {
                "schedule_id": "${schedule_id}",
                "field_name": "Number",
                "ascending": True
            }
        },
        {
            "step": 5,
            "tool": "get_schedule_data",
            "description": "Get schedule data",
            "args": {
                "schedule_id": "${schedule_id}"
            }
        }
    ]

    return {
        "name": "Room Finish Schedule",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# INTERIOR FIT-OUT TEMPLATE
# =============================================================================

def detect_interior_fitout_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to fit out an existing shell with interior partitions"""

    triggers = ["fit out", "fit-out", "fitout", "partition interior",
                "subdivide shell", "interior fit", "add partitions to"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse bedroom/bathroom count
    bed_match = re.search(r'(\d+)\s*(?:bed|bedroom|br)', query_lower)
    bath_match = re.search(r'(\d+)\s*(?:bath|bathroom|ba)', query_lower)

    bedrooms = int(bed_match.group(1)) if bed_match else 2
    bathrooms = int(bath_match.group(1)) if bath_match else 1

    print(f"   🎯 Interior Fit-Out Template: {bedrooms} bed, {bathrooms} bath")

    plan = [
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get existing perimeter walls",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate available interior space",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        },
        {
            "step": 3,
            "tool": "generate_floor_plan_walls",
            "description": "Generate interior partitions",
            "args": {
                "width": "${bounds.width}",
                "depth": "${bounds.depth}",
                "rooms": [
                    {"type": "entry", "min_area": 40},
                    {"type": "living", "min_area": 180},
                    {"type": "kitchen", "min_area": 100},
                    {"type": "primary_bedroom", "min_area": 140},
                ] + [{"type": "bedroom", "min_area": 100, "name": f"Bedroom {i+2}"} for i in range(bedrooms - 1)]
                  + [{"type": "primary_bath", "min_area": 50}]
                  + [{"type": "bathroom", "min_area": 40, "name": f"Bath {i+2}"} for i in range(bathrooms - 1)]
                  + [{"type": "hallway", "min_area": 30}],
                "level_name": "${base_level_name}",
                "wall_height": 10.0,
                "interior_wall_type": "${default_interior_wall_type}",
                "wet_wall_type": "${default_wet_wall_type}",
                "interior_only": True,
                "origin_x": "${bounds.min_x}",
                "origin_y": "${bounds.min_y}"
            },
            "extract": "partition_result"
        },
        {
            "step": 4,
            "tool": "create_doors_batch",
            "description": "Place interior doors",
            "args": {
                "doors": "${generate_floor_plan_walls_doors}",
                "level_name": "${base_level_name}"
            }
        },
        {
            "step": 5,
            "tool": "create_floor_plan",
            "description": "Create floor plan view",
            "args": {
                "level_name": "${base_level_name}",
                "view_name": "Interior Fit-Out Plan"
            }
        },
        {
            "step": 6,
            "tool": "auto_dimension_all",
            "description": "Dimension the layout",
            "args": {
                "level_name": "${base_level_name}"
            }
        }
    ]

    return {
        "name": f"Interior Fit-Out: {bedrooms} bed {bathrooms} bath",
        "plan": plan
    }


# =============================================================================
# CONSTRUCTION DOCUMENT SET TEMPLATE
# =============================================================================

def detect_cd_set_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create a full construction document set"""

    triggers = ["cd set", "construction documents", "drawing set", "documentation package",
                "full documentation", "complete drawings", "drawing package"]
    if not any(t in query_lower for t in triggers):
        return None

    # Check for level name
    level_name = "Level 1"
    level_match = re.search(r'(?:for|on)\s+(?:level\s+)?["\']?([^"\']+)["\']?', query_lower)
    if level_match:
        level_name = level_match.group(1).strip().title()

    print(f"   🎯 Construction Document Set Template: Level = {level_name}")

    plan = [
        # Step 1: Discover existing geometry
        {
            "step": 1,
            "tool": "list_walls",
            "description": "Get existing walls for grid placement",
            "args": {},
            "extract": "walls_data"
        },
        {
            "step": 2,
            "tool": "analyze_geometry_bounds",
            "description": "Calculate building bounds",
            "args": {
                "walls": "${walls_data}"
            },
            "extract": "bounds"
        },
        # Step 3: Create floor plan view
        {
            "step": 3,
            "tool": "create_floor_plan",
            "description": "Create annotated floor plan",
            "args": {
                "level_name": level_name,
                "view_name": f"{level_name} - Floor Plan"
            },
            "extract": "floor_plan_view"
        },
        # Step 4-7: Create 4 elevations
        {
            "step": 4,
            "tool": "create_elevation",
            "description": "Create North elevation",
            "args": {
                "point": ["${bounds.center_x}", "${bounds.max_y}", 0],
                "view_name": "North Elevation",
                "scale": 48
            },
            "extract": "north_elev"
        },
        {
            "step": 5,
            "tool": "create_elevation",
            "description": "Create South elevation",
            "args": {
                "point": ["${bounds.center_x}", "${bounds.min_y}", 0],
                "view_name": "South Elevation",
                "scale": 48
            },
            "extract": "south_elev"
        },
        {
            "step": 6,
            "tool": "create_elevation",
            "description": "Create East elevation",
            "args": {
                "point": ["${bounds.max_x}", "${bounds.center_y}", 0],
                "view_name": "East Elevation",
                "scale": 48
            },
            "extract": "east_elev"
        },
        {
            "step": 7,
            "tool": "create_elevation",
            "description": "Create West elevation",
            "args": {
                "point": ["${bounds.min_x}", "${bounds.center_y}", 0],
                "view_name": "West Elevation",
                "scale": 48
            },
            "extract": "west_elev"
        },
        # Step 8-9: Create sections
        {
            "step": 8,
            "tool": "create_section",
            "description": "Create longitudinal section",
            "args": {
                "start_point": ["${bounds.min_x}", "${bounds.center_y}", 0],
                "end_point": ["${bounds.max_x}", "${bounds.center_y}", 0],
                "height": 15.0,
                "view_name": "Section A-A"
            },
            "extract": "section_a"
        },
        {
            "step": 9,
            "tool": "create_section",
            "description": "Create transverse section",
            "args": {
                "start_point": ["${bounds.center_x}", "${bounds.min_y}", 0],
                "end_point": ["${bounds.center_x}", "${bounds.max_y}", 0],
                "height": 15.0,
                "view_name": "Section B-B"
            },
            "extract": "section_b"
        },
        # Step 10: Create grid lines
        {
            "step": 10,
            "tool": "create_grids_batch",
            "description": "Create structural grids",
            "args": {
                "grids": [
                    {"start_point": ["${bounds.min_x}", "${bounds.min_y}", 0],
                     "end_point": ["${bounds.min_x}", "${bounds.max_y}", 0], "name": "1"},
                    {"start_point": ["${bounds.max_x}", "${bounds.min_y}", 0],
                     "end_point": ["${bounds.max_x}", "${bounds.max_y}", 0], "name": "2"},
                    {"start_point": ["${bounds.min_x}", "${bounds.min_y}", 0],
                     "end_point": ["${bounds.max_x}", "${bounds.min_y}", 0], "name": "A"},
                    {"start_point": ["${bounds.min_x}", "${bounds.max_y}", 0],
                     "end_point": ["${bounds.max_x}", "${bounds.max_y}", 0], "name": "B"}
                ]
            }
        },
        # Step 11: Dimension the floor plan
        {
            "step": 11,
            "tool": "auto_dimension_all",
            "description": "Add dimensions to floor plan",
            "args": {
                "level_name": level_name
            }
        },
        # Step 12: Create sheets
        {
            "step": 12,
            "tool": "create_sheets_batch",
            "description": "Create drawing sheets",
            "args": {
                "sheets": [
                    {"name": "Floor Plan", "number": "A101"},
                    {"name": "Elevations", "number": "A201"},
                    {"name": "Sections", "number": "A301"}
                ]
            },
            "extract": "sheets"
        },
        # Step 13: Place views on sheets
        {
            "step": 13,
            "tool": "place_views_batch",
            "description": "Place views on sheets",
            "args": {
                "placements": [
                    {"sheet_id": "${sheet_0_id}", "view_id": "${floor_plan_view_id}", "point": [1.5, 1.0, 0]},
                    {"sheet_id": "${sheet_1_id}", "view_id": "${north_elev_id}", "point": [0.8, 1.5, 0]},
                    {"sheet_id": "${sheet_1_id}", "view_id": "${south_elev_id}", "point": [2.2, 1.5, 0]},
                    {"sheet_id": "${sheet_1_id}", "view_id": "${east_elev_id}", "point": [0.8, 0.5, 0]},
                    {"sheet_id": "${sheet_1_id}", "view_id": "${west_elev_id}", "point": [2.2, 0.5, 0]},
                    {"sheet_id": "${sheet_2_id}", "view_id": "${section_a_id}", "point": [1.5, 1.5, 0]},
                    {"sheet_id": "${sheet_2_id}", "view_id": "${section_b_id}", "point": [1.5, 0.5, 0]}
                ]
            }
        }
    ]

    return {
        "name": "Construction Document Set",
        "plan": plan
    }


# =============================================================================
# STRUCTURAL ANALYSIS TEMPLATE
# =============================================================================

def detect_structural_analysis_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for structural analysis"""

    triggers = ["structural analysis", "analyze structure", "frame analysis",
                "check structure", "structural check", "beam check", "column check",
                "analyze framing"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse specific parameters if provided
    span_ft = 12.0
    span_match = re.search(r'(\d+)\s*(?:\'|ft|foot|feet)\s*span', query_lower)
    if span_match:
        span_ft = float(span_match.group(1))

    trib_width = 8.0
    trib_match = re.search(r'(\d+)\s*(?:\'|ft|foot|feet)\s*(?:tributary|trib)', query_lower)
    if trib_match:
        trib_width = float(trib_match.group(1))

    print(f"   🎯 Structural Analysis Template: span={span_ft}', trib={trib_width}'")

    plan = [
        {
            "step": 1,
            "tool": "list_assembly_presets",
            "description": "Get available structural assemblies",
            "args": {},
            "extract": "presets"
        },
        {
            "step": 2,
            "tool": "analyze_beam",
            "description": "Analyze floor/roof beam",
            "args": {
                "span_ft": span_ft,
                "tributary_width_ft": trib_width,
                "dead_load_psf": 15.0,
                "live_load_psf": 40.0,
                "material": "wood_spf",
                "depth_in": 9.25,
                "width_in": 3.5
            },
            "extract": "beam_analysis"
        },
        {
            "step": 3,
            "tool": "analyze_column",
            "description": "Analyze support column",
            "args": {
                "height_ft": 9.0,
                "axial_load_lbs": 8000,
                "material": "wood_spf",
                "depth_in": 5.5,
                "width_in": 5.5
            },
            "extract": "column_analysis"
        },
        {
            "step": 4,
            "tool": "estimate_fasteners",
            "description": "Estimate fastener requirements for walls",
            "args": {
                "assembly_type": "wall",
                "length_ft": 40.0,
                "height_ft": 9.0
            },
            "extract": "wall_fasteners"
        },
        {
            "step": 5,
            "tool": "estimate_fasteners",
            "description": "Estimate fastener requirements for floor",
            "args": {
                "assembly_type": "floor",
                "length_ft": 40.0,
                "width_ft": 30.0
            },
            "extract": "floor_fasteners"
        }
    ]

    return {
        "name": "Structural Analysis",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# THERMAL ANALYSIS TEMPLATE
# =============================================================================

def detect_thermal_analysis_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for thermal/energy analysis"""

    triggers = ["thermal analysis", "heat loss", "r-value", "thermal performance",
                "envelope analysis", "energy analysis", "thermal check", "insulation check"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse climate zone if provided
    climate_zone = 5  # Default to zone 5 (cold climate)
    zone_match = re.search(r'(?:zone|climate)\s*(\d)', query_lower)
    if zone_match:
        climate_zone = int(zone_match.group(1))

    # Detect which assembly to analyze
    assembly = "ext_wall_2x6"  # Default
    if "floor" in query_lower:
        assembly = "floor_wood"
    elif "roof" in query_lower:
        assembly = "roof_shingle"
    elif "interior" in query_lower or "partition" in query_lower:
        assembly = "int_wall_2x4"

    print(f"   🎯 Thermal Analysis Template: zone={climate_zone}, assembly={assembly}")

    plan = [
        {
            "step": 1,
            "tool": "list_assembly_presets",
            "description": "Get available assemblies",
            "args": {},
            "extract": "presets"
        },
        {
            "step": 2,
            "tool": "get_assembly_details",
            "description": "Get assembly layer details",
            "args": {
                "assembly_name": assembly
            },
            "extract": "assembly_details"
        },
        {
            "step": 3,
            "tool": "analyze_thermal_assembly",
            "description": "Analyze thermal performance",
            "args": {
                "assembly_name": assembly,
                "interior_temp_f": 70.0,
                "exterior_temp_f": 0.0,
                "relative_humidity_pct": 40.0
            },
            "extract": "thermal_analysis"
        },
        {
            "step": 4,
            "tool": "calculate_heat_loss",
            "description": "Calculate whole-building heat loss",
            "args": {
                "climate_zone": climate_zone,
                "floor_area_sqft": 1200.0,
                "wall_area_sqft": 800.0,
                "roof_area_sqft": 1200.0,
                "window_area_sqft": 150.0,
                "volume_cuft": 10800.0,
                "wall_r_value": 21.0,
                "roof_r_value": 38.0,
                "window_type": "double_pane_low_e"
            },
            "extract": "heat_loss"
        }
    ]

    return {
        "name": f"Thermal Analysis - {assembly}",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# LIGHTING ANALYSIS TEMPLATE
# =============================================================================

def detect_lighting_analysis_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for daylighting and electric lighting analysis"""

    triggers = ["lighting analysis", "daylight analysis", "daylighting", "light levels",
                "electric lighting", "lighting design", "illumination", "lux levels"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse room parameters if provided
    room_width = 20.0
    room_depth = 15.0
    room_height = 9.0

    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)
    if size_match:
        room_width = float(size_match.group(1))
        room_depth = float(size_match.group(2))

    height_match = re.search(r'(\d+)\s*(?:\'|ft|foot|feet)\s*(?:tall|high|ceiling)', query_lower)
    if height_match:
        room_height = float(height_match.group(1))

    # Detect room type for target lux
    target_lux = 300  # Default office
    if any(t in query_lower for t in ["office", "work"]):
        target_lux = 500
    elif any(t in query_lower for t in ["living", "lounge", "residential"]):
        target_lux = 300
    elif any(t in query_lower for t in ["kitchen", "task"]):
        target_lux = 500
    elif any(t in query_lower for t in ["bedroom", "sleep"]):
        target_lux = 150
    elif any(t in query_lower for t in ["corridor", "hallway"]):
        target_lux = 100

    print(f"   🎯 Lighting Analysis Template: {room_width}x{room_depth}, target={target_lux} lux")

    plan = [
        {
            "step": 1,
            "tool": "analyze_daylighting",
            "description": "Analyze natural daylight levels",
            "args": {
                "room_width_ft": room_width,
                "room_depth_ft": room_depth,
                "room_height_ft": room_height,
                "window_area_sqft": room_width * 3,  # Assume 3ft high windows across width
                "window_orientation": "south",
                "glazing_vlt": 0.7
            },
            "extract": "daylight_analysis"
        },
        {
            "step": 2,
            "tool": "calculate_electric_lighting",
            "description": "Calculate supplemental electric lighting needs",
            "args": {
                "room_area_sqft": room_width * room_depth,
                "target_lux": target_lux,
                "daylight_factor": "${daylight_analysis.daylight_factor}",
                "fixture_type": "LED_panel",
                "mounting_height_ft": room_height - 0.5
            },
            "extract": "electric_lighting"
        }
    ]

    return {
        "name": f"Lighting Analysis - {room_width}x{room_depth} room",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# ACOUSTIC ANALYSIS TEMPLATE
# =============================================================================

def detect_acoustic_analysis_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for acoustic/sound analysis"""

    triggers = ["acoustic analysis", "acoustics", "sound analysis", "stc rating",
                "reverberation", "reverb time", "noise control", "sound isolation",
                "acoustic design", "rt60"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse room parameters if provided
    room_volume = 3000.0  # Default cubic feet

    size_match = re.search(r'(\d+)\s*(?:x|by|×)\s*(\d+)', query_lower)
    if size_match:
        width = float(size_match.group(1))
        depth = float(size_match.group(2))
        room_volume = width * depth * 9.0  # Assume 9ft ceiling

    # Detect room type for target RT
    room_type = "office"
    if any(t in query_lower for t in ["theater", "auditorium", "concert"]):
        room_type = "theater"
    elif any(t in query_lower for t in ["classroom", "lecture"]):
        room_type = "classroom"
    elif any(t in query_lower for t in ["studio", "recording"]):
        room_type = "studio"
    elif any(t in query_lower for t in ["restaurant", "dining"]):
        room_type = "restaurant"

    # Detect wall assembly for STC
    wall_assembly = "int_wall_2x4"
    if "exterior" in query_lower:
        wall_assembly = "ext_wall_2x6"
    elif "party" in query_lower or "demising" in query_lower:
        wall_assembly = "party_wall"

    print(f"   🎯 Acoustic Analysis Template: {room_type}, volume={room_volume} cuft")

    plan = [
        {
            "step": 1,
            "tool": "analyze_wall_stc",
            "description": "Analyze wall sound transmission class",
            "args": {
                "assembly_name": wall_assembly
            },
            "extract": "stc_analysis"
        },
        {
            "step": 2,
            "tool": "calculate_reverberation_time",
            "description": "Calculate room reverberation time (RT60)",
            "args": {
                "room_volume_cuft": room_volume,
                "room_type": room_type,
                "surface_materials": {
                    "floor": "carpet",
                    "ceiling": "acoustic_tile",
                    "walls": "gypsum"
                }
            },
            "extract": "reverb_analysis"
        },
        {
            "step": 3,
            "tool": "list_materials",
            "description": "Get available acoustic materials",
            "args": {
                "category": "acoustic"
            },
            "extract": "acoustic_materials"
        }
    ]

    return {
        "name": f"Acoustic Analysis - {room_type}",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# ROOM CREATION TEMPLATE
# =============================================================================

def detect_room_creation_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to create rooms with separation lines"""

    triggers = ["create rooms", "add rooms", "place rooms", "room creation",
                "define rooms", "room boundaries", "room separation"]
    if not any(t in query_lower for t in triggers):
        return None

    # Check for level name
    level_name = "${base_level_name}"
    level_match = re.search(r'(?:on|for|at)\s+(?:level\s+)?["\']?([^"\']+)["\']?', query_lower)
    if level_match:
        level_name = level_match.group(1).strip().title()

    # Parse room count if specified
    room_count = 1
    count_match = re.search(r'(\d+)\s*rooms?', query_lower)
    if count_match:
        room_count = int(count_match.group(1))

    # Check if automatic room detection is requested
    auto_detect = any(t in query_lower for t in ["auto", "automatic", "detect", "find"])

    print(f"   🎯 Room Creation Template: {room_count} rooms on {level_name}, auto={auto_detect}")

    if auto_detect:
        # Auto-detect rooms from enclosed areas
        plan = [
            {
                "step": 1,
                "tool": "list_walls",
                "description": "Get walls to find enclosed areas",
                "args": {
                    "level_name": level_name
                },
                "extract": "walls_data"
            },
            {
                "step": 2,
                "tool": "analyze_geometry_bounds",
                "description": "Analyze building geometry",
                "args": {
                    "walls": "${walls_data}"
                },
                "extract": "bounds"
            },
            {
                "step": 3,
                "tool": "create_rooms_batch",
                "description": "Create rooms in enclosed areas",
                "args": {
                    "level_name": level_name,
                    "auto_detect": True
                },
                "extract": "rooms_created"
            },
            {
                "step": 4,
                "tool": "create_floor_plan",
                "description": "Create floor plan view",
                "args": {
                    "level_name": level_name,
                    "view_name": f"{level_name} - Rooms"
                }
            }
        ]
    else:
        # Manual room placement with separation lines
        plan = [
            {
                "step": 1,
                "tool": "list_walls",
                "description": "Get existing walls",
                "args": {
                    "level_name": level_name
                },
                "extract": "walls_data"
            },
            {
                "step": 2,
                "tool": "analyze_geometry_bounds",
                "description": "Analyze building bounds",
                "args": {
                    "walls": "${walls_data}"
                },
                "extract": "bounds"
            },
            {
                "step": 3,
                "tool": "create_room_separation_lines",
                "description": "Create room separation lines where needed",
                "args": {
                    "level_name": level_name,
                    "bounds": "${bounds}"
                },
                "extract": "separation_lines"
            },
            {
                "step": 4,
                "tool": "create_rooms_batch",
                "description": "Place rooms",
                "args": {
                    "level_name": level_name,
                    "count": room_count
                },
                "extract": "rooms_created"
            },
            {
                "step": 5,
                "tool": "create_floor_plan",
                "description": "Create floor plan view",
                "args": {
                    "level_name": level_name,
                    "view_name": f"{level_name} - Rooms"
                }
            }
        ]

    return {
        "name": f"Room Creation - {room_count} room(s)",
        "plan": plan
    }


# =============================================================================
# TYPE DISCOVERY TEMPLATE
# =============================================================================

def detect_type_discovery_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests to discover/list available element types"""

    triggers = ["list types", "available types", "show types", "what types",
                "type discovery", "find types", "get types", "all types"]
    if not any(t in query_lower for t in triggers):
        return None

    # Determine which categories to list
    list_walls = "wall" in query_lower or "all" in query_lower
    list_doors = "door" in query_lower or "all" in query_lower
    list_windows = "window" in query_lower or "all" in query_lower
    list_floors = "floor" in query_lower or "all" in query_lower
    list_ceilings = "ceiling" in query_lower or "all" in query_lower
    list_roofs = "roof" in query_lower or "all" in query_lower
    list_furniture = "furniture" in query_lower

    # If no specific category, list common ones
    if not any([list_walls, list_doors, list_windows, list_floors, list_ceilings, list_roofs, list_furniture]):
        list_walls = list_doors = list_windows = True

    print(f"   🎯 Type Discovery Template: walls={list_walls}, doors={list_doors}, windows={list_windows}")

    plan = []
    step_num = 1

    if list_walls:
        plan.append({
            "step": step_num,
            "tool": "list_wall_types",
            "description": "Get available wall types",
            "args": {},
            "extract": "wall_types"
        })
        step_num += 1

    if list_doors:
        plan.append({
            "step": step_num,
            "tool": "list_door_types",
            "description": "Get available door types",
            "args": {},
            "extract": "door_types"
        })
        step_num += 1

    if list_windows:
        plan.append({
            "step": step_num,
            "tool": "list_window_types",
            "description": "Get available window types",
            "args": {},
            "extract": "window_types"
        })
        step_num += 1

    if list_floors:
        plan.append({
            "step": step_num,
            "tool": "list_floor_types",
            "description": "Get available floor types",
            "args": {},
            "extract": "floor_types"
        })
        step_num += 1

    if list_ceilings:
        plan.append({
            "step": step_num,
            "tool": "list_ceiling_types",
            "description": "Get available ceiling types",
            "args": {},
            "extract": "ceiling_types"
        })
        step_num += 1

    if list_roofs:
        plan.append({
            "step": step_num,
            "tool": "list_roof_types",
            "description": "Get available roof types",
            "args": {},
            "extract": "roof_types"
        })
        step_num += 1

    if list_furniture:
        plan.append({
            "step": step_num,
            "tool": "list_furniture_types",
            "description": "Get available furniture types",
            "args": {},
            "extract": "furniture_types"
        })
        step_num += 1

    categories = []
    if list_walls: categories.append("Wall")
    if list_doors: categories.append("Door")
    if list_windows: categories.append("Window")
    if list_floors: categories.append("Floor")
    if list_ceilings: categories.append("Ceiling")
    if list_roofs: categories.append("Roof")
    if list_furniture: categories.append("Furniture")

    return {
        "name": f"Type Discovery - {', '.join(categories)}",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# RENDER PIPELINE TEMPLATE
# =============================================================================

def detect_render_pipeline_template(query_lower: str, variables: Dict = None) -> Optional[Dict]:
    """Detect requests for AI-enhanced rendering pipeline"""

    triggers = ["render pipeline", "extract channels", "ai render", "enhance view",
                "channel extraction", "channel render", "ai visualization"]
    if not any(t in query_lower for t in triggers):
        return None

    # Parse render parameters
    prompt = "Photorealistic architectural visualization with warm lighting"
    if "night" in query_lower:
        prompt = "Night view with dramatic lighting and interior glow"
    elif "sunset" in query_lower or "dusk" in query_lower:
        prompt = "Golden hour sunset with warm tones and long shadows"
    elif "sketch" in query_lower or "artistic" in query_lower:
        prompt = "Architectural sketch style with pencil rendering"

    print(f"   🎯 Render Pipeline Template: prompt='{prompt[:40]}...'")

    plan = [
        {
            "step": 1,
            "tool": "list_views",
            "description": "Find 3D views for rendering",
            "args": {
                "view_type": "ThreeD"
            },
            "extract": "views"
        },
        {
            "step": 2,
            "tool": "render_channels_from_view",
            "description": "Export view and extract render channels",
            "args": {
                "view_id": "${view_0_id}",
                "output_dir": "./render_output",
                "channels": ["depth", "normals", "material_id", "edges"],
                "resolution_width": 1920,
                "resolution_height": 1080
            },
            "extract": "channels"
        },
        {
            "step": 3,
            "tool": "enhance_render",
            "description": "AI-enhance the render",
            "args": {
                "depth_path": "${channels.depth}",
                "material_path": "${channels.material_id}",
                "prompt": prompt,
                "output_path": "./render_output/enhanced.png",
                "strength": 0.8,
                "steps": 30
            },
            "extract": "enhanced"
        }
    ]

    return {
        "name": "AI Render Pipeline",
        "plan": plan,
        "display_in_chat": True
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_template_names() -> List[str]:
    """Return list of available template names for help/discovery"""
    return [
        # === SCHEDULES ===
        "Material Schedule (e.g., 'material schedule', 'material takeoff')",
        "Door/Window Schedule (e.g., 'door schedule', 'window schedule', 'opening schedule')",
        "Room Finish Schedule (e.g., 'finish schedule', 'room finishes')",

        # === ANALYSIS ===
        "Structural Analysis (e.g., 'structural analysis', 'frame analysis', 'beam check')",
        "Thermal Analysis (e.g., 'thermal analysis', 'heat loss', 'r-value analysis')",
        "Lighting Analysis (e.g., 'lighting analysis', 'daylighting', 'lux levels')",
        "Acoustic Analysis (e.g., 'acoustic analysis', 'stc rating', 'reverberation')",

        # === TYPE DISCOVERY ===
        "Type Discovery (e.g., 'list types', 'available wall types', 'show door types')",

        # === ROOM CREATION ===
        "Room Creation (e.g., 'create rooms', 'add rooms', 'room boundaries')",

        # === RENDERING ===
        "AI Render Pipeline (e.g., 'render pipeline', 'ai render', 'extract channels')",

        # === DOCUMENTATION ===
        "Construction Document Set (e.g., 'cd set', 'construction documents', 'drawing set')",
        "Floor Plan Documentation (e.g., 'document floor plan for Ground Floor')",

        # === GEOMETRY CREATION ===
        "House/Room (e.g., 'create a 40x40 house')",
        "Room Layout (e.g., '35x25 2 bed 1 bath')",
        "Interior Fit-Out (e.g., 'fit out 2 bed 1 bath', 'partition interior')",
        "Foundation (e.g., 'create foundation', 'add footing')",

        # === DISCOVERY ===
        "Geometry Discovery (e.g., 'analyze existing geometry', 'find building footprint')",
        "Window Geometry (e.g., 'window geometry', 'window sill heights')",
        "Window Discovery (e.g., 'find windows', 'window locations')",
        "Door Discovery (e.g., 'find doors', 'door locations')",

        # === ANNOTATION ===
        "Dimensions (e.g., 'dimension the walls', 'dimension all')",
        "Elevation Dimensions (e.g., 'dimension north elevation', 'elevation dims')",
        "Tagging (e.g., 'tag everything', 'tag walls on Level 0')",

        # === CONSTRUCTION DETAILS ===
        "List Assemblies (e.g., 'list assemblies', 'show construction assemblies')",
        "Explosion View (e.g., 'explode exterior wall', 'show layers')",
        "Section Detail (e.g., 'wall section detail', 'construction detail')",
        "Assembly Info (e.g., 'assembly info', 'wall assembly details')",

        # === UTILITIES ===
        "Help/Tools (e.g., 'what can you do', 'list tools', 'help')",
    ]