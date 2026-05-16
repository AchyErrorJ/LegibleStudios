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

const USAGE: &str = "usage: qbd_dump <building.json> [--out <floor_plan.svg>] [--bundle <dir>] [--project <name>]";

fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut path: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut bundle_dir: Option<PathBuf> = None;
    let mut project = String::from("QBD Project");

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

    let doc = archgeometry::parse_file(&path)
        .with_context(|| format!("failed to parse {}", path.display()))?;
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
            std::fs::write(&p, body)
                .with_context(|| format!("failed to write {}", p.display()))?;
            eprintln!("  wrote {} ({} bytes)", p.display(), body.len());
            Ok(())
        };

        write_sheet("01_site_plan.svg", &docs.site_plan_svg)?;
        write_sheet("02_floor_plan.svg", &docs.floor_plan_svg)?;
        for elev in &docs.elevations {
            let name = drawing::elevation_sheet_name(elev.direction);
            write_sheet(&name, &elev.svg)?;
        }
        write_sheet("04_section_aa.svg", &docs.section_svg)?;

        for (i, detail) in docs.wall_details.iter().enumerate() {
            let name = format!("07_wall_detail_{:02}_{}.svg", i + 1, detail.detail.wall_type_id);
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
            docs.project_name,
            docs.generated_date,
        );
        std::fs::write(dir.join("manifest.json"), manifest)?;
        eprintln!("  wrote {}/manifest.json", dir.display());

        return Ok(());
    }

    match out {
        Some(out_path) => {
            std::fs::write(&out_path, &docs.floor_plan_svg)
                .with_context(|| format!("failed to write {}", out_path.display()))?;
            eprintln!("wrote {} ({} bytes)", out_path.display(), docs.floor_plan_svg.len());
        }
        None => {
            print!("{}", docs.floor_plan_svg);
        }
    }

    Ok(())
}
