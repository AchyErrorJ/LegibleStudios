#pragma once
/**
 * @file opening_geometry.hpp
 * @brief Door and window geometry generation
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"
#include <tuple>

namespace archgeometry {

/**
 * @brief Generates door and window geometry
 *
 * Handles both 3D mesh generation and 2D plan symbols.
 */
class OpeningGeometryGenerator {
public:
    //==========================================================================
    // Door Geometry
    //==========================================================================

    /**
     * @brief Generate complete door geometry
     * @param door The door schema element
     * @param wall The wall this door is in
     * @param wall_thickness Wall thickness for frame depth
     * @return DoorGeometry with 3D mesh and 2D symbol
     */
    static DoorGeometry generateDoor(
        const SchemaDoor& door,
        const SchemaWall& wall,
        float wall_thickness
    );

    /**
     * @brief Get door cutout rectangle for wall CSG
     */
    static OpeningCutout getDoorCutout(
        const SchemaDoor& door,
        const SchemaWall& wall
    );

    /**
     * @brief Generate 2D door swing arc for plan view
     * @param door The door
     * @param wall The wall
     * @return Geometry2D with door symbol (leaf line + swing arc)
     */
    static Geometry2D generateDoorSymbol(
        const SchemaDoor& door,
        const SchemaWall& wall
    );

    //==========================================================================
    // Window Geometry
    //==========================================================================

    /**
     * @brief Generate complete window geometry
     * @param window The window schema element
     * @param wall The wall this window is in
     * @param wall_thickness Wall thickness for frame depth
     * @return WindowGeometry with 3D mesh and 2D symbol
     */
    static WindowGeometry generateWindow(
        const SchemaWindow& window,
        const SchemaWall& wall,
        float wall_thickness
    );

    /**
     * @brief Get window cutout rectangle for wall CSG
     */
    static OpeningCutout getWindowCutout(
        const SchemaWindow& window,
        const SchemaWall& wall
    );

    /**
     * @brief Generate 2D window symbol for plan view
     * @return Geometry2D with window lines
     */
    static Geometry2D generateWindowSymbol(
        const SchemaWindow& window,
        const SchemaWall& wall,
        float wall_thickness
    );

    //==========================================================================
    // Utilities
    //==========================================================================

    /**
     * @brief Calculate opening position on wall
     *
     * @param offset Distance along wall from start
     * @param width Opening width
     * @param wall The wall
     * @return Tuple of (center_x, center_z, dir_x, dir_z, angle_degrees)
     */
    static std::tuple<float, float, float, float, float> getOpeningPosition(
        float offset,
        float width,
        const SchemaWall& wall
    );

    /**
     * @brief Generate 3D frame mesh for door or window
     */
    static Mesh3D generateFrameMesh(
        const Vec3& position,
        float width, float height,
        float frame_depth, float frame_width,
        const Vec2& wall_direction,
        const Vec3& color
    );

private:
    /// Calculate door swing direction based on swing type
    static float getSwingAngle(const std::string& swing_type);

    /// Determine if door swings inward based on swing type
    static bool isInwardSwing(const std::string& swing_type);
};

} // namespace archgeometry
