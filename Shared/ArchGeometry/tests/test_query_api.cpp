/**
 * @file test_query_api.cpp
 * @brief Unit tests for query API
 */

#include <gtest/gtest.h>
#include "archgeometry/archgeometry.hpp"

using namespace archgeometry;

class QueryAPITest : public ::testing::Test {
protected:
    const char* TEST_SCHEMA = R"({
        "version": "1.0.0",
        "building_id": "test_house",
        "unit": "mm",
        "width": 12000,
        "depth": 10000,
        "wall_types": [
            {
                "id": "exterior_2x6",
                "name": "Exterior 2x6",
                "layers": [
                    {"name": "structure", "thickness": 176}
                ]
            },
            {
                "id": "interior_2x4",
                "name": "Interior 2x4",
                "layers": [
                    {"name": "structure", "thickness": 114}
                ]
            }
        ],
        "walls_batch": [
            {
                "start": [0, 0, 0],
                "end": [12000, 0, 0],
                "height": 2700,
                "wall_type": "exterior_2x6",
                "category": "exterior",
                "level_name": "Level 1",
                "rooms": ["living_room", ""]
            },
            {
                "start": [12000, 0, 0],
                "end": [12000, 0, 10000],
                "height": 2700,
                "wall_type": "exterior_2x6",
                "category": "exterior",
                "level_name": "Level 1",
                "rooms": ["kitchen", ""]
            },
            {
                "start": [6000, 0, 0],
                "end": [6000, 0, 10000],
                "height": 2700,
                "wall_type": "interior_2x4",
                "category": "interior",
                "level_name": "Level 1",
                "rooms": ["living_room", "kitchen"]
            }
        ],
        "doors": [
            {
                "wall_index": 2,
                "offset": 3000,
                "width": 914,
                "height": 2134,
                "type": "swing",
                "room1": "living_room",
                "room2": "kitchen"
            }
        ],
        "windows": [
            {
                "wall_index": 0,
                "offset": 3000,
                "width": 1200,
                "height": 1200,
                "sill_height": 900,
                "room": "living_room"
            },
            {
                "wall_index": 0,
                "offset": 9000,
                "width": 1200,
                "height": 1200,
                "sill_height": 900,
                "room": "living_room"
            }
        ],
        "rooms": {
            "living_room": {
                "name": "Living Room",
                "room_type": "living",
                "zone": "living",
                "level": "Level 1",
                "bounds": {"x": 0, "y": 0, "width": 6000, "height": 10000}
            },
            "kitchen": {
                "name": "Kitchen",
                "room_type": "kitchen",
                "zone": "service",
                "level": "Level 1",
                "bounds": {"x": 6000, "y": 0, "width": 6000, "height": 10000}
            }
        },
        "levels": [
            {"name": "Level 1", "elevation": 0, "height": 2700}
        ]
    })";

    SchemaDocument doc;

    void SetUp() override {
        auto result = SchemaParser::parseJson(TEST_SCHEMA);
        ASSERT_TRUE(std::holds_alternative<SchemaDocument>(result));
        doc = std::get<SchemaDocument>(result);
    }
};

TEST_F(QueryAPITest, GetWallCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getWallCount(), 3);
}

TEST_F(QueryAPITest, GetRoomCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getRoomCount(), 2);
}

TEST_F(QueryAPITest, GetDoorCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getDoorCount(), 1);
}

TEST_F(QueryAPITest, GetWindowCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getWindowCount(), 2);
}

TEST_F(QueryAPITest, GetWallByIndex) {
    QueryAPI query(doc);

    const SchemaWall* wall = query.getWallByIndex(0);
    ASSERT_NE(wall, nullptr);
    EXPECT_FLOAT_EQ(wall->end.x, 12000.0f);

    // Invalid index returns nullptr
    EXPECT_EQ(query.getWallByIndex(-1), nullptr);
    EXPECT_EQ(query.getWallByIndex(100), nullptr);
}

TEST_F(QueryAPITest, GetRoomById) {
    QueryAPI query(doc);

    const SchemaRoom* room = query.getRoomById("living_room");
    ASSERT_NE(room, nullptr);
    EXPECT_EQ(room->name, "Living Room");

    // Unknown ID returns nullptr
    EXPECT_EQ(query.getRoomById("unknown"), nullptr);
}

TEST_F(QueryAPITest, GetWallsOnLevel) {
    QueryAPI query(doc);

    auto walls = query.getWallsOnLevel("Level 1");
    EXPECT_EQ(walls.size(), 3);

    auto level2Walls = query.getWallsOnLevel("Level 2");
    EXPECT_EQ(level2Walls.size(), 0);
}

TEST_F(QueryAPITest, GetRoomsOnLevel) {
    QueryAPI query(doc);

    auto rooms = query.getRoomsOnLevel("Level 1");
    EXPECT_EQ(rooms.size(), 2);
}

TEST_F(QueryAPITest, GetWallsForRoom) {
    QueryAPI query(doc);

    auto walls = query.getWallsForRoom("living_room");
    EXPECT_EQ(walls.size(), 2);  // Exterior + interior wall
}

TEST_F(QueryAPITest, GetDoorsForWall) {
    QueryAPI query(doc);

    auto doors = query.getDoorsForWall(2);  // Interior wall
    EXPECT_EQ(doors.size(), 1);

    auto noDoors = query.getDoorsForWall(0);  // Exterior wall
    EXPECT_EQ(noDoors.size(), 0);
}

TEST_F(QueryAPITest, GetWindowsForWall) {
    QueryAPI query(doc);

    auto windows = query.getWindowsForWall(0);
    EXPECT_EQ(windows.size(), 2);

    auto noWindows = query.getWindowsForWall(2);
    EXPECT_EQ(noWindows.size(), 0);
}

TEST_F(QueryAPITest, GetWallLength) {
    QueryAPI query(doc);

    float length = query.getWallLength(0);  // 12m wall
    EXPECT_FLOAT_EQ(length, 12000.0f);
}

TEST_F(QueryAPITest, GetWallThickness) {
    QueryAPI query(doc);

    float extThickness = query.getWallThickness(0);  // Exterior wall
    EXPECT_FLOAT_EQ(extThickness, 176.0f);

    float intThickness = query.getWallThickness(2);  // Interior wall
    EXPECT_FLOAT_EQ(intThickness, 114.0f);
}

TEST_F(QueryAPITest, GetRoomArea) {
    QueryAPI query(doc);

    float area = query.getRoomArea("living_room");
    EXPECT_FLOAT_EQ(area, 6000.0f * 10000.0f);  // 60 sqm in sq mm
}

TEST_F(QueryAPITest, GetBuildingBounds) {
    QueryAPI query(doc);

    Vec3 min = query.getBuildingBoundsMin();
    Vec3 max = query.getBuildingBoundsMax();

    EXPECT_FLOAT_EQ(min.x, 0.0f);
    EXPECT_FLOAT_EQ(min.z, 0.0f);
    EXPECT_FLOAT_EQ(max.x, 12000.0f);
    EXPECT_FLOAT_EQ(max.z, 10000.0f);
    EXPECT_FLOAT_EQ(max.y, 2700.0f);  // Wall height
}

TEST_F(QueryAPITest, GetExteriorWallCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getExteriorWallCount(), 2);
}

TEST_F(QueryAPITest, GetInteriorWallCount) {
    QueryAPI query(doc);
    EXPECT_EQ(query.getInteriorWallCount(), 1);
}

TEST_F(QueryAPITest, GetTotalExteriorWallLength) {
    QueryAPI query(doc);
    float length = query.getTotalExteriorWallLength();
    EXPECT_FLOAT_EQ(length, 12000.0f + 10000.0f);  // Two exterior walls
}

TEST_F(QueryAPITest, GetTotalWindowArea) {
    QueryAPI query(doc);
    float area = query.getTotalWindowArea();
    EXPECT_FLOAT_EQ(area, 2 * 1200.0f * 1200.0f);  // Two identical windows
}

TEST_F(QueryAPITest, GetAdjacentRooms) {
    QueryAPI query(doc);

    auto adjacent = query.getAdjacentRooms("living_room");
    ASSERT_EQ(adjacent.size(), 1);
    EXPECT_EQ(adjacent[0]->id, "kitchen");
}
