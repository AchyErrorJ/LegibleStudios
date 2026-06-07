/**
 * @file py_archgeometry.cpp
 * @brief Python bindings for ArchGeometry library using pybind11
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "archgeometry/archgeometry.hpp"

namespace py = pybind11;
using namespace archgeometry;

//==============================================================================
// Helper Functions
//==============================================================================

// Convert Mesh3D vertices to numpy array
py::array_t<float> mesh_vertices_to_numpy(const Mesh3D& mesh) {
    size_t n = mesh.vertices.size();
    py::array_t<float> result({n, size_t(3)});
    auto buf = result.mutable_unchecked<2>();
    for (size_t i = 0; i < n; ++i) {
        buf(i, 0) = mesh.vertices[i].position.x;
        buf(i, 1) = mesh.vertices[i].position.y;
        buf(i, 2) = mesh.vertices[i].position.z;
    }
    return result;
}

// Convert Mesh3D normals to numpy array
py::array_t<float> mesh_normals_to_numpy(const Mesh3D& mesh) {
    size_t n = mesh.vertices.size();
    py::array_t<float> result({n, size_t(3)});
    auto buf = result.mutable_unchecked<2>();
    for (size_t i = 0; i < n; ++i) {
        buf(i, 0) = mesh.vertices[i].normal.x;
        buf(i, 1) = mesh.vertices[i].normal.y;
        buf(i, 2) = mesh.vertices[i].normal.z;
    }
    return result;
}

// Convert Mesh3D colors to numpy array
py::array_t<float> mesh_colors_to_numpy(const Mesh3D& mesh) {
    size_t n = mesh.vertices.size();
    py::array_t<float> result({n, size_t(3)});
    auto buf = result.mutable_unchecked<2>();
    for (size_t i = 0; i < n; ++i) {
        buf(i, 0) = mesh.vertices[i].color.x;
        buf(i, 1) = mesh.vertices[i].color.y;
        buf(i, 2) = mesh.vertices[i].color.z;
    }
    return result;
}

// Convert Mesh3D triangles to numpy array
py::array_t<uint32_t> mesh_indices_to_numpy(const Mesh3D& mesh) {
    size_t n = mesh.triangles.size();
    py::array_t<uint32_t> result({n, size_t(3)});
    auto buf = result.mutable_unchecked<2>();
    for (size_t i = 0; i < n; ++i) {
        buf(i, 0) = mesh.triangles[i].v0;
        buf(i, 1) = mesh.triangles[i].v1;
        buf(i, 2) = mesh.triangles[i].v2;
    }
    return result;
}

// Convert Polygon2D points to numpy array
py::array_t<float> polygon_to_numpy(const Polygon2D& poly) {
    size_t n = poly.points.size();
    py::array_t<float> result({n, size_t(2)});
    auto buf = result.mutable_unchecked<2>();
    for (size_t i = 0; i < n; ++i) {
        buf(i, 0) = poly.points[i].x;
        buf(i, 1) = poly.points[i].y;
    }
    return result;
}

//==============================================================================
// Module Definition
//==============================================================================

PYBIND11_MODULE(archgeometry, m) {
    m.doc() = "ArchGeometry - Shared geometry library for ArchEngine";

    //==========================================================================
    // Basic Types
    //==========================================================================

    py::class_<Vec3>(m, "Vec3")
        .def(py::init<>())
        .def(py::init<float, float, float>())
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    py::class_<Vec2>(m, "Vec2")
        .def(py::init<>())
        .def(py::init<float, float>())
        .def_readwrite("x", &Vec2::x)
        .def_readwrite("y", &Vec2::y)
        .def("length", &Vec2::length)
        .def("perpendicular", &Vec2::perpendicular);

    py::class_<Point2D>(m, "Point2D")
        .def(py::init<>())
        .def(py::init<float, float>())
        .def_readwrite("x", &Point2D::x)
        .def_readwrite("y", &Point2D::y);

    //==========================================================================
    // Schema Types
    //==========================================================================

    py::class_<WallLayer>(m, "WallLayer")
        .def(py::init<>())
        .def_readwrite("name", &WallLayer::name)
        .def_readwrite("material", &WallLayer::material)
        .def_readwrite("thickness", &WallLayer::thickness)
        .def_readwrite("function", &WallLayer::function)
        .def_readwrite("r_value", &WallLayer::r_value);

    py::class_<WallType>(m, "WallType")
        .def(py::init<>())
        .def_readwrite("id", &WallType::id)
        .def_readwrite("name", &WallType::name)
        .def_readwrite("layers", &WallType::layers)
        .def("total_thickness", &WallType::totalThickness);

    py::class_<SchemaWall>(m, "SchemaWall")
        .def(py::init<>())
        .def_readwrite("start", &SchemaWall::start)
        .def_readwrite("end", &SchemaWall::end)
        .def_readwrite("height", &SchemaWall::height)
        .def_readwrite("wall_type", &SchemaWall::wall_type)
        .def_readwrite("category", &SchemaWall::category)
        .def_readwrite("level_name", &SchemaWall::level_name)
        .def_readwrite("is_pinned", &SchemaWall::is_pinned)
        .def("length", &SchemaWall::length)
        .def("direction", &SchemaWall::direction);

    py::class_<SchemaFloor>(m, "SchemaFloor")
        .def(py::init<>())
        .def_readwrite("start", &SchemaFloor::start)
        .def_readwrite("end", &SchemaFloor::end)
        .def_readwrite("thickness", &SchemaFloor::thickness)
        .def_readwrite("level_name", &SchemaFloor::level_name)
        .def_readwrite("room", &SchemaFloor::room)
        .def_readwrite("material", &SchemaFloor::material);

    py::class_<SchemaDoor>(m, "SchemaDoor")
        .def(py::init<>())
        .def_readwrite("wall_index", &SchemaDoor::wall_index)
        .def_readwrite("offset", &SchemaDoor::offset)
        .def_readwrite("width", &SchemaDoor::width)
        .def_readwrite("height", &SchemaDoor::height)
        .def_readwrite("type", &SchemaDoor::type)
        .def_readwrite("swing", &SchemaDoor::swing)
        .def_readwrite("room1", &SchemaDoor::room1)
        .def_readwrite("room2", &SchemaDoor::room2);

    py::class_<SchemaWindow>(m, "SchemaWindow")
        .def(py::init<>())
        .def_readwrite("wall_index", &SchemaWindow::wall_index)
        .def_readwrite("offset", &SchemaWindow::offset)
        .def_readwrite("width", &SchemaWindow::width)
        .def_readwrite("height", &SchemaWindow::height)
        .def_readwrite("sill_height", &SchemaWindow::sill_height)
        .def_readwrite("type", &SchemaWindow::type)
        .def_readwrite("room", &SchemaWindow::room);

    py::class_<RoofSurface>(m, "RoofSurface")
        .def(py::init<>())
        .def_readwrite("id", &RoofSurface::id)
        .def_readwrite("pitch", &RoofSurface::pitch)
        .def_readwrite("orientation", &RoofSurface::orientation)
        .def_readwrite("vertices", &RoofSurface::vertices);

    py::class_<SchemaRoof>(m, "SchemaRoof")
        .def(py::init<>())
        .def_readwrite("id", &SchemaRoof::id)
        .def_readwrite("type", &SchemaRoof::type)
        .def_readwrite("pitch", &SchemaRoof::pitch)
        .def_readwrite("overhang", &SchemaRoof::overhang)
        .def_readwrite("material", &SchemaRoof::material)
        .def_readwrite("surfaces", &SchemaRoof::surfaces);

    py::class_<RoomBounds>(m, "RoomBounds")
        .def(py::init<>())
        .def_readwrite("x", &RoomBounds::x)
        .def_readwrite("y", &RoomBounds::y)
        .def_readwrite("width", &RoomBounds::width)
        .def_readwrite("height", &RoomBounds::height);

    py::class_<SchemaRoom>(m, "SchemaRoom")
        .def(py::init<>())
        .def_readwrite("id", &SchemaRoom::id)
        .def_readwrite("name", &SchemaRoom::name)
        .def_readwrite("room_type", &SchemaRoom::room_type)
        .def_readwrite("zone", &SchemaRoom::zone)
        .def_readwrite("level", &SchemaRoom::level)
        .def_readwrite("bounds", &SchemaRoom::bounds)
        .def_readwrite("area", &SchemaRoom::area)
        .def_readwrite("is_pinned", &SchemaRoom::is_pinned);

    py::class_<SchemaLevel>(m, "SchemaLevel")
        .def(py::init<>())
        .def_readwrite("name", &SchemaLevel::name)
        .def_readwrite("elevation", &SchemaLevel::elevation)
        .def_readwrite("height", &SchemaLevel::height);

    py::class_<SchemaDocument>(m, "SchemaDocument")
        .def(py::init<>())
        .def_readwrite("version", &SchemaDocument::version)
        .def_readwrite("building_id", &SchemaDocument::building_id)
        .def_readwrite("width", &SchemaDocument::width)
        .def_readwrite("depth", &SchemaDocument::depth)
        .def_readwrite("walls", &SchemaDocument::walls)
        .def_readwrite("floors", &SchemaDocument::floors)
        .def_readwrite("doors", &SchemaDocument::doors)
        .def_readwrite("windows", &SchemaDocument::windows)
        .def_readwrite("roofs", &SchemaDocument::roofs)
        .def_readwrite("rooms", &SchemaDocument::rooms)
        .def_readwrite("levels", &SchemaDocument::levels)
        .def_readwrite("wall_types", &SchemaDocument::wall_types);

    //==========================================================================
    // Geometry Types
    //==========================================================================

    py::class_<Mesh3D>(m, "Mesh3D")
        .def(py::init<>())
        .def_readwrite("element_type", &Mesh3D::element_type)
        .def_readwrite("lod_hint", &Mesh3D::lod_hint)
        .def("vertex_count", &Mesh3D::vertexCount)
        .def("triangle_count", &Mesh3D::triangleCount)
        .def("get_vertices", &mesh_vertices_to_numpy,
             "Get vertex positions as numpy array (N, 3)")
        .def("get_normals", &mesh_normals_to_numpy,
             "Get vertex normals as numpy array (N, 3)")
        .def("get_colors", &mesh_colors_to_numpy,
             "Get vertex colors as numpy array (N, 3)")
        .def("get_indices", &mesh_indices_to_numpy,
             "Get triangle indices as numpy array (N, 3)");

    py::class_<Polygon2D>(m, "Polygon2D")
        .def(py::init<>())
        .def_readwrite("layer", &Polygon2D::layer)
        .def_readwrite("closed", &Polygon2D::closed)
        .def_readwrite("fill_pattern", &Polygon2D::fill_pattern)
        .def_readwrite("fill_color", &Polygon2D::fill_color)
        .def("get_points", &polygon_to_numpy,
             "Get polygon points as numpy array (N, 2)");

    py::class_<Geometry2D>(m, "Geometry2D")
        .def(py::init<>())
        .def_readwrite("element_type", &Geometry2D::element_type)
        .def_readwrite("polygons", &Geometry2D::polygons);

    py::class_<WallGeometry>(m, "WallGeometry")
        .def(py::init<>())
        .def_readwrite("wall_id", &WallGeometry::wall_id)
        .def_readwrite("mesh_3d", &WallGeometry::mesh_3d)
        .def_readwrite("plan_view", &WallGeometry::plan_view);

    py::class_<FloorGeometry>(m, "FloorGeometry")
        .def(py::init<>())
        .def_readwrite("floor_id", &FloorGeometry::floor_id)
        .def_readwrite("room_id", &FloorGeometry::room_id)
        .def_readwrite("mesh_3d", &FloorGeometry::mesh_3d)
        .def_readwrite("plan_view", &FloorGeometry::plan_view);

    py::class_<RoofGeometry>(m, "RoofGeometry")
        .def(py::init<>())
        .def_readwrite("roof_id", &RoofGeometry::roof_id)
        .def_readwrite("mesh_3d", &RoofGeometry::mesh_3d)
        .def_readwrite("plan_view", &RoofGeometry::plan_view);

    py::class_<DoorGeometry>(m, "DoorGeometry")
        .def(py::init<>())
        .def_readwrite("door_type", &DoorGeometry::door_type)
        .def_readwrite("frame_mesh", &DoorGeometry::frame_mesh)
        .def_readwrite("panel_mesh", &DoorGeometry::panel_mesh)
        .def_readwrite("plan_symbol", &DoorGeometry::plan_symbol);

    py::class_<WindowGeometry>(m, "WindowGeometry")
        .def(py::init<>())
        .def_readwrite("window_type", &WindowGeometry::window_type)
        .def_readwrite("frame_mesh", &WindowGeometry::frame_mesh)
        .def_readwrite("glass_mesh", &WindowGeometry::glass_mesh)
        .def_readwrite("plan_symbol", &WindowGeometry::plan_symbol);

    py::class_<RoomBoundary>(m, "RoomBoundary")
        .def(py::init<>())
        .def_readwrite("room_id", &RoomBoundary::room_id)
        .def_readwrite("room_name", &RoomBoundary::room_name)
        .def_readwrite("room_type", &RoomBoundary::room_type)
        .def_readwrite("polygon", &RoomBoundary::polygon)
        .def_readwrite("area", &RoomBoundary::area)
        .def_readwrite("centroid", &RoomBoundary::centroid);

    py::class_<BuildingGeometry>(m, "BuildingGeometry")
        .def(py::init<>())
        .def_readwrite("building_id", &BuildingGeometry::building_id)
        .def_readwrite("walls", &BuildingGeometry::walls)
        .def_readwrite("floors", &BuildingGeometry::floors)
        .def_readwrite("roofs", &BuildingGeometry::roofs)
        .def_readwrite("doors", &BuildingGeometry::doors)
        .def_readwrite("windows", &BuildingGeometry::windows)
        .def_readwrite("rooms", &BuildingGeometry::rooms);

    //==========================================================================
    // Parse Error
    //==========================================================================

    py::class_<ParseError>(m, "ParseError")
        .def(py::init<>())
        .def_readwrite("message", &ParseError::message)
        .def_readwrite("line", &ParseError::line)
        .def_readwrite("column", &ParseError::column)
        .def("__repr__", [](const ParseError& e) {
            return "ParseError: " + e.message;
        });

    //==========================================================================
    // Parser Functions
    //==========================================================================

    m.def("parse_json", [](const std::string& json_string) {
        auto result = SchemaParser::parseJson(json_string);
        if (std::holds_alternative<ParseError>(result)) {
            throw py::value_error(std::get<ParseError>(result).message);
        }
        return std::get<SchemaDocument>(result);
    }, "Parse JSON string into SchemaDocument", py::arg("json_string"));

    m.def("parse_file", [](const std::string& file_path) {
        auto result = SchemaParser::parseFile(file_path);
        if (std::holds_alternative<ParseError>(result)) {
            throw py::value_error(std::get<ParseError>(result).message);
        }
        return std::get<SchemaDocument>(result);
    }, "Parse JSON file into SchemaDocument", py::arg("file_path"));

    //==========================================================================
    // High-Level API
    //==========================================================================

    m.def("generate_from_json", [](const std::string& json_string) {
        auto result = ArchGeometry::generateFromJson(json_string);
        if (std::holds_alternative<ParseError>(result)) {
            throw py::value_error(std::get<ParseError>(result).message);
        }
        return std::get<BuildingGeometry>(result);
    }, "Parse JSON and generate all building geometry", py::arg("json_string"));

    m.def("generate_from_file", [](const std::string& file_path) {
        auto result = ArchGeometry::generateFromFile(file_path);
        if (std::holds_alternative<ParseError>(result)) {
            throw py::value_error(std::get<ParseError>(result).message);
        }
        return std::get<BuildingGeometry>(result);
    }, "Load JSON file and generate all building geometry", py::arg("file_path"));

    m.def("generate_from_schema", &ArchGeometry::generateFromSchema,
          "Generate geometry from parsed schema document", py::arg("doc"));

    //==========================================================================
    // Query API
    //==========================================================================

    py::class_<QueryAPI>(m, "QueryAPI")
        .def(py::init<const SchemaDocument&>())
        .def("get_walls", &QueryAPI::getWalls,
             py::return_value_policy::reference_internal)
        .def("get_wall_by_index", &QueryAPI::getWallByIndex,
             py::return_value_policy::reference_internal)
        .def("get_room_by_id", &QueryAPI::getRoomById,
             py::return_value_policy::reference_internal)
        .def("get_walls_on_level", &QueryAPI::getWallsOnLevel)
        .def("get_rooms_on_level", &QueryAPI::getRoomsOnLevel)
        .def("get_adjacent_rooms", &QueryAPI::getAdjacentRooms)
        .def("get_walls_for_room", &QueryAPI::getWallsForRoom)
        .def("get_doors_for_wall", &QueryAPI::getDoorsForWall)
        .def("get_windows_for_wall", &QueryAPI::getWindowsForWall)
        .def("get_room_area", &QueryAPI::getRoomArea)
        .def("get_wall_length", &QueryAPI::getWallLength)
        .def("get_wall_thickness", &QueryAPI::getWallThickness)
        .def("get_building_bounds_min", &QueryAPI::getBuildingBoundsMin)
        .def("get_building_bounds_max", &QueryAPI::getBuildingBoundsMax)
        .def("get_wall_count", &QueryAPI::getWallCount)
        .def("get_room_count", &QueryAPI::getRoomCount)
        .def("get_door_count", &QueryAPI::getDoorCount)
        .def("get_window_count", &QueryAPI::getWindowCount);

    //==========================================================================
    // Version Info
    //==========================================================================

    m.def("version", &ArchGeometry::version,
          "Get library version string");

    m.attr("__version__") = ArchGeometry::version();
}
