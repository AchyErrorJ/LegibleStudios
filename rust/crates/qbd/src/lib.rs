//! QBD layout ingest, building conversion, validation + documentation orchestration.
//!
//! Port of `ArchEngine_kernel/{include,src}/qbd_interface.{hpp,cpp}`.
//! Single JSON parse path via `archgeometry::schema_parser` (§8 — the
//! C++'s parallel parse paths are collapsed in the Rust port).
