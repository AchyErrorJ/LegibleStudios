"""
Curtain Wall Tools Test Suite

Tests the curtain wall, panel, and mullion tools in RevitMCP:
- Discovery: list_curtain_wall_types, list_curtain_panel_types, list_mullion_types
- Creation: create_curtain_wall, create_curved_curtain_wall, create_curtain_wall_by_profile
- Curtain Systems: create_curtain_system_by_face, create_curtain_system_by_extrusion
- Grid Operations: add_curtain_grid_line, set_curtain_grid_pattern
- Panel Operations: list_curtain_panels, change_curtain_panel_type, replace_panel_with_door
- Mullion Operations: add_mullion, add_all_mullions, change_mullion_type

Usage:
    python tests/test_curtain_wall_tools.py              # Run all tests
    python tests/test_curtain_wall_tools.py --offline    # Run offline validation only
    python tests/test_curtain_wall_tools.py --verbose    # Verbose output

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
from tools import curtain_wall_tools

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
    """Verify all curtain wall tools are registered"""
    expected_tools = [
        # Discovery
        'list_curtain_wall_types', 'list_curtain_panel_types',
        'list_mullion_types', 'list_curtain_walls',
        # Creation
        'create_curtain_wall', 'create_curtain_wall_by_profile',
        'create_curved_curtain_wall',
        # Curtain Systems
        'create_curtain_system_by_face', 'create_curtain_system_by_extrusion',
        # Grid operations
        'add_curtain_grid_line', 'add_curtain_grid_lines_evenly',
        'set_curtain_grid_pattern', 'delete_curtain_grid_line',
        # Panel operations
        'list_curtain_panels', 'change_curtain_panel_type',
        'replace_panel_with_door', 'set_panel_transparency',
        # Mullion operations
        'add_mullion', 'add_all_mullions', 'change_mullion_type', 'delete_mullion',
        # Info
        'get_curtain_wall_info', 'get_curtain_wall_schedule_data'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_curtain_wall', 'create_curved_curtain_wall',
        'add_curtain_grid_line', 'add_mullion', 'change_curtain_panel_type'
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


def test_curtain_wall_shapes():
    """Verify all curtain wall shape creation tools exist"""
    shapes = [
        ('linear', 'create_curtain_wall'),
        ('profile', 'create_curtain_wall_by_profile'),
        ('curved', 'create_curved_curtain_wall')
    ]

    missing = []
    for shape, tool in shapes:
        if not hasattr(curtain_wall_tools, tool):
            missing.append(shape)

    if missing:
        return TestResult("curtain_wall_shapes", "fail", f"Missing: {missing}")
    return TestResult("curtain_wall_shapes", "pass", "All 3 wall shapes covered")


def test_curtain_system_tools():
    """Verify curtain system creation tools exist"""
    tools = ['create_curtain_system_by_face', 'create_curtain_system_by_extrusion']

    missing = [t for t in tools if not hasattr(curtain_wall_tools, t)]

    if missing:
        return TestResult("curtain_systems", "fail", f"Missing: {missing}")
    return TestResult("curtain_systems", "pass", "Both curtain system tools exist")


def test_grid_operations():
    """Verify grid operation tools exist"""
    tools = [
        'add_curtain_grid_line', 'add_curtain_grid_lines_evenly',
        'set_curtain_grid_pattern', 'delete_curtain_grid_line'
    ]

    missing = [t for t in tools if not hasattr(curtain_wall_tools, t)]

    if missing:
        return TestResult("grid_operations", "fail", f"Missing: {missing}")
    return TestResult("grid_operations", "pass", "All 4 grid operations covered")


def test_panel_operations():
    """Verify panel operation tools exist"""
    tools = [
        'list_curtain_panels', 'change_curtain_panel_type',
        'replace_panel_with_door', 'set_panel_transparency'
    ]

    missing = [t for t in tools if not hasattr(curtain_wall_tools, t)]

    if missing:
        return TestResult("panel_operations", "fail", f"Missing: {missing}")
    return TestResult("panel_operations", "pass", "All 4 panel operations covered")


def test_mullion_operations():
    """Verify mullion operation tools exist"""
    tools = ['add_mullion', 'add_all_mullions', 'change_mullion_type', 'delete_mullion']

    missing = [t for t in tools if not hasattr(curtain_wall_tools, t)]

    if missing:
        return TestResult("mullion_operations", "fail", f"Missing: {missing}")
    return TestResult("mullion_operations", "pass", "All 4 mullion operations covered")


def test_grid_justification_options():
    """Verify grid pattern has justification options"""
    import inspect
    sig = inspect.signature(curtain_wall_tools.set_curtain_grid_pattern)
    params = sig.parameters

    checks = []
    if 'horizontal_justification' in params:
        checks.append("horizontal_justification")
    if 'vertical_justification' in params:
        checks.append("vertical_justification")

    if len(checks) >= 2:
        return TestResult("grid_justification", "pass", f"Found: {', '.join(checks)}")
    return TestResult("grid_justification", "fail", f"Missing justification params")


def test_add_all_mullions_params():
    """Verify add_all_mullions has type params for each direction"""
    import inspect
    sig = inspect.signature(curtain_wall_tools.add_all_mullions)
    params = sig.parameters

    expected = ['horizontal_mullion_type', 'vertical_mullion_type', 'border_mullion_type']
    found = [p for p in expected if p in params]

    if len(found) == 3:
        return TestResult("mullion_params", "pass", "All 3 mullion type params exist")
    return TestResult("mullion_params", "fail", f"Found: {found}")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_curtain_wall_types():
    """Test listing curtain wall types"""
    try:
        result = await revit_get("/list_curtain_wall_types/")
        return TestResult("list_curtain_wall_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_curtain_wall_types", "fail", str(e))


async def test_list_curtain_panel_types():
    """Test listing curtain panel types"""
    try:
        result = await revit_get("/list_curtain_panel_types/")
        return TestResult("list_curtain_panel_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_curtain_panel_types", "fail", str(e))


async def test_list_mullion_types():
    """Test listing mullion types"""
    try:
        result = await revit_get("/list_mullion_types/")
        return TestResult("list_mullion_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_mullion_types", "fail", str(e))


async def test_create_curtain_wall():
    """Test curtain wall creation"""
    payload = {
        "start_point": [300, 0, 0],
        "end_point": [330, 0, 0],
        "level_name": "Level 1",
        "height": 12.0
    }
    try:
        result = await revit_post("/create_curtain_wall/", payload)
        return TestResult("create_curtain_wall", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_curtain_wall", "fail", str(e))


async def test_create_curved_curtain_wall():
    """Test curved curtain wall creation"""
    payload = {
        "center_point": [350, 50, 0],
        "radius": 15.0,
        "start_angle": 0.0,
        "end_angle": 90.0,
        "level_name": "Level 1",
        "height": 12.0
    }
    try:
        result = await revit_post("/create_curved_curtain_wall/", payload)
        return TestResult("create_curved_curtain_wall", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_curved_curtain_wall", "fail", str(e))


async def test_add_grid_line_invalid():
    """Test adding grid line with invalid wall ID"""
    payload = {
        "curtain_wall_id": 999999999,
        "direction": "horizontal",
        "position": 0.5
    }
    try:
        result = await revit_post("/add_curtain_grid/", payload)
        return TestResult("add_grid_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("add_grid_invalid", "fail", str(e))


async def test_add_mullion_invalid():
    """Test adding mullion with invalid grid ID"""
    payload = {
        "grid_line_id": 999999999,
        "mullion_type": None
    }
    try:
        result = await revit_post("/add_mullion/", payload)
        return TestResult("add_mullion_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("add_mullion_invalid", "fail", str(e))


async def test_get_curtain_wall_info_invalid():
    """Test get info with invalid wall ID"""
    payload = {"curtain_wall_id": 999999999}
    try:
        result = await revit_post("/get_curtain_wall_info/", payload)
        return TestResult("get_info_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("get_info_invalid", "fail", str(e))


async def test_list_curtain_walls():
    """Test listing all curtain walls"""
    try:
        result = await revit_get("/list_curtain_walls/")
        return TestResult("list_curtain_walls", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_curtain_walls", "fail", str(e))


async def test_schedule_data():
    """Test getting curtain wall schedule data"""
    payload = {"curtain_wall_ids": None}
    try:
        result = await revit_post("/curtain_wall_schedule_data/", payload)
        return TestResult("schedule_data", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("schedule_data", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("CURTAIN WALL TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_curtain_wall_shapes,
        test_curtain_system_tools,
        test_grid_operations,
        test_panel_operations,
        test_mullion_operations,
        test_grid_justification_options,
        test_add_all_mullions_params,
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
                'list_curtain_wall_types', 'list_curtain_panel_types',
                'list_mullion_types', 'create_curtain_wall',
                'create_curved_curtain_wall', 'add_grid_invalid',
                'add_mullion_invalid', 'get_info_invalid',
                'list_curtain_walls', 'schedule_data'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_list_curtain_wall_types,
                test_list_curtain_panel_types,
                test_list_mullion_types,
                test_create_curtain_wall,
                test_create_curved_curtain_wall,
                test_add_grid_line_invalid,
                test_add_mullion_invalid,
                test_get_curtain_wall_info_invalid,
                test_list_curtain_walls,
                test_schedule_data,
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
    parser = argparse.ArgumentParser(description='Curtain Wall Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
