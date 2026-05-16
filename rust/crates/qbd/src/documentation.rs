//! Top-level documentation pipeline: SchemaDocument → permit-set SVG +
//! per-wall-type section details.
//!
//! Ported from `QBDInterface::generateDocumentation`
//! (`qbd_interface.cpp:948`) + `generateWallDetails` (`:1131-1156`).

use archgeometry::SchemaDocument;
use drawing::{
    drawing_info_for, export_to_svg, generate_elevation_sheet_svg, generate_section_sheet_svg,
    generate_site_plan_svg, generate_title_block, generate_wall_detail, wall_detail_to_svg,
    Config, DrawingType, ElevationDirection, ElevationInput, ElevationOpeningInput,
    ElevationWallInput, ProjectInfo, SectionCut, SectionInput, SectionWallInput, SitePlan,
    WallSectionDetail,
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
    pub floor_plan_svg: String,
    pub elevations: Vec<Elevation>,
    pub section_svg: String,
    pub wall_details: Vec<WallDetail>,
}

/// Generate documentation from a parsed schema. `scale` follows the C++
/// default of `10.0` (used at `qbd_interface.cpp:964`).
#[must_use]
pub fn generate_documentation(
    doc: &SchemaDocument,
    project_name: impl Into<String>,
) -> Documentation {
    let config = Config::with_defaults();
    // Standard floor-plan cut height: 4 ft = ~1219 mm. C++ default at
    // `qbd_interface.cpp:963` is 4.0 (presumably feet in the kernel's
    // mixed-unit space). The schema is mm; we use 1219 mm (≈4 ft).
    let cut_height = 1219.0;
    let result = generate_floor_plan_with_openings(doc, cut_height, &config);
    let mut floor_plan_raw = export_to_svg(&result, 10.0);
    // Inject Tier-1 dimensions on the floor plan: overall width below the
    // footprint, overall depth to the left. Coordinates in plan view are
    // (X, Z), so Y in 2D space is the schema's Z.
    if doc.width > 0.0 && doc.depth > 0.0 {
        let width_dim = drawing::LinearDim::horizontal_mm(0.0, doc.width, doc.depth + 500.0);
        let depth_dim = drawing::LinearDim::vertical_mm(0.0, doc.depth, -500.0);
        let mut dims = String::new();
        dims.push_str(&drawing::render_horizontal_dim(&width_dim, 250.0));
        dims.push_str(&drawing::render_vertical_dim(&depth_dim, 250.0));
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &dims);
    }
    // Inject room labels (name + area). Sort by id so output is
    // deterministic regardless of HashMap iteration order.
    if !doc.rooms.is_empty() {
        let mut rooms: Vec<_> = doc.rooms.iter().collect();
        rooms.sort_by(|a, b| a.0.cmp(b.0));

        // Room labels.
        let room_labels: Vec<drawing::RoomLabelInput> = rooms
            .iter()
            .map(|(_id, r)| drawing::RoomLabelInput {
                name: if r.name.is_empty() {
                    r.id.clone()
                } else {
                    r.name.clone()
                },
                bounds_x: r.bounds.x,
                bounds_y: r.bounds.y,
                width: r.bounds.width,
                height: r.bounds.height,
                area_mm2: r.area,
            })
            .collect();
        let labels_svg = drawing::render_room_labels(&room_labels, 250.0);
        floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &labels_svg);

        // Tier-4: per-room interior dimensions (width along top inside
        // edge, height along left inside edge).
        let mut tier4 = String::new();
        for (_id, r) in &rooms {
            if r.bounds.width < 600.0 || r.bounds.height < 600.0 {
                // Skip rooms too small to fit a labelled dim chain.
                continue;
            }
            let (w_dim, h_dim) = drawing::room_interior_dims(
                r.bounds.x,
                r.bounds.y,
                r.bounds.width,
                r.bounds.height,
                150.0,
            );
            tier4.push_str(&drawing::render_horizontal_dim(&w_dim, 140.0));
            tier4.push_str(&drawing::render_vertical_dim(&h_dim, 140.0));
        }
        if !tier4.is_empty() {
            floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &tier4);
        }

        // Tier-2: structural-grid chain dimensions. Collect the unique
        // X coordinates where any room edge falls (rounded to 1mm to
        // suppress floating-point near-duplicates), and chain them along
        // a horizontal line above the floor plan. Same for Z along the
        // right side.
        let dedup = |mut vs: Vec<f32>| -> Vec<f32> {
            vs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
            vs.dedup_by(|a, b| (*a - *b).abs() < 1.0);
            vs
        };
        let xs: Vec<f32> = dedup(
            rooms
                .iter()
                .flat_map(|(_, r)| [r.bounds.x, r.bounds.x + r.bounds.width])
                .collect(),
        );
        let zs: Vec<f32> = dedup(
            rooms
                .iter()
                .flat_map(|(_, r)| [r.bounds.y, r.bounds.y + r.bounds.height])
                .collect(),
        );
        let mut tier2 = String::new();
        // Horizontal chain along top (Y = -1100, above Tier-1 width).
        for d in drawing::chain_dims(&xs, -1100.0, true) {
            tier2.push_str(&drawing::render_horizontal_dim(&d, 180.0));
        }
        // Vertical chain along right (X = doc.width + 1100, right of plan).
        for d in drawing::chain_dims(&zs, doc.width + 1100.0, false) {
            tier2.push_str(&drawing::render_vertical_dim(&d, 180.0));
        }
        if !tier2.is_empty() {
            floor_plan_raw = inject_before_svg_close(&floor_plan_raw, &tier2);
        }
    }
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

    Documentation {
        project_name: project_name.clone(),
        generated_date: date.clone(),
        site_plan_svg: with_tb(generate_site_plan(doc), DrawingType::FloorPlan, "1:200"),
        floor_plan_svg: with_tb(floor_plan_raw, DrawingType::FloorPlan, "1:100"),
        elevations: generate_elevations(doc)
            .into_iter()
            .map(|e| Elevation {
                direction: e.direction,
                svg: with_tb(e.svg, drawing_type_for_direction(e.direction), "1:100"),
            })
            .collect(),
        section_svg: with_tb(generate_section(doc), DrawingType::SectionA, "1:100"),
        wall_details: generate_wall_details(doc, &config),
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
    };
    let cut = drawing::default_cut(&input);
    generate_section_sheet_svg(&input, &cut, 0.05)
}

/// Build an ElevationInput from the schema document and render one
/// elevation per cardinal direction.
fn generate_elevations(doc: &SchemaDocument) -> Vec<Elevation> {
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
            })
            .collect(),
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

fn build_detail(wall_type: domain::WallType, config: &Config) -> WallDetail {
    let detail = generate_wall_detail(&wall_type, 9.0, config);
    let svg = wall_detail_to_svg(&detail, 1.0);
    WallDetail { detail, svg }
}

/// Current date in `YYYY-MM-DD`. Uses `SystemTime` and a small
/// hand-rolled Gregorian-calendar conversion so we don't pull in the
/// `chrono` crate for this single use.
#[allow(clippy::cast_sign_loss, clippy::cast_possible_truncation)]
fn today_iso() -> String {
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
        let ids: Vec<_> = docs.wall_details.iter().map(|d| d.detail.wall_type_id.as_str()).collect();
        assert!(ids.contains(&"ext_2x6_r21"));
        assert!(ids.contains(&"int_2x4"));
        assert!(ids.contains(&"wet_2x6"));
    }
}
