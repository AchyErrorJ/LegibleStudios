//! Floor strategy selection from a manifest.
//!
//! Takes a [`ProgramManifest`] and decides, for each floor, which layout
//! strategy to use and what envelope it gets. Mixed-use buildings get a Part 3
//! podium strategy on lower floors and Part 9 residential above; vertical
//! circulation cores are aligned by reserving the same core bay on every floor.

use crate::{
    manifest::{FloorManifest, ProgramManifest, RoomManifest},
    mode::BuildingMode,
    Rect, RoomSpec,
};

/// How a single floor should be laid out.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FloorStrategy {
    /// Standard Part 9 residential BSP suite layout.
    ResidentialBsp,
    /// Part 3 office / business: central corridor with rooms on both sides.
    CorridorSpine,
    /// Part 3 retail / restaurant: one large open space plus service rooms.
    OpenRetail,
}

/// One floor ready for layout.
#[derive(Debug, Clone)]
pub struct FloorPlanInput {
    pub level: usize,
    pub name: String,
    pub occupancy: Option<String>,
    pub mode: BuildingMode,
    pub program: Vec<RoomSpec>,
    pub envelope: Rect,
    pub strategy: FloorStrategy,
    /// Size of the reserved circulation core (stairs + elevator + shaft), in
    /// feet. The core is pinned to the same corner on every floor.
    pub core: Rect,
}

/// Build per-floor plan inputs from a manifest.
#[must_use]
pub fn plan_floors(manifest: &ProgramManifest) -> Vec<FloorPlanInput> {
    let total_sqft: f32 = manifest
        .floors
        .iter()
        .map(|f| f.rooms.iter().map(|r| r.min_area.unwrap_or(0.0)).sum::<f32>())
        .sum();
    let requested = manifest.sqft.unwrap_or(total_sqft);
    let footprint = requested.max(total_sqft);

    // Choose a footprint shape. For Part 3 / mixed we use a squarer aspect
    // than the Part 9 golden ratio because commercial floor plates are usually
    // closer to square.
    let (w, d) = shape_envelope(footprint, manifest.mode);
    let envelope = Rect { x: 0.0, y: 0.0, w, h: d };

    // Reserve a vertical circulation core on every floor. Its size is the same
    // on every floor so stairs/elevators align; it is subtracted from the
    // envelope before the rest of the rooms are laid out.
    let core = circulation_core(manifest, envelope);

    manifest
        .floors
        .iter()
        .map(|floor| {
            let strategy = choose_strategy(manifest.mode, floor);
            let mode = floor_mode(manifest.mode, floor);
            let program: Vec<RoomSpec> = floor
                .rooms
                .iter()
                .map(|r| room_manifest_to_spec(r, mode))
                .collect();
            FloorPlanInput {
                level: floor.level,
                name: floor.name.clone(),
                occupancy: floor.occupancy.clone(),
                mode,
                program,
                envelope,
                strategy,
                core,
            }
        })
        .collect()
}

fn room_manifest_to_spec(r: &RoomManifest, mode: BuildingMode) -> RoomSpec {
    use crate::catalog::RoomCatalog;
    let cat = RoomCatalog::for_mode(mode);
    let entry = cat.get(&r.room_type);
    RoomSpec {
        id: r.id.clone(),
        room_type: r.room_type.clone(),
        weight: r.weight.unwrap_or_else(|| entry.map_or(1.0, |e| e.default_weight)),
        min_area: r.min_area.unwrap_or_else(|| entry.map_or(50.0, |e| e.default_min_area)),
    }
}

fn shape_envelope(footprint: f32, mode: BuildingMode) -> (f32, f32) {
    let ratio = match mode {
        BuildingMode::Part9 => 1.4,
        BuildingMode::Part3 | BuildingMode::Mixed => 1.15,
    };
    let depth = (footprint / ratio).sqrt();
    let width = footprint / depth;
    (width.round(), depth.round())
}

fn choose_strategy(mode: BuildingMode, floor: &FloorManifest) -> FloorStrategy {
    match mode {
        BuildingMode::Part9 => FloorStrategy::ResidentialBsp,
        BuildingMode::Part3 => part3_strategy(floor),
        BuildingMode::Mixed => {
            if is_residential_floor(floor) {
                FloorStrategy::ResidentialBsp
            } else {
                part3_strategy(floor)
            }
        }
    }
}

fn part3_strategy(floor: &FloorManifest) -> FloorStrategy {
    let has_open_retail = floor
        .rooms
        .iter()
        .any(|r| r.room_type == "retail" || r.room_type == "restaurant");
    let has_corridor = floor.rooms.iter().any(|r| r.room_type == "corridor" || r.room_type == "hallway");
    if has_open_retail && !has_corridor {
        FloorStrategy::OpenRetail
    } else {
        FloorStrategy::CorridorSpine
    }
}

fn is_residential_floor(floor: &FloorManifest) -> bool {
    floor
        .rooms
        .iter()
        .any(|r| r.room_type.contains("bedroom") || r.room_type == "living" || r.room_type == "kitchen")
}

fn floor_mode(building_mode: BuildingMode, floor: &FloorManifest) -> BuildingMode {
    match building_mode {
        BuildingMode::Part9 | BuildingMode::Part3 => building_mode,
        BuildingMode::Mixed => {
            if is_residential_floor(floor) {
                BuildingMode::Part9
            } else {
                BuildingMode::Part3
            }
        }
    }
}

/// Reserved circulation core (stairs + elevator + shaft). Pinned to the
/// front-left corner. If the manifest has no circulation rooms, the core is
/// empty and layout uses the full envelope.
fn circulation_core(manifest: &ProgramManifest, envelope: Rect) -> Rect {
    let mut core_w = 0.0_f32;
    let mut core_d = 0.0_f32;
    for floor in &manifest.floors {
        for r in &floor.rooms {
            if r.room_type == "stairs" {
                // Buildable stair bay, approximately 7 ft × 10 ft.
                core_w = core_w.max(7.0);
                core_d = core_d.max(10.0);
            } else if r.room_type == "elevator" {
                core_w = core_w.max(5.0);
                core_d = core_d.max(5.0);
            } else if r.room_type == "shaft" {
                core_w = core_w.max(4.0);
                core_d = core_d.max(4.0);
            }
        }
    }
    // Combine stairs + elevator side by side when both present.
    let total_w = (core_w + if core_d >= 5.0 { 5.0 } else { 0.0 }).min(envelope.w * 0.35);
    let total_d = core_d.max(5.0).min(envelope.h * 0.35);
    if total_w > 0.0 && total_d > 0.0 {
        Rect {
            x: envelope.x,
            y: envelope.y,
            w: total_w,
            h: total_d,
        }
    } else {
        // Empty core.
        Rect {
            x: envelope.x,
            y: envelope.y,
            w: 0.0,
            h: 0.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_office_manifest() -> ProgramManifest {
        ProgramManifest::from_json(
            r#"{
                "mode": "part3",
                "building_name": "Office",
                "sqft": 5000,
                "floors": [
                    {
                        "level": 1,
                        "name": "Ground",
                        "occupancy": "business",
                        "rooms": [
                            {"id": "lobby", "room_type": "lobby", "min_area": 200},
                            {"id": "corridor", "room_type": "corridor", "min_area": 150},
                            {"id": "stairs_1", "room_type": "stairs", "min_area": 120},
                            {"id": "elevator_1", "room_type": "elevator", "min_area": 25},
                            {"id": "office_open", "room_type": "office_open", "min_area": 1200},
                            {"id": "washroom_1", "room_type": "washroom", "min_area": 80}
                        ]
                    }
                ]
            }"#,
        )
        .unwrap()
    }

    #[test]
    fn plan_floors_makes_corridor_spine_for_office() {
        let manifest = sample_office_manifest();
        let plans = plan_floors(&manifest);
        assert_eq!(plans.len(), 1);
        assert_eq!(plans[0].strategy, FloorStrategy::CorridorSpine);
        assert!(plans[0].core.w > 0.0);
        assert!(plans[0].core.h > 0.0);
    }

    #[test]
    fn plan_floors_makes_open_retail_for_retail_floor() {
        let manifest = ProgramManifest::from_json(
            r#"{
                "mode": "part3",
                "floors": [
                    {
                        "level": 1,
                        "rooms": [
                            {"id": "retail_1", "room_type": "retail", "min_area": 1500},
                            {"id": "lobby", "room_type": "lobby", "min_area": 200},
                            {"id": "stairs_1", "room_type": "stairs", "min_area": 120},
                            {"id": "washroom_1", "room_type": "washroom", "min_area": 80}
                        ]
                    }
                ]
            }"#,
        )
        .unwrap();
        let plans = plan_floors(&manifest);
        assert_eq!(plans[0].strategy, FloorStrategy::OpenRetail);
    }

    #[test]
    fn mixed_building_splits_strategies_by_floor() {
        let manifest = ProgramManifest::from_json(
            r#"{
                "mode": "mixed",
                "floors": [
                    {
                        "level": 1,
                        "occupancy": "mercantile",
                        "rooms": [
                            {"id": "retail_1", "room_type": "retail", "min_area": 1200},
                            {"id": "lobby", "room_type": "lobby", "min_area": 150},
                            {"id": "stairs_1", "room_type": "stairs", "min_area": 120}
                        ]
                    },
                    {
                        "level": 2,
                        "occupancy": "residential",
                        "rooms": [
                            {"id": "living", "room_type": "living", "min_area": 200},
                            {"id": "bedroom_2", "room_type": "bedroom", "min_area": 120},
                            {"id": "stairs_2", "room_type": "stairs", "min_area": 120}
                        ]
                    }
                ]
            }"#,
        )
        .unwrap();
        let plans = plan_floors(&manifest);
        assert_eq!(plans[0].strategy, FloorStrategy::OpenRetail);
        assert_eq!(plans[1].strategy, FloorStrategy::ResidentialBsp);
        // Core is the same size on both floors.
        assert_eq!(plans[0].core, plans[1].core);
    }
}
