//! Part 3 egress checks (OBC 3.3 / 3.4).
//!
//! v1 uses a conservative proxy: the straight-line distance from each room's
//! centroid to the nearest exit stair must be within the occupancy's maximum
//! travel distance. A true path-distance check is deferred to a later phase.

use crate::part3::tables::{MajorOccupancy, TravelDistanceLimit};
use crate::report::{ComplianceCheck, ComplianceStatus};

/// Check that every room on each floor is within the maximum travel distance
/// to an exit stair. The distance is the straight-line room-centroid to
/// nearest-stair-centroid distance, treated as a conservative proxy.
#[must_use]
pub fn check_travel_distance(
    limits: &std::collections::HashMap<MajorOccupancy, TravelDistanceLimit>,
    floors: &[FloorEgress],
) -> Vec<ComplianceCheck> {
    let mut out = Vec::new();
    for floor in floors {
        let limit = limits
            .get(&floor.occupancy)
            .map(|l| l.max_distance_m)
            .unwrap_or(45.0);
        for room in &floor.rooms {
            let nearest = floor
                .stairs
                .iter()
                .map(|s| distance(room.center_m, *s))
                .min_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
                .unwrap_or(f32::INFINITY);
            // Scale straight-line by 1.5 to approximate actual walking path.
            let approx_walk_m = nearest * 1.5;
            let pass = approx_walk_m <= limit;
            out.push(ComplianceCheck {
                rule_name: format!("OBC 3.4.2.5 travel distance — {}", room.id),
                code_section: "OBC 3.4.2.5".into(),
                status: if pass { ComplianceStatus::Pass } else { ComplianceStatus::Fail },
                actual: format!("approx {approx_walk_m:.1} m to nearest stair"),
                requirement: format!("≤ {limit:.1} m for {}", floor.occupancy.as_str()),
                message: "Straight-line distance scaled by 1.5 as a path proxy.".into(),
            });
        }
    }
    out
}

fn distance(a: (f32, f32), b: (f32, f32)) -> f32 {
    ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2)).sqrt()
}

/// Egress geometry for one floor.
#[derive(Debug, Clone)]
pub struct FloorEgress {
    pub level: usize,
    pub occupancy: MajorOccupancy,
    pub rooms: Vec<RoomEgress>,
    /// Stair centroids in metres (plan coordinates).
    pub stairs: Vec<(f32, f32)>,
}

#[derive(Debug, Clone)]
pub struct RoomEgress {
    pub id: String,
    pub room_type: String,
    /// Room centroid in metres (plan coordinates).
    pub center_m: (f32, f32),
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn travel_distance_passes_when_room_near_stair() {
        let limits = {
            let mut m = std::collections::HashMap::new();
            m.insert(
                MajorOccupancy::Business,
                TravelDistanceLimit {
                    occupancy: MajorOccupancy::Business,
                    max_distance_m: 45.0,
                },
            );
            m
        };
        let floors = vec![FloorEgress {
            level: 1,
            occupancy: MajorOccupancy::Business,
            rooms: vec![RoomEgress {
                id: "office".into(),
                room_type: "office_open".into(),
                center_m: (10.0, 5.0),
            }],
            stairs: vec![(12.0, 5.0)],
        }];
        let checks = check_travel_distance(&limits, &floors);
        assert_eq!(checks[0].status, ComplianceStatus::Pass);
    }
}
