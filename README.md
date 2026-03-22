# Archengine - Generative CAD for Residential Construction

Permit-ready drawing generation from simple inputs. No manual drafting required.

## Quick Start

### 1. Generate a Complete Permit Drawing Set (9 Sheets)

```bash
cd /root/ArchEngine
python permit_drawing_set.py
```

This creates:
- **01_site_plan.svg** — Lot, setbacks, driveway, north arrow
- **02_floor_plan.svg** — Floor plan with 4-tier intelligent dimensions
- **03-06_elevation_*.svg** — North, South, East, West elevations with materials
- **04_section_aa.svg** — Transverse section through building center
- **05_door_schedule.svg** — Door schedule table
- **05_window_schedule.svg** — Window schedule table

Output location: `test_pipeline/permit_set/`

### 2. Use the GUI (Optional)

```bash
pip install PyQt6
python archengine_gui.py
```

GUI inputs:
- Site address, lot dimensions, setbacks
- Building type, target area, room counts
- Generate button → complete drawing set

### 3. API Server (Headless)

```bash
cd headless
python api_server.py

# Then POST to /solve_building
curl -X POST http://localhost:8000/solve_building \
  -H "Content-Type: application/json" \
  -d '{
    "structure_type": "residential",
    "target_area_m2": 150,
    "width_m": 12,
    "depth_m": 13,
    "max_rooms": 15,
    "floor": 0
  }'
```

## Input Format

### Minimal Input (Building JSON)

```json
{
  "name": "My House",
  "structure_type": "residential",
  "target_area_m2": 150,
  "width_m": 12,
  "depth_m": 13,
  "rooms": [
    {"id": "kitchen", "name": "Kitchen", "min_area_m2": 12, "preferred_aspect": "square"},
    {"id": "living", "name": "Living Room", "min_area_m2": 20, "preferred_aspect": "wide"}
  ],
  "walls": [...],
  "doors": [...],
  "windows": [...]
}
```

### Full Solver Pipeline

```python
from headless.api_server import solve_building

result = solve_building({
    "structure_type": "residential",
    "target_area_m2": 150,
    "width_m": 12,
    "depth_m": 13,
    "solver_type": "grid"  # or "wave_collapse", "tree", "hybrid"
})

# result contains:
# - rooms: placed rooms with positions
# - walls: generated wall segments
# - openings: doors and windows
# - svg_url: path to generated floor plan
```

## Key Features

### 4-Tier Intelligent Dimensioning

The floor plan includes architectural-standard dimensions:

| Tier | Location | Example |
|------|----------|---------|
| **OVERALL** | Outside building | 13.4 m (full envelope) |
| **STRUCTURAL** | Outside, closer | 3.0 m, 2.4 m (wall grid) |
| **OPENING** | Centered on opening | 929 mm (door), 1219 mm (window) |
| **INTERIOR** | Inside rooms | 4.9 m × 4.9 m (room size) |

### 9 Integrated Solvers

- `grid` — Grid-based room placement
- `wave_collapse` — WFC constraint solving
- `tree` — Tree-structured branching
- `perfect_adjacency` — Graph-based adjacency
- `constraint` — CSP solver
- `genetic` — Genetic algorithm optimization
- `annealing` — Simulated annealing
- `force_directed` — Force-directed layout
- `space_colonization` — Growth-based placement
- `hybrid` — Combines multiple approaches

### Layout Refiner

Post-solver pass that:
- Removes walls between adjacent spaces (open plan)
- Adds doors between connected rooms
- Places windows on exterior walls
- Applies design fragments (PRIVATE_WING, EFFICIENT_CIRCULATION, etc.)

## Output Formats

| Format | Use Case | Command |
|--------|----------|---------|
| **SVG** | Permit submission, editing | Default output |
| **PDF** | Professional printing | `pdf_exporter.py` |
| **JSON** — 3D viewer, AR | `api_server.py` output |

### SVG to PDF

```python
from ArchEngine_CAD.exports.pdf_exporter import export_floor_plan_pdf

export_floor_plan_pdf(
    svg_path="floor_plan.svg",
    pdf_path="floor_plan.pdf",
    paper_size="ARCH_D"  # 24"×36" for permits
)
```

## File Structure

```
/root/ArchEngine/
├── archengine_gui.py              ← GUI frontend (PyQt6)
├── permit_drawing_set.py          ← Complete permit set generator
├── ArchEngine_kernel/
│   └── scripts/
│       ├── generate_elevations.py ← 4 elevations with materials
│       ├── generate_sections.py   ← Section drawings
│       ├── generate_schedules.py  ← Door/window schedules
│       ├── generate_plans.py      ← Floor plan with dimensions
│       ├── generate_site_plan.py  ← Site plan generator
│       └── intelligent_dimensions.py ← 4-tier dimensioning
├── headless/
│   └── api_server.py              ← FastAPI server
└── ArchEngine_CAD/
    └── exports/
        └── pdf_exporter.py        ← PDF export bridge
```

## Permit Submission Checklist

- [x] Site plan with setbacks and north arrow
- [x] Floor plan with dimensions (4-tier)
- [x] 4 elevations (N, S, E, W)
- [x] Section drawing
- [x] Door schedule
- [x] Window schedule

All generated automatically from your inputs.

## Troubleshooting

### "No module named 'PyQt6'"
```bash
pip install PyQt6
```

### "No module named 'reportlab'"
```bash
pip install reportlab svglib
```

### Elevations show no roof
Fixed in latest version — roofs now generate from building bounds if vertex data missing.

### Dimensions don't align
Fixed — dimensions now use raw mm coordinates (identity transform) matching wall geometry.

## Next Steps / Roadmap

- [ ] Vulkan viewer integration (3D walkthrough)
- [ ] Section box tool (interactive cutting planes)
- [ ] Elevation depth adjustment (clipping planes for protruded faces)
- [ ] PDF batch export (all 9 sheets)
- [ ] Topography import for site plans

## License

Copyright (c) 2026 Legible Studios
