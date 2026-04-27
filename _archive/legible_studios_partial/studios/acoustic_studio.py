"""
Acoustic Studio - Sound and isolation interpretation.

Analyzes building geometry for acoustic performance and noise control.
"""

from typing import Dict, List, Any
from ..core.constraint_lens import ConstraintLens, LensResult, ConstraintPriority


class AcousticStudio(ConstraintLens):
    """Acoustic constraint lens - sound, isolation, reverberation."""

    # Simplified acoustic properties
    MATERIAL_STC = {
        "drywall": 35,
        "concrete": 55,
        "brick": 50,
        "wood": 25,
        "glass": 30,
    }

    @property
    def name(self) -> str:
        return "Acoustic Studio"

    @property
    def description(self) -> str:
        return "Detail documentation - sound, isolation"

    def analyze(self, geometry: Dict[str, Any], 
                intensity: float = 0.5) -> LensResult:
        """Analyze geometry for acoustic performance."""
        result = LensResult(studio_name=self.name)

        rooms = geometry.get("rooms", [])
        walls = geometry.get("walls", [])
        openings = geometry.get("openings", [])

        # Reverberation analysis
        for room in rooms:
            volume = room.get("volume", room.get("area", 0) * 2.7)  # Assume 2.7m height
            rt60 = self._estimate_rt60(room, volume)
            
            room_type = room.get("type", "")
            target_rt60 = self._target_rt60(room_type)
            
            result.metrics[f"{room.get('id')}_rt60"] = round(rt60, 1)
            result.metrics[f"{room.get('id')}_target"] = target_rt60

            if abs(rt60 - target_rt60) > 0.5 and intensity > 0.3:
                if rt60 > target_rt60:
                    result.add_violation(
                        message=f"{room.get('name', 'Room')} reverberation too high ({rt60:.1f}s vs {target_rt60}s target)",
                        priority=ConstraintPriority.WARNING,
                        location=room.get("center"),
                        element_id=room.get("id"),
                        suggestion="Add absorptive materials (acoustic panels, carpet, drapes)"
                    )
                else:
                    result.add_violation(
                        message=f"{room.get('name', 'Room')} too dead ({rt60:.1f}s vs {target_rt60}s target)",
                        priority=ConstraintPriority.INFO,
                        location=room.get("center"),
                        element_id=room.get("id"),
                        suggestion="Add reflective surfaces if speech intelligibility is poor"
                    )

        # Sound isolation between rooms
        adjacent_pairs = self._find_adjacent_rooms(rooms, walls)
        for pair in adjacent_pairs:
            isolation = self._calculate_isolation(pair["wall"])
            required = self._required_isolation(pair["room1"], pair["room2"])
            
            if isolation < required and intensity > 0.4:
                result.add_violation(
                    message=f"Insufficient isolation ({isolation} STC) between {pair['room1'].get('name')} and {pair['room2'].get('name')}",
                    priority=ConstraintPriority.WARNING if isolation < required - 10 else ConstraintPriority.INFO,
                    suggestion=f"Increase to {required} STC with staggered studs or insulation"
                )

        # Noise sources
        noise_sources = self._identify_noise_sources(geometry)
        for source in noise_sources:
            affected_rooms = self._find_affected_rooms(source, rooms)
            for room in affected_rooms:
                if room.get("type") in ["bedroom", "study"]:
                    result.add_violation(
                        message=f"Noise source near {room.get('name')}",
                        priority=ConstraintPriority.WARNING,
                        location=room.get("center"),
                        suggestion="Add buffer space or increase isolation"
                    )

        result.score = self._calculate_acoustic_score(result)
        return result

    def get_visual_overlays(self, geometry: Dict[str, Any],
                           intensity: float = 0.5) -> List[Dict]:
        """Get acoustic visual overlays."""
        overlays = []

        rooms = geometry.get("rooms", [])

        # RT60 zones
        for room in rooms:
            volume = room.get("volume", room.get("area", 0) * 2.7)
            rt60 = self._estimate_rt60(room, volume)
            target = self._target_rt60(room.get("type", ""))
            deviation = abs(rt60 - target)

            overlays.append({
                "type": "acoustic_zone",
                "room_id": room.get("id"),
                "rt60": rt60,
                "target": target,
                "deviation": deviation,
                "color": "green" if deviation < 0.3 else "yellow" if deviation < 0.6 else "red",
                "studio": "acoustic"
            })

        # Sound isolation indicators
        walls = geometry.get("walls", [])
        for wall in walls:
            if wall.get("between_rooms"):
                stc = self._calculate_stc(wall)
                overlays.append({
                    "type": "isolation_indicator",
                    "wall_id": wall.get("id"),
                    "stc": stc,
                    "color": "green" if stc >= 50 else "yellow" if stc >= 45 else "red",
                    "studio": "acoustic"
                })

        return overlays

    def _estimate_rt60(self, room: Dict, volume: float) -> float:
        """Estimate reverberation time using Sabine equation."""
        # Simplified Sabine: RT60 = 0.161 * V / A
        surface_area = room.get("surface_area", room.get("area", 0) * 5)  # Rough approximation
        avg_absorption = 0.15  # Typical room
        
        total_absorption = surface_area * avg_absorption
        if total_absorption <= 0:
            return 0
        
        return 0.161 * volume / total_absorption

    def _target_rt60(self, room_type: str) -> float:
        """Get target RT60 for room type."""
        targets = {
            "living": 0.5,
            "bedroom": 0.4,
            "kitchen": 0.6,
            "bathroom": 0.8,
            "theater": 0.3,
            "office": 0.6,
        }
        return targets.get(room_type.lower(), 0.5)

    def _calculate_isolation(self, wall: Dict) -> int:
        """Calculate STC rating for a wall."""
        material = wall.get("material", "drywall")
        base_stc = self.MATERIAL_STC.get(material, 35)
        
        # Add for insulation
        if wall.get("insulated", False):
            base_stc += 5
        
        # Add for double layer
        if wall.get("double_layer", False):
            base_stc += 3
        
        return base_stc

    def _find_adjacent_rooms(self, rooms: List[Dict], walls: List[Dict]) -> List[Dict]:
        """Find adjacent room pairs."""
        pairs = []
        for wall in walls:
            room1_id = wall.get("room1_id")
            room2_id = wall.get("room2_id")
            
            if room1_id and room2_id:
                room1 = next((r for r in rooms if r.get("id") == room1_id), None)
                room2 = next((r for r in rooms if r.get("id") == room2_id), None)
                
                if room1 and room2:
                    pairs.append({
                        "room1": room1,
                        "room2": room2,
                        "wall": wall
                    })
        return pairs

    def _required_isolation(self, room1: Dict, room2: Dict) -> int:
        """Get required STC between room types."""
        types = {room1.get("type", "").lower(), room2.get("type", "").lower()}
        
        if "bedroom" in types and ("kitchen" in types or "living" in types):
            return 55
        elif "bathroom" in types:
            return 50
        elif "bedroom" in types:
            return 50
        return 45

    def _identify_noise_sources(self, geometry: Dict) -> List[Dict]:
        """Identify potential noise sources."""
        sources = []
        
        # Mechanical equipment
        for room in geometry.get("rooms", []):
            if room.get("type") in ["mechanical", "utility"]:
                sources.append({
                    "type": "mechanical",
                    "location": room.get("center"),
                    "level": 70  # dB
                })
        
        return sources

    def _find_affected_rooms(self, source: Dict, rooms: List[Dict]) -> List[Dict]:
        """Find rooms affected by a noise source."""
        # Simplified - would calculate actual sound transmission
        return [r for r in rooms if r.get("type") in ["bedroom", "study"]]

    def _calculate_stc(self, wall: Dict) -> int:
        """Calculate STC for a wall."""
        return self._calculate_isolation(wall)

    def _calculate_acoustic_score(self, result: LensResult) -> float:
        """Calculate overall acoustic score."""
        base_score = 1.0
        base_score -= result.get_critical_count() * 0.3
        base_score -= result.get_warning_count() * 0.1
        return max(0.0, min(1.0, base_score))
