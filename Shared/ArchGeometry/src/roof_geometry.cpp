/**
 * @file roof_geometry.cpp
 * @brief Roof geometry generation implementation
 *
 * CRITICAL INTERPRETATION FIX:
 * - Uses provided 3D vertex coordinates directly (roof.surfaces[].vertices)
 * - Does NOT ignore the Y coordinate (ridge height)
 * - Falls back to procedural generation only if no surfaces provided
 */

#include "archgeometry/roof_geometry.hpp"
#include <algorithm>
#include <cmath>

namespace archgeometry {

//==============================================================================
// Public API
//==============================================================================

RoofGeometry RoofGeometryGenerator::generate(const SchemaRoof& roof) {
    RoofGeometry result;
    result.roof_id = roof.id;

    // Prefer pre-computed surfaces if available
    if (!roof.surfaces.empty()) {
        result.mesh_3d = generateFromSurfaces(roof);
    } else {
        // Fall back to procedural generation based on type
        // (Would need building bounds - not implemented here)
        // result.mesh_3d = generateDefault(roof);
    }

    result.mesh_3d.element_type = "roof";
    result.mesh_3d.lod_hint = 1;  // Roof can simplify at distance

    // Generate plan view (outline only)
    result.plan_view.element_type = "roof";
    for (const auto& surface : roof.surfaces) {
        result.plan_view.polygons.push_back(generatePlanPolygon(surface, roof.material));
    }

    return result;
}

Mesh3D RoofGeometryGenerator::generateFromSurfaces(const SchemaRoof& roof) {
    Mesh3D mesh;
    Vec3 color = getMaterialColor(roof.material);

    for (const auto& surface : roof.surfaces) {
        if (surface.vertices.size() < 3) continue;

        // Triangulate the surface polygon
        // For simple convex polygons, use fan triangulation from first vertex
        for (size_t i = 1; i + 1 < surface.vertices.size(); ++i) {
            const Vec3& v0 = surface.vertices[0];
            const Vec3& v1 = surface.vertices[i];
            const Vec3& v2 = surface.vertices[i + 1];

            // Calculate normal from cross product
            Vec3 edge1{v1.x - v0.x, v1.y - v0.y, v1.z - v0.z};
            Vec3 edge2{v2.x - v0.x, v2.y - v0.y, v2.z - v0.z};
            Vec3 normal = cross(edge1, edge2).normalized();

            // Add triangle
            mesh.addTriangle(v0, v1, v2, normal, color);
        }

        // Add backface for thickness (roof underside)
        // Offset down by roof thickness (typically 150-200mm)
        float thickness = 200.0f;  // Default roof thickness
        Vec3 offsetDown{0, -thickness, 0};

        for (size_t i = 1; i + 1 < surface.vertices.size(); ++i) {
            Vec3 v0{surface.vertices[0].x + offsetDown.x,
                    surface.vertices[0].y + offsetDown.y,
                    surface.vertices[0].z + offsetDown.z};
            Vec3 v1{surface.vertices[i].x + offsetDown.x,
                    surface.vertices[i].y + offsetDown.y,
                    surface.vertices[i].z + offsetDown.z};
            Vec3 v2{surface.vertices[i + 1].x + offsetDown.x,
                    surface.vertices[i + 1].y + offsetDown.y,
                    surface.vertices[i + 1].z + offsetDown.z};

            Vec3 edge1{v1.x - v0.x, v1.y - v0.y, v1.z - v0.z};
            Vec3 edge2{v2.x - v0.x, v2.y - v0.y, v2.z - v0.z};
            Vec3 normal = cross(edge2, edge1).normalized();  // Reversed for underside

            mesh.addTriangle(v0, v2, v1, normal, color);  // Reversed winding
        }
    }

    // Generate fascia (edge faces between top and bottom)
    for (const auto& surface : roof.surfaces) {
        if (surface.vertices.size() < 3) continue;

        float thickness = 200.0f;
        size_t n = surface.vertices.size();

        for (size_t i = 0; i < n; ++i) {
            size_t j = (i + 1) % n;

            Vec3 t0 = surface.vertices[i];
            Vec3 t1 = surface.vertices[j];
            Vec3 b0{t0.x, t0.y - thickness, t0.z};
            Vec3 b1{t1.x, t1.y - thickness, t1.z};

            // Edge direction
            Vec3 edge{t1.x - t0.x, t1.y - t0.y, t1.z - t0.z};
            Vec3 down{0, -1, 0};
            Vec3 normal = cross(edge, down).normalized();

            mesh.addQuad(t0, b0, b1, t1, normal, color);
        }
    }

    return mesh;
}

float RoofGeometryGenerator::pitchToAngle(float pitch) {
    // Pitch is typically expressed as rise:run (e.g., 6:12)
    // Convert to radians
    return std::atan(pitch / 12.0f);
}

float RoofGeometryGenerator::getRidgeHeight(float pitch, float span) {
    // Calculate ridge height from pitch and half-span
    float halfSpan = span / 2.0f;
    float angle = pitchToAngle(pitch);
    return halfSpan * std::tan(angle);
}

float RoofGeometryGenerator::getSlopeLength(float pitch, float span) {
    float halfSpan = span / 2.0f;
    float ridgeHeight = getRidgeHeight(pitch, span);
    return std::sqrt(halfSpan * halfSpan + ridgeHeight * ridgeHeight);
}

Vec3 RoofGeometryGenerator::getMaterialColor(const std::string& material) {
    if (material == "asphalt_shingle" || material == "shingle") {
        return {0.3f, 0.3f, 0.32f};   // Dark gray
    } else if (material == "metal" || material == "standing_seam") {
        return {0.5f, 0.52f, 0.55f};  // Medium gray metallic
    } else if (material == "tile" || material == "clay_tile") {
        return {0.7f, 0.35f, 0.25f};  // Terracotta
    } else if (material == "slate") {
        return {0.35f, 0.38f, 0.42f}; // Blue-gray
    } else if (material == "wood_shake") {
        return {0.5f, 0.4f, 0.3f};    // Brown
    } else if (material == "copper") {
        return {0.6f, 0.45f, 0.35f};  // Copper tone
    } else {
        return {0.4f, 0.4f, 0.42f};   // Default dark gray
    }
}

//==============================================================================
// Private Implementation
//==============================================================================

Vec3 RoofGeometryGenerator::cross(const Vec3& a, const Vec3& b) {
    return Vec3{
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x
    };
}

Polygon2D RoofGeometryGenerator::generatePlanPolygon(
    const RoofSurface& surface,
    const std::string& material
) {
    Polygon2D poly;
    poly.layer = "roof";

    // Project 3D vertices to plan view (XZ plane)
    for (const auto& v : surface.vertices) {
        poly.points.push_back(Point2D{v.x, v.z});
    }
    poly.closed = true;

    // Roof fill (semi-transparent in plan view)
    poly.fill_pattern = "hatch_diagonal";
    Vec3 color = getMaterialColor(material);
    poly.fill_color = {color.x, color.y, color.z, 0.2f};

    return poly;
}

Mesh3D RoofGeometryGenerator::generateGableDefault(
    const Vec3& min, const Vec3& max,
    float pitch, float overhang,
    const std::string& material
) {
    Mesh3D mesh;
    Vec3 color = getMaterialColor(material);

    // Building bounds (from walls)
    float buildingWidth = max.x - min.x;
    float buildingDepth = max.z - min.z;
    float eaveHeight = max.y;

    // Calculate ridge height
    float ridgeHeight = getRidgeHeight(pitch, buildingWidth);

    // Ridge line runs along Z axis (front to back)
    float ridgeX = (min.x + max.x) / 2.0f;
    float ridgeY = eaveHeight + ridgeHeight;

    // Include overhang
    float eaveMinX = min.x - overhang;
    float eaveMaxX = max.x + overhang;
    float eaveMinZ = min.z - overhang;
    float eaveMaxZ = max.z + overhang;

    // Left slope
    Vec3 l0{eaveMinX, eaveHeight, eaveMinZ};
    Vec3 l1{eaveMinX, eaveHeight, eaveMaxZ};
    Vec3 l2{ridgeX, ridgeY, eaveMaxZ};
    Vec3 l3{ridgeX, ridgeY, eaveMinZ};

    Vec3 leftNormal = cross(
        Vec3{l1.x - l0.x, l1.y - l0.y, l1.z - l0.z},
        Vec3{l3.x - l0.x, l3.y - l0.y, l3.z - l0.z}
    ).normalized();
    mesh.addQuad(l0, l1, l2, l3, leftNormal, color);

    // Right slope
    Vec3 r0{ridgeX, ridgeY, eaveMinZ};
    Vec3 r1{ridgeX, ridgeY, eaveMaxZ};
    Vec3 r2{eaveMaxX, eaveHeight, eaveMaxZ};
    Vec3 r3{eaveMaxX, eaveHeight, eaveMinZ};

    Vec3 rightNormal = cross(
        Vec3{r1.x - r0.x, r1.y - r0.y, r1.z - r0.z},
        Vec3{r3.x - r0.x, r3.y - r0.y, r3.z - r0.z}
    ).normalized();
    mesh.addQuad(r0, r1, r2, r3, rightNormal, color);

    // Front gable (triangle)
    Vec3 frontNormal{0, 0, -1};
    mesh.addTriangle(
        Vec3{eaveMinX, eaveHeight, eaveMinZ},
        Vec3{ridgeX, ridgeY, eaveMinZ},
        Vec3{eaveMaxX, eaveHeight, eaveMinZ},
        frontNormal, color
    );

    // Back gable (triangle)
    Vec3 backNormal{0, 0, 1};
    mesh.addTriangle(
        Vec3{eaveMaxX, eaveHeight, eaveMaxZ},
        Vec3{ridgeX, ridgeY, eaveMaxZ},
        Vec3{eaveMinX, eaveHeight, eaveMaxZ},
        backNormal, color
    );

    return mesh;
}

Mesh3D RoofGeometryGenerator::generateHipDefault(
    const Vec3& min, const Vec3& max,
    float pitch, float overhang,
    const std::string& material
) {
    Mesh3D mesh;
    Vec3 color = getMaterialColor(material);

    float buildingWidth = max.x - min.x;
    float buildingDepth = max.z - min.z;
    float eaveHeight = max.y;

    // Ridge height (from narrower dimension)
    float minDim = std::min(buildingWidth, buildingDepth);
    float ridgeHeight = getRidgeHeight(pitch, minDim);
    float ridgeY = eaveHeight + ridgeHeight;

    // Include overhang
    float eaveMinX = min.x - overhang;
    float eaveMaxX = max.x + overhang;
    float eaveMinZ = min.z - overhang;
    float eaveMaxZ = max.z + overhang;

    // Hip roof ridge points (inset from corners)
    float ridgeInset = minDim / 2.0f;  // Ridge is inset from the shorter sides

    Vec3 ridgeStart, ridgeEnd;
    if (buildingWidth >= buildingDepth) {
        // Ridge runs along X
        ridgeStart = Vec3{min.x + ridgeInset, ridgeY, (min.z + max.z) / 2.0f};
        ridgeEnd = Vec3{max.x - ridgeInset, ridgeY, (min.z + max.z) / 2.0f};
    } else {
        // Ridge runs along Z
        ridgeStart = Vec3{(min.x + max.x) / 2.0f, ridgeY, min.z + ridgeInset};
        ridgeEnd = Vec3{(min.x + max.x) / 2.0f, ridgeY, max.z - ridgeInset};
    }

    // Four eave corners
    Vec3 c0{eaveMinX, eaveHeight, eaveMinZ};  // Front-left
    Vec3 c1{eaveMaxX, eaveHeight, eaveMinZ};  // Front-right
    Vec3 c2{eaveMaxX, eaveHeight, eaveMaxZ};  // Back-right
    Vec3 c3{eaveMinX, eaveHeight, eaveMaxZ};  // Back-left

    if (buildingWidth >= buildingDepth) {
        // Front slope (trapezoid)
        Vec3 frontNormal = cross(
            Vec3{c1.x - c0.x, c1.y - c0.y, c1.z - c0.z},
            Vec3{ridgeStart.x - c0.x, ridgeStart.y - c0.y, ridgeStart.z - c0.z}
        ).normalized();
        mesh.addQuad(c0, c1, ridgeEnd, ridgeStart, frontNormal, color);

        // Back slope (trapezoid)
        Vec3 backNormal = cross(
            Vec3{c3.x - c2.x, c3.y - c2.y, c3.z - c2.z},
            Vec3{ridgeEnd.x - c2.x, ridgeEnd.y - c2.y, ridgeEnd.z - c2.z}
        ).normalized();
        mesh.addQuad(c2, c3, ridgeStart, ridgeEnd, backNormal, color);

        // Left hip (triangle)
        Vec3 leftNormal = cross(
            Vec3{c0.x - c3.x, c0.y - c3.y, c0.z - c3.z},
            Vec3{ridgeStart.x - c3.x, ridgeStart.y - c3.y, ridgeStart.z - c3.z}
        ).normalized();
        mesh.addTriangle(c3, c0, ridgeStart, leftNormal, color);

        // Right hip (triangle)
        Vec3 rightNormal = cross(
            Vec3{c2.x - c1.x, c2.y - c1.y, c2.z - c1.z},
            Vec3{ridgeEnd.x - c1.x, ridgeEnd.y - c1.y, ridgeEnd.z - c1.z}
        ).normalized();
        mesh.addTriangle(c1, c2, ridgeEnd, rightNormal, color);
    } else {
        // Ridge runs along Z - similar logic but rotated
        // Left slope (trapezoid)
        mesh.addQuad(c3, c0, ridgeStart, ridgeEnd, Vec3{-1, 0.5f, 0}.normalized(), color);

        // Right slope (trapezoid)
        mesh.addQuad(c1, c2, ridgeEnd, ridgeStart, Vec3{1, 0.5f, 0}.normalized(), color);

        // Front hip (triangle)
        mesh.addTriangle(c0, c1, ridgeStart, Vec3{0, 0.5f, -1}.normalized(), color);

        // Back hip (triangle)
        mesh.addTriangle(c2, c3, ridgeEnd, Vec3{0, 0.5f, 1}.normalized(), color);
    }

    return mesh;
}

} // namespace archgeometry
