"""
Geometry primitives for furniture generation.

Generates Vulkan-compatible vertex buffers for basic shapes:
- Box (rectangular prism)
- Cylinder
- Plane
- Wedge (for cushions, backrests)

All dimensions are in millimeters.
"""
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

from furniture.models import Vertex, Mesh, Material


def normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Normalize a 3D vector."""
    x, y, z = v
    length = math.sqrt(x*x + y*y + z*z)
    if length < 0.0001:
        return (0.0, 1.0, 0.0)
    return (x/length, y/length, z/length)


def create_box(
    width: float,
    height: float,
    depth: float,
    offset: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> Mesh:
    """
    Create a box (rectangular prism) mesh.

    Args:
        width: X-axis dimension (mm)
        height: Y-axis dimension (mm)
        depth: Z-axis dimension (mm)
        offset: Position offset (x, y, z)
        color: RGB color (0-1)

    Returns:
        Mesh with vertices and indices
    """
    ox, oy, oz = offset
    w, h, d = width / 2, height, depth / 2  # Half-width, full height from base, half-depth

    # 8 corners of the box (centered on X/Z, bottom at Y=0)
    corners = [
        (-w + ox, oy,     -d + oz),  # 0: bottom-back-left
        ( w + ox, oy,     -d + oz),  # 1: bottom-back-right
        ( w + ox, oy,      d + oz),  # 2: bottom-front-right
        (-w + ox, oy,      d + oz),  # 3: bottom-front-left
        (-w + ox, h + oy, -d + oz),  # 4: top-back-left
        ( w + ox, h + oy, -d + oz),  # 5: top-back-right
        ( w + ox, h + oy,  d + oz),  # 6: top-front-right
        (-w + ox, h + oy,  d + oz),  # 7: top-front-left
    ]

    # Face definitions: (corner indices, normal)
    faces = [
        # Front face (+Z)
        ([3, 2, 6, 7], (0, 0, 1)),
        # Back face (-Z)
        ([1, 0, 4, 5], (0, 0, -1)),
        # Right face (+X)
        ([2, 1, 5, 6], (1, 0, 0)),
        # Left face (-X)
        ([0, 3, 7, 4], (-1, 0, 0)),
        # Top face (+Y)
        ([7, 6, 5, 4], (0, 1, 0)),
        # Bottom face (-Y)
        ([0, 1, 2, 3], (0, -1, 0)),
    ]

    vertices = []
    indices = []

    for corner_indices, normal in faces:
        base_idx = len(vertices)

        # UV coordinates for the quad
        uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]

        for i, ci in enumerate(corner_indices):
            vertices.append(Vertex(
                position=corners[ci],
                normal=normal,
                color=color,
                tex_coord=uvs[i],
                stress=0.0,
            ))

        # Two triangles per face
        indices.extend([
            base_idx, base_idx + 1, base_idx + 2,
            base_idx, base_idx + 2, base_idx + 3,
        ])

    return Mesh(vertices=vertices, indices=indices)


def create_cylinder(
    radius: float,
    height: float,
    segments: int = 16,
    offset: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
    capped: bool = True,
) -> Mesh:
    """
    Create a cylinder mesh.

    Args:
        radius: Radius in mm
        height: Height in mm (Y-axis)
        segments: Number of segments around circumference
        offset: Position offset (x, y, z)
        color: RGB color (0-1)
        capped: Whether to include top and bottom caps

    Returns:
        Mesh with vertices and indices
    """
    ox, oy, oz = offset
    vertices = []
    indices = []

    # Generate side vertices
    for i in range(segments):
        angle = (2 * math.pi * i) / segments
        x = math.cos(angle) * radius + ox
        z = math.sin(angle) * radius + oz
        nx, nz = math.cos(angle), math.sin(angle)

        # Bottom vertex
        vertices.append(Vertex(
            position=(x, oy, z),
            normal=(nx, 0, nz),
            color=color,
            tex_coord=(i / segments, 0),
            stress=0.0,
        ))

        # Top vertex
        vertices.append(Vertex(
            position=(x, height + oy, z),
            normal=(nx, 0, nz),
            color=color,
            tex_coord=(i / segments, 1),
            stress=0.0,
        ))

    # Side indices
    for i in range(segments):
        i0 = i * 2
        i1 = i * 2 + 1
        i2 = ((i + 1) % segments) * 2
        i3 = ((i + 1) % segments) * 2 + 1

        indices.extend([i0, i2, i1])
        indices.extend([i1, i2, i3])

    if capped:
        # Bottom cap
        base_idx = len(vertices)
        center_bottom = len(vertices)
        vertices.append(Vertex(
            position=(ox, oy, oz),
            normal=(0, -1, 0),
            color=color,
            tex_coord=(0.5, 0.5),
            stress=0.0,
        ))

        for i in range(segments):
            angle = (2 * math.pi * i) / segments
            x = math.cos(angle) * radius + ox
            z = math.sin(angle) * radius + oz
            vertices.append(Vertex(
                position=(x, oy, z),
                normal=(0, -1, 0),
                color=color,
                tex_coord=(math.cos(angle) * 0.5 + 0.5, math.sin(angle) * 0.5 + 0.5),
                stress=0.0,
            ))

        for i in range(segments):
            i1 = base_idx + 1 + i
            i2 = base_idx + 1 + ((i + 1) % segments)
            indices.extend([center_bottom, i2, i1])

        # Top cap
        base_idx = len(vertices)
        center_top = len(vertices)
        vertices.append(Vertex(
            position=(ox, height + oy, oz),
            normal=(0, 1, 0),
            color=color,
            tex_coord=(0.5, 0.5),
            stress=0.0,
        ))

        for i in range(segments):
            angle = (2 * math.pi * i) / segments
            x = math.cos(angle) * radius + ox
            z = math.sin(angle) * radius + oz
            vertices.append(Vertex(
                position=(x, height + oy, z),
                normal=(0, 1, 0),
                color=color,
                tex_coord=(math.cos(angle) * 0.5 + 0.5, math.sin(angle) * 0.5 + 0.5),
                stress=0.0,
            ))

        for i in range(segments):
            i1 = base_idx + 1 + i
            i2 = base_idx + 1 + ((i + 1) % segments)
            indices.extend([center_top, i1, i2])

    return Mesh(vertices=vertices, indices=indices)


def create_plane(
    width: float,
    depth: float,
    offset: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
    facing_up: bool = True,
) -> Mesh:
    """
    Create a flat plane mesh.

    Args:
        width: X-axis dimension (mm)
        depth: Z-axis dimension (mm)
        offset: Position offset (x, y, z)
        color: RGB color (0-1)
        facing_up: Normal points up (+Y) if True, down (-Y) if False

    Returns:
        Mesh with vertices and indices
    """
    ox, oy, oz = offset
    w, d = width / 2, depth / 2
    normal = (0, 1, 0) if facing_up else (0, -1, 0)

    vertices = [
        Vertex((-w + ox, oy, -d + oz), normal, color, (0, 0), 0.0),
        Vertex(( w + ox, oy, -d + oz), normal, color, (1, 0), 0.0),
        Vertex(( w + ox, oy,  d + oz), normal, color, (1, 1), 0.0),
        Vertex((-w + ox, oy,  d + oz), normal, color, (0, 1), 0.0),
    ]

    if facing_up:
        indices = [0, 1, 2, 0, 2, 3]
    else:
        indices = [0, 2, 1, 0, 3, 2]

    return Mesh(vertices=vertices, indices=indices)


def create_wedge(
    width: float,
    height_front: float,
    height_back: float,
    depth: float,
    offset: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> Mesh:
    """
    Create a wedge mesh (for angled surfaces like seat cushions).

    Args:
        width: X-axis dimension (mm)
        height_front: Height at front (mm)
        height_back: Height at back (mm)
        depth: Z-axis dimension (mm)
        offset: Position offset (x, y, z)
        color: RGB color (0-1)

    Returns:
        Mesh with vertices and indices
    """
    ox, oy, oz = offset
    w, d = width / 2, depth / 2
    hf, hb = height_front, height_back

    # 8 corners
    corners = [
        (-w + ox, oy,      -d + oz),  # 0: bottom-back-left
        ( w + ox, oy,      -d + oz),  # 1: bottom-back-right
        ( w + ox, oy,       d + oz),  # 2: bottom-front-right
        (-w + ox, oy,       d + oz),  # 3: bottom-front-left
        (-w + ox, hb + oy, -d + oz),  # 4: top-back-left
        ( w + ox, hb + oy, -d + oz),  # 5: top-back-right
        ( w + ox, hf + oy,  d + oz),  # 6: top-front-right
        (-w + ox, hf + oy,  d + oz),  # 7: top-front-left
    ]

    # Calculate top surface normal (angled)
    # Vector from back to front on top surface
    v1 = (0, hf - hb, 2 * d)
    # Cross product with side vector to get normal
    top_normal = normalize((0, 2 * d, hb - hf))

    vertices = []
    indices = []

    # Front face (+Z)
    base = len(vertices)
    for ci in [3, 2, 6, 7]:
        vertices.append(Vertex(corners[ci], (0, 0, 1), color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    # Back face (-Z)
    base = len(vertices)
    for ci in [1, 0, 4, 5]:
        vertices.append(Vertex(corners[ci], (0, 0, -1), color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    # Right face (+X)
    base = len(vertices)
    for ci in [2, 1, 5, 6]:
        vertices.append(Vertex(corners[ci], (1, 0, 0), color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    # Left face (-X)
    base = len(vertices)
    for ci in [0, 3, 7, 4]:
        vertices.append(Vertex(corners[ci], (-1, 0, 0), color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    # Top face (angled)
    base = len(vertices)
    for ci in [7, 6, 5, 4]:
        vertices.append(Vertex(corners[ci], top_normal, color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    # Bottom face (-Y)
    base = len(vertices)
    for ci in [0, 1, 2, 3]:
        vertices.append(Vertex(corners[ci], (0, -1, 0), color, (0, 0), 0.0))
    indices.extend([base, base+1, base+2, base, base+2, base+3])

    return Mesh(vertices=vertices, indices=indices)


def create_rounded_box(
    width: float,
    height: float,
    depth: float,
    corner_radius: float,
    segments: int = 4,
    offset: Tuple[float, float, float] = (0, 0, 0),
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> Mesh:
    """
    Create a box with rounded vertical edges (for cushions, upholstery).

    This creates a box with cylindrical corners on the vertical edges.

    Args:
        width: X-axis dimension (mm)
        height: Y-axis dimension (mm)
        depth: Z-axis dimension (mm)
        corner_radius: Radius of rounded corners (mm)
        segments: Number of segments per corner
        offset: Position offset (x, y, z)
        color: RGB color (0-1)

    Returns:
        Mesh with vertices and indices
    """
    ox, oy, oz = offset

    # Clamp radius to half of smallest dimension
    max_radius = min(width, depth) / 2 - 1
    r = min(corner_radius, max_radius)

    w = width / 2 - r
    d = depth / 2 - r

    vertices = []
    indices = []

    # Corner centers
    corners = [
        (-w + ox, oy, -d + oz),  # back-left
        ( w + ox, oy, -d + oz),  # back-right
        ( w + ox, oy,  d + oz),  # front-right
        (-w + ox, oy,  d + oz),  # front-left
    ]

    # Start angles for each corner
    start_angles = [math.pi, 1.5 * math.pi, 0, 0.5 * math.pi]

    # Generate rounded edges
    all_bottom = []
    all_top = []

    for ci, (cx, cy, cz) in enumerate(corners):
        start = start_angles[ci]
        for i in range(segments + 1):
            angle = start + (math.pi / 2) * (i / segments)
            x = cx + math.cos(angle) * r
            z = cz + math.sin(angle) * r
            nx, nz = math.cos(angle), math.sin(angle)

            all_bottom.append((x, oy, z, nx, nz))
            all_top.append((x, height + oy, z, nx, nz))

    # Side surface
    n = len(all_bottom)
    for i in range(n):
        x0, y0, z0, nx0, nz0 = all_bottom[i]
        x1, y1, z1, nx1, nz1 = all_top[i]
        x2, y2, z2, nx2, nz2 = all_bottom[(i + 1) % n]
        x3, y3, z3, nx3, nz3 = all_top[(i + 1) % n]

        base = len(vertices)
        vertices.append(Vertex((x0, y0, z0), (nx0, 0, nz0), color, (0, 0), 0.0))
        vertices.append(Vertex((x1, y1, z1), (nx0, 0, nz0), color, (0, 1), 0.0))
        vertices.append(Vertex((x2, y2, z2), (nx2, 0, nz2), color, (1, 0), 0.0))
        vertices.append(Vertex((x3, y3, z3), (nx2, 0, nz2), color, (1, 1), 0.0))

        indices.extend([base, base+2, base+1, base+1, base+2, base+3])

    # Top cap (simple fan for now)
    center_idx = len(vertices)
    vertices.append(Vertex((ox, height + oy, oz), (0, 1, 0), color, (0.5, 0.5), 0.0))

    for i in range(n):
        x, _, z, _, _ = all_top[i]
        vertices.append(Vertex((x, height + oy, z), (0, 1, 0), color, (0, 0), 0.0))

    for i in range(n):
        i1 = center_idx + 1 + i
        i2 = center_idx + 1 + ((i + 1) % n)
        indices.extend([center_idx, i1, i2])

    # Bottom cap
    center_idx = len(vertices)
    vertices.append(Vertex((ox, oy, oz), (0, -1, 0), color, (0.5, 0.5), 0.0))

    for i in range(n):
        x, _, z, _, _ = all_bottom[i]
        vertices.append(Vertex((x, oy, z), (0, -1, 0), color, (0, 0), 0.0))

    for i in range(n):
        i1 = center_idx + 1 + i
        i2 = center_idx + 1 + ((i + 1) % n)
        indices.extend([center_idx, i2, i1])

    return Mesh(vertices=vertices, indices=indices)


def merge_meshes(meshes: List[Mesh]) -> Mesh:
    """
    Merge multiple meshes into a single mesh.

    Args:
        meshes: List of meshes to merge

    Returns:
        Single merged mesh
    """
    all_vertices = []
    all_indices = []

    for mesh in meshes:
        offset = len(all_vertices)
        all_vertices.extend(mesh.vertices)
        all_indices.extend([i + offset for i in mesh.indices])

    return Mesh(vertices=all_vertices, indices=all_indices)


def transform_mesh(
    mesh: Mesh,
    translate: Tuple[float, float, float] = (0, 0, 0),
    rotate_y: float = 0,
    scale: Tuple[float, float, float] = (1, 1, 1),
) -> Mesh:
    """
    Transform a mesh (translate, rotate around Y, scale).

    Args:
        mesh: Input mesh
        translate: Translation offset (x, y, z)
        rotate_y: Rotation around Y axis in degrees
        scale: Scale factors (x, y, z)

    Returns:
        Transformed mesh (new instance)
    """
    tx, ty, tz = translate
    sx, sy, sz = scale
    angle = math.radians(rotate_y)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    new_vertices = []
    for v in mesh.vertices:
        # Scale
        x = v.position[0] * sx
        y = v.position[1] * sy
        z = v.position[2] * sz

        # Rotate around Y
        rx = x * cos_a - z * sin_a
        rz = x * sin_a + z * cos_a

        # Translate
        px = rx + tx
        py = y + ty
        pz = rz + tz

        # Rotate normal
        nx = v.normal[0] * cos_a - v.normal[2] * sin_a
        nz = v.normal[0] * sin_a + v.normal[2] * cos_a

        new_vertices.append(Vertex(
            position=(px, py, pz),
            normal=(nx, v.normal[1], nz),
            color=v.color,
            tex_coord=v.tex_coord,
            stress=v.stress,
        ))

    return Mesh(vertices=new_vertices, indices=mesh.indices.copy())
