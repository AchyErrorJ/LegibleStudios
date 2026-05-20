//! Room-layout solver — the live `qbd_layout_generator` path, ported lean.
//!
//! Replaces a ~4,000-LOC Python live path (and skips ~5,300 LOC of dead
//! exploratory solvers — `coordinate_solver`, `solver_suite`,
//! `advanced_solvers`, `layout_refiner`, none of which the default
//! `solver_mode="subdivision"` path imports) with a clean, zoned,
//! top-down BSP.
//!
//! Pipeline: `Answers → program_from_answers → auto_size → subdivide`.
//! Wired behind `pk_object::Solver` as [`SubdivisionRoomSolver`], the same
//! seam Increment 3's grid placeholder used — so the app upgrades from a
//! grid to real program-driven zoning with no other change.
//!
//! Not yet ported (next slice): wall/door/dimension emission to the full
//! `qbd_output.schema.json` (`layout_to_walls/doors/dimensions`).

pub mod emit;
pub use emit::building_json;

use pk_geom::Transform;
use pk_object::{Constraint, Object, Scene, Solver};

/// Functional zone a room belongs to. Drives the top-level partition
/// (public near the entry, private at the back).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Zone {
    Public,
    Circulation,
    Service,
    Private,
}

impl Zone {
    /// Near→far ordering from the entry edge.
    const ORDER: [Zone; 4] = [Zone::Public, Zone::Circulation, Zone::Service, Zone::Private];

    #[must_use]
    pub fn of(room_type: &str) -> Zone {
        match room_type {
            "entry" | "living" | "great_room" | "dining" | "kitchen" | "office" | "foyer" => {
                Zone::Public
            }
            "hallway" | "corridor" => Zone::Circulation,
            "mudroom" | "pantry" | "mechanical" | "laundry" | "garage" => Zone::Service,
            _ => Zone::Private, // bedrooms, baths, closets, powder room
        }
    }

    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Zone::Public => "public",
            Zone::Circulation => "circulation",
            Zone::Service => "service",
            Zone::Private => "private",
        }
    }
}

/// One room in the program: identity + minimum area (sqft).
#[derive(Debug, Clone, PartialEq)]
pub struct RoomSpec {
    pub id: String,
    pub room_type: String,
    pub min_area: f32,
}

impl RoomSpec {
    fn new(id: &str, room_type: &str, min_area: f32) -> Self {
        Self {
            id: id.into(),
            room_type: room_type.into(),
            min_area,
        }
    }
    #[must_use]
    pub fn zone(&self) -> Zone {
        Zone::of(&self.room_type)
    }
}

/// QBD answers — the questionnaire inputs. Mirrors the fields
/// `create_spatial_graph_from_qbd` reads.
#[derive(Debug, Clone)]
pub struct Answers {
    pub bedrooms: u32,
    pub bathrooms: u32,
    pub sqft: f32,
    pub garage: String, // "none" | "1car" | "2car" | "3car"
    pub special_rooms: Vec<String>,
}

impl Default for Answers {
    fn default() -> Self {
        Self {
            bedrooms: 3,
            bathrooms: 2,
            sqft: 1800.0,
            garage: "none".into(),
            special_rooms: Vec::new(),
        }
    }
}

/// Build the room program from answers. Direct port of
/// `create_spatial_graph_from_qbd`'s room set + min-area fractions.
#[must_use]
pub fn program_from_answers(a: &Answers) -> Vec<RoomSpec> {
    let sqft = a.sqft;
    let frac = |min: f32, f: f32| (sqft * f).max(min);
    let mut p = Vec::new();

    p.push(RoomSpec::new("entry", "entry", frac(40.0, 0.03)));
    p.push(RoomSpec::new("living", "living", frac(180.0, 0.18)));
    p.push(RoomSpec::new("kitchen", "kitchen", frac(100.0, 0.10)));
    if sqft > 800.0 {
        p.push(RoomSpec::new("dining", "dining", frac(100.0, 0.08)));
    }
    if a.bedrooms > 1 {
        p.push(RoomSpec::new("hallway", "hallway", frac(50.0, 0.04)));
    }
    if a.bedrooms > 0 {
        p.push(RoomSpec::new("primary_bedroom", "primary_bedroom", frac(150.0, 0.14)));
        p.push(RoomSpec::new("primary_bath", "primary_bath", frac(60.0, 0.05)));
        p.push(RoomSpec::new("primary_closet", "walk_in_closet", frac(30.0, 0.025)));
    }
    for i in 2..=a.bedrooms {
        p.push(RoomSpec::new(&format!("bedroom_{i}"), "bedroom", frac(120.0, 0.10)));
        p.push(RoomSpec::new(&format!("closet_{i}"), "closet", frac(15.0, 0.015)));
    }
    if a.bathrooms > 1 {
        p.push(RoomSpec::new("bathroom_2", "bathroom", frac(45.0, 0.035)));
    }
    if a.bathrooms > 2 {
        p.push(RoomSpec::new("powder_room", "powder_room", frac(25.0, 0.02)));
    }
    p.push(RoomSpec::new("laundry", "laundry", frac(35.0, 0.025)));
    if a.garage != "none" {
        let area = match a.garage.as_str() {
            "1car" => 220.0,
            "3car" => 660.0,
            _ => 440.0,
        };
        p.push(RoomSpec::new("garage", "garage", area));
        p.push(RoomSpec::new("mudroom", "mudroom", frac(40.0, 0.03)));
    }
    if a.special_rooms.iter().any(|s| s == "office") {
        p.push(RoomSpec::new("office", "office", frac(100.0, 0.06)));
    }
    if a.special_rooms.iter().any(|s| s == "pantry") {
        p.push(RoomSpec::new("pantry", "pantry", frac(25.0, 0.02)));
    }
    p
}

/// Auto-size the building envelope `(width, depth)` in feet from the
/// program: 35% overhead over the summed min areas, golden-ish 1.4 ratio.
/// Port of the auto-size block in `generate_floor_plan_from_qbd`.
#[must_use]
pub fn auto_size(program: &[RoomSpec], requested_sqft: f32) -> (f32, f32) {
    let total_min: f32 = program.iter().map(|r| r.min_area).sum();
    let required = total_min * 1.35;
    let sqft = requested_sqft.max(required);
    let ratio = 1.4_f32;
    let depth = (sqft / ratio).sqrt();
    let width = sqft / depth;
    (width.round(), depth.round())
}

/// An axis-aligned rectangle (feet), origin at min corner.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Rect {
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
}

impl Rect {
    #[must_use]
    pub fn area(&self) -> f32 {
        self.w * self.h
    }
    /// Split into two along the given fraction of the longer side.
    fn split(&self, frac: f32) -> (Rect, Rect) {
        if self.w >= self.h {
            let wa = self.w * frac;
            (
                Rect { x: self.x, y: self.y, w: wa, h: self.h },
                Rect { x: self.x + wa, y: self.y, w: self.w - wa, h: self.h },
            )
        } else {
            let ha = self.h * frac;
            (
                Rect { x: self.x, y: self.y, w: self.w, h: ha },
                Rect { x: self.x, y: self.y + ha, w: self.w, h: self.h - ha },
            )
        }
    }
    /// Split along Y (depth) at the given fraction — used for the zone bands.
    fn split_y(&self, frac: f32) -> (Rect, Rect) {
        let ha = self.h * frac;
        (
            Rect { x: self.x, y: self.y, w: self.w, h: ha },
            Rect { x: self.x, y: self.y + ha, w: self.w, h: self.h - ha },
        )
    }
}

/// A placed room: its spec plus the rect it occupies.
#[derive(Debug, Clone)]
pub struct PlacedRoom {
    pub id: String,
    pub room_type: String,
    pub zone: Zone,
    pub rect: Rect,
}

/// Balanced binary partition of `rect` among weighted items: recursively
/// bisect the item list by cumulative weight and split the rect's longer
/// side proportionally. Produces a clean BSP with area ≈ weight.
fn slice_proportional<T: Clone>(rect: Rect, items: &[(T, f32)]) -> Vec<(T, Rect)> {
    match items {
        [] => Vec::new(),
        [(only, _)] => vec![(only.clone(), rect)],
        _ => {
            let total: f32 = items.iter().map(|(_, w)| *w).sum();
            let half = total * 0.5;
            let mut acc = 0.0;
            let mut split = 1;
            for (i, (_, w)) in items.iter().enumerate() {
                acc += *w;
                if acc >= half {
                    split = (i + 1).min(items.len() - 1);
                    break;
                }
            }
            let (a, b) = items.split_at(split);
            let wa: f32 = a.iter().map(|(_, w)| *w).sum();
            let frac = if total > 0.0 { wa / total } else { 0.5 };
            let (ra, rb) = rect.split(frac);
            let mut out = slice_proportional(ra, a);
            out.extend(slice_proportional(rb, b));
            out
        }
    }
}

/// Lay out the program inside `envelope` (feet). Two-level BSP: split the
/// envelope into zone bands (public near the entry edge → private at the
/// back) along depth, then BSP each band into its rooms by min area.
#[must_use]
pub fn subdivide(envelope: Rect, program: &[RoomSpec], entry_edge: &str) -> Vec<PlacedRoom> {
    if program.is_empty() || envelope.area() <= 0.0 {
        return Vec::new();
    }
    // Group rooms by zone, preserving program order within a zone.
    let mut placed = Vec::with_capacity(program.len());
    let zone_weight = |z: Zone| -> f32 {
        program
            .iter()
            .filter(|r| r.zone() == z)
            .map(|r| r.min_area)
            .sum()
    };
    let active: Vec<(Zone, f32)> = Zone::ORDER
        .into_iter()
        .map(|z| (z, zone_weight(z)))
        .filter(|(_, w)| *w > 0.0)
        .collect();

    // Public should sit at the entry edge. We band along depth (Y); for a
    // north entry, flip so public lands at high Y.
    let bands = slice_zone_bands(envelope, &active, entry_edge);

    for (zone, band) in bands {
        let rooms: Vec<(&RoomSpec, f32)> = program
            .iter()
            .filter(|r| r.zone() == zone)
            .map(|r| (r, r.min_area))
            .collect();
        for (spec, rect) in slice_proportional(band, &rooms) {
            placed.push(PlacedRoom {
                id: spec.id.clone(),
                room_type: spec.room_type.clone(),
                zone,
                rect,
            });
        }
    }
    placed
}

/// Split the envelope into depth bands, one per active zone, area ∝ weight,
/// ordered so the public zone meets the entry edge.
fn slice_zone_bands(envelope: Rect, zones: &[(Zone, f32)], entry_edge: &str) -> Vec<(Zone, Rect)> {
    // Bands run front (entry) → back. For south entry, front = low Y.
    let total: f32 = zones.iter().map(|(_, w)| *w).sum();
    let mut bands = Vec::with_capacity(zones.len());
    let mut remaining = envelope;
    let mut acc_total = total;
    for (i, (zone, w)) in zones.iter().enumerate() {
        if i == zones.len() - 1 {
            bands.push((*zone, remaining));
        } else {
            let frac = w / acc_total;
            let (front, back) = remaining.split_y(frac);
            bands.push((*zone, front));
            remaining = back;
            acc_total -= *w;
        }
    }
    // For a north entry, the public zone should be at high Y → reverse the
    // depth ordering by mirroring each band's y about the envelope.
    if entry_edge == "north" {
        for (_, r) in &mut bands {
            r.y = envelope.y + (envelope.y + envelope.h - (r.y + r.h));
        }
    }
    bands
}

/// `pk_object::Solver` wrapping the layout. Uses the first sketched
/// `Region`'s bounding box as the envelope if present; otherwise
/// auto-sizes from the program. Adds one `"room"` Object per placed room
/// (rect + room_type + zone in params), the shape `ls-catalog::room_rect`
/// already reads.
pub struct SubdivisionRoomSolver {
    pub program: Vec<RoomSpec>,
    pub entry_edge: String,
}

impl SubdivisionRoomSolver {
    #[must_use]
    pub fn from_answers(a: &Answers) -> Self {
        Self {
            program: program_from_answers(a),
            entry_edge: "south".into(),
        }
    }
}

impl Solver for SubdivisionRoomSolver {
    fn solve(&self, scene: &mut Scene) {
        scene.objects.retain(|o| o.kind != "room");

        let envelope = match scene.regions.first() {
            Some(region) if region.polygon.len() >= 2 => {
                let mut min = glam::Vec2::splat(f32::INFINITY);
                let mut max = glam::Vec2::splat(f32::NEG_INFINITY);
                for p in &region.polygon {
                    min = min.min(*p);
                    max = max.max(*p);
                }
                Rect { x: min.x, y: min.y, w: max.x - min.x, h: max.y - min.y }
            }
            _ => {
                let (w, h) = auto_size(&self.program, 0.0);
                Rect { x: 0.0, y: 0.0, w, h }
            }
        };

        let rooms = subdivide(envelope, &self.program, &self.entry_edge);
        let mut next_id = scene.objects.iter().map(|o| o.id.0).max().unwrap_or(0) + 1;
        for r in rooms {
            let obj = Object::new(next_id, "room")
                .with_param("rect", serde_json::json!([r.rect.x, r.rect.y, r.rect.w, r.rect.h]))
                .with_param("room_id", serde_json::json!(r.id))
                .with_param("room_type", serde_json::json!(r.room_type))
                .with_param("zone", serde_json::json!(r.zone.as_str()))
                .with_constraint(Constraint::FixedAt(Transform::identity()));
            scene.add(obj);
            next_id += 1;
        }
    }
}

#[cfg(test)]
#[allow(clippy::cast_precision_loss)] // counts → f32 for test averages
mod tests {
    use super::*;

    #[test]
    fn program_for_3bed_2bath_has_expected_rooms() {
        let a = Answers {
            bedrooms: 3,
            bathrooms: 2,
            sqft: 1800.0,
            garage: "none".into(),
            special_rooms: vec![],
        };
        let p = program_from_answers(&a);
        let ids: Vec<&str> = p.iter().map(|r| r.id.as_str()).collect();
        for want in [
            "entry", "living", "kitchen", "dining", "hallway",
            "primary_bedroom", "primary_bath", "primary_closet",
            "bedroom_2", "bedroom_3", "bathroom_2", "laundry",
        ] {
            assert!(ids.contains(&want), "missing room {want}; got {ids:?}");
        }
        // 3 bedrooms → primary + bedroom_2 + bedroom_3.
        assert_eq!(p.iter().filter(|r| r.room_type.contains("bedroom")).count(), 3);
    }

    #[test]
    fn garage_adds_garage_and_mudroom() {
        let a = Answers {
            garage: "2car".into(),
            ..Answers::default()
        };
        let p = program_from_answers(&a);
        assert!(p.iter().any(|r| r.id == "garage" && (r.min_area - 440.0).abs() < 1.0));
        assert!(p.iter().any(|r| r.id == "mudroom"));
    }

    #[test]
    fn auto_size_covers_program_with_overhead() {
        let a = Answers::default();
        let p = program_from_answers(&a);
        let (w, d) = auto_size(&p, 0.0);
        let total_min: f32 = p.iter().map(|r| r.min_area).sum();
        // Envelope comfortably holds the program (with overhead), and isn't
        // wildly oversized. Exact area drifts ±a few % after rounding both
        // dims, so assert the band rather than a post-round figure.
        assert!(w * d >= total_min, "{} < program min {}", w * d, total_min);
        assert!(w * d <= total_min * 1.5, "{} > 1.5× program min", w * d);
        // Roughly the 1.4 aspect ratio.
        assert!((w / d - 1.4).abs() < 0.1);
    }

    #[test]
    fn subdivide_places_every_room_inside_the_envelope() {
        let a = Answers::default();
        let p = program_from_answers(&a);
        let (w, d) = auto_size(&p, 0.0);
        let env = Rect { x: 0.0, y: 0.0, w, h: d };
        let placed = subdivide(env, &p, "south");
        assert_eq!(placed.len(), p.len(), "every room placed");
        for r in &placed {
            assert!(r.rect.x >= -0.01 && r.rect.y >= -0.01);
            assert!(r.rect.x + r.rect.w <= w + 0.01);
            assert!(r.rect.y + r.rect.h <= d + 0.01);
            assert!(r.rect.area() > 0.0);
        }
        // Placed area tiles the whole envelope (BSP leaves no gaps).
        let total: f32 = placed.iter().map(|r| r.rect.area()).sum();
        assert!((total - w * d).abs() < 1.0, "tiled {total} vs {}", w * d);
    }

    #[test]
    fn public_zone_sits_at_the_entry_edge_south() {
        let a = Answers::default();
        let p = program_from_answers(&a);
        let env = Rect { x: 0.0, y: 0.0, w: 60.0, h: 40.0 };
        let placed = subdivide(env, &p, "south");
        // South entry → public rooms at low Y, private at high Y.
        let public_y: f32 = placed
            .iter()
            .filter(|r| r.zone == Zone::Public)
            .map(|r| r.rect.y)
            .sum::<f32>()
            / placed.iter().filter(|r| r.zone == Zone::Public).count().max(1) as f32;
        let private_y: f32 = placed
            .iter()
            .filter(|r| r.zone == Zone::Private)
            .map(|r| r.rect.y)
            .sum::<f32>()
            / placed.iter().filter(|r| r.zone == Zone::Private).count().max(1) as f32;
        assert!(public_y < private_y, "public {public_y} should be nearer entry than private {private_y}");
    }

    #[test]
    fn solver_populates_scene_rooms_from_answers() {
        let solver = SubdivisionRoomSolver::from_answers(&Answers::default());
        let mut scene = Scene::new();
        solver.solve(&mut scene);
        let rooms = scene.objects.iter().filter(|o| o.kind == "room").count();
        assert_eq!(rooms, solver.program.len());
        // Idempotent.
        solver.solve(&mut scene);
        assert_eq!(scene.objects.iter().filter(|o| o.kind == "room").count(), rooms);
    }
}
