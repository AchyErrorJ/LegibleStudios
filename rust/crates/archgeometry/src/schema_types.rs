//! Schema element types — port of `Shared/ArchGeometry/include/archgeometry/schema_types.hpp`.
//!
//! These types mirror the JSON wire format produced by the Python QBD
//! generator. Field names use `snake_case` to match the JSON keys directly,
//! so most types need no `#[serde(rename)]`.
//!
//! Per port plan §8: the C++ has TWO JSON paths (`QBDInterface::loadFromJSON`
//! and `QBDInterface::parseWithArchGeometry`). The Rust port collapses to
//! this one — these types ARE the wire format.

use crate::wire::{map_or_empty_array, vec2_xy_object, vec3_array, vec3_array_vec};
use glam::{Vec2, Vec3};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Wall types (schema-side; distinct from `domain::WallType`).
// ---------------------------------------------------------------------------

/// Wall layer (schema-side). The schema stores `function` as a free-form
/// string and `color` as RGBA — both differ from `domain::WallLayer`
/// (which uses the `LayerFunction` enum and RGB only).
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct WallLayer {
    pub name: String,
    pub material: String,
    #[serde(default)]
    pub thickness: f32,
    /// Layer function as a free-form string: `"structure"`, `"insulation"`,
    /// `"finish"`, … See `domain::LayerFunction` for the canonical set.
    #[serde(default)]
    pub function: String,
    /// RGBA. Default `[0.9, 0.9, 0.9, 1.0]`.
    #[serde(default = "default_layer_color")]
    pub color: [f32; 4],
    #[serde(default)]
    pub r_value: f32,
}

fn default_layer_color() -> [f32; 4] {
    [0.9, 0.9, 0.9, 1.0]
}

/// Wall type — an assembly recipe (schema-side).
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct WallType {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub layers: Vec<WallLayer>,
}

impl WallType {
    /// Sum of layer thicknesses.
    #[must_use]
    pub fn total_thickness(&self) -> f32 {
        self.layers.iter().map(|l| l.thickness).sum()
    }

    /// Sum of layer R-values.
    #[must_use]
    pub fn total_r_value(&self) -> f32 {
        self.layers.iter().map(|l| l.r_value).sum()
    }
}

// ---------------------------------------------------------------------------
// Schema elements.
// ---------------------------------------------------------------------------

/// Wall element from the schema. Centerline-based.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaWall {
    #[serde(with = "vec3_array")]
    pub start: Vec3,
    #[serde(with = "vec3_array")]
    pub end: Vec3,
    #[serde(default = "default_wall_height")]
    pub height: f32,
    #[serde(default)]
    pub wall_type: String,
    #[serde(default)]
    pub category: String,
    #[serde(default)]
    pub level_name: String,
    /// Adjacent room IDs (two sides). Defaults to `["", ""]`.
    #[serde(default)]
    pub rooms: [String; 2],

    #[serde(default)]
    pub is_pinned: bool,
    #[serde(default)]
    pub locked_properties: Vec<String>,
}

fn default_wall_height() -> f32 {
    2700.0
}

impl SchemaWall {
    /// Wall length in the XZ plane (ignores Y).
    #[must_use]
    pub fn length(&self) -> f32 {
        let dx = self.end.x - self.start.x;
        let dz = self.end.z - self.start.z;
        (dx * dx + dz * dz).sqrt()
    }

    /// Unit direction in the XZ plane.
    #[must_use]
    pub fn direction(&self) -> Vec2 {
        let dx = self.end.x - self.start.x;
        let dz = self.end.z - self.start.z;
        let dir = Vec2::new(dx, dz);
        let len = dir.length();
        if len > 0.0001 { dir / len } else { Vec2::ZERO }
    }
}

/// Floor element from the schema.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaFloor {
    #[serde(with = "vec3_array")]
    pub start: Vec3,
    #[serde(with = "vec3_array")]
    pub end: Vec3,
    #[serde(default = "default_floor_thickness")]
    pub thickness: f32,
    #[serde(default)]
    pub level_name: String,
    #[serde(default)]
    pub room: Option<String>,
    #[serde(default = "default_floor_material")]
    pub material: String,
}

fn default_floor_thickness() -> f32 {
    150.0
}

fn default_floor_material() -> String {
    "concrete".to_string()
}

impl SchemaFloor {
    #[must_use]
    pub fn width(&self) -> f32 {
        (self.end.x - self.start.x).abs()
    }

    #[must_use]
    pub fn depth(&self) -> f32 {
        (self.end.z - self.start.z).abs()
    }

    #[must_use]
    pub fn elevation(&self) -> f32 {
        self.start.y
    }

    #[must_use]
    pub fn area(&self) -> f32 {
        self.width() * self.depth()
    }
}

/// Door element from the schema.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaDoor {
    #[serde(default)]
    pub wall_index: i32,
    #[serde(default)]
    pub offset: f32,
    #[serde(default = "default_door_width")]
    pub width: f32,
    #[serde(default = "default_door_height")]
    pub height: f32,
    #[serde(default = "default_door_type", rename = "type")]
    pub door_type: String,
    #[serde(default = "default_door_swing")]
    pub swing: String,
    #[serde(default)]
    pub room1: String,
    #[serde(default)]
    pub room2: String,

    #[serde(default)]
    pub is_pinned: bool,
    #[serde(default)]
    pub locked_properties: Vec<String>,
}

fn default_door_width() -> f32 {
    914.0
}
fn default_door_height() -> f32 {
    2134.0
}
fn default_door_type() -> String {
    "swing".to_string()
}
fn default_door_swing() -> String {
    "left_in".to_string()
}

/// Window element from the schema.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaWindow {
    #[serde(default)]
    pub wall_index: i32,
    #[serde(default)]
    pub offset: f32,
    #[serde(default = "default_window_width")]
    pub width: f32,
    #[serde(default = "default_window_height")]
    pub height: f32,
    #[serde(default = "default_window_sill")]
    pub sill_height: f32,
    #[serde(default = "default_window_type", rename = "type")]
    pub window_type: String,
    #[serde(default)]
    pub room: String,

    #[serde(default)]
    pub is_pinned: bool,
    #[serde(default)]
    pub locked_properties: Vec<String>,
}

fn default_window_width() -> f32 {
    1200.0
}
fn default_window_height() -> f32 {
    1200.0
}
fn default_window_sill() -> f32 {
    900.0
}
fn default_window_type() -> String {
    "double_hung".to_string()
}

/// Roof ridge line.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct RoofRidge {
    #[serde(default)]
    pub id: String,
    #[serde(with = "vec3_array")]
    pub start_point: Vec3,
    #[serde(with = "vec3_array")]
    pub end_point: Vec3,
    #[serde(default)]
    pub height: f32,
}

/// Roof surface (one slope).
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct RoofSurface {
    #[serde(default)]
    pub id: String,
    /// 3D polygon vertices.
    #[serde(default, with = "vec3_array_vec")]
    pub vertices: Vec<Vec3>,
    /// Pitch in degrees or rise:12 (consumer decides).
    #[serde(default)]
    pub pitch: f32,
    #[serde(default)]
    pub orientation: String,
}

/// Roof element from the schema.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SchemaRoof {
    #[serde(default)]
    pub id: String,
    #[serde(default = "default_roof_type", rename = "type")]
    pub roof_type: String,
    #[serde(default = "default_roof_pitch")]
    pub pitch: f32,
    #[serde(default = "default_roof_overhang")]
    pub overhang: f32,
    #[serde(default = "default_roof_material")]
    pub material: String,
    #[serde(default)]
    pub level_name: String,
    #[serde(default)]
    pub ridges: Vec<RoofRidge>,
    #[serde(default)]
    pub surfaces: Vec<RoofSurface>,
    #[serde(default)]
    pub dormers: Vec<String>,
    #[serde(default)]
    pub skylights: Vec<String>,
}

fn default_roof_type() -> String {
    "gable".to_string()
}
fn default_roof_pitch() -> f32 {
    6.0
}
fn default_roof_overhang() -> f32 {
    600.0
}
fn default_roof_material() -> String {
    "asphalt_shingle".to_string()
}

impl Default for SchemaRoof {
    fn default() -> Self {
        Self {
            id: String::new(),
            roof_type: default_roof_type(),
            pitch: default_roof_pitch(),
            overhang: default_roof_overhang(),
            material: default_roof_material(),
            level_name: String::new(),
            ridges: Vec::new(),
            surfaces: Vec::new(),
            dormers: Vec::new(),
            skylights: Vec::new(),
        }
    }
}

/// Room bounds in plan view. NOTE: `y` here is Z in 3D space (plan
/// convention from the C++).
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct RoomBounds {
    #[serde(default)]
    pub x: f32,
    #[serde(default)]
    pub y: f32,
    #[serde(default)]
    pub width: f32,
    #[serde(default)]
    pub height: f32,
}

/// Room element from the schema.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaRoom {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub room_type: String,
    #[serde(default)]
    pub bounds: RoomBounds,
    #[serde(default)]
    pub area: f32,
    /// Wire format is `{"x": …, "y": …}` object (per the locked
    /// `qbd_output.schema.json`), unlike the wall/floor coordinate vectors
    /// which are JSON arrays.
    #[serde(default, with = "vec2_xy_object")]
    pub center: Vec2,
    #[serde(default)]
    pub zone: String,
    #[serde(default = "default_level_name")]
    pub level: String,

    #[serde(default)]
    pub is_pinned: bool,
    #[serde(default)]
    pub locked_properties: Vec<String>,
}

fn default_level_name() -> String {
    "Level 1".to_string()
}

/// Level definition (a floor of the building).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SchemaLevel {
    pub name: String,
    #[serde(default)]
    pub elevation: f32,
    #[serde(default = "default_wall_height")]
    pub height: f32,
}

impl Default for SchemaLevel {
    fn default() -> Self {
        Self {
            name: String::new(),
            elevation: 0.0,
            height: default_wall_height(),
        }
    }
}

/// QBD design parameters from the conversation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct QBDAnswers {
    #[serde(default)]
    pub description: String,
    #[serde(default = "default_building_type")]
    pub building_type: String,
    #[serde(default = "default_style")]
    pub style: String,
    #[serde(default = "default_stories")]
    pub stories: i32,
    #[serde(default)]
    pub garage: String,
    #[serde(default = "default_roof_type")]
    pub roof_type: String,
    #[serde(default = "default_roof_pitch")]
    pub roof_pitch: f32,
    #[serde(default = "default_roof_material")]
    pub roof_material: String,
    #[serde(default)]
    pub sqft: i32,
    #[serde(default)]
    pub bedrooms: i32,
    #[serde(default)]
    pub bathrooms: i32,
}

fn default_building_type() -> String {
    "residential".to_string()
}
fn default_style() -> String {
    "traditional".to_string()
}
fn default_stories() -> i32 {
    1
}

impl Default for QBDAnswers {
    fn default() -> Self {
        Self {
            description: String::new(),
            building_type: default_building_type(),
            style: default_style(),
            stories: default_stories(),
            garage: String::new(),
            roof_type: default_roof_type(),
            roof_pitch: default_roof_pitch(),
            roof_material: default_roof_material(),
            sqft: 0,
            bedrooms: 0,
            bathrooms: 0,
        }
    }
}

// ---------------------------------------------------------------------------
// Schema document — top-level.
// ---------------------------------------------------------------------------

/// Summary statistics from the QBD generator.
#[derive(Debug, Clone, Copy, PartialEq, Default, Serialize, Deserialize)]
pub struct SchemaSummary {
    #[serde(default)]
    pub total_walls: i32,
    #[serde(default)]
    pub exterior_walls: i32,
    #[serde(default)]
    pub interior_walls: i32,
    #[serde(default)]
    pub doors_count: i32,
    #[serde(default)]
    pub windows_count: i32,
    #[serde(default)]
    pub rooms_placed: i32,
}

/// Top-level schema document parsed from a QBD JSON output.
///
/// Note: the JSON uses `walls_batch`/`floors_batch` (legacy naming), but
/// we expose the fields as `walls`/`floors` via `#[serde(rename)]` since
/// the rest of the code shouldn't care about the wire-level name.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct SchemaDocument {
    #[serde(default = "default_version")]
    pub version: String,
    #[serde(default)]
    pub building_id: String,

    /// Overall building width (X axis).
    #[serde(default)]
    pub width: f32,
    /// Overall building depth (Z axis).
    #[serde(default)]
    pub depth: f32,
    #[serde(default)]
    pub sqm: f32,
    #[serde(default)]
    pub sqft: f32,
    #[serde(default = "default_unit")]
    pub unit: String,

    /// JSON key: `walls_batch`.
    #[serde(default, rename = "walls_batch")]
    pub walls: Vec<SchemaWall>,
    /// JSON key: `floors_batch`.
    #[serde(default, rename = "floors_batch")]
    pub floors: Vec<SchemaFloor>,
    #[serde(default)]
    pub doors: Vec<SchemaDoor>,
    #[serde(default)]
    pub windows: Vec<SchemaWindow>,
    #[serde(default)]
    pub roofs: Vec<SchemaRoof>,
    /// Python writes `[]` when empty and `{"room_id": {...}}` when populated.
    #[serde(default, deserialize_with = "map_or_empty_array::deserialize")]
    pub rooms: HashMap<String, SchemaRoom>,
    #[serde(default)]
    pub levels: Vec<SchemaLevel>,
    /// Wire format is an array of `WallType`s (each has its own `id`);
    /// the C++ schema_parser turns this into a map keyed by `id` after
    /// parsing. We keep it as a Vec here and let the query API build the
    /// lookup map if needed.
    #[serde(default)]
    pub wall_types: Vec<WallType>,

    #[serde(default)]
    pub qbd_answers: QBDAnswers,
    #[serde(default)]
    pub summary: SchemaSummary,
    /// Life-safety alarms (smoke / CO) — rules-engine annotation pass.
    #[serde(default)]
    pub detectors: Vec<SchemaDetector>,
    /// Electrical devices (receptacles / lights) — rules-engine annotation.
    #[serde(default)]
    pub electrical: Vec<SchemaElectrical>,
    /// Header (lintel) callouts over openings — rules-engine annotation.
    #[serde(default)]
    pub headers: Vec<SchemaHeader>,
}

/// A header/lintel callout over a door or window opening. `size` is the OBC
/// member (e.g. `"2-2x10"`); position in mm at the opening centre.
#[derive(Debug, Clone, Default, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SchemaHeader {
    #[serde(default)]
    pub size: String,
    #[serde(default)]
    pub x: f32,
    #[serde(default)]
    pub y: f32,
    #[serde(default)]
    pub level_name: String,
    #[serde(default)]
    pub opening: String,
    #[serde(default)]
    pub width: f32,
    #[serde(default)]
    pub needs_review: bool,
}

/// A placed electrical device. `kind` is `"receptacle"`, `"gfci"` or
/// `"light"`; position in mm.
#[derive(Debug, Clone, Default, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SchemaElectrical {
    #[serde(default, rename = "type")]
    pub kind: String,
    #[serde(default)]
    pub x: f32,
    #[serde(default)]
    pub y: f32,
    #[serde(default)]
    pub level_name: String,
    #[serde(default)]
    pub room: String,
}

/// A placed life-safety alarm (smoke or CO). Position is the room/ceiling
/// point in mm; `kind` is `"smoke"` or `"co"`.
#[derive(Debug, Clone, Default, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct SchemaDetector {
    #[serde(default, rename = "type")]
    pub kind: String,
    #[serde(default)]
    pub x: f32,
    #[serde(default)]
    pub y: f32,
    #[serde(default)]
    pub level_name: String,
    #[serde(default)]
    pub room: String,
}

fn default_version() -> String {
    "1.0.0".to_string()
}
fn default_unit() -> String {
    "mm".to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schema_wall_round_trips_through_json() {
        let w = SchemaWall {
            start: Vec3::new(0.0, 0.0, 0.0),
            end: Vec3::new(5000.0, 0.0, 0.0),
            height: 2700.0,
            wall_type: "exterior_2x6".into(),
            category: "exterior".into(),
            ..Default::default()
        };
        let json = serde_json::to_string(&w).unwrap();
        assert!(json.contains(r#""start":[0.0,0.0,0.0]"#));
        assert!(json.contains(r#""end":[5000.0,0.0,0.0]"#));
        let back: SchemaWall = serde_json::from_str(&json).unwrap();
        assert_eq!(back.wall_type, w.wall_type);
        assert_eq!(back.start, w.start);
    }

    #[test]
    fn schema_wall_parses_minimal_input() {
        // Only the required fields supplied — defaults fill the rest.
        let json = r#"{"start":[0,0,0],"end":[1000,0,0]}"#;
        let w: SchemaWall = serde_json::from_str(json).unwrap();
        assert_eq!(w.start, Vec3::ZERO);
        assert_eq!(w.height, 2700.0); // default
        assert_eq!(w.wall_type, ""); // default
    }

    #[test]
    fn schema_wall_length_xz_ignores_y() {
        // Wall on second floor (Y=3048) should still have correct XZ length.
        let w = SchemaWall {
            start: Vec3::new(0.0, 3048.0, 0.0),
            end: Vec3::new(3000.0, 3048.0, 4000.0),
            ..Default::default()
        };
        assert_eq!(w.length(), 5000.0);
    }

    #[test]
    fn schema_document_parses_walls_batch() {
        let json = r#"{
            "width": 9144,
            "depth": 12192,
            "walls_batch": [
                {"start":[0,0,0],"end":[9144,0,0],"height":3048,"wall_type":"brick","category":"exterior"}
            ]
        }"#;
        let doc: SchemaDocument = serde_json::from_str(json).unwrap();
        assert_eq!(doc.width, 9144.0);
        assert_eq!(doc.walls.len(), 1);
        assert_eq!(doc.walls[0].category, "exterior");
    }

    #[test]
    fn floor_area_uses_width_times_depth() {
        let f = SchemaFloor {
            start: Vec3::new(0.0, 0.0, 0.0),
            end: Vec3::new(5000.0, 0.0, 4000.0),
            ..Default::default()
        };
        assert_eq!(f.area(), 20_000_000.0);
    }
}
