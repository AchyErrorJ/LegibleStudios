#pragma once
/**
 * @file opening_geometry.hpp
 * @brief Door and window geometry generation
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"

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
     * @brief Generate door frame mesh
     */
    static Mesh3D generateDoorFrame(
        const Vec3& position,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        float width,
        float height,
        float wall_thickness
    );

    /**
     * @brief Generate door panel mesh
     */
    static Mesh3D generateDoorPanel(
        const Vec3& position,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        float width,
        float height,
        const std::string& swing
    );

    /**
     * @brief Generate 2D door swing arc for plan view
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
     * @brief Generate window frame mesh
     */
    static Mesh3D generateWindowFrame(
        const Vec3& position,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        float width,
        float height,
        float wall_thickness
    );

    /**
     * @brief Generate window glass mesh
     */
    static Mesh3D generateWindowGlass(
        const Vec3& position,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        float width,
        float height
    );

    /**
     * @brief Generate 2D window symbol for plan view
     */
    static Geometry2D generateWindowSymbol(
        const SchemaWindow& window,
        const SchemaWall& wall
    );

    //==========================================================================
    // Utilities
    //==========================================================================

    /**
     * @brief Calculate opening position on wall
     */
    static Vec3 getOpeningPosition(float offset, const SchemaWall& wall);

    /**
     * @brief Generate vertical frame member (jamb)
     */
    static void generateFrameMember(
        Mesh3D& mesh,
        const Vec3& base,
        float width,
        float height,
        float depth,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        const Vec3& color
    );

    /**
     * @brief Generate horizontal frame member (sill/head)
     */
    static void generateFrameMemberHorizontal(
        Mesh3D& mesh,
        const Vec3& base,
        float width,
        float height,
        float depth,
        const Vec2& wallDir,
        const Vec2& wallPerp,
        const Vec3& color
    );
};

} // namespace archgeometry
