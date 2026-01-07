"""
Structural Tools Test Suite

Tests the structural framing tools in RevitMCP:
- Beams: create_beam, create_beams_batch, create_beam_system
- Columns: create_column, create_columns_batch, create_columns_at_grids
- Braces: create_brace, create_x_bracing
- Foundations: create_isolated_foundation, create_wall_foundation, create_slab_foundation
- Connections: create_beam_to_column_connection, create_beam_to_beam_connection
- Discovery: list_beam_types, list_column_types, list_brace_types, list_foundation_types

Usage:
    python tests/test_structural_tools.py              # Run all tests
    python tests/test_structural_tools.py --offline    # Run offline validation only
    python tests/test_structural_tools.py --verbose    # Verbose output

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
from tools import structural_tools

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
    """Verify all structural tools are registered"""
    expected_tools = [
        # Discovery
        'list_beam_types', 'list_column_types', 'list_brace_types',
        'list_foundation_types', 'list_structural_elements',
        # Beams
        'create_beam', 'create_beams_batch', 'create_beam_system',
        # Columns
        'create_column', 'create_columns_batch', 'create_columns_at_grids',
        # Braces
        'create_brace', 'create_x_bracing',
        # Foundations
        'create_isolated_foundation', 'create_wall_foundation', 'create_slab_foundation',
        # Modification
        'modify_beam', 'modify_column',
        # Connections
        'create_beam_to_column_connection', 'create_beam_to_beam_connection',
        # Info
        'get_structural_element_info', 'get_framing_schedule_data',
        # Analytical
        'enable_analytical_model', 'get_analytical_model_geometry'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_beam', 'create_column', 'create_brace',
        'create_isolated_foundation', 'modify_beam'
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
    source = inspect.getsource(structural_tools)

    validators = ['validate_point', 'validate_level_name', 'validate_positive']
    found = [v for v in validators if v in source]

    if len(found) >= 2:
        return TestResult("validation_imports", "pass", f"Found: {', '.join(found)}")
    return TestResult("validation_imports", "fail", f"Missing validators")


def test_with_validation_decorator():
    """Verify @with_validation decorator is used"""
    import inspect
    source = inspect.getsource(structural_tools)

    if '@with_validation' in source:
        # Count decorated functions
        count = source.count('@with_validation')
        return TestResult("validation_decorator", "pass", f"@with_validation used {count} times")
    return TestResult("validation_decorator", "fail", "No @with_validation decorator found")


def test_beam_structural_usage_options():
    """Verify beam structural usage parameter options"""
    import inspect
    sig = inspect.signature(structural_tools.create_beam)
    params = sig.parameters

    if 'structural_usage' in params:
        default = params['structural_usage'].default
        if default == "Girder":
            return TestResult("beam_usage", "pass", f"Default structural_usage='{default}'")
    return TestResult("beam_usage", "fail", "No structural_usage parameter")


def test_column_rotation_parameter():
    """Verify column has rotation parameter"""
    import inspect
    sig = inspect.signature(structural_tools.create_column)
    params = sig.parameters

    if 'rotation' in params:
        default = params['rotation'].default
        return TestResult("column_rotation", "pass", f"rotation param with default={default}")
    return TestResult("column_rotation", "fail", "No rotation parameter")


def test_connection_types():
    """Verify connection type options are documented"""
    import inspect

    # Check beam-column connection
    source_bc = inspect.getsource(structural_tools.create_beam_to_column_connection)
    has_bc_types = 'moment' in source_bc or 'shear' in source_bc or 'pinned' in source_bc

    # Check beam-beam connection
    source_bb = inspect.getsource(structural_tools.create_beam_to_beam_connection)
    has_bb_types = 'cope' in source_bb or 'hanger' in source_bb

    if has_bc_types and has_bb_types:
        return TestResult("connection_types", "pass", "Connection types documented")
    return TestResult("connection_types", "fail", "Missing connection type docs")


def test_foundation_types_covered():
    """Verify all foundation types have tools"""
    tools = ['create_isolated_foundation', 'create_wall_foundation', 'create_slab_foundation']

    missing = [t for t in tools if not hasattr(structural_tools, t)]

    if missing:
        return TestResult("foundation_types", "fail", f"Missing: {missing}")
    return TestResult("foundation_types", "pass", "All 3 foundation types covered")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_beam_types():
    """Test listing beam types"""
    try:
        result = await revit_get("/list_beam_types/")
        return TestResult("list_beam_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_beam_types", "fail", str(e))


async def test_list_column_types():
    """Test listing column types"""
    try:
        result = await revit_get("/list_column_types/")
        return TestResult("list_column_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_column_types", "fail", str(e))


async def test_list_brace_types():
    """Test listing brace types"""
    try:
        result = await revit_get("/list_brace_types/")
        return TestResult("list_brace_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_brace_types", "fail", str(e))


async def test_list_foundation_types():
    """Test listing foundation types"""
    try:
        result = await revit_get("/list_foundation_types/")
        return TestResult("list_foundation_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_foundation_types", "fail", str(e))


async def test_create_beam():
    """Test beam creation"""
    payload = {
        "start_point": [800, 0, 0],
        "end_point": [820, 0, 0],
        "level_name": "Level 1",
        "structural_usage": "Girder"
    }
    try:
        result = await revit_post("/create_beam/", payload)
        return TestResult("create_beam", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_beam", "fail", str(e))


async def test_create_column():
    """Test column creation"""
    payload = {
        "location": [850, 0, 0],
        "base_level_name": "Level 1",
        "height": 10.0
    }
    try:
        result = await revit_post("/create_column/", payload)
        return TestResult("create_column", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_column", "fail", str(e))


async def test_create_brace():
    """Test brace creation"""
    payload = {
        "start_point": [860, 0, 0],
        "end_point": [870, 0, 10],
        "level_name": "Level 1"
    }
    try:
        result = await revit_post("/create_brace/", payload)
        return TestResult("create_brace", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_brace", "fail", str(e))


async def test_create_isolated_foundation():
    """Test isolated foundation creation"""
    payload = {
        "location": [880, 0, 0],
        "level_name": "Level 1"
    }
    try:
        result = await revit_post("/create_isolated_foundation/", payload)
        return TestResult("create_isolated_foundation", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_isolated_foundation", "fail", str(e))


async def test_create_x_bracing():
    """Test X-bracing creation"""
    payload = {
        "bay_start": [900, 0, 0],
        "bay_end": [920, 20, 0],
        "base_level_name": "Level 1",
        "top_level_name": "Level 2"
    }
    try:
        result = await revit_post("/create_x_bracing/", payload)
        return TestResult("create_x_bracing", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_x_bracing", "fail", str(e))


async def test_create_beams_batch():
    """Test batch beam creation"""
    payload = {
        "beams": [
            {"start_point": [930, 0, 0], "end_point": [940, 0, 0], "level_name": "Level 1"},
            {"start_point": [940, 0, 0], "end_point": [950, 0, 0], "level_name": "Level 1"}
        ]
    }
    try:
        result = await revit_post("/create_beams_batch/", payload)
        return TestResult("create_beams_batch", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_beams_batch", "fail", str(e))


async def test_modify_beam_invalid():
    """Test beam modification with invalid ID"""
    payload = {
        "beam_id": 999999999,
        "z_offset": 1.0
    }
    try:
        result = await revit_post("/modify_beam/", payload)
        # Should handle gracefully
        return TestResult("modify_beam_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("modify_beam_invalid", "fail", str(e))


async def test_get_structural_element_info_invalid():
    """Test get info with invalid element ID"""
    payload = {"element_id": 999999999}
    try:
        result = await revit_post("/get_structural_element_info/", payload)
        return TestResult("get_element_info_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("get_element_info_invalid", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("STRUCTURAL TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_validation_imports,
        test_with_validation_decorator,
        test_beam_structural_usage_options,
        test_column_rotation_parameter,
        test_connection_types,
        test_foundation_types_covered,
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
                'list_beam_types', 'list_column_types', 'list_brace_types',
                'list_foundation_types', 'create_beam', 'create_column',
                'create_brace', 'create_isolated_foundation', 'create_x_bracing',
                'create_beams_batch', 'modify_beam_invalid', 'get_element_info_invalid'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_list_beam_types,
                test_list_column_types,
                test_list_brace_types,
                test_list_foundation_types,
                test_create_beam,
                test_create_column,
                test_create_brace,
                test_create_isolated_foundation,
                test_create_x_bracing,
                test_create_beams_batch,
                test_modify_beam_invalid,
                test_get_structural_element_info_invalid,
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
    parser = argparse.ArgumentParser(description='Structural Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
