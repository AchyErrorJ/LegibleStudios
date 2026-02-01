"""
Terrain Mesh Generator
======================
Convert elevation data to 3D mesh for rendering.
"""

import math
from typing import List, Tuple, Dict


class TerrainVertex:
    """Single vertex in terrain mesh."""
    def __init__(self, x: float, y: float, z: float, nx: float, ny: float, nz: float, u: float, v: float):
        self.x = x
        self.y = y
        self.z = z
        self.nx = nx
        self.ny = ny
        self.nz = nz
        self.u = u
        self.v = v

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "position": [self.x, self.y, self.z],
            "normal": [self.nx, self.ny, self.nz],
            "uv": [self.u, self.v]
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary."""
        pos = data["position"]
        normal = data["normal"]
        uv = data["uv"]
        return cls(pos[0], pos[1], pos[2], normal[0], normal[1], normal[2], uv[0], uv[1])


class TerrainMesh:
    """3D terrain mesh generated from elevation data."""

    def __init__(self, vertices: List[TerrainVertex], indices: List[int],
                 width_ft: float, depth_ft: float, min_elevation: float, max_elevation: float):
        self.vertices = vertices
        self.indices = indices
        self.width_ft = width_ft
        self.depth_ft = depth_ft
        self.min_elevation = min_elevation
        self.max_elevation = max_elevation

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "vertices": [v.to_dict() for v in self.vertices],
            "indices": self.indices,
            "width_ft": self.width_ft,
            "depth_ft": self.depth_ft,
            "min_elevation": self.min_elevation,
            "max_elevation": self.max_elevation,
            "vertex_count": len(self.vertices),
            "triangle_count": len(self.indices) // 3
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary."""
        vertices = [TerrainVertex.from_dict(v) for v in data["vertices"]]
        return cls(
            vertices,
            data["indices"],
            data["width_ft"],
            data["depth_ft"],
            data["min_elevation"],
            data["max_elevation"]
        )


class TerrainGenerator:
    """Generate terrain mesh from elevation grid data."""

    def __init__(self, elevation_grid: Dict[str, Dict], property_width_ft: float, property_depth_ft: float):
        """
        Initialize generator.

        Args:
            elevation_grid: Dict of {"lat,lng": {elevation_ft: value, ...}}
            property_width_ft: Property width in feet
            property_depth_ft: Property depth in feet
        """
        self.elevation_grid = elevation_grid
        self.width_ft = property_width_ft
        self.depth_ft = property_depth_ft

        # Sort points into grid
        self._organize_grid()

    def _organize_grid(self):
        """Sort elevation points into a regular grid."""
        # Extract and sort points
        points = list(self.elevation_grid.values())

        # Get unique lats and lngs to determine grid size
        lats = sorted(set(p['lat'] for p in points))
        lngs = sorted(set(p['lng'] for p in points))

        self.grid_rows = len(lats)
        self.grid_cols = len(lngs)

        # Create 2D array
        self.grid = [[None for _ in range(self.grid_cols)] for _ in range(self.grid_rows)]

        # Fill grid
        for point in points:
            lat_idx = lats.index(point['lat'])
            lng_idx = lngs.index(point['lng'])
            self.grid[lat_idx][lng_idx] = point

        print(f"[Terrain] Organized into {self.grid_rows}x{self.grid_cols} grid")

    def generate_mesh(self) -> TerrainMesh:
        """Generate terrain mesh from elevation grid."""
        vertices = []
        indices = []

        # Calculate elevation range for coloring
        elevations = [p['elevation_ft'] for row in self.grid for p in row if p]
        min_elev = min(elevations)
        max_elev = max(elevations)
        elev_range = max_elev - min_elev if max_elev != min_elev else 1.0

        # Offset elevation so min_elevation is slightly below ground level (buildings sit on top)
        # Use -10mm offset so terrain appears as ground plane beneath building floors at Y=0
        elevation_offset = -min_elev - 0.0328  # -0.0328 ft = -10 mm

        # Generate vertices
        for i in range(self.grid_rows):
            for j in range(self.grid_cols):
                point = self.grid[i][j]
                if not point:
                    continue

                # World position (origin at property corner)
                # Convert feet to millimeters (1 ft = 304.8 mm)
                # Building coordinate system: X=east-west, Y=up, Z=north-south
                x = (j / max(1, self.grid_cols - 1)) * self.width_ft * 304.8  # east-west
                y = (point['elevation_ft'] + elevation_offset) * 304.8  # elevation offset to start at 0
                z = (i / max(1, self.grid_rows - 1)) * self.depth_ft * 304.8  # north-south

                # Compute normal from adjacent heights
                nx, ny, nz = self._compute_normal(i, j)

                # UV coordinates
                u = j / max(1, self.grid_cols - 1)
                v = i / max(1, self.grid_rows - 1)

                vertices.append(TerrainVertex(x, y, z, nx, ny, nz, u, v))

        # Generate triangle indices
        for i in range(self.grid_rows - 1):
            for j in range(self.grid_cols - 1):
                # Current quad vertex indices
                idx = i * self.grid_cols + j

                # Two triangles per quad (clockwise winding for front faces)
                # Triangle 1: (i,j) -> (i+1,j) -> (i,j+1)
                indices.extend([idx, idx + self.grid_cols, idx + 1])

                # Triangle 2: (i,j+1) -> (i+1,j) -> (i+1,j+1)
                indices.extend([idx + 1, idx + self.grid_cols, idx + self.grid_cols + 1])

        mesh = TerrainMesh(vertices, indices, self.width_ft, self.depth_ft, min_elev, max_elev)

        # Print scale information
        width_mm = self.width_ft * 304.8
        depth_mm = self.depth_ft * 304.8
        print(f"[Terrain] Generated mesh: {len(vertices)} vertices, {len(indices)//3} triangles")
        print(f"[Terrain] Property size: {self.width_ft:.1f}'x{self.depth_ft:.1f}' ({width_mm:.0f}x{depth_mm:.0f} mm)")
        print(f"[Terrain] Original elevation (from Google): {min_elev:.1f}' to {max_elev:.1f}' above sea level")
        if vertices:
            x_range = (vertices[0].x, vertices[-1].x)
            z_range = (vertices[0].z, vertices[-1].z)
            y_range = (min(v.y for v in vertices), max(v.y for v in vertices))
            print(f"[Terrain] After offset - vertex ranges: X=[{x_range[0]:.0f}, {x_range[1]:.0f}], Y=[{y_range[0]:.0f}, {y_range[1]:.0f}], Z=[{z_range[0]:.0f}, {z_range[1]:.0f}] mm")
            print(f"[Terrain] Ground level (Y=0) is {(max_elev - min_elev):.1f}' ({(max_elev - min_elev) * 304.8:.0f} mm) above lowest terrain point")

        return mesh

    def _compute_normal(self, row: int, col: int) -> Tuple[float, float, float]:
        """
        Compute vertex normal from adjacent elevations.

        Uses central difference to approximate surface normal.
        """
        # Get current elevation
        current = self.grid[row][col]
        if not current:
            return (0, 0, 1)  # Default upward normal

        z = current['elevation_ft']

        # Sample neighbors with boundary checking
        z_left = self._get_elevation(row, col - 1, z)
        z_right = self._get_elevation(row, col + 1, z)
        z_up = self._get_elevation(row - 1, col, z)
        z_down = self._get_elevation(row + 1, col, z)

        # Compute gradients
        dz_dx = (z_right - z_left) / 2.0
        dz_dy = (z_down - z_up) / 2.0

        # Normal is perpendicular to surface
        # Tangent vectors: (1, 0, dz_dx) and (0, 1, dz_dy)
        # Normal = cross product
        nx = -dz_dx
        ny = -dz_dy
        nz = 1.0

        # Normalize
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 0:
            nx /= length
            ny /= length
            nz /= length

        return (nx, ny, nz)

    def _get_elevation(self, row: int, col: int, default: float) -> float:
        """Get elevation at grid position with boundary checking."""
        if 0 <= row < self.grid_rows and 0 <= col < self.grid_cols:
            point = self.grid[row][col]
            if point:
                return point['elevation_ft']
        return default


def generate_terrain_from_site(site_data: dict) -> TerrainMesh:
    """
    Generate terrain mesh from site data.

    Args:
        site_data: Site data dictionary with google_maps.elevation_grid

    Returns:
        TerrainMesh object, or None if no elevation data
    """
    google_maps = site_data.get("google_maps", {})
    elevation_grid = google_maps.get("elevation_grid", {})

    if not elevation_grid:
        print("[Terrain] No elevation data in site")
        return None

    width_ft = site_data.get("property_width_ft", 100)
    depth_ft = site_data.get("property_depth_ft", 120)

    generator = TerrainGenerator(elevation_grid, width_ft, depth_ft)
    mesh = generator.generate_mesh()

    return mesh


def generate_test_terrain(width_ft: float = 100, depth_ft: float = 100, grid_size: int = 15) -> TerrainMesh:
    """
    Generate a simple test terrain with gentle rolling hills.

    Args:
        width_ft: Terrain width in feet
        depth_ft: Terrain depth in feet
        grid_size: Number of grid points per axis

    Returns:
        TerrainMesh object for testing
    """
    vertices = []
    indices = []

    # Convert to mm (renderer uses mm internally with Y-up)
    FT_TO_MM = 304.8
    width_mm = width_ft * FT_TO_MM
    depth_mm = depth_ft * FT_TO_MM

    # Generate vertices with simple sine-wave hills
    min_elev = 0.0
    max_elev = 0.0

    for z in range(grid_size):
        for x in range(grid_size):
            # Position in mm - terrain starts at origin and extends positive (like buildings)
            px = (x / (grid_size - 1)) * width_mm
            pz = (z / (grid_size - 1)) * depth_mm

            # SIMPLE TEST: Tilted plane - should be VERY obvious
            # X axis: 0 to 100ft, elevation goes from 0mm to 15000mm (50ft!)
            # Z axis: constant 5000mm elevation
            elev_mm = (x / (grid_size - 1)) * 15000.0  # 0 to 50ft ramp on X
            if z == 0 and x == 0:
                print(f"[Terrain] DEBUG: Vertex (0,0) elevation = {elev_mm:.1f} mm")
            if z == 0 and x == grid_size - 1:
                print(f"[Terrain] DEBUG: Vertex ({grid_size-1},0) elevation = {elev_mm:.1f} mm")

            min_elev = min(min_elev, elev_mm)
            max_elev = max(max_elev, elev_mm)

            # UV coordinates
            u = x / (grid_size - 1)
            v = z / (grid_size - 1)

            # Normal will be computed after
            vertices.append(TerrainVertex(px, elev_mm, pz, 0, 1, 0, u, v))

    # Compute proper normals using finite differences
    for z in range(grid_size):
        for x in range(grid_size):
            idx = z * grid_size + x

            # Get neighboring heights
            h_left = vertices[idx - 1].y if x > 0 else vertices[idx].y
            h_right = vertices[idx + 1].y if x < grid_size - 1 else vertices[idx].y
            h_down = vertices[idx - grid_size].y if z > 0 else vertices[idx].y
            h_up = vertices[idx + grid_size].y if z < grid_size - 1 else vertices[idx].y

            # Compute normal from height differences
            dx = width_mm / (grid_size - 1)
            dz = depth_mm / (grid_size - 1)

            nx = (h_left - h_right) / (2 * dx)
            nz = (h_down - h_up) / (2 * dz)
            ny = 1.0

            # Normalize
            length = math.sqrt(nx*nx + ny*ny + nz*nz)
            if length > 0.0001:
                vertices[idx].nx = nx / length
                vertices[idx].ny = ny / length
                vertices[idx].nz = nz / length

    # Generate triangle indices
    for z in range(grid_size - 1):
        for x in range(grid_size - 1):
            top_left = z * grid_size + x
            top_right = top_left + 1
            bottom_left = (z + 1) * grid_size + x
            bottom_right = bottom_left + 1

            # Two triangles per quad (clockwise winding for front faces)
            indices.extend([top_left, top_right, bottom_left])
            indices.extend([top_right, bottom_right, bottom_left])

    # Print sample vertices to debug
    print(f"[Terrain] Sample vertex positions:")
    print(f"  (0,0): pos=[{vertices[0].x:.1f}, {vertices[0].y:.1f}, {vertices[0].z:.1f}]")
    mid_idx = len(vertices) // 2
    print(f"  (mid): pos=[{vertices[mid_idx].x:.1f}, {vertices[mid_idx].y:.1f}, {vertices[mid_idx].z:.1f}]")
    last_idx = len(vertices) - 1
    print(f"  (last): pos=[{vertices[last_idx].x:.1f}, {vertices[last_idx].y:.1f}, {vertices[last_idx].z:.1f}]")

    print(f"[Terrain] Generated test terrain: {len(vertices)} vertices, {len(indices)//3} triangles")
    print(f"[Terrain] Position range: X=[0, {width_mm:.0f}], Z=[0, {depth_mm:.0f}] mm")
    print(f"[Terrain] Elevation range: Y=[{min_elev:.0f}, {max_elev:.0f}] mm")

    return TerrainMesh(
        vertices=vertices,
        indices=indices,
        width_ft=width_ft,
        depth_ft=depth_ft,
        min_elevation=min_elev / FT_TO_MM,
        max_elevation=max_elev / FT_TO_MM
    )
