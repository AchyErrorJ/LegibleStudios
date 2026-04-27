"""
Construction Assembly System
============================
Generates accurate construction geometry with all layers, membranes, and connections.
Enables automatic detail generation and explosion views.
"""

import json
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class LayerType(Enum):
    """Types of construction layers"""
    STRUCTURE = "structure"          # Load-bearing (studs, joists, beams)
    SHEATHING = "sheathing"          # Structural sheathing (plywood, OSB)
    INSULATION = "insulation"        # Thermal insulation
    MEMBRANE = "membrane"            # WRB, vapor barrier, air barrier
    CLADDING = "cladding"            # Exterior finish (siding, brick)
    FINISH = "finish"                # Interior finish (drywall, plaster)
    AIR_GAP = "air_gap"              # Ventilation cavity, rain screen
    SUBSTRATE = "substrate"          # Backer board, underlayment
    FASTENER = "fastener"            # Screws, nails, ties


class MaterialCategory(Enum):
    """Material categories for rendering and scheduling"""
    WOOD = "wood"
    METAL = "metal"
    CONCRETE = "concrete"
    MASONRY = "masonry"
    INSULATION = "insulation"
    MEMBRANE = "membrane"
    GYPSUM = "gypsum"
    CEMENT = "cement"
    PLASTIC = "plastic"
    AIR = "air"


# =============================================================================
# UNIT SYSTEM CONFIGURATION
# =============================================================================

class UnitSystem:
    """
    Unit system configuration.
    Primary: Metric (mm for thickness, m for length)
    Secondary: Imperial (inches for thickness, feet for length)

    Revit uses feet internally, so we convert on output.
    Custom software will use metric natively.
    """
    METRIC = "metric"
    IMPERIAL = "imperial"

    # Current input mode (what users enter)
    current = METRIC

    # Conversion factors
    MM_TO_FEET = 0.00328084      # 1mm = 0.00328084 feet
    INCH_TO_FEET = 1/12          # 1 inch = 0.0833... feet
    M_TO_FEET = 3.28084          # 1m = 3.28084 feet
    MM_TO_INCH = 0.0393701       # 1mm = 0.0393701 inches
    INCH_TO_MM = 25.4            # 1 inch = 25.4mm

    @classmethod
    def to_feet(cls, value: float, unit: str = None) -> float:
        """Convert value to feet (Revit internal unit)"""
        unit = unit or cls.current
        if unit == cls.METRIC:
            return value * cls.MM_TO_FEET  # Input in mm
        else:
            return value * cls.INCH_TO_FEET  # Input in inches

    @classmethod
    def to_display(cls, feet_value: float, unit: str = None) -> tuple:
        """Convert feet to display value with unit label"""
        unit = unit or cls.current
        if unit == cls.METRIC:
            mm = feet_value / cls.MM_TO_FEET
            return (mm, "mm")
        else:
            inches = feet_value / cls.INCH_TO_FEET
            return (inches, "in")

    @classmethod
    def format_thickness(cls, feet_value: float) -> str:
        """Format thickness for display (shows both units)"""
        mm = feet_value / cls.MM_TO_FEET
        inches = feet_value / cls.INCH_TO_FEET
        return f"{mm:.1f}mm ({inches:.3f}\")"

    @classmethod
    def set_metric(cls):
        """Set input mode to metric (mm)"""
        cls.current = cls.METRIC
        print("   📐 Unit system: METRIC (mm input)")

    @classmethod
    def set_imperial(cls):
        """Set input mode to imperial (inches)"""
        cls.current = cls.IMPERIAL
        print("   📐 Unit system: IMPERIAL (inch input)")


# Shorthand converters
def mm(value: float) -> float:
    """Convert millimeters to feet (for Revit)"""
    return value * UnitSystem.MM_TO_FEET

def inch(value: float) -> float:
    """Convert inches to feet (for Revit)"""
    return value * UnitSystem.INCH_TO_FEET

def m(value: float) -> float:
    """Convert meters to feet (for Revit)"""
    return value * UnitSystem.M_TO_FEET


# Standard material thicknesses - METRIC PRIMARY (mm), imperial reference
# Format: metric_mm (imperial_equivalent)
STANDARD_THICKNESSES = {
    # Sheathing/boards
    "12mm_ply": mm(12),          # ~1/2" plywood
    "15mm_ply": mm(15),          # ~5/8" plywood
    "18mm_ply": mm(18),          # ~3/4" plywood
    "12mm_gyp": mm(12.5),        # ~1/2" gypsum
    "15mm_gyp": mm(15.9),        # ~5/8" gypsum

    # Framing - nominal sizes (actual dimensions)
    "38x89": mm(89),             # 2x4 (actual 38x89mm / 1.5x3.5")
    "38x140": mm(140),           # 2x6 (actual 38x140mm / 1.5x5.5")
    "38x184": mm(184),           # 2x8 (actual 38x184mm / 1.5x7.25")
    "38x235": mm(235),           # 2x10 (actual 38x235mm / 1.5x9.25")
    "38x286": mm(286),           # 2x12 (actual 38x286mm / 1.5x11.25")

    # Membranes
    "membrane": mm(0.25),        # ~0.01" typical membrane
    "vapor_barrier": mm(0.15),   # ~0.006" poly

    # Legacy imperial references (for transition)
    "1/2_ply": inch(0.5),
    "5/8_ply": inch(0.625),
    "3/4_ply": inch(0.75),
    "1/2_gyp": inch(0.5),
    "5/8_gyp": inch(0.625),
    "2x4": inch(3.5),
    "2x6": inch(5.5),
    "2x8": inch(7.25),
    "2x10": inch(9.25),
    "2x12": inch(11.25),
}

# Shorthand for common thicknesses
INCH = inch(1)  # Legacy support


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Layer:
    """A single layer in a construction assembly"""
    name: str
    thickness: float  # in feet
    layer_type: LayerType
    material_category: MaterialCategory
    material_name: str = ""

    # Visual properties
    color: Tuple[int, int, int] = (128, 128, 128)  # RGB
    hatch_pattern: str = ""

    # Construction properties
    is_structural: bool = False
    is_continuous: bool = True  # False for framing with cavities
    cavity_spacing: float = 0  # Stud/joist spacing if not continuous
    cavity_fill: str = ""  # What fills the cavity (insulation type)

    # For membranes
    wraps_at_openings: bool = False
    lap_distance: float = 0  # Overlap at seams

    # Fastening
    fastener_type: str = ""
    fastener_spacing: float = 0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "thickness": self.thickness,
            "layer_type": self.layer_type.value,
            "material_category": self.material_category.value,
            "material_name": self.material_name,
            "color": self.color,
            "is_structural": self.is_structural,
            "is_continuous": self.is_continuous,
        }


@dataclass
class ConnectionDetail:
    """How an assembly connects at specific conditions"""
    name: str
    condition: str  # "at_floor", "at_roof", "at_window", etc.
    layers_affected: List[str]  # Which layers have special treatment
    description: str = ""
    detail_components: List[Dict] = field(default_factory=list)


@dataclass
class ConstructionAssembly:
    """A complete construction assembly (wall, floor, roof)"""
    name: str
    assembly_type: str  # "wall", "floor", "roof"
    layers: List[Layer]
    connections: Dict[str, ConnectionDetail] = field(default_factory=dict)

    # Assembly properties
    fire_rating: str = ""
    r_value: float = 0
    stc_rating: int = 0  # Sound Transmission Class

    # For walls
    is_exterior: bool = False
    is_load_bearing: bool = False

    def total_thickness(self) -> float:
        """Calculate total assembly thickness"""
        return sum(layer.thickness for layer in self.layers)

    def get_layer_offsets(self, from_exterior: bool = True) -> List[Tuple[Layer, float]]:
        """Get each layer with its offset from exterior/interior face"""
        offsets = []
        current_offset = 0

        layers = self.layers if from_exterior else reversed(self.layers)
        for layer in layers:
            offsets.append((layer, current_offset))
            current_offset += layer.thickness

        return offsets

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "assembly_type": self.assembly_type,
            "layers": [l.to_dict() for l in self.layers],
            "total_thickness": self.total_thickness(),
            "is_exterior": self.is_exterior,
            "r_value": self.r_value,
        }


# =============================================================================
# GEOMETRY GENERATION
# =============================================================================

@dataclass
class LayerGeometry:
    """Geometry for a single layer"""
    layer: Layer
    offset_from_core: float  # Distance from structural core

    # Wall segment geometry
    start_point: List[float] = field(default_factory=list)
    end_point: List[float] = field(default_factory=list)
    height: float = 0
    base_offset: float = 0

    # For explosion views
    explosion_offset: float = 0

    def to_revit_solid(self) -> Dict:
        """Convert to Revit-compatible solid definition"""
        # Calculate the 4 corners of the layer (in plan)
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        length = math.sqrt(dx*dx + dy*dy)

        if length == 0:
            return None

        # Normal vector (perpendicular to wall direction)
        nx = -dy / length
        ny = dx / length

        # Inner and outer face offsets
        inner_offset = self.offset_from_core
        outer_offset = self.offset_from_core + self.layer.thickness

        # Apply explosion offset if set
        if self.explosion_offset:
            inner_offset += self.explosion_offset
            outer_offset += self.explosion_offset

        # Four corners of the layer in plan
        points = [
            # Inner face
            [self.start_point[0] + nx * inner_offset,
             self.start_point[1] + ny * inner_offset,
             self.base_offset],
            [self.end_point[0] + nx * inner_offset,
             self.end_point[1] + ny * inner_offset,
             self.base_offset],
            # Outer face
            [self.end_point[0] + nx * outer_offset,
             self.end_point[1] + ny * outer_offset,
             self.base_offset],
            [self.start_point[0] + nx * outer_offset,
             self.start_point[1] + ny * outer_offset,
             self.base_offset],
        ]

        # Enhanced visualization for membranes
        is_membrane = self.layer.layer_type == LayerType.MEMBRANE

        return {
            "type": "extrusion",
            "profile_points": points,
            "height": self.height,
            "layer_name": self.layer.name,
            "material": self.layer.material_name,
            "color": self.layer.color,
            "is_membrane": is_membrane,
            "layer_type": self.layer.layer_type.value,
            "thickness": self.layer.thickness,
        }


class AssemblyGeometryGenerator:
    """Generates Revit geometry from construction assemblies"""

    def __init__(self, assembly: ConstructionAssembly):
        self.assembly = assembly

    def generate_wall_segment(
        self,
        start_point: List[float],
        end_point: List[float],
        height: float,
        base_offset: float = 0,
        core_location: str = "center"  # "center", "exterior", "interior"
    ) -> List[LayerGeometry]:
        """Generate geometry for all layers of a wall segment"""

        total_thickness = self.assembly.total_thickness()

        # Determine core offset based on location preference
        if core_location == "center":
            core_offset = -total_thickness / 2
        elif core_location == "exterior":
            core_offset = 0
        else:  # interior
            core_offset = -total_thickness

        geometries = []
        current_offset = core_offset

        for layer in self.assembly.layers:
            geom = LayerGeometry(
                layer=layer,
                offset_from_core=current_offset,
                start_point=start_point,
                end_point=end_point,
                height=height,
                base_offset=base_offset,
            )
            geometries.append(geom)
            current_offset += layer.thickness

        return geometries

    def generate_explosion_view(
        self,
        start_point: List[float],
        end_point: List[float],
        height: float,
        separation: float = 0.5,  # Gap between layers in explosion
        base_offset: float = 0
    ) -> List[LayerGeometry]:
        """Generate exploded view geometry with layers separated"""

        geometries = []
        current_explosion_offset = 0

        # Start from exterior, explode outward
        for i, layer in enumerate(self.assembly.layers):
            geom = LayerGeometry(
                layer=layer,
                offset_from_core=0,  # All start at same position
                start_point=start_point,
                end_point=end_point,
                height=height,
                base_offset=base_offset,
                explosion_offset=current_explosion_offset,
            )
            geometries.append(geom)
            current_explosion_offset += layer.thickness + separation

        return geometries

    def generate_section_detail(
        self,
        cut_location: float,  # Distance along wall
        wall_length: float,
        height: float,
        detail_width: float = 2.0,  # Width of detail view
    ) -> Dict:
        """Generate a section detail at a specific location"""

        # Create a narrow slice of the wall for the detail
        half_width = detail_width / 2
        start = [cut_location - half_width, 0, 0]
        end = [cut_location + half_width, 0, 0]

        layers_data = []
        current_offset = 0
        membrane_locations = []

        for layer in self.assembly.layers:
            is_membrane = layer.layer_type == LayerType.MEMBRANE

            layer_info = {
                "name": layer.name,
                "thickness": layer.thickness,
                "offset": current_offset,
                "material": layer.material_name,
                "color": layer.color,
                "layer_type": layer.layer_type.value,
                "is_continuous": layer.is_continuous,
                "is_membrane": is_membrane,
            }

            layers_data.append(layer_info)

            # Track membrane positions for highlighting
            if is_membrane:
                membrane_locations.append({
                    "name": layer.name,
                    "offset": current_offset,
                    "thickness": layer.thickness,
                    "material": layer.material_name,
                })

            current_offset += layer.thickness

        return {
            "assembly_name": self.assembly.name,
            "total_thickness": self.assembly.total_thickness(),
            "height": height,
            "layers": layers_data,
            "membrane_locations": membrane_locations,
            "cut_location": cut_location,
            "r_value": self.assembly.r_value,
        }


# =============================================================================
# REVIT INTEGRATION
# =============================================================================

class RevitAssemblyBuilder:
    """Builds assembly geometry in Revit"""

    def __init__(self, api_url: str = "http://localhost:48884"):
        self.api_url = api_url

    def create_assembly_wall(
        self,
        assembly: ConstructionAssembly,
        start_point: List[float],
        end_point: List[float],
        height: float,
        level_name: str,
        core_location: str = "center"
    ) -> List[Dict]:
        """Create a wall with all assembly layers as separate geometry"""

        generator = AssemblyGeometryGenerator(assembly)
        layer_geoms = generator.generate_wall_segment(
            start_point, end_point, height,
            core_location=core_location
        )

        # Convert to Revit commands
        commands = []
        for geom in layer_geoms:
            solid = geom.to_revit_solid()
            if solid:
                # For now, create as generic model or direct shape
                # In future, could create proper Revit wall layers
                commands.append({
                    "tool": "create_direct_shape",
                    "args": {
                        "geometry": solid,
                        "category": "Generic Models",
                        "name": f"{assembly.name} - {geom.layer.name}",
                        "level_name": level_name,
                    }
                })

        return commands

    def create_explosion_view(
        self,
        assembly: ConstructionAssembly,
        start_point: List[float],
        end_point: List[float],
        height: float,
        level_name: str,
        separation: float = 0.5
    ) -> List[Dict]:
        """Create an exploded view of the assembly"""

        generator = AssemblyGeometryGenerator(assembly)
        layer_geoms = generator.generate_explosion_view(
            start_point, end_point, height,
            separation=separation
        )

        commands = []
        for geom in layer_geoms:
            solid = geom.to_revit_solid()
            if solid:
                commands.append({
                    "tool": "create_direct_shape",
                    "args": {
                        "geometry": solid,
                        "category": "Generic Models",
                        "name": f"EXPLODED - {assembly.name} - {geom.layer.name}",
                        "level_name": level_name,
                    }
                })

        return commands


# =============================================================================
# ASSEMBLY LIBRARY - COMMON CONSTRUCTIONS
# =============================================================================

def create_2x6_exterior_wall() -> ConstructionAssembly:
    """Standard 2x6 wood frame exterior wall with rain screen"""

    layers = [
        # Exterior to interior
        Layer(
            name="Fiber Cement Siding",
            thickness=0.375 * INCH,
            layer_type=LayerType.CLADDING,
            material_category=MaterialCategory.CEMENT,
            material_name="Fiber Cement",
            color=(180, 175, 165),
            fastener_type="SS screws",
            fastener_spacing=16 * INCH,
        ),
        Layer(
            name="Rain Screen Cavity",
            thickness=0.75 * INCH,
            layer_type=LayerType.AIR_GAP,
            material_category=MaterialCategory.AIR,
            material_name="Air",
            color=(200, 220, 240),
            is_continuous=False,
            cavity_spacing=16 * INCH,
        ),
        Layer(
            name="Weather Resistive Barrier",
            thickness=STANDARD_THICKNESSES["membrane"],
            layer_type=LayerType.MEMBRANE,
            material_category=MaterialCategory.MEMBRANE,
            material_name="WRB",
            color=(255, 255, 255),
            wraps_at_openings=True,
            lap_distance=6 * INCH,
        ),
        Layer(
            name="Exterior Sheathing",
            thickness=STANDARD_THICKNESSES["1/2_ply"],
            layer_type=LayerType.SHEATHING,
            material_category=MaterialCategory.WOOD,
            material_name="Plywood",
            color=(210, 180, 140),
            is_structural=True,
        ),
        Layer(
            name="2x6 Stud Cavity",
            thickness=STANDARD_THICKNESSES["2x6"],
            layer_type=LayerType.STRUCTURE,
            material_category=MaterialCategory.WOOD,
            material_name="SPF Lumber",
            color=(240, 220, 180),
            is_structural=True,
            is_continuous=False,
            cavity_spacing=16 * INCH,
            cavity_fill="R-21 Batt Insulation",
        ),
        Layer(
            name="Vapor Retarder",
            thickness=STANDARD_THICKNESSES["vapor_barrier"],
            layer_type=LayerType.MEMBRANE,
            material_category=MaterialCategory.PLASTIC,
            material_name="6 mil Poly",
            color=(200, 200, 255),
        ),
        Layer(
            name="Gypsum Board",
            thickness=STANDARD_THICKNESSES["5/8_gyp"],
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.GYPSUM,
            material_name="Type X Gypsum",
            color=(245, 245, 240),
        ),
    ]

    return ConstructionAssembly(
        name="Ext Wall - 2x6 Frame w/ Rain Screen",
        assembly_type="wall",
        layers=layers,
        is_exterior=True,
        is_load_bearing=True,
        r_value=21,
        fire_rating="1-hour",
    )


def create_2x4_interior_wall() -> ConstructionAssembly:
    """Standard 2x4 interior partition wall"""

    layers = [
        Layer(
            name="Gypsum Board",
            thickness=STANDARD_THICKNESSES["1/2_gyp"],
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.GYPSUM,
            material_name="Gypsum",
            color=(245, 245, 240),
        ),
        Layer(
            name="2x4 Stud Cavity",
            thickness=STANDARD_THICKNESSES["2x4"],
            layer_type=LayerType.STRUCTURE,
            material_category=MaterialCategory.WOOD,
            material_name="SPF Lumber",
            color=(240, 220, 180),
            is_structural=False,
            is_continuous=False,
            cavity_spacing=16 * INCH,
            cavity_fill="R-13 Batt (optional)",
        ),
        Layer(
            name="Gypsum Board",
            thickness=STANDARD_THICKNESSES["1/2_gyp"],
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.GYPSUM,
            material_name="Gypsum",
            color=(245, 245, 240),
        ),
    ]

    return ConstructionAssembly(
        name="Int Wall - 2x4 Partition",
        assembly_type="wall",
        layers=layers,
        is_exterior=False,
        is_load_bearing=False,
        r_value=0,
        stc_rating=35,
    )


def create_floor_assembly_wood() -> ConstructionAssembly:
    """Wood frame floor assembly"""

    layers = [
        # Top to bottom
        Layer(
            name="Hardwood Flooring",
            thickness=0.75 * INCH,
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.WOOD,
            material_name="Oak",
            color=(180, 140, 100),
        ),
        Layer(
            name="Underlayment",
            thickness=0.25 * INCH,
            layer_type=LayerType.SUBSTRATE,
            material_category=MaterialCategory.WOOD,
            material_name="Plywood",
            color=(210, 180, 140),
        ),
        Layer(
            name="Subfloor",
            thickness=STANDARD_THICKNESSES["3/4_ply"],
            layer_type=LayerType.SHEATHING,
            material_category=MaterialCategory.WOOD,
            material_name="T&G Plywood",
            color=(200, 170, 130),
            is_structural=True,
        ),
        Layer(
            name="Floor Joist Cavity",
            thickness=STANDARD_THICKNESSES["2x10"],
            layer_type=LayerType.STRUCTURE,
            material_category=MaterialCategory.WOOD,
            material_name="SPF Lumber",
            color=(240, 220, 180),
            is_structural=True,
            is_continuous=False,
            cavity_spacing=16 * INCH,
            cavity_fill="R-30 Batt (if over unconditioned)",
        ),
        Layer(
            name="Gypsum Ceiling",
            thickness=STANDARD_THICKNESSES["1/2_gyp"],
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.GYPSUM,
            material_name="Gypsum",
            color=(245, 245, 240),
        ),
    ]

    return ConstructionAssembly(
        name="Floor - Wood Frame",
        assembly_type="floor",
        layers=layers,
        fire_rating="1-hour",
    )


def create_roof_assembly() -> ConstructionAssembly:
    """Typical asphalt shingle roof assembly"""

    layers = [
        # Top to bottom
        Layer(
            name="Asphalt Shingles",
            thickness=0.25 * INCH,
            layer_type=LayerType.CLADDING,
            material_category=MaterialCategory.PLASTIC,
            material_name="Architectural Shingles",
            color=(60, 60, 60),
        ),
        Layer(
            name="Roofing Underlayment",
            thickness=STANDARD_THICKNESSES["membrane"],
            layer_type=LayerType.MEMBRANE,
            material_category=MaterialCategory.MEMBRANE,
            material_name="Synthetic Underlayment",
            color=(80, 80, 80),
            lap_distance=6 * INCH,
        ),
        Layer(
            name="Roof Sheathing",
            thickness=STANDARD_THICKNESSES["1/2_ply"],
            layer_type=LayerType.SHEATHING,
            material_category=MaterialCategory.WOOD,
            material_name="OSB",
            color=(200, 180, 140),
            is_structural=True,
        ),
        Layer(
            name="Rafter Cavity",
            thickness=STANDARD_THICKNESSES["2x10"],
            layer_type=LayerType.STRUCTURE,
            material_category=MaterialCategory.WOOD,
            material_name="SPF Lumber",
            color=(240, 220, 180),
            is_structural=True,
            is_continuous=False,
            cavity_spacing=24 * INCH,
            cavity_fill="R-30 Batt",
        ),
        Layer(
            name="Vapor Retarder",
            thickness=STANDARD_THICKNESSES["vapor_barrier"],
            layer_type=LayerType.MEMBRANE,
            material_category=MaterialCategory.PLASTIC,
            material_name="6 mil Poly",
            color=(200, 200, 255),
        ),
        Layer(
            name="Gypsum Ceiling",
            thickness=STANDARD_THICKNESSES["5/8_gyp"],
            layer_type=LayerType.FINISH,
            material_category=MaterialCategory.GYPSUM,
            material_name="Type X Gypsum",
            color=(245, 245, 240),
        ),
    ]

    return ConstructionAssembly(
        name="Roof - Asphalt Shingle",
        assembly_type="roof",
        layers=layers,
        r_value=30,
    )


# Assembly library
ASSEMBLY_LIBRARY = {
    "ext_wall_2x6": create_2x6_exterior_wall,
    "int_wall_2x4": create_2x4_interior_wall,
    "floor_wood": create_floor_assembly_wood,
    "roof_shingle": create_roof_assembly,
}

# Custom assemblies loaded from JSON or added at runtime
CUSTOM_ASSEMBLIES: Dict[str, ConstructionAssembly] = {}


def get_assembly(name: str) -> Optional[ConstructionAssembly]:
    """Get an assembly from the library by name"""
    # Check custom assemblies first
    if name in CUSTOM_ASSEMBLIES:
        return CUSTOM_ASSEMBLIES[name]

    # Then check built-in library
    factory = ASSEMBLY_LIBRARY.get(name)
    if factory:
        return factory()
    return None


def list_assemblies() -> List[Dict]:
    """List all available assemblies"""
    result = []

    # Built-in assemblies
    for key, factory in ASSEMBLY_LIBRARY.items():
        assembly = factory()
        result.append({
            "key": key,
            "name": assembly.name,
            "type": assembly.assembly_type,
            "thickness": assembly.total_thickness(),
            "r_value": assembly.r_value,
            "layers": len(assembly.layers),
            "source": "built-in",
        })

    # Custom assemblies
    for key, assembly in CUSTOM_ASSEMBLIES.items():
        result.append({
            "key": key,
            "name": assembly.name,
            "type": assembly.assembly_type,
            "thickness": assembly.total_thickness(),
            "r_value": assembly.r_value,
            "layers": len(assembly.layers),
            "source": "custom",
        })

    return result


# =============================================================================
# EASY ASSEMBLY CREATION
# =============================================================================

def add_assembly(
    key: str,
    name: str,
    assembly_type: str,  # "wall", "floor", "roof"
    layers: List[Dict],
    is_exterior: bool = False,
    is_load_bearing: bool = False,
    r_value: float = 0,
    fire_rating: str = "",
    units: str = "metric",  # "metric" (mm) or "imperial" (inches)
) -> ConstructionAssembly:
    """
    Easy way to add a new assembly.

    METRIC EXAMPLE (primary - thickness in mm):
        add_assembly(
            key="my_wall",
            name="My Custom Wall",
            assembly_type="wall",
            units="metric",  # thickness in mm
            layers=[
                {"name": "Siding", "thickness": 12, "type": "cladding", "material": "wood"},
                {"name": "Sheathing", "thickness": 12, "type": "sheathing", "material": "plywood"},
                {"name": "Studs", "thickness": 89, "type": "structure", "material": "wood", "spacing": 400},
                {"name": "Drywall", "thickness": 12.5, "type": "finish", "material": "gypsum"},
            ],
            is_exterior=True,
            r_value=13
        )

    IMPERIAL EXAMPLE (legacy - thickness in inches):
        add_assembly(
            key="my_wall",
            name="My Custom Wall",
            assembly_type="wall",
            units="imperial",  # thickness in inches
            layers=[
                {"name": "Siding", "thickness": 0.5, "type": "cladding", "material": "wood"},
                {"name": "Studs", "thickness": 3.5, "type": "structure", "material": "wood", "spacing": 16},
                {"name": "Drywall", "thickness": 0.5, "type": "finish", "material": "gypsum"},
            ],
            is_exterior=True,
            r_value=13
        )

    Layer dict keys:
        - name: Layer name (required)
        - thickness: Thickness in mm (metric) or inches (imperial) (required)
        - type: "structure", "sheathing", "insulation", "membrane", "cladding", "finish", "air_gap"
        - material: Material name
        - color: [R, G, B] tuple (optional)
        - spacing: Stud/joist spacing in mm (metric) or inches (imperial) (optional)
        - structural: True/False (optional)
    """

    # Type mapping
    type_map = {
        "structure": LayerType.STRUCTURE,
        "sheathing": LayerType.SHEATHING,
        "insulation": LayerType.INSULATION,
        "membrane": LayerType.MEMBRANE,
        "cladding": LayerType.CLADDING,
        "finish": LayerType.FINISH,
        "air_gap": LayerType.AIR_GAP,
        "substrate": LayerType.SUBSTRATE,
    }

    # Material category mapping
    material_map = {
        "wood": MaterialCategory.WOOD,
        "plywood": MaterialCategory.WOOD,
        "osb": MaterialCategory.WOOD,
        "lumber": MaterialCategory.WOOD,
        "metal": MaterialCategory.METAL,
        "steel": MaterialCategory.METAL,
        "concrete": MaterialCategory.CONCRETE,
        "masonry": MaterialCategory.MASONRY,
        "brick": MaterialCategory.MASONRY,
        "insulation": MaterialCategory.INSULATION,
        "batt": MaterialCategory.INSULATION,
        "foam": MaterialCategory.INSULATION,
        "membrane": MaterialCategory.MEMBRANE,
        "wrb": MaterialCategory.MEMBRANE,
        "tyvek": MaterialCategory.MEMBRANE,
        "poly": MaterialCategory.PLASTIC,
        "plastic": MaterialCategory.PLASTIC,
        "gypsum": MaterialCategory.GYPSUM,
        "drywall": MaterialCategory.GYPSUM,
        "cement": MaterialCategory.CEMENT,
        "fiber_cement": MaterialCategory.CEMENT,
        "air": MaterialCategory.AIR,
    }

    # Default colors by type
    default_colors = {
        "structure": (240, 220, 180),
        "sheathing": (210, 180, 140),
        "insulation": (255, 200, 200),
        "membrane": (255, 255, 255),
        "cladding": (180, 175, 165),
        "finish": (245, 245, 240),
        "air_gap": (200, 220, 240),
        "substrate": (200, 180, 160),
    }

    # Determine conversion function based on units
    if units == "metric":
        convert_thickness = mm  # mm to feet
    else:
        convert_thickness = inch  # inches to feet

    # Convert layer dicts to Layer objects
    layer_objects = []
    for l in layers:
        layer_type_str = l.get("type", "finish")
        layer_type = type_map.get(layer_type_str, LayerType.FINISH)

        material_str = l.get("material", "").lower()
        material_cat = material_map.get(material_str, MaterialCategory.WOOD)

        color = l.get("color", default_colors.get(layer_type_str, (128, 128, 128)))
        if isinstance(color, list):
            color = tuple(color)

        spacing = l.get("spacing", 0)
        is_continuous = spacing == 0

        layer_objects.append(Layer(
            name=l["name"],
            thickness=convert_thickness(l["thickness"]),  # Convert to feet based on unit system
            layer_type=layer_type,
            material_category=material_cat,
            material_name=l.get("material", ""),
            color=color,
            is_structural=l.get("structural", layer_type == LayerType.STRUCTURE),
            is_continuous=is_continuous,
            cavity_spacing=convert_thickness(spacing) if spacing else 0,
            cavity_fill=l.get("cavity_fill", ""),
            wraps_at_openings=l.get("wraps", False),
        ))

    assembly = ConstructionAssembly(
        name=name,
        assembly_type=assembly_type,
        layers=layer_objects,
        is_exterior=is_exterior,
        is_load_bearing=is_load_bearing,
        r_value=r_value,
        fire_rating=fire_rating,
    )

    # Add to custom assemblies
    CUSTOM_ASSEMBLIES[key] = assembly
    print(f"   ✅ Added assembly: {key} ({name})")

    return assembly


def add_assembly_from_json(json_data: Dict) -> ConstructionAssembly:
    """
    Add assembly from a JSON dict.

    JSON format (METRIC - thickness in mm, spacing in mm):
    {
        "key": "my_wall",
        "name": "My Wall Assembly",
        "type": "wall",
        "units": "metric",
        "is_exterior": true,
        "r_value": 21,
        "layers": [
            {"name": "Siding", "thickness": 9.5, "type": "cladding", "material": "fiber_cement"},
            {"name": "Studs", "thickness": 140, "type": "structure", "material": "wood", "spacing": 400},
            {"name": "Drywall", "thickness": 12.5, "type": "finish", "material": "gypsum"}
        ]
    }

    For imperial (legacy), set "units": "imperial" and use inches.
    """
    return add_assembly(
        key=json_data["key"],
        name=json_data["name"],
        assembly_type=json_data.get("type", "wall"),
        layers=json_data["layers"],
        is_exterior=json_data.get("is_exterior", False),
        is_load_bearing=json_data.get("is_load_bearing", False),
        r_value=json_data.get("r_value", 0),
        fire_rating=json_data.get("fire_rating", ""),
        units=json_data.get("units", "metric"),  # Default to metric
    )


def load_assemblies_from_file(file_path: str) -> List[ConstructionAssembly]:
    """
    Load assemblies from a JSON file.

    File format:
    {
        "assemblies": [
            { assembly1 },
            { assembly2 },
            ...
        ]
    }
    """
    import json as json_module
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        print(f"   ⚠️ Assembly file not found: {file_path}")
        return []

    try:
        with open(path) as f:
            data = json_module.load(f)

        assemblies = []
        for assembly_data in data.get("assemblies", []):
            assembly = add_assembly_from_json(assembly_data)
            assemblies.append(assembly)

        print(f"   📂 Loaded {len(assemblies)} assemblies from {file_path}")
        return assemblies

    except Exception as e:
        print(f"   ❌ Error loading assemblies: {e}")
        return []


def remove_assembly(key: str) -> bool:
    """Remove a custom assembly"""
    if key in CUSTOM_ASSEMBLIES:
        del CUSTOM_ASSEMBLIES[key]
        print(f"   🗑️ Removed assembly: {key}")
        return True
    return False


def clear_custom_assemblies():
    """Clear all custom assemblies"""
    CUSTOM_ASSEMBLIES.clear()
    print(f"   🗑️ Cleared all custom assemblies")


# =============================================================================
# PRE-BUILT QUICK ASSEMBLIES
# =============================================================================

def quick_wall(
    key: str,
    name: str,
    stud_size: str = "2x4",  # "2x4", "2x6"
    exterior_finish: str = "siding",  # "siding", "brick", "stucco", "none"
    interior_finish: str = "drywall",  # "drywall", "plaster", "none"
    insulation: bool = True,
    vapor_barrier: bool = False,
    rain_screen: bool = False,
    is_exterior: bool = True,
) -> ConstructionAssembly:
    """
    Quick helper to create common wall types.

    Examples:
        quick_wall("ext_basic", "Basic Exterior", stud_size="2x4", exterior_finish="siding")
        quick_wall("ext_rain", "Rain Screen Wall", stud_size="2x6", rain_screen=True)
        quick_wall("int_basic", "Interior Partition", stud_size="2x4", is_exterior=False, exterior_finish="none")
    """
    layers = []

    # Exterior finish
    if exterior_finish == "siding":
        layers.append({"name": "Fiber Cement Siding", "thickness": 0.375, "type": "cladding", "material": "fiber_cement"})
    elif exterior_finish == "brick":
        layers.append({"name": "Brick Veneer", "thickness": 4.0, "type": "cladding", "material": "masonry"})
    elif exterior_finish == "stucco":
        layers.append({"name": "Stucco", "thickness": 0.875, "type": "cladding", "material": "cement"})

    # Rain screen
    if rain_screen and exterior_finish != "none":
        layers.append({"name": "Rain Screen Cavity", "thickness": 0.75, "type": "air_gap", "material": "air"})

    # WRB (for exterior walls with cladding)
    if is_exterior and exterior_finish != "none":
        layers.append({"name": "Weather Resistive Barrier", "thickness": 0.01, "type": "membrane", "material": "wrb", "wraps": True})

    # Sheathing (exterior walls)
    if is_exterior:
        layers.append({"name": "Sheathing", "thickness": 0.5, "type": "sheathing", "material": "plywood", "structural": True})

    # Studs
    stud_thickness = 3.5 if stud_size == "2x4" else 5.5 if stud_size == "2x6" else 7.25
    r_value = 13 if stud_size == "2x4" else 21 if stud_size == "2x6" else 30
    layers.append({
        "name": f"{stud_size} Stud Cavity",
        "thickness": stud_thickness,
        "type": "structure",
        "material": "lumber",
        "spacing": 16,
        "cavity_fill": f"R-{r_value} Batt" if insulation else "",
        "structural": True,
    })

    # Vapor barrier
    if vapor_barrier:
        layers.append({"name": "Vapor Retarder", "thickness": 0.006, "type": "membrane", "material": "poly"})

    # Interior finish
    if interior_finish == "drywall":
        layers.append({"name": "Gypsum Board", "thickness": 0.5, "type": "finish", "material": "gypsum"})
    elif interior_finish == "plaster":
        layers.append({"name": "Plaster", "thickness": 0.625, "type": "finish", "material": "gypsum"})

    # For interior walls, add finish on both sides
    if not is_exterior and interior_finish != "none":
        # Insert at beginning
        if interior_finish == "drywall":
            layers.insert(0, {"name": "Gypsum Board", "thickness": 0.5, "type": "finish", "material": "gypsum"})
        elif interior_finish == "plaster":
            layers.insert(0, {"name": "Plaster", "thickness": 0.625, "type": "finish", "material": "gypsum"})

    return add_assembly(
        key=key,
        name=name,
        assembly_type="wall",
        layers=layers,
        is_exterior=is_exterior,
        is_load_bearing=is_exterior,
        r_value=r_value if insulation else 0,
    )
