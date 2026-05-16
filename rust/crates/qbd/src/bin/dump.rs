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

        // Sheets the Rust pipeline can produce today. The Python permit
        // pipeline writes 9 sheets total (site plan, floor plan, 4
        // elevations, section, door+window schedules); the Rust crates
        // currently support floor plan + per-category wall section
        // details. Missing generators are flagged in M5_GAPS below.
        let fp = dir.join("02_floor_plan.svg");
        std::fs::write(&fp, &docs.floor_plan_svg)
            .with_context(|| format!("failed to write {}", fp.display()))?;
        eprintln!("  wrote {} ({} bytes)", fp.display(), docs.floor_plan_svg.len());

        for (i, detail) in docs.wall_details.iter().enumerate() {
            let name = format!("07_wall_detail_{:02}_{}.svg", i + 1, detail.detail.wall_type_id);
            let p = dir.join(&name);
            std::fs::write(&p, &detail.svg)
                .with_context(|| format!("failed to write {}", p.display()))?;
            eprintln!("  wrote {} ({} bytes)", p.display(), detail.svg.len());
        }

        // Manifest so the M5 oracle knows what's present vs deferred.
        let manifest = format!(
            "{{\n  \"project\": \"{}\",\n  \"generated_date\": \"{}\",\n  \"produced\": [\n    \"02_floor_plan.svg\"{}\n  ],\n  \"deferred_to_m5_plus\": [\n    \"01_site_plan.svg\",\n    \"03_elevation_north.svg\",\n    \"03_elevation_south.svg\",\n    \"03_elevation_east.svg\",\n    \"03_elevation_west.svg\",\n    \"04_section_aa.svg\",\n    \"05_door_schedule.svg\",\n    \"05_window_schedule.svg\"\n  ]\n}}\n",
            docs.project_name,
            docs.generated_date,
            (0..docs.wall_details.len())
                .map(|i| format!(",\n    \"07_wall_detail_{:02}_{}.svg\"",
                    i + 1, docs.wall_details[i].detail.wall_type_id))
                .collect::<String>()
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
