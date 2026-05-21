//! Emit a placed layout as a `qbd_output.schema.json` building bundle.
//!
//! Port of `qbd_layout_generator`'s `layout_to_walls/doors/rooms_data/
//! levels/dimensions` + `subdivision_solver::_generate_walls`. Walls are
//! the envelope perimeter (exterior, with an entry door) plus interior
//! partitions along each adjacent-room boundary (each with a centred
//! door). Output is ARCHENGINE format (mm) — feet × 304.8.
//!
//! This completes the pure-Rust `answers → schema-valid bundle` path; no
//! Python in the loop.

use crate::{
    footprint_for, program_from_answers, shape_envelope, split_floors, subdivide, Answers,
    PlacedRoom, Rect, Zone,
};
use serde_json::{json, Value};

const FEET_TO_MM: f32 = 304.8;
const WALL_HEIGHT_FT: f32 = 9.0; // 9' plate
const DOOR_WIDTH_FT: f32 = 3.0;
const DOOR_HEIGHT_FT: f32 = 6.67; // 6'8"
const EPS: f32 = 0.01;

struct Opening {
    start: (f32, f32),
    end: (f32, f32),
}

struct Wall {
    start: (f32, f32),
    end: (f32, f32),
    category: &'static str, // "exterior" | "interior"
    room1: String,
    room2: String,
    openings: Vec<Opening>,
}

/// One laid-out storey: its rooms, walls and windows in the shared footprint.
struct Floor {
    level: usize, // 1-based
    rooms: Vec<PlacedRoom>,
    walls: Vec<Wall>,
    windows: Vec<WindowOut>,
}

/// Full pipeline: answers → program → split across storeys → per-floor
/// auto-size/subdivide/walls/windows → combined bundle JSON. `sqft` is the
/// **total** across storeys, so each floor targets `sqft / storeys`; all
/// floors share one (stacked) footprint sized to the largest floor's program.
#[must_use]
pub fn building_json(answers: &Answers) -> Value {
    let program = program_from_answers(answers);
    let floors_n = answers.floor_count();
    let programs = split_floors(&program, floors_n);
    #[allow(clippy::cast_precision_loss)]
    let per_floor_target = answers.sqft / floors_n as f32;

    // One footprint, big enough for every floor's program.
    let footprint = programs
        .iter()
        .map(|p| footprint_for(p, per_floor_target))
        .fold(per_floor_target, f32::max);
    let (w, d) = shape_envelope(footprint);
    let envelope = Rect { x: 0.0, y: 0.0, w, h: d };

    let floors: Vec<Floor> = programs
        .iter()
        .enumerate()
        .map(|(i, pgm)| {
            let rooms = subdivide(envelope, pgm, "south");
            let is_ground = i == 0;
            let walls = generate_walls(&rooms, envelope, is_ground);
            let windows = generate_windows(&rooms, envelope);
            Floor { level: i + 1, rooms, walls, windows }
        })
        .collect();

    to_json(answers, envelope, &floors)
}

/// Perimeter (exterior) + interior partition walls. On the ground floor, an
/// entry door sits on the south edge centred on the `entry` room; upper floors
/// have no exterior door (the stair is their access). Each interior wall gets
/// a centred door.
fn generate_walls(rooms: &[PlacedRoom], env: Rect, is_ground: bool) -> Vec<Wall> {
    let (x0, y0, x1, y1) = (env.x, env.y, env.x + env.w, env.y + env.h);
    let half = DOOR_WIDTH_FT * 0.5;
    let mut walls = Vec::new();

    // Exterior perimeter, CCW from south-west.
    let mut south = Wall {
        start: (x0, y0),
        end: (x1, y0),
        category: "exterior",
        room1: "exterior".into(),
        room2: "exterior".into(),
        openings: Vec::new(),
    };
    // Entry door (ground floor only) centred on the entry room.
    if let Some(entry) = rooms.iter().find(|r| is_ground && r.id == "entry") {
        let entry_cx = entry.rect.x + entry.rect.w * 0.5;
        south.openings.push(Opening {
            start: (entry_cx - half, y0),
            end: (entry_cx + half, y0),
        });
    }
    walls.push(south);
    for (s, e) in [
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ] {
        walls.push(Wall {
            start: s,
            end: e,
            category: "exterior",
            room1: "exterior".into(),
            room2: "exterior".into(),
            openings: Vec::new(),
        });
    }

    // Interior partitions: for each adjacent room pair, the shared boundary.
    for i in 0..rooms.len() {
        for j in (i + 1)..rooms.len() {
            if let Some((s, e)) = shared_edge(&rooms[i].rect, &rooms[j].rect) {
                let mut wall = Wall {
                    start: s,
                    end: e,
                    category: "interior",
                    room1: rooms[i].id.clone(),
                    room2: rooms[j].id.clone(),
                    openings: Vec::new(),
                };
                // Centred door if the shared edge is wide enough.
                let len = ((e.0 - s.0).powi(2) + (e.1 - s.1).powi(2)).sqrt();
                if len > DOOR_WIDTH_FT + 1.0 {
                    let t0 = (len * 0.5 - half) / len;
                    let t1 = (len * 0.5 + half) / len;
                    let lerp = |t: f32| (s.0 + (e.0 - s.0) * t, s.1 + (e.1 - s.1) * t);
                    wall.openings.push(Opening {
                        start: lerp(t0),
                        end: lerp(t1),
                    });
                }
                walls.push(wall);
            }
        }
    }
    walls
}

/// The shared boundary segment between two axis-aligned rects, if they abut
/// with a non-trivial overlap (vertical or horizontal).
fn shared_edge(a: &Rect, b: &Rect) -> Option<((f32, f32), (f32, f32))> {
    let (ax1, ay1, ax2, ay2) = (a.x, a.y, a.x + a.w, a.y + a.h);
    let (bx1, by1, bx2, by2) = (b.x, b.y, b.x + b.w, b.y + b.h);

    // Vertical shared edge (a.right == b.left or vice-versa).
    for &x in &[(ax2, bx1), (bx2, ax1)] {
        if (x.0 - x.1).abs() < EPS {
            let lo = ay1.max(by1);
            let hi = ay2.min(by2);
            if hi - lo > 1.0 {
                return Some(((x.0, lo), (x.0, hi)));
            }
        }
    }
    // Horizontal shared edge (a.top == b.bottom or vice-versa).
    for &y in &[(ay2, by1), (by2, ay1)] {
        if (y.0 - y.1).abs() < EPS {
            let lo = ax1.max(bx1);
            let hi = ax2.min(bx2);
            if hi - lo > 1.0 {
                return Some(((lo, y.0), (hi, y.0)));
            }
        }
    }
    None
}

/// A window placed on one of the four exterior perimeter walls.
struct WindowOut {
    wall_index: usize,
    offset: f32, // mm along the wall from its start point
    width: f32,  // mm
    height: f32, // mm
    sill: f32,   // mm above floor
    win_type: &'static str,
    room: String,
}

/// OBC-driven window pass (Part 9). For every room with a daylight or egress
/// duty ([`obc::windows`]), place one window on the longest exterior edge the
/// room touches, sized to satisfy the glazing fraction (and the egress minimum
/// for bedrooms). Rooms with no exterior wall get none — a real OBC gap for
/// interior habitable rooms, surfaced rather than papered over.
///
/// This is the placement seam the window-design work plugs into: the *rules*
/// live in `obc`, the *strategy* (which wall, how big, where along it) is here
/// and can be replaced wholesale without touching either side.
fn generate_windows(rooms: &[PlacedRoom], env: Rect) -> Vec<WindowOut> {
    use obc::windows as w;
    const WIN_H_MM: f32 = 1200.0; // ~900 sill → ~2100 head
    const SILL_MM: f32 = 900.0;
    const EDGE_EPS: f32 = 0.5; // feet — room edge ≈ envelope edge

    let s = FEET_TO_MM;
    let (x0, y0, x1, y1) = (env.x, env.y, env.x + env.w, env.y + env.h);
    let mut out = Vec::new();
    for r in rooms {
        if !w::needs_window(&r.room_type) {
            continue;
        }
        // Required glazing area (m²), floored by egress for bedrooms.
        let area_m2 = (r.rect.w * s / 1000.0) * (r.rect.h * s / 1000.0);
        let egress = w::requires_egress(&r.room_type);
        let mut need_m2 = area_m2 * w::glazing_fraction(&r.room_type);
        if egress {
            need_m2 = need_m2.max(w::EGRESS_MIN_AREA_M2);
        }
        if need_m2 <= 0.0 {
            continue;
        }

        // Exterior edges this room touches: (wall_index, span_ft, dist_from_wall_start_ft).
        let (cx, cy) = (r.rect.x + r.rect.w * 0.5, r.rect.y + r.rect.h * 0.5);
        let mut cands: Vec<(usize, f32, f32)> = Vec::new();
        if (r.rect.y - y0).abs() < EDGE_EPS {
            cands.push((0, r.rect.w, cx - x0)); // south: +x from x0
        }
        if ((r.rect.x + r.rect.w) - x1).abs() < EDGE_EPS {
            cands.push((1, r.rect.h, cy - y0)); // east: +y from y0
        }
        if ((r.rect.y + r.rect.h) - y1).abs() < EDGE_EPS {
            cands.push((2, r.rect.w, x1 - cx)); // north: -x from x1
        }
        if (r.rect.x - x0).abs() < EDGE_EPS {
            cands.push((3, r.rect.h, y1 - cy)); // west: -y from y1
        }
        let Some(&(wall_index, span_ft, dist_ft)) = cands
            .iter()
            .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
        else {
            continue; // interior room, no exterior wall
        };

        // Width from area / fixed head height, bounded by egress min and the
        // available exterior span (leave 20% for wall returns).
        let mut width = (need_m2 / (WIN_H_MM / 1000.0)) * 1000.0;
        width = width.max(w::EGRESS_MIN_DIMENSION_MM).min(span_ft * s * 0.8);
        let wall_len_mm = if wall_index % 2 == 0 { env.w * s } else { env.h * s };
        let offset = (dist_ft * s - width * 0.5).clamp(0.0, (wall_len_mm - width).max(0.0));
        let sill = if egress { SILL_MM.min(w::EGRESS_MAX_SILL_MM) } else { SILL_MM };

        out.push(WindowOut {
            wall_index,
            offset,
            width,
            height: WIN_H_MM,
            sill,
            win_type: if egress { "casement" } else { "double_hung" },
            room: r.id.clone(),
        });
    }
    out
}

#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_precision_loss,
    clippy::too_many_lines
)]
fn to_json(answers: &Answers, env: Rect, floors: &[Floor]) -> Value {
    let s = FEET_TO_MM;
    let p3 = |x: f32, y: f32| json!([x * s, 0.0, y * s]); // plan (x,y) → 3D (x,0,z)

    let mut walls_batch: Vec<Value> = Vec::new();
    let mut doors: Vec<Value> = Vec::new();
    let mut windows_json: Vec<Value> = Vec::new();
    let mut egress_warnings: Vec<Value> = Vec::new();
    let mut rooms_map = serde_json::Map::new();
    let mut wall_offset = 0usize; // walls_batch is global; per-floor indices shift by this

    for floor in floors {
        let level_name = format!("Level {}", floor.level);

        // Walls (global index = wall_offset + local).
        for (i, w) in floor.walls.iter().enumerate() {
            walls_batch.push(json!({
                "start": p3(w.start.0, w.start.1),
                "end": p3(w.end.0, w.end.1),
                "height": WALL_HEIGHT_FT * s,
                "wall_type": if w.category == "exterior" { "ext_2x6_r21" } else { "int_2x4" },
                "category": w.category,
                "level_name": level_name,
                "rooms": [w.room1.clone(), w.room2.clone()],
                "wall_index": wall_offset + i,
            }));
        }

        // Doors from wall openings (global wall_index).
        for (wi, w) in floor.walls.iter().enumerate() {
            for o in &w.openings {
                let cx = (o.start.0 + o.end.0) * 0.5 * s;
                let cy = (o.start.1 + o.end.1) * 0.5 * s;
                let width = ((o.end.0 - o.start.0).powi(2) + (o.end.1 - o.start.1).powi(2)).sqrt() * s;
                doors.push(json!({
                    "x": cx, "y": cy, "width": width, "type": "door",
                    "height": DOOR_HEIGHT_FT * s, "wall_index": wall_offset + wi, "offset": 0.0,
                }));
            }
        }

        // Windows (perimeter walls are the first of each floor's list, so the
        // local wall_index shifts by the same offset).
        for w in &floor.windows {
            windows_json.push(json!({
                "wall_index": wall_offset + w.wall_index,
                "offset": w.offset,
                "width": w.width,
                "height": w.height,
                "sill_height": w.sill,
                "type": w.win_type,
                "room": w.room,
                "level_name": level_name,
            }));
        }

        // Egress flag: bedrooms on this floor with no exterior wall (OBC 9.9.10.1).
        for r in &floor.rooms {
            if obc::windows::requires_egress(&r.room_type)
                && !floor.windows.iter().any(|w| w.room == r.id)
            {
                egress_warnings.push(json!({
                    "room": r.id,
                    "level": level_name,
                    "code": "OBC 9.9.10.1",
                    "issue": "bedroom has no exterior wall for an egress window",
                }));
            }
        }

        // Rooms map (ids are unique across floors).
        for r in &floor.rooms {
            let zone = match r.zone {
                Zone::Public => "public",
                Zone::Circulation => "circulation",
                Zone::Service => "service",
                Zone::Private => "private",
            };
            rooms_map.insert(
                r.id.clone(),
                json!({
                    "name": title_case(&r.id),
                    "level": level_name,
                    "bounds": { "x": r.rect.x * s, "y": r.rect.y * s, "width": r.rect.w * s, "height": r.rect.h * s },
                    "area": r.rect.area() * s * s,
                    "center": { "x": (r.rect.x + r.rect.w * 0.5) * s, "y": (r.rect.y + r.rect.h * 0.5) * s },
                    "room_type": r.room_type,
                    "zone": zone,
                }),
            );
        }

        wall_offset += floor.walls.len();
    }

    // Levels: one per storey + a roof on top, 10 ft floor-to-floor.
    let mut levels_v: Vec<Value> = (0..floors.len())
        .map(|i| {
            json!({
                "id": format!("level_{}", i + 1),
                "name": format!("Level {}", i + 1),
                "elevation": i as f32 * 10.0 * s,
                "floor_to_floor_height": 10.0 * s,
            })
        })
        .collect();
    levels_v.push(json!({
        "id": "roof_level", "name": "Roof Level",
        "elevation": floors.len() as f32 * 10.0 * s, "floor_to_floor_height": 0.0,
    }));
    let levels = Value::Array(levels_v);

    // dimensions: overall width + depth (shared footprint).
    let dimensions = json!([
        {
            "id": "dim_overall_w", "type": "linear",
            "start_point": p3(env.x, env.y), "end_point": p3(env.x + env.w, env.y),
            "value": env.w * s, "unit": "mm", "label": "Overall Width", "level": "Level 1",
        },
        {
            "id": "dim_overall_d", "type": "linear",
            "start_point": p3(env.x, env.y), "end_point": p3(env.x, env.y + env.h),
            "value": env.h * s, "unit": "mm", "label": "Overall Depth", "level": "Level 1",
        },
    ]);

    let total_walls: usize = floors.iter().map(|f| f.walls.len()).sum();
    let total_windows: usize = floors.iter().map(|f| f.windows.len()).sum();
    let total_rooms: usize = floors.iter().map(|f| f.rooms.len()).sum();
    let total_doors: usize = floors.iter().map(|f| doors_count(&f.walls)).sum();
    let ext = walls_batch.iter().filter(|w| w["category"] == "exterior").count();
    let int = total_walls - ext;
    let storeys = floors.len() as f32;

    json!({
        "success": true,
        "building_id": building_id(answers),
        "width": env.w * s,
        "depth": env.h * s,
        // Total built area across storeys (each floor tiles the footprint).
        "sqft": env.w * env.h * storeys,
        "storeys": floors.len(),
        "output_format": "archengine",
        "unit": "mm",
        "creative_mode": false,
        "walls_batch": walls_batch,
        "doors": doors,
        "windows": windows_json,
        "egress_warnings": egress_warnings,
        "levels": levels,
        "dimensions": dimensions,
        "rooms": Value::Object(rooms_map),
        "is_complete": true,
        "unplaced_rooms": [],
        "score": 1.0,
        "summary": {
            "total_walls": total_walls,
            "exterior_walls": ext,
            "interior_walls": int,
            "wet_walls": 0,
            "doors": total_doors,
            "windows": total_windows,
            "egress_violations": egress_warnings.len(),
            "rooms_placed": total_rooms,
            "rooms_requested": total_rooms,
            "storeys": floors.len(),
        },
        "qbd_answers": {
            "bedrooms": answers.bedrooms,
            "bathrooms": answers.bathrooms,
            // archgeometry's QBDAnswers.sqft is i32 — emit an integer (the
            // locked schema accepts string|number, but the Rust parser is
            // stricter, so round to keep the qbd_dump chain happy).
            "sqft": answers.sqft as i32,
            "garage": answers.garage,
        },
    })
}

fn doors_count(walls: &[Wall]) -> usize {
    walls.iter().map(|w| w.openings.len()).sum()
}

/// Deterministic 8-hex id from the answers (FNV-1a), so output is stable.
#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)] // byte extraction
fn building_id(a: &Answers) -> String {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in [
        a.bedrooms as u8,
        a.bathrooms as u8,
        (a.sqft as u32 & 0xff) as u8,
        ((a.sqft as u32 >> 8) & 0xff) as u8,
    ] {
        h ^= u64::from(byte);
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("{:08x}", (h & 0xffff_ffff) as u32)
}

fn title_case(id: &str) -> String {
    id.split('_')
        .map(|w| {
            let mut c = w.chars();
            c.next().map_or_else(String::new, |f| f.to_uppercase().collect::<String>() + c.as_str())
        })
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn building_json_is_schema_shaped() {
        let v = building_json(&Answers { storeys: 1, ..Answers::default() });
        assert_eq!(v["success"], json!(true));
        assert_eq!(v["unit"], json!("mm"));
        assert_eq!(v["output_format"], json!("archengine"));
        assert!(v["building_id"].as_str().unwrap().len() == 8);
        // 4 exterior walls + interior partitions (single storey).
        let walls = v["walls_batch"].as_array().unwrap();
        assert!(walls.len() >= 4);
        assert_eq!(walls.iter().filter(|w| w["category"] == "exterior").count(), 4);
        // Walls carry the required schema fields.
        let w0 = &walls[0];
        for k in ["start", "end", "height", "wall_type", "category", "level_name", "rooms", "wall_index"] {
            assert!(w0.get(k).is_some(), "wall missing {k}");
        }
        // Rooms map non-empty, each with required fields.
        let rooms = v["rooms"].as_object().unwrap();
        assert!(!rooms.is_empty());
        for (_, r) in rooms {
            for k in ["name", "bounds", "area", "center", "level"] {
                assert!(r.get(k).is_some(), "room missing {k}");
            }
        }
    }

    #[test]
    fn entry_door_present() {
        let v = building_json(&Answers::default());
        let doors = v["doors"].as_array().unwrap();
        assert!(!doors.is_empty(), "no doors emitted");
        // At least the entry door on the south exterior wall.
        assert!(doors.iter().any(|d| d["wall_index"] == json!(0)));
    }

    #[test]
    fn windows_placed_for_habitable_rooms_meet_obc() {
        let v = building_json(&Answers { storeys: 1, ..Answers::default() });
        let windows = v["windows"].as_array().unwrap();
        assert!(!windows.is_empty(), "no windows emitted");
        let walls = v["walls_batch"].as_array().unwrap().len();
        for win in windows {
            // On a real (exterior) perimeter wall, with required schema fields.
            let wi = win["wall_index"].as_u64().unwrap();
            assert!(wi < 4, "window not on a perimeter wall: {wi}");
            assert!(wi < walls as u64);
            for k in ["wall_index", "offset", "width", "height", "sill_height", "type", "room"] {
                assert!(win.get(k).is_some(), "window missing {k}");
            }
            // Egress-capable opening: never below the OBC minimum dimension.
            assert!(win["width"].as_f64().unwrap() >= 380.0);
        }
        // Every bedroom is EITHER covered by an egress (casement) window OR
        // honestly flagged as an egress violation (interior bedroom). No
        // bedroom is silently left non-compliant.
        let rooms = v["rooms"].as_object().unwrap();
        let warned: Vec<&str> = v["egress_warnings"]
            .as_array()
            .unwrap()
            .iter()
            .map(|w| w["room"].as_str().unwrap())
            .collect();
        for id in rooms.keys().filter(|k| k.contains("bedroom")) {
            let has_egress = windows
                .iter()
                .any(|w| w["room"] == json!(id) && w["type"] == json!("casement"));
            assert!(
                has_egress || warned.contains(&id.as_str()),
                "bedroom {id} neither glazed nor flagged for egress"
            );
        }
        // Summary counts match.
        assert_eq!(v["summary"]["windows"], json!(windows.len()));
        assert_eq!(v["summary"]["egress_violations"], json!(warned.len()));
    }

    #[test]
    fn multi_storey_splits_public_down_and_bedrooms_up() {
        let a = Answers {
            bedrooms: 4,
            bathrooms: 3,
            sqft: 2400.0,
            garage: "2car".into(),
            special_rooms: vec![],
            storeys: 0, // auto → 2 storeys (4 bedrooms)
        };
        let v = building_json(&a);
        assert_eq!(v["storeys"], json!(2));
        // Three levels: two storeys + roof.
        assert_eq!(v["levels"].as_array().unwrap().len(), 3);
        let rooms = v["rooms"].as_object().unwrap();
        let level_of = |id: &str| rooms[id]["level"].as_str().unwrap().to_string();
        // Public/service downstairs, bedrooms upstairs.
        assert_eq!(level_of("living"), "Level 1");
        assert_eq!(level_of("garage"), "Level 1");
        assert_eq!(level_of("primary_bedroom"), "Level 2");
        assert_eq!(level_of("bedroom_2"), "Level 2");
        // Each floor has its own stair.
        assert!(rooms.contains_key("stairs_1") && rooms.contains_key("stairs_2"));
        // Total sqft is split across floors: footprint ≈ total/2.
        let footprint = v["width"].as_f64().unwrap() * v["depth"].as_f64().unwrap()
            / (304.8 * 304.8);
        assert!((footprint - 1200.0).abs() < 250.0, "per-floor footprint {footprint}");
        // Walls/windows are level-tagged; bedrooms upstairs still get egress.
        assert!(v["walls_batch"].as_array().unwrap().iter().any(|w| w["level_name"] == "Level 2"));
        assert!(v["windows"].as_array().unwrap().iter().any(|w| w["level_name"] == "Level 2"));
    }

    #[test]
    fn single_storey_for_two_bedrooms() {
        let a = Answers {
            bedrooms: 2,
            bathrooms: 1,
            sqft: 1100.0,
            garage: "none".into(),
            special_rooms: vec![],
            storeys: 0, // auto → 1 storey (< 3 bedrooms)
        };
        let v = building_json(&a);
        assert_eq!(v["storeys"], json!(1));
        assert_eq!(v["levels"].as_array().unwrap().len(), 2); // Level 1 + roof
    }

    #[test]
    fn building_id_is_deterministic() {
        let a = Answers::default();
        assert_eq!(building_id(&a), building_id(&a));
    }

    #[test]
    fn shared_edge_detects_vertical_abutment() {
        let a = Rect { x: 0.0, y: 0.0, w: 10.0, h: 10.0 };
        let b = Rect { x: 10.0, y: 0.0, w: 10.0, h: 10.0 };
        let edge = shared_edge(&a, &b).expect("should share a vertical edge");
        assert!((edge.0 .0 - 10.0).abs() < EPS);
        assert!((edge.1 .0 - 10.0).abs() < EPS);
    }

    #[test]
    fn disjoint_rects_share_no_edge() {
        let a = Rect { x: 0.0, y: 0.0, w: 10.0, h: 10.0 };
        let b = Rect { x: 50.0, y: 50.0, w: 10.0, h: 10.0 };
        assert!(shared_edge(&a, &b).is_none());
    }
}
