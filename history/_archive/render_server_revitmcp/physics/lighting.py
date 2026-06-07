# lighting.py
# Lighting analysis module - daylight factor, lumens, glare
#
# Future: Integrate with or port concepts from:
# - Radiance (industry standard lighting simulation)
# - Honeybee/Ladybug (Grasshopper environmental analysis)
# - Climate-based daylight modeling (CBDM)

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import math

print("=== LIGHTING ANALYZER LOADED ===")


class SpaceType(Enum):
    """Space types with recommended light levels"""
    OFFICE_GENERAL = "office_general"
    OFFICE_DETAILED = "office_detailed"
    RESIDENTIAL_LIVING = "residential_living"
    RESIDENTIAL_KITCHEN = "residential_kitchen"
    RESIDENTIAL_BEDROOM = "residential_bedroom"
    CLASSROOM = "classroom"
    RETAIL = "retail"
    WAREHOUSE = "warehouse"
    CORRIDOR = "corridor"


# Recommended illuminance levels (lux)
RECOMMENDED_LUX = {
    SpaceType.OFFICE_GENERAL: 500,
    SpaceType.OFFICE_DETAILED: 750,
    SpaceType.RESIDENTIAL_LIVING: 300,
    SpaceType.RESIDENTIAL_KITCHEN: 500,
    SpaceType.RESIDENTIAL_BEDROOM: 150,
    SpaceType.CLASSROOM: 500,
    SpaceType.RETAIL: 750,
    SpaceType.WAREHOUSE: 200,
    SpaceType.CORRIDOR: 100,
}


@dataclass
class DaylightResult:
    """Result of daylight analysis"""
    daylight_factor_pct: float  # Average DF%
    uniformity_ratio: float  # Min/Average
    meets_criteria: bool
    sda_pct: float  # Spatial Daylight Autonomy estimate
    recommendations: List[str]


@dataclass
class ElectricLightingResult:
    """Result of electric lighting calculation"""
    required_lumens: float
    recommended_fixtures: int
    watts_per_sqft: float
    meets_target: bool
    recommendations: List[str]


@dataclass
class GlareResult:
    """Result of glare analysis"""
    dgp: float  # Daylight Glare Probability 0-1
    risk_level: str  # "Low", "Moderate", "High"
    recommendations: List[str]


class LightingAnalyzer:
    """
    Lighting analysis for architectural design.

    Phase 1: Rule-of-thumb calculations and simple geometry
    Phase 2: Raytracing integration (Radiance or custom)
    """

    def __init__(self):
        self.sky_luminance = 10000  # Overcast sky (cd/m²)

    def calculate_daylight_factor(
        self,
        room_width_ft: float,
        room_depth_ft: float,
        room_height_ft: float,
        window_area_sqft: float,
        window_height_ft: float,
        glazing_transmittance: float = 0.6,
        surface_reflectances: Dict[str, float] = None
    ) -> DaylightResult:
        """
        Estimate daylight factor using simplified BRE method.

        Args:
            room_width_ft: Room width (parallel to windows)
            room_depth_ft: Room depth (perpendicular to windows)
            room_height_ft: Floor to ceiling height
            window_area_sqft: Total glazing area
            window_height_ft: Head height of window
            glazing_transmittance: Light transmission of glass (0-1)
            surface_reflectances: Optional dict of reflectances

        Returns:
            DaylightResult with daylight factor and recommendations
        """
        recommendations = []

        # Default reflectances
        if surface_reflectances is None:
            surface_reflectances = {
                "ceiling": 0.8,
                "walls": 0.5,
                "floor": 0.2
            }

        # Room area
        floor_area = room_width_ft * room_depth_ft

        # Window to floor ratio
        wfr = window_area_sqft / floor_area

        # Average reflectance
        total_surface = (2 * floor_area +
                        2 * room_width_ft * room_height_ft +
                        2 * room_depth_ft * room_height_ft)

        avg_reflectance = (
            surface_reflectances["ceiling"] * floor_area +
            surface_reflectances["floor"] * floor_area +
            surface_reflectances["walls"] * 2 * room_width_ft * room_height_ft +
            surface_reflectances["walls"] * 2 * room_depth_ft * room_height_ft
        ) / total_surface

        # Simplified daylight factor formula (BRE method)
        # DF% ≈ (Aw × τ × θ) / (A × (1 - ρ²))
        # Where θ is visible sky angle (simplified to 0.5 for vertical windows)

        theta = 0.5  # Simplified sky angle factor

        df = (window_area_sqft * glazing_transmittance * theta * 100) / \
             (floor_area * (1 - avg_reflectance**2))

        # Clamp to reasonable range
        df = min(df, 20.0)  # Max 20% DF

        # Estimate uniformity (very simplified)
        # Typically decreases with room depth
        depth_ratio = room_depth_ft / window_height_ft
        uniformity = max(0.2, 1.0 - (depth_ratio * 0.1))

        # Check criteria (2% DF is typical minimum for daylit space)
        meets_criteria = df >= 2.0 and uniformity >= 0.3

        # Estimate SDA (Spatial Daylight Autonomy)
        # Very rough estimate based on DF
        sda = min(100, df * 20)  # Approximate

        # Recommendations
        if df < 2.0:
            recommendations.append(
                f"Daylight factor {df:.1f}% is below 2% minimum. "
                "Increase window area or add skylights."
            )
        if uniformity < 0.3:
            recommendations.append(
                "Poor uniformity - room is too deep relative to windows. "
                "Consider light shelves or additional windows."
            )
        if wfr < 0.15:
            recommendations.append(
                f"Window-to-floor ratio {wfr:.0%} is low. "
                "Target 15-25% for good daylighting."
            )
        if wfr > 0.35:
            recommendations.append(
                f"Window-to-floor ratio {wfr:.0%} is high. "
                "May have glare or overheating issues."
            )
        if df >= 2.0 and uniformity >= 0.3:
            recommendations.append("Good daylighting conditions achieved.")

        return DaylightResult(
            daylight_factor_pct=df,
            uniformity_ratio=uniformity,
            meets_criteria=meets_criteria,
            sda_pct=sda,
            recommendations=recommendations
        )

    def calculate_electric_lighting(
        self,
        floor_area_sqft: float,
        space_type: SpaceType,
        ceiling_height_ft: float = 9.0,
        fixture_lumens: int = 3000,
        fixture_watts: int = 30,
        light_loss_factor: float = 0.85
    ) -> ElectricLightingResult:
        """
        Calculate required electric lighting using lumen method.

        Args:
            floor_area_sqft: Room floor area
            space_type: Type of space for target illuminance
            ceiling_height_ft: Ceiling height
            fixture_lumens: Lumens per fixture
            fixture_watts: Watts per fixture
            light_loss_factor: Maintenance factor (typically 0.8-0.9)

        Returns:
            ElectricLightingResult with fixture count and power
        """
        recommendations = []

        # Target illuminance
        target_lux = RECOMMENDED_LUX.get(space_type, 500)
        target_fc = target_lux * 0.0929  # Convert lux to footcandles

        # Room Cavity Ratio (simplified)
        # RCR = 5h(L+W) / (L×W) where h = mounting height
        # Simplified: assume work plane at 2.5'
        room_dim = math.sqrt(floor_area_sqft)  # Assume square
        mounting_height = ceiling_height_ft - 2.5
        rcr = (5 * mounting_height * 2 * room_dim) / floor_area_sqft

        # Coefficient of Utilization (simplified lookup)
        # Depends on room reflectances and RCR
        # Using approximate value for typical conditions
        cu = max(0.4, 0.8 - (rcr * 0.05))

        # Required lumens
        # Lumens = (fc × area) / (CU × LLF)
        required_lumens = (target_fc * floor_area_sqft) / (cu * light_loss_factor)

        # Number of fixtures
        num_fixtures = math.ceil(required_lumens / fixture_lumens)

        # Total watts
        total_watts = num_fixtures * fixture_watts
        watts_per_sqft = total_watts / floor_area_sqft

        # Check against energy code (typical limit ~1.0 W/sqft)
        meets_target = watts_per_sqft <= 1.2

        # Recommendations
        if watts_per_sqft > 1.0:
            recommendations.append(
                f"Power density {watts_per_sqft:.2f} W/sqft exceeds typical code limit. "
                "Consider more efficient fixtures."
            )
        if num_fixtures > floor_area_sqft / 50:
            recommendations.append(
                "High fixture density - consider higher output fixtures."
            )

        fixture_spacing = math.sqrt(floor_area_sqft / num_fixtures)
        recommendations.append(
            f"Suggested fixture spacing: ~{fixture_spacing:.1f} ft on center"
        )

        return ElectricLightingResult(
            required_lumens=required_lumens,
            recommended_fixtures=num_fixtures,
            watts_per_sqft=watts_per_sqft,
            meets_target=meets_target,
            recommendations=recommendations
        )

    def estimate_glare_risk(
        self,
        window_orientation: str,  # "N", "E", "S", "W"
        window_area_sqft: float,
        room_depth_ft: float,
        has_blinds: bool = False,
        has_overhang: bool = False
    ) -> GlareResult:
        """
        Estimate glare risk from windows.

        Args:
            window_orientation: Cardinal direction window faces
            window_area_sqft: Window area
            room_depth_ft: Depth of room from window
            has_blinds: Whether blinds/shades are present
            has_overhang: Whether exterior shading exists

        Returns:
            GlareResult with glare probability estimate
        """
        recommendations = []

        # Base glare risk by orientation
        orientation_factor = {
            "N": 0.2,
            "E": 0.5,
            "S": 0.6,
            "W": 0.7,  # West is worst for glare
        }.get(window_orientation.upper(), 0.5)

        # Size factor - larger windows = more glare potential
        size_factor = min(1.0, window_area_sqft / 50)

        # Depth factor - deeper rooms = less glare at work plane
        depth_factor = max(0.3, 1.0 - (room_depth_ft / 30))

        # Calculate base DGP (Daylight Glare Probability)
        dgp = orientation_factor * size_factor * depth_factor

        # Mitigation
        if has_blinds:
            dgp *= 0.5
            recommendations.append("Blinds can reduce glare when needed")
        if has_overhang:
            dgp *= 0.7
            recommendations.append("Overhang helps reduce direct sun penetration")

        # Clamp
        dgp = min(dgp, 0.9)

        # Risk level
        if dgp < 0.35:
            risk_level = "Low"
        elif dgp < 0.45:
            risk_level = "Moderate"
        else:
            risk_level = "High"
            recommendations.append(
                "High glare risk - add blinds, shades, or exterior shading"
            )

        if window_orientation.upper() == "W" and not has_blinds:
            recommendations.append(
                "West-facing windows have significant afternoon glare - blinds recommended"
            )

        return GlareResult(
            dgp=dgp,
            risk_level=risk_level,
            recommendations=recommendations
        )


# Quick test
if __name__ == "__main__":
    analyzer = LightingAnalyzer()

    # Test daylight analysis
    result = analyzer.calculate_daylight_factor(
        room_width_ft=15,
        room_depth_ft=20,
        room_height_ft=9,
        window_area_sqft=40,
        window_height_ft=7,
    )

    print(f"Daylight Factor: {result.daylight_factor_pct:.1f}%")
    print(f"Uniformity: {result.uniformity_ratio:.2f}")
    print(f"Meets criteria: {result.meets_criteria}")
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
