//! `archgeometry_dump` — Rust counterpart to the C++ tool of the same name.
//!
//! Same CLI, same output format. Currently a stub: every category line is
//! `UNIMPLEMENTED`. As the archgeometry crate gets ported (schema_types →
//! geometry_types → schema_parser → generators), this binary fills in,
//! and `tests/m1_diff.py` flips from yellow to green per category.
//!
//! M1 exit criterion: every category line matches C++ output exactly on
//! the QBD test corpus.

use std::path::Path;
use std::process::ExitCode;

const FORMAT_VERSION: &str = "ARCHGEOMETRY_DUMP v1";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 2 {
        eprintln!("usage: archgeometry_dump <building.json>");
        return ExitCode::from(2);
    }

    let path = Path::new(&args[1]);
    if !path.exists() {
        eprintln!("error: file not found: {}", path.display());
        return ExitCode::from(2);
    }

    let filename = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("?");

    // Stub output — same shape as the C++ tool. Replace per category as the
    // archgeometry crate's modules land.
    println!("{FORMAT_VERSION}");
    println!("INPUT {filename}");
    println!(
        "BUILDING id=- bounds_min=UNIMPLEMENTED bounds_max=UNIMPLEMENTED"
    );
    for label in ["WALLS", "FLOORS", "ROOFS", "DOORS", "WINDOWS", "ROOMS"] {
        println!("{label:<8} UNIMPLEMENTED");
    }
    println!("END");

    ExitCode::SUCCESS
}
