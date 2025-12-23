#!/usr/bin/env python3
"""
generate_schedules.py - Generate architectural schedule drawings

Creates schedule sheets showing:
- Door schedule (sizes, types, hardware)
- Window schedule (sizes, types, glazing)
- Room finish schedule (floor, wall, ceiling finishes)
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from title_block import generate_title_block, get_project_info_from_json

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DoorEntry:
    """Door schedule entry."""
    mark: str
    room: str
    width: int
    height: int
    door_type: str
    frame: str
    hardware: str
    remarks: str = ""

@dataclass
class WindowEntry:
    """Window schedule entry."""
    mark: str
    room: str
    width: int
    height: int
    sill_height: int
    window_type: str
    glazing: str
    remarks: str = ""

@dataclass
class RoomFinishEntry:
    """Room finish schedule entry."""
    number: str
    name: str
    floor: str
    base: str
    walls: str
    ceiling: str
    ceiling_height: str
    remarks: str = ""

# =============================================================================
# SCHEDULE EXTRACTION
# =============================================================================

def extract_door_schedule(data: Dict) -> List[DoorEntry]:
    """Extract door information from building JSON."""
    doors = data.get('doors', [])
    walls = data.get('walls_batch', [])
    rooms = data.get('rooms', {})

    entries = []
    door_marks = {}  # Track unique door sizes for marks

    for i, door in enumerate(doors):
        width = int(door.get('width', 900))
        height = int(door.get('height', 2100))

        # Generate mark based on size
        size_key = f"{width}x{height}"
        if size_key not in door_marks:
            door_marks[size_key] = chr(65 + len(door_marks))  # A, B, C...
        mark = door_marks[size_key]

        # Find associated room
        wall_idx = door.get('wall_index', -1)
        room_name = "-"
        if wall_idx >= 0 and wall_idx < len(walls):
            wall = walls[wall_idx]
            # Try to find room from wall position
            for room_id, room_data in rooms.items():
                if 'bounds' in room_data:
                    room_name = room_data.get('name', room_id)
                    break

        # Determine door type
        if width >= 1500:
            door_type = "DOUBLE PANEL"
        elif width >= 900:
            door_type = "SINGLE PANEL"
        else:
            door_type = "POCKET"

        # Determine frame type based on wall category
        if wall_idx >= 0 and wall_idx < len(walls):
            wall = walls[wall_idx]
            if wall.get('category') == 'exterior':
                frame = "WOOD W/ WEATHERSTRIP"
                hardware = "ENTRY LOCKSET"
            else:
                frame = "WOOD"
                hardware = "PASSAGE SET"
        else:
            frame = "WOOD"
            hardware = "PASSAGE SET"

        entries.append(DoorEntry(
            mark=mark,
            room=room_name,
            width=width,
            height=height,
            door_type=door_type,
            frame=frame,
            hardware=hardware
        ))

    return entries


def extract_window_schedule(data: Dict) -> List[WindowEntry]:
    """Extract window information from building JSON."""
    windows = data.get('windows', [])
    walls = data.get('walls_batch', [])
    rooms = data.get('rooms', {})

    entries = []
    window_marks = {}  # Track unique window sizes for marks

    for i, window in enumerate(windows):
        width = int(window.get('width', 1200))
        height = int(window.get('height', 1200))
        sill = int(window.get('sill_height', 900))

        # Generate mark based on size
        size_key = f"{width}x{height}"
        if size_key not in window_marks:
            window_marks[size_key] = str(len(window_marks) + 1)  # 1, 2, 3...
        mark = window_marks[size_key]

        # Find associated room
        wall_idx = window.get('wall_index', -1)
        room_name = "-"

        # Determine window type based on size
        if width >= 1800:
            window_type = "PICTURE"
            glazing = "FIXED"
        elif width >= 1200:
            window_type = "DOUBLE HUNG"
            glazing = "INSULATED"
        elif height > width:
            window_type = "CASEMENT"
            glazing = "INSULATED"
        else:
            window_type = "SLIDER"
            glazing = "INSULATED"

        entries.append(WindowEntry(
            mark=mark,
            room=room_name,
            width=width,
            height=height,
            sill_height=sill,
            window_type=window_type,
            glazing=glazing
        ))

    return entries


def extract_room_finish_schedule(data: Dict) -> List[RoomFinishEntry]:
    """Extract room finish information from building JSON."""
    rooms = data.get('rooms', {})
    walls = data.get('walls_batch', [])

    # Default ceiling height
    default_height = 2700
    if walls:
        default_height = walls[0].get('height', 2700)

    entries = []
    room_number = 100

    # Define typical finishes by room type
    finish_map = {
        'living': ('HARDWOOD', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'bedroom': ('CARPET', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'primary': ('CARPET', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'kitchen': ('TILE', '4" TILE', 'PAINT', 'GYP. BD.'),
        'bath': ('TILE', '4" TILE', 'TILE', 'GYP. BD.'),
        'hallway': ('HARDWOOD', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'entry': ('TILE', '4" TILE', 'PAINT', 'GYP. BD.'),
        'garage': ('CONCRETE', 'NONE', 'PAINT', 'EXPOSED'),
        'laundry': ('TILE', '4" TILE', 'PAINT', 'GYP. BD.'),
        'closet': ('CARPET', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'dining': ('HARDWOOD', '4" WOOD', 'PAINT', 'GYP. BD.'),
        'office': ('CARPET', '4" WOOD', 'PAINT', 'GYP. BD.'),
    }

    for room_id, room_data in rooms.items():
        name = room_data.get('name', room_id).upper()

        # Look up finishes based on room type
        room_lower = name.lower()
        floor, base, walls_finish, ceiling = ('CARPET', '4" WOOD', 'PAINT', 'GYP. BD.')

        for key, finishes in finish_map.items():
            if key in room_lower:
                floor, base, walls_finish, ceiling = finishes
                break

        # Get ceiling height
        height = room_data.get('ceiling_height', default_height)
        height_str = f"{int(height)}mm ({height/304.8:.1f}')"

        entries.append(RoomFinishEntry(
            number=str(room_number),
            name=name,
            floor=floor,
            base=base,
            walls=walls_finish,
            ceiling=ceiling,
            ceiling_height=height_str
        ))

        room_number += 1

    return entries


# =============================================================================
# SVG TABLE RENDERER
# =============================================================================

def render_table(
    title: str,
    headers: List[str],
    rows: List[List[str]],
    col_widths: List[int],
    x: float,
    y: float,
    row_height: float = 300
) -> str:
    """Render a schedule table as SVG."""

    lines = []
    total_width = sum(col_widths)
    header_height = row_height * 1.2

    # Table title
    lines.append(f'<text x="{x + total_width/2}" y="{y - 150}" font-family="Arial" font-size="180" font-weight="bold" text-anchor="middle">{title}</text>')

    # Header row background
    lines.append(f'<rect x="{x}" y="{y}" width="{total_width}" height="{header_height}" fill="#E8E8E8" stroke="#000" stroke-width="2"/>')

    # Header cells
    current_x = x
    for i, (header, width) in enumerate(zip(headers, col_widths)):
        # Vertical line
        if i > 0:
            lines.append(f'<line x1="{current_x}" y1="{y}" x2="{current_x}" y2="{y + header_height + len(rows) * row_height}" stroke="#000" stroke-width="1"/>')

        # Header text
        lines.append(f'<text x="{current_x + width/2}" y="{y + header_height/2 + 50}" font-family="Arial" font-size="100" font-weight="bold" text-anchor="middle">{header}</text>')
        current_x += width

    # Header bottom line
    lines.append(f'<line x1="{x}" y1="{y + header_height}" x2="{x + total_width}" y2="{y + header_height}" stroke="#000" stroke-width="2"/>')

    # Data rows
    for row_idx, row in enumerate(rows):
        row_y = y + header_height + row_idx * row_height

        # Alternating row background
        if row_idx % 2 == 1:
            lines.append(f'<rect x="{x}" y="{row_y}" width="{total_width}" height="{row_height}" fill="#F8F8F8" stroke="none"/>')

        # Row bottom line
        lines.append(f'<line x1="{x}" y1="{row_y + row_height}" x2="{x + total_width}" y2="{row_y + row_height}" stroke="#000" stroke-width="0.5"/>')

        # Cell data
        current_x = x
        for cell, width in zip(row, col_widths):
            lines.append(f'<text x="{current_x + width/2}" y="{row_y + row_height/2 + 35}" font-family="Arial" font-size="90" text-anchor="middle">{cell}</text>')
            current_x += width

    # Table outline
    table_height = header_height + len(rows) * row_height
    lines.append(f'<rect x="{x}" y="{y}" width="{total_width}" height="{table_height}" fill="none" stroke="#000" stroke-width="2"/>')

    return '\n'.join(lines)


# =============================================================================
# SVG RENDERER
# =============================================================================

def render_schedules_svg(
    door_schedule: List[DoorEntry],
    window_schedule: List[WindowEntry],
    room_schedule: List[RoomFinishEntry],
    project_info: Dict = None
) -> str:
    """Render all schedules to a single SVG sheet."""

    # Sheet dimensions
    margin = 500
    sheet_width = 16000
    sheet_height = 12000

    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg"')
    lines.append(f'     width="1000" height="750"')
    lines.append(f'     viewBox="0 0 {sheet_width} {sheet_height}">')

    # Background
    lines.append('<rect width="100%" height="100%" fill="white"/>')

    # Styles
    lines.append('''<style>
    .sheet-title { font-family: Arial, sans-serif; font-size: 250px; font-weight: bold; fill: #333; }
</style>''')

    # Sheet title
    lines.append(f'<text x="{sheet_width/2}" y="{margin}" text-anchor="middle" class="sheet-title">SCHEDULES</text>')

    # Door Schedule
    door_headers = ['MARK', 'LOCATION', 'WIDTH', 'HEIGHT', 'TYPE', 'FRAME', 'HARDWARE']
    door_widths = [500, 1200, 600, 600, 1000, 1200, 1000]
    door_rows = [[d.mark, d.room, f"{d.width}mm", f"{d.height}mm", d.door_type, d.frame, d.hardware] for d in door_schedule]

    if door_rows:
        door_table = render_table("DOOR SCHEDULE", door_headers, door_rows, door_widths, margin + 200, margin + 800)
        lines.append(door_table)

    # Window Schedule
    window_headers = ['MARK', 'WIDTH', 'HEIGHT', 'SILL HT', 'TYPE', 'GLAZING', 'REMARKS']
    window_widths = [400, 600, 600, 600, 1000, 800, 800]
    window_rows = [[w.mark, f"{w.width}mm", f"{w.height}mm", f"{w.sill_height}mm", w.window_type, w.glazing, w.remarks if w.remarks else "-"] for w in window_schedule]

    if window_rows:
        # Position window schedule to the right of door schedule
        window_x = margin + 200 + sum(door_widths) + 800
        window_table = render_table("WINDOW SCHEDULE", window_headers, window_rows, window_widths, window_x, margin + 800)
        lines.append(window_table)

    # Room Finish Schedule (below door schedule)
    room_headers = ['NO.', 'ROOM NAME', 'FLOOR', 'BASE', 'WALLS', 'CEILING', 'CLG. HT.']
    room_widths = [400, 1400, 800, 600, 600, 700, 1000]
    room_rows = [[r.number, r.name, r.floor, r.base, r.walls, r.ceiling, r.ceiling_height] for r in room_schedule]

    if room_rows:
        # Calculate Y position based on door schedule size
        door_table_height = 360 + len(door_rows) * 300 + 400  # header + rows + spacing
        room_y = margin + 800 + door_table_height
        room_table = render_table("ROOM FINISH SCHEDULE", room_headers, room_rows, room_widths, margin + 200, room_y)
        lines.append(room_table)

    # Legend/Notes
    notes_y = sheet_height - 2000
    lines.append(f'<text x="{margin + 200}" y="{notes_y}" font-family="Arial" font-size="140" font-weight="bold">GENERAL NOTES:</text>')

    notes = [
        "1. ALL DIMENSIONS ARE IN MILLIMETERS UNLESS OTHERWISE NOTED.",
        "2. VERIFY ALL DIMENSIONS AND CONDITIONS IN FIELD BEFORE ORDERING.",
        "3. ALL DOORS TO HAVE SELF-CLOSING HINGES WHERE REQUIRED BY CODE.",
        "4. ALL EXTERIOR DOORS TO BE INSULATED WITH WEATHERSTRIPPING.",
        "5. ALL WINDOWS TO BE DOUBLE-GLAZED INSULATED UNITS.",
    ]

    for i, note in enumerate(notes):
        lines.append(f'<text x="{margin + 200}" y="{notes_y + 180 + i * 150}" font-family="Arial" font-size="100">{note}</text>')

    # Title block
    if project_info:
        drawing_info = {
            'title': 'DOOR, WINDOW & FINISH SCHEDULES',
            'number': 'A-601',
            'scale': 'NOT TO SCALE',
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

def generate_schedules(input_path: str, output_dir: str):
    """Generate schedule drawings from building JSON."""

    # Load building data
    with open(input_path, 'r') as f:
        data = json.load(f)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get project info
    project_info = get_project_info_from_json(data)

    # Extract schedules
    print("Generating schedules...")

    door_schedule = extract_door_schedule(data)
    print(f"  - {len(door_schedule)} doors")

    window_schedule = extract_window_schedule(data)
    print(f"  - {len(window_schedule)} windows")

    room_schedule = extract_room_finish_schedule(data)
    print(f"  - {len(room_schedule)} rooms")

    # Render to SVG
    svg = render_schedules_svg(door_schedule, window_schedule, room_schedule, project_info)

    out_file = output_path / "schedules.svg"
    with open(out_file, 'w') as f:
        f.write(svg)

    print(f"  Wrote {out_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate schedule drawings')
    parser.add_argument('input', nargs='?',
                        default='../../Shared/TestData/output/generated_building.json',
                        help='Input JSON file path')
    parser.add_argument('-o', '--output',
                        default='../../Shared/TestData/output',
                        help='Output directory for SVG files')

    args = parser.parse_args()

    generate_schedules(args.input, args.output)


if __name__ == '__main__':
    main()
