//! Part 3 fire separation between major occupancies (OBC 3.1).

use crate::part3::tables::{FireSeparation, MajorOccupancy};
use crate::report::{ComplianceCheck, ComplianceStatus};

/// Check whether adjacent floors with different occupancies require a fire
/// separation. Returns one check per unique adjacent pair.
#[must_use]
pub fn check_fire_separations(
    separations: &[FireSeparation],
    floor_occupancies: &[(usize, MajorOccupancy)],
) -> Vec<ComplianceCheck> {
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for window in floor_occupancies.windows(2) {
        let (a_level, a) = window[0];
        let (b_level, b) = window[1];
        if a == b {
            continue;
        }
        let key = sorted_key(a, b, a_level, b_level);
        if !seen.insert(key) {
            continue;
        }
        let rating = find_rating(separations, a, b);
        out.push(ComplianceCheck {
            rule_name: format!(
                "OBC 3.1 fire separation between Level {a_level} ({}) and Level {b_level} ({})",
                a.as_str(),
                b.as_str()
            ),
            code_section: "OBC 3.1".into(),
            status: if rating.is_some() {
                ComplianceStatus::Pass
            } else {
                ComplianceStatus::DataMissing
            },
            actual: format!(
                "required rating {}",
                rating.map_or("unknown".into(), |r| format!("{r:.1} h"))
            ),
            requirement: "fire separation between different major occupancies".into(),
            message: String::new(),
        });
    }
    out
}

fn sorted_key(
    a: MajorOccupancy,
    b: MajorOccupancy,
    a_level: usize,
    b_level: usize,
) -> (MajorOccupancy, MajorOccupancy, usize, usize) {
    if a.as_str() <= b.as_str() {
        (a, b, a_level, b_level)
    } else {
        (b, a, b_level, a_level)
    }
}

fn find_rating(separations: &[FireSeparation], a: MajorOccupancy, b: MajorOccupancy) -> Option<f32> {
    separations
        .iter()
        .find(|s| {
            (s.occupancy_a == a && s.occupancy_b == b)
                || (s.occupancy_a == b && s.occupancy_b == a)
        })
        .map(|s| s.rating_hours)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fire_separation_between_different_occupancies() {
        let seps = vec![FireSeparation {
            occupancy_a: MajorOccupancy::Residential,
            occupancy_b: MajorOccupancy::Mercantile,
            rating_hours: 2.0,
        }];
        let floors = vec![
            (1, MajorOccupancy::Mercantile),
            (2, MajorOccupancy::Residential),
        ];
        let checks = check_fire_separations(&seps, &floors);
        assert_eq!(checks.len(), 1);
        assert_eq!(checks[0].status, ComplianceStatus::Pass);
        assert!(checks[0].actual.contains("2.0"));
    }

    #[test]
    fn no_separation_for_same_occupancy() {
        let floors = vec![
            (1, MajorOccupancy::Business),
            (2, MajorOccupancy::Business),
        ];
        let checks = check_fire_separations(&[], &floors);
        assert!(checks.is_empty());
    }
}
