#pragma once
/**
 * @file floor_geometry.hpp
 * @brief Floor slab geometry generation from schema parameters
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"

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
     * @brief Generate 3D slab mesh
     */
    static Mesh3D generateMesh(
        const Vec3& position,
        float width, float depth, float thickness,
        const Vec3& color = {0.7f, 0.7f, 0.7f}
    );

    /**
     * @brief Generate 2D plan outline
     */
    static Polygon2D generatePlanOutline(const SchemaFloor& floor);
};

} // namespace archgeometry
