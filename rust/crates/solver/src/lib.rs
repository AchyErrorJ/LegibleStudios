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
    #[must_use]
    pub fn of(room_type: &str) -> Zone {
        match room_type {
            "entry" | "living" | "great_room" | "dining" | "kitchen" | "office" | "foyer" => {
                Zone::Public
            }
            "hallway" | "corridor" | "stairs" => Zone::Circulation,
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

/// One room in the program: identity, a relative size `weight`, and an
/// absolute `min_area` floor (sqft). Final area is a floored-proportional
/// share of the footprint (see [`allocate_areas`]) — high-weight rooms
/// (living, bedrooms) absorb the slack; low-weight rooms (closets, baths,
/// garage) pin to their minimum.
#[derive(Debug, Clone, PartialEq)]
pub struct RoomSpec {
    pub id: String,
    pub room_type: String,
    pub weight: f32,
    pub min_area: f32,
}

impl RoomSpec {
    fn new(id: &str, room_type: &str, weight: f32, min_area: f32) -> Self {
        Self {
            id: id.into(),
            room_type: room_type.into(),
            weight,
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
    /// Storeys: `0` = auto (2 when 3+ bedrooms, else 1), or an explicit `1`/`2`.
    pub storeys: u32,
}

impl Answers {
    /// Resolved number of storeys: the explicit value, or the auto rule
    /// (3+ bedrooms → 2, else 1). `sqft` is the **total** across all storeys.
    #[must_use]
    pub fn floor_count(&self) -> u32 {
        match self.storeys {
            1 | 2 => self.storeys,
            _ if self.bedrooms >= 3 => 2,
            _ => 1,
        }
    }
}

impl Default for Answers {
    fn default() -> Self {
        Self {
            bedrooms: 3,
            bathrooms: 2,
            sqft: 1800.0,
            garage: "none".into(),
            special_rooms: Vec::new(),
            storeys: 0,
        }
    }
}

/// Build the room program from answers: each room carries a relative size
/// `weight` and an absolute `min_area` floor. High-weight rooms (living,
/// bedrooms, kitchen) grow with the house; low-weight service rooms (closets,
/// baths, garage, laundry) stay near their minimum. Final areas come from
/// [`allocate_areas`] over the chosen footprint — no fraction summing, so the
/// program can't over- or under-subscribe the envelope.
#[must_use]
pub fn program_from_answers(a: &Answers) -> Vec<RoomSpec> {
    // (id, type, weight, min_area_sqft)
    let mut p = vec![
        RoomSpec::new("entry", "entry", 2.0, 40.0),
        RoomSpec::new("living", "living", 18.0, 160.0),
        RoomSpec::new("kitchen", "kitchen", 10.0, 100.0),
    ];
    if a.sqft > 800.0 {
        p.push(RoomSpec::new("dining", "dining", 8.0, 90.0));
    }
    if a.bedrooms > 1 {
        p.push(RoomSpec::new("hallway", "hallway", 5.0, 40.0));
    }
    if a.bedrooms > 0 {
        p.push(RoomSpec::new("primary_bedroom", "primary_bedroom", 12.0, 140.0));
        p.push(RoomSpec::new("primary_bath", "primary_bath", 3.0, 50.0));
        p.push(RoomSpec::new("primary_closet", "walk_in_closet", 2.0, 25.0));
    }
    for i in 2..=a.bedrooms {
        p.push(RoomSpec::new(&format!("bedroom_{i}"), "bedroom", 9.0, 100.0));
        p.push(RoomSpec::new(&format!("closet_{i}"), "closet", 1.0, 15.0));
    }
    if a.bathrooms > 1 {
        p.push(RoomSpec::new("bathroom_2", "bathroom", 2.0, 40.0));
    }
    if a.bathrooms > 2 {
        p.push(RoomSpec::new("powder_room", "powder_room", 1.0, 20.0));
    }
    p.push(RoomSpec::new("laundry", "laundry", 2.0, 35.0));
    if a.garage != "none" {
        // Low weight → the garage pins to its size minimum rather than
        // ballooning with the house.
        let (wt, min) = match a.garage.as_str() {
            "1car" => (8.0, 220.0),
            "3car" => (16.0, 660.0),
            _ => (10.0, 440.0),
        };
        p.push(RoomSpec::new("garage", "garage", wt, min));
        p.push(RoomSpec::new("mudroom", "mudroom", 2.0, 40.0));
    }
    if a.special_rooms.iter().any(|s| s == "office") {
        p.push(RoomSpec::new("office", "office", 6.0, 90.0));
    }
    if a.special_rooms.iter().any(|s| s == "pantry") {
        p.push(RoomSpec::new("pantry", "pantry", 1.0, 25.0));
    }
    p
}

/// Floored-proportional area allocation (sqft), aligned with `program`. Each
/// room gets at least its `min_area`; the remaining footprint is split among
/// the rest by `weight`. Rooms whose proportional share falls below their
/// minimum are pinned to it and removed from the pool, then the remainder is
/// redistributed — iterated to a fixed point.
#[must_use]
pub fn allocate_areas(program: &[RoomSpec], footprint: f32) -> Vec<f32> {
    let n = program.len();
    let mut areas = vec![0.0_f32; n];
    let mut pinned = vec![false; n];
    loop {
        let pinned_area: f32 = (0..n).filter(|&i| pinned[i]).map(|i| program[i].min_area).sum();
        let free_weight: f32 = (0..n).filter(|&i| !pinned[i]).map(|i| program[i].weight).sum();
        let free_area = (footprint - pinned_area).max(0.0);
        let mut changed = false;
        for i in 0..n {
            if pinned[i] {
                areas[i] = program[i].min_area;
                continue;
            }
            let share = if free_weight > 0.0 {
                program[i].weight / free_weight * free_area
            } else {
                program[i].min_area
            };
            if share < program[i].min_area {
                pinned[i] = true;
                areas[i] = program[i].min_area;
                changed = true;
            } else {
                areas[i] = share;
            }
        }
        if !changed {
            break;
        }
    }
    areas
}

/// The building footprint (sqft): the requested area, grown only if the
/// program's minimum areas don't fit inside it.
#[must_use]
pub fn footprint_for(program: &[RoomSpec], requested_sqft: f32) -> f32 {
    let min_total: f32 = program.iter().map(|r| r.min_area).sum();
    requested_sqft.max(min_total)
}

/// Shape a footprint area (sqft) into envelope `(width, depth)` feet at a
/// golden-ish 1.4 aspect ratio.
#[must_use]
pub fn shape_envelope(footprint: f32) -> (f32, f32) {
    let ratio = 1.4_f32;
    let depth = (footprint / ratio).sqrt();
    let width = footprint / depth;
    (width.round(), depth.round())
}

/// Envelope `(width, depth)` in feet for the program: the footprint is the
/// requested area (grown only to fit the program minimums — see
/// [`footprint_for`]), shaped to a golden-ish 1.4 aspect ratio. The rooms
/// then tile this footprint, so there is no separate overhead factor — the
/// area the user asked for is the area they get.
#[must_use]
pub fn auto_size(program: &[RoomSpec], requested_sqft: f32) -> (f32, f32) {
    shape_envelope(footprint_for(program, requested_sqft))
}

/// Room types that live on the private upper floor of a multi-storey house.
fn is_upper_floor(room_type: &str) -> bool {
    matches!(
        room_type,
        "primary_bedroom" | "primary_bath" | "walk_in_closet" | "bedroom" | "closet" | "bathroom"
    )
}

/// Split a program across `floors`. One storey → the whole program. Two →
/// private rooms (bedrooms + their baths/closets) go upstairs; public + service
/// stay down; each floor gets its own stair, and the upper floor its own
/// circulation hallway.
#[must_use]
pub fn split_floors(program: &[RoomSpec], floors: u32) -> Vec<Vec<RoomSpec>> {
    if floors <= 1 {
        return vec![program.to_vec()];
    }
    let mut ground: Vec<RoomSpec> = program
        .iter()
        .filter(|r| !is_upper_floor(&r.room_type))
        .cloned()
        .collect();
    let mut upper: Vec<RoomSpec> = program
        .iter()
        .filter(|r| is_upper_floor(&r.room_type))
        .cloned()
        .collect();
    ground.push(RoomSpec::new("stairs_1", "stairs", 4.0, 70.0));
    upper.insert(0, RoomSpec::new("hallway_2", "hallway", 5.0, 40.0));
    upper.push(RoomSpec::new("stairs_2", "stairs", 4.0, 70.0));
    vec![ground, upper]
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

/// Adjacency affinity between two room *types* (0 = unrelated, 1 = strongly
/// want to share a wall). Symmetric. This is the relationship graph that
/// drives the layout: high-affinity rooms get seriated next to each other and
/// therefore land adjacent. Pairs not listed fall back to a small same-zone
/// bonus so a zone still reads as a cluster.
#[allow(clippy::unnested_or_patterns, clippy::match_same_arms)] // table reads clearer as explicit pairs
fn affinity(a: &str, b: &str) -> f32 {
    let (lo, hi) = if a <= b { (a, b) } else { (b, a) };
    match (lo, hi) {
        // Public core.
        ("entry", "living") | ("entry", "foyer") | ("foyer", "living") => 0.9,
        ("dining", "living") => 0.85,
        ("dining", "kitchen") => 0.95,
        ("kitchen", "living") => 0.5,
        ("living", "powder_room") | ("entry", "powder_room") => 0.5,
        // Service links.
        ("garage", "mudroom") => 0.95,
        ("kitchen", "mudroom") => 0.7,
        ("kitchen", "pantry") => 0.9,
        ("kitchen", "laundry") | ("laundry", "mudroom") => 0.5,
        ("entry", "hallway") | ("hallway", "living") => 0.7,
        // Stairs anchor the circulation core, on every floor.
        ("entry", "stairs") | ("hallway", "stairs") => 0.85,
        ("living", "stairs") => 0.4,
        // Private suite.
        ("primary_bath", "primary_bedroom") => 0.95,
        ("primary_bedroom", "walk_in_closet") => 0.9,
        ("bedroom", "closet") => 0.9,
        ("bathroom", "bedroom") => 0.6,
        ("bathroom", "hallway") | ("hallway", "primary_bedroom") => 0.7,
        ("bedroom", "hallway") => 0.75,
        _ => {
            if Zone::of(a) == Zone::of(b) {
                0.3 // same zone, no specific pairing
            } else {
                0.05
            }
        }
    }
}

/// Order the program so high-affinity rooms are contiguous: a greedy
/// nearest-neighbour walk over the affinity graph, seeded at the entry (so the
/// order flows entry → public → service → private). Deterministic — ties keep
/// the lower program index. Returns indices into `program`.
fn seriate(program: &[RoomSpec]) -> Vec<usize> {
    let n = program.len();
    if n == 0 {
        return Vec::new();
    }
    // Seed at the stair when present (multi-storey): both floors then grow
    // their layout from the same anchor, so the stacked stairs land in the
    // same corner. Otherwise seed at the entry, then living.
    let seed = program
        .iter()
        .position(|r| r.room_type == "stairs")
        .or_else(|| program.iter().position(|r| r.room_type == "entry"))
        .or_else(|| program.iter().position(|r| r.room_type == "living"))
        .unwrap_or(0);
    let mut visited = vec![false; n];
    let mut order = Vec::with_capacity(n);
    order.push(seed);
    visited[seed] = true;
    for _ in 1..n {
        let last = *order.last().unwrap();
        let mut best = usize::MAX;
        let mut best_aff = f32::NEG_INFINITY;
        for j in 0..n {
            if visited[j] {
                continue;
            }
            let aff = affinity(&program[last].room_type, &program[j].room_type);
            if aff > best_aff + 1e-6 {
                best_aff = aff;
                best = j;
            }
        }
        order.push(best);
        visited[best] = true;
    }
    order
}

/// How many of `r`'s four edges lie on the `env` boundary (0–4). A room needs
/// only one such edge to reach an exterior wall (for a window).
fn perim_edges(r: Rect, env: Rect) -> i32 {
    const E: f32 = 0.5;
    i32::from((r.x - env.x).abs() < E)
        + i32::from((r.y - env.y).abs() < E)
        + i32::from(((r.x + r.w) - (env.x + env.w)).abs() < E)
        + i32::from(((r.y + r.h) - (env.y + env.h)).abs() < E)
}

/// Count rooms in `items` that need a window (daylight or egress).
fn window_count(items: &[(usize, f32)], program: &[RoomSpec]) -> i32 {
    items
        .iter()
        .filter(|(i, _)| obc::windows::needs_window(&program[*i].room_type))
        .count()
        .try_into()
        .unwrap_or(i32::MAX)
}

/// Recursively slice `rect` among the seriated `items` (index, area), keeping
/// adjacency clusters together AND pushing window-needing rooms to the
/// envelope perimeter. The list is split at its cumulative-area midpoint (a
/// weak link in the seriation); the two groups are then assigned to the low/
/// high sub-rect by whichever assignment gives window-needing rooms more
/// perimeter exposure. The top split runs along depth (`y_first`) and is left
/// un-flipped so the entry cluster anchors to the front; deeper splits take
/// the longer side for sane aspect ratios.
fn slice_seriated(
    env: Rect,
    rect: Rect,
    items: &[(usize, f32)],
    program: &[RoomSpec],
    y_first: bool,
) -> Vec<(usize, Rect)> {
    match items {
        [] => Vec::new(),
        [(only, _)] => vec![(*only, rect)],
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
            let wb = total - wa;
            let frac_a = if total > 0.0 { wa / total } else { 0.5 };
            let frac_b = if total > 0.0 { wb / total } else { 0.5 };
            let cut = |f: f32| if y_first { rect.split_y(f) } else { rect.split(f) };

            // Default: group `a` (front of the order) takes the low sub-rect.
            // Deeper than the top, consider swapping so the more
            // window-hungry group lands on the more-exposed rect.
            let (la, lb) = cut(frac_a); // a → la (low), b → lb (high)
            let mut a_rect = la;
            let mut b_rect = lb;
            if !y_first {
                let (sb, sa) = cut(frac_b); // b → sb (low), a → sa (high)
                let aw = window_count(a, program);
                let bw = window_count(b, program);
                let keep = aw * perim_edges(la, env) + bw * perim_edges(lb, env);
                let swap = bw * perim_edges(sb, env) + aw * perim_edges(sa, env);
                if swap > keep {
                    a_rect = sa;
                    b_rect = sb;
                }
            }
            let mut out = slice_seriated(env, a_rect, a, program, false);
            out.extend(slice_seriated(env, b_rect, b, program, false));
            out
        }
    }
}

/// Lay out the program inside `envelope` (feet) by adjacency. Rooms are
/// allocated real areas, seriated along the relationship graph ([`seriate`]),
/// then sliced so adjacency clusters stay together ([`slice_seriated`]). The
/// entry cluster anchors to the entry edge; a north entry mirrors depth.
#[must_use]
pub fn subdivide(envelope: Rect, program: &[RoomSpec], entry_edge: &str) -> Vec<PlacedRoom> {
    if program.is_empty() || envelope.area() <= 0.0 {
        return Vec::new();
    }
    let areas = allocate_areas(program, envelope.area());
    let order = seriate(program);
    let items: Vec<(usize, f32)> = order.iter().map(|&i| (i, areas[i])).collect();

    let mut placed: Vec<PlacedRoom> = slice_seriated(envelope, envelope, &items, program, true)
        .into_iter()
        .map(|(i, rect)| PlacedRoom {
            id: program[i].id.clone(),
            room_type: program[i].room_type.clone(),
            zone: program[i].zone(),
            rect,
        })
        .collect();

    // For a north entry, mirror depth so the entry cluster sits at high Y.
    if entry_edge == "north" {
        for r in &mut placed {
            r.rect.y = envelope.y + (envelope.y + envelope.h - (r.rect.y + r.rect.h));
        }
    }
    placed
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
            storeys: 1,
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
    fn auto_size_uses_requested_footprint_without_overhead() {
        let p = program_from_answers(&Answers::default());
        let min_total: f32 = p.iter().map(|r| r.min_area).sum();
        // A request above the program minimum IS the footprint — no overhead.
        let (w, d) = auto_size(&p, 1800.0);
        assert!((w * d - 1800.0).abs() <= 1800.0 * 0.03, "got {} for 1800", w * d);
        // With no request it falls back to just fitting the minimums (not ×1.35).
        let (w0, d0) = auto_size(&p, 0.0);
        assert!((w0 * d0 - min_total).abs() <= min_total * 0.03, "got {} vs min {}", w0 * d0, min_total);
        assert!(w0 * d0 < min_total * 1.1, "no 35% overhead: {} vs {}", w0 * d0, min_total);
        // Golden-ish aspect.
        assert!((w / d - 1.4).abs() < 0.1);
    }

    #[test]
    fn allocate_areas_floors_small_rooms_and_sums_to_footprint() {
        let p = program_from_answers(&Answers::default());
        let areas = allocate_areas(&p, 1800.0);
        assert_eq!(areas.len(), p.len());
        // Tiles the whole footprint.
        let total: f32 = areas.iter().sum();
        assert!((total - 1800.0).abs() < 1.0, "areas sum {total} != 1800");
        // Every room meets its minimum; high-weight rooms exceed it.
        for (spec, &a) in p.iter().zip(&areas) {
            assert!(a >= spec.min_area - 0.01, "{} below min: {a} < {}", spec.id, spec.min_area);
        }
        let living = areas[p.iter().position(|r| r.id == "living").unwrap()];
        assert!(living > 200.0, "living should absorb slack, got {living}");
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
    fn window_rooms_reach_the_perimeter_for_typical_programs() {
        // The egress-guarantee bias should put every daylight/egress room on
        // an exterior wall for ordinary 3- and 4-bed houses.
        for (bd, ba, sqft) in [(3, 2, 1800.0), (4, 3, 2400.0), (2, 2, 1400.0)] {
            let a = Answers {
                bedrooms: bd,
                bathrooms: ba,
                sqft,
                garage: "none".into(),
                special_rooms: vec![],
                storeys: 1, // this test exercises single-floor perimeter logic
            };
            let p = program_from_answers(&a);
            let (w, d) = auto_size(&p, sqft);
            let env = Rect { x: 0.0, y: 0.0, w, h: d };
            let placed = subdivide(env, &p, "south");
            let touches = |r: &Rect| {
                r.x <= 0.5 || r.y <= 0.5 || r.x + r.w >= w - 0.5 || r.y + r.h >= d - 0.5
            };
            for room in &placed {
                if obc::windows::needs_window(&room.room_type) {
                    assert!(
                        touches(&room.rect),
                        "{}-bed: {} needs a window but is interior",
                        bd,
                        room.id
                    );
                }
            }
        }
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
