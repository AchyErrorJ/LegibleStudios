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
     * @param roof The roof schema element
     * @return RoofGeometry containing 3D mesh and 2D roof plan
     */
    static RoofGeometry generate(const SchemaRoof& roof);

    /**
     * @brief Generate from provided surface vertices
     *
     * Uses the 3D vertices directly from roof.surfaces[].vertices
     * This preserves the actual ridge heights.
     */
    static RoofGeometry generateFromSurfaces(const SchemaRoof& roof);

    /**
     * @brief Generate default gable roof (if no surfaces provided)
     */
    static RoofGeometry generateGableDefault(
        float building_width,
        float building_depth,
        float wall_height,
        float pitch,
        float overhang
    );

    /**
     * @brief Generate default hip roof (if no surfaces provided)
     */
    static RoofGeometry generateHipDefault(
        float building_width,
        float building_depth,
        float wall_height,
        float pitch,
        float overhang
    );

    /**
     * @brief Generate flat roof
     */
    static RoofGeometry generateFlatDefault(
        float building_width,
        float building_depth,
        float wall_height,
        float overhang
    );

    /**
     * @brief Generate shed roof (single slope)
     */
    static RoofGeometry generateShedDefault(
        float building_width,
        float building_depth,
        float wall_height,
        float pitch,
        float overhang
    );

    /**
     * @brief Convert pitch ratio (rise:12) to angle in radians
     * @param pitch Rise per 12 units of run (e.g., 6 for 6:12)
     * @return Angle in radians
     */
    static float pitchToRadians(float pitch);

    /**
     * @brief Calculate ridge height from pitch and span
     * @param pitch Rise per 12 units
     * @param span Distance from wall to ridge (typically half building width)
     * @return Ridge height above wall top in mm
     */
    static float ridgeHeight(float pitch, float span);

    /**
     * @brief Generate 2D roof plan lines (ridge, hip, eave, rake)
     */
    static Geometry2D generateRoofPlan(const SchemaRoof& roof);

private:
    /// Generate mesh from polygon vertices (fan triangulation)
    static Mesh3D generateSurfaceMesh(
        const std::vector<Vec3>& vertices,
        const Vec3& color
    );

    /// Calculate surface normal from vertices
    static Vec3 calculateNormal(const std::vector<Vec3>& vertices);
};

} // namespace archgeometry
