#!/usr/bin/env python3
"""
generate_sections.py - Generate 2D building section drawings from JSON

Creates section views cutting through the building showing:
- Wall construction with layers (cut walls shown with hatching)
- Floor and ceiling levels
- Roof structure and pitch
- Interior spaces and heights
- Doors and windows in section or elevation (depending on position)
"""

import json
import math
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum

from title_block import generate_title_block, get_project_info_from_json, get_drawing_info

# =============================================================================
# DATA STRUCTURES
# =============================================================================

class SectionDirection(Enum):
    LONGITUDINAL = "longitudinal"  # Looking east/west (cut along building length)
    TRANSVERSE = "transverse"      # Looking north/south (cut across building width)

@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class WallSection:
    """A wall shown in section (cut through)"""
    x: float            # Horizontal position in section
    bottom_y: float     # Bottom of wall
    top_y: float        # Top of wall
    thickness: float    # Wall thickness (shown in section)
    layers: List[dict]  # Layer information for hatching
    is_exterior: bool

@dataclass
class WallElevation:
    """A wall shown in elevation (behind cut plane)"""
    start_x: float
    end_x: float
    bottom_y: float
    top_y: float
    is_exterior: bool
    depth: float = 0      # Distance from cut plane (for layering)
    wall_index: int = -1  # Original wall index for finding doors/windows

@dataclass
class Opening:
    """Door or window in section view"""
    center_x: float
    width: float
    bottom_y: float
    top_y: float
    is_door: bool
    in_section: bool    # True if cut through, False if in elevation behind
    depth: float = 0    # Distance from cut plane (for layering in elevation)

@dataclass
class FloorLevel:
    """Floor or ceiling level"""
    y: float
    label: str
    start_x: float
    end_x: float

@dataclass
class RoofSection:
    """Roof shown in section"""
    points: List[Point2D]   # Outline of roof in section
    ridge_height: float
    is_cut: bool            # True if section cuts through roof

@dataclass
class RoomLabel:
    """Room label in section"""
    center_x: float
    center_y: float
    name: str

@dataclass
class Section:
    """Complete section data"""
    name: str
    direction: SectionDirection
    cut_position: float         # Where the cut is made
    walls_cut: List[WallSection]
    walls_beyond: List[WallElevation]
    openings: List[Opening]
    floor_levels: List[FloorLevel]
    roof: Optional[RoofSection]
    room_labels: List[RoomLabel]
    width: float
    height: float

# =============================================================================
# WALL TYPE LAYERS
# =============================================================================

DEFAULT_EXTERIOR_LAYERS = [
    {"name": "Siding", "thickness": 20, "function": "exterior_finish"},
    {"name": "Sheathing", "thickness": 12, "function": "sheathing"},
    {"name": "Stud Cavity", "thickness": 140, "function": "structure"},
    {"name": "Drywall", "thickness": 13, "function": "interior_finish"},
]

DEFAULT_INTERIOR_LAYERS = [
    {"name": "Drywall", "thickness": 13, "function": "interior_finish"},
    {"name": "Stud Cavity", "thickness": 89, "function": "structure"},
    {"name": "Drywall", "thickness": 13, "function": "interior_finish"},
]

def get_wall_layers(wall: dict, wall_types: List[dict]) -> List[dict]:
    """Get layer information for a wall."""
    wall_type_id = wall.get('wall_type', '')

    for wt in wall_types:
        if wt.get('id') == wall_type_id:
            return wt.get('layers', [])

    # Default layers based on category
    if wall.get('category') == 'exterior':
        return DEFAULT_EXTERIOR_LAYERS
    else:
        return DEFAULT_INTERIOR_LAYERS

# =============================================================================
# SECTION GENERATION
# =============================================================================

def generate_section(data: dict, direction: SectionDirection,
                     cut_position: float = None, name: str = "A") -> Section:
    """
    Generate a section through the building.

    direction: LONGITUDINAL cuts parallel to the long axis (view looking east or west)
               TRANSVERSE cuts across the width (view looking north or south)
    cut_position: Where to make the cut (in mm). If None, cuts through center.
    """

    building_width = data.get('width', 10000)
    building_depth = data.get('depth', 10000)

    if cut_position is None:
        if direction == SectionDirection.LONGITUDINAL:
            cut_position = building_depth / 2  # Cut through middle depth
        else:
            cut_position = building_width / 2  # Cut through middle width

    walls = data.get('walls_batch', [])
    doors = data.get('doors', [])
    windows = data.get('windows', [])
    roofs = data.get('roofs', [])
    wall_types = data.get('wall_types', [])
    rooms = data.get('rooms', {})

    # Add index to walls
    for i, wall in enumerate(walls):
        wall['_index'] = i

    walls_cut = []
    walls_beyond = []
    openings = []
    room_labels = []

    # Tolerance for determining if wall is at cut position
    cut_tolerance = 200  # mm

    for wall in walls:
        start = wall['start']
        end = wall['end']
        height = wall.get('height', 2700)
        wall_index = wall.get('_index', -1)

        dx = end[0] - start[0]
        dz = end[2] - start[2]

        is_exterior = wall.get('category') == 'exterior'
        layers = get_wall_layers(wall, wall_types)
        total_thickness = sum(l.get('thickness', 0) for l in layers) if layers else 150

        if direction == SectionDirection.LONGITUDINAL:
            # Cutting along Z axis, viewing toward increasing Z (north)
            # Walls running along X (dz ≈ 0) are seen face-on in elevation
            # Walls running along Z (dx ≈ 0) are seen edge-on (in section if at cut)

            wall_z = (start[2] + end[2]) / 2

            if abs(dz) < 100:  # Wall runs along X axis (horizontal in plan)
                if abs(wall_z - cut_position) < cut_tolerance:
                    # This wall is AT the cut - show in section
                    wall_x = (start[0] + end[0]) / 2
                    walls_cut.append(WallSection(
                        x=wall_x,
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        thickness=total_thickness,
                        layers=layers,
                        is_exterior=is_exterior
                    ))
                elif wall_z > cut_position:
                    # Wall is BEYOND the cut - show as face-on elevation
                    depth = wall_z - cut_position
                    walls_beyond.append(WallElevation(
                        start_x=min(start[0], end[0]),
                        end_x=max(start[0], end[0]),
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        is_exterior=is_exterior,
                        depth=depth,
                        wall_index=wall_index
                    ))
            else:  # Wall runs along Z axis (vertical in plan)
                # Show in elevation if any part is beyond the cut
                min_z = min(start[2], end[2])
                max_z = max(start[2], end[2])

                if max_z > cut_position:
                    # Show as edge-on line in elevation
                    wall_x = start[0]  # X position in section
                    depth = min_z - cut_position if min_z > cut_position else 0
                    walls_beyond.append(WallElevation(
                        start_x=wall_x - total_thickness/2,
                        end_x=wall_x + total_thickness/2,
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        is_exterior=is_exterior,
                        depth=depth,
                        wall_index=wall_index
                    ))
        else:
            # TRANSVERSE: Cutting along X axis, viewing toward increasing X (east)
            wall_x = (start[0] + end[0]) / 2

            if abs(dx) < 100:  # Wall runs along Z axis (vertical in plan)
                if abs(wall_x - cut_position) < cut_tolerance:
                    # This wall is AT the cut - show in section
                    wall_z = (start[2] + end[2]) / 2
                    walls_cut.append(WallSection(
                        x=wall_z,
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        thickness=total_thickness,
                        layers=layers,
                        is_exterior=is_exterior
                    ))
                elif wall_x > cut_position:
                    # Wall is BEYOND the cut - show as face-on elevation
                    depth = wall_x - cut_position
                    walls_beyond.append(WallElevation(
                        start_x=min(start[2], end[2]),
                        end_x=max(start[2], end[2]),
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        is_exterior=is_exterior,
                        depth=depth,
                        wall_index=wall_index
                    ))
            else:  # Wall runs along X axis (horizontal in plan)
                # Show in elevation if any part is beyond the cut
                min_x = min(start[0], end[0])
                max_x = max(start[0], end[0])

                if max_x > cut_position:
                    # Show as edge-on line in elevation
                    wall_z = start[2]  # Z position in section
                    depth = min_x - cut_position if min_x > cut_position else 0
                    walls_beyond.append(WallElevation(
                        start_x=wall_z - total_thickness/2,
                        end_x=wall_z + total_thickness/2,
                        bottom_y=start[1],
                        top_y=start[1] + height,
                        is_exterior=is_exterior,
                        depth=depth,
                        wall_index=wall_index
                    ))

    # Process openings - both in section and in elevation
    for door in doors:
        wall_idx = door.get('wall_index', -1)
        if wall_idx < 0 or wall_idx >= len(walls):
            continue

        wall = walls[wall_idx]
        wall_start = wall['start']
        wall_end = wall['end']

        # Calculate door position
        wall_dx = wall_end[0] - wall_start[0]
        wall_dz = wall_end[2] - wall_start[2]
        wall_length = math.sqrt(wall_dx**2 + wall_dz**2)

        if wall_length < 1:
            continue

        t = door['offset'] / wall_length
        door_x = wall_start[0] + t * wall_dx
        door_z = wall_start[2] + t * wall_dz

        # Determine position in section
        if direction == SectionDirection.LONGITUDINAL:
            wall_z = (wall_start[2] + wall_end[2]) / 2
            is_horizontal_wall = abs(wall_dz) < 100

            if is_horizontal_wall and abs(wall_z - cut_position) < cut_tolerance:
                # Door in wall at cut position - show in section
                openings.append(Opening(
                    center_x=door_x,
                    width=door['width'],
                    bottom_y=0,
                    top_y=door['height'],
                    is_door=True,
                    in_section=True
                ))
            elif is_horizontal_wall and wall_z > cut_position:
                # Door in wall beyond cut - show in elevation
                openings.append(Opening(
                    center_x=door_x,
                    width=door['width'],
                    bottom_y=0,
                    top_y=door['height'],
                    is_door=True,
                    in_section=False,
                    depth=wall_z - cut_position
                ))
        else:
            wall_x = (wall_start[0] + wall_end[0]) / 2
            is_vertical_wall = abs(wall_dx) < 100

            if is_vertical_wall and abs(wall_x - cut_position) < cut_tolerance:
                # Door in wall at cut position - show in section
                openings.append(Opening(
                    center_x=door_z,
                    width=door['width'],
                    bottom_y=0,
                    top_y=door['height'],
                    is_door=True,
                    in_section=True
                ))
            elif is_vertical_wall and wall_x > cut_position:
                # Door in wall beyond cut - show in elevation
                openings.append(Opening(
                    center_x=door_z,
                    width=door['width'],
                    bottom_y=0,
                    top_y=door['height'],
                    is_door=True,
                    in_section=False,
                    depth=wall_x - cut_position
                ))

    for window in windows:
        wall_idx = window.get('wall_index', -1)
        if wall_idx < 0 or wall_idx >= len(walls):
            continue

        wall = walls[wall_idx]
        wall_start = wall['start']
        wall_end = wall['end']

        wall_dx = wall_end[0] - wall_start[0]
        wall_dz = wall_end[2] - wall_start[2]
        wall_length = math.sqrt(wall_dx**2 + wall_dz**2)

        if wall_length < 1:
            continue

        t = window['offset'] / wall_length
        win_x = wall_start[0] + t * wall_dx
        win_z = wall_start[2] + t * wall_dz

        sill = window.get('sill_height', 900)

        if direction == SectionDirection.LONGITUDINAL:
            wall_z = (wall_start[2] + wall_end[2]) / 2
            is_horizontal_wall = abs(wall_dz) < 100

            if is_horizontal_wall and abs(wall_z - cut_position) < cut_tolerance:
                # Window in wall at cut position - show in section
                openings.append(Opening(
                    center_x=win_x,
                    width=window['width'],
                    bottom_y=sill,
                    top_y=sill + window['height'],
                    is_door=False,
                    in_section=True
                ))
            elif is_horizontal_wall and wall_z > cut_position:
                # Window in wall beyond cut - show in elevation
                openings.append(Opening(
                    center_x=win_x,
                    width=window['width'],
                    bottom_y=sill,
                    top_y=sill + window['height'],
                    is_door=False,
                    in_section=False,
                    depth=wall_z - cut_position
                ))
        else:
            wall_x = (wall_start[0] + wall_end[0]) / 2
            is_vertical_wall = abs(wall_dx) < 100

            if is_vertical_wall and abs(wall_x - cut_position) < cut_tolerance:
                # Window in wall at cut position - show in section
                openings.append(Opening(
                    center_x=win_z,
                    width=window['width'],
                    bottom_y=sill,
                    top_y=sill + window['height'],
                    is_door=False,
                    in_section=True
                ))
            elif is_vertical_wall and wall_x > cut_position:
                # Window in wall beyond cut - show in elevation
                openings.append(Opening(
                    center_x=win_z,
                    width=window['width'],
                    bottom_y=sill,
                    top_y=sill + window['height'],
                    is_door=False,
                    in_section=False,
                    depth=wall_x - cut_position
                ))

    # Floor levels
    wall_height = 2700
    if walls:
        wall_height = walls[0].get('height', 2700)

    if direction == SectionDirection.LONGITUDINAL:
        section_width = building_width
    else:
        section_width = building_depth

    floor_levels = [
        FloorLevel(y=0, label="Floor", start_x=0, end_x=section_width),
        FloorLevel(y=wall_height, label="Ceiling/Plate", start_x=0, end_x=section_width),
    ]

    # Roof section - generate roof profile based on roof type and geometry
    roof_section = None
    max_roof_height = wall_height

    if roofs:
        roof = roofs[0]
        roof_type = roof.get('type', 'gable')
        pitch = roof.get('pitch', 4)  # Rise per 12 run
        overhang = roof.get('overhang', 600)

        # Calculate ridge height based on pitch
        # For gable: ridge is at center, height = (depth/2) * (pitch/12)
        # For hip: similar but ridge is shorter
        roof_points = []

        if direction == SectionDirection.LONGITUDINAL:
            # Looking along the building length (north/south view)
            # Shows the roof slope from eave to ridge to eave

            # Eave height at plate line
            eave_height = wall_height

            # Ridge height calculation
            half_depth = building_depth / 2
            ridge_rise = half_depth * (pitch / 12)
            ridge_height = eave_height + ridge_rise

            if roof_type in ['gable', 'hip']:
                # Left eave (with overhang)
                roof_points.append(Point2D(-overhang, eave_height))
                # Left plate
                roof_points.append(Point2D(0, eave_height))
                # Ridge
                roof_points.append(Point2D(section_width / 2, ridge_height))
                # Right plate
                roof_points.append(Point2D(section_width, eave_height))
                # Right eave (with overhang)
                roof_points.append(Point2D(section_width + overhang, eave_height))

            max_roof_height = ridge_height

        else:
            # TRANSVERSE - looking across the building width (east/west view)
            # For gable roof: shows the triangular gable end
            # For hip roof: shows sloped end

            eave_height = wall_height
            half_depth = building_depth / 2
            ridge_rise = half_depth * (pitch / 12)
            ridge_height = eave_height + ridge_rise

            if roof_type == 'gable':
                # Gable end - triangular profile
                # Bottom left
                roof_points.append(Point2D(-overhang, eave_height))
                # Peak (ridge extends to gable end)
                roof_points.append(Point2D(section_width / 2, ridge_height))
                # Bottom right
                roof_points.append(Point2D(section_width + overhang, eave_height))

            elif roof_type == 'hip':
                # Hip end - sloped profile
                hip_inset = half_depth  # Hip comes in from end
                # Bottom left eave
                roof_points.append(Point2D(-overhang, eave_height))
                # Left plate
                roof_points.append(Point2D(0, eave_height))
                # Ridge point (hip reaches ridge inside the building)
                roof_points.append(Point2D(section_width / 2, ridge_height))
                # Right plate
                roof_points.append(Point2D(section_width, eave_height))
                # Bottom right eave
                roof_points.append(Point2D(section_width + overhang, eave_height))

            max_roof_height = ridge_height

        if roof_points:
            roof_section = RoofSection(
                points=roof_points,
                ridge_height=max_roof_height,
                is_cut=True
            )

    # Room labels
    for room_id, room_data in rooms.items():
        if 'bounds' in room_data:
            bounds = room_data['bounds']
            room_cx = bounds.get('x', 0) + bounds.get('width', 0) / 2
            room_cz = bounds.get('y', 0) + bounds.get('height', 0) / 2  # 'y' is actually Z in plan

            # Check if room intersects with section cut
            if direction == SectionDirection.LONGITUDINAL:
                if bounds.get('y', 0) < cut_position < bounds.get('y', 0) + bounds.get('height', 0):
                    room_labels.append(RoomLabel(
                        center_x=room_cx,
                        center_y=wall_height / 2,
                        name=room_data.get('name', room_id)
                    ))
            else:
                if bounds.get('x', 0) < cut_position < bounds.get('x', 0) + bounds.get('width', 0):
                    room_labels.append(RoomLabel(
                        center_x=room_cz,
                        center_y=wall_height / 2,
                        name=room_data.get('name', room_id)
                    ))

    return Section(
        name=name,
        direction=direction,
        cut_position=cut_position,
        walls_cut=walls_cut,
        walls_beyond=walls_beyond,
        openings=openings,
        floor_levels=floor_levels,
        roof=roof_section,
        room_labels=room_labels,
        width=section_width,
        height=max_roof_height + 500  # Add margin for roof
    )

# =============================================================================
# SVG RENDERER
# =============================================================================

def get_hatch_pattern(function: str) -> str:
    """Return SVG pattern ID for layer function."""
    patterns = {
        'structure': 'hatch-wood',
        'insulation': 'hatch-insulation',
        'sheathing': 'hatch-plywood',
        'exterior_finish': 'hatch-solid',
        'interior_finish': 'hatch-gypsum',
    }
    return patterns.get(function, 'hatch-solid')

def render_section_svg(section: Section, scale: float = 0.05, margin: float = 80,
                       project_info: Dict = None, drawing_type: str = 'section_a') -> str:
    """Render a section to SVG format."""

    svg_width = section.width * scale + margin * 2 + 100
    svg_height = section.height * scale + margin * 2 + 50

    def tx(x): return x * scale + margin + 60
    def ty(y): return svg_height - margin - y * scale

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width:.0f} {svg_height:.0f}">')
    lines.append(f'  <title>Section {section.name}</title>')

    # Background
    lines.append('  <rect width="100%" height="100%" fill="white"/>')

    # Define patterns for hatching
    lines.append('''  <defs>
    <!-- Wood hatching (diagonal lines) -->
    <pattern id="hatch-wood" patternUnits="userSpaceOnUse" width="8" height="8">
      <path d="M0,8 L8,0 M-2,2 L2,-2 M6,10 L10,6" stroke="#8B4513" stroke-width="0.5" fill="none"/>
    </pattern>
    <!-- Insulation hatching (wavy lines) -->
    <pattern id="hatch-insulation" patternUnits="userSpaceOnUse" width="12" height="6">
      <path d="M0,3 Q3,0 6,3 Q9,6 12,3" stroke="#FFB6C1" stroke-width="1" fill="none"/>
    </pattern>
    <!-- Plywood/Sheathing (cross-hatch) -->
    <pattern id="hatch-plywood" patternUnits="userSpaceOnUse" width="6" height="6">
      <path d="M0,0 L6,6 M6,0 L0,6" stroke="#DEB887" stroke-width="0.5" fill="none"/>
    </pattern>
    <!-- Solid fill -->
    <pattern id="hatch-solid" patternUnits="userSpaceOnUse" width="4" height="4">
      <rect width="4" height="4" fill="#E0E0E0"/>
    </pattern>
    <!-- Gypsum (dots) -->
    <pattern id="hatch-gypsum" patternUnits="userSpaceOnUse" width="4" height="4">
      <circle cx="2" cy="2" r="0.5" fill="#999"/>
    </pattern>
    <!-- Concrete hatching -->
    <pattern id="hatch-concrete" patternUnits="userSpaceOnUse" width="10" height="10">
      <circle cx="2" cy="2" r="1" fill="#888"/>
      <circle cx="7" cy="6" r="1.5" fill="#888"/>
      <circle cx="4" cy="8" r="0.8" fill="#888"/>
    </pattern>
  </defs>''')

    # Styles
    lines.append('''  <style>
    .cut-wall { stroke: #000; stroke-width: 2; }
    .beyond-wall { fill: #f5f5f5; stroke: #666; stroke-width: 1; }
    .opening { fill: white; stroke: #333; stroke-width: 1; }
    .floor-line { stroke: #000; stroke-width: 2; }
    .level-line { stroke: #999; stroke-width: 0.5; stroke-dasharray: 5,5; }
    .roof-line { stroke: #000; stroke-width: 2; fill: none; }
    .room-label { font-family: Arial, sans-serif; font-size: 11px; fill: #333; text-anchor: middle; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #333; }
    .dimension { font-family: Arial, sans-serif; font-size: 9px; fill: #333; }
    .level-marker { font-family: Arial, sans-serif; font-size: 10px; fill: #666; }
    .ground { fill: #e8e8e8; }
    .grade-hatch { fill: url(#hatch-concrete); }
  </style>''')

    # Ground
    ground_y = ty(0)
    lines.append(f'  <rect x="{tx(0) - 30}" y="{ground_y}" width="{section.width * scale + 60}" height="30" class="ground"/>')
    lines.append(f'  <rect x="{tx(0) - 30}" y="{ground_y}" width="{section.width * scale + 60}" height="30" class="grade-hatch"/>')

    # Floor lines
    for level in section.floor_levels:
        y = ty(level.y)
        x1 = tx(level.start_x)
        x2 = tx(level.end_x)

        if level.label == "Floor":
            lines.append(f'  <line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="floor-line"/>')
        else:
            lines.append(f'  <line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" class="level-line"/>')

        # Level marker
        lines.append(f'  <text x="{margin/2}" y="{y + 3:.1f}" class="level-marker">{level.label}</text>')

    # Walls beyond (in elevation) - sort by depth (farthest first so closer walls draw on top)
    sorted_walls_beyond = sorted(section.walls_beyond, key=lambda w: -w.depth)
    for wall in sorted_walls_beyond:
        x1 = tx(wall.start_x)
        x2 = tx(wall.end_x)
        y1 = ty(wall.bottom_y)
        y2 = ty(wall.top_y)

        # Fade color based on depth (farther = lighter)
        max_depth = max(w.depth for w in section.walls_beyond) if section.walls_beyond else 1
        depth_factor = min(wall.depth / max_depth, 1) if max_depth > 0 else 0
        gray_value = int(220 + depth_factor * 30)  # Range 220-250 (light gray)
        fill_color = f"rgb({gray_value},{gray_value},{gray_value})"

        stroke_color = "#888" if wall.depth > 500 else "#666"
        stroke_width = "0.5" if wall.depth > 500 else "1"

        lines.append(f'  <rect x="{x1:.1f}" y="{y2:.1f}" width="{x2-x1:.1f}" height="{y1-y2:.1f}" fill="{fill_color}" stroke="{stroke_color}" stroke-width="{stroke_width}"/>')

    # Walls in section (cut through)
    for wall in section.walls_cut:
        x = tx(wall.x - wall.thickness / 2)
        y = ty(wall.top_y)
        w = wall.thickness * scale
        h = (wall.top_y - wall.bottom_y) * scale

        # Draw layers
        current_x = x
        for layer in wall.layers:
            layer_w = layer.get('thickness', 20) * scale
            pattern = get_hatch_pattern(layer.get('function', 'structure'))
            lines.append(f'  <rect x="{current_x:.1f}" y="{y:.1f}" width="{layer_w:.1f}" height="{h:.1f}" fill="url(#{pattern})" class="cut-wall"/>')
            current_x += layer_w

        # Outline
        lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" class="cut-wall"/>')

    # Openings - sort by depth (farthest first) for proper layering
    sorted_openings = sorted(section.openings, key=lambda o: -o.depth)
    for opening in sorted_openings:
        x = tx(opening.center_x - opening.width / 2)
        y = ty(opening.top_y)
        w = opening.width * scale
        h = (opening.top_y - opening.bottom_y) * scale

        if opening.in_section:
            # Show as cut-through (just the opening)
            lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="opening"/>')
        else:
            # Show in elevation - door or window behind the cut
            if opening.is_door:
                # Door in elevation - rectangle with threshold line
                lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="white" stroke="#666" stroke-width="1"/>')
            else:
                # Window in elevation - rectangle with mullion cross
                lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#e8f4fc" stroke="#666" stroke-width="1"/>')
                # Horizontal mullion
                mid_y = y + h / 2
                lines.append(f'  <line x1="{x:.1f}" y1="{mid_y:.1f}" x2="{x + w:.1f}" y2="{mid_y:.1f}" stroke="#666" stroke-width="0.5"/>')
                # Vertical mullion
                mid_x = x + w / 2
                lines.append(f'  <line x1="{mid_x:.1f}" y1="{y:.1f}" x2="{mid_x:.1f}" y2="{y + h:.1f}" stroke="#666" stroke-width="0.5"/>')

    # Roof
    if section.roof and section.roof.points:
        points = section.roof.points
        if len(points) >= 2:
            # Sort points by x
            sorted_points = sorted(points, key=lambda p: p.x)

            # Draw filled roof profile with thickness
            roof_thickness = 200  # mm - typical roof assembly thickness

            # Create outer roof line
            path_d = f"M {tx(sorted_points[0].x):.1f} {ty(sorted_points[0].y):.1f}"
            for p in sorted_points[1:]:
                path_d += f" L {tx(p.x):.1f} {ty(p.y):.1f}"

            # Create inner (underside) line - offset by thickness toward interior
            inner_points = []
            for i, p in enumerate(sorted_points):
                # Offset each point downward by roof thickness
                # For ridge point, offset straight down; for eave points, offset perpendicular to slope
                if i == 0 or i == len(sorted_points) - 1:
                    # Eave points - just offset down
                    inner_points.append(Point2D(p.x, p.y - roof_thickness * 0.3))
                elif i == len(sorted_points) // 2:
                    # Ridge point - offset down
                    inner_points.append(Point2D(p.x, p.y - roof_thickness))
                else:
                    # Intermediate points
                    inner_points.append(Point2D(p.x, p.y - roof_thickness * 0.5))

            # Complete the filled polygon (outer line + inner line reversed)
            for p in reversed(inner_points):
                path_d += f" L {tx(p.x):.1f} {ty(p.y):.1f}"
            path_d += " Z"

            # Draw filled roof section with hatching
            lines.append(f'  <path d="{path_d}" fill="url(#hatch-wood)" stroke="#000" stroke-width="1.5"/>')

            # Draw just the outer roof line thicker for emphasis
            outer_path = f"M {tx(sorted_points[0].x):.1f} {ty(sorted_points[0].y):.1f}"
            for p in sorted_points[1:]:
                outer_path += f" L {tx(p.x):.1f} {ty(p.y):.1f}"
            lines.append(f'  <path d="{outer_path}" fill="none" stroke="#000" stroke-width="2"/>')

    # Room labels
    for label in section.room_labels:
        x = tx(label.center_x)
        y = ty(label.center_y)
        lines.append(f'  <text x="{x:.1f}" y="{y:.1f}" class="room-label">{label.name.upper()}</text>')

    # Title
    dir_label = "Longitudinal" if section.direction == SectionDirection.LONGITUDINAL else "Transverse"
    lines.append(f'  <text x="{svg_width/2}" y="25" text-anchor="middle" class="title">SECTION {section.name} - {dir_label.upper()}</text>')

    # Section cut indicator
    lines.append(f'  <text x="{svg_width/2}" y="40" text-anchor="middle" class="dimension">Cut @ {section.cut_position:.0f}mm</text>')

    # Scale bar
    scale_bar_y = svg_height - 20
    scale_bar_x = svg_width / 2 - 50
    scale_length = 1000 * scale
    lines.append(f'  <line x1="{scale_bar_x}" y1="{scale_bar_y}" x2="{scale_bar_x + scale_length}" y2="{scale_bar_y}" stroke="#333" stroke-width="2"/>')
    lines.append(f'  <text x="{scale_bar_x + scale_length/2}" y="{scale_bar_y - 8}" text-anchor="middle" class="dimension">1m</text>')

    # Title block
    if project_info:
        drawing_info = get_drawing_info(drawing_type, '1:100')
        lines.append(generate_title_block(section.width, section.height, project_info, drawing_info, scale, margin))

    lines.append('</svg>')

    return '\n'.join(lines)

# =============================================================================
# MAIN
# =============================================================================

def generate_all_sections(input_path: str, output_dir: str, scale: float = 0.05):
    """Generate longitudinal and transverse sections."""

    with open(input_path, 'r') as f:
        data = json.load(f)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get project info for title blocks
    project_info = get_project_info_from_json(data)

    building_width = data.get('width', 10000)
    building_depth = data.get('depth', 10000)

    sections = [
        # Section A-A: Transverse cut through center
        (SectionDirection.TRANSVERSE, building_width / 2, "A", "section_a"),
        # Section B-B: Longitudinal cut through center
        (SectionDirection.LONGITUDINAL, building_depth / 2, "B", "section_b"),
    ]

    for direction, cut_pos, name, drawing_type in sections:
        print(f"Generating Section {name}...")

        section = generate_section(data, direction, cut_pos, name)
        svg = render_section_svg(section, scale=scale, project_info=project_info, drawing_type=drawing_type)

        out_file = output_path / f"section_{name.lower()}.svg"
        with open(out_file, 'w') as f:
            f.write(svg)

        print(f"  Wrote {out_file}")
        print(f"  - {len(section.walls_cut)} walls in section")
        print(f"  - {len(section.walls_beyond)} walls beyond")
        print(f"  - {len(section.openings)} openings")
        print(f"  - {len(section.room_labels)} room labels")

    print(f"\nGenerated {len(sections)} sections in {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Generate 2D sections from building JSON')
    parser.add_argument('input', nargs='?',
                        default='../../Shared/TestData/output/generated_building.json',
                        help='Input JSON file path')
    parser.add_argument('-o', '--output',
                        default='../../Shared/TestData/output',
                        help='Output directory for SVG files')
    parser.add_argument('-s', '--scale', type=float, default=0.05,
                        help='Scale factor (default: 0.05)')

    args = parser.parse_args()

    generate_all_sections(args.input, args.output, args.scale)

if __name__ == '__main__':
    main()
