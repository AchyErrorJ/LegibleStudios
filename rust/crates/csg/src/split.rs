//! `split_triangle` — partition a triangle against a plane into coplanar,
//! front, and back triangle lists.
//!
//! Ported from `csg.cpp:71-141`. Fan-triangulates the front and back
//! polygons. Coplanar triangles are kept whole.

use crate::mesh::{Plane, Side, Triangle};

/// Split `tri` against `plane`. Appends to `coplanar`, `front`, `back`.
///
/// - Triangle entirely on the plane → `coplanar`.
/// - Triangle entirely on one side → that side.
/// - Triangle spans the plane → split along the intersection edge, then
///   each polygon is fan-triangulated from its first vertex.
pub fn split_triangle(
    tri: &Triangle,
    plane: &Plane,
    coplanar: &mut Vec<Triangle>,
    front: &mut Vec<Triangle>,
    back: &mut Vec<Triangle>,
) {
    let mut types = [Side::On; 3];
    let mut dists = [0.0_f32; 3];
    let mut front_count = 0;
    let mut back_count = 0;

    for i in 0..3 {
        dists[i] = plane.signed_distance(tri.v[i]);
        types[i] = plane.classify(tri.v[i]);
        match types[i] {
            Side::Front => front_count += 1,
            Side::Back => back_count += 1,
            Side::On => {}
        }
    }

    // All on the plane.
    if front_count == 0 && back_count == 0 {
        coplanar.push(*tri);
        return;
    }
    // No back-side vertices → triangle is entirely in front.
    if back_count == 0 {
        front.push(*tri);
        return;
    }
    // No front-side vertices → triangle is entirely behind.
    if front_count == 0 {
        back.push(*tri);
        return;
    }

    // Triangle spans the plane — split along the intersection edge.
    let mut front_verts = Vec::with_capacity(4);
    let mut back_verts = Vec::with_capacity(4);

    for i in 0..3 {
        let j = (i + 1) % 3;
        let vi = tri.v[i];
        let vj = tri.v[j];

        if types[i] != Side::Back {
            front_verts.push(vi);
        }
        if types[i] != Side::Front {
            back_verts.push(vi);
        }

        // Only split the edge when the two endpoints are strictly on
        // opposite sides (Front × Back or Back × Front).
        let crosses_plane = matches!(
            (types[i], types[j]),
            (Side::Front, Side::Back) | (Side::Back, Side::Front)
        );
        if !crosses_plane {
            continue;
        }

        let t = dists[i] / (dists[i] - dists[j]);
        let intersection = vi + (vj - vi) * t;
        front_verts.push(intersection);
        back_verts.push(intersection);
    }

    // Fan-triangulate the front polygon.
    if front_verts.len() >= 3 {
        for i in 1..front_verts.len() - 1 {
            front.push(Triangle::new(
                front_verts[0],
                front_verts[i],
                front_verts[i + 1],
            ));
        }
    }
    // Fan-triangulate the back polygon.
    if back_verts.len() >= 3 {
        for i in 1..back_verts.len() - 1 {
            back.push(Triangle::new(
                back_verts[0],
                back_verts[i],
                back_verts[i + 1],
            ));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use glam::Vec3;

    /// Y=0 plane, normal +Y.
    fn xz_plane() -> Plane {
        Plane::from_normal_distance(Vec3::Y, 0.0)
    }

    #[test]
    fn triangle_entirely_above_plane_goes_to_front() {
        let tri = Triangle::new(
            Vec3::new(0.0, 1.0, 0.0),
            Vec3::new(1.0, 1.0, 0.0),
            Vec3::new(0.0, 1.0, 1.0),
        );
        let (mut c, mut f, mut b) = (Vec::new(), Vec::new(), Vec::new());
        split_triangle(&tri, &xz_plane(), &mut c, &mut f, &mut b);
        assert_eq!(c.len(), 0);
        assert_eq!(f.len(), 1);
        assert_eq!(b.len(), 0);
    }

    #[test]
    fn triangle_entirely_below_plane_goes_to_back() {
        let tri = Triangle::new(
            Vec3::new(0.0, -1.0, 0.0),
            Vec3::new(1.0, -1.0, 0.0),
            Vec3::new(0.0, -1.0, 1.0),
        );
        let (mut c, mut f, mut b) = (Vec::new(), Vec::new(), Vec::new());
        split_triangle(&tri, &xz_plane(), &mut c, &mut f, &mut b);
        assert_eq!(c.len(), 0);
        assert_eq!(f.len(), 0);
        assert_eq!(b.len(), 1);
    }

    #[test]
    fn triangle_lying_on_plane_is_coplanar() {
        let tri = Triangle::new(
            Vec3::new(0.0, 0.0, 0.0),
            Vec3::new(1.0, 0.0, 0.0),
            Vec3::new(0.0, 0.0, 1.0),
        );
        let (mut c, mut f, mut b) = (Vec::new(), Vec::new(), Vec::new());
        split_triangle(&tri, &xz_plane(), &mut c, &mut f, &mut b);
        assert_eq!(c.len(), 1);
        assert_eq!(f.len(), 0);
        assert_eq!(b.len(), 0);
    }

    #[test]
    fn triangle_spanning_plane_splits_into_one_front_one_back() {
        // Two verts above the plane, one below → 1 quad (2 tris) front,
        // 1 triangle back.
        let tri = Triangle::new(
            Vec3::new(0.0, 1.0, 0.0),
            Vec3::new(1.0, 1.0, 0.0),
            Vec3::new(0.5, -1.0, 0.0),
        );
        let (mut c, mut f, mut b) = (Vec::new(), Vec::new(), Vec::new());
        split_triangle(&tri, &xz_plane(), &mut c, &mut f, &mut b);
        assert_eq!(c.len(), 0);
        assert_eq!(f.len(), 2, "front polygon (quad) fans into 2 triangles");
        assert_eq!(b.len(), 1, "back polygon (triangle) stays as 1");
    }
}
