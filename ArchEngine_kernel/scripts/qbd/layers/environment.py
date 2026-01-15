"""Environment Layer - Physics of building reality.

Models how the building interacts with physical forces:
- Solar: Sun path, shading, daylighting, glare
- Thermal: Heat transfer, insulation, passive strategies
- Acoustic: Sound transmission, reverberation, privacy
- Air: Ventilation, cross-breezes, air quality
- Structure: Span limits, loads, seismic

This is not optimization - it's constraint modeling.
The physics reveals what's POSSIBLE, not what's "best".
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math


class ClimateZone(Enum):
    """IECC climate zones (simplified)."""
    HOT_HUMID = "1A"
    HOT_DRY = "1B"
    MIXED_HUMID = "2A"
    MIXED_DRY = "2B"
    MIXED_MARINE = "3C"
    COOL_HUMID = "4A"
    COOL_DRY = "4B"
    COLD = "5"
    VERY_COLD = "6"
    SUBARCTIC = "7"
    ARCTIC = "8"


class CardinalDirection(Enum):
    """Cardinal and intercardinal directions."""
    N = 0
    NE = 45
    E = 90
    SE = 135
    S = 180
    SW = 225
    W = 270
    NW = 315


# =============================================================================
# Solar Analysis
# =============================================================================

@dataclass
class SolarPosition:
    """Position of the sun at a given time."""
    azimuth: float  # Degrees from north, clockwise
    altitude: float  # Degrees above horizon
    hour: int  # 0-23
    month: int  # 1-12


@dataclass
class DaylightResult:
    """Result of daylight analysis for a room."""
    room_id: str
    daylight_factor: float  # 0-1, percentage of exterior illuminance
    direct_hours: Dict[str, int]  # Hours of direct sun by season
    uv_exposure: float  # Relative UV damage risk
    glare_potential: str  # "low", "medium", "high"
    recommended_shading: List[str]  # Suggested shading strategies


class SolarAnalysis:
    """Analyzes solar relationships."""

    def __init__(self, site_data: Dict[str, Any]):
        """Initialize with site context.

        Args:
            site_data: Site info including latitude, climate zone, orientation
        """
        self.latitude = site_data.get("latitude", 40.0)  # Default ~NYC
        self.climate_zone = ClimateZone(site_data.get("climate_zone", "4A"))
        self.front_faces = CardinalDirection[site_data.get("orientation", {}).get("front_faces", "S")]
        self.hemisphere = "N" if self.latitude >= 0 else "S"

    def calculate_sun_position(self, month: int, hour: int, day: int = 15) -> SolarPosition:
        """Calculate sun position (simplified).

        Args:
            month: 1-12
            hour: 0-23 (solar time)
            day: Day of month (default 15 for average)

        Returns:
            SolarPosition with azimuth and altitude
        """
        # Approximate declination angle
        day_of_year = (month - 1) * 30 + day
        declination = 23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365))

        # Hour angle
        hour_angle = 15 * (hour - 12)  # Solar noon at hour 12

        # Altitude
        lat_rad = math.radians(self.latitude)
        dec_rad = math.radians(declination)
        ha_rad = math.radians(hour_angle)

        altitude = math.asin(
            math.sin(lat_rad) * math.sin(dec_rad) +
            math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad)
        )

        # Azimuth
        azimuth = math.atan2(
            math.sin(ha_rad),
            math.cos(ha_rad) * math.sin(lat_rad) -
            math.tan(dec_rad) * math.cos(lat_rad)
        )

        return SolarPosition(
            azimuth=math.degrees(azimuth),
            altitude=max(0, math.degrees(altitude)),
            hour=hour,
            month=month
        )

    def analyze_room_daylight(
        self,
        room: Dict[str, Any],
        building_layout: Dict[str, Any]
    ) -> DaylightResult:
        """Analyze daylight potential for a room.

        Considers:
        - Window orientation (south = best in N hemisphere)
        - Obstructions (adjacent rooms, overhangs)
        - Room depth (light penetrates ~2x window height)
        """
        room_id = room.get("id")
        room_type = room.get("type")
        window_area = room.get("window_area", 0)
        floor_area = room.get("area_min", 10)

        # Default window area if not specified (20% of floor area)
        if window_area == 0:
            window_area = floor_area * 0.2

        # Get window orientations
        windows = room.get("windows", [])
        if not windows:
            # Infer from room type defaults
            window_prefs = room.get("window_preferences", {})
            orientation_str = window_prefs.get("orientation") or "S"
            orientation = CardinalDirection[orientation_str.upper()]
            windows = [{"orientation": orientation, "area": window_area}]

        # Calculate daylight factor (simplified)
        # DF = (Window Area * Transmittance * Angle factor) / (Floor Area * 2)
        daylight_factor = 0.0
        direct_solar_hours = {"summer": 0, "equinox": 0, "winter": 0}
        uv_risk = 0.0

        for window in windows:
            orientation = window.get("orientation")
            area = window.get("area", window_area)

            # Orientation effectiveness (N hemisphere)
            effectiveness = {
                CardinalDirection.S: 1.0,
                CardinalDirection.SE: 0.9,
                CardinalDirection.SW: 0.9,
                CardinalDirection.E: 0.7,
                CardinalDirection.W: 0.6,
                CardinalDirection.NE: 0.4,
                CardinalDirection.NW: 0.4,
                CardinalDirection.N: 0.3,
            }

            eff = effectiveness.get(orientation, 0.5)
            daylight_factor += (area * 0.85 * eff) / (floor_area * 2)

            # Direct solar hours (simplified)
            if orientation in (CardinalDirection.S, CardinalDirection.SE, CardinalDirection.SW):
                direct_solar_hours["winter"] = 4
                direct_solar_hours["equinox"] = 6
                direct_solar_hours["summer"] = 8
            elif orientation in (CardinalDirection.E,):
                direct_solar_hours["winter"] = 2
                direct_solar_hours["equinox"] = 3
                direct_solar_hours["summer"] = 4
            elif orientation in (CardinalDirection.W,):
                direct_solar_hours["winter"] = 1
                direct_solar_hours["equinox"] = 2
                direct_solar_hours["summer"] = 3

            # UV exposure (south/west get more)
            uv_risk += 0.3 * eff

        # Glare potential
        glare = "low"
        if daylight_factor > 0.15:
            glare = "high"
        elif daylight_factor > 0.08:
            glare = "medium"

        # Shading recommendations
        shading = []
        if direct_solar_hours["summer"] >= 6:
            shading.append("overhangs")
            shading.append("deciduous vegetation")
        if glare in ("medium", "high"):
            shading.append("light shelves")
            shading.append("diffusing glass")

        return DaylightResult(
            room_id=room_id,
            daylight_factor=min(1.0, daylight_factor),
            direct_hours=direct_solar_hours,
            uv_exposure=min(1.0, uv_risk),
            glare_potential=glare,
            recommended_shading=shading
        )

    def recommend_overhang_depth(self, orientation: CardinalDirection) -> float:
        """Calculate recommended overhang depth (simplified).

        Rule of thumb: Overhang should shade window at solar noon in summer
        but allow sun in winter.

        Returns depth in meters.
        """
        # Sun angle: summer (~70°), winter (~25°) at mid-latitudes
        window_height = 2.1  # Standard window height (m)

        if self.hemisphere == "N":
            if orientation in (CardinalDirection.S,):
                # Summer shading
                summer_alt = 70
                winter_alt = 25

                # Shade in summer: depth = height / tan(altitude)
                overhang = window_height / math.tan(math.radians(summer_alt))
                return round(overhang, 2)
            elif orientation in (CardinalDirection.E, CardinalDirection.W):
                # Vertical fins needed (not horizontal overhangs)
                return 0.3  # Minimal for aesthetics

        return 0.5  # Default


# =============================================================================
# Thermal Analysis
# =============================================================================

@dataclass
class ThermalZone:
    """Thermal properties of a space."""
    room_id: str
    heating_load: float  # Watts
    cooling_load: float  # Watts
    insulation_level: str  # "code_minimum", "improved", "passive_house"
    thermal_mass: str  # "light", "medium", "heavy"
    heat_loss_coefficient: float  # W/K


@dataclass
class ThermalResult:
    """Result of thermal analysis."""
    zones: List[ThermalZone]
    total_heating_load: float  # kW
    total_cooling_load: float  # kW
    peak_heating_month: str
    peak_cooling_month: str
    recommended_insulation: Dict[str, str]
    passive_strategy_potential: List[str]  # "night_flush", "thermal_mass", etc.


class ThermalAnalysis:
    """Analyzes thermal performance."""

    def __init__(self, climate_zone: ClimateZone):
        """Initialize with climate context."""
        self.climate_zone = climate_zone

        # Heating/cooling degree days by zone (approximate)
        self._hdd_by_zone = {
            ClimateZone.HOT_HUMID: 100,
            ClimateZone.HOT_DRY: 200,
            ClimateZone.MIXED_HUMID: 1500,
            ClimateZone.MIXED_DRY: 1800,
            ClimateZone.COOL_HUMID: 3000,
            ClimateZone.COOL_DRY: 3500,
            ClimateZone.COLD: 5000,
            ClimateZone.VERY_COLD: 7000,
        }

        self._cdd_by_zone = {
            ClimateZone.HOT_HUMID: 3000,
            ClimateZone.HOT_DRY: 3500,
            ClimateZone.MIXED_HUMID: 1500,
            ClimateZone.MIXED_DRY: 2000,
            ClimateZone.COOL_HUMID: 500,
            ClimateZone.COOL_DRY: 800,
            ClimateZone.COLD: 200,
            ClimateZone.VERY_COLD: 100,
        }

    def analyze_building_thermal(
        self,
        rooms: List[Dict[str, Any]],
        adjacencies: List[Dict[str, Any]],
        site: Dict[str, Any]
    ) -> ThermalResult:
        """Analyze thermal performance of building.

        Considers:
        - Envelope area (exterior walls, roof)
        - Insulation levels
        - Climate zone
        - Internal gains (people, equipment)
        - Solar gains
        """
        zones = []
        total_heating = 0.0
        total_cooling = 0.0

        # Get climate severity
        hdd = self._hdd_by_zone.get(self.climate_zone, 2500)
        cdd = self._cdd_by_zone.get(self.climate_zone, 1000)

        for room in rooms:
            room_id = room.get("id")
            area = room.get("area_min", 10)

            # Calculate exterior exposure
            exterior_walls = self._count_exterior_walls(room_id, adjacencies)
            perimeter = exterior_walls * math.sqrt(area)  # Rough estimate
            has_deck_above = self._has_deck_above(room_id, adjacencies)

            # Heat loss coefficient (simplified)
            # U = 0.3 W/m²K (typical insulated wall)
            # A = perimeter * 2.4m (ceiling height)
            u_wall = 0.3
            u_roof = 0.2 if not has_deck_above else 0.0
            ua_value = (perimeter * 2.4 * u_wall) + (area * u_roof)

            # Heating load = UA * ΔT * 24 / 1000
            # ΔT varies by climate, using HDD/365 as proxy
            delta_t_heating = hdd / 365
            heating_load = (ua_value * delta_t_heating * 24) / 1000  # kW
            heating_load_w = heating_load * 1000 * area  # Scale by room size

            # Cooling load
            delta_t_cooling = cdd / 365
            # Add solar gains (simplified)
            solar_gain = area * 50  # 50 W/m² peak solar
            cooling_load = ((ua_value * delta_t_cooling * 24) / 1000) + (solar_gain / 1000)
            cooling_load_w = cooling_load * 1000 * area

            # Determine insulation level from constraints
            constraints = room.get("constraints", {})
            insulation = constraints.get("insulation", "code_minimum")

            zone = ThermalZone(
                room_id=room_id,
                heating_load=round(heating_load_w),
                cooling_load=round(cooling_load_w),
                insulation_level=insulation,
                thermal_mass=constraints.get("thermal_mass", "medium"),
                heat_loss_coefficient=round(ua_value, 2)
            )
            zones.append(zone)
            total_heating += heating_load_w
            total_cooling += cooling_load_w

        # Peak months (simplified)
        peak_heating = "January" if hdd > 1000 else "December"
        peak_cooling = "July" if cdd > 500 else "August"

        # Insulation recommendations
        insulation_recs = {
            "walls": "R-20" if hdd > 3000 else "R-13",
            "roof": "R-40" if hdd > 3000 else "R-30",
            "slab": "R-10" if hdd > 3000 else "R-5",
        }

        # Passive strategies
        passive_potential = []
        if cdd > 1000:
            passive_potential.append("night_flush_ventilation")
        if hdd > 2000:
            passive_potential.append("passive_solar_gain")
        if cdd > 2000:
            passive_potential.append("shading_devices")
        passive_potential.append("natural_ventilation")

        return ThermalResult(
            zones=zones,
            total_heating_load=round(total_heating / 1000, 1),  # kW
            total_cooling_load=round(total_cooling / 1000, 1),
            peak_heating_month=peak_heating,
            peak_cooling_month=peak_cooling,
            recommended_insulation=insulation_recs,
            passive_strategy_potential=passive_potential
        )

    def _count_exterior_walls(self, room_id: str, adjacencies: List[Dict]) -> int:
        """Count how many walls are exterior."""
        # If room has no adjacency on a side, it's exterior
        # Simplified: check adjacency count, assume 4 sides total
        related = [a for a in adjacencies
                   if a.get("room_a") == room_id or a.get("room_b") == room_id]
        return max(1, 4 - len(related))

    def _has_deck_above(self, room_id: str, adjacencies: List[Dict]) -> bool:
        """Check if room has another room above (not roof)."""
        # Simplified: no multi-story analysis yet
        return False


# =============================================================================
# Acoustic Analysis
# =============================================================================

@dataclass
class AcousticResult:
    """Result of acoustic analysis."""
    room_id: str
    stc_rating: int  # Sound Transmission Class (25-60+)
    nrc_rating: float  # Noise Reduction Coefficient (0-1)
    reverberation_time: float  # RT60 in seconds
    privacy_level: str  # "poor", "fair", "good", "excellent"
    noise_sources: List[str]  # Adjacent noisy spaces
    recommendations: List[str]


class AcousticAnalysis:
    """Analyzes acoustic performance."""

    # Target RT60 by room type (seconds)
    RT60_TARGETS = {
        "living": 0.6,
        "great_room": 0.6,
        "dining": 0.5,
        "kitchen": 0.5,
        "bedroom": 0.4,
        "primary_bedroom": 0.4,
        "office": 0.5,
        "bathroom": 0.4,
        "ensuite": 0.4,
        "powder_room": 0.3,
        "laundry": 0.4,
        "garage": 1.0,
    }

    # Noise generation by room type
    NOISE_LEVELS = {
        "kitchen": "loud",
        "laundry": "loud",
        "bathroom": "moderate",
        "living": "moderate",
        "great_room": "moderate",
        "dining": "moderate",
        "office": "quiet",
        "bedroom": "quiet",
        "primary_bedroom": "quiet",
        "powder_room": "moderate",
        "ensuite": "quiet",
    }

    def analyze_room_acoustics(
        self,
        room: Dict[str, Any],
        adjacencies: List[Dict[str, Any]],
        separations: List[Dict[str, Any]]
    ) -> AcousticResult:
        """Analyze acoustic performance.

        Considers:
        - Adjacent noisy spaces
        - Separation requirements
        - Room volume
        - Surface materials
        """
        room_id = room.get("id")
        room_type = room.get("type")
        area = room.get("area_min", 10)
        height = room.get("ceiling_height", 2.7)
        volume = area * height

        # Calculate RT60 (Sabine's formula, simplified)
        # RT60 = 0.161 * V / A
        # A = total absorption = Σ(Surface * α)

        # Default absorption coefficients (assuming typical construction)
        floor_area = area
        wall_area = 2.4 * (2 * math.sqrt(area) + 2 * math.sqrt(area))
        ceiling_area = area

        # Get material preferences
        materials = room.get("finishes", {})
        floor_alpha = {"hard": 0.03, "soft": 0.15, "carpet": 0.35}
        wall_alpha = {"hard": 0.05, "soft": 0.10}
        ceiling_alpha = {"hard": 0.05, "acoustic": 0.60}

        floor_type = materials.get("floor", "hard")
        wall_type = materials.get("walls", "hard")
        ceiling_type = materials.get("ceiling", "hard")

        total_absorption = (
            floor_area * floor_alpha.get(floor_type, 0.03) +
            wall_area * wall_alpha.get(wall_type, 0.05) +
            ceiling_area * ceiling_alpha.get(ceiling_type, 0.05)
        )

        rt60 = 0.161 * volume / total_absorption if total_absorption > 0 else 0.8

        # Check adjacent noise sources
        noise_sources = []
        stc_rating = 35  # Default

        for adj in adjacencies:
            other_id = None
            if adj.get("room_a") == room_id:
                other_id = adj.get("room_b")
            elif adj.get("room_b") == room_id:
                other_id = adj.get("room_a")

            if other_id:
                # Find other room and check noise level
                # This is simplified - in real implementation would look up room
                for other in [r for r in [] if r.get("id") == other_id]:  # Placeholder
                    other_type = other.get("type")
                    if self.NOISE_LEVELS.get(other_type) in ("loud", "moderate"):
                        noise_sources.append(other_id)

                # Check connection type
                connection = adj.get("connection_type", "door")
                if connection == "open":
                    stc_rating = 25  # No separation
                elif connection == "door":
                    stc_rating = 30  # Standard door

        # Check explicit separations
        for sep in separations:
            if sep.get("room_a") == room_id or sep.get("room_b") == room_id:
                buffer = sep.get("buffer", 0)
                if buffer > 0:
                    stc_rating = min(60, stc_rating + 15)
                else:
                    stc_rating = min(55, stc_rating + 10)

        # Calculate NRC (average absorption)
        nrc = total_absorption / (floor_area + wall_area + ceiling_area) if (floor_area + wall_area + ceiling_area) > 0 else 0.1

        # Privacy assessment
        privacy = "poor"
        if stc_rating >= 50:
            privacy = "excellent"
        elif stc_rating >= 45:
            privacy = "good"
        elif stc_rating >= 35:
            privacy = "fair"

        # Recommendations
        recommendations = []
        target_rt60 = self.RT60_TARGETS.get(room_type, 0.5)
        if rt60 > target_rt60 * 1.2:
            recommendations.append("add_acoustic_ceiling")
            recommendations.append("add_soft_furnishings")
        if privacy == "poor" and room_type in ("bedroom", "primary_bedroom", "office"):
            recommendations.append("increase_wall_stc")
            recommendations.append("add_door_seals")

        return AcousticResult(
            room_id=room_id,
            stc_rating=stc_rating,
            nrc_rating=round(nrc, 2),
            reverberation_time=round(rt60, 2),
            privacy_level=privacy,
            noise_sources=noise_sources,
            recommendations=recommendations
        )


# =============================================================================
# Environment Layer (Orchestrator)
# =============================================================================

@dataclass
class EnvironmentResult:
    """Combined environmental analysis result."""
    solar: Dict[str, DaylightResult]  # room_id → DaylightResult
    thermal: ThermalResult
    acoustic: Dict[str, AcousticResult]  # room_id → AcousticResult
    passive_design_strategies: List[str]
    critical_issues: List[str]  # Physics violations


class EnvironmentLayer:
    """Physics-based analysis of building reality.

    This layer doesn't "optimize" - it reveals constraints.
    The physics is what it is.
    """

    def __init__(self, site_data: Dict[str, Any]):
        """Initialize with site context.

        Args:
            site_data: Site configuration including latitude, climate zone
        """
        self.site_data = site_data
        self.solar = SolarAnalysis(site_data)
        climate = ClimateZone(site_data.get("climate_zone", "4A"))
        self.thermal = ThermalAnalysis(climate)
        self.acoustic = AcousticAnalysis()

    def analyze(
        self,
        rooms: List[Dict[str, Any]],
        adjacencies: List[Dict[str, Any]],
        separations: List[Dict[str, Any]],
        building_layout: Dict[str, Any]
    ) -> EnvironmentResult:
        """Run all environmental analyses.

        Returns constraints and requirements imposed by physics.
        """
        # Solar/daylight analysis
        solar_results = {}
        for room in rooms:
            solar_results[room.get("id")] = self.solar.analyze_room_daylight(room, building_layout)

        # Thermal analysis
        thermal_result = self.thermal.analyze_building_thermal(rooms, adjacencies, self.site_data)

        # Acoustic analysis
        acoustic_results = {}
        for room in rooms:
            acoustic_results[room.get("id")] = self.acoustic.analyze_room_acoustics(
                room, adjacencies, separations
            )

        # Identify passive design opportunities
        passive_strategies = self._identify_passive_strategies(solar_results, thermal_result)

        # Check for physics violations
        issues = self._check_physics_constraints(solar_results, thermal_result, acoustic_results)

        return EnvironmentResult(
            solar=solar_results,
            thermal=thermal_result,
            acoustic=acoustic_results,
            passive_design_strategies=passive_strategies,
            critical_issues=issues
        )

    def _identify_passive_strategies(
        self,
        solar: Dict[str, DaylightResult],
        thermal: ThermalResult
    ) -> List[str]:
        """Identify applicable passive design strategies."""
        strategies = []

        # Check solar potential
        south_facing = sum(1 for s in solar.values()
                          if s.direct_hours.get("winter", 0) >= 4)
        if south_facing >= 2:
            strategies.append("passive_solar_heating")

        # Check night flush potential
        if thermal.total_cooling_load > 5:
            strategies.append("night_flush_ventilation")

        # Cross ventilation
        strategies.append("cross_ventilation")  # Always check

        return strategies

    def _check_physics_constraints(
        self,
        solar: Dict[str, DaylightResult],
        thermal: ThermalResult,
        acoustic: Dict[str, AcousticResult]
    ) -> List[str]:
        """Check for violations of physical laws."""
        issues = []

        # Daylight minimums
        for room_id, daylight in solar.items():
            if daylight.daylight_factor < 0.02:  # 2% daylight factor minimum
                issues.append(f"Room {room_id}: Insufficient daylight (< 2%)")

        # Thermal limits
        if thermal.total_heating_load > 50:  # 50kW is a lot for residential
            issues.append(f"Excessive heating load: {thermal.total_heating_load} kW")

        # Acoustic privacy for bedrooms
        for room_id, acoustic_res in acoustic.items():
            if acoustic_res.privacy_level in ("poor", "fair"):
                if "bedroom" in room_id or "primary" in room_id:
                    issues.append(f"Room {room_id}: Poor acoustic privacy ({acoustic_res.privacy_level})")

        return issues
