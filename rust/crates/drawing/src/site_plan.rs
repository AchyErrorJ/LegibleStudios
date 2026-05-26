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
    /// Street the lot fronts (drawn along the front lot line).
    pub street: String,
    /// Municipal zone label (e.g. "R1").
    pub zone: String,
    /// Whether the footprint fits inside the buildable envelope.
    pub fits: bool,
    /// LiDAR grade spot elevations (m) at the corners, SW/SE/NE/NW. Empty if
    /// no terrain is wired; then no grade is drawn.
    pub grade_corners_m: Vec<f32>,
}

impl SitePlan {
    /// Compute a SitePlan from building width/depth in metres plus standard
    /// Ontario residential setbacks (matches `permit_drawing_set.py`'s
    /// defaults: 60' x 120' lot, 25/6/25 setbacks, 12' driveway, building
    /// centred X-wise and offset 30' from the front lot line).
    #[must_use]
    pub fn from_building_metres(building_width_m: f32, building_depth_m: f32) -> Self {
        let m_to_ft = 3.280_84;
        Self::from_lot(60.0, 120.0, building_width_m * m_to_ft, building_depth_m * m_to_ft, (25.0, 6.0, 25.0), "Street", "R1")
    }

    /// Place a building footprint (ft) on a lot (ft) per `(front, side, rear)`
    /// setbacks (ft): centred across the lot, sitting at the front setback.
    /// `fits` records whether it stays inside the buildable envelope.
    #[must_use]
    pub fn from_lot(
        lot_width_ft: f32,
        lot_depth_ft: f32,
        building_width_ft: f32,
        building_depth_ft: f32,
        setbacks_ft: (f32, f32, f32),
        street: &str,
        zone: &str,
    ) -> Self {
        let (front, side, rear) = setbacks_ft;
        let buildable_w = lot_width_ft - 2.0 * side;
        let buildable_d = lot_depth_ft - front - rear;
        let fits = building_width_ft <= buildable_w + 0.01 && building_depth_ft <= buildable_d + 0.01;
        Self {
            lot_width_ft,
            lot_depth_ft,
            building_x_ft: (lot_width_ft - building_width_ft) * 0.5,
            building_z_ft: front,
            building_width_ft,
            building_depth_ft,
            front_setback_ft: front,
            side_setback_ft: side,
            rear_setback_ft: rear,
            driveway_width_ft: 12.0,
            street: street.to_string(),
            zone: zone.to_string(),
            fits,
            grade_corners_m: Vec::new(),
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

    // Street along the front lot line (the front setback is measured from it).
    let street_top = y(0.0) + 8.0;
    let _ = writeln!(
        s,
        r##"<rect x="0" y="{street_top}" width="{w}" height="30" fill="#cfcfcf" stroke="#999" stroke-width="1"/>"##,
    );
    let _ = writeln!(
        s,
        r#"<text x="{cx}" y="{ty}" text-anchor="middle" {label_attrs}>{street} (STREET)</text>"#,
        cx = w * 0.5,
        ty = street_top + 20.0,
        street = site.street,
    );

    // Setback dimensions: front + rear down the left margin, side across the top.
    let dim = r##"stroke="#06c" stroke-width="1""##;
    let dimlbl = r##"font-family="Helvetica, Arial, sans-serif" font-size="10" fill="#06c""##;
    let lx = x(0.0) - 22.0; // left of the lot, in the margin
    // front (lot front line → building front)
    let _ = writeln!(s, r#"<line x1="{lx}" y1="{a}" x2="{lx}" y2="{b}" {dim}/>"#, a = y(0.0), b = y(site.front_setback_ft));
    let _ = writeln!(s, r#"<text x="{tx}" y="{ty}" text-anchor="middle" transform="rotate(-90 {tx} {ty})" {dimlbl}>F {f:.1} m</text>"#, tx = lx - 6.0, ty = (y(0.0) + y(site.front_setback_ft)) * 0.5, f = site.front_setback_ft / 3.280_84);
    // rear (building rear → rear lot line)
    let rear_z = site.building_z_ft + site.building_depth_ft;
    let _ = writeln!(s, r#"<line x1="{lx}" y1="{a}" x2="{lx}" y2="{b}" {dim}/>"#, a = y(rear_z), b = y(site.lot_depth_ft));
    let _ = writeln!(s, r#"<text x="{tx}" y="{ty}" text-anchor="middle" transform="rotate(-90 {tx} {ty})" {dimlbl}>R {r:.1} m</text>"#, tx = lx - 6.0, ty = (y(rear_z) + y(site.lot_depth_ft)) * 0.5, r = site.rear_setback_ft / 3.280_84);
    // side (lot side → building side), across the top
    let ty_line = y(site.lot_depth_ft) - 12.0;
    let _ = writeln!(s, r#"<line x1="{a}" y1="{ty_line}" x2="{b}" y2="{ty_line}" {dim}/>"#, a = x(0.0), b = x(site.building_x_ft));
    let _ = writeln!(s, r#"<text x="{tx}" y="{tt}" text-anchor="middle" {dimlbl}>S {sd:.1} m</text>"#, tx = (x(0.0) + x(site.building_x_ft)) * 0.5, tt = ty_line - 4.0, sd = site.side_setback_ft / 3.280_84);

    // North arrow (top-right).
    let nx = w - 30.0;
    let ny = 40.0;
    let _ = writeln!(s, r#"<line x1="{nx}" y1="{a}" x2="{nx}" y2="{b}" stroke="black" stroke-width="1.5"/>"#, a = ny + 18.0, b = ny - 10.0);
    let _ = writeln!(s, r#"<polygon points="{nx},{t} {l},{m} {r},{m}" fill="black"/>"#, t = ny - 16.0, l = nx - 5.0, r = nx + 5.0, m = ny - 6.0);
    let _ = writeln!(s, r#"<text x="{nx}" y="{ty}" text-anchor="middle" {label_attrs}>N</text>"#, ty = ny + 30.0);

    // Zone label + fit flag.
    let _ = writeln!(s, r#"<text x="{xs}" y="{ys}" {label_attrs}>ZONE: {zone}</text>"#, xs = x(2.0), ys = y(6.0), zone = site.zone);
    if !site.fits {
        let _ = writeln!(
            s,
            r##"<text x="{cx}" y="{ty}" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="12" font-weight="bold" fill="#c00">FOOTPRINT EXCEEDS BUILDABLE ENVELOPE</text>"##,
            cx = w * 0.5,
            ty = y(site.lot_depth_ft * 0.5),
        );
    }

    // LiDAR grade: spot elevations at the corners + a drainage arrow downhill.
    if site.grade_corners_m.len() == 4 {
        // Corner plan positions (ft): SW, SE, NE, NW.
        let corners = [
            (0.0, 0.0),
            (site.lot_width_ft, 0.0),
            (site.lot_width_ft, site.lot_depth_ft),
            (0.0, site.lot_depth_ft),
        ];
        let glbl = r##"font-family="Helvetica, Arial, sans-serif" font-size="10" fill="#070""##;
        for (i, &(cxft, czft)) in corners.iter().enumerate() {
            let _ = writeln!(
                s,
                r#"<text x="{tx}" y="{ty}" text-anchor="middle" {glbl}>▲{e:.1}</text>"#,
                tx = x(cxft),
                ty = y(czft) - 4.0,
                e = site.grade_corners_m[i],
            );
        }
        // Drainage arrow: from the highest corner toward the lowest.
        let hi = (0..4).max_by(|&a, &b| site.grade_corners_m[a].total_cmp(&site.grade_corners_m[b])).unwrap_or(0);
        let lo = (0..4).min_by(|&a, &b| site.grade_corners_m[a].total_cmp(&site.grade_corners_m[b])).unwrap_or(0);
        if (site.grade_corners_m[hi] - site.grade_corners_m[lo]).abs() > 0.05 {
            let (hx, hz) = corners[hi];
            let (lx, lz) = corners[lo];
            let (x1, y1, x2, y2) = (x(hx), y(hz), x(lx), y(lz));
            // Pull the arrow toward the lot centre so it reads inside.
            let cx = x(site.lot_width_ft * 0.5);
            let cy = y(site.lot_depth_ft * 0.5);
            let (ax1, ay1) = ((x1 + cx) * 0.5, (y1 + cy) * 0.5);
            let (ax2, ay2) = ((x2 + cx) * 0.5, (y2 + cy) * 0.5);
            let _ = writeln!(s, r##"<line x1="{ax1}" y1="{ay1}" x2="{ax2}" y2="{ay2}" stroke="#070" stroke-width="1.5"/>"##);
            let _ = writeln!(s, r#"<text x="{tx}" y="{ty}" {glbl}>drainage</text>"#, tx = (ax1 + ax2) * 0.5 + 4.0, ty = (ay1 + ay2) * 0.5);
        }
    }

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
        // bg + lot + setback envelope + building + driveway + street = 6 rects.
        assert_eq!(svg.matches("<rect").count(), 6);
        assert!(svg.contains("LOT: 60' x 120'"));
        assert!(svg.contains("BUILDING"));
        assert!(svg.contains("Setbacks: F 25' / S 6' / R 25'"));
        // Street + north arrow + zone label are present.
        assert!(svg.contains("(STREET)"));
        assert!(svg.contains(">N</text>"));
        assert!(svg.contains("ZONE:"));
    }

    #[test]
    fn from_lot_centres_building_and_flags_fit() {
        // 40x50 ft building on a 50x100 lot with 20/5/25 setbacks:
        // buildable = 40 x 55 → fits (40<=40 wide, 50<=55 deep).
        let s = SitePlan::from_lot(50.0, 100.0, 40.0, 50.0, (20.0, 5.0, 25.0), "Elm St", "R1");
        assert!(s.fits);
        assert!((s.building_x_ft - 5.0).abs() < 0.01); // (50-40)/2
        assert!((s.building_z_ft - 20.0).abs() < 0.01); // at the front setback
        assert_eq!(s.zone, "R1");
        // Too-wide building overflows the buildable envelope.
        let bad = SitePlan::from_lot(40.0, 100.0, 45.0, 30.0, (20.0, 5.0, 25.0), "Elm St", "R1");
        assert!(!bad.fits);
    }

    #[test]
    fn unfit_footprint_renders_a_warning() {
        let bad = SitePlan::from_lot(30.0, 60.0, 40.0, 50.0, (20.0, 5.0, 25.0), "Elm St", "R1");
        let svg = generate_site_plan_svg(&bad);
        assert!(svg.contains("EXCEEDS BUILDABLE ENVELOPE"));
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
