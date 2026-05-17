//! 2D drawing pipeline — merged port of `slicer_2d` and `plan_generator`.
//!
//! See port plan §8 Q1 for the merge rationale.
//!
//! Module layout:
//! - `primitives` — Line2D, Polyline2D, Arc2D, Circle2D, Text2D,
//!   Dimension2D, Hatch2D, SliceResult.
//! - `slice_plane` — SlicePlane + 3D→2D projection math.
//! - `config` — Layer + material-hatch defaults.
//! - `slice` — element / wall / building slicing into SliceResults.
//! - `svg` — SVG emission.
//! - `dxf` — DXF emission.

pub mod annotate;
pub mod config;
pub mod detail;
pub mod dimensions;
pub mod elevation_sheet;
pub mod primitives;
pub mod room_labels;
pub mod schedule;
pub mod section_sheet;
pub mod site_plan;
pub mod slice;
pub mod slice_plane;
pub mod svg;
pub mod title_block;

pub use annotate::{
    AnnotationSet, Dimension, GridLine, Leader, PlanType, RoofAnnotation, RoofAnnotationType,
    Symbol, SymbolType, TextLabel,
};
pub use config::{Config, HatchSpec, LayerConfig};
pub use detail::{
    detail_to_slice_result, generate_wall_detail, wall_detail_to_svg, LayerDetail,
    WallSectionDetail,
};
pub use primitives::{
    Arc2D, Circle2D, Dimension2D, Hatch2D, Line2D, Point2D, Polyline2D, SliceResult, Text2D,
};
pub use dimensions::{
    chain_dims, overall_envelope_dims, render_horizontal as render_horizontal_dim,
    render_vertical as render_vertical_dim, room_interior_dims, LinearDim,
};
pub use elevation_sheet::{
    generate_elevation_sheet_svg, sheet_name as elevation_sheet_name,
    Direction as ElevationDirection, ElevationInput, ElevationOpeningInput, ElevationWallInput,
};
pub use section_sheet::{
    default_cut, generate_section_sheet_svg, CutDirection, SectionCut, SectionInput,
    SectionWallInput, ViewDirection,
};
pub use room_labels::{render_room_label, render_room_labels, RoomLabelInput};
pub use schedule::{
    door_type_for_width, format_dim_mm, schedule_to_svg, window_type_for_width, ScheduleEntry,
};
pub use site_plan::{generate_site_plan_svg, SitePlan};
pub use title_block::{
    drawing_info_for, generate_title_block, DrawingInfo, DrawingType, ProjectInfo,
};
pub use slice::{
    create_material_hatch, generate_floor_plan, generate_section, slice_box, slice_building,
    slice_element, slice_wall,
};
pub use slice_plane::{intersect_line_with_plane, project_to_2d, SlicePlane, SlicePlaneType};
pub use svg::{
    color_to_svg, cpp_double, export_to_svg, svg_arc, svg_circle, svg_hatch, svg_line,
    svg_polyline, svg_text,
};
