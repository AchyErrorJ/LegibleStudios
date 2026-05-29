//! Read Legible Studio's LiDAR terrain JSON and sample it for the site plan.
//!
//! The CAD's LiDAR extractor (`ArchEngine_CAD/tools/lidar`) reads Ontario
//! GeoTIFF DEMs over a property's bounds and writes a terrain — a `terrain_mesh`
//! of local-mm vertices plus `width_ft`/`depth_ft` and min/max elevation. The
//! property bounds *are* the lot, so the terrain gives both the lot size and
//! the grade. This reader extracts the lot dimensions and spot elevations at
//! the lot corners to drive the site plan.

use serde_json::Value;

/// Terrain sampled for a site plan: lot size (ft) + corner grade (m) + the
/// raw vertex mesh in local mm so contours can be derived.
#[derive(Debug, Clone)]
pub struct Terrain {
    pub lot_width_ft: f32,
    pub lot_depth_ft: f32,
    /// Spot elevations (m) at the lot corners, SW / SE / NE / NW.
    pub corners_m: [f32; 4],
    /// Raw vertex mesh as `[x_mm, elev_mm, z_mm]` (CAD's local mm coords).
    /// Kept for marching-squares contour generation; empty if the input had
    /// no vertices.
    pub vertices: Vec<[f32; 3]>,
}

/// One marching-squares segment in lot-local feet: `((x1, y1), (x2, y2))`.
pub type ContourSegment = ((f32, f32), (f32, f32));

/// A single contour line at one elevation, expressed as a bag of straight
/// segments in lot-local feet. Segments are unstitched (marching squares
/// emits them per-cell) — fine for SVG line rendering.
#[derive(Debug, Clone)]
pub struct Contour {
    pub elevation_m: f32,
    pub segments_ft: Vec<ContourSegment>,
}

/// Parse a terrain JSON (the `terrain_mesh` shape) and sample the four lot
/// corners. Returns `None` if the file has no usable terrain mesh.
#[must_use]
#[allow(clippy::cast_possible_truncation)] // elevations/dims are bounded
pub fn from_json(json: &str) -> Option<Terrain> {
    const FT_TO_MM: f32 = 304.8;
    let v: Value = serde_json::from_str(json).ok()?;
    // terrain_mesh may be at the root or nested.
    let mesh = v.get("terrain_mesh").unwrap_or(&v);
    let f = |k: &str| mesh.get(k).and_then(Value::as_f64).map(|x| x as f32);

    let width_ft = f("width_ft").unwrap_or(0.0);
    let depth_ft = f("depth_ft").unwrap_or(0.0);
    if width_ft <= 0.0 || depth_ft <= 0.0 {
        return None;
    }

    // Vertices: [{ "position": [x, y, z] }] in local mm (y = elevation).
    let verts: Vec<[f32; 3]> = mesh
        .get("vertices")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .filter_map(|p| {
                    let pos = p.get("position").and_then(Value::as_array)?;
                    Some([num(pos, 0), num(pos, 1), num(pos, 2)])
                })
                .collect()
        })
        .unwrap_or_default();

    let (w, d) = (width_ft * FT_TO_MM, depth_ft * FT_TO_MM);
    // Corners in local plan mm (x, z): SW, SE, NE, NW.
    let corner_xy = [(0.0, 0.0), (w, 0.0), (w, d), (0.0, d)];
    let corners_m = corner_xy.map(|(cx, cz)| nearest_elevation_m(&verts, cx, cz));

    Some(Terrain { lot_width_ft: width_ft, lot_depth_ft: depth_ft, corners_m, vertices: verts })
}

/// Generate contour lines at `interval_m` spacing across the lot via marching
/// squares on a uniform 32×32 sample grid. Returns an empty vector if there's
/// no usable mesh or the elevation range is below a contour interval.
#[must_use]
#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_precision_loss,
    clippy::many_single_char_names,
    clippy::similar_names,
)]
pub fn contours(terrain: &Terrain, interval_m: f32) -> Vec<Contour> {
    const N: usize = 32;
    const FT_TO_MM: f32 = 304.8;
    if terrain.vertices.is_empty() || interval_m <= 0.0 {
        return Vec::new();
    }
    let w_mm = terrain.lot_width_ft * FT_TO_MM;
    let d_mm = terrain.lot_depth_ft * FT_TO_MM;
    // Sample elevations onto an (N+1)×(N+1) grid in metres.
    let mut grid = vec![0.0_f32; (N + 1) * (N + 1)];
    let mut emin = f32::INFINITY;
    let mut emax = f32::NEG_INFINITY;
    for j in 0..=N {
        for i in 0..=N {
            let x = w_mm * (i as f32 / N as f32);
            let z = d_mm * (j as f32 / N as f32);
            let e = nearest_elevation_m(&terrain.vertices, x, z);
            grid[j * (N + 1) + i] = e;
            emin = emin.min(e);
            emax = emax.max(e);
        }
    }
    if !emax.is_finite() || emax - emin < interval_m * 0.5 {
        return Vec::new();
    }
    // Walk discrete levels through the elevation range, snapped to interval.
    let start = (emin / interval_m).ceil() * interval_m;
    let mut out = Vec::new();
    let mut level = start;
    let cell_w_ft = terrain.lot_width_ft / N as f32;
    let cell_d_ft = terrain.lot_depth_ft / N as f32;
    while level <= emax + 1e-6 {
        let mut segs = Vec::new();
        for j in 0..N {
            for i in 0..N {
                // Corner elevations: a=SW, b=SE, c=NE, d=NW.
                let row = j * (N + 1);
                let row1 = (j + 1) * (N + 1);
                let a = grid[row + i];
                let b = grid[row + i + 1];
                let c = grid[row1 + i + 1];
                let d = grid[row1 + i];
                let x0 = i as f32 * cell_w_ft;
                let x1 = (i + 1) as f32 * cell_w_ft;
                let y0 = j as f32 * cell_d_ft;
                let y1 = (j + 1) as f32 * cell_d_ft;
                marching_square(level, a, b, c, d, x0, x1, y0, y1, &mut segs);
            }
        }
        if !segs.is_empty() {
            out.push(Contour { elevation_m: level, segments_ft: segs });
        }
        level += interval_m;
    }
    out
}

/// One cell of marching squares. Corners (`a` SW, `b` SE, `c` NE, `d` NW)
/// classified above/below the iso-level → 16 cases. Linear interpolation on
/// each crossed edge gives the segment endpoints in lot-local feet.
#[allow(clippy::too_many_arguments, clippy::many_single_char_names)]
fn marching_square(
    iso: f32,
    a: f32, b: f32, c: f32, d: f32,
    x0: f32, x1: f32, y0: f32, y1: f32,
    out: &mut Vec<ContourSegment>,
) {
    let bit = |v: f32| u8::from(v >= iso);
    let idx = bit(a) | (bit(b) << 1) | (bit(c) << 2) | (bit(d) << 3);
    if idx == 0 || idx == 15 {
        return;
    }
    let interp = |va: f32, vb: f32| -> f32 {
        if (vb - va).abs() < 1e-6 { 0.5 } else { ((iso - va) / (vb - va)).clamp(0.0, 1.0) }
    };
    let e0 = || { let t = interp(a, b); (x0 + t * (x1 - x0), y0) }; // bottom
    let e1 = || { let t = interp(b, c); (x1, y0 + t * (y1 - y0)) }; // right
    let e2 = || { let t = interp(d, c); (x0 + t * (x1 - x0), y1) }; // top
    let e3 = || { let t = interp(a, d); (x0, y0 + t * (y1 - y0)) }; // left
    match idx {
        1 | 14 => out.push((e3(), e0())),
        2 | 13 => out.push((e0(), e1())),
        3 | 12 => out.push((e3(), e1())),
        4 | 11 => out.push((e1(), e2())),
        5 => { out.push((e3(), e0())); out.push((e1(), e2())); }
        6 | 9 => out.push((e0(), e2())),
        7 | 8 => out.push((e3(), e2())),
        10 => { out.push((e0(), e1())); out.push((e2(), e3())); }
        _ => {}
    }
}

#[allow(clippy::cast_possible_truncation)]
fn num(arr: &[Value], i: usize) -> f32 {
    arr.get(i).and_then(Value::as_f64).map_or(0.0, |x| x as f32)
}

/// Elevation (m) of the vertex nearest `(x, z)` in plan mm; `position` is
/// `[x, y, z]` with y the elevation in mm → metres.
fn nearest_elevation_m(verts: &[[f32; 3]], x: f32, z: f32) -> f32 {
    let mut best = (f32::INFINITY, 0.0);
    for p in verts {
        let d2 = (p[0] - x).powi(2) + (p[2] - z).powi(2);
        if d2 < best.0 {
            best = (d2, p[1] / 1000.0); // mm → m
        }
    }
    best.1
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_terrain_mesh_and_samples_corners() {
        // A 50 x 50 ft mesh sloping from 0 (SW) up to 2 m (NE).
        let json = r#"{
            "terrain_mesh": {
                "width_ft": 50, "depth_ft": 50,
                "min_elevation": 0, "max_elevation": 2,
                "vertices": [
                    {"position": [0, 0, 0]},
                    {"position": [15240, 1000, 0]},
                    {"position": [0, 1000, 15240]},
                    {"position": [15240, 2000, 15240]}
                ]
            }
        }"#;
        let t = from_json(json).expect("terrain");
        assert!((t.lot_width_ft - 50.0).abs() < 1e-3);
        // SW corner ~0 m, NE corner ~2 m.
        assert!(t.corners_m[0].abs() < 0.1);
        assert!((t.corners_m[2] - 2.0).abs() < 0.1);
    }

    #[test]
    fn contours_emits_lines_on_a_sloping_lot() {
        // A 50x50 ft lot sloping 0 → 2 m corner-to-corner (4 corner vertices,
        // nearest-neighbour upsampled). At 0.5 m interval, expect ~4 contours
        // (0.5, 1.0, 1.5, 2.0) each with at least one segment.
        let json = r#"{
            "terrain_mesh": {
                "width_ft": 50, "depth_ft": 50,
                "vertices": [
                    {"position": [0, 0, 0]},
                    {"position": [15240, 1000, 0]},
                    {"position": [0, 1000, 15240]},
                    {"position": [15240, 2000, 15240]}
                ]
            }
        }"#;
        let t = from_json(json).expect("terrain");
        let c = contours(&t, 0.5);
        assert!(c.len() >= 2, "expected ≥2 contour levels, got {}", c.len());
        for ct in &c {
            assert!(!ct.segments_ft.is_empty(), "level {} empty", ct.elevation_m);
        }
        // Flat terrain emits nothing.
        let flat_json = r#"{
            "terrain_mesh": {
                "width_ft": 50, "depth_ft": 50,
                "vertices": [{"position":[0,1000,0]},{"position":[15240,1000,0]}]
            }
        }"#;
        let tf = from_json(flat_json).expect("flat");
        assert!(contours(&tf, 0.5).is_empty());
    }

    #[test]
    fn no_terrain_mesh_is_none() {
        assert!(from_json(r#"{"foo":1}"#).is_none());
        assert!(from_json("not json").is_none());
    }
}
