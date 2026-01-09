"""
Furniture module for ArchEngine CAD.

Provides parametric furniture generation with multi-LOD support:
- LOD0: 2D plan symbols
- LOD1: Bounding boxes (distant 3D)
- LOD2: Composed primitives (mid-range 3D)
- LOD3+: AI-generated detailed meshes (future)
"""
from furniture.models import (
    FurnitureCategory,
    FurnitureStyle,
    FurnitureItem,
    FurniturePlacement,
    LODLevel,
    LODGeometry,
    Dimensions,
    Material,
    Materials,
    Vertex,
    Mesh,
)
from furniture.catalog import FurnitureCatalog, get_default_catalog
from furniture.generator import (
    FurnitureGenerator,
    generate_furniture_mesh,
    generate_furniture_svg,
)
from furniture.primitives import (
    create_box,
    create_cylinder,
    create_plane,
    create_wedge,
    create_rounded_box,
    merge_meshes,
    transform_mesh,
)

__all__ = [
    # Models
    "FurnitureCategory",
    "FurnitureStyle",
    "FurnitureItem",
    "FurniturePlacement",
    "LODLevel",
    "LODGeometry",
    "Dimensions",
    "Material",
    "Materials",
    "Vertex",
    "Mesh",
    # Catalog
    "FurnitureCatalog",
    "get_default_catalog",
    # Generator
    "FurnitureGenerator",
    "generate_furniture_mesh",
    "generate_furniture_svg",
    # Primitives
    "create_box",
    "create_cylinder",
    "create_plane",
    "create_wedge",
    "create_rounded_box",
    "merge_meshes",
    "transform_mesh",
]
