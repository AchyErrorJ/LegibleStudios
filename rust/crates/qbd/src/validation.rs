//! QBD validation orchestration.
//!
//! Ported from `QBDInterface::validateLayout` / `validateWall`
//! (`qbd_interface.cpp:883-931`). Wraps the `obc` engine: per-wall
//! compliance reports + an overall pass/fail with thermal aggregation.

use archgeometry::{SchemaDocument, SchemaWall};
use obc::{ComplianceReport, OBCEngine};

use crate::wall_types;

/// Aggregated validation result. Mirrors the C++ `QBDValidationResult`.
#[derive(Debug, Clone, Default)]
pub struct ValidationResult {
    pub overall_pass: bool,
    pub wall_reports: Vec<ComplianceReport>,

    // Thermal summary.
    pub total_exterior_wall_area: f32,
    pub average_r_value: f32,
    pub thermal_compliance: bool,

    // Structural summary.
    pub walls_checked: i32,
    pub walls_passed: i32,
    pub walls_failed: i32,
}

impl ValidationResult {
    /// Human-readable summary matching `QBDValidationResult::getSummary`.
    #[must_use]
    pub fn summary(&self) -> String {
        use std::fmt::Write as _;
        let mut out = String::from("=== QBD Validation Summary ===\n");
        let pass_label = if self.overall_pass { "PASS" } else { "FAIL" };
        let thermal_label = if self.thermal_compliance {
            "PASS"
        } else {
            "FAIL"
        };
        #[allow(clippy::cast_possible_truncation)]
        let r_int = self.average_r_value as i32;
        let _ = writeln!(out, "Overall: {pass_label}");
        let _ = writeln!(
            out,
            "Walls: {}/{} passed",
            self.walls_passed, self.walls_checked
        );
        let _ = writeln!(out, "Thermal: R-{r_int} ({thermal_label})");
        let _ = writeln!(
            out,
            "Exterior Wall Area: {} sqft",
            self.total_exterior_wall_area
        );
        out
    }
}

/// Millimetres per imperial foot — used to convert schema wall heights
/// (mm) into the foot-based units the OBC stud-span tables expect.
const MM_PER_FT: f32 = 304.8;

/// Validate one wall against the OBC engine using the default wall-type
/// for its category. Matches `QBDInterface::validateWall`
/// (`qbd_interface.cpp:923`).
///
/// `wall_height_mm` is the schema-native millimetre height; the OBC engine
/// works in feet, so the conversion happens at the boundary.
#[must_use]
pub fn validate_wall(
    obc: &OBCEngine,
    wall: &SchemaWall,
    wall_height_mm: f32,
    climate_zone: &str,
) -> ComplianceReport {
    let wall_type = wall_types::for_category(&wall.category);
    obc.validate_wall_assembly(
        &wall_type,
        wall_height_mm / MM_PER_FT,
        wall.category == "exterior",
        climate_zone,
    )
}

/// Validate every wall in the schema and return an aggregated result.
/// Matches `QBDInterface::validateLayout` (`qbd_interface.cpp:883`).
#[must_use]
pub fn validate_layout(
    obc: &OBCEngine,
    doc: &SchemaDocument,
    climate_zone: &str,
) -> ValidationResult {
    let mut result = ValidationResult::default();
    let mut exterior_wall_count = 0_usize;

    for wall in &doc.walls {
        let report = validate_wall(obc, wall, wall.height, climate_zone);
        let passed = report.passes();
        result.walls_checked += 1;
        if passed {
            result.walls_passed += 1;
        } else {
            result.walls_failed += 1;
        }
        result.wall_reports.push(report);

        if wall.category == "exterior" {
            result.total_exterior_wall_area += wall.length() * wall.height;
            exterior_wall_count += 1;
        }
    }

    if exterior_wall_count > 0 {
        let exterior_default = wall_types::for_category("exterior");
        result.average_r_value = exterior_default.total_r_value();
        let required_r = obc.minimum_r_value(climate_zone, "wall");
        result.thermal_compliance = result.average_r_value >= required_r;
    } else {
        // No exterior walls → thermal isn't applicable; don't fail on it.
        result.thermal_compliance = true;
    }

    result.overall_pass = result.walls_failed == 0 && result.thermal_compliance;
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    use archgeometry::SchemaWall;
    use glam::Vec3;

    #[test]
    fn empty_layout_passes_trivially() {
        let obc = OBCEngine::new();
        let doc = SchemaDocument::default();
        let r = validate_layout(&obc, &doc, "Zone 6");
        assert_eq!(r.walls_checked, 0);
        assert!(r.overall_pass);
    }

    #[test]
    fn one_exterior_wall_aggregates_area_and_r_value() {
        let obc = OBCEngine::new();
        let doc = SchemaDocument {
            walls: vec![SchemaWall {
                start: Vec3::ZERO,
                end: Vec3::new(5000.0, 0.0, 0.0),
                height: 2700.0,
                category: "exterior".into(),
                ..Default::default()
            }],
            ..Default::default()
        };
        let r = validate_layout(&obc, &doc, "Zone 6");
        assert_eq!(r.walls_checked, 1);
        // Area = 5000mm × 2700mm = 13_500_000 (mm² in this aggregation).
        assert!((r.total_exterior_wall_area - 13_500_000.0).abs() < 1.0);
        // Default exterior wall type (R-22 batt + R-5 c.i.) has total R = 28.45.
        assert!((r.average_r_value - 28.45).abs() < 0.01);
        // Zone 6 requires R-24 → passes thermal with R-28.45.
        assert!(r.thermal_compliance);
    }

    #[test]
    fn summary_contains_pass_or_fail_marker() {
        let obc = OBCEngine::new();
        let doc = SchemaDocument::default();
        let r = validate_layout(&obc, &doc, "Zone 6");
        let s = r.summary();
        assert!(s.contains("Overall: PASS") || s.contains("Overall: FAIL"));
        assert!(s.contains("Walls:"));
    }
}
