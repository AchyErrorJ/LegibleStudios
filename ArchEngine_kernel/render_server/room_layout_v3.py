"""
Room Layout Generator v3
========================
Simplified, template-based room layout system that integrates with:
- QBD (Question Based Design) workflow
- Multi-model vision processing
- Direct LLM-guided placement

Design Philosophy:
- Template-first: Use pre-built layouts for common configurations
- Fallback to constraint solver only when templates don't fit
- Integration with sketch input for guided refinement
- Simple, predictable, fast

Key Improvements over v2:
1. Pre-built templates for studio, 1BR, 2BR, 3BR, 4BR
2. Sketch-guided mode: Vision output guides room placement
3. QBD integration: Interview answers map to templates
4. Simpler constraint system
5. Better performance (no deep backtracking)
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# ROOM TEMPLATES
# =============================================================================

@dataclass
class RoomTemplate:
    """A pre-defined room within a layout template"""
    name: str
    room_type: str
    x_ratio: float  # Position as ratio of total width (0.0 - 1.0)
    y_ratio: float  # Position as ratio of total depth (0.0 - 1.0)
    width_ratio: float  # Width as ratio
    depth_ratio: float  # Depth as ratio
    is_exterior: bool = False
    is_wet: bool = False


@dataclass
class LayoutTemplate:
    """A complete floor plan template"""
    name: str
    description: str
    min_width: float  # Minimum footprint width (ft)
    min_depth: float  # Minimum footprint depth (ft)
    ideal_ratio: float  # Ideal width/depth ratio
    rooms: List[RoomTemplate]
    bedroom_count: int
    bathroom_count: int
    total_sqft_range: Tuple[float, float]  # Min/max recommended sqft


# Pre-built templates for common residential layouts
LAYOUT_TEMPLATES = {
    "studio": LayoutTemplate(
        name="Studio",
        description="Open-plan studio apartment",
        min_width=20, min_depth=24,
        ideal_ratio=0.83,
        bedroom_count=0,
        bathroom_count=1,
        total_sqft_range=(350, 550),
        rooms=[
            # Living/Sleeping area (60% of space)
            RoomTemplate("Living Area", "living", 0.0, 0.35, 0.7, 0.65, is_exterior=True),
            # Kitchen (open to living)
            RoomTemplate("Kitchen", "kitchen", 0.7, 0.35, 0.3, 0.65, is_exterior=True, is_wet=True),
            # Bathroom
            RoomTemplate("Bathroom", "bathroom", 0.7, 0.0, 0.3, 0.35, is_wet=True),
            # Entry/Closet
            RoomTemplate("Entry", "entry", 0.0, 0.0, 0.4, 0.35, is_exterior=True),
            RoomTemplate("Closet", "closet", 0.4, 0.0, 0.3, 0.35),
        ]
    ),

    "1br": LayoutTemplate(
        name="One Bedroom",
        description="Separate bedroom apartment",
        min_width=28, min_depth=30,
        ideal_ratio=0.93,
        bedroom_count=1,
        bathroom_count=1,
        total_sqft_range=(550, 800),
        rooms=[
            # Entry
            RoomTemplate("Entry", "entry", 0.0, 0.0, 0.2, 0.25, is_exterior=True),
            # Living Room
            RoomTemplate("Living Room", "living", 0.0, 0.25, 0.5, 0.45, is_exterior=True),
            # Dining/Kitchen
            RoomTemplate("Kitchen", "kitchen", 0.2, 0.0, 0.4, 0.25, is_wet=True),
            RoomTemplate("Dining", "dining", 0.5, 0.25, 0.25, 0.45),
            # Bedroom
            RoomTemplate("Bedroom", "bedroom", 0.0, 0.7, 0.5, 0.3, is_exterior=True),
            # Bathroom
            RoomTemplate("Bathroom", "bathroom", 0.6, 0.0, 0.25, 0.25, is_wet=True),
            # Closet
            RoomTemplate("Closet", "closet", 0.5, 0.7, 0.25, 0.3),
            # Hallway
            RoomTemplate("Hallway", "hallway", 0.75, 0.25, 0.25, 0.75),
        ]
    ),

    "2br": LayoutTemplate(
        name="Two Bedroom",
        description="Two bedroom home/apartment",
        min_width=35, min_depth=35,
        ideal_ratio=1.0,
        bedroom_count=2,
        bathroom_count=1,
        total_sqft_range=(800, 1200),
        rooms=[
            # PUBLIC ZONE (bottom half)
            RoomTemplate("Entry", "entry", 0.0, 0.0, 0.15, 0.2, is_exterior=True),
            RoomTemplate("Living Room", "living", 0.0, 0.2, 0.45, 0.35, is_exterior=True),
            RoomTemplate("Dining", "dining", 0.15, 0.0, 0.3, 0.2),
            RoomTemplate("Kitchen", "kitchen", 0.45, 0.0, 0.35, 0.35, is_wet=True),

            # PRIVATE ZONE (top half)
            RoomTemplate("Primary Bedroom", "primary_bedroom", 0.0, 0.55, 0.45, 0.45, is_exterior=True),
            RoomTemplate("Bedroom 2", "bedroom", 0.55, 0.55, 0.45, 0.45, is_exterior=True),
            RoomTemplate("Bathroom", "bathroom", 0.45, 0.35, 0.25, 0.2, is_wet=True),
            RoomTemplate("Hallway", "hallway", 0.45, 0.55, 0.1, 0.45),

            # SERVICE
            RoomTemplate("Closet", "closet", 0.8, 0.0, 0.2, 0.35),
        ]
    ),

    "3br": LayoutTemplate(
        name="Three Bedroom",
        description="Three bedroom single-family home",
        min_width=40, min_depth=40,
        ideal_ratio=1.0,
        bedroom_count=3,
        bathroom_count=2,
        total_sqft_range=(1200, 1800),
        rooms=[
            # PUBLIC ZONE
            RoomTemplate("Entry", "entry", 0.4, 0.0, 0.2, 0.15, is_exterior=True),
            RoomTemplate("Living Room", "living", 0.0, 0.0, 0.4, 0.4, is_exterior=True),
            RoomTemplate("Dining", "dining", 0.0, 0.4, 0.3, 0.25, is_exterior=True),
            RoomTemplate("Kitchen", "kitchen", 0.3, 0.4, 0.3, 0.25, is_wet=True),

            # PRIVATE ZONE - Primary Suite (bottom right)
            RoomTemplate("Primary Bedroom", "primary_bedroom", 0.6, 0.0, 0.4, 0.35, is_exterior=True),
            RoomTemplate("Primary Bath", "primary_bath", 0.6, 0.35, 0.2, 0.15, is_wet=True),
            RoomTemplate("Walk-in Closet", "closet", 0.8, 0.35, 0.2, 0.15),

            # PRIVATE ZONE - Secondary Bedrooms (top)
            RoomTemplate("Bedroom 2", "bedroom", 0.0, 0.65, 0.35, 0.35, is_exterior=True),
            RoomTemplate("Bedroom 3", "bedroom", 0.55, 0.65, 0.45, 0.35, is_exterior=True),
            RoomTemplate("Bathroom", "bathroom", 0.6, 0.5, 0.2, 0.15, is_wet=True),
            RoomTemplate("Hallway", "hallway", 0.35, 0.5, 0.25, 0.5),

            # SERVICE
            RoomTemplate("Laundry", "laundry", 0.35, 0.65, 0.2, 0.2, is_wet=True),
        ]
    ),

    "4br": LayoutTemplate(
        name="Four Bedroom",
        description="Four bedroom family home",
        min_width=50, min_depth=45,
        ideal_ratio=1.1,
        bedroom_count=4,
        bathroom_count=2.5,
        total_sqft_range=(1800, 2500),
        rooms=[
            # PUBLIC ZONE (front/bottom)
            RoomTemplate("Entry", "entry", 0.4, 0.0, 0.2, 0.12, is_exterior=True),
            RoomTemplate("Living Room", "living", 0.0, 0.0, 0.4, 0.35, is_exterior=True),
            RoomTemplate("Dining", "dining", 0.0, 0.35, 0.25, 0.2, is_exterior=True),
            RoomTemplate("Kitchen", "kitchen", 0.25, 0.35, 0.3, 0.2, is_wet=True),
            RoomTemplate("Family Room", "living", 0.55, 0.35, 0.25, 0.25),

            # PRIMARY SUITE (bottom right)
            RoomTemplate("Primary Bedroom", "primary_bedroom", 0.6, 0.0, 0.4, 0.25, is_exterior=True),
            RoomTemplate("Primary Bath", "primary_bath", 0.75, 0.25, 0.25, 0.1, is_wet=True),
            RoomTemplate("Walk-in Closet", "closet", 0.6, 0.25, 0.15, 0.1),

            # SECONDARY BEDROOMS (back/top)
            RoomTemplate("Bedroom 2", "bedroom", 0.0, 0.55, 0.3, 0.3, is_exterior=True),
            RoomTemplate("Bedroom 3", "bedroom", 0.3, 0.7, 0.3, 0.3, is_exterior=True),
            RoomTemplate("Bedroom 4", "bedroom", 0.65, 0.6, 0.35, 0.25, is_exterior=True),
            RoomTemplate("Bathroom", "bathroom", 0.55, 0.6, 0.1, 0.15, is_wet=True),
            RoomTemplate("Half Bath", "bathroom", 0.8, 0.35, 0.1, 0.1, is_wet=True),

            # CIRCULATION
            RoomTemplate("Hallway", "hallway", 0.3, 0.55, 0.35, 0.15),

            # SERVICE
            RoomTemplate("Laundry", "laundry", 0.55, 0.35, 0.1, 0.1, is_wet=True),
            RoomTemplate("Garage", "garage", 0.0, 0.85, 0.4, 0.15, is_exterior=True),
        ]
    ),
}


# =============================================================================
# TEMPLATE SELECTOR
# =============================================================================

def select_template(
    bedroom_count: int = None,
    bathroom_count: int = None,
    sqft: float = None,
    style: str = None
) -> Optional[LayoutTemplate]:
    """
    Select the best template based on requirements.

    Args:
        bedroom_count: Number of bedrooms (0-4)
        bathroom_count: Number of bathrooms
        sqft: Target square footage
        style: Layout style hint ("open", "traditional", "compact")

    Returns:
        Best matching template or None
    """
    # Direct style shortcuts
    style_map = {
        "studio": "studio",
        "1br": "1br", "1bed": "1br", "one bedroom": "1br",
        "2br": "2br", "2bed": "2br", "two bedroom": "2br",
        "3br": "3br", "3bed": "3br", "three bedroom": "3br",
        "4br": "4br", "4bed": "4br", "four bedroom": "4br",
    }

    if style and style.lower() in style_map:
        return LAYOUT_TEMPLATES.get(style_map[style.lower()])

    # Select by bedroom count
    if bedroom_count is not None:
        if bedroom_count == 0:
            return LAYOUT_TEMPLATES["studio"]
        elif bedroom_count == 1:
            return LAYOUT_TEMPLATES["1br"]
        elif bedroom_count == 2:
            return LAYOUT_TEMPLATES["2br"]
        elif bedroom_count == 3:
            return LAYOUT_TEMPLATES["3br"]
        else:
            return LAYOUT_TEMPLATES["4br"]

    # Select by sqft
    if sqft is not None:
        if sqft < 500:
            return LAYOUT_TEMPLATES["studio"]
        elif sqft < 800:
            return LAYOUT_TEMPLATES["1br"]
        elif sqft < 1200:
            return LAYOUT_TEMPLATES["2br"]
        elif sqft < 1800:
            return LAYOUT_TEMPLATES["3br"]
        else:
            return LAYOUT_TEMPLATES["4br"]

    # Default to 2BR
    return LAYOUT_TEMPLATES["2br"]


# =============================================================================
# LAYOUT GENERATOR
# =============================================================================

@dataclass
class GeneratedRoom:
    """A room with concrete dimensions"""
    name: str
    room_type: str
    x: float
    y: float
    width: float
    depth: float
    is_exterior: bool = False
    is_wet: bool = False

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.depth

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.depth / 2)


@dataclass
class GeneratedLayout:
    """Complete generated floor plan"""
    template_name: str
    width: float
    depth: float
    rooms: List[GeneratedRoom]
    walls: List[Dict] = field(default_factory=list)
    doors: List[Dict] = field(default_factory=list)

    @property
    def total_area(self) -> float:
        return self.width * self.depth

    @property
    def room_area(self) -> float:
        return sum(r.area for r in self.rooms)

    @property
    def efficiency(self) -> float:
        return self.room_area / self.total_area if self.total_area > 0 else 0


def generate_layout(
    template: LayoutTemplate,
    width: float,
    depth: float,
    origin_x: float = 0.0,
    origin_y: float = 0.0,
    grid_snap: float = 1.0
) -> GeneratedLayout:
    """
    Generate a concrete layout from a template.

    Args:
        template: The layout template to use
        width: Footprint width in feet
        depth: Footprint depth in feet
        origin_x: X offset for placement
        origin_y: Y offset for placement
        grid_snap: Snap dimensions to this grid size

    Returns:
        GeneratedLayout with concrete room dimensions
    """
    rooms = []

    for rt in template.rooms:
        # Calculate dimensions from ratios
        x = rt.x_ratio * width + origin_x
        y = rt.y_ratio * depth + origin_y
        w = rt.width_ratio * width
        d = rt.depth_ratio * depth

        # Snap to grid
        if grid_snap > 0:
            x = round(x / grid_snap) * grid_snap
            y = round(y / grid_snap) * grid_snap
            w = max(grid_snap, round(w / grid_snap) * grid_snap)
            d = max(grid_snap, round(d / grid_snap) * grid_snap)

        rooms.append(GeneratedRoom(
            name=rt.name,
            room_type=rt.room_type,
            x=x,
            y=y,
            width=w,
            depth=d,
            is_exterior=rt.is_exterior,
            is_wet=rt.is_wet
        ))

    layout = GeneratedLayout(
        template_name=template.name,
        width=width,
        depth=depth,
        rooms=rooms
    )

    # Generate walls and doors
    layout.walls = _generate_walls(layout, origin_x, origin_y)
    layout.doors = _generate_doors(layout)

    return layout


def _generate_walls(layout: GeneratedLayout, origin_x: float, origin_y: float) -> List[Dict]:
    """Generate wall segments from room layout"""
    walls = {
        "exterior": [],
        "interior": [],
        "wet_wall": []
    }

    # Exterior walls (boundary)
    w, d = layout.width, layout.depth

    # South wall
    walls["exterior"].append({
        "start": {"x": origin_x, "y": origin_y},
        "end": {"x": origin_x + w, "y": origin_y}
    })
    # North wall
    walls["exterior"].append({
        "start": {"x": origin_x, "y": origin_y + d},
        "end": {"x": origin_x + w, "y": origin_y + d}
    })
    # West wall
    walls["exterior"].append({
        "start": {"x": origin_x, "y": origin_y},
        "end": {"x": origin_x, "y": origin_y + d}
    })
    # East wall
    walls["exterior"].append({
        "start": {"x": origin_x + w, "y": origin_y},
        "end": {"x": origin_x + w, "y": origin_y + d}
    })

    # Interior walls (between rooms)
    rooms = layout.rooms
    for i, room1 in enumerate(rooms):
        for room2 in rooms[i+1:]:
            edge = _shared_edge(room1, room2)
            if edge:
                wall_type = "wet_wall" if (room1.is_wet or room2.is_wet) else "interior"
                walls[wall_type].append({
                    "start": {"x": edge[0][0], "y": edge[0][1]},
                    "end": {"x": edge[1][0], "y": edge[1][1]},
                    "rooms": [room1.name, room2.name]
                })

    return walls


def _shared_edge(room1: GeneratedRoom, room2: GeneratedRoom, tolerance: float = 1.5) -> Optional[Tuple]:
    """Find shared edge between two rooms (tolerance increased to handle grid snapping gaps)"""
    # Check vertical edge (rooms are left-right)
    if abs(room1.x2 - room2.x) < tolerance:
        y_start = max(room1.y, room2.y)
        y_end = min(room1.y2, room2.y2)
        if y_end > y_start:
            return ((room1.x2, y_start), (room1.x2, y_end))

    if abs(room1.x - room2.x2) < tolerance:
        y_start = max(room1.y, room2.y)
        y_end = min(room1.y2, room2.y2)
        if y_end > y_start:
            return ((room1.x, y_start), (room1.x, y_end))

    # Check horizontal edge (rooms are top-bottom)
    if abs(room1.y2 - room2.y) < tolerance:
        x_start = max(room1.x, room2.x)
        x_end = min(room1.x2, room2.x2)
        if x_end > x_start:
            return ((x_start, room1.y2), (x_end, room1.y2))

    if abs(room1.y - room2.y2) < tolerance:
        x_start = max(room1.x, room2.x)
        x_end = min(room1.x2, room2.x2)
        if x_end > x_start:
            return ((x_start, room1.y), (x_end, room1.y))

    return None


def _generate_doors(layout: GeneratedLayout) -> List[Dict]:
    """Generate door placements"""
    doors = []

    rooms = layout.rooms
    for i, room1 in enumerate(rooms):
        for room2 in rooms[i+1:]:
            edge = _shared_edge(room1, room2)
            if edge:
                # Skip closet-to-closet, hallway-only connections
                if room1.room_type == "closet" and room2.room_type == "closet":
                    continue

                # Place door at center of shared edge
                center_x = (edge[0][0] + edge[1][0]) / 2
                center_y = (edge[0][1] + edge[1][1]) / 2

                doors.append({
                    "point": [center_x, center_y, 0],
                    "rooms": [room1.name, room2.name],
                    "width": 3.0
                })

    return doors


# =============================================================================
# OUTPUT FORMATTING (MCP COMPATIBLE)
# =============================================================================

def layout_to_walls_batch(
    layout: GeneratedLayout,
    level_name: str = "Level 1",
    wall_height: float = 10.0,
    exterior_wall_type: str = None,
    interior_wall_type: str = None,
    wet_wall_type: str = None
) -> List[Dict]:
    """
    Convert layout to wall batch format for create_walls_batch endpoint.

    Returns list ready to send to /revit_mcp/create_walls_batch
    """
    walls_batch = []

    for wall in layout.walls.get("exterior", []):
        walls_batch.append({
            "start": [wall["start"]["x"], wall["start"]["y"]],
            "end": [wall["end"]["x"], wall["end"]["y"]],
            "level_name": level_name,
            "height": wall_height,
            "wall_type": exterior_wall_type,
            "category": "exterior"
        })

    for wall in layout.walls.get("interior", []):
        walls_batch.append({
            "start": [wall["start"]["x"], wall["start"]["y"]],
            "end": [wall["end"]["x"], wall["end"]["y"]],
            "level_name": level_name,
            "height": wall_height,
            "wall_type": interior_wall_type,
            "category": "interior",
            "rooms": wall.get("rooms", [])
        })

    for wall in layout.walls.get("wet_wall", []):
        walls_batch.append({
            "start": [wall["start"]["x"], wall["start"]["y"]],
            "end": [wall["end"]["x"], wall["end"]["y"]],
            "level_name": level_name,
            "height": wall_height,
            "wall_type": wet_wall_type or interior_wall_type,
            "category": "wet_wall",
            "rooms": wall.get("rooms", [])
        })

    return walls_batch


def layout_to_room_data(layout: GeneratedLayout) -> Dict[str, Dict]:
    """Convert layout to room data for reference"""
    rooms = {}
    for room in layout.rooms:
        rooms[room.name] = {
            "type": room.room_type,
            "bounds": {
                "x1": room.x,
                "y1": room.y,
                "x2": room.x2,
                "y2": room.y2
            },
            "center": list(room.center),
            "area_sqft": room.area,
            "is_exterior": room.is_exterior,
            "is_wet": room.is_wet
        }
    return rooms


# =============================================================================
# MAIN GENERATION FUNCTION (MCP TOOL INTERFACE)
# =============================================================================

def generate_floor_plan(
    width: float = 40,
    depth: float = 30,
    bedroom_count: int = None,
    style: str = None,
    level_name: str = "Level 1",
    wall_height: float = 10.0,
    exterior_wall_type: str = None,
    interior_wall_type: str = None,
    wet_wall_type: str = None,
    origin_x: float = 0.0,
    origin_y: float = 0.0
) -> Dict[str, Any]:
    """
    Generate a floor plan using template-based approach.

    This is the main MCP tool function - simplified interface.

    Args:
        width: Footprint width in feet
        depth: Footprint depth in feet
        bedroom_count: Number of bedrooms (selects template)
        style: Style hint ("studio", "1br", "2br", "3br", "4br")
        level_name: Revit level name
        wall_height: Wall height in feet
        exterior_wall_type: Revit wall type for exterior
        interior_wall_type: Revit wall type for interior
        wet_wall_type: Revit wall type for wet walls
        origin_x: X offset
        origin_y: Y offset

    Returns:
        Dict with walls_batch, rooms, doors, summary
    """
    try:
        # Calculate sqft for template selection
        sqft = width * depth

        # Select template
        template = select_template(
            bedroom_count=bedroom_count,
            sqft=sqft,
            style=style
        )

        if not template:
            return {
                "success": False,
                "error": "No suitable template found"
            }

        # Check minimum size
        if width < template.min_width:
            width = template.min_width
        if depth < template.min_depth:
            depth = template.min_depth

        # Generate layout
        layout = generate_layout(
            template=template,
            width=width,
            depth=depth,
            origin_x=origin_x,
            origin_y=origin_y,
            grid_snap=1.0
        )

        # Convert to output format
        walls_batch = layout_to_walls_batch(
            layout,
            level_name=level_name,
            wall_height=wall_height,
            exterior_wall_type=exterior_wall_type,
            interior_wall_type=interior_wall_type,
            wet_wall_type=wet_wall_type
        )

        rooms_data = layout_to_room_data(layout)

        return {
            "success": True,
            "template_used": template.name,
            "walls_batch": walls_batch,
            "rooms": rooms_data,
            "doors": layout.doors,
            "summary": {
                "total_walls": len(walls_batch),
                "exterior_walls": len(layout.walls.get("exterior", [])),
                "interior_walls": len(layout.walls.get("interior", [])),
                "wet_walls": len(layout.walls.get("wet_wall", [])),
                "rooms": len(layout.rooms),
                "doors": len(layout.doors),
                "total_sqft": layout.total_area,
                "efficiency": f"{layout.efficiency * 100:.0f}%"
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# =============================================================================
# QBD INTEGRATION
# =============================================================================

def qbd_to_layout_params(qbd_answers: Dict) -> Dict:
    """
    Convert QBD interview answers to generate_floor_plan parameters.

    Expected QBD answers:
    - building_type: "residential" / "commercial"
    - style: "studio" / "1br" / "2br" / "3br" / "4br"
    - bedroom_count: 0-4
    - sqft: target square footage
    - width: footprint width (optional)
    - depth: footprint depth (optional)
    """
    params = {}

    # Extract bedroom count
    if "bedroom_count" in qbd_answers:
        params["bedroom_count"] = int(qbd_answers["bedroom_count"])
    elif "style" in qbd_answers:
        params["style"] = qbd_answers["style"]

    # Extract dimensions
    if "sqft" in qbd_answers:
        sqft = float(qbd_answers["sqft"])
        # Calculate reasonable dimensions
        ratio = 1.2  # Slightly wider than deep
        params["depth"] = math.sqrt(sqft / ratio)
        params["width"] = sqft / params["depth"]

    if "width" in qbd_answers:
        params["width"] = float(qbd_answers["width"])
    if "depth" in qbd_answers:
        params["depth"] = float(qbd_answers["depth"])

    return params


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ROOM LAYOUT GENERATOR V3 - Template Based")
    print("=" * 60)

    # Test 2BR layout
    result = generate_floor_plan(
        width=40,
        depth=35,
        bedroom_count=2,
        level_name="Level 1",
        exterior_wall_type="Generic - 8\" Masonry",
        interior_wall_type="Interior - 4 7/8\" Partition",
        wet_wall_type="Interior - 6 1/8\" Partition"
    )

    if result["success"]:
        print(f"\n✅ Layout Generated: {result['template_used']}")
        print(f"\n📊 Summary:")
        for k, v in result["summary"].items():
            print(f"   {k}: {v}")

        print(f"\n🏠 Rooms:")
        for name, room in result["rooms"].items():
            print(f"   {name}: {room['area_sqft']:.0f} sqft ({room['type']})")

        print(f"\n🧱 Walls batch preview (first 3):")
        for wall in result["walls_batch"][:3]:
            cat = wall.get("category", "?")
            print(f"   [{cat}] {wall['start']} -> {wall['end']}")
    else:
        print(f"❌ Error: {result['error']}")
