//! Legible Studio's object catalog, registered against the parametric-kernel.
//!
//! This is the consumer side of `pk-object`: Legible's building-element
//! `ObjectGenerator`s and `ValidationRule`s plug into the kernel `Registry`,
//! exactly the way Mech Arena plugs in its part generators. It proves the
//! catalog/registry pattern end-to-end with a real, kernel-typed generator.
//!
//! Scope note: this hosts a **kernel-native** wall generator (params → a
//! world-space box `pk_geom::Mesh`). Migrating archgeometry's richer
//! generators (door/window cutouts, 2D plan output, structural `stress`)
//! into the kernel is a separate follow-up gated on unifying
//! `archgeometry::Mesh3D` with `pk_geom::Mesh` (the `stress`-field
//! decision). The 2D permit-drawing pipeline stays in `ls-drawing`.

use archgeometry::{SchemaDocument, SchemaWall};
use glam::{Vec2, Vec3};
use pk_geom::Mesh;
use pk_object::{
    GenContext, GeneratedGeometry, Object, ObjectGenerator, Registry, Scene, Severity, ValidationRule,
    Violation,
};

/// JSON key under which a wall `Object` carries its `SchemaWall`.
const WALL_PARAM: &str = "wall";

/// Default exterior/interior wall thickness in mm (mirrors archgeometry's
/// 150 mm default wall type).
const DEFAULT_THICKNESS: f32 = 150.0;

/// Wrap a `SchemaWall` as a kernel `Object` of kind `"wall"`.
#[must_use]
pub fn wall_object(id: u64, wall: &SchemaWall) -> Object {
    let value = serde_json::to_value(wall).unwrap_or(serde_json::Value::Null);
    Object::new(id, "wall").with_param(WALL_PARAM, value)
}

/// Build a kernel `Scene` from a parsed schema document's walls.
#[must_use]
pub fn scene_from_schema(doc: &SchemaDocument) -> Scene {
    let mut scene = Scene::new();
    for (i, wall) in doc.walls.iter().enumerate() {
        scene.add(wall_object(i as u64, wall));
    }
    scene
}

/// A registry wired with Legible's building catalog + rules.
#[must_use]
pub fn building_registry() -> Registry {
    let mut r = Registry::new();
    r.register_generator(Box::new(WallGenerator));
    r.register_validator(Box::new(WallLengthRule));
    r
}

/// Generates a wall as a 6-face box in **world space** (built directly from
/// the wall's start/end, so no object transform is needed). Winding +
/// per-category colour mirror archgeometry's `solid_mesh` so the shape is
/// the canonical Legible wall.
pub struct WallGenerator;

impl ObjectGenerator for WallGenerator {
    #[allow(clippy::unnecessary_literal_bound)] // trait sig is `-> &str`; we return a literal
    fn kind(&self) -> &str {
        "wall"
    }

    fn generate(&self, obj: &Object, _ctx: &GenContext) -> GeneratedGeometry {
        let Some(wall) = wall_from(obj) else {
            return GeneratedGeometry::default();
        };
        let color = category_color(&wall.category);
        let mesh = wall_box(wall.start, wall.end, wall.height, DEFAULT_THICKNESS, color);
        GeneratedGeometry { mesh: Some(mesh) }
    }
}

/// Flags degenerate (near-zero-length) walls.
pub struct WallLengthRule;

impl ValidationRule for WallLengthRule {
    fn applies_to(&self, kind: &str) -> bool {
        kind == "wall"
    }
    fn check(&self, obj: &Object, _scene: &Scene) -> Vec<Violation> {
        let Some(wall) = wall_from(obj) else {
            return Vec::new();
        };
        let len = (wall.end - wall.start).length();
        if len < 1.0 {
            vec![Violation {
                object: obj.id,
                rule: "catalog.wall_length".into(),
                message: format!("degenerate wall: length {len:.2} mm"),
                severity: Severity::Critical,
            }]
        } else {
            Vec::new()
        }
    }
}

fn wall_from(obj: &Object) -> Option<SchemaWall> {
    obj.params
        .get(WALL_PARAM)
        .and_then(|v| serde_json::from_value(v.clone()).ok())
}

fn category_color(category: &str) -> Vec3 {
    match category {
        "exterior" => Vec3::new(0.85, 0.85, 0.8),
        "wet_wall" => Vec3::new(0.7, 0.85, 0.9),
        _ => Vec3::new(0.9, 0.9, 0.88),
    }
}

/// Six-face box from `start` to `end` (in the XZ plane), `height` along Y,
/// `thickness` perpendicular. Returns an empty mesh for a zero-length wall.
fn wall_box(start: Vec3, end: Vec3, height: f32, thickness: f32, color: Vec3) -> Mesh {
    let dir = Vec2::new(end.x - start.x, end.z - start.z);
    let len = dir.length();
    let mut m = Mesh::new();
    if len < 1e-3 {
        return m;
    }
    let d = dir / len;
    let perp = Vec2::new(-d.y, d.x);
    let ht = thickness * 0.5;

    let b0 = Vec3::new(start.x + perp.x * ht, start.y, start.z + perp.y * ht);
    let b1 = Vec3::new(start.x - perp.x * ht, start.y, start.z - perp.y * ht);
    let b2 = Vec3::new(end.x - perp.x * ht, start.y, end.z - perp.y * ht);
    let b3 = Vec3::new(end.x + perp.x * ht, start.y, end.z + perp.y * ht);
    let top_y = start.y + height;
    let t0 = Vec3::new(b0.x, top_y, b0.z);
    let t1 = Vec3::new(b1.x, top_y, b1.z);
    let t2 = Vec3::new(b2.x, top_y, b2.z);
    let t3 = Vec3::new(b3.x, top_y, b3.z);

    m.add_quad(b0, t0, t3, b3, Vec3::new(perp.x, 0.0, perp.y), color); // front
    m.add_quad(b1, b2, t2, t1, Vec3::new(-perp.x, 0.0, -perp.y), color); // back
    m.add_quad(b0, b1, t1, t0, Vec3::new(-d.x, 0.0, -d.y), color); // left end
    m.add_quad(b3, t3, t2, b2, Vec3::new(d.x, 0.0, d.y), color); // right end
    m.add_quad(t0, t1, t2, t3, Vec3::new(0.0, 1.0, 0.0), color); // top
    m.add_quad(b0, b3, b2, b1, Vec3::new(0.0, -1.0, 0.0), color); // bottom
    m
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rect_walls() -> Vec<SchemaWall> {
        [
            ((0.0, 0.0), (5000.0, 0.0)),
            ((5000.0, 0.0), (5000.0, 4000.0)),
            ((5000.0, 4000.0), (0.0, 4000.0)),
            ((0.0, 4000.0), (0.0, 0.0)),
        ]
        .into_iter()
        .map(|((sx, sz), (ex, ez))| SchemaWall {
            start: Vec3::new(sx, 0.0, sz),
            end: Vec3::new(ex, 0.0, ez),
            height: 2700.0,
            category: "exterior".into(),
            ..Default::default()
        })
        .collect()
    }

    fn scene_of(walls: &[SchemaWall]) -> Scene {
        let mut s = Scene::new();
        for (i, w) in walls.iter().enumerate() {
            s.add(wall_object(i as u64, w));
        }
        s
    }

    #[test]
    fn registry_builds_one_box_mesh_per_wall() {
        let walls = rect_walls();
        let mut scene = scene_of(&walls);
        let geo = building_registry().build(&mut scene);
        assert_eq!(geo.per_object.len(), 4);
        for (_, g) in &geo.per_object {
            let m = g.mesh.as_ref().unwrap();
            assert_eq!(m.vertex_count(), 24); // 6 faces * 4
            assert_eq!(m.triangle_count(), 12);
        }
        let merged = geo.merged();
        assert_eq!(merged.vertex_count(), 96);
        assert_eq!(merged.triangle_count(), 48);
    }

    #[test]
    fn wall_mesh_is_world_placed_from_start_end() {
        let walls = vec![SchemaWall {
            start: Vec3::new(0.0, 0.0, 0.0),
            end: Vec3::new(5000.0, 0.0, 0.0),
            height: 2700.0,
            category: "exterior".into(),
            ..Default::default()
        }];
        let mut scene = scene_of(&walls);
        let geo = building_registry().build(&mut scene);
        let bb = geo.merged().aabb();
        // Spans the wall length in X, thickness in Z, height in Y.
        assert!((bb.size().x - 5000.0).abs() < 1.0);
        assert!((bb.size().y - 2700.0).abs() < 1.0);
        assert!((bb.size().z - DEFAULT_THICKNESS).abs() < 1.0);
    }

    #[test]
    fn validator_flags_degenerate_wall() {
        let walls = vec![SchemaWall {
            start: Vec3::ZERO,
            end: Vec3::ZERO,
            height: 2700.0,
            category: "interior".into(),
            ..Default::default()
        }];
        let scene = scene_of(&walls);
        let v = building_registry().validate(&scene);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0].rule, "catalog.wall_length");
        assert_eq!(v[0].severity, Severity::Critical);
    }

    #[test]
    fn scene_from_schema_makes_one_object_per_wall() {
        let mut doc = SchemaDocument::default();
        doc.walls = rect_walls();
        let scene = scene_from_schema(&doc);
        assert_eq!(scene.objects.len(), 4);
        assert!(scene.objects.iter().all(|o| o.kind == "wall"));
    }
}
