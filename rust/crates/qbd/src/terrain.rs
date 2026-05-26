//! Read Legible Studio's LiDAR terrain JSON and sample it for the site plan.
//!
//! The CAD's LiDAR extractor (`ArchEngine_CAD/tools/lidar`) reads Ontario
//! GeoTIFF DEMs over a property's bounds and writes a terrain — a `terrain_mesh`
//! of local-mm vertices plus `width_ft`/`depth_ft` and min/max elevation. The
//! property bounds *are* the lot, so the terrain gives both the lot size and
//! the grade. This reader extracts the lot dimensions and spot elevations at
//! the lot corners to drive the site plan.

use serde_json::Value;

/// Terrain sampled for a site plan: lot size (ft) + corner grade (m).
#[derive(Debug, Clone)]
pub struct Terrain {
    pub lot_width_ft: f32,
    pub lot_depth_ft: f32,
    /// Spot elevations (m) at the lot corners, SW / SE / NE / NW.
    pub corners_m: [f32; 4],
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

    Some(Terrain { lot_width_ft: width_ft, lot_depth_ft: depth_ft, corners_m })
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
    fn no_terrain_mesh_is_none() {
        assert!(from_json(r#"{"foo":1}"#).is_none());
        assert!(from_json("not json").is_none());
    }
}
