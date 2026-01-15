"""Perception Layer - Psychology of human experience.

Models how humans perceive and experience space:
- Wayfinding: Navigation, legibility, landmarks, cognitive mapping
- Comfort: Thermal, visual, acoustic, ergonomic comfort
- Delight: Affect, beauty, surprise, meaning, attachment
- Social: Privacy gradients, territoriality, co-presence patterns
- Biological: Circadian rhythms, biophilia, sensory processing

This reveals how architecture HUMANS, not just houses.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math


class PrivacyLevel(Enum):
    """Privacy levels for spaces."""
    PUBLIC = "public"  # Street, front yard, anyone welcome
    SOCIAL = "social"  # Living room, guests expected
    SEMI_PRIVATE = "semi_private"  # Kitchen, family room, close friends
    PRIVATE = "private"  # Bedrooms, bathrooms, family only
    INTIMATE = "intimate"  # Primary bathroom, dressing, self


class AffectQuality(Enum):
    """Emotional qualities of space."""
    SHELTER = "shelter"  # Safety, protection, enclosure
    EXPANSION = "expansion"  # Freedom, prospect, horizon
    INTIMACY = "intimacy"  # Warmth, connection, nesting
    AWE = "awe"  # Vastness, transcendence, sublime
    DELIGHT = "delight"  # Joy, surprise, playfulness
    CALM = "calm"  # Peace, rest, restoration
    FOCUS = "focus"  # Concentration, flow, productivity


# =============================================================================
# Wayfinding Analysis
# =============================================================================

@dataclass
class WayfindingNode:
    """A node in the wayfinding graph."""
    room_id: str
    room_type: str
    is_destination: bool  # Is this a primary target (bathroom, bedroom)?
    is_landmark: bool  # Is this memorable/recognizable?
    visibility_score: float  # 0-1, how visible from circulation


@dataclass
class WayfindingPath:
    """A path between nodes."""
    from_room: str
    to_room: str
    steps: int  # Number of rooms/stairs
    decision_points: int  # Number of direction choices
    has_landmark: bool  # Is there a landmark along the way?
    legibility_score: float  # 0-1, how easy to understand


@dataclass
class WayfindingResult:
    """Result of wayfinding analysis."""
    nodes: List[WayfindingNode]
    paths: List[WayfindingPath]
    overall_legibility: float  # 0-1
    critical_paths: Dict[str, WayfindingPath]  # Important routes (entry→bedroom, etc.)
    issues: List[str]  # Navigation problems
    recommendations: List[str]


class WayfindingAnalysis:
    """Analyzes wayfinding and navigation."""

    # Room privacy levels
    ROOM_PRIVACY = {
        "entry": PrivacyLevel.PUBLIC,
        "foyer": PrivacyLevel.PUBLIC,
        "living": PrivacyLevel.SOCIAL,
        "great_room": PrivacyLevel.SOCIAL,
        "dining": PrivacyLevel.SOCIAL,
        "kitchen": PrivacyLevel.SEMI_PRIVATE,
        "family_room": PrivacyLevel.SEMI_PRIVATE,
        "office": PrivacyLevel.PRIVATE,
        "bedroom": PrivacyLevel.PRIVATE,
        "primary_bedroom": PrivacyLevel.PRIVATE,
        "bathroom": PrivacyLevel.PRIVATE,
        "ensuite": PrivacyLevel.INTIMATE,
        "powder_room": PrivacyLevel.SEMI_PRIVATE,
        "laundry": PrivacyLevel.SEMI_PRIVATE,
        "garage": PrivacyLevel.SEMI_PRIVATE,
    }

    # Room destination importance (how often people need to find it)
    DESTINATION_IMPORTANCE = {
        "bathroom": 0.9,
        "powder_room": 0.8,
        "kitchen": 0.8,
        "living": 0.6,
        "bedroom": 0.7,
        "primary_bedroom": 0.7,
        "entry": 0.5,  # You're already there
        "office": 0.5,
    }

    # Landmark potential (memorability)
    LANDMARK_POTENTIAL = {
        "entry": 0.9,
        "living": 0.7,
        "great_room": 0.8,
        "kitchen": 0.6,
        "primary_bedroom": 0.5,
        "bathroom": 0.2,
    }

    def analyze_wayfinding(
        self,
        rooms: List[Dict[str, Any]],
        adjacencies: List[Dict[str, Any]],
        layout: Dict[str, Any]
    ) -> WayfindingResult:
        """Analyze wayfinding and navigation.

        Considers:
        - Path length (steps from entry to destinations)
        - Decision points (confusing junctions)
        - Landmarks (memorable spaces for orientation)
        - Visibility (can I see where I'm going?)
        """
        # Build nodes
        nodes = []
        for room in rooms:
            room_type = room.get("type")
            nodes.append(WayfindingNode(
                room_id=room.get("id"),
                room_type=room_type,
                is_destination=self.DESTINATION_IMPORTANCE.get(room_type, 0) > 0.5,
                is_landmark=self.LANDMARK_POTENTIAL.get(room_type, 0) > 0.5,
                visibility_score=self._calculate_visibility(room, layout),
            ))

        # Build adjacency graph
        graph = self._build_graph(rooms, adjacencies)

        # Find all paths
        paths = []
        for from_node in nodes:
            for to_node in nodes:
                if from_node.room_id != to_node.room_id:
                    path = self._find_path(from_node, to_node, graph, nodes)
                    if path:
                        paths.append(path)

        # Identify critical paths (entry→bedroom, entry→bathroom)
        critical = self._identify_critical_paths(paths, nodes)

        # Calculate overall legibility
        legibility = self._calculate_legibility(paths, nodes)

        # Identify issues
        issues = self._identify_wayfinding_issues(paths, nodes, critical)

        # Recommendations
        recommendations = self._generate_wayfinding_recommendations(issues)

        return WayfindingResult(
            nodes=nodes,
            paths=paths,
            overall_legibility=legibility,
            critical_paths=critical,
            issues=issues,
            recommendations=recommendations
        )

    def _build_graph(
        self,
        rooms: List[Dict[str, Any]],
        adjacencies: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Build adjacency graph."""
        room_ids = [r.get("id") for r in rooms]
        graph = {rid: [] for rid in room_ids}

        for adj in adjacencies:
            room_a = adj.get("room_a")
            room_b = adj.get("room_b")
            if room_a in graph and room_b in graph:
                graph[room_a].append(room_b)
                graph[room_b].append(room_a)

        return graph

    def _find_path(
        self,
        from_node: WayfindingNode,
        to_node: WayfindingNode,
        graph: Dict[str, List[str]],
        all_nodes: List[WayfindingNode]
    ) -> Optional[WayfindingPath]:
        """Find shortest path between nodes (BFS)."""
        from collections import deque

        queue = deque([(from_node.room_id, [])])
        visited = {from_node.room_id}

        while queue:
            current, path = queue.popleft()

            if current == to_node.room_id:
                # Calculate decision points
                decision_points = sum(1 for i, room_id in enumerate(path)
                                     if len(graph.get(room_id, [])) > 2)

                # Check for landmarks
                has_landmark = any(
                    any(n.room_id == room_id and n.is_landmark for n in all_nodes)
                    for room_id in path
                )

                return WayfindingPath(
                    from_room=from_node.room_id,
                    to_room=to_node.room_id,
                    steps=len(path),
                    decision_points=decision_points,
                    has_landmark=has_landmark,
                    legibility_score=0.0  # Calculated later
                )

            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def _calculate_visibility(self, room: Dict[str, Any], layout: Dict[str, Any]) -> float:
        """Calculate visibility from circulation (simplified)."""
        # In a real implementation, this would analyze geometry
        # For now, use heuristics
        room_type = room.get("type")

        # Open plans are more visible
        if room_type in ("living", "great_room", "kitchen", "dining"):
            return 0.8
        elif room_type in ("entry", "foyer"):
            return 0.9
        elif room_type in ("bedroom", "primary_bedroom"):
            return 0.3
        else:
            return 0.5

    def _identify_critical_paths(
        self,
        paths: List[WayfindingPath],
        nodes: List[WayfindingNode]
    ) -> Dict[str, WayfindingPath]:
        """Identify critical navigation paths."""
        critical = {}

        # Find entry node
        entry_nodes = [n for n in nodes if n.room_type in ("entry", "foyer")]
        if not entry_nodes:
            return critical

        entry_id = entry_nodes[0].room_id

        # Paths from entry to important destinations
        for path in paths:
            if path.from_room == entry_id:
                to_node = next((n for n in nodes if n.room_id == path.to_room), None)
                if to_node and to_node.is_destination:
                    key = f"entry_to_{to_node.room_type}"
                    critical[key] = path

        return critical

    def _calculate_legibility(
        self,
        paths: List[WayfindingPath],
        nodes: List[WayfindingNode]
    ) -> float:
        """Calculate overall legibility score."""
        if not paths:
            return 0.0

        # Average steps to destinations (lower is better)
        destination_paths = [p for p in paths
                            if any(n.room_id == p.to_room and n.is_destination for n in nodes)]
        avg_steps = sum(p.steps for p in destination_paths) / len(destination_paths) if destination_paths else 5

        # Normalize: 2 steps = 1.0, 5+ steps = 0.0
        steps_score = max(0, 1 - (avg_steps - 2) / 3)

        # Decision points (fewer is better)
        avg_decisions = sum(p.decision_points for p in paths) / len(paths) if paths else 0
        decision_score = max(0, 1 - avg_decisions / 2)

        # Landmarks (more is better)
        landmark_ratio = sum(1 for p in paths if p.has_landmark) / len(paths) if paths else 0

        # Weighted average
        return (steps_score * 0.5 + decision_score * 0.3 + landmark_ratio * 0.2)

    def _identify_wayfinding_issues(
        self,
        paths: List[WayfindingPath],
        nodes: List[WayfindingNode],
        critical: Dict[str, WayfindingPath]
    ) -> List[str]:
        """Identify wayfinding problems."""
        issues = []

        # Check critical paths
        for key, path in critical.items():
            if path.steps > 4:
                issues.append(f"{key}: Too many steps ({path.steps})")
            if path.decision_points > 2:
                issues.append(f"{key}: Confusing ({path.decision_points} decision points)")

        # Check for landmarks
        landmark_count = sum(1 for n in nodes if n.is_landmark)
        if landmark_count < 2:
            issues.append("Insufficient landmarks for orientation")

        return issues

    def _generate_wayfinding_recommendations(self, issues: List[str]) -> List[str]:
        """Generate wayfinding recommendations."""
        recommendations = []

        if any("steps" in i for i in issues):
            recommendations.append("reduce_path_lengths")
        if any("decision" in i.lower() for i in issues):
            recommendations.append("simplify_circulation")
        if any("landmark" in i.lower() for i in issues):
            recommendations.append("add_orienting_features")

        return recommendations


# =============================================================================
# Comfort Analysis
# =============================================================================

@dataclass
class ComfortResult:
    """Result of comfort analysis."""
    room_id: str
    thermal_comfort: float  # 0-1
    visual_comfort: float  # 0-1 (glare, contrast)
    acoustic_comfort: float  # 0-1
    ergonomic_comfort: float  # 0-1 (reach, clearances)
    overall_comfort: float  # 0-1
    discomfort_factors: List[str]


class ComfortAnalysis:
    """Analyzes human comfort in spaces."""

    # Target room temperatures by activity
    TEMPERATURE_TARGETS = {
        "living": 21,  # °C
        "great_room": 21,
        "dining": 21,
        "kitchen": 20,  # Cooler for cooking
        "bedroom": 18,  # Cooler for sleep
        "primary_bedroom": 18,
        "bathroom": 23,  # Warmer
        "ensuite": 23,
        "office": 22,
        "laundry": 18,
    }

    # Recommended illuminance levels (lux)
    ILLUMINANCE_TARGETS = {
        "living": 150,
        "great_room": 150,
        "dining": 200,
        "kitchen": 500,  # Food prep needs light
        "bedroom": 100,
        "primary_bedroom": 100,
        "bathroom": 300,
        "ensuite": 300,
        "office": 500,
        "laundry": 300,
    }

    def analyze_room_comfort(
        self,
        room: Dict[str, Any],
        environmental_result: Any,  # From EnvironmentLayer
        layout: Dict[str, Any]
    ) -> ComfortResult:
        """Analyze comfort factors for a room.

        Considers:
        - Thermal comfort (temperature, humidity, drafts)
        - Visual comfort (light levels, glare, contrast)
        - Acoustic comfort (noise, reverberation)
        - Ergonomic comfort (reach, clearances, anthropometrics)
        """
        room_id = room.get("id")
        room_type = room.get("type")

        # Thermal comfort
        thermal = self._assess_thermal_comfort(room, environmental_result)

        # Visual comfort
        visual = self._assess_visual_comfort(room, environmental_result)

        # Acoustic comfort
        acoustic = self._assess_acoustic_comfort(room, environmental_result)

        # Ergonomic comfort
        ergonomic = self._assess_ergonomic_comfort(room, layout)

        # Overall comfort
        overall = (thermal + visual + acoustic + ergonomic) / 4

        # Discomfort factors
        discomfort_factors = []
        if thermal < 0.5:
            discomfort_factors.append("thermal_discomfort")
        if visual < 0.5:
            discomfort_factors.append("visual_discomfort")
        if acoustic < 0.5:
            discomfort_factors.append("acoustic_discomfort")
        if ergonomic < 0.5:
            discomfort_factors.append("ergonomic_discomfort")

        return ComfortResult(
            room_id=room_id,
            thermal_comfort=round(thermal, 2),
            visual_comfort=round(visual, 2),
            acoustic_comfort=round(acoustic, 2),
            ergonomic_comfort=round(ergonomic, 2),
            overall_comfort=round(overall, 2),
            discomfort_factors=discomfort_factors
        )

    def _assess_thermal_comfort(self, room: Dict[str, Any], env_result: Any) -> float:
        """Assess thermal comfort."""
        # This would integrate with thermal analysis from EnvironmentLayer
        # For now, simplified heuristic

        room_type = room.get("type")

        # Check if room has appropriate heating/cooling
        has_hvac = room.get("mechanical", {}).get("hvac", True)
        if not has_hvac:
            return 0.3

        # Check insulation
        insulation = room.get("constraints", {}).get("insulation", "code_minimum")
        if insulation == "code_minimum":
            base_score = 0.7
        elif insulation == "improved":
            base_score = 0.85
        elif insulation == "passive_house":
            base_score = 0.95
        else:
            base_score = 0.6

        # Check for thermal mass (helps stability)
        thermal_mass = room.get("constraints", {}).get("thermal_mass", "medium")
        if thermal_mass == "heavy":
            base_score += 0.05

        return min(1.0, base_score)

    def _assess_visual_comfort(self, room: Dict[str, Any], env_result: Any) -> float:
        """Assess visual comfort."""
        room_type = room.get("type")

        # Daylight factor
        window_area = room.get("window_area", 0)
        floor_area = room.get("area_min", 10)
        window_ratio = window_area / floor_area if floor_area > 0 else 0

        # Target window ratio: 15-25%
        if 0.15 <= window_ratio <= 0.25:
            daylight_score = 1.0
        elif 0.10 <= window_ratio < 0.15 or 0.25 < window_ratio <= 0.35:
            daylight_score = 0.8
        elif window_ratio < 0.10:
            daylight_score = 0.4
        else:  # Too much window (glare, heat loss)
            daylight_score = 0.6

        # Glare potential
        # Would integrate with solar analysis
        glare_score = 0.8  # Placeholder

        # Artificial light
        has_lighting = room.get("electrical", {}).get("lighting", True)
        if not has_lighting:
            daylight_score *= 0.7

        return (daylight_score + glare_score) / 2

    def _assess_acoustic_comfort(self, room: Dict[str, Any], env_result: Any) -> float:
        """Assess acoustic comfort."""
        # Would integrate with acoustic analysis from EnvironmentLayer
        # For now, simplified

        room_type = room.get("type")

        # NRC target
        target_nrc = {
            "living": 0.4,
            "great_room": 0.4,
            "dining": 0.3,
            "kitchen": 0.3,
            "bedroom": 0.5,
            "primary_bedroom": 0.5,
            "office": 0.5,
            "bathroom": 0.3,
        }.get(room_type, 0.4)

        # Check finishes
        finishes = room.get("finishes", {})
        floor = finishes.get("floor", "hard")
        ceiling = finishes.get("ceiling", "hard")

        # Carpet helps
        if floor == "carpet":
            nrc_score = 0.8
        elif floor == "soft":
            nrc_score = 0.6
        else:
            nrc_score = 0.4

        # Acoustic ceiling helps
        if ceiling == "acoustic":
            nrc_score += 0.2

        return min(1.0, nrc_score)

    def _assess_ergonomic_comfort(self, room: Dict[str, Any], layout: Dict[str, Any]) -> float:
        """Assess ergonomic comfort."""
        room_type = room.get("type")

        # Check clearances based on furniture
        furniture = room.get("furniture", [])
        if not furniture:
            return 0.7  # Default

        # Check for appropriate clearances
        # This is simplified - full implementation would check reach zones
        clearance_score = 0.7

        # Check ceiling height
        ceiling_height = room.get("ceiling_height", 2.7)
        if ceiling_height < 2.4:
            clearance_score *= 0.7
        elif ceiling_height > 3.0:
            clearance_score *= 1.1

        return min(1.0, clearance_score)


# =============================================================================
# Delight Analysis
# =============================================================================

@dataclass
class DelightResult:
    """Result of delight analysis."""
    room_id: str
    affect_qualities: List[AffectQuality]  # Emotional qualities present
    delight_score: float  # 0-1
    biophilia_score: float  # 0-1 (connection to nature)
    prospect_refuge_score: float  # 0-1 (Appleton's theory)
    surprise_moments: List[str]  # Notable spatial experiences
    attachment_potential: float  # 0-1 (will people love this place?)


class DelightAnalysis:
    """Analyzes emotional and experiential qualities."""

    # Room type affect potentials
    ROOM_AFFECT = {
        "entry": [AffectQuality.SHELTER],
        "living": [AffectQuality.EXPANSION, AffectQuality.CALM],
        "great_room": [AffectQuality.AWE, AffectQuality.EXPANSION],
        "kitchen": [AffectQuality.INTIMACY, AffectQuality.DELIGHT],
        "bedroom": [AffectQuality.SHELTER, AffectQuality.CALM],
        "primary_bedroom": [AffectQuality.SHELTER, AffectQuality.INTIMACY],
        "bathroom": [AffectQuality.SHELTER, AffectQuality.CALM],
        "dining": [AffectQuality.INTIMACY, AffectQuality.DELIGHT],
        "office": [AffectQuality.FOCUS, AffectQuality.CALM],
    }

    def analyze_delight(
        self,
        room: Dict[str, Any],
        environmental_result: Any,
        layout: Dict[str, Any]
    ) -> DelightResult:
        """Analyze delight and emotional qualities.

        Considers:
        - Affect: What emotions does this space evoke?
        - Biophilia: Connection to nature (light, views, plants)
        - Prospect/Refuge: Appleton's habitat theory
        - Surprise: Notable spatial experiences
        - Attachment: Will people form emotional bonds?
        """
        room_id = room.get("id")
        room_type = room.get("type")

        # Affect qualities
        affect = self.ROOM_AFFECT.get(room_type, [])

        # Biophilia
        biophilia = self._assess_biophilia(room, environmental_result)

        # Prospect/refuge
        prospect_refuge = self._assess_prospect_refuge(room, layout)

        # Surprise moments
        surprises = self._identify_surprise_moments(room, layout)

        # Delight score
        delight = (biophilia + prospect_refuge) / 2
        if surprises:
            delight = min(1.0, delight + 0.1)

        # Attachment potential
        attachment = self._assess_attachment_potential(room, delight)

        return DelightResult(
            room_id=room_id,
            affect_qualities=affect,
            delight_score=round(delight, 2),
            biophilia_score=round(biophilia, 2),
            prospect_refuge_score=round(prospect_refuge, 2),
            surprise_moments=surprises,
            attachment_potential=round(attachment, 2)
        )

    def _assess_biophilia(self, room: Dict[str, Any], env_result: Any) -> float:
        """Assess biophilic qualities."""
        score = 0.0

        # Natural light
        daylight = env_result.solar.get(room.get("id"), None) if env_result else None
        if daylight and daylight.daylight_factor > 0.05:
            score += 0.3

        # Views (would check for windows overlooking nature)
        has_views = room.get("views", [])
        if has_views:
            score += 0.3

        # Natural materials
        finishes = room.get("finishes", {})
        if finishes.get("floor") in ("hardwood",):
            score += 0.1
        if finishes.get("walls") in ("wood", "stone"):
            score += 0.1

        # Plants / greenery
        features = room.get("features", {})
        if isinstance(features, dict):
            if features.get("plants"):
                score += 0.2
        elif isinstance(features, list):
            if "plants" in features:
                score += 0.2

        return min(1.0, score)

    def _assess_prospect_refuge(self, room: Dict[str, Any], layout: Dict[str, Any]) -> float:
        """Assess prospect/refuge balance.

        Prospect: Ability to see surroundings (safety, opportunity)
        Refuge: Protected, enclosed space (safety, rest)

        Great rooms have high prospect. Bedrooms have high refuge.
        Ideal spaces have both or a clear sequence.
        """
        room_type = room.get("type")

        # Prospect
        prospect_scores = {
            "living": 0.7,
            "great_room": 0.9,
            "kitchen": 0.6,
            "dining": 0.5,
            "entry": 0.5,
            "office": 0.4,
        }

        # Refuge
        refuge_scores = {
            "bedroom": 0.9,
            "primary_bedroom": 0.95,
            "bathroom": 0.8,
            "ensuite": 0.85,
            "living": 0.3,
            "great_room": 0.2,
        }

        prospect = prospect_scores.get(room_type, 0.3)
        refuge = refuge_scores.get(room_type, 0.3)

        # Balance is ideal - either strong in one or moderate in both
        balance = abs(prospect - refuge)
        if balance > 0.6:
            # Clear character (good)
            return max(prospect, refuge)
        elif balance < 0.2:
            # Balanced (good)
            return (prospect + refuge) / 2
        else:
            # Unclear (meh)
            return 0.5

    def _identify_surprise_moments(self, room: Dict[str, Any], layout: Dict[str, Any]) -> List[str]:
        """Identify surprise/delight moments."""
        surprises = []

        # Volume changes
        ceiling_height = room.get("ceiling_height", 2.7)
        if ceiling_height > 3.5:
            surprises.append("double_height_space")
        elif ceiling_height < 2.4:
            surprises.append("intimate_nook")

        # Views
        views = room.get("views", [])
        for view in views:
            if isinstance(view, dict) and view.get("type") == "dramatic":
                surprises.append("dramatic_view")

        # Features
        features = room.get("features", {})
        if isinstance(features, dict):
            if features.get("fireplace"):
                surprises.append("fireplace")
            if features.get("built_in_seating"):
                surprises.append("built_in_nook")

        return surprises

    def _assess_attachment_potential(self, room: Dict[str, Any], delight: float) -> float:
        """Assess potential for emotional attachment."""
        score = delight

        # Personalization potential
        if room.get("type") in ("bedroom", "primary_bedroom", "office"):
            score += 0.1

        # Storage/clutter (people accumulate stuff)
        storage = room.get("storage", 0)
        if storage and storage > 0:
            score += 0.05

        return min(1.0, score)


# =============================================================================
# Perception Layer (Orchestrator)
# =============================================================================

@dataclass
class PerceptionResult:
    """Combined perception analysis result."""
    wayfinding: WayfindingResult
    comfort: Dict[str, ComfortResult]  # room_id → ComfortResult
    delight: Dict[str, DelightResult]  # room_id → DelightResult
    overall_experience_score: float  # 0-1
    critical_issues: List[str]  # Human experience failures
    enhancement_opportunities: List[str]  # Ways to improve experience


class PerceptionLayer:
    """Psychology-based analysis of human experience.

    This layer doesn't "optimize" - it reveals constraints.
    Human psychology is what it is.
    """

    def __init__(self):
        """Initialize perception layer."""
        self.wayfinding = WayfindingAnalysis()
        self.comfort = ComfortAnalysis()
        self.delight = DelightAnalysis()

    def analyze(
        self,
        rooms: List[Dict[str, Any]],
        adjacencies: List[Dict[str, Any]],
        separations: List[Dict[str, Any]],
        layout: Dict[str, Any],
        environmental_result: Any = None
    ) -> PerceptionResult:
        """Run all perception analyses.

        Returns constraints and requirements imposed by human psychology.
        """
        # Wayfinding
        wayfinding = self.wayfinding.analyze_wayfinding(rooms, adjacencies, layout)

        # Comfort (per room)
        comfort_results = {}
        for room in rooms:
            comfort_results[room.get("id")] = self.comfort.analyze_room_comfort(
                room, environmental_result, layout
            )

        # Delight (per room)
        delight_results = {}
        for room in rooms:
            delight_results[room.get("id")] = self.delight.analyze_delight(
                room, environmental_result, layout
            )

        # Overall experience score
        overall = self._calculate_overall_experience(
            wayfinding, comfort_results, delight_results
        )

        # Critical issues
        issues = self._identify_perception_issues(
            wayfinding, comfort_results, delight_results
        )

        # Enhancement opportunities
        opportunities = self._identify_enhancement_opportunities(
            wayfinding, comfort_results, delight_results
        )

        return PerceptionResult(
            wayfinding=wayfinding,
            comfort=comfort_results,
            delight=delight_results,
            overall_experience_score=overall,
            critical_issues=issues,
            enhancement_opportunities=opportunities
        )

    def _calculate_overall_experience(
        self,
        wayfinding: WayfindingResult,
        comfort: Dict[str, ComfortResult],
        delight: Dict[str, DelightResult]
    ) -> float:
        """Calculate overall human experience score."""
        # Wayfinding legibility
        wayfinding_score = wayfinding.overall_legibility

        # Average comfort
        comfort_scores = [c.overall_comfort for c in comfort.values()]
        avg_comfort = sum(comfort_scores) / len(comfort_scores) if comfort_scores else 0.5

        # Average delight
        delight_scores = [d.delight_score for d in delight.values()]
        avg_delight = sum(delight_scores) / len(delight_scores) if delight_scores else 0.5

        # Weighted average (comfort is most important)
        return (wayfinding_score * 0.3 + avg_comfort * 0.5 + avg_delight * 0.2)

    def _identify_perception_issues(
        self,
        wayfinding: WayfindingResult,
        comfort: Dict[str, ComfortResult],
        delight: Dict[str, DelightResult]
    ) -> List[str]:
        """Identify critical human experience issues."""
        issues = []

        # Wayfinding issues
        if wayfinding.overall_legibility < 0.4:
            issues.append("poor_wayfinding_legibility")

        # Comfort issues
        for room_id, comfort_result in comfort.items():
            if comfort_result.overall_comfort < 0.4:
                issues.append(f"low_comfort_{room_id}")

        # Delight issues ( Bedrooms should have refuge)
        for room_id, delight_result in delight.items():
            if "bedroom" in room_id and delight_result.prospect_refuge_score < 0.6:
                issues.append(f"insufficient_refuge_{room_id}")

        return issues

    def _identify_enhancement_opportunities(
        self,
        wayfinding: WayfindingResult,
        comfort: Dict[str, ComfortResult],
        delight: Dict[str, DelightResult]
    ) -> List[str]:
        """Identify opportunities to enhance human experience."""
        opportunities = []

        # Wayfinding recommendations
        opportunities.extend(wayfinding.recommendations)

        # Comfort enhancements
        low_comfort = [rid for rid, c in comfort.items() if c.overall_comfort < 0.6]
        if low_comfort:
            opportunities.append("improve_comfort_in_low_scoring_rooms")

        # Delight enhancements
        low_biophilia = [rid for rid, d in delight.items() if d.biophilia_score < 0.4]
        if len(low_biophilia) > len(delight) / 2:
            opportunities.append("increase_biophilic_elements")

        return opportunities
