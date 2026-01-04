#pragma once
/**
 * @file floor_geometry.hpp
 * @brief Floor slab geometry generation from schema parameters
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"
#include <utility>

namespace archgeometry {

/**
 * @brief Generates floor geometry from schema parameters
 *
 * IMPORTANT: This implementation correctly interprets floor coordinates:
 * - start/end define XZ bounds (plan view rectangle)
 * - start.y is the elevation (typically 0 for ground floor)
 * - thickness is a separate property, NOT derived from Y coordinates
 */
class FloorGeometryGenerator {
public:
    /**
     * @brief Generate complete floor geometry
     * @param floor The floor schema element
     * @return FloorGeometry containing 3D mesh and 2D plan view
     */
    static FloorGeometry generate(const SchemaFloor& floor);

    /**
     * @brief Get floor width (X dimension)
     *
     * CORRECT INTERPRETATION: width = |end.x - start.x|
     */
    static float getWidth(const SchemaFloor& floor);

    /**
     * @brief Get floor depth (Z dimension)
     *
     * CORRECT INTERPRETATION: depth = |end.z - start.z|
     * This is NOT the same as thickness!
     */
    static float getDepth(const SchemaFloor& floor);

    /**
     * @brief Get floor elevation (Y coordinate)
     */
    static float getElevation(const SchemaFloor& floor);

    /**
     * @brief Get floor area in square mm
     */
    static float getArea(const SchemaFloor& floor);

    /**
     * @brief Get floor bounding box
     */
    static std::pair<Vec3, Vec3> getBounds(const SchemaFloor& floor);

    /**
     * @brief Get floor center point in plan view
     */
    static Point2D getCenter(const SchemaFloor& floor);

    /**
     * @brief Get material color for rendering
     */
    static Vec3 getMaterialColor(const std::string& material);

    /**
     * @brief Generate 3D floor mesh
     */
    static Mesh3D generateFloorMesh(
        float minX, float maxX, float minZ, float maxZ,
        float bottomY, float topY,
        const std::string& material = "concrete"
    );

    /**
     * @brief Generate 2D plan polygon
     */
    static Polygon2D generatePlanPolygon(const SchemaFloor& floor);
};

} // namespace archgeometry
