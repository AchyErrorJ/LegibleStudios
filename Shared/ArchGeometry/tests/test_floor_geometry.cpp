/**
 * @file test_floor_geometry.cpp
 * @brief Unit tests for floor geometry generation
 *
 * These tests verify the CORRECT interpretation of floor coordinates:
 * - start/end define XZ bounds (plan view rectangle)
 * - thickness is Y dimension (vertical slab depth)
 */

#include <gtest/gtest.h>
#include "archgeometry/archgeometry.hpp"

using namespace archgeometry;

class FloorGeometryTest : public ::testing::Test {
protected:
    SchemaFloor createTestFloor() {
        SchemaFloor floor;
        floor.start = Vec3{0.0f, 0.0f, 0.0f};
        floor.end = Vec3{5000.0f, 0.0f, 4000.0f};
        floor.thickness = 150.0f;
        floor.level_name = "Level 1";
        floor.room = "living_room";
        floor.material = "hardwood";
        return floor;
    }
};

TEST_F(FloorGeometryTest, GetWidthReturnsXDimension) {
    SchemaFloor floor = createTestFloor();

    // Width is X dimension (end.x - start.x)
    float width = FloorGeometryGenerator::getWidth(floor);
    EXPECT_FLOAT_EQ(width, 5000.0f);
}

TEST_F(FloorGeometryTest, GetDepthReturnsZDimension) {
    // CRITICAL TEST: Depth is Z dimension, NOT thickness!
    SchemaFloor floor = createTestFloor();

    float depth = FloorGeometryGenerator::getDepth(floor);
    EXPECT_FLOAT_EQ(depth, 4000.0f);  // Z extent, not thickness
    EXPECT_NE(depth, floor.thickness);  // Must be different from thickness
}

TEST_F(FloorGeometryTest, GetElevationReturnsYCoordinate) {
    SchemaFloor floor = createTestFloor();
    floor.start.y = 2700.0f;  // Second floor

    float elevation = FloorGeometryGenerator::getElevation(floor);
    EXPECT_FLOAT_EQ(elevation, 2700.0f);
}

TEST_F(FloorGeometryTest, GetAreaCalculatesCorrectly) {
    SchemaFloor floor = createTestFloor();

    float area = FloorGeometryGenerator::getArea(floor);
    EXPECT_FLOAT_EQ(area, 5000.0f * 4000.0f);  // Width * Depth
}

TEST_F(FloorGeometryTest, GeneratesFloorMesh) {
    SchemaFloor floor = createTestFloor();

    FloorGeometry geom = FloorGeometryGenerator::generate(floor);

    // Floor slab is a box with 6 faces = 12 triangles
    EXPECT_GT(geom.mesh_3d.vertexCount(), 0);
    EXPECT_EQ(geom.mesh_3d.triangleCount(), 12);
}

TEST_F(FloorGeometryTest, FloorBoundsCorrect) {
    SchemaFloor floor = createTestFloor();

    auto [minBound, maxBound] = FloorGeometryGenerator::getBounds(floor);

    EXPECT_FLOAT_EQ(minBound.x, 0.0f);
    EXPECT_FLOAT_EQ(minBound.y, -150.0f);  // Bottom of slab
    EXPECT_FLOAT_EQ(minBound.z, 0.0f);

    EXPECT_FLOAT_EQ(maxBound.x, 5000.0f);
    EXPECT_FLOAT_EQ(maxBound.y, 0.0f);  // Top of slab
    EXPECT_FLOAT_EQ(maxBound.z, 4000.0f);
}

TEST_F(FloorGeometryTest, FloorCenterCorrect) {
    SchemaFloor floor = createTestFloor();

    Point2D center = FloorGeometryGenerator::getCenter(floor);

    EXPECT_FLOAT_EQ(center.x, 2500.0f);  // Midpoint of X
    EXPECT_FLOAT_EQ(center.y, 2000.0f);  // Midpoint of Z (y in Point2D)
}

TEST_F(FloorGeometryTest, MaterialColorVaries) {
    Vec3 hardwood = FloorGeometryGenerator::getMaterialColor("hardwood");
    Vec3 tile = FloorGeometryGenerator::getMaterialColor("tile");
    Vec3 concrete = FloorGeometryGenerator::getMaterialColor("concrete");

    // Different materials should have different colors
    EXPECT_NE(hardwood.x, tile.x);
    EXPECT_NE(tile.x, concrete.x);
}

TEST_F(FloorGeometryTest, GeneratesPlanPolygon) {
    SchemaFloor floor = createTestFloor();

    FloorGeometry geom = FloorGeometryGenerator::generate(floor);

    ASSERT_EQ(geom.plan_view.polygons.size(), 1);
    EXPECT_EQ(geom.plan_view.polygons[0].points.size(), 4);  // Rectangle
    EXPECT_TRUE(geom.plan_view.polygons[0].closed);
}

TEST_F(FloorGeometryTest, ElementTypeSet) {
    SchemaFloor floor = createTestFloor();

    FloorGeometry geom = FloorGeometryGenerator::generate(floor);

    EXPECT_EQ(geom.mesh_3d.element_type, "floor");
    EXPECT_EQ(geom.plan_view.element_type, "floor");
}
