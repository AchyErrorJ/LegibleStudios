#pragma once
/**
 * @file room_geometry.hpp
 * @brief Room boundary computation from schema parameters
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"
#include <vector>

namespace archgeometry {

/**
 * @brief Computes room boundaries and spatial properties
 *
 * IMPORTANT: This implementation correctly handles the Y/Z confusion
 * in room bounds where bounds.y is actually the Z coordinate in 3D space.
 */
class RoomGeometryGenerator {
public:
    /**
     * @brief Generate room boundary polygon
     *
     * @param room The room schema element
     * @param walls All walls (for potential boundary refinement)
     * @return RoomBoundary with 2D polygon and computed properties
     */
    static RoomBoundary generateBoundary(
        const SchemaRoom& room,
        const std::vector<SchemaWall>& walls
    );

    /**
     * @brief Generate boundary from room bounds only (simpler)
     *
     * Uses the rectangular bounds directly without wall intersection.
     */
    static RoomBoundary generateFromBounds(const SchemaRoom& room);

    /**
     * @brief Get room center from bounds
     *
     * CORRECT INTERPRETATION:
     * - bounds.y is Z coordinate in plan view
     * - Return Point2D where x = center X, y = center Z (for plan view)
     */
    static Point2D getCenter(const RoomBounds& bounds);

    /**
     * @brief Calculate room area from bounds
     * @return Area in square mm
     */
    static float getArea(const RoomBounds& bounds);

    /**
     * @brief Convert room bounds to 3D bounding box
     * @param bounds 2D room bounds
     * @param elevation Floor elevation (Y)
     * @param height Ceiling height
     * @return Pair of (min, max) Vec3
     */
    static std::pair<Vec3, Vec3> bounds2Dto3D(
        const RoomBounds& bounds,
        float elevation,
        float height
    );

    /**
     * @brief Generate room label text element
     */
    static Text2D generateLabel(const SchemaRoom& room);

    /**
     * @brief Check if a point is inside a room (2D)
     * @param point Point to test (plan view coordinates)
     * @param room The room to test against
     */
    static bool containsPoint(const Point2D& point, const SchemaRoom& room);

    /**
     * @brief Get room color based on zone type
     */
    static Vec3 getZoneColor(const std::string& zone);
};

} // namespace archgeometry
