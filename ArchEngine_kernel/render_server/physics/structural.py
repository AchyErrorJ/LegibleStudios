# structural.py
# Structural analysis module - load paths, beam sizing, foundation checks
#
# Reference Standards:
# - AISC Steel Manual (steel design)
# - NDS (National Design Specification for Wood)
# - ACI 318 (concrete design)
# - IBC Chapter 16 (loads)
# - ASCE 7 (minimum design loads)

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math

print("=== STRUCTURAL ANALYZER LOADED ===")


class MaterialType(Enum):
    WOOD = "wood"
    STEEL = "steel"
    CONCRETE = "concrete"
    MASONRY = "masonry"


class SeismicCategory(Enum):
    """ASCE 7 Seismic Design Categories"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


class ExposureCategory(Enum):
    """ASCE 7 Wind Exposure Categories"""
    B = "B"  # Urban, suburban
    C = "C"  # Open terrain
    D = "D"  # Flat, open coastal


@dataclass
class Material:
    """Structural material properties"""
    name: str
    type: MaterialType
    density_pcf: float
    yield_strength_psi: float
    elastic_modulus_psi: float
    min_yield_strength_psi: float = None
    shear_modulus_psi: float = None

    def __post_init__(self):
        if self.min_yield_strength_psi is None:
            self.min_yield_strength_psi = self.yield_strength_psi
        if self.shear_modulus_psi is None:
            self.shear_modulus_psi = self.elastic_modulus_psi / 2.6

    @classmethod
    def wood_spf(cls):
        """Spruce-Pine-Fir #2"""
        return cls("SPF #2", MaterialType.WOOD, 35, 1200, 1_400_000)

    @classmethod
    def wood_df(cls):
        """Douglas Fir-Larch #1"""
        return cls("DF-L #1", MaterialType.WOOD, 34, 1500, 1_700_000)

    @classmethod
    def steel_a36(cls):
        """A36 structural steel"""
        return cls("A36 Steel", MaterialType.STEEL, 490, 36_000, 29_000_000,
                   min_yield_strength_psi=36_000, shear_modulus_psi=11_200_000)

    @classmethod
    def steel_a992(cls):
        """A992 structural steel (W shapes)"""
        return cls("A992 Steel", MaterialType.STEEL, 490, 50_000, 29_000_000,
                   min_yield_strength_psi=50_000, shear_modulus_psi=11_200_000)

    @classmethod
    def concrete_3000(cls):
        """3000 PSI concrete"""
        return cls("3000 PSI Concrete", MaterialType.CONCRETE, 150, 3_000, 3_100_000)

    @classmethod
    def concrete_4000(cls):
        """4000 PSI concrete"""
        return cls("4000 PSI Concrete", MaterialType.CONCRETE, 150, 4_000, 3_600_000)


@dataclass
class BeamResult:
    passes: bool
    max_stress_psi: float
    allowable_stress_psi: float
    max_deflection_in: float
    allowable_deflection_in: float
    utilization_ratio: float
    warnings: List[str]


@dataclass
class ColumnResult:
    passes: bool
    applied_load_lbs: float
    allowable_load_lbs: float
    slenderness_ratio: float
    effective_length_factor: float
    buckling_mode: str
    utilization_ratio: float
    warnings: List[str]
    recommendations: List[str]


@dataclass
class FloorSystemResult:
    passes: bool
    joist_size: str
    joist_spacing_in: float
    joist_utilization: float
    sheathing_adequate: bool
    total_depth_in: float
    deflection_in: float
    allowable_deflection_in: float
    vibration_check: str
    warnings: List[str]
    recommendations: List[str]


@dataclass
class LateralLoadResult:
    passes: bool
    wind_base_shear_lbs: float
    seismic_base_shear_lbs: float
    controlling_load: str
    story_drift_ratio: float
    allowable_drift_ratio: float
    overturning_moment_lb_ft: float
    required_shear_wall_length_ft: float
    warnings: List[str]
    recommendations: List[str]


@dataclass
class ConnectionResult:
    passes: bool
    connection_type: str
    applied_load_lbs: float
    capacity_lbs: float
    utilization_ratio: float
    failure_mode: str
    warnings: List[str]
    recommendations: List[str]


@dataclass
class LoadPathResult:
    valid: bool
    issues: List[str]
    load_diagram: Optional[Dict] = None


class StructuralAnalyzer:
    """Structural analysis for architectural designs."""

    def __init__(self):
        self.safety_factor = 1.5
        self.deflection_limit = 240
        self.deflection_limit_roof = 180

    def analyze_simple_beam(
        self,
        span_ft: float,
        width_in: float,
        depth_in: float,
        material: Material,
        uniform_load_plf: float,
        point_loads: List[Tuple[float, float]] = None
    ) -> BeamResult:
        """
        Analyze simply-supported beam.
        Bending: sigma = M/S, Deflection: delta = 5wL^4/(384EI)
        """
        warnings = []
        span_in = span_ft * 12
        area = width_in * depth_in
        moment_of_inertia = (width_in * depth_in**3) / 12
        section_modulus = (width_in * depth_in**2) / 6

        volume_cf = (area / 144) * span_ft
        self_weight_lbs = volume_cf * material.density_pcf
        self_weight_plf = self_weight_lbs / span_ft
        total_uniform = uniform_load_plf + self_weight_plf

        max_moment_lb_in = (total_uniform / 12) * span_in**2 / 8

        if point_loads:
            for pos_ft, load_lbs in point_loads:
                pos_in = pos_ft * 12
                a = pos_in
                b = span_in - pos_in
                point_moment = (load_lbs * a * b) / span_in
                max_moment_lb_in += point_moment

        max_stress = max_moment_lb_in / section_modulus
        allowable_stress = material.yield_strength_psi / self.safety_factor

        w_per_inch = total_uniform / 12
        E = material.elastic_modulus_psi
        I = moment_of_inertia
        max_deflection = (5 * w_per_inch * span_in**4) / (384 * E * I)
        allowable_deflection = span_in / self.deflection_limit

        stress_util = max_stress / allowable_stress
        deflection_util = max_deflection / allowable_deflection
        utilization = max(stress_util, deflection_util)

        if stress_util > 0.9:
            warnings.append(f"Stress utilization high: {stress_util:.1%}")
        if deflection_util > 0.9:
            warnings.append(f"Deflection utilization high: {deflection_util:.1%}")
        if depth_in / width_in > 6:
            warnings.append("Beam very deep - check lateral stability")

        passes = stress_util <= 1.0 and deflection_util <= 1.0

        return BeamResult(
            passes=passes,
            max_stress_psi=max_stress,
            allowable_stress_psi=allowable_stress,
            max_deflection_in=max_deflection,
            allowable_deflection_in=allowable_deflection,
            utilization_ratio=utilization,
            warnings=warnings
        )

    def analyze_column(
        self,
        height_ft: float,
        width_in: float,
        depth_in: float,
        material: Material,
        axial_load_lbs: float,
        end_condition: str = "pinned-pinned",
        braced_axis: str = "both"
    ) -> ColumnResult:
        """
        Analyze column with buckling check.
        Euler: Pe = pi^2*EI/(KL)^2, Slenderness = KL/r
        Ref: AISC Ch E (steel), NDS Ch 3 (wood)
        """
        warnings = []
        recommendations = []
        height_in = height_ft * 12

        k_factors = {
            "fixed-fixed": 0.65,
            "fixed-pinned": 0.80,
            "pinned-pinned": 1.0,
            "fixed-free": 2.1,
        }
        K = k_factors.get(end_condition, 1.0)

        area = width_in * depth_in
        I_strong = (width_in * depth_in**3) / 12
        I_weak = (depth_in * width_in**3) / 12
        r_strong = math.sqrt(I_strong / area)
        r_weak = math.sqrt(I_weak / area)

        if braced_axis == "both":
            r_min = min(r_strong, r_weak)
        elif braced_axis == "weak":
            r_min = r_strong
        elif braced_axis == "strong":
            r_min = r_weak
        else:
            r_min = min(r_strong, r_weak)

        effective_length = K * height_in
        slenderness = effective_length / r_min

        if slenderness > 200:
            warnings.append(f"Slenderness {slenderness:.0f} exceeds 200 limit")
        elif slenderness > 150:
            warnings.append(f"Slenderness {slenderness:.0f} is high")

        if material.type == MaterialType.STEEL:
            Fy = material.min_yield_strength_psi
            E = material.elastic_modulus_psi
            Fe = (math.pi**2 * E) / (slenderness**2) if slenderness > 0 else float("inf")
            if Fe >= 0.44 * Fy:
                Fcr = (0.658 ** (Fy / Fe)) * Fy
                buckling_mode = "inelastic_buckling"
            else:
                Fcr = 0.877 * Fe
                buckling_mode = "elastic_buckling"
            allowable_stress = Fcr / self.safety_factor
            allowable_load = allowable_stress * area

        elif material.type == MaterialType.WOOD:
            Fc = material.yield_strength_psi
            E_min = material.elastic_modulus_psi * 0.58
            le_d = effective_length / min(width_in, depth_in)
            FcE = (0.822 * E_min) / (le_d**2)
            c = 0.8
            ratio = FcE / Fc
            Cp = (1 + ratio) / (2 * c) - math.sqrt(((1 + ratio) / (2 * c))**2 - ratio / c)
            allowable_stress = Fc * Cp / self.safety_factor
            allowable_load = allowable_stress * area
            if Cp < 0.5:
                buckling_mode = "elastic_buckling"
            elif Cp < 0.9:
                buckling_mode = "inelastic_buckling"
            else:
                buckling_mode = "yielding"
        else:
            Fe = (math.pi**2 * material.elastic_modulus_psi) / (slenderness**2) if slenderness > 0 else float("inf")
            allowable_stress = min(Fe, material.yield_strength_psi) / self.safety_factor
            allowable_load = allowable_stress * area
            buckling_mode = "elastic_buckling" if Fe < material.yield_strength_psi else "yielding"

        utilization = axial_load_lbs / allowable_load if allowable_load > 0 else float("inf")
        passes = utilization <= 1.0

        if not passes:
            recommendations.append("Column overstressed - increase size or add bracing")
            if slenderness > 100:
                recommendations.append("Reduce unbraced length with intermediate bracing")
        if slenderness > 120:
            recommendations.append(f"Consider larger section to reduce slenderness from {slenderness:.0f}")

        return ColumnResult(
            passes=passes,
            applied_load_lbs=axial_load_lbs,
            allowable_load_lbs=allowable_load,
            slenderness_ratio=slenderness,
            effective_length_factor=K,
            buckling_mode=buckling_mode,
            utilization_ratio=utilization,
            warnings=warnings,
            recommendations=recommendations
        )

    def analyze_floor_system(
        self,
        span_ft: float,
        floor_width_ft: float,
        live_load_psf: float = 40,
        dead_load_psf: float = 15,
        joist_material: Material = None,
        sheathing_thickness_in: float = 0.75,
        ceiling_below: bool = True
    ) -> FloorSystemResult:
        """
        Analyze floor with joists and subfloor.
        Ref: IRC Table R502.3.1 (floor joist spans)
        """
        warnings = []
        recommendations = []

        if joist_material is None:
            joist_material = Material.wood_spf()

        total_load_psf = live_load_psf + dead_load_psf
        spacings = [12, 16, 19.2, 24]
        joist_sizes = [
            ("2x6", 1.5, 5.5), ("2x8", 1.5, 7.25), ("2x10", 1.5, 9.25),
            ("2x12", 1.5, 11.25), ("2x14", 1.5, 13.25),
        ]

        best_solution = None
        for spacing in spacings:
            trib_width_ft = spacing / 12
            uniform_load_plf = total_load_psf * trib_width_ft

            for name, width, depth in joist_sizes:
                result = self.analyze_simple_beam(
                    span_ft=span_ft, width_in=width, depth_in=depth,
                    material=joist_material, uniform_load_plf=uniform_load_plf
                )

                if result.passes and result.utilization_ratio <= 0.95:
                    span_in = span_ft * 12
                    I = (width * depth**3) / 12
                    E = joist_material.elastic_modulus_psi
                    live_load_plf = live_load_psf * trib_width_ft
                    w_live = live_load_plf / 12
                    live_deflection = (5 * w_live * span_in**4) / (384 * E * I)
                    allowable_live_deflection = span_in / 360

                    if live_deflection <= allowable_live_deflection:
                        if best_solution is None or depth < best_solution["depth"]:
                            best_solution = {
                                "name": name, "width": width, "depth": depth,
                                "spacing": spacing, "utilization": result.utilization_ratio,
                                "deflection": result.max_deflection_in,
                                "allowable_deflection": result.allowable_deflection_in,
                            }
                        break

        if best_solution is None:
            warnings.append("No standard joist adequate - use engineered joists")
            return FloorSystemResult(
                passes=False, joist_size="N/A", joist_spacing_in=16,
                joist_utilization=0, sheathing_adequate=False, total_depth_in=0,
                deflection_in=0, allowable_deflection_in=0, vibration_check="N/A",
                warnings=warnings, recommendations=["Use I-joists or LVL"]
            )

        sheathing_ok = True
        if best_solution["spacing"] > 16 and sheathing_thickness_in < 0.75:
            sheathing_ok = False
            warnings.append("Subfloor needs upgrade for joist spacing over 16 inches")
        if best_solution["spacing"] > 19.2 and sheathing_thickness_in < 0.875:
            sheathing_ok = False
            warnings.append("Need 7/8 inch subfloor for 24 inch OC spacing")

        span_depth_ratio = (span_ft * 12) / best_solution["depth"]
        if span_depth_ratio > 20:
            vibration = "concern"
            warnings.append("Floor may feel bouncy")
        elif span_depth_ratio > 16:
            vibration = "marginal"
            recommendations.append("Use T&G subfloor with glue for stiffness")
        else:
            vibration = "OK"

        total_depth = best_solution["depth"] + sheathing_thickness_in
        if ceiling_below:
            total_depth += 0.5

        return FloorSystemResult(
            passes=True, joist_size=best_solution["name"],
            joist_spacing_in=best_solution["spacing"],
            joist_utilization=best_solution["utilization"],
            sheathing_adequate=sheathing_ok, total_depth_in=total_depth,
            deflection_in=best_solution["deflection"],
            allowable_deflection_in=best_solution["allowable_deflection"],
            vibration_check=vibration, warnings=warnings, recommendations=recommendations
        )

    def analyze_lateral_loads(
        self,
        building_width_ft: float,
        building_length_ft: float,
        building_height_ft: float,
        num_stories: int,
        roof_dead_load_psf: float = 15,
        floor_dead_load_psf: float = 40,
        wind_speed_mph: float = 115,
        exposure: ExposureCategory = ExposureCategory.B,
        seismic_category: SeismicCategory = SeismicCategory.D,
        Sds: float = 1.0,
    ) -> LateralLoadResult:
        """
        Calculate lateral loads from wind and seismic.
        Wind: qz = 0.00256 * Kz * Kzt * Kd * V^2 (ASCE 7)
        Seismic: V = Cs * W (ASCE 7)
        """
        warnings = []
        recommendations = []
        floor_area = building_width_ft * building_length_ft

        # Wind calculation
        Kz_values = {
            ExposureCategory.B: 0.70 + 0.15 * min(building_height_ft / 30, 1),
            ExposureCategory.C: 0.85 + 0.10 * min(building_height_ft / 30, 1),
            ExposureCategory.D: 1.00 + 0.08 * min(building_height_ft / 30, 1),
        }
        Kz = Kz_values.get(exposure, 0.85)
        Kzt = 1.0
        Kd = 0.85
        qz = 0.00256 * Kz * Kzt * Kd * wind_speed_mph**2
        Cp_combined = 1.3
        wind_pressure = qz * Cp_combined
        wall_area = building_width_ft * building_height_ft
        wind_base_shear = wind_pressure * wall_area
        wind_moment = wind_base_shear * (building_height_ft * 0.6)

        # Seismic calculation
        R = 6.5  # Wood shear walls
        Ie = 1.0
        Cs = Sds / (R / Ie)
        Cs = max(Cs, 0.044 * Sds * Ie)
        Cs = max(Cs, 0.01)
        roof_weight = roof_dead_load_psf * floor_area
        floor_weight = floor_dead_load_psf * floor_area * (num_stories - 1)
        total_weight = roof_weight + floor_weight
        seismic_base_shear = Cs * total_weight
        seismic_moment = seismic_base_shear * (building_height_ft * 0.67)

        # Controlling load
        if wind_base_shear > seismic_base_shear:
            controlling = "wind"
            design_base_shear = wind_base_shear
            design_moment = wind_moment
        else:
            controlling = "seismic"
            design_base_shear = seismic_base_shear
            design_moment = seismic_moment

        # Drift check
        story_drift_ratio = design_base_shear / (total_weight * 100)
        story_drift_ratio = min(story_drift_ratio, 0.025)
        allowable_drift = 0.02
        if seismic_category.value in ["D", "E", "F"]:
            allowable_drift = 0.015

        # Shear wall requirements
        shear_wall_capacity_plf = 300
        required_shear_wall_length = design_base_shear / shear_wall_capacity_plf
        min_shear_wall_pct = required_shear_wall_length / (2 * (building_width_ft + building_length_ft))

        if min_shear_wall_pct > 0.5:
            warnings.append(f"High shear wall requirement ({min_shear_wall_pct:.0%} of perimeter)")
            recommendations.append("Consider stronger sheathing or closer nailing")

        passes = story_drift_ratio <= allowable_drift

        if not passes:
            recommendations.append("Add shear walls or increase capacity")
        if controlling == "seismic" and seismic_category.value in ["D", "E", "F"]:
            recommendations.append("High seismic zone - ensure continuous load path")
            recommendations.append("Holdowns required at shear wall ends")

        return LateralLoadResult(
            passes=passes,
            wind_base_shear_lbs=wind_base_shear,
            seismic_base_shear_lbs=seismic_base_shear,
            controlling_load=controlling,
            story_drift_ratio=story_drift_ratio,
            allowable_drift_ratio=allowable_drift,
            overturning_moment_lb_ft=design_moment,
            required_shear_wall_length_ft=required_shear_wall_length,
            warnings=warnings,
            recommendations=recommendations
        )

    def check_connection(
        self,
        connection_type: str,
        load_lbs: float,
        member_width_in: float = 3.5,
        member_depth_in: float = 9.25,
        bearing_length_in: float = 3.5,
        num_fasteners: int = 1,
        fastener_type: str = "nail"
    ) -> ConnectionResult:
        """
        Check connection for bearing/shear/tension.
        Ref: NDS Chapter 11-12 (connections)
        """
        warnings = []
        recommendations = []

        if connection_type == "bearing":
            Fc_perp = 425  # PSI for SPF
            bearing_area = member_width_in * bearing_length_in
            capacity = Fc_perp * bearing_area
            if bearing_length_in < 1.5:
                warnings.append("Bearing length under 1.5 inch - need bearing plate")
                capacity *= 0.5
            failure_mode = "crushing perpendicular to grain"

        elif connection_type == "shear":
            Fv = 180
            shear_area = member_width_in * member_depth_in * 0.67
            capacity = Fv * shear_area
            failure_mode = "horizontal shear at support"

        elif connection_type == "tension":
            capacity_per_fastener = {"nail": 80, "screw": 200, "bolt": 1000, "lag": 400}
            per_fastener = capacity_per_fastener.get(fastener_type, 100)
            capacity = per_fastener * num_fasteners
            failure_mode = "fastener withdrawal"
            if fastener_type == "nail":
                warnings.append("Nails have low withdrawal capacity")

        elif connection_type == "hanger":
            hanger_caps = {"2x6": 400, "2x8": 550, "2x10": 700, "2x12": 850}
            if member_depth_in <= 5.5:
                size_key = "2x6"
            elif member_depth_in <= 7.5:
                size_key = "2x8"
            elif member_depth_in <= 9.5:
                size_key = "2x10"
            else:
                size_key = "2x12"
            capacity = hanger_caps.get(size_key, 500)
            failure_mode = "hanger capacity"
            recommendations.append("Verify hanger capacity from manufacturer")
        else:
            capacity = 1000
            failure_mode = "unknown"
            warnings.append(f"Unknown connection type: {connection_type}")

        utilization = load_lbs / capacity if capacity > 0 else float("inf")
        passes = utilization <= 1.0

        if not passes:
            recommendations.append(f"Connection overstressed ({utilization:.0%})")
            if connection_type == "bearing":
                recommendations.append("Add bearing plate or increase length")
            elif connection_type == "tension":
                recommendations.append("Add more or larger fasteners")
            elif connection_type == "hanger":
                recommendations.append("Select higher-capacity hanger")

        return ConnectionResult(
            passes=passes, connection_type=connection_type,
            applied_load_lbs=load_lbs, capacity_lbs=capacity,
            utilization_ratio=utilization, failure_mode=failure_mode,
            warnings=warnings, recommendations=recommendations
        )

    def check_load_path(self, model: Dict) -> LoadPathResult:
        """Verify loads have continuous path to foundation."""
        issues = []
        if not model.get("foundation"):
            issues.append("No foundation defined")
        if not model.get("walls") and not model.get("columns"):
            issues.append("No vertical load-bearing elements")
        if model.get("floors") and model.get("walls"):
            for floor in model.get("floors", []):
                if not floor.get("connected_to_walls"):
                    issues.append(f"Floor level {floor.get('level', '?')}: not connected")
        if model.get("shear_walls"):
            sw = model.get("shear_walls", [])
            if len(sw) < 2:
                issues.append("Need shear walls in both directions")
            for wall in sw:
                if not wall.get("holdowns"):
                    issues.append(f"Shear wall {wall.get('id', '?')}: missing holdowns")
        return LoadPathResult(valid=len(issues) == 0, issues=issues)

    def suggest_beam_size(
        self, span_ft: float, tributary_width_ft: float,
        floor_load_psf: float, material: Material, max_depth_in: float = 24
    ) -> Dict:
        """Suggest beam size for given conditions."""
        uniform_load_plf = floor_load_psf * tributary_width_ft
        if material.type == MaterialType.WOOD:
            sizes = [
                (1.5, 5.5), (1.5, 7.25), (1.5, 9.25), (1.5, 11.25),
                (3.0, 5.5), (3.0, 7.25), (3.0, 9.25), (3.0, 11.25),
                (3.5, 9.25), (3.5, 11.25), (5.5, 11.25),
            ]
        else:
            sizes = [(w, d) for w in [4, 6, 8] for d in range(6, int(max_depth_in)+1, 2)]

        for width, depth in sizes:
            if depth > max_depth_in:
                continue
            result = self.analyze_simple_beam(
                span_ft=span_ft, width_in=width, depth_in=depth,
                material=material, uniform_load_plf=uniform_load_plf
            )
            if result.passes:
                return {"width_in": width, "depth_in": depth,
                        "utilization": result.utilization_ratio, "analysis": result}
        return {"error": "No standard size works", "suggestion": "Consider deeper beam or shorter span"}
