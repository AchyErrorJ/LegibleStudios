# thermal.py
# Thermal analysis module - heat loss, R-values, air tightness
#
# Future: Integrate with or port concepts from:
# - EnergyPlus (DOE building energy simulation)
# - OpenFOAM (CFD for airflow)
# - THERM (2D heat transfer)

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

print("=== THERMAL ANALYZER LOADED ===")


class ClimateZone(Enum):
    """IECC Climate Zones"""
    ZONE_1 = 1  # Very Hot-Humid
    ZONE_2 = 2  # Hot-Humid
    ZONE_3 = 3  # Warm-Humid/Marine
    ZONE_4 = 4  # Mixed-Humid/Marine
    ZONE_5 = 5  # Cool-Humid
    ZONE_6 = 6  # Cold-Humid
    ZONE_7 = 7  # Very Cold
    ZONE_8 = 8  # Subarctic


@dataclass
class Assembly:
    """A wall/roof/floor assembly with R-value"""
    name: str
    r_value: float  # hr·ft²·°F/BTU
    thickness_in: float

    @classmethod
    def wall_2x4_r13(cls):
        """Standard 2x4 wall with R-13 insulation"""
        return cls("2x4 Wall R-13", 13.0, 4.5)

    @classmethod
    def wall_2x6_r21(cls):
        """2x6 wall with R-21 insulation"""
        return cls("2x6 Wall R-21", 21.0, 6.5)

    @classmethod
    def roof_r38(cls):
        """Attic with R-38 insulation"""
        return cls("Attic R-38", 38.0, 12.0)

    @classmethod
    def slab_uninsulated(cls):
        """Uninsulated slab on grade"""
        return cls("Uninsulated Slab", 1.0, 4.0)


@dataclass
class Window:
    """Window with U-factor and SHGC"""
    name: str
    u_factor: float  # BTU/(hr·ft²·°F) - lower is better
    shgc: float  # Solar Heat Gain Coefficient 0-1

    @classmethod
    def single_pane(cls):
        return cls("Single Pane", 1.0, 0.86)

    @classmethod
    def double_pane_clear(cls):
        return cls("Double Pane Clear", 0.50, 0.70)

    @classmethod
    def double_pane_low_e(cls):
        return cls("Double Pane Low-E", 0.30, 0.40)

    @classmethod
    def triple_pane_low_e(cls):
        return cls("Triple Pane Low-E", 0.20, 0.25)


@dataclass
class HeatLossResult:
    """Result of heat loss calculation"""
    total_btuh: float  # BTU per hour
    envelope_btuh: float  # Through walls/roof/floor
    infiltration_btuh: float  # Air leakage
    ventilation_btuh: float  # Mechanical ventilation
    component_breakdown: Dict[str, float]  # By component
    recommendations: List[str]


@dataclass
class AirTightnessResult:
    """Result of air tightness estimation"""
    ach50: float  # Air changes per hour at 50 Pa
    ach_natural: float  # Natural air changes per hour
    cfm50: float  # CFM at 50 Pa
    rating: str  # "Tight", "Average", "Leaky"
    recommendations: List[str]


class ThermalAnalyzer:
    """
    Thermal analysis for buildings.

    Phase 1: Manual J style calculations
    Phase 2: Full energy modeling integration
    """

    def __init__(self):
        # Default design temperatures by climate zone (winter heating)
        self.design_temps = {
            ClimateZone.ZONE_1: 40,
            ClimateZone.ZONE_2: 30,
            ClimateZone.ZONE_3: 25,
            ClimateZone.ZONE_4: 15,
            ClimateZone.ZONE_5: 5,
            ClimateZone.ZONE_6: -5,
            ClimateZone.ZONE_7: -15,
            ClimateZone.ZONE_8: -30,
        }
        self.indoor_temp = 70  # °F

    def calculate_heat_loss(
        self,
        climate_zone: ClimateZone,
        floor_area_sqft: float,
        wall_area_sqft: float,
        wall_assembly: Assembly,
        roof_area_sqft: float,
        roof_assembly: Assembly,
        window_area_sqft: float,
        window: Window,
        volume_cuft: float,
        ach_natural: float = 0.35,  # Natural air changes/hour
    ) -> HeatLossResult:
        """
        Calculate design heat loss for a building.

        This is a simplified Manual J style calculation.

        Args:
            climate_zone: IECC climate zone
            floor_area_sqft: Conditioned floor area
            wall_area_sqft: Gross exterior wall area (excluding windows)
            wall_assembly: Wall construction
            roof_area_sqft: Ceiling/roof area
            roof_assembly: Roof/attic construction
            window_area_sqft: Total window area
            window: Window type
            volume_cuft: Conditioned volume
            ach_natural: Natural air infiltration rate

        Returns:
            HeatLossResult with breakdown
        """
        # Temperature difference
        outdoor_temp = self.design_temps[climate_zone]
        delta_t = self.indoor_temp - outdoor_temp

        breakdown = {}
        recommendations = []

        # Wall heat loss: Q = A × U × ΔT, where U = 1/R
        wall_u = 1.0 / wall_assembly.r_value
        wall_loss = wall_area_sqft * wall_u * delta_t
        breakdown["Walls"] = wall_loss

        # Roof heat loss
        roof_u = 1.0 / roof_assembly.r_value
        roof_loss = roof_area_sqft * roof_u * delta_t
        breakdown["Roof/Ceiling"] = roof_loss

        # Window heat loss
        window_loss = window_area_sqft * window.u_factor * delta_t
        breakdown["Windows"] = window_loss

        # Floor/slab (simplified - assumes unheated below or slab)
        floor_u = 0.05  # Approximate for slab edge
        floor_loss = floor_area_sqft * floor_u * delta_t * 0.5  # Reduced for ground temp
        breakdown["Floor"] = floor_loss

        envelope_total = wall_loss + roof_loss + window_loss + floor_loss

        # Infiltration heat loss
        # Q = 0.018 × CFM × ΔT (sensible heat)
        cfm_infiltration = (volume_cuft * ach_natural) / 60
        infiltration_loss = 0.018 * cfm_infiltration * delta_t * 60  # BTU/hr
        breakdown["Infiltration"] = infiltration_loss

        # Ventilation (assuming minimal mechanical ventilation)
        cfm_ventilation = floor_area_sqft * 0.03  # ~0.03 CFM/sqft minimum
        ventilation_loss = 0.018 * cfm_ventilation * delta_t * 60
        breakdown["Ventilation"] = ventilation_loss

        total_loss = envelope_total + infiltration_loss + ventilation_loss

        # Generate recommendations
        window_pct = (window_loss / envelope_total) * 100 if envelope_total > 0 else 0
        if window_pct > 30:
            recommendations.append(
                f"Windows account for {window_pct:.0f}% of envelope loss. "
                "Consider higher performance glazing."
            )

        if wall_assembly.r_value < 20 and climate_zone.value >= 5:
            recommendations.append(
                f"Wall R-{wall_assembly.r_value:.0f} is low for Climate Zone {climate_zone.value}. "
                "Consider R-21+ walls."
            )

        if roof_assembly.r_value < 38 and climate_zone.value >= 4:
            recommendations.append(
                f"Roof R-{roof_assembly.r_value:.0f} is low for Climate Zone {climate_zone.value}. "
                "Consider R-49+ attic insulation."
            )

        btuh_per_sqft = total_loss / floor_area_sqft
        if btuh_per_sqft > 30:
            recommendations.append(
                f"Heat loss of {btuh_per_sqft:.1f} BTU/hr/sqft is high. "
                "Review envelope and air sealing."
            )

        return HeatLossResult(
            total_btuh=total_loss,
            envelope_btuh=envelope_total,
            infiltration_btuh=infiltration_loss,
            ventilation_btuh=ventilation_loss,
            component_breakdown=breakdown,
            recommendations=recommendations
        )

    def estimate_air_tightness(
        self,
        floor_area_sqft: float,
        volume_cuft: float,
        stories: int,
        construction_quality: str = "average"  # "tight", "average", "leaky"
    ) -> AirTightnessResult:
        """
        Estimate air tightness based on construction type.

        This is a rough estimate - real testing requires blower door.

        Args:
            floor_area_sqft: Conditioned floor area
            volume_cuft: Conditioned volume
            stories: Number of stories
            construction_quality: "tight", "average", or "leaky"

        Returns:
            AirTightnessResult with ACH estimates
        """
        recommendations = []

        # Typical ACH50 values by construction quality
        ach50_table = {
            "tight": 2.0,      # Passive House level
            "good": 3.0,       # Well-sealed new construction
            "average": 5.0,    # Code-built new construction
            "leaky": 10.0,     # Older or poorly sealed
            "very_leaky": 15.0 # Pre-1980 or no air barrier
        }

        ach50 = ach50_table.get(construction_quality, 5.0)

        # Calculate CFM50
        cfm50 = (volume_cuft * ach50) / 60

        # Estimate natural ACH using LBL correlation
        # ACH_natural ≈ ACH50 / N, where N depends on climate and shielding
        # Simplified: N ≈ 15-20 for typical conditions
        n_factor = 17
        ach_natural = ach50 / n_factor

        # Rating
        if ach50 <= 3:
            rating = "Tight (high performance)"
        elif ach50 <= 5:
            rating = "Average (code compliant)"
        elif ach50 <= 8:
            rating = "Leaky (below average)"
        else:
            rating = "Very Leaky (needs improvement)"

        # Recommendations
        if ach50 > 5:
            recommendations.append("Consider air sealing: caulk, weatherstrip, foam gaps")
            recommendations.append("Check attic hatch, recessed lights, electrical boxes")
        if ach50 > 8:
            recommendations.append("Blower door test recommended to identify major leaks")
            recommendations.append("Consider adding a continuous air barrier")
        if ach50 <= 3:
            recommendations.append("Excellent air tightness - ensure adequate mechanical ventilation")

        return AirTightnessResult(
            ach50=ach50,
            ach_natural=ach_natural,
            cfm50=cfm50,
            rating=rating,
            recommendations=recommendations
        )

    def calculate_condensation_risk(
        self,
        indoor_temp_f: float,
        indoor_rh_pct: float,
        surface_temp_f: float
    ) -> Dict:
        """
        Check if condensation is likely on a surface.

        Args:
            indoor_temp_f: Indoor air temperature (°F)
            indoor_rh_pct: Indoor relative humidity (%)
            surface_temp_f: Temperature of surface (window, wall, etc.)

        Returns:
            Dict with dew point and condensation risk
        """
        # Approximate dew point calculation
        # Using simplified Magnus formula
        indoor_temp_c = (indoor_temp_f - 32) * 5/9
        rh = indoor_rh_pct / 100

        a = 17.27
        b = 237.7

        alpha = (a * indoor_temp_c) / (b + indoor_temp_c) + np.log(rh)
        dew_point_c = (b * alpha) / (a - alpha)
        dew_point_f = dew_point_c * 9/5 + 32

        surface_temp_c = (surface_temp_f - 32) * 5/9

        condensation_risk = surface_temp_f <= dew_point_f
        margin = surface_temp_f - dew_point_f

        return {
            "dew_point_f": dew_point_f,
            "surface_temp_f": surface_temp_f,
            "margin_f": margin,
            "condensation_risk": condensation_risk,
            "recommendation": (
                "Condensation likely - improve window performance or reduce indoor humidity"
                if condensation_risk else
                f"OK - {margin:.1f}°F margin above dew point"
            )
        }


# Quick test
if __name__ == "__main__":
    analyzer = ThermalAnalyzer()

    # Test heat loss for a small house
    result = analyzer.calculate_heat_loss(
        climate_zone=ClimateZone.ZONE_5,
        floor_area_sqft=1500,
        wall_area_sqft=1200,
        wall_assembly=Assembly.wall_2x4_r13(),
        roof_area_sqft=1500,
        roof_assembly=Assembly.roof_r38(),
        window_area_sqft=200,
        window=Window.double_pane_low_e(),
        volume_cuft=12000,
    )

    print(f"Total heat loss: {result.total_btuh:,.0f} BTU/hr")
    print(f"Per sqft: {result.total_btuh/1500:.1f} BTU/hr/sqft")
    print("\nBreakdown:")
    for component, loss in result.component_breakdown.items():
        print(f"  {component}: {loss:,.0f} BTU/hr")
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
