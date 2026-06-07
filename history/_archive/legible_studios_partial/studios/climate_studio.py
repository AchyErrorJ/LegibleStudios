"""
Climate Studio - Environmental constraint interpretation.

Analyzes building geometry for thermal, wind, and solar performance.
"""

from typing import Dict, List, Any, Optional
from ..core.constraint_lens import ConstraintLens, LensResult, ConstraintPriority


class ClimateStudio(ConstraintLens):
    """Climate constraint lens - thermal, wind, solar analysis."""

    @property
    def name(self) -> str:
        return "Climate Studio"

    @property
    def description(self) -> str:
        return "Environmental topology - thermal, wind, solar analysis"

    def analyze(self, geometry: Dict[str, Any], 
                intensity: float = 0.5) -> LensResult:
        """Analyze geometry for climate constraints."""
        result = LensResult(studio_name=self.name)

        rooms = geometry.get("rooms", [])
        walls = geometry.get("walls", [])
        openings = geometry.get("openings", [])

        # Solar analysis
        south_facing_rooms = self._identify_south_facing_rooms(rooms, walls)
        result.metrics["south_facing_rooms"] = len(south_facing_rooms)
        result.metrics["solar_gain_potential"] = self._calculate_solar_gain(south_facing_rooms, openings)

        # Thermal zoning
        thermal_zones = self._analyze_thermal_zoning(rooms)
        result.metrics["thermal_zones"] = len(thermal_zones)

        # Natural ventilation
        cross_ventilation = self._analyze_cross_ventilation(rooms, openings)
        result.metrics["cross_ventilation_score"] = cross_ventilation

        # Check for issues based on intensity
        if intensity > 0.3:
            # Check living spaces without daylight
            for room in rooms:
                if room.get("type") in ["living", "kitchen", "dining"]:
                    window_area = self._get_window_area_for_room(room, openings)
                    room_area = room.get("area", 0)
                    if room_area > 0 and window_area / room_area < 0.1:
                        result.add_violation(
                            message=f"{room.get('name', 'Room')} has insufficient daylight",
                            priority=ConstraintPriority.WARNING if intensity < 0.7 else ConstraintPriority.CRITICAL,
                            location=room.get("center"),
                            element_id=room.get("id"),
                            suggestion="Add windows or skylights"
                        )

        # Calculate overall score
        result.score = self._calculate_score(result)
        return result

    def get_visual_overlays(self, geometry: Dict[str, Any],
                           intensity: float = 0.5) -> List[Dict]:
        """Get climate visual overlays."""
        overlays = []

        # Solar zones
        rooms = geometry.get("rooms", [])
        for room in rooms:
            solar_exposure = self._calculate_room_solar_exposure(room, geometry)
            if solar_exposure > 0.3:
                overlays.append({
                    "type": "heatmap_zone",
                    "geometry": room.get("polygon"),
                    "intensity": solar_exposure,
                    "color": "orange",
                    "label": f"Solar: {solar_exposure:.0%}",
                    "studio": "climate"
                })

        # Wind roses (simplified)
        building_center = self._get_building_center(geometry)
        if building_center:
            overlays.append({
                "type": "wind_rose",
                "center": building_center,
                "radius": 50,
                "studio": "climate"
            })

        return overlays

    def _identify_south_facing_rooms(self, rooms: List[Dict], walls: List[Dict]) -> List[Dict]:
        """Identify rooms with significant south-facing exposure."""
        # Simplified - would use actual wall normals
        return [r for r in rooms if r.get("orientation") == "south"]

    def _calculate_solar_gain(self, rooms: List[Dict], openings: List[Dict]) -> float:
        """Calculate potential solar gain."""
        total_gain = 0
        for room in rooms:
            room_openings = [o for o in openings if o.get("room_id") == room.get("id")]
            total_gain += sum(o.get("area", 0) * 0.5 for o in room_openings)  # kW approx
        return total_gain

    def _analyze_thermal_zoning(self, rooms: List[Dict]) -> List[Dict]:
        """Group rooms into thermal zones."""
        zones = []
        # Group by floor and exposure
        floors = {}
        for room in rooms:
            floor = room.get("floor", 0)
            if floor not in floors:
                floors[floor] = []
            floors[floor].append(room)

        for floor, floor_rooms in floors.items():
            zones.append({
                "floor": floor,
                "rooms": [r.get("id") for r in floor_rooms],
                "type": "perimeter" if any(r.get("exterior", False) for r in floor_rooms) else "core"
            })

        return zones

    def _analyze_cross_ventilation(self, rooms: List[Dict], openings: List[Dict]) -> float:
        """Score cross-ventilation potential 0-1."""
        scores = []
        for room in rooms:
            room_openings = [o for o in openings if o.get("room_id") == room.get("id")]
            if len(room_openings) >= 2:
                # Check if openings are on opposite walls
                scores.append(0.8)
            elif len(room_openings) == 1:
                scores.append(0.3)
            else:
                scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0

    def _get_window_area_for_room(self, room: Dict, openings: List[Dict]) -> float:
        """Get total window area for a room."""
        room_openings = [o for o in openings if o.get("room_id") == room.get("id")]
        return sum(o.get("area", 0) for o in room_openings if o.get("type") == "window")

    def _calculate_room_solar_exposure(self, room: Dict, geometry: Dict) -> float:
        """Calculate solar exposure 0-1 for a room."""
        # Simplified calculation
        orientation = room.get("orientation", "")
        if "south" in orientation.lower():
            return 0.8
        elif "east" in orientation.lower():
            return 0.6
        elif "west" in orientation.lower():
            return 0.5
        return 0.2

    def _get_building_center(self, geometry: Dict) -> Optional[tuple]:
        """Calculate building centroid."""
        rooms = geometry.get("rooms", [])
        if not rooms:
            return None
        
        centers = [r.get("center", (0, 0)) for r in rooms if "center" in r]
        if not centers:
            return None

        avg_x = sum(c[0] for c in centers) / len(centers)
        avg_y = sum(c[1] for c in centers) / len(centers)
        return (avg_x, avg_y)

    def _calculate_score(self, result: LensResult) -> float:
        """Calculate overall climate score."""
        base_score = 1.0
        base_score -= result.get_critical_count() * 0.3
        base_score -= result.get_warning_count() * 0.1
        return max(0.0, min(1.0, base_score))
