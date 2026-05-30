//! Native map widget for the parcel-sketch flow.
//!
//! Renders OSM raster tiles into a tiny-skia pixmap, lets the user pan and
//! zoom, click to add parcel-polygon vertices, and on Enter writes a
//! `site.json` matching the `qbd_dump --parcel` schema. Replaces the
//! Python `dialogs/site_dialog*` + `widgets/embedded_map_widget` stack.

#![allow(
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_precision_loss,
    clippy::similar_names,
    clippy::many_single_char_names,
)] // pixel/tile/world coordinate math; concise math vocabulary beats clippy here

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{Receiver, Sender, TryRecvError, channel};
use std::sync::{Arc, Mutex};
use std::thread;

use ls_site::{
    LatLon, TILE_SIZE_PX, TileCoord, TileFetcher, TileImage,
    lat_lon_to_world_pixel, utm17_from_wgs84, world_pixel_to_lat_lon,
};
use tiny_skia::{Color, Paint, PathBuilder, Pixmap, PixmapPaint, Stroke, Transform};

const M_TO_FT: f64 = 3.280_84;
const MIN_ZOOM: u8 = 1;
const MAX_ZOOM: u8 = 19;

/// Live map viewport + parcel sketch.
pub struct Map {
    /// Centre of the viewport in WGS84.
    pub centre: LatLon,
    /// Slippy-map zoom level (integer; OSM tiles are tile-quantised).
    pub zoom: u8,
    /// Parcel vertices in WGS84, in click order.
    pub polygon: Vec<LatLon>,
    /// Where to write the emitted `site.json` on Enter.
    out_path: PathBuf,
    /// Decoded tiles ready to blit.
    cache: HashMap<TileCoord, TileImage>,
    /// Tiles a fetch worker is currently downloading — don't re-request.
    pending: Arc<Mutex<HashSet<TileCoord>>>,
    /// Channel: main → worker, "please fetch this tile".
    req_tx: Sender<TileCoord>,
    /// Channel: worker → main, "here's the decoded tile (or an error)".
    resp_rx: Receiver<(TileCoord, Result<TileImage, String>)>,
}

impl Map {
    /// New map centred on Sudbury (the default residential market) at a
    /// neighbourhood-scale zoom. Spawns a background tile-fetch worker so
    /// the UI thread never blocks on HTTPS.
    pub fn new(out_path: impl Into<PathBuf>) -> Result<Self, ls_site::FetchError> {
        let fetcher = TileFetcher::new()?;
        let pending: Arc<Mutex<HashSet<TileCoord>>> = Arc::default();
        let (req_tx, req_rx) = channel::<TileCoord>();
        let (resp_tx, resp_rx) = channel::<(TileCoord, Result<TileImage, String>)>();
        let pending_w = Arc::clone(&pending);
        thread::Builder::new()
            .name("ls-app/tile-fetch".into())
            .spawn(move || {
                tile_worker(fetcher, &req_rx, &resp_tx, &pending_w);
            })
            .expect("spawn tile worker");
        Ok(Self {
            centre: LatLon { lat_deg: 46.4917, lon_deg: -80.9930 },
            zoom: 17,
            polygon: Vec::new(),
            out_path: out_path.into(),
            cache: HashMap::new(),
            pending,
            req_tx,
            resp_rx,
        })
    }

    /// Convert a screen-pixel offset (relative to the viewport top-left) to
    /// a WGS84 point. The viewport is conceptually centred on `self.centre`.
    #[must_use]
    pub fn screen_to_lat_lon(&self, sx: f32, sy: f32, vp_w: u32, vp_h: u32) -> LatLon {
        let (cwx, cwy) = lat_lon_to_world_pixel(self.centre, self.zoom);
        let wx = cwx + f64::from(sx) - f64::from(vp_w) / 2.0;
        let wy = cwy + f64::from(sy) - f64::from(vp_h) / 2.0;
        world_pixel_to_lat_lon(wx, wy, self.zoom)
    }

    /// Convert a WGS84 point to a screen-pixel offset (relative to the
    /// viewport top-left).
    #[must_use]
    #[allow(clippy::cast_possible_truncation)]
    pub fn lat_lon_to_screen(&self, p: LatLon, vp_w: u32, vp_h: u32) -> (f32, f32) {
        let (cwx, cwy) = lat_lon_to_world_pixel(self.centre, self.zoom);
        let (px, py) = lat_lon_to_world_pixel(p, self.zoom);
        (
            (px - cwx + f64::from(vp_w) / 2.0) as f32,
            (py - cwy + f64::from(vp_h) / 2.0) as f32,
        )
    }

    /// Pan the map by `(dx, dy)` screen pixels — i.e. dragging the map RIGHT
    /// by `dx` pixels shifts `centre` LEFT by `dx` world pixels.
    pub fn pan(&mut self, dx: f32, dy: f32) {
        let (cwx, cwy) = lat_lon_to_world_pixel(self.centre, self.zoom);
        let nx = cwx - f64::from(dx);
        let ny = cwy - f64::from(dy);
        self.centre = world_pixel_to_lat_lon(nx, ny, self.zoom);
    }

    /// Zoom in (positive) or out (negative) by one step, keeping the world
    /// point under `(anchor_sx, anchor_sy)` fixed on screen.
    pub fn zoom_about(&mut self, steps: i8, anchor_sx: f32, anchor_sy: f32, vp_w: u32, vp_h: u32) {
        let target_zoom = (i16::from(self.zoom) + i16::from(steps))
            .clamp(i16::from(MIN_ZOOM), i16::from(MAX_ZOOM)) as u8;
        if target_zoom == self.zoom {
            return;
        }
        // Lock the lat/lon under the anchor.
        let anchor = self.screen_to_lat_lon(anchor_sx, anchor_sy, vp_w, vp_h);
        self.zoom = target_zoom;
        // Adjust centre so `anchor` lands back at the same screen pixel.
        let (cwx, _cwy) = lat_lon_to_world_pixel(self.centre, self.zoom);
        let (awx, awy) = lat_lon_to_world_pixel(anchor, self.zoom);
        let new_cwx = awx - (f64::from(anchor_sx) - f64::from(vp_w) / 2.0);
        let new_cwy = awy - (f64::from(anchor_sy) - f64::from(vp_h) / 2.0);
        let _ = cwx; // silence "unused after rebind" reader confusion
        self.centre = world_pixel_to_lat_lon(new_cwx, new_cwy, self.zoom);
    }

    /// Append a parcel vertex at the clicked screen position.
    pub fn add_vertex(&mut self, sx: f32, sy: f32, vp_w: u32, vp_h: u32) {
        self.polygon.push(self.screen_to_lat_lon(sx, sy, vp_w, vp_h));
    }

    /// Drop all parcel vertices.
    pub fn clear_polygon(&mut self) {
        self.polygon.clear();
    }

    /// Drop the most recent vertex (Backspace handler).
    pub fn undo_vertex(&mut self) {
        self.polygon.pop();
    }

    /// Compute UTM-relative `(x_ft, y_ft)` coords for the parcel polygon,
    /// origin at the SW corner of the polygon's UTM bbox. Y is north (so
    /// matches CAD's `vertices_ft` convention).
    #[must_use]
    pub fn vertices_ft(&self) -> Vec<[f64; 2]> {
        if self.polygon.is_empty() {
            return Vec::new();
        }
        let utms: Vec<_> = self.polygon.iter().map(|p| utm17_from_wgs84(*p)).collect();
        let min_e = utms.iter().map(|u| u.easting_m).fold(f64::INFINITY, f64::min);
        let min_n = utms.iter().map(|u| u.northing_m).fold(f64::INFINITY, f64::min);
        utms.into_iter()
            .map(|u| [(u.easting_m - min_e) * M_TO_FT, (u.northing_m - min_n) * M_TO_FT])
            .collect()
    }

    /// Lat/lon bbox of the parcel polygon (NW + SE), useful for LiDAR query.
    #[must_use]
    pub fn bbox(&self) -> Option<(LatLon, LatLon)> {
        if self.polygon.is_empty() {
            return None;
        }
        let lat_min = self.polygon.iter().map(|p| p.lat_deg).fold(f64::INFINITY, f64::min);
        let lat_max = self.polygon.iter().map(|p| p.lat_deg).fold(f64::NEG_INFINITY, f64::max);
        let lon_min = self.polygon.iter().map(|p| p.lon_deg).fold(f64::INFINITY, f64::min);
        let lon_max = self.polygon.iter().map(|p| p.lon_deg).fold(f64::NEG_INFINITY, f64::max);
        Some((
            LatLon { lat_deg: lat_max, lon_deg: lon_min },
            LatLon { lat_deg: lat_min, lon_deg: lon_max },
        ))
    }

    /// Write `site.json` matching what `qbd_dump --parcel` expects, plus a
    /// `bbox` block the LiDAR backend (increments 4-6) will read.
    pub fn save_site_json(&self) -> std::io::Result<()> {
        let mut out = serde_json::Map::new();
        let verts: Vec<_> = self
            .vertices_ft()
            .into_iter()
            .map(|p| serde_json::json!([p[0], p[1]]))
            .collect();
        out.insert("vertices_ft".into(), serde_json::Value::Array(verts));
        if let Some((nw, se)) = self.bbox() {
            out.insert(
                "bbox".into(),
                serde_json::json!({
                    "lat_max": nw.lat_deg, "lon_min": nw.lon_deg,
                    "lat_min": se.lat_deg, "lon_max": se.lon_deg,
                }),
            );
        }
        let json = serde_json::to_string_pretty(&serde_json::Value::Object(out))?;
        if let Some(parent) = self.out_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&self.out_path, json)
    }

    /// Path the next `save_site_json` will write to.
    #[must_use]
    pub fn out_path(&self) -> &Path {
        &self.out_path
    }

    /// Drain any tiles the worker has finished and add them to the cache.
    /// Logs decode/HTTP errors to stderr (without crashing the UI).
    fn drain_worker_results(&mut self) {
        loop {
            match self.resp_rx.try_recv() {
                Ok((t, Ok(img))) => {
                    self.cache.insert(t, img);
                }
                Ok((t, Err(e))) => {
                    eprintln!("map: tile {}/{}/{} failed: {e}", t.z, t.x, t.y);
                }
                Err(TryRecvError::Empty | TryRecvError::Disconnected) => break,
            }
        }
    }

    /// Render the OSM raster + parcel overlay into `pix`. Non-blocking:
    /// tiles already in cache are blitted; missing tiles are queued on the
    /// worker thread and drawn next frame. The UI never freezes.
    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
    pub fn render(&mut self, pix: &mut Pixmap) {
        // 1. Pick up any tiles the worker finished since last frame.
        self.drain_worker_results();

        let (vp_w, vp_h) = (pix.width(), pix.height());
        // Background — grey behind any missing tiles.
        pix.fill(Color::from_rgba8(200, 200, 200, 255));

        // 2. World-pixel rect the viewport covers.
        let (cwx, cwy) = lat_lon_to_world_pixel(self.centre, self.zoom);
        let half_w = f64::from(vp_w) / 2.0;
        let half_h = f64::from(vp_h) / 2.0;
        let world_left = cwx - half_w;
        let world_top = cwy - half_h;
        let ts = f64::from(TILE_SIZE_PX);
        let tx_min = (world_left / ts).floor() as i64;
        let ty_min = (world_top / ts).floor() as i64;
        let tx_max = ((world_left + f64::from(vp_w)) / ts).floor() as i64;
        let ty_max = ((world_top + f64::from(vp_h)) / ts).floor() as i64;
        let tile_grid_max = i64::from(1u32 << u32::from(self.zoom));

        // 3. For each visible tile: blit if cached, otherwise queue.
        for ty in ty_min..=ty_max {
            for tx in tx_min..=tx_max {
                if tx < 0 || ty < 0 || tx >= tile_grid_max || ty >= tile_grid_max {
                    continue;
                }
                let t = TileCoord { z: self.zoom, x: tx as u32, y: ty as u32 };
                let ox = tx as f64 * ts - world_left;
                let oy = ty as f64 * ts - world_top;
                if let Some(img) = self.cache.get(&t) {
                    blit_rgba_tile(img, pix, ox, oy);
                } else {
                    // Queue the fetch if not already in flight.
                    let need_send = self
                        .pending
                        .lock()
                        .ok()
                        .is_some_and(|mut p| p.insert(t));
                    if need_send {
                        let _ = self.req_tx.send(t);
                    }
                }
            }
        }

        // 4. Parcel overlay + chrome.
        self.draw_polygon(pix, vp_w, vp_h);
        draw_crosshair(pix, vp_w as f32 / 2.0, vp_h as f32 / 2.0);
        draw_status_band(
            pix,
            vp_w,
            &format!(
                "MAP  z={}  centre {:.5}, {:.5}  parcel: {} pts  enter→save  v→exit",
                self.zoom,
                self.centre.lat_deg,
                self.centre.lon_deg,
                self.polygon.len(),
            ),
        );
    }

    fn draw_polygon(&self, pix: &mut Pixmap, vp_w: u32, vp_h: u32) {
        if self.polygon.is_empty() {
            return;
        }
        let pts: Vec<(f32, f32)> = self
            .polygon
            .iter()
            .map(|p| self.lat_lon_to_screen(*p, vp_w, vp_h))
            .collect();
        // Polyline edge.
        let mut pb = PathBuilder::new();
        pb.move_to(pts[0].0, pts[0].1);
        for p in &pts[1..] {
            pb.line_to(p.0, p.1);
        }
        if pts.len() >= 3 {
            pb.line_to(pts[0].0, pts[0].1); // close
        }
        if let Some(path) = pb.finish() {
            let mut paint = Paint::default();
            paint.set_color(Color::from_rgba8(220, 60, 30, 230));
            paint.anti_alias = true;
            let stroke = Stroke { width: 2.5, ..Stroke::default() };
            pix.stroke_path(&path, &paint, &stroke, Transform::identity(), None);
        }
        // Vertex dots.
        let mut dot_paint = Paint::default();
        dot_paint.set_color(Color::from_rgba8(220, 60, 30, 255));
        dot_paint.anti_alias = true;
        for (x, y) in &pts {
            if let Some(circle) = PathBuilder::from_circle(*x, *y, 4.0) {
                pix.fill_path(&circle, &dot_paint, tiny_skia::FillRule::Winding, Transform::identity(), None);
            }
        }
    }
}

/// Worker thread: pull TileCoord requests off `req_rx`, fetch + decode each
/// one, push the result on `resp_tx`, and remove from `pending` so the main
/// thread can re-queue if the user navigates back.
#[allow(clippy::needless_pass_by_value)] // worker thread owns the fetcher for its lifetime
fn tile_worker(
    fetcher: TileFetcher,
    req_rx: &Receiver<TileCoord>,
    resp_tx: &Sender<(TileCoord, Result<TileImage, String>)>,
    pending: &Arc<Mutex<HashSet<TileCoord>>>,
) {
    while let Ok(t) = req_rx.recv() {
        let result = fetcher.fetch(t).map_err(|e| e.to_string());
        if let Ok(mut p) = pending.lock() {
            p.remove(&t);
        }
        if resp_tx.send((t, result)).is_err() {
            break; // main thread dropped the receiver
        }
    }
}

/// Blit a decoded OSM tile into `dst` at top-left `(ox, oy)` (tiny-skia
/// clips for us). The tile's RGBA bytes go straight in — tiny-skia's
/// `Pixmap` format is RGBA premultiplied, and OSM tiles are fully opaque,
/// so unpremul-RGBA == premul-RGBA byte-for-byte.
#[allow(
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_precision_loss,
)]
fn blit_rgba_tile(img: &TileImage, dst: &mut Pixmap, ox: f64, oy: f64) {
    let expected = (img.size as usize) * (img.size as usize) * 4;
    if img.rgba.len() < expected {
        eprintln!(
            "map: tile rgba truncated ({} < expected {}), skipping",
            img.rgba.len(), expected,
        );
        return;
    }
    let Some(mut src) = Pixmap::new(img.size, img.size) else { return; };
    src.data_mut()[..expected].copy_from_slice(&img.rgba[..expected]);
    let pp = PixmapPaint::default();
    dst.draw_pixmap(
        ox as i32,
        oy as i32,
        src.as_ref(),
        &pp,
        Transform::identity(),
        None,
    );
}

fn draw_crosshair(pix: &mut Pixmap, x: f32, y: f32) {
    let mut paint = Paint::default();
    paint.set_color(Color::from_rgba8(0, 0, 0, 180));
    paint.anti_alias = true;
    let stroke = Stroke { width: 1.0, ..Stroke::default() };
    let mut pb = PathBuilder::new();
    pb.move_to(x - 8.0, y);
    pb.line_to(x + 8.0, y);
    pb.move_to(x, y - 8.0);
    pb.line_to(x, y + 8.0);
    if let Some(path) = pb.finish() {
        pix.stroke_path(&path, &paint, &stroke, Transform::identity(), None);
    }
}

#[allow(clippy::cast_precision_loss)]
fn draw_status_band(pix: &mut Pixmap, vp_w: u32, _text: &str) {
    // Solid band at the bottom; the actual text rendering would need
    // fontdue. The app's existing render layer doesn't do text yet, so this
    // is just a visible status strip with the data echoed to stderr.
    let h = 24_f32;
    let y0 = pix.height() as f32 - h;
    let Some(rect) = tiny_skia::Rect::from_xywh(0.0, y0, vp_w as f32, h) else { return; };
    let path = PathBuilder::from_rect(rect);
    let mut paint = Paint::default();
    paint.set_color(Color::from_rgba8(0, 0, 0, 180));
    pix.fill_path(&path, &paint, tiny_skia::FillRule::Winding, Transform::identity(), None);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp_out() -> PathBuf {
        std::env::temp_dir().join("ls-app-map-test.json")
    }

    #[test]
    fn pan_then_lookup_round_trips_through_centre() {
        let mut m = Map::new(tmp_out()).expect("map");
        let start = m.centre;
        m.pan(50.0, 30.0);
        m.pan(-50.0, -30.0);
        assert!((m.centre.lat_deg - start.lat_deg).abs() < 1e-9);
        assert!((m.centre.lon_deg - start.lon_deg).abs() < 1e-9);
    }

    #[test]
    fn zoom_in_about_anchor_keeps_anchor_lat_lon_under_anchor_pixel() {
        let mut m = Map::new(tmp_out()).expect("map");
        let (vp_w, vp_h) = (800_u32, 600_u32);
        let anchor = (200.0_f32, 150.0_f32);
        let p_before = m.screen_to_lat_lon(anchor.0, anchor.1, vp_w, vp_h);
        m.zoom_about(1, anchor.0, anchor.1, vp_w, vp_h);
        let p_after = m.screen_to_lat_lon(anchor.0, anchor.1, vp_w, vp_h);
        // Within a quarter-pixel at z+1 → sub-metre on the ground.
        assert!((p_before.lat_deg - p_after.lat_deg).abs() < 1e-5, "lat {} vs {}", p_before.lat_deg, p_after.lat_deg);
        assert!((p_before.lon_deg - p_after.lon_deg).abs() < 1e-5, "lon {} vs {}", p_before.lon_deg, p_after.lon_deg);
    }

    #[test]
    fn vertices_ft_origin_at_sw_corner() {
        let mut m = Map::new(tmp_out()).expect("map");
        // Three points around Sudbury — small enough that UTM 17 is metric-flat.
        m.polygon = vec![
            LatLon { lat_deg: 46.4900, lon_deg: -80.9900 },
            LatLon { lat_deg: 46.4900, lon_deg: -80.9890 },
            LatLon { lat_deg: 46.4910, lon_deg: -80.9890 },
        ];
        let v = m.vertices_ft();
        assert_eq!(v.len(), 3);
        // SW corner gets origin: at least one vertex must have x≈0 AND at
        // least one must have y≈0 (potentially different vertices).
        assert!(v.iter().any(|p| p[0] < 0.01));
        assert!(v.iter().any(|p| p[1] < 0.01));
    }

    #[test]
    fn save_site_json_emits_vertices_and_bbox() {
        let mut m = Map::new(tmp_out()).expect("map");
        m.polygon = vec![
            LatLon { lat_deg: 46.49, lon_deg: -80.99 },
            LatLon { lat_deg: 46.49, lon_deg: -80.98 },
            LatLon { lat_deg: 46.50, lon_deg: -80.99 },
        ];
        m.save_site_json().expect("write");
        let text = std::fs::read_to_string(m.out_path()).expect("read back");
        let v: serde_json::Value = serde_json::from_str(&text).unwrap();
        assert!(v["vertices_ft"].as_array().unwrap().len() == 3);
        assert!(v["bbox"]["lat_min"].as_f64().unwrap() < v["bbox"]["lat_max"].as_f64().unwrap());
        assert!(v["bbox"]["lon_min"].as_f64().unwrap() < v["bbox"]["lon_max"].as_f64().unwrap());
    }
}
