#!/usr/bin/env python3
"""
generate_details.py - Generate architectural detail drawings

Creates typical construction details showing:
- Wall section (foundation to roof)
- Eave/fascia detail
- Window head, jamb, and sill details
- Door head, jamb, and threshold details
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from title_block import generate_title_block, get_project_info_from_json, get_drawing_info

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Layer:
    """A material layer in a wall or roof assembly."""
    name: str
    thickness: float  # mm
    material: str     # wood, insulation, gypsum, concrete, etc.

@dataclass
class Detail:
    """A single detail drawing."""
    name: str
    number: str
    scale: str
    width: float   # mm in model space
    height: float  # mm in model space
    svg_content: str

# =============================================================================
# MATERIAL PATTERNS
# =============================================================================

HATCH_PATTERNS = '''
    <!-- Wood (diagonal lines) -->
    <pattern id="hatch-wood" patternUnits="userSpaceOnUse" width="6" height="6">
      <path d="M0,6 L6,0 M-1,1 L1,-1 M5,7 L7,5" stroke="#8B4513" stroke-width="0.5" fill="none"/>
    </pattern>
    <!-- Insulation (wavy lines) -->
    <pattern id="hatch-insulation" patternUnits="userSpaceOnUse" width="10" height="5">
      <path d="M0,2.5 Q2.5,0 5,2.5 Q7.5,5 10,2.5" stroke="#E8A0B0" stroke-width="0.8" fill="none"/>
    </pattern>
    <!-- Plywood/OSB (cross-hatch) -->
    <pattern id="hatch-plywood" patternUnits="userSpaceOnUse" width="5" height="5">
      <path d="M0,0 L5,5 M5,0 L0,5" stroke="#C4A86B" stroke-width="0.4" fill="none"/>
    </pattern>
    <!-- Gypsum/Drywall (dots) -->
    <pattern id="hatch-gypsum" patternUnits="userSpaceOnUse" width="4" height="4">
      <circle cx="2" cy="2" r="0.6" fill="#AAA"/>
    </pattern>
    <!-- Concrete (random dots) -->
    <pattern id="hatch-concrete" patternUnits="userSpaceOnUse" width="8" height="8">
      <circle cx="1.5" cy="1.5" r="0.8" fill="#777"/>
      <circle cx="5.5" cy="4" r="1.1" fill="#777"/>
      <circle cx="3" cy="6.5" r="0.7" fill="#777"/>
      <circle cx="6.5" cy="7" r="0.5" fill="#777"/>
    </pattern>
    <!-- Earth/Gravel (stipple) -->
    <pattern id="hatch-earth" patternUnits="userSpaceOnUse" width="10" height="10">
      <circle cx="2" cy="3" r="1.2" fill="#A08060"/>
      <circle cx="7" cy="2" r="0.8" fill="#907050"/>
      <circle cx="5" cy="6" r="1.0" fill="#A08060"/>
      <circle cx="8" cy="8" r="0.7" fill="#907050"/>
      <circle cx="1" cy="8" r="0.9" fill="#A08060"/>
    </pattern>
    <!-- Rigid insulation (horizontal lines) -->
    <pattern id="hatch-rigid" patternUnits="userSpaceOnUse" width="4" height="4">
      <line x1="0" y1="2" x2="4" y2="2" stroke="#7AC5E8" stroke-width="0.5"/>
    </pattern>
    <!-- Metal (solid gray) -->
    <pattern id="hatch-metal" patternUnits="userSpaceOnUse" width="4" height="4">
      <rect width="4" height="4" fill="#B0B0B0"/>
    </pattern>
    <!-- Air gap (empty) -->
    <pattern id="hatch-air" patternUnits="userSpaceOnUse" width="4" height="4">
      <rect width="4" height="4" fill="#FAFAFA"/>
    </pattern>
    <!-- Siding (horizontal lines) -->
    <pattern id="hatch-siding" patternUnits="userSpaceOnUse" width="20" height="8">
      <line x1="0" y1="7" x2="20" y2="7" stroke="#666" stroke-width="0.5"/>
      <rect width="20" height="8" fill="#E8E0D8"/>
    </pattern>
    <!-- Brick -->
    <pattern id="hatch-brick" patternUnits="userSpaceOnUse" width="16" height="8">
      <rect width="16" height="8" fill="#C4755C"/>
      <line x1="0" y1="4" x2="16" y2="4" stroke="#8B4513" stroke-width="0.5"/>
      <line x1="8" y1="0" x2="8" y2="4" stroke="#8B4513" stroke-width="0.5"/>
      <line x1="0" y1="8" x2="0" y2="4" stroke="#8B4513" stroke-width="0.5"/>
      <line x1="16" y1="8" x2="16" y2="4" stroke="#8B4513" stroke-width="0.5"/>
    </pattern>
    <!-- Roofing/Shingles -->
    <pattern id="hatch-roofing" patternUnits="userSpaceOnUse" width="12" height="6">
      <rect width="12" height="6" fill="#505050"/>
      <line x1="0" y1="5" x2="12" y2="5" stroke="#333" stroke-width="0.5"/>
      <line x1="6" y1="0" x2="6" y2="5" stroke="#333" stroke-width="0.3"/>
    </pattern>
'''

MATERIAL_TO_PATTERN = {
    'wood': 'hatch-wood',
    'framing': 'hatch-wood',
    'stud': 'hatch-wood',
    'insulation': 'hatch-insulation',
    'batt': 'hatch-insulation',
    'plywood': 'hatch-plywood',
    'osb': 'hatch-plywood',
    'sheathing': 'hatch-plywood',
    'gypsum': 'hatch-gypsum',
    'drywall': 'hatch-gypsum',
    'concrete': 'hatch-concrete',
    'foundation': 'hatch-concrete',
    'earth': 'hatch-earth',
    'gravel': 'hatch-earth',
    'rigid': 'hatch-rigid',
    'foam': 'hatch-rigid',
    'metal': 'hatch-metal',
    'flashing': 'hatch-metal',
    'air': 'hatch-air',
    'cavity': 'hatch-air',
    'siding': 'hatch-siding',
    'brick': 'hatch-brick',
    'roofing': 'hatch-roofing',
    'shingles': 'hatch-roofing',
}

def get_pattern(material: str) -> str:
    """Get SVG pattern ID for a material."""
    return MATERIAL_TO_PATTERN.get(material.lower(), 'hatch-wood')

# =============================================================================
# DETAIL GENERATORS
# =============================================================================

def generate_wall_section_detail(wall_types: List[dict], wall_height: float = 2700) -> Detail:
    """
    Generate a typical wall section detail from foundation to eave.
    Shows all layers with dimensions and labels.
    """

    # Default exterior wall assembly if none provided
    if not wall_types:
        layers = [
            Layer("Lap Siding", 20, "siding"),
            Layer("Air Gap", 20, "air"),
            Layer("House Wrap", 1, "air"),
            Layer("OSB Sheathing", 12, "plywood"),
            Layer("2x6 Stud w/ Batt", 140, "insulation"),
            Layer("Vapor Barrier", 1, "air"),
            Layer("5/8\" Gypsum", 16, "gypsum"),
        ]
    else:
        # Use first exterior wall type
        ext_wall = None
        for wt in wall_types:
            if wt.get('category') == 'exterior':
                ext_wall = wt
                break
        if ext_wall and ext_wall.get('layers'):
            layers = [Layer(l['name'], l.get('thickness', 20),
                          l.get('material', 'wood')) for l in ext_wall['layers']]
        else:
            layers = [
                Layer("Lap Siding", 20, "siding"),
                Layer("OSB Sheathing", 12, "plywood"),
                Layer("2x6 Stud w/ Batt", 140, "insulation"),
                Layer("5/8\" Gypsum", 16, "gypsum"),
            ]

    # Calculate total wall thickness
    total_thickness = sum(l.thickness for l in layers)

    # Detail dimensions (mm in model space)
    detail_width = 600
    detail_height = 1200

    # Scale for detail (larger scale for details)
    scale = "1:10"

    # Start building SVG content
    svg_lines = []

    # Foundation
    foundation_height = 300
    foundation_width = total_thickness + 150  # Wider than wall
    footing_width = foundation_width + 200
    footing_height = 200

    # Positions
    wall_left = (detail_width - total_thickness) / 2
    foundation_left = wall_left - 75
    footing_left = foundation_left - 100

    floor_y = detail_height - 400  # Floor level
    foundation_top = floor_y + 50  # Foundation goes below floor
    footing_top = foundation_top + foundation_height

    # Draw footing
    svg_lines.append(f'  <rect x="{footing_left}" y="{footing_top}" width="{footing_width}" height="{footing_height}" fill="url(#hatch-concrete)" stroke="#000" stroke-width="1.5"/>')

    # Draw foundation wall
    svg_lines.append(f'  <rect x="{foundation_left}" y="{foundation_top}" width="{foundation_width}" height="{foundation_height}" fill="url(#hatch-concrete)" stroke="#000" stroke-width="1.5"/>')

    # Draw earth on sides
    svg_lines.append(f'  <rect x="0" y="{floor_y + 100}" width="{foundation_left - 20}" height="{footing_top + footing_height - floor_y - 100}" fill="url(#hatch-earth)" stroke="none"/>')
    svg_lines.append(f'  <rect x="{foundation_left + foundation_width + 20}" y="{floor_y + 100}" width="{detail_width - foundation_left - foundation_width - 20}" height="{footing_top + footing_height - floor_y - 100}" fill="url(#hatch-earth)" stroke="none"/>')

    # Draw floor slab
    slab_thickness = 100
    svg_lines.append(f'  <rect x="{foundation_left}" y="{floor_y}" width="{foundation_width}" height="{slab_thickness}" fill="url(#hatch-concrete)" stroke="#000" stroke-width="1"/>')

    # Draw wall layers
    wall_bottom = floor_y
    wall_top = 150
    current_x = wall_left

    for layer in layers:
        pattern = get_pattern(layer.material)
        svg_lines.append(f'  <rect x="{current_x}" y="{wall_top}" width="{layer.thickness}" height="{wall_bottom - wall_top}" fill="url(#{pattern})" stroke="#000" stroke-width="0.5"/>')
        current_x += layer.thickness

    # Wall outline
    svg_lines.append(f'  <rect x="{wall_left}" y="{wall_top}" width="{total_thickness}" height="{wall_bottom - wall_top}" fill="none" stroke="#000" stroke-width="1.5"/>')

    # Top plate (double)
    plate_height = 40
    svg_lines.append(f'  <rect x="{wall_left + 20}" y="{wall_top}" width="{total_thickness - 40}" height="{plate_height}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <rect x="{wall_left + 20}" y="{wall_top + plate_height}" width="{total_thickness - 40}" height="{plate_height}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Roof/ceiling indication at top
    rafter_height = 50
    svg_lines.append(f'  <rect x="{wall_left - 50}" y="{wall_top - rafter_height}" width="{total_thickness + 150}" height="{rafter_height}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Ceiling
    svg_lines.append(f'  <rect x="{wall_left + total_thickness - 16}" y="{wall_top + plate_height * 2}" width="{16}" height="{100}" fill="url(#hatch-gypsum)" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <line x1="{wall_left + total_thickness - 16}" y1="{wall_top + plate_height * 2 + 100}" x2="{detail_width}" y2="{wall_top + plate_height * 2 + 100}" stroke="#000" stroke-width="0.5" stroke-dasharray="5,3"/>')

    # Dimension lines
    dim_offset = 50

    # Wall thickness dimension
    svg_lines.append(f'  <line x1="{wall_left}" y1="{wall_bottom + dim_offset}" x2="{wall_left + total_thickness}" y2="{wall_bottom + dim_offset}" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <line x1="{wall_left}" y1="{wall_bottom + dim_offset - 10}" x2="{wall_left}" y2="{wall_bottom + dim_offset + 10}" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <line x1="{wall_left + total_thickness}" y1="{wall_bottom + dim_offset - 10}" x2="{wall_left + total_thickness}" y2="{wall_bottom + dim_offset + 10}" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <text x="{wall_left + total_thickness/2}" y="{wall_bottom + dim_offset + 25}" font-family="Arial" font-size="12" text-anchor="middle">{total_thickness:.0f}mm</text>')

    # Layer labels (on right side)
    label_x = wall_left + total_thickness + 20
    current_y = wall_top + 50
    layer_spacing = (wall_bottom - wall_top - 100) / len(layers)

    for i, layer in enumerate(layers):
        y_pos = wall_top + 50 + i * layer_spacing
        svg_lines.append(f'  <line x1="{wall_left + total_thickness}" y1="{y_pos}" x2="{label_x + 10}" y2="{y_pos}" stroke="#666" stroke-width="0.5"/>')
        svg_lines.append(f'  <text x="{label_x + 15}" y="{y_pos + 4}" font-family="Arial" font-size="9" fill="#333">{layer.name}</text>')

    # Foundation label
    svg_lines.append(f'  <text x="{footing_left + footing_width/2}" y="{footing_top + footing_height + 20}" font-family="Arial" font-size="10" text-anchor="middle">CONTINUOUS FOOTING</text>')

    return Detail(
        name="TYPICAL WALL SECTION",
        number="1",
        scale=scale,
        width=detail_width,
        height=detail_height,
        svg_content='\n'.join(svg_lines)
    )


def generate_eave_detail() -> Detail:
    """Generate a typical eave/fascia detail."""

    detail_width = 400
    detail_height = 350

    svg_lines = []

    # Roof pitch (4:12)
    pitch = 4/12

    # Starting point for roof
    roof_start_x = 50
    roof_start_y = 200

    # Rafter
    rafter_length = 300
    rafter_depth = 38  # 2x8 actual
    roof_end_x = roof_start_x + rafter_length
    roof_end_y = roof_start_y - rafter_length * pitch

    # Draw rafter
    svg_lines.append(f'  <polygon points="{roof_start_x},{roof_start_y} {roof_end_x},{roof_end_y} {roof_end_x},{roof_end_y + rafter_depth} {roof_start_x},{roof_start_y + rafter_depth}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Roof sheathing
    sheathing_thickness = 12
    svg_lines.append(f'  <polygon points="{roof_start_x},{roof_start_y - sheathing_thickness} {roof_end_x},{roof_end_y - sheathing_thickness} {roof_end_x},{roof_end_y} {roof_start_x},{roof_start_y}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="0.5"/>')

    # Roofing
    roofing_thickness = 8
    svg_lines.append(f'  <polygon points="{roof_start_x},{roof_start_y - sheathing_thickness - roofing_thickness} {roof_end_x},{roof_end_y - sheathing_thickness - roofing_thickness} {roof_end_x},{roof_end_y - sheathing_thickness} {roof_start_x},{roof_start_y - sheathing_thickness}" fill="url(#hatch-roofing)" stroke="#000" stroke-width="0.5"/>')

    # Drip edge
    svg_lines.append(f'  <path d="M {roof_start_x},{roof_start_y - sheathing_thickness - roofing_thickness} L {roof_start_x - 10},{roof_start_y - sheathing_thickness - roofing_thickness} L {roof_start_x - 10},{roof_start_y + 20}" fill="none" stroke="#000" stroke-width="1.5"/>')

    # Fascia board
    fascia_width = 25
    fascia_height = 150
    svg_lines.append(f'  <rect x="{roof_start_x - fascia_width}" y="{roof_start_y}" width="{fascia_width}" height="{fascia_height}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Soffit
    soffit_y = roof_start_y + fascia_height - 15
    svg_lines.append(f'  <rect x="{roof_start_x - fascia_width}" y="{soffit_y}" width="{120}" height="{12}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="0.5"/>')

    # Wall top
    wall_x = roof_start_x + 80
    wall_top_y = soffit_y + 12
    svg_lines.append(f'  <rect x="{wall_x}" y="{wall_top_y}" width="{150}" height="{detail_height - wall_top_y - 20}" fill="url(#hatch-insulation)" stroke="#000" stroke-width="1"/>')

    # Top plate
    svg_lines.append(f'  <rect x="{wall_x}" y="{wall_top_y}" width="{100}" height="{38}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <rect x="{wall_x}" y="{wall_top_y + 38}" width="{100}" height="{38}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Exterior sheathing on wall
    svg_lines.append(f'  <rect x="{wall_x - 12}" y="{wall_top_y + 76}" width="{12}" height="{detail_height - wall_top_y - 96}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="0.5"/>')

    # Labels
    svg_lines.append(f'  <text x="{roof_end_x - 50}" y="{roof_end_y - 30}" font-family="Arial" font-size="9" fill="#333">ASPHALT SHINGLES</text>')
    svg_lines.append(f'  <text x="{roof_start_x + 100}" y="{roof_start_y + 25}" font-family="Arial" font-size="9" fill="#333">2x8 RAFTER</text>')
    svg_lines.append(f'  <text x="{roof_start_x - fascia_width - 5}" y="{roof_start_y + 80}" font-family="Arial" font-size="9" fill="#333" text-anchor="end">1x8 FASCIA</text>')
    svg_lines.append(f'  <text x="{roof_start_x + 30}" y="{soffit_y + 30}" font-family="Arial" font-size="9" fill="#333">SOFFIT</text>')

    return Detail(
        name="EAVE DETAIL",
        number="2",
        scale="1:5",
        width=detail_width,
        height=detail_height,
        svg_content='\n'.join(svg_lines)
    )


def generate_window_detail() -> Detail:
    """Generate window head, jamb, and sill details."""

    detail_width = 500
    detail_height = 400

    svg_lines = []

    # Three sub-details: HEAD, JAMB, SILL
    section_width = 140
    section_height = 120
    spacing = 30

    # HEAD detail (top of window)
    head_x = 30
    head_y = 50

    svg_lines.append(f'  <text x="{head_x + section_width/2}" y="{head_y - 10}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">HEAD</text>')

    # Header
    svg_lines.append(f'  <rect x="{head_x}" y="{head_y}" width="{section_width}" height="{40}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y + 25}" font-family="Arial" font-size="8">2x10 HEADER</text>')

    # Sheathing
    svg_lines.append(f'  <rect x="{head_x}" y="{head_y + 40}" width="{12}" height="{section_height - 40}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="0.5"/>')

    # Window frame
    svg_lines.append(f'  <rect x="{head_x + 15}" y="{head_y + 45}" width="{section_width - 30}" height="{25}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y + 60}" font-family="Arial" font-size="8">WINDOW FRAME</text>')

    # Glass
    svg_lines.append(f'  <rect x="{head_x + 25}" y="{head_y + 70}" width="{section_width - 50}" height="{section_height - 75}" fill="#E8F4FC" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <line x1="{head_x + 25}" y1="{head_y + 70 + (section_height - 75)/2}" x2="{head_x + section_width - 25}" y2="{head_y + 70 + (section_height - 75)/2}" stroke="#666" stroke-width="0.5"/>')

    # Interior trim
    svg_lines.append(f'  <rect x="{head_x + section_width - 20}" y="{head_y + 40}" width="{20}" height="{section_height - 40}" fill="url(#hatch-wood)" stroke="#000" stroke-width="0.5"/>')

    # JAMB detail (side of window)
    jamb_x = head_x + section_width + spacing + 40
    jamb_y = head_y

    svg_lines.append(f'  <text x="{jamb_x + section_width/2}" y="{jamb_y - 10}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">JAMB</text>')

    # Stud
    svg_lines.append(f'  <rect x="{jamb_x}" y="{jamb_y}" width="{38}" height="{section_height}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{jamb_x + 19}" y="{jamb_y + section_height + 15}" font-family="Arial" font-size="8" text-anchor="middle">KING STUD</text>')

    # Jack stud
    svg_lines.append(f'  <rect x="{jamb_x + 40}" y="{jamb_y + 20}" width="{38}" height="{section_height - 20}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{jamb_x + 59}" y="{jamb_y + section_height + 15}" font-family="Arial" font-size="8" text-anchor="middle">JACK</text>')

    # Window frame
    svg_lines.append(f'  <rect x="{jamb_x + 80}" y="{jamb_y + 25}" width="{25}" height="{section_height - 30}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Glass
    svg_lines.append(f'  <rect x="{jamb_x + 107}" y="{jamb_y + 30}" width="{section_width - 112}" height="{section_height - 40}" fill="#E8F4FC" stroke="#000" stroke-width="1"/>')

    # SILL detail (bottom of window)
    sill_x = jamb_x + section_width + spacing + 40
    sill_y = head_y

    svg_lines.append(f'  <text x="{sill_x + section_width/2}" y="{sill_y - 10}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">SILL</text>')

    # Wall below
    svg_lines.append(f'  <rect x="{sill_x}" y="{sill_y + 60}" width="{section_width}" height="{section_height - 60}" fill="url(#hatch-insulation)" stroke="#000" stroke-width="1"/>')

    # Sheathing
    svg_lines.append(f'  <rect x="{sill_x}" y="{sill_y + 60}" width="{12}" height="{section_height - 60}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="0.5"/>')

    # Sill plate
    svg_lines.append(f'  <polygon points="{sill_x + 15},{sill_y + 55} {sill_x + section_width - 20},{sill_y + 55} {sill_x + section_width - 10},{sill_y + 65} {sill_x + 5},{sill_y + 65}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{sill_x + section_width + 5}" y="{sill_y + 62}" font-family="Arial" font-size="8">SLOPED SILL</text>')

    # Window frame
    svg_lines.append(f'  <rect x="{sill_x + 20}" y="{sill_y + 30}" width="{section_width - 40}" height="{25}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Glass
    svg_lines.append(f'  <rect x="{sill_x + 25}" y="{sill_y}" width="{section_width - 50}" height="{30}" fill="#E8F4FC" stroke="#000" stroke-width="1"/>')

    # Interior trim
    svg_lines.append(f'  <rect x="{sill_x + section_width - 20}" y="{sill_y + 55}" width="{20}" height="{section_height - 55}" fill="url(#hatch-wood)" stroke="#000" stroke-width="0.5"/>')

    # Interior sill
    svg_lines.append(f'  <rect x="{sill_x + section_width - 40}" y="{sill_y + 55}" width="{40}" height="{15}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{sill_x + section_width + 5}" y="{sill_y + 90}" font-family="Arial" font-size="8">STOOL</text>')

    return Detail(
        name="WINDOW DETAILS",
        number="3",
        scale="1:5",
        width=detail_width,
        height=detail_height,
        svg_content='\n'.join(svg_lines)
    )


def generate_door_detail() -> Detail:
    """Generate door head and threshold details."""

    detail_width = 400
    detail_height = 350

    svg_lines = []

    section_width = 160
    section_height = 140

    # HEAD detail
    head_x = 30
    head_y = 50

    svg_lines.append(f'  <text x="{head_x + section_width/2}" y="{head_y - 10}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">DOOR HEAD</text>')

    # Header (doubled 2x10)
    svg_lines.append(f'  <rect x="{head_x}" y="{head_y}" width="{section_width}" height="{38}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <rect x="{head_x}" y="{head_y + 38}" width="{section_width}" height="{38}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y + 45}" font-family="Arial" font-size="8">(2) 2x10 HEADER</text>')

    # Cripple
    svg_lines.append(f'  <rect x="{head_x + 60}" y="{head_y - 30}" width="{38}" height="{30}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y - 10}" font-family="Arial" font-size="8">CRIPPLE</text>')

    # Door frame
    svg_lines.append(f'  <rect x="{head_x + 20}" y="{head_y + 80}" width="{section_width - 40}" height="{30}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y + 100}" font-family="Arial" font-size="8">DOOR FRAME</text>')

    # Door
    svg_lines.append(f'  <rect x="{head_x + 30}" y="{head_y + 110}" width="{section_width - 60}" height="{section_height - 110}" fill="#F5F0E8" stroke="#000" stroke-width="1.5"/>')

    # Casing
    svg_lines.append(f'  <rect x="{head_x + section_width - 25}" y="{head_y + 76}" width="{25}" height="{section_height - 76}" fill="url(#hatch-wood)" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <text x="{head_x + section_width + 5}" y="{head_y + 130}" font-family="Arial" font-size="8">CASING</text>')

    # THRESHOLD detail
    thresh_x = head_x + section_width + 80
    thresh_y = head_y

    svg_lines.append(f'  <text x="{thresh_x + section_width/2}" y="{thresh_y - 10}" font-family="Arial" font-size="11" font-weight="bold" text-anchor="middle">THRESHOLD</text>')

    # Subfloor
    svg_lines.append(f'  <rect x="{thresh_x}" y="{thresh_y + 80}" width="{section_width}" height="{18}" fill="url(#hatch-plywood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{thresh_x - 5}" y="{thresh_y + 92}" font-family="Arial" font-size="8" text-anchor="end">SUBFLOOR</text>')

    # Floor joist indication
    svg_lines.append(f'  <rect x="{thresh_x + 20}" y="{thresh_y + 98}" width="{38}" height="{section_height - 98}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <rect x="{thresh_x + section_width - 58}" y="{thresh_y + 98}" width="{38}" height="{section_height - 98}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1"/>')

    # Threshold
    svg_lines.append(f'  <polygon points="{thresh_x + 40},{thresh_y + 65} {thresh_x + section_width - 40},{thresh_y + 65} {thresh_x + section_width - 35},{thresh_y + 80} {thresh_x + 35},{thresh_y + 80}" fill="url(#hatch-metal)" stroke="#000" stroke-width="1"/>')
    svg_lines.append(f'  <text x="{thresh_x + section_width + 5}" y="{thresh_y + 75}" font-family="Arial" font-size="8">THRESHOLD</text>')

    # Door
    svg_lines.append(f'  <rect x="{thresh_x + 50}" y="{thresh_y}" width="{section_width - 100}" height="{65}" fill="#F5F0E8" stroke="#000" stroke-width="1.5"/>')
    svg_lines.append(f'  <text x="{thresh_x + section_width/2}" y="{thresh_y + 35}" font-family="Arial" font-size="9" text-anchor="middle">DOOR</text>')

    # Weather stripping indication
    svg_lines.append(f'  <ellipse cx="{thresh_x + 48}" cy="{thresh_y + 67}" rx="3" ry="5" fill="#333" stroke="none"/>')
    svg_lines.append(f'  <text x="{thresh_x + section_width + 5}" y="{thresh_y + 55}" font-family="Arial" font-size="8">WEATHERSTRIP</text>')

    # Finish floor
    svg_lines.append(f'  <rect x="{thresh_x + section_width - 30}" y="{thresh_y + 70}" width="{30}" height="{10}" fill="url(#hatch-wood)" stroke="#000" stroke-width="0.5"/>')
    svg_lines.append(f'  <text x="{thresh_x + section_width + 5}" y="{thresh_y + 95}" font-family="Arial" font-size="8">FIN. FLOOR</text>')

    return Detail(
        name="DOOR DETAILS",
        number="4",
        scale="1:5",
        width=detail_width,
        height=detail_height,
        svg_content='\n'.join(svg_lines)
    )


# =============================================================================
# SVG RENDERER
# =============================================================================

def render_details_svg(details: List[Detail], project_info: Dict = None) -> str:
    """Render all details to a single SVG sheet."""

    # Sheet layout
    margin = 500  # mm
    sheet_width = 16000   # ~A1 width in mm at 1:1
    sheet_height = 12000  # ~A1 height

    # Calculate detail positions (2x2 grid)
    detail_positions = [
        (margin + 500, margin + 1500),      # Top left
        (sheet_width/2 + 500, margin + 1500),  # Top right
        (margin + 500, sheet_height/2 + 500),  # Bottom left
        (sheet_width/2 + 500, sheet_height/2 + 500),  # Bottom right
    ]

    # Scale details to fit
    detail_scale = 8  # Scale up from detail model space to sheet space

    lines = []
    lines.append(f'<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg"')
    lines.append(f'     width="1000" height="750"')
    lines.append(f'     viewBox="0 0 {sheet_width} {sheet_height}">')

    # Background
    lines.append(f'<rect width="100%" height="100%" fill="white"/>')

    # Patterns
    lines.append('<defs>')
    lines.append(HATCH_PATTERNS)
    lines.append('</defs>')

    # Styles
    lines.append('''<style>
    .detail-title { font-family: Arial, sans-serif; font-size: 200px; font-weight: bold; fill: #333; }
    .detail-scale { font-family: Arial, sans-serif; font-size: 120px; fill: #666; }
    .detail-number { font-family: Arial, sans-serif; font-size: 160px; font-weight: bold; fill: #333; }
</style>''')

    # Sheet title
    lines.append(f'<text x="{sheet_width/2}" y="{margin - 100}" text-anchor="middle" class="detail-title">CONSTRUCTION DETAILS</text>')

    # Render each detail
    for i, detail in enumerate(details):
        if i >= len(detail_positions):
            break

        x, y = detail_positions[i]

        # Detail border
        detail_w = detail.width * detail_scale
        detail_h = detail.height * detail_scale
        lines.append(f'<rect x="{x - 100}" y="{y - 100}" width="{detail_w + 200}" height="{detail_h + 400}" fill="none" stroke="#ccc" stroke-width="2"/>')

        # Detail title
        lines.append(f'<text x="{x + detail_w/2}" y="{y - 50}" text-anchor="middle" class="detail-number">{detail.number}</text>')
        lines.append(f'<text x="{x + detail_w/2}" y="{y + detail_h + 150}" text-anchor="middle" font-family="Arial" font-size="140" font-weight="bold">{detail.name}</text>')
        lines.append(f'<text x="{x + detail_w/2}" y="{y + detail_h + 280}" text-anchor="middle" class="detail-scale">SCALE: {detail.scale}</text>')

        # Detail content (scaled and translated)
        lines.append(f'<g transform="translate({x}, {y}) scale({detail_scale})">')
        lines.append(detail.svg_content)
        lines.append('</g>')

    # Title block
    if project_info:
        drawing_info = {
            'title': 'CONSTRUCTION DETAILS',
            'number': 'A-501',
            'scale': 'AS NOTED',
            'sheet': '1 OF 1',
            'revision': '-',
            'drawn_by': 'AE',
        }
        lines.append(generate_title_block(sheet_width - 2*margin, sheet_height - 2*margin,
                                          project_info, drawing_info, scale=1.0, margin=margin))

    lines.append('</svg>')

    return '\n'.join(lines)


# =============================================================================
# MAIN
# =============================================================================

def generate_details(input_path: str, output_dir: str):
    """Generate detail drawings from building JSON."""

    # Load building data
    with open(input_path, 'r') as f:
        data = json.load(f)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get project info
    project_info = get_project_info_from_json(data)

    # Get wall types from data
    wall_types = data.get('wall_types', [])

    # Generate details
    print("Generating construction details...")

    details = [
        generate_wall_section_detail(wall_types),
        generate_eave_detail(),
        generate_window_detail(),
        generate_door_detail(),
    ]

    # Render to SVG
    svg = render_details_svg(details, project_info)

    out_file = output_path / "details.svg"
    with open(out_file, 'w') as f:
        f.write(svg)

    print(f"  Wrote {out_file}")
    print(f"  - {len(details)} details generated")
    for d in details:
        print(f"    {d.number}. {d.name} ({d.scale})")


def main():
    parser = argparse.ArgumentParser(description='Generate construction detail drawings')
    parser.add_argument('input', nargs='?',
                        default='../../Shared/TestData/output/generated_building.json',
                        help='Input JSON file path')
    parser.add_argument('-o', '--output',
                        default='../../Shared/TestData/output',
                        help='Output directory for SVG files')

    args = parser.parse_args()

    generate_details(args.input, args.output)


if __name__ == '__main__':
    main()
