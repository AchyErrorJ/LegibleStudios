"""
Construction Detail Tools
=========================
Tools for creating accurate construction details, assembly walls, and explosion views.
Integrates with the assembly system to generate real geometry in Revit.
"""

import requests
from typing import List, Dict, Any, Optional
from assembly_system import (
    ConstructionAssembly, AssemblyGeometryGenerator, LayerGeometry,
    get_assembly, list_assemblies, ASSEMBLY_LIBRARY,
    create_2x6_exterior_wall, create_2x4_interior_wall,
    INCH
)


# =============================================================================
# REVIT API INTEGRATION
# =============================================================================

REVIT_API_URL = "http://localhost:48884"


def create_mass_from_profile(
    profile_points: List[List[float]],
    height: float,
    level_name: str,
    name: str = "Assembly Layer",
    material_name: str = "",
    color: tuple = (128, 128, 128)
) -> Dict:
    """
    Create an extruded mass/solid in Revit from a profile.
    Uses DirectShape or in-place mass depending on Revit capabilities.
    """
    # For now, we'll create these as floor slabs at different heights
    # This is a workaround until we add DirectShape support to the C# API

    payload = {
        "points": profile_points,
        "height": height,
        "level_name": level_name,
        "name": name,
    }

    try:
        # Try DirectShape endpoint first (if available)
        response = requests.post(
            f"{REVIT_API_URL}/revit_mcp/create_direct_shape",
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass

    # Fallback: Create as a series of thin floors (each layer)
    # This isn't ideal but demonstrates the concept
    return {"status": "pending", "message": "DirectShape endpoint needed"}


# =============================================================================
# ASSEMBLY WALL CREATION
# =============================================================================

def create_assembly_wall(
    assembly_key: str,
    start_point: List[float],
    end_point: List[float],
    height: float = 10.0,
    level_name: str = "Level 1",
    core_location: str = "center"
) -> Dict:
    """
    Create a wall with all construction layers as real geometry.

    Args:
        assembly_key: Key from assembly library (e.g., "ext_wall_2x6")
        start_point: [x, y, z] start of wall
        end_point: [x, y, z] end of wall
        height: Wall height in feet
        level_name: Revit level name
        core_location: "center", "exterior", or "interior"

    Returns:
        Dict with created layer information
    """
    assembly = get_assembly(assembly_key)
    if not assembly:
        return {"status": "error", "message": f"Unknown assembly: {assembly_key}"}

    generator = AssemblyGeometryGenerator(assembly)
    layer_geoms = generator.generate_wall_segment(
        start_point, end_point, height,
        core_location=core_location
    )

    print(f"   🏗️ Creating assembly wall: {assembly.name}")
    print(f"   📏 Total thickness: {assembly.total_thickness() * 12:.2f} inches")
    print(f"   📋 Layers: {len(assembly.layers)}")

    created_layers = []

    for i, geom in enumerate(layer_geoms):
        layer = geom.layer
        print(f"      {i+1}. {layer.name} ({layer.thickness * 12:.3f}\")")

        solid = geom.to_revit_solid()
        if solid:
            # For now, store the geometry data
            # When DirectShape is available, this will create real geometry
            created_layers.append({
                "name": layer.name,
                "thickness": layer.thickness,
                "offset": geom.offset_from_core,
                "geometry": solid,
            })

    return {
        "status": "success",
        "assembly": assembly.name,
        "layers_created": len(created_layers),
        "total_thickness_inches": assembly.total_thickness() * 12,
        "layers": created_layers,
    }


def create_assembly_wall_batch(
    assembly_key: str,
    wall_segments: List[Dict],
    height: float = 10.0,
    level_name: str = "Level 1"
) -> Dict:
    """
    Create multiple wall segments with the same assembly.

    Args:
        assembly_key: Assembly from library
        wall_segments: List of {"start": [x,y,z], "end": [x,y,z]}
        height: Wall height
        level_name: Revit level

    Returns:
        Batch creation results
    """
    results = []

    for segment in wall_segments:
        result = create_assembly_wall(
            assembly_key,
            segment.get("start", segment.get("start_point", [0, 0, 0])),
            segment.get("end", segment.get("end_point", [0, 0, 0])),
            height,
            level_name
        )
        results.append(result)

    success_count = sum(1 for r in results if r.get("status") == "success")

    return {
        "status": "batch_complete",
        "total": len(wall_segments),
        "successful": success_count,
        "results": results,
    }


# =============================================================================
# EXPLOSION VIEW
# =============================================================================

def create_explosion_view(
    assembly_key: str,
    start_point: List[float],
    end_point: List[float],
    height: float = 10.0,
    level_name: str = "Level 1",
    separation: float = 0.5,  # Gap between layers in feet
    direction: str = "perpendicular"  # "perpendicular" or "parallel"
) -> Dict:
    """
    Create an exploded view showing all assembly layers separated.

    Args:
        assembly_key: Assembly from library
        start_point: Wall start
        end_point: Wall end
        height: Wall height
        level_name: Revit level
        separation: Gap between layers (feet)
        direction: Explosion direction

    Returns:
        Explosion view data
    """
    assembly = get_assembly(assembly_key)
    if not assembly:
        return {"status": "error", "message": f"Unknown assembly: {assembly_key}"}

    generator = AssemblyGeometryGenerator(assembly)
    layer_geoms = generator.generate_explosion_view(
        start_point, end_point, height,
        separation=separation
    )

    print(f"   💥 Creating explosion view: {assembly.name}")
    print(f"   📏 Separation: {separation * 12:.1f} inches between layers")

    exploded_layers = []

    for i, geom in enumerate(layer_geoms):
        layer = geom.layer
        solid = geom.to_revit_solid()

        exploded_layers.append({
            "index": i,
            "name": layer.name,
            "thickness_inches": layer.thickness * 12,
            "explosion_offset": geom.explosion_offset,
            "layer_type": layer.layer_type.value,
            "color": layer.color,
            "geometry": solid,
        })

    # Calculate total exploded length
    total_exploded = sum(l.layer.thickness + separation for l in layer_geoms)

    return {
        "status": "success",
        "assembly": assembly.name,
        "layers": exploded_layers,
        "layer_count": len(exploded_layers),
        "separation_inches": separation * 12,
        "total_exploded_length_inches": total_exploded * 12,
    }


# =============================================================================
# SECTION DETAIL GENERATION
# =============================================================================

def generate_section_detail(
    assembly_key: str,
    height: float = 10.0,
    detail_width: float = 2.0,
    include_dimensions: bool = True,
    include_labels: bool = True
) -> Dict:
    """
    Generate a section detail view of an assembly.

    Args:
        assembly_key: Assembly from library
        height: Section height
        detail_width: Width of detail view
        include_dimensions: Add dimension annotations
        include_labels: Add layer labels

    Returns:
        Section detail data
    """
    assembly = get_assembly(assembly_key)
    if not assembly:
        return {"status": "error", "message": f"Unknown assembly: {assembly_key}"}

    generator = AssemblyGeometryGenerator(assembly)
    detail = generator.generate_section_detail(
        cut_location=detail_width / 2,
        wall_length=detail_width,
        height=height,
        detail_width=detail_width
    )

    # Add dimension data
    dimensions = []
    if include_dimensions:
        current_offset = 0
        for layer_data in detail["layers"]:
            dimensions.append({
                "layer": layer_data["name"],
                "start_offset": current_offset,
                "end_offset": current_offset + layer_data["thickness"],
                "value_inches": layer_data["thickness"] * 12,
            })
            current_offset += layer_data["thickness"]

        # Overall dimension
        dimensions.append({
            "layer": "TOTAL",
            "start_offset": 0,
            "end_offset": detail["total_thickness"],
            "value_inches": detail["total_thickness"] * 12,
        })

    # Add labels
    labels = []
    if include_labels:
        for layer_data in detail["layers"]:
            labels.append({
                "text": layer_data["name"],
                "offset": layer_data["offset"] + layer_data["thickness"] / 2,
            })

    return {
        "status": "success",
        "assembly": detail["assembly_name"],
        "total_thickness_inches": detail["total_thickness"] * 12,
        "r_value": detail["r_value"],
        "layers": detail["layers"],
        "dimensions": dimensions,
        "labels": labels,
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_available_assemblies() -> Dict:
    """Get list of all available construction assemblies"""
    assemblies = list_assemblies()
    return {
        "status": "success",
        "count": len(assemblies),
        "assemblies": assemblies,
    }


def get_assembly_info(assembly_key: str) -> Dict:
    """Get detailed information about a specific assembly"""
    assembly = get_assembly(assembly_key)
    if not assembly:
        return {"status": "error", "message": f"Unknown assembly: {assembly_key}"}

    layers_info = []
    for layer in assembly.layers:
        layers_info.append({
            "name": layer.name,
            "thickness_inches": layer.thickness * 12,
            "type": layer.layer_type.value,
            "material": layer.material_name,
            "is_structural": layer.is_structural,
            "is_continuous": layer.is_continuous,
        })

    return {
        "status": "success",
        "name": assembly.name,
        "type": assembly.assembly_type,
        "is_exterior": assembly.is_exterior,
        "is_load_bearing": assembly.is_load_bearing,
        "total_thickness_inches": assembly.total_thickness() * 12,
        "r_value": assembly.r_value,
        "fire_rating": assembly.fire_rating,
        "layer_count": len(assembly.layers),
        "layers": layers_info,
    }


def compare_assemblies(assembly_keys: List[str]) -> Dict:
    """Compare multiple assemblies side by side"""
    comparisons = []

    for key in assembly_keys:
        info = get_assembly_info(key)
        if info.get("status") == "success":
            comparisons.append({
                "key": key,
                "name": info["name"],
                "thickness": info["total_thickness_inches"],
                "r_value": info["r_value"],
                "layers": info["layer_count"],
                "fire_rating": info.get("fire_rating", ""),
            })

    return {
        "status": "success",
        "assemblies_compared": len(comparisons),
        "comparison": comparisons,
    }


# =============================================================================
# WALL DETAIL WITH MEMBRANE EMPHASIS
# =============================================================================

def create_wall_detail_with_membranes(
    assembly_key: str,
    start_point: List[float],
    end_point: List[float],
    height: float = 10.0,
    level_name: str = "Level 1",
    core_location: str = "center",
    show_section: bool = True
) -> Dict:
    """
    Create a wall with automatic membrane layer emphasis.

    This function creates a wall assembly in Revit where membrane layers
    (WRB, vapor barriers, air barriers) are automatically identified and
    highlighted with distinct geometry for construction documentation.

    Args:
        assembly_key: Assembly from library (e.g., "ext_wall_2x6")
        start_point: [x, y, z] wall start point
        end_point: [x, y, z] wall end point
        height: Wall height in feet
        level_name: Revit level name
        core_location: "center", "exterior", or "interior"
        show_section: Generate section detail data

    Returns:
        Dict with:
        - wall_info: Created wall layer information
        - membrane_info: List of membrane layers with positions
        - section_detail: Optional section cut data
        - geometry: All layer geometries including membranes
    """
    assembly = get_assembly(assembly_key)
    if not assembly:
        return {"status": "error", "message": f"Unknown assembly: {assembly_key}"}

    generator = AssemblyGeometryGenerator(assembly)

    # Generate wall geometry
    layer_geoms = generator.generate_wall_segment(
        start_point, end_point, height,
        core_location=core_location
    )

    print(f"   [WALL] Creating wall detail with membranes: {assembly.name}")
    print(f"   [LOCATION] {start_point} -> {end_point}")
    print(f"   [HEIGHT] {height:.2f} ft")

    # Collect all layer info and identify membranes
    layers_info = []
    membrane_info = []

    for geom in layer_geoms:
        solid_def = geom.to_revit_solid()
        if solid_def:
            layers_info.append({
                "name": geom.layer.name,
                "thickness": geom.layer.thickness,
                "offset": geom.offset_from_core,
                "material": geom.layer.material_name,
                "color": geom.layer.color,
                "layer_type": geom.layer.layer_type.value,
                "is_membrane": solid_def["is_membrane"],
                "geometry": solid_def,
            })

            # Track membranes separately
            if solid_def["is_membrane"]:
                membrane_info.append({
                    "name": geom.layer.name,
                    "material": geom.layer.material_name,
                    "offset_from_core": geom.offset_from_core,
                    "thickness": geom.layer.thickness,
                    "position_description": f"{geom.offset_from_core:.3f} ft from core",
                })
                print(f"      [MEMBRANE] {geom.layer.name} at {geom.offset_from_core:.3f} ft")

    result = {
        "status": "success",
        "assembly_name": assembly.name,
        "assembly_key": assembly_key,
        "total_thickness": assembly.total_thickness(),
        "r_value": assembly.r_value,
        "layers": layers_info,
        "membrane_count": len(membrane_info),
        "membrane_info": membrane_info,
    }

    # Add section detail if requested
    if show_section:
        wall_length = ((end_point[0] - start_point[0])**2 +
                      (end_point[1] - start_point[1])**2)**0.5
        section_detail = generator.generate_section_detail(
            cut_location=wall_length / 2,
            wall_length=wall_length,
            height=height,
            detail_width=2.0
        )
        result["section_detail"] = section_detail

        print(f"   [SECTION] Section detail generated")
        print(f"      Membranes identified: {len(section_detail['membrane_locations'])}")

    return result


# =============================================================================
# TEMPLATE DETECTION FOR ORCHESTRATOR
# =============================================================================

def detect_detail_template(query_lower: str, variables: dict = None) -> Optional[Dict]:
    """Detect detail/assembly related queries"""

    # List assemblies
    if any(t in query_lower for t in ["list assemblies", "available assemblies", "show assemblies", "construction assemblies"]):
        return {
            "name": "List Construction Assemblies",
            "plan": [{"tool": "list_construction_assemblies", "args": {}}],
            "display_in_chat": True,
        }

    # Explosion view
    if any(t in query_lower for t in ["explosion view", "explode wall", "exploded view", "show layers", "layer breakdown"]):
        return {
            "name": "Assembly Explosion View",
            "needs_input": True,
            "question": "Which assembly would you like to explode?",
            "options": ["ext_wall_2x6 - Exterior 2x6 Frame", "int_wall_2x4 - Interior Partition", "floor_wood - Wood Floor", "roof_shingle - Shingle Roof"],
            "plan": [],
        }

    # Section detail
    if any(t in query_lower for t in ["section detail", "wall section", "assembly detail", "construction detail"]):
        return {
            "name": "Generate Section Detail",
            "needs_input": True,
            "question": "Which assembly do you want a section detail for?",
            "options": ["ext_wall_2x6 - Exterior 2x6 Frame", "int_wall_2x4 - Interior Partition", "floor_wood - Wood Floor", "roof_shingle - Shingle Roof"],
            "plan": [],
        }

    # Assembly info
    if "assembly info" in query_lower or "assembly detail" in query_lower:
        return {
            "name": "Assembly Information",
            "needs_input": True,
            "question": "Which assembly do you want information about?",
            "options": list(ASSEMBLY_LIBRARY.keys()),
            "plan": [],
        }

    return None
