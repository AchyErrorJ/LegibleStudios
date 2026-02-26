"""
Code Studio - Building code and regulation interpretation.

Analyzes building geometry for code compliance: egress, accessibility, zoning.
"""

from typing import Dict, List, Any, Optional
from ..core.constraint_lens import ConstraintLens, LensResult, ConstraintPriority


class CodeStudio(ConstraintLens):
    """Code constraint lens - egress, accessibility, zoning compliance."""

    @property
    def name(self) -> str:
        return "Code Studio"

    @property
    def description(self) -> str:
        return "Compliance fixtures - egress, accessibility, zoning"

    def analyze(self, geometry: Dict[str, Any], 
                intensity: float = 0.5) -> LensResult:
        """Analyze geometry for code compliance."""
        result = LensResult(studio_name=self.name)

        rooms = geometry.get("rooms", [])
        doors = geometry.get("doors", [])
        stairs = geometry.get("stairs", [])
        windows = geometry.get("windows", [])

        # Egress analysis
        egress_paths = self._analyze_egress(rooms, doors, stairs)
        result.metrics["egress_paths"] = len(egress_paths)
        result.metrics["min_egress_width_mm"] = self._min_egress_width(doors)

        # Accessibility
        accessible_rooms = self._check_accessibility(rooms, doors)
        result.metrics["accessible_rooms"] = accessible_rooms

        # Zoning checks
        setbacks = geometry.get("setbacks", {})
        result.metrics["setback_compliance"] = self._check_setbacks(geometry, setbacks)

        # Natural light
        light_compliance = self._check_natural_light(rooms, windows)
        result.metrics["light_compliance"] = light_compliance

        # Violations based on intensity
        if intensity > 0.3:
            # Check bedroom egress
            for room in rooms:
                if "bedroom" in room.get("type", "").lower():
                    has_egress_window = self._has_egress_window(room, windows)
                    if not has_egress_window:
                        result.add_violation(
                            message=f"{room.get('name', 'Bedroom')} lacks required egress window",
                            priority=ConstraintPriority.CRITICAL,
                            location=room.get("center"),
                            element_id=room.get("id"),
                            suggestion="Add window with minimum 0.35m² clear opening"
                        )

            # Check corridor widths
            corridors = self._identify_corridors(geometry)
            for corridor in corridors:
                if corridor.get("width", 0) < 1100:  # 1.1m minimum
                    result.add_violation(
                        message=f"Corridor width {corridor.get('width', 0)}mm below 1100mm minimum",
                        priority=ConstraintPriority.CRITICAL,
                        location=corridor.get("center"),
                        suggestion="Widen corridor or seek variance"
                    )

            # Check stair riser/tread
            for stair in stairs:
                riser = stair.get("riser_mm", 0)
                tread = stair.get("tread_mm", 0)
                if riser > 200 or tread < 250:
                    result.add_violation(
                        message=f"Stair dimensions non-compliant (riser {riser}mm, tread {tread}mm)",
                        priority=ConstraintPriority.CRITICAL,
                        location=stair.get("center"),
                        suggestion="Adjust to max 200mm riser, min 250mm tread"
                    )

        result.score = self._calculate_score(result)
        return result

    def get_visual_overlays(self, geometry: Dict[str, Any],
                           intensity: float = 0.5) -> List[Dict]:
        """Get code compliance visual overlays."""
        overlays = []

        # Egress routes
        rooms = geometry.get("rooms", [])
        doors = geometry.get("doors", [])
        stairs = geometry.get("stairs", [])

        egress_paths = self._analyze_egress(rooms, doors, stairs)
        for path in egress_paths:
            overlays.append({
                "type": "egress_route",
                "path": path["points"],
                "width": path.get("width", 1100),
                "color": "green" if path.get("compliant") else "red",
                "studio": "code"
            })

        # Accessibility zones
        for room in rooms:
            if room.get("accessible", False):
                overlays.append({
                    "type": "accessibility_zone",
                    "room_id": room.get("id"),
                    "turning_circle": room.get("turning_circle", 1500),
                    "color": "blue",
                    "studio": "code"
                })

        # Setback lines
        setbacks = geometry.get("setbacks", {})
        for direction, distance in setbacks.items():
            overlays.append({
                "type": "setback_line",
                "direction": direction,
                "distance": distance,
                "color": "purple",
                "studio": "code"
            })

        return overlays

    def _analyze_egress(self, rooms: List[Dict], doors: List[Dict], 
                       stairs: List[Dict]) -> List[Dict]:
        """Analyze egress paths from each room."""
        paths = []
        
        for room in rooms:
            room_doors = [d for d in doors if d.get("room_id") == room.get("id")]
            for door in room_doors:
                path = {
                    "room_id": room.get("id"),
                    "door_id": door.get("id"),
                    "points": [room.get("center"), door.get("center")],
                    "width": door.get("width", 800),
                    "compliant": door.get("width", 0) >= 800
                }
                paths.append(path)

        return paths

    def _min_egress_width(self, doors: List[Dict]) -> int:
        """Get minimum egress door width."""
        widths = [d.get("width", 800) for d in doors if d.get("egress", False)]
        return min(widths) if widths else 0

    def _check_accessibility(self, rooms: List[Dict], doors: List[Dict]) -> int:
        """Count accessible rooms."""
        accessible = 0
        for room in rooms:
            if room.get("accessible", False):
                accessible += 1
        return accessible

    def _check_setbacks(self, geometry: Dict, setbacks: Dict) -> float:
        """Check setback compliance 0-1."""
        # Simplified - would check actual building position
        return 1.0

    def _check_natural_light(self, rooms: List[Dict], windows: List[Dict]) -> float:
        """Check natural light compliance."""
        compliant = 0
        for room in rooms:
            if self._has_required_light(room, windows):
                compliant += 1
        return compliant / len(rooms) if rooms else 1.0

    def _has_egress_window(self, room: Dict, windows: List[Dict]) -> bool:
        """Check if room has code-compliant egress window."""
        room_windows = [w for w in windows if w.get("room_id") == room.get("id")]
        for window in room_windows:
            if window.get("egress", False) or window.get("area", 0) >= 0.35:
                return True
        return False

    def _has_required_light(self, room: Dict, windows: List[Dict]) -> bool:
        """Check if room has required natural light."""
        room_windows = [w for w in windows if w.get("room_id") == room.get("id")]
        window_area = sum(w.get("area", 0) for w in room_windows)
        floor_area = room.get("area", 0)
        return floor_area > 0 and window_area / floor_area >= 0.1

    def _identify_corridors(self, geometry: Dict) -> List[Dict]:
        """Identify corridor spaces."""
        # Simplified - would analyze circulation
        return geometry.get("corridors", [])

    def _calculate_score(self, result: LensResult) -> float:
        """Calculate overall code compliance score."""
        base_score = 1.0
        base_score -= result.get_critical_count() * 0.5
        base_score -= result.get_warning_count() * 0.1
        return max(0.0, min(1.0, base_score))
