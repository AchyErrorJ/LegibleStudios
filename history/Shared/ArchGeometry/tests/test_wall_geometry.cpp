/**
 * @file test_wall_geometry.cpp
 * @brief Unit tests for wall geometry generation
 */

#include <gtest/gtest.h>
#include "archgeometry/archgeometry.hpp"

using namespace archgeometry;

class WallGeometryTest : public ::testing::Test {
protected:
    SchemaWall createTestWall(float startX, float startZ, float endX, float endZ) {
        SchemaWall wall;
        wall.start = Vec3{startX, 0.0f, startZ};
        wall.end = Vec3{endX, 0.0f, endZ};
        wall.height = 2700.0f;
        wall.wall_type = "test";
        wall.category = "exterior";
        return wall;
    }

    WallType createTestWallType(float thickness) {
        WallType wt;
        wt.id = "test";
        wt.name = "Test Wall";
        WallLayer layer;
        layer.name = "structure";
        layer.thickness = thickness;
        wt.layers.push_back(layer);
        return wt;
    }
};

TEST_F(WallGeometryTest, GeneratesSolidWall) {
    SchemaWall wall = createTestWall(0, 0, 5000, 0);
    WallType wallType = createTestWallType(150);

    WallGeometry geom = WallGeometryGenerator::generate(wall, wallType, {}, {});

    // Should have vertices and triangles
    EXPECT_GT(geom.mesh_3d.vertexCount(), 0);
    EXPECT_GT(geom.mesh_3d.triangleCount(), 0);

    // Solid wall box has 6 faces, each with 2 triangles = 12 triangles
    EXPECT_EQ(geom.mesh_3d.triangleCount(), 12);
}

TEST_F(WallGeometryTest, WallThicknessFromType) {
    WallType wt;
    wt.id = "multi_layer";
    wt.name = "Multi Layer Wall";

    WallLayer layer1, layer2, layer3;
    layer1.thickness = 12.0f;
    layer2.thickness = 140.0f;
    layer3.thickness = 13.0f;
    wt.layers = {layer1, layer2, layer3};

    float thickness = WallGeometryGenerator::getThickness(wt);
    EXPECT_FLOAT_EQ(thickness, 165.0f);
}

TEST_F(WallGeometryTest, WallLength) {
    SchemaWall wall = createTestWall(0, 0, 3000, 4000);

    float length = WallGeometryGenerator::getLength(wall);
    EXPECT_FLOAT_EQ(length, 5000.0f);  // 3-4-5 triangle
}

TEST_F(WallGeometryTest, WallDirection) {
    SchemaWall wall = createTestWall(0, 0, 3000, 4000);

    Vec2 dir = WallGeometryGenerator::getDirection(wall);
    EXPECT_FLOAT_EQ(dir.x, 0.6f);  // 3/5
    EXPECT_FLOAT_EQ(dir.y, 0.8f);  // 4/5
}

TEST_F(WallGeometryTest, WallCenterline) {
    SchemaWall wall = createTestWall(1000, 2000, 5000, 2000);

    auto [start, end] = WallGeometryGenerator::getCenterline(wall);
    EXPECT_FLOAT_EQ(start.x, 1000.0f);
    EXPECT_FLOAT_EQ(end.x, 5000.0f);
}

TEST_F(WallGeometryTest, GeneratesWithDoorCutout) {
    SchemaWall wall = createTestWall(0, 0, 5000, 0);
    WallType wallType = createTestWallType(150);

    SchemaDoor door;
    door.wall_index = 0;
    door.offset = 2500.0f;
    door.width = 914.0f;
    door.height = 2134.0f;

    WallGeometry geom = WallGeometryGenerator::generate(wall, wallType, {door}, {});

    // Should have more triangles due to segmentation around door
    EXPECT_GT(geom.mesh_3d.triangleCount(), 0);

    // Should have cutout info
    ASSERT_EQ(geom.cutouts.size(), 1);
    EXPECT_EQ(geom.cutouts[0].opening_type, "door");
    EXPECT_FLOAT_EQ(geom.cutouts[0].width, 914.0f);
}

TEST_F(WallGeometryTest, GeneratesWithWindowCutout) {
    SchemaWall wall = createTestWall(0, 0, 5000, 0);
    WallType wallType = createTestWallType(150);

    SchemaWindow window;
    window.wall_index = 0;
    window.offset = 2500.0f;
    window.width = 1200.0f;
    window.height = 1200.0f;
    window.sill_height = 900.0f;

    WallGeometry geom = WallGeometryGenerator::generate(wall, wallType, {}, {window});

    // Should have cutout info
    ASSERT_EQ(geom.cutouts.size(), 1);
    EXPECT_EQ(geom.cutouts[0].opening_type, "window");
    EXPECT_FLOAT_EQ(geom.cutouts[0].bottom_height, 900.0f);
}

TEST_F(WallGeometryTest, GeneratesPlanPolygon) {
    SchemaWall wall = createTestWall(0, 0, 5000, 0);
    WallType wallType = createTestWallType(150);

    WallGeometry geom = WallGeometryGenerator::generate(wall, wallType, {}, {});

    // Should have plan view polygon
    ASSERT_EQ(geom.plan_view.polygons.size(), 1);
    EXPECT_EQ(geom.plan_view.polygons[0].points.size(), 4);  // Rectangle
    EXPECT_TRUE(geom.plan_view.polygons[0].closed);
}

TEST_F(WallGeometryTest, CategoryColor) {
    Vec3 extColor = WallGeometryGenerator::getCategoryColor("exterior");
    Vec3 intColor = WallGeometryGenerator::getCategoryColor("interior");
    Vec3 wetColor = WallGeometryGenerator::getCategoryColor("wet_wall");

    // Colors should be different for different categories
    EXPECT_NE(extColor.x, intColor.x);
    EXPECT_NE(intColor.x, wetColor.x);
}
