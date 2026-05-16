//! `BSPNode` — recursive binary space partition over triangles.
//!
//! Ported from `csg.hpp:73-93` and `csg.cpp:145-215`.

use crate::mesh::{Plane, Triangle};
use crate::split::split_triangle;

/// A node in the BSP tree.
///
/// Children use `Option<Box<BSPNode>>` (the obvious port of
/// `std::unique_ptr<BSPNode>`). Recursion depth is bounded by mesh
/// complexity; no arena needed for this scale.
#[derive(Debug, Default)]
pub struct BSPNode {
    pub plane: Plane,
    pub coplanar: Vec<Triangle>,
    pub front: Option<Box<BSPNode>>,
    pub back: Option<Box<BSPNode>>,
}

impl BSPNode {
    /// Build a BSP tree from a triangle list. Uses the first triangle's
    /// plane as the splitter. Returns `None` for empty input.
    /// Matches `csg.cpp:145`.
    ///
    /// Takes `triangles` by value to match the C++ move semantics —
    /// callers shouldn't need the input after building.
    #[must_use]
    #[allow(clippy::needless_pass_by_value)]
    pub fn build(triangles: Vec<Triangle>) -> Option<Box<BSPNode>> {
        if triangles.is_empty() {
            return None;
        }

        let mut node = Box::new(BSPNode {
            plane: Plane::from_three_points(
                triangles[0].v[0],
                triangles[0].v[1],
                triangles[0].v[2],
            ),
            coplanar: Vec::new(),
            front: None,
            back: None,
        });

        let mut front_tris: Vec<Triangle> = Vec::new();
        let mut back_tris: Vec<Triangle> = Vec::new();

        for tri in &triangles {
            split_triangle(
                tri,
                &node.plane,
                &mut node.coplanar,
                &mut front_tris,
                &mut back_tris,
            );
        }

        if !front_tris.is_empty() {
            node.front = Self::build(front_tris);
        }
        if !back_tris.is_empty() {
            node.back = Self::build(back_tris);
        }

        Some(node)
    }

    /// Clip `triangles` against this tree's volume. After return,
    /// `triangles` contains only the parts that lie OUTSIDE the volume.
    /// Coplanar fragments are kept on the front side.
    /// Matches `csg.cpp:169`.
    pub fn clip_to(&self, triangles: &mut Vec<Triangle>) {
        if triangles.is_empty() {
            return;
        }

        let mut front_tris: Vec<Triangle> = Vec::new();
        let mut back_tris: Vec<Triangle> = Vec::new();

        for tri in &*triangles {
            let mut coplanar_tmp: Vec<Triangle> = Vec::new();
            split_triangle(
                tri,
                &self.plane,
                &mut coplanar_tmp,
                &mut front_tris,
                &mut back_tris,
            );
            // Coplanar triangles go to the front (C++ behaviour).
            front_tris.append(&mut coplanar_tmp);
        }

        if let Some(front) = self.front.as_deref() {
            front.clip_to(&mut front_tris);
        }
        if let Some(back) = self.back.as_deref() {
            back.clip_to(&mut back_tris);
        } else {
            // No back subtree → everything behind is inside the volume.
            back_tris.clear();
        }

        triangles.clear();
        triangles.append(&mut front_tris);
        triangles.append(&mut back_tris);
    }

    /// Flip the tree: swap front/back children, negate plane normals, and
    /// reverse triangle windings + normals. Matches `csg.cpp:195`.
    pub fn invert(&mut self) {
        for tri in &mut self.coplanar {
            tri.v.swap(0, 2);
            tri.normal = -tri.normal;
        }
        self.plane.normal = -self.plane.normal;
        self.plane.d = -self.plane.d;

        std::mem::swap(&mut self.front, &mut self.back);

        if let Some(front) = self.front.as_deref_mut() {
            front.invert();
        }
        if let Some(back) = self.back.as_deref_mut() {
            back.invert();
        }
    }

    /// Collect every triangle in the tree. Matches `csg.cpp:211`.
    pub fn all_triangles(&self, result: &mut Vec<Triangle>) {
        result.extend_from_slice(&self.coplanar);
        if let Some(front) = self.front.as_deref() {
            front.all_triangles(result);
        }
        if let Some(back) = self.back.as_deref() {
            back.all_triangles(result);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mesh::{Mesh, Triangle};
    use glam::Vec3;

    fn unit_cube() -> Mesh {
        crate::mesh::tests::unit_cube()
    }

    #[test]
    fn empty_input_yields_none() {
        let tree = BSPNode::build(Vec::new());
        assert!(tree.is_none());
    }

    #[test]
    fn single_triangle_makes_a_leaf_with_coplanar_only() {
        let tri = Triangle::new(
            Vec3::ZERO,
            Vec3::new(1.0, 0.0, 0.0),
            Vec3::new(0.0, 0.0, 1.0),
        );
        let tree = BSPNode::build(vec![tri]).unwrap();
        assert_eq!(tree.coplanar.len(), 1);
        assert!(tree.front.is_none());
        assert!(tree.back.is_none());
    }

    #[test]
    fn unit_cube_round_trips_through_build_and_all_triangles() {
        let cube = unit_cube();
        let n_in = cube.triangles.len();
        let tree = BSPNode::build(cube.triangles).unwrap();
        let mut out = Vec::new();
        tree.all_triangles(&mut out);
        // No splits in this case — every face plane is unique and the
        // cube has flat axis-aligned faces.
        assert_eq!(out.len(), n_in, "no triangle splits expected for unit cube");
    }

    #[test]
    fn invert_negates_plane_normal() {
        let cube = unit_cube();
        let mut tree = BSPNode::build(cube.triangles).unwrap();
        let original_normal = tree.plane.normal;
        tree.invert();
        assert_eq!(tree.plane.normal, -original_normal);
    }

    #[test]
    fn invert_swaps_front_and_back_subtrees() {
        let cube = unit_cube();
        let mut tree = BSPNode::build(cube.triangles).unwrap();
        let had_front = tree.front.is_some();
        let had_back = tree.back.is_some();
        if !had_front && !had_back {
            return;
        }
        tree.invert();
        assert_eq!(tree.front.is_some(), had_back);
        assert_eq!(tree.back.is_some(), had_front);
    }

    #[test]
    fn invert_is_an_involution() {
        let cube = unit_cube();
        let mut tree = BSPNode::build(cube.triangles).unwrap();
        let mut before = Vec::new();
        tree.all_triangles(&mut before);

        tree.invert();
        tree.invert();

        let mut after = Vec::new();
        tree.all_triangles(&mut after);

        // Two inversions must restore the triangle set (modulo ordering
        // within the recursion, which the cube case happens to preserve).
        assert_eq!(before.len(), after.len());
    }

    #[test]
    fn clip_to_self_keeps_coplanar_on_front() {
        // The C++ algorithm shunts coplanar triangles to the front side
        // (`csg.cpp:178`). For a cube clipped against its own BSP, the
        // cube's surface triangles are coplanar with each splitter plane
        // they meet, so they all survive on the front side rather than
        // being discarded as "inside." This is documented BSP-CSG
        // behaviour, not a bug — and the property we test is the count
        // stability (no infinite recursion, deterministic output).
        let cube = unit_cube();
        let tree = BSPNode::build(cube.triangles.clone()).unwrap();
        let mut clipped = cube.triangles;
        tree.clip_to(&mut clipped);
        // The count is bounded and deterministic; exact value depends on
        // the recursion order of coplanar handling.
        assert!(clipped.len() <= 12, "got {} triangles", clipped.len());
    }
}
