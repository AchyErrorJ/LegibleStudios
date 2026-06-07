/**
 * @file wall_geometry.cpp
 * @brief Wall geometry generation implementation
 */

#include "archgeometry/wall_geometry.hpp"
#include <algorithm>
#include <cmath>

namespace archgeometry {

//==============================================================================
// Public API
//==============================================================================

WallGeometry WallGeometryGenerator::generate(
    const SchemaWall& wall,
    const WallType& wall_type,
    const std::vector<SchemaDoor>& doors,
    const std::vector<SchemaWindow>& windows
) {
    WallGeometry result;
    result.wall_id = wall.wall_type;

    float thickness = getThickness(wall_type);
    Vec3 color = getCategoryColor(wall.category);

    // Collect cutouts for this wall
    std::vector<OpeningCutout> cutouts;

    for (size_t i = 0; i < doors.size(); ++i) {
        OpeningCutout cutout;
        cutout.start_offset = doors[i].offset;
        cutout.width = doors[i].width;
        cutout.height = doors[i].height;
        cutout.bottom_height = 0.0f;  // Doors start at floor
        cutout.opening_type = "door";
        cutout.opening_index = static_cast<int>(i);
        cutouts.push_back(cutout);
    }

    for (size_t i = 0; i < windows.size(); ++i) {
        OpeningCutout cutout;
        cutout.start_offset = windows[i].offset;
        cutout.width = windows[i].width;
        cutout.height = windows[i].height;
        cutout.bottom_height = windows[i].sill_height;
        cutout.opening_type = "window";
        cutout.opening_index = static_cast<int>(i);
        cutouts.push_back(cutout);
    }

    result.cutouts = cutouts;

    // Generate 3D mesh
    if (cutouts.empty()) {
        result.mesh_3d = generateSolidMesh(wall.start, wall.end, wall.height, thickness, color);
    } else {
        result.mesh_3d = generateMeshWithCutouts(wall.start, wall.end, wall.height, thickness, color, cutouts);
    }

    result.mesh_3d.element_type = "wall";
    result.mesh_3d.lod_hint = 0;  // Walls visible at all LODs

    // Generate 2D plan view
    result.plan_view.element_type = "wall";
    result.plan_view.polygons.push_back(generatePlanPolygon(wall, thickness));

    return result;
}

WallGeometry WallGeometryGenerator::generateSolid(
    const SchemaWall& wall,
    const WallType& wall_type
) {
    return generate(wall, wall_type, {}, {});
}

float WallGeometryGenerator::getThickness(const WallType& wall_type) {
    return wall_type.totalThickness();
}

std::pair<Vec3, Vec3> WallGeometryGenerator::getCenterline(const SchemaWall& wall) {
    return {wall.start, wall.end};
}

Vec2 WallGeometryGenerator::getDirection(const SchemaWall& wall) {
    return wall.direction();
}

float WallGeometryGenerator::getLength(const SchemaWall& wall) {
    return wall.length();
}

Vec3 WallGeometryGenerator::getPerpendicularOffset(const SchemaWall& wall, float distance) {
    Vec2 dir = wall.direction();
    Vec2 perp = dir.perpendicular();
    return Vec3{perp.x * distance, 0.0f, perp.y * distance};
}

Polygon2D WallGeometryGenerator::generatePlanPolygon(const SchemaWall& wall, float thickness) {
    Polygon2D poly;
    poly.layer = wall.category == "exterior" ? "walls_exterior" : "walls_interior";

    Vec2 dir = wall.direction();
    Vec2 perp = dir.perpendicular();
    float halfT = thickness / 2.0f;

    // Four corners of wall polygon
    Point2D p1{wall.start.x + perp.x * halfT, wall.start.z + perp.y * halfT};
    Point2D p2{wall.start.x - perp.x * halfT, wall.start.z - perp.y * halfT};
    Point2D p3{wall.end.x - perp.x * halfT, wall.end.z - perp.y * halfT};
    Point2D p4{wall.end.x + perp.x * halfT, wall.end.z + perp.y * halfT};

    poly.points = {p1, p2, p3, p4};
    poly.closed = true;

    // Fill based on category
    if (wall.category == "exterior") {
        poly.fill_pattern = "solid";
        poly.fill_color = {0.2f, 0.2f, 0.2f, 1.0f};
    } else {
        poly.fill_pattern = "solid";
        poly.fill_color = {0.4f, 0.4f, 0.4f, 1.0f};
    }

    return poly;
}

Vec3 WallGeometryGenerator::getCategoryColor(const std::string& category) {
    if (category == "exterior") {
        return {0.85f, 0.85f, 0.8f};  // Light tan
    } else if (category == "wet_wall") {
        return {0.7f, 0.85f, 0.9f};   // Light blue
    } else {
        return {0.9f, 0.9f, 0.88f};   // Off-white
    }
}

//==============================================================================
// Private Implementation
//==============================================================================

Mesh3D WallGeometryGenerator::generateSolidMesh(
    const Vec3& start, const Vec3& end,
    float height, float thickness, const Vec3& color
) {
    Mesh3D mesh;

    // Calculate wall direction and perpendicular
    Vec2 dir{end.x - start.x, end.z - start.z};
    float len = dir.length();
    if (len < 0.001f) return mesh;

    dir = dir * (1.0f / len);  // Normalize
    Vec2 perp = dir.perpendicular();
    float halfT = thickness / 2.0f;

    // Calculate 8 corners of the wall box
    // Bottom corners (Y = start.y)
    Vec3 b0{start.x + perp.x * halfT, start.y, start.z + perp.y * halfT};
    Vec3 b1{start.x - perp.x * halfT, start.y, start.z - perp.y * halfT};
    Vec3 b2{end.x - perp.x * halfT, start.y, end.z - perp.y * halfT};
    Vec3 b3{end.x + perp.x * halfT, start.y, end.z + perp.y * halfT};

    // Top corners (Y = start.y + height)
    float topY = start.y + height;
    Vec3 t0{b0.x, topY, b0.z};
    Vec3 t1{b1.x, topY, b1.z};
    Vec3 t2{b2.x, topY, b2.z};
    Vec3 t3{b3.x, topY, b3.z};

    // Generate 6 faces

    // Front face (exterior side)
    Vec3 frontNormal{perp.x, 0, perp.y};
    mesh.addQuad(b0, t0, t3, b3, frontNormal, color);

    // Back face (interior side)
    Vec3 backNormal{-perp.x, 0, -perp.y};
    mesh.addQuad(b1, b2, t2, t1, backNormal, color);

    // Left end
    Vec3 leftNormal{-dir.x, 0, -dir.y};
    mesh.addQuad(b0, b1, t1, t0, leftNormal, color);

    // Right end
    Vec3 rightNormal{dir.x, 0, dir.y};
    mesh.addQuad(b3, t3, t2, b2, rightNormal, color);

    // Top face
    Vec3 topNormal{0, 1, 0};
    mesh.addQuad(t0, t1, t2, t3, topNormal, color);

    // Bottom face
    Vec3 bottomNormal{0, -1, 0};
    mesh.addQuad(b0, b3, b2, b1, bottomNormal, color);

    return mesh;
}

Mesh3D WallGeometryGenerator::generateMeshWithCutouts(
    const Vec3& start, const Vec3& end,
    float height, float thickness, const Vec3& color,
    const std::vector<OpeningCutout>& cutouts
) {
    // For simplicity, this implementation creates segments around openings
    // A full CSG implementation would be more accurate but more complex

    Mesh3D mesh;

    Vec2 dir{end.x - start.x, end.z - start.z};
    float wallLength = dir.length();
    if (wallLength < 0.001f) return mesh;

    dir = dir * (1.0f / wallLength);  // Normalize
    Vec2 perp = dir.perpendicular();
    float halfT = thickness / 2.0f;

    // Sort cutouts by offset
    std::vector<OpeningCutout> sorted = cutouts;
    std::sort(sorted.begin(), sorted.end(),
              [](const OpeningCutout& a, const OpeningCutout& b) {
                  return a.start_offset < b.start_offset;
              });

    // Generate wall segments around openings
    float currentOffset = 0.0f;

    for (const auto& cutout : sorted) {
        float cutStart = cutout.start_offset - cutout.width / 2.0f;
        float cutEnd = cutout.start_offset + cutout.width / 2.0f;

        // Segment before opening
        if (cutStart > currentOffset + 1.0f) {
            Vec3 segStart{
                start.x + dir.x * currentOffset,
                start.y,
                start.z + dir.y * currentOffset
            };
            Vec3 segEnd{
                start.x + dir.x * cutStart,
                start.y,
                start.z + dir.y * cutStart
            };
            mesh.merge(generateSolidMesh(segStart, segEnd, height, thickness, color));
        }

        // Wall above opening (if opening doesn't go to ceiling)
        float openingTop = cutout.bottom_height + cutout.height;
        if (openingTop < height - 1.0f) {
            Vec3 aboveStart{
                start.x + dir.x * cutStart,
                start.y + openingTop,
                start.z + dir.y * cutStart
            };
            Vec3 aboveEnd{
                start.x + dir.x * cutEnd,
                start.y + openingTop,
                start.z + dir.y * cutEnd
            };
            float aboveHeight = height - openingTop;
            mesh.merge(generateSolidMesh(aboveStart, aboveEnd, aboveHeight, thickness, color));
        }

        // Wall below opening (for windows)
        if (cutout.bottom_height > 1.0f) {
            Vec3 belowStart{
                start.x + dir.x * cutStart,
                start.y,
                start.z + dir.y * cutStart
            };
            Vec3 belowEnd{
                start.x + dir.x * cutEnd,
                start.y,
                start.z + dir.y * cutEnd
            };
            mesh.merge(generateSolidMesh(belowStart, belowEnd, cutout.bottom_height, thickness, color));
        }

        currentOffset = cutEnd;
    }

    // Final segment after last opening
    if (currentOffset < wallLength - 1.0f) {
        Vec3 segStart{
            start.x + dir.x * currentOffset,
            start.y,
            start.z + dir.y * currentOffset
        };
        mesh.merge(generateSolidMesh(segStart, end, height, thickness, color));
    }

    return mesh;
}

} // namespace archgeometry
