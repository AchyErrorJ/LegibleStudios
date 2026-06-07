/**
 * @file room_geometry.cpp
 * @brief Room boundary computation implementation
 *
 * CRITICAL INTERPRETATION FIX:
 * - bounds.y is the Z coordinate in 3D space (plan view convention)
 * - bounds.height is the depth in Z direction, NOT ceiling height
 * - Point2D uses (x, y) where y represents Z in 3D
 */

#include "archgeometry/room_geometry.hpp"
#include <algorithm>
#include <cmath>

namespace archgeometry {

//==============================================================================
// Public API
//==============================================================================

RoomBoundary RoomGeometryGenerator::generateBoundary(
    const SchemaRoom& room,
    const std::vector<SchemaWall>& walls
) {
    // For now, use bounds-based generation
    // A more sophisticated implementation could trace wall intersections
    RoomBoundary boundary = generateFromBounds(room);

    // Could enhance by finding actual wall boundaries
    // for (const auto& wall : walls) {
    //     if (wall.rooms[0] == room.id || wall.rooms[1] == room.id) {
    //         // Wall bounds this room - could refine boundary
    //     }
    // }

    return boundary;
}

RoomBoundary RoomGeometryGenerator::generateFromBounds(const SchemaRoom& room) {
    RoomBoundary boundary;
    boundary.room_id = room.id;
    boundary.room_name = room.name;
    boundary.room_type = room.room_type;

    // CORRECT INTERPRETATION:
    // bounds.x, bounds.y are plan view coordinates
    // bounds.y is Z in 3D space
    // bounds.width is X extent
    // bounds.height is Z extent (depth)

    float minX = room.bounds.x;
    float maxX = room.bounds.x + room.bounds.width;
    float minZ = room.bounds.y;  // This is Z in 3D!
    float maxZ = room.bounds.y + room.bounds.height;  // This is depth in Z!

    // Create polygon (clockwise for interior)
    Polygon2D poly;
    poly.layer = "rooms";
    poly.points = {
        Point2D{minX, minZ},
        Point2D{maxX, minZ},
        Point2D{maxX, maxZ},
        Point2D{minX, maxZ}
    };
    poly.closed = true;

    // Fill based on zone type
    Vec3 zoneColor = getZoneColor(room.zone);
    poly.fill_pattern = "solid";
    poly.fill_color = {zoneColor.x, zoneColor.y, zoneColor.z, 0.15f};  // Semi-transparent

    boundary.polygon = poly;

    // Calculate area
    boundary.area = room.bounds.width * room.bounds.height;  // Both are in mm

    // Calculate centroid
    boundary.centroid = getCenter(room.bounds);

    return boundary;
}

Point2D RoomGeometryGenerator::getCenter(const RoomBounds& bounds) {
    // CORRECT: bounds.y is Z coordinate in plan view
    return Point2D{
        bounds.x + bounds.width / 2.0f,
        bounds.y + bounds.height / 2.0f  // This represents Z center
    };
}

float RoomGeometryGenerator::getArea(const RoomBounds& bounds) {
    // Area in square millimeters
    return bounds.width * bounds.height;
}

std::pair<Vec3, Vec3> RoomGeometryGenerator::bounds2Dto3D(
    const RoomBounds& bounds,
    float elevation,
    float height
) {
    // CORRECT conversion from 2D bounds to 3D bounding box
    // bounds.y → Z coordinate
    // elevation → Y coordinate (floor level)
    // height → Y extent (ceiling height)

    Vec3 min{
        bounds.x,
        elevation,
        bounds.y  // bounds.y is Z in 3D!
    };

    Vec3 max{
        bounds.x + bounds.width,
        elevation + height,
        bounds.y + bounds.height  // bounds.height is Z extent!
    };

    return {min, max};
}

Text2D RoomGeometryGenerator::generateLabel(const SchemaRoom& room) {
    Text2D label;
    label.layer = "room_labels";

    // Position at room center
    Point2D center = getCenter(room.bounds);
    label.position = center;

    // Room name as primary text
    label.text = room.name;
    if (label.text.empty()) {
        label.text = room.room_type;
    }

    label.font_size = 150.0f;  // mm
    label.alignment = "center";

    // Calculate area for secondary label
    float areaSqMm = room.bounds.width * room.bounds.height;
    float areaSqM = areaSqMm / 1000000.0f;
    float areaSqFt = areaSqM * 10.764f;

    // Could add area as secondary text
    // label.secondary_text = std::to_string((int)areaSqFt) + " sf";

    return label;
}

bool RoomGeometryGenerator::containsPoint(const Point2D& point, const SchemaRoom& room) {
    // Check if point is inside room bounds (rectangular)
    float minX = room.bounds.x;
    float maxX = room.bounds.x + room.bounds.width;
    float minZ = room.bounds.y;  // bounds.y is Z!
    float maxZ = room.bounds.y + room.bounds.height;

    return (point.x >= minX && point.x <= maxX &&
            point.y >= minZ && point.y <= maxZ);  // point.y is Z!
}

Vec3 RoomGeometryGenerator::getZoneColor(const std::string& zone) {
    if (zone == "living" || zone == "public") {
        return {0.9f, 0.95f, 0.85f};   // Light green
    } else if (zone == "sleeping" || zone == "private") {
        return {0.85f, 0.9f, 0.95f};   // Light blue
    } else if (zone == "wet" || zone == "service") {
        return {0.9f, 0.9f, 0.95f};    // Light purple
    } else if (zone == "circulation") {
        return {0.95f, 0.95f, 0.9f};   // Light yellow
    } else if (zone == "utility" || zone == "garage") {
        return {0.9f, 0.9f, 0.9f};     // Light gray
    } else if (zone == "outdoor") {
        return {0.85f, 0.95f, 0.85f};  // Green tint
    } else {
        return {0.95f, 0.95f, 0.95f};  // Default off-white
    }
}

} // namespace archgeometry
