#pragma once
/**
 * @file roof_geometry.hpp
 * @brief Roof geometry generation from schema parameters
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"

namespace archgeometry {

/**
 * @brief Generates roof geometry from schema parameters
 *
 * IMPORTANT: This implementation correctly uses the 3D vertices from
 * roof surfaces. The Y coordinate contains the actual ridge height
 * and should NOT be ignored.
 */
class RoofGeometryGenerator {
public:
    /**
     * @brief Generate complete roof geometry
     */
    static RoofGeometry generate(const SchemaRoof& roof);

    /**
     * @brief Generate mesh from provided surface vertices
     */
    static Mesh3D generateFromSurfaces(const SchemaRoof& roof);

    /**
     * @brief Generate default gable roof from building bounds
     */
    static Mesh3D generateGableDefault(
        const Vec3& min, const Vec3& max,
        float pitch, float overhang,
        const std::string& material
    );

    /**
     * @brief Generate default hip roof from building bounds
     */
    static Mesh3D generateHipDefault(
        const Vec3& min, const Vec3& max,
        float pitch, float overhang,
        const std::string& material
    );

    /**
     * @brief Convert pitch ratio (rise:12) to angle in radians
     */
    static float pitchToAngle(float pitch);

    /**
     * @brief Calculate ridge height from pitch and span
     */
    static float getRidgeHeight(float pitch, float span);

    /**
     * @brief Calculate slope length from pitch and span
     */
    static float getSlopeLength(float pitch, float span);

    /**
     * @brief Get material color for rendering
     */
    static Vec3 getMaterialColor(const std::string& material);

private:
    /**
     * @brief Cross product helper
     */
    static Vec3 cross(const Vec3& a, const Vec3& b);

    /**
     * @brief Generate plan polygon from roof surface
     */
    static Polygon2D generatePlanPolygon(
        const RoofSurface& surface,
        const std::string& material
    );
};

} // namespace archgeometry
