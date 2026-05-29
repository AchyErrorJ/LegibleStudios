//! `qbd_dump` — end-user CLI for the M5 permit-set pipeline.
//!
//! Loads a QBD-format JSON file via `archgeometry::parse_file`, runs
//! `qbd::generate_documentation`, and prints the resulting floor-plan
//! SVG to stdout. Optionally writes the SVG to a file with `--out`.
//!
//! Usage:
//!     qbd_dump <building.json>
//!     qbd_dump <building.json> --out floor_plan.svg

use anyhow::Context;
use std::path::PathBuf;

const USAGE: &str = "usage: qbd_dump <building.json> [--out <floor_plan.svg>] [--bundle <dir>] [--ifc <out.ifc>] [--terrain <terrain.json>] [--parcel <parcel.json>] [--project <name>] [--bare]";

/// Longest displayed edge, in CSS px, for a written sheet.
const DISPLAY_MAX_PX: f32 = 1100.0;

/// Default elevation step between LiDAR contour lines on the site plan.
const CONTOUR_INTERVAL_M: f32 = 0.5;

/// Cap an SVG's displayed size. The geometry is exported in millimetres (often
/// ×10), so the raw `width`/`height` attributes are hundreds of thousands of
/// units — a browser renders that at that many *pixels*. We rewrite only the
/// `width`/`height` attributes (keeping the `viewBox`, so the drawing is
/// untouched) to fit `DISPLAY_MAX_PX` at the viewBox aspect ratio.
fn fit_display(svg: &str) -> String {
    let Some(start) = svg.find("<svg") else {
        return svg.to_string();
    };
    let Some(rel_end) = svg[start..].find('>') else {
        return svg.to_string();
    };
    let end = start + rel_end; // index of '>'
    let tag = &svg[start..end];
    // Parse the viewBox "minx miny w h".
    let Some(vb) = tag.split("viewBox=\"").nth(1).and_then(|s| s.split('"').next()) else {
        return svg.to_string();
    };
    let nums: Vec<f32> = vb.split_whitespace().filter_map(|n| n.parse().ok()).collect();
    if nums.len() != 4 {
        return svg.to_string();
    }
    let (vw, vh) = (nums[2].abs(), nums[3].abs());
    if vw <= 0.0 || vh <= 0.0 {
        return svg.to_string();
    }
    let (w, h) = if vw >= vh {
        (DISPLAY_MAX_PX, DISPLAY_MAX_PX * vh / vw)
    } else {
        (DISPLAY_MAX_PX * vw / vh, DISPLAY_MAX_PX)
    };
    let replace_attr = |tag: &str, name: &str, val: f32| -> String {
        let pat = format!("{name}=\"");
        if let Some(s) = tag.find(&pat) {
            let after = s + pat.len();
            if let Some(rel) = tag[after..].find('"') {
                return format!("{}{:.1}{}", &tag[..after], val, &tag[after + rel..]);
            }
        }
        tag.to_string()
    };
    let new_tag = replace_attr(&replace_attr(tag, "width", w), "height", h);
    format!("{}{}{}", &svg[..start], new_tag, &svg[end..])
}

#[allow(clippy::too_many_lines)] // CLI dispatch + bundle emission read top-down.
#[allow(clippy::format_collect)] // Manifest JSON assembly is one-shot; iterator-format is fine here.
#[allow(clippy::cast_possible_truncation)] // parcel coords are bounded lot dimensions
fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut path: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut bundle_dir: Option<PathBuf> = None;
    let mut ifc_out: Option<PathBuf> = None;
    let mut terrain_path: Option<PathBuf> = None;
    let mut parcel_path: Option<PathBuf> = None;
    let mut project = String::from("QBD Project");
    // `--bare`: emit just the slicer's raw floor-plan SVG (no dimensions,
    // no title block, no room labels). The m5_cpp_diff oracle relies on
    // this — the C++ QBDInterface doesn't add annotations, so a fair
    // byte-comparison must strip Rust's annotation overlay.
    let mut bare = false;

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--out" if i + 1 < args.len() => {
                out = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--bundle" if i + 1 < args.len() => {
                bundle_dir = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--project" if i + 1 < args.len() => {
                project.clone_from(&args[i + 1]);
                i += 2;
            }
            "--ifc" if i + 1 < args.len() => {
                ifc_out = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--terrain" if i + 1 < args.len() => {
                terrain_path = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--parcel" if i + 1 < args.len() => {
                parcel_path = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--bare" => {
                bare = true;
                i += 1;
            }
            "-h" | "--help" => {
                eprintln!("{USAGE}");
                return Ok(());
            }
            arg => {
                if path.is_none() {
                    path = Some(PathBuf::from(arg));
                }
                i += 1;
            }
        }
    }

    let path = path.ok_or_else(|| anyhow::anyhow!("{USAGE}"))?;

    let mut doc = archgeometry::parse_file(&path)
        .with_context(|| format!("failed to parse {}", path.display()))?;

    // LiDAR terrain: lot size + corner grade from the extracted property.
    if let Some(tpath) = &terrain_path {
        let json = std::fs::read_to_string(tpath)
            .with_context(|| format!("failed to read {}", tpath.display()))?;
        if let Some(t) = qbd::terrain::from_json(&json) {
            doc.site.lot_width_ft = t.lot_width_ft;
            doc.site.lot_depth_ft = t.lot_depth_ft;
            doc.site.grade_corners_m = t.corners_m.to_vec();
            // Contour lines from the same LiDAR mesh.
            let contours = qbd::terrain::contours(&t, CONTOUR_INTERVAL_M);
            doc.site.contours_ft = contours
                .iter()
                .map(|c| archgeometry::SchemaContour {
                    elevation_m: c.elevation_m,
                    segments_ft: c
                        .segments_ft
                        .iter()
                        .map(|((x1, y1), (x2, y2))| [[*x1, *y1], [*x2, *y2]])
                        .collect(),
                })
                .collect();
            doc.site.contour_interval_m = CONTOUR_INTERVAL_M;
            eprintln!(
                "  terrain: lot {:.0}x{:.0} ft, grade {:.1}-{:.1} m, {} contour level(s) @ {:.1} m",
                t.lot_width_ft,
                t.lot_depth_ft,
                t.corners_m.iter().copied().fold(f32::INFINITY, f32::min),
                t.corners_m.iter().copied().fold(f32::NEG_INFINITY, f32::max),
                contours.len(),
                CONTOUR_INTERVAL_M,
            );
        } else {
            eprintln!("  terrain: no usable mesh in {}", tpath.display());
        }
    }

    // Parcel polygon: the real lot outline the user drew on the map widget
    // (CAD's `vertices_ft`). Accepts a top-level `vertices_ft`/`lot_polygon_ft`
    // array of `[x, y]` ft pairs, or a bare array of pairs.
    if let Some(ppath) = &parcel_path {
        let json = std::fs::read_to_string(ppath)
            .with_context(|| format!("failed to read {}", ppath.display()))?;
        let v: serde_json::Value = serde_json::from_str(&json)
            .with_context(|| format!("failed to parse {}", ppath.display()))?;
        let arr = v
            .get("vertices_ft")
            .or_else(|| v.get("lot_polygon_ft"))
            .or(Some(&v))
            .and_then(serde_json::Value::as_array);
        if let Some(arr) = arr {
            let poly: Vec<[f32; 2]> = arr
                .iter()
                .filter_map(|p| {
                    let a = p.as_array()?;
                    Some([a.first()?.as_f64()? as f32, a.get(1)?.as_f64()? as f32])
                })
                .collect();
            if poly.len() >= 3 {
                eprintln!("  parcel: {} vertices", poly.len());
                doc.site.lot_polygon_ft = poly;
            } else {
                eprintln!("  parcel: no usable polygon in {}", ppath.display());
            }
        }
    }

    // IFC4 export (decoupled Revit-import bridge).
    if let Some(ifc_path) = &ifc_out {
        let ifc = qbd::ifc::to_ifc(&doc, &project, &qbd::documentation::today_iso());
        std::fs::write(ifc_path, &ifc)
            .with_context(|| format!("failed to write {}", ifc_path.display()))?;
        eprintln!("  wrote {} ({} bytes)", ifc_path.display(), ifc.len());
        if bundle_dir.is_none() && out.is_none() && !bare {
            return Ok(());
        }
    }

    // `--bare` short-circuits before generate_documentation runs, so we
    // don't pay the cost of building elevations / sections / details.
    if bare {
        let config = drawing::Config::with_defaults();
        let result = qbd::generate_floor_plan_with_openings(&doc, 1219.0, &config);
        let svg = drawing::export_to_svg(&result, 10.0);
        print!("{svg}");
        return Ok(());
    }

    let docs = qbd::generate_documentation(&doc, project);

    if let Some(dir) = bundle_dir {
        std::fs::create_dir_all(&dir)
            .with_context(|| format!("failed to create bundle dir {}", dir.display()))?;

        // Rust-side bundle: all 8 sheets that the Rust pipeline can produce
        // today (site plan, floor plan, 4 elevations, section, plus
        // per-category wall section details). The Python's 9-sheet bundle
        // adds 2 schedule sheets that the Rust pipeline doesn't yet emit
        // (schedule generator is M5+ scope; the Python pipeline doesn't
        // actually write them today either due to a `extract_openings` bug
        // — see m5_diff.py for the picture).
        let write_sheet = |name: &str, body: &str| -> anyhow::Result<()> {
            let p = dir.join(name);
            let body = fit_display(body);
            std::fs::write(&p, &body).with_context(|| format!("failed to write {}", p.display()))?;
            eprintln!("  wrote {} ({} bytes)", p.display(), body.len());
            Ok(())
        };

        write_sheet("01_site_plan.svg", &docs.site_plan_svg)?;
        write_sheet("06_roof_plan.svg", &docs.roof_plan_svg)?;
        // Floor plans: ground floor keeps the canonical name; upper storeys
        // get their own sheet so the storeys aren't overlaid.
        if docs.floor_plans.len() <= 1 {
            write_sheet("02_floor_plan.svg", &docs.floor_plan_svg)?;
        } else {
            for (i, (level, svg)) in docs.floor_plans.iter().enumerate() {
                let name = if i == 0 {
                    "02_floor_plan.svg".to_string()
                } else {
                    format!("02_floor_plan_l{}.svg", i + 1)
                };
                eprintln!("  ({level})");
                write_sheet(&name, svg)?;
            }
        }
        for elev in &docs.elevations {
            let name = drawing::elevation_sheet_name(elev.direction);
            write_sheet(&name, &elev.svg)?;
        }
        write_sheet("04_section_aa.svg", &docs.section_svg)?;

        // Schedules: only emit when non-empty (parity with permit
        // convention — no blank schedule sheets).
        if !docs.door_schedule_svg.is_empty() {
            write_sheet("05_door_schedule.svg", &docs.door_schedule_svg)?;
        }
        if !docs.window_schedule_svg.is_empty() {
            write_sheet("05_window_schedule.svg", &docs.window_schedule_svg)?;
        }

        for (i, detail) in docs.wall_details.iter().enumerate() {
            let name = format!(
                "07_wall_detail_{:02}_{}.svg",
                i + 1,
                detail.detail.wall_type_id
            );
            write_sheet(&name, &detail.svg)?;
        }

        // Manifest declaring what's present vs M5+ deferred.
        let elev_lines: String = docs
            .elevations
            .iter()
            .map(|e| format!(",\n    \"{}\"", drawing::elevation_sheet_name(e.direction)))
            .collect();
        let detail_lines: String = (0..docs.wall_details.len())
            .map(|i| {
                format!(
                    ",\n    \"07_wall_detail_{:02}_{}.svg\"",
                    i + 1,
                    docs.wall_details[i].detail.wall_type_id
                )
            })
            .collect();
        let manifest = format!(
            "{{\n  \"project\": \"{}\",\n  \"generated_date\": \"{}\",\n  \"produced\": [\n    \"01_site_plan.svg\",\n    \"02_floor_plan.svg\"{elev_lines},\n    \"04_section_aa.svg\"{detail_lines}\n  ],\n  \"deferred_to_m5_plus\": [\n    \"05_door_schedule.svg\",\n    \"05_window_schedule.svg\"\n  ]\n}}\n",
            docs.project_name, docs.generated_date,
        );
        std::fs::write(dir.join("manifest.json"), manifest)?;
        eprintln!("  wrote {}/manifest.json", dir.display());

        return Ok(());
    }

    match out {
        Some(out_path) => {
            std::fs::write(&out_path, &docs.floor_plan_svg)
                .with_context(|| format!("failed to write {}", out_path.display()))?;
            eprintln!(
                "wrote {} ({} bytes)",
                out_path.display(),
                docs.floor_plan_svg.len()
            );
        }
        None => {
            print!("{}", docs.floor_plan_svg);
        }
    }

    Ok(())
}
