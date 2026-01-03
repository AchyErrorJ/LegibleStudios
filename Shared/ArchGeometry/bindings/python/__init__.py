"""
ArchGeometry - Shared geometry library for ArchEngine

This module provides Python bindings to the C++ ArchGeometry library,
which is the canonical source for interpreting ArchEngine JSON schemas
and converting them to geometry.

Usage:
    import archgeometry

    # Parse and generate all geometry from file
    geometry = archgeometry.generate_from_file("building.json")

    # Access generated walls, floors, roofs, etc.
    for wall in geometry.walls:
        vertices = wall.mesh_3d.get_vertices()  # numpy array
        indices = wall.mesh_3d.get_indices()    # numpy array

    # Parse schema for querying
    doc = archgeometry.parse_file("building.json")
    query = archgeometry.QueryAPI(doc)
    print(f"Wall count: {query.get_wall_count()}")
    print(f"Room count: {query.get_room_count()}")

    # Get room area
    area = query.get_room_area("living_room")
    print(f"Living room area: {area / 1_000_000:.1f} sqm")

Key types:
    - SchemaDocument: Parsed JSON schema
    - BuildingGeometry: Generated geometry for all elements
    - WallGeometry, FloorGeometry, RoofGeometry: Per-element geometry
    - Mesh3D: 3D mesh with numpy conversion methods
    - QueryAPI: Query interface for schema elements
"""

from .archgeometry import *

__all__ = [
    # Types
    "Vec3", "Vec2", "Point2D",
    "WallLayer", "WallType",
    "SchemaWall", "SchemaFloor", "SchemaDoor", "SchemaWindow",
    "SchemaRoof", "RoofSurface", "SchemaRoom", "RoomBounds",
    "SchemaLevel", "SchemaDocument",
    "Mesh3D", "Polygon2D", "Geometry2D",
    "WallGeometry", "FloorGeometry", "RoofGeometry",
    "DoorGeometry", "WindowGeometry", "RoomBoundary",
    "BuildingGeometry", "ParseError",
    "QueryAPI",
    # Functions
    "parse_json", "parse_file",
    "generate_from_json", "generate_from_file", "generate_from_schema",
    "version",
]
