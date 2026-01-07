"""
Physics Analysis Tools for MCP

Exposes structural, thermal, lighting, and acoustic analysis capabilities
through the MCP interface, enabling LLM agents to perform building physics
calculations and generate detail drawings.
"""

import json
import base64
import io
from typing import List, Dict, Optional, Any
from mcp.server.fastmcp import Context
from .registry import mcp, register_tool

# Import physics modules
import sys
sys.path.insert(0, '..')
from physics import (
    # Analyzers
    StructuralAnalyzer,
    ThermalAnalyzer,
    LightingAnalyzer,
    AcousticAnalyzer,
    # Visualizers
    StructuralVisualizer,
    ThermalVisualizer,
    LightingVisualizer,
    AcousticVisualizer,
    # Assemblies (thermal materials)
    Material,
    MaterialCategory,
    Layer,
    LayeredAssembly,
    DetailRenderer,
    get_all_assembly_presets,
    # Connections
    FastenerEstimator,
    ConnectionRenderer,
    # IFC Import
    IFC_IMPORT_AVAILABLE,
)
# Import structural Material class separately (different from assembly Material)
from physics.structural import Material as StructuralMaterial

if IFC_IMPORT_AVAILABLE:
    from physics import IFCImporter, import_ifc_assemblies


def format_response(response: Any) -> str:
    """Format response as JSON string."""
    if isinstance(response, dict):
        return json.dumps(response, indent=2)
    return str(response)


# =========================================================
# STRUCTURAL ANALYSIS TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def analyze_beam(
    span_ft: float,
    tributary_width_ft: float,
    dead_load_psf: float = 15.0,
    live_load_psf: float = 40.0,
    material: str = "wood_spf",
    depth_in: float = 9.25,
    width_in: float = 3.5,
    ctx: Context = None
) -> str:
    """
    Analyze a beam for structural adequacy.

    Args:
        span_ft: Beam span in feet
        tributary_width_ft: Tributary width in feet
        dead_load_psf: Dead load in pounds per square foot (default 15)
        live_load_psf: Live load in pounds per square foot (default 40)
        material: Material type - 'wood_spf', 'wood_df', 'steel_a36', 'steel_a992'
        depth_in: Beam depth in inches
        width_in: Beam width in inches

    Returns:
        JSON with beam analysis results including stress ratios and pass/fail status
    """
    analyzer = StructuralAnalyzer()

    # Get material properties using class methods
    materials = {
        'wood_spf': StructuralMaterial.wood_spf(),
        'wood_df': StructuralMaterial.wood_df(),
        'steel_a36': StructuralMaterial.steel_a36(),
        'steel_a992': StructuralMaterial.steel_a992(),
    }
    mat = materials.get(material, StructuralMaterial.wood_spf())

    # Convert tributary loads to uniform load (plf)
    uniform_load_plf = (dead_load_psf + live_load_psf) * tributary_width_ft

    result = analyzer.analyze_simple_beam(
        span_ft=span_ft,
        width_in=width_in,
        depth_in=depth_in,
        material=mat,
        uniform_load_plf=uniform_load_plf
    )

    return format_response({
        "status": "success",
        "analysis": "beam",
        "input": {
            "span_ft": span_ft,
            "tributary_width_ft": tributary_width_ft,
            "dead_load_psf": dead_load_psf,
            "live_load_psf": live_load_psf,
            "uniform_load_plf": round(uniform_load_plf, 1),
            "size": f"{width_in}x{depth_in}"
        },
        "result": {
            "passes": result.passes,
            "max_stress_psi": round(result.max_stress_psi, 0),
            "allowable_stress_psi": round(result.allowable_stress_psi, 0),
            "utilization_ratio": round(result.utilization_ratio, 3),
            "actual_deflection_in": round(result.max_deflection_in, 3),
            "allowable_deflection_in": round(result.allowable_deflection_in, 3),
            "warnings": result.warnings
        }
    })


@mcp.tool()
@register_tool
async def analyze_column(
    height_ft: float,
    axial_load_lbs: float,
    material: str = "wood_spf",
    depth_in: float = 5.5,
    width_in: float = 5.5,
    unbraced_length_ft: Optional[float] = None,
    ctx: Context = None
) -> str:
    """
    Analyze a column for structural adequacy including buckling.

    Args:
        height_ft: Column height in feet
        axial_load_lbs: Axial load in pounds
        material: Material type - 'wood_spf', 'wood_df', 'steel_a36', 'steel_a992'
        depth_in: Column depth in inches
        width_in: Column width in inches
        unbraced_length_ft: Unbraced length (defaults to full height)

    Returns:
        JSON with column analysis including buckling check
    """
    analyzer = StructuralAnalyzer()

    # Get material properties using class methods
    materials = {
        'wood_spf': StructuralMaterial.wood_spf(),
        'wood_df': StructuralMaterial.wood_df(),
        'steel_a36': StructuralMaterial.steel_a36(),
        'steel_a992': StructuralMaterial.steel_a992(),
    }
    mat = materials.get(material, StructuralMaterial.wood_spf())

    result = analyzer.analyze_column(
        height_ft=height_ft,
        width_in=width_in,
        depth_in=depth_in,
        material=mat,
        axial_load_lbs=axial_load_lbs
    )

    return format_response({
        "status": "success",
        "analysis": "column",
        "input": {
            "height_ft": height_ft,
            "size": f"{width_in}x{depth_in}",
            "axial_load_lbs": axial_load_lbs
        },
        "result": {
            "passes": result.passes,
            "utilization_ratio": round(result.utilization_ratio, 3),
            "slenderness_ratio": round(result.slenderness_ratio, 2),
            "allowable_load_lbs": round(result.allowable_load_lbs, 0),
            "applied_load_lbs": round(result.applied_load_lbs, 0),
            "buckling_mode": result.buckling_mode,
            "warnings": result.warnings,
            "recommendations": result.recommendations
        }
    })


@mcp.tool()
@register_tool
async def analyze_floor_system(
    span_ft: float,
    floor_width_ft: float = 12.0,
    dead_load_psf: float = 15.0,
    live_load_psf: float = 40.0,
    ctx: Context = None
) -> str:
    """
    Analyze a floor joist system and get recommended joist size.

    Args:
        span_ft: Joist span in feet
        floor_width_ft: Floor width in feet (perpendicular to joists)
        dead_load_psf: Dead load in PSF
        live_load_psf: Live load in PSF

    Returns:
        JSON with floor system analysis including recommended joist size
    """
    analyzer = StructuralAnalyzer()

    result = analyzer.analyze_floor_system(
        span_ft=span_ft,
        floor_width_ft=floor_width_ft,
        dead_load_psf=dead_load_psf,
        live_load_psf=live_load_psf
    )

    return format_response({
        "status": "success",
        "analysis": "floor_system",
        "input": {
            "span_ft": span_ft,
            "floor_width_ft": floor_width_ft,
            "dead_load_psf": dead_load_psf,
            "live_load_psf": live_load_psf
        },
        "result": {
            "passes": result.passes,
            "joist_size": result.joist_size,
            "joist_spacing_in": result.joist_spacing_in,
            "joist_utilization": round(result.joist_utilization, 3),
            "total_depth_in": result.total_depth_in,
            "deflection_in": round(result.deflection_in, 3),
            "allowable_deflection_in": round(result.allowable_deflection_in, 3),
            "vibration_check": result.vibration_check,
            "warnings": result.warnings,
            "recommendations": result.recommendations
        }
    })


# =========================================================
# THERMAL ANALYSIS TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def analyze_thermal_assembly(
    assembly_name: str,
    interior_temp_f: float = 70.0,
    exterior_temp_f: float = 0.0,
    relative_humidity_pct: float = 40.0,
    ctx: Context = None
) -> str:
    """
    Analyze thermal performance of a wall/floor/roof assembly.

    Args:
        assembly_name: Preset assembly name (use list_assembly_presets to see options)
        interior_temp_f: Interior temperature in Fahrenheit
        exterior_temp_f: Exterior design temperature in Fahrenheit
        relative_humidity_pct: Interior relative humidity percentage

    Returns:
        JSON with R-value, U-factor, temperature profile, and condensation risk
    """
    assembly = _get_assembly_by_name(assembly_name)

    if assembly is None:
        return format_response({
            "status": "error",
            "message": f"Unknown assembly: {assembly_name}",
            "available_presets": _get_all_preset_names()
        })

    # Get temperature profile
    profile = assembly.get_temperature_profile(interior_temp_f, exterior_temp_f)

    # Check condensation risk
    condensation_result = assembly.find_condensation_plane(
        interior_temp_f, exterior_temp_f, relative_humidity_pct
    )

    # Format condensation risk
    if condensation_result is None:
        condensation_risk = {
            "risk_level": "low",
            "message": "No condensation risk detected"
        }
    else:
        depth_in, layer_name, dew_point = condensation_result
        condensation_risk = {
            "risk_level": "high",
            "depth_in": round(float(depth_in), 2),
            "layer": layer_name,
            "dew_point_f": round(float(dew_point), 1),
            "message": f"Condensation risk at {layer_name} ({depth_in:.1f}\" from interior)"
        }

    return format_response({
        "status": "success",
        "analysis": "thermal",
        "assembly": {
            "name": assembly.name,
            "type": assembly.assembly_type,
            "total_thickness_in": round(assembly.total_thickness_in, 2),
            "r_value": round(assembly.total_r_value, 1),
            "u_factor": round(assembly.u_factor, 4),
        },
        "temperature_profile": [
            {"position_in": round(p, 2), "temp_f": round(t, 1), "layer": l}
            for p, t, l in profile
        ],
        "condensation_risk": condensation_risk
    })


@mcp.tool()
@register_tool
async def calculate_heat_loss(
    climate_zone: int,
    floor_area_sqft: float,
    wall_area_sqft: float,
    roof_area_sqft: float,
    window_area_sqft: float,
    volume_cuft: float,
    wall_r_value: float = 13.0,
    roof_r_value: float = 38.0,
    window_type: str = "double_pane_low_e",
    ach_natural: float = 0.35,
    ctx: Context = None
) -> str:
    """
    Calculate building heat loss using simplified Manual J method.

    Args:
        climate_zone: IECC climate zone (1-8)
        floor_area_sqft: Conditioned floor area in square feet
        wall_area_sqft: Gross exterior wall area (excluding windows) in square feet
        roof_area_sqft: Ceiling/roof area in square feet
        window_area_sqft: Total window area in square feet
        volume_cuft: Conditioned volume in cubic feet
        wall_r_value: Wall R-value (default R-13 for 2x4 wall)
        roof_r_value: Roof/attic R-value (default R-38)
        window_type: Window type - 'single_pane', 'double_pane_clear', 'double_pane_low_e', 'triple_pane_low_e'
        ach_natural: Natural air infiltration rate (default 0.35)

    Returns:
        JSON with heat loss breakdown and total BTU/hr
    """
    from physics.thermal import ThermalAnalyzer, ClimateZone, Assembly, Window as ThermalWindow

    analyzer = ThermalAnalyzer()

    # Map climate zone integer to enum
    zone_map = {i: ClimateZone(i) for i in range(1, 9)}
    zone = zone_map.get(climate_zone, ClimateZone.ZONE_5)

    # Create assemblies from R-values
    wall_assembly = Assembly(f"Wall R-{wall_r_value}", wall_r_value, 4.5)
    roof_assembly = Assembly(f"Roof R-{roof_r_value}", roof_r_value, 12.0)

    # Map window type to Window object
    window_types = {
        'single_pane': ThermalWindow.single_pane(),
        'double_pane_clear': ThermalWindow.double_pane_clear(),
        'double_pane_low_e': ThermalWindow.double_pane_low_e(),
        'triple_pane_low_e': ThermalWindow.triple_pane_low_e(),
    }
    window = window_types.get(window_type, ThermalWindow.double_pane_low_e())

    result = analyzer.calculate_heat_loss(
        climate_zone=zone,
        floor_area_sqft=floor_area_sqft,
        wall_area_sqft=wall_area_sqft,
        wall_assembly=wall_assembly,
        roof_area_sqft=roof_area_sqft,
        roof_assembly=roof_assembly,
        window_area_sqft=window_area_sqft,
        window=window,
        volume_cuft=volume_cuft,
        ach_natural=ach_natural
    )

    return format_response({
        "status": "success",
        "analysis": "heat_loss",
        "input": {
            "climate_zone": climate_zone,
            "floor_area_sqft": floor_area_sqft,
            "wall_r_value": wall_r_value,
            "roof_r_value": roof_r_value,
            "window_type": window_type
        },
        "result": {
            "total_btuh": round(result.total_btuh, 0),
            "envelope_btuh": round(result.envelope_btuh, 0),
            "infiltration_btuh": round(result.infiltration_btuh, 0),
            "ventilation_btuh": round(result.ventilation_btuh, 0),
            "component_breakdown": {k: round(v, 0) for k, v in result.component_breakdown.items()},
            "btuh_per_sqft": round(result.total_btuh / floor_area_sqft, 2),
            "recommendations": result.recommendations
        }
    })


# =========================================================
# LIGHTING ANALYSIS TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def analyze_daylighting(
    room_width_ft: float,
    room_depth_ft: float,
    room_height_ft: float,
    window_area_sqft: float,
    window_height_ft: float,
    glazing_transmittance: float = 0.6,
    ctx: Context = None
) -> str:
    """
    Analyze daylighting potential for a space using BRE daylight factor method.

    Args:
        room_width_ft: Room width (parallel to windows) in feet
        room_depth_ft: Room depth (perpendicular to windows) in feet
        room_height_ft: Floor to ceiling height in feet
        window_area_sqft: Total glazing area in square feet
        window_height_ft: Head height of window from floor
        glazing_transmittance: Light transmission of glass (0-1, typical 0.6)

    Returns:
        JSON with daylight factor, uniformity, and recommendations
    """
    analyzer = LightingAnalyzer()

    result = analyzer.calculate_daylight_factor(
        room_width_ft=room_width_ft,
        room_depth_ft=room_depth_ft,
        room_height_ft=room_height_ft,
        window_area_sqft=window_area_sqft,
        window_height_ft=window_height_ft,
        glazing_transmittance=glazing_transmittance
    )

    # Calculate window-to-floor ratio
    floor_area = room_width_ft * room_depth_ft
    wfr = window_area_sqft / floor_area

    return format_response({
        "status": "success",
        "analysis": "daylighting",
        "input": {
            "room_dimensions_ft": f"{room_width_ft} x {room_depth_ft} x {room_height_ft}",
            "window_area_sqft": window_area_sqft,
            "glazing_transmittance": glazing_transmittance
        },
        "result": {
            "daylight_factor_pct": round(result.daylight_factor_pct, 1),
            "uniformity_ratio": round(result.uniformity_ratio, 2),
            "sda_pct": round(result.sda_pct, 1),
            "meets_criteria": result.meets_criteria,
            "window_to_floor_ratio": round(wfr, 3),
            "recommendations": result.recommendations
        }
    })


@mcp.tool()
@register_tool
async def calculate_electric_lighting(
    floor_area_sqft: float,
    space_type: str = "office_general",
    ceiling_height_ft: float = 9.0,
    fixture_lumens: int = 3000,
    fixture_watts: int = 30,
    light_loss_factor: float = 0.85,
    ctx: Context = None
) -> str:
    """
    Calculate required electric lighting using lumen method.

    Args:
        floor_area_sqft: Room floor area in square feet
        space_type: Type of space - 'office_general', 'office_detailed', 'residential_living',
                   'residential_kitchen', 'residential_bedroom', 'classroom', 'retail',
                   'warehouse', 'corridor'
        ceiling_height_ft: Ceiling height in feet (default 9)
        fixture_lumens: Lumens per fixture (default 3000)
        fixture_watts: Watts per fixture (default 30)
        light_loss_factor: LLF for maintenance (typical 0.85)

    Returns:
        JSON with number of fixtures needed and lighting power density
    """
    from physics.lighting import LightingAnalyzer, SpaceType

    analyzer = LightingAnalyzer()

    # Map string to SpaceType enum
    space_type_map = {
        'office_general': SpaceType.OFFICE_GENERAL,
        'office_detailed': SpaceType.OFFICE_DETAILED,
        'residential_living': SpaceType.RESIDENTIAL_LIVING,
        'residential_kitchen': SpaceType.RESIDENTIAL_KITCHEN,
        'residential_bedroom': SpaceType.RESIDENTIAL_BEDROOM,
        'classroom': SpaceType.CLASSROOM,
        'retail': SpaceType.RETAIL,
        'warehouse': SpaceType.WAREHOUSE,
        'corridor': SpaceType.CORRIDOR,
    }
    space = space_type_map.get(space_type.lower(), SpaceType.OFFICE_GENERAL)

    result = analyzer.calculate_electric_lighting(
        floor_area_sqft=floor_area_sqft,
        space_type=space,
        ceiling_height_ft=ceiling_height_ft,
        fixture_lumens=fixture_lumens,
        fixture_watts=fixture_watts,
        light_loss_factor=light_loss_factor
    )

    return format_response({
        "status": "success",
        "analysis": "electric_lighting",
        "input": {
            "floor_area_sqft": floor_area_sqft,
            "space_type": space_type,
            "fixture_lumens": fixture_lumens,
            "fixture_watts": fixture_watts
        },
        "result": {
            "recommended_fixtures": result.recommended_fixtures,
            "required_lumens": round(result.required_lumens, 0),
            "watts_per_sqft": round(result.watts_per_sqft, 2),
            "meets_target": result.meets_target,
            "recommendations": result.recommendations
        }
    })


# =========================================================
# ACOUSTIC ANALYSIS TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def analyze_wall_stc(
    assembly_name: str,
    ctx: Context = None
) -> str:
    """
    Get STC (Sound Transmission Class) rating for a wall assembly.

    Args:
        assembly_name: Wall assembly preset name

    Returns:
        JSON with STC rating and noise reduction performance
    """
    analyzer = AcousticAnalyzer()
    presets = get_all_assembly_presets()

    if assembly_name not in presets:
        return format_response({
            "status": "error",
            "message": f"Unknown assembly: {assembly_name}",
            "available_presets": [k for k in presets.keys() if 'wall' in k.lower()]
        })

    assembly = presets[assembly_name]

    # Estimate STC based on assembly mass and layers
    total_mass = sum(
        layer.material.density_pcf * layer.thickness_in / 12
        for layer in assembly.layers
    )

    # Simplified STC estimation (mass law + construction bonus)
    base_stc = 20 * (1 + total_mass / 5)  # Mass law approximation

    # Add bonus for multiple layers, air gaps, resilient channels
    layer_count = len(assembly.layers)
    if layer_count > 4:
        base_stc += 5
    if any('insul' in l.material.name.lower() for l in assembly.layers):
        base_stc += 3

    stc = min(int(base_stc), 65)  # Cap at STC 65

    # Determine rating
    if stc >= 55:
        rating = "Excellent - Loud sounds barely audible"
    elif stc >= 50:
        rating = "Very Good - Loud speech not intelligible"
    elif stc >= 45:
        rating = "Good - Loud speech audible but not intelligible"
    elif stc >= 40:
        rating = "Fair - Normal speech audible"
    else:
        rating = "Poor - Normal speech easily understood"

    return format_response({
        "status": "success",
        "analysis": "acoustic_stc",
        "result": {
            "assembly": assembly.name,
            "estimated_stc": stc,
            "rating": rating,
            "surface_mass_psf": round(total_mass, 2),
            "recommendations": [
                "Add mass (extra drywall layer) for +3-5 STC",
                "Use resilient channels for +5-8 STC",
                "Add insulation in cavity for +3-5 STC",
                "Seal all penetrations and edges"
            ] if stc < 50 else ["Assembly meets typical residential requirements"]
        }
    })


@mcp.tool()
@register_tool
async def calculate_reverberation_time(
    room_volume_cuft: float,
    surface_areas: Dict[str, float],
    occupancy_type: str = "office_private",
    num_occupants: int = 0,
    ctx: Context = None
) -> str:
    """
    Calculate room reverberation time (RT60) using Sabine equation.

    Args:
        room_volume_cuft: Room volume in cubic feet
        surface_areas: Dict of surface type to area in SF
            Valid types: 'drywall', 'concrete', 'carpet', 'acoustic_ceiling', 'glass', 'heavy_curtain'
            Example: {"drywall": 500, "carpet": 200, "acoustic_ceiling": 200}
        occupancy_type: Space type - 'residential_bedroom', 'residential_living', 'office_private',
                       'office_open', 'classroom', 'music_rehearsal', 'auditorium', 'restaurant'
        num_occupants: Number of people in the room (adds absorption)

    Returns:
        JSON with RT60 and acoustic quality assessment
    """
    from physics.acoustic import AcousticAnalyzer, SurfaceMaterial, OccupancyType

    analyzer = AcousticAnalyzer()

    # Map surface type strings to SurfaceMaterial objects
    material_map = {
        'drywall': SurfaceMaterial.drywall(),
        'gypsum': SurfaceMaterial.drywall(),
        'gypsum_wall': SurfaceMaterial.drywall(),
        'concrete': SurfaceMaterial.concrete(),
        'carpet': SurfaceMaterial.carpet(),
        'acoustic_ceiling': SurfaceMaterial.acoustic_ceiling(),
        'ceiling': SurfaceMaterial.acoustic_ceiling(),
        'glass': SurfaceMaterial.glass(),
        'window': SurfaceMaterial.glass(),
        'heavy_curtain': SurfaceMaterial.heavy_curtain(),
        'curtain': SurfaceMaterial.heavy_curtain(),
    }

    # Build surfaces list
    surfaces = []
    for surface_type, area in surface_areas.items():
        material = material_map.get(surface_type.lower(), SurfaceMaterial.drywall())
        surfaces.append({"material": material, "area_sqft": area})

    # Map occupancy type string to enum
    occupancy_map = {
        'residential_bedroom': OccupancyType.RESIDENTIAL_BEDROOM,
        'residential_living': OccupancyType.RESIDENTIAL_LIVING,
        'office_private': OccupancyType.OFFICE_PRIVATE,
        'office_open': OccupancyType.OFFICE_OPEN,
        'office': OccupancyType.OFFICE_PRIVATE,
        'classroom': OccupancyType.CLASSROOM,
        'music_rehearsal': OccupancyType.MUSIC_REHEARSAL,
        'auditorium': OccupancyType.AUDITORIUM,
        'restaurant': OccupancyType.RESTAURANT,
    }
    occupancy = occupancy_map.get(occupancy_type.lower(), OccupancyType.OFFICE_PRIVATE)

    result = analyzer.calculate_reverberation_time(
        volume_cuft=room_volume_cuft,
        surfaces=surfaces,
        occupancy_type=occupancy,
        num_occupants=num_occupants
    )

    return format_response({
        "status": "success",
        "analysis": "reverberation",
        "input": {
            "room_volume_cuft": room_volume_cuft,
            "surfaces": surface_areas,
            "occupancy_type": occupancy_type,
            "num_occupants": num_occupants
        },
        "result": {
            "rt60_seconds": round(result.rt60_seconds, 2),
            "target_range": list(result.target_range),
            "within_target": result.within_target,
            "rt60_by_frequency": {str(k): round(v, 2) for k, v in result.rt60_by_frequency.items()},
            "recommendations": result.recommendations
        }
    })


# =========================================================
# ASSEMBLY & DETAIL TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def list_assembly_presets(ctx: Context = None) -> str:
    """
    List all available wall, floor, and roof assembly presets.

    Returns:
        JSON with categorized list of assembly presets and their R-values
    """
    walls = {}
    floors = {}
    roofs = {}

    # Get all preset method names from LayeredAssembly
    preset_methods = [m for m in dir(LayeredAssembly)
                      if not m.startswith('_') and
                      (m.startswith('wall') or m.startswith('floor') or m.startswith('roof'))]

    for method_name in preset_methods:
        try:
            assembly = getattr(LayeredAssembly, method_name)()
            info = {
                "r_value": round(assembly.total_r_value, 1),
                "thickness_in": round(assembly.total_thickness_in, 2),
                "layers": len(assembly.layers)
            }

            if method_name.startswith('wall'):
                walls[method_name] = info
            elif method_name.startswith('floor'):
                floors[method_name] = info
            elif method_name.startswith('roof'):
                roofs[method_name] = info
        except Exception:
            pass

    return format_response({
        "status": "success",
        "presets": {
            "walls": walls,
            "floors": floors,
            "roofs": roofs
        }
    })


def _get_assembly_by_name(name: str):
    """Helper to get assembly by preset name."""
    if hasattr(LayeredAssembly, name):
        return getattr(LayeredAssembly, name)()
    return None

def _get_all_preset_names():
    """Helper to get all preset names."""
    return [m for m in dir(LayeredAssembly)
            if not m.startswith('_') and
            (m.startswith('wall') or m.startswith('floor') or m.startswith('roof'))]


@mcp.tool()
@register_tool
async def get_assembly_details(
    assembly_name: str,
    ctx: Context = None
) -> str:
    """
    Get detailed layer-by-layer breakdown of an assembly.

    Args:
        assembly_name: Name of assembly preset

    Returns:
        JSON with complete layer details including materials and R-values
    """
    assembly = _get_assembly_by_name(assembly_name)

    if assembly is None:
        return format_response({
            "status": "error",
            "message": f"Unknown assembly: {assembly_name}",
            "available_presets": _get_all_preset_names()
        })

    layers = []
    for layer in assembly.layers:
        layers.append({
            "material": layer.material.name,
            "category": layer.material.category.value,
            "thickness_in": round(layer.thickness_in, 3),
            "r_value": round(layer.r_value, 2),
            "is_framing_layer": layer.is_framing_layer,
        })

    return format_response({
        "status": "success",
        "assembly": {
            "name": assembly.name,
            "type": assembly.assembly_type,
            "total_r_value": round(assembly.total_r_value, 1),
            "u_factor": round(assembly.u_factor, 4),
            "total_thickness_in": round(assembly.total_thickness_in, 2),
            "layers": layers
        }
    })


@mcp.tool()
@register_tool
async def estimate_fasteners(
    assembly_type: str,
    length_ft: float,
    width_ft: float = 0.0,
    height_ft: float = 9.0,
    ctx: Context = None
) -> str:
    """
    Estimate fastener counts for construction material takeoff.

    Args:
        assembly_type: 'wall', 'floor', or 'roof'
        length_ft: Length of assembly in feet (wall length, floor/roof length)
        width_ft: Width in feet (for floor/roof, ignored for walls)
        height_ft: Height in feet (for walls, default 9ft)

    Returns:
        JSON with fastener schedule and quantities
    """
    import math
    estimator = FastenerEstimator()

    if assembly_type == "wall":
        schedule = estimator.estimate_wall_fasteners(
            wall_length_ft=length_ft,
            wall_height_ft=height_ft,
            stud_spacing_in=16
        )
        area_sf = length_ft * height_ft
    elif assembly_type == "floor":
        schedule = estimator.estimate_floor_fasteners(
            floor_length_ft=length_ft,
            floor_width_ft=width_ft,
            joist_spacing_in=16
        )
        area_sf = length_ft * width_ft
    elif assembly_type == "roof":
        schedule = estimator.estimate_roof_fasteners(
            roof_length_ft=length_ft,
            roof_width_ft=width_ft,
            rafter_spacing_in=24
        )
        area_sf = length_ft * width_ft
    else:
        return format_response({
            "status": "error",
            "message": f"Unknown assembly type: {assembly_type}",
            "valid_types": ["wall", "floor", "roof"]
        })

    # Build fastener summary
    fasteners = {}
    if schedule.framing_nails:
        for nail_type, qty in schedule.framing_nails.items():
            fasteners[f"framing_{nail_type}"] = qty
    if schedule.sheathing_nails:
        for nail_type, qty in schedule.sheathing_nails.items():
            fasteners[f"sheathing_{nail_type}"] = qty
    if schedule.drywall_screws > 0:
        fasteners["drywall_screws"] = schedule.drywall_screws
    if schedule.siding_fasteners > 0:
        fasteners["siding_fasteners"] = schedule.siding_fasteners
    if schedule.roofing_fasteners > 0:
        fasteners["roofing_fasteners"] = schedule.roofing_fasteners
    if schedule.subfloor_fasteners > 0:
        fasteners["subfloor_fasteners"] = schedule.subfloor_fasteners

    # Build connector summary
    connectors = {}
    for connector, qty in schedule.connectors:
        connectors[connector.type.value] = {
            "quantity": qty,
            "model": connector.model
        }

    return format_response({
        "status": "success",
        "fastener_schedule": {
            "assembly_type": assembly_type,
            "dimensions_ft": f"{length_ft} x {width_ft if assembly_type != 'wall' else height_ft}",
            "area_sf": area_sf,
            "fasteners": fasteners,
            "connectors": connectors,
            "estimated_cost": round(schedule.total_fastener_cost(), 2)
        }
    })


# =========================================================
# IFC IMPORT TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def check_ifc_support(ctx: Context = None) -> str:
    """
    Check if IFC import functionality is available.

    Returns:
        JSON with IFC support status
    """
    return format_response({
        "status": "success",
        "ifc_import_available": IFC_IMPORT_AVAILABLE,
        "message": "ifcopenshell is installed" if IFC_IMPORT_AVAILABLE
                   else "Install ifcopenshell for IFC support: pip install ifcopenshell"
    })


if IFC_IMPORT_AVAILABLE:
    @mcp.tool()
    @register_tool
    async def import_ifc_assemblies_tool(
        ifc_path: str,
        ctx: Context = None
    ) -> str:
        """
        Import wall, floor, and roof assemblies from an IFC file.

        Args:
            ifc_path: Path to IFC file

        Returns:
            JSON with imported assemblies and their layer information
        """
        try:
            importer = IFCImporter(ifc_path)
            summary = importer.get_layer_summary()

            return format_response({
                "status": "success",
                "import": summary
            })
        except Exception as e:
            return format_response({
                "status": "error",
                "message": str(e)
            })


# =========================================================
# MATERIAL REFERENCE TOOLS
# =========================================================

@mcp.tool()
@register_tool
async def list_materials(
    category: Optional[str] = None,
    ctx: Context = None
) -> str:
    """
    List available material presets.

    Args:
        category: Optional filter - 'wood', 'insulation', 'concrete', 'gypsum', etc.

    Returns:
        JSON with material presets and their thermal properties
    """
    # Get all material preset methods
    material_methods = [m for m in dir(Material) if not m.startswith('_') and callable(getattr(Material, m))]

    materials = {}
    for method_name in material_methods:
        try:
            mat = getattr(Material, method_name)()
            if category is None or category.lower() in mat.category.value.lower():
                materials[method_name] = {
                    "name": mat.name,
                    "category": mat.category.value,
                    "r_value_per_inch": mat.r_value_per_inch,
                    "density_pcf": mat.density_pcf
                }
        except:
            pass

    return format_response({
        "status": "success",
        "materials": materials
    })
