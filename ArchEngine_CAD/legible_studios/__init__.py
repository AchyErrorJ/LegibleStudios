"""
Legible Studios - Constraint-based design interpretation suite.

A suite of tools that interpret the same building geometry through different
constraint lenses: climate, structural, code, cost, acoustic.

Each studio is like an LOD level, but for constraint domains instead of zoom.
"""

from .core.studio_manager import StudioManager, StudioLevel
from .core.constraint_lens import ConstraintLens, LensResult
from .studios.climate_studio import ClimateStudio
from .studios.structural_studio import StructuralStudio
from .studios.code_studio import CodeStudio
from .studios.cost_studio import CostStudio
from .studios.acoustic_studio import AcousticStudio

__all__ = [
    # Core
    "StudioManager",
    "StudioLevel",
    "ConstraintLens",
    "LensResult",
    # Studios
    "ClimateStudio",
    "StructuralStudio",
    "CodeStudio",
    "CostStudio",
    "AcousticStudio",
]


def get_studio_manager() -> StudioManager:
    """Get the singleton studio manager instance."""
    return StudioManager()


def create_all_studios() -> dict:
    """Create all studio instances.
    
    Returns:
        Dict mapping StudioLevel to studio instance
    """
    return {
        StudioLevel.CLIMATE: ClimateStudio(),
        StudioLevel.STRUCTURAL: StructuralStudio(),
        StudioLevel.CODE: CodeStudio(),
        StudioLevel.COST: CostStudio(),
        StudioLevel.ACOUSTIC: AcousticStudio(),
    }
