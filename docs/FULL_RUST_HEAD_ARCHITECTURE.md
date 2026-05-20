# Full-Rust Head + Object-Generation Architecture

**Date:** 2026-05-16
**Status:** Design. Decisions locked (see below); no code yet.
**Supersedes scope in:** `RUST_PORT_ROADMAP.md` §2 (which assumed headless + deferred UI). The UI is now in scope, bare-metal, and the product scope broadened to general object generation.

## Decisions locked (owner, 2026-05-16)

1. **Rendering: bare-metal software, not wgpu, not Tauri/webview.** `winit` + `softbuffer` + `tiny-skia` + `fontdue` + a hand-rolled immediate-mode UI. Chosen so the draw layer is identical on desktop and the Semantic OS kernel.
2. **Sketch pad: hybrid.** Strokes are both solver *constraints* and freeform *geometry objects* you can edit. This is the input/editing surface for the v2 in-app editor already in progress.
3. **Scope: "design anything."** General object generation via a flexible mechanism + scoped, growable catalog. Not residential-permit-only.
4. **Full Rust.** Drop Python (incl. the still-Python solver) and the webview option. Keep foundational crates (glam/serde/thiserror/anyhow/bytemuck).

## Guiding principle: separate mechanism from catalog

```
        ┌──────────────── MECHANISM (built once, robust, fixed) ────────────────┐
input → ConstraintGraph → Solver → PlacedObject[] → Generator → Geometry → Validator → Output
        └────────────────────────────────────────────────────────────────────────┘
                                       ▲                  ▲              ▲
                              ObjectGenerator        ValidationRule    SVG / Mesh3D / IFC
                              trait registry         trait registry
        ┌──────────────── CATALOG (open, grows, never edits the core) ───────────┐
        wall · floor · roof · door · window · furniture · fixture · freeform · …
        └──────────────────────────────────────────────────────────────────────────┘
```

"Design anything" = the registries are open. You ship scoped to the residential catalog you already have, and new object types are *registrations*, not core changes.

---

## Part 1 — The rendering stack (`Surface` abstraction)

The whole UI is written against one trait. Desktop and kernel each implement it; nothing above the trait knows which it's on.

```rust
/// The only platform-specific seam. Desktop impl wraps winit+softbuffer;
/// kernel impl wraps the framebuffer + SYS_INPUT_POLL syscalls.
pub trait Surface {
    fn size(&self) -> (u32, u32);
    /// ARGB8888 (or platform-native) pixel buffer for this frame.
    fn pixels_mut(&mut self) -> &mut [u32];
    /// Push the buffer to the display.
    fn present(&mut self);
    /// Drain input since the last call.
    fn poll_input(&mut self) -> Vec<InputEvent>;
}

pub enum InputEvent {
    PointerMove { x: f32, y: f32 },
    PointerDown { x: f32, y: f32, button: Button },
    PointerUp   { x: f32, y: f32, button: Button },
    Key         { code: KeyCode, pressed: bool, mods: Modifiers },
    Scroll      { dx: f32, dy: f32 },
    Resize      { w: u32, h: u32 },
}
```

Everything above draws with `tiny-skia::Pixmap` (backed by `pixels_mut()`) and `fontdue` for glyphs. Crates:

| Crate | Version | License | Role |
|---|---|---|---|
| `winit` | 0.30 | Apache/MIT | desktop window + events (desktop `Surface` only) |
| `softbuffer` | 0.4 | Apache/MIT | CPU framebuffer present (desktop `Surface` only) |
| `tiny-skia` | 0.11 | BSD-3 | 2D path/fill/stroke rasterization (shared) |
| `fontdue` | 0.9 | MIT/Apache | glyph rasterization (shared) |

**Crate layout (new):**
```
rust/crates/
├── surface/        # Surface trait + InputEvent. no platform deps.
├── surface-winit/  # desktop impl (winit + softbuffer). desktop-only.
├── ui/             # immediate-mode widgets on tiny-skia + fontdue (shared)
└── app/            # binary: wires Surface + ui + qbd/drawing pipeline
```
The kernel later adds `surface-kernel/` and swaps it in `app`. `ui/`, `drawing/`, `qbd/` are untouched.

**Immediate-mode UI** — minimal, hand-rolled (no egui, since egui needs wgpu/glow). Core loop:
```rust
loop {
    let input = surface.poll_input();
    let mut pixmap = pixmap_over(surface.pixels_mut(), w, h);
    let mut ui = Ui::new(&mut pixmap, &input, &font);
    app.update(&mut ui);   // panels, buttons, sketch canvas — all draw immediately
    surface.present();
}
```

---

## Part 2 — The object-generation pipeline

### Core types (new crate `objects/`)

```rust
/// Anything the system can place + draw. Domain-agnostic.
pub struct Object {
    pub id: ObjectId,
    pub kind: String,              // "wall", "furniture", "freeform", …
    pub params: ParamMap,          // type-specific parameters
    pub constraints: Vec<Constraint>,
    pub placement: Option<Placement>,  // filled by the solver
}

pub enum Constraint {
    InsideRegion(RegionId),        // from a sketched boundary
    AdjacentTo(ObjectId, Side),
    AlignedWith(ObjectId, Axis),
    OffsetFrom(ObjectId, f32),
    FixedAt(Placement),            // freeform / hand-placed
    CodeRule(String),              // e.g. "OBC.9.5.5.2" min egress width
}
```

### The two open registries

```rust
/// Turns (params + resolved placement) into drawable/3D geometry.
/// The 4 existing generators (wall/floor/roof/opening) become impls.
pub trait ObjectGenerator {
    fn kind(&self) -> &str;
    fn generate(&self, obj: &Object, ctx: &SceneContext) -> GeneratedGeometry;
}

/// Domain rules. OBC today; generic over object kind.
pub trait ValidationRule {
    fn applies_to(&self, kind: &str) -> bool;
    fn check(&self, obj: &Object, scene: &Scene) -> Vec<Violation>;
}

pub struct Registry {
    generators: HashMap<String, Box<dyn ObjectGenerator>>,
    validators: Vec<Box<dyn ValidationRule>>,
}
```

Adding a new object type = `registry.register(Box::new(MyGenerator))`. Zero core edits. That is the entire "design anything" claim, made concrete.

### Hybrid sketch pad → objects

A stroke resolves into one of two things, user-selectable (the "hybrid"):
- **Constraint mode:** stroke → `RegionId` boundary, guide line, or a `FixedAt`/`InsideRegion` constraint fed to the solver. The solver still produces the geometry. (Pivot-consistent: inputs → drawings.)
- **Freeform mode:** stroke → an `Object { kind: "freeform", … }` with a polygon/profile param and a `FixedAt` placement. It IS the geometry. (v2-editor direction.)

Both land in the same `ConstraintGraph`; the solver treats fixed objects as hard placements and solves the rest around them.

---

## Part 3 — Increment ladder (spine before breadth)

Each increment ships something runnable. Breadth is last.

### Increment 1 — Desktop shell renders the existing bundle
- New crates `surface`, `surface-winit`, `ui`, `app`.
- `app` runs the existing `qbd::generate_documentation`, rasterizes the resulting SVG into the window via tiny-skia (parse the SVG we already emit, or render from the `SliceResult`/primitives directly — prefer the latter to avoid an SVG re-parse).
- **Acceptance:** `cargo run -p app` opens a window showing the floor plan of a fixture, pan/zoom works, no Python, no GPU.

### Increment 2 — `ObjectGenerator` trait + registry
- Define `objects/` crate: `Object`, `Constraint`, `ObjectGenerator`, `Registry`.
- Refactor `wall_geometry`/`floor_geometry`/`roof_geometry`/`opening_geometry` to impl `ObjectGenerator`.
- `qbd::generate_documentation` drives the registry instead of calling generators directly.
- **Acceptance:** identical SVG output to today (m5_diff still PASS), but generation goes through the registry. Proves the catalog pattern with zero new types.

### Increment 3 — Sketch pad (constraint mode)
- `ui` gains a canvas widget: capture pointer drags into strokes.
- Strokes → `Constraint::InsideRegion` / boundary fed to the existing room solver.
- **Acceptance:** draw a lot boundary in the window, solver lays rooms inside it, floor plan re-renders live.

### Increment 4 — Port the Python solver to Rust
- Port `qbd_layout_generator.py` + `qbd/` suite (~8000 LOC) into a `solver` crate.
- Regression oracle: Rust solver output validates against `qbd_output.schema.json` AND matches the Python solver on the smoke corpus (extend `m5_diff.py`).
- **Acceptance:** pure-Rust answers → permit bundle, no Python anywhere in the path.

### Increment 5 — Freeform objects + new catalog types
- Sketch pad freeform mode → `Object { kind: "freeform" }`.
- First non-building catalog type (furniture via the existing TripoSR abstraction, or a parametric fixture) registered.
- **Acceptance:** place a non-wall object from the sketch pad; it generates + draws through the same pipeline. "Design anything" is now incremental.

---

## Risks / open questions

- **Hand-rolled immediate-mode UI is real work.** No egui means we build text fields, buttons, panels, scroll on tiny-skia ourselves. Mitigated by it being kernel-mandatory work anyway. If desktop velocity matters more than kernel-readiness short-term, egui-on-glow is the escape hatch — but it's the throwaway path.
- **Solver port (increment 4) is the largest single item** and gates "full Rust." Until it lands, the head is Rust but the brain is Python (acceptable interim: `app` shells out to the Python solver, like smoke_test `--use-rust` does in reverse).
- **"Design anything" validation.** OBC rules are residential-building-specific. A general object catalog needs either per-domain rule sets or an explicit "unvalidated" mode for non-building objects. Decide per catalog type.
- **SVG-in-window: re-parse vs direct render.** Rendering from `SliceResult`/primitives directly (not re-parsing emitted SVG) is cleaner and faster — recommend that, treat SVG as an export format only.

---

*Written 2026-05-16. Decisions per owner direction this session; recorded in memory `project_ui_rendering_direction` + `project_full_rust_head_scope`.*
