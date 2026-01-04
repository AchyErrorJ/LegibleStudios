/**
 * @file floor_geometry.cpp
 * @brief Floor geometry generation implementation
 *
 * CRITICAL INTERPRETATION FIX:
 * - start/end define XZ bounds (plan view rectangle)
 * - thickness is the Y dimension (vertical slab depth)
 * - This differs from the C++ kernel which confused depth with thickness
 */

#include "archgeometry/floor_geometry.hpp"
#include <algorithm>
#include <cmath>

namespace archgeometry {

//==============================================================================
// Public API
//==============================================================================

FloorGeometry FloorGeometryGenerator::generate(const SchemaFloor& floor) {
    FloorGeometry result;
    result.floor_id = floor.level_name;
    result.room_id = floor.room.value_or("");

    // Get floor dimensions - CORRECT interpretation
    float width = getWidth(floor);    // X dimension
    float depth = getDepth(floor);    // Z dimension (NOT thickness!)
    float thickness = floor.thickness; // Y dimension (slab depth)

    // Floor bounds
    float minX = std::min(floor.start.x, floor.end.x);
    float maxX = std::max(floor.start.x, floor.end.x);
    float minZ = std::min(floor.start.z, floor.end.z);
    float maxZ = std::max(floor.start.z, floor.end.z);

    // Elevation is the Y coordinate (top of floor slab)
    float topY = floor.start.y;
    float bottomY = topY - thickness;

    // Generate 3D mesh (box)
    result.mesh_3d = generateFloorMesh(minX, maxX, minZ, maxZ, bottomY, topY, floor.material);
    result.mesh_3d.element_type = "floor";
    result.mesh_3d.lod_hint = 0;  // Floors visible at all LODs

    // Generate 2D plan view
    result.plan_view.element_type = "floor";
    result.plan_view.polygons.push_back(generatePlanPolygon(floor));

    return result;
}

float FloorGeometryGenerator::getWidth(const SchemaFloor& floor) {
    // X dimension from start to end
    return std::abs(floor.end.x - floor.start.x);
}

float FloorGeometryGenerator::getDepth(const SchemaFloor& floor) {
    // Z dimension from start to end (NOT thickness!)
    // This is the critical fix - depth is the Z extent in plan view
    return std::abs(floor.end.z - floor.start.z);
}

float FloorGeometryGenerator::getElevation(const SchemaFloor& floor) {
    // Y coordinate (floor level)
    return floor.start.y;
}

float FloorGeometryGenerator::getArea(const SchemaFloor& floor) {
    return getWidth(floor) * getDepth(floor);
}

std::pair<Vec3, Vec3> FloorGeometryGenerator::getBounds(const SchemaFloor& floor) {
    Vec3 minBound{
        std::min(floor.start.x, floor.end.x),
        floor.start.y - floor.thickness,
        std::min(floor.start.z, floor.end.z)
    };
    Vec3 maxBound{
        std::max(floor.start.x, floor.end.x),
        floor.start.y,
        std::max(floor.start.z, floor.end.z)
    };
    return {minBound, maxBound};
}

Point2D FloorGeometryGenerator::getCenter(const SchemaFloor& floor) {
    return Point2D{
        (floor.start.x + floor.end.x) / 2.0f,
        (floor.start.z + floor.end.z) / 2.0f
    };
}

Vec3 FloorGeometryGenerator::getMaterialColor(const std::string& material) {
    if (material == "hardwood" || material == "wood") {
        return {0.65f, 0.45f, 0.25f};  // Brown
    } else if (material == "tile" || material == "ceramic") {
        return {0.85f, 0.85f, 0.8f};   // Light tan
    } else if (material == "carpet") {
        return {0.6f, 0.55f, 0.5f};    // Warm gray
    } else if (material == "concrete") {
        return {0.7f, 0.7f, 0.7f};     // Gray
    } else if (material == "marble") {
        return {0.95f, 0.95f, 0.92f};  // Off-white
    } else if (material == "vinyl" || material == "lvp") {
        return {0.75f, 0.6f, 0.45f};   // Light wood tone
    } else {
        return {0.8f, 0.8f, 0.78f};    // Default light gray
    }
}

//==============================================================================
// Private Implementation
//==============================================================================

Mesh3D FloorGeometryGenerator::generateFloorMesh(
    float minX, float maxX,
    float minZ, float maxZ,
    float bottomY, float topY,
    const std::string& material
) {
    Mesh3D mesh;
    Vec3 color = getMaterialColor(material);

    // 8 corners of the floor slab
    // Bottom corners
    Vec3 b0{minX, bottomY, minZ};
    Vec3 b1{maxX, bottomY, minZ};
    Vec3 b2{maxX, bottomY, maxZ};
    Vec3 b3{minX, bottomY, maxZ};

    // Top corners
    Vec3 t0{minX, topY, minZ};
    Vec3 t1{maxX, topY, minZ};
    Vec3 t2{maxX, topY, maxZ};
    Vec3 t3{minX, topY, maxZ};

    // Top face (visible from above)
    Vec3 topNormal{0, 1, 0};
    mesh.addQuad(t0, t1, t2, t3, topNormal, color);

    // Bottom face (typically not visible but include for completeness)
    Vec3 bottomNormal{0, -1, 0};
    mesh.addQuad(b3, b2, b1, b0, bottomNormal, color);

    // Side faces (edges of slab)
    Vec3 frontNormal{0, 0, -1};
    mesh.addQuad(t0, b0, b1, t1, frontNormal, color);

    Vec3 backNormal{0, 0, 1};
    mesh.addQuad(t2, b2, b3, t3, backNormal, color);

    Vec3 leftNormal{-1, 0, 0};
    mesh.addQuad(t3, b3, b0, t0, leftNormal, color);

    Vec3 rightNormal{1, 0, 0};
    mesh.addQuad(t1, b1, b2, t2, rightNormal, color);

    return mesh;
}

Polygon2D FloorGeometryGenerator::generatePlanPolygon(const SchemaFloor& floor) {
    Polygon2D poly;
    poly.layer = "floors";

    float minX = std::min(floor.start.x, floor.end.x);
    float maxX = std::max(floor.start.x, floor.end.x);
    float minZ = std::min(floor.start.z, floor.end.z);
    float maxZ = std::max(floor.start.z, floor.end.z);

    // Rectangle in plan view
    poly.points = {
        Point2D{minX, minZ},
        Point2D{maxX, minZ},
        Point2D{maxX, maxZ},
        Point2D{minX, maxZ}
    };
    poly.closed = true;

    // Floor fill
    poly.fill_pattern = "solid";
    Vec3 color = getMaterialColor(floor.material);
    poly.fill_color = {color.x, color.y, color.z, 0.3f};  // Semi-transparent

    return poly;
}

} // namespace archgeometry
