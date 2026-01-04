/**
 * @file opening_geometry.cpp
 * @brief Door and window geometry generation implementation
 */

#include "archgeometry/opening_geometry.hpp"
#include <cmath>

namespace archgeometry {

//==============================================================================
// Door Geometry
//==============================================================================

DoorGeometry OpeningGeometryGenerator::generateDoor(
    const SchemaDoor& door,
    const SchemaWall& wall,
    float wall_thickness
) {
    DoorGeometry result;
    result.door_type = door.type;

    // Calculate door position along wall
    Vec3 position = getOpeningPosition(door.offset, wall);
    Vec2 wallDir = wall.direction();
    Vec2 wallPerp = wallDir.perpendicular();

    // Door frame mesh
    result.frame_mesh = generateDoorFrame(
        position, wallDir, wallPerp,
        door.width, door.height, wall_thickness
    );
    result.frame_mesh.element_type = "door_frame";
    result.frame_mesh.lod_hint = 2;  // Frames can be simplified

    // Door panel mesh (if not open)
    result.panel_mesh = generateDoorPanel(
        position, wallDir, wallPerp,
        door.width, door.height, door.swing
    );
    result.panel_mesh.element_type = "door_panel";
    result.panel_mesh.lod_hint = 2;

    // 2D plan symbol
    result.plan_symbol = generateDoorSymbol(door, wall);

    return result;
}

OpeningCutout OpeningGeometryGenerator::getDoorCutout(
    const SchemaDoor& door,
    const SchemaWall& wall
) {
    OpeningCutout cutout;
    cutout.start_offset = door.offset;
    cutout.width = door.width;
    cutout.height = door.height;
    cutout.bottom_height = 0.0f;  // Doors start at floor level
    cutout.opening_type = "door";
    return cutout;
}

Mesh3D OpeningGeometryGenerator::generateDoorFrame(
    const Vec3& position, const Vec2& wallDir, const Vec2& wallPerp,
    float width, float height, float wall_thickness
) {
    Mesh3D mesh;
    Vec3 frameColor{0.45f, 0.35f, 0.25f};  // Wood brown

    float frameWidth = 50.0f;    // Frame member width
    float frameDepth = 25.0f;    // Frame member depth
    float halfWidth = width / 2.0f;

    // Left jamb
    Vec3 leftBase{
        position.x - wallDir.x * halfWidth,
        position.y,
        position.z - wallDir.y * halfWidth
    };
    generateFrameMember(mesh, leftBase, frameWidth, height, frameDepth, wallDir, wallPerp, frameColor);

    // Right jamb
    Vec3 rightBase{
        position.x + wallDir.x * halfWidth,
        position.y,
        position.z + wallDir.y * halfWidth
    };
    generateFrameMember(mesh, rightBase, frameWidth, height, frameDepth, wallDir, wallPerp, frameColor);

    // Head (top)
    Vec3 headBase{
        position.x - wallDir.x * halfWidth,
        position.y + height - frameWidth,
        position.z - wallDir.y * halfWidth
    };
    generateFrameMemberHorizontal(mesh, headBase, width, frameWidth, frameDepth, wallDir, wallPerp, frameColor);

    return mesh;
}

Mesh3D OpeningGeometryGenerator::generateDoorPanel(
    const Vec3& position, const Vec2& wallDir, const Vec2& wallPerp,
    float width, float height, const std::string& swing
) {
    Mesh3D mesh;
    Vec3 panelColor{0.55f, 0.45f, 0.35f};  // Light wood

    float panelThickness = 44.0f;  // Standard door thickness
    float halfWidth = width / 2.0f;
    float halfThick = panelThickness / 2.0f;

    // Determine panel position based on swing direction
    // For simplicity, show door in closed position
    Vec3 panelBase{
        position.x - wallDir.x * halfWidth + wallPerp.x * halfThick,
        position.y,
        position.z - wallDir.y * halfWidth + wallPerp.y * halfThick
    };

    // Panel corners (closed position, perpendicular to wall)
    Vec3 b0 = panelBase;
    Vec3 b1{b0.x + wallDir.x * width, b0.y, b0.z + wallDir.y * width};
    Vec3 b2{b1.x - wallPerp.x * panelThickness, b1.y, b1.z - wallPerp.y * panelThickness};
    Vec3 b3{b0.x - wallPerp.x * panelThickness, b0.y, b0.z - wallPerp.y * panelThickness};

    Vec3 t0{b0.x, b0.y + height, b0.z};
    Vec3 t1{b1.x, b1.y + height, b1.z};
    Vec3 t2{b2.x, b2.y + height, b2.z};
    Vec3 t3{b3.x, b3.y + height, b3.z};

    // Front face
    Vec3 frontNormal{wallPerp.x, 0, wallPerp.y};
    mesh.addQuad(b0, t0, t1, b1, frontNormal, panelColor);

    // Back face
    Vec3 backNormal{-wallPerp.x, 0, -wallPerp.y};
    mesh.addQuad(b2, t2, t3, b3, backNormal, panelColor);

    // Edges
    mesh.addQuad(b0, b3, t3, t0, Vec3{-wallDir.x, 0, -wallDir.y}, panelColor);
    mesh.addQuad(b1, t1, t2, b2, Vec3{wallDir.x, 0, wallDir.y}, panelColor);
    mesh.addQuad(t0, t3, t2, t1, Vec3{0, 1, 0}, panelColor);

    return mesh;
}

Geometry2D OpeningGeometryGenerator::generateDoorSymbol(
    const SchemaDoor& door,
    const SchemaWall& wall
) {
    Geometry2D symbol;
    symbol.element_type = "door_symbol";

    Vec2 wallDir = wall.direction();
    Vec2 wallPerp = wallDir.perpendicular();
    float halfWidth = door.width / 2.0f;

    // Door position in plan view
    float offset = door.offset;
    Point2D doorCenter{
        wall.start.x + wallDir.x * offset,
        wall.start.z + wallDir.y * offset
    };

    // Door opening line (gap in wall)
    Line2D opening;
    opening.layer = "doors";
    opening.start = Point2D{
        doorCenter.x - wallDir.x * halfWidth,
        doorCenter.y - wallDir.y * halfWidth
    };
    opening.end = Point2D{
        doorCenter.x + wallDir.x * halfWidth,
        doorCenter.y + wallDir.y * halfWidth
    };
    symbol.lines.push_back(opening);

    // Door swing arc
    Arc2D swingArc;
    swingArc.layer = "doors";
    swingArc.radius = door.width;

    // Determine hinge side and swing direction
    bool hingeLeft = (door.swing.find("left") != std::string::npos);
    bool swingIn = (door.swing.find("in") != std::string::npos);

    if (hingeLeft) {
        swingArc.center = opening.start;
        swingArc.start_angle = swingIn ? 0.0f : 180.0f;
        swingArc.end_angle = swingIn ? 90.0f : 270.0f;
    } else {
        swingArc.center = opening.end;
        swingArc.start_angle = swingIn ? 90.0f : 270.0f;
        swingArc.end_angle = swingIn ? 180.0f : 360.0f;
    }

    // Adjust arc angles based on wall direction
    float wallAngle = std::atan2(wallDir.y, wallDir.x) * 180.0f / 3.14159f;
    swingArc.start_angle += wallAngle;
    swingArc.end_angle += wallAngle;

    symbol.arcs.push_back(swingArc);

    // Door panel line (closed position)
    Line2D panelLine;
    panelLine.layer = "doors";
    panelLine.start = opening.start;
    panelLine.end = opening.end;
    symbol.lines.push_back(panelLine);

    return symbol;
}

//==============================================================================
// Window Geometry
//==============================================================================

WindowGeometry OpeningGeometryGenerator::generateWindow(
    const SchemaWindow& window,
    const SchemaWall& wall,
    float wall_thickness
) {
    WindowGeometry result;
    result.window_type = window.type;

    Vec3 position = getOpeningPosition(window.offset, wall);
    position.y += window.sill_height;  // Windows start at sill height

    Vec2 wallDir = wall.direction();
    Vec2 wallPerp = wallDir.perpendicular();

    // Window frame mesh
    result.frame_mesh = generateWindowFrame(
        position, wallDir, wallPerp,
        window.width, window.height, wall_thickness
    );
    result.frame_mesh.element_type = "window_frame";
    result.frame_mesh.lod_hint = 2;

    // Glass pane mesh
    result.glass_mesh = generateWindowGlass(
        position, wallDir, wallPerp,
        window.width, window.height
    );
    result.glass_mesh.element_type = "window_glass";
    result.glass_mesh.lod_hint = 3;  // Glass can be omitted at distance

    // 2D plan symbol
    result.plan_symbol = generateWindowSymbol(window, wall);

    return result;
}

OpeningCutout OpeningGeometryGenerator::getWindowCutout(
    const SchemaWindow& window,
    const SchemaWall& wall
) {
    OpeningCutout cutout;
    cutout.start_offset = window.offset;
    cutout.width = window.width;
    cutout.height = window.height;
    cutout.bottom_height = window.sill_height;
    cutout.opening_type = "window";
    return cutout;
}

Mesh3D OpeningGeometryGenerator::generateWindowFrame(
    const Vec3& position, const Vec2& wallDir, const Vec2& wallPerp,
    float width, float height, float wall_thickness
) {
    Mesh3D mesh;
    Vec3 frameColor{0.9f, 0.9f, 0.92f};  // White/light gray

    float frameWidth = 60.0f;
    float frameDepth = 80.0f;
    float halfWidth = width / 2.0f;

    // Left jamb
    Vec3 leftBase{
        position.x - wallDir.x * halfWidth,
        position.y,
        position.z - wallDir.y * halfWidth
    };
    generateFrameMember(mesh, leftBase, frameWidth, height, frameDepth, wallDir, wallPerp, frameColor);

    // Right jamb
    Vec3 rightBase{
        position.x + wallDir.x * halfWidth,
        position.y,
        position.z + wallDir.y * halfWidth
    };
    generateFrameMember(mesh, rightBase, frameWidth, height, frameDepth, wallDir, wallPerp, frameColor);

    // Sill (bottom)
    Vec3 sillBase{
        position.x - wallDir.x * halfWidth,
        position.y,
        position.z - wallDir.y * halfWidth
    };
    generateFrameMemberHorizontal(mesh, sillBase, width, frameWidth, frameDepth, wallDir, wallPerp, frameColor);

    // Head (top)
    Vec3 headBase{
        position.x - wallDir.x * halfWidth,
        position.y + height - frameWidth,
        position.z - wallDir.y * halfWidth
    };
    generateFrameMemberHorizontal(mesh, headBase, width, frameWidth, frameDepth, wallDir, wallPerp, frameColor);

    return mesh;
}

Mesh3D OpeningGeometryGenerator::generateWindowGlass(
    const Vec3& position, const Vec2& wallDir, const Vec2& wallPerp,
    float width, float height
) {
    Mesh3D mesh;
    Vec3 glassColor{0.7f, 0.85f, 0.95f};  // Light blue tint

    float glassInset = 60.0f;  // Frame width
    float halfWidth = (width - 2 * glassInset) / 2.0f;
    float glassHeight = height - 2 * glassInset;

    // Glass pane (single quad, both sides)
    Vec3 glassBase{
        position.x - wallDir.x * halfWidth,
        position.y + glassInset,
        position.z - wallDir.y * halfWidth
    };

    Vec3 g0 = glassBase;
    Vec3 g1{g0.x + wallDir.x * (width - 2 * glassInset), g0.y, g0.z + wallDir.y * (width - 2 * glassInset)};
    Vec3 g2{g1.x, g1.y + glassHeight, g1.z};
    Vec3 g3{g0.x, g0.y + glassHeight, g0.z};

    Vec3 frontNormal{wallPerp.x, 0, wallPerp.y};
    Vec3 backNormal{-wallPerp.x, 0, -wallPerp.y};

    mesh.addQuad(g0, g1, g2, g3, frontNormal, glassColor);
    mesh.addQuad(g1, g0, g3, g2, backNormal, glassColor);

    return mesh;
}

Geometry2D OpeningGeometryGenerator::generateWindowSymbol(
    const SchemaWindow& window,
    const SchemaWall& wall
) {
    Geometry2D symbol;
    symbol.element_type = "window_symbol";

    Vec2 wallDir = wall.direction();
    Vec2 wallPerp = wallDir.perpendicular();
    float halfWidth = window.width / 2.0f;

    // Window position in plan view
    Point2D windowCenter{
        wall.start.x + wallDir.x * window.offset,
        wall.start.z + wallDir.y * window.offset
    };

    // Window opening lines (three parallel lines)
    float wallHalfThick = 75.0f;  // Half wall thickness for symbol

    // Outer line 1
    Line2D line1;
    line1.layer = "windows";
    line1.start = Point2D{
        windowCenter.x - wallDir.x * halfWidth + wallPerp.x * wallHalfThick,
        windowCenter.y - wallDir.y * halfWidth + wallPerp.y * wallHalfThick
    };
    line1.end = Point2D{
        windowCenter.x + wallDir.x * halfWidth + wallPerp.x * wallHalfThick,
        windowCenter.y + wallDir.y * halfWidth + wallPerp.y * wallHalfThick
    };
    symbol.lines.push_back(line1);

    // Center line (glass)
    Line2D line2;
    line2.layer = "windows";
    line2.start = Point2D{
        windowCenter.x - wallDir.x * halfWidth,
        windowCenter.y - wallDir.y * halfWidth
    };
    line2.end = Point2D{
        windowCenter.x + wallDir.x * halfWidth,
        windowCenter.y + wallDir.y * halfWidth
    };
    symbol.lines.push_back(line2);

    // Outer line 2
    Line2D line3;
    line3.layer = "windows";
    line3.start = Point2D{
        windowCenter.x - wallDir.x * halfWidth - wallPerp.x * wallHalfThick,
        windowCenter.y - wallDir.y * halfWidth - wallPerp.y * wallHalfThick
    };
    line3.end = Point2D{
        windowCenter.x + wallDir.x * halfWidth - wallPerp.x * wallHalfThick,
        windowCenter.y + wallDir.y * halfWidth - wallPerp.y * wallHalfThick
    };
    symbol.lines.push_back(line3);

    return symbol;
}

//==============================================================================
// Helper Functions
//==============================================================================

Vec3 OpeningGeometryGenerator::getOpeningPosition(float offset, const SchemaWall& wall) {
    Vec2 dir = wall.direction();
    return Vec3{
        wall.start.x + dir.x * offset,
        wall.start.y,
        wall.start.z + dir.y * offset
    };
}

void OpeningGeometryGenerator::generateFrameMember(
    Mesh3D& mesh,
    const Vec3& base,
    float width, float height, float depth,
    const Vec2& wallDir, const Vec2& wallPerp,
    const Vec3& color
) {
    // Vertical frame member (jamb)
    float halfDepth = depth / 2.0f;

    Vec3 b0{base.x - wallPerp.x * halfDepth, base.y, base.z - wallPerp.y * halfDepth};
    Vec3 b1{base.x + wallPerp.x * halfDepth, base.y, base.z + wallPerp.y * halfDepth};
    Vec3 b2{b1.x + wallDir.x * width, b1.y, b1.z + wallDir.y * width};
    Vec3 b3{b0.x + wallDir.x * width, b0.y, b0.z + wallDir.y * width};

    Vec3 t0{b0.x, b0.y + height, b0.z};
    Vec3 t1{b1.x, b1.y + height, b1.z};
    Vec3 t2{b2.x, b2.y + height, b2.z};
    Vec3 t3{b3.x, b3.y + height, b3.z};

    // Six faces
    mesh.addQuad(b0, t0, t1, b1, Vec3{-wallPerp.x, 0, -wallPerp.y}, color);
    mesh.addQuad(b1, t1, t2, b2, Vec3{wallDir.x, 0, wallDir.y}, color);
    mesh.addQuad(b2, t2, t3, b3, Vec3{wallPerp.x, 0, wallPerp.y}, color);
    mesh.addQuad(b3, t3, t0, b0, Vec3{-wallDir.x, 0, -wallDir.y}, color);
    mesh.addQuad(t0, t3, t2, t1, Vec3{0, 1, 0}, color);
    mesh.addQuad(b0, b1, b2, b3, Vec3{0, -1, 0}, color);
}

void OpeningGeometryGenerator::generateFrameMemberHorizontal(
    Mesh3D& mesh,
    const Vec3& base,
    float width, float height, float depth,
    const Vec2& wallDir, const Vec2& wallPerp,
    const Vec3& color
) {
    // Horizontal frame member (sill or head)
    float halfDepth = depth / 2.0f;

    Vec3 b0{base.x - wallPerp.x * halfDepth, base.y, base.z - wallPerp.y * halfDepth};
    Vec3 b1{base.x + wallPerp.x * halfDepth, base.y, base.z + wallPerp.y * halfDepth};
    Vec3 b2{b1.x + wallDir.x * width, b1.y, b1.z + wallDir.y * width};
    Vec3 b3{b0.x + wallDir.x * width, b0.y, b0.z + wallDir.y * width};

    Vec3 t0{b0.x, b0.y + height, b0.z};
    Vec3 t1{b1.x, b1.y + height, b1.z};
    Vec3 t2{b2.x, b2.y + height, b2.z};
    Vec3 t3{b3.x, b3.y + height, b3.z};

    mesh.addQuad(b0, t0, t1, b1, Vec3{-wallDir.x, 0, -wallDir.y}, color);
    mesh.addQuad(b2, t2, t3, b3, Vec3{wallDir.x, 0, wallDir.y}, color);
    mesh.addQuad(b0, b3, t3, t0, Vec3{-wallPerp.x, 0, -wallPerp.y}, color);
    mesh.addQuad(b1, t1, t2, b2, Vec3{wallPerp.x, 0, wallPerp.y}, color);
    mesh.addQuad(t0, t3, t2, t1, Vec3{0, 1, 0}, color);
    mesh.addQuad(b0, b1, b2, b3, Vec3{0, -1, 0}, color);
}

} // namespace archgeometry
