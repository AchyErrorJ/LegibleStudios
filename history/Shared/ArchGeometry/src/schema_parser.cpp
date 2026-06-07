/**
 * @file schema_parser.cpp
 * @brief JSON schema parser implementation
 */

#include "archgeometry/schema_parser.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <sstream>

namespace archgeometry {

using json = nlohmann::json;

//==============================================================================
// Helper Functions
//==============================================================================

namespace {

Vec3 parseVec3(const json& j) {
    if (!j.is_array() || j.size() < 3) {
        return Vec3{0, 0, 0};
    }
    return Vec3{
        j[0].get<float>(),
        j[1].get<float>(),
        j[2].get<float>()
    };
}

std::array<float, 4> parseColor4(const json& j) {
    if (!j.is_array()) {
        return {0.9f, 0.9f, 0.9f, 1.0f};
    }
    std::array<float, 4> color = {0.9f, 0.9f, 0.9f, 1.0f};
    for (size_t i = 0; i < std::min(j.size(), size_t(4)); ++i) {
        color[i] = j[i].get<float>();
    }
    return color;
}

WallLayer parseWallLayer(const json& j) {
    WallLayer layer;
    layer.name = j.value("name", "");
    layer.material = j.value("material", "");
    layer.thickness = j.value("thickness", 0.0f);
    layer.function = j.value("function", "");
    layer.r_value = j.value("r_value", 0.0f);
    if (j.contains("color")) {
        layer.color = parseColor4(j["color"]);
    }
    return layer;
}

WallType parseWallType(const json& j) {
    WallType wt;
    wt.id = j.value("id", "");
    wt.name = j.value("name", "");
    if (j.contains("layers") && j["layers"].is_array()) {
        for (const auto& lj : j["layers"]) {
            wt.layers.push_back(parseWallLayer(lj));
        }
    }
    return wt;
}

SchemaWall parseWall(const json& j) {
    SchemaWall wall;
    if (j.contains("start")) {
        wall.start = parseVec3(j["start"]);
    }
    if (j.contains("end")) {
        wall.end = parseVec3(j["end"]);
    }
    wall.height = j.value("height", 2700.0f);
    wall.wall_type = j.value("wall_type", "");
    wall.category = j.value("category", "interior");
    wall.level_name = j.value("level_name", "Level 1");

    if (j.contains("rooms") && j["rooms"].is_array()) {
        for (size_t i = 0; i < std::min(j["rooms"].size(), size_t(2)); ++i) {
            if (j["rooms"][i].is_string()) {
                wall.rooms[i] = j["rooms"][i].get<std::string>();
            }
        }
    }

    // Constraint data
    wall.is_pinned = j.value("is_pinned", false);
    if (j.contains("locked_properties") && j["locked_properties"].is_array()) {
        for (const auto& prop : j["locked_properties"]) {
            if (prop.is_string()) {
                wall.locked_properties.push_back(prop.get<std::string>());
            }
        }
    }

    return wall;
}

SchemaFloor parseFloor(const json& j) {
    SchemaFloor floor;
    if (j.contains("start")) {
        floor.start = parseVec3(j["start"]);
    }
    if (j.contains("end")) {
        floor.end = parseVec3(j["end"]);
    }
    floor.thickness = j.value("thickness", 150.0f);
    floor.level_name = j.value("level_name", "Level 1");
    if (j.contains("room") && j["room"].is_string()) {
        floor.room = j["room"].get<std::string>();
    }
    floor.material = j.value("material", "concrete");
    return floor;
}

SchemaDoor parseDoor(const json& j) {
    SchemaDoor door;
    door.wall_index = j.value("wall_index", 0);
    door.offset = j.value("offset", 0.0f);
    door.width = j.value("width", 914.0f);
    door.height = j.value("height", 2134.0f);
    door.type = j.value("type", "swing");
    door.swing = j.value("swing", "left_in");
    door.room1 = j.value("room1", "");
    door.room2 = j.value("room2", "");
    door.is_pinned = j.value("is_pinned", false);
    return door;
}

SchemaWindow parseWindow(const json& j) {
    SchemaWindow window;
    window.wall_index = j.value("wall_index", 0);
    window.offset = j.value("offset", 0.0f);
    window.width = j.value("width", 1200.0f);
    window.height = j.value("height", 1200.0f);
    window.sill_height = j.value("sill_height", 900.0f);
    window.type = j.value("type", "double_hung");
    window.room = j.value("room", "");
    window.is_pinned = j.value("is_pinned", false);
    return window;
}

RoofRidge parseRoofRidge(const json& j) {
    RoofRidge ridge;
    ridge.id = j.value("id", "");
    if (j.contains("start_point")) {
        ridge.start_point = parseVec3(j["start_point"]);
    }
    if (j.contains("end_point")) {
        ridge.end_point = parseVec3(j["end_point"]);
    }
    ridge.height = j.value("height", 0.0f);
    return ridge;
}

RoofSurface parseRoofSurface(const json& j) {
    RoofSurface surface;
    surface.id = j.value("id", "");
    surface.pitch = j.value("pitch", 0.0f);
    surface.orientation = j.value("orientation", "");

    if (j.contains("vertices") && j["vertices"].is_array()) {
        for (const auto& vj : j["vertices"]) {
            surface.vertices.push_back(parseVec3(vj));
        }
    }
    return surface;
}

SchemaRoof parseRoof(const json& j) {
    SchemaRoof roof;
    roof.id = j.value("id", "");
    roof.type = j.value("type", "gable");
    roof.pitch = j.value("pitch", 6.0f);
    roof.overhang = j.value("overhang", 600.0f);
    roof.material = j.value("material", "asphalt_shingle");
    roof.level_name = j.value("level_name", "Roof Level");

    if (j.contains("ridges") && j["ridges"].is_array()) {
        for (const auto& rj : j["ridges"]) {
            roof.ridges.push_back(parseRoofRidge(rj));
        }
    }

    if (j.contains("surfaces") && j["surfaces"].is_array()) {
        for (const auto& sj : j["surfaces"]) {
            roof.surfaces.push_back(parseRoofSurface(sj));
        }
    }

    return roof;
}

SchemaRoom parseRoom(const std::string& id, const json& j) {
    SchemaRoom room;
    room.id = id;
    room.name = j.value("name", "");
    room.room_type = j.value("room_type", "");
    room.zone = j.value("zone", "");
    room.level = j.value("level", "Level 1");

    if (j.contains("bounds")) {
        const auto& b = j["bounds"];
        room.bounds.x = b.value("x", 0.0f);
        room.bounds.y = b.value("y", 0.0f);  // Note: This is Z in 3D!
        room.bounds.width = b.value("width", 0.0f);
        room.bounds.height = b.value("height", 0.0f);  // This is depth in 3D!
    }

    room.area = j.value("area", 0.0f);

    if (j.contains("center")) {
        const auto& c = j["center"];
        room.center.x = c.value("x", 0.0f);
        room.center.y = c.value("y", 0.0f);  // Note: This is Z in 3D!
    }

    room.is_pinned = j.value("is_pinned", false);
    if (j.contains("locked_properties") && j["locked_properties"].is_array()) {
        for (const auto& prop : j["locked_properties"]) {
            if (prop.is_string()) {
                room.locked_properties.push_back(prop.get<std::string>());
            }
        }
    }

    return room;
}

SchemaLevel parseLevel(const json& j) {
    SchemaLevel level;
    level.name = j.value("name", "Level 1");
    level.elevation = j.value("elevation", 0.0f);
    level.height = j.value("height", 2700.0f);
    return level;
}

QBDAnswers parseQBDAnswers(const json& j) {
    QBDAnswers answers;
    answers.description = j.value("description", "");
    answers.building_type = j.value("building_type", "residential");
    answers.style = j.value("style", "traditional");
    answers.stories = j.value("stories", 1);
    answers.garage = j.value("garage", "");
    answers.roof_type = j.value("roof_type", "gable");
    answers.roof_pitch = j.value("roof_pitch", 6.0f);
    answers.roof_material = j.value("roof_material", "asphalt_shingle");
    answers.sqft = j.value("sqft", 0);
    answers.bedrooms = j.value("bedrooms", 0);
    answers.bathrooms = j.value("bathrooms", 0);
    return answers;
}

} // anonymous namespace

//==============================================================================
// SchemaParser Implementation
//==============================================================================

ParseResult<SchemaDocument> SchemaParser::parseJson(const std::string& json_string) {
    try {
        json j = json::parse(json_string);
        SchemaDocument doc;

        // Basic metadata
        doc.version = j.value("version", "1.0.0");
        doc.building_id = j.value("building_id", "");
        doc.width = j.value("width", 0.0f);
        doc.depth = j.value("depth", 0.0f);
        doc.sqm = j.value("sqm", 0.0f);
        doc.sqft = j.value("sqft", 0.0f);
        doc.unit = j.value("unit", "mm");

        // Parse wall types
        if (j.contains("wall_types") && j["wall_types"].is_array()) {
            for (const auto& wtj : j["wall_types"]) {
                WallType wt = parseWallType(wtj);
                if (!wt.id.empty()) {
                    doc.wall_types[wt.id] = wt;
                }
            }
        }

        // Parse walls
        if (j.contains("walls_batch") && j["walls_batch"].is_array()) {
            for (const auto& wj : j["walls_batch"]) {
                doc.walls.push_back(parseWall(wj));
            }
        }

        // Parse floors
        if (j.contains("floors_batch") && j["floors_batch"].is_array()) {
            for (const auto& fj : j["floors_batch"]) {
                doc.floors.push_back(parseFloor(fj));
            }
        }

        // Parse doors
        if (j.contains("doors") && j["doors"].is_array()) {
            for (const auto& dj : j["doors"]) {
                doc.doors.push_back(parseDoor(dj));
            }
        }

        // Parse windows
        if (j.contains("windows") && j["windows"].is_array()) {
            for (const auto& wj : j["windows"]) {
                doc.windows.push_back(parseWindow(wj));
            }
        }

        // Parse roofs
        if (j.contains("roofs") && j["roofs"].is_array()) {
            for (const auto& rj : j["roofs"]) {
                doc.roofs.push_back(parseRoof(rj));
            }
        }

        // Parse rooms (object with room IDs as keys)
        if (j.contains("rooms") && j["rooms"].is_object()) {
            for (const auto& [id, rj] : j["rooms"].items()) {
                doc.rooms[id] = parseRoom(id, rj);
            }
        }

        // Parse levels
        if (j.contains("levels") && j["levels"].is_array()) {
            for (const auto& lj : j["levels"]) {
                doc.levels.push_back(parseLevel(lj));
            }
        }

        // Parse QBD answers
        if (j.contains("qbd_answers")) {
            doc.qbd_answers = parseQBDAnswers(j["qbd_answers"]);
        }

        // Parse summary
        if (j.contains("summary")) {
            const auto& s = j["summary"];
            doc.summary.total_walls = s.value("total_walls", static_cast<int>(doc.walls.size()));
            doc.summary.exterior_walls = s.value("exterior_walls", 0);
            doc.summary.interior_walls = s.value("interior_walls", 0);
            doc.summary.doors_count = s.value("doors", static_cast<int>(doc.doors.size()));
            doc.summary.windows_count = s.value("windows", static_cast<int>(doc.windows.size()));
            doc.summary.rooms_placed = s.value("rooms_placed", static_cast<int>(doc.rooms.size()));
        }

        return doc;

    } catch (const json::parse_error& e) {
        return ParseError{
            std::string("JSON parse error: ") + e.what(),
            static_cast<int>(e.byte),
            -1
        };
    } catch (const std::exception& e) {
        return ParseError{std::string("Parse error: ") + e.what(), -1, -1};
    }
}

ParseResult<SchemaDocument> SchemaParser::parseFile(const std::string& file_path) {
    std::ifstream file(file_path);
    if (!file.is_open()) {
        return ParseError{"Failed to open file: " + file_path, -1, -1};
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    return parseJson(buffer.str());
}

ParseResult<bool> SchemaParser::validate(const SchemaDocument& doc) {
    // Basic validation
    if (doc.walls.empty() && doc.floors.empty() && doc.roofs.empty()) {
        return ParseError{"Document has no geometry elements", -1, -1};
    }

    // Validate wall indices in doors/windows
    for (size_t i = 0; i < doc.doors.size(); ++i) {
        if (doc.doors[i].wall_index < 0 ||
            doc.doors[i].wall_index >= static_cast<int>(doc.walls.size())) {
            return ParseError{
                "Door " + std::to_string(i) + " has invalid wall_index: " +
                std::to_string(doc.doors[i].wall_index),
                -1, -1
            };
        }
    }

    for (size_t i = 0; i < doc.windows.size(); ++i) {
        if (doc.windows[i].wall_index < 0 ||
            doc.windows[i].wall_index >= static_cast<int>(doc.walls.size())) {
            return ParseError{
                "Window " + std::to_string(i) + " has invalid wall_index: " +
                std::to_string(doc.windows[i].wall_index),
                -1, -1
            };
        }
    }

    // Validate wall lengths
    for (size_t i = 0; i < doc.walls.size(); ++i) {
        float len = doc.walls[i].length();
        if (len < 1.0f) {
            return ParseError{
                "Wall " + std::to_string(i) + " has zero or negative length",
                -1, -1
            };
        }
    }

    return true;
}

std::string SchemaParser::getVersion(const std::string& json_string) {
    try {
        json j = json::parse(json_string);
        return j.value("version", "1.0.0");
    } catch (...) {
        return "unknown";
    }
}

ParseResult<std::unordered_map<std::string, WallType>>
SchemaParser::parseWallTypes(const std::string& json_string) {
    try {
        json j = json::parse(json_string);
        std::unordered_map<std::string, WallType> result;

        if (j.contains("wall_types") && j["wall_types"].is_array()) {
            for (const auto& wtj : j["wall_types"]) {
                WallType wt = parseWallType(wtj);
                if (!wt.id.empty()) {
                    result[wt.id] = wt;
                }
            }
        }

        return result;

    } catch (const std::exception& e) {
        return ParseError{std::string("Parse error: ") + e.what(), -1, -1};
    }
}

} // namespace archgeometry
