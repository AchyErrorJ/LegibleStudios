"""
IFC Layer Importer

Imports IFC (Industry Foundation Classes) geometry and extracts material layer sets
to create LayeredAssembly objects for thermal analysis and detail rendering.

Requires: pip install ifcopenshell
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
import re

try:
    import ifcopenshell
    import ifcopenshell.util.element as element_util
    IFC_AVAILABLE = True
except ImportError:
    IFC_AVAILABLE = False
    print("Warning: ifcopenshell not installed. IFC import will not be available.")
    print("Install with: pip install ifcopenshell")

from .assemblies import Material, MaterialCategory, Layer, LayeredAssembly


class IFCElementType(Enum):
    """Types of IFC elements that can have material layers."""
    WALL = "IfcWall"
    WALL_STANDARD = "IfcWallStandardCase"
    SLAB = "IfcSlab"
    ROOF = "IfcRoof"
    COVERING = "IfcCovering"
    MEMBER = "IfcMember"
    PLATE = "IfcPlate"


@dataclass
class IFCMaterialLayer:
    """Represents a single material layer from IFC."""
    name: str
    thickness_mm: float
    category: Optional[str] = None
    is_ventilated: bool = False

    @property
    def thickness_in(self) -> float:
        """Thickness in inches."""
        return self.thickness_mm / 25.4


@dataclass
class IFCLayerSet:
    """Represents a complete material layer set from IFC."""
    name: str
    layers: List[IFCMaterialLayer] = field(default_factory=list)
    total_thickness_mm: float = 0.0
    element_type: Optional[str] = None
    element_id: Optional[int] = None

    @property
    def total_thickness_in(self) -> float:
        """Total thickness in inches."""
        return self.total_thickness_mm / 25.4


# Material name mapping from common IFC names to our Material presets
# Note: Preset names must match methods in the Material class
IFC_MATERIAL_MAP: Dict[str, str] = {
    # Gypsum board variants
    'gypsum': 'drywall_5_8',
    'gypsum board': 'drywall_5_8',
    'gyp bd': 'drywall_5_8',
    'drywall': 'drywall_5_8',
    'sheetrock': 'drywall_5_8',
    'plasterboard': 'drywall_5_8',
    'type x': 'drywall_5_8',
    'type x gypsum': 'drywall_5_8',
    'fire rated gypsum': 'drywall_5_8',
    'fire-rated gypsum': 'drywall_5_8',
    'densglass': 'drywall_5_8',
    '1/2" drywall': 'drywall_half',
    '5/8" drywall': 'drywall_5_8',

    # Wood framing
    'wood stud': 'wood_stud',
    'wood studs': 'wood_stud',
    'stud': 'wood_stud',
    'studs': 'wood_stud',
    '2x4': 'wood_stud',
    '2x6': 'wood_stud',
    '2x8': 'wood_stud',
    '2x10': 'wood_stud',
    '2x12': 'wood_stud',
    'lumber': 'wood_stud',
    'framing': 'wood_stud',
    'wood framing': 'wood_stud',
    'dimensional lumber': 'wood_stud',
    'lvl': 'lvl',

    # Sheathing
    'osb': 'osb',
    'oriented strand board': 'osb',
    'plywood': 'plywood',
    'sheathing': 'osb',
    'structural sheathing': 'osb',
    'wall sheathing': 'osb',
    'roof sheathing': 'osb',
    'subfloor': 'subfloor_osb',

    # Insulation - Batts
    'fiberglass': 'fiberglass_batt',
    'fiberglass batt': 'fiberglass_batt',
    'fiberglass insulation': 'fiberglass_batt',
    'batt insulation': 'fiberglass_batt',
    'batt': 'fiberglass_batt',
    'mineral wool': 'mineral_wool',
    'rockwool': 'mineral_wool',
    'rock wool': 'mineral_wool',
    'cellulose': 'cellulose',
    'blown cellulose': 'cellulose',
    'dense pack cellulose': 'cellulose',

    # Insulation - Rigid
    'xps': 'xps_foam',
    'extruded polystyrene': 'xps_foam',
    'styrofoam': 'xps_foam',
    'eps': 'eps_foam',
    'expanded polystyrene': 'eps_foam',
    'polyiso': 'polyiso',
    'polyisocyanurate': 'polyiso',
    'iso board': 'polyiso',
    'rigid insulation': 'xps_foam',
    'continuous insulation': 'xps_foam',
    'ci': 'xps_foam',

    # Insulation - Spray
    'spray foam': 'spray_foam_closed',
    'closed cell': 'spray_foam_closed',
    'closed cell spray foam': 'spray_foam_closed',
    'open cell': 'spray_foam_open',
    'open cell spray foam': 'spray_foam_open',
    'spf': 'spray_foam_closed',

    # Concrete/Masonry
    'concrete': 'concrete',
    'cast concrete': 'concrete',
    'cast in place concrete': 'concrete',
    'cip concrete': 'concrete',
    'reinforced concrete': 'concrete',
    'concrete block': 'cmu',
    'cmu': 'cmu',
    'concrete masonry': 'cmu',
    'masonry': 'cmu',
    'brick': 'brick',
    'face brick': 'brick',
    'clay brick': 'brick',
    'brick veneer': 'brick',

    # Membranes
    'air barrier': 'air_barrier_membrane',
    'vapor barrier': 'vapor_barrier',
    'vapor retarder': 'vapor_barrier',
    'house wrap': 'housewrap',
    'housewrap': 'housewrap',
    'tyvek': 'housewrap',
    'wrb': 'housewrap',
    'weather barrier': 'housewrap',
    'building paper': 'housewrap',
    'felt paper': 'housewrap',

    # Finishes
    'stucco': 'stucco',
    'eifs': 'stucco',
    'siding': 'fiber_cement',
    'fiber cement': 'fiber_cement',
    'hardie': 'fiber_cement',
    'hardieboard': 'fiber_cement',
    'cement board': 'fiber_cement',
    'lap siding': 'fiber_cement',
    'vinyl siding': 'vinyl_siding',
    'aluminum siding': 'vinyl_siding',
    'metal siding': 'metal_roof',
    'metal panel': 'metal_roof',
    'steel panel': 'metal_roof',
    'wood siding': 'wood_siding',
    'cedar siding': 'wood_siding',
    'stone veneer': 'stone_veneer',

    # Roofing
    'shingles': 'asphalt_shingles',
    'asphalt shingles': 'asphalt_shingles',
    'roofing': 'asphalt_shingles',
    'roof membrane': 'roof_membrane',
    'epdm': 'roof_membrane',
    'tpo': 'roof_membrane',
    'pvc membrane': 'roof_membrane',
    'built-up roofing': 'roof_membrane',
    'metal roofing': 'metal_roof',
    'standing seam': 'metal_roof',

    # Flooring
    'hardwood': 'hardwood_floor',
    'wood floor': 'hardwood_floor',
    'oak floor': 'hardwood_floor',
    'tile': 'tile_thinset',
    'ceramic tile': 'tile_thinset',
    'porcelain tile': 'tile_thinset',
    'carpet': 'carpet_pad',
    'carpet and pad': 'carpet_pad',
    'vinyl floor': 'vinyl_siding',
    'lvp': 'vinyl_siding',
    'lvt': 'vinyl_siding',

    # Subfloor
    'subfloor': 'subfloor_osb',
    'underlayment': 'subfloor_plywood',
    'floor sheathing': 'osb',

    # Steel
    'steel': 'steel_beam',
    'steel stud': 'steel_beam',
    'steel framing': 'steel_beam',
    'metal stud': 'steel_beam',
    'light gauge steel': 'steel_beam',
    'lgs': 'steel_beam',
    'steel beam': 'steel_beam',
}


class IFCImporter:
    """
    Imports IFC files and extracts material layer information.

    Usage:
        importer = IFCImporter('building.ifc')

        # Get all wall assemblies
        walls = importer.get_wall_assemblies()

        # Get specific element by ID
        assembly = importer.get_assembly_by_id(12345)

        # Get summary of all elements
        summary = importer.get_layer_summary()
    """

    def __init__(self, ifc_path: Optional[str] = None):
        """
        Initialize the IFC importer.

        Args:
            ifc_path: Path to IFC file. Can be set later with load_file().
        """
        if not IFC_AVAILABLE:
            raise ImportError(
                "ifcopenshell is required for IFC import. "
                "Install with: pip install ifcopenshell"
            )

        self.ifc_path = ifc_path
        self.model: Optional[Any] = None
        self._layer_sets_cache: Dict[int, IFCLayerSet] = {}

        if ifc_path:
            self.load_file(ifc_path)

    def load_file(self, ifc_path: str) -> bool:
        """
        Load an IFC file.

        Args:
            ifc_path: Path to the IFC file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.model = ifcopenshell.open(ifc_path)
            self.ifc_path = ifc_path
            self._layer_sets_cache.clear()
            return True
        except Exception as e:
            print(f"Error loading IFC file: {e}")
            return False

    def _normalize_material_name(self, name: str) -> str:
        """Normalize material name for matching."""
        if not name:
            return ""
        # Convert to lowercase and remove extra whitespace
        normalized = re.sub(r'\s+', ' ', name.lower().strip())
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(material[:\s]*|mat[:\s]*)', '', normalized)
        normalized = re.sub(r'[\d.]+\s*(mm|in|inch|inches|"|\')\s*', '', normalized)
        return normalized.strip()

    def _map_material(self, ifc_name: str, thickness_in: float) -> Material:
        """
        Map an IFC material name to our Material class.

        Args:
            ifc_name: Material name from IFC
            thickness_in: Layer thickness in inches

        Returns:
            Mapped Material object
        """
        normalized = self._normalize_material_name(ifc_name)

        # Try direct lookup
        if normalized in IFC_MATERIAL_MAP:
            preset_name = IFC_MATERIAL_MAP[normalized]
            return getattr(Material, preset_name)()

        # Try partial matching
        for pattern, preset_name in IFC_MATERIAL_MAP.items():
            if pattern in normalized or normalized in pattern:
                return getattr(Material, preset_name)()

        # Infer from thickness and name patterns
        # Thin layers (< 0.25") are likely membranes
        if thickness_in < 0.25:
            if any(term in normalized for term in ['air', 'vapor', 'barrier']):
                if 'vapor' in normalized:
                    return Material.vapor_barrier()
                return Material.air_barrier_membrane()
            if any(term in normalized for term in ['wrap', 'paper', 'weather']):
                return Material.housewrap()
            # Default thin layer to air barrier
            return Material.air_barrier_membrane()

        # Very thin layers (0.25-0.75") could be sheathing or finish
        if thickness_in < 0.75:
            if any(term in normalized for term in ['gyp', 'board', 'dry']):
                return Material.drywall_5_8()
            if any(term in normalized for term in ['ply', 'osb', 'sheath']):
                return Material.osb()
            return Material.drywall_5_8()  # Default

        # Medium layers (0.75-2") could be rigid insulation or finishes
        if thickness_in < 2.0:
            if any(term in normalized for term in ['insul', 'rigid', 'foam']):
                return Material.xps_foam()
            if any(term in normalized for term in ['stucco', 'render']):
                return Material.stucco()
            return Material.xps_foam()  # Default to insulation

        # Thick layers (2-8") are likely cavity insulation or framing
        if thickness_in < 8.0:
            if any(term in normalized for term in ['insul', 'batt', 'fiber', 'cellu']):
                return Material.fiberglass_batt()
            if any(term in normalized for term in ['stud', 'fram', 'wood', 'lumber']):
                return Material.wood_stud()
            if any(term in normalized for term in ['concr', 'cmu', 'block', 'mason']):
                return Material.cmu()
            # Default to framing cavity
            return Material.wood_stud()

        # Very thick layers (>8") are usually concrete or masonry
        if any(term in normalized for term in ['concr']):
            return Material.concrete()
        if any(term in normalized for term in ['brick', 'mason', 'cmu']):
            return Material.brick()

        # Final fallback
        return Material.concrete()

    def _extract_material_layers(self, element) -> Optional[IFCLayerSet]:
        """
        Extract material layer information from an IFC element.

        Args:
            element: IfcElement object

        Returns:
            IFCLayerSet if layers found, None otherwise
        """
        # Check cache first
        element_id = element.id()
        if element_id in self._layer_sets_cache:
            return self._layer_sets_cache[element_id]

        # Get material associations
        material = None

        # Try to get material layer set usage (most common for walls/slabs)
        for rel in self.model.by_type('IfcRelAssociatesMaterial'):
            if element in rel.RelatedObjects:
                material = rel.RelatingMaterial
                break

        if not material:
            return None

        layers = []
        layer_set_name = "Unknown"

        # Handle IfcMaterialLayerSetUsage
        if material.is_a('IfcMaterialLayerSetUsage'):
            layer_set = material.ForLayerSet
            layer_set_name = layer_set.LayerSetName or "Unnamed Layer Set"

            for mat_layer in layer_set.MaterialLayers:
                layer_name = "Unknown"
                if mat_layer.Material:
                    layer_name = mat_layer.Material.Name or "Unknown"

                thickness_mm = mat_layer.LayerThickness or 0.0
                is_ventilated = getattr(mat_layer, 'IsVentilated', False) or False
                category = getattr(mat_layer, 'Category', None)

                layers.append(IFCMaterialLayer(
                    name=layer_name,
                    thickness_mm=thickness_mm,
                    category=category,
                    is_ventilated=is_ventilated
                ))

        # Handle IfcMaterialLayerSet directly
        elif material.is_a('IfcMaterialLayerSet'):
            layer_set_name = material.LayerSetName or "Unnamed Layer Set"

            for mat_layer in material.MaterialLayers:
                layer_name = "Unknown"
                if mat_layer.Material:
                    layer_name = mat_layer.Material.Name or "Unknown"

                thickness_mm = mat_layer.LayerThickness or 0.0
                is_ventilated = getattr(mat_layer, 'IsVentilated', False) or False
                category = getattr(mat_layer, 'Category', None)

                layers.append(IFCMaterialLayer(
                    name=layer_name,
                    thickness_mm=thickness_mm,
                    category=category,
                    is_ventilated=is_ventilated
                ))

        # Handle single material (create single layer)
        elif material.is_a('IfcMaterial'):
            layer_set_name = material.Name or "Single Material"
            # Try to get thickness from element geometry
            # For now, use a default
            layers.append(IFCMaterialLayer(
                name=material.Name or "Unknown",
                thickness_mm=100.0,  # Default 100mm
                category=None,
                is_ventilated=False
            ))

        if not layers:
            return None

        total_thickness = sum(l.thickness_mm for l in layers)

        layer_set = IFCLayerSet(
            name=layer_set_name,
            layers=layers,
            total_thickness_mm=total_thickness,
            element_type=element.is_a(),
            element_id=element_id
        )

        self._layer_sets_cache[element_id] = layer_set
        return layer_set

    def _layer_set_to_assembly(
        self,
        layer_set: IFCLayerSet,
        assembly_type: str = "wall"
    ) -> LayeredAssembly:
        """
        Convert an IFCLayerSet to a LayeredAssembly.

        Args:
            layer_set: IFCLayerSet object
            assembly_type: Type of assembly ('wall', 'floor', 'roof')

        Returns:
            LayeredAssembly object
        """
        layers = []

        for ifc_layer in layer_set.layers:
            material = self._map_material(ifc_layer.name, ifc_layer.thickness_in)

            # Check if this is a framing layer based on material category or name
            is_framing = (
                material.category in [MaterialCategory.WOOD, MaterialCategory.METAL]
                or any(term in ifc_layer.name.lower() for term in ['stud', 'joist', 'rafter', 'framing'])
            )

            if is_framing:
                # For framing layers, use default framing material and spacing
                layer = Layer(
                    material=Material.fiberglass_batt(),  # Insulation in cavity
                    thickness_in=ifc_layer.thickness_in,
                    is_framing_layer=True,
                    framing_material=material,
                    framing_spacing_in=16.0,
                    framing_width_in=1.5
                )
            else:
                layer = Layer(
                    material=material,
                    thickness_in=ifc_layer.thickness_in,
                    is_framing_layer=False
                )
            layers.append(layer)

        return LayeredAssembly(
            name=layer_set.name,
            layers=layers,
            assembly_type=assembly_type
        )

    def get_all_elements_with_layers(self) -> List[Tuple[Any, IFCLayerSet]]:
        """
        Get all elements that have material layer sets.

        Returns:
            List of (element, layer_set) tuples
        """
        if not self.model:
            return []

        results = []

        # Element types that commonly have layer sets
        element_types = [
            'IfcWall', 'IfcWallStandardCase',
            'IfcSlab', 'IfcRoof', 'IfcCovering'
        ]

        for element_type in element_types:
            for element in self.model.by_type(element_type):
                layer_set = self._extract_material_layers(element)
                if layer_set:
                    results.append((element, layer_set))

        return results

    def get_wall_assemblies(self) -> List[LayeredAssembly]:
        """
        Get all wall assemblies from the IFC file.

        Returns:
            List of LayeredAssembly objects for walls
        """
        if not self.model:
            return []

        assemblies = []
        seen_layer_sets = set()

        for element_type in ['IfcWall', 'IfcWallStandardCase']:
            for element in self.model.by_type(element_type):
                layer_set = self._extract_material_layers(element)
                if layer_set and layer_set.name not in seen_layer_sets:
                    seen_layer_sets.add(layer_set.name)
                    assembly = self._layer_set_to_assembly(layer_set, "wall")
                    assemblies.append(assembly)

        return assemblies

    def get_floor_assemblies(self) -> List[LayeredAssembly]:
        """
        Get all floor/slab assemblies from the IFC file.

        Returns:
            List of LayeredAssembly objects for floors
        """
        if not self.model:
            return []

        assemblies = []
        seen_layer_sets = set()

        for element in self.model.by_type('IfcSlab'):
            # Check if it's a floor (not a roof slab)
            predefined_type = getattr(element, 'PredefinedType', None)
            if predefined_type and predefined_type in ['ROOF', 'LANDING']:
                continue

            layer_set = self._extract_material_layers(element)
            if layer_set and layer_set.name not in seen_layer_sets:
                seen_layer_sets.add(layer_set.name)
                assembly = self._layer_set_to_assembly(layer_set, "floor")
                assemblies.append(assembly)

        return assemblies

    def get_roof_assemblies(self) -> List[LayeredAssembly]:
        """
        Get all roof assemblies from the IFC file.

        Returns:
            List of LayeredAssembly objects for roofs
        """
        if not self.model:
            return []

        assemblies = []
        seen_layer_sets = set()

        # Get IfcRoof elements
        for element in self.model.by_type('IfcRoof'):
            layer_set = self._extract_material_layers(element)
            if layer_set and layer_set.name not in seen_layer_sets:
                seen_layer_sets.add(layer_set.name)
                assembly = self._layer_set_to_assembly(layer_set, "roof")
                assemblies.append(assembly)

        # Also check slabs marked as roofs
        for element in self.model.by_type('IfcSlab'):
            predefined_type = getattr(element, 'PredefinedType', None)
            if predefined_type == 'ROOF':
                layer_set = self._extract_material_layers(element)
                if layer_set and layer_set.name not in seen_layer_sets:
                    seen_layer_sets.add(layer_set.name)
                    assembly = self._layer_set_to_assembly(layer_set, "roof")
                    assemblies.append(assembly)

        return assemblies

    def get_assembly_by_id(self, element_id: int) -> Optional[LayeredAssembly]:
        """
        Get assembly for a specific IFC element ID.

        Args:
            element_id: IFC element ID

        Returns:
            LayeredAssembly if found, None otherwise
        """
        if not self.model:
            return None

        try:
            element = self.model.by_id(element_id)
            layer_set = self._extract_material_layers(element)
            if layer_set:
                # Determine type
                if element.is_a('IfcWall') or element.is_a('IfcWallStandardCase'):
                    return self._layer_set_to_assembly(layer_set, "wall")
                elif element.is_a('IfcSlab'):
                    predefined_type = getattr(element, 'PredefinedType', None)
                    if predefined_type == 'ROOF':
                        return self._layer_set_to_assembly(layer_set, "roof")
                    return self._layer_set_to_assembly(layer_set, "floor")
                elif element.is_a('IfcRoof'):
                    return self._layer_set_to_assembly(layer_set, "roof")
                else:
                    return self._layer_set_to_assembly(layer_set, "wall")
        except Exception:
            pass

        return None

    def get_layer_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all layer sets in the IFC file.

        Returns:
            Dictionary with summary information
        """
        if not self.model:
            return {"error": "No model loaded"}

        elements = self.get_all_elements_with_layers()

        walls = []
        floors = []
        roofs = []
        other = []

        for element, layer_set in elements:
            info = {
                "id": layer_set.element_id,
                "name": layer_set.name,
                "type": layer_set.element_type,
                "total_thickness_mm": round(layer_set.total_thickness_mm, 1),
                "total_thickness_in": round(layer_set.total_thickness_in, 2),
                "layer_count": len(layer_set.layers),
                "layers": [
                    {
                        "name": l.name,
                        "thickness_mm": round(l.thickness_mm, 1),
                        "thickness_in": round(l.thickness_in, 2)
                    }
                    for l in layer_set.layers
                ]
            }

            if element.is_a('IfcWall') or element.is_a('IfcWallStandardCase'):
                walls.append(info)
            elif element.is_a('IfcSlab'):
                predefined_type = getattr(element, 'PredefinedType', None)
                if predefined_type == 'ROOF':
                    roofs.append(info)
                else:
                    floors.append(info)
            elif element.is_a('IfcRoof'):
                roofs.append(info)
            else:
                other.append(info)

        return {
            "file": self.ifc_path,
            "total_elements_with_layers": len(elements),
            "walls": walls,
            "floors": floors,
            "roofs": roofs,
            "other": other
        }

    def print_layer_summary(self):
        """Print a formatted summary of all layer sets."""
        summary = self.get_layer_summary()

        if "error" in summary:
            print(f"Error: {summary['error']}")
            return

        print(f"\nIFC Layer Summary: {summary['file']}")
        print(f"{'='*60}")
        print(f"Total elements with layers: {summary['total_elements_with_layers']}")

        for category in ['walls', 'floors', 'roofs', 'other']:
            items = summary[category]
            if items:
                print(f"\n{category.upper()} ({len(items)} types):")
                print("-" * 40)

                for item in items:
                    print(f"\n  {item['name']} (ID: {item['id']})")
                    print(f"  Type: {item['type']}")
                    print(f"  Total: {item['total_thickness_in']}\" ({item['total_thickness_mm']}mm)")
                    print(f"  Layers:")
                    for layer in item['layers']:
                        print(f"    - {layer['name']}: {layer['thickness_in']}\" ({layer['thickness_mm']}mm)")


def import_ifc_assemblies(ifc_path: str) -> Dict[str, List[LayeredAssembly]]:
    """
    Convenience function to import all assemblies from an IFC file.

    Args:
        ifc_path: Path to IFC file

    Returns:
        Dictionary with 'walls', 'floors', 'roofs' keys containing LayeredAssembly lists
    """
    importer = IFCImporter(ifc_path)

    return {
        'walls': importer.get_wall_assemblies(),
        'floors': importer.get_floor_assemblies(),
        'roofs': importer.get_roof_assemblies()
    }
