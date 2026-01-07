"""
Stair Tools Test Suite

Tests the stair and railing tools in RevitMCP:
- Discovery: list_stair_types, list_railing_types, list_stairs, list_railings
- Stair Creation: create_stair_by_run, create_u_shaped_stair, create_l_shaped_stair, create_spiral_stair
- Railing Creation: create_railing, create_railing_on_floor_edge
- Modification: modify_stair_properties, modify_railing
- Code Compliance: check_stair_code_compliance

Usage:
    python tests/test_stair_tools.py              # Run all tests
    python tests/test_stair_tools.py --offline    # Run offline validation only
    python tests/test_stair_tools.py --verbose    # Verbose output

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
from tools import stair_tools

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
    """Verify all stair tools are registered"""
    expected_tools = [
        # Discovery
        'list_stair_types', 'list_railing_types', 'list_stairs', 'list_railings',
        # Stair creation
        'create_stair_by_run', 'create_stair_by_sketch',
        'create_u_shaped_stair', 'create_l_shaped_stair', 'create_spiral_stair',
        # Modification
        'modify_stair_properties', 'get_stair_info',
        # Railings
        'create_railing', 'create_railing_on_floor_edge', 'modify_railing',
        # Landing
        'add_stair_landing',
        # Code compliance
        'check_stair_code_compliance'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_stair_by_run', 'create_u_shaped_stair', 'create_railing',
        'check_stair_code_compliance', 'modify_stair_properties'
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


def test_validation_imports():
    """Verify validation helpers are imported"""
    import inspect
    source = inspect.getsource(stair_tools)

    validators = ['validate_point', 'validate_level_name', 'validate_positive']
    found = [v for v in validators if v in source]

    if len(found) >= 2:
        return TestResult("validation_imports", "pass", f"Found: {', '.join(found)}")
    return TestResult("validation_imports", "fail", f"Missing validators")


def test_stair_shapes_covered():
    """Verify all stair shapes have creation tools"""
    shapes = [
        ('straight', 'create_stair_by_run'),
        ('u_shaped', 'create_u_shaped_stair'),
        ('l_shaped', 'create_l_shaped_stair'),
        ('spiral', 'create_spiral_stair'),
        ('sketch', 'create_stair_by_sketch')
    ]

    missing = []
    for shape, tool in shapes:
        if not hasattr(stair_tools, tool):
            missing.append(shape)

    if missing:
        return TestResult("stair_shapes", "fail", f"Missing: {missing}")
    return TestResult("stair_shapes", "pass", "All 5 stair shapes covered")


def test_default_parameters():
    """Test default parameter values"""
    import inspect
    sig = inspect.signature(stair_tools.create_stair_by_run)
    params = sig.parameters

    checks = []
    if params.get("width") and params["width"].default == 3.0:
        checks.append("width=3.0")
    if params.get("include_railing") and params["include_railing"].default == True:
        checks.append("include_railing=True")

    if len(checks) >= 2:
        return TestResult("default_params", "pass", f"Found: {', '.join(checks)}")
    return TestResult("default_params", "fail", f"Missing defaults, found: {checks}")


def test_turn_directions():
    """Verify L-shaped stair has turn direction parameter"""
    import inspect
    sig = inspect.signature(stair_tools.create_l_shaped_stair)
    params = sig.parameters

    if 'turn_direction' in params:
        default = params['turn_direction'].default
        return TestResult("turn_directions", "pass", f"turn_direction param with default='{default}'")
    return TestResult("turn_directions", "fail", "No turn_direction parameter")


def test_code_compliance_options():
    """Verify code compliance tool has code options"""
    import inspect
    source = inspect.getsource(stair_tools.check_stair_code_compliance)

    codes = ['IBC2021', 'IBC2018', 'IRC']
    found = [c for c in codes if c in source]

    if len(found) >= 2:
        return TestResult("code_options", "pass", f"Codes: {', '.join(found)}")
    return TestResult("code_options", "fail", "Missing code options")


def test_railing_host_option():
    """Verify railing can be hosted on stair"""
    import inspect
    sig = inspect.signature(stair_tools.create_railing)
    params = sig.parameters

    if 'host_stair_id' in params:
        return TestResult("railing_host", "pass", "host_stair_id parameter exists")
    return TestResult("railing_host", "fail", "No host_stair_id parameter")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_stair_types():
    """Test listing stair types"""
    try:
        result = await revit_get("/list_stair_types/")
        return TestResult("list_stair_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_stair_types", "fail", str(e))


async def test_list_railing_types():
    """Test listing railing types"""
    try:
        result = await revit_get("/list_railing_types/")
        return TestResult("list_railing_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_railing_types", "fail", str(e))


async def test_list_stairs():
    """Test listing stairs"""
    try:
        result = await revit_get("/list_stairs/")
        return TestResult("list_stairs", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_stairs", "fail", str(e))


async def test_create_stair_by_run():
    """Test straight stair creation"""
    payload = {
        "base_level_name": "Level 1",
        "top_level_name": "Level 2",
        "start_point": [100, 100, 0],
        "end_point": [115, 100, 0],
        "width": 3.0,
        "include_railing": True
    }
    try:
        result = await revit_post("/create_stair_by_run/", payload)
        return TestResult("create_stair_by_run", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_stair_by_run", "fail", str(e))


async def test_create_u_shaped_stair():
    """Test U-shaped stair creation"""
    payload = {
        "base_level_name": "Level 1",
        "top_level_name": "Level 2",
        "start_point": [130, 100, 0],
        "first_run_direction": "X",
        "width": 3.0,
        "landing_length": 4.0
    }
    try:
        result = await revit_post("/create_u_shaped_stair/", payload)
        return TestResult("create_u_shaped_stair", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_u_shaped_stair", "fail", str(e))


async def test_create_l_shaped_stair():
    """Test L-shaped stair creation"""
    payload = {
        "base_level_name": "Level 1",
        "top_level_name": "Level 2",
        "start_point": [160, 100, 0],
        "first_run_direction": "X",
        "turn_direction": "left",
        "width": 3.0
    }
    try:
        result = await revit_post("/create_l_shaped_stair/", payload)
        return TestResult("create_l_shaped_stair", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_l_shaped_stair", "fail", str(e))


async def test_create_spiral_stair():
    """Test spiral stair creation"""
    payload = {
        "base_level_name": "Level 1",
        "top_level_name": "Level 2",
        "center_point": [190, 100, 0],
        "radius": 5.0,
        "clockwise": True,
        "start_angle": 0.0
    }
    try:
        result = await revit_post("/create_spiral_stair/", payload)
        return TestResult("create_spiral_stair", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_spiral_stair", "fail", str(e))


async def test_create_railing():
    """Test railing creation"""
    payload = {
        "path_points": [[200, 100, 0], [210, 100, 0], [210, 110, 0]],
        "level_name": "Level 1"
    }
    try:
        result = await revit_post("/create_railing/", payload)
        return TestResult("create_railing", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_railing", "fail", str(e))


async def test_check_code_compliance_invalid():
    """Test code compliance with invalid stair ID"""
    payload = {
        "stair_id": 999999999,
        "code": "IBC2021",
        "occupancy": "residential"
    }
    try:
        result = await revit_post("/check_stair_code/", payload)
        return TestResult("check_code_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("check_code_invalid", "fail", str(e))


async def test_get_stair_info_invalid():
    """Test get stair info with invalid ID"""
    payload = {"stair_id": 999999999}
    try:
        result = await revit_post("/get_stair_info/", payload)
        return TestResult("get_stair_info_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("get_stair_info_invalid", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("STAIR TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_validation_imports,
        test_stair_shapes_covered,
        test_default_parameters,
        test_turn_directions,
        test_code_compliance_options,
        test_railing_host_option,
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
                'list_stair_types', 'list_railing_types', 'list_stairs',
                'create_stair_by_run', 'create_u_shaped_stair', 'create_l_shaped_stair',
                'create_spiral_stair', 'create_railing',
                'check_code_invalid', 'get_stair_info_invalid'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_list_stair_types,
                test_list_railing_types,
                test_list_stairs,
                test_create_stair_by_run,
                test_create_u_shaped_stair,
                test_create_l_shaped_stair,
                test_create_spiral_stair,
                test_create_railing,
                test_check_code_compliance_invalid,
                test_get_stair_info_invalid,
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
    parser = argparse.ArgumentParser(description='Stair Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
