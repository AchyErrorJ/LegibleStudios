//! Boolean CSG operations on triangle meshes: union, intersection,
//! difference. Plus mesh ↔ vertex/index conversion helpers.
//!
//! Matches the C++ implementation in `csg.cpp` AFTER the 2026-05-16
//! semantics fix. The original C++ inverted the BSP before `clipTo`
//! which reversed the meaning of clip_to and made union/difference
//! produce intersection-like geometry. Both halves now follow the
//! reference BSP-CSG algorithm (Evan Wallace's csg.js):
//!
//! ```text
//! clip_to(against)  := keep parts OUTSIDE the volume of `against`
//!
//! union(A, B):     keep A outside B, keep B outside A
//! intersection(A, B): keep A inside B, keep B inside A
//! difference(A, B): keep A outside B, keep B inside A (flipped)
//! ```
//!
//! "Keep inside" is implemented as `bsp.invert(); bsp.clip_to(tris);
//! bsp.invert()` — invert flips outside/inside semantics, the restore
//! avoids mutating the caller's tree (matches C++).

use crate::bsp::BSPNode;
use crate::mesh::{Mesh, Triangle};
use glam::Vec3;

/// CPU vertex emitted by `mesh_to_vertices_indices`. Mirrors
/// `domain::Vertex` but kept local to keep the crate boundary tight.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct OutVertex {
    pub position: Vec3,
    pub normal: Vec3,
    pub color: Vec3,
}

/// Union: A ∪ B. Keeps every part of A outside B and every part of B
/// outside A. Coplanar shared faces are kept once each (BSP coplanar
/// handling shunts them to front).
#[must_use]
pub fn mesh_union(a: &Mesh, b: &Mesh) -> Mesh {
    let bsp_a = BSPNode::build(a.triangles.clone());
    let bsp_b = BSPNode::build(b.triangles.clone());

    match (bsp_a, bsp_b) {
        (None, None) => Mesh::default(),
        (Some(_), None) => a.clone(),
        (None, Some(_)) => b.clone(),
        (Some(tree_a), Some(tree_b)) => {
            let mut a_outside = a.triangles.clone();
            tree_b.clip_to(&mut a_outside);

            let mut b_outside = b.triangles.clone();
            tree_a.clip_to(&mut b_outside);

            let mut triangles = a_outside;
            triangles.append(&mut b_outside);
            Mesh { triangles }
        }
    }
}

/// Intersection: A ∩ B. Keeps parts of A inside B and parts of B inside A.
#[must_use]
pub fn mesh_intersection(a: &Mesh, b: &Mesh) -> Mesh {
    let bsp_a = BSPNode::build(a.triangles.clone());
    let bsp_b = BSPNode::build(b.triangles.clone());

    match (bsp_a, bsp_b) {
        (Some(mut tree_a), Some(mut tree_b)) => {
            let mut a_inside = a.triangles.clone();
            tree_b.invert();
            tree_b.clip_to(&mut a_inside);
            tree_b.invert();

            let mut b_inside = b.triangles.clone();
            tree_a.invert();
            tree_a.clip_to(&mut b_inside);
            tree_a.invert();

            let mut triangles = a_inside;
            triangles.append(&mut b_inside);
            Mesh { triangles }
        }
        _ => Mesh::default(),
    }
}

/// Difference: A − B. Keeps:
/// 1. Parts of A outside B (the carved outer surface).
/// 2. Parts of B inside A, with reversed winding + normals so they face
///    into the carved-out void (the inner hole surface).
#[must_use]
pub fn mesh_difference(a: &Mesh, b: &Mesh) -> Mesh {
    let bsp_a = BSPNode::build(a.triangles.clone());
    let bsp_b = BSPNode::build(b.triangles.clone());

    let Some(mut tree_a) = bsp_a else {
        return Mesh::default();
    };
    let Some(tree_b) = bsp_b else {
        return a.clone();
    };

    // Parts of A outside B
    let mut a_outside = a.triangles.clone();
    tree_b.clip_to(&mut a_outside);

    // Parts of B inside A
    let mut b_inside = b.triangles.clone();
    tree_a.invert();
    tree_a.clip_to(&mut b_inside);
    tree_a.invert();

    // Flip the inner-surface fragments so their normals point into the hole.
    for tri in &mut b_inside {
        tri.v.swap(0, 2);
        tri.normal = -tri.normal;
    }

    let mut triangles = a_outside;
    triangles.append(&mut b_inside);
    Mesh { triangles }
}

/// Convert a mesh to flat vertex/index arrays. Every triangle gets its
/// own three vertices (no sharing) — matches the C++ behaviour.
#[must_use]
pub fn mesh_to_vertices_indices(mesh: &Mesh, color: Vec3) -> (Vec<OutVertex>, Vec<u32>) {
    let mut vertices = Vec::with_capacity(mesh.triangles.len() * 3);
    let mut indices = Vec::with_capacity(mesh.triangles.len() * 3);

    for tri in &mesh.triangles {
        #[allow(clippy::cast_possible_truncation)]
        let base = vertices.len() as u32;
        for i in 0..3 {
            vertices.push(OutVertex {
                position: tri.v[i],
                normal: tri.normal,
                color,
            });
        }
        indices.push(base);
        indices.push(base + 1);
        indices.push(base + 2);
    }

    (vertices, indices)
}

/// Inverse: build a `Mesh` from flat vertex/index arrays. Uses positions
/// only (CSG doesn't need the other vertex attributes during ops).
#[must_use]
pub fn vertices_indices_to_mesh(verts: &[OutVertex], indices: &[u32]) -> Mesh {
    let mut triangles = Vec::with_capacity(indices.len() / 3);
    let mut i = 0;
    while i + 2 < indices.len() {
        triangles.push(Triangle::new(
            verts[indices[i] as usize].position,
            verts[indices[i + 1] as usize].position,
            verts[indices[i + 2] as usize].position,
        ));
        i += 3;
    }
    Mesh { triangles }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mesh::tests::unit_cube;
    use glam::Vec3;

    fn translate(mesh: &Mesh, offset: Vec3) -> Mesh {
        Mesh {
            triangles: mesh
                .triangles
                .iter()
                .map(|t| Triangle::new(t.v[0] + offset, t.v[1] + offset, t.v[2] + offset))
                .collect(),
        }
    }

    #[test]
    fn union_of_disjoint_cubes_keeps_full_surface_of_both() {
        // Two unit cubes with no shared volume → union keeps every
        // surface triangle.
        let a = unit_cube();
        let b = translate(&a, Vec3::new(5.0, 0.0, 0.0));
        let result = mesh_union(&a, &b);
        assert_eq!(
            result.triangles.len(),
            24,
            "12 per cube × 2 cubes, none removed"
        );
    }

    #[test]
    fn intersection_of_disjoint_cubes_is_empty() {
        let a = unit_cube();
        let b = translate(&a, Vec3::new(5.0, 0.0, 0.0));
        let result = mesh_intersection(&a, &b);
        assert_eq!(result.triangles.len(), 0);
    }

    #[test]
    fn difference_minus_disjoint_returns_a() {
        let a = unit_cube();
        let b = translate(&a, Vec3::new(5.0, 0.0, 0.0));
        let result = mesh_difference(&a, &b);
        assert_eq!(result.triangles.len(), a.triangles.len());
    }

    #[test]
    fn difference_of_overlapping_cubes_carves_a_chunk() {
        // Cube A centered at origin (range -1..1 on each axis); cube B
        // translated +0.5 X (range -0.5..1.5 in X). Difference A − B
        // removes the overlap region (X in [-0.5, 1.0]) from A.
        let a = unit_cube();
        let b = translate(&a, Vec3::new(0.5, 0.0, 0.0));
        let result = mesh_difference(&a, &b);
        assert!(!result.triangles.is_empty());
        // (-0.8, 0.2, 0.3) is in A (X=-0.8 ∈ [-1, 1]) but NOT in B
        // (X=-0.8 < -0.5), so it survives A − B.
        assert!(
            result.contains_point(Vec3::new(-0.8, 0.2, 0.3)),
            "uncarved -X half still inside"
        );
        // (0.7, 0.1, 0.2) is in both → carved away from A.
        assert!(!result.contains_point(Vec3::new(0.7, 0.1, 0.2)));
    }

    #[test]
    fn mesh_to_vertices_indices_emits_3_verts_per_triangle() {
        let cube = unit_cube();
        let n = cube.triangles.len();
        let (verts, indices) = mesh_to_vertices_indices(&cube, Vec3::splat(0.5));
        assert_eq!(verts.len(), n * 3);
        assert_eq!(indices.len(), n * 3);
        // Color propagates to every vertex.
        assert!(verts.iter().all(|v| v.color == Vec3::splat(0.5)));
    }

    #[test]
    fn vertices_indices_to_mesh_round_trips() {
        let cube = unit_cube();
        let (verts, indices) = mesh_to_vertices_indices(&cube, Vec3::ZERO);
        let back = vertices_indices_to_mesh(&verts, &indices);
        assert_eq!(back.triangles.len(), cube.triangles.len());
    }
}
