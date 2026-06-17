//! OBC Part 3 commercial / mid-rise / mixed-use rules engine.

pub mod egress;
pub mod engine;
pub mod fire_separation;
pub mod occupancy;
pub mod stairs;
pub mod tables;

pub use engine::{FloorInput, Part3Engine, RoomInput};
pub use stairs::StairInput;
pub use tables::MajorOccupancy;
