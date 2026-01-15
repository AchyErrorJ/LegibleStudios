"""QBD Layers - Physics, Economics, Psychology.

Expands QBD Algebra from pure logic to reality modeling:
- Environment: Physics of site, climate, materials
- Materiality: Economics of construction, cost, supply
- Perception: Psychology of experience, comfort, delight

Architecture:
    Logic (current)  →  Rooms touch each other correctly
    + Environment     →  Building responds to sun, air, gravity
    + Materiality     →  Building respects cost, labor, materials
    + Perception      →  Building serves human needs

Total Reality = Logic + Physics + Economics + Psychology
"""

from .environment import EnvironmentLayer, SolarAnalysis, ThermalAnalysis, AcousticAnalysis
from .materiality import MaterialityLayer, CostAnalysis, ConstructionSystemAnalysis, MaterialLibrary
from .perception import PerceptionLayer, WayfindingAnalysis, ComfortAnalysis, DelightAnalysis

__all__ = [
    # Environment
    "EnvironmentLayer",
    "SolarAnalysis",
    "ThermalAnalysis",
    "AcousticAnalysis",

    # Materiality
    "MaterialityLayer",
    "CostAnalysis",
    "ConstructionSystemAnalysis",
    "MaterialLibrary",

    # Perception
    "PerceptionLayer",
    "WayfindingAnalysis",
    "ComfortAnalysis",
    "DelightAnalysis",
]
