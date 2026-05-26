//! `qbd_solve` — pure-Rust answers → `qbd_output.schema.json` bundle.
//!
//! The end of the Increment-4 path: no Python in answers → drawings.
//! Prints the building JSON to stdout.
//!
//! Usage:
//!     qbd_solve [--bedrooms N] [--bathrooms N] [--sqft N]
//!               [--garage none|1car|2car|3car] [--storeys 0|1|2]
//!               [--windows balanced|more_light|privacy|south_bank]
//!               [--style balanced|ranch|colonial|contemporary]
//!               [--lot WxD (ft)] [--zone R1|R2|R3] [--street "Name"]
//!     (--storeys 0 = auto: 2 when 3+ bedrooms, else 1)

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
            "--storeys" => a.storeys = args[i + 1].parse().unwrap_or(a.storeys),
            "--windows" => a.window_intent.clone_from(&args[i + 1]),
            "--style" => a.style.clone_from(&args[i + 1]),
            "--zone" => a.zone.clone_from(&args[i + 1]),
            "--street" => a.street.clone_from(&args[i + 1]),
            "--lot" => {
                // WxD in feet, e.g. --lot 60x120
                if let Some((w, d)) = args[i + 1].split_once('x') {
                    a.lot_width_ft = w.parse().unwrap_or(a.lot_width_ft);
                    a.lot_depth_ft = d.parse().unwrap_or(a.lot_depth_ft);
                }
            }
            _ => {}
        }
        i += 2;
    }
    let value = building_json(&a);
    println!("{}", serde_json::to_string_pretty(&value).unwrap_or_default());
}
