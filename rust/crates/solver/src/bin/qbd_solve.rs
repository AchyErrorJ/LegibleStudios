//! `qbd_solve` — pure-Rust answers → `qbd_output.schema.json` bundle.
//!
//! The end of the Increment-4 path: no Python in answers → drawings.
//! Prints the building JSON to stdout.
//!
//! Usage:
//!     qbd_solve [--bedrooms N] [--bathrooms N] [--sqft N] [--garage none|1car|2car|3car]

use solver::{building_json, Answers};

fn main() {
    let mut a = Answers::default();
    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i + 1 < args.len() {
        match args[i].as_str() {
            "--bedrooms" => a.bedrooms = args[i + 1].parse().unwrap_or(a.bedrooms),
            "--bathrooms" => a.bathrooms = args[i + 1].parse().unwrap_or(a.bathrooms),
            "--sqft" => a.sqft = args[i + 1].parse().unwrap_or(a.sqft),
            "--garage" => a.garage.clone_from(&args[i + 1]),
            _ => {}
        }
        i += 2;
    }
    let value = building_json(&a);
    println!("{}", serde_json::to_string_pretty(&value).unwrap_or_default());
}
