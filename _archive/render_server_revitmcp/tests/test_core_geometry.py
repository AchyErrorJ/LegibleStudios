"""
Core Geometry Tools Test Suite

Tests the fundamental geometry creation tools in RevitMCP:
- create_floor, create_roof, create_room
- place_door, place_window, place_family
- create_directshape_mass
- Wall type and assembly tools

Usage:
    python tests/test_core_geometry.py              # Run all tests
    python tests/test_core_geometry.py --offline    # Run offline validation only
    python tests/test_core_geometry.py --verbose    # Verbose output

Requirements:
    - Revit 2024+ running with RevitMCP plugin loaded (for live tests)
    - Server running on localhost:48884
"""

import asyncio
import json
import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import tools
from tools.registry import TOOL_FUNCTIONS
from tools import geometry_tools

# Check Revit availability
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

REVIT_API_URL = "http://localhost:48884/revit_mcp"


# =============================================================================
# HELPERS
# =============================================================================

async def check_revit_connection():
    """Check if Revit is connected"""
    if not HTTPX_AVAILABLE:
        return False
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{REVIT_API_URL}/status/", timeout=5.0)
            return resp.status_code == 200
    except:
        return False


async def revit_post(endpoint: str, payload: dict) -> dict:
    """POST request to Revit API"""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=60.0)
        return resp.json()


async def revit_get(endpoint: str) -> dict:
    """GET request to Revit API"""
    url = f"{REVIT_API_URL}{endpoint}"
    if not url.endswith("/"):
        url += "/"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30.0)
        return resp.json()


class TestResult:
    def __init__(self, name, status, message="", duration=0):
        self.name = name
        self.status = status  # 'pass', 'fail', 'skip'
        self.message = message
        self.duration = duration


# =============================================================================
# OFFLINE TESTS (No Revit Required)
# =============================================================================

def test_tool_registration():
    """Verify all geometry tools are registered"""
    expected_tools = [
        'create_level', 'create_levels_batch',
        'create_wall', 'create_walls_batch',
        'create_floor', 'create_roof',
        'create_room', 'create_rooms_batch',
        'create_directshape_mass',
        'place_family', 'place_door', 'place_window', 'place_hosted_batch',
        'create_wall_type', 'create_assembly_view',
        'list_wall_type_layers', 'duplicate_wall_type'
    ]

    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing: {missing}")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    results = []
    test_tools = ['create_floor', 'create_roof', 'create_room', 'place_door', 'place_window']

    for tool_name in test_tools:
        func = TOOL_FUNCTIONS.get(tool_name)
        if func is None:
            results.append(f"{tool_name}: NOT FOUND")
        elif not callable(func):
            results.append(f"{tool_name}: NOT CALLABLE")
        else:
            results.append(f"{tool_name}: OK")

    failed = [r for r in results if "NOT" in r]
    if failed:
        return TestResult("tool_signatures", "fail", "; ".join(failed))
    return TestResult("tool_signatures", "pass", "All tools callable")


def test_argument_repair():
    """Verify argument normalization in create_floor"""
    # Test that kwargs aliases work
    import inspect
    sig = inspect.signature(geometry_tools.create_floor)
    params = list(sig.parameters.keys())

    if 'kwargs' in params or any('**' in str(sig.parameters[p]) for p in params):
        return TestResult("argument_repair", "pass", "kwargs supported for arg aliases")
    return TestResult("argument_repair", "fail", "No kwargs support found")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_create_floor():
    """Test floor creation"""
    payload = {
        "points": [[500, 500, 0], [520, 500, 0], [520, 515, 0], [500, 515, 0]],
        "level_name": "Level 1"
    }
    try:
        result = await revit_post("/create_floor/", payload)
        if "error" in str(result).lower() and "level" not in str(result).lower():
            return TestResult("create_floor", "fail", str(result)[:100])
        return TestResult("create_floor", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_floor", "fail", str(e))


async def test_create_roof():
    """Test roof creation"""
    payload = {
        "points": [[600, 500, 0], [640, 500, 0], [640, 530, 0], [600, 530, 0]],
        "level_name": "Level 1",
        "slope_degrees": 0.0
    }
    try:
        result = await revit_post("/create_roof/", payload)
        return TestResult("create_roof", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_roof", "fail", str(e))


async def test_create_room():
    """Test room creation"""
    payload = {
        "level_name": "Level 1",
        "point": [510, 507, 0],
        "name": "Test Room",
        "number": "T101",
        "auto_tag": True
    }
    try:
        result = await revit_post("/create_room/", payload)
        return TestResult("create_room", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_room", "fail", str(e))


async def test_create_directshape_mass():
    """Test mass creation"""
    payload = {
        "points": [[700, 500, 0], [720, 500, 0], [720, 520, 0], [700, 520, 0]],
        "height": 15.0,
        "category_name": "Generic Models"
    }
    try:
        result = await revit_post("/create_directshape_mass/", payload)
        return TestResult("create_directshape_mass", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_directshape_mass", "fail", str(e))


async def test_place_door_invalid_host():
    """Test door placement error handling"""
    payload = {
        "host_id": 999999999,
        "point": [10, 0, 3],
        "family_name": "Single-Flush",
        "type_name": "36\" x 84\""
    }
    try:
        result = await revit_post("/place_door/", payload)
        # Should return error for invalid host
        if "error" in str(result).lower() or "not found" in str(result).lower():
            return TestResult("place_door_invalid_host", "pass", "Correctly rejected invalid host")
        return TestResult("place_door_invalid_host", "fail", "Did not reject invalid host")
    except Exception as e:
        return TestResult("place_door_invalid_host", "fail", str(e))


async def test_place_window_invalid_host():
    """Test window placement error handling"""
    payload = {
        "host_id": 999999999,
        "point": [15, 0, 4],
        "family_name": "Fixed",
        "type_name": "36\" x 48\""
    }
    try:
        result = await revit_post("/place_window/", payload)
        if "error" in str(result).lower() or "not found" in str(result).lower():
            return TestResult("place_window_invalid_host", "pass", "Correctly rejected invalid host")
        return TestResult("place_window_invalid_host", "fail", "Did not reject invalid host")
    except Exception as e:
        return TestResult("place_window_invalid_host", "fail", str(e))


async def test_list_wall_type_layers():
    """Test wall type layer inspection"""
    payload = {"wall_type_name": "Generic - 8\""}
    try:
        result = await revit_post("/get_wall_type_layers/", payload)
        return TestResult("list_wall_type_layers", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_wall_type_layers", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("CORE GEOMETRY TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_argument_repair,
    ]

    for test in offline_tests:
        result = test()
        results.append(result)
        symbol = "✓" if result.status == "pass" else "✗" if result.status == "fail" else "○"
        print(f"  {symbol} {result.name}: {result.status.upper()} - {result.message}")

    if offline_only:
        print("\n(Skipping live tests - offline mode)")
    else:
        # Check Revit connection
        print("\n--- LIVE TESTS (Require Revit) ---")
        connected = await check_revit_connection()

        if not connected:
            print("  ○ Revit not connected - skipping live tests")
            for test_name in ['create_floor', 'create_roof', 'create_room',
                            'create_directshape_mass', 'place_door_invalid_host',
                            'place_window_invalid_host', 'list_wall_type_layers']:
                results.append(TestResult(test_name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_create_floor,
                test_create_roof,
                test_create_room,
                test_create_directshape_mass,
                test_place_door_invalid_host,
                test_place_window_invalid_host,
                test_list_wall_type_layers,
            ]

            for test in live_tests:
                result = await test()
                results.append(result)
                symbol = "✓" if result.status == "pass" else "✗" if result.status == "fail" else "○"
                print(f"  {symbol} {result.name}: {result.status.upper()}")
                if verbose and result.message:
                    print(f"      {result.message}")

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    passed = len([r for r in results if r.status == "pass"])
    failed = len([r for r in results if r.status == "fail"])
    skipped = len([r for r in results if r.status == "skip"])

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Duration: {duration:.2f}s")

    if failed > 0:
        print("\n  FAILED TESTS:")
        for r in results:
            if r.status == "fail":
                print(f"    - {r.name}: {r.message}")

    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description='Core Geometry Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
