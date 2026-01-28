"""Materiality Layer - Economics of construction reality.

Models the economic constraints of building:
- Cost: Materials, labor, equipment, permits
- Construction: System compatibility, sequencing, complexity
- Supply: Material availability, lead times, regional factors
- Lifecycle: Maintenance, energy, replacement costs

This reveals what's AFFORDABLE and BUILDABLE, not what's "best".
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math


class ConstructionSystem(Enum):
    """Primary structural systems."""
    WOOD_LIGHT_FRAME = "wood_light_frame"  # 2x4/2x6, typical residential
    WOOD_ADVANCED = "wood_advanced"  # CLT, glulam, heavy timber
    STEEL_LIGHT_GAUGE = "steel_light_gauge"  # Light gauge steel framing
    STEEL_STRUCTURAL = "steel_structural"  # Red iron, wide-flange
    CONCRETE_CMU = "concrete_cmu"  # Concrete masonry units
    CONCRETE_CAST = "concrete_cast"  # Poured-in-place concrete
    INSULATED_FORMS = "insulated_forms"  # ICFs
    STRUCTURAL_INSULATED = "structural_insulated"  # SIPs


class QualityLevel(Enum):
    """Construction quality tiers."""
    BASIC = "basic"  # Code minimum, builder-grade
    STANDARD = "standard"  # Typical custom home quality
    PREMIUM = "premium"  # Architectural grade, premium materials
    CUSTOM = "custom"  # High-end, custom details


# =============================================================================
# Material Library
# =============================================================================

@dataclass
class MaterialSpec:
    """Specification for a building material."""
    name: str
    category: str  # "structural", "enclosure", "finish", "mechanical"
    unit: str  # "sqft", "linear_ft", "each", "cubic_yard"
    base_cost: float  # $ per unit (2024 USD, national average)
    regional_multipliers: Dict[str, float]  # Cost adjustment by region
    labor_intensity: float  # Labor hours per unit
    skill_level: str  # "unskilled", "semi_skilled", "skilled", "specialized"
    lead_time: int  # Weeks to procure
    carbon_intensity: float  # kg CO2e per unit
    lifespan: int  # Years before replacement needed


class MaterialLibrary:
    """Database of building materials and costs."""

    # 2024 USD costs (national average, will be regionally adjusted)
    MATERIALS: Dict[str, MaterialSpec] = {
        # Structural
        "lumber_2x4": MaterialSpec(
            name="2x4 Lumber",
            category="structural",
            unit="linear_ft",
            base_cost=2.50,
            regional_multipliers={"northeast": 1.15, "west": 1.25, "midwest": 1.0, "south": 0.95},
            labor_intensity=0.05,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=0.8,
            lifespan=100
        ),
        "lumber_2x6": MaterialSpec(
            name="2x6 Lumber",
            category="structural",
            unit="linear_ft",
            base_cost=3.20,
            regional_multipliers={"northeast": 1.15, "west": 1.25, "midwest": 1.0, "south": 0.95},
            labor_intensity=0.05,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=1.0,
            lifespan=100
        ),
        "lumber_clt": MaterialSpec(
            name="Cross-Laminated Timber Panel",
            category="structural",
            unit="sqft",
            base_cost=18.00,
            regional_multipliers={"northeast": 1.3, "west": 1.0, "midwest": 1.2, "south": 1.4},
            labor_intensity=0.15,
            skill_level="specialized",
            lead_time=8,
            carbon_intensity=-5.0,  # Carbon sequestering
            lifespan=100
        ),
        "steel_light_gauge": MaterialSpec(
            name="Light Gauge Steel Stud",
            category="structural",
            unit="linear_ft",
            base_cost=4.50,
            regional_multipliers={"northeast": 1.1, "west": 1.2, "midwest": 1.0, "south": 0.95},
            labor_intensity=0.08,
            skill_level="semi_skilled",
            lead_time=2,
            carbon_intensity=2.5,
            lifespan=100
        ),
        "concrete_cmu": MaterialSpec(
            name="Concrete Masonry Unit (CMU)",
            category="structural",
            unit="sqft",
            base_cost=12.00,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 0.9},
            labor_intensity=0.5,
            skill_level="skilled",
            lead_time=1,
            carbon_intensity=15.0,
            lifespan=100
        ),

        # Enclosure
        "insulation_batt": MaterialSpec(
            name="Fiberglass Batt Insulation (R-13)",
            category="enclosure",
            unit="sqft",
            base_cost=1.80,
            regional_multipliers={"northeast": 1.0, "west": 1.1, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.1,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=1.5,
            lifespan=50
        ),
        "insulation_rigid": MaterialSpec(
            name="Rigid Foam Insulation (R-5)",
            category="enclosure",
            unit="sqft",
            base_cost=3.50,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 1.05},
            labor_intensity=0.08,
            skill_level="semi_skilled",
            lead_time=2,
            carbon_intensity=8.0,
            lifespan=50
        ),
        "insulation_spray": MaterialSpec(
            name="Spray Foam Insulation (closed cell)",
            category="enclosure",
            unit="sqft",
            base_cost=6.00,
            regional_multipliers={"northeast": 1.0, "west": 1.1, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.15,
            skill_level="specialized",
            lead_time=1,
            carbon_intensity=12.0,
            lifespan=50
        ),
        "sheathing_osb": MaterialSpec(
            name="OSB Sheathing",
            category="enclosure",
            unit="sqft",
            base_cost=1.20,
            regional_multipliers={"northeast": 1.1, "west": 1.2, "midwest": 1.0, "south": 1.05},
            labor_intensity=0.05,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=3.0,
            lifespan=100
        ),
        "house_wrap": MaterialSpec(
            name="House Wrap (Tyvek)",
            category="enclosure",
            unit="sqft",
            base_cost=0.80,
            regional_multipliers={"northeast": 1.0, "west": 1.05, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.03,
            skill_level="unskilled",
            lead_time=1,
            carbon_intensity=0.5,
            lifespan=50
        ),
        "roofing_asphalt": MaterialSpec(
            name="Asphalt Shingle Roof",
            category="enclosure",
            unit="sqft",
            base_cost=4.50,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 1.05},
            labor_intensity=0.2,
            skill_level="skilled",
            lead_time=1,
            carbon_intensity=5.0,
            lifespan=20
        ),
        "roofing_metal": MaterialSpec(
            name="Standing Seam Metal Roof",
            category="enclosure",
            unit="sqft",
            base_cost=14.00,
            regional_multipliers={"northeast": 1.1, "west": 1.0, "midwest": 1.05, "south": 1.1},
            labor_intensity=0.25,
            skill_level="specialized",
            lead_time=4,
            carbon_intensity=10.0,
            lifespan=50
        ),

        # Finishes
        "drywall": MaterialSpec(
            name="Gypsum Drywall (1/2\")",
            category="finish",
            unit="sqft",
            base_cost=2.20,
            regional_multipliers={"northeast": 1.1, "west": 1.2, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.25,
            skill_level="skilled",
            lead_time=1,
            carbon_intensity=2.0,
            lifespan=50
        ),
        "flooring_hardwood": MaterialSpec(
            name="Hardwood Flooring",
            category="finish",
            unit="sqft",
            base_cost=12.00,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 1.05},
            labor_intensity=0.3,
            skill_level="specialized",
            lead_time=2,
            carbon_intensity=2.0,
            lifespan=50
        ),
        "flooring_lvp": MaterialSpec(
            name="Luxury Vinyl Plank",
            category="finish",
            unit="sqft",
            base_cost=5.50,
            regional_multipliers={"northeast": 1.0, "west": 1.0, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.15,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=8.0,
            lifespan=15
        ),
        "flooring_tile": MaterialSpec(
            name="Ceramic Tile",
            category="finish",
            unit="sqft",
            base_cost=8.00,
            regional_multipliers={"northeast": 1.05, "west": 1.1, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.4,
            skill_level="skilled",
            lead_time=2,
            carbon_intensity=3.0,
            lifespan=50
        ),
        "flooring_carpet": MaterialSpec(
            name="Wall-to-Wall Carpet",
            category="finish",
            unit="sqft",
            base_cost=4.00,
            regional_multipliers={"northeast": 1.0, "west": 1.05, "midwest": 1.0, "south": 1.0},
            labor_intensity=0.15,
            skill_level="semi_skilled",
            lead_time=1,
            carbon_intensity=5.0,
            lifespan=10
        ),

        # Windows/Doors
        "window_vinyl": MaterialSpec(
            name="Vinyl Window (double pane)",
            category="enclosure",
            unit="each",
            base_cost=450,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 1.0},
            labor_intensity=2.0,
            skill_level="semi_skilled",
            lead_time=2,
            carbon_intensity=30.0,
            lifespan=25
        ),
        "window_fiberglass": MaterialSpec(
            name="Fiberglass Window (triple pane)",
            category="enclosure",
            unit="each",
            base_cost=900,
            regional_multipliers={"northeast": 1.1, "west": 1.15, "midwest": 1.0, "south": 1.05},
            labor_intensity=2.5,
            skill_level="skilled",
            lead_time=4,
            carbon_intensity=40.0,
            lifespan=40
        ),
    }

    def get_material(self, material_id: str) -> Optional[MaterialSpec]:
        """Get material specification by ID."""
        return self.MATERIALS.get(material_id)

    def calculate_material_cost(
        self,
        material_id: str,
        quantity: float,
        region: str = "midwest"
    ) -> float:
        """Calculate cost for a material quantity."""
        material = self.get_material(material_id)
        if not material:
            return 0.0

        base_cost = material.base_cost * quantity
        regional_mult = material.regional_multipliers.get(region, 1.0)
        return base_cost * regional_mult


# =============================================================================
# Cost Analysis
# =============================================================================

@dataclass
class CostBreakdown:
    """Detailed cost breakdown."""
    category: str  # "foundation", "structure", "enclosure", "interior", "mechanical"
    materials: float  # Material cost
    labor: float  # Labor cost
    total: float
    items: List[Dict[str, Any]]  # Detailed line items


@dataclass
class CostResult:
    """Result of cost analysis."""
    total_cost: float  # Total construction cost (USD)
    cost_per_sqft: float  # Cost per square meter
    breakdown: List[CostBreakdown]
    high_cost_items: List[Dict[str, Any]]  # Items driving cost
    budget_status: str  # "under", "near", "over"
    contingency_recommendation: float  # Recommended contingency %


class CostAnalysis:
    """Analyzes construction costs."""

    # Labor rates by region (2024 USD/hr)
    LABOR_RATES = {
        "unskilled": 35,
        "semi_skilled": 55,
        "skilled": 85,
        "specialized": 120,
    }

    # Regional adjustments for labor
    REGIONAL_LABOR_MULTIPLIERS = {
        "northeast": 1.25,
        "west": 1.30,
        "midwest": 1.0,
        "south": 0.90,
    }

    def __init__(self, region: str = "midwest"):
        """Initialize with region context."""
        self.region = region
        self.material_library = MaterialLibrary()

    def estimate_building_cost(
        self,
        rooms: List[Dict[str, Any]],
        site: Dict[str, Any],
        construction_system: ConstructionSystem,
        quality_level: QualityLevel
    ) -> CostResult:
        """Estimate total construction cost.

        Args:
            rooms: List of room definitions
            site: Site constraints
            construction_system: Primary structural system
            quality_level: Construction quality tier

        Returns:
            CostResult with detailed breakdown
        """
        # Calculate total area
        total_area = sum(r.get("area_min", 0) for r in rooms)

        # Quality multipliers
        quality_mults = {
            QualityLevel.BASIC: 0.85,
            QualityLevel.STANDARD: 1.0,
            QualityLevel.PREMIUM: 1.4,
            QualityLevel.CUSTOM: 1.8,
        }
        quality_mult = quality_mults.get(quality_level, 1.0)

        # System multipliers
        system_mults = {
            ConstructionSystem.WOOD_LIGHT_FRAME: 1.0,
            ConstructionSystem.WOOD_ADVANCED: 1.3,
            ConstructionSystem.STEEL_LIGHT_GAUGE: 1.15,
            ConstructionSystem.STEEL_STRUCTURAL: 1.5,
            ConstructionSystem.CONCRETE_CMU: 1.2,
            ConstructionSystem.CONCRETE_CAST: 1.6,
            ConstructionSystem.INSULATED_FORMS: 1.25,
            ConstructionSystem.STRUCTURAL_INSULATED: 1.35,
        }
        system_mult = system_mults.get(construction_system, 1.0)

        # Base cost per sqm by system (2024 USD)
        base_costs = {
            ConstructionSystem.WOOD_LIGHT_FRAME: 2500,  # $250/sqft
            ConstructionSystem.WOOD_ADVANCED: 3200,
            ConstructionSystem.STEEL_LIGHT_GAUGE: 2800,
            ConstructionSystem.STEEL_STRUCTURAL: 3700,
            ConstructionSystem.CONCRETE_CMU: 3000,
            ConstructionSystem.CONCRETE_CAST: 4000,
            ConstructionSystem.INSULATED_FORMS: 3100,
            ConstructionSystem.STRUCTURAL_INSULATED: 3300,
        }

        base_cost_per_sqm = base_costs.get(construction_system, 2500)
        adjusted_cost_per_sqm = base_cost_per_sqm * quality_mult * system_mult

        # Regional adjustment
        regional_mult = self.REGIONAL_LABOR_MULTIPLIERS.get(self.region, 1.0)
        adjusted_cost_per_sqm *= regional_mult

        total_cost = total_area * adjusted_cost_per_sqm

        # Generate breakdown (simplified allocation)
        breakdown = self._generate_breakdown(total_cost, total_area)

        # Identify high-cost items
        high_cost = self._identify_high_cost_items(breakdown)

        # Budget status
        budget_max = site.get("constraints", {}).get("budget_max")
        budget_status = "under"
        if budget_max:
            if total_cost > budget_max * 1.1:
                budget_status = "over"
            elif total_cost > budget_max * 0.9:
                budget_status = "near"

        # Contingency (10-20% based on complexity)
        if construction_system in (ConstructionSystem.WOOD_ADVANCED, ConstructionSystem.CONCRETE_CAST):
            contingency = 0.20
        elif quality_level in (QualityLevel.CUSTOM,):
            contingency = 0.18
        else:
            contingency = 0.12

        return CostResult(
            total_cost=round(total_cost),
            cost_per_sqft=round(adjusted_cost_per_sqm / 10.764, 2),  # Convert to sqft
            breakdown=breakdown,
            high_cost_items=high_cost,
            budget_status=budget_status,
            contingency_recommendation=contingency
        )

    def _generate_breakdown(self, total_cost: float, total_area: float) -> List[CostBreakdown]:
        """Generate detailed cost breakdown by category.

        Typical residential allocation:
        - Foundation: 10%
        - Structure: 20%
        - Enclosure: 25%
        - Interior: 30%
        - Mechanical: 15%
        """
        # Labor percentage varies by category
        labor_percentages = {
            "foundation": 0.35,
            "structure": 0.40,
            "enclosure": 0.35,
            "interior": 0.45,
            "mechanical": 0.50,
        }

        breakdown = []
        allocations = {
            "foundation": 0.10,
            "structure": 0.20,
            "enclosure": 0.25,
            "interior": 0.30,
            "mechanical": 0.15,
        }

        for category, allocation in allocations.items():
            cat_total = total_cost * allocation
            labor_cost = cat_total * labor_percentages[category]
            material_cost = cat_total - labor_cost

            breakdown.append(CostBreakdown(
                category=category,
                materials=round(material_cost),
                labor=round(labor_cost),
                total=round(cat_total),
                items=[]  # Would be populated with actual line items
            ))

        return breakdown

    def _identify_high_cost_items(self, breakdown: List[CostBreakdown]) -> List[Dict[str, Any]]:
        """Identify items driving cost."""
        high_cost = []

        # Find categories with highest totals
        sorted_cats = sorted(breakdown, key=lambda b: b.total, reverse=True)
        for cat in sorted_cats[:2]:
            high_cost.append({
                "category": cat.category,
                "impact": f"${cat.total:,.0f} ({cat.total / sum(b.total for b in breakdown) * 100:.0f}%)",
            })

        return high_cost


# =============================================================================
# Construction System Analysis
# =============================================================================

@dataclass
class SystemCompatibilityResult:
    """Result of system compatibility check."""
    compatible: bool
    conflicts: List[str]  # Incompatible combinations
    recommendations: List[str]  # Suggested alternatives


@dataclass
class ConstructionComplexity:
    """Complexity assessment for constructability."""
    complexity_score: float  # 0-1, higher = more complex
    crew_size: int  # Typical crew needed
    duration_weeks: int  # Estimated construction time
    special_equipment: List[str]  # Equipment needed
    skilled_trades_needed: List[str]  # Specialized trades
    risk_factors: List[str]  # Potential issues


class ConstructionSystemAnalysis:
    """Analyzes construction system compatibility and complexity."""

    # System compatibility matrix
    COMPATIBILITY = {
        # Can these systems be mixed in one building?
        (ConstructionSystem.WOOD_LIGHT_FRAME, ConstructionSystem.WOOD_ADVANCED): True,
        (ConstructionSystem.WOOD_LIGHT_FRAME, ConstructionSystem.STEEL_LIGHT_GAUGE): True,
        (ConstructionSystem.WOOD_LIGHT_FRAME, ConstructionSystem.INSULATED_FORMS): True,
        (ConstructionSystem.WOOD_ADVANCED, ConstructionSystem.WOOD_LIGHT_FRAME): True,
        (ConstructionSystem.STEEL_LIGHT_GAUGE, ConstructionSystem.WOOD_LIGHT_FRAME): True,
        (ConstructionSystem.INSULATED_FORMS, ConstructionSystem.WOOD_LIGHT_FRAME): True,
    }

    # Complexity scores (0-1)
    COMPLEXITY_SCORES = {
        ConstructionSystem.WOOD_LIGHT_FRAME: 0.2,
        ConstructionSystem.WOOD_ADVANCED: 0.5,
        ConstructionSystem.STEEL_LIGHT_GAUGE: 0.3,
        ConstructionSystem.STEEL_STRUCTURAL: 0.7,
        ConstructionSystem.CONCRETE_CMU: 0.4,
        ConstructionSystem.CONCRETE_CAST: 0.8,
        ConstructionSystem.INSULATED_FORMS: 0.35,
        ConstructionSystem.STRUCTURAL_INSULATED: 0.5,
    }

    def analyze_compatibility(
        self,
        primary_system: ConstructionSystem,
        secondary_systems: List[ConstructionSystem]
    ) -> SystemCompatibilityResult:
        """Check if construction systems are compatible."""
        conflicts = []
        recommendations = []

        for secondary in secondary_systems:
            key = (primary_system, secondary)
            reverse_key = (secondary, primary_system)

            if key not in self.COMPATIBILITY and reverse_key not in self.COMPATIBILITY:
                conflicts.append(f"{primary_system.value} and {secondary.value} are not typically mixed")
                recommendations.append(f"Use {primary_system.value} throughout, or design detail for transition")

        return SystemCompatibilityResult(
            compatible=len(conflicts) == 0,
            conflicts=conflicts,
            recommendations=recommendations
        )

    def assess_complexity(
        self,
        system: ConstructionSystem,
        total_area: float,
        stories: int = 1
    ) -> ConstructionComplexity:
        """Assess construction complexity."""
        complexity = self.COMPLEXITY_SCORES.get(system, 0.3)

        # Adjust for scale
        if total_area > 400:  # > 4000 sqft
            complexity += 0.1
        if stories > 1:
            complexity += 0.15

        # Crew size
        crew_sizes = {
            ConstructionSystem.WOOD_LIGHT_FRAME: 3,
            ConstructionSystem.WOOD_ADVANCED: 4,
            ConstructionSystem.STEEL_LIGHT_GAUGE: 4,
            ConstructionSystem.STEEL_STRUCTURAL: 6,
            ConstructionSystem.CONCRETE_CMU: 5,
            ConstructionSystem.CONCRETE_CAST: 8,
            ConstructionSystem.INSULATED_FORMS: 4,
            ConstructionSystem.STRUCTURAL_INSULATED: 5,
        }
        crew = crew_sizes.get(system, 4)

        # Duration (rough estimate: weeks per 100 sqm)
        duration_weeks = max(8, int(total_area / 100 * 1.5))
        if stories > 1:
            duration_weeks = int(duration_weeks * (1 + stories * 0.2))

        # Equipment
        equipment = []
        if system in (ConstructionSystem.STEEL_STRUCTURAL,):
            equipment.extend(["crane", "welding_equipment"])
        if system in (ConstructionSystem.CONCRETE_CAST,):
            equipment.extend(["concrete_pump", "forms"])
        if total_area > 300:
            equipment.append("skid_steer")

        # Special trades
        trades = ["carpenter"]
        if system in (ConstructionSystem.STEEL_STRUCTURAL, ConstructionSystem.STEEL_LIGHT_GAUGE):
            trades.append("ironworker")
        if system in (ConstructionSystem.CONCRETE_CMU, ConstructionSystem.CONCRETE_CAST):
            trades.append("mason" if system == ConstructionSystem.CONCRETE_CMU else "concrete_finisher")
        if system == ConstructionSystem.WOOD_ADVANCED:
            trades.append("timber_specialist")

        # Risk factors
        risks = []
        if complexity > 0.6:
            risks.append("high_complexity")
        if stories > 2 and system not in (ConstructionSystem.CONCRETE_CAST, ConstructionSystem.STEEL_STRUCTURAL):
            risks.append("multi_story_limit")
        if system == ConstructionSystem.WOOD_LIGHT_FRAME and total_area > 500:
            risks.append("span_limitations")

        return ConstructionComplexity(
            complexity_score=round(min(1.0, complexity), 2),
            crew_size=crew,
            duration_weeks=duration_weeks,
            special_equipment=equipment,
            skilled_trades_needed=trades,
            risk_factors=risks
        )


# =============================================================================
# Materiality Layer (Orchestrator)
# =============================================================================

@dataclass
class MaterialityResult:
    """Combined materiality analysis result."""
    cost: CostResult
    complexity: ConstructionComplexity
    carbon_footprint: float  # kg CO2e (embodied carbon)
    supply_chain_risks: List[str]  # Material availability issues
    lifecycle_cost_30yr: float  # Construction + energy + maintenance


class MaterialityLayer:
    """Economics-based analysis of buildability.

    This layer doesn't "optimize" - it reveals constraints.
    The economics is what it is.
    """

    # Export the enum for convenience
    System = ConstructionSystem
    Quality = QualityLevel

    def __init__(self, region: str = "midwest"):
        """Initialize with regional context.

        Args:
            region: Regional cost adjustment area
        """
        self.region = region
        self.cost_analysis = CostAnalysis(region)
        self.system_analysis = ConstructionSystemAnalysis()
        self.material_library = MaterialLibrary()

    def analyze(
        self,
        rooms: List[Dict[str, Any]],
        site: Dict[str, Any],
        construction_system: ConstructionSystem,
        quality_level: QualityLevel
    ) -> MaterialityResult:
        """Run all materiality analyses.

        Returns constraints and requirements imposed by economics.
        """
        # Cost analysis
        cost = self.cost_analysis.estimate_building_cost(
            rooms, site, construction_system, quality_level
        )

        # Complexity assessment
        total_area = sum(r.get("area_min", 0) for r in rooms)
        stories = site.get("constraints", {}).get("stories_max", 1)
        complexity = self.system_analysis.assess_complexity(
            construction_system, total_area, stories
        )

        # Carbon footprint (embodied carbon)
        carbon = self._calculate_embodied_carbon(rooms, construction_system)

        # Supply chain risks
        supply_risks = self._assess_supply_chain_risks(construction_system, quality_level)

        # Lifecycle cost (30 years)
        lifecycle_cost = self._calculate_lifecycle_cost(cost, supply_risks)

        return MaterialityResult(
            cost=cost,
            complexity=complexity,
            carbon_footprint=carbon,
            supply_chain_risks=supply_risks,
            lifecycle_cost_30yr=lifecycle_cost
        )

    def _calculate_embodied_carbon(
        self,
        rooms: List[Dict[str, Any]],
        system: ConstructionSystem
    ) -> float:
        """Calculate embodied carbon (simplified)."""
        # Approximate kg CO2e per sqm by system
        carbon_per_sqm = {
            ConstructionSystem.WOOD_LIGHT_FRAME: 150,  # Wood stores carbon
            ConstructionSystem.WOOD_ADVANCED: 100,  # More wood = more sequestration
            ConstructionSystem.STEEL_LIGHT_GAUGE: 250,
            ConstructionSystem.STEEL_STRUCTURAL: 400,
            ConstructionSystem.CONCRETE_CMU: 300,
            ConstructionSystem.CONCRETE_CAST: 450,
            ConstructionSystem.INSULATED_FORMS: 200,
            ConstructionSystem.STRUCTURAL_INSULATED: 120,
        }

        total_area = sum(r.get("area_min", 0) for r in rooms)
        multiplier = carbon_per_sqm.get(system, 200)
        return total_area * multiplier

    def _assess_supply_chain_risks(
        self,
        system: ConstructionSystem,
        quality: QualityLevel
    ) -> List[str]:
        """Assess supply chain and lead time risks."""
        risks = []

        # System-specific risks
        if system == ConstructionSystem.WOOD_ADVANCED:
            risks.append("clt_availability")
        if system == ConstructionSystem.STEEL_STRUCTURAL:
            risks.append("steel_lead_time")
        if quality == QualityLevel.CUSTOM:
            risks.append("custom_materials_lead_time")

        return risks

    def _calculate_lifecycle_cost(
        self,
        construction_cost: CostResult,
        risks: List[str]
    ) -> float:
        """Calculate 30-year lifecycle cost (simplified)."""
        # Construction
        initial = construction_cost.total_cost

        # Energy (rough estimate: $2-4/sqft/yr depending on climate)
        total_area = construction_cost.total_cost / (construction_cost.cost_per_sqft * 10.764)
        annual_energy = total_area * 30  # $30/sqm/yr average
        energy_30yr = annual_energy * 30

        # Maintenance (rough estimate: 0.5-2% of construction cost annually)
        annual_maintenance = initial * 0.01
        maintenance_30yr = annual_maintenance * 30

        return initial + energy_30yr + maintenance_30yr
