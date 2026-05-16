//! Elevation-sheet generator (one drawing per cardinal direction).
//!
//! Port of `ArchEngine_kernel/scripts/generate_elevations.py` (855 LOC),
//! scoped to the permit-drawing critical path: wall outline + openings
//! (doors/windows projected onto the elevation plane) + simple gable roof
//! profile + grade line + title. The Python's optional layers (materials,
//! detailed level markers, surface-based roof projection) are deferred.

use std::fmt::Write as _;

use glam::Vec3;

/// Which cardinal direction the viewer is looking from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    North,
    South,
    East,
    West,
}

impl Direction {
    fn as_str(self) -> &'static str {
        match self {
            Direction::North => "north",
            Direction::South => "south",
            Direction::East => "east",
            Direction::West => "west",
        }
    }
    fn label(self) -> &'static str {
        match self {
            Direction::North => "NORTH",
            Direction::South => "SOUTH",
            Direction::East => "EAST",
            Direction::West => "WEST",
        }
    }
    /// All four cardinal directions in the conventional order.
    pub const ALL: [Direction; 4] = [
        Direction::North,
        Direction::South,
        Direction::East,
        Direction::West,
    ];
}

/// Minimal wall description for elevation projection: centreline + height.
#[derive(Debug, Clone)]
pub struct ElevationWallInput {
    pub start: Vec3,
    pub end: Vec3,
    pub height: f32,
}

/// Door or window on a specific wall.
#[derive(Debug, Clone)]
pub struct ElevationOpeningInput {
    pub wall_index: usize,
    /// Distance along wall from start to opening centre, in mm.
    pub offset: f32,
    pub width: f32,
    pub height: f32,
    pub sill_height: f32,
    pub is_door: bool,
}

/// Building-level inputs for elevation generation.
#[derive(Debug, Clone, Default)]
pub struct ElevationInput {
    /// Building width in mm (X extent — used for South/North projection).
    pub width: f32,
    /// Building depth in mm (Z extent — used for East/West projection).
    pub depth: f32,
    pub walls: Vec<ElevationWallInput>,
    pub openings: Vec<ElevationOpeningInput>,
    /// If > 0, draw a simple gable-roof silhouette of this ridge height
    /// above the wall plate (mm). 0 disables.
    pub gable_ridge_above_plate: f32,
}

struct WallSegment {
    start_x: f32,
    end_x: f32,
    top_y: f32,
}

struct Opening {
    center_x: f32,
    width: f32,
    bottom_y: f32,
    top_y: f32,
    is_door: bool,
}

fn project_wall(wall: &ElevationWallInput, dir: Direction, input: &ElevationInput) -> WallSegment {
    let (s, e) = (wall.start, wall.end);
    let (mut start_x, mut end_x) = match dir {
        Direction::South | Direction::North => (s.x.min(e.x), s.x.max(e.x)),
        Direction::East | Direction::West => (s.z.min(e.z), s.z.max(e.z)),
    };
    if dir == Direction::North {
        let bw = input.width;
        let (a, b) = (bw - end_x, bw - start_x);
        start_x = a;
        end_x = b;
    } else if dir == Direction::East {
        let bd = input.depth;
        let (a, b) = (bd - end_x, bd - start_x);
        start_x = a;
        end_x = b;
    }
    WallSegment {
        start_x,
        end_x,
        top_y: s.y + wall.height,
    }
}

fn project_opening(
    op: &ElevationOpeningInput,
    wall: &ElevationWallInput,
    dir: Direction,
    input: &ElevationInput,
) -> Option<Opening> {
    let (s, e) = (wall.start, wall.end);
    let wall_dx = e.x - s.x;
    let wall_dz = e.z - s.z;
    let wall_len = (wall_dx * wall_dx + wall_dz * wall_dz).sqrt();
    if wall_len < 1.0 {
        return None;
    }
    let t = op.offset / wall_len;
    let opening_x = s.x + t * wall_dx;
    let opening_z = s.z + t * wall_dz;

    let mut center_x = match dir {
        Direction::South | Direction::North => opening_x,
        Direction::East | Direction::West => opening_z,
    };
    if dir == Direction::North {
        center_x = input.width - center_x;
    } else if dir == Direction::East {
        center_x = input.depth - center_x;
    }

    let sill = if op.is_door { 0.0 } else { op.sill_height };
    Some(Opening {
        center_x,
        width: op.width,
        bottom_y: sill,
        top_y: sill + op.height,
        is_door: op.is_door,
    })
}

/// Render an elevation drawing to an SVG string. `scale` is mm-to-pixels
/// (the Python default is 0.05, i.e. 1 px per 20 mm).
#[must_use]
#[allow(clippy::too_many_lines)]
pub fn generate_elevation_sheet_svg(input: &ElevationInput, dir: Direction, scale: f32) -> String {
    // Project all walls; keep those facing this direction by virtue of
    // having a horizontal extent. Walls aligned with the view direction
    // collapse to a vertical edge (start_x == end_x) and are filtered.
    let walls: Vec<WallSegment> = input
        .walls
        .iter()
        .map(|w| project_wall(w, dir, input))
        .filter(|w| (w.end_x - w.start_x).abs() > 1.0)
        .collect();

    // Project openings onto walls that survive projection. Openings on
    // collapsed walls don't appear in this view.
    let openings: Vec<Opening> = input
        .openings
        .iter()
        .filter_map(|op| {
            let wall = input.walls.get(op.wall_index)?;
            let projected_wall = project_wall(wall, dir, input);
            if (projected_wall.end_x - projected_wall.start_x).abs() < 1.0 {
                return None;
            }
            project_opening(op, wall, dir, input)
        })
        .collect();

    // Compute bounds across all elements (walls + openings + roof if any).
    let (mut min_x, mut max_x, mut min_y, mut max_y) =
        (f32::INFINITY, f32::NEG_INFINITY, 0.0_f32, f32::NEG_INFINITY);
    for w in &walls {
        min_x = min_x.min(w.start_x);
        max_x = max_x.max(w.end_x);
        max_y = max_y.max(w.top_y);
    }
    for op in &openings {
        max_y = max_y.max(op.top_y);
    }
    let gable_top_y = if input.gable_ridge_above_plate > 0.0 {
        let max_wall_top = walls.iter().map(|w| w.top_y).fold(0.0_f32, f32::max);
        max_wall_top + input.gable_ridge_above_plate
    } else {
        0.0
    };
    if gable_top_y > max_y {
        max_y = gable_top_y;
    }

    if !min_x.is_finite() {
        min_x = 0.0;
        max_x = match dir {
            Direction::South | Direction::North => input.width.max(10_000.0),
            Direction::East | Direction::West => input.depth.max(10_000.0),
        };
    }
    if !max_y.is_finite() || max_y <= 0.0 {
        max_y = 2700.0;
    }

    let margin_x = 1000.0_f32;
    let margin_y = 800.0_f32;
    let vb_x = min_x - margin_x;
    let vb_y = min_y - margin_y;
    let vb_w = (max_x - min_x) + 2.0 * margin_x;
    let vb_h = (max_y - min_y) + 2.0 * margin_y;

    #[allow(clippy::cast_possible_truncation)]
    let px_w = (vb_w * scale) as i32;
    #[allow(clippy::cast_possible_truncation)]
    let px_h = (vb_h * scale) as i32;

    let mut s = String::with_capacity(4096);
    s.push_str("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    let _ = writeln!(
        s,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{px_w}" height="{px_h}" viewBox="{vb_x} {vb_y} {vb_w} {vb_h}">"#,
    );
    let _ = writeln!(s, "  <title>{} Elevation</title>", dir.label());
    s.push_str("  <rect width=\"100%\" height=\"100%\" fill=\"white\"/>\n");

    // Styles.
    s.push_str("  <style>\n");
    s.push_str("    .wall-face { fill: #e8e4d8; stroke: #000; stroke-width: 4; }\n");
    s.push_str("    .opening { fill: white; stroke: #000; stroke-width: 3; }\n");
    s.push_str("    .door { fill: #c8c0b0; stroke: #000; stroke-width: 3; }\n");
    s.push_str("    .roof { fill: #888; stroke: #000; stroke-width: 4; }\n");
    s.push_str("    .grade { stroke: #666; stroke-width: 6; fill: none; }\n");
    s.push_str("    .title { font-family: Arial, sans-serif; font-size: 350px; font-weight: bold; fill: #333; }\n");
    s.push_str("    .label { font-family: Arial, sans-serif; font-size: 200px; fill: #333; }\n");
    s.push_str("  </style>\n");

    // Flip Y so 0 is at the bottom (grade) and ridges go up the page.
    let flip_y = max_y + min_y;
    let _ = writeln!(s, r#"<g transform="translate(0, {flip_y}) scale(1, -1)">"#);

    // Walls — single envelope rect spanning the elevation width.
    if !walls.is_empty() {
        let _ = writeln!(
            s,
            r#"    <rect x="{x}" y="0" width="{w}" height="{h}" class="wall-face"/>"#,
            x = min_x,
            w = max_x - min_x,
            h = max_y,
        );
    }

    // Gable roof silhouette (simple triangle peak above wall plate).
    if input.gable_ridge_above_plate > 0.0 && !walls.is_empty() {
        let plate_y = walls.iter().map(|w| w.top_y).fold(0.0_f32, f32::max);
        let cx = (min_x + max_x) * 0.5;
        let _ = writeln!(
            s,
            r#"    <polygon points="{min_x},{plate_y} {cx},{ridge} {max_x},{plate_y}" class="roof"/>"#,
            ridge = gable_top_y,
        );
    }

    // Openings — door (filled tinted) or window (white, no sill bar).
    for op in &openings {
        let class_attr = if op.is_door { "door" } else { "opening" };
        let _ = writeln!(
            s,
            r#"    <rect x="{x}" y="{yb}" width="{w}" height="{h}" class="{class_attr}"/>"#,
            x = op.center_x - op.width * 0.5,
            yb = op.bottom_y,
            w = op.width,
            h = op.top_y - op.bottom_y,
        );
    }

    // Grade line at Y=0.
    let _ = writeln!(
        s,
        r#"    <line x1="{x1}" y1="0" x2="{x2}" y2="0" class="grade"/>"#,
        x1 = min_x - 500.0,
        x2 = max_x + 500.0,
    );

    // Overall envelope dimensions (Tier-1): width along the bottom,
    // height along the left. Skip if the building bounds are degenerate.
    if max_x > min_x {
        let width_dim = crate::dimensions::LinearDim::horizontal_mm(min_x, max_x, -500.0);
        s.push_str(&crate::dimensions::render_horizontal(&width_dim, 250.0));
    }
    if max_y > 0.0 {
        let height_dim = crate::dimensions::LinearDim::vertical_mm(0.0, max_y, min_x - 500.0);
        s.push_str(&crate::dimensions::render_vertical(&height_dim, 250.0));
    }

    // Per-opening width dimensions (Tier-3): each door/window gets a
    // small width callout just below the elevation grade line.
    for op in &openings {
        let dim = crate::dimensions::LinearDim::horizontal_mm(
            op.center_x - op.width * 0.5,
            op.center_x + op.width * 0.5,
            -200.0,
        );
        s.push_str(&crate::dimensions::render_horizontal(&dim, 150.0));
    }

    s.push_str("  </g>\n");

    // Title (NOT flipped).
    let title_y = vb_y + vb_h - 200.0;
    let title_x = vb_x + vb_w * 0.5;
    let _ = writeln!(
        s,
        r#"  <text x="{title_x:.0}" y="{title_y}" text-anchor="middle" class="title">{label} ELEVATION</text>"#,
        label = dir.label(),
    );

    s.push_str("</svg>\n");
    s
}

/// Sheet number prefix for the elevation drawing — matches the Python
/// permit-set's naming convention (03_elevation_{direction}.svg).
#[must_use]
pub fn sheet_name(dir: Direction) -> String {
    format!("03_elevation_{}.svg", dir.as_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rectangular_input() -> ElevationInput {
        let mut input = ElevationInput {
            width: 5000.0,
            depth: 4000.0,
            gable_ridge_above_plate: 1200.0,
            ..Default::default()
        };
        for ((sx, sz), (ex, ez)) in [
            ((0.0, 0.0), (5000.0, 0.0)),
            ((5000.0, 0.0), (5000.0, 4000.0)),
            ((5000.0, 4000.0), (0.0, 4000.0)),
            ((0.0, 4000.0), (0.0, 0.0)),
        ] {
            input.walls.push(ElevationWallInput {
                start: Vec3::new(sx, 0.0, sz),
                end: Vec3::new(ex, 0.0, ez),
                height: 2700.0,
            });
        }
        // Door on wall 0 (south face), centred.
        input.openings.push(ElevationOpeningInput {
            wall_index: 0,
            offset: 2500.0,
            width: 900.0,
            height: 2100.0,
            sill_height: 0.0,
            is_door: true,
        });
        // Window on wall 1 (east face), 1.5m up.
        input.openings.push(ElevationOpeningInput {
            wall_index: 1,
            offset: 2000.0,
            width: 1200.0,
            height: 1200.0,
            sill_height: 900.0,
            is_door: false,
        });
        input
    }

    #[test]
    fn all_four_directions_emit_well_formed_svg() {
        let input = rectangular_input();
        for dir in Direction::ALL {
            let svg = generate_elevation_sheet_svg(&input, dir, 0.05);
            assert!(svg.starts_with("<?xml version=\"1.0\""), "{dir:?}");
            assert!(svg.ends_with("</svg>\n"), "{dir:?}");
            assert!(svg.contains(dir.label()), "{dir:?}");
            assert!(svg.contains("scale(1, -1)"));
            assert!(svg.contains(r#"class="wall-face""#));
            assert!(svg.contains(r#"class="roof""#));
        }
    }

    #[test]
    fn south_elevation_shows_the_door_not_the_east_window() {
        let input = rectangular_input();
        let svg = generate_elevation_sheet_svg(&input, Direction::South, 0.05);
        assert!(svg.contains(r#"class="door""#), "south view must show door");
        // Window is on east-facing wall — should not appear in south view.
        assert!(!svg.contains(r#"class="opening""#),
            "south view should not show east-facing window: {svg}");
    }

    #[test]
    fn east_elevation_shows_the_window_not_the_south_door() {
        let input = rectangular_input();
        let svg = generate_elevation_sheet_svg(&input, Direction::East, 0.05);
        assert!(svg.contains(r#"class="opening""#));
        assert!(!svg.contains(r#"class="door""#),
            "east view should not show south-facing door: {svg}");
    }

    #[test]
    fn sheet_name_matches_python_pattern() {
        assert_eq!(sheet_name(Direction::North), "03_elevation_north.svg");
        assert_eq!(sheet_name(Direction::South), "03_elevation_south.svg");
        assert_eq!(sheet_name(Direction::East), "03_elevation_east.svg");
        assert_eq!(sheet_name(Direction::West), "03_elevation_west.svg");
    }
}
