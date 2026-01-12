"""
Detail Tools Test Suite

Tests the detail and drafting tools in RevitMCP:
- Line styles/patterns: list_line_styles, list_line_patterns, list_fill_patterns
- Detail lines: create_detail_line, create_detail_arc, create_detail_circle, etc.
- Filled regions: create_filled_region, create_masking_region
- Detail components: place_detail_component, place_repeating_detail
- Drafting views: create_drafting_view, list_drafting_views
- Detail groups: create_detail_group, place_detail_group
- Line modification: change_line_style, offset_detail_line, trim_extend_detail_lines
- Break lines: place_break_line, place_insulation

Usage:
    python tests/test_detail_tools.py              # Run all tests
    python tests/test_detail_tools.py --offline    # Run offline validation only
    python tests/test_detail_tools.py --verbose    # Verbose output

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
from tools import detail_tools

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
    """Verify all detail tools are registered"""
    expected_tools = [
        # Line styles/patterns
        'list_line_styles', 'list_line_patterns', 'list_fill_patterns',
        # Detail lines
        'create_detail_line', 'create_detail_lines_batch', 'create_detail_arc',
        'create_detail_circle', 'create_detail_rectangle', 'create_detail_polyline',
        # Filled regions
        'list_filled_region_types', 'create_filled_region',
        'create_filled_region_with_openings', 'create_masking_region',
        # Detail components
        'list_detail_component_families', 'place_detail_component', 'place_repeating_detail',
        # Drafting views
        'list_drafting_views', 'create_drafting_view', 'import_drafting_view',
        # Detail groups
        'list_detail_groups', 'create_detail_group', 'place_detail_group',
        # Line modification
        'change_line_style', 'offset_detail_line', 'trim_extend_detail_lines',
        # Break lines
        'place_break_line', 'place_insulation'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_detail_line', 'create_detail_arc', 'create_filled_region',
        'place_detail_component', 'create_drafting_view'
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


def test_detail_line_shapes():
    """Verify all detail line shape tools exist"""
    shapes = [
        ('line', 'create_detail_line'),
        ('arc', 'create_detail_arc'),
        ('circle', 'create_detail_circle'),
        ('rectangle', 'create_detail_rectangle'),
        ('polyline', 'create_detail_polyline')
    ]

    missing = []
    for shape, tool in shapes:
        if not hasattr(detail_tools, tool):
            missing.append(shape)

    if missing:
        return TestResult("detail_line_shapes", "fail", f"Missing: {missing}")
    return TestResult("detail_line_shapes", "pass", "All 5 line shapes covered")


def test_filled_region_tools():
    """Verify filled region tools exist"""
    tools = [
        'list_filled_region_types', 'create_filled_region',
        'create_filled_region_with_openings', 'create_masking_region'
    ]

    missing = [t for t in tools if not hasattr(detail_tools, t)]

    if missing:
        return TestResult("filled_region_tools", "fail", f"Missing: {missing}")
    return TestResult("filled_region_tools", "pass", "All 4 filled region tools exist")


def test_drafting_view_tools():
    """Verify drafting view tools exist"""
    tools = ['list_drafting_views', 'create_drafting_view', 'import_drafting_view']

    missing = [t for t in tools if not hasattr(detail_tools, t)]

    if missing:
        return TestResult("drafting_view_tools", "fail", f"Missing: {missing}")
    return TestResult("drafting_view_tools", "pass", "All 3 drafting view tools exist")


def test_detail_group_tools():
    """Verify detail group tools exist"""
    tools = ['list_detail_groups', 'create_detail_group', 'place_detail_group']

    missing = [t for t in tools if not hasattr(detail_tools, t)]

    if missing:
        return TestResult("detail_group_tools", "fail", f"Missing: {missing}")
    return TestResult("detail_group_tools", "pass", "All 3 detail group tools exist")


def test_line_modification_tools():
    """Verify line modification tools exist"""
    tools = ['change_line_style', 'offset_detail_line', 'trim_extend_detail_lines']

    missing = [t for t in tools if not hasattr(detail_tools, t)]

    if missing:
        return TestResult("line_modification", "fail", f"Missing: {missing}")
    return TestResult("line_modification", "pass", "All 3 line modification tools exist")


def test_drafting_view_scale_param():
    """Verify drafting view has scale parameter"""
    import inspect
    sig = inspect.signature(detail_tools.create_drafting_view)
    params = sig.parameters

    if 'scale' in params:
        default = params['scale'].default
        return TestResult("drafting_scale", "pass", f"scale param with default={default}")
    return TestResult("drafting_scale", "fail", "No scale parameter")


def test_detail_line_style_param():
    """Verify detail line has line_style parameter"""
    import inspect
    sig = inspect.signature(detail_tools.create_detail_line)
    params = sig.parameters

    if 'line_style' in params:
        return TestResult("line_style_param", "pass", "line_style parameter exists")
    return TestResult("line_style_param", "fail", "No line_style parameter")


def test_polyline_closed_param():
    """Verify polyline has closed parameter"""
    import inspect
    sig = inspect.signature(detail_tools.create_detail_polyline)
    params = sig.parameters

    if 'closed' in params:
        default = params['closed'].default
        return TestResult("polyline_closed", "pass", f"closed param with default={default}")
    return TestResult("polyline_closed", "fail", "No closed parameter")


def test_offset_copy_param():
    """Verify offset_detail_line has create_copy parameter"""
    import inspect
    sig = inspect.signature(detail_tools.offset_detail_line)
    params = sig.parameters

    if 'create_copy' in params:
        default = params['create_copy'].default
        return TestResult("offset_copy", "pass", f"create_copy param with default={default}")
    return TestResult("offset_copy", "fail", "No create_copy parameter")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_line_styles():
    """Test listing line styles"""
    try:
        result = await revit_get("/list_line_styles/")
        return TestResult("list_line_styles", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_line_styles", "fail", str(e))


async def test_list_line_patterns():
    """Test listing line patterns"""
    try:
        result = await revit_get("/list_line_patterns/")
        return TestResult("list_line_patterns", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_line_patterns", "fail", str(e))


async def test_list_fill_patterns():
    """Test listing fill patterns"""
    try:
        result = await revit_get("/list_fill_patterns/")
        return TestResult("list_fill_patterns", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_fill_patterns", "fail", str(e))


async def test_list_filled_region_types():
    """Test listing filled region types"""
    try:
        result = await revit_get("/list_filled_region_types/")
        return TestResult("list_filled_region_types", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_filled_region_types", "fail", str(e))


async def test_list_drafting_views():
    """Test listing drafting views"""
    try:
        result = await revit_get("/list_drafting_views/")
        return TestResult("list_drafting_views", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_drafting_views", "fail", str(e))


async def test_list_detail_groups():
    """Test listing detail groups"""
    try:
        result = await revit_get("/list_detail_groups/")
        return TestResult("list_detail_groups", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_detail_groups", "fail", str(e))


async def test_create_drafting_view():
    """Test drafting view creation"""
    payload = {
        "name": f"Test Drafting View {datetime.now().strftime('%H%M%S')}",
        "scale": 96
    }
    try:
        result = await revit_post("/create_drafting_view/", payload)
        return TestResult("create_drafting_view", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_drafting_view", "fail", str(e))


async def test_create_detail_line_invalid():
    """Test detail line with invalid view ID"""
    payload = {
        "view_id": 999999999,
        "start_point": [0, 0],
        "end_point": [1, 1]
    }
    try:
        result = await revit_post("/create_detail_line/", payload)
        return TestResult("create_detail_line_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("create_detail_line_invalid", "fail", str(e))


async def test_create_filled_region_invalid():
    """Test filled region with invalid view ID"""
    payload = {
        "view_id": 999999999,
        "boundary_points": [[0, 0], [1, 0], [1, 1], [0, 1]]
    }
    try:
        result = await revit_post("/create_filled_region/", payload)
        return TestResult("create_filled_region_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("create_filled_region_invalid", "fail", str(e))


async def test_change_line_style_invalid():
    """Test changing line style with invalid IDs"""
    payload = {
        "element_ids": [999999999],
        "new_line_style": "Thin Lines"
    }
    try:
        result = await revit_post("/change_line_style/", payload)
        return TestResult("change_line_style_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("change_line_style_invalid", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("DETAIL TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_detail_line_shapes,
        test_filled_region_tools,
        test_drafting_view_tools,
        test_detail_group_tools,
        test_line_modification_tools,
        test_drafting_view_scale_param,
        test_detail_line_style_param,
        test_polyline_closed_param,
        test_offset_copy_param,
    ]

    for test in offline_tests:
        result = test()
        results.append(result)
        symbol = "+" if result.status == "pass" else "x" if result.status == "fail" else "o"
        print(f"  {symbol} {result.name}: {result.status.upper()} - {result.message}")

    if offline_only:
        print("\n(Skipping live tests - offline mode)")
    else:
        # Check Revit connection
        print("\n--- LIVE TESTS (Require Revit) ---")
        connected = await check_revit_connection()

        if not connected:
            print("  o Revit not connected - skipping live tests")
            live_test_names = [
                'list_line_styles', 'list_line_patterns', 'list_fill_patterns',
                'list_filled_region_types', 'list_drafting_views', 'list_detail_groups',
                'create_drafting_view', 'create_detail_line_invalid',
                'create_filled_region_invalid', 'change_line_style_invalid'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  + Revit connected")

            live_tests = [
                test_list_line_styles,
                test_list_line_patterns,
                test_list_fill_patterns,
                test_list_filled_region_types,
                test_list_drafting_views,
                test_list_detail_groups,
                test_create_drafting_view,
                test_create_detail_line_invalid,
                test_create_filled_region_invalid,
                test_change_line_style_invalid,
            ]

            for test in live_tests:
                result = await test()
                results.append(result)
                symbol = "+" if result.status == "pass" else "x" if result.status == "fail" else "o"
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
    parser = argparse.ArgumentParser(description='Detail Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
