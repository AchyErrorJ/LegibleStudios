"""
Cost Studio - Budget and constructability interpretation.

Analyzes building geometry for cost estimation and construction feasibility.
"""

from typing import Dict, List, Any
from ..core.constraint_lens import ConstraintLens, LensResult, ConstraintPriority


class CostStudio(ConstraintLens):
    """Cost constraint lens - budget, constructability, material optimization."""

    # Simplified cost rates (per unit)
    COST_RATES = {
        "wall_m2": 150,      # $/m² finished wall
        "floor_m2": 200,     # $/m² finished floor
        "roof_m2": 250,      # $/m² roof
        "window_m2": 800,    # $/m² window
        "door_each": 1200,   # $/door
        "foundation_m3": 400, # $/m³ concrete
    }

    @property
    def name(self) -> str:
        return "Cost Studio"

    @property
    def description(self) -> str:
        return "Specification view - budget, constructability"

    def analyze(self, geometry: Dict[str, Any], 
                intensity: float = 0.5) -> LensResult:
        """Analyze geometry for cost and constructability."""
        result = LensResult(studio_name=self.name)

        rooms = geometry.get("rooms", [])
        walls = geometry.get("walls", [])
        floors = geometry.get("floors", [])
        openings = geometry.get("openings", [])

        # Area calculations
        total_floor_area = sum(r.get("area", 0) for r in rooms)
        total_wall_area = sum(w.get("area", 0) for w in walls)
        window_area = sum(o.get("area", 0) for o in openings if o.get("type") == "window")

        result.metrics["total_floor_area_m2"] = round(total_floor_area, 1)
        result.metrics["total_wall_area_m2"] = round(total_wall_area, 1)
        result.metrics["window_area_m2"] = round(window_area, 1)
        result.metrics["window_to_floor_ratio"] = round(window_area / total_floor_area, 2) if total_floor_area > 0 else 0

        # Cost estimation
        estimated_cost = self._estimate_cost(geometry)
        result.metrics["estimated_cost_usd"] = estimated_cost
        result.metrics["cost_per_m2"] = round(estimated_cost / total_floor_area, 0) if total_floor_area > 0 else 0

        # Constructability score
        constructability = self._assess_constructability(geometry)
        result.metrics["constructability_score"] = constructability

        # Complexity metrics
        result.metrics["corner_count"] = self._count_corners(walls)
        result.metrics["unique_wall_lengths"] = len(set(round(w.get("length", 0), 2) for w in walls))

        # Violations based on intensity
        if intensity > 0.3:
            # Check for expensive custom sizes
            for wall in walls:
                length = wall.get("length", 0)
                if length > 6 and not wall.get("structural", False):
                    # Long non-structural spans may need engineered lumber
                    result.add_violation(
                        message=f"Long non-structural wall ({length:.1f}m) may require engineered lumber",
                        priority=ConstraintPriority.INFO if intensity < 0.7 else ConstraintPriority.WARNING,
                        element_id=wall.get("id"),
                        suggestion="Consider breaking into shorter spans or use LVL"
                    )

            # Check window-to-wall ratio (affects cost)
            if result.metrics["window_to_floor_ratio"] > 0.4:
                result.add_violation(
                    message=f"High window ratio ({result.metrics['window_to_floor_ratio']:.0%}) increases cost significantly",
                    priority=ConstraintPriority.INFO,
                    suggestion="Consider reducing window area for cost savings"
                )

            # Check complex geometry
            if result.metrics["corner_count"] > 20:
                result.add_violation(
                    message=f"Complex geometry ({result.metrics['corner_count']} corners) increases labor costs",
                    priority=ConstraintPriority.WARNING,
                    suggestion="Simplify building shape to reduce construction time"
                )

        result.score = constructability
        return result

    def get_visual_overlays(self, geometry: Dict[str, Any],
                           intensity: float = 0.5) -> List[Dict]:
        """Get cost visual overlays."""
        overlays = []

        # Cost heatmap by room
        rooms = geometry.get("rooms", [])
        for room in rooms:
            room_cost = self._estimate_room_cost(room, geometry)
            cost_per_m2 = room_cost / room.get("area", 1)

            overlays.append({
                "type": "cost_zone",
                "room_id": room.get("id"),
                "cost_usd": room_cost,
                "cost_per_m2": cost_per_m2,
                "intensity": min(1.0, cost_per_m2 / 3000),  # Normalize
                "color": self._cost_to_color(cost_per_m2),
                "studio": "cost"
            })

        # Material takeoff indicators
        walls = geometry.get("walls", [])
        for wall in walls:
            if wall.get("length", 0) > 6:
                overlays.append({
                    "type": "material_note",
                    "wall_id": wall.get("id"),
                    "note": "LVL or engineered lumber required",
                    "color": "orange",
                    "studio": "cost"
                })

        return overlays

    def _estimate_cost(self, geometry: Dict) -> float:
        """Estimate total construction cost."""
        cost = 0

        walls = geometry.get("walls", [])
        floors = geometry.get("floors", [])
        openings = geometry.get("openings", [])

        # Walls
        wall_area = sum(w.get("area", 0) for w in walls)
        cost += wall_area * self.COST_RATES["wall_m2"]

        # Floors
        floor_area = sum(f.get("area", 0) for f in floors)
        cost += floor_area * self.COST_RATES["floor_m2"]

        # Windows
        window_area = sum(o.get("area", 0) for o in openings if o.get("type") == "window")
        cost += window_area * self.COST_RATES["window_m2"]

        # Doors
        door_count = sum(1 for o in openings if o.get("type") == "door")
        cost += door_count * self.COST_RATES["door_each"]

        # Add 15% for complexity/overhead
        cost *= 1.15

        return round(cost, 0)

    def _estimate_room_cost(self, room: Dict, geometry: Dict) -> float:
        """Estimate cost for a single room."""
        area = room.get("area", 0)
        
        # Base cost per m² varies by room type
        base_rates = {
            "kitchen": 2500,
            "bathroom": 3000,
            "bedroom": 1800,
            "living": 2000,
            "default": 2000
        }
        
        rate = base_rates.get(room.get("type"), base_rates["default"])
        return area * rate

    def _assess_constructability(self, geometry: Dict) -> float:
        """Assess constructability 0-1."""
        score = 1.0

        # Penalize complexity
        corners = self._count_corners(geometry.get("walls", []))
        score -= corners * 0.01

        # Penalize unusual dimensions
        unique_lengths = len(set(round(w.get("length", 0), 2) for w in geometry.get("walls", [])))
        if unique_lengths > 10:
            score -= (unique_lengths - 10) * 0.02

        return max(0.0, min(1.0, score))

    def _count_corners(self, walls: List[Dict]) -> int:
        """Count wall corners."""
        # Simplified - would analyze actual geometry
        return len(walls)  # Rough approximation

    def _cost_to_color(self, cost_per_m2: float) -> str:
        """Convert cost to color."""
        if cost_per_m2 < 1500:
            return "green"
        elif cost_per_m2 < 2500:
            return "yellow"
        return "red"
