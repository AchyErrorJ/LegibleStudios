"""
LOD Bridge - Integration between LOD system and Legible Studios.

Connects the zoom-based LOD system to the constraint-based Studio system,
allowing them to work together or independently.
"""

from typing import Dict, Any, Optional, Callable
from ..core.studio_manager import StudioManager, StudioLevel


class LODStudioBridge:
    """
    Bridges LOD (zoom-based) and Studios (constraint-based).
    
    Allows two modes:
    1. Linked: Studio level follows LOD level (zoom changes constraint view)
    2. Independent: LOD and Studios operate separately
    """

    def __init__(self, studio_manager: Optional[StudioManager] = None):
        self.studio_manager = studio_manager or StudioManager()
        self._linked = True
        self._lod_to_studio_map = {
            1: StudioLevel.CLIMATE,      # Topology → Climate
            2: StudioLevel.STRUCTURAL,   # Walls → Structural
            3: StudioLevel.CODE,         # Fixtures → Code
            4: StudioLevel.COST,         # Viewports → Cost
            5: StudioLevel.ACOUSTIC,     # Documentation → Acoustic
        }
        self._studio_to_lod_map = {v: k for k, v in self._lod_to_studio_map.items()}

    @property
    def linked(self) -> bool:
        """Whether LOD and Studios are linked."""
        return self._linked

    @linked.setter
    def linked(self, value: bool):
        """Set linked mode."""
        self._linked = value

    def on_lod_change(self, lod_level: int, transition: float):
        """
        Handle LOD change from zoom system.
        
        If linked, updates studio level to match.
        """
        if not self._linked:
            return

        studio_level = self._lod_to_studio_map.get(lod_level)
        if studio_level:
            self.studio_manager.set_studio_override(studio_level)

    def on_studio_change(self, studio_level: StudioLevel):
        """
        Handle studio change from studio selector.
        
        If linked, could update LOD (though typically LOD drives Studios).
        """
        if not self._linked:
            return

        # When user manually selects studio, we could zoom to matching LOD
        # This is optional behavior
        lod_level = self._studio_to_lod_map.get(studio_level)
        # Would emit signal to LOD system here

    def get_combined_opacities(self, lod_level: int, focus: float) -> Dict[str, float]:
        """
        Get combined opacity values for both LOD and Studio layers.
        
        Returns dict with both LOD and Studio opacity values.
        """
        # LOD opacities (from LOD system)
        lod_opacities = {
            f"lod-{i}": 1.0 if i <= lod_level else 0.0
            for i in range(1, 6)
        }

        # Studio opacities
        studio_opacities = self.studio_manager.calculate_all_opacities(focus)
        studio_opacities = {
            f"studio-{level.value}": opacity
            for level, opacity in studio_opacities.items()
        }

        return {**lod_opacities, **studio_opacities}

    def get_active_content_types(self, lod_level: int, studio_focus: float) -> set:
        """Get all content types that should be visible."""
        content_types = set()

        # Add LOD content types
        # (Would integrate with LOD_LAYERS from lod_layers.py)

        # Add Studio content types
        dominant = self.studio_manager.get_dominant_studio(studio_focus)
        content_types.update(self.studio_manager.get_content_types(dominant))

        return content_types

    def create_linked_indicator(self, parent=None):
        """Create a UI indicator showing LOD/Studio linkage."""
        # Would return a widget showing both LOD and Studio state
        pass


def create_default_bridge() -> LODStudioBridge:
    """Create a default LOD-Studio bridge."""
    return LODStudioBridge()
