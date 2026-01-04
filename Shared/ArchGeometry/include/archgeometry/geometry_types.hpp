#pragma once
/**
 * @file geometry_types.hpp
 * @brief Output geometry structures for 3D meshes and 2D drawings
 *
 * These types represent the computed geometry that consumers use for
 * rendering (3D) or drawing (2D plans/sections).
 */

#include "schema_types.hpp"
#include <vector>
#include <cstdint>

namespace archgeometry {

//==============================================================================
// 3D Mesh Types
//==============================================================================

/// Vertex for 3D mesh output
struct Vertex3D {
    Vec3 position;
    Vec3 normal;
    Vec3 color = {0.9f, 0.9f, 0.9f};
    Vec2 uv = {0.0f, 0.0f};
    float stress = 0.0f;        ///< For structural visualization
};

/// Triangle face (indices into vertex array)
struct Triangle {
    uint32_t v0, v1, v2;

    Triangle() : v0(0), v1(0), v2(0) {}
    Triangle(uint32_t a, uint32_t b, uint32_t c) : v0(a), v1(b), v2(c) {}
};

/// 3D Mesh output
struct Mesh3D {
    std::vector<Vertex3D> vertices;
    std::vector<Triangle> faces;

    std::string element_id;
    std::string element_type;   ///< "wall", "floor", "roof", "door", "window"
    int lod_hint = 0;           ///< LOD level where this appears

    bool empty() const { return vertices.empty(); }

    /// Get vertex count
    size_t vertexCount() const { return vertices.size(); }

    /// Get triangle/face count
    size_t triangleCount() const { return faces.size(); }

    /// Add a quad (two triangles)
    void addQuad(const Vec3& p0, const Vec3& p1, const Vec3& p2, const Vec3& p3,
                 const Vec3& normal, const Vec3& color = {0.9f, 0.9f, 0.9f}) {
        uint32_t base = static_cast<uint32_t>(vertices.size());

        vertices.push_back({p0, normal, color, {0, 0}});
        vertices.push_back({p1, normal, color, {1, 0}});
        vertices.push_back({p2, normal, color, {1, 1}});
        vertices.push_back({p3, normal, color, {0, 1}});

        faces.push_back({base, base + 1, base + 2});
        faces.push_back({base, base + 2, base + 3});
    }

    /// Add a triangle
    void addTriangle(const Vec3& p0, const Vec3& p1, const Vec3& p2,
                     const Vec3& normal, const Vec3& color = {0.9f, 0.9f, 0.9f}) {
        uint32_t base = static_cast<uint32_t>(vertices.size());

        vertices.push_back({p0, normal, color, {0, 0}});
        vertices.push_back({p1, normal, color, {1, 0}});
        vertices.push_back({p2, normal, color, {0.5f, 1}});

        faces.push_back({base, base + 1, base + 2});
    }

    /// Merge another mesh into this one
    void merge(const Mesh3D& other) {
        uint32_t offset = static_cast<uint32_t>(vertices.size());
        vertices.insert(vertices.end(), other.vertices.begin(), other.vertices.end());
        for (const auto& face : other.faces) {
            faces.push_back({face.v0 + offset, face.v1 + offset, face.v2 + offset});
        }
    }
};

//==============================================================================
// 2D Geometry Types (for plan views)
//==============================================================================

/// 2D line segment
struct Line2D {
    Point2D start;
    Point2D end;
    std::string layer = "default";      ///< CAD layer
    std::string line_type = "continuous"; ///< "continuous", "dashed", "hidden"
    float line_weight = 0.25f;          ///< Line weight in mm
};

/// 2D polygon (closed shape)
struct Polygon2D {
    std::vector<Point2D> points;
    bool closed = true;
    std::string layer = "default";
    std::string fill_pattern;           ///< For hatching (empty = no fill)
    std::array<float, 4> fill_color = {1, 1, 1, 1};
};

/// 2D arc
struct Arc2D {
    Point2D center;
    float radius;
    float start_angle = 0.0f;           ///< Radians
    float end_angle = 6.283185f;        ///< Radians (2*PI = full circle)
    std::string layer = "default";
};

/// 2D text annotation
struct Text2D {
    Point2D position;
    std::string text;
    float height = 100.0f;              ///< Text height in mm
    float font_size = 100.0f;           ///< Alias for height (font size in mm)
    float rotation = 0.0f;              ///< Rotation in radians
    std::string layer = "annotation";
    std::string anchor = "middle";      ///< "left", "middle", "right"
    std::string alignment = "center";   ///< "left", "center", "right"
};

/// Collection of 2D geometry
struct Geometry2D {
    std::vector<Line2D> lines;
    std::vector<Polygon2D> polygons;
    std::vector<Arc2D> arcs;
    std::vector<Text2D> texts;

    std::string element_id;
    std::string element_type;
    int lod_hint = 0;

    bool empty() const {
        return lines.empty() && polygons.empty() && arcs.empty() && texts.empty();
    }

    void merge(const Geometry2D& other) {
        lines.insert(lines.end(), other.lines.begin(), other.lines.end());
        polygons.insert(polygons.end(), other.polygons.begin(), other.polygons.end());
        arcs.insert(arcs.end(), other.arcs.begin(), other.arcs.end());
        texts.insert(texts.end(), other.texts.begin(), other.texts.end());
    }
};

//==============================================================================
// Element Geometry Results
//==============================================================================

/// Cutout rectangle for door/window openings
struct OpeningCutout {
    float start_offset;         ///< Distance along wall from start
    float bottom_height;        ///< Height from floor (0 for doors)
    float width;
    float height;
    std::string opening_type;   ///< "door" or "window"
    int opening_index;          ///< Index into doors/windows array
};

/// Wall geometry result
struct WallGeometry {
    Mesh3D mesh_3d;
    Geometry2D plan_view;       ///< Floor plan representation
    Geometry2D section_view;    ///< Section cut representation
    std::vector<OpeningCutout> cutouts;

    std::string wall_id;
    int wall_index = -1;
};

/// Floor geometry result
struct FloorGeometry {
    Mesh3D mesh_3d;
    Geometry2D plan_view;

    std::string floor_id;
    std::string room_id;            ///< Room this floor belongs to (optional)
    int floor_index = -1;
};

/// Roof geometry result
struct RoofGeometry {
    Mesh3D mesh_3d;
    Geometry2D plan_view;       ///< Roof plan with ridge/hip lines

    std::vector<Line2D> ridge_lines;
    std::vector<Line2D> hip_lines;
    std::vector<Line2D> eave_lines;
    std::vector<Line2D> rake_lines;

    std::string roof_id;
    int roof_index = -1;
};

/// Door geometry result
struct DoorGeometry {
    Mesh3D mesh_3d;             ///< Combined 3D mesh
    Mesh3D frame_mesh;          ///< Door frame mesh
    Mesh3D panel_mesh;          ///< Door panel mesh
    Geometry2D plan_symbol;     ///< Door symbol for floor plan (swing arc, etc.)

    OpeningCutout cutout;       ///< Cutout info for parent wall
    std::string door_id;
    std::string door_type;      ///< Door type (swing, pocket, etc.)
    int door_index = -1;
};

/// Window geometry result
struct WindowGeometry {
    Mesh3D mesh_3d;             ///< Combined 3D mesh
    Mesh3D frame_mesh;          ///< Window frame mesh
    Mesh3D glass_mesh;          ///< Window glass mesh
    Geometry2D plan_symbol;     ///< Window symbol for floor plan

    OpeningCutout cutout;       ///< Cutout info for parent wall
    std::string window_id;
    std::string window_type;    ///< Window type (casement, double-hung, etc.)
    int window_index = -1;
};

/// Room boundary result
struct RoomBoundary {
    Polygon2D boundary;         ///< 2D boundary polygon
    Polygon2D polygon;          ///< Alias for boundary (for compatibility)
    Point2D center;             ///< Centroid
    Point2D centroid;           ///< Alias for center
    float area = 0.0f;          ///< Computed area in mm^2
    std::string label;          ///< Room name
    std::string room_name;      ///< Alias for label
    std::string room_type;      ///< Room type (living, bedroom, etc.)
    std::string room_id;
};

//==============================================================================
// Complete Building Geometry
//==============================================================================

/// Complete building geometry output
struct BuildingGeometry {
    std::string building_id;    ///< Building identifier

    std::vector<WallGeometry> walls;
    std::vector<FloorGeometry> floors;
    std::vector<RoofGeometry> roofs;
    std::vector<DoorGeometry> doors;
    std::vector<WindowGeometry> windows;
    std::vector<RoomBoundary> rooms;  ///< Room boundaries

    Vec3 bounds_min;
    Vec3 bounds_max;

    /// Get combined 3D mesh for all walls
    Mesh3D getAllWallMeshes() const {
        Mesh3D combined;
        for (const auto& w : walls) {
            combined.merge(w.mesh_3d);
        }
        return combined;
    }

    /// Get combined floor plan geometry
    Geometry2D getFloorPlan() const {
        Geometry2D combined;
        for (const auto& w : walls) combined.merge(w.plan_view);
        for (const auto& d : doors) combined.merge(d.plan_symbol);
        for (const auto& win : windows) combined.merge(win.plan_symbol);
        return combined;
    }
};

} // namespace archgeometry
