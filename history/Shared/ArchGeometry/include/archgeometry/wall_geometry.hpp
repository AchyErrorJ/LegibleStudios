#pragma once
/**
 * @file wall_geometry.hpp
 * @brief Wall geometry generation from schema parameters
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"
#include <vector>

namespace archgeometry {

/**
 * @brief Generates wall geometry from schema parameters
 *
 * This is the canonical implementation for wall geometry interpretation.
 * All consumers should use this class instead of implementing their own.
 */
class WallGeometryGenerator {
public:
    /**
     * @brief Generate complete wall geometry including 3D mesh and 2D views
     *
     * @param wall The wall schema element
     * @param wall_type Wall assembly definition (for thickness)
     * @param doors Doors on this wall (for cutouts)
     * @param windows Windows on this wall (for cutouts)
     * @return WallGeometry containing 3D mesh and 2D representations
     */
    static WallGeometry generate(
        const SchemaWall& wall,
        const WallType& wall_type,
        const std::vector<SchemaDoor>& doors,
        const std::vector<SchemaWindow>& windows
    );

    /**
     * @brief Generate wall without openings (simpler case)
     */
    static WallGeometry generateSolid(
        const SchemaWall& wall,
        const WallType& wall_type
    );

    /**
     * @brief Get wall thickness from wall type
     * @return Total thickness in mm
     */
    static float getThickness(const WallType& wall_type);

    /**
     * @brief Get wall centerline points
     * @return Pair of (start, end) in 3D
     */
    static std::pair<Vec3, Vec3> getCenterline(const SchemaWall& wall);

    /**
     * @brief Get normalized direction vector (XZ plane)
     */
    static Vec2 getDirection(const SchemaWall& wall);

    /**
     * @brief Get wall length in XZ plane
     */
    static float getLength(const SchemaWall& wall);

    /**
     * @brief Get perpendicular offset vector for wall thickness
     * @param wall The wall
     * @param distance Offset distance (positive = left of direction)
     * @return 3D offset vector (Y=0)
     */
    static Vec3 getPerpendicularOffset(const SchemaWall& wall, float distance);

    /**
     * @brief Generate 2D plan view polygon for wall
     * @param wall The wall
     * @param thickness Wall thickness
     * @return Polygon2D representing wall outline
     */
    static Polygon2D generatePlanPolygon(const SchemaWall& wall, float thickness);

    /**
     * @brief Get color based on wall category
     */
    static Vec3 getCategoryColor(const std::string& category);

private:
    /// Generate 3D mesh for solid wall (no openings)
    static Mesh3D generateSolidMesh(
        const Vec3& start, const Vec3& end,
        float height, float thickness, const Vec3& color
    );

    /// Generate 3D mesh with rectangular cutouts
    static Mesh3D generateMeshWithCutouts(
        const Vec3& start, const Vec3& end,
        float height, float thickness, const Vec3& color,
        const std::vector<OpeningCutout>& cutouts
    );
};

} // namespace archgeometry
