//! Legible Studio desktop head.
//!
//! Bare-metal: opens a window via `pk-surface-winit`, generates the permit
//! floor plan with the existing Rust pipeline, and software-rasterizes it
//! with tiny-skia. No Python, no GPU, no webview. The render layer is shared
//! with the eventual Semantic OS kernel target; only the window/input shim
//! (pk-surface-winit) is desktop-specific.
//!
//! Usage:
//!     legible [building.json]      (defaults to smoke_test_output/building.json)
//!
//! Controls: scroll = zoom, left-drag = pan, Esc = quit.

mod render;

use anyhow::Context;
use pk_surface::{Button, InputEvent, KeyCode, Surface};
use pk_surface_winit::WinitSurface;
use std::path::PathBuf;
use tiny_skia::Pixmap;

fn main() -> anyhow::Result<()> {
    let path = std::env::args()
        .nth(1)
        .map_or_else(|| PathBuf::from("smoke_test_output/building.json"), PathBuf::from);

    let doc = archgeometry::parse_file(&path)
        .with_context(|| format!("failed to parse {}", path.display()))?;
    let config = drawing::Config::with_defaults();
    let slice = qbd::generate_floor_plan_with_openings(&doc, 1219.0, &config);

    let mut surface = WinitSurface::new(1000, 800, "Legible Studio — Floor Plan")
        .map_err(|e| anyhow::anyhow!("window init failed: {e}"))?;

    // Start fit-to-window; user can zoom/pan from there.
    let (w0, h0) = surface.size();
    let mut view = render::fit_view(&slice, w0, h0, 40.0);
    let mut dragging = false;
    let mut last_pointer = (0.0f32, 0.0f32);

    while !surface.should_close() {
        for ev in surface.poll_input() {
            match ev {
                InputEvent::Key {
                    code: KeyCode::Escape,
                    pressed: true,
                    ..
                } => return Ok(()),
                InputEvent::Scroll { dy, .. } => {
                    let factor = if dy > 0.0 { 1.1 } else { 0.9 };
                    view.zoom_about(factor, last_pointer.0, last_pointer.1);
                }
                InputEvent::PointerDown {
                    button: Button::Left,
                    x,
                    y,
                } => {
                    dragging = true;
                    last_pointer = (x, y);
                }
                InputEvent::PointerUp {
                    button: Button::Left,
                    ..
                } => dragging = false,
                InputEvent::PointerMove { x, y } => {
                    if dragging {
                        view.pan(x - last_pointer.0, y - last_pointer.1);
                    }
                    last_pointer = (x, y);
                }
                _ => {}
            }
        }

        let (w, h) = surface.size();
        if w == 0 || h == 0 {
            continue;
        }
        let mut pixmap = Pixmap::new(w, h).context("pixmap alloc")?;
        render::render(&slice, &mut pixmap, view);
        render::pixmap_to_argb(&pixmap, surface.pixels_mut());
        surface.present();
    }

    Ok(())
}
