"""
Furniture data models and JSON schema.

Defines the structure for furniture items, their properties,
and placement within a building.
"""
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import uuid


class FurnitureCategory(Enum):
    """Categories of furniture."""
    SEATING = "seating"           # Chairs, sofas, stools, benches
    TABLES = "tables"             # Dining, coffee, desk, side tables
    BEDS = "beds"                 # Single, double, queen, king, bunk
    STORAGE = "storage"           # Shelves, cabinets, wardrobes, dressers
    APPLIANCES = "appliances"     # Kitchen, bathroom, laundry
    FIXTURES = "fixtures"         # Sinks, toilets, bathtubs, showers
    LIGHTING = "lighting"         # Floor lamps, table lamps (furniture-style)
    DECOR = "decor"               # Plants, rugs, artwork stands
    OFFICE = "office"             # Desks, office chairs, filing cabinets
    OUTDOOR = "outdoor"           # Patio furniture, outdoor seating


class FurnitureStyle(Enum):
    """Visual style of furniture."""
    MODERN = "modern"
    TRADITIONAL = "traditional"
    CONTEMPORARY = "contemporary"
    MINIMALIST = "minimalist"
    INDUSTRIAL = "industrial"
    RUSTIC = "rustic"
    SCANDINAVIAN = "scandinavian"
    MID_CENTURY = "mid_century"


class LODLevel(Enum):
    """Level of Detail for rendering."""
    LOD0 = 0  # 2D plan symbol (footprint only)
    LOD1 = 1  # Bounding box (simple 3D)
    LOD2 = 2  # Composed primitives (boxes, cylinders)
    LOD3 = 3  # Detailed mesh (AI-generated, future)
    LOD4 = 4  # High-detail mesh with materials (future)
    LOD5 = 5  # Photorealistic (future)


@dataclass
class Dimensions:
    """Physical dimensions of furniture in millimeters."""
    width: float   # X-axis (left-right)
    depth: float   # Z-axis (front-back)
    height: float  # Y-axis (floor to top)

    # Optional sub-dimensions for complex furniture
    seat_height: Optional[float] = None      # For seating
    arm_height: Optional[float] = None       # For chairs with arms
    back_height: Optional[float] = None      # For seating backs
    table_top_thickness: Optional[float] = None  # For tables
    leg_width: Optional[float] = None        # For tables/chairs

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
        }
        if self.seat_height is not None:
            result["seat_height"] = self.seat_height
        if self.arm_height is not None:
            result["arm_height"] = self.arm_height
        if self.back_height is not None:
            result["back_height"] = self.back_height
        if self.table_top_thickness is not None:
            result["table_top_thickness"] = self.table_top_thickness
        if self.leg_width is not None:
            result["leg_width"] = self.leg_width
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dimensions":
        return cls(
            width=data["width"],
            depth=data["depth"],
            height=data["height"],
            seat_height=data.get("seat_height"),
            arm_height=data.get("arm_height"),
            back_height=data.get("back_height"),
            table_top_thickness=data.get("table_top_thickness"),
            leg_width=data.get("leg_width"),
        )


@dataclass
class Material:
    """Material properties for rendering."""
    name: str                    # e.g., "oak_wood", "leather", "fabric"
    base_color: Tuple[float, float, float] = (0.5, 0.5, 0.5)  # RGB 0-1
    metallic: float = 0.0        # 0 = dielectric, 1 = metal
    roughness: float = 0.5       # 0 = smooth, 1 = rough

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "base_color": list(self.base_color),
            "metallic": self.metallic,
            "roughness": self.roughness,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Material":
        return cls(
            name=data["name"],
            base_color=tuple(data.get("base_color", [0.5, 0.5, 0.5])),
            metallic=data.get("metallic", 0.0),
            roughness=data.get("roughness", 0.5),
        )


# Predefined materials
class Materials:
    """Common furniture materials."""
    # Woods
    OAK = Material("oak", (0.55, 0.35, 0.18), 0.0, 0.7)
    WALNUT = Material("walnut", (0.35, 0.22, 0.12), 0.0, 0.65)
    PINE = Material("pine", (0.75, 0.6, 0.4), 0.0, 0.75)
    MAHOGANY = Material("mahogany", (0.45, 0.2, 0.15), 0.0, 0.6)

    # Fabrics
    FABRIC_GRAY = Material("fabric_gray", (0.4, 0.4, 0.42), 0.0, 0.95)
    FABRIC_BLUE = Material("fabric_blue", (0.2, 0.35, 0.5), 0.0, 0.95)
    FABRIC_BEIGE = Material("fabric_beige", (0.7, 0.65, 0.55), 0.0, 0.95)
    LEATHER_BROWN = Material("leather_brown", (0.4, 0.25, 0.15), 0.0, 0.6)
    LEATHER_BLACK = Material("leather_black", (0.1, 0.1, 0.1), 0.0, 0.5)

    # Metals
    CHROME = Material("chrome", (0.9, 0.9, 0.9), 0.9, 0.2)
    BRUSHED_STEEL = Material("brushed_steel", (0.6, 0.6, 0.62), 0.85, 0.4)
    BLACK_METAL = Material("black_metal", (0.15, 0.15, 0.15), 0.7, 0.5)

    # Other
    GLASS = Material("glass", (0.9, 0.95, 1.0), 0.0, 0.05)
    MARBLE_WHITE = Material("marble_white", (0.95, 0.93, 0.9), 0.0, 0.3)
    PLASTIC_WHITE = Material("plastic_white", (0.95, 0.95, 0.95), 0.0, 0.4)


@dataclass
class FurnitureItem:
    """
    Definition of a furniture type in the catalog.

    This is the template/blueprint, not a placed instance.
    """
    id: str                                  # Unique identifier
    name: str                                # Display name
    category: FurnitureCategory
    furniture_type: str                      # e.g., "dining_chair", "sofa_3seat"
    dimensions: Dimensions
    style: FurnitureStyle = FurnitureStyle.MODERN

    # Materials (can have multiple for different parts)
    primary_material: Material = field(default_factory=lambda: Materials.OAK)
    secondary_material: Optional[Material] = None  # e.g., cushion material

    # Description for AI generation (LOD3+)
    description: Optional[str] = None

    # Reference image path for AI generation
    reference_image: Optional[str] = None

    # Tags for searching/filtering
    tags: List[str] = field(default_factory=list)

    # Clearance requirements (mm) - space needed around furniture
    clearance_front: float = 0
    clearance_back: float = 0
    clearance_left: float = 0
    clearance_right: float = 0

    # Generated geometry cache (per LOD)
    _geometry_cache: Dict[LODLevel, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "furniture_type": self.furniture_type,
            "dimensions": self.dimensions.to_dict(),
            "style": self.style.value,
            "primary_material": self.primary_material.to_dict(),
            "secondary_material": self.secondary_material.to_dict() if self.secondary_material else None,
            "description": self.description,
            "reference_image": self.reference_image,
            "tags": self.tags,
            "clearance": {
                "front": self.clearance_front,
                "back": self.clearance_back,
                "left": self.clearance_left,
                "right": self.clearance_right,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FurnitureItem":
        clearance = data.get("clearance", {})
        return cls(
            id=data["id"],
            name=data["name"],
            category=FurnitureCategory(data["category"]),
            furniture_type=data["furniture_type"],
            dimensions=Dimensions.from_dict(data["dimensions"]),
            style=FurnitureStyle(data.get("style", "modern")),
            primary_material=Material.from_dict(data["primary_material"]) if "primary_material" in data else Materials.OAK,
            secondary_material=Material.from_dict(data["secondary_material"]) if data.get("secondary_material") else None,
            description=data.get("description"),
            reference_image=data.get("reference_image"),
            tags=data.get("tags", []),
            clearance_front=clearance.get("front", 0),
            clearance_back=clearance.get("back", 0),
            clearance_left=clearance.get("left", 0),
            clearance_right=clearance.get("right", 0),
        )


@dataclass
class FurniturePlacement:
    """
    A placed instance of furniture in the building.

    References a FurnitureItem from the catalog and adds
    position/rotation for placement.
    """
    id: str                          # Unique instance ID
    furniture_id: str                # Reference to FurnitureItem.id
    room_id: Optional[str] = None    # Room this furniture is in

    # Position in mm (building coordinates)
    position_x: float = 0
    position_y: float = 0            # Floor level (0 = ground floor)
    position_z: float = 0

    # Rotation in degrees (around Y-axis)
    rotation: float = 0

    # Optional instance-level overrides
    custom_dimensions: Optional[Dimensions] = None
    custom_material: Optional[Material] = None

    # Metadata
    label: Optional[str] = None      # User-assigned label
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "furniture_id": self.furniture_id,
            "room_id": self.room_id,
            "position": {
                "x": self.position_x,
                "y": self.position_y,
                "z": self.position_z,
            },
            "rotation": self.rotation,
            "custom_dimensions": self.custom_dimensions.to_dict() if self.custom_dimensions else None,
            "custom_material": self.custom_material.to_dict() if self.custom_material else None,
            "label": self.label,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FurniturePlacement":
        pos = data.get("position", {})
        return cls(
            id=data["id"],
            furniture_id=data["furniture_id"],
            room_id=data.get("room_id"),
            position_x=pos.get("x", 0),
            position_y=pos.get("y", 0),
            position_z=pos.get("z", 0),
            rotation=data.get("rotation", 0),
            custom_dimensions=Dimensions.from_dict(data["custom_dimensions"]) if data.get("custom_dimensions") else None,
            custom_material=Material.from_dict(data["custom_material"]) if data.get("custom_material") else None,
            label=data.get("label"),
            notes=data.get("notes"),
        )

    @staticmethod
    def create(furniture_id: str, x: float, z: float, rotation: float = 0, room_id: str = None) -> "FurniturePlacement":
        """Convenience method to create a new placement."""
        return FurniturePlacement(
            id=str(uuid.uuid4()),
            furniture_id=furniture_id,
            room_id=room_id,
            position_x=x,
            position_y=0,
            position_z=z,
            rotation=rotation,
        )


# ============================================================================
# GEOMETRY OUTPUT TYPES (for Vulkan)
# ============================================================================

@dataclass
class Vertex:
    """
    Single vertex matching Vulkan vertex format.

    Matches arch::Vertex in types.hpp:
    - position: vec3
    - normal: vec3
    - color: vec3
    - texCoord: vec2
    - stress: f32
    """
    position: Tuple[float, float, float]     # x, y, z
    normal: Tuple[float, float, float]       # nx, ny, nz
    color: Tuple[float, float, float]        # r, g, b
    tex_coord: Tuple[float, float] = (0.0, 0.0)  # u, v
    stress: float = 0.0

    def to_floats(self) -> List[float]:
        """Convert to flat list of floats for buffer."""
        return [
            *self.position,  # 3 floats
            *self.normal,    # 3 floats
            *self.color,     # 3 floats
            *self.tex_coord, # 2 floats
            self.stress,     # 1 float
        ]  # Total: 12 floats per vertex


@dataclass
class Mesh:
    """
    Generated mesh geometry.

    Contains vertices and indices ready for Vulkan rendering.
    """
    vertices: List[Vertex]
    indices: List[int]            # Triangle indices (3 per triangle)

    def get_vertex_buffer(self) -> List[float]:
        """Get flat vertex data for VkBuffer."""
        buffer = []
        for v in self.vertices:
            buffer.extend(v.to_floats())
        return buffer

    def get_index_buffer(self) -> List[int]:
        """Get index data for VkBuffer."""
        return self.indices

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.indices) // 3


@dataclass
class LODGeometry:
    """
    Geometry for a specific LOD level.
    """
    lod: LODLevel
    mesh: Optional[Mesh] = None           # 3D mesh (LOD1+)
    svg_symbol: Optional[str] = None      # 2D SVG symbol (LOD0)
    bounding_box: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None  # (min, max)
