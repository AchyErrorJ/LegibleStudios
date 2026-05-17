//! QBD orchestration — converts an `archgeometry::SchemaDocument` into a
//! `domain::Building`, runs floor-plan generation with door/window
//! enhancements, and produces final permit-set SVG/DXF output.
//!
//! Port of `ArchEngine_kernel/{include,src}/qbd_interface.{hpp,cpp}`.
//! Per port plan §8 — the legacy custom JSON parser is collapsed; this
//! crate consumes `SchemaDocument` from `archgeometry` directly. The
//! per-layer wall CSG mesh path is also skipped (3D-render only, not
//! needed for permit drawings).

pub mod convert;
pub mod documentation;
pub mod floor_plan;
pub mod schedule;
pub mod validation;
pub mod wall_types;

pub use convert::{layout_to_building, walls_to_parametric, wall_type_for_wall};
pub use documentation::{generate_documentation, Documentation};
pub use floor_plan::generate_floor_plan_with_openings;
pub use schedule::{door_entries, window_entries};
pub use validation::{validate_layout, validate_wall, ValidationResult};
pub use wall_types::{exterior_2x6_r21, for_category, interior_2x4, wet_2x6};
