#!/usr/bin/env python3
"""
ArchEngine Plan Generator
Generates annotated floor plans and roof plans from QBD JSON output.
Plans update automatically when JSON changes.
"""

import json
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

from title_block import generate_title_block, get_project_info_from_json, get_drawing_info

@dataclass
class Wall:
    start: Tuple[float, float, float]
    end: Tuple[float, float, float]
    height: float
    category: str
    wall_type: str
    index: int

@dataclass
class Door:
    wall_index: int
    offset: float
    width: float
    height: float
    door_type: str
    swing: str

@dataclass
class Window:
    wall_index: int
    offset: float
    width: float
    height: float
    sill_height: float

@dataclass
class Room:
    name: str
    room_type: str
    bounds: Dict
    area: float
    center: Dict

@dataclass
class Roof:
    id: str
    roof_type: str  # gable, hip, flat, shed, mansard, gambrel
    pitch: float  # Rise over 12" run (e.g., 4 for 4:12)
    overhang: float  # Eave overhang in mm
    ridges: List[Dict] = field(default_factory=list)
    surfaces: List[Dict] = field(default_factory=list)
    skylights: List[Dict] = field(default_factory=list)
    dormers: List[Dict] = field(default_factory=list)

class PlanGenerator:
    def __init__(self, json_path: str):
        with open(json_path, 'r') as f:
            self.data = json.load(f)

        self.walls = self._parse_walls()
        self.doors = self._parse_doors()
        self.windows = self._parse_windows()
        self.rooms = self._parse_rooms()
        self.roofs = self._parse_roofs()

        # Get building bounds
        self.width = self.data.get('width', 12000)
        self.depth = self.data.get('depth', 9000)

        # Building type - residential buildings don't need grid lines
        building_type = self.data.get('building_type', 'residential')
        qbd_answers = self.data.get('qbd_answers', {})
        self.is_residential = building_type.lower() in ['residential', 'house', 'home'] or \
                              qbd_answers.get('building_type', '').lower() in ['residential', 'house', 'home'] or \
                              'bedroom' in str(qbd_answers).lower()

        # Wall thickness (mm)
        self.ext_wall_thickness = 175
        self.int_wall_thickness = 115

        # Roof defaults
        self.default_overhang = 600  # 600mm overhang
        self.default_pitch = 4  # 4:12 pitch

    def _parse_walls(self) -> List[Wall]:
        walls = []
        for i, w in enumerate(self.data.get('walls_batch', [])):
            walls.append(Wall(
                start=tuple(w['start']),
                end=tuple(w['end']),
                height=w['height'],
                category=w['category'],
                wall_type=w.get('wall_type', ''),
                index=i
            ))
        return walls

    def _parse_doors(self) -> List[Door]:
        doors = []
        for d in self.data.get('doors', []):
            doors.append(Door(
                wall_index=d['wall_index'],
                offset=d['offset'],
                width=d['width'],
                height=d['height'],
                door_type=d.get('type', 'swing'),
                swing=d.get('swing', 'left_in')
            ))
        return doors

    def _parse_windows(self) -> List[Window]:
        windows = []
        for w in self.data.get('windows', []):
            windows.append(Window(
                wall_index=w['wall_index'],
                offset=w['offset'],
                width=w['width'],
                height=w['height'],
                sill_height=w.get('sill_height', 900)
            ))
        return windows

    def _parse_rooms(self) -> Dict[str, Room]:
        rooms = {}
        for room_id, r in self.data.get('rooms', {}).items():
            rooms[room_id] = Room(
                name=r.get('name', room_id),
                room_type=r.get('room_type', ''),
                bounds=r.get('bounds', {}),
                area=r.get('area', 0),
                center=r.get('center', {})
            )
        return rooms

    def _parse_roofs(self) -> List[Roof]:
        roofs = []
        for r in self.data.get('roofs', []):
            roofs.append(Roof(
                id=r.get('id', 'roof_1'),
                roof_type=r.get('type', 'gable'),
                pitch=r.get('pitch', 4),
                overhang=r.get('overhang', 600),
                ridges=r.get('ridges', []),
                surfaces=r.get('surfaces', []),
                skylights=r.get('skylights', []),
                dormers=r.get('dormers', [])
            ))
        return roofs

    def _get_wall_geometry(self, wall: Wall) -> Dict:
        """Get wall start/end points and direction."""
        sx, sy, sz = wall.start
        ex, ey, ez = wall.end

        # Wall runs along X (horizontal) or Z (vertical in plan)
        dx = ex - sx
        dz = ez - sz
        length = math.sqrt(dx*dx + dz*dz)

        return {
            'start_x': sx,
            'start_z': sz,
            'end_x': ex,
            'end_z': ez,
            'length': length,
            'is_horizontal': abs(dz) < 1,  # Runs along X
            'is_vertical': abs(dx) < 1,    # Runs along Z
        }

    def _get_opening_position(self, wall: Wall, offset: float, width: float) -> Tuple[float, float, float, float]:
        """Get opening rectangle position on wall."""
        geom = self._get_wall_geometry(wall)

        if geom['is_horizontal']:
            # Wall runs along X axis
            start_x = min(geom['start_x'], geom['end_x']) + offset - width/2
            return (start_x, geom['start_z'], width, self.ext_wall_thickness)
        else:
            # Wall runs along Z axis
            start_z = min(geom['start_z'], geom['end_z']) + offset - width/2
            return (geom['start_x'], start_z, self.ext_wall_thickness, width)

    def generate_floor_plan_svg(self, scale: float = 0.1) -> str:
        """Generate floor plan SVG with proper annotations."""

        # Margins for dimensions
        margin = 4000

        # Viewbox
        vb_x = -margin
        vb_y = -margin
        vb_w = self.width + 2 * margin
        vb_h = self.depth + 2 * margin

        svg = []
        svg.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{int(vb_w * scale)}" height="{int(vb_h * scale)}"
     viewBox="{vb_x} {vb_y} {vb_w} {vb_h}">
<defs>
<style>
.wall-ext {{ fill: none; stroke: #000; stroke-width: 8; }}
.wall-int {{ fill: none; stroke: #000; stroke-width: 6; }}
.wall-wet {{ fill: none; stroke: #5588cc; stroke-width: 6; }}
.opening {{ fill: white; stroke: none; }}
.door-leaf {{ stroke: #000; stroke-width: 4; fill: none; }}
.door-swing {{ stroke: #000; stroke-width: 2; fill: none; }}
.window {{ fill: white; stroke: #000; stroke-width: 4; }}
.window-glass {{ stroke: #000; stroke-width: 2; }}
.grid-line {{ stroke: #ccc; stroke-width: 2; stroke-dasharray: 60,30; }}
.grid-bubble {{ fill: white; stroke: #000; stroke-width: 4; }}
.grid-label {{ font: bold 280px Arial; text-anchor: middle; dominant-baseline: central; }}
.room-label {{ font: 500 320px Arial; text-anchor: middle; }}
.room-area {{ font: 220px Arial; text-anchor: middle; fill: #555; }}
.dim-line {{ stroke: #000; stroke-width: 3; }}
.dim-ext {{ stroke: #000; stroke-width: 2; }}
.dim-text {{ font: 160px Arial; text-anchor: middle; }}
.title {{ font: bold 350px Arial; }}
</style>
</defs>
<rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="white"/>
''')

        # Title
        svg.append(f'<text x="{self.width/2}" y="{-margin + 400}" class="title" text-anchor="middle">FLOOR PLAN - LEVEL 1</text>')

        # Grid lines (only for commercial/non-residential)
        if not self.is_residential:
            svg.append(self._generate_grid_lines())

        # Walls
        svg.append(self._generate_walls())

        # Openings (doors and windows cut through walls)
        svg.append(self._generate_openings())

        # Door symbols
        svg.append(self._generate_door_symbols())

        # Window symbols
        svg.append(self._generate_window_symbols())

        # Room labels
        svg.append(self._generate_room_labels())

        # Ladder dimensions
        svg.append(self._generate_ladder_dimensions())

        # North arrow
        svg.append(self._generate_north_arrow(-margin + 800, 1500))

        # Scale bar
        svg.append(self._generate_scale_bar(-margin + 500, self.depth - 500))

        # Title block
        project_info = get_project_info_from_json(self.data)
        drawing_info = get_drawing_info('floor_plan', '1:100')
        svg.append(generate_title_block(self.width, self.depth, project_info, drawing_info, scale, margin))

        svg.append('</svg>')
        return '\n'.join(svg)

    def generate_roof_plan_svg(self, scale: float = 0.1) -> str:
        """Generate roof plan SVG with annotations."""

        # Get roof info (use first roof or generate default gable)
        if self.roofs:
            roof = self.roofs[0]
            overhang = roof.overhang
            pitch = roof.pitch
            roof_type = roof.roof_type
        else:
            overhang = self.default_overhang
            pitch = self.default_pitch
            roof_type = 'gable'

        # Roof extends beyond building by overhang
        roof_width = self.width + 2 * overhang
        roof_depth = self.depth + 2 * overhang

        # Margins for dimensions and annotations
        margin = 4000

        # Viewbox
        vb_x = -overhang - margin
        vb_y = -overhang - margin
        vb_w = roof_width + 2 * margin
        vb_h = roof_depth + 2 * margin

        svg = []
        svg.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{int(vb_w * scale)}" height="{int(vb_h * scale)}"
     viewBox="{vb_x} {vb_y} {vb_w} {vb_h}">
<defs>
<marker id="arrow-drain" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
  <polygon points="0 0, 10 3.5, 0 7" fill="#2196F3"/>
</marker>
<style>
.roof-outline {{ fill: #f5f5f5; stroke: #333; stroke-width: 6; }}
.building-outline {{ fill: none; stroke: #999; stroke-width: 2; stroke-dasharray: 30,15; }}
.ridge {{ stroke: #000; stroke-width: 8; stroke-linecap: round; }}
.hip {{ stroke: #000; stroke-width: 5; stroke-dasharray: 50,25; }}
.valley {{ stroke: #000; stroke-width: 5; stroke-dasharray: 25,12; }}
.eave {{ stroke: #555; stroke-width: 4; }}
.rake {{ stroke: #555; stroke-width: 4; stroke-dasharray: 40,20; }}
.drainage {{ stroke: #2196F3; stroke-width: 4; }}
.gutter {{ stroke: #795548; stroke-width: 10; stroke-linecap: round; }}
.downspout {{ fill: #795548; stroke: #5D4037; stroke-width: 2; }}
.skylight {{ fill: none; stroke: #00BCD4; stroke-width: 6; }}
.skylight-x {{ stroke: #00BCD4; stroke-width: 2; }}
.grid-line {{ stroke: #ddd; stroke-width: 2; stroke-dasharray: 60,30; }}
.grid-bubble {{ fill: white; stroke: #000; stroke-width: 4; }}
.grid-label {{ font: bold 280px Arial; text-anchor: middle; dominant-baseline: central; }}
.title {{ font: bold 400px Arial; }}
.subtitle {{ font: 250px Arial; fill: #666; }}
.pitch-label {{ font: bold 240px Arial; }}
.annotation {{ font: 180px Arial; }}
.dim-line {{ stroke: #000; stroke-width: 3; }}
.dim-ext {{ stroke: #000; stroke-width: 2; }}
.dim-text {{ font: 160px Arial; text-anchor: middle; }}
.legend-text {{ font: 160px Arial; }}
.legend-title {{ font: bold 200px Arial; }}
</style>
</defs>
<rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="white"/>
''')

        # Title
        svg.append(f'<text x="{self.width/2}" y="{-overhang - margin + 500}" class="title" text-anchor="middle">ROOF PLAN</text>')
        svg.append(f'<text x="{self.width/2}" y="{-overhang - margin + 900}" class="subtitle" text-anchor="middle">Scale: 1:100 | {roof_type.title()} Roof - {pitch}:12 Pitch</text>')

        # Grid lines (only for commercial/non-residential)
        if not self.is_residential:
            svg.append(self._generate_roof_grid_lines())

        # Roof outline with overhang
        svg.append(f'''<!-- Roof Outline -->
<rect x="{-overhang}" y="{-overhang}" width="{roof_width}" height="{roof_depth}" class="roof-outline"/>''')

        # Building outline (dashed, inside roof)
        svg.append(f'''<!-- Building Outline -->
<rect x="0" y="0" width="{self.width}" height="{self.depth}" class="building-outline"/>''')

        # Roof elements based on type
        if roof_type == 'gable':
            svg.append(self._generate_gable_roof(overhang, pitch))
        elif roof_type == 'hip':
            svg.append(self._generate_hip_roof(overhang, pitch))
        else:
            # Default to gable
            svg.append(self._generate_gable_roof(overhang, pitch))

        # Skylights
        svg.append(self._generate_skylights())

        # Gutters and downspouts
        svg.append(self._generate_gutters(overhang))

        # Dimensions
        svg.append(self._generate_roof_dimensions(overhang))

        # North arrow
        svg.append(self._generate_north_arrow(self.width + overhang + margin - 1000, 1500))

        # Legend
        svg.append(self._generate_roof_legend(-overhang - margin + 500, self.depth + overhang + 800))

        # Roof areas
        svg.append(self._generate_roof_areas(overhang, pitch))

        # Scale bar
        svg.append(self._generate_scale_bar(self.width/2 - 1000, self.depth + overhang + 2500))

        # Title block
        project_info = get_project_info_from_json(self.data)
        drawing_info = get_drawing_info('roof_plan', '1:100')
        svg.append(generate_title_block(roof_width, roof_depth, project_info, drawing_info, scale, margin))

        svg.append('</svg>')
        return '\n'.join(svg)

    def _generate_roof_grid_lines(self) -> str:
        """Generate grid lines for roof plan."""
        lines = ['<!-- Grid Lines -->']

        x_grids = sorted(set([0, self.width]))
        z_grids = sorted(set([0, self.depth]))

        # Add interior wall positions for grid
        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            if geom['is_vertical'] and wall.category == 'interior':
                x_grids.append(geom['start_x'])
            if geom['is_horizontal'] and wall.category == 'interior':
                z_grids.append(geom['start_z'])

        x_grids = sorted(set(x_grids))
        z_grids = sorted(set(z_grids))

        # Vertical grid lines
        for i, x in enumerate(x_grids):
            label = chr(65 + i)
            lines.append(f'<line x1="{x}" y1="-2500" x2="{x}" y2="{self.depth + 1500}" class="grid-line"/>')
            lines.append(f'<circle cx="{x}" cy="-3000" r="280" class="grid-bubble"/>')
            lines.append(f'<text x="{x}" y="-3000" class="grid-label">{label}</text>')

        # Horizontal grid lines
        for i, z in enumerate(z_grids):
            label = str(i + 1)
            lines.append(f'<line x1="-2500" y1="{z}" x2="{self.width + 1500}" y2="{z}" class="grid-line"/>')
            lines.append(f'<circle cx="-3000" cy="{z}" r="280" class="grid-bubble"/>')
            lines.append(f'<text x="-3000" y="{z}" class="grid-label">{label}</text>')

        return '\n'.join(lines)

    def _generate_gable_roof(self, overhang: float, pitch: float) -> str:
        """Generate gable roof elements (ridge runs E-W, gable ends on E and W)."""
        elements = ['<!-- Gable Roof Elements -->']

        # Ridge line (center of building, running along X axis)
        ridge_y = self.depth / 2
        elements.append(f'<line x1="{-overhang}" y1="{ridge_y}" x2="{self.width + overhang}" y2="{ridge_y}" class="ridge"/>')

        # Eave lines (north and south)
        elements.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{self.width + overhang}" y2="{-overhang}" class="eave"/>')
        elements.append(f'<line x1="{-overhang}" y1="{self.depth + overhang}" x2="{self.width + overhang}" y2="{self.depth + overhang}" class="eave"/>')

        # Rake lines (gable ends - east and west)
        elements.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{-overhang}" y2="{self.depth + overhang}" class="rake"/>')
        elements.append(f'<line x1="{self.width + overhang}" y1="{-overhang}" x2="{self.width + overhang}" y2="{self.depth + overhang}" class="rake"/>')

        # Drainage arrows - North slope (draining toward north eave)
        num_arrows = 3
        for i in range(num_arrows):
            x = (i + 1) * self.width / (num_arrows + 1)
            # Arrow from ridge toward north eave
            elements.append(f'<line x1="{x}" y1="{ridge_y - 500}" x2="{x}" y2="{-overhang + 300}" class="drainage" marker-end="url(#arrow-drain)"/>')

        # Drainage arrows - South slope (draining toward south eave)
        for i in range(num_arrows):
            x = (i + 1) * self.width / (num_arrows + 1)
            # Arrow from ridge toward south eave
            elements.append(f'<line x1="{x}" y1="{ridge_y + 500}" x2="{x}" y2="{self.depth + overhang - 300}" class="drainage" marker-end="url(#arrow-drain)"/>')

        # Pitch indicators
        # North slope
        elements.append(self._pitch_indicator(1500, ridge_y/2 - 200, pitch, 'north'))
        # South slope
        elements.append(self._pitch_indicator(self.width - 2500, ridge_y + ridge_y/2, pitch, 'south'))

        return '\n'.join(elements)

    def _generate_hip_roof(self, overhang: float, pitch: float) -> str:
        """Generate hip roof elements."""
        elements = ['<!-- Hip Roof Elements -->']

        # Ridge line (shorter than building, centered)
        ridge_y = self.depth / 2
        hip_inset = self.depth / 2  # Hip comes in from each end
        ridge_start_x = hip_inset
        ridge_end_x = self.width - hip_inset

        # Main ridge
        elements.append(f'<line x1="{ridge_start_x}" y1="{ridge_y}" x2="{ridge_end_x}" y2="{ridge_y}" class="ridge"/>')

        # Hip lines (from corners to ridge ends)
        # Northwest hip
        elements.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{ridge_start_x}" y2="{ridge_y}" class="hip"/>')
        # Southwest hip
        elements.append(f'<line x1="{-overhang}" y1="{self.depth + overhang}" x2="{ridge_start_x}" y2="{ridge_y}" class="hip"/>')
        # Northeast hip
        elements.append(f'<line x1="{self.width + overhang}" y1="{-overhang}" x2="{ridge_end_x}" y2="{ridge_y}" class="hip"/>')
        # Southeast hip
        elements.append(f'<line x1="{self.width + overhang}" y1="{self.depth + overhang}" x2="{ridge_end_x}" y2="{ridge_y}" class="hip"/>')

        # Eave lines (all four sides)
        elements.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{self.width + overhang}" y2="{-overhang}" class="eave"/>')
        elements.append(f'<line x1="{-overhang}" y1="{self.depth + overhang}" x2="{self.width + overhang}" y2="{self.depth + overhang}" class="eave"/>')
        elements.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{-overhang}" y2="{self.depth + overhang}" class="eave"/>')
        elements.append(f'<line x1="{self.width + overhang}" y1="{-overhang}" x2="{self.width + overhang}" y2="{self.depth + overhang}" class="eave"/>')

        # Drainage arrows for hip roof (4 directions)
        mid_x = self.width / 2
        elements.append(f'<line x1="{mid_x}" y1="{ridge_y - 400}" x2="{mid_x}" y2="{-overhang + 300}" class="drainage" marker-end="url(#arrow-drain)"/>')
        elements.append(f'<line x1="{mid_x}" y1="{ridge_y + 400}" x2="{mid_x}" y2="{self.depth + overhang - 300}" class="drainage" marker-end="url(#arrow-drain)"/>')
        elements.append(f'<line x1="{ridge_start_x - 400}" y1="{ridge_y}" x2="{-overhang + 300}" y2="{ridge_y}" class="drainage" marker-end="url(#arrow-drain)"/>')
        elements.append(f'<line x1="{ridge_end_x + 400}" y1="{ridge_y}" x2="{self.width + overhang - 300}" y2="{ridge_y}" class="drainage" marker-end="url(#arrow-drain)"/>')

        # Pitch indicator
        elements.append(self._pitch_indicator(mid_x - 500, ridge_y/2, pitch, 'north'))

        return '\n'.join(elements)

    def _pitch_indicator(self, x: float, y: float, pitch: float, direction: str) -> str:
        """Generate a pitch indicator triangle with label."""
        # Triangle showing rise/run ratio
        run = 600
        rise = run * pitch / 12

        if direction == 'north':
            # Triangle pointing up (north slope drains north)
            return f'''<g transform="translate({x}, {y})">
  <path d="M 0 {rise} L {run} {rise} L {run} 0 Z" fill="none" stroke="black" stroke-width="4"/>
  <text x="{run/2}" y="{rise + 300}" class="pitch-label" text-anchor="middle">{pitch}:12</text>
</g>'''
        else:
            # Triangle pointing down (south slope drains south)
            return f'''<g transform="translate({x}, {y})">
  <path d="M 0 0 L {run} 0 L {run} {rise} Z" fill="none" stroke="black" stroke-width="4"/>
  <text x="{run/2}" y="{rise + 300}" class="pitch-label" text-anchor="middle">{pitch}:12</text>
</g>'''

    def _generate_skylights(self) -> str:
        """Generate skylight symbols."""
        skylights_svg = ['<!-- Skylights -->']

        # Check for skylights in roof data
        if self.roofs and self.roofs[0].skylights:
            for skylight in self.roofs[0].skylights:
                pos = skylight.get('position', [0, 0, 0])
                w = skylight.get('width', 1000)
                h = skylight.get('height', 800)
                x = pos[0] - w/2
                y = pos[2] - h/2  # Use Z for plan view

                skylights_svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="skylight"/>')
                skylights_svg.append(f'<line x1="{x}" y1="{y}" x2="{x+w}" y2="{y+h}" class="skylight-x"/>')
                skylights_svg.append(f'<line x1="{x+w}" y1="{y}" x2="{x}" y2="{y+h}" class="skylight-x"/>')
                skylights_svg.append(f'<text x="{pos[0]}" y="{pos[2] + h/2 + 250}" class="annotation" text-anchor="middle">SKYLIGHT</text>')
                skylights_svg.append(f'<text x="{pos[0]}" y="{pos[2] + h/2 + 450}" class="annotation" text-anchor="middle">{int(w)} x {int(h)}</text>')
        else:
            # Add a sample skylight for demonstration
            # Place it on the south slope, offset from center
            sky_x = self.width * 0.65
            sky_y = self.depth * 0.65
            sky_w = 1200
            sky_h = 900

            skylights_svg.append(f'<rect x="{sky_x - sky_w/2}" y="{sky_y - sky_h/2}" width="{sky_w}" height="{sky_h}" class="skylight"/>')
            skylights_svg.append(f'<line x1="{sky_x - sky_w/2}" y1="{sky_y - sky_h/2}" x2="{sky_x + sky_w/2}" y2="{sky_y + sky_h/2}" class="skylight-x"/>')
            skylights_svg.append(f'<line x1="{sky_x + sky_w/2}" y1="{sky_y - sky_h/2}" x2="{sky_x - sky_w/2}" y2="{sky_y + sky_h/2}" class="skylight-x"/>')
            skylights_svg.append(f'<text x="{sky_x}" y="{sky_y + sky_h/2 + 300}" class="annotation" text-anchor="middle">SKYLIGHT</text>')
            skylights_svg.append(f'<text x="{sky_x}" y="{sky_y + sky_h/2 + 500}" class="annotation" text-anchor="middle">{sky_w} x {sky_h}</text>')

        return '\n'.join(skylights_svg)

    def _generate_gutters(self, overhang: float) -> str:
        """Generate gutters and downspouts."""
        gutters = ['<!-- Gutters and Downspouts -->']

        # Gutters along eaves (north and south for gable)
        gutters.append(f'<line x1="{-overhang}" y1="{-overhang}" x2="{self.width + overhang}" y2="{-overhang}" class="gutter"/>')
        gutters.append(f'<line x1="{-overhang}" y1="{self.depth + overhang}" x2="{self.width + overhang}" y2="{self.depth + overhang}" class="gutter"/>')

        # Downspouts at corners
        ds_positions = [
            (-overhang + 200, -overhang),
            (self.width + overhang - 200, -overhang),
            (-overhang + 200, self.depth + overhang),
            (self.width + overhang - 200, self.depth + overhang)
        ]

        for x, y in ds_positions:
            gutters.append(f'<circle cx="{x}" cy="{y}" r="100" class="downspout"/>')
            # DS label
            label_y = y - 300 if y < self.depth/2 else y + 350
            gutters.append(f'<text x="{x}" y="{label_y}" class="annotation" text-anchor="middle">DS</text>')

        return '\n'.join(gutters)

    def _generate_roof_dimensions(self, overhang: float) -> str:
        """Generate roof dimensions."""
        dims = ['<!-- Roof Dimensions -->']

        roof_width = self.width + 2 * overhang
        roof_depth = self.depth + 2 * overhang

        # Overall width with overhang (top)
        dims.append(self._dim_line(-overhang, -overhang - 800, self.width + overhang, -overhang - 800, roof_width))
        dims.append(f'<text x="{self.width/2}" y="{-overhang - 1100}" class="annotation" text-anchor="middle">(incl. {int(overhang)}mm overhang)</text>')

        # Overall depth with overhang (right side)
        dims.append(self._dim_line_v(self.width + overhang + 800, -overhang, self.depth + overhang, roof_depth))

        # Building width (interior dimension line)
        dims.append(self._dim_line(0, -overhang - 1600, self.width, -overhang - 1600, self.width))

        return '\n'.join(dims)

    def _generate_roof_legend(self, x: float, y: float) -> str:
        """Generate roof plan legend."""
        return f'''<!-- Legend -->
<g transform="translate({x}, {y})">
  <text x="0" y="0" class="legend-title">LEGEND:</text>

  <line x1="0" y1="350" x2="400" y2="350" class="ridge"/>
  <text x="500" y="380" class="legend-text">Ridge</text>

  <line x1="0" y1="550" x2="400" y2="550" class="eave"/>
  <text x="500" y="580" class="legend-text">Eave</text>

  <line x1="0" y1="750" x2="400" y2="750" class="rake"/>
  <text x="500" y="780" class="legend-text">Rake</text>

  <line x1="0" y1="950" x2="400" y2="950" class="hip"/>
  <text x="500" y="980" class="legend-text">Hip/Valley</text>

  <line x1="0" y1="1150" x2="400" y2="1150" class="gutter"/>
  <text x="500" y="1180" class="legend-text">Gutter</text>

  <line x1="0" y1="1350" x2="400" y2="1350" class="drainage" marker-end="url(#arrow-drain)"/>
  <text x="500" y="1380" class="legend-text">Drainage</text>

  <circle cx="80" cy="1550" r="80" class="downspout"/>
  <text x="500" y="1580" class="legend-text">Downspout</text>
</g>'''

    def _generate_roof_areas(self, overhang: float, pitch: float) -> str:
        """Generate roof area calculations."""
        # Calculate actual roof area (accounting for slope)
        # Slope factor = sqrt(1 + (pitch/12)^2)
        slope_factor = math.sqrt(1 + (pitch/12)**2)

        # Plan area of each slope
        plan_area_per_slope = (self.width + 2*overhang) * (self.depth/2 + overhang) / 1_000_000  # m²
        actual_area_per_slope = plan_area_per_slope * slope_factor
        total_area = actual_area_per_slope * 2

        x = self.width/2 + 1500
        y = self.depth + overhang + 800

        return f'''<!-- Roof Areas -->
<g transform="translate({x}, {y})">
  <text x="0" y="0" class="legend-title">ROOF AREAS:</text>
  <text x="0" y="350" class="annotation">North Slope: {actual_area_per_slope:.1f} m&#178; ({pitch}:12 pitch)</text>
  <text x="0" y="550" class="annotation">South Slope: {actual_area_per_slope:.1f} m&#178; ({pitch}:12 pitch)</text>
  <text x="0" y="750" class="annotation">Total Roof Area: {total_area:.1f} m&#178;</text>
  <text x="0" y="950" class="annotation">Slope Factor: {slope_factor:.3f}</text>
</g>'''

    def _generate_grid_lines(self) -> str:
        """Generate structural grid with bubbles."""
        lines = ['<!-- Grid Lines -->']

        # Determine grid positions based on walls
        x_grids = sorted(set([0, self.width]))
        z_grids = sorted(set([0, self.depth]))

        # Add interior wall positions
        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            if geom['is_vertical'] and wall.category == 'interior':
                x_grids.append(geom['start_x'])
            if geom['is_horizontal'] and wall.category == 'interior':
                z_grids.append(geom['start_z'])

        x_grids = sorted(set(x_grids))
        z_grids = sorted(set(z_grids))

        # Vertical grid lines (letters A, B, C...)
        for i, x in enumerate(x_grids):
            label = chr(65 + i)  # A, B, C...
            lines.append(f'<line x1="{x}" y1="-2000" x2="{x}" y2="{self.depth + 1000}" class="grid-line"/>')
            # Top bubble
            lines.append(f'<circle cx="{x}" cy="-2500" r="280" class="grid-bubble"/>')
            lines.append(f'<text x="{x}" y="-2500" class="grid-label">{label}</text>')

        # Horizontal grid lines (numbers 1, 2, 3...)
        for i, z in enumerate(z_grids):
            label = str(i + 1)
            lines.append(f'<line x1="-2000" y1="{z}" x2="{self.width + 1000}" y2="{z}" class="grid-line"/>')
            # Left bubble
            lines.append(f'<circle cx="-2500" cy="{z}" r="280" class="grid-bubble"/>')
            lines.append(f'<text x="-2500" y="{z}" class="grid-label">{label}</text>')

        return '\n'.join(lines)

    def _generate_walls(self) -> str:
        """Generate walls as double lines (outline rectangles) per architectural convention."""
        walls_svg = ['<!-- Walls -->']

        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            thickness = self.ext_wall_thickness if wall.category == 'exterior' else self.int_wall_thickness

            css_class = 'wall-ext'
            if wall.category == 'interior':
                css_class = 'wall-int'
            elif wall.category == 'wet_wall':
                css_class = 'wall-wet'

            if geom['is_horizontal']:
                # Horizontal wall (runs along X axis)
                x = min(geom['start_x'], geom['end_x'])
                w = geom['length']
                y = geom['start_z'] - thickness/2
                h = thickness
            else:
                # Vertical wall (runs along Z axis)
                x = geom['start_x'] - thickness/2
                w = thickness
                y = min(geom['start_z'], geom['end_z'])
                h = geom['length']

            # Draw wall as outline rectangle (double lines) - no fill, just stroke
            walls_svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="{css_class}"/>')

        return '\n'.join(walls_svg)

    def _generate_openings(self) -> str:
        """Generate white rectangles to cut openings in walls."""
        openings = ['<!-- Openings -->']

        # Door openings
        for door in self.doors:
            if door.wall_index < len(self.walls):
                wall = self.walls[door.wall_index]
                x, y, w, h = self._get_opening_position(wall, door.offset, door.width)
                openings.append(f'<rect x="{x}" y="{y - 50}" width="{w}" height="{h + 100}" class="opening"/>')

        # Window openings (windows are in the wall, so we don't cut through)
        # But we do need to show them differently

        return '\n'.join(openings)

    def _generate_door_symbols(self) -> str:
        """Generate proper door symbols with swing arcs.

        Standard door symbol convention:
        - Hinge is at one end of the door opening
        - Door panel is shown as a line from hinge, swinging 90 degrees into the room
        - Arc shows the path of the door edge from closed to open position
        """
        doors_svg = ['<!-- Door Symbols -->']

        for door in self.doors:
            if door.wall_index >= len(self.walls):
                continue

            wall = self.walls[door.wall_index]
            geom = self._get_wall_geometry(wall)
            thickness = self.ext_wall_thickness if wall.category == 'exterior' else self.int_wall_thickness

            if geom['is_horizontal']:
                # Door in horizontal wall (wall runs along X axis)
                door_center_x = min(geom['start_x'], geom['end_x']) + door.offset
                door_y = geom['start_z']

                # Hinge position (left or right side of opening)
                if 'left' in door.swing:
                    hinge_x = door_center_x - door.width / 2
                    leaf_end_x = door_center_x + door.width / 2  # Where the door edge starts in opening
                else:
                    hinge_x = door_center_x + door.width / 2
                    leaf_end_x = door_center_x - door.width / 2

                # Swing direction (in = positive Y, out = negative Y)
                if 'in' in door.swing or door.swing == 'left':
                    swing_dir = 1  # Into room (positive Y)
                else:
                    swing_dir = -1  # Out of room (negative Y)

                # Door panel - line from hinge perpendicular into room
                panel_end_y = door_y + swing_dir * door.width
                doors_svg.append(f'<line x1="{hinge_x}" y1="{door_y}" x2="{hinge_x}" y2="{panel_end_y}" class="door-leaf"/>')

                # Swing arc - from the other edge of opening to where the door panel ends
                # Arc is 90 degrees from where door would be when closed (in wall) to open position
                if 'left' in door.swing:
                    # Left hinge - arc sweeps from right edge to panel end
                    if swing_dir > 0:
                        doors_svg.append(f'<path d="M {leaf_end_x},{door_y} A {door.width},{door.width} 0 0 1 {hinge_x},{panel_end_y}" class="door-swing"/>')
                    else:
                        doors_svg.append(f'<path d="M {leaf_end_x},{door_y} A {door.width},{door.width} 0 0 0 {hinge_x},{panel_end_y}" class="door-swing"/>')
                else:
                    # Right hinge - arc sweeps from left edge to panel end
                    if swing_dir > 0:
                        doors_svg.append(f'<path d="M {leaf_end_x},{door_y} A {door.width},{door.width} 0 0 0 {hinge_x},{panel_end_y}" class="door-swing"/>')
                    else:
                        doors_svg.append(f'<path d="M {leaf_end_x},{door_y} A {door.width},{door.width} 0 0 1 {hinge_x},{panel_end_y}" class="door-swing"/>')

            else:
                # Door in vertical wall (wall runs along Z axis)
                door_x = geom['start_x']
                door_center_y = min(geom['start_z'], geom['end_z']) + door.offset

                # Hinge position
                if 'left' in door.swing:
                    hinge_y = door_center_y - door.width / 2
                    leaf_end_y = door_center_y + door.width / 2
                else:
                    hinge_y = door_center_y + door.width / 2
                    leaf_end_y = door_center_y - door.width / 2

                # Swing direction (assume swing into positive X for vertical walls)
                if 'in' in door.swing:
                    swing_dir = 1
                else:
                    swing_dir = -1

                # Door panel
                panel_end_x = door_x + swing_dir * door.width
                doors_svg.append(f'<line x1="{door_x}" y1="{hinge_y}" x2="{panel_end_x}" y2="{hinge_y}" class="door-leaf"/>')

                # Swing arc
                if 'left' in door.swing:
                    if swing_dir > 0:
                        doors_svg.append(f'<path d="M {door_x},{leaf_end_y} A {door.width},{door.width} 0 0 0 {panel_end_x},{hinge_y}" class="door-swing"/>')
                    else:
                        doors_svg.append(f'<path d="M {door_x},{leaf_end_y} A {door.width},{door.width} 0 0 1 {panel_end_x},{hinge_y}" class="door-swing"/>')
                else:
                    if swing_dir > 0:
                        doors_svg.append(f'<path d="M {door_x},{leaf_end_y} A {door.width},{door.width} 0 0 1 {panel_end_x},{hinge_y}" class="door-swing"/>')
                    else:
                        doors_svg.append(f'<path d="M {door_x},{leaf_end_y} A {door.width},{door.width} 0 0 0 {panel_end_x},{hinge_y}" class="door-swing"/>')

            # Pocket/sliding doors shown as dashed lines in opening
            if door.door_type == 'pocket' or door.door_type == 'sliding':
                if geom['is_horizontal']:
                    x1 = door_center_x - door.width / 2
                    x2 = door_center_x + door.width / 2
                    doors_svg.append(f'<line x1="{x1}" y1="{door_y}" x2="{x2}" y2="{door_y}" stroke="#000" stroke-width="3" stroke-dasharray="40,20"/>')
                else:
                    y1 = door_center_y - door.width / 2
                    y2 = door_center_y + door.width / 2
                    doors_svg.append(f'<line x1="{door_x}" y1="{y1}" x2="{door_x}" y2="{y2}" stroke="#000" stroke-width="3" stroke-dasharray="40,20"/>')

        return '\n'.join(doors_svg)

    def _generate_window_symbols(self) -> str:
        """Generate window symbols."""
        windows_svg = ['<!-- Window Symbols -->']

        for window in self.windows:
            if window.wall_index >= len(self.walls):
                continue

            wall = self.walls[window.wall_index]
            geom = self._get_wall_geometry(wall)
            thickness = self.ext_wall_thickness if wall.category == 'exterior' else self.int_wall_thickness

            if geom['is_horizontal']:
                win_x = min(geom['start_x'], geom['end_x']) + window.offset - window.width/2
                win_y = geom['start_z'] - thickness/2
                windows_svg.append(f'<rect x="{win_x}" y="{win_y}" width="{window.width}" height="{thickness}" class="window"/>')
                # Glass lines
                windows_svg.append(f'<line x1="{win_x}" y1="{geom["start_z"]}" x2="{win_x + window.width}" y2="{geom["start_z"]}" class="window-glass"/>')
            else:
                win_x = geom['start_x'] - thickness/2
                win_y = min(geom['start_z'], geom['end_z']) + window.offset - window.width/2
                windows_svg.append(f'<rect x="{win_x}" y="{win_y}" width="{thickness}" height="{window.width}" class="window"/>')
                # Glass lines
                windows_svg.append(f'<line x1="{geom["start_x"]}" y1="{win_y}" x2="{geom["start_x"]}" y2="{win_y + window.width}" class="window-glass"/>')

        return '\n'.join(windows_svg)

    def _generate_room_labels(self) -> str:
        """Generate room labels with areas.

        Room centers use x and z coordinates (plan view coordinates).
        In the JSON, 'center' may have 'x', 'y' (height), and 'z' keys,
        or it may use 'x' and 'y' for plan coordinates. We try both.
        """
        labels = ['<!-- Room Labels -->']

        for room_id, room in self.rooms.items():
            if room.center:
                # Try to get center coordinates - handle both naming conventions
                cx = room.center.get('x', 0)
                # Use 'z' if available (3D convention), otherwise 'y' (2D plan convention)
                cz = room.center.get('z', room.center.get('y', 0))

                # Convert area from mm² to m²
                area_m2 = room.area / 1_000_000 if room.area > 10000 else room.area

                labels.append(f'<text x="{cx}" y="{cz - 150}" class="room-label">{room.name.upper()}</text>')
                if area_m2 > 0:
                    labels.append(f'<text x="{cx}" y="{cz + 200}" class="room-area">{area_m2:.1f} m&#178;</text>')

            elif room.bounds:
                # Calculate center from bounds
                bounds = room.bounds
                cx = bounds.get('x', 0) + bounds.get('width', 0) / 2
                cz = bounds.get('y', 0) + bounds.get('height', 0) / 2  # 'y' is Z in plan

                # Convert area from mm² to m²
                area_m2 = room.area / 1_000_000 if room.area > 10000 else room.area

                labels.append(f'<text x="{cx}" y="{cz - 150}" class="room-label">{room.name.upper()}</text>')
                if area_m2 > 0:
                    labels.append(f'<text x="{cx}" y="{cz + 200}" class="room-area">{area_m2:.1f} m&#178;</text>')

        return '\n'.join(labels)

    def _generate_ladder_dimensions(self) -> str:
        """Generate ladder dimensions (detail, wall, overall)."""
        dims = ['<!-- Ladder Dimensions -->']

        # South side dimensions (3 layers)
        # Layer 1: Detail (closest) at y = -600
        # Layer 2: Wall-to-wall at y = -1200
        # Layer 3: Overall at y = -1800

        # Find all break points along south wall
        x_breaks = [0, self.width]

        # Add door/window positions
        for door in self.doors:
            if door.wall_index < len(self.walls):
                wall = self.walls[door.wall_index]
                geom = self._get_wall_geometry(wall)
                if geom['is_horizontal'] and geom['start_z'] == 0:
                    x_breaks.append(door.offset - door.width/2)
                    x_breaks.append(door.offset + door.width/2)

        for window in self.windows:
            if window.wall_index < len(self.walls):
                wall = self.walls[window.wall_index]
                geom = self._get_wall_geometry(wall)
                if geom['is_horizontal'] and geom['start_z'] == 0:
                    x_breaks.append(window.offset - window.width/2)
                    x_breaks.append(window.offset + window.width/2)

        # Add interior wall positions
        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            if geom['is_vertical'] and wall.category != 'exterior':
                if geom['start_z'] <= 100:  # Connects to south wall
                    x_breaks.append(geom['start_x'])

        x_breaks = sorted(set(x_breaks))

        # Layer 1: Detail dimensions
        for i in range(len(x_breaks) - 1):
            x1, x2 = x_breaks[i], x_breaks[i + 1]
            if x2 - x1 > 100:  # Skip tiny segments
                dims.append(self._dim_line(x1, -600, x2, -600, x2 - x1))

        # Layer 2: Major breaks (walls)
        wall_x = [0]
        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            if geom['is_vertical']:
                wall_x.append(geom['start_x'])
        wall_x.append(self.width)
        wall_x = sorted(set(wall_x))

        for i in range(len(wall_x) - 1):
            x1, x2 = wall_x[i], wall_x[i + 1]
            dims.append(self._dim_line(x1, -1200, x2, -1200, x2 - x1))

        # Layer 3: Overall
        dims.append(self._dim_line(0, -1800, self.width, -1800, self.width))

        # East side dimensions
        z_breaks = [0, self.depth]
        for wall in self.walls:
            geom = self._get_wall_geometry(wall)
            if geom['is_horizontal'] and wall.category != 'exterior':
                z_breaks.append(geom['start_z'])
        z_breaks = sorted(set(z_breaks))

        # Layer 2 (walls) on east side
        for i in range(len(z_breaks) - 1):
            z1, z2 = z_breaks[i], z_breaks[i + 1]
            dims.append(self._dim_line_v(self.width + 1200, z1, z2, z2 - z1))

        # Layer 3 (overall) on east side
        dims.append(self._dim_line_v(self.width + 1800, 0, self.depth, self.depth))

        return '\n'.join(dims)

    def _dim_line(self, x1: float, y: float, x2: float, y2: float, value: float) -> str:
        """Generate a horizontal dimension line with ticks and text."""
        return f'''<g>
  <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" class="dim-line"/>
  <line x1="{x1}" y1="{y + 100}" x2="{x1}" y2="{y - 100}" class="dim-ext"/>
  <line x1="{x2}" y1="{y + 100}" x2="{x2}" y2="{y - 100}" class="dim-ext"/>
  <text x="{(x1 + x2)/2}" y="{y - 50}" class="dim-text">{int(value)}</text>
</g>'''

    def _dim_line_v(self, x: float, z1: float, z2: float, value: float) -> str:
        """Generate a vertical dimension line."""
        return f'''<g>
  <line x1="{x}" y1="{z1}" x2="{x}" y2="{z2}" class="dim-line"/>
  <line x1="{x - 100}" y1="{z1}" x2="{x + 100}" y2="{z1}" class="dim-ext"/>
  <line x1="{x - 100}" y1="{z2}" x2="{x + 100}" y2="{z2}" class="dim-ext"/>
  <text x="{x + 50}" y="{(z1 + z2)/2}" class="dim-text" writing-mode="tb">{int(value)}</text>
</g>'''

    def _generate_north_arrow(self, x: float, y: float) -> str:
        """Generate north arrow symbol."""
        return f'''<!-- North Arrow -->
<g transform="translate({x}, {y})">
  <circle cx="0" cy="0" r="400" fill="none" stroke="#000" stroke-width="4"/>
  <polygon points="0,-300 -80,200 0,80 80,200" fill="black"/>
  <text x="0" y="-450" class="grid-label" text-anchor="middle">N</text>
</g>'''

    def _generate_scale_bar(self, x: float, y: float) -> str:
        """Generate scale bar."""
        return f'''<!-- Scale Bar -->
<g transform="translate({x}, {y})">
  <text x="0" y="-80" style="font: 180px Arial;">SCALE 1:100</text>
  <rect x="0" y="0" width="1000" height="80" fill="black"/>
  <rect x="1000" y="0" width="1000" height="80" fill="white" stroke="black" stroke-width="2"/>
  <text x="0" y="180" style="font: 140px Arial;">0</text>
  <text x="1000" y="180" style="font: 140px Arial;">1m</text>
  <text x="2000" y="180" style="font: 140px Arial;">2m</text>
</g>'''


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Generate floor and roof plans from building JSON')
    parser.add_argument('input', nargs='?',
                        default='../../Shared/TestData/output/generated_building.json',
                        help='Input JSON file path')
    parser.add_argument('-o', '--output',
                        default='../../Shared/TestData/output',
                        help='Output directory for SVG files')
    parser.add_argument('-s', '--scale', type=float, default=0.05,
                        help='Scale factor (default: 0.05)')

    args = parser.parse_args()

    json_path = Path(args.input)
    if not json_path.is_absolute():
        json_path = Path(__file__).parent / json_path

    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = Path(__file__).parent / output_dir

    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        return 1

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating plans from: {json_path}")

    generator = PlanGenerator(str(json_path))

    # Generate floor plan
    floor_plan_svg = generator.generate_floor_plan_svg(scale=args.scale)
    floor_plan_path = output_dir / "floor_plan.svg"
    with open(floor_plan_path, 'w', encoding='utf-8') as f:
        f.write(floor_plan_svg)
    print(f"  Floor plan: {floor_plan_path}")

    # Generate roof plan
    roof_plan_svg = generator.generate_roof_plan_svg(scale=args.scale)
    roof_plan_path = output_dir / "roof_plan.svg"
    with open(roof_plan_path, 'w', encoding='utf-8') as f:
        f.write(roof_plan_svg)
    print(f"  Roof plan:  {roof_plan_path}")

    print("Done!")
    return 0


if __name__ == "__main__":
    exit(main())
