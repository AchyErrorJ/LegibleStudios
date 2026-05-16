//! `archgeometry_dump` — Rust counterpart to the C++ tool of the same name.
//!
//! Output is line-oriented and byte-equivalent to the C++ tool's so the
//! M1 diff oracle (`rust/tests/m1_diff.py`) can compare them directly.
//! Categories whose generators haven't been ported yet emit
//! `UNIMPLEMENTED` instead — the diff harness treats that as yellow.

use archgeometry::dump_hash::{Hasher, hash_mesh, hash_room};
use archgeometry::geometry_types::{
    BuildingGeometry, DoorGeometry, FloorGeometry, Mesh3D, RoofGeometry, RoomBoundary,
    WallGeometry, WindowGeometry,
};
use archgeometry::{generate_from_schema, parse_file};
use std::path::Path;
use std::process::ExitCode;

const FORMAT_VERSION: &str = "ARCHGEOMETRY_DUMP v1";

/// Categories with ported generators emit real hashes; the rest emit
/// `UNIMPLEMENTED` until their crate modules land.
const IMPLEMENTED_ROOFS: bool = false;
const IMPLEMENTED_DOORS: bool = false;
const IMPLEMENTED_WINDOWS: bool = false;
const IMPLEMENTED_ROOMS: bool = false;

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

    let filename = path.file_name().and_then(|n| n.to_str()).unwrap_or("?");

    let doc = match parse_file(path) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("error: {e}");
            return ExitCode::from(1);
        }
    };

    let g = generate_from_schema(&doc);

    println!("{FORMAT_VERSION}");
    println!("INPUT {filename}");
    print_building(&g);

    print_mesh_category("WALLS", &g.walls, |w| (w.wall_index, w.wall_id.as_str()), |w| &w.mesh_3d);
    print_mesh_category("FLOORS", &g.floors, |f| (f.floor_index, f.floor_id.as_str()), |f| &f.mesh_3d);

    if IMPLEMENTED_ROOFS {
        print_mesh_category("ROOFS", &g.roofs, |r| (r.roof_index, r.roof_id.as_str()), |r| &r.mesh_3d);
    } else {
        unimpl_mesh_category("ROOFS", &g.roofs);
    }
    if IMPLEMENTED_DOORS {
        print_mesh_category("DOORS", &g.doors, |d| (d.door_index, d.door_id.as_str()), |d| &d.mesh_3d);
    } else {
        unimpl_mesh_category("DOORS", &g.doors);
    }
    if IMPLEMENTED_WINDOWS {
        print_mesh_category(
            "WINDOWS",
            &g.windows,
            |w| (w.window_index, w.window_id.as_str()),
            |w| &w.mesh_3d,
        );
    } else {
        unimpl_mesh_category("WINDOWS", &g.windows);
    }
    if IMPLEMENTED_ROOMS {
        print_room_category(&g.rooms);
    } else {
        println!("{:<8} UNIMPLEMENTED", "ROOMS");
    }

    println!("END");
    ExitCode::SUCCESS
}

fn print_building(g: &BuildingGeometry) {
    let id = if g.building_id.is_empty() {
        "-"
    } else {
        g.building_id.as_str()
    };
    println!(
        "BUILDING id={id} bounds_min={:.4},{:.4},{:.4} bounds_max={:.4},{:.4},{:.4}",
        g.bounds_min.x,
        g.bounds_min.y,
        g.bounds_min.z,
        g.bounds_max.x,
        g.bounds_max.y,
        g.bounds_max.z,
    );
}

/// Stable-sort by `(index, id)` and accumulate vertex/triangle counts and
/// an FNV-1a hash of each mesh's vertex+index byte sequence.
fn print_mesh_category<T, K, M>(label: &str, items: &[T], key_of: K, mesh_of: M)
where
    K: for<'a> Fn(&'a T) -> (i32, &'a str),
    M: for<'a> Fn(&'a T) -> &'a Mesh3D,
{
    let mut order: Vec<usize> = (0..items.len()).collect();
    // Stable sort by (index, id) to match `std::stable_sort` in the C++.
    order.sort_by(|&a, &b| {
        let (ai, an) = key_of(&items[a]);
        let (bi, bn) = key_of(&items[b]);
        (ai, an).cmp(&(bi, bn))
    });

    let mut h = Hasher::new();
    let mut total_v: usize = 0;
    let mut total_t: usize = 0;
    for &idx in &order {
        let m = mesh_of(&items[idx]);
        hash_mesh(&mut h, m);
        total_v += m.vertices.len();
        total_t += m.faces.len();
    }

    println!(
        "{label:<8} count={count} vertices={total_v} triangles={total_t} hash=0x{state:016x}",
        count = items.len(),
        state = h.state,
    );
}

/// Same line format as `print_mesh_category` but with zero counts and the
/// FNV offset hash — so a yet-to-be-ported category whose schema input is
/// empty already matches the C++ output, and only the `UNIMPLEMENTED`
/// sentinel marks "this generator hasn't landed yet."
fn unimpl_mesh_category<T>(label: &str, _items: &[T]) {
    println!("{label:<8} UNIMPLEMENTED");
}

fn print_room_category(rooms: &[RoomBoundary]) {
    let mut order: Vec<usize> = (0..rooms.len()).collect();
    order.sort_by(|&a, &b| rooms[a].room_id.cmp(&rooms[b].room_id));

    let mut h = Hasher::new();
    for &idx in &order {
        hash_room(&mut h, &rooms[idx]);
    }

    println!(
        "{:<8} count={count} hash=0x{state:016x}",
        "ROOMS",
        count = rooms.len(),
        state = h.state,
    );
}

// Silence dead-code warnings on the type parameters used only as compile-
// time hints in the generic signature.
#[allow(dead_code)]
fn _type_hints() {
    let _w: &WallGeometry;
    let _f: &FloorGeometry;
    let _r: &RoofGeometry;
    let _d: &DoorGeometry;
    let _wn: &WindowGeometry;
}
