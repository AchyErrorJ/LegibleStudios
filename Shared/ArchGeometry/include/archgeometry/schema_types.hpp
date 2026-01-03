#pragma once
/**
 * @file schema_types.hpp
 * @brief Schema element definitions for ArchEngine JSON format
 *
 * This file defines the canonical C++ types for all elements in the
 * ArchEngine JSON schema. These types are the single source of truth
 * for schema interpretation across all consumers.
 */

#include <string>
#include <vector>
#include <array>
#include <optional>
#include <unordered_map>
#include <cmath>

namespace archgeometry {

//==============================================================================
// Basic Types
//==============================================================================

/// 3D vector (X=width, Y=height/elevation, Z=depth)
struct Vec3 {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;

    Vec3() = default;
    Vec3(float x_, float y_, float z_) : x(x_), y(y_), z(z_) {}

    Vec3 operator+(const Vec3& other) const { return {x + other.x, y + other.y, z + other.z}; }
    Vec3 operator-(const Vec3& other) const { return {x - other.x, y - other.y, z - other.z}; }
    Vec3 operator*(float s) const { return {x * s, y * s, z * s}; }
    Vec3 operator/(float s) const { return {x / s, y / s, z / s}; }

    float length() const { return std::sqrt(x * x + y * y + z * z); }
    float lengthXZ() const { return std::sqrt(x * x + z * z); }
    Vec3 normalized() const {
        float len = length();
        return len > 0.0001f ? *this / len : Vec3{0, 0, 0};
    }

    static float dot(const Vec3& a, const Vec3& b) {
        return a.x * b.x + a.y * b.y + a.z * b.z;
    }

    static Vec3 cross(const Vec3& a, const Vec3& b) {
        return {
            a.y * b.z - a.z * b.y,
            a.z * b.x - a.x * b.z,
            a.x * b.y - a.y * b.x
        };
    }
};

/// 2D vector (for plan views)
struct Vec2 {
    float x = 0.0f;
    float y = 0.0f;

    Vec2() = default;
    Vec2(float x_, float y_) : x(x_), y(y_) {}

    Vec2 operator+(const Vec2& other) const { return {x + other.x, y + other.y}; }
    Vec2 operator-(const Vec2& other) const { return {x - other.x, y - other.y}; }
    Vec2 operator*(float s) const { return {x * s, y * s}; }

    float length() const { return std::sqrt(x * x + y * y); }
    Vec2 normalized() const {
        float len = length();
        return len > 0.0001f ? *this / len : Vec2{0, 0};
    }
    Vec2 perpendicular() const { return {-y, x}; }
};

/// 2D point (alias for clarity in API)
using Point2D = Vec2;

//==============================================================================
// Wall Types
//==============================================================================

/// Wall layer in an assembly
struct WallLayer {
    std::string name;           ///< Layer name (e.g., "Drywall", "OSB Sheathing")
    std::string material;       ///< Material type (e.g., "gypsum", "osb", "fiberglass")
    float thickness = 0.0f;     ///< Thickness in mm
    std::string function;       ///< Layer function: "structure", "insulation", "finish", etc.
    std::array<float, 4> color = {0.9f, 0.9f, 0.9f, 1.0f};  ///< RGBA color
    float r_value = 0.0f;       ///< Thermal R-value
};

/// Wall type definition (assembly of layers)
struct WallType {
    std::string id;             ///< Unique identifier (e.g., "ext_2x6_r21")
    std::string name;           ///< Display name
    std::vector<WallLayer> layers;  ///< Layers ordered exterior to interior

    /// Calculate total thickness from all layers
    float totalThickness() const {
        float total = 0.0f;
        for (const auto& layer : layers) {
            total += layer.thickness;
        }
        return total;
    }

    /// Calculate total R-value
    float totalRValue() const {
        float total = 0.0f;
        for (const auto& layer : layers) {
            total += layer.r_value;
        }
        return total;
    }
};

//==============================================================================
// Schema Elements
//==============================================================================

/// Wall element from schema
struct SchemaWall {
    Vec3 start;                 ///< Start point in 3D (centerline)
    Vec3 end;                   ///< End point in 3D (centerline)
    float height = 2700.0f;     ///< Wall height in mm
    std::string wall_type;      ///< Reference to WallType id
    std::string category;       ///< "exterior", "interior", "wet_wall"
    std::string level_name;     ///< Level this wall belongs to
    std::array<std::string, 2> rooms = {"", ""};  ///< Adjacent room IDs

    // Constraint data
    bool is_pinned = false;
    std::vector<std::string> locked_properties;

    /// Get wall length (XZ plane distance)
    float length() const {
        float dx = end.x - start.x;
        float dz = end.z - start.z;
        return std::sqrt(dx * dx + dz * dz);
    }

    /// Get normalized direction vector in XZ plane
    Vec2 direction() const {
        Vec2 dir{end.x - start.x, end.z - start.z};
        return dir.normalized();
    }
};

/// Floor element from schema
struct SchemaFloor {
    Vec3 start;                 ///< Start corner (X, elevation Y, Z)
    Vec3 end;                   ///< End corner (X, Y, Z) - Y should match start.y
    float thickness = 150.0f;   ///< Floor slab thickness in mm
    std::string level_name;
    std::optional<std::string> room;  ///< Optional room this floor belongs to
    std::string material = "concrete";

    /// Get floor width (X dimension)
    float width() const { return std::abs(end.x - start.x); }

    /// Get floor depth (Z dimension)
    float depth() const { return std::abs(end.z - start.z); }

    /// Get elevation (Y coordinate)
    float elevation() const { return start.y; }

    /// Get floor area in square mm
    float area() const { return width() * depth(); }
};

/// Door element from schema
struct SchemaDoor {
    int wall_index = 0;         ///< Index into walls array
    float offset = 0.0f;        ///< Distance along wall from start (mm)
    float width = 914.0f;       ///< Door width (mm)
    float height = 2134.0f;     ///< Door height (mm)
    std::string type = "swing"; ///< "swing", "pocket", "sliding", "entry", "bifold", "french"
    std::string swing = "left_in";  ///< "left_in", "right_in", "left_out", "right_out"
    std::string room1;          ///< Room on one side
    std::string room2;          ///< Room on other side

    bool is_pinned = false;
    std::vector<std::string> locked_properties;
};

/// Window element from schema
struct SchemaWindow {
    int wall_index = 0;         ///< Index into walls array
    float offset = 0.0f;        ///< Distance along wall from start (mm)
    float width = 1200.0f;      ///< Window width (mm)
    float height = 1200.0f;     ///< Window height (mm)
    float sill_height = 900.0f; ///< Height from floor to window bottom (mm)
    std::string type = "double_hung";  ///< "fixed", "casement", "double_hung", "sliding"
    std::string room;           ///< Room this window is in

    bool is_pinned = false;
    std::vector<std::string> locked_properties;
};

/// Roof ridge line
struct RoofRidge {
    std::string id;
    Vec3 start_point;
    Vec3 end_point;
    float height = 0.0f;        ///< Ridge height above wall top
};

/// Roof surface (slope)
struct RoofSurface {
    std::string id;
    std::vector<Vec3> vertices; ///< 3D polygon vertices
    float pitch = 0.0f;         ///< Pitch in degrees or rise:12
    std::string orientation;    ///< "north", "south", "east", "west"
};

/// Roof element from schema
struct SchemaRoof {
    std::string id;
    std::string type = "gable"; ///< "gable", "hip", "flat", "shed", "mansard"
    float pitch = 6.0f;         ///< Rise per 12" run (e.g., 6 = 6:12)
    float overhang = 600.0f;    ///< Eave overhang in mm
    std::string material = "asphalt_shingle";
    std::string level_name;
    std::vector<RoofRidge> ridges;
    std::vector<RoofSurface> surfaces;
    std::vector<std::string> dormers;   // Future
    std::vector<std::string> skylights; // Future
};

/// Room bounds (2D plan view)
/// NOTE: 'y' here corresponds to Z in 3D space (plan view convention)
struct RoomBounds {
    float x = 0.0f;
    float y = 0.0f;             ///< This is Z in 3D space!
    float width = 0.0f;
    float height = 0.0f;        ///< This is depth in 3D space!
};

/// Room element from schema
struct SchemaRoom {
    std::string id;
    std::string name;
    std::string room_type;      ///< "living", "bedroom", "bathroom", "kitchen", etc.
    RoomBounds bounds;
    float area = 0.0f;          ///< Area in mm^2
    Point2D center;             ///< Centroid in plan view
    std::string zone;           ///< "public", "private", "service", "circulation"
    std::string level = "Level 1";

    bool is_pinned = false;
    std::vector<std::string> locked_properties;
};

/// Level definition
struct SchemaLevel {
    std::string name;
    float elevation = 0.0f;     ///< Y position
    float height = 2700.0f;     ///< Floor-to-floor height
};

//==============================================================================
// Schema Document
//==============================================================================

/// QBD answers (design parameters from conversation)
struct QBDAnswers {
    std::string description;
    std::string building_type = "residential";
    std::string style = "traditional";
    int stories = 1;
    std::string garage;
    std::string roof_type = "gable";
    float roof_pitch = 6.0f;
    std::string roof_material = "asphalt_shingle";
    int sqft = 0;
    int bedrooms = 0;
    int bathrooms = 0;
};

/// Complete schema document
struct SchemaDocument {
    std::string version = "1.0.0";
    std::string building_id;
    float width = 0.0f;         ///< Overall building width (X)
    float depth = 0.0f;         ///< Overall building depth (Z)
    float sqm = 0.0f;
    float sqft = 0.0f;
    std::string unit = "mm";

    std::vector<SchemaWall> walls;
    std::vector<SchemaFloor> floors;
    std::vector<SchemaDoor> doors;
    std::vector<SchemaWindow> windows;
    std::vector<SchemaRoof> roofs;
    std::unordered_map<std::string, SchemaRoom> rooms;
    std::vector<SchemaLevel> levels;
    std::unordered_map<std::string, WallType> wall_types;

    QBDAnswers qbd_answers;

    // Summary stats
    struct {
        int total_walls = 0;
        int exterior_walls = 0;
        int interior_walls = 0;
        int doors_count = 0;
        int windows_count = 0;
        int rooms_placed = 0;
    } summary;
};

} // namespace archgeometry
