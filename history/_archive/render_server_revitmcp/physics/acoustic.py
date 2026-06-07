# acoustic.py
# Acoustic analysis module - sound transmission, reverberation
#
# Future: Integrate with or port concepts from:
# - ODEON (room acoustics)
# - COMSOL Acoustics (FEM)
# - Custom ray-tracing acoustics

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import math

print("=== ACOUSTIC ANALYZER LOADED ===")


class OccupancyType(Enum):
    """Room types for acoustic criteria"""
    RESIDENTIAL_BEDROOM = "residential_bedroom"
    RESIDENTIAL_LIVING = "residential_living"
    OFFICE_PRIVATE = "office_private"
    OFFICE_OPEN = "office_open"
    CLASSROOM = "classroom"
    MUSIC_REHEARSAL = "music_rehearsal"
    AUDITORIUM = "auditorium"
    RESTAURANT = "restaurant"


# STC (Sound Transmission Class) requirements by adjacency type
STC_REQUIREMENTS = {
    ("residential", "residential"): 50,  # Code minimum
    ("residential", "corridor"): 45,
    ("residential", "mechanical"): 55,
    ("office", "office"): 45,
    ("classroom", "classroom"): 50,
    ("music", "any"): 60,
}

# Recommended reverberation times (seconds) by space type
TARGET_RT60 = {
    OccupancyType.RESIDENTIAL_BEDROOM: (0.4, 0.6),
    OccupancyType.RESIDENTIAL_LIVING: (0.5, 0.8),
    OccupancyType.OFFICE_PRIVATE: (0.4, 0.6),
    OccupancyType.OFFICE_OPEN: (0.6, 0.8),
    OccupancyType.CLASSROOM: (0.6, 0.8),
    OccupancyType.MUSIC_REHEARSAL: (0.8, 1.2),
    OccupancyType.AUDITORIUM: (1.2, 1.8),
    OccupancyType.RESTAURANT: (0.6, 1.0),
}


@dataclass
class WallAssembly:
    """Wall assembly with acoustic properties"""
    name: str
    stc: int  # Sound Transmission Class

    @classmethod
    def drywall_single(cls):
        """Single layer drywall on studs"""
        return cls("Single Drywall", 33)

    @classmethod
    def drywall_double(cls):
        """Double layer drywall on studs"""
        return cls("Double Drywall", 40)

    @classmethod
    def drywall_staggered_studs(cls):
        """Double drywall, staggered studs, insulation"""
        return cls("Staggered Stud Wall", 52)

    @classmethod
    def drywall_resilient_channel(cls):
        """Drywall on resilient channel"""
        return cls("Resilient Channel Wall", 48)

    @classmethod
    def double_stud_wall(cls):
        """Double stud wall with air gap"""
        return cls("Double Stud Wall", 58)


@dataclass
class SurfaceMaterial:
    """Surface material with absorption coefficients"""
    name: str
    absorption_coefficients: Dict[int, float]  # {frequency_hz: coefficient}

    @classmethod
    def concrete(cls):
        return cls("Concrete", {125: 0.01, 250: 0.01, 500: 0.02, 1000: 0.02, 2000: 0.02, 4000: 0.03})

    @classmethod
    def drywall(cls):
        return cls("Drywall", {125: 0.29, 250: 0.10, 500: 0.05, 1000: 0.04, 2000: 0.07, 4000: 0.09})

    @classmethod
    def carpet(cls):
        return cls("Carpet", {125: 0.05, 250: 0.10, 500: 0.20, 1000: 0.45, 2000: 0.65, 4000: 0.70})

    @classmethod
    def acoustic_ceiling(cls):
        return cls("Acoustic Ceiling Tile", {125: 0.20, 250: 0.40, 500: 0.70, 1000: 0.80, 2000: 0.80, 4000: 0.75})

    @classmethod
    def glass(cls):
        return cls("Glass", {125: 0.25, 250: 0.15, 500: 0.10, 1000: 0.07, 2000: 0.05, 4000: 0.05})

    @classmethod
    def heavy_curtain(cls):
        return cls("Heavy Curtain", {125: 0.15, 250: 0.35, 500: 0.55, 1000: 0.75, 2000: 0.80, 4000: 0.80})


@dataclass
class STCResult:
    """Result of sound transmission analysis"""
    stc_rating: int
    required_stc: int
    passes: bool
    margin: int  # dB above/below requirement
    recommendations: List[str]


@dataclass
class ReverberationResult:
    """Result of reverberation analysis"""
    rt60_seconds: float  # At 500-1000 Hz
    target_range: tuple  # (min, max)
    within_target: bool
    rt60_by_frequency: Dict[int, float]
    recommendations: List[str]


class AcousticAnalyzer:
    """
    Acoustic analysis for architectural design.

    Phase 1: STC calculations and Sabine reverberation
    Phase 2: Ray-tracing room acoustics, flanking paths
    """

    def __init__(self):
        pass

    def check_sound_transmission(
        self,
        wall_assembly: WallAssembly,
        source_space: str,
        receiver_space: str,
    ) -> STCResult:
        """
        Check if wall assembly meets STC requirements for adjacency.

        Args:
            wall_assembly: Wall construction
            source_space: Type of space on source side
            receiver_space: Type of space on receiving side

        Returns:
            STCResult with pass/fail and recommendations
        """
        recommendations = []

        # Find required STC
        required_stc = 45  # Default
        for (s1, s2), stc in STC_REQUIREMENTS.items():
            if (s1 in source_space.lower() or s1 == "any") and \
               (s2 in receiver_space.lower() or s2 == "any"):
                required_stc = stc
                break

        margin = wall_assembly.stc - required_stc
        passes = margin >= 0

        if not passes:
            recommendations.append(
                f"Wall STC {wall_assembly.stc} is {abs(margin)} points below required {required_stc}"
            )
            if wall_assembly.stc < 40:
                recommendations.append("Consider double drywall or resilient channels")
            elif wall_assembly.stc < 50:
                recommendations.append("Consider staggered stud or double stud construction")
            else:
                recommendations.append("Consider adding mass or decoupling")
        else:
            recommendations.append(
                f"Wall STC {wall_assembly.stc} meets requirement ({margin} point margin)"
            )

        # General recommendations
        if "mechanical" in receiver_space.lower() or "mechanical" in source_space.lower():
            recommendations.append("Seal all penetrations and gaps for mechanical room adjacency")

        return STCResult(
            stc_rating=wall_assembly.stc,
            required_stc=required_stc,
            passes=passes,
            margin=margin,
            recommendations=recommendations
        )

    def calculate_reverberation_time(
        self,
        volume_cuft: float,
        surfaces: List[Dict],  # [{"material": SurfaceMaterial, "area_sqft": float}, ...]
        occupancy_type: OccupancyType,
        num_occupants: int = 0
    ) -> ReverberationResult:
        """
        Calculate reverberation time using Sabine equation.

        RT60 = 0.049 × V / A
        Where V = volume (ft³), A = total absorption (sabins)

        Args:
            volume_cuft: Room volume in cubic feet
            surfaces: List of surfaces with materials and areas
            occupancy_type: Type of space for target RT60
            num_occupants: Number of people (add absorption)

        Returns:
            ReverberationResult with RT60 values
        """
        recommendations = []

        # Frequencies to analyze
        frequencies = [125, 250, 500, 1000, 2000, 4000]

        # Calculate absorption at each frequency
        rt60_by_freq = {}

        for freq in frequencies:
            total_absorption = 0

            # Surface absorption
            for surface in surfaces:
                material = surface["material"]
                area = surface["area_sqft"]
                alpha = material.absorption_coefficients.get(freq, 0.1)
                total_absorption += alpha * area

            # Occupant absorption (~4.5 sabins per person at mid frequencies)
            if freq >= 500:
                total_absorption += num_occupants * 4.5
            else:
                total_absorption += num_occupants * 2.5

            # Sabine equation
            # RT60 = 0.049 × V / A (imperial units)
            rt60 = (0.049 * volume_cuft) / total_absorption if total_absorption > 0 else 5.0
            rt60_by_freq[freq] = rt60

        # Average RT60 at 500-1000 Hz (typical reporting)
        rt60_mid = (rt60_by_freq[500] + rt60_by_freq[1000]) / 2

        # Target range
        target_range = TARGET_RT60.get(occupancy_type, (0.5, 1.0))
        within_target = target_range[0] <= rt60_mid <= target_range[1]

        # Recommendations
        if rt60_mid > target_range[1]:
            recommendations.append(
                f"RT60 {rt60_mid:.2f}s exceeds target {target_range[1]}s - room is too reverberant"
            )
            recommendations.append("Add absorptive materials: acoustic panels, carpet, curtains")
        elif rt60_mid < target_range[0]:
            recommendations.append(
                f"RT60 {rt60_mid:.2f}s below target {target_range[0]}s - room is too dead"
            )
            recommendations.append("Reduce absorption or add reflective surfaces")
        else:
            recommendations.append(
                f"RT60 {rt60_mid:.2f}s within target range {target_range}"
            )

        # Check frequency balance
        low_freq_rt = rt60_by_freq[125]
        high_freq_rt = rt60_by_freq[4000]
        if low_freq_rt > rt60_mid * 1.5:
            recommendations.append("Low frequency RT is high - consider bass traps in corners")

        return ReverberationResult(
            rt60_seconds=rt60_mid,
            target_range=target_range,
            within_target=within_target,
            rt60_by_frequency=rt60_by_freq,
            recommendations=recommendations
        )

    def estimate_noise_criteria(
        self,
        hvac_cfm: float,
        room_volume_cuft: float,
        diffuser_count: int = 1
    ) -> Dict:
        """
        Estimate HVAC noise level (NC/RC rating).

        Args:
            hvac_cfm: Total supply air CFM
            room_volume_cuft: Room volume
            diffuser_count: Number of supply diffusers

        Returns:
            Dict with estimated NC rating and recommendations
        """
        # CFM per diffuser
        cfm_per_diffuser = hvac_cfm / max(1, diffuser_count)

        # Rough NC estimate based on velocity
        # Higher velocity = more noise
        if cfm_per_diffuser < 100:
            estimated_nc = 25
        elif cfm_per_diffuser < 200:
            estimated_nc = 30
        elif cfm_per_diffuser < 400:
            estimated_nc = 35
        elif cfm_per_diffuser < 600:
            estimated_nc = 40
        else:
            estimated_nc = 45

        recommendations = []
        if estimated_nc > 35:
            recommendations.append("High airflow per diffuser may cause noise - add more diffusers")
        if cfm_per_diffuser > 300:
            recommendations.append("Consider larger or additional diffusers to reduce velocity")

        return {
            "estimated_nc": estimated_nc,
            "cfm_per_diffuser": cfm_per_diffuser,
            "recommendations": recommendations
        }


# Quick test
if __name__ == "__main__":
    analyzer = AcousticAnalyzer()

    # Test reverberation calculation
    surfaces = [
        {"material": SurfaceMaterial.drywall(), "area_sqft": 800},  # Walls
        {"material": SurfaceMaterial.acoustic_ceiling(), "area_sqft": 400},  # Ceiling
        {"material": SurfaceMaterial.carpet(), "area_sqft": 400},  # Floor
        {"material": SurfaceMaterial.glass(), "area_sqft": 100},  # Windows
    ]

    result = analyzer.calculate_reverberation_time(
        volume_cuft=3600,
        surfaces=surfaces,
        occupancy_type=OccupancyType.OFFICE_PRIVATE,
        num_occupants=2
    )

    print(f"RT60: {result.rt60_seconds:.2f} seconds")
    print(f"Target: {result.target_range}")
    print(f"Within target: {result.within_target}")
    print("\nRT60 by frequency:")
    for freq, rt in result.rt60_by_frequency.items():
        print(f"  {freq} Hz: {rt:.2f}s")
    print("\nRecommendations:")
    for rec in result.recommendations:
        print(f"  - {rec}")
