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

fn main() -> anyhow::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let mut path: Option<PathBuf> = None;
    let mut out: Option<PathBuf> = None;
    let mut project = String::from("QBD Project");

    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--out" if i + 1 < args.len() => {
                out = Some(PathBuf::from(&args[i + 1]));
                i += 2;
            }
            "--project" if i + 1 < args.len() => {
                project.clone_from(&args[i + 1]);
                i += 2;
            }
            "-h" | "--help" => {
                eprintln!(
                    "usage: qbd_dump <building.json> [--out <floor_plan.svg>] [--project <name>]"
                );
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

    let path = path.ok_or_else(|| {
        anyhow::anyhow!("usage: qbd_dump <building.json> [--out <floor_plan.svg>] [--project <name>]")
    })?;

    let doc = archgeometry::parse_file(&path)
        .with_context(|| format!("failed to parse {}", path.display()))?;
    let docs = qbd::generate_documentation(&doc, project);

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
