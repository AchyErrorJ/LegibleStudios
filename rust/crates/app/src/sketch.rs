//! Sketch-pad state: a boundary polygon the user draws point-by-point,
//! which becomes a kernel `Region` (constraint input) for the room solver.
//!
//! This is the "constraint mode" of the hybrid sketch pad — the strokes
//! are inputs to the solver, not final geometry. Freeform-object mode is
//! a later increment.

use glam::Vec2;
use pk_object::{Region, RegionId, Scene};

/// A boundary being sketched. Points are in world mm.
#[derive(Debug, Default, Clone)]
pub struct Sketch {
    pub points: Vec<(f32, f32)>,
    pub closed: bool,
}

impl Sketch {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a boundary vertex (ignored once the boundary is closed).
    pub fn add_point(&mut self, x: f32, y: f32) {
        if !self.closed {
            self.points.push((x, y));
        }
    }

    /// Close the boundary if it has at least 3 vertices. Returns whether it closed.
    pub fn close(&mut self) -> bool {
        if self.points.len() >= 3 {
            self.closed = true;
        }
        self.closed
    }

    pub fn clear(&mut self) {
        self.points.clear();
        self.closed = false;
    }

    /// Build a kernel `Scene` carrying this boundary as its sole `Region`.
    /// Empty (no region) until the boundary has 3+ points.
    #[must_use]
    pub fn to_scene(&self) -> Scene {
        let mut scene = Scene::new();
        if self.points.len() >= 3 {
            scene.regions.push(Region {
                id: RegionId(0),
                polygon: self.points.iter().map(|&(x, y)| Vec2::new(x, y)).collect(),
            });
        }
        scene
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use catalog::{room_rect, GridRoomSolver};
    use pk_object::Solver;

    #[test]
    fn add_point_respects_closed() {
        let mut s = Sketch::new();
        s.add_point(0.0, 0.0);
        s.add_point(1.0, 0.0);
        s.add_point(1.0, 1.0);
        assert!(s.close());
        s.add_point(2.0, 2.0); // ignored — closed
        assert_eq!(s.points.len(), 3);
    }

    #[test]
    fn close_needs_three_points() {
        let mut s = Sketch::new();
        s.add_point(0.0, 0.0);
        s.add_point(1.0, 0.0);
        assert!(!s.close());
        assert!(!s.closed);
    }

    #[test]
    fn to_scene_emits_a_region_when_closed_enough() {
        let mut s = Sketch::new();
        assert!(s.to_scene().regions.is_empty());
        for p in [(0.0, 0.0), (6000.0, 0.0), (6000.0, 4000.0), (0.0, 4000.0)] {
            s.add_point(p.0, p.1);
        }
        assert_eq!(s.to_scene().regions.len(), 1);
    }

    #[test]
    fn sketch_to_solver_yields_rooms() {
        // The full Increment-3 loop, headless: boundary → scene → solver → rooms.
        let mut s = Sketch::new();
        for p in [(0.0, 0.0), (6000.0, 0.0), (6000.0, 4000.0), (0.0, 4000.0)] {
            s.add_point(p.0, p.1);
        }
        s.close();
        let mut scene = s.to_scene();
        GridRoomSolver::default().solve(&mut scene);
        let rooms: Vec<_> = scene
            .objects
            .iter()
            .filter(|o| o.kind == "room")
            .filter_map(room_rect)
            .collect();
        assert!(!rooms.is_empty(), "solver produced no rooms from the sketch");
    }
}
