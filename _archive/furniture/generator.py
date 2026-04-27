"""
Furniture geometry generator.

Generates geometry at different LOD levels:
- LOD0: 2D SVG symbols for floor plans
- LOD1: 3D bounding boxes (distant view)
- LOD2: 3D composed primitives (mid-range)
- LOD3: AI-generated base mesh (no materials, for iteration)
- LOD4: AI-generated mesh with materials
- LOD5: Reserved for documentation/reference

All dimensions in millimeters.
"""
import math
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass

from furniture.models import (
    FurnitureItem,
    FurniturePlacement,
    FurnitureCategory,
    LODLevel,
    LODGeometry,
    Dimensions,
    Material,
    Mesh,
    Vertex,
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
from furniture.catalog import FurnitureCatalog, get_default_catalog

# AI generation (optional, for LOD3/LOD4)
_AI_AVAILABLE = False
try:
    from furniture.ai_generator import (
        AIFurnitureGenerator,
        get_ai_generator,
        GenerationQuality,
    )
    from furniture.backends.lm_studio import LMStudioBackend
    _AI_AVAILABLE = True
except ImportError:
    AIFurnitureGenerator = None
    get_ai_generator = None
    GenerationQuality = None
    LMStudioBackend = None


class FurnitureGenerator:
    """
    Generates furniture geometry at multiple LOD levels.

    Supports parametric generation based on furniture dimensions
    and style, with material-based coloring.
    """

    def __init__(
        self,
        catalog: Optional[FurnitureCatalog] = None,
        lm_studio_url: str = "http://localhost:1234/v1",
    ):
        self.catalog = catalog or get_default_catalog()
        self._template_registry: Dict[str, Callable] = {}
        self._register_default_templates()

        # Initialize AI generator for LOD3/LOD4
        self._ai_generator: Optional[AIFurnitureGenerator] = None
        if _AI_AVAILABLE:
            self._ai_generator = get_ai_generator()
            # Register LM Studio backend
            backend = LMStudioBackend(base_url=lm_studio_url)
            self._ai_generator.register_backend(backend)

    def _register_default_templates(self):
        """Register built-in parametric templates."""
        # Seating
        self._template_registry["dining_chair"] = self._generate_dining_chair
        self._template_registry["office_chair"] = self._generate_office_chair
        self._template_registry["sofa_3seat"] = self._generate_sofa
        self._template_registry["sofa_2seat"] = self._generate_sofa
        self._template_registry["armchair"] = self._generate_armchair

        # Tables
        self._template_registry["dining_table"] = self._generate_table
        self._template_registry["coffee_table"] = self._generate_table
        self._template_registry["side_table"] = self._generate_table
        self._template_registry["desk"] = self._generate_desk

        # Beds
        self._template_registry["bed_queen"] = self._generate_bed
        self._template_registry["bed_king"] = self._generate_bed
        self._template_registry["bed_single"] = self._generate_bed

        # Storage
        self._template_registry["wardrobe"] = self._generate_wardrobe
        self._template_registry["bookshelf"] = self._generate_bookshelf
        self._template_registry["dresser"] = self._generate_dresser
        self._template_registry["nightstand"] = self._generate_nightstand

        # Fixtures
        self._template_registry["toilet"] = self._generate_toilet
        self._template_registry["sink"] = self._generate_sink
        self._template_registry["bathtub"] = self._generate_bathtub
        self._template_registry["shower"] = self._generate_shower

        # Appliances
        self._template_registry["refrigerator"] = self._generate_appliance_box
        self._template_registry["stove"] = self._generate_stove
        self._template_registry["dishwasher"] = self._generate_appliance_box
        self._template_registry["washing_machine"] = self._generate_appliance_box

    def register_template(self, furniture_type: str, generator_fn: Callable):
        """Register a custom parametric template."""
        self._template_registry[furniture_type] = generator_fn

    def generate(
        self,
        item: FurnitureItem,
        lod: LODLevel,
        placement: Optional[FurniturePlacement] = None,
    ) -> LODGeometry:
        """
        Generate geometry for a furniture item at a specific LOD.

        Args:
            item: Furniture item definition
            lod: Level of detail to generate
            placement: Optional placement for transform (if None, generates at origin)

        Returns:
            LODGeometry with mesh and/or SVG symbol
        """
        # Check cache first
        if lod in item._geometry_cache:
            geometry = item._geometry_cache[lod]
            if placement:
                return self._apply_placement(geometry, placement)
            return geometry

        # Generate based on LOD
        if lod == LODLevel.LOD0:
            geometry = self._generate_lod0(item)
        elif lod == LODLevel.LOD1:
            geometry = self._generate_lod1(item)
        elif lod == LODLevel.LOD2:
            geometry = self._generate_lod2(item)
        elif lod == LODLevel.LOD3:
            geometry = self._generate_lod3(item)
        elif lod == LODLevel.LOD4:
            geometry = self._generate_lod4(item)
        else:
            # LOD5 is documentation, fallback to LOD4
            geometry = self._generate_lod4(item)

        # Cache the result
        item._geometry_cache[lod] = geometry

        # Apply placement transform if provided
        if placement:
            return self._apply_placement(geometry, placement)

        return geometry

    def _apply_placement(
        self,
        geometry: LODGeometry,
        placement: FurniturePlacement
    ) -> LODGeometry:
        """Apply placement transform to geometry."""
        if geometry.mesh is None:
            return geometry

        transformed_mesh = transform_mesh(
            geometry.mesh,
            translate=(placement.position_x, placement.position_y, placement.position_z),
            rotate_y=placement.rotation,
        )

        return LODGeometry(
            lod=geometry.lod,
            mesh=transformed_mesh,
            svg_symbol=geometry.svg_symbol,
            bounding_box=geometry.bounding_box,
        )

    # =========================================================================
    # LOD0: 2D SVG Symbols
    # =========================================================================

    def _generate_lod0(self, item: FurnitureItem) -> LODGeometry:
        """Generate 2D SVG symbol for floor plan view."""
        d = item.dimensions
        category = item.category

        # SVG uses top-down view, so we use width (X) and depth (Z)
        # Centered at origin, will be transformed when placed
        svg = self._get_svg_symbol(item)

        return LODGeometry(
            lod=LODLevel.LOD0,
            mesh=None,
            svg_symbol=svg,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    def _get_svg_symbol(self, item: FurnitureItem) -> str:
        """Get appropriate SVG symbol based on furniture type."""
        d = item.dimensions
        w, h = d.width, d.depth  # In plan view, depth becomes the Y axis

        # Common styles
        stroke = "stroke='#333' stroke-width='2'"
        fill_light = "fill='#f5f5f5'"
        fill_medium = "fill='#e0e0e0'"
        fill_dark = "fill='#bbb'"

        ftype = item.furniture_type

        if ftype == "dining_chair":
            return self._svg_chair(w, h, stroke, fill_light, fill_medium)
        elif ftype == "office_chair":
            return self._svg_office_chair(w, h, stroke, fill_light, fill_medium)
        elif ftype in ("sofa_3seat", "sofa_2seat"):
            return self._svg_sofa(w, h, stroke, fill_light, fill_medium)
        elif ftype == "armchair":
            return self._svg_armchair(w, h, stroke, fill_light, fill_medium)
        elif ftype in ("dining_table", "coffee_table", "desk"):
            return self._svg_table(w, h, stroke, fill_light)
        elif ftype == "side_table":
            return self._svg_round_table(w, stroke, fill_light)
        elif ftype in ("bed_queen", "bed_king", "bed_single"):
            return self._svg_bed(w, h, stroke, fill_light, fill_medium)
        elif ftype == "wardrobe":
            return self._svg_wardrobe(w, h, stroke, fill_light)
        elif ftype == "bookshelf":
            return self._svg_bookshelf(w, h, stroke, fill_light)
        elif ftype in ("dresser", "nightstand"):
            return self._svg_dresser(w, h, stroke, fill_light)
        elif ftype == "toilet":
            return self._svg_toilet(w, h, stroke, fill_light)
        elif ftype == "sink":
            return self._svg_sink(w, h, stroke, fill_light)
        elif ftype == "bathtub":
            return self._svg_bathtub(w, h, stroke, fill_light)
        elif ftype == "shower":
            return self._svg_shower(w, h, stroke, fill_light)
        elif ftype == "refrigerator":
            return self._svg_refrigerator(w, h, stroke, fill_light)
        elif ftype == "stove":
            return self._svg_stove(w, h, stroke, fill_light)
        else:
            # Default: simple rectangle
            return f"<rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill_light}/>"

    def _svg_chair(self, w: float, h: float, stroke: str, fill_light: str, fill_medium: str) -> str:
        """Generate chair SVG symbol."""
        seat_depth = h * 0.6
        back_depth = h * 0.15
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{back_depth}' {stroke} {fill_medium}/>
            <rect x='{-w/2}' y='{-h/2 + back_depth}' width='{w}' height='{seat_depth}' {stroke} {fill_light}/>
        </g>"""

    def _svg_office_chair(self, w: float, h: float, stroke: str, fill_light: str, fill_medium: str) -> str:
        """Generate office chair SVG symbol (with wheels indicator)."""
        seat_r = min(w, h) * 0.35
        return f"""<g>
            <circle cx='0' cy='0' r='{seat_r}' {stroke} {fill_light}/>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h*0.2}' {stroke} {fill_medium}/>
            <circle cx='{-w*0.35}' cy='{h*0.35}' r='{w*0.06}' fill='#666'/>
            <circle cx='{w*0.35}' cy='{h*0.35}' r='{w*0.06}' fill='#666'/>
            <circle cx='{-w*0.35}' cy='{-h*0.35}' r='{w*0.06}' fill='#666'/>
            <circle cx='{w*0.35}' cy='{-h*0.35}' r='{w*0.06}' fill='#666'/>
        </g>"""

    def _svg_sofa(self, w: float, h: float, stroke: str, fill_light: str, fill_medium: str) -> str:
        """Generate sofa SVG symbol."""
        arm_w = w * 0.08
        back_d = h * 0.2
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{back_d}' {stroke} {fill_medium}/>
            <rect x='{-w/2}' y='{-h/2}' width='{arm_w}' height='{h}' {stroke} {fill_medium}/>
            <rect x='{w/2 - arm_w}' y='{-h/2}' width='{arm_w}' height='{h}' {stroke} {fill_medium}/>
            <rect x='{-w/2 + arm_w}' y='{-h/2 + back_d}' width='{w - 2*arm_w}' height='{h - back_d}' {stroke} {fill_light}/>
        </g>"""

    def _svg_armchair(self, w: float, h: float, stroke: str, fill_light: str, fill_medium: str) -> str:
        """Generate armchair SVG symbol."""
        arm_w = w * 0.15
        back_d = h * 0.2
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{back_d}' {stroke} {fill_medium}/>
            <rect x='{-w/2}' y='{-h/2}' width='{arm_w}' height='{h}' {stroke} {fill_medium}/>
            <rect x='{w/2 - arm_w}' y='{-h/2}' width='{arm_w}' height='{h}' {stroke} {fill_medium}/>
            <rect x='{-w/2 + arm_w}' y='{-h/2 + back_d}' width='{w - 2*arm_w}' height='{h - back_d}' {stroke} {fill_light}/>
        </g>"""

    def _svg_table(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate table SVG symbol."""
        leg_size = min(w, h) * 0.08
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <rect x='{-w/2 + leg_size/2}' y='{-h/2 + leg_size/2}' width='{leg_size}' height='{leg_size}' fill='#999'/>
            <rect x='{w/2 - leg_size*1.5}' y='{-h/2 + leg_size/2}' width='{leg_size}' height='{leg_size}' fill='#999'/>
            <rect x='{-w/2 + leg_size/2}' y='{h/2 - leg_size*1.5}' width='{leg_size}' height='{leg_size}' fill='#999'/>
            <rect x='{w/2 - leg_size*1.5}' y='{h/2 - leg_size*1.5}' width='{leg_size}' height='{leg_size}' fill='#999'/>
        </g>"""

    def _svg_round_table(self, diameter: float, stroke: str, fill: str) -> str:
        """Generate round table SVG symbol."""
        r = diameter / 2
        return f"<circle cx='0' cy='0' r='{r}' {stroke} {fill}/>"

    def _svg_bed(self, w: float, h: float, stroke: str, fill_light: str, fill_medium: str) -> str:
        """Generate bed SVG symbol."""
        headboard_h = h * 0.08
        pillow_h = h * 0.15
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{headboard_h}' {stroke} {fill_medium}/>
            <rect x='{-w/2}' y='{-h/2 + headboard_h}' width='{w}' height='{h - headboard_h}' {stroke} {fill_light}/>
            <rect x='{-w/2 + w*0.05}' y='{-h/2 + headboard_h + h*0.02}' width='{w*0.4}' height='{pillow_h}' {stroke} fill='#fff'/>
            <rect x='{w/2 - w*0.45}' y='{-h/2 + headboard_h + h*0.02}' width='{w*0.4}' height='{pillow_h}' {stroke} fill='#fff'/>
        </g>"""

    def _svg_wardrobe(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate wardrobe SVG symbol."""
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <line x1='0' y1='{-h/2}' x2='0' y2='{h/2}' stroke='#666' stroke-width='1'/>
        </g>"""

    def _svg_bookshelf(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate bookshelf SVG symbol."""
        return f"<rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>"

    def _svg_dresser(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate dresser SVG symbol."""
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <circle cx='{-w*0.25}' cy='0' r='{min(w,h)*0.05}' fill='#888'/>
            <circle cx='{w*0.25}' cy='0' r='{min(w,h)*0.05}' fill='#888'/>
        </g>"""

    def _svg_toilet(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate toilet SVG symbol."""
        tank_h = h * 0.25
        bowl_h = h - tank_h
        bowl_w = w * 0.9
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{tank_h}' {stroke} {fill}/>
            <ellipse cx='0' cy='{-h/2 + tank_h + bowl_h/2}' rx='{bowl_w/2}' ry='{bowl_h/2}' {stroke} {fill}/>
        </g>"""

    def _svg_sink(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate sink SVG symbol."""
        return f"""<g>
            <ellipse cx='0' cy='0' rx='{w/2}' ry='{h/2}' {stroke} {fill}/>
            <circle cx='0' cy='0' r='{min(w,h)*0.1}' fill='#666'/>
        </g>"""

    def _svg_bathtub(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate bathtub SVG symbol."""
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' rx='{w*0.1}' ry='{w*0.1}' {stroke} {fill}/>
            <ellipse cx='0' cy='{-h*0.35}' rx='{w*0.15}' ry='{w*0.08}' fill='#ccc'/>
        </g>"""

    def _svg_shower(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate shower SVG symbol."""
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <circle cx='0' cy='0' r='{min(w,h)*0.3}' stroke='#999' stroke-width='1' fill='none' stroke-dasharray='4,4'/>
        </g>"""

    def _svg_refrigerator(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate refrigerator SVG symbol."""
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <line x1='{-w/2}' y1='{-h*0.1}' x2='{w/2}' y2='{-h*0.1}' stroke='#666' stroke-width='1'/>
        </g>"""

    def _svg_stove(self, w: float, h: float, stroke: str, fill: str) -> str:
        """Generate stove SVG symbol."""
        burner_r = min(w, h) * 0.12
        return f"""<g>
            <rect x='{-w/2}' y='{-h/2}' width='{w}' height='{h}' {stroke} {fill}/>
            <circle cx='{-w*0.25}' cy='{-h*0.25}' r='{burner_r}' stroke='#666' stroke-width='2' fill='none'/>
            <circle cx='{w*0.25}' cy='{-h*0.25}' r='{burner_r}' stroke='#666' stroke-width='2' fill='none'/>
            <circle cx='{-w*0.25}' cy='{h*0.25}' r='{burner_r}' stroke='#666' stroke-width='2' fill='none'/>
            <circle cx='{w*0.25}' cy='{h*0.25}' r='{burner_r}' stroke='#666' stroke-width='2' fill='none'/>
        </g>"""

    # =========================================================================
    # LOD1: Bounding Boxes
    # =========================================================================

    def _generate_lod1(self, item: FurnitureItem) -> LODGeometry:
        """Generate simple bounding box mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        mesh = create_box(d.width, d.height, d.depth, color=color)

        return LODGeometry(
            lod=LODLevel.LOD1,
            mesh=mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    # =========================================================================
    # LOD2: Composed Primitives
    # =========================================================================

    def _generate_lod2(self, item: FurnitureItem) -> LODGeometry:
        """Generate detailed mesh using composed primitives."""
        # Look up template generator
        gen_fn = self._template_registry.get(item.furniture_type)

        if gen_fn:
            mesh = gen_fn(item)
        else:
            # Fallback to bounding box
            return self._generate_lod1(item)

        d = item.dimensions
        return LODGeometry(
            lod=LODLevel.LOD2,
            mesh=mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    # =========================================================================
    # LOD3: AI-Generated Base Mesh (No Materials)
    # =========================================================================

    def _generate_lod3(
        self,
        item: FurnitureItem,
        reference_image: Optional[str] = None,
    ) -> LODGeometry:
        """
        Generate AI-created base mesh without materials.

        Uses VL model to analyze furniture and create detailed geometry.
        Falls back to LOD2 if AI is not available.
        """
        if self._ai_generator is None or not self._ai_generator.get_available_backends():
            # Fallback to LOD2 if AI not available
            return self._generate_lod2(item)

        # Use reference image from item if not provided
        ref_image = reference_image or item.reference_image

        result = self._ai_generator.generate_lod3(
            item,
            reference_image=ref_image,
            quality=GenerationQuality.STANDARD,
        )

        if not result.success or result.mesh is None:
            # Fallback to LOD2 on failure
            print(f"[FurnitureGen] LOD3 generation failed: {result.error_message}")
            return self._generate_lod2(item)

        d = item.dimensions
        return LODGeometry(
            lod=LODLevel.LOD3,
            mesh=result.mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    def generate_lod3_with_image(
        self,
        item: FurnitureItem,
        image_path: str,
        quality: str = "standard",
    ) -> LODGeometry:
        """
        Generate LOD3 with a specific reference image.

        Args:
            item: Furniture item definition
            image_path: Path to reference image
            quality: "draft", "standard", or "high"

        Returns:
            LODGeometry with AI-generated mesh
        """
        if self._ai_generator is None:
            return self._generate_lod2(item)

        quality_map = {
            "draft": GenerationQuality.DRAFT,
            "standard": GenerationQuality.STANDARD,
            "high": GenerationQuality.HIGH,
        }
        gen_quality = quality_map.get(quality, GenerationQuality.STANDARD)

        result = self._ai_generator.generate_lod3(
            item,
            reference_image=image_path,
            quality=gen_quality,
        )

        if not result.success or result.mesh is None:
            return self._generate_lod2(item)

        d = item.dimensions
        return LODGeometry(
            lod=LODLevel.LOD3,
            mesh=result.mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    # =========================================================================
    # LOD4: AI-Generated Mesh with Materials
    # =========================================================================

    def _generate_lod4(
        self,
        item: FurnitureItem,
        reference_image: Optional[str] = None,
    ) -> LODGeometry:
        """
        Generate AI-created mesh with materials.

        Uses VL model to create detailed geometry with PBR materials.
        Falls back to LOD3 if AI is not available.
        """
        if self._ai_generator is None or not self._ai_generator.get_available_backends():
            # Fallback to LOD3 if AI not available
            return self._generate_lod3(item, reference_image)

        # Use reference image from item if not provided
        ref_image = reference_image or item.reference_image

        # Try to get LOD3 mesh first for better consistency
        lod3_geometry = self._generate_lod3(item, ref_image)
        lod3_mesh = lod3_geometry.mesh if lod3_geometry else None

        result = self._ai_generator.generate_lod4(
            item,
            reference_image=ref_image,
            quality=GenerationQuality.STANDARD,
            lod3_mesh=lod3_mesh,
        )

        if not result.success or result.mesh is None:
            # Fallback to LOD3 on failure
            print(f"[FurnitureGen] LOD4 generation failed: {result.error_message}")
            return self._generate_lod3(item, reference_image)

        d = item.dimensions
        return LODGeometry(
            lod=LODLevel.LOD4,
            mesh=result.mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    def generate_lod4_with_image(
        self,
        item: FurnitureItem,
        image_path: str,
        quality: str = "standard",
    ) -> LODGeometry:
        """
        Generate LOD4 with a specific reference image.

        Args:
            item: Furniture item definition
            image_path: Path to reference image
            quality: "draft", "standard", or "high"

        Returns:
            LODGeometry with AI-generated mesh and materials
        """
        if self._ai_generator is None:
            return self._generate_lod3(item, image_path)

        quality_map = {
            "draft": GenerationQuality.DRAFT,
            "standard": GenerationQuality.STANDARD,
            "high": GenerationQuality.HIGH,
        }
        gen_quality = quality_map.get(quality, GenerationQuality.STANDARD)

        result = self._ai_generator.generate_lod4(
            item,
            reference_image=image_path,
            quality=gen_quality,
        )

        if not result.success or result.mesh is None:
            return self._generate_lod3(item, image_path)

        d = item.dimensions
        return LODGeometry(
            lod=LODLevel.LOD4,
            mesh=result.mesh,
            svg_symbol=None,
            bounding_box=(
                (-d.width/2, 0, -d.depth/2),
                (d.width/2, d.height, d.depth/2)
            ),
        )

    # =========================================================================
    # AI Generation Utilities
    # =========================================================================

    def is_ai_available(self) -> bool:
        """Check if AI generation is available."""
        return (
            self._ai_generator is not None and
            len(self._ai_generator.get_available_backends()) > 0
        )

    def get_ai_backends(self) -> List[str]:
        """Get list of available AI backends."""
        if self._ai_generator is None:
            return []
        return self._ai_generator.get_available_backends()

    # =========================================================================
    # Parametric Templates (LOD2)
    # =========================================================================

    def _generate_dining_chair(self, item: FurnitureItem) -> Mesh:
        """Generate a dining chair mesh."""
        d = item.dimensions
        frame_color = item.primary_material.base_color
        cushion_color = item.secondary_material.base_color if item.secondary_material else frame_color

        seat_h = d.seat_height or 450
        back_h = d.back_height or (d.height - seat_h)
        leg_w = d.leg_width or 40

        meshes = []

        # Four legs
        for x in [-1, 1]:
            for z in [-1, 1]:
                leg = create_box(
                    leg_w, seat_h, leg_w,
                    offset=(x * (d.width/2 - leg_w), 0, z * (d.depth/2 - leg_w)),
                    color=frame_color,
                )
                meshes.append(leg)

        # Seat
        seat = create_box(
            d.width - leg_w, 50, d.depth - leg_w,
            offset=(0, seat_h - 25, 0),
            color=cushion_color,
        )
        meshes.append(seat)

        # Back support (two vertical posts)
        back_w = leg_w
        for x in [-1, 1]:
            back_post = create_box(
                back_w, back_h, leg_w,
                offset=(x * (d.width/2 - leg_w), seat_h, -d.depth/2 + leg_w),
                color=frame_color,
            )
            meshes.append(back_post)

        # Back rest
        back_rest = create_box(
            d.width - leg_w * 2, back_h * 0.6, 20,
            offset=(0, seat_h + back_h * 0.5, -d.depth/2 + leg_w/2),
            color=frame_color,
        )
        meshes.append(back_rest)

        return merge_meshes(meshes)

    def _generate_office_chair(self, item: FurnitureItem) -> Mesh:
        """Generate an office chair mesh."""
        d = item.dimensions
        frame_color = item.primary_material.base_color
        cushion_color = item.secondary_material.base_color if item.secondary_material else (0.3, 0.3, 0.3)

        seat_h = d.seat_height or 450
        back_h = d.back_height or 500

        meshes = []

        # Base star (5 points)
        base_r = d.width * 0.4
        for i in range(5):
            angle = (2 * math.pi * i) / 5
            x = math.cos(angle) * base_r
            z = math.sin(angle) * base_r
            arm = create_box(base_r, 30, 40, offset=(x/2, 15, z/2), color=frame_color)
            arm = transform_mesh(arm, rotate_y=math.degrees(angle))
            meshes.append(arm)

        # Center post
        post = create_cylinder(40, seat_h - 50, segments=12, offset=(0, 30, 0), color=frame_color)
        meshes.append(post)

        # Seat
        seat = create_rounded_box(d.width * 0.85, 80, d.depth * 0.85, 30, offset=(0, seat_h - 40, 0), color=cushion_color)
        meshes.append(seat)

        # Back
        back = create_rounded_box(d.width * 0.8, back_h, 60, 20, offset=(0, seat_h + back_h/2, -d.depth * 0.35), color=cushion_color)
        meshes.append(back)

        # Arms (if present)
        if d.arm_height:
            arm_h = d.arm_height
            for x in [-1, 1]:
                arm_post = create_box(30, arm_h, 30, offset=(x * d.width * 0.4, seat_h, 0), color=frame_color)
                meshes.append(arm_post)
                arm_rest = create_box(30, 20, d.depth * 0.5, offset=(x * d.width * 0.4, seat_h + arm_h, d.depth * 0.1), color=frame_color)
                meshes.append(arm_rest)

        return merge_meshes(meshes)

    def _generate_sofa(self, item: FurnitureItem) -> Mesh:
        """Generate a sofa mesh."""
        d = item.dimensions
        fabric_color = item.primary_material.base_color
        frame_color = item.secondary_material.base_color if item.secondary_material else (0.4, 0.3, 0.2)

        seat_h = d.seat_height or 450
        arm_h = d.arm_height or 200
        back_h = d.back_height or 350
        arm_w = d.width * 0.08

        meshes = []

        # Base/feet
        foot_h = 80
        for x in [-1, 1]:
            for z in [-1, 1]:
                foot = create_box(60, foot_h, 60, offset=(x * (d.width/2 - 80), 0, z * (d.depth/2 - 80)), color=frame_color)
                meshes.append(foot)

        # Main seat frame
        frame = create_box(d.width, seat_h - 100, d.depth, offset=(0, foot_h + (seat_h - 100)/2, 0), color=frame_color)
        meshes.append(frame)

        # Seat cushion
        cushion_w = d.width - arm_w * 2
        seat_cushion = create_rounded_box(cushion_w, 100, d.depth - 100, 30, offset=(0, seat_h, d.depth * 0.05), color=fabric_color)
        meshes.append(seat_cushion)

        # Back cushion
        back_cushion = create_rounded_box(cushion_w, back_h, 150, 40, offset=(0, seat_h + back_h/2 + 50, -d.depth/2 + 100), color=fabric_color)
        meshes.append(back_cushion)

        # Arms
        for x in [-1, 1]:
            arm = create_rounded_box(arm_w * 2, seat_h + arm_h, d.depth - 50, 20, offset=(x * (d.width/2 - arm_w), (seat_h + arm_h)/2, 0), color=fabric_color)
            meshes.append(arm)

        return merge_meshes(meshes)

    def _generate_armchair(self, item: FurnitureItem) -> Mesh:
        """Generate an armchair mesh."""
        # Similar to sofa but single seat
        d = item.dimensions
        fabric_color = item.primary_material.base_color
        frame_color = (0.4, 0.3, 0.2)

        seat_h = d.seat_height or 450
        arm_h = d.arm_height or 200
        back_h = d.back_height or 400
        arm_w = d.width * 0.12

        meshes = []

        # Feet
        foot_h = 60
        for x in [-1, 1]:
            for z in [-1, 1]:
                foot = create_box(50, foot_h, 50, offset=(x * (d.width/2 - 70), 0, z * (d.depth/2 - 70)), color=frame_color)
                meshes.append(foot)

        # Frame
        frame_h = seat_h - foot_h - 50
        frame = create_box(d.width, frame_h, d.depth, offset=(0, foot_h + frame_h/2, 0), color=frame_color)
        meshes.append(frame)

        # Seat cushion
        cushion_w = d.width - arm_w * 2 - 40
        seat_cushion = create_rounded_box(cushion_w, 120, d.depth - 150, 40, offset=(0, seat_h, d.depth * 0.05), color=fabric_color)
        meshes.append(seat_cushion)

        # Back cushion
        back_cushion = create_rounded_box(cushion_w, back_h, 180, 50, offset=(0, seat_h + back_h/2 + 60, -d.depth/2 + 120), color=fabric_color)
        meshes.append(back_cushion)

        # Arms
        for x in [-1, 1]:
            arm = create_rounded_box(arm_w * 1.5, seat_h + arm_h, d.depth - 80, 25, offset=(x * (d.width/2 - arm_w), (seat_h + arm_h)/2, 0), color=fabric_color)
            meshes.append(arm)

        return merge_meshes(meshes)

    def _generate_table(self, item: FurnitureItem) -> Mesh:
        """Generate a table mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        top_thick = d.table_top_thickness or 30
        leg_w = d.leg_width or 60

        meshes = []

        # Table top
        top = create_box(d.width, top_thick, d.depth, offset=(0, d.height - top_thick/2, 0), color=color)
        meshes.append(top)

        # Four legs
        leg_h = d.height - top_thick
        inset = leg_w * 1.5
        for x in [-1, 1]:
            for z in [-1, 1]:
                leg = create_box(leg_w, leg_h, leg_w, offset=(x * (d.width/2 - inset), leg_h/2, z * (d.depth/2 - inset)), color=color)
                meshes.append(leg)

        return merge_meshes(meshes)

    def _generate_desk(self, item: FurnitureItem) -> Mesh:
        """Generate a desk mesh with panel legs."""
        d = item.dimensions
        top_color = item.primary_material.base_color
        frame_color = item.secondary_material.base_color if item.secondary_material else (0.5, 0.5, 0.55)

        top_thick = d.table_top_thickness or 30
        leg_w = 40

        meshes = []

        # Table top
        top = create_box(d.width, top_thick, d.depth, offset=(0, d.height - top_thick/2, 0), color=top_color)
        meshes.append(top)

        # Side panels (instead of legs)
        panel_h = d.height - top_thick
        panel_thick = 25
        for x in [-1, 1]:
            panel = create_box(panel_thick, panel_h, d.depth - 100, offset=(x * (d.width/2 - panel_thick), panel_h/2, 0), color=frame_color)
            meshes.append(panel)

        # Back panel (modesty panel)
        back_h = panel_h * 0.4
        back = create_box(d.width - panel_thick * 2, back_h, panel_thick, offset=(0, panel_h - back_h/2, -d.depth/2 + 80), color=frame_color)
        meshes.append(back)

        return merge_meshes(meshes)

    def _generate_bed(self, item: FurnitureItem) -> Mesh:
        """Generate a bed mesh."""
        d = item.dimensions
        frame_color = item.primary_material.base_color
        fabric_color = item.secondary_material.base_color if item.secondary_material else (0.9, 0.9, 0.9)

        headboard_h = d.back_height or 1100

        meshes = []

        # Base frame
        frame_h = d.height * 0.6
        frame = create_box(d.width, frame_h, d.depth, offset=(0, frame_h/2, 0), color=frame_color)
        meshes.append(frame)

        # Mattress
        mattress_h = d.height - frame_h
        mattress = create_rounded_box(d.width - 40, mattress_h, d.depth - 40, 30, offset=(0, frame_h + mattress_h/2, 0), color=fabric_color)
        meshes.append(mattress)

        # Headboard
        headboard = create_box(d.width, headboard_h - d.height, 40, offset=(0, d.height + (headboard_h - d.height)/2, -d.depth/2 + 20), color=frame_color)
        meshes.append(headboard)

        # Pillows
        pillow_w = d.width * 0.35
        pillow_h = 80
        pillow_d = 200
        for x in [-0.25, 0.25]:
            pillow = create_rounded_box(pillow_w, pillow_h, pillow_d, 30, offset=(x * d.width, d.height + pillow_h/2 + 20, -d.depth/2 + pillow_d/2 + 60), color=(1, 1, 1))
            meshes.append(pillow)

        return merge_meshes(meshes)

    def _generate_wardrobe(self, item: FurnitureItem) -> Mesh:
        """Generate a wardrobe mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Main body
        body = create_box(d.width, d.height, d.depth, offset=(0, d.height/2, 0), color=color)
        meshes.append(body)

        # Door line (cosmetic)
        door_inset = 10
        door_color = tuple(c * 0.9 for c in color)
        left_door = create_box(d.width/2 - 20, d.height - 40, door_inset, offset=(-d.width/4, d.height/2, d.depth/2 - door_inset), color=door_color)
        right_door = create_box(d.width/2 - 20, d.height - 40, door_inset, offset=(d.width/4, d.height/2, d.depth/2 - door_inset), color=door_color)
        meshes.append(left_door)
        meshes.append(right_door)

        return merge_meshes(meshes)

    def _generate_bookshelf(self, item: FurnitureItem) -> Mesh:
        """Generate a bookshelf mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Side panels
        panel_thick = 20
        for x in [-1, 1]:
            panel = create_box(panel_thick, d.height, d.depth, offset=(x * (d.width/2 - panel_thick/2), d.height/2, 0), color=color)
            meshes.append(panel)

        # Back panel
        back = create_box(d.width - panel_thick * 2, d.height, 10, offset=(0, d.height/2, -d.depth/2 + 5), color=color)
        meshes.append(back)

        # Shelves (4 shelves)
        shelf_thick = 20
        num_shelves = 5
        for i in range(num_shelves):
            y = (d.height / (num_shelves - 1)) * i
            shelf = create_box(d.width - panel_thick * 2, shelf_thick, d.depth - 20, offset=(0, y, 10), color=color)
            meshes.append(shelf)

        return merge_meshes(meshes)

    def _generate_dresser(self, item: FurnitureItem) -> Mesh:
        """Generate a dresser mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Main body
        body = create_box(d.width, d.height, d.depth, offset=(0, d.height/2, 0), color=color)
        meshes.append(body)

        # Drawer fronts
        drawer_h = d.height / 3 - 10
        drawer_color = tuple(c * 0.95 for c in color)
        for i in range(3):
            y = drawer_h/2 + i * (drawer_h + 10) + 5
            drawer = create_box(d.width - 20, drawer_h, 15, offset=(0, y, d.depth/2 - 7), color=drawer_color)
            meshes.append(drawer)

        return merge_meshes(meshes)

    def _generate_nightstand(self, item: FurnitureItem) -> Mesh:
        """Generate a nightstand mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Main body
        body = create_box(d.width, d.height, d.depth, offset=(0, d.height/2, 0), color=color)
        meshes.append(body)

        # Top drawer
        drawer_h = d.height * 0.35
        drawer_color = tuple(c * 0.95 for c in color)
        drawer = create_box(d.width - 20, drawer_h, 15, offset=(0, d.height - drawer_h/2 - 10, d.depth/2 - 7), color=drawer_color)
        meshes.append(drawer)

        return merge_meshes(meshes)

    def _generate_toilet(self, item: FurnitureItem) -> Mesh:
        """Generate a toilet mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Tank
        tank_h = d.height * 0.5
        tank_d = d.depth * 0.3
        tank = create_box(d.width * 0.8, tank_h, tank_d, offset=(0, d.height - tank_h/2, -d.depth/2 + tank_d/2), color=color)
        meshes.append(tank)

        # Bowl (simplified as rounded box)
        bowl_h = d.height - tank_h + 50
        bowl = create_rounded_box(d.width * 0.9, bowl_h, d.depth - tank_d, min(d.width, d.depth) * 0.2, offset=(0, bowl_h/2, d.depth * 0.1), color=color)
        meshes.append(bowl)

        return merge_meshes(meshes)

    def _generate_sink(self, item: FurnitureItem) -> Mesh:
        """Generate a sink mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Pedestal
        pedestal_w = d.width * 0.3
        pedestal = create_box(pedestal_w, d.height * 0.7, pedestal_w, offset=(0, d.height * 0.35, 0), color=color)
        meshes.append(pedestal)

        # Basin
        basin_h = d.height * 0.25
        basin = create_rounded_box(d.width, basin_h, d.depth, min(d.width, d.depth) * 0.15, offset=(0, d.height - basin_h/2, 0), color=color)
        meshes.append(basin)

        return merge_meshes(meshes)

    def _generate_bathtub(self, item: FurnitureItem) -> Mesh:
        """Generate a bathtub mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        meshes = []

        # Outer shell
        shell = create_rounded_box(d.width, d.height, d.depth, min(d.width, d.height) * 0.15, offset=(0, d.height/2, 0), color=color)
        meshes.append(shell)

        return merge_meshes(meshes)

    def _generate_shower(self, item: FurnitureItem) -> Mesh:
        """Generate a shower enclosure mesh."""
        d = item.dimensions
        frame_color = (0.7, 0.7, 0.75)
        glass_color = (0.9, 0.95, 1.0)

        meshes = []

        # Base
        base_h = 50
        base = create_box(d.width, base_h, d.depth, offset=(0, base_h/2, 0), color=(0.9, 0.9, 0.9))
        meshes.append(base)

        # Glass panels (represented as thin boxes)
        panel_thick = 10
        # Back panel
        back = create_box(d.width, d.height - base_h, panel_thick, offset=(0, base_h + (d.height - base_h)/2, -d.depth/2 + panel_thick/2), color=glass_color)
        meshes.append(back)
        # Side panel
        side = create_box(panel_thick, d.height - base_h, d.depth, offset=(-d.width/2 + panel_thick/2, base_h + (d.height - base_h)/2, 0), color=glass_color)
        meshes.append(side)

        # Frame posts
        for x in [-1, 1]:
            for z in [-1, 1]:
                if not (x == 1 and z == 1):  # Leave door opening
                    post = create_box(20, d.height - base_h, 20, offset=(x * (d.width/2 - 10), base_h + (d.height - base_h)/2, z * (d.depth/2 - 10)), color=frame_color)
                    meshes.append(post)

        return merge_meshes(meshes)

    def _generate_appliance_box(self, item: FurnitureItem) -> Mesh:
        """Generate a simple appliance box mesh."""
        d = item.dimensions
        color = item.primary_material.base_color

        return create_box(d.width, d.height, d.depth, offset=(0, d.height/2, 0), color=color)

    def _generate_stove(self, item: FurnitureItem) -> Mesh:
        """Generate a stove mesh."""
        d = item.dimensions
        color = item.primary_material.base_color
        burner_color = (0.2, 0.2, 0.2)

        meshes = []

        # Main body
        body = create_box(d.width, d.height, d.depth, offset=(0, d.height/2, 0), color=color)
        meshes.append(body)

        # Burners (4 cylinders)
        burner_r = min(d.width, d.depth) * 0.1
        burner_h = 20
        positions = [(-0.25, -0.25), (0.25, -0.25), (-0.25, 0.25), (0.25, 0.25)]
        for px, pz in positions:
            burner = create_cylinder(burner_r, burner_h, segments=12, offset=(px * d.width, d.height, pz * d.depth), color=burner_color)
            meshes.append(burner)

        return merge_meshes(meshes)


# Convenience functions
def generate_furniture_mesh(
    item_id: str,
    lod: LODLevel = LODLevel.LOD2,
    catalog: Optional[FurnitureCatalog] = None,
) -> Optional[Mesh]:
    """
    Generate mesh for a furniture item by ID.

    Args:
        item_id: Furniture catalog ID
        lod: Level of detail
        catalog: Optional catalog (uses default if not provided)

    Returns:
        Generated mesh or None if item not found
    """
    cat = catalog or get_default_catalog()
    item = cat.get(item_id)
    if item is None:
        return None

    generator = FurnitureGenerator(cat)
    geometry = generator.generate(item, lod)
    return geometry.mesh


def generate_furniture_svg(
    item_id: str,
    catalog: Optional[FurnitureCatalog] = None,
) -> Optional[str]:
    """
    Generate SVG symbol for a furniture item by ID.

    Args:
        item_id: Furniture catalog ID
        catalog: Optional catalog (uses default if not provided)

    Returns:
        SVG symbol string or None if item not found
    """
    cat = catalog or get_default_catalog()
    item = cat.get(item_id)
    if item is None:
        return None

    generator = FurnitureGenerator(cat)
    geometry = generator.generate(item, LODLevel.LOD0)
    return geometry.svg_symbol
