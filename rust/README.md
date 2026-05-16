# Legible Studio — Rust

Rust port of the C++ ArchEngine geometry kernel. Critical path for permit-drawing generation.

See `../docs/VULKAN_KERNEL_PORT_PLAN.md` for the full port plan, milestones (M1–M6),
and per-crate scope.

## Layout

```
crates/
├── domain/           # Semantic types (StructuralElement, Building, color palettes, …)
├── archgeometry/     # Schema types + parser + geometry generators (port of Shared/ArchGeometry)
├── csg/              # BSP CSG: union / intersection / difference
├── bvh/              # SAH BVH builder (CPU; GPU node format moves to renderer crate later)
├── wall-system/      # Parametric walls, corner detection, L-corner adjustment
├── mesh-gen/         # Procedural mesh generators (beam, column, gable roof, …)
├── geometry-loader/  # JSON building loader + sample builders
├── obc/              # Ontario Building Code tables + compliance validation
├── drawing/          # MERGED slicer + plan_generator (slice / annotate / svg / dxf)
├── qbd/              # QBD JSON ingest + orchestration
├── api/              # axum HTTP API (replaces ipc_server)
└── project-migrate/  # bin: one-shot project.json → split-file migration
```

## Status

M1 in progress.

## License

MIT.
