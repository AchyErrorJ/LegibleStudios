"""
View Filter Tools Test Suite

Tests the view filter, visibility/graphics, and template tools in RevitMCP:
- Filter discovery: list_view_filters, get_filter_details, list_filters_in_view
- Filter creation: create_selection_filter, create_rule_filter, create_parameter_filter
- Filter application: add_filter_to_view, set_filter_visibility, set_filter_overrides
- Category visibility: get_category_visibility, set_category_visibility, set_category_overrides
- Element overrides: set_element_override, hide_elements_in_view, isolate_elements_in_view
- View templates: list_view_templates, create_view_template_from_view, apply_view_template
- Worksets: list_worksets, set_workset_visibility

Usage:
    python tests/test_view_filter_tools.py              # Run all tests
    python tests/test_view_filter_tools.py --offline    # Run offline validation only
    python tests/test_view_filter_tools.py --verbose    # Verbose output

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
from tools import view_filter_tools

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
    """Verify all view filter tools are registered"""
    expected_tools = [
        # Filter discovery
        'list_view_filters', 'get_filter_details', 'list_filters_in_view',
        # Filter creation
        'create_selection_filter', 'create_rule_filter', 'create_parameter_filter', 'delete_filter',
        # Filter application
        'add_filter_to_view', 'remove_filter_from_view', 'set_filter_visibility', 'set_filter_overrides',
        # Category visibility
        'get_category_visibility', 'set_category_visibility', 'set_category_overrides', 'reset_category_overrides',
        # Element overrides
        'set_element_override', 'hide_elements_in_view', 'unhide_elements_in_view',
        'isolate_elements_in_view', 'reset_temporary_hide_isolate',
        # View templates
        'list_view_templates', 'create_view_template_from_view', 'apply_view_template', 'remove_view_template',
        # Worksets
        'list_worksets', 'set_workset_visibility'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'list_view_filters', 'create_rule_filter', 'set_filter_overrides',
        'set_category_visibility', 'apply_view_template'
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


def test_filter_discovery_tools():
    """Verify filter discovery tools exist"""
    tools = ['list_view_filters', 'get_filter_details', 'list_filters_in_view']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("filter_discovery", "fail", f"Missing: {missing}")
    return TestResult("filter_discovery", "pass", "All 3 filter discovery tools exist")


def test_filter_creation_tools():
    """Verify filter creation tools exist"""
    tools = ['create_selection_filter', 'create_rule_filter', 'create_parameter_filter', 'delete_filter']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("filter_creation", "fail", f"Missing: {missing}")
    return TestResult("filter_creation", "pass", "All 4 filter creation tools exist")


def test_filter_application_tools():
    """Verify filter application tools exist"""
    tools = ['add_filter_to_view', 'remove_filter_from_view', 'set_filter_visibility', 'set_filter_overrides']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("filter_application", "fail", f"Missing: {missing}")
    return TestResult("filter_application", "pass", "All 4 filter application tools exist")


def test_category_visibility_tools():
    """Verify category visibility tools exist"""
    tools = ['get_category_visibility', 'set_category_visibility', 'set_category_overrides', 'reset_category_overrides']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("category_visibility", "fail", f"Missing: {missing}")
    return TestResult("category_visibility", "pass", "All 4 category visibility tools exist")


def test_element_override_tools():
    """Verify element override tools exist"""
    tools = ['set_element_override', 'hide_elements_in_view', 'unhide_elements_in_view',
             'isolate_elements_in_view', 'reset_temporary_hide_isolate']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("element_overrides", "fail", f"Missing: {missing}")
    return TestResult("element_overrides", "pass", "All 5 element override tools exist")


def test_view_template_tools():
    """Verify view template tools exist"""
    tools = ['list_view_templates', 'create_view_template_from_view', 'apply_view_template', 'remove_view_template']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("view_templates", "fail", f"Missing: {missing}")
    return TestResult("view_templates", "pass", "All 4 view template tools exist")


def test_workset_tools():
    """Verify workset tools exist"""
    tools = ['list_worksets', 'set_workset_visibility']

    missing = [t for t in tools if not hasattr(view_filter_tools, t)]

    if missing:
        return TestResult("workset_tools", "fail", f"Missing: {missing}")
    return TestResult("workset_tools", "pass", "Both workset tools exist")


def test_rule_filter_params():
    """Verify rule filter has categories and rules params"""
    import inspect
    sig = inspect.signature(view_filter_tools.create_rule_filter)
    params = sig.parameters

    checks = []
    if 'categories' in params:
        checks.append("categories")
    if 'rules' in params:
        checks.append("rules")

    if len(checks) >= 2:
        return TestResult("rule_filter_params", "pass", f"Found: {', '.join(checks)}")
    return TestResult("rule_filter_params", "fail", f"Missing params")


def test_filter_overrides_params():
    """Verify filter overrides has color and transparency params"""
    import inspect
    sig = inspect.signature(view_filter_tools.set_filter_overrides)
    params = sig.parameters

    expected = ['projection_color', 'surface_color', 'transparency', 'halftone']
    found = [p for p in expected if p in params]

    if len(found) >= 3:
        return TestResult("filter_overrides_params", "pass", f"Found: {len(found)} params")
    return TestResult("filter_overrides_params", "fail", f"Missing params")


def test_category_overrides_params():
    """Verify category overrides has detail_level param"""
    import inspect
    sig = inspect.signature(view_filter_tools.set_category_overrides)
    params = sig.parameters

    if 'detail_level' in params:
        return TestResult("category_detail_level", "pass", "detail_level parameter exists")
    return TestResult("category_detail_level", "fail", "No detail_level parameter")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_view_filters():
    """Test listing view filters"""
    try:
        result = await revit_get("/list_view_filters/")
        return TestResult("list_view_filters", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_view_filters", "fail", str(e))


async def test_list_view_templates():
    """Test listing view templates"""
    try:
        result = await revit_get("/list_view_templates/")
        return TestResult("list_view_templates", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_view_templates", "fail", str(e))


async def test_list_worksets():
    """Test listing worksets"""
    try:
        result = await revit_get("/list_worksets/")
        return TestResult("list_worksets", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_worksets", "fail", str(e))


async def test_get_filter_details_invalid():
    """Test get filter details with invalid ID"""
    payload = {"filter_id": 999999999}
    try:
        result = await revit_post("/get_filter_details/", payload)
        return TestResult("get_filter_details_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("get_filter_details_invalid", "fail", str(e))


async def test_list_filters_in_view_invalid():
    """Test list filters in view with invalid ID"""
    payload = {"view_id": 999999999}
    try:
        result = await revit_post("/list_filters_in_view/", payload)
        return TestResult("list_filters_in_view_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("list_filters_in_view_invalid", "fail", str(e))


async def test_get_category_visibility_invalid():
    """Test get category visibility with invalid ID"""
    payload = {"view_id": 999999999, "category_name": "Walls"}
    try:
        result = await revit_post("/get_category_visibility/", payload)
        return TestResult("get_category_visibility_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("get_category_visibility_invalid", "fail", str(e))


async def test_set_category_visibility_invalid():
    """Test set category visibility with invalid ID"""
    payload = {"view_id": 999999999, "category_name": "Walls", "visible": False}
    try:
        result = await revit_post("/set_category_visibility/", payload)
        return TestResult("set_category_visibility_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("set_category_visibility_invalid", "fail", str(e))


async def test_hide_elements_invalid():
    """Test hide elements with invalid IDs"""
    payload = {"view_id": 999999999, "element_ids": [999999999]}
    try:
        result = await revit_post("/hide_elements/", payload)
        return TestResult("hide_elements_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("hide_elements_invalid", "fail", str(e))


async def test_apply_view_template_invalid():
    """Test apply view template with invalid IDs"""
    payload = {"view_id": 999999999, "template_id": 999999999}
    try:
        result = await revit_post("/apply_view_template/", payload)
        return TestResult("apply_template_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("apply_template_invalid", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("VIEW FILTER TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_filter_discovery_tools,
        test_filter_creation_tools,
        test_filter_application_tools,
        test_category_visibility_tools,
        test_element_override_tools,
        test_view_template_tools,
        test_workset_tools,
        test_rule_filter_params,
        test_filter_overrides_params,
        test_category_overrides_params,
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
                'list_view_filters', 'list_view_templates', 'list_worksets',
                'get_filter_details_invalid', 'list_filters_in_view_invalid',
                'get_category_visibility_invalid', 'set_category_visibility_invalid',
                'hide_elements_invalid', 'apply_template_invalid'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  + Revit connected")

            live_tests = [
                test_list_view_filters,
                test_list_view_templates,
                test_list_worksets,
                test_get_filter_details_invalid,
                test_list_filters_in_view_invalid,
                test_get_category_visibility_invalid,
                test_set_category_visibility_invalid,
                test_hide_elements_invalid,
                test_apply_view_template_invalid,
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
    parser = argparse.ArgumentParser(description='View Filter Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
