"""
ArchGeometry - Unified geometry library for ArchEngine

Automatically uses C++ bindings if available, falls back to pure Python.

Usage:
    from archgeometry import parse_file, QueryAPI

    doc = parse_file("building.json")
    query = QueryAPI(doc)
    print(f"Walls: {query.get_wall_count()}")
"""

try:
    # Try C++ bindings first (faster)
    from archgeometry.archgeometry import *
    _USING_CPP = True
except ImportError:
    # Fall back to pure Python implementation
    from .archgeometry_py import *
    _USING_CPP = False

def using_cpp_bindings() -> bool:
    """Check if using C++ bindings or Python fallback."""
    return _USING_CPP
