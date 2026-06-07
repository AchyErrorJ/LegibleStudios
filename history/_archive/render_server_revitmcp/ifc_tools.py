# ifc_tools.py
# IFC parsing utilities for element-level AI enhancement

import ifcopenshell
import ifcopenshell.geom
from pathlib import Path
from collections import defaultdict
import hashlib

print("=== IFC TOOLS MODULE LOADED ===")


def load_ifc(ifc_path: str):
    """Load an IFC file."""
    return ifcopenshell.open(ifc_path)


def get_element_summary(ifc_path: str) -> dict:
    """
    Get summary of all element types in an IFC file.

    Returns dict like:
    {
        "IfcWall": 45,
        "IfcWindow": 12,
        "IfcDoor": 8,
        ...
    }
    """
    ifc = load_ifc(ifc_path)

    summary = defaultdict(int)
    for element in ifc.by_type("IfcBuildingElement"):
        summary[element.is_a()] += 1

    # Also get other common types
    for type_name in ["IfcSpace", "IfcFurnishingElement", "IfcCovering"]:
        elements = ifc.by_type(type_name)
        if elements:
            summary[type_name] = len(elements)

    return dict(sorted(summary.items(), key=lambda x: -x[1]))


def get_elements_by_type(ifc_path: str, element_type: str) -> list:
    """
    Get all elements of a specific type.

    Args:
        ifc_path: Path to IFC file
        element_type: IFC class name (e.g., "IfcWall", "IfcWindow")

    Returns:
        List of element info dicts
    """
    ifc = load_ifc(ifc_path)
    elements = ifc.by_type(element_type)

    result = []
    for el in elements:
        info = {
            "id": el.id(),
            "global_id": el.GlobalId,
            "name": el.Name or f"Unnamed {element_type}",
            "type": el.is_a(),
        }

        # Try to get material
        if hasattr(el, "HasAssociations"):
            for assoc in el.HasAssociations:
                if assoc.is_a("IfcRelAssociatesMaterial"):
                    mat = assoc.RelatingMaterial
                    if hasattr(mat, "Name"):
                        info["material"] = mat.Name

        result.append(info)

    return result


def global_id_to_color(global_id: str) -> tuple:
    """Convert IFC GlobalId to unique RGB color for element ID rendering."""
    hash_bytes = hashlib.md5(global_id.encode()).digest()
    return (hash_bytes[0], hash_bytes[1], hash_bytes[2])


def get_element_colors(ifc_path: str, element_types: list = None) -> dict:
    """
    Generate unique colors for each element for ID pass rendering.

    Args:
        ifc_path: Path to IFC file
        element_types: List of types to include (None = all)

    Returns:
        Dict mapping global_id -> (r, g, b)
    """
    ifc = load_ifc(ifc_path)

    colors = {}

    if element_types is None:
        elements = ifc.by_type("IfcBuildingElement")
    else:
        elements = []
        for et in element_types:
            elements.extend(ifc.by_type(et))

    for el in elements:
        colors[el.GlobalId] = global_id_to_color(el.GlobalId)

    return colors


def get_materials(ifc_path: str) -> dict:
    """
    Get all materials in the IFC file.

    Returns dict like:
    {
        "Brick - Common": ["IfcWall", "IfcWall", ...],
        "Glass - Clear": ["IfcWindow", "IfcWindow", ...],
    }
    """
    ifc = load_ifc(ifc_path)

    materials = defaultdict(list)

    for rel in ifc.by_type("IfcRelAssociatesMaterial"):
        mat = rel.RelatingMaterial
        mat_name = getattr(mat, "Name", None) or str(mat.is_a())

        for obj in rel.RelatedObjects:
            if hasattr(obj, "is_a"):
                materials[mat_name].append(obj.is_a())

    return dict(materials)


def get_elements_by_material(ifc_path: str, material_name: str) -> list:
    """Get all elements using a specific material."""
    ifc = load_ifc(ifc_path)

    result = []

    for rel in ifc.by_type("IfcRelAssociatesMaterial"):
        mat = rel.RelatingMaterial
        mat_str = getattr(mat, "Name", None) or str(mat.is_a())

        if material_name.lower() in mat_str.lower():
            for obj in rel.RelatedObjects:
                result.append({
                    "id": obj.id(),
                    "global_id": obj.GlobalId,
                    "name": obj.Name or "Unnamed",
                    "type": obj.is_a(),
                    "material": mat_str
                })

    return result


# Quick test
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ifc_tools.py <path_to_ifc>")
        print("\nThis tool analyzes IFC files for element-level AI enhancement.")
        sys.exit(1)

    ifc_path = sys.argv[1]

    if not Path(ifc_path).exists():
        print(f"File not found: {ifc_path}")
        sys.exit(1)

    print(f"\nAnalyzing: {ifc_path}")
    print("=" * 50)

    # Element summary
    print("\n[ELEMENT SUMMARY]")
    summary = get_element_summary(ifc_path)
    for elem_type, count in summary.items():
        print(f"  {elem_type}: {count}")

    # Materials
    print("\n[MATERIALS]")
    materials = get_materials(ifc_path)
    for mat_name, elements in list(materials.items())[:15]:
        print(f"  {mat_name}: {len(elements)} elements")

    print("\n[DONE] IFC analysis complete!")
    print("\nYou can now select elements by type or material for AI enhancement.")
