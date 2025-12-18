#include "geometry_loader.hpp"
#include <iostream>
#include <cmath>

namespace arch {

void GeometryLoader::addColumn(Building& building, vec3 position, f32 width, f32 depth, f32 height,
                               const std::string& material, f32 stress) {
    StructuralElement col;
    col.type = ElementType::Column;
    col.start = position;
    col.end = position + vec3(0, height, 0);
    col.width = width;
    col.depth = depth;
    col.material = material;
    col.stress = stress;
    col.deflection = 0.0f;
    col.failed = stress > 1.0f;
    building.elements.push_back(col);
}

void GeometryLoader::addBeam(Building& building, vec3 start, vec3 end, f32 width, f32 depth,
                             const std::string& material, f32 stress, f32 deflection) {
    StructuralElement beam;
    beam.type = ElementType::Beam;
    beam.start = start;
    beam.end = end;
    beam.width = width;
    beam.depth = depth;
    beam.material = material;
    beam.stress = stress;
    beam.deflection = deflection;
    beam.failed = stress > 1.0f;
    building.elements.push_back(beam);
}

void GeometryLoader::addFloor(Building& building, vec3 position, f32 width, f32 depth, f32 thickness,
                              const std::string& material) {
    StructuralElement floor;
    floor.type = ElementType::Floor;
    floor.start = position;
    floor.end = position + vec3(width, 0, depth);
    floor.width = width;
    floor.depth = thickness;
    floor.material = material;
    floor.stress = 0.0f;
    floor.deflection = 0.0f;
    floor.failed = false;
    building.elements.push_back(floor);
}

void GeometryLoader::addWall(Building& building, vec3 start, vec3 end, f32 height, f32 thickness,
                             const std::string& material) {
    StructuralElement wall;
    wall.type = ElementType::Wall;
    wall.start = start;
    wall.end = vec3(end.x, start.y + height, end.z);
    wall.width = glm::length(vec2(end.x - start.x, end.z - start.z));
    wall.depth = thickness;
    wall.material = material;
    wall.stress = 0.0f;
    wall.deflection = 0.0f;
    wall.failed = false;
    building.elements.push_back(wall);
}

void GeometryLoader::addDoor(Building& building, vec3 position, f32 width, f32 height, f32 depth,
                             const std::string& material) {
    StructuralElement door;
    door.type = ElementType::Door;
    door.start = position;
    door.end = position + vec3(0, height, 0);
    door.width = width;
    door.depth = depth;
    door.material = material;
    door.stress = 0.0f;
    door.deflection = 0.0f;
    door.failed = false;
    building.elements.push_back(door);
}

void GeometryLoader::addWindow(Building& building, vec3 position, f32 width, f32 height, f32 depth,
                               const std::string& material) {
    StructuralElement window;
    window.type = ElementType::Window;
    window.start = position;
    window.end = position + vec3(0, height, 0);
    window.width = width;
    window.depth = depth;
    window.material = material;
    window.stress = 0.0f;
    window.deflection = 0.0f;
    window.failed = false;
    building.elements.push_back(window);
}

void GeometryLoader::addRoof(Building& building, vec3 position, f32 width, f32 depth, f32 thickness,
                             const std::string& material) {
    StructuralElement roof;
    roof.type = ElementType::Roof;
    roof.start = position;
    roof.end = position + vec3(width, thickness, depth);
    roof.width = width;
    roof.depth = thickness;
    roof.material = material;
    roof.stress = 0.0f;
    roof.deflection = 0.0f;
    roof.failed = false;
    building.elements.push_back(roof);
}

Building GeometryLoader::createSimpleFrame(f32 width, f32 depth, f32 height) {
    Building building;
    building.name = "Simple Frame";

    f32 colWidth = 0.83f;
    f32 colDepth = 0.83f;
    f32 beamWidth = 0.52f;
    f32 beamDepth = 1.0f;

    int colsX = 3;
    int colsZ = 2;
    f32 spacingX = width / (colsX - 1);
    f32 spacingZ = depth / (colsZ - 1);

    for (int x = 0; x < colsX; ++x) {
        for (int z = 0; z < colsZ; ++z) {
            vec3 pos(x * spacingX, 0, z * spacingZ);
            f32 stress = 0.3f + 0.2f * ((float)x / colsX) + 0.1f * ((float)z / colsZ);
            addColumn(building, pos, colWidth, colDepth, height, "steel", stress);
        }
    }

    for (int z = 0; z < colsZ; ++z) {
        for (int x = 0; x < colsX - 1; ++x) {
            vec3 start(x * spacingX, height, z * spacingZ);
            vec3 end((x + 1) * spacingX, height, z * spacingZ);
            f32 stress = 0.5f + 0.15f * x;
            f32 deflection = 0.002f * (1.0f + 0.5f * x);
            addBeam(building, start, end, beamWidth, beamDepth, "steel", stress, deflection);
        }
    }

    for (int x = 0; x < colsX; ++x) {
        for (int z = 0; z < colsZ - 1; ++z) {
            vec3 start(x * spacingX, height, z * spacingZ);
            vec3 end(x * spacingX, height, (z + 1) * spacingZ);
            f32 stress = 0.4f + 0.1f * z;
            addBeam(building, start, end, beamWidth, beamDepth * 0.8f, "steel", stress, 0.001f);
        }
    }

    return building;
}

Building GeometryLoader::createMultiStoryFrame(int stories, f32 width, f32 depth, f32 storyHeight) {
    Building building;
    building.name = "Multi-Story Frame (" + std::to_string(stories) + " floors)";

    f32 colWidth = 0.83f;
    f32 colDepth = 0.83f;
    f32 beamWidth = 0.5f;
    f32 beamDepth = 1.0f;

    int colsX = 4;
    int colsZ = 3;
    f32 spacingX = width / (colsX - 1);
    f32 spacingZ = depth / (colsZ - 1);

    for (int story = 0; story < stories; ++story) {
        f32 baseY = story * storyHeight;
        f32 topY = (story + 1) * storyHeight;
        f32 storyStressFactor = 1.0f - (float)story / stories * 0.4f;

        for (int x = 0; x < colsX; ++x) {
            for (int z = 0; z < colsZ; ++z) {
                vec3 pos(x * spacingX, baseY, z * spacingZ);
                f32 stress = 0.4f * storyStressFactor + 0.1f * ((float)(x + z) / (colsX + colsZ));
                addColumn(building, pos, colWidth, colDepth, storyHeight, "steel", stress);
            }
        }

        for (int z = 0; z < colsZ; ++z) {
            for (int x = 0; x < colsX - 1; ++x) {
                vec3 start(x * spacingX, topY, z * spacingZ);
                vec3 end((x + 1) * spacingX, topY, z * spacingZ);
                f32 stress = 0.5f + 0.1f * storyStressFactor;
                addBeam(building, start, end, beamWidth, beamDepth, "steel", stress, 0.002f);
            }
        }

        for (int x = 0; x < colsX; ++x) {
            for (int z = 0; z < colsZ - 1; ++z) {
                vec3 start(x * spacingX, topY, z * spacingZ);
                vec3 end(x * spacingX, topY, (z + 1) * spacingZ);
                f32 stress = 0.45f + 0.05f * storyStressFactor;
                addBeam(building, start, end, beamWidth, beamDepth * 0.9f, "steel", stress, 0.001f);
            }
        }

        addFloor(building, vec3(0, topY, 0), width, depth, 0.5f, "concrete");
    }

    return building;
}

Building GeometryLoader::createWarehouse(f32 width, f32 depth, f32 height) {
    Building building;
    building.name = "Warehouse";

    f32 colWidth = 1.0f;
    f32 colDepth = 1.0f;
    f32 beamWidth = 0.67f;
    f32 beamDepth = 2.0f;

    int colsX = 5;
    int colsZ = 4;
    f32 spacingX = width / (colsX - 1);
    f32 spacingZ = depth / (colsZ - 1);

    for (int x = 0; x < colsX; ++x) {
        addColumn(building, vec3(x * spacingX, 0, 0), colWidth, colDepth, height, "steel", 0.35f);
        addColumn(building, vec3(x * spacingX, 0, depth), colWidth, colDepth, height, "steel", 0.35f);
    }
    for (int z = 1; z < colsZ - 1; ++z) {
        addColumn(building, vec3(0, 0, z * spacingZ), colWidth, colDepth, height, "steel", 0.35f);
        addColumn(building, vec3(width, 0, z * spacingZ), colWidth, colDepth, height, "steel", 0.35f);
    }

    for (int x = 2; x < colsX - 1; x += 2) {
        for (int z = 1; z < colsZ - 1; z += 2) {
            addColumn(building, vec3(x * spacingX, 0, z * spacingZ), colWidth * 1.2f, colDepth * 1.2f,
                     height, "steel", 0.5f);
        }
    }

    for (int z = 0; z < colsZ; ++z) {
        vec3 start(0, height, z * spacingZ);
        vec3 end(width, height, z * spacingZ);
        f32 stress = 0.6f + 0.1f * ((float)z / colsZ);
        addBeam(building, start, end, beamWidth, beamDepth, "steel", stress, 0.005f);
    }

    for (int x = 0; x < colsX; ++x) {
        vec3 start(x * spacingX, height, 0);
        vec3 end(x * spacingX, height, depth);
        addBeam(building, start, end, beamWidth * 0.8f, beamDepth * 0.8f, "steel", 0.5f, 0.003f);
    }

    return building;
}

Building GeometryLoader::createResidential(f32 width, f32 depth, int stories) {
    Building building;
    building.name = "Residential (" + std::to_string(stories) + " story)";

    f32 studWidth = 0.292f;
    f32 studDepth = 0.125f;
    f32 joistWidth = 0.125f;
    f32 joistDepth = 0.792f;
    f32 storyHeight = 9.0f;

    int postsX = 3;
    int postsZ = 2;
    f32 spacingX = width / (postsX - 1);
    f32 spacingZ = depth / (postsZ - 1);

    for (int story = 0; story < stories; ++story) {
        f32 baseY = story * storyHeight;
        f32 topY = (story + 1) * storyHeight;

        for (int x = 0; x < postsX; ++x) {
            for (int z = 0; z < postsZ; ++z) {
                vec3 pos(x * spacingX, baseY, z * spacingZ);
                addColumn(building, pos, studWidth, studDepth, storyHeight, "wood", 0.3f);
            }
        }

        int numJoists = static_cast<int>(width / 1.33f);
        for (int j = 0; j <= numJoists; ++j) {
            f32 jx = j * (width / numJoists);
            vec3 start(jx, topY, 0);
            vec3 end(jx, topY, depth);
            addBeam(building, start, end, joistWidth, joistDepth, "wood", 0.35f, 0.003f);
        }

        addBeam(building, vec3(0, topY, 0), vec3(width, topY, 0), joistWidth, joistDepth, "wood", 0.25f);
        addBeam(building, vec3(0, topY, depth), vec3(width, topY, depth), joistWidth, joistDepth, "wood", 0.25f);
    }

    return building;
}

Building GeometryLoader::loadFromJSON(const std::string& filepath) {
    Building building;

    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "Failed to open file: " << filepath << "\n";
        return building;
    }

    try {
        json data = json::parse(file);
        from_json(data, building);
    } catch (const std::exception& e) {
        std::cerr << "Failed to parse JSON: " << e.what() << "\n";
    }

    return building;
}

void GeometryLoader::saveToJSON(const std::string& filepath, const Building& building) {
    json data;
    to_json(data, building);

    std::ofstream file(filepath);
    if (file.is_open()) {
        file << data.dump(2);
    } else {
        std::cerr << "Failed to save to: " << filepath << "\n";
    }
}

Building GeometryLoader::loadFromIFC(const std::string& filepath) {
    Building building;
    building.name = "IFC Import";

    std::string tempJson = "X:/tmp/temp_ifc_import.json";
    std::string scriptPath = "X:/ARCH/Software/ArchEngine/scripts/ifc_import.py";
    std::string cmd = "python \"" + scriptPath + "\" \"" + filepath + "\" \"" + tempJson + "\"";

    int result = system(cmd.c_str());
    if (result != 0) {
        std::cerr << "IFC import failed. Make sure ifcopenshell is installed: pip install ifcopenshell\n";
        return building;
    }

    building = loadFromJSON(tempJson);
    std::remove(tempJson.c_str());

    if (building.elements.empty()) {
        std::cerr << "No elements imported from IFC file\n";
    } else {
        std::cout << "Imported " << building.elements.size() << " elements from IFC\n";
    }

    return building;
}

void to_json(json& j, const Building& b) {
    j["name"] = b.name;
    j["elements"] = json::array();

    for (const auto& elem : b.elements) {
        json e;
        e["type"] = static_cast<int>(elem.type);
        e["start"] = {elem.start.x, elem.start.y, elem.start.z};
        e["end"] = {elem.end.x, elem.end.y, elem.end.z};
        e["width"] = elem.width;
        e["depth"] = elem.depth;
        e["material"] = elem.material;
        e["stress"] = elem.stress;
        e["deflection"] = elem.deflection;
        e["failed"] = elem.failed;
        j["elements"].push_back(e);
    }
}

void from_json(const json& j, Building& b) {
    b.name = j.value("name", "Unnamed Building");
    b.elements.clear();

    if (j.contains("elements")) {
        for (const auto& e : j["elements"]) {
            StructuralElement elem;
            elem.type = static_cast<ElementType>(e.value("type", 0));

            if (e.contains("start")) {
                elem.start = {e["start"][0], e["start"][1], e["start"][2]};
            }
            if (e.contains("end")) {
                elem.end = {e["end"][0], e["end"][1], e["end"][2]};
            }

            elem.width = e.value("width", 0.5f);
            elem.depth = e.value("depth", 0.5f);
            elem.material = e.value("material", "steel");
            elem.stress = e.value("stress", 0.0f);
            elem.deflection = e.value("deflection", 0.0f);
            elem.failed = e.value("failed", false);

            // Parse mesh data if present
            if (e.contains("mesh")) {
                const auto& meshData = e["mesh"];
                if (meshData.contains("vertices") && meshData.contains("faces")) {
                    for (const auto& v : meshData["vertices"]) {
                        elem.mesh.vertices.push_back({v[0], v[1], v[2]});
                    }
                    for (const auto& f : meshData["faces"]) {
                        elem.mesh.faces.push_back({f[0], f[1], f[2]});
                    }
                }
            }

            b.elements.push_back(elem);
        }
    }
}

} // namespace arch
