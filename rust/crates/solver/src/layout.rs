//! Part 3 / mixed layout strategies.
//!
//! These are intentionally simpler than the Part 9 BSP suite engine: they
//! reserve a vertical circulation core, then lay out the remaining rooms with
//! a strategy matched to the floor type (corridor-spine office, open retail,
//! or residential BSP for mixed upper floors).

use crate::{
    adjacency::AdjacencyGraph,
    floors::FloorPlanInput,
    subdivide, PlacedRoom, Rect, RoomSpec, Zone,
};

/// Lay out one floor according to its strategy.
#[must_use]
pub fn layout_floor(input: &FloorPlanInput, graph: &AdjacencyGraph) -> Vec<PlacedRoom> {
    match input.strategy {
        crate::floors::FloorStrategy::ResidentialBsp => layout_residential_bsp(input, graph),
        crate::floors::FloorStrategy::CorridorSpine => layout_corridor_spine(input, graph),
        crate::floors::FloorStrategy::OpenRetail => layout_open_retail(input),
    }
}

fn mk_room(spec: &RoomSpec, rect: Rect) -> PlacedRoom {
    PlacedRoom {
        id: spec.id.clone(),
        room_type: spec.room_type.clone(),
        zone: Zone::of(&spec.room_type),
        rect,
    }
}

/// Split program into core rooms (stairs/elevator/shaft) and other rooms.
fn split_core(program: &[RoomSpec]) -> (Vec<RoomSpec>, Vec<RoomSpec>) {
    program.iter().cloned().partition(|r| {
        matches!(
            r.room_type.as_str(),
            "stairs" | "elevator" | "shaft"
        )
    })
}

/// Place core rooms inside the reserved core rectangle, stacked side by side.
fn place_core_rooms(placed: &mut Vec<PlacedRoom>, core_specs: &[RoomSpec], core: Rect) {
    if core_specs.is_empty() || core.w <= 0.0 || core.h <= 0.0 {
        return;
    }
    let total_area: f32 = core_specs.iter().map(|r| r.min_area).sum::<f32>().max(1.0);
    let mut x = core.x;
    for spec in core_specs {
        let bw = core.w * spec.min_area / total_area;
        placed.push(mk_room(
            spec,
            Rect {
                x,
                y: core.y,
                w: bw,
                h: core.h,
            },
        ));
        x += bw;
    }
}

/// Part 9 residential BSP on the envelope minus the circulation core.
fn layout_residential_bsp(input: &FloorPlanInput, graph: &AdjacencyGraph) -> Vec<PlacedRoom> {
    let (core_specs, other_specs) = split_core(&input.program);
    let env = input.envelope;
    let core = input.core;
    let usable = Rect {
        x: env.x + core.w,
        y: env.y,
        w: env.w - core.w,
        h: env.h,
    };
    let mut placed = if other_specs.is_empty() {
        Vec::new()
    } else {
        subdivide(usable, &other_specs, "south", "switchback", graph)
    };
    place_core_rooms(&mut placed, &core_specs, core);
    placed
}

/// Part 3 office: circulation core at front-left, a full-width corridor spine
/// just above it, and vertical bays for the remaining rooms above the corridor.
fn layout_corridor_spine(input: &FloorPlanInput, _graph: &AdjacencyGraph) -> Vec<PlacedRoom> {
    let (core_specs, other_specs) = split_core(&input.program);
    let env = input.envelope;
    let core = input.core;

    let mut placed = Vec::new();
    place_core_rooms(&mut placed, &core_specs, core);

    // Corridor height: ~8 ft clear, capped at 15% of floor depth.
    let corridor_h = (env.h * 0.12).clamp(6.0, 12.0);
    let corridor_y = env.y + core.h;
    let remaining_h = env.h - core.h - corridor_h;

    let corridor_pos = other_specs
        .iter()
        .position(|r| r.room_type == "corridor" || r.room_type == "hallway");
    let corridor_spec = corridor_pos.map(|i| other_specs[i].clone());
    let other_without_corridor: Vec<RoomSpec> = other_specs
        .iter()
        .enumerate()
        .filter(|(i, _)| Some(*i) != corridor_pos)
        .map(|(_, r)| r.clone())
        .collect();

    if let Some(spec) = corridor_spec {
        placed.push(mk_room(
            &spec,
            Rect {
                x: env.x,
                y: corridor_y,
                w: env.w,
                h: corridor_h,
            },
        ));
    }

    if remaining_h > 0.0 && !other_without_corridor.is_empty() {
        let upper = Rect {
            x: env.x,
            y: corridor_y + corridor_h,
            w: env.w,
            h: remaining_h,
        };
        tile_bays(&mut placed,
            &other_without_corridor,
            upper,
            true, // bays run full depth of the upper band
        );
    }

    placed
}

/// Part 3 retail: circulation core at front-left, one large open retail space,
/// and service rooms tucked into the remaining rear band.
fn layout_open_retail(input: &FloorPlanInput) -> Vec<PlacedRoom> {
    let (core_specs, other_specs) = split_core(&input.program);
    let env = input.envelope;
    let core = input.core;

    let mut placed = Vec::new();
    place_core_rooms(&mut placed, &core_specs, core);

    let retail_pos = other_specs
        .iter()
        .position(|r| r.room_type == "retail" || r.room_type == "restaurant");
    let retail_spec = retail_pos.map(|i| other_specs[i].clone());
    let service_specs: Vec<RoomSpec> = other_specs
        .iter()
        .enumerate()
        .filter(|(i, _)| Some(*i) != retail_pos)
        .map(|(_, r)| r.clone())
        .collect();

    // Retail occupies the full width and most of the depth, leaving a rear
    // service band roughly 15% of the depth.
    let service_band_h = if service_specs.is_empty() {
        0.0
    } else {
        (env.h * 0.15).clamp(8.0, 18.0)
    };
    let retail_h = env.h - service_band_h;

    if let Some(spec) = retail_spec {
        placed.push(mk_room(
            &spec,
            Rect {
                x: env.x,
                y: env.y,
                w: env.w,
                h: retail_h,
            },
        ));
    }

    if service_band_h > 0.0 {
        let service_band = Rect {
            x: env.x,
            y: env.y + retail_h,
            w: env.w,
            h: service_band_h,
        };
        tile_bays(&mut placed, &service_specs, service_band, false);
    }

    placed
}

/// Tile rooms as vertical bays across a region. If `full_depth` is true each
/// bay is a single room filling the region depth; otherwise rooms are stacked
/// within each bay.
fn tile_bays(placed: &mut Vec<PlacedRoom>, specs: &[RoomSpec], region: Rect, full_depth: bool) {
    if specs.is_empty() || region.w <= 0.0 || region.h <= 0.0 {
        return;
    }
    let total_area: f32 = specs.iter().map(|r| r.min_area).sum::<f32>().max(1.0);
    let region_area = region.w * region.h;
    let mut x = region.x;
    for spec in specs {
        let area = spec.min_area.max(1.0);
        let bw = region.w * area / total_area;
        if full_depth {
            placed.push(mk_room(
                spec,
                Rect {
                    x,
                    y: region.y,
                    w: bw,
                    h: region.h,
                },
            ));
        } else {
            let bay_area = region_area * area / total_area;
            let bh = (bay_area / bw).clamp(1.0, region.h);
            placed.push(mk_room(
                spec,
                Rect {
                    x,
                    y: region.y,
                    w: bw,
                    h: bh,
                },
            ));
        }
        x += bw;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::catalog::RoomCatalog;
    use crate::floors::{plan_floors, FloorStrategy};
    use crate::manifest::ProgramManifest;
    use crate::mode::BuildingMode;

    #[test]
    fn corridor_spine_places_corridor_and_bays() {
        let manifest = ProgramManifest::from_json(
            r#"{
                "mode": "part3",
                "sqft": 4000,
                "floors": [
                    {
                        "level": 1,
                        "rooms": [
                            {"id": "lobby", "room_type": "lobby", "min_area": 200},
                            {"id": "corridor", "room_type": "corridor", "min_area": 150},
                            {"id": "stairs_1", "room_type": "stairs", "min_area": 120},
                            {"id": "office_open", "room_type": "office_open", "min_area": 1000},
                            {"id": "washroom_1", "room_type": "washroom", "min_area": 80}
                        ]
                    }
                ]
            }"#,
        )
        .unwrap();
        let plans = plan_floors(&manifest);
        let graph = AdjacencyGraph::new_for_mode(BuildingMode::Part3).with_manifest(&manifest);
        let placed = layout_floor(&plans[0], &graph);
        assert!(placed.iter().any(|r| r.room_type == "corridor"));
        assert!(placed.iter().any(|r| r.room_type == "office_open"));
        assert!(placed.iter().any(|r| r.room_type == "stairs"));
    }

    #[test]
    fn open_retail_places_large_retail() {
        let manifest = ProgramManifest::from_json(
            r#"{
                "mode": "part3",
                "sqft": 3000,
                "floors": [
                    {
                        "level": 1,
                        "rooms": [
                            {"id": "retail_1", "room_type": "retail", "min_area": 1800},
                            {"id": "lobby", "room_type": "lobby", "min_area": 150},
                            {"id": "stairs_1", "room_type": "stairs", "min_area": 120},
                            {"id": "washroom_1", "room_type": "washroom", "min_area": 80}
                        ]
                    }
                ]
            }"#,
        )
        .unwrap();
        let plans = plan_floors(&manifest);
        let graph = AdjacencyGraph::new_for_mode(BuildingMode::Part3).with_manifest(&manifest);
        let placed = layout_floor(&plans[0], &graph);
        let retail = placed.iter().find(|r| r.room_type == "retail").unwrap();
        assert!(retail.rect.area() > 1200.0, "retail should be the dominant room");
    }
}
