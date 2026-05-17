//! `Triangle`, `Plane`, and `Mesh` — the data types CSG operates on.
//!
//! Ported from `csg.hpp` lines 17-63 and `csg.cpp` lines 12-67.

use crate::EPSILON;
use glam::Vec3;

/// A single triangle with a precomputed face normal.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Triangle {
    pub v: [Vec3; 3],
    pub normal: Vec3,
}

impl Triangle {
    /// Build a triangle from three vertices, deriving the normal from
    /// `normalize(cross(b - a, c - a))`.
    #[must_use]
    pub fn new(a: Vec3, b: Vec3, c: Vec3) -> Self {
        let normal = (b - a).cross(c - a).normalize();
        Self {
            v: [a, b, c],
            normal,
        }
    }

    #[must_use]
    pub fn center(&self) -> Vec3 {
        (self.v[0] + self.v[1] + self.v[2]) / 3.0
    }
}

/// Plane in Hessian normal form: `dot(normal, p) + d = 0`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Plane {
    pub normal: Vec3,
    pub d: f32,
}

impl Default for Plane {
    fn default() -> Self {
        Self {
            normal: Vec3::Y,
            d: 0.0,
        }
    }
}

/// Classification for a point against a plane.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Back = -1,
    On = 0,
    Front = 1,
}

impl Plane {
    /// Build a plane from a normal and distance term.
    #[must_use]
    pub fn from_normal_distance(normal: Vec3, d: f32) -> Self {
        Self {
            normal: normal.normalize(),
            d,
        }
    }

    /// Build a plane from three points on it (CCW front-facing).
    /// Matches `csg.cpp:64`.
    #[must_use]
    pub fn from_three_points(a: Vec3, b: Vec3, c: Vec3) -> Self {
        let normal = (b - a).cross(c - a).normalize();
        let d = -normal.dot(a);
        Self { normal, d }
    }

    /// Signed distance from `p` to the plane. Positive = in front.
    #[must_use]
    pub fn signed_distance(&self, p: Vec3) -> f32 {
        self.normal.dot(p) + self.d
    }

    /// Classify `p` against the plane using `EPSILON`. Matches
    /// `csg.hpp:56`.
    #[must_use]
    pub fn classify(&self, p: Vec3) -> Side {
        let dist = self.signed_distance(p);
        if dist > EPSILON {
            Side::Front
        } else if dist < -EPSILON {
            Side::Back
        } else {
            Side::On
        }
    }
}

/// A triangle soup. CSG operations consume `Mesh`es and produce a new one.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Mesh {
    pub triangles: Vec<Triangle>,
}

impl Mesh {
    /// Build a mesh from a flat vertex array + face-index array. Matches
    /// `csg.cpp:12`.
    #[must_use]
    pub fn from_vertices_indices(verts: &[Vec3], faces: &[[u32; 3]]) -> Self {
        let mut triangles = Vec::with_capacity(faces.len());
        for f in faces {
            triangles.push(Triangle::new(
                verts[f[0] as usize],
                verts[f[1] as usize],
                verts[f[2] as usize],
            ));
        }
        Self { triangles }
    }

    /// Axis-aligned bounds. Returns `(min, max)`. Empty mesh returns the
    /// C++ sentinel of `(+1e9, -1e9)` so callers can detect emptiness.
    #[must_use]
    pub fn bounds(&self) -> (Vec3, Vec3) {
        let mut min = Vec3::splat(1e9);
        let mut max = Vec3::splat(-1e9);
        for tri in &self.triangles {
            for v in tri.v {
                min = min.min(v);
                max = max.max(v);
            }
        }
        (min, max)
    }

    /// Point-in-mesh test via ray casting along +X. Counts triangle
    /// intersections and returns true on odd parity. Möller-Trumbore.
    /// Matches `csg.cpp:33`.
    #[must_use]
    #[allow(clippy::many_single_char_names)] // a/f/u/v/t/h/s/q are the standard Möller-Trumbore symbols
    pub fn contains_point(&self, p: Vec3) -> bool {
        let dir = Vec3::X;
        let mut count: i32 = 0;

        for tri in &self.triangles {
            let edge1 = tri.v[1] - tri.v[0];
            let edge2 = tri.v[2] - tri.v[0];
            let h = dir.cross(edge2);
            let a = edge1.dot(h);
            if a.abs() < EPSILON {
                continue;
            }

            let f = 1.0 / a;
            let s = p - tri.v[0];
            let u = f * s.dot(h);
            if !(0.0..=1.0).contains(&u) {
                continue;
            }

            let q = s.cross(edge1);
            let v = f * dir.dot(q);
            if v < 0.0 || u + v > 1.0 {
                continue;
            }

            let t = f * edge2.dot(q);
            if t > EPSILON {
                count += 1;
            }
        }

        count % 2 == 1
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    #[test]
    fn triangle_normal_follows_right_hand_rule() {
        // Triangle::new(a, b, c) computes normal = normalize(cross(b-a, c-a)).
        // For a in -Y up direction, vertices going (0,0,0) → (1,0,0) → (0,0,1)
        // are clockwise when viewed from +Y, so the normal points -Y.
        let t = Triangle::new(
            Vec3::ZERO,
            Vec3::new(1.0, 0.0, 0.0),
            Vec3::new(0.0, 0.0, 1.0),
        );
        assert!((t.normal - Vec3::new(0.0, -1.0, 0.0)).length() < 1e-6);
        assert!((t.normal.length() - 1.0).abs() < 1e-6);
    }

    #[test]
    fn triangle_center_averages_vertices() {
        let t = Triangle::new(
            Vec3::ZERO,
            Vec3::new(3.0, 0.0, 0.0),
            Vec3::new(0.0, 0.0, 6.0),
        );
        assert_eq!(t.center(), Vec3::new(1.0, 0.0, 2.0));
    }

    #[test]
    fn plane_from_three_points_has_d_negative_normal_dot_a() {
        // Same right-hand-rule winding as Triangle::new. To get +Y normal,
        // go CCW when viewed from +Y: a → c → b in screen order.
        let p = Plane::from_three_points(
            Vec3::new(0.0, 1.0, 0.0),
            Vec3::new(0.0, 1.0, 1.0),
            Vec3::new(1.0, 1.0, 0.0),
        );
        // Y=1 plane, normal=+Y, d=-1.
        assert!((p.normal - Vec3::Y).length() < 1e-6);
        assert!((p.d + 1.0).abs() < 1e-6);
    }

    #[test]
    fn classify_uses_epsilon_band() {
        let p = Plane::from_normal_distance(Vec3::Y, 0.0);
        // Within EPSILON either side → On.
        assert_eq!(p.classify(Vec3::new(0.0, EPSILON * 0.5, 0.0)), Side::On);
        assert_eq!(p.classify(Vec3::new(0.0, -EPSILON * 0.5, 0.0)), Side::On);
        // Clearly above/below.
        assert_eq!(p.classify(Vec3::new(0.0, 1.0, 0.0)), Side::Front);
        assert_eq!(p.classify(Vec3::new(0.0, -1.0, 0.0)), Side::Back);
    }

    #[test]
    fn signed_distance_matches_plane_math() {
        let p = Plane::from_normal_distance(Vec3::Y, -5.0);
        // Y=5 plane: point (0, 10, 0) → distance +5.
        assert!((p.signed_distance(Vec3::new(0.0, 10.0, 0.0)) - 5.0).abs() < 1e-6);
        assert!((p.signed_distance(Vec3::new(0.0, 0.0, 0.0)) + 5.0).abs() < 1e-6);
    }

    #[test]
    fn from_vertices_indices_constructs_correct_triangle_count() {
        let verts = vec![
            Vec3::ZERO,
            Vec3::new(1.0, 0.0, 0.0),
            Vec3::new(0.0, 0.0, 1.0),
            Vec3::new(1.0, 0.0, 1.0),
        ];
        let faces = vec![[0, 1, 2], [1, 3, 2]];
        let mesh = Mesh::from_vertices_indices(&verts, &faces);
        assert_eq!(mesh.triangles.len(), 2);
    }

    #[test]
    fn bounds_span_all_vertices() {
        let verts = vec![
            Vec3::new(-1.0, -2.0, -3.0),
            Vec3::new(4.0, 5.0, 6.0),
            Vec3::new(0.0, 0.0, 0.0),
        ];
        let mesh = Mesh::from_vertices_indices(&verts, &[[0, 1, 2]]);
        let (min, max) = mesh.bounds();
        assert_eq!(min, Vec3::new(-1.0, -2.0, -3.0));
        assert_eq!(max, Vec3::new(4.0, 5.0, 6.0));
    }

    /// Unit cube centered at origin (8 verts, 12 triangles, CCW outward).
    pub fn unit_cube() -> Mesh {
        let verts = vec![
            // bottom
            Vec3::new(-1.0, -1.0, -1.0),
            Vec3::new(1.0, -1.0, -1.0),
            Vec3::new(1.0, -1.0, 1.0),
            Vec3::new(-1.0, -1.0, 1.0),
            // top
            Vec3::new(-1.0, 1.0, -1.0),
            Vec3::new(1.0, 1.0, -1.0),
            Vec3::new(1.0, 1.0, 1.0),
            Vec3::new(-1.0, 1.0, 1.0),
        ];
        // CCW winding for outward-facing normals (right-hand rule).
        // Verified by hand: each cross((b-a), (c-a)) → expected axis sign.
        let faces = vec![
            // -Y (bottom, normal points down)
            [0, 1, 2],
            [0, 2, 3],
            // +Y (top, normal points up)
            [4, 7, 6],
            [4, 6, 5],
            // -Z (front)
            [0, 4, 5],
            [0, 5, 1],
            // +Z (back)
            [3, 2, 6],
            [3, 6, 7],
            // -X (left)
            [0, 3, 7],
            [0, 7, 4],
            // +X (right)
            [1, 5, 6],
            [1, 6, 2],
        ];
        Mesh::from_vertices_indices(&verts, &faces)
    }

    #[test]
    fn contains_point_inside_cube() {
        // Use an off-center probe so the +X ray doesn't hit triangle
        // diagonals (degenerate counting on shared edges is a known
        // limitation of the C++ Möller-Trumbore impl we're porting).
        let cube = unit_cube();
        assert!(cube.contains_point(Vec3::new(0.1, 0.2, 0.3)));
    }

    #[test]
    fn contains_point_outside_cube() {
        let cube = unit_cube();
        // Probes offset off the X axis to avoid hitting shared diagonals.
        assert!(!cube.contains_point(Vec3::new(2.0, 0.2, 0.3)));
        assert!(!cube.contains_point(Vec3::new(0.1, 2.0, 0.3)));
        assert!(!cube.contains_point(Vec3::new(-5.0, 0.2, 0.3)));
    }
}
