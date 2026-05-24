//! Top-level documentation pipeline: SchemaDocument → permit-set SVG +
//! per-wall-type section details.
//!
//! Ported from `QBDInterface::generateDocumentation`
//! (`qbd_interface.cpp:948`) + `generateWallDetails` (`:1131-1156`).

use archgeometry::SchemaDocument;
use std::fmt::Write as _;
use drawing::{
    Config, DrawingType, ElevationDirection, ElevationInput, ElevationOpeningInput,
    ElevationWallInput, ProjectInfo, SectionInput, SectionWallInput, SitePlan, WallSectionDetail,
    drawing_info_for, export_to_svg_padded, generate_elevation_sheet_svg, generate_section_sheet_svg,
    generate_site_plan_svg, generate_title_block, generate_wall_detail, wall_detail_to_svg,
};

use crate::floor_plan::generate_floor_plan_with_openings;
use crate::wall_types;

/// One wall-section detail with its rendered SVG.
#[derive(Debug, Clone, Default)]
pub struct WallDetail {
    pub detail: WallSectionDetail,
    pub svg: String,
}

/// One elevation drawing.
#[derive(Debug, Clone)]
pub struct Elevation {
    pub direction: ElevationDirection,
    pub svg: String,
}

/// Permit-set bundle. Carries the floor-plan SVG plus the surrounding
/// permit-set sheets (site plan, elevations, section, wall details) for
/// the parts the Rust pipeline ports today.
#[derive(Debug, Clone, Default)]
pub struct Documentation {
    pub project_name: String,
    pub generated_date: String,
    pub site_plan_svg: String,
    /// Ground-floor (Level 1) plan — kept for back-compat / single-storey.
    pub floor_plan_svg: String,
    /// One `(level name, SVG)` per storey; `floor_plan_svg` is the first.
    pub floor_plans: Vec<(String, String)>,
    pub elevations: Vec<Elevation>,
    pub section_svg: String,
    pub wall_details: Vec<WallDetail>,
    /// Door schedule SVG, empty string if the building has no doors.
    pub door_schedule_svg: String,
    /// Window schedule SVG, empty string if the building has no windows.
    pub window_schedule_svg: String,
}

/// Geometry export scale for the floor plan: `export_to_svg` maps plan
/// `(x, y)` to SVG `(x*scale, -y*scale)`. Annotations are authored in plan-mm
/// and lifted into this space by [`lift`].
const FP_SCALE: f32 = 10.0;
/// Pre-scale padding (mm) so dimensions that sit outside the building footprint
/// (overall + structural-grid tiers) aren't clipped by the tight viewBox.
const FP_PAD: f32 = 2500.0;

/// Lift a plan-mm annotation fragment into the floor plan's exported space.
/// Y is pre-negated in the dim inputs (keeping glyphs upright), so all that
/// remains is the uniform magnitude scale — a positive `scale()` group, which
/// does not mirror text.
fn lift(fragment: &str) -> String {
    if fragment.is_empty() {
        return String::new();
    }
    format!("<g transform=\"scale({FP_SCALE})\">\n{fragment}</g>\n")
}

/// Flip a horizontal dim's perpendicular offset (its Y) to match the geometry's
/// negated Y. The dimensioned axis (`from`/`to`) is X and is left untouched.
fn flip_h(mut d: drawing::LinearDim) -> drawing::LinearDim {
    d.offset = -d.offset;
    d
}

/// Flip a vertical dim's Y endpoints; its offset is X and is left untouched.
fn flip_v(mut d: drawing::LinearDim) -> drawing::LinearDim {
    d.from = -d.from;
    d.to = -d.to;
    d
}

/// Non-roof level names in document order. Falls back to a single
/// `"Level 1"` for documents that predate the `levels` array.
fn level_names(doc: &SchemaDocument) -> Vec<String> {
    let names: Vec<String> = doc
        .levels
        .iter()
        .map(|l| l.name.clone())
        .filter(|n| !n.to_lowercase().contains("roof"))
        .collect();
    if names.is_empty() {
        vec!["Level 1".to_string()]
    } else {
        names
    }
}

/// A view of `doc` restricted to one `level`: only that level's walls, rooms,
/// and the doors/windows on those walls. Wall indices are remapped to the
/// filtered list so door/window `wall_index` references stay valid.
fn filter_doc_to_level(doc: &SchemaDocument, level: &str) -> SchemaDocument {
    use std::collections::HashMap;
    let mut remap: HashMap<usize, usize> = HashMap::new();
    let mut walls = Vec::new();
    for (gi, w) in doc.walls.iter().enumerate() {
        if w.level_name == level {
            remap.insert(gi, walls.len());
            walls.push(w.clone());
        }
    }
    let map_idx = |gi: i32| -> Option<i32> {
        usize::try_from(gi)
            .ok()
            .and_then(|u| remap.get(&u))
            .and_then(|&l| i32::try_from(l).ok())
    };
    let doors = doc
        .doors
        .iter()
        .filter_map(|d| {
            map_idx(d.wall_index).map(|li| {
                let mut d2 = d.clone();
                d2.wall_index = li;
                d2
            })
        })
        .collect();
    let windows = doc
        .windows
        .iter()
        .filter_map(|w| {
            map_idx(w.wall_index).map(|li| {
                let mut w2 = w.clone();
                w2.wall_index = li;
                w2
            })
        })
        .collect();
    let rooms = doc
        .rooms
        .iter()
        .filter(|(_, r)| r.level == level)
        .map(|(k, v)| (k.clone(), v.clone()))
        .collect();
    let detectors = doc.detectors.iter().filter(|d| d.level_name == level).cloned().collect();
    let electrical = doc.electrical.iter().filter(|e| e.level_name == level).cloned().collect();
    let headers = doc.headers.iter().filter(|h| h.level_name == level).cloned().collect();
    SchemaDocument { walls, doors, windows, rooms, detectors, electrical, headers, ..doc.clone() }
}

/// Build one floor-plan SVG (geometry + dimension tiers + room labels, no
/// title block) for the given document view. Pass a level-filtered doc for a
/// single storey; the footprint dims come from `doc.width`/`doc.depth`.
#[allow(clippy::too_many_lines, clippy::uninlined_format_args)] // sequential annotation injection
fn build_floor_plan_svg(doc: &SchemaDocument, config: &Config) -> String {
    let cut_height = 1219.0;
    let result = generate_floor_plan_with_openings(doc, cut_height, config);
    // Pad the viewBox so the out-of-footprint dimension tiers below aren't
    // clipped. Annotations are injected in plan-mm + lifted via `lift`.
    let mut floor_plan_raw = export_to_svg_padded(&result, FP_SCALE, FP_PAD);
    // Tier-1 overall dimensions: width below the footprint, depth to the left.
    if doc.width > 0.0 && doc.depth > 0.0 {
        let width_dim = flip_h(drawing::LinearDim::horizontal_mm(0.0, doc.width, doc.depth + 500.0));
        let depth_dim = flip_v(drawing::LinearDim::vertical_mm(0.0, doc.depth, -500.0));
        let mut dims = String::new();
        dims.push_str(&drawing::render_horizontal_dim(&width_dim, 250.0));
        dims.push_str(&drawing::render_vertical_dim(&depth_dim, 250.0));
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&dims));
    }
    // Room labels + per-room (tier-4) + structural-grid (tier-2) dimensions.
    if !doc.rooms.is_empty() {
        let mut rooms: Vec<_> = doc.rooms.iter().collect();
        rooms.sort_by(|a, b| a.0.cmp(b.0));

        let room_labels: Vec<drawing::RoomLabelInput> = rooms
            .iter()
            .map(|(_id, r)| drawing::RoomLabelInput {
                name: if r.name.is_empty() { r.id.clone() } else { r.name.clone() },
                bounds_x: r.bounds.x,
                // Flip Y into the export's negated-Y space.
                bounds_y: -(r.bounds.y + r.bounds.height),
                width: r.bounds.width,
                height: r.bounds.height,
                area_mm2: r.area,
            })
            .collect();
        let labels_svg = drawing::render_room_labels(&room_labels, 250.0);
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&labels_svg));

        let mut tier4 = String::new();
        for (_id, r) in &rooms {
            if r.bounds.width < 600.0 || r.bounds.height < 600.0 {
                continue;
            }
            let (w_dim, h_dim) =
                drawing::room_interior_dims(r.bounds.x, r.bounds.y, r.bounds.width, r.bounds.height, 150.0);
            tier4.push_str(&drawing::render_horizontal_dim(&flip_h(w_dim), 140.0));
            tier4.push_str(&drawing::render_vertical_dim(&flip_v(h_dim), 140.0));
        }
        if !tier4.is_empty() {
            floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&tier4));
        }

        let dedup = |mut vs: Vec<f32>| -> Vec<f32> {
            vs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            vs.dedup_by(|a, b| (*a - *b).abs() < 1.0);
            vs
        };
        let xs: Vec<f32> = dedup(
            rooms.iter().flat_map(|(_, r)| [r.bounds.x, r.bounds.x + r.bounds.width]).collect(),
        );
        let zs: Vec<f32> = dedup(
            rooms.iter().flat_map(|(_, r)| [r.bounds.y, r.bounds.y + r.bounds.height]).collect(),
        );
        let mut tier2 = String::new();
        for d in drawing::chain_dims(&xs, -1100.0, true) {
            tier2.push_str(&drawing::render_horizontal_dim(&flip_h(d), 180.0));
        }
        for d in drawing::chain_dims(&zs, doc.width + 1100.0, false) {
            tier2.push_str(&drawing::render_vertical_dim(&flip_v(d), 180.0));
        }
        if !tier2.is_empty() {
            floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&tier2));
        }
    }

    // Tier-3: opening-location dimensions — locate each door/window along its
    // exterior wall, chained from the corners, on a line outside that wall.
    {
        const EPS: f32 = 1.0;
        const OFF: f32 = 2000.0; // mm outside the wall (within FP_PAD)
        let mut t3 = String::new();
        for (wi, w) in doc.walls.iter().enumerate() {
            if w.category != "exterior" {
                continue;
            }
            let (sx, sz, ex, ez) = (w.start.x, w.start.z, w.end.x, w.end.z);
            let horizontal = (sz - ez).abs() < EPS;
            if !horizontal && (sx - ex).abs() >= EPS {
                continue; // not axis-aligned
            }
            // Opening centres along this wall (doors carry absolute x/y;
            // windows are offset along the wall).
            let on_wall = |idx: i32| usize::try_from(idx).ok() == Some(wi);
            let len = ((ex - sx).powi(2) + (ez - sz).powi(2)).sqrt().max(1.0);
            // Centre of an opening, projected to the dimensioned axis. Doors
            // carry offset-to-centre; windows offset-to-start (+half width).
            let project = |along: f32| {
                if horizontal {
                    sx + (ex - sx) / len * along
                } else {
                    sz + (ez - sz) / len * along
                }
            };
            let mut stops: Vec<f32> = Vec::new();
            for d in doc.doors.iter().filter(|d| on_wall(d.wall_index)) {
                stops.push(project(d.offset));
            }
            for win in doc.windows.iter().filter(|w| on_wall(w.wall_index)) {
                stops.push(project(win.offset + win.width * 0.5));
            }
            if stops.is_empty() {
                continue;
            }
            // Chain from corner to corner through the openings.
            let (lo, hi) = if horizontal { (sx.min(ex), sx.max(ex)) } else { (sz.min(ez), sz.max(ez)) };
            stops.push(lo);
            stops.push(hi);
            stops.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            stops.dedup_by(|a, b| (*a - *b).abs() < 1.0);
            if horizontal {
                let line = if sz < doc.depth * 0.5 { sz - OFF } else { sz + OFF };
                for d in drawing::chain_dims(&stops, line, true) {
                    t3.push_str(&drawing::render_horizontal_dim(&flip_h(d), 150.0));
                }
            } else {
                let line = if sx < doc.width * 0.5 { sx - OFF } else { sx + OFF };
                for d in drawing::chain_dims(&stops, line, false) {
                    t3.push_str(&drawing::render_vertical_dim(&flip_v(d), 150.0));
                }
            }
        }
        if !t3.is_empty() {
            floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&t3));
        }
    }

    // Life-safety alarms (rules-engine annotation): smoke = S, CO = CO, drawn
    // as a labelled disc at the device's plan position (Y pre-negated for the
    // export's flipped space).
    if !doc.detectors.is_empty() {
        let mut det = String::new();
        for d in &doc.detectors {
            let (cx, cy) = (d.x, -d.y);
            let label = if d.kind == "co" { "CO" } else { "S" };
            let _ = write!(
                det,
                concat!(
                    r##"    <circle cx="{cx}" cy="{cy}" r="200" fill="#fff" stroke="#c00" stroke-width="25"/>"##,
                    "\n",
                    r##"    <text x="{cx}" y="{ty}" font-family="Arial, sans-serif" font-size="220" font-weight="bold" text-anchor="middle" fill="#c00">{label}</text>"##,
                    "\n",
                ),
                cx = cx,
                cy = cy,
                ty = cy + 80.0,
                label = label,
            );
        }
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&det));
    }

    // Electrical (rules-engine annotation): receptacle = small open circle on
    // the wall (GFCI labelled "G"), light = a circle-with-cross at the centre.
    if !doc.electrical.is_empty() {
        let mut elec = String::new();
        for e in &doc.electrical {
            let (cx, cy) = (e.x, -e.y);
            match e.kind.as_str() {
                "light" => {
                    let _ = write!(
                        elec,
                        concat!(
                            r##"    <circle cx="{cx}" cy="{cy}" r="160" fill="none" stroke="#d80" stroke-width="22"/>"##,
                            "\n",
                            r##"    <line x1="{l}" y1="{cy}" x2="{r}" y2="{cy}" stroke="#d80" stroke-width="22"/>"##,
                            "\n",
                            r##"    <line x1="{cx}" y1="{t}" x2="{cx}" y2="{b}" stroke="#d80" stroke-width="22"/>"##,
                            "\n",
                        ),
                        cx = cx, cy = cy,
                        l = cx - 160.0, r = cx + 160.0, t = cy - 160.0, b = cy + 160.0,
                    );
                }
                "switch" => {
                    // Wall switch: blue "S" (no disc — the smoke alarm's S is a
                    // red disc, so these don't collide).
                    let _ = write!(
                        elec,
                        r##"    <text x="{cx}" y="{ty}" font-family="Arial, sans-serif" font-size="200" font-weight="bold" text-anchor="middle" fill="#06c">S</text>"##,
                        cx = cx, ty = cy + 70.0,
                    );
                    elec.push('\n');
                }
                kind => {
                    // receptacle / gfci
                    let _ = write!(
                        elec,
                        r##"    <circle cx="{cx}" cy="{cy}" r="110" fill="#fff" stroke="#06c" stroke-width="22"/>"##,
                        cx = cx, cy = cy,
                    );
                    elec.push('\n');
                    if kind == "gfci" {
                        let _ = write!(
                            elec,
                            r##"    <text x="{cx}" y="{ty}" font-family="Arial, sans-serif" font-size="150" font-weight="bold" text-anchor="middle" fill="#06c">G</text>"##,
                            cx = cx, ty = cy + 55.0,
                        );
                        elec.push('\n');
                    }
                }
            }
        }
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&elec));
    }

    // Header callouts (rules-engine annotation): the OBC member size over each
    // opening, labelled at the opening centre (red if flagged for engineer
    // review). Y pre-negated for the export's flipped space.
    if !doc.headers.is_empty() {
        let mut hdr = String::new();
        for h in &doc.headers {
            let fill = if h.needs_review { "#c00" } else { "#333" };
            let _ = write!(
                hdr,
                r#"    <text x="{cx}" y="{cy}" font-family="Arial, sans-serif" font-size="170" text-anchor="middle" fill="{fill}">{size}</text>"#,
                cx = h.x,
                cy = -h.y,
                fill = fill,
                size = h.size,
            );
            hdr.push('\n');
        }
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &lift(&hdr));
    }
    floor_plan_raw
}

/// Generate documentation from a parsed schema. `scale` follows the C++
/// default of `10.0` (used at `qbd_interface.cpp:964`).
#[must_use]
#[allow(clippy::too_many_lines)] // Sequential sheet assembly; splitting hides the data flow.
pub fn generate_documentation(
    doc: &SchemaDocument,
    project_name: impl Into<String>,
) -> Documentation {
    let config = Config::with_defaults();
    let project_name: String = project_name.into();
    let date = today_iso();

    let project = ProjectInfo {
        name: project_name.clone(),
        number: doc.building_id.clone(),
        solver: "QBD Layout".into(),
        ..Default::default()
    };

    // Inject a title block into each generated SVG so the bundle reads
    // like a permit set (project info, drawing number, scale, sheet
    // count) rather than a bare geometry dump.
    let with_tb = |svg: String, dt: DrawingType, scale: &str| -> String {
        let info = drawing_info_for(dt, scale, &date);
        let tb = generate_title_block(doc.width, doc.depth, &project, &info, 500.0);
        inject_before_svg_close(&svg, &tb)
    };

    // One floor plan per storey when the walls genuinely span multiple levels
    // (a single combined plan would overlay the floors on the shared
    // footprint). Single-storey / untagged documents render one combined plan,
    // preserving the legacy behaviour.
    let distinct: std::collections::HashSet<&str> = doc
        .walls
        .iter()
        .map(|w| w.level_name.as_str())
        .filter(|s| !s.is_empty())
        .collect();
    let floor_plans: Vec<(String, String)> = if distinct.len() > 1 {
        level_names(doc)
            .into_iter()
            .map(|ln| {
                let view = filter_doc_to_level(doc, &ln);
                let svg =
                    with_tb(build_floor_plan_svg(&view, &config), DrawingType::FloorPlan, "1:100");
                (ln, svg)
            })
            .collect()
    } else {
        vec![(
            "Level 1".to_string(),
            with_tb(build_floor_plan_svg(doc, &config), DrawingType::FloorPlan, "1:100"),
        )]
    };
    let floor_plan_svg = floor_plans.first().map_or_else(String::new, |(_, s)| s.clone());

    Documentation {
        project_name: project_name.clone(),
        generated_date: date.clone(),
        site_plan_svg: with_tb(generate_site_plan(doc), DrawingType::FloorPlan, "1:200"),
        floor_plan_svg,
        floor_plans,
        elevations: generate_elevations(doc)
            .into_iter()
            .map(|e| Elevation {
                direction: e.direction,
                svg: with_tb(e.svg, drawing_type_for_direction(e.direction), "1:100"),
            })
            .collect(),
        section_svg: with_tb(generate_section(doc), DrawingType::SectionA, "1:100"),
        wall_details: generate_wall_details(doc, &config),
        door_schedule_svg: render_schedule_svg(
            &crate::schedule::door_entries(doc),
            "DOOR SCHEDULE",
        ),
        window_schedule_svg: render_schedule_svg(
            &crate::schedule::window_entries(doc),
            "WINDOW SCHEDULE",
        ),
    }
}

/// Wrap `drawing::schedule_to_svg` with an empty-input short-circuit:
/// permit sets traditionally suppress empty schedule sheets.
fn render_schedule_svg(entries: &[drawing::ScheduleEntry], title: &str) -> String {
    if entries.is_empty() {
        String::new()
    } else {
        drawing::schedule_to_svg(entries, title)
    }
}

/// Inject SVG content before the closing `</svg>` tag. If the input has
/// no `</svg>`, returns the input unchanged.
fn inject_before_svg_close(svg: &str, fragment: &str) -> String {
    if let Some(idx) = svg.rfind("</svg>") {
        let mut out = String::with_capacity(svg.len() + fragment.len() + 1);
        out.push_str(&svg[..idx]);
        out.push_str(fragment);
        out.push_str(&svg[idx..]);
        out
    } else {
        svg.to_string()
    }
}

fn drawing_type_for_direction(d: ElevationDirection) -> DrawingType {
    match d {
        ElevationDirection::North => DrawingType::ElevationNorth,
        ElevationDirection::South => DrawingType::ElevationSouth,
        ElevationDirection::East => DrawingType::ElevationEast,
        ElevationDirection::West => DrawingType::ElevationWest,
    }
}

/// Compute SitePlan from the schema document's overall building footprint
/// (in mm) and render the site-plan SVG.
fn generate_site_plan(doc: &SchemaDocument) -> String {
    let building_width_m = doc.width / 1000.0;
    let building_depth_m = doc.depth / 1000.0;
    let site = SitePlan::from_building_metres(building_width_m, building_depth_m);
    generate_site_plan_svg(&site)
}

/// Build a SectionInput from the schema document and render the default
/// (transverse, centre, looking-east) section.
fn generate_section(doc: &SchemaDocument) -> String {
    let level_base: std::collections::HashMap<&str, f32> =
        doc.levels.iter().map(|l| (l.name.as_str(), l.elevation)).collect();
    let input = SectionInput {
        width: doc.width,
        walls: doc
            .walls
            .iter()
            .map(|w| SectionWallInput {
                start: w.start,
                end: w.end,
                height: w.height,
                category: w.category.clone(),
                base: level_base.get(w.level_name.as_str()).copied().unwrap_or(0.0),
            })
            .collect(),
        // Use the tallest ridge height across all roofs, fallback to 1000mm
        // if no roof structure (matches the section module's documented
        // fallback). Empty vec -> no roof element rendered.
        ridge_heights_above_plate: doc
            .roofs
            .iter()
            .map(|r| {
                r.ridges
                    .iter()
                    .map(|ridge| ridge.height)
                    .fold(1000.0_f32, f32::max)
            })
            .collect(),
        floor_lines: doc.levels.iter().map(|l| l.elevation).filter(|&e| e > 1.0).collect(),
    };
    let cut = drawing::default_cut(&input);
    generate_section_sheet_svg(&input, &cut, 0.05)
}

/// Build an ElevationInput from the schema document and render one
/// elevation per cardinal direction.
fn generate_elevations(doc: &SchemaDocument) -> Vec<Elevation> {
    // Level name → base elevation (mm), so upper-storey walls stack.
    let level_base: std::collections::HashMap<&str, f32> =
        doc.levels.iter().map(|l| (l.name.as_str(), l.elevation)).collect();
    let input = ElevationInput {
        width: doc.width,
        depth: doc.depth,
        walls: doc
            .walls
            .iter()
            .map(|w| ElevationWallInput {
                start: w.start,
                end: w.end,
                height: w.height,
                base: level_base.get(w.level_name.as_str()).copied().unwrap_or(0.0),
            })
            .collect(),
        // wall_index is `i32` in the schema but `usize` in the elevation
        // input; max(0) clamps the negative-index sentinel before the
        // truncate-when-cast.
        #[allow(clippy::cast_sign_loss)]
        openings: doc
            .doors
            .iter()
            .map(|d| ElevationOpeningInput {
                wall_index: d.wall_index.max(0) as usize,
                offset: d.offset,
                width: d.width,
                height: d.height,
                sill_height: 0.0,
                is_door: true,
            })
            .chain(doc.windows.iter().map(|w| ElevationOpeningInput {
                wall_index: w.wall_index.max(0) as usize,
                offset: w.offset,
                width: w.width,
                height: w.height,
                sill_height: w.sill_height,
                is_door: false,
            }))
            .collect(),
        // Default to a 1.2m gable ridge if a roof is present in the schema;
        // disable otherwise so the elevation is a flat-roof silhouette.
        gable_ridge_above_plate: if doc.roofs.is_empty() { 0.0 } else { 1200.0 },
        // A floor line at each storey base above grade (Level 2+).
        floor_lines: doc.levels.iter().map(|l| l.elevation).filter(|&e| e > 1.0).collect(),
    };
    ElevationDirection::ALL
        .iter()
        .map(|&dir| Elevation {
            direction: dir,
            svg: generate_elevation_sheet_svg(&input, dir, 0.05),
        })
        .collect()
}

/// One detail per wall category actually present in the layout.
/// Matches `QBDInterface::generateWallDetails` (`qbd_interface.cpp:1131`).
#[must_use]
fn generate_wall_details(doc: &SchemaDocument, config: &Config) -> Vec<WallDetail> {
    let mut has_exterior = false;
    let mut has_interior = false;
    let mut has_wet = false;
    for wall in &doc.walls {
        match wall.category.as_str() {
            "exterior" => has_exterior = true,
            "wet_wall" => has_wet = true,
            _ => has_interior = true,
        }
    }

    let mut details = Vec::new();
    if has_exterior {
        details.push(build_detail(wall_types::exterior_2x6_r21(), config));
    }
    if has_interior {
        details.push(build_detail(wall_types::interior_2x4(), config));
    }
    if has_wet {
        details.push(build_detail(wall_types::wet_2x6(), config));
    }
    details
}

// WallType is small and owned (the helpers in `wall_types` return owned
// values); taking it by value mirrors the caller pattern with no extra cost.
#[allow(clippy::needless_pass_by_value)]
fn build_detail(wall_type: domain::WallType, config: &Config) -> WallDetail {
    let detail = generate_wall_detail(&wall_type, 9.0, config);
    let svg = wall_detail_to_svg(&detail, 1.0);
    WallDetail { detail, svg }
}

/// Current date in `YYYY-MM-DD`. Uses `SystemTime` and a small
/// hand-rolled Gregorian-calendar conversion so we don't pull in the
/// `chrono` crate for this single use.
#[must_use]
#[allow(clippy::cast_sign_loss, clippy::cast_possible_truncation)]
pub fn today_iso() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs();
    let days_since_epoch = secs / 86_400;

    // Convert days-since-1970-01-01 to (year, month, day) — algorithm
    // from Howard Hinnant's date library, simplified for >= 1970.
    let days = i64::try_from(days_since_epoch).unwrap_or(0);
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    // Post-1970 dates: z >> 0, so the subtraction is non-negative.
    #[allow(clippy::cast_sign_loss)]
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    #[allow(clippy::cast_possible_wrap)]
    let y = (yoe as i64) + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    let y = if m <= 2 { y + 1 } else { y };

    format!("{y:04}-{m:02}-{d:02}")
}

#[cfg(test)]
mod tests {
    use super::*;
    use archgeometry::{SchemaDoor, SchemaWall, SchemaWindow};
    use glam::Vec3;

    fn rect_room_doc() -> SchemaDocument {
        let mut doc = SchemaDocument::default();
        for ((sx, sz), (ex, ez)) in [
            ((0.0, 0.0), (5000.0, 0.0)),
            ((5000.0, 0.0), (5000.0, 4000.0)),
            ((5000.0, 4000.0), (0.0, 4000.0)),
            ((0.0, 4000.0), (0.0, 0.0)),
        ] {
            doc.walls.push(SchemaWall {
                start: Vec3::new(sx, 0.0, sz),
                end: Vec3::new(ex, 0.0, ez),
                height: 2700.0,
                category: "exterior".into(),
                ..Default::default()
            });
        }
        doc
    }

    #[test]
    fn generated_documentation_has_floor_plan_svg() {
        let docs = generate_documentation(&rect_room_doc(), "Test Project");
        assert_eq!(docs.project_name, "Test Project");
        assert!(docs.floor_plan_svg.starts_with("<?xml version=\"1.0\""));
        assert!(docs.floor_plan_svg.contains("<svg"));
        assert!(docs.floor_plan_svg.ends_with("</svg>\n"));
    }

    #[test]
    fn generated_documentation_includes_door_and_window_primitives() {
        let mut doc = rect_room_doc();
        doc.doors.push(SchemaDoor {
            wall_index: 0,
            offset: 2500.0,
            width: 900.0,
            height: 2100.0,
            door_type: "swing".into(),
            swing: "left_in".into(),
            ..Default::default()
        });
        doc.windows.push(SchemaWindow {
            wall_index: 1,
            offset: 2000.0,
            width: 1200.0,
            height: 1200.0,
            sill_height: 900.0,
            ..Default::default()
        });
        let docs = generate_documentation(&doc, "Test");
        // Door white fill → polygon with white fill in SVG.
        assert!(docs.floor_plan_svg.contains(r#"fill="rgb(255,255,255)""#));
        // Window glazing → A-GLAZ — but the SVG layer name isn't in the
        // output (we don't emit class/id). Instead check for the swing
        // arc, which is unique to doors.
        assert!(docs.floor_plan_svg.contains("<path d=\"M"));
    }

    #[test]
    fn today_iso_is_well_formed() {
        let s = today_iso();
        // YYYY-MM-DD = 10 chars, two hyphens.
        assert_eq!(s.len(), 10);
        assert_eq!(s.chars().filter(|&c| c == '-').count(), 2);
    }

    #[test]
    fn exterior_only_layout_yields_one_wall_detail() {
        let docs = generate_documentation(&rect_room_doc(), "Test");
        assert_eq!(docs.wall_details.len(), 1);
        let d = &docs.wall_details[0];
        assert_eq!(d.detail.wall_type_id, "ext_2x6_r21");
        assert!(d.svg.starts_with("<?xml version=\"1.0\""));
        assert!(d.svg.contains("<svg"));
    }

    #[test]
    fn mixed_layout_yields_one_detail_per_category() {
        let mut doc = rect_room_doc();
        // Add one interior + one wet-wall.
        doc.walls.push(SchemaWall {
            start: Vec3::new(2000.0, 0.0, 0.0),
            end: Vec3::new(2000.0, 0.0, 4000.0),
            height: 2700.0,
            category: "interior".into(),
            ..Default::default()
        });
        doc.walls.push(SchemaWall {
            start: Vec3::new(3000.0, 0.0, 0.0),
            end: Vec3::new(3000.0, 0.0, 4000.0),
            height: 2700.0,
            category: "wet_wall".into(),
            ..Default::default()
        });
        let docs = generate_documentation(&doc, "Mixed");
        assert_eq!(docs.wall_details.len(), 3);
        let ids: Vec<_> = docs
            .wall_details
            .iter()
            .map(|d| d.detail.wall_type_id.as_str())
            .collect();
        assert!(ids.contains(&"ext_2x6_r21"));
        assert!(ids.contains(&"int_2x4"));
        assert!(ids.contains(&"wet_2x6"));
    }
}
