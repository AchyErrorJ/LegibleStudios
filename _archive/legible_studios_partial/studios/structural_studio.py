"""
Structural Studio - Structural constraint interpretation.

Analyzes building geometry for loads, spans, and structural feasibility.
"""

from typing import Dict, List, Any, Optional
from ..core.constraint_lens import ConstraintLens, LensResult, ConstraintPriority


class StructuralStudio(ConstraintLens):
    """Structural constraint lens - loads, spans, materials."""

    @property
    def name(self) -> str:
        return "Structural Studio"

    @property
    def description(self) -> str:
        return "Forces and members - loads, spans, materials"

    def analyze(self, geometry: Dict[str, Any], 
                intensity: float = 0.5) -> LensResult:
        """Analyze geometry for structural constraints."""
        result = LensResult(studio_name=self.name)

        rooms = geometry.get("rooms", [])
        walls = geometry.get("walls", [])
        floors = geometry.get("floors", [])

        # Span analysis
        max_span = self._calculate_max_span(walls)
        result.metrics["max_span_m"] = max_span
        result.metrics["span_category"] = self._categorize_span(max_span)

        # Load path analysis
        load_paths = self._trace_load_paths(walls, floors)
        result.metrics["load_paths"] = len(load_paths)

        # Structural depth estimation
        estimated_depth = self._estimate_structural_depth(max_span)
        result.metrics["estimated_beam_depth_mm"] = estimated_depth

        # Check for issues based on intensity
        if intensity > 0.3:
            # Check for long spans without support
            for room in rooms:
                width = room.get("width", 0)
                length = room.get("length", 0)
                max_dim = max(width, length)

                if max_dim > 8:  # 8 meters
                    has_support = self._check_interior_support(room, walls)
                    if not has_support:
                        result.add_violation(
                            message=f"{room.get('name', 'Room')} has {max_dim:.1f}m span without intermediate support",
                            priority=ConstraintPriority.CRITICAL if max_dim > 12 else ConstraintPriority.WARNING,
                            location=room.get("center"),
                            element_id=room.get("id"),
                            suggestion="Add column or structural wall" if max_dim > 12 else "Consider beam depth or add support"
                        )

            # Check cantilevers
            cantilevers = self._identify_cantilevers(geometry)
            for cant in cantilevers:
                if cant["length"] > 2.0:  # 2m cantilever
                    result.add_violation(
                        message=f"Cantilever of {cant['length']:.1f}m exceeds typical limits",
                        priority=ConstraintPriority.WARNING,
                        location=cant["location"],
                        suggestion="Reduce cantilever or increase structural depth"
                    )

        result.score = self._calculate_score(result)
        return result

    def get_visual_overlays(self, geometry: Dict[str, Any],
                           intensity: float = 0.5) -> List[Dict]:
        """Get structural visual overlays."""
        overlays = []

        walls = geometry.get("walls", [])
        
        # Load paths
        load_paths = self._trace_load_paths(walls, geometry.get("floors", []))
        for path in load_paths:
            overlays.append({
                "type": "load_path",
                "path": path["points"],
                "load": path["load_kn"],
                "color": "blue",
                "studio": "structural"
            })

        # Span indicators
        rooms = geometry.get("rooms", [])
        for room in rooms:
            width = room.get("width", 0)
            length = room.get("length", 0)
            max_span = max(width, length)
            
            if max_span > 6:
                overlays.append({
                    "type": "span_indicator",
                    "room_id": room.get("id"),
                    "span_m": max_span,
                    "suggested_depth_mm": self._estimate_structural_depth(max_span),
                    "color": "red" if max_span > 10 else "orange",
                    "studio": "structural"
                })

        return overlays

    def _calculate_max_span(self, walls: List[Dict]) -> float:
        """Calculate maximum span in the building."""
        max_span = 0
        for wall in walls:
            length = wall.get("length", 0)
            if length > max_span:
                max_span = length
        return max_span

    def _categorize_span(self, span: float) -> str:
        """Categorize span length."""
        if span < 4:
            return "short"
        elif span < 8:
            return "medium"
        elif span < 12:
            return "long"
        return "very_long"

    def _trace_load_paths(self, walls: List[Dict], floors: List[Dict]) -> List[Dict]:
        """Trace load paths from floors to foundations."""
        paths = []
        
        for floor in floors:
            area = floor.get("area", 0)
            load = area * 2.0  # kN, simplified live+dead load
            
            # Find supporting walls
            supporting_walls = [w for w in walls if w.get("supports_floor")]
            
            if supporting_walls:
                for wall in supporting_walls[:2]:  # Top 2 supports
                    paths.append({
                        "floor_id": floor.get("id"),
                        "wall_id": wall.get("id"),
                        "load_kn": load / len(supporting_walls),
                        "points": [floor.get("center"), wall.get("center")]
                    })

        return paths

    def _estimate_structural_depth(self, span: float) -> int:
        """Estimate required beam depth in mm."""
        # Rule of thumb: span/20 for steel, span/15 for wood
        return int(span * 1000 / 18)  # Conservative estimate

    def _check_interior_support(self, room: Dict, walls: List[Dict]) -> bool:
        """Check if room has interior structural support."""
        room_id = room.get("id")
        # Check for walls inside room bounds
        for wall in walls:
            if wall.get("room_id") == room_id and wall.get("structural", False):
                if wall.get("interior", False):
                    return True
        return False

    def _identify_cantilevers(self, geometry: Dict) -> List[Dict]:
        """Identify cantilevered elements."""
        cantilevers = []
        # Simplified - would analyze actual geometry
        return cantilevers

    def _calculate_score(self, result: LensResult) -> float:
        """Calculate overall structural score."""
        base_score = 1.0
        base_score -= result.get_critical_count() * 0.4
        base_score -= result.get_warning_count() * 0.15
        return max(0.0, min(1.0, base_score))
