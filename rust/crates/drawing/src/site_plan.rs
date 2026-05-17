//! Site plan SVG generator.
//!
//! Port of `ArchEngine_kernel/scripts/generate_site_plan.py` (91 LOC). Emits
//! a permit-style site plan: lot boundary, building footprint, setbacks,
//! driveway. Distances in feet (Ontario residential convention is mixed;
//! permit sets in Toronto/Ottawa typically use imperial for site plans).

use std::fmt::Write as _;

/// Geometry of the site plan: lot box, building footprint, setbacks, driveway.
/// All distances in feet (the Python uses imperial throughout).
#[derive(Debug, Clone)]
pub struct SitePlan {
    pub lot_width_ft: f32,
    pub lot_depth_ft: f32,
    pub building_x_ft: f32,
    pub building_z_ft: f32,
    pub building_width_ft: f32,
    pub building_depth_ft: f32,
    pub front_setback_ft: f32,
    pub side_setback_ft: f32,
    pub rear_setback_ft: f32,
    pub driveway_width_ft: f32,
}

impl SitePlan {
    /// Compute a SitePlan from building width/depth in metres plus standard
    /// Ontario residential setbacks (matches `permit_drawing_set.py`'s
    /// defaults: 60' x 120' lot, 25/6/25 setbacks, 12' driveway, building
    /// centred X-wise and offset 30' from the front lot line).
    #[must_use]
    pub fn from_building_metres(building_width_m: f32, building_depth_m: f32) -> Self {
        let m_to_ft = 3.280_84;
        let lot_width_ft = 60.0;
        let lot_depth_ft = 120.0;
        let building_width_ft = building_width_m * m_to_ft;
        let building_depth_ft = building_depth_m * m_to_ft;
        Self {
            lot_width_ft,
            lot_depth_ft,
            building_x_ft: (lot_width_ft - building_width_ft) * 0.5,
            building_z_ft: 30.0,
            building_width_ft,
            building_depth_ft,
            front_setback_ft: 25.0,
            side_setback_ft: 6.0,
            rear_setback_ft: 25.0,
            driveway_width_ft: 12.0,
        }
    }
}

/// Render the site plan to an SVG string. Port of
/// `generate_site_plan_svg` (`generate_site_plan.py:26`). The Python's
/// `building_data` argument is unused in the body — we drop it.
#[must_use]
#[allow(clippy::too_many_lines)]
// Drawing math uses single-letter binding conventions (x, y, w, h) that
// match the SVG vocabulary; renaming them would obscure rather than clarify.
#[allow(clippy::many_single_char_names)]
pub fn generate_site_plan_svg(site: &SitePlan) -> String {
    let scale: f32 = 5.0;
    let margin: f32 = 60.0;
    let w = site.lot_width_ft * scale + 2.0 * margin;
    let h = site.lot_depth_ft * scale + 2.0 * margin;

    let x = |ft: f32| margin + ft * scale;
    let y = |ft: f32| h - margin - ft * scale;

    let mut s = String::with_capacity(2048);

    let _ = writeln!(
        s,
        r#"<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">"#
    );
    let _ = writeln!(s, r#"<rect width="{w}" height="{h}" fill="white"/>"#);

    // Lot boundary.
    let _ = writeln!(
        s,
        r##"<rect x="{x_lot}" y="{y_lot}" width="{w_lot}" height="{h_lot}" fill="#f4f4f0" stroke="black" stroke-width="2"/>"##,
        x_lot = x(0.0),
        y_lot = y(site.lot_depth_ft),
        w_lot = site.lot_width_ft * scale,
        h_lot = site.lot_depth_ft * scale,
    );

    // Setback envelope (dashed grey).
    let _ = writeln!(
        s,
        r##"<rect x="{xs}" y="{ys}" width="{ws}" height="{hs}" fill="none" stroke="#888" stroke-width="1" stroke-dasharray="6,4"/>"##,
        xs = x(site.side_setback_ft),
        ys = y(site.lot_depth_ft - site.rear_setback_ft),
        ws = (site.lot_width_ft - 2.0 * site.side_setback_ft) * scale,
        hs = (site.lot_depth_ft - site.front_setback_ft - site.rear_setback_ft) * scale,
    );

    // Building footprint.
    let _ = writeln!(
        s,
        r##"<rect x="{xb}" y="{yb}" width="{wb}" height="{hb}" fill="#d8d4c8" stroke="black" stroke-width="1.5"/>"##,
        xb = x(site.building_x_ft),
        yb = y(site.building_z_ft + site.building_depth_ft),
        wb = site.building_width_ft * scale,
        hb = site.building_depth_ft * scale,
    );

    // Driveway (between building front and lot front line, centred on building).
    let drive_x = site.building_x_ft + (site.building_width_ft - site.driveway_width_ft) * 0.5;
    let _ = writeln!(
        s,
        r##"<rect x="{xd}" y="{yd}" width="{wd}" height="{hd}" fill="#e8e4d8" stroke="#888" stroke-width="1"/>"##,
        xd = x(drive_x),
        yd = y(site.building_z_ft),
        wd = site.driveway_width_ft * scale,
        hd = site.building_z_ft * scale,
    );

    // Labels.
    let label_attrs = r#"font-family="Helvetica, Arial, sans-serif" font-size="11" fill="black""#;
    let _ = writeln!(
        s,
        r#"<text x="{xl}" y="{yl}" text-anchor="middle" {label_attrs}>LOT: {lw:.0}' x {ld:.0}'</text>"#,
        xl = x(site.lot_width_ft * 0.5),
        yl = y(-2.0),
        lw = site.lot_width_ft,
        ld = site.lot_depth_ft,
    );
    let _ = writeln!(
        s,
        r#"<text x="{xb}" y="{yb}" text-anchor="middle" dominant-baseline="middle" {label_attrs}>BUILDING</text>"#,
        xb = x(site.building_x_ft + site.building_width_ft * 0.5),
        yb = y(site.building_z_ft + site.building_depth_ft * 0.5),
    );
    let _ = writeln!(
        s,
        r#"<text x="{xs}" y="{ys}" {label_attrs}>Setbacks: F {f:.0}' / S {sd:.0}' / R {r:.0}'</text>"#,
        xs = x(2.0),
        ys = y(2.0),
        f = site.front_setback_ft,
        sd = site.side_setback_ft,
        r = site.rear_setback_ft,
    );

    s.push_str("</svg>\n");
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_building_metres_uses_standard_defaults() {
        let s = SitePlan::from_building_metres(12.0, 10.0);
        assert_eq!(s.lot_width_ft, 60.0);
        assert_eq!(s.lot_depth_ft, 120.0);
        assert_eq!(s.front_setback_ft, 25.0);
        assert_eq!(s.side_setback_ft, 6.0);
        assert_eq!(s.rear_setback_ft, 25.0);
        assert_eq!(s.driveway_width_ft, 12.0);
        // 12 m * 3.28084 ≈ 39.37 ft
        assert!((s.building_width_ft - 39.37).abs() < 0.01);
        // building centred X-wise on the 60' lot
        assert!((s.building_x_ft - (60.0 - 39.37) * 0.5).abs() < 0.01);
    }

    #[test]
    fn generate_site_plan_svg_emits_well_formed_svg() {
        let site = SitePlan::from_building_metres(12.0, 10.0);
        let svg = generate_site_plan_svg(&site);
        assert!(svg.starts_with("<svg xmlns="));
        assert!(svg.ends_with("</svg>\n"));
        // Lot + setback envelope + building + driveway = 4 rects, plus the
        // white background = 5 total.
        assert_eq!(svg.matches("<rect").count(), 5);
        // 3 text labels: LOT, BUILDING, Setbacks.
        assert_eq!(svg.matches("<text").count(), 3);
        assert!(svg.contains("LOT: 60' x 120'"));
        assert!(svg.contains("BUILDING"));
        assert!(svg.contains("Setbacks: F 25' / S 6' / R 25'"));
    }

    #[test]
    fn driveway_runs_between_building_front_and_lot_front() {
        let site = SitePlan::from_building_metres(12.0, 10.0);
        let svg = generate_site_plan_svg(&site);
        // building_z_ft = 30 → driveway height = 30 * 5 = 150 in SVG units.
        // The driveway is the only rect with stroke="#888" and fill="#e8e4d8".
        assert!(svg.contains(r##"fill="#e8e4d8""##));
    }
}
