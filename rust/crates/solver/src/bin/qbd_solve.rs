//! `qbd_solve` — pure-Rust answers → `qbd_output.schema.json` bundle.
//!
//! The end of the Increment-4 path: no Python in answers → drawings.
//! Prints the building JSON to stdout.
//!
//! Usage:
//!     qbd_solve [--mode part9|part3|mixed]
//!               [--bedrooms N] [--bathrooms N] [--sqft N]
//!               [--garage none|1car|2car|3car] [--storeys 0|1|2]
//!               [--windows balanced|more_light|privacy|south_bank]
//!               [--style balanced|ranch|colonial|contemporary]
//!               [--lot WxD (ft)] [--zone R1|R2|R3] [--street "Name"]
//!               [--roof gable|hip]
//!               [--stair-config switchback|straight|l_shaped]
//!     qbd_solve --manifest <path>
//!     qbd_solve --catalog <mode>
//!     (--storeys 0 = auto: 2 when 3+ bedrooms, else 1)

use solver::{building_json, building_json_from_manifest, Answers, BuildingMode, ProgramManifest, RoomCatalog};

fn main() {
    let mut a = Answers::default();
    let mut manifest_path: Option<String> = None;
    let mut catalog_mode: Option<String> = None;

    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i + 1 < args.len() {
        match args[i].as_str() {
            "--mode" => {
                if let Ok(mode) = args[i + 1].parse::<BuildingMode>() {
                    a.mode = mode;
                }
            }
            "--bedrooms" => a.bedrooms = args[i + 1].parse().unwrap_or(a.bedrooms),
            "--bathrooms" => a.bathrooms = args[i + 1].parse().unwrap_or(a.bathrooms),
            "--sqft" => a.sqft = args[i + 1].parse().unwrap_or(a.sqft),
            "--garage" => a.garage.clone_from(&args[i + 1]),
            "--storeys" => a.storeys = args[i + 1].parse().unwrap_or(a.storeys),
            "--windows" => a.window_intent.clone_from(&args[i + 1]),
            "--style" => a.style.clone_from(&args[i + 1]),
            "--zone" => a.zone.clone_from(&args[i + 1]),
            "--street" => a.street.clone_from(&args[i + 1]),
            "--roof" => a.roof_type.clone_from(&args[i + 1]),
            "--stair-config" => a.stair_config.clone_from(&args[i + 1]),
            "--lot" => {
                // WxD in feet, e.g. --lot 60x120
                if let Some((w, d)) = args[i + 1].split_once('x') {
                    a.lot_width_ft = w.parse().unwrap_or(a.lot_width_ft);
                    a.lot_depth_ft = d.parse().unwrap_or(a.lot_depth_ft);
                }
            }
            "--manifest" => manifest_path = Some(args[i + 1].clone()),
            "--catalog" => catalog_mode = Some(args[i + 1].clone()),
            _ => {}
        }
        i += 2;
    }

    if let Some(mode_str) = catalog_mode {
        let mode = mode_str.parse::<BuildingMode>().unwrap_or(BuildingMode::Part9);
        let cat = RoomCatalog::for_mode(mode);
        println!(
            "{}",
            serde_json::to_string_pretty(&serde_json::json!({
                "mode": mode.as_str(),
                "room_types": cat.room_types(),
            })
            )
            .unwrap_or_default()
        );
        return;
    }

    if let Some(path) = manifest_path {
        let contents = std::fs::read_to_string(&path).unwrap_or_else(|e| {
            eprintln!("failed to read manifest {path}: {e}");
            std::process::exit(1);
        });
        let manifest = ProgramManifest::from_json(&contents).unwrap_or_else(|e| {
            eprintln!("failed to parse manifest: {e}");
            std::process::exit(1);
        });
        if let Err(errors) = manifest.validate() {
            println!(
                "{}",
                serde_json::to_string_pretty(
                    &serde_json::json!({ "success": false, "errors": errors })
                )
                .unwrap_or_default()
            );
            return;
        }
        let value = building_json_from_manifest(&manifest);
        println!("{}", serde_json::to_string_pretty(&value).unwrap_or_default());
        return;
    }

    let value = building_json(&a);
    println!("{}", serde_json::to_string_pretty(&value).unwrap_or_default());
}
