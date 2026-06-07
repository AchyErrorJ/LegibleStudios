/**
 * @file test_schema_parser.cpp
 * @brief Unit tests for schema parser
 */

#include <gtest/gtest.h>
#include "archgeometry/archgeometry.hpp"

using namespace archgeometry;

class SchemaParserTest : public ::testing::Test {
protected:
    const char* MINIMAL_SCHEMA = R"({
        "version": "1.0.0",
        "building_id": "test_building",
        "unit": "mm",
        "width": 10000,
        "depth": 8000,
        "walls_batch": [
            {
                "start": [0, 0, 0],
                "end": [5000, 0, 0],
                "height": 2700,
                "wall_type": "exterior_2x6",
                "category": "exterior"
            }
        ],
        "wall_types": [
            {
                "id": "exterior_2x6",
                "name": "Exterior 2x6",
                "layers": [
                    {"name": "siding", "material": "vinyl", "thickness": 12},
                    {"name": "sheathing", "material": "osb", "thickness": 11},
                    {"name": "stud", "material": "wood", "thickness": 140},
                    {"name": "drywall", "material": "gypsum", "thickness": 13}
                ]
            }
        ],
        "rooms": {
            "living_room": {
                "name": "Living Room",
                "room_type": "living",
                "zone": "living",
                "level": "Level 1",
                "bounds": {"x": 0, "y": 0, "width": 5000, "height": 4000},
                "area": 20000000
            }
        }
    })";
};

TEST_F(SchemaParserTest, ParsesMinimalSchema) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    EXPECT_EQ(doc.version, "1.0.0");
    EXPECT_EQ(doc.building_id, "test_building");
    EXPECT_EQ(doc.width, 10000);
    EXPECT_EQ(doc.depth, 8000);
}

TEST_F(SchemaParserTest, ParsesWalls) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    ASSERT_EQ(doc.walls.size(), 1);

    const auto& wall = doc.walls[0];
    EXPECT_FLOAT_EQ(wall.start.x, 0.0f);
    EXPECT_FLOAT_EQ(wall.end.x, 5000.0f);
    EXPECT_FLOAT_EQ(wall.height, 2700.0f);
    EXPECT_EQ(wall.category, "exterior");
}

TEST_F(SchemaParserTest, ParsesWallTypes) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    ASSERT_EQ(doc.wall_types.size(), 1);

    auto it = doc.wall_types.find("exterior_2x6");
    ASSERT_NE(it, doc.wall_types.end());

    const auto& wallType = it->second;
    EXPECT_EQ(wallType.layers.size(), 4);

    // Total thickness should be sum of layers
    float totalThickness = wallType.totalThickness();
    EXPECT_FLOAT_EQ(totalThickness, 12 + 11 + 140 + 13);  // 176mm
}

TEST_F(SchemaParserTest, ParsesRooms) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    ASSERT_EQ(doc.rooms.size(), 1);

    auto it = doc.rooms.find("living_room");
    ASSERT_NE(it, doc.rooms.end());

    const auto& room = it->second;
    EXPECT_EQ(room.name, "Living Room");
    EXPECT_EQ(room.room_type, "living");
    EXPECT_FLOAT_EQ(room.bounds.width, 5000.0f);
    EXPECT_FLOAT_EQ(room.bounds.height, 4000.0f);  // This is Z extent!
}

TEST_F(SchemaParserTest, RejectsInvalidJson) {
    auto result = SchemaParser::parseJson("{ invalid json }");
    ASSERT_TRUE(std::holds_alternative<ParseError>(result));
}

TEST_F(SchemaParserTest, ValidationPassesForValidDoc) {
    auto parseResult = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(parseResult));

    const auto& doc = std::get<SchemaDocument>(parseResult);
    auto validResult = SchemaParser::validate(doc);
    EXPECT_TRUE(std::holds_alternative<bool>(validResult));
}

TEST_F(SchemaParserTest, WallLengthCalculation) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    float length = doc.walls[0].length();
    EXPECT_FLOAT_EQ(length, 5000.0f);
}

TEST_F(SchemaParserTest, WallDirectionCalculation) {
    auto result = SchemaParser::parseJson(MINIMAL_SCHEMA);
    ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));

    const auto& doc = std::get<SchemaDocument>(result);
    Vec2 dir = doc.walls[0].direction();
    EXPECT_FLOAT_EQ(dir.x, 1.0f);  // Wall runs along X axis
    EXPECT_FLOAT_EQ(dir.y, 0.0f);
}
