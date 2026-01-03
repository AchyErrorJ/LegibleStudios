/**
 * @file archgeometry.cpp
 * @brief Main ArchGeometry library implementation
 *
 * High-level API for parsing JSON schemas and generating all building geometry.
 * This is the primary entry point for most consumers.
 */

#include "archgeometry/archgeometry.hpp"

namespace archgeometry {

// Version info
#define ARCHGEOMETRY_VERSION_MAJOR 1
#define ARCHGEOMETRY_VERSION_MINOR 0
#define ARCHGEOMETRY_VERSION_PATCH 0
#define ARCHGEOMETRY_VERSION_STRING "1.0.0"

//==============================================================================
// Version API
//==============================================================================

const char* ArchGeometry::version() {
    return ARCHGEOMETRY_VERSION_STRING;
}

void ArchGeometry::getVersionComponents(int& major, int& minor, int& patch) {
    major = ARCHGEOMETRY_VERSION_MAJOR;
    minor = ARCHGEOMETRY_VERSION_MINOR;
    patch = ARCHGEOMETRY_VERSION_PATCH;
}

//==============================================================================
// High-Level Generation API
//==============================================================================

ParseResult<BuildingGeometry> ArchGeometry::generateFromJson(const std::string& json_string) {
    // Parse schema
    auto parseResult = SchemaParser::parseJson(json_string);
    if (std::holds_alternative<ParseError>(parseResult)) {
        return std::get<ParseError>(parseResult);
    }

    const SchemaDocument& doc = std::get<SchemaDocument>(parseResult);

    // Validate
    auto validResult = SchemaParser::validate(doc);
    if (std::holds_alternative<ParseError>(validResult)) {
        return std::get<ParseError>(validResult);
    }

    // Generate geometry
    return generateFromSchema(doc);
}

ParseResult<BuildingGeometry> ArchGeometry::generateFromFile(const std::string& file_path) {
    // Parse file
    auto parseResult = SchemaParser::parseFile(file_path);
    if (std::holds_alternative<ParseError>(parseResult)) {
        return std::get<ParseError>(parseResult);
    }

    const SchemaDocument& doc = std::get<SchemaDocument>(parseResult);

    // Validate
    auto validResult = SchemaParser::validate(doc);
    if (std::holds_alternative<ParseError>(validResult)) {
        return std::get<ParseError>(validResult);
    }

    // Generate geometry
    return generateFromSchema(doc);
}

BuildingGeometry ArchGeometry::generateFromSchema(const SchemaDocument& doc) {
    BuildingGeometry result;
    result.building_id = doc.building_id;

    // Get default wall type for walls without explicit type
    WallType defaultWallType;
    defaultWallType.id = "default";
    defaultWallType.name = "Default Wall";
    WallLayer defaultLayer;
    defaultLayer.name = "structure";
    defaultLayer.thickness = 150.0f;
    defaultWallType.layers.push_back(defaultLayer);

    // Generate wall geometry
    for (size_t i = 0; i < doc.walls.size(); ++i) {
        const SchemaWall& wall = doc.walls[i];

        // Find wall type
        const WallType* wallType = &defaultWallType;
        auto it = doc.wall_types.find(wall.wall_type);
        if (it != doc.wall_types.end()) {
            wallType = &it->second;
        }

        // Collect doors and windows for this wall
        std::vector<SchemaDoor> wallDoors;
        for (const auto& door : doc.doors) {
            if (door.wall_index == static_cast<int>(i)) {
                wallDoors.push_back(door);
            }
        }

        std::vector<SchemaWindow> wallWindows;
        for (const auto& window : doc.windows) {
            if (window.wall_index == static_cast<int>(i)) {
                wallWindows.push_back(window);
            }
        }

        // Generate wall geometry
        WallGeometry wallGeom = WallGeometryGenerator::generate(
            wall, *wallType, wallDoors, wallWindows
        );
        result.walls.push_back(wallGeom);
    }

    // Generate floor geometry
    for (const auto& floor : doc.floors) {
        FloorGeometry floorGeom = FloorGeometryGenerator::generate(floor);
        result.floors.push_back(floorGeom);
    }

    // Generate roof geometry
    for (const auto& roof : doc.roofs) {
        RoofGeometry roofGeom = RoofGeometryGenerator::generate(roof);
        result.roofs.push_back(roofGeom);
    }

    // Generate door geometry
    for (const auto& door : doc.doors) {
        if (door.wall_index >= 0 && door.wall_index < static_cast<int>(doc.walls.size())) {
            const SchemaWall& wall = doc.walls[door.wall_index];

            // Get wall thickness
            float thickness = 150.0f;
            auto it = doc.wall_types.find(wall.wall_type);
            if (it != doc.wall_types.end()) {
                thickness = it->second.totalThickness();
            }

            DoorGeometry doorGeom = OpeningGeometryGenerator::generateDoor(door, wall, thickness);
            result.doors.push_back(doorGeom);
        }
    }

    // Generate window geometry
    for (const auto& window : doc.windows) {
        if (window.wall_index >= 0 && window.wall_index < static_cast<int>(doc.walls.size())) {
            const SchemaWall& wall = doc.walls[window.wall_index];

            // Get wall thickness
            float thickness = 150.0f;
            auto it = doc.wall_types.find(wall.wall_type);
            if (it != doc.wall_types.end()) {
                thickness = it->second.totalThickness();
            }

            WindowGeometry windowGeom = OpeningGeometryGenerator::generateWindow(window, wall, thickness);
            result.windows.push_back(windowGeom);
        }
    }

    // Generate room boundaries
    for (const auto& [id, room] : doc.rooms) {
        RoomBoundary roomBoundary = RoomGeometryGenerator::generateBoundary(room, doc.walls);
        result.rooms.push_back(roomBoundary);
    }

    return result;
}

//==============================================================================
// Incremental Regeneration
//==============================================================================

WallGeometry ArchGeometry::regenerateWall(
    const SchemaDocument& doc,
    int wall_index
) {
    if (wall_index < 0 || wall_index >= static_cast<int>(doc.walls.size())) {
        return WallGeometry{};
    }

    const SchemaWall& wall = doc.walls[wall_index];

    // Find wall type
    WallType defaultWallType;
    defaultWallType.id = "default";
    WallLayer defaultLayer;
    defaultLayer.thickness = 150.0f;
    defaultWallType.layers.push_back(defaultLayer);

    const WallType* wallType = &defaultWallType;
    auto it = doc.wall_types.find(wall.wall_type);
    if (it != doc.wall_types.end()) {
        wallType = &it->second;
    }

    // Collect doors and windows for this wall
    std::vector<SchemaDoor> wallDoors;
    for (const auto& door : doc.doors) {
        if (door.wall_index == wall_index) {
            wallDoors.push_back(door);
        }
    }

    std::vector<SchemaWindow> wallWindows;
    for (const auto& window : doc.windows) {
        if (window.wall_index == wall_index) {
            wallWindows.push_back(window);
        }
    }

    return WallGeometryGenerator::generate(wall, *wallType, wallDoors, wallWindows);
}

RoomBoundary ArchGeometry::regenerateRoom(
    const SchemaDocument& doc,
    const std::string& room_id
) {
    auto it = doc.rooms.find(room_id);
    if (it == doc.rooms.end()) {
        return RoomBoundary{};
    }

    return RoomGeometryGenerator::generateBoundary(it->second, doc.walls);
}

FloorGeometry ArchGeometry::regenerateFloor(
    const SchemaDocument& doc,
    int floor_index
) {
    if (floor_index < 0 || floor_index >= static_cast<int>(doc.floors.size())) {
        return FloorGeometry{};
    }

    return FloorGeometryGenerator::generate(doc.floors[floor_index]);
}

} // namespace archgeometry
