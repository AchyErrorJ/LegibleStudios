//! High-level generation: `SchemaDocument` → `BuildingGeometry`.
//!
//! Port of `ArchGeometry::generateFromSchema` (`Shared/ArchGeometry/src/archgeometry.cpp:75`).
//!
//! Behaviour intentionally identical to the C++:
//! - Walls without a matching entry in `wall_types` fall back to a 150 mm
//!   "default" wall type (`generateFromSchema:80-87`).
//! - Doors/windows are filtered onto their host wall by `wall_index`.
//! - `BuildingGeometry::bounds_min/bounds_max` are NOT computed here (they
//!   stay at the default `Vec3::ZERO`) to mirror the C++ behaviour — the
//!   M1 diff oracle depends on the same bytes coming out.

use crate::geometry_types::BuildingGeometry;
use crate::schema_types::{SchemaDocument, WallLayer, WallType};
use crate::{floor_geometry, wall_geometry};

/// Generate full building geometry from a parsed schema document.
#[must_use]
pub fn generate_from_schema(doc: &SchemaDocument) -> BuildingGeometry {
    let mut result = BuildingGeometry {
        building_id: doc.building_id.clone(),
        ..Default::default()
    };

    let default_wall_type = WallType {
        id: "default".into(),
        name: "Default Wall".into(),
        layers: vec![WallLayer {
            name: "structure".into(),
            thickness: 150.0,
            ..Default::default()
        }],
    };

    // Walls. The schema's `wall_types` is a Vec; the C++ uses a map keyed
    // by id, so look up by id linearly here.
    let wall_type_by_id = |id: &str| -> Option<&WallType> {
        doc.wall_types.iter().find(|wt| wt.id == id)
    };

    for (i, wall) in doc.walls.iter().enumerate() {
        let wt = wall_type_by_id(&wall.wall_type).unwrap_or(&default_wall_type);

        let i_i32 = i32::try_from(i).expect("wall index fits in i32");
        let doors_on_wall: Vec<_> = doc
            .doors
            .iter()
            .filter(|d| d.wall_index == i_i32)
            .cloned()
            .collect();
        let windows_on_wall: Vec<_> = doc
            .windows
            .iter()
            .filter(|w| w.wall_index == i_i32)
            .cloned()
            .collect();

        let geom = wall_geometry::generate(wall, wt, &doors_on_wall, &windows_on_wall);
        result.walls.push(geom);
    }

    // Floors.
    for floor in &doc.floors {
        result.floors.push(floor_geometry::generate(floor));
    }

    // Roofs / doors / windows / rooms: generators not yet ported.
    // Leaving result.roofs / .doors / .windows / .rooms empty matches the
    // pre-implementation state of those modules; the diff oracle treats
    // their dump lines as UNIMPLEMENTED until the generators land.

    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse_file;
    use std::path::PathBuf;

    fn fixture(name: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../..")
            .join("test-data")
            .join(name)
    }

    #[test]
    fn corpus_generates_walls_and_floors() {
        let doc = parse_file(fixture("test_building_qbd.json")).unwrap();
        let g = generate_from_schema(&doc);

        // 8 walls × 24 verts each (no openings in this fixture, default thickness).
        assert_eq!(g.walls.len(), 8);
        for w in &g.walls {
            assert_eq!(w.mesh_3d.vertex_count(), 24);
        }
        // 3 floors.
        assert_eq!(g.floors.len(), 3);
        // No roofs / doors / windows / rooms in this fixture.
        assert!(g.roofs.is_empty());
        assert!(g.doors.is_empty());
        assert!(g.windows.is_empty());
        assert!(g.rooms.is_empty());
    }
}
