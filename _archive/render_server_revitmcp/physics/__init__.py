# Physics Engine Module
# Part of the RevitMCP Design Engine
#
# Phase 1: Python prototypes for validation
# Phase 2: Port to C++/Rust for performance

# Analysis modules
from .structural import StructuralAnalyzer
from .thermal import ThermalAnalyzer
from .lighting import LightingAnalyzer
from .acoustic import AcousticAnalyzer

# Visualization modules
from .structural_viz import StructuralVisualizer
from .thermal_viz import ThermalVisualizer
from .lighting_viz import LightingVisualizer
from .acoustic_viz import AcousticVisualizer

# Layer-based assemblies and detail rendering
from .assemblies import (
    Material,
    MaterialCategory,
    Layer,
    LayeredAssembly,
    get_all_assembly_presets,
)
from .detail_renderer import DetailRenderer, HatchPatterns

# Structural connections and fastener estimation
from .connections import (
    Connector,
    ConnectorType,
    Fastener,
    FastenerType,
    FastenerSchedule,
    FastenerEstimator,
    ConnectionRenderer,
)

# IFC import (optional - requires ifcopenshell)
try:
    from .ifc_importer import (
        IFCImporter,
        IFCLayerSet,
        IFCMaterialLayer,
        import_ifc_assemblies,
    )
    IFC_IMPORT_AVAILABLE = True
except ImportError:
    IFC_IMPORT_AVAILABLE = False

__all__ = [
    # Analyzers
    'StructuralAnalyzer',
    'ThermalAnalyzer',
    'LightingAnalyzer',
    'AcousticAnalyzer',
    # Visualizers
    'StructuralVisualizer',
    'ThermalVisualizer',
    'LightingVisualizer',
    'AcousticVisualizer',
    # Assemblies & Details
    'Material',
    'MaterialCategory',
    'Layer',
    'LayeredAssembly',
    'DetailRenderer',
    'HatchPatterns',
    'get_all_assembly_presets',
    # Connections & Fasteners
    'Connector',
    'ConnectorType',
    'Fastener',
    'FastenerType',
    'FastenerSchedule',
    'FastenerEstimator',
    'ConnectionRenderer',
    # IFC Import
    'IFCImporter',
    'IFCLayerSet',
    'IFCMaterialLayer',
    'import_ifc_assemblies',
    'IFC_IMPORT_AVAILABLE',
]
