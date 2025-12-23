#!/usr/bin/env python3
"""
generate_elevations.py - Generate 2D elevation drawings from building JSON

Creates North, South, East, West elevation views showing:
- Exterior wall faces with proper heights
- Windows with sill heights and headers
- Doors with proper heights
- Roof profiles
- Level markers (floor, ceiling, plate heights)
"""

import json
import math
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

from title_block import generate_title_block, get_project_info_from_json, get_drawing_info

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Point2D:
    x: float
    y: float

@dataclass
class WallSegment:
    """A wall segment projected onto an elevation plane"""
    start_x: float      # Horizontal position (along elevation)
    end_x: float        # Horizontal end position
    bottom_y: float     # Vertical position (usually 0 for ground floor)
    top_y: float        # Top of wall
    wall_index: int     # Original wall index for door/window matching

@dataclass
class Opening:
    """Door or window opening"""
    center_x: float     # Horizontal center position
    width: float
    bottom_y: float     # Sill height (0 for doors)
    top_y: float        # Header height
    is_door: bool
    opening_type: str   # "entry", "swing", "double_hung", etc.

@dataclass
class RoofEdge:
    """Roof edge/profile line"""
    start: Point2D
    end: Point2D

@dataclass
class LevelMarker:
    """Horizontal level marker"""
    y: float
    label: str
    is_major: bool = True

@dataclass
class Elevation:
    """Complete elevation data for one direction"""
    direction: str      # "north", "south", "east", "west"
    walls: List[WallSegment]
    openings: List[Opening]
    roof_edges: List[RoofEdge]
    level_markers: List[LevelMarker]
    width: float        # Total width of elevation
    height: float       # Total height including roof

# =============================================================================
# GEOMETRY HELPERS
# =============================================================================

def get_wall_direction(start: List[float], end: List[float]) -> Optional[str]:
    """
    Determine which direction a wall faces based on its orientation.
    Walls are defined in XZ plane (Y is up in kernel coords).

    Returns: 'north', 'south', 'east', 'west', or None for angled walls
    """
    dx = end[0] - start[0]
    dz = end[2] - start[2]

    # Threshold for considering a wall axis-aligned
    threshold = 50  # mm

    if abs(dz) < threshold and abs(dx) > threshold:
        # Wall runs along X axis - faces North or South
        # Normal points in +Z or -Z direction
        # Convention: exterior is on the side with larger Z (north-facing)
        # This is simplified - actual direction depends on room placement
        return 'south' if dx > 0 else 'south'  # South-facing wall (front)
    elif abs(dx) < threshold and abs(dz) > threshold:
        # Wall runs along Z axis - faces East or West
        return 'east' if dz > 0 else 'west'

    return None  # Angled wall - skip for now

def get_wall_facing(wall: dict, all_walls: List[dict], building_bounds: dict) -> Optional[str]:
    """
    Determine wall facing direction based on position relative to building center.
    """
    start = wall['start']
    end = wall['end']

    dx = end[0] - start[0]
    dz = end[2] - start[2]

    # Calculate wall center
    wall_cx = (start[0] + end[0]) / 2
    wall_cz = (start[2] + end[2]) / 2

    # Building center
    bld_cx = building_bounds['width'] / 2
    bld_cz = building_bounds['depth'] / 2

    threshold = 50  # mm

    if abs(dz) < threshold and abs(dx) > threshold:
        # Wall runs along X axis (horizontal in plan)
        # Check if it's at the front (south, low Z) or back (north, high Z)
        if wall_cz < bld_cz:
            return 'south'
        else:
            return 'north'
    elif abs(dx) < threshold and abs(dz) > threshold:
        # Wall runs along Z axis (vertical in plan)
        # Check if it's on the left (west) or right (east)
        if wall_cx < bld_cx:
            return 'west'
        else:
            return 'east'

    return None

def project_to_elevation(wall: dict, direction: str, building_bounds: dict) -> WallSegment:
    """
    Project a 3D wall onto a 2D elevation plane.

    For South/North elevations: X position maps to horizontal, Y/height maps to vertical
    For East/West elevations: Z position maps to horizontal, Y/height maps to vertical
    """
    start = wall['start']
    end = wall['end']
    height = wall.get('height', 2700)  # Default 9' ceiling

    if direction in ['south', 'north']:
        # Project onto XY plane (looking from south or north)
        start_x = min(start[0], end[0])
        end_x = max(start[0], end[0])
        if direction == 'north':
            # Flip horizontally for north view (mirror)
            bw = building_bounds['width']
            start_x, end_x = bw - end_x, bw - start_x
    else:
        # Project onto ZY plane (looking from east or west)
        start_x = min(start[2], end[2])
        end_x = max(start[2], end[2])
        if direction == 'east':
            # Flip horizontally for east view
            bd = building_bounds['depth']
            start_x, end_x = bd - end_x, bd - start_x

    return WallSegment(
        start_x=start_x,
        end_x=end_x,
        bottom_y=start[1],  # Usually 0
        top_y=start[1] + height,
        wall_index=wall.get('_index', -1)
    )

def project_opening(opening: dict, wall: dict, direction: str,
                    building_bounds: dict, is_door: bool) -> Optional[Opening]:
    """Project a door or window onto the elevation plane."""

    wall_start = wall['start']
    wall_end = wall['end']

    # Calculate wall direction vector
    wall_dx = wall_end[0] - wall_start[0]
    wall_dz = wall_end[2] - wall_start[2]
    wall_length = math.sqrt(wall_dx**2 + wall_dz**2)

    if wall_length < 1:
        return None

    # Opening position along wall
    offset = opening['offset']  # Distance from wall start to opening center

    # Calculate 3D position of opening center
    t = offset / wall_length
    opening_x = wall_start[0] + t * wall_dx
    opening_z = wall_start[2] + t * wall_dz

    # Project to elevation
    if direction in ['south', 'north']:
        center_x = opening_x
        if direction == 'north':
            center_x = building_bounds['width'] - center_x
    else:
        center_x = opening_z
        if direction == 'east':
            center_x = building_bounds['depth'] - center_x

    width = opening['width']
    height = opening['height']
    sill_height = opening.get('sill_height', 0) if not is_door else 0

    return Opening(
        center_x=center_x,
        width=width,
        bottom_y=sill_height,
        top_y=sill_height + height,
        is_door=is_door,
        opening_type=opening.get('type', 'unknown')
    )

def get_roof_profile(roof: dict, direction: str, building_bounds: dict) -> List[RoofEdge]:
    """Extract the roof profile visible from the given direction."""
    edges = []

    if 'surfaces' not in roof:
        return edges

    for surface in roof['surfaces']:
        vertices = surface.get('vertices', [])
        if len(vertices) < 3:
            continue

        # Find edges that would be visible from this direction
        # For now, extract edges along the perimeter
        for i in range(len(vertices)):
            v1 = vertices[i]
            v2 = vertices[(i + 1) % len(vertices)]

            # Project vertices
            if direction in ['south', 'north']:
                x1, y1 = v1[0], v1[1]
                x2, y2 = v2[0], v2[1]
                if direction == 'north':
                    x1 = building_bounds['width'] - x1
                    x2 = building_bounds['width'] - x2
            else:
                x1, y1 = v1[2], v1[1]
                x2, y2 = v2[2], v2[1]
                if direction == 'east':
                    x1 = building_bounds['depth'] - x1
                    x2 = building_bounds['depth'] - x2

            edges.append(RoofEdge(
                start=Point2D(x1, y1),
                end=Point2D(x2, y2)
            ))

    return edges

# =============================================================================
# ELEVATION GENERATOR
# =============================================================================

def generate_elevation(data: dict, direction: str) -> Elevation:
    """Generate elevation data for a single direction."""

    building_bounds = {
        'width': data.get('width', 10000),
        'depth': data.get('depth', 10000)
    }

    walls = data.get('walls_batch', [])
    doors = data.get('doors', [])
    windows = data.get('windows', [])
    roofs = data.get('roofs', [])

    # Add index to walls for reference
    for i, wall in enumerate(walls):
        wall['_index'] = i

    # Filter exterior walls facing this direction
    elevation_walls = []
    wall_map = {}  # wall_index -> WallSegment

    for wall in walls:
        if wall.get('category') != 'exterior':
            continue

        facing = get_wall_facing(wall, walls, building_bounds)
        if facing == direction:
            segment = project_to_elevation(wall, direction, building_bounds)
            elevation_walls.append(segment)
            wall_map[wall['_index']] = segment

    # Collect openings for these walls
    elevation_openings = []

    for door in doors:
        wall_idx = door.get('wall_index', -1)
        if wall_idx in wall_map:
            wall = walls[wall_idx]
            opening = project_opening(door, wall, direction, building_bounds, is_door=True)
            if opening:
                elevation_openings.append(opening)

    for window in windows:
        wall_idx = window.get('wall_index', -1)
        if wall_idx in wall_map:
            wall = walls[wall_idx]
            opening = project_opening(window, wall, direction, building_bounds, is_door=False)
            if opening:
                elevation_openings.append(opening)

    # Get roof profile
    roof_edges = []
    for roof in roofs:
        roof_edges.extend(get_roof_profile(roof, direction, building_bounds))

    # Calculate level markers
    wall_height = 2700  # Default, could be extracted from walls
    if elevation_walls:
        wall_height = max(w.top_y - w.bottom_y for w in elevation_walls)

    level_markers = [
        LevelMarker(y=0, label="Floor", is_major=True),
        LevelMarker(y=wall_height, label="Plate", is_major=True),
    ]

    # Add window sill markers
    sill_heights = set()
    for op in elevation_openings:
        if not op.is_door and op.bottom_y > 0:
            sill_heights.add(op.bottom_y)

    for sill in sorted(sill_heights):
        level_markers.append(LevelMarker(y=sill, label=f"Sill {sill:.0f}", is_major=False))

    # Calculate bounds
    if direction in ['south', 'north']:
        width = building_bounds['width']
    else:
        width = building_bounds['depth']

    max_height = wall_height
    for edge in roof_edges:
        max_height = max(max_height, edge.start.y, edge.end.y)

    return Elevation(
        direction=direction,
        walls=elevation_walls,
        openings=elevation_openings,
        roof_edges=roof_edges,
        level_markers=level_markers,
        width=width,
        height=max_height
    )

# =============================================================================
# SVG RENDERER
# =============================================================================

def render_elevation_svg(elevation: Elevation, scale: float = 0.05,
                         margin: float = 50, project_info: Dict = None,
                         drawing_type: str = 'elevation_south') -> str:
    """Render an elevation to SVG format."""

    # Calculate SVG dimensions - add space for title block
    tb_margin = 1500  # Extra margin for title block
    svg_width = elevation.width * scale + margin * 2 + 100 + tb_margin * scale
    svg_height = elevation.height * scale + margin * 2 + 50 + tb_margin * scale

    # SVG coordinate system: Y increases downward, so we flip
    def tx(x): return x * scale + margin + 80  # Offset for level markers
    def ty(y): return svg_height - margin - y * scale

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width:.0f} {svg_height:.0f}">')
    lines.append(f'  <title>{elevation.direction.title()} Elevation</title>')

    # Background
    lines.append(f'  <rect width="100%" height="100%" fill="white"/>')

    # Styles
    lines.append('''  <style>
    .wall { fill: #f5f5f5; stroke: #333; stroke-width: 1.5; }
    .wall-outline { fill: none; stroke: #333; stroke-width: 2; }
    .opening { fill: white; stroke: #333; stroke-width: 1; }
    .door { fill: #d4a574; stroke: #333; stroke-width: 1; }
    .window-frame { fill: none; stroke: #333; stroke-width: 1.5; }
    .window-glass { fill: #cce5ff; stroke: #666; stroke-width: 0.5; }
    .window-mullion { stroke: #333; stroke-width: 1; }
    .roof { fill: none; stroke: #333; stroke-width: 2; }
    .level-line { stroke: #999; stroke-width: 0.5; stroke-dasharray: 5,5; }
    .level-line-major { stroke: #666; stroke-width: 1; stroke-dasharray: none; }
    .level-text { font-family: Arial, sans-serif; font-size: 10px; fill: #666; }
    .title { font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; fill: #333; }
    .dimension { font-family: Arial, sans-serif; font-size: 9px; fill: #333; }
    .ground { fill: #e8e8e8; }
    .grade-line { stroke: #666; stroke-width: 2; }
  </style>''')

    # Ground indication
    ground_y = ty(0)
    lines.append(f'  <rect x="{tx(0) - 20}" y="{ground_y}" width="{elevation.width * scale + 40}" height="20" class="ground"/>')
    lines.append(f'  <line x1="{tx(0) - 20}" y1="{ground_y}" x2="{tx(elevation.width) + 20}" y2="{ground_y}" class="grade-line"/>')

    # Draw walls
    for wall in elevation.walls:
        x1, x2 = tx(wall.start_x), tx(wall.end_x)
        y1, y2 = ty(wall.bottom_y), ty(wall.top_y)
        lines.append(f'  <rect x="{x1:.1f}" y="{y2:.1f}" width="{x2-x1:.1f}" height="{y1-y2:.1f}" class="wall"/>')

    # Draw openings
    for opening in elevation.openings:
        x = tx(opening.center_x - opening.width / 2)
        y = ty(opening.top_y)
        w = opening.width * scale
        h = (opening.top_y - opening.bottom_y) * scale

        if opening.is_door:
            # Door with panel indication
            lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="door"/>')
            # Door frame
            frame_w = 3
            lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="window-frame"/>')
            # Door handle
            handle_x = x + w * 0.85
            handle_y = y + h * 0.5
            lines.append(f'  <circle cx="{handle_x:.1f}" cy="{handle_y:.1f}" r="3" fill="#666"/>')
        else:
            # Window with glass and frame
            lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="window-glass"/>')
            lines.append(f'  <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="window-frame"/>')

            # Mullions for double-hung windows
            if opening.opening_type in ['double_hung', 'sliding']:
                # Horizontal meeting rail
                mid_y = y + h / 2
                lines.append(f'  <line x1="{x:.1f}" y1="{mid_y:.1f}" x2="{x + w:.1f}" y2="{mid_y:.1f}" class="window-mullion"/>')

            # Window sill
            sill_y = ty(opening.bottom_y)
            lines.append(f'  <line x1="{x - 5:.1f}" y1="{sill_y:.1f}" x2="{x + w + 5:.1f}" y2="{sill_y:.1f}" stroke="#333" stroke-width="2"/>')

    # Draw roof profile
    for edge in elevation.roof_edges:
        x1, y1 = tx(edge.start.x), ty(edge.start.y)
        x2, y2 = tx(edge.end.x), ty(edge.end.y)
        lines.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="roof"/>')

    # Draw level markers
    marker_x = margin / 2
    for marker in elevation.level_markers:
        y = ty(marker.y)
        line_class = "level-line-major" if marker.is_major else "level-line"

        # Level line
        lines.append(f'  <line x1="{marker_x}" y1="{y:.1f}" x2="{tx(elevation.width) + 20}" y2="{y:.1f}" class="{line_class}"/>')

        # Level symbol (circle with line)
        if marker.is_major:
            lines.append(f'  <circle cx="{marker_x}" cy="{y:.1f}" r="8" fill="white" stroke="#333" stroke-width="1"/>')
            lines.append(f'  <text x="{marker_x}" y="{y + 3:.1f}" text-anchor="middle" class="dimension">{marker.y/1000:.1f}</text>')

        # Label
        lines.append(f'  <text x="{marker_x + 15}" y="{y - 5:.1f}" class="level-text">{marker.label}</text>')

    # Title
    lines.append(f'  <text x="{svg_width / 2}" y="25" text-anchor="middle" class="title">{elevation.direction.upper()} ELEVATION</text>')

    # Scale bar
    scale_bar_y = svg_height - 20
    scale_bar_x = svg_width / 2 - 50
    scale_length = 1000 * scale  # 1 meter
    lines.append(f'  <line x1="{scale_bar_x}" y1="{scale_bar_y}" x2="{scale_bar_x + scale_length}" y2="{scale_bar_y}" stroke="#333" stroke-width="2"/>')
    lines.append(f'  <line x1="{scale_bar_x}" y1="{scale_bar_y - 5}" x2="{scale_bar_x}" y2="{scale_bar_y + 5}" stroke="#333" stroke-width="2"/>')
    lines.append(f'  <line x1="{scale_bar_x + scale_length}" y1="{scale_bar_y - 5}" x2="{scale_bar_x + scale_length}" y2="{scale_bar_y + 5}" stroke="#333" stroke-width="2"/>')
    lines.append(f'  <text x="{scale_bar_x + scale_length/2}" y="{scale_bar_y - 8}" text-anchor="middle" class="dimension">1m</text>')

    # Title block
    if project_info:
        drawing_info = get_drawing_info(drawing_type, '1:100')
        lines.append(generate_title_block(elevation.width, elevation.height, project_info, drawing_info, scale, margin))

    lines.append('</svg>')

    return '\n'.join(lines)

# =============================================================================
# MAIN
# =============================================================================

def generate_all_elevations(input_path: str, output_dir: str, scale: float = 0.05):
    """Generate all four elevations from a building JSON file."""

    # Load JSON
    with open(input_path, 'r') as f:
        data = json.load(f)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get project info for title blocks
    project_info = get_project_info_from_json(data)

    directions = ['south', 'north', 'east', 'west']

    for direction in directions:
        print(f"Generating {direction} elevation...")

        elevation = generate_elevation(data, direction)
        drawing_type = f'elevation_{direction}'
        svg = render_elevation_svg(elevation, scale=scale, project_info=project_info, drawing_type=drawing_type)

        out_file = output_path / f"elevation_{direction}.svg"
        with open(out_file, 'w') as f:
            f.write(svg)

        print(f"  Wrote {out_file}")
        print(f"  - {len(elevation.walls)} wall segments")
        print(f"  - {len(elevation.openings)} openings")
        print(f"  - {len(elevation.roof_edges)} roof edges")

    print(f"\nGenerated {len(directions)} elevations in {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Generate 2D elevations from building JSON')
    parser.add_argument('input', nargs='?',
                        default='../../Shared/TestData/output/generated_building.json',
                        help='Input JSON file path')
    parser.add_argument('-o', '--output',
                        default='../../Shared/TestData/output',
                        help='Output directory for SVG files')
    parser.add_argument('-s', '--scale', type=float, default=0.05,
                        help='Scale factor (default: 0.05, meaning 1mm = 0.05px)')

    args = parser.parse_args()

    generate_all_elevations(args.input, args.output, args.scale)

if __name__ == '__main__':
    main()
