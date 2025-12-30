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
# ROOF GEOMETRY CALCULATORS
# =============================================================================

def calculate_rafter_depth(span: float, spacing: float = 600, load: str = "normal") -> float:
    """
    Calculate rafter depth based on span.

    Args:
        span: Rafter span in mm (horizontal distance)
        spacing: Rafter spacing in mm (typically 400 or 600)
        load: "light", "normal", or "heavy"

    Returns:
        Recommended rafter depth in mm
    """
    # Basic rule: span/15 to span/20 depending on load
    # Common sizes: 140, 190, 240, 290mm
    load_factors = {"light": 20, "normal": 17, "heavy": 15}
    factor = load_factors.get(load, 17)

    min_depth = span / factor

    # Round up to standard lumber sizes
    standard_depths = [140, 190, 240, 290, 340]
    for depth in standard_depths:
        if depth >= min_depth:
            return depth
    return standard_depths[-1]


def calculate_heel_height(pitch: float, rafter_depth: float,
                          insulation_depth: float = 300, energy_heel: bool = True) -> float:
    """
    Calculate heel height at the eave.

    Heel height is the vertical distance from top of wall plate
    to top of rafter at the bearing point.

    Args:
        pitch: Roof pitch as rise per 12 run
        rafter_depth: Rafter/truss depth in mm
        insulation_depth: Required ceiling insulation depth in mm
        energy_heel: If True, size for full insulation at eave

    Returns:
        Heel height in mm
    """
    import math

    pitch_angle = math.atan(pitch / 12)

    if energy_heel:
        # Energy heel: sized to allow full insulation depth at eave
        # Heel height = insulation_depth + rafter_depth * cos(angle)
        heel = insulation_depth + rafter_depth * math.cos(pitch_angle) * 0.3
        return max(heel, 250)  # Minimum 250mm for energy heel
    else:
        # Standard heel: minimal, just enough for birdsmouth
        # Typically rafter_depth * cos(angle) * 0.6
        heel = rafter_depth * math.cos(pitch_angle) * 0.6
        return max(heel, 100)  # Minimum 100mm


def calculate_birdsmouth(rafter_depth: float, pitch: float,
                         plate_width: float = 90) -> dict:
    """
    Calculate birdsmouth cut dimensions.

    The birdsmouth is the notch cut in a rafter where it sits on the wall plate.

    Args:
        rafter_depth: Rafter depth in mm
        pitch: Roof pitch as rise per 12 run
        plate_width: Wall plate width in mm (typically 90 for 2x4)

    Returns:
        Dict with seat_cut, plumb_cut, notch_depth, remaining_depth
    """
    import math

    pitch_angle = math.atan(pitch / 12)

    # Seat cut (horizontal bearing surface) - minimum 38mm per code
    seat_cut = max(plate_width * 0.9, 38)

    # Notch depth - max 1/3 of rafter depth per code
    max_notch = rafter_depth / 3

    # Calculate actual notch based on seat cut and pitch
    notch_depth = seat_cut * math.tan(pitch_angle)
    notch_depth = min(notch_depth, max_notch)

    # Plumb cut (vertical cut at heel)
    plumb_cut = notch_depth / math.sin(pitch_angle) if pitch_angle > 0.1 else notch_depth

    return {
        'seat_cut': seat_cut,
        'plumb_cut': plumb_cut,
        'notch_depth': notch_depth,
        'remaining_depth': rafter_depth - notch_depth,
        'pitch_angle_deg': math.degrees(pitch_angle)
    }


def calculate_roof_section_profile(
    building_width: float,
    wall_height: float,
    pitch: float,
    overhang: float = 600,
    rafter_depth: float = None,
    energy_heel: bool = True
) -> dict:
    """
    Calculate complete roof section profile with proper geometry.

    Args:
        building_width: Building width in mm
        wall_height: Wall/plate height in mm
        pitch: Roof pitch as rise per 12 run
        overhang: Eave overhang in mm
        rafter_depth: Rafter depth (calculated if None)
        energy_heel: Use energy heel sizing

    Returns:
        Dict with all roof geometry points and dimensions
    """
    import math

    # Calculate span (half building width for symmetrical gable)
    half_span = building_width / 2

    # Calculate rafter depth if not provided
    if rafter_depth is None:
        rafter_depth = calculate_rafter_depth(half_span)

    # Calculate heel height
    heel_height = calculate_heel_height(pitch, rafter_depth, energy_heel=energy_heel)

    # Calculate birdsmouth
    birdsmouth = calculate_birdsmouth(rafter_depth, pitch)

    # Pitch angle
    pitch_angle = math.atan(pitch / 12)

    # Ridge height from plate level
    ridge_rise = half_span * (pitch / 12)
    ridge_height = wall_height + heel_height + ridge_rise

    # Rafter length (along slope)
    rafter_length = half_span / math.cos(pitch_angle)

    # Eave point (bottom of fascia at overhang)
    eave_drop = overhang * math.tan(pitch_angle)
    eave_height = wall_height + heel_height - eave_drop

    # Fascia height (typically 150-200mm)
    fascia_height = min(rafter_depth + 50, 200)

    # Build profile points (for section view)
    # Left side of building looking at section
    profile = {
        'dimensions': {
            'rafter_depth': rafter_depth,
            'heel_height': heel_height,
            'ridge_height': ridge_height,
            'eave_height': eave_height,
            'fascia_height': fascia_height,
            'pitch_angle_deg': math.degrees(pitch_angle),
            'rafter_length': rafter_length,
        },
        'birdsmouth': birdsmouth,
        'points': {
            # Outer roof line (top of rafters)
            'left_eave_outer': (-overhang, eave_height + fascia_height),
            'left_plate_outer': (0, wall_height + heel_height),
            'ridge_outer': (half_span, ridge_height),
            'right_plate_outer': (building_width, wall_height + heel_height),
            'right_eave_outer': (building_width + overhang, eave_height + fascia_height),

            # Inner roof line (bottom of rafters)
            'left_eave_inner': (-overhang, eave_height + fascia_height - rafter_depth * 0.3),
            'left_plate_inner': (0, wall_height + heel_height - rafter_depth * math.cos(pitch_angle)),
            'ridge_inner': (half_span, ridge_height - rafter_depth),
            'right_plate_inner': (building_width, wall_height + heel_height - rafter_depth * math.cos(pitch_angle)),
            'right_eave_inner': (building_width + overhang, eave_height + fascia_height - rafter_depth * 0.3),

            # Fascia
            'left_fascia_top': (-overhang, eave_height + fascia_height),
            'left_fascia_bottom': (-overhang, eave_height),
            'right_fascia_top': (building_width + overhang, eave_height + fascia_height),
            'right_fascia_bottom': (building_width + overhang, eave_height),

            # Ceiling line (at plate height)
            'ceiling_left': (0, wall_height),
            'ceiling_right': (building_width, wall_height),
        }
    }

    return profile


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

    # Roof section - generate roof profile using truss calculator for proper geometry
    roof_section = None
    max_roof_height = wall_height

    if roofs:
        roof = roofs[0]
        roof_type = roof.get('type', 'gable')
        pitch = roof.get('pitch', 4)  # Rise per 12 run
        overhang = roof.get('overhang', 600)

        # Use roof geometry calculator for accurate heel height and profile
        roof_profile = calculate_roof_section_profile(
            building_width=section_width,
            wall_height=wall_height,
            pitch=pitch,
            overhang=overhang,
            energy_heel=True
        )

        dims = roof_profile['dimensions']
        pts = roof_profile['points']

        roof_points = []

        if direction == SectionDirection.LONGITUDINAL:
            # Looking along the building length (north/south view)
            # Shows the roof slope from eave to ridge to eave with proper heel height

            if roof_type in ['gable', 'hip']:
                # Use calculated profile points with heel height
                roof_points.append(Point2D(pts['left_eave_outer'][0], pts['left_eave_outer'][1]))
                roof_points.append(Point2D(pts['left_plate_outer'][0], pts['left_plate_outer'][1]))
                roof_points.append(Point2D(pts['ridge_outer'][0], pts['ridge_outer'][1]))
                roof_points.append(Point2D(pts['right_plate_outer'][0], pts['right_plate_outer'][1]))
                roof_points.append(Point2D(pts['right_eave_outer'][0], pts['right_eave_outer'][1]))

            max_roof_height = dims['ridge_height']

        else:
            # TRANSVERSE - looking across the building width (east/west view)
            # For gable roof: shows the triangular gable end with heel height

            if roof_type == 'gable':
                # Gable end - triangular profile with heel
                roof_points.append(Point2D(pts['left_eave_outer'][0], pts['left_eave_outer'][1]))
                roof_points.append(Point2D(pts['ridge_outer'][0], pts['ridge_outer'][1]))
                roof_points.append(Point2D(pts['right_eave_outer'][0], pts['right_eave_outer'][1]))

            elif roof_type == 'hip':
                # Hip end - sloped profile with heel
                roof_points.append(Point2D(pts['left_eave_outer'][0], pts['left_eave_outer'][1]))
                roof_points.append(Point2D(pts['left_plate_outer'][0], pts['left_plate_outer'][1]))
                roof_points.append(Point2D(pts['ridge_outer'][0], pts['ridge_outer'][1]))
                roof_points.append(Point2D(pts['right_plate_outer'][0], pts['right_plate_outer'][1]))
                roof_points.append(Point2D(pts['right_eave_outer'][0], pts['right_eave_outer'][1]))

            max_roof_height = dims['ridge_height']

        # Add heel height level marker
        heel_height = dims['heel_height']
        floor_levels.append(FloorLevel(
            y=wall_height + heel_height,
            label=f"Heel ({heel_height:.0f}mm)",
            start_x=0, end_x=section_width
        ))

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

def _draw_angled_member(x1: float, y1: float, x2: float, y2: float, thickness: float) -> str:
    """
    Generate SVG path for an angled structural member with thickness.

    Returns an SVG path string for a parallelogram representing the member.
    """
    import math

    # Calculate angle and perpendicular offset
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx*dx + dy*dy)

    if length < 1:
        return ""

    # Unit perpendicular vector
    px = -dy / length
    py = dx / length

    # Half thickness offset
    offset = thickness / 2

    # Four corners of the member
    p1x = x1 + px * offset
    p1y = y1 + py * offset
    p2x = x2 + px * offset
    p2y = y2 + py * offset
    p3x = x2 - px * offset
    p3y = y2 - py * offset
    p4x = x1 - px * offset
    p4y = y1 - py * offset

    return f"M {p1x:.0f} {p1y:.0f} L {p2x:.0f} {p2y:.0f} L {p3x:.0f} {p3y:.0f} L {p4x:.0f} {p4y:.0f} Z"


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

def render_section_svg(section: Section, scale: float = 0.1, margin: float = 4000,
                       project_info: Dict = None, drawing_type: str = 'section_a') -> str:
    """Render a section to SVG format using model-space coordinates."""

    # Use model-space viewBox (like floor plan and elevations)
    vb_x = -margin
    vb_y = -margin
    vb_w = section.width + 2 * margin
    vb_h = section.height + 2 * margin + 1000

    lines = []
    lines.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{int(vb_w * scale)}" height="{int(vb_h * scale)}"
     viewBox="{vb_x} {vb_y} {vb_w} {vb_h}">''')
    lines.append(f'  <title>Section {section.name}</title>')

    # Define patterns for hatching (in model-space units)
    lines.append('''  <defs>
    <!-- Wood framing hatching (diagonal lines) -->
    <pattern id="hatch-wood" patternUnits="userSpaceOnUse" width="100" height="100">
      <rect width="100" height="100" fill="#f5e6d3"/>
      <path d="M0,100 L100,0 M-20,20 L20,-20 M80,120 L120,80" stroke="#c9a87c" stroke-width="6" fill="none"/>
    </pattern>

    <!-- Insulation hatching (wavy lines) -->
    <pattern id="hatch-insulation" patternUnits="userSpaceOnUse" width="150" height="80">
      <rect width="150" height="80" fill="#fff5f5"/>
      <path d="M0,40 Q37,10 75,40 Q112,70 150,40" stroke="#ffb6c1" stroke-width="8" fill="none"/>
    </pattern>

    <!-- Plywood/Sheathing (cross-hatch) -->
    <pattern id="hatch-plywood" patternUnits="userSpaceOnUse" width="80" height="80">
      <rect width="80" height="80" fill="#e8dcc8"/>
      <path d="M0,0 L80,80 M80,0 L0,80" stroke="#c9b8a8" stroke-width="4" fill="none"/>
    </pattern>

    <!-- Solid fill for exterior finish -->
    <pattern id="hatch-solid" patternUnits="userSpaceOnUse" width="50" height="50">
      <rect width="50" height="50" fill="#d0d0d0"/>
    </pattern>

    <!-- Gypsum/Drywall (stipple dots) -->
    <pattern id="hatch-gypsum" patternUnits="userSpaceOnUse" width="60" height="60">
      <rect width="60" height="60" fill="#f8f8f8"/>
      <circle cx="15" cy="15" r="4" fill="#ddd"/>
      <circle cx="45" cy="45" r="4" fill="#ddd"/>
    </pattern>

    <!-- Concrete hatching (aggregate) -->
    <pattern id="hatch-concrete" patternUnits="userSpaceOnUse" width="150" height="150">
      <rect width="150" height="150" fill="#c0c0c0"/>
      <circle cx="30" cy="30" r="12" fill="#999"/>
      <circle cx="100" cy="60" r="18" fill="#888"/>
      <circle cx="50" cy="110" r="10" fill="#999"/>
      <circle cx="120" cy="130" r="14" fill="#888"/>
    </pattern>

    <!-- Earth/Grade hatching (diagonal) -->
    <pattern id="hatch-earth" patternUnits="userSpaceOnUse" width="100" height="100">
      <rect width="100" height="100" fill="#d4c9b8"/>
      <line x1="0" y1="100" x2="100" y2="0" stroke="#c4b9a8" stroke-width="5"/>
      <line x1="50" y1="100" x2="100" y2="50" stroke="#c4b9a8" stroke-width="5"/>
      <line x1="0" y1="50" x2="50" y2="0" stroke="#c4b9a8" stroke-width="5"/>
    </pattern>

    <!-- Roof shingle pattern -->
    <pattern id="hatch-roof" patternUnits="userSpaceOnUse" width="200" height="100">
      <rect width="200" height="100" fill="#5a5a5a"/>
      <line x1="0" y1="50" x2="200" y2="50" stroke="#484848" stroke-width="4"/>
      <line x1="50" y1="0" x2="50" y2="50" stroke="#4a4a4a" stroke-width="3"/>
      <line x1="150" y1="0" x2="150" y2="50" stroke="#4a4a4a" stroke-width="3"/>
      <line x1="0" y1="50" x2="0" y2="100" stroke="#4a4a4a" stroke-width="3"/>
      <line x1="100" y1="50" x2="100" y2="100" stroke="#4a4a4a" stroke-width="3"/>
    </pattern>
  </defs>''')

    # Background
    lines.append(f'  <rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="white"/>')

    # Styles (in model-space units)
    lines.append('''  <style>
    .cut-wall { stroke: #000; stroke-width: 10; }
    .beyond-wall { fill: #f5f5f5; stroke: #666; stroke-width: 4; }
    .opening { fill: white; stroke: #333; stroke-width: 4; }
    .floor-line { stroke: #000; stroke-width: 10; }
    .level-line { stroke: #999; stroke-width: 4; stroke-dasharray: 80,40; }
    .roof-line { stroke: #000; stroke-width: 10; fill: none; }
    .room-label { font-family: Arial, sans-serif; font-size: 300px; fill: #333; text-anchor: middle; }
    .title { font-family: Arial, sans-serif; font-size: 400px; font-weight: bold; fill: #333; }
    .dimension { font-family: Arial, sans-serif; font-size: 200px; fill: #333; }
    .level-marker { font-family: Arial, sans-serif; font-size: 200px; fill: #666; }
    .ground { fill: url(#hatch-earth); }
    .shadow { fill: rgba(0,0,0,0.15); }
  </style>''')

    # Y-flip transform for section drawing (Y=0 at ground, positive Y going up)
    flip_y = section.height + 500

    lines.append(f'<!-- Section drawing (Y-flipped) -->')
    lines.append(f'<g transform="translate(0, {flip_y}) scale(1, -1)">')

    # Ground/grade with hatching
    lines.append(f'  <rect x="-200" y="-500" width="{section.width + 400}" height="500" class="ground"/>')
    lines.append(f'  <line x1="-200" y1="0" x2="{section.width + 200}" y2="0" stroke="#666" stroke-width="8"/>')

    # Walls beyond (in elevation) - sort by depth (farthest first so closer walls draw on top)
    sorted_walls_beyond = sorted(section.walls_beyond, key=lambda w: -w.depth)
    for wall in sorted_walls_beyond:
        x = wall.start_x
        y = wall.bottom_y
        w = wall.end_x - wall.start_x
        h = wall.top_y - wall.bottom_y

        # Fade color based on depth (farther = lighter)
        max_depth = max(wd.depth for wd in section.walls_beyond) if section.walls_beyond else 1
        depth_factor = min(wall.depth / max_depth, 1) if max_depth > 0 else 0
        gray_value = int(220 + depth_factor * 30)  # Range 220-250 (light gray)
        fill_color = f"rgb({gray_value},{gray_value},{gray_value})"

        stroke_width = 4 if wall.depth > 500 else 6
        lines.append(f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{fill_color}" stroke="#888" stroke-width="{stroke_width}"/>')

    # Floor lines
    for level in section.floor_levels:
        line_class = "floor-line" if level.label == "Floor" else "level-line"
        lines.append(f'  <line x1="{level.start_x:.0f}" y1="{level.y:.0f}" x2="{level.end_x:.0f}" y2="{level.y:.0f}" class="{line_class}"/>')

    # Walls in section (cut through) with layer hatching
    for wall in section.walls_cut:
        x = wall.x - wall.thickness / 2
        y = wall.bottom_y
        w = wall.thickness
        h = wall.top_y - wall.bottom_y

        # Draw each layer with its hatching pattern
        current_x = x
        for layer in wall.layers:
            layer_w = layer.get('thickness', 20)
            pattern = get_hatch_pattern(layer.get('function', 'structure'))
            lines.append(f'  <rect x="{current_x:.0f}" y="{y:.0f}" width="{layer_w:.0f}" height="{h:.0f}" fill="url(#{pattern})" stroke="#333" stroke-width="4"/>')
            current_x += layer_w

        # Bold outline around entire wall section
        lines.append(f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="none" stroke="#000" stroke-width="10"/>')

    # Openings - sort by depth (farthest first) for proper layering
    sorted_openings = sorted(section.openings, key=lambda o: -o.depth)
    for opening in sorted_openings:
        x = opening.center_x - opening.width / 2
        y = opening.bottom_y
        w = opening.width
        h = opening.top_y - opening.bottom_y

        if opening.in_section:
            # Show as cut-through (white opening in wall)
            lines.append(f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="white" stroke="#333" stroke-width="6"/>')
        else:
            # Show in elevation - door or window behind the cut
            if opening.is_door:
                # Door in elevation
                lines.append(f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#d4a574" stroke="#666" stroke-width="4"/>')
                # Door panels
                panel_margin = 40
                panel_h = (h - 3 * panel_margin) / 2
                lines.append(f'  <rect x="{x + panel_margin:.0f}" y="{y + panel_margin:.0f}" width="{w - 2*panel_margin:.0f}" height="{panel_h:.0f}" fill="#c49664" stroke="#8b6e4a" stroke-width="3"/>')
                lines.append(f'  <rect x="{x + panel_margin:.0f}" y="{y + 2*panel_margin + panel_h:.0f}" width="{w - 2*panel_margin:.0f}" height="{panel_h:.0f}" fill="#c49664" stroke="#8b6e4a" stroke-width="3"/>')
            else:
                # Window in elevation
                lines.append(f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="#cce5ff" stroke="#666" stroke-width="4"/>')
                # Mullions
                mid_y = y + h / 2
                mid_x = x + w / 2
                lines.append(f'  <line x1="{x:.0f}" y1="{mid_y:.0f}" x2="{x + w:.0f}" y2="{mid_y:.0f}" stroke="#666" stroke-width="4"/>')
                lines.append(f'  <line x1="{mid_x:.0f}" y1="{y:.0f}" x2="{mid_x:.0f}" y2="{y + h:.0f}" stroke="#666" stroke-width="4"/>')
                # Sill
                lines.append(f'  <rect x="{x - 50:.0f}" y="{y - 40:.0f}" width="{w + 100:.0f}" height="40" fill="#ddd" stroke="#333" stroke-width="4"/>')

    # Roof truss - draw actual truss structure
    if section.roof and section.roof.points:
        points = section.roof.points
        if len(points) >= 2:
            sorted_points = sorted(points, key=lambda p: p.x)

            # Get wall height (ceiling level) for bottom chord
            wall_height = 2700
            for level in section.floor_levels:
                if "Ceiling" in level.label or "Plate" in level.label:
                    wall_height = level.y
                    break

            # Calculate truss geometry
            left_eave = sorted_points[0]
            ridge = sorted_points[len(sorted_points) // 2]
            right_eave = sorted_points[-1]

            # Find heel points (where slope meets wall)
            left_plate_x = 0
            right_plate_x = section.width

            # Interpolate heel heights on the slope
            if ridge.x > left_eave.x:
                t_left = (left_plate_x - left_eave.x) / (ridge.x - left_eave.x)
                left_heel_y = left_eave.y + t_left * (ridge.y - left_eave.y)
            else:
                left_heel_y = left_eave.y

            if right_eave.x > ridge.x:
                t_right = (right_plate_x - ridge.x) / (right_eave.x - ridge.x)
                right_heel_y = ridge.y + t_right * (right_eave.y - ridge.y)
            else:
                right_heel_y = right_eave.y

            # Truss member thickness
            chord_depth = 190  # 2x8 typical
            web_thickness = 89  # 2x4

            # Draw bottom chord (at ceiling level)
            bc_y = wall_height
            lines.append(f'  <rect x="0" y="{bc_y - chord_depth/2:.0f}" width="{section.width:.0f}" height="{chord_depth:.0f}" fill="url(#hatch-wood)" stroke="#333" stroke-width="6"/>')

            # Draw top chords with proper angle and thickness
            # Left top chord: from left heel to ridge
            lines.append(f'  <!-- Left top chord -->')
            tc_left_path = _draw_angled_member(
                left_plate_x, left_heel_y,
                ridge.x, ridge.y,
                chord_depth
            )
            lines.append(f'  <path d="{tc_left_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="6"/>')

            # Right top chord: from ridge to right heel
            lines.append(f'  <!-- Right top chord -->')
            tc_right_path = _draw_angled_member(
                ridge.x, ridge.y,
                right_plate_x, right_heel_y,
                chord_depth
            )
            lines.append(f'  <path d="{tc_right_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="6"/>')

            # King post (center vertical from bottom chord to ridge)
            kp_x = section.width / 2
            kp_bottom = bc_y
            kp_top = ridge.y - chord_depth
            lines.append(f'  <rect x="{kp_x - web_thickness/2:.0f}" y="{kp_bottom:.0f}" width="{web_thickness:.0f}" height="{kp_top - kp_bottom:.0f}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Web members (W pattern for Fink truss)
            quarter_span = section.width / 4

            # Left web diagonal (from 1/4 point on BC up to midpoint on left TC)
            web_bc_left = quarter_span
            web_tc_left_x = quarter_span
            web_tc_left_y = left_heel_y + (ridge.y - left_heel_y) * 0.5

            web_left_path = _draw_angled_member(
                web_bc_left, bc_y,
                web_tc_left_x, web_tc_left_y,
                web_thickness
            )
            lines.append(f'  <path d="{web_left_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Left inner diagonal (from TC midpoint down to center BC)
            web_inner_left_path = _draw_angled_member(
                web_tc_left_x, web_tc_left_y,
                kp_x, bc_y,
                web_thickness
            )
            lines.append(f'  <path d="{web_inner_left_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Right web diagonal (mirror of left)
            web_bc_right = section.width - quarter_span
            web_tc_right_x = section.width - quarter_span
            web_tc_right_y = right_heel_y + (ridge.y - right_heel_y) * 0.5

            web_right_path = _draw_angled_member(
                web_bc_right, bc_y,
                web_tc_right_x, web_tc_right_y,
                web_thickness
            )
            lines.append(f'  <path d="{web_right_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Right inner diagonal
            web_inner_right_path = _draw_angled_member(
                web_tc_right_x, web_tc_right_y,
                kp_x, bc_y,
                web_thickness
            )
            lines.append(f'  <path d="{web_inner_right_path}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Heel blocks (vertical at ends)
            heel_block_height = left_heel_y - bc_y
            if heel_block_height > 50:
                # Left heel
                lines.append(f'  <rect x="{-web_thickness/2:.0f}" y="{bc_y:.0f}" width="{web_thickness:.0f}" height="{heel_block_height:.0f}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')
                # Right heel
                lines.append(f'  <rect x="{section.width - web_thickness/2:.0f}" y="{bc_y:.0f}" width="{web_thickness:.0f}" height="{heel_block_height:.0f}" fill="url(#hatch-wood)" stroke="#333" stroke-width="4"/>')

            # Roof sheathing on top of top chords
            sheathing_thickness = 18  # OSB/plywood
            # Left sheathing
            lines.append(f'  <line x1="{left_eave.x:.0f}" y1="{left_eave.y:.0f}" x2="{ridge.x:.0f}" y2="{ridge.y:.0f}" stroke="#8B4513" stroke-width="{sheathing_thickness}"/>')
            # Right sheathing
            lines.append(f'  <line x1="{ridge.x:.0f}" y1="{ridge.y:.0f}" x2="{right_eave.x:.0f}" y2="{right_eave.y:.0f}" stroke="#8B4513" stroke-width="{sheathing_thickness}"/>')

            # Fascia at eaves
            fascia_height = 200
            lines.append(f'  <rect x="{left_eave.x - 25:.0f}" y="{left_eave.y - fascia_height:.0f}" width="50" height="{fascia_height:.0f}" fill="#DEB887" stroke="#333" stroke-width="4"/>')
            lines.append(f'  <rect x="{right_eave.x - 25:.0f}" y="{right_eave.y - fascia_height:.0f}" width="50" height="{fascia_height:.0f}" fill="#DEB887" stroke="#333" stroke-width="4"/>')

    lines.append('</g>')

    # Level markers (outside flipped group - text right-side up)
    marker_x = -margin + 500
    for level in section.floor_levels:
        y = flip_y - level.y  # Convert to SVG Y

        # Level line extending from marker
        if level.label == "Floor":
            lines.append(f'<line x1="{marker_x}" y1="{y:.0f}" x2="{section.width + 200}" y2="{y:.0f}" stroke="#666" stroke-width="6"/>')
        else:
            lines.append(f'<line x1="{marker_x}" y1="{y:.0f}" x2="{section.width + 200}" y2="{y:.0f}" stroke="#999" stroke-width="4" stroke-dasharray="80,40"/>')

        # Level circle marker
        lines.append(f'<circle cx="{marker_x}" cy="{y:.0f}" r="200" fill="white" stroke="#333" stroke-width="6"/>')
        lines.append(f'<text x="{marker_x}" y="{y + 60:.0f}" text-anchor="middle" class="dimension">{level.y/1000:.1f}</text>')

        # Label
        lines.append(f'<text x="{marker_x + 350}" y="{y - 100:.0f}" class="level-marker">{level.label}</text>')

    # Room labels (outside flipped group)
    for label in section.room_labels:
        x = label.center_x
        y = flip_y - label.center_y
        lines.append(f'<text x="{x:.0f}" y="{y:.0f}" class="room-label">{label.name.upper()}</text>')

    # Title (in model space at top)
    dir_label = "LONGITUDINAL" if section.direction == SectionDirection.LONGITUDINAL else "TRANSVERSE"
    lines.append(f'<text x="{section.width/2}" y="{-margin + 600}" text-anchor="middle" class="title">SECTION {section.name} - {dir_label}</text>')

    # Scale bar
    sb_x = section.width / 2 - 500
    sb_y = section.height + 800
    lines.append(f'<line x1="{sb_x}" y1="{sb_y}" x2="{sb_x + 1000}" y2="{sb_y}" stroke="#333" stroke-width="8"/>')
    lines.append(f'<line x1="{sb_x}" y1="{sb_y - 50}" x2="{sb_x}" y2="{sb_y + 50}" stroke="#333" stroke-width="8"/>')
    lines.append(f'<line x1="{sb_x + 1000}" y1="{sb_y - 50}" x2="{sb_x + 1000}" y2="{sb_y + 50}" stroke="#333" stroke-width="8"/>')
    lines.append(f'<text x="{sb_x + 500}" y="{sb_y - 100}" text-anchor="middle" class="dimension">1m</text>')

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
