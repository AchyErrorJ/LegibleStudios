#pragma once
/**
 * @file archgeometry.hpp
 * @brief Main include header for ArchGeometry library
 *
 * ArchGeometry is the canonical shared library for interpreting
 * ArchEngine JSON schemas and converting them to geometry.
 *
 * All consumers (kernel, CAD viewer, plan generators) should use this
 * library instead of implementing their own schema interpretation.
 *
 * Usage:
 * @code
 *   #include <archgeometry/archgeometry.hpp>
 *
 *   // Parse and generate all geometry
 *   auto result = archgeometry::ArchGeometry::generateFromFile("building.json");
 *   if (result) {
 *       auto& geometry = *result;
 *       // Use geometry.walls, geometry.floors, etc.
 *   }
 *
 *   // Or use individual generators
 *   auto doc = archgeometry::SchemaParser::parseFile("building.json");
 *   auto wall_geom = archgeometry::WallGeometryGenerator::generate(
 *       doc.walls[0], wall_type, doors, windows);
 * @endcode
 */

// Core types
#include "archgeometry/schema_types.hpp"
#include "archgeometry/geometry_types.hpp"

// Parser
#include "archgeometry/schema_parser.hpp"

// Geometry generators
#include "archgeometry/wall_geometry.hpp"
#include "archgeometry/floor_geometry.hpp"
#include "archgeometry/roof_geometry.hpp"
#include "archgeometry/opening_geometry.hpp"
#include "archgeometry/room_geometry.hpp"

// Query interface
#include "archgeometry/query_api.hpp"

namespace archgeometry {

/**
 * @brief High-level API for generating all building geometry
 *
 * This is the recommended entry point for most consumers.
 */
class ArchGeometry {
public:
    /**
     * @brief Parse JSON and generate all geometry
     * @param json_string JSON content
     * @return BuildingGeometry or error
     */
    static ParseResult<BuildingGeometry> generateFromJson(const std::string& json_string);

    /**
     * @brief Load file (JSON) and generate all geometry
     * @param file_path Path to JSON file
     * @return BuildingGeometry or error
     */
    static ParseResult<BuildingGeometry> generateFromFile(const std::string& file_path);

    /**
     * @brief Generate all geometry from parsed schema
     * @param doc Parsed schema document
     * @return BuildingGeometry
     */
    static BuildingGeometry generateFromSchema(const SchemaDocument& doc);

    //==========================================================================
    // Incremental Generation (for live editing)
    //==========================================================================

    /**
     * @brief Regenerate geometry for a single wall
     *
     * Use this when only one wall changed, to avoid regenerating everything.
     */
    static WallGeometry regenerateWall(
        const SchemaDocument& doc,
        int wall_index
    );

    /**
     * @brief Regenerate geometry for a single room
     */
    static RoomBoundary regenerateRoom(
        const SchemaDocument& doc,
        const std::string& room_id
    );

    /**
     * @brief Regenerate geometry for a single floor
     */
    static FloorGeometry regenerateFloor(
        const SchemaDocument& doc,
        int floor_index
    );

    //==========================================================================
    // Version Info
    //==========================================================================

    /// Get library version string
    static const char* version();

    /// Get library version components
    static void getVersionComponents(int& major, int& minor, int& patch);
};

} // namespace archgeometry
