#pragma once
/**
 * @file query_api.hpp
 * @brief Query interface for schema elements and geometry
 */

#include "schema_types.hpp"
#include "geometry_types.hpp"
#include <vector>
#include <optional>

namespace archgeometry {

/**
 * @brief Query API for schema document
 *
 * Provides convenient access to schema elements and computed properties.
 * This is the recommended interface for consumers that need to query
 * the building data.
 */
class QueryAPI {
public:
    /**
     * @brief Construct query API for a schema document
     * @param doc Reference to schema document (must outlive QueryAPI)
     */
    explicit QueryAPI(const SchemaDocument& doc);

    //==========================================================================
    // Element Access
    //==========================================================================

    /// Get all walls
    const std::vector<SchemaWall>& getWalls() const;

    /// Get wall by index
    const SchemaWall* getWallByIndex(int index) const;

    /// Get room by ID
    const SchemaRoom* getRoomById(const std::string& id) const;

    /// Get level by name
    const SchemaLevel* getLevelByName(const std::string& name) const;

    /// Get wall type by ID
    const WallType* getWallTypeById(const std::string& id) const;

    //==========================================================================
    // Spatial Queries
    //==========================================================================

    /// Get all walls on a specific level
    std::vector<const SchemaWall*> getWallsOnLevel(const std::string& level_name) const;

    /// Get all walls within a bounding box
    std::vector<const SchemaWall*> getWallsInBounds(const Vec3& min, const Vec3& max) const;

    /// Get all rooms on a specific level
    std::vector<const SchemaRoom*> getRoomsOnLevel(const std::string& level_name) const;

    /// Find room containing a point (plan view)
    const SchemaRoom* getRoomAtPoint(const Point2D& point) const;

    //==========================================================================
    // Relationship Queries
    //==========================================================================

    /// Get rooms adjacent to a given room
    std::vector<const SchemaRoom*> getAdjacentRooms(const std::string& room_id) const;

    /// Get all walls bounding a room
    std::vector<const SchemaWall*> getWallsForRoom(const std::string& room_id) const;

    /// Get all doors on a wall
    std::vector<const SchemaDoor*> getDoorsForWall(int wall_index) const;

    /// Get all windows on a wall
    std::vector<const SchemaWindow*> getWindowsForWall(int wall_index) const;

    //==========================================================================
    // Geometry Queries
    //==========================================================================

    /// Get room boundary polygon
    RoomBoundary getRoomBoundary(const std::string& room_id) const;

    /// Get room area (computed from bounds)
    float getRoomArea(const std::string& room_id) const;

    /// Get wall length
    float getWallLength(int wall_index) const;

    /// Get wall thickness (from wall type)
    float getWallThickness(int wall_index) const;

    //==========================================================================
    // Building-Level Queries
    //==========================================================================

    /// Get building bounding box minimum
    Vec3 getBuildingBoundsMin() const;

    /// Get building bounding box maximum
    Vec3 getBuildingBoundsMax() const;

    /// Get total floor area (sum of all floors)
    float getTotalFloorArea() const;

    /// Get wall count
    int getWallCount() const;

    /// Get room count
    int getRoomCount() const;

    /// Get floor count
    int getFloorCount() const;

    /// Get door count
    int getDoorCount() const;

    /// Get window count
    int getWindowCount() const;

    //==========================================================================
    // Statistics
    //==========================================================================

    /// Get exterior wall count
    int getExteriorWallCount() const;

    /// Get interior wall count
    int getInteriorWallCount() const;

    /// Get total exterior wall length
    float getTotalExteriorWallLength() const;

    /// Get total window area
    float getTotalWindowArea() const;

private:
    const SchemaDocument& m_doc;
};

} // namespace archgeometry
