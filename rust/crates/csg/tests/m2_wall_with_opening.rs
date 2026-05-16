//! Milestone M2: CSG produces correct wall-with-opening geometry.
//!
//! Asserts topology + spatial properties for wall-minus-door and
//! wall-minus-(door+window) cases. These are the canonical CSG
//! operations the kernel's `Geometry::CSG::wallWithOpening` API
//! advertises — though in practice the kernel uses segment-based
//! cutouts (`wall_geometry.cpp:202`) rather than these CSG ops, which
//! is why the C++ CSG bug shipped unnoticed (see ops.rs preamble).
//!
//! Now that the C++ ops are corrected, both sides produce the same
//! geometry shape. Byte-for-byte cross-language diff (the M1 oracle
//! style) is left as future work — these unit tests assert spatial
//! correctness, which is the M2 acceptance criterion.

use csg::{mesh_difference, Mesh, Triangle};
use glam::Vec3;

/// Axis-aligned box from `min` to `max`. 12 triangles, CCW outward.
fn make_box(min: Vec3, max: Vec3) -> Mesh {
    let v = [
        Vec3::new(min.x, min.y, min.z),
        Vec3::new(max.x, min.y, min.z),
        Vec3::new(max.x, min.y, max.z),
        Vec3::new(min.x, min.y, max.z),
        Vec3::new(min.x, max.y, min.z),
        Vec3::new(max.x, max.y, min.z),
        Vec3::new(max.x, max.y, max.z),
        Vec3::new(min.x, max.y, max.z),
    ];
    let mut triangles = Vec::with_capacity(12);
    let mut push = |i: usize, j: usize, k: usize| {
        triangles.push(Triangle::new(v[i], v[j], v[k]));
    };
    push(0, 1, 2); push(0, 2, 3);     // -Y bottom
    push(4, 7, 6); push(4, 6, 5);     // +Y top
    push(0, 4, 5); push(0, 5, 1);     // -Z front
    push(3, 2, 6); push(3, 6, 7);     // +Z back
    push(0, 3, 7); push(0, 7, 4);     // -X left
    push(1, 5, 6); push(1, 6, 2);     // +X right
    Mesh { triangles }
}

/// Off-axis probe so the +X ray cast doesn't hit cube diagonals
/// (Möller-Trumbore double-counts shared edges).
fn probe(x: f32, y: f32, z: f32) -> Vec3 {
    Vec3::new(x + 0.13, y + 0.21, z + 0.07)
}

#[test]
fn wall_minus_door_carves_a_hole() {
    // Wall: 5 m long, 3 m tall, 150 mm thick at origin.
    let wall = make_box(Vec3::ZERO, Vec3::new(5000.0, 3000.0, 150.0));

    // Door: 1 m wide, 2.1 m tall, centred at X=2500. Goes ~10 mm beyond
    // the wall thickness on both sides so the CSG cut surfaces are
    // clean (the door's ±Z faces lie outside the wall, not coplanar).
    let door = make_box(
        Vec3::new(2000.0, 0.0, -10.0),
        Vec3::new(3000.0, 2100.0, 160.0),
    );

    let carved = mesh_difference(&wall, &door);
    assert!(!carved.triangles.is_empty(), "result should not be empty");

    // Probe in the surviving wall area (left of door).
    assert!(
        carved.contains_point(probe(500.0, 1000.0, 75.0)),
        "left of door is still wall"
    );
    // Probe in the surviving wall area (right of door).
    assert!(
        carved.contains_point(probe(4000.0, 1000.0, 75.0)),
        "right of door is still wall"
    );
    // Probe in the surviving wall area (above door header).
    assert!(
        carved.contains_point(probe(2500.0, 2700.0, 75.0)),
        "above door is still wall"
    );
    // Probe in the carved door void — should NOT be inside the result.
    assert!(
        !carved.contains_point(probe(2500.0, 1000.0, 75.0)),
        "door void is no longer wall"
    );
}

#[test]
fn wall_minus_door_plus_window_carves_two_holes() {
    // Wall: 8 m × 3 m × 150 mm.
    let wall = make_box(Vec3::ZERO, Vec3::new(8000.0, 3000.0, 150.0));

    // Door at X=1500, 1 m × 2.1 m.
    let door = make_box(
        Vec3::new(1000.0, 0.0, -10.0),
        Vec3::new(2000.0, 2100.0, 160.0),
    );
    // Window at X=5500, 1.2 m × 1.2 m, sill 900 mm.
    let window = make_box(
        Vec3::new(4900.0, 900.0, -10.0),
        Vec3::new(6100.0, 2100.0, 160.0),
    );

    // Sequential subtraction: (wall − door) − window.
    let after_door = mesh_difference(&wall, &door);
    let final_mesh = mesh_difference(&after_door, &window);

    assert!(!final_mesh.triangles.is_empty());

    // Door void: outside the result.
    assert!(!final_mesh.contains_point(probe(1500.0, 1000.0, 75.0)));
    // Window void: outside the result.
    assert!(!final_mesh.contains_point(probe(5500.0, 1500.0, 75.0)));

    // Wall below the window (under the sill, sill_height=900): still
    // inside the result.
    assert!(final_mesh.contains_point(probe(5500.0, 400.0, 75.0)));
    // Wall above the window header (above 2100): still inside.
    assert!(final_mesh.contains_point(probe(5500.0, 2700.0, 75.0)));
    // Wall between door and window: still inside.
    assert!(final_mesh.contains_point(probe(3500.0, 1500.0, 75.0)));
}

#[test]
fn wall_minus_door_topology_grows_with_carving() {
    // Sanity: the carved wall has MORE triangles than the original
    // (cutout introduces inner surface fragments + splits outer faces).
    let wall = make_box(Vec3::ZERO, Vec3::new(5000.0, 3000.0, 150.0));
    let door = make_box(
        Vec3::new(2000.0, 0.0, -10.0),
        Vec3::new(3000.0, 2100.0, 160.0),
    );
    let carved = mesh_difference(&wall, &door);
    assert!(
        carved.triangles.len() > wall.triangles.len(),
        "carving should add inner-surface triangles ({} > {})",
        carved.triangles.len(),
        wall.triangles.len()
    );
}

#[test]
fn wall_minus_door_bounds_stay_within_wall_bounds() {
    // Carving removes material — it should never push the bounding box
    // outside the original wall (the door is fully contained on ±Y and
    // straddles ±Z slightly, but the wall's Z extent dominates).
    let wall = make_box(Vec3::ZERO, Vec3::new(5000.0, 3000.0, 150.0));
    let door = make_box(
        Vec3::new(2000.0, 0.0, -10.0),
        Vec3::new(3000.0, 2100.0, 160.0),
    );
    let carved = mesh_difference(&wall, &door);
    let (min, max) = carved.bounds();
    // X: stays within wall's [0, 5000].
    assert!(min.x >= -0.01);
    assert!(max.x <= 5000.01);
    // Y: stays within wall's [0, 3000].
    assert!(min.y >= -0.01);
    assert!(max.y <= 3000.01);
    // Z: door surface fragments inherit door's Z extent [-10, 160] but
    // those will be CLIPPED to the wall's [0, 150]. Allow small slop.
    assert!(min.z >= -0.01);
    assert!(max.z <= 150.01);
}
