# assemblies.py
# Layer-based building assemblies for realistic section details
#
# Supports walls, floors, roofs with individual material layers
# Enables accurate thermal analysis and architectural detail generation

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class MaterialCategory(Enum):
    """Material categories for hatching/rendering"""
    WOOD = "wood"
    CONCRETE = "concrete"
    MASONRY = "masonry"
    INSULATION_BATT = "insulation_batt"
    INSULATION_RIGID = "insulation_rigid"
    INSULATION_SPRAY = "insulation_spray"
    GYPSUM = "gypsum"
    SHEATHING = "sheathing"
    MEMBRANE = "membrane"
    METAL = "metal"
    AIR_GAP = "air_gap"
    FINISH = "finish"
    FLOORING = "flooring"
    ROOFING = "roofing"
    EARTH = "earth"


@dataclass
class Material:
    """Material with thermal and visual properties"""
    name: str
    category: MaterialCategory
    r_value_per_inch: float  # R/inch
    density_pcf: float       # lb/ft³
    specific_heat: float     # BTU/(lb·°F)
    vapor_permeance: float   # perms (gr/h·ft²·inHg)

    # Visual properties for rendering
    color: str               # Hex color
    hatch_pattern: str       # Pattern name for section cuts

    @classmethod
    def drywall_half(cls):
        """1/2\" drywall (gypsum board)"""
        return cls("1/2\" Drywall", MaterialCategory.GYPSUM,
                   0.45, 50, 0.26, 50.0, "#f5f5f4", "dots")

    @classmethod
    def drywall_5_8(cls):
        """5/8\" drywall (Type X)"""
        return cls("5/8\" Type X Drywall", MaterialCategory.GYPSUM,
                   0.56, 50, 0.26, 50.0, "#e7e5e4", "dots")

    @classmethod
    def fiberglass_batt(cls):
        """Fiberglass batt insulation"""
        return cls("Fiberglass Batt", MaterialCategory.INSULATION_BATT,
                   3.2, 0.5, 0.2, 120.0, "#fef08a", "wavy")

    @classmethod
    def mineral_wool(cls):
        """Mineral wool batt insulation"""
        return cls("Mineral Wool", MaterialCategory.INSULATION_BATT,
                   3.7, 2.0, 0.2, 80.0, "#fde047", "wavy")

    @classmethod
    def cellulose(cls):
        """Dense-pack cellulose"""
        return cls("Dense-Pack Cellulose", MaterialCategory.INSULATION_BATT,
                   3.5, 3.5, 0.33, 60.0, "#a3a3a3", "stipple")

    @classmethod
    def xps_foam(cls):
        """XPS rigid foam (blue/pink board)"""
        return cls("XPS Rigid Foam", MaterialCategory.INSULATION_RIGID,
                   5.0, 1.5, 0.29, 1.0, "#38bdf8", "solid")

    @classmethod
    def eps_foam(cls):
        """EPS rigid foam (white beadboard)"""
        return cls("EPS Rigid Foam", MaterialCategory.INSULATION_RIGID,
                   3.8, 1.0, 0.29, 3.5, "#e5e5e5", "circles")

    @classmethod
    def polyiso(cls):
        """Polyisocyanurate rigid foam"""
        return cls("Polyiso Foam", MaterialCategory.INSULATION_RIGID,
                   6.0, 2.0, 0.24, 1.5, "#fcd34d", "solid")

    @classmethod
    def spray_foam_closed(cls):
        """Closed-cell spray foam"""
        return cls("Closed-Cell Spray Foam", MaterialCategory.INSULATION_SPRAY,
                   6.5, 2.0, 0.25, 1.0, "#a78bfa", "speckle")

    @classmethod
    def spray_foam_open(cls):
        """Open-cell spray foam"""
        return cls("Open-Cell Spray Foam", MaterialCategory.INSULATION_SPRAY,
                   3.7, 0.5, 0.25, 50.0, "#c4b5fd", "speckle")

    @classmethod
    def osb(cls):
        """OSB sheathing"""
        return cls("OSB Sheathing", MaterialCategory.SHEATHING,
                   1.25, 40, 0.45, 2.0, "#d6b88a", "wood_cross")

    @classmethod
    def plywood(cls):
        """Plywood sheathing"""
        return cls("Plywood Sheathing", MaterialCategory.SHEATHING,
                   1.25, 34, 0.45, 0.7, "#c9a86c", "wood_cross")

    @classmethod
    def wood_stud(cls):
        """Dimensional lumber (SPF)"""
        return cls("Wood Stud (SPF)", MaterialCategory.WOOD,
                   1.0, 35, 0.45, 1.5, "#b8956e", "wood_grain")

    @classmethod
    def lvl(cls):
        """LVL (Laminated Veneer Lumber)"""
        return cls("LVL", MaterialCategory.WOOD,
                   1.0, 42, 0.45, 0.5, "#a67c52", "wood_grain")

    @classmethod
    def tji_flange(cls):
        """I-joist flange (LVL/LSL)"""
        return cls("I-Joist Flange", MaterialCategory.WOOD,
                   1.0, 42, 0.45, 0.5, "#8b5e3c", "wood_grain")

    @classmethod
    def tji_web(cls):
        """I-joist OSB web"""
        return cls("I-Joist Web", MaterialCategory.SHEATHING,
                   1.25, 40, 0.45, 2.0, "#c9a86c", "wood_cross")

    @classmethod
    def concrete(cls):
        """Normal weight concrete"""
        return cls("Concrete", MaterialCategory.CONCRETE,
                   0.08, 145, 0.22, 3.0, "#9ca3af", "concrete")

    @classmethod
    def cmu(cls):
        """Concrete masonry unit (hollow)"""
        return cls("CMU (Hollow)", MaterialCategory.MASONRY,
                   0.2, 85, 0.22, 6.0, "#a1a1aa", "masonry")

    @classmethod
    def brick(cls):
        """Face brick"""
        return cls("Face Brick", MaterialCategory.MASONRY,
                   0.2, 120, 0.22, 1.0, "#c2410c", "masonry")

    @classmethod
    def stone_veneer(cls):
        """Thin stone veneer"""
        return cls("Stone Veneer", MaterialCategory.MASONRY,
                   0.08, 150, 0.2, 0.5, "#78716c", "stone")

    @classmethod
    def housewrap(cls):
        """WRB (Tyvek type)"""
        return cls("House Wrap (WRB)", MaterialCategory.MEMBRANE,
                   0.0, 0.1, 0.3, 50.0, "#d4d4d4", "membrane")

    @classmethod
    def vapor_barrier(cls):
        """Polyethylene vapor barrier"""
        return cls("6 mil Poly Vapor Barrier", MaterialCategory.MEMBRANE,
                   0.0, 0.1, 0.3, 0.06, "#7dd3fc", "membrane")

    @classmethod
    def air_barrier_membrane(cls):
        """Self-adhered air barrier"""
        return cls("Air Barrier Membrane", MaterialCategory.MEMBRANE,
                   0.0, 0.2, 0.3, 0.05, "#4b5563", "membrane")

    @classmethod
    def vinyl_siding(cls):
        """Vinyl siding"""
        return cls("Vinyl Siding", MaterialCategory.FINISH,
                   0.6, 10, 0.3, 50.0, "#e2e8f0", "lines_horiz")

    @classmethod
    def fiber_cement(cls):
        """Fiber cement siding (Hardie)"""
        return cls("Fiber Cement Siding", MaterialCategory.FINISH,
                   0.25, 75, 0.2, 10.0, "#cbd5e1", "lines_horiz")

    @classmethod
    def wood_siding(cls):
        """Wood lap siding"""
        return cls("Wood Siding", MaterialCategory.FINISH,
                   0.8, 32, 0.45, 35.0, "#a16207", "wood_grain")

    @classmethod
    def stucco(cls):
        """Three-coat stucco"""
        return cls("Stucco (3-coat)", MaterialCategory.FINISH,
                   0.2, 116, 0.2, 10.0, "#d6d3d1", "stipple")

    @classmethod
    def air_gap(cls):
        """Air gap / cavity"""
        return cls("Air Gap", MaterialCategory.AIR_GAP,
                   0.9, 0.0, 0.24, 999.0, "#ffffff", "none")

    @classmethod
    def hardwood_floor(cls):
        """3/4\" hardwood flooring"""
        return cls("Hardwood Flooring", MaterialCategory.FLOORING,
                   0.9, 45, 0.45, 5.0, "#92400e", "wood_grain")

    @classmethod
    def subfloor_osb(cls):
        """3/4\" OSB subfloor"""
        return cls("OSB Subfloor", MaterialCategory.SHEATHING,
                   0.9, 40, 0.45, 2.0, "#d6b88a", "wood_cross")

    @classmethod
    def subfloor_plywood(cls):
        """3/4\" plywood subfloor"""
        return cls("Plywood Subfloor", MaterialCategory.SHEATHING,
                   0.9, 34, 0.45, 0.7, "#c9a86c", "wood_cross")

    @classmethod
    def carpet_pad(cls):
        """Carpet with pad"""
        return cls("Carpet & Pad", MaterialCategory.FLOORING,
                   2.0, 8, 0.3, 100.0, "#737373", "carpet")

    @classmethod
    def tile_thinset(cls):
        """Ceramic tile with thinset"""
        return cls("Ceramic Tile", MaterialCategory.FLOORING,
                   0.1, 150, 0.2, 0.1, "#e7e5e4", "tile")

    @classmethod
    def asphalt_shingles(cls):
        """Asphalt shingles"""
        return cls("Asphalt Shingles", MaterialCategory.ROOFING,
                   0.44, 70, 0.3, 20.0, "#374151", "shingles")

    @classmethod
    def metal_roof(cls):
        """Standing seam metal roofing"""
        return cls("Metal Roofing", MaterialCategory.ROOFING,
                   0.0, 50, 0.12, 0.0, "#64748b", "metal")

    @classmethod
    def roof_membrane(cls):
        """TPO/EPDM roof membrane"""
        return cls("Roof Membrane (TPO)", MaterialCategory.ROOFING,
                   0.0, 12, 0.3, 0.05, "#f8fafc", "membrane")

    @classmethod
    def steel_beam(cls):
        """Structural steel"""
        return cls("Steel", MaterialCategory.METAL,
                   0.003, 490, 0.12, 0.0, "#475569", "steel")


@dataclass
class Layer:
    """A single layer in an assembly"""
    material: Material
    thickness_in: float

    # Optional: for framing layers with thermal bridging
    is_framing_layer: bool = False
    framing_material: Material = None
    framing_spacing_in: float = 16.0  # OC spacing
    framing_width_in: float = 1.5     # Stud width

    @property
    def r_value(self) -> float:
        """Calculate R-value accounting for thermal bridging"""
        if not self.is_framing_layer or self.framing_material is None:
            return self.material.r_value_per_inch * self.thickness_in

        # Parallel path method for thermal bridging
        cavity_r = self.material.r_value_per_inch * self.thickness_in
        framing_r = self.framing_material.r_value_per_inch * self.thickness_in

        # Calculate framing fraction (typical 25% for 16" OC with plates/headers)
        framing_fraction = self.framing_width_in / self.framing_spacing_in
        framing_fraction = min(framing_fraction * 1.25, 0.25)  # Account for plates

        cavity_fraction = 1 - framing_fraction

        # Parallel path: 1/R_total = f_cavity/R_cavity + f_framing/R_framing
        if cavity_r > 0 and framing_r > 0:
            u_total = cavity_fraction / cavity_r + framing_fraction / framing_r
            return 1 / u_total if u_total > 0 else cavity_r
        return cavity_r


@dataclass
class LayeredAssembly:
    """A complete wall/floor/roof assembly with multiple layers"""
    name: str
    assembly_type: str  # "wall", "floor", "roof", "foundation"
    layers: List[Layer] = field(default_factory=list)
    description: str = ""

    @property
    def total_thickness_in(self) -> float:
        return sum(layer.thickness_in for layer in self.layers)

    @property
    def total_r_value(self) -> float:
        """Total R-value including air films"""
        # Interior air film R-0.68, exterior R-0.17 (winter)
        r_interior = 0.68
        r_exterior = 0.17
        r_layers = sum(layer.r_value for layer in self.layers)
        return r_interior + r_layers + r_exterior

    @property
    def u_factor(self) -> float:
        """U-factor (1/R)"""
        return 1 / self.total_r_value if self.total_r_value > 0 else 1.0

    def get_temperature_profile(
        self,
        indoor_temp_f: float,
        outdoor_temp_f: float
    ) -> List[Tuple[float, float, str]]:
        """
        Calculate temperature at each layer interface.

        Returns list of (position_in, temperature_f, layer_name)
        """
        delta_t = indoor_temp_f - outdoor_temp_f
        r_total = self.total_r_value

        profile = []
        position = 0.0
        current_temp = indoor_temp_f

        # Interior air film
        r_interior = 0.68
        temp_drop = (r_interior / r_total) * delta_t
        current_temp -= temp_drop
        profile.append((position, indoor_temp_f, "Interior Air"))

        # Each layer (from interior to exterior)
        for layer in self.layers:
            layer_r = layer.r_value
            temp_drop = (layer_r / r_total) * delta_t

            profile.append((position, current_temp, layer.material.name))
            position += layer.thickness_in
            current_temp -= temp_drop

        # Exterior
        profile.append((position, outdoor_temp_f, "Exterior Air"))

        return profile

    def find_condensation_plane(
        self,
        indoor_temp_f: float,
        outdoor_temp_f: float,
        indoor_rh_pct: float
    ) -> Optional[Tuple[float, str]]:
        """
        Find where condensation might occur in the assembly.

        Returns (position_in, layer_name) or None if no risk
        """
        # Calculate dew point
        temp_c = (indoor_temp_f - 32) * 5/9
        rh = indoor_rh_pct / 100
        a, b = 17.27, 237.7
        alpha = (a * temp_c) / (b + temp_c) + np.log(max(rh, 0.01))
        dew_point_c = (b * alpha) / (a - alpha)
        dew_point_f = dew_point_c * 9/5 + 32

        profile = self.get_temperature_profile(indoor_temp_f, outdoor_temp_f)

        for i, (pos, temp, name) in enumerate(profile):
            if temp <= dew_point_f:
                return (pos, name, dew_point_f)

        return None

    # ==================== WALL ASSEMBLY PRESETS ====================

    @classmethod
    def wall_2x4_r13(cls):
        """Standard 2x4 wall with R-13 fiberglass"""
        return cls(
            name="2x4 Wall R-13",
            assembly_type="wall",
            description="Standard 2x4 stud wall with fiberglass batt",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.fiberglass_batt(), 3.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=16.0),
                Layer(Material.osb(), 0.5),
                Layer(Material.housewrap(), 0.02),
                Layer(Material.vinyl_siding(), 0.5),
            ]
        )

    @classmethod
    def wall_2x6_r21(cls):
        """2x6 wall with R-21 fiberglass"""
        return cls(
            name="2x6 Wall R-21",
            assembly_type="wall",
            description="2x6 stud wall with high-density fiberglass batt",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.fiberglass_batt(), 5.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0),
                Layer(Material.osb(), 0.5),
                Layer(Material.housewrap(), 0.02),
                Layer(Material.fiber_cement(), 0.375),
            ]
        )

    @classmethod
    def wall_2x6_r21_plus_ci(cls):
        """2x6 wall with R-21 + continuous insulation"""
        return cls(
            name="2x6 Wall R-21 + R-5 CI",
            assembly_type="wall",
            description="2x6 wall with exterior continuous rigid insulation",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.fiberglass_batt(), 5.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0),
                Layer(Material.osb(), 0.5),
                Layer(Material.xps_foam(), 1.0),  # R-5 CI
                Layer(Material.housewrap(), 0.02),
                Layer(Material.fiber_cement(), 0.375),
            ]
        )

    @classmethod
    def wall_double_stud(cls):
        """Double-stud wall (high performance)"""
        return cls(
            name="Double Stud Wall R-40",
            assembly_type="wall",
            description="12\" double stud wall with dense-pack cellulose",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.vapor_barrier(), 0.01),
                Layer(Material.cellulose(), 3.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0),
                Layer(Material.cellulose(), 4.0),  # Cavity between studs
                Layer(Material.cellulose(), 3.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0),
                Layer(Material.osb(), 0.5),
                Layer(Material.housewrap(), 0.02),
                Layer(Material.wood_siding(), 0.75),
            ]
        )

    @classmethod
    def wall_brick_veneer(cls):
        """Brick veneer over 2x6 frame"""
        return cls(
            name="Brick Veneer Wall",
            assembly_type="wall",
            description="Brick veneer with 2x6 frame and rigid insulation",
            layers=[
                Layer(Material.drywall_5_8(), 0.625),
                Layer(Material.fiberglass_batt(), 5.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=16.0),
                Layer(Material.osb(), 0.5),
                Layer(Material.xps_foam(), 1.0),
                Layer(Material.air_barrier_membrane(), 0.05),
                Layer(Material.air_gap(), 1.0),
                Layer(Material.brick(), 3.625),
            ]
        )

    @classmethod
    def wall_cmu_interior_insulation(cls):
        """CMU wall with interior frame and insulation"""
        return cls(
            name="CMU with Interior Insulation",
            assembly_type="wall",
            description="8\" CMU with interior 2x4 frame",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.fiberglass_batt(), 3.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud()),
                Layer(Material.cmu(), 7.625),
                Layer(Material.stucco(), 0.75),
            ]
        )

    # ==================== FLOOR ASSEMBLY PRESETS ====================

    @classmethod
    def floor_2x10_standard(cls):
        """Standard 2x10 floor system"""
        return cls(
            name="2x10 Floor System",
            assembly_type="floor",
            description="2x10 joists @ 16\" OC with 3/4\" subfloor",
            layers=[
                Layer(Material.hardwood_floor(), 0.75),
                Layer(Material.subfloor_osb(), 0.75),
                Layer(Material.air_gap(), 9.25,  # Joist cavity
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=16.0,
                      framing_width_in=1.5),
            ]
        )

    @classmethod
    def floor_tji_14(cls):
        """14\" TJI floor system"""
        return cls(
            name="14\" TJI Floor System",
            assembly_type="floor",
            description="14\" I-joists @ 16\" OC",
            layers=[
                Layer(Material.hardwood_floor(), 0.75),
                Layer(Material.subfloor_plywood(), 0.75),
                Layer(Material.air_gap(), 14.0,  # I-joist depth
                      is_framing_layer=True,
                      framing_material=Material.tji_web(),
                      framing_spacing_in=16.0,
                      framing_width_in=0.375),
            ]
        )

    @classmethod
    def floor_over_unconditioned(cls):
        """Floor over unconditioned space (insulated)"""
        return cls(
            name="Insulated Floor (Over Garage/Crawl)",
            assembly_type="floor",
            description="2x10 floor with R-30 insulation below",
            layers=[
                Layer(Material.carpet_pad(), 0.5),
                Layer(Material.subfloor_plywood(), 0.75),
                Layer(Material.fiberglass_batt(), 9.25,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=16.0,
                      framing_width_in=1.5),
            ]
        )

    @classmethod
    def floor_slab_on_grade(cls):
        """Insulated slab on grade"""
        return cls(
            name="Slab on Grade (Insulated)",
            assembly_type="floor",
            description="4\" slab with underslab insulation",
            layers=[
                Layer(Material.tile_thinset(), 0.5),
                Layer(Material.concrete(), 4.0),
                Layer(Material.vapor_barrier(), 0.01),
                Layer(Material.xps_foam(), 2.0),
                Layer(Material.concrete(), 4.0),  # Gravel base (simplified)
            ]
        )

    # ==================== ROOF ASSEMBLY PRESETS ====================

    @classmethod
    def roof_truss_r38(cls):
        """Vented attic with R-38 on ceiling"""
        return cls(
            name="Vented Attic R-38",
            assembly_type="roof",
            description="Truss roof with R-38 blown insulation on ceiling",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.cellulose(), 10.5),  # ~R-38
                # Note: attic air space and roof deck not included (vented)
            ]
        )

    @classmethod
    def roof_truss_r60(cls):
        """Vented attic with R-60 on ceiling"""
        return cls(
            name="Vented Attic R-60",
            assembly_type="roof",
            description="Truss roof with R-60 blown insulation on ceiling",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.cellulose(), 16.5),  # ~R-60
            ]
        )

    @classmethod
    def roof_unvented_cathedral(cls):
        """Unvented cathedral ceiling"""
        return cls(
            name="Unvented Cathedral Ceiling",
            assembly_type="roof",
            description="2x12 rafters with spray foam",
            layers=[
                Layer(Material.drywall_half(), 0.5),
                Layer(Material.spray_foam_closed(), 3.0),
                Layer(Material.fiberglass_batt(), 8.5,
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0,
                      framing_width_in=1.5),
                Layer(Material.osb(), 0.5),
                Layer(Material.asphalt_shingles(), 0.25),
            ]
        )

    @classmethod
    def roof_flat_commercial(cls):
        """Flat roof (commercial style)"""
        return cls(
            name="Flat Roof Assembly",
            assembly_type="roof",
            description="Flat roof with tapered insulation",
            layers=[
                Layer(Material.drywall_5_8(), 0.625),
                Layer(Material.air_gap(), 14.0,  # Open-web truss cavity
                      is_framing_layer=True,
                      framing_material=Material.wood_stud(),
                      framing_spacing_in=24.0),
                Layer(Material.plywood(), 0.75),
                Layer(Material.polyiso(), 4.0),
                Layer(Material.roof_membrane(), 0.1),
            ]
        )


# Utility function to list all presets
def get_all_assembly_presets() -> Dict[str, List[str]]:
    """Get all available assembly presets organized by type"""
    return {
        "wall": [
            "wall_2x4_r13",
            "wall_2x6_r21",
            "wall_2x6_r21_plus_ci",
            "wall_double_stud",
            "wall_brick_veneer",
            "wall_cmu_interior_insulation",
        ],
        "floor": [
            "floor_2x10_standard",
            "floor_tji_14",
            "floor_over_unconditioned",
            "floor_slab_on_grade",
        ],
        "roof": [
            "roof_truss_r38",
            "roof_truss_r60",
            "roof_unvented_cathedral",
            "roof_flat_commercial",
        ]
    }


# Quick test
if __name__ == "__main__":
    print("Testing LayeredAssembly...")

    wall = LayeredAssembly.wall_2x6_r21_plus_ci()
    print(f"\n{wall.name}")
    print(f"Total thickness: {wall.total_thickness_in:.2f}\"")
    print(f"Total R-value: {wall.total_r_value:.1f}")
    print(f"U-factor: {wall.u_factor:.3f}")

    print("\nLayers:")
    for layer in wall.layers:
        print(f"  {layer.material.name}: {layer.thickness_in}\" (R-{layer.r_value:.1f})")

    print("\nTemperature profile (70°F indoor, 10°F outdoor):")
    profile = wall.get_temperature_profile(70, 10)
    for pos, temp, name in profile:
        print(f"  {pos:5.2f}\": {temp:5.1f}°F - {name}")

    condensation = wall.find_condensation_plane(70, 10, 45)
    if condensation:
        print(f"\n⚠ Condensation risk at {condensation[0]:.2f}\" ({condensation[1]})")
        print(f"  Dew point: {condensation[2]:.1f}°F")
    else:
        print("\n✓ No condensation risk")
