# Parametric Kernel — shared library spec

**Status:** Design, locked. Working name `parametric-kernel` (crate prefix `pk-`) — **rename before first commit** if you have a better one.
**Audience:** Any agent building a parametric design/generation app for the Semantic OS family — Legible Studio (CAD/permit), Mech Arena (game/editor), MarlOS, future apps.
**Purpose:** One shared Rust library that turns *parametric object specs → geometry*, so consumers don't each reimplement primitives, CSG, the object model, and the platform surface. **Reference this; don't duplicate it.**

---

## 0. The one rule

The kernel is **domain-neutral and render-neutral.** It knows nothing about buildings, mechs, OBC codes, combat, or how pixels reach a screen. It only knows: *spec → objects → geometry → (optional) validation*.

Extraction is driven by **real consumers only** (today: Legible Studio + Mech Arena). Do not add a capability "because it could generalize." Two concrete consumers shaping the API = healthy. Anticipating a hypothetical third = the foundational-reach trap. If a feature is needed by exactly one consumer, it lives in that consumer, not here.

---

## 1. What's in the kernel vs what's yours

```
┌──────────────────────── PARAMETRIC KERNEL (shared) ────────────────────────┐
│ pk-geom        Mesh, Vertex, Triangle, Aabb, Transform (glam-based)         │
│ pk-primitives  capsule · rounded_box · cone/frustum · wedge · cylinder ·    │
│                sphere → triangle meshes                                      │
│ pk-csg         BSP union / intersection / difference                        │
│ pk-object      Object, Constraint, Hardpoint, Registry,                     │
│                ObjectGenerator + ValidationRule + Solver traits             │
│ pk-surface     Surface trait + InputEvent (framebuffer + input seam)        │
│ pk-surface-winit  desktop Surface impl (winit + softbuffer) — optional      │
└──────────────────────────────────────────────────────────────────────────────┘
        ▲                              ▲                          ▲
   YOUR CATALOG                  YOUR DOMAIN RULES          YOUR RENDERER
   (ObjectGenerator impls)       (ValidationRule impls)     (you draw the geometry)
   walls/doors (Legible)         OBC/cost (Legible)          tiny-skia 2D (Legible)
   capsule-parts (Mech)          mass/hardpoint (Mech)       Iris Xe / UE5 3D (Mech)
```

**The kernel never:** renders, knows your domain, runs your physics/combat, or owns your app loop.
**You always:** register generators for your object kinds, register validators for your rules, pick a renderer, own your app loop.

---

## 2. Crate APIs (build against these)

### `pk-geom`
```rust
pub struct Vertex { pub position: Vec3, pub normal: Vec3, pub color: Vec3, pub uv: Vec2 }
pub struct Triangle(pub u32, pub u32, pub u32);

pub struct Mesh { pub vertices: Vec<Vertex>, pub faces: Vec<Triangle> }
impl Mesh {
    pub fn add_quad(&mut self, p0: Vec3, p1: Vec3, p2: Vec3, p3: Vec3, n: Vec3, c: Vec3);
    pub fn add_triangle(&mut self, p0: Vec3, p1: Vec3, p2: Vec3, n: Vec3, c: Vec3);
    pub fn merge(&mut self, other: &Mesh);     // offsets indices
    pub fn aabb(&self) -> Aabb;
}

pub struct Aabb { pub min: Vec3, pub max: Vec3 }
pub struct Transform { pub translation: Vec3, pub rotation: Quat, pub scale: Vec3 }
impl Transform { pub fn identity() -> Self; pub fn apply(&self, p: Vec3) -> Vec3; pub fn to_mat4(&self) -> Mat4; }
```
*Note:* this is Legible's existing `geometry_types::Mesh3D`/`Vertex3D`/`Triangle` generalized. Legible's `archgeometry` keeps its 2D `Geometry2D` types locally (2D drawing is Legible-specific).

### `pk-primitives`
```rust
pub fn capsule(radius: f32, length: f32, segments: u32) -> Mesh;
pub fn rounded_box(dims: Vec3, chamfer: f32) -> Mesh;
pub fn cone(base_r: f32, top_r: f32, height: f32, segments: u32) -> Mesh;  // frustum when top_r > 0
pub fn wedge(dims: Vec3, angle_deg: f32) -> Mesh;
pub fn cylinder(radius: f32, height: f32, segments: u32) -> Mesh;
pub fn sphere(radius: f32, segments: u32) -> Mesh;
```
The Mech palette (capsule/box/cone/wedge/cylinder/sphere) is the full set. Legible's existing `mesh-gen` beam/column/floor/gable-roof are domain compositions that can move into Legible's catalog OR stay as derived helpers — TBD when extracting.

### `pk-csg`
```rust
pub fn mesh_union(a: &Mesh, b: &Mesh) -> Mesh;
pub fn mesh_intersection(a: &Mesh, b: &Mesh) -> Mesh;
pub fn mesh_difference(a: &Mesh, b: &Mesh) -> Mesh;
```
*Already implemented* — this is Legible's `csg` crate (BSP, csg.js semantics) moved out verbatim. Mech's spec deferred CSG; it gets it for free.

### `pk-object` — the heart
```rust
pub struct ObjectId(pub u64);
pub type ParamMap = std::collections::BTreeMap<String, serde_json::Value>;

pub struct Object {
    pub id: ObjectId,
    pub kind: String,                 // "wall", "capsule", "freeform", …
    pub params: ParamMap,             // generator-specific
    pub transform: Transform,         // local placement (may be solved/derived)
    pub constraints: Vec<Constraint>,
    pub children: Vec<ObjectId>,      // attachment hierarchy
}

pub struct Hardpoint { pub id: String, pub transform: Transform, pub tags: Vec<String> }

pub enum Constraint {
    FixedAt(Transform),                                  // explicit placement
    AttachedTo { parent: ObjectId, hardpoint: String },  // snap to a parent hardpoint
    InsideRegion(RegionId),                              // for a domain Solver to satisfy
    AdjacentTo { other: ObjectId, side: Side },
    AlignedWith { other: ObjectId, axis: Axis },
    OffsetFrom  { other: ObjectId, distance: f32 },
    Custom(String),                                      // opaque to the kernel; your Solver handles it
}

pub struct GeneratedGeometry {
    pub mesh: Option<Mesh>,           // 3D consumers (Mech viewport, Legible verification view)
    // 2D output stays in the consumer (Legible's Geometry2D) — the kernel is 3D-geometry-neutral.
}

pub trait ObjectGenerator: Send + Sync {
    fn kind(&self) -> &str;
    fn generate(&self, obj: &Object, ctx: &GenContext) -> GeneratedGeometry;
    fn hardpoints(&self, obj: &Object) -> Vec<Hardpoint> { Vec::new() }  // default: none
}

pub trait ValidationRule: Send + Sync {
    fn applies_to(&self, kind: &str) -> bool;
    fn check(&self, obj: &Object, scene: &Scene) -> Vec<Violation>;
}

/// Optional hook for domain layout solving. The kernel resolves the
/// EXPLICIT placement graph itself (FixedAt + AttachedTo hardpoints).
/// Anything needing search (InsideRegion, Adjacent/Aligned satisfaction)
/// is handed to a consumer-provided Solver. Mech needs none (parts are
/// FixedAt/AttachedTo). Legible plugs its room-layout solver in here.
pub trait Solver: Send + Sync {
    fn solve(&self, scene: &mut Scene);
}

pub struct Registry { /* generators by kind, validators, optional solver */ }
impl Registry {
    pub fn new() -> Self;
    pub fn register_generator(&mut self, g: Box<dyn ObjectGenerator>);
    pub fn register_validator(&mut self, v: Box<dyn ValidationRule>);
    pub fn set_solver(&mut self, s: Box<dyn Solver>);

    /// 1. run solver (if any) → 2. resolve attachment graph → 3. run generators.
    pub fn build(&self, scene: &mut Scene) -> SceneGeometry;
    pub fn validate(&self, scene: &Scene) -> Vec<Violation>;
}
```

### `pk-surface` — the platform seam
```rust
pub trait Surface {
    fn size(&self) -> (u32, u32);
    fn pixels_mut(&mut self) -> &mut [u32];   // ARGB8888
    fn present(&mut self);
    fn poll_input(&mut self) -> Vec<InputEvent>;
}
pub enum InputEvent {
    PointerMove { x: f32, y: f32 },
    PointerDown { x: f32, y: f32, button: Button },
    PointerUp   { x: f32, y: f32, button: Button },
    Key { code: KeyCode, pressed: bool, mods: Modifiers },
    Scroll { dx: f32, dy: f32 },
    Resize { w: u32, h: u32 },
}
```
`pk-surface-winit` implements `Surface` over `winit` 0.30 + `softbuffer` 0.4 for desktop. The Semantic OS kernel adds `pk-surface-kernel` (framebuffer + `SYS_INPUT_POLL`) later. Consumers that don't draw to a CPU framebuffer (UE5-hosted Mech on Steam) simply don't use `pk-surface` — they only consume the geometry crates.

---

## 3. The consumer contract

To use the kernel, a consuming app:

1. **Registers a catalog** — one `ObjectGenerator` impl per object kind it supports.
   - Legible: `WallGenerator`, `FloorGenerator`, `RoofGenerator`, `OpeningGenerator`, `FreeformGenerator`, …
   - Mech: parts are direct primitives, so a thin `PrimitiveGenerator` wrapping `pk-primitives` + a `FreeformGenerator`. Hardpoints come from the chassis spec.
2. **Registers validators** — `ValidationRule` impls for its domain.
   - Legible: OBC egress/light/cost rules. Mech: mass budget, hardpoint tonnage, part-overlap rules.
3. **Optionally sets a Solver** — only if it has constraints needing search.
   - Legible: room-layout solver (the ~8000-LOC port). Mech: none.
4. **Picks a renderer** — the kernel hands you `SceneGeometry` (meshes + your own 2D); you draw it.
   - Legible: tiny-skia 2D drawing + (later) Vulkan/kernel 3D verification view. Mech: UE5 ProceduralMesh on Steam; Iris Xe driver on the kernel.
5. **Owns its app loop** — kernel has no event loop, no frame timing, no globals.

---

## 4. How to depend on it (no duplication)

The kernel is its **own git repo**. Consumers reference it; nobody copies it.

**During co-development** (all repos checked out under a common parent), use path deps:
```toml
# in each consumer's Cargo.toml
[dependencies]
pk-object     = { path = "../parametric-kernel/crates/pk-object" }
pk-primitives = { path = "../parametric-kernel/crates/pk-primitives" }
pk-csg        = { path = "../parametric-kernel/crates/pk-csg" }
pk-geom       = { path = "../parametric-kernel/crates/pk-geom" }
pk-surface    = { path = "../parametric-kernel/crates/pk-surface" }
```

**For stability** (CI, releases), pin to a git tag:
```toml
pk-object = { git = "https://github.com/<org>/parametric-kernel", tag = "v0.1.0" }
```

Workspace edition 2024, MSRV 1.92 (matches Legible's workspace), `#![forbid(unsafe_code)]` at every crate root, MIT/Apache-2.0 deps only (glam, serde, thiserror — all no_std-friendly for the eventual kernel target).

---

## 5. Bootstrapping the kernel (where the code comes from)

Most of this already exists in Legible Studio's `rust/crates/` — the kernel is largely an **extraction**, not a green-field build:

| Kernel crate | Extract from | State |
|---|---|---|
| `pk-csg` | `LegibleStudios/rust/crates/csg` | done — move verbatim |
| `pk-geom` | `archgeometry::geometry_types` (Mesh3D/Vertex3D/Triangle) | done — generalize names |
| `pk-primitives` | `LegibleStudios/rust/crates/mesh-gen` (`Geometry::` ns) + add capsule/wedge/sphere for Mech | partial — needs the mech palette added |
| `pk-object` | new — but the `ObjectGenerator`/registry pattern is from `FULL_RUST_HEAD_ARCHITECTURE.md` §2 | new |
| `pk-surface` | new — per the Surface design in the architecture doc | new |

Extraction order: `pk-geom` → `pk-csg` → `pk-primitives` → `pk-object` → `pk-surface`. After each, Legible swaps its local crate for the kernel dep and its tests must stay green (the m1/m4/m5 oracles are the safety net).

---

## 6. What is explicitly NOT shared (keep in your repo)

- **Rendering** — tiny-skia 2D (Legible), Iris Xe / UE5 3D (Mech). Only the *geometry* is shared; pixels are yours.
- **Domain logic** — OBC compliance, cost (Legible); combat, physics, waves, scoring, AI (Mech).
- **The layout solver** — Legible's architectural room solver is domain-specific; it plugs in via the `Solver` trait but lives in Legible.
- **2D drawing / permit sheets** — site plan, elevations, sections, dimensions, title blocks: all Legible-specific, stay in `LegibleStudios/rust/crates/drawing`.
- **App shell / UI widgets** — each app's immediate-mode UI is its own (though both may later converge on a shared `pk-ui` *if* a second real consumer needs the exact same widgets — not before).

---

*Written 2026-05-16. Hand this to any agent building a parametric app for the Semantic OS family. When the shared repo is created, this file becomes its README/spec. Companion: Legible's `FULL_RUST_HEAD_ARCHITECTURE.md` (consumer view) and the Mech Arena spec at `X:/ARCH/ETE 26/Games/MECH_ARENA_SPEC.md`.*
