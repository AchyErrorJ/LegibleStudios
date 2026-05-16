//! 2D drawing pipeline — merged port of `slicer_2d` and `plan_generator`.
//!
//! Sub-modules:
//! - `slice`    — 3D mesh → 2D plane slicing
//! - `annotate` — dimensions, grids, north arrow, symbols, roof pitch
//! - `svg`      — SVG emission
//! - `dxf`      — DXF emission (via `dxf` crate)
//!
//! See port plan §8 Q1 for the merge rationale.
