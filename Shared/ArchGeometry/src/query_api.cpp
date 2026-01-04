/**
 * @file query_api.cpp
 * @brief Query API implementation for schema document access
 */

#include "archgeometry/query_api.hpp"
#include "archgeometry/room_geometry.hpp"
#include <algorithm>
#include <cmath>
#include <limits>

namespace archgeometry {

//==============================================================================
// Constructor
//==============================================================================

QueryAPI::QueryAPI(const SchemaDocument& doc)
    : m_doc(doc)
{
}

//==============================================================================
// Element Access
//==============================================================================

const std::vector<SchemaWall>& QueryAPI::getWalls() const {
    return m_doc.walls;
}

const SchemaWall* QueryAPI::getWallByIndex(int index) const {
    if (index < 0 || index >= static_cast<int>(m_doc.walls.size())) {
        return nullptr;
    }
    return &m_doc.walls[index];
}

const SchemaRoom* QueryAPI::getRoomById(const std::string& id) const {
    auto it = m_doc.rooms.find(id);
    if (it == m_doc.rooms.end()) {
        return nullptr;
    }
    return &it->second;
}

const SchemaLevel* QueryAPI::getLevelByName(const std::string& name) const {
    for (const auto& level : m_doc.levels) {
        if (level.name == name) {
            return &level;
        }
    }
    return nullptr;
}

const WallType* QueryAPI::getWallTypeById(const std::string& id) const {
    auto it = m_doc.wall_types.find(id);
    if (it == m_doc.wall_types.end()) {
        return nullptr;
    }
    return &it->second;
}

//==============================================================================
// Spatial Queries
//==============================================================================

std::vector<const SchemaWall*> QueryAPI::getWallsOnLevel(const std::string& level_name) const {
    std::vector<const SchemaWall*> result;
    for (const auto& wall : m_doc.walls) {
        if (wall.level_name == level_name) {
            result.push_back(&wall);
        }
    }
    return result;
}

std::vector<const SchemaWall*> QueryAPI::getWallsInBounds(const Vec3& min, const Vec3& max) const {
    std::vector<const SchemaWall*> result;
    for (const auto& wall : m_doc.walls) {
        // Check if wall intersects bounding box
        float wallMinX = std::min(wall.start.x, wall.end.x);
        float wallMaxX = std::max(wall.start.x, wall.end.x);
        float wallMinZ = std::min(wall.start.z, wall.end.z);
        float wallMaxZ = std::max(wall.start.z, wall.end.z);
        float wallMinY = wall.start.y;
        float wallMaxY = wall.start.y + wall.height;

        // AABB intersection test
        if (wallMaxX >= min.x && wallMinX <= max.x &&
            wallMaxY >= min.y && wallMinY <= max.y &&
            wallMaxZ >= min.z && wallMinZ <= max.z) {
            result.push_back(&wall);
        }
    }
    return result;
}

std::vector<const SchemaRoom*> QueryAPI::getRoomsOnLevel(const std::string& level_name) const {
    std::vector<const SchemaRoom*> result;
    for (const auto& [id, room] : m_doc.rooms) {
        if (room.level == level_name) {
            result.push_back(&room);
        }
    }
    return result;
}

const SchemaRoom* QueryAPI::getRoomAtPoint(const Point2D& point) const {
    for (const auto& [id, room] : m_doc.rooms) {
        if (RoomGeometryGenerator::containsPoint(point, room)) {
            return &room;
        }
    }
    return nullptr;
}

//==============================================================================
// Relationship Queries
//==============================================================================

std::vector<const SchemaRoom*> QueryAPI::getAdjacentRooms(const std::string& room_id) const {
    std::vector<const SchemaRoom*> result;

    // Find rooms that share a wall with this room
    for (const auto& wall : m_doc.walls) {
        std::string otherRoom;
        if (wall.rooms[0] == room_id && !wall.rooms[1].empty()) {
            otherRoom = wall.rooms[1];
        } else if (wall.rooms[1] == room_id && !wall.rooms[0].empty()) {
            otherRoom = wall.rooms[0];
        }

        if (!otherRoom.empty()) {
            auto it = m_doc.rooms.find(otherRoom);
            if (it != m_doc.rooms.end()) {
                // Check if already in result
                bool found = false;
                for (const auto* r : result) {
                    if (r->id == otherRoom) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    result.push_back(&it->second);
                }
            }
        }
    }

    return result;
}

std::vector<const SchemaWall*> QueryAPI::getWallsForRoom(const std::string& room_id) const {
    std::vector<const SchemaWall*> result;
    for (const auto& wall : m_doc.walls) {
        if (wall.rooms[0] == room_id || wall.rooms[1] == room_id) {
            result.push_back(&wall);
        }
    }
    return result;
}

std::vector<const SchemaDoor*> QueryAPI::getDoorsForWall(int wall_index) const {
    std::vector<const SchemaDoor*> result;
    for (const auto& door : m_doc.doors) {
        if (door.wall_index == wall_index) {
            result.push_back(&door);
        }
    }
    return result;
}

std::vector<const SchemaWindow*> QueryAPI::getWindowsForWall(int wall_index) const {
    std::vector<const SchemaWindow*> result;
    for (const auto& window : m_doc.windows) {
        if (window.wall_index == wall_index) {
            result.push_back(&window);
        }
    }
    return result;
}

//==============================================================================
// Geometry Queries
//==============================================================================

RoomBoundary QueryAPI::getRoomBoundary(const std::string& room_id) const {
    const SchemaRoom* room = getRoomById(room_id);
    if (!room) {
        return RoomBoundary{};
    }
    return RoomGeometryGenerator::generateFromBounds(*room);
}

float QueryAPI::getRoomArea(const std::string& room_id) const {
    const SchemaRoom* room = getRoomById(room_id);
    if (!room) {
        return 0.0f;
    }
    return RoomGeometryGenerator::getArea(room->bounds);
}

float QueryAPI::getWallLength(int wall_index) const {
    const SchemaWall* wall = getWallByIndex(wall_index);
    if (!wall) {
        return 0.0f;
    }
    return wall->length();
}

float QueryAPI::getWallThickness(int wall_index) const {
    const SchemaWall* wall = getWallByIndex(wall_index);
    if (!wall) {
        return 0.0f;
    }

    const WallType* wallType = getWallTypeById(wall->wall_type);
    if (!wallType) {
        return 150.0f;  // Default thickness
    }

    return wallType->totalThickness();
}

//==============================================================================
// Building-Level Queries
//==============================================================================

Vec3 QueryAPI::getBuildingBoundsMin() const {
    Vec3 min{
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max(),
        std::numeric_limits<float>::max()
    };

    for (const auto& wall : m_doc.walls) {
        min.x = std::min({min.x, wall.start.x, wall.end.x});
        min.y = std::min({min.y, wall.start.y});
        min.z = std::min({min.z, wall.start.z, wall.end.z});
    }

    // If no walls, return zero
    if (min.x == std::numeric_limits<float>::max()) {
        return Vec3{0, 0, 0};
    }

    return min;
}

Vec3 QueryAPI::getBuildingBoundsMax() const {
    Vec3 max{
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest(),
        std::numeric_limits<float>::lowest()
    };

    for (const auto& wall : m_doc.walls) {
        max.x = std::max({max.x, wall.start.x, wall.end.x});
        max.y = std::max({max.y, wall.start.y + wall.height});
        max.z = std::max({max.z, wall.start.z, wall.end.z});
    }

    // If no walls, return zero
    if (max.x == std::numeric_limits<float>::lowest()) {
        return Vec3{0, 0, 0};
    }

    return max;
}

float QueryAPI::getTotalFloorArea() const {
    float total = 0.0f;
    for (const auto& floor : m_doc.floors) {
        float width = std::abs(floor.end.x - floor.start.x);
        float depth = std::abs(floor.end.z - floor.start.z);
        total += width * depth;
    }
    return total;
}

int QueryAPI::getWallCount() const {
    return static_cast<int>(m_doc.walls.size());
}

int QueryAPI::getRoomCount() const {
    return static_cast<int>(m_doc.rooms.size());
}

int QueryAPI::getFloorCount() const {
    return static_cast<int>(m_doc.floors.size());
}

int QueryAPI::getDoorCount() const {
    return static_cast<int>(m_doc.doors.size());
}

int QueryAPI::getWindowCount() const {
    return static_cast<int>(m_doc.windows.size());
}

//==============================================================================
// Statistics
//==============================================================================

int QueryAPI::getExteriorWallCount() const {
    int count = 0;
    for (const auto& wall : m_doc.walls) {
        if (wall.category == "exterior") {
            ++count;
        }
    }
    return count;
}

int QueryAPI::getInteriorWallCount() const {
    int count = 0;
    for (const auto& wall : m_doc.walls) {
        if (wall.category == "interior" || wall.category == "wet_wall") {
            ++count;
        }
    }
    return count;
}

float QueryAPI::getTotalExteriorWallLength() const {
    float total = 0.0f;
    for (const auto& wall : m_doc.walls) {
        if (wall.category == "exterior") {
            total += wall.length();
        }
    }
    return total;
}

float QueryAPI::getTotalWindowArea() const {
    float total = 0.0f;
    for (const auto& window : m_doc.windows) {
        total += window.width * window.height;
    }
    return total;
}

} // namespace archgeometry
