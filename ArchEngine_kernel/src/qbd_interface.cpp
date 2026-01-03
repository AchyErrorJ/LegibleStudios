#include "qbd_interface.hpp"
#include <fstream>
#include <sstream>
#include <filesystem>
#include <iostream>
#include <chrono>
#include <iomanip>
#include <nlohmann/json.hpp>
#include "mesh.hpp"

using json = nlohmann::json;

namespace arch {
namespace qbd {

// ============================================================================
// CONSTRUCTOR / DESTRUCTOR
// ============================================================================

QBDInterface::QBDInterface() {
    initDefaultWallTypes();
}

QBDInterface::~QBDInterface() = default;

void QBDInterface::initDefaultWallTypes() {
    // Default exterior wall (2x6 with insulation)
    m_exteriorWallType.id = "ext_2x6_r21";
    m_exteriorWallType.name = "2x6 Exterior Wall R-21";
    m_exteriorWallType.intent.rValueTarget = 21.0f;
    m_exteriorWallType.intent.structuralRole = "load_bearing";
    m_exteriorWallType.intent.climateZone = "Zone 6";

    // Layer thicknesses in mm
    m_exteriorWallType.layers = {
        {"Vinyl Siding", "vinyl", LayerFunction::ExteriorFinish, 6.0f, {0.8f, 0.8f, 0.85f}, 0.5f, {}},
        {"OSB Sheathing", "osb", LayerFunction::Sheathing, 11.0f, {0.7f, 0.6f, 0.4f}, 0.5f, {}},
        {"2x6 Stud + R-21 Batt", "fiberglass", LayerFunction::Structure, 140.0f, {1.0f, 0.9f, 0.7f}, 21.0f, {}},
        {"6mil Poly Vapor Barrier", "polyethylene", LayerFunction::Membrane, 0.15f, {0.9f, 0.9f, 0.95f}, 0.0f, {}},
        {"1/2\" Drywall", "gypsum", LayerFunction::InteriorFinish, 13.0f, {0.95f, 0.95f, 0.95f}, 0.45f, {}}
    };

    // Default interior wall (2x4)
    m_interiorWallType.id = "int_2x4";
    m_interiorWallType.name = "2x4 Interior Partition";
    m_interiorWallType.intent.structuralRole = "non_bearing";

    // Layer thicknesses in mm
    m_interiorWallType.layers = {
        {"1/2\" Drywall", "gypsum", LayerFunction::InteriorFinish, 13.0f, {0.95f, 0.95f, 0.95f}, 0.45f, {}},
        {"2x4 Stud", "wood", LayerFunction::Structure, 89.0f, {0.9f, 0.8f, 0.6f}, 0.0f, {}},
        {"1/2\" Drywall", "gypsum", LayerFunction::InteriorFinish, 13.0f, {0.95f, 0.95f, 0.95f}, 0.45f, {}}
    };

    // Default wet wall (2x6 for plumbing)
    m_wetWallType.id = "wet_2x6";
    m_wetWallType.name = "2x6 Plumbing Wall";
    m_wetWallType.intent.structuralRole = "non_bearing";

    // Layer thicknesses in mm
    m_wetWallType.layers = {
        {"1/2\" Moisture Resistant Drywall", "gypsum", LayerFunction::InteriorFinish, 13.0f, {0.9f, 0.95f, 0.9f}, 0.45f, {}},
        {"2x6 Stud (Plumbing Chase)", "wood", LayerFunction::Structure, 140.0f, {0.9f, 0.8f, 0.6f}, 0.0f, {}},
        {"1/2\" Moisture Resistant Drywall", "gypsum", LayerFunction::InteriorFinish, 13.0f, {0.9f, 0.95f, 0.9f}, 0.45f, {}}
    };

    m_initialized = true;
}

// ============================================================================
// PARSING HELPERS
// ============================================================================

WallCategory QBDInterface::parseWallCategory(const std::string& cat) {
    if (cat == "exterior") return WallCategory::Exterior;
    if (cat == "wet_wall") return WallCategory::WetWall;
    return WallCategory::Interior;
}

DoorType QBDInterface::parseDoorType(const std::string& type) {
    if (type == "swing" || type == "door") return DoorType::Swing;
    if (type == "entry") return DoorType::Entry;
    if (type == "pocket" || type == "pocket_door") return DoorType::Pocket;
    if (type == "sliding" || type == "sliding_door") return DoorType::Sliding;
    if (type == "bifold") return DoorType::Bifold;
    if (type == "french" || type == "french_door") return DoorType::French;
    if (type == "barn" || type == "barn_door") return DoorType::Barn;
    return DoorType::Swing;
}

DoorSwing QBDInterface::parseDoorSwing(const std::string& swing) {
    if (swing == "left_in") return DoorSwing::LeftIn;
    if (swing == "right_in") return DoorSwing::RightIn;
    if (swing == "left_out") return DoorSwing::LeftOut;
    if (swing == "right_out") return DoorSwing::RightOut;
    if (swing == "left") return DoorSwing::Left;
    if (swing == "right") return DoorSwing::Right;
    return DoorSwing::LeftIn;
}

WindowType QBDInterface::parseWindowType(const std::string& type) {
    if (type == "fixed") return WindowType::Fixed;
    if (type == "casement") return WindowType::Casement;
    if (type == "double_hung") return WindowType::DoubleHung;
    if (type == "sliding") return WindowType::Sliding;
    if (type == "awning") return WindowType::Awning;
    return WindowType::DoubleHung;
}

RoomZone QBDInterface::inferRoomZone(const std::string& roomType) {
    // Private rooms
    if (roomType.find("bedroom") != std::string::npos ||
        roomType.find("bath") != std::string::npos ||
        roomType.find("closet") != std::string::npos) {
        return RoomZone::Private;
    }
    // Service rooms
    if (roomType.find("kitchen") != std::string::npos ||
        roomType.find("laundry") != std::string::npos ||
        roomType.find("garage") != std::string::npos ||
        roomType.find("mudroom") != std::string::npos ||
        roomType.find("pantry") != std::string::npos) {
        return RoomZone::Service;
    }
    // Circulation
    if (roomType.find("hall") != std::string::npos ||
        roomType.find("entry") != std::string::npos ||
        roomType.find("stair") != std::string::npos) {
        return RoomZone::Circulation;
    }
    // Default to public
    return RoomZone::Public;
}

// ============================================================================
// LOADING
// ============================================================================

std::optional<QBDLayout> QBDInterface::loadFromJSON(const std::string& jsonString) {
    try {
        json j = json::parse(jsonString);
        QBDLayout layout;

        // Basic fields
        layout.success = j.value("success", false);
        layout.width = j.value("width", 0.0f);
        layout.depth = j.value("depth", 0.0f);
        layout.sqft = j.value("sqft", 0.0f);
        layout.isComplete = j.value("is_complete", false);
        layout.score = j.value("score", 0.0f);

        // Parse walls
        if (j.contains("walls_batch") && j["walls_batch"].is_array()) {
            for (const auto& wj : j["walls_batch"]) {
                QBDWall wall;

                // QBD uses mm, convert to internal units (also mm for consistency)
                if (wj.contains("start") && wj["start"].is_array() && wj["start"].size() >= 3) {
                    wall.start = vec3(
                        static_cast<f32>(wj["start"][0]),
                        static_cast<f32>(wj["start"][1]),
                        static_cast<f32>(wj["start"][2])
                    );
                }
                if (wj.contains("end") && wj["end"].is_array() && wj["end"].size() >= 3) {
                    wall.end = vec3(
                        static_cast<f32>(wj["end"][0]),
                        static_cast<f32>(wj["end"][1]),
                        static_cast<f32>(wj["end"][2])
                    );
                }

                wall.height = wj.value("height", 2700.0f);  // Default 2700mm (2.7m)
                wall.wallType = wj.value("wall_type", "");
                wall.levelName = wj.value("level_name", "Level 1");
                wall.category = parseWallCategory(wj.value("category", "interior"));

                if (wj.contains("rooms") && wj["rooms"].is_array() && wj["rooms"].size() >= 2) {
                    // Handle null room values
                    if (wj["rooms"][0].is_string()) {
                        wall.room1 = wj["rooms"][0].get<std::string>();
                    }
                    if (wj["rooms"][1].is_string()) {
                        wall.room2 = wj["rooms"][1].get<std::string>();
                    }
                }

                layout.walls.push_back(wall);
            }
        }

        // Parse floors
        // JSON format: floors_batch array with objects containing:
        //   start: [x, y, z] - bottom-left corner in mm (y = floor elevation)
        //   end: [x, y, z] - top-right corner in mm
        //   thickness: floor thickness in mm (default 300)
        //   level_name: string
        //   room: string (optional)
        if (j.contains("floors_batch") && j["floors_batch"].is_array()) {
            std::cout << "[QBD] Found floors_batch with " << j["floors_batch"].size() << " entries\n";
            for (const auto& fj : j["floors_batch"]) {
                QBDFloor floor;

                // Parse start point
                if (fj.contains("start") && fj["start"].is_array() && fj["start"].size() >= 3) {
                    floor.start = vec3(
                        static_cast<f32>(fj["start"][0]),
                        static_cast<f32>(fj["start"][1]),
                        static_cast<f32>(fj["start"][2])
                    );
                }

                // Parse end point
                if (fj.contains("end") && fj["end"].is_array() && fj["end"].size() >= 3) {
                    floor.end = vec3(
                        static_cast<f32>(fj["end"][0]),
                        static_cast<f32>(fj["end"][1]),
                        static_cast<f32>(fj["end"][2])
                    );
                }

                floor.thickness = fj.value("thickness", 300.0f);  // Default 300mm
                floor.levelName = fj.value("level_name", "Level 1");
                if (fj.contains("room") && !fj["room"].is_null()) {
                    floor.room = fj["room"].get<std::string>();
                } else {
                    floor.room = "";
                }

                layout.floors.push_back(floor);
            }
        }

        // Parse doors (new format with wall_index and offset)
        if (j.contains("doors") && j["doors"].is_array()) {
            for (const auto& dj : j["doors"]) {
                QBDDoor door;
                door.wallIndex = dj.value("wall_index", 0);
                door.offset = dj.value("offset", 0.0f);
                door.width = dj.value("width", 900.0f);
                door.height = dj.value("height", 2100.0f);
                door.type = parseDoorType(dj.value("type", "swing"));
                door.swing = parseDoorSwing(dj.value("swing", "left_in"));
                door.room1 = dj.value("room1", "");
                door.room2 = dj.value("room2", "");
                layout.doors.push_back(door);
            }
        }

        // Parse windows
        if (j.contains("windows") && j["windows"].is_array()) {
            for (const auto& wj : j["windows"]) {
                QBDWindow window;
                window.wallIndex = wj.value("wall_index", 0);
                window.offset = wj.value("offset", 0.0f);
                window.width = wj.value("width", 1200.0f);
                window.height = wj.value("height", 1200.0f);
                window.sillHeight = wj.value("sill_height", 900.0f);
                window.type = parseWindowType(wj.value("type", "double_hung"));
                window.room = wj.value("room", "");
                layout.windows.push_back(window);
            }
        }

        // Parse roofs
        if (j.contains("roofs") && j["roofs"].is_array()) {
            for (const auto& rj : j["roofs"]) {
                QBDRoof roof;
                roof.id = rj.value("id", "roof_1");
                roof.pitch = rj.value("pitch", 6.0f);
                roof.overhang = rj.value("overhang", 600.0f);
                roof.ridgeHeight = rj.value("ridge_height", 0.0f);

                // Parse roof type
                std::string typeStr = rj.value("type", "gable");
                if (typeStr == "flat") roof.type = RoofType::Flat;
                else if (typeStr == "gable") roof.type = RoofType::Gable;
                else if (typeStr == "hip") roof.type = RoofType::Hip;
                else if (typeStr == "shed") roof.type = RoofType::Shed;
                else if (typeStr == "mansard") roof.type = RoofType::Mansard;
                else if (typeStr == "gambrel") roof.type = RoofType::Gambrel;

                // Parse surfaces
                if (rj.contains("surfaces") && rj["surfaces"].is_array()) {
                    for (const auto& sj : rj["surfaces"]) {
                        QBDRoofSurface surface;
                        surface.id = sj.value("id", "");
                        surface.name = sj.value("name", "");
                        surface.pitch = sj.value("pitch", 0.0f);

                        // Parse vertices array
                        if (sj.contains("vertices") && sj["vertices"].is_array()) {
                            for (const auto& vj : sj["vertices"]) {
                                if (vj.is_array() && vj.size() >= 3) {
                                    surface.vertices.push_back(vec3(
                                        static_cast<f32>(vj[0]),
                                        static_cast<f32>(vj[1]),
                                        static_cast<f32>(vj[2])
                                    ));
                                }
                            }
                        }
                        roof.surfaces.push_back(surface);
                    }
                }

                // Parse ridges
                if (rj.contains("ridges") && rj["ridges"].is_array()) {
                    for (const auto& ridgeJ : rj["ridges"]) {
                        QBDRoofRidge ridge;
                        ridge.id = ridgeJ.value("id", "");
                        ridge.height = ridgeJ.value("height", 0.0f);

                        if (ridgeJ.contains("start_point") && ridgeJ["start_point"].is_array()) {
                            const auto& sp = ridgeJ["start_point"];
                            if (sp.size() >= 3) {
                                ridge.startPoint = vec3(sp[0], sp[1], sp[2]);
                            }
                        }
                        if (ridgeJ.contains("end_point") && ridgeJ["end_point"].is_array()) {
                            const auto& ep = ridgeJ["end_point"];
                            if (ep.size() >= 3) {
                                ridge.endPoint = vec3(ep[0], ep[1], ep[2]);
                            }
                        }
                        roof.ridges.push_back(ridge);
                    }
                }

                // Parse dormers
                if (rj.contains("dormers") && rj["dormers"].is_array()) {
                    for (const auto& dj : rj["dormers"]) {
                        QBDDormer dormer;
                        dormer.id = dj.value("id", "");
                        dormer.type = dj.value("type", "gable");
                        dormer.width = dj.value("width", 1200.0f);
                        dormer.height = dj.value("height", 1500.0f);
                        dormer.depth = dj.value("depth", 900.0f);

                        if (dj.contains("position") && dj["position"].is_array()) {
                            const auto& pos = dj["position"];
                            if (pos.size() >= 3) {
                                dormer.position = vec3(pos[0], pos[1], pos[2]);
                            }
                        }
                        roof.dormers.push_back(dormer);
                    }
                }

                // Parse skylights
                if (rj.contains("skylights") && rj["skylights"].is_array()) {
                    for (const auto& sj : rj["skylights"]) {
                        QBDSkylight skylight;
                        skylight.id = sj.value("id", "");
                        skylight.surfaceId = sj.value("surface_id", "");
                        skylight.width = sj.value("width", 600.0f);
                        skylight.height = sj.value("height", 900.0f);

                        if (sj.contains("position") && sj["position"].is_array()) {
                            const auto& pos = sj["position"];
                            if (pos.size() >= 3) {
                                skylight.position = vec3(pos[0], pos[1], pos[2]);
                            }
                        }
                        roof.skylights.push_back(skylight);
                    }
                }

                layout.roofs.push_back(roof);
            }
        }

        // Parse rooms
        if (j.contains("rooms") && j["rooms"].is_object()) {
            for (auto& [roomId, rj] : j["rooms"].items()) {
                QBDRoom room;
                room.id = roomId;
                room.name = rj.value("name", roomId);
                room.roomType = rj.value("room_type", "");
                room.area = rj.value("area", 0.0f);

                if (rj.contains("bounds")) {
                    room.bounds.x = rj["bounds"].value("x", 0.0f);
                    room.bounds.y = rj["bounds"].value("y", 0.0f);
                    room.bounds.width = rj["bounds"].value("width", 0.0f);
                    room.bounds.height = rj["bounds"].value("height", 0.0f);
                }

                if (rj.contains("center")) {
                    room.center = vec2(rj["center"].value("x", 0.0f),
                                       rj["center"].value("y", 0.0f));
                } else {
                    room.center = room.bounds.center();
                }

                room.zone = inferRoomZone(room.roomType.empty() ? roomId : room.roomType);

                layout.rooms[roomId] = room;
            }
        }

        // Parse unplaced rooms
        if (j.contains("unplaced_rooms") && j["unplaced_rooms"].is_array()) {
            for (const auto& r : j["unplaced_rooms"]) {
                if (r.is_string()) {
                    layout.unplacedRooms.push_back(r.get<std::string>());
                }
            }
        }

        // Parse summary
        if (j.contains("summary")) {
            layout.summary.totalWalls = j["summary"].value("total_walls", 0);
            layout.summary.exteriorWalls = j["summary"].value("exterior_walls", 0);
            layout.summary.interiorWalls = j["summary"].value("interior_walls", 0);
            layout.summary.wetWalls = j["summary"].value("wet_walls", 0);
            layout.summary.doors = j["summary"].value("doors", 0);
            layout.summary.windows = j["summary"].value("windows", 0);
            layout.summary.floors = j["summary"].value("floors", 0);
            layout.summary.roomsPlaced = j["summary"].value("rooms_placed", 0);
            layout.summary.roomsRequested = j["summary"].value("rooms_requested", 0);
        }

        // Parse QBD answers
        if (j.contains("qbd_answers")) {
            auto& aj = j["qbd_answers"];
            layout.answers.buildingType = aj.value("building_type", "residential");
            layout.answers.residenceType = aj.value("res_type", "");
            layout.answers.garage = aj.value("garage", "none");
            layout.answers.style = aj.value("style", "modern");

            // Handle sqft as either number or string
            if (aj.contains("sqft")) {
                if (aj["sqft"].is_number()) {
                    layout.answers.sqft = aj["sqft"].get<int>();
                } else if (aj["sqft"].is_string()) {
                    layout.answers.sqft = std::stoi(aj["sqft"].get<std::string>());
                }
            }

            // Handle bedrooms as either number or string
            if (aj.contains("bedrooms")) {
                if (aj["bedrooms"].is_number()) {
                    layout.answers.bedrooms = aj["bedrooms"].get<int>();
                } else if (aj["bedrooms"].is_string()) {
                    std::string bedStr = aj["bedrooms"].get<std::string>();
                    layout.answers.bedrooms = std::stoi(bedStr.substr(0, 1));
                }
            }

            // Handle bathrooms as either number or string
            if (aj.contains("bathrooms")) {
                if (aj["bathrooms"].is_number()) {
                    layout.answers.bathrooms = aj["bathrooms"].get<float>();
                } else if (aj["bathrooms"].is_string()) {
                    std::string bathStr = aj["bathrooms"].get<std::string>();
                    layout.answers.bathrooms = std::stof(bathStr.substr(0, bathStr.find('+')));
                }
            }

            if (aj.contains("special_rooms")) {
                if (aj["special_rooms"].is_array()) {
                    for (const auto& r : aj["special_rooms"]) {
                        if (r.is_string()) {
                            layout.answers.specialRooms.push_back(r.get<std::string>());
                        }
                    }
                } else if (aj["special_rooms"].is_string()) {
                    layout.answers.specialRooms.push_back(aj["special_rooms"].get<std::string>());
                }
            }
        }

        std::cout << "[QBD] Loaded layout: " << layout.width << "x" << layout.depth
                  << " with " << layout.walls.size() << " walls, "
                  << layout.floors.size() << " floors, "
                  << layout.doors.size() << " doors, "
                  << layout.windows.size() << " windows, "
                  << layout.roofs.size() << " roofs, "
                  << layout.rooms.size() << " rooms" << std::endl;

        return layout;

    } catch (const std::exception& e) {
        std::cerr << "[QBD] Error parsing JSON: " << e.what() << std::endl;
        return std::nullopt;
    }
}

std::optional<QBDLayout> QBDInterface::loadFromFile(const std::string& filepath) {
    try {
        std::ifstream file(filepath);
        if (!file.is_open()) {
            std::cerr << "[QBD] Could not open file: " << filepath << std::endl;
            return std::nullopt;
        }

        std::stringstream buffer;
        buffer << file.rdbuf();
        return loadFromJSON(buffer.str());

    } catch (const std::exception& e) {
        std::cerr << "[QBD] Error loading file: " << e.what() << std::endl;
        return std::nullopt;
    }
}

// ============================================================================
// CONVERSION TO KERNEL TYPES
// ============================================================================

Building QBDInterface::toBuilding(const QBDLayout& layout) {
    Building building;
    building.name = "QBD Generated Building";

    // Convert walls to structural elements (with door/window cutouts)
    for (size_t wallIdx = 0; wallIdx < layout.walls.size(); ++wallIdx) {
        const auto& wall = layout.walls[wallIdx];
        StructuralElement elem;
        elem.type = ElementType::Wall;
        elem.start = wall.start;
        elem.end = vec3(wall.end.x, wall.start.y + wall.height, wall.end.z);
        elem.width = 0.5f;
        elem.depth = 0.5f;

        switch (wall.category) {
            case WallCategory::Exterior:
                elem.depth = m_exteriorWallType.getTotalThickness();
                elem.material = "exterior_wall";
                break;
            case WallCategory::WetWall:
                elem.depth = m_wetWallType.getTotalThickness();
                elem.material = "wet_wall";
                break;
            default:
                elem.depth = m_interiorWallType.getTotalThickness();
                elem.material = "interior_wall";
                break;
        }

        // Collect all openings (doors and windows) for this wall
        std::vector<std::array<f32, 4>> openings;  // {offset, width, bottom, height}

        for (const auto& door : layout.doors) {
            if (door.wallIndex == static_cast<i32>(wallIdx)) {
                openings.push_back({door.offset, door.width, 0.0f, door.height});
            }
        }
        for (const auto& window : layout.windows) {
            if (window.wallIndex == static_cast<i32>(wallIdx)) {
                openings.push_back({window.offset, window.width, window.sillHeight, window.height});
            }
        }

        // Generate wall mesh with all cutouts
        if (!openings.empty()) {
            auto [verts, indices] = Geometry::CSG::wallWithMultipleOpenings(
                wall.start, wall.end, wall.height, elem.depth,
                openings, vec3(0.9f, 0.88f, 0.85f)
            );
            if (!verts.empty() && !indices.empty()) {
                elem.mesh.vertices.clear();
                elem.mesh.faces.clear();
                for (const auto& v : verts) {
                    elem.mesh.vertices.push_back(v.position);
                }
                for (size_t i = 0; i + 2 < indices.size(); i += 3) {
                    elem.mesh.faces.push_back({indices[i], indices[i+1], indices[i+2]});
                }
            }
        }

        building.elements.push_back(elem);
    }

    // Convert floors to structural elements
    for (const auto& floor : layout.floors) {
        StructuralElement elem;
        elem.type = ElementType::Floor;

        // Floor uses start/end to define the rectangle
        // Y is the elevation, thickness is the depth of the floor slab
        elem.start = floor.start;
        elem.end = vec3(floor.end.x, floor.start.y + floor.thickness, floor.end.z);

        // Width and depth are the horizontal dimensions
        elem.width = std::abs(floor.end.x - floor.start.x);
        elem.depth = std::abs(floor.end.z - floor.start.z);

        elem.material = "floor_slab";
        elem.stress = 0.0f;
        elem.deflection = 0.0f;
        elem.failed = false;

        building.elements.push_back(elem);
    }

    // Convert roofs to structural elements with mesh data
    for (const auto& roof : layout.roofs) {
        for (const auto& surface : roof.surfaces) {
            if (surface.vertices.size() < 3) continue;

            StructuralElement elem;
            elem.type = ElementType::Roof;
            elem.material = "roof_shingle";
            elem.stress = 0.0f;
            elem.deflection = 0.0f;
            elem.failed = false;

            // Calculate bounding box for start/end (used for picking/selection)
            vec3 minBound(1e9f), maxBound(-1e9f);
            for (const auto& v : surface.vertices) {
                minBound = glm::min(minBound, v);
                maxBound = glm::max(maxBound, v);
            }
            elem.start = minBound;
            elem.end = maxBound;
            elem.width = maxBound.x - minBound.x;
            elem.depth = maxBound.z - minBound.z;

            // Create mesh data for the surface
            // Vertices are already in mm from JSON
            for (const auto& v : surface.vertices) {
                elem.mesh.vertices.push_back(v);
            }

            // Fan triangulation for convex polygon
            for (size_t i = 1; i + 1 < surface.vertices.size(); i++) {
                elem.mesh.faces.push_back({0, static_cast<u32>(i), static_cast<u32>(i + 1)});
            }

            building.elements.push_back(elem);
        }
    }

    // Convert doors to structural elements
    for (const auto& door : layout.doors) {
        if (door.wallIndex < 0 || door.wallIndex >= static_cast<i32>(layout.walls.size())) continue;

        const auto& wall = layout.walls[door.wallIndex];
        vec3 wallStart = wall.start;
        vec3 wallEnd = wall.end;
        vec3 wallDir = glm::normalize(wallEnd - wallStart);
        f32 wallLength = glm::length(vec2(wallEnd.x - wallStart.x, wallEnd.z - wallStart.z));

        // Position door along wall at offset
        f32 doorOffset = glm::clamp(door.offset, 0.0f, wallLength - door.width);
        vec3 doorCenter = wallStart + wallDir * (doorOffset + door.width * 0.5f);
        doorCenter.y = wall.start.y;  // Door starts at floor level

        StructuralElement elem;
        elem.type = ElementType::Door;
        elem.start = doorCenter - wallDir * (door.width * 0.5f);
        elem.end = doorCenter + wallDir * (door.width * 0.5f);
        elem.end.y = wall.start.y + door.height;
        elem.width = door.width;
        elem.depth = 100.0f;  // Door thickness ~100mm
        elem.material = "door";
        elem.stress = 0.0f;
        elem.deflection = 0.0f;
        elem.failed = false;

        building.elements.push_back(elem);
    }

    // Convert windows to structural elements
    for (const auto& window : layout.windows) {
        if (window.wallIndex < 0 || window.wallIndex >= static_cast<i32>(layout.walls.size())) continue;

        const auto& wall = layout.walls[window.wallIndex];
        vec3 wallStart = wall.start;
        vec3 wallEnd = wall.end;
        vec3 wallDir = glm::normalize(wallEnd - wallStart);
        f32 wallLength = glm::length(vec2(wallEnd.x - wallStart.x, wallEnd.z - wallStart.z));

        // Position window along wall at offset
        f32 windowOffset = glm::clamp(window.offset, 0.0f, wallLength - window.width);
        vec3 windowCenter = wallStart + wallDir * (windowOffset + window.width * 0.5f);
        windowCenter.y = wall.start.y + window.sillHeight;  // Window starts at sill height

        StructuralElement elem;
        elem.type = ElementType::Window;
        elem.start = windowCenter - wallDir * (window.width * 0.5f);
        elem.start.y = wall.start.y + window.sillHeight;
        elem.end = windowCenter + wallDir * (window.width * 0.5f);
        elem.end.y = wall.start.y + window.sillHeight + window.height;
        elem.width = window.width;
        elem.depth = 100.0f;  // Window thickness ~100mm
        elem.material = "window";
        elem.stress = 0.0f;
        elem.deflection = 0.0f;
        elem.failed = false;

        building.elements.push_back(elem);
    }

    // Add wall types
    building.wallTypes = {m_exteriorWallType, m_interiorWallType, m_wetWallType};

    // Convert to parametric walls
    building.parametricWalls = toParametricWalls(layout);

    return building;
}

std::vector<ParametricWall> QBDInterface::toParametricWalls(const QBDLayout& layout) {
    std::vector<ParametricWall> walls;

    for (size_t i = 0; i < layout.walls.size(); i++) {
        const auto& qw = layout.walls[i];

        ParametricWall pw;
        pw.id = "wall_" + std::to_string(i);
        pw.startPoint = vec2(qw.start.x, qw.start.z);
        pw.endPoint = vec2(qw.end.x, qw.end.z);
        pw.baseHeight = qw.start.y;
        pw.topHeight = qw.start.y + qw.height;

        // Assign wall type index based on category
        switch (qw.category) {
            case WallCategory::Exterior: pw.wallTypeIndex = 0; break;
            case WallCategory::WetWall: pw.wallTypeIndex = 2; break;
            default: pw.wallTypeIndex = 1; break;
        }

        walls.push_back(pw);
    }

    return walls;
}

WallType QBDInterface::getWallTypeForCategory(WallCategory category) {
    switch (category) {
        case WallCategory::Exterior: return m_exteriorWallType;
        case WallCategory::WetWall: return m_wetWallType;
        default: return m_interiorWallType;
    }
}

// ============================================================================
// VALIDATION
// ============================================================================

QBDValidationResult QBDInterface::validateLayout(const QBDLayout& layout,
                                                   const std::string& climateZone) {
    QBDValidationResult result;

    auto& obc = obc::getOBCEngine();
    if (!obc.isInitialized() && !m_obcLibraryPath.empty()) {
        obc.initialize(m_obcLibraryPath);
    }

    // Validate each wall
    for (const auto& wall : layout.walls) {
        auto report = validateWall(wall, wall.height);
        result.wallReports.push_back(report);

        result.wallsChecked++;
        if (report.passes()) {
            result.wallsPassed++;
        } else {
            result.wallsFailed++;
        }

        // Track exterior wall area for thermal
        if (wall.category == WallCategory::Exterior) {
            result.totalExteriorWallArea += wall.length() * wall.height;
        }
    }

    // Calculate average R-value for exterior walls
    if (result.totalExteriorWallArea > 0) {
        result.averageRValue = m_exteriorWallType.getTotalRValue();
        f32 requiredR = obc.getMinimumRValue(climateZone, "wall");
        result.thermalCompliance = result.averageRValue >= requiredR;
    }

    // Overall pass/fail
    result.overallPass = (result.wallsFailed == 0) && result.thermalCompliance;

    return result;
}

obc::ComplianceReport QBDInterface::validateWall(const QBDWall& wall, f32 wallHeight) {
    auto& obc = obc::getOBCEngine();

    WallType wallType = getWallTypeForCategory(wall.category);

    return obc.validateWallAssembly(wallType, wallHeight,
                                     wall.category == WallCategory::Exterior,
                                     m_climateZone);
}

std::string QBDValidationResult::getSummary() const {
    std::stringstream ss;
    ss << "=== QBD Validation Summary ===\n";
    ss << "Overall: " << (overallPass ? "PASS" : "FAIL") << "\n";
    ss << "Walls: " << wallsPassed << "/" << wallsChecked << " passed\n";
    ss << "Thermal: R-" << static_cast<int>(averageRValue)
       << " (" << (thermalCompliance ? "PASS" : "FAIL") << ")\n";
    ss << "Exterior Wall Area: " << totalExteriorWallArea << " sqft\n";
    return ss.str();
}

// ============================================================================
// DOCUMENTATION
// ============================================================================

QBDDocumentation QBDInterface::generateDocumentation(const QBDLayout& layout,
                                                       const std::string& projectName) {
    QBDDocumentation docs;
    docs.projectName = projectName;

    // Timestamp
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time), "%Y-%m-%d");
    docs.generatedDate = ss.str();

    auto& slicer = slicer::getSlicer();

    // Generate floor plan
    docs.floorPlan = generateFloorPlan(layout, 4.0f);
    docs.floorPlanSVG = slicer.exportToSVG(docs.floorPlan, 10.0f);
    docs.floorPlanDXF = slicer.exportToDXF(docs.floorPlan);

    // Generate wall details
    docs.wallDetails = generateWallDetails(layout);

    return docs;
}

slicer::SliceResult QBDInterface::generateFloorPlan(const QBDLayout& layout, f32 cutHeight) {
    Building building = toBuilding(layout);
    auto& slicer = slicer::getSlicer();
    slicer::SliceResult result = slicer.generateFloorPlan(building, cutHeight);

    // Add doors to floor plan
    for (const auto& door : layout.doors) {
        if (door.wallIndex < 0 || door.wallIndex >= static_cast<i32>(layout.walls.size())) continue;

        const auto& wall = layout.walls[door.wallIndex];
        vec2 wallStart(wall.start.x, wall.start.z);
        vec2 wallEnd(wall.end.x, wall.end.z);
        vec2 wallDir = glm::normalize(wallEnd - wallStart);
        vec2 wallNormal(-wallDir.y, wallDir.x);

        // Door center position along wall
        vec2 doorCenter = wallStart + wallDir * door.offset;
        f32 halfWidth = door.width * 0.5f;

        // Door opening line (breaks the wall visually with a white rectangle)
        slicer::Polyline2D doorOpening;
        f32 wallThickness = 175.0f;  // Approximate wall thickness in mm
        if (wall.category == WallCategory::Interior) wallThickness = 115.0f;

        vec2 p1 = doorCenter - wallDir * halfWidth - wallNormal * (wallThickness * 0.5f);
        vec2 p2 = doorCenter + wallDir * halfWidth - wallNormal * (wallThickness * 0.5f);
        vec2 p3 = doorCenter + wallDir * halfWidth + wallNormal * (wallThickness * 0.5f);
        vec2 p4 = doorCenter - wallDir * halfWidth + wallNormal * (wallThickness * 0.5f);

        doorOpening.points = {p1, p2, p3, p4};
        doorOpening.closed = true;
        doorOpening.layer = "A-DOOR";
        doorOpening.color = {1.0f, 1.0f, 1.0f};  // White to "cut" wall
        doorOpening.lineWeight = 0.0f;

        // Add as a white fill hatch to cover wall
        slicer::Hatch2D doorFill;
        doorFill.boundaries.push_back(doorOpening);
        doorFill.pattern = "SOLID";
        doorFill.color = {1.0f, 1.0f, 1.0f};
        result.hatches.push_back(doorFill);

        // Door leaf (the actual door panel)
        slicer::Line2D doorLeaf;
        doorLeaf.layer = "A-DOOR";
        doorLeaf.color = {0.0f, 0.0f, 0.0f};
        doorLeaf.lineWeight = 20.0f;  // Thicker for visibility at 0.1 scale

        // Door swing arc (90 degrees)
        slicer::Arc2D swingArc;
        swingArc.layer = "A-DOOR";
        swingArc.color = {0.0f, 0.0f, 0.0f};
        swingArc.lineWeight = 15.0f;  // Thicker for visibility
        swingArc.radius = door.width;

        // Calculate swing based on door swing direction
        bool swingLeft = (door.swing == DoorSwing::LeftIn || door.swing == DoorSwing::LeftOut || door.swing == DoorSwing::Left);
        bool swingIn = (door.swing == DoorSwing::LeftIn || door.swing == DoorSwing::RightIn);

        vec2 hingePos, swingDir;
        if (swingLeft) {
            hingePos = doorCenter - wallDir * halfWidth;
            swingDir = wallDir;
        } else {
            hingePos = doorCenter + wallDir * halfWidth;
            swingDir = -wallDir;
        }

        // Determine which side the door swings to
        vec2 swingNormal = swingIn ? wallNormal : -wallNormal;

        // Door leaf line
        doorLeaf.start = hingePos;
        doorLeaf.end = hingePos + swingNormal * door.width;
        result.lines.push_back(doorLeaf);

        // Swing arc
        swingArc.center = hingePos;
        f32 baseAngle = std::atan2(swingDir.y, swingDir.x);
        f32 swingAngle = std::atan2(swingNormal.y, swingNormal.x);
        swingArc.startAngle = baseAngle;
        swingArc.endAngle = swingAngle;
        result.arcs.push_back(swingArc);

        // For pocket doors, draw a dashed rectangle instead
        if (door.type == DoorType::Pocket || door.type == DoorType::Sliding) {
            result.lines.pop_back();  // Remove the swing door leaf
            result.arcs.pop_back();   // Remove the swing arc

            // Draw pocket door as dashed line in wall
            slicer::Line2D pocketLine;
            pocketLine.start = doorCenter - wallDir * halfWidth;
            pocketLine.end = doorCenter + wallDir * halfWidth;
            pocketLine.layer = "A-DOOR";
            pocketLine.lineType = "dashed";
            pocketLine.lineWeight = 15.0f;  // Thicker for visibility
            pocketLine.color = {0.0f, 0.0f, 0.0f};
            result.lines.push_back(pocketLine);
        }
    }

    // Add windows to floor plan
    for (const auto& window : layout.windows) {
        if (window.wallIndex < 0 || window.wallIndex >= static_cast<i32>(layout.walls.size())) continue;

        const auto& wall = layout.walls[window.wallIndex];
        vec2 wallStart(wall.start.x, wall.start.z);
        vec2 wallEnd(wall.end.x, wall.end.z);
        vec2 wallDir = glm::normalize(wallEnd - wallStart);
        vec2 wallNormal(-wallDir.y, wallDir.x);

        // Window center position along wall
        vec2 windowCenter = wallStart + wallDir * window.offset;
        f32 halfWidth = window.width * 0.5f;

        // Window lines - two parallel lines across the wall
        f32 wallThickness = 175.0f;  // Approximate exterior wall thickness
        f32 lineOffset = wallThickness * 0.3f;

        // Outer line
        slicer::Line2D outerLine;
        outerLine.start = windowCenter - wallDir * halfWidth + wallNormal * lineOffset;
        outerLine.end = windowCenter + wallDir * halfWidth + wallNormal * lineOffset;
        outerLine.layer = "A-GLAZ";
        outerLine.color = {0.0f, 0.0f, 0.0f};
        outerLine.lineWeight = 20.0f;  // Thicker for visibility
        result.lines.push_back(outerLine);

        // Inner line
        slicer::Line2D innerLine;
        innerLine.start = windowCenter - wallDir * halfWidth - wallNormal * lineOffset;
        innerLine.end = windowCenter + wallDir * halfWidth - wallNormal * lineOffset;
        innerLine.layer = "A-GLAZ";
        innerLine.color = {0.0f, 0.0f, 0.0f};
        innerLine.lineWeight = 20.0f;  // Thicker for visibility
        result.lines.push_back(innerLine);

        // End caps
        slicer::Line2D leftCap;
        leftCap.start = windowCenter - wallDir * halfWidth + wallNormal * lineOffset;
        leftCap.end = windowCenter - wallDir * halfWidth - wallNormal * lineOffset;
        leftCap.layer = "A-GLAZ";
        leftCap.color = {0.0f, 0.0f, 0.0f};
        leftCap.lineWeight = 20.0f;  // Thicker for visibility
        result.lines.push_back(leftCap);

        slicer::Line2D rightCap;
        rightCap.start = windowCenter + wallDir * halfWidth + wallNormal * lineOffset;
        rightCap.end = windowCenter + wallDir * halfWidth - wallNormal * lineOffset;
        rightCap.layer = "A-GLAZ";
        rightCap.color = {0.0f, 0.0f, 0.0f};
        rightCap.lineWeight = 20.0f;  // Thicker for visibility
        result.lines.push_back(rightCap);
    }

    return result;
}

std::vector<slicer::WallSectionDetail> QBDInterface::generateWallDetails(const QBDLayout& layout) {
    std::vector<slicer::WallSectionDetail> details;
    auto& slicer = slicer::getSlicer();

    // Generate detail for each unique wall type used
    std::vector<WallType*> usedTypes;

    bool hasExterior = false, hasInterior = false, hasWet = false;
    for (const auto& wall : layout.walls) {
        if (wall.category == WallCategory::Exterior) hasExterior = true;
        if (wall.category == WallCategory::Interior) hasInterior = true;
        if (wall.category == WallCategory::WetWall) hasWet = true;
    }

    if (hasExterior) {
        details.push_back(slicer.generateWallDetail(m_exteriorWallType, 9.0f));
    }
    if (hasInterior) {
        details.push_back(slicer.generateWallDetail(m_interiorWallType, 9.0f));
    }
    if (hasWet) {
        details.push_back(slicer.generateWallDetail(m_wetWallType, 9.0f));
    }

    return details;
}

bool QBDInterface::exportDocumentation(const QBDDocumentation& docs,
                                         const std::string& outputDir) {
    try {
        std::filesystem::path outPath(outputDir);
        std::filesystem::create_directories(outPath);

        // Export floor plan
        std::ofstream svgFile(outPath / "floor_plan.svg");
        svgFile << docs.floorPlanSVG;
        svgFile.close();

        std::ofstream dxfFile(outPath / "floor_plan.dxf");
        dxfFile << docs.floorPlanDXF;
        dxfFile.close();

        // Export wall details
        auto& slicer = slicer::getSlicer();
        int detailNum = 1;
        for (const auto& detail : docs.wallDetails) {
            std::string filename = "wall_detail_" + std::to_string(detailNum++) + ".svg";
            std::ofstream detailFile(outPath / filename);
            detailFile << slicer.wallDetailToSVG(detail);
            detailFile.close();
        }

        std::cout << "[QBD] Documentation exported to: " << outputDir << std::endl;
        return true;

    } catch (const std::exception& e) {
        std::cerr << "[QBD] Error exporting documentation: " << e.what() << std::endl;
        return false;
    }
}

// ============================================================================
// ASSEMBLY ASSIGNMENT
// ============================================================================

void QBDInterface::assignWallAssemblies(QBDLayout& layout) {
    for (auto& wall : layout.walls) {
        switch (wall.category) {
            case WallCategory::Exterior:
                wall.wallType = m_exteriorWallType.id;
                break;
            case WallCategory::WetWall:
                wall.wallType = m_wetWallType.id;
                break;
            default:
                wall.wallType = m_interiorWallType.id;
                break;
        }
    }
}

void QBDInterface::setExteriorWallType(const WallType& type) {
    m_exteriorWallType = type;
}

void QBDInterface::setInteriorWallType(const WallType& type) {
    m_interiorWallType = type;
}

void QBDInterface::setWetWallType(const WallType& type) {
    m_wetWallType = type;
}

// ============================================================================
// CONFIGURATION
// ============================================================================

void QBDInterface::setOBCLibraryPath(const std::string& path) {
    m_obcLibraryPath = path;
    obc::getOBCEngine().initialize(path);
}

void QBDInterface::setClimateZone(const std::string& zone) {
    m_climateZone = zone;
}

// ============================================================================
// GLOBAL INTERFACE
// ============================================================================

QBDInterface& getQBDInterface() {
    static QBDInterface instance;
    return instance;
}

} // namespace qbd
} // namespace arch
