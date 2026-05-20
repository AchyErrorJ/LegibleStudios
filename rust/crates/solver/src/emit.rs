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

use crate::{auto_size, program_from_answers, subdivide, Answers, PlacedRoom, Rect, Zone};
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

/// Full pipeline: answers → program → auto-size → subdivide → bundle JSON.
#[must_use]
pub fn building_json(answers: &Answers) -> Value {
    let program = program_from_answers(answers);
    let (w, d) = auto_size(&program, answers.sqft);
    let envelope = Rect { x: 0.0, y: 0.0, w, h: d };
    let rooms = subdivide(envelope, &program, "south");
    let walls = generate_walls(&rooms, envelope);
    to_json(answers, envelope, &rooms, &walls)
}

/// Perimeter (exterior) + interior partition walls. Entry door on the south
/// edge centred on the `entry` room; a centred door on each interior wall.
fn generate_walls(rooms: &[PlacedRoom], env: Rect) -> Vec<Wall> {
    let (x0, y0, x1, y1) = (env.x, env.y, env.x + env.w, env.y + env.h);
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
    // Entry door centred on the entry room (fallback: envelope centre).
    let entry_cx = rooms
        .iter()
        .find(|r| r.id == "entry")
        .map_or((x0 + x1) * 0.5, |r| r.rect.x + r.rect.w * 0.5);
    let half = DOOR_WIDTH_FT * 0.5;
    south.openings.push(Opening {
        start: (entry_cx - half, y0),
        end: (entry_cx + half, y0),
    });
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

#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss, clippy::too_many_lines)]
fn to_json(answers: &Answers, env: Rect, rooms: &[PlacedRoom], walls: &[Wall]) -> Value {
    let s = FEET_TO_MM;
    let p3 = |x: f32, y: f32| json!([x * s, 0.0, y * s]); // plan (x,y) → 3D (x,0,z)

    // walls_batch
    let walls_batch: Vec<Value> = walls
        .iter()
        .enumerate()
        .map(|(i, w)| {
            json!({
                "start": p3(w.start.0, w.start.1),
                "end": p3(w.end.0, w.end.1),
                "height": WALL_HEIGHT_FT * s,
                "wall_type": if w.category == "exterior" { "ext_2x6_r21" } else { "int_2x4" },
                "category": w.category,
                "level_name": "Level 1",
                "rooms": [w.room1, w.room2],
                "wall_index": i,
            })
        })
        .collect();

    // doors (from wall openings)
    let mut doors = Vec::new();
    for (wi, w) in walls.iter().enumerate() {
        for o in &w.openings {
            let cx = (o.start.0 + o.end.0) * 0.5 * s;
            let cy = (o.start.1 + o.end.1) * 0.5 * s;
            let width = ((o.end.0 - o.start.0).powi(2) + (o.end.1 - o.start.1).powi(2)).sqrt() * s;
            doors.push(json!({
                "x": cx, "y": cy, "width": width, "type": "door",
                "height": DOOR_HEIGHT_FT * s, "wall_index": wi, "offset": 0.0,
            }));
        }
    }

    // rooms map
    let mut rooms_map = serde_json::Map::new();
    for r in rooms {
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
                "level": "Level 1",
                "bounds": { "x": r.rect.x * s, "y": r.rect.y * s, "width": r.rect.w * s, "height": r.rect.h * s },
                "area": r.rect.area() * s * s,
                "center": { "x": (r.rect.x + r.rect.w * 0.5) * s, "y": (r.rect.y + r.rect.h * 0.5) * s },
                "room_type": r.room_type,
                "zone": zone,
            }),
        );
    }

    let levels = json!([
        { "id": "level_1", "name": "Level 1", "elevation": 0.0, "floor_to_floor_height": 10.0 * s },
        { "id": "roof_level", "name": "Roof Level", "elevation": 10.0 * s, "floor_to_floor_height": 0.0 },
    ]);

    // dimensions: overall width + depth
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

    let ext = walls_batch.iter().filter(|w| w["category"] == "exterior").count();
    let int = walls_batch.len() - ext;
    let total_min: f32 = program_min_total(answers);

    json!({
        "success": true,
        "building_id": building_id(answers),
        "width": env.w * s,
        "depth": env.h * s,
        "sqft": answers.sqft.max(total_min * 1.35),
        "output_format": "archengine",
        "unit": "mm",
        "creative_mode": false,
        "walls_batch": walls_batch,
        "doors": doors,
        "windows": [],
        "levels": levels,
        "dimensions": dimensions,
        "rooms": Value::Object(rooms_map),
        "is_complete": true,
        "unplaced_rooms": [],
        "score": 1.0,
        "summary": {
            "total_walls": walls.len(),
            "exterior_walls": ext,
            "interior_walls": int,
            "wet_walls": 0,
            "doors": doors_count(walls),
            "windows": 0,
            "rooms_placed": rooms.len(),
            "rooms_requested": rooms.len(),
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

fn program_min_total(answers: &Answers) -> f32 {
    program_from_answers(answers).iter().map(|r| r.min_area).sum()
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
        let v = building_json(&Answers::default());
        assert_eq!(v["success"], json!(true));
        assert_eq!(v["unit"], json!("mm"));
        assert_eq!(v["output_format"], json!("archengine"));
        assert!(v["building_id"].as_str().unwrap().len() == 8);
        // 4 exterior walls + interior partitions.
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
