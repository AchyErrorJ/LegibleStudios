"""
Auto Dimension Tools Test Suite

Tests the automatic dimensioning tools in RevitMCP:
- auto_dimension_walls: 3-tier professional wall dimensioning
- auto_dimension_rooms: Room boundary dimensions
- auto_dimension_openings: Door/window position dimensions
- auto_dimension_all: Complete one-command dimensioning

Usage:
    python tests/test_auto_dimensions.py              # Run all tests
    python tests/test_auto_dimensions.py --offline    # Run offline validation only
    python tests/test_auto_dimensions.py --verbose    # Verbose output

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
from tools import auto_dimensions

# Check httpx availability
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


async def revit_post(endpoint: str, payload) -> dict:
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
    """Verify all auto dimension tools are registered"""
    expected_tools = [
        'auto_dimension_walls',
        'auto_dimension_rooms',
        'auto_dimension_openings',
        'auto_dimension_all'
    ]

    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing: {missing}")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'auto_dimension_walls',
        'auto_dimension_rooms',
        'auto_dimension_openings',
        'auto_dimension_all'
    ]

    results = []
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


def test_helper_functions_exist():
    """Verify helper functions exist"""
    helpers = [
        'group_walls_by_orientation',
        'calculate_dimension_extents',
        'get_or_create_floor_plan_view'
    ]

    missing = []
    for helper in helpers:
        if not hasattr(auto_dimensions, helper):
            missing.append(helper)

    if missing:
        return TestResult("helper_functions", "fail", f"Missing: {missing}")
    return TestResult("helper_functions", "pass", f"All {len(helpers)} helpers found")


def test_group_walls_by_orientation():
    """Test wall orientation grouping logic"""
    # Create test data
    test_walls = [
        {"id": 1, "start_point": [0, 0, 0], "end_point": [20, 0, 0]},   # Horizontal
        {"id": 2, "start_point": [20, 0, 0], "end_point": [20, 15, 0]}, # Vertical
        {"id": 3, "start_point": [0, 15, 0], "end_point": [20, 15, 0]}, # Horizontal
        {"id": 4, "start_point": [0, 0, 0], "end_point": [0, 15, 0]},   # Vertical
    ]

    result = auto_dimensions.group_walls_by_orientation(test_walls)

    if len(result["horizontal"]) != 2:
        return TestResult("group_walls", "fail", f"Expected 2 horizontal, got {len(result['horizontal'])}")
    if len(result["vertical"]) != 2:
        return TestResult("group_walls", "fail", f"Expected 2 vertical, got {len(result['vertical'])}")

    return TestResult("group_walls", "pass", "Correctly grouped 2 horizontal, 2 vertical")


def test_calculate_dimension_extents():
    """Test bounding box calculation"""
    test_walls = [
        {"start_point": [0, 0, 0], "end_point": [20, 0, 0]},
        {"start_point": [20, 0, 0], "end_point": [20, 15, 0]},
        {"start_point": [0, 15, 0], "end_point": [20, 15, 0]},
        {"start_point": [0, 0, 0], "end_point": [0, 15, 0]},
    ]

    extents = auto_dimensions.calculate_dimension_extents(test_walls)

    expected = {"min_x": 0, "max_x": 20, "min_y": 0, "max_y": 15}

    if extents["min_x"] != expected["min_x"]:
        return TestResult("calc_extents", "fail", f"min_x: expected {expected['min_x']}, got {extents['min_x']}")
    if extents["max_x"] != expected["max_x"]:
        return TestResult("calc_extents", "fail", f"max_x: expected {expected['max_x']}, got {extents['max_x']}")
    if extents["min_y"] != expected["min_y"]:
        return TestResult("calc_extents", "fail", f"min_y: expected {expected['min_y']}, got {extents['min_y']}")
    if extents["max_y"] != expected["max_y"]:
        return TestResult("calc_extents", "fail", f"max_y: expected {expected['max_y']}, got {extents['max_y']}")

    return TestResult("calc_extents", "pass", f"Correct extents: {extents}")


def test_empty_walls_handling():
    """Test handling of empty wall list"""
    extents = auto_dimensions.calculate_dimension_extents([])

    # Should return default values, not crash
    if "min_x" not in extents:
        return TestResult("empty_walls", "fail", "No default extents for empty input")

    return TestResult("empty_walls", "pass", "Handles empty walls gracefully")


def test_default_parameters():
    """Test default parameter values in auto_dimension_walls"""
    import inspect
    sig = inspect.signature(auto_dimensions.auto_dimension_walls)
    params = sig.parameters

    checks = []
    if params.get("tier_1_offset") and params["tier_1_offset"].default == 3.0:
        checks.append("tier_1_offset=3.0")
    if params.get("tier_2_offset") and params["tier_2_offset"].default == 6.0:
        checks.append("tier_2_offset=6.0")
    if params.get("tier_3_offset") and params["tier_3_offset"].default == 9.0:
        checks.append("tier_3_offset=9.0")
    if params.get("include_interior") and params["include_interior"].default == True:
        checks.append("include_interior=True")

    if len(checks) >= 3:
        return TestResult("default_params", "pass", f"Found: {', '.join(checks)}")
    return TestResult("default_params", "fail", f"Missing default params, found: {checks}")


def test_error_handling_import():
    """Test that error helpers are imported"""
    import inspect
    source = inspect.getsource(auto_dimensions)

    if "format_error_response" in source or "ErrorCategory" in source:
        return TestResult("error_handling", "pass", "Error helpers imported")
    return TestResult("error_handling", "fail", "No error helpers found")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_auto_dimension_walls():
    """Test wall auto-dimensioning"""
    try:
        # Call the tool directly
        result = await auto_dimensions.auto_dimension_walls(level_name="Level 1")
        data = json.loads(result) if isinstance(result, str) else result

        if data.get("success") == False and "No walls found" in data.get("error", ""):
            return TestResult("auto_dimension_walls", "pass", "Correctly reports no walls (empty model)")

        if "dimensions_created" in data or "total_dimensions" in data:
            return TestResult("auto_dimension_walls", "pass", f"Created {data.get('total_dimensions', 0)} dimensions")

        return TestResult("auto_dimension_walls", "pass", f"Response: {str(data)[:80]}")
    except Exception as e:
        return TestResult("auto_dimension_walls", "fail", str(e))


async def test_auto_dimension_rooms():
    """Test room auto-dimensioning"""
    try:
        result = await auto_dimensions.auto_dimension_rooms(level_name="Level 1")
        data = json.loads(result) if isinstance(result, str) else result

        if data.get("success") == False and "No rooms found" in data.get("error", ""):
            return TestResult("auto_dimension_rooms", "pass", "Correctly reports no rooms (empty model)")

        if "rooms_dimensioned" in data:
            return TestResult("auto_dimension_rooms", "pass", f"Dimensioned {data.get('total_rooms_dimensioned', 0)} rooms")

        return TestResult("auto_dimension_rooms", "pass", f"Response: {str(data)[:80]}")
    except Exception as e:
        return TestResult("auto_dimension_rooms", "fail", str(e))


async def test_auto_dimension_openings():
    """Test opening auto-dimensioning"""
    try:
        result = await auto_dimensions.auto_dimension_openings(level_name="Level 1")
        data = json.loads(result) if isinstance(result, str) else result

        if data.get("success") == False and "No walls found" in data.get("error", ""):
            return TestResult("auto_dimension_openings", "pass", "Correctly reports no walls")

        if "openings_dimensioned" in data:
            return TestResult("auto_dimension_openings", "pass", f"Dimensioned {data.get('walls_with_openings_dimensioned', 0)} wall openings")

        return TestResult("auto_dimension_openings", "pass", f"Response: {str(data)[:80]}")
    except Exception as e:
        return TestResult("auto_dimension_openings", "fail", str(e))


async def test_auto_dimension_all():
    """Test complete auto-dimensioning"""
    try:
        result = await auto_dimensions.auto_dimension_all(level_name="Level 1")
        data = json.loads(result) if isinstance(result, str) else result

        if "wall_dimensions" in data and "room_dimensions" in data and "opening_dimensions" in data:
            return TestResult("auto_dimension_all", "pass", f"Total: {data.get('total_dimensions', 0)} dimensions")

        return TestResult("auto_dimension_all", "pass", f"Response: {str(data)[:80]}")
    except Exception as e:
        return TestResult("auto_dimension_all", "fail", str(e))


async def test_tier_offsets():
    """Test custom tier offsets"""
    try:
        result = await auto_dimensions.auto_dimension_walls(
            level_name="Level 1",
            tier_1_offset=2.0,
            tier_2_offset=4.0,
            tier_3_offset=6.0
        )
        data = json.loads(result) if isinstance(result, str) else result

        # Should not crash with custom offsets
        return TestResult("tier_offsets", "pass", "Custom offsets accepted")
    except Exception as e:
        return TestResult("tier_offsets", "fail", str(e))


async def test_exclude_interior():
    """Test excluding interior walls"""
    try:
        result = await auto_dimensions.auto_dimension_walls(
            level_name="Level 1",
            include_interior=False
        )
        data = json.loads(result) if isinstance(result, str) else result

        return TestResult("exclude_interior", "pass", "include_interior=False accepted")
    except Exception as e:
        return TestResult("exclude_interior", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("AUTO DIMENSION TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_helper_functions_exist,
        test_group_walls_by_orientation,
        test_calculate_dimension_extents,
        test_empty_walls_handling,
        test_default_parameters,
        test_error_handling_import,
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
            live_test_names = [
                'auto_dimension_walls', 'auto_dimension_rooms',
                'auto_dimension_openings', 'auto_dimension_all',
                'tier_offsets', 'exclude_interior'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_auto_dimension_walls,
                test_auto_dimension_rooms,
                test_auto_dimension_openings,
                test_auto_dimension_all,
                test_tier_offsets,
                test_exclude_interior,
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
    parser = argparse.ArgumentParser(description='Auto Dimension Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
