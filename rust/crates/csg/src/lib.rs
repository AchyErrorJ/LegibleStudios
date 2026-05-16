//! BSP-based CSG: union / intersection / difference on triangle meshes.
//!
//! Port of `ArchEngine_kernel/{include,src}/csg.{hpp,cpp}`. M2 milestone.
//!
//! Algorithm (unchanged from the C++):
//! - `Mesh` is a `Vec<Triangle>` (no shared vertices).
//! - `BSPNode::build` partitions triangles using the first triangle's
//!   plane as the splitter. Triangles spanning the plane are split via
//!   `split_triangle` (fan-triangulate the front and back polygons).
//! - `BSPNode::clip_to` removes parts of input triangles that lie inside
//!   the tree's volume.
//! - `BSPNode::invert` flips the tree (swap front/back children and
//!   negate plane normals + triangle windings).
//! - Boolean ops are clip + invert + clip variations. See `ops.rs`.
//!
//! Ownership matches the C++ shape: `Option<Box<BSPNode>>` for children,
//! moves into `build`. The recursion depth is bounded by mesh complexity
//! so a plain box tree is fine — no arena needed (per port plan §7 the
//! arena suggestion was for the BVH crate going to the GPU).

pub mod bsp;
pub mod mesh;
pub mod ops;
pub mod split;

pub use bsp::BSPNode;
pub use mesh::{Mesh, Plane, Triangle};
pub use ops::{
    mesh_difference, mesh_intersection, mesh_to_vertices_indices, mesh_union,
    vertices_indices_to_mesh, OutVertex,
};
pub use split::split_triangle;

/// Plane-distance epsilon used for classifying vertices as front/back/on.
/// Matches `csg.cpp:8`.
pub const EPSILON: f32 = 0.000_01;
