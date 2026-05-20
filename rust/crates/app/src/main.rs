//! Legible Studio desktop head — sketch pad (Increment 3) + floor-plan view.
//!
//! Bare-metal: window via `pk-surface-winit`, software rasterization via
//! tiny-skia. No Python, no GPU, no webview.
//!
//! Sketch a lot boundary; the room solver (a kernel `Solver`) lays out
//! rooms inside it, re-rendered live. Optionally underlay an existing
//! permit floor plan by passing a building.json.
//!
//! Usage:
//!     legible [building.json]      (building.json is an optional underlay)
//!
//! Controls:
//!   (opens in View mode — clicks just navigate)
//!   b            enter boundary mode (sketch the lot → solve rooms)
//!   f            enter freeform mode (draw shapes → freeform objects)
//!   v            back to view mode
//!   left-click   add a vertex (only in boundary/freeform mode)
//!   Enter        close: solve rooms (boundary) / bank the shape (freeform)
//!   c            clear the active mode's strokes
//!   right-drag   pan      scroll  zoom      Esc  quit

mod render;
mod sketch;

use catalog::room_rect;
use pk_object::Solver;
use pk_surface::{Button, InputEvent, KeyCode, Surface};
use pk_surface_winit::WinitSurface;
use sketch::Sketch;
use solver::{Answers, SubdivisionRoomSolver};
use tiny_skia::Pixmap;

#[allow(clippy::too_many_lines)] // the event loop reads better as one piece
fn main() -> anyhow::Result<()> {
    // Optional floor-plan underlay from a building.json.
    let slice = std::env::args().nth(1).and_then(|p| {
        let doc = archgeometry::parse_file(&p).ok()?;
        Some(qbd::generate_floor_plan_with_openings(
            &doc,
            1219.0,
            &drawing::Config::with_defaults(),
        ))
    });

    let mut surface = WinitSurface::new(1000, 800, "Legible Studio — Sketch")
        .map_err(|e| anyhow::anyhow!("window init failed: {e}"))?;

    let (w0, h0) = surface.size();
    // If we have a floor plan, fit to it; otherwise a sketch canvas at
    // 1px = 20mm with the origin near the bottom-left.
    let mut view = match &slice {
        Some(s) => render::fit_view(s, w0, h0, 40.0),
        None => render::View {
            scale: 0.05,
            offset_x: 60.0,
            offset_y: f32::from(u16::try_from(h0).unwrap_or(u16::MAX)) - 60.0,
        },
    };

    let mut sketch = Sketch::new();
    let mut rooms: Vec<[f32; 4]> = Vec::new();
    // Real program-driven zoned layout (3-bed/2-bath default program). The
    // sketched boundary is the envelope; rooms tile it proportionally.
    let solver = SubdivisionRoomSolver::from_answers(&Answers::default());

    let mut panning = false;
    let mut last = (0.0f32, 0.0f32);

    let resolve = |sketch: &Sketch| -> Vec<[f32; 4]> {
        let mut scene = sketch.to_scene();
        solver.solve(&mut scene);
        scene
            .objects
            .iter()
            .filter(|o| o.kind == "room")
            .filter_map(room_rect)
            .collect()
    };

    while !surface.should_close() {
        for ev in surface.poll_input() {
            match ev {
                InputEvent::Key {
                    code: KeyCode::Escape,
                    pressed: true,
                    ..
                } => return Ok(()),
                InputEvent::Key {
                    code: KeyCode::Enter,
                    pressed: true,
                    ..
                } => {
                    if sketch.close() {
                        rooms = resolve(&sketch);
                    }
                }
                InputEvent::Key {
                    code: KeyCode::Char('b'),
                    pressed: true,
                    ..
                } => sketch.set_mode(sketch::Mode::Boundary),
                InputEvent::Key {
                    code: KeyCode::Char('f'),
                    pressed: true,
                    ..
                } => sketch.set_mode(sketch::Mode::Freeform),
                InputEvent::Key {
                    code: KeyCode::Char('v'),
                    pressed: true,
                    ..
                } => sketch.set_mode(sketch::Mode::View),
                InputEvent::Key {
                    code: KeyCode::Char('c'),
                    pressed: true,
                    ..
                } => {
                    let was_boundary = sketch.mode == sketch::Mode::Boundary;
                    sketch.clear();
                    if was_boundary {
                        rooms.clear();
                    }
                }
                InputEvent::Scroll { dy, .. } => {
                    let factor = if dy > 0.0 { 1.1 } else { 0.9 };
                    view.zoom_about(factor, last.0, last.1);
                }
                InputEvent::PointerDown {
                    button: Button::Left,
                    x,
                    y,
                } => {
                    let (wx, wy) = view.unmap(x, y);
                    sketch.add_point(wx, wy);
                    last = (x, y);
                }
                InputEvent::PointerDown {
                    button: Button::Right,
                    x,
                    y,
                } => {
                    panning = true;
                    last = (x, y);
                }
                InputEvent::PointerUp {
                    button: Button::Right,
                    ..
                } => panning = false,
                InputEvent::PointerMove { x, y } => {
                    if panning {
                        view.pan(x - last.0, y - last.1);
                    }
                    last = (x, y);
                }
                _ => {}
            }
        }

        let (w, h) = surface.size();
        if w == 0 || h == 0 {
            continue;
        }
        let mut pixmap = Pixmap::new(w, h).ok_or_else(|| anyhow::anyhow!("pixmap alloc"))?;
        match &slice {
            Some(s) => render::render(s, &mut pixmap, view),
            None => render::fill_white(&mut pixmap),
        }
        render::draw_rooms(&rooms, &mut pixmap, view);
        render::draw_boundary(&sketch.points, sketch.closed, &mut pixmap, view);
        render::draw_freeforms(&sketch.freeforms, &sketch.current, &mut pixmap, view);
        render::pixmap_to_argb(&pixmap, surface.pixels_mut());
        surface.present();
    }

    Ok(())
}
