# Full-Rust Head — Legible Studio (consumer view)

**Date:** 2026-05-16
**Status:** Design. Decisions locked (see below); no code yet.
**Supersedes scope in:** `RUST_PORT_ROADMAP.md` §2 (which assumed headless + deferred UI). The UI is now in scope, bare-metal, and the product scope broadened to general object generation.

> **This doc is the Legible-Studio-specific view.** The domain-neutral object model, primitive
> library, CSG, registry traits, and the `Surface` seam live in the **shared `parametric-kernel`**
> — see `docs/PARAMETRIC_KERNEL_SPEC.md`. That kernel is consumed by Legible Studio *and* Mech Arena
> (and future Semantic OS apps) so we build it once. This doc covers only what Legible adds on top:
> its catalog, its OBC validators, its 2D drawing pipeline, its room solver, and its app shell.

## Decisions locked (owner, 2026-05-16)

1. **Rendering: bare-metal software, not wgpu, not Tauri/webview.** `winit` + `softbuffer` + `tiny-skia` + `fontdue` + a hand-rolled immediate-mode UI. Chosen so the draw layer is identical on desktop and the Semantic OS kernel.
2. **Sketch pad: hybrid.** Strokes are both solver *constraints* and freeform *geometry objects* you can edit. This is the input/editing surface for the v2 in-app editor already in progress.
3. **Scope: "design anything."** General object generation via a flexible mechanism + scoped, growable catalog. Not residential-permit-only.
4. **Full Rust.** Drop Python (incl. the still-Python solver) and the webview option. Keep foundational crates (glam/serde/thiserror/anyhow/bytemuck).

## Guiding principle: separate mechanism from catalog

The **mechanism** is the shared `parametric-kernel` (see `PARAMETRIC_KERNEL_SPEC.md`). The **catalog**
is what Legible registers against it. Same factoring the Mech Arena project independently arrived at —
that cross-product agreement is why the kernel is extracted, not duplicated.

```
        ┌──────── parametric-kernel (SHARED — see PARAMETRIC_KERNEL_SPEC.md) ────────┐
input → ConstraintGraph → Solver hook → resolve → ObjectGenerator → Mesh/2D → ValidationRule
        └────────────────────────────────────────────────────────────────────────────┘
                                  ▲                    ▲                 ▲
                       Legible's room Solver   Legible's catalog   Legible's OBC rules
                       (impl Solver)           (impl ObjectGenerator)  (impl ValidationRule)
        ┌──────── Legible catalog (registered, grows, never edits the kernel) ───────┐
        wall · floor · roof · door · window · furniture · fixture · freeform · …
        └──────────────────────────────────────────────────────────────────────────────┘
```

"Design anything" = the kernel's registries are open. Legible ships scoped to its residential catalog
and adds new object types as *registrations*, never kernel edits.

---

## Part 1 — Rendering: consume `pk-surface`, draw with tiny-skia

The `Surface` trait + `InputEvent` + the desktop `winit`+`softbuffer` impl live in the kernel
(`pk-surface` / `pk-surface-winit`). Legible doesn't define them — it consumes them. See
`PARAMETRIC_KERNEL_SPEC.md` §2 for the trait.

What's **Legible-specific** on top of the surface:

- **2D rasterization** with `tiny-skia` 0.11 (`Pixmap` backed by `surface.pixels_mut()`) + `fontdue` 0.9 for glyphs. (Mech draws 3D into the same surface via its own renderer — that part is not shared.)
- **A hand-rolled immediate-mode UI** for Legible's panels/canvas (no egui — egui needs wgpu/glow). Core loop:

```rust
loop {
    let input = surface.poll_input();         // pk-surface
    let mut pixmap = pixmap_over(surface.pixels_mut(), w, h);  // tiny-skia
    let mut ui = Ui::new(&mut pixmap, &input, &font);          // Legible UI
    app.update(&mut ui);   // questionnaire, sketch canvas, live preview — draw immediately
    surface.present();     // pk-surface
}
```

**Legible crate layout** (consumes the kernel):
```
LegibleStudios/rust/crates/
├── (depends on) pk-geom, pk-primitives, pk-csg, pk-object, pk-surface, pk-surface-winit
├── catalog/        # Legible's ObjectGenerator impls (wall/floor/roof/opening/freeform)
├── obc/            # OBC ValidationRule impls (exists today as ls-obc)
├── solver/         # Legible's room-layout Solver impl (the Python port lands here)
├── drawing/        # 2D permit sheets — site/elevation/section/dims/title (exists, ls-drawing)
├── ui/             # Legible's immediate-mode widgets on tiny-skia
└── app/            # binary: pk-surface + ui + catalog + drawing + solver
```
The kernel later ships `pk-surface-kernel`; `app` swaps it for `pk-surface-winit`. Everything else is untouched.

---

## Part 2 — The object pipeline (kernel) and Legible's catalog

The object model — `Object`, `Constraint`, `Hardpoint`, `ObjectGenerator`/`ValidationRule`/`Solver`
traits, `Registry` — is **all in `pk-object`** (see `PARAMETRIC_KERNEL_SPEC.md` §2). Legible does not
redefine any of it. Legible's job is to **register**:

- **Catalog** — `impl ObjectGenerator` for `wall`, `floor`, `roof`, `opening`, later `freeform`/furniture. The four building generators exist today in `archgeometry`; they get lifted to impl the kernel trait and moved into `catalog/`.
- **Validators** — `impl ValidationRule` for OBC egress/light/corridor + cost. Exists as `ls-obc`.
- **Solver** — `impl Solver` wrapping Legible's room-layout solver (the ~8000-LOC Python port). Mech registers no solver; Legible does. This is the seam that keeps the architectural solver *out* of the shared kernel.

### Hybrid sketch pad → kernel objects

A stroke resolves into one of two things, user-selectable (the "hybrid"), both expressed in kernel types:
- **Constraint mode:** stroke → `Constraint::InsideRegion` / a boundary region fed to Legible's `Solver`. The solver produces the geometry. (Pivot-consistent: inputs → drawings.)
- **Freeform mode:** stroke → `Object { kind: "freeform", params: { profile }, constraints: [FixedAt(..)] }`. It IS the geometry. (v2-editor direction.)

Both land in the same kernel `Scene`; the kernel resolves `FixedAt`/`AttachedTo` directly and hands the rest to Legible's `Solver`.

---

## Part 3 — Increment ladder (spine before breadth)

Each increment ships something runnable. Breadth is last.

### Increment 0 — Stand up the shared `parametric-kernel` repo
- New repo (working name `parametric-kernel`). Extract from Legible's existing crates per `PARAMETRIC_KERNEL_SPEC.md` §5: `pk-geom` ← archgeometry geometry types, `pk-csg` ← `csg` (verbatim), `pk-primitives` ← `mesh-gen` + add capsule/wedge/sphere, then new `pk-object` + `pk-surface`.
- Legible adds the kernel as a path dependency and swaps its local `csg`/`mesh-gen`/geom types for the kernel crates.
- **Acceptance:** `cargo test` across Legible still green (m1/m4/m5 oracles PASS) with geometry now coming from the shared kernel. Mech Arena agent can `cargo add` the kernel and call `pk-primitives::capsule(...)`.

### Increment 1 — Desktop shell renders the existing bundle
- New Legible crates `ui`, `app`; depend on `pk-surface` + `pk-surface-winit`.
- `app` runs `qbd::generate_documentation`, renders the result into the window via tiny-skia — render from `SliceResult`/primitives directly, **not** by re-parsing emitted SVG (treat SVG as export only).
- **Acceptance:** `cargo run -p app` opens a window showing a fixture's floor plan, pan/zoom works, no Python, no GPU.

### Increment 2 — Register Legible's catalog against the kernel
- Lift `wall`/`floor`/`roof`/`opening` generators to `impl pk_object::ObjectGenerator`; move into `catalog/`.
- `qbd::generate_documentation` drives `pk_object::Registry` instead of calling generators directly.
- **Acceptance:** identical drawing output to today (m5_diff still PASS), but generation flows through the kernel registry. Proves the catalog pattern with zero new types — and proves the kernel API is right (Mech registers its catalog the same way).

### Increment 3 — Sketch pad (constraint mode)
- `ui` gains a canvas widget: pointer drags → strokes → `pk_object::Constraint::InsideRegion`/boundary fed to Legible's `Solver`.
- **Acceptance:** draw a lot boundary in the window, room solver lays rooms inside it, floor plan re-renders live.

### Increment 4 — Port the Python solver to Rust (as a `Solver` impl)
- Port `qbd_layout_generator.py` + `qbd/` suite (~8000 LOC) into Legible's `solver/` crate as `impl pk_object::Solver`.
- Regression oracle: Rust solver output validates against `qbd_output.schema.json` AND matches the Python solver on the smoke corpus (extend `m5_diff.py`).
- **Acceptance:** pure-Rust answers → permit bundle, no Python anywhere in the path.

### Increment 5 — Freeform objects + new catalog types
- Sketch pad freeform mode → `Object { kind: "freeform" }` (kernel type).
- First non-building catalog type (furniture via the existing TripoSR abstraction, or a parametric fixture) registered.
- **Acceptance:** place a non-wall object from the sketch pad; it generates + draws through the same pipeline. "Design anything" is now incremental — and the kernel is proven across two domains (Legible + Mech).

---

## Risks / open questions

- **Hand-rolled immediate-mode UI is real work.** No egui means we build text fields, buttons, panels, scroll on tiny-skia ourselves. Mitigated by it being kernel-mandatory work anyway. If desktop velocity matters more than kernel-readiness short-term, egui-on-glow is the escape hatch — but it's the throwaway path.
- **Solver port (increment 4) is the largest single item** and gates "full Rust." Until it lands, the head is Rust but the brain is Python (acceptable interim: `app` shells out to the Python solver, like smoke_test `--use-rust` does in reverse).
- **"Design anything" validation.** OBC rules are residential-building-specific. A general object catalog needs either per-domain rule sets or an explicit "unvalidated" mode for non-building objects. Decide per catalog type.
- **SVG-in-window: re-parse vs direct render.** Rendering from `SliceResult`/primitives directly (not re-parsing emitted SVG) is cleaner and faster — recommend that, treat SVG as an export format only.
- **Cross-repo coordination (kernel).** The shared `parametric-kernel` is consumed by Legible *and* Mech (and the Mech `MechCore` should be Rust-from-start, not C++-then-M17, to share it via FFI to UE5). Risk: API churn breaking a consumer. Mitigation: path deps during co-dev, pin git tags once stable; keep the kernel scoped to what the two real consumers need (see `PARAMETRIC_KERNEL_SPEC.md` §0 — no speculative generalization).

---

*Written 2026-05-16. Legible-Studio consumer view of the shared `parametric-kernel` (`PARAMETRIC_KERNEL_SPEC.md`). Decisions per owner direction this session; recorded in memory `project_ui_rendering_direction` + `project_full_rust_head_scope`.*
