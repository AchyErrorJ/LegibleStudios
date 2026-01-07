"""
Demo Workflows Test Suite

Tests the high-level demo workflow tools in RevitMCP:
- create_floor_plan_from_description: NL description -> complete floor plan
- document_view: View -> dimensioned sheet placement
- create_room_sections: Generate sections through all rooms

Also tests helper functions:
- parse_description: NL parsing to room requirements
- generate_rooms: Room list generation from parsed description

Usage:
    python tests/test_demo_workflows.py              # Run all tests
    python tests/test_demo_workflows.py --offline    # Run offline validation only
    python tests/test_demo_workflows.py --verbose    # Verbose output

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
from tools import demo_workflows

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
    """Verify all demo workflow tools are registered"""
    expected_tools = [
        'create_floor_plan_from_description',
        'document_view',
        'create_room_sections'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing: {missing}")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_floor_plan_from_description',
        'document_view',
        'create_room_sections'
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


def test_parse_description_bedrooms():
    """Test parse_description extracts bedroom count"""
    parsed = demo_workflows.parse_description("3 bedroom house")
    if parsed.get("bedrooms") == 3:
        return TestResult("parse_bedrooms", "pass", "Correctly parsed 3 bedrooms")
    return TestResult("parse_bedrooms", "fail", f"Got: {parsed.get('bedrooms')}")


def test_parse_description_bathrooms():
    """Test parse_description extracts bathroom count"""
    parsed = demo_workflows.parse_description("2 bath house")
    if parsed.get("bathrooms") == 2:
        return TestResult("parse_bathrooms", "pass", "Correctly parsed 2 bathrooms")
    return TestResult("parse_bathrooms", "fail", f"Got: {parsed.get('bathrooms')}")


def test_parse_description_sqft():
    """Test parse_description extracts square footage"""
    parsed = demo_workflows.parse_description("house with 2500 sqft")
    if parsed.get("target_sqft") == 2500:
        return TestResult("parse_sqft", "pass", "Correctly parsed 2500 sqft")
    return TestResult("parse_sqft", "fail", f"Got: {parsed.get('target_sqft')}")


def test_parse_description_garage():
    """Test parse_description detects garage"""
    parsed = demo_workflows.parse_description("house with garage")
    if parsed.get("has_garage") == True:
        return TestResult("parse_garage", "pass", "Correctly detected garage")
    return TestResult("parse_garage", "fail", f"Got: {parsed.get('has_garage')}")


def test_parse_description_office():
    """Test parse_description detects office"""
    parsed = demo_workflows.parse_description("house with office")
    if parsed.get("has_office") == True:
        return TestResult("parse_office", "pass", "Correctly detected office")
    return TestResult("parse_office", "fail", f"Got: {parsed.get('has_office')}")


def test_parse_description_open_concept():
    """Test parse_description detects open concept"""
    parsed = demo_workflows.parse_description("open floor plan")
    if parsed.get("open_concept") == True:
        return TestResult("parse_open", "pass", "Correctly detected open concept")
    return TestResult("parse_open", "fail", f"Got: {parsed.get('open_concept')}")


def test_generate_rooms_count():
    """Test generate_rooms creates appropriate number of rooms"""
    parsed = {"bedrooms": 3, "bathrooms": 2, "width": 40, "depth": 30,
              "target_sqft": 1200, "has_garage": False, "has_office": False, "open_concept": False}
    rooms = demo_workflows.generate_rooms(parsed)

    # Should have: entry, living, kitchen, dining, primary_bed, 2 more beds, primary_bath, 1 more bath, hallway, laundry
    # That's approximately 11 rooms
    if len(rooms) >= 10:
        return TestResult("generate_rooms_count", "pass", f"Generated {len(rooms)} rooms")
    return TestResult("generate_rooms_count", "fail", f"Only {len(rooms)} rooms")


def test_generate_rooms_with_garage():
    """Test generate_rooms includes garage when specified"""
    parsed = {"bedrooms": 2, "bathrooms": 1, "width": 40, "depth": 30,
              "target_sqft": 1200, "has_garage": True, "has_office": False, "open_concept": False}
    rooms = demo_workflows.generate_rooms(parsed)

    room_types = [r.get("type") for r in rooms]
    if "garage" in room_types:
        return TestResult("generate_garage", "pass", "Garage included in rooms")
    return TestResult("generate_garage", "fail", "Garage not found")


def test_generate_rooms_open_concept():
    """Test generate_rooms excludes dining for open concept"""
    parsed = {"bedrooms": 2, "bathrooms": 1, "width": 40, "depth": 30,
              "target_sqft": 1200, "has_garage": False, "has_office": False, "open_concept": True}
    rooms = demo_workflows.generate_rooms(parsed)

    room_types = [r.get("type") for r in rooms]
    if "dining" not in room_types:
        return TestResult("generate_open", "pass", "Dining excluded for open concept")
    return TestResult("generate_open", "fail", "Dining included despite open concept")


def test_document_view_params():
    """Verify document_view has required parameters"""
    import inspect
    sig = inspect.signature(demo_workflows.document_view)
    params = sig.parameters

    checks = []
    if 'view_name' in params:
        checks.append("view_name")
    if 'sheet_number' in params:
        checks.append("sheet_number")
    if 'add_dimensions' in params:
        checks.append("add_dimensions")

    if len(checks) >= 3:
        return TestResult("document_view_params", "pass", f"Found: {', '.join(checks)}")
    return TestResult("document_view_params", "fail", f"Missing params")


def test_create_room_sections_params():
    """Verify create_room_sections has required parameters"""
    import inspect
    sig = inspect.signature(demo_workflows.create_room_sections)
    params = sig.parameters

    checks = []
    if 'level_name' in params:
        checks.append("level_name")
    if 'room_names' in params:
        checks.append("room_names")
    if 'all_rooms' in params:
        checks.append("all_rooms")

    if len(checks) >= 3:
        return TestResult("room_sections_params", "pass", f"Found: {', '.join(checks)}")
    return TestResult("room_sections_params", "fail", f"Missing params")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_views_for_document():
    """Test listing views (prereq for document_view)"""
    try:
        result = await revit_get("/list_views/")
        return TestResult("list_views", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_views", "fail", str(e))


async def test_list_levels_for_rooms():
    """Test listing levels (prereq for create_room_sections)"""
    try:
        result = await revit_get("/list_levels/")
        return TestResult("list_levels", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_levels", "fail", str(e))


async def test_list_rooms():
    """Test listing rooms"""
    payload = {"category_name": "Rooms"}
    try:
        result = await revit_post("/list_elements/", payload)
        return TestResult("list_rooms", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_rooms", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("DEMO WORKFLOWS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_parse_description_bedrooms,
        test_parse_description_bathrooms,
        test_parse_description_sqft,
        test_parse_description_garage,
        test_parse_description_office,
        test_parse_description_open_concept,
        test_generate_rooms_count,
        test_generate_rooms_with_garage,
        test_generate_rooms_open_concept,
        test_document_view_params,
        test_create_room_sections_params,
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
            live_test_names = ['list_views', 'list_levels', 'list_rooms']
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  + Revit connected")

            live_tests = [
                test_list_views_for_document,
                test_list_levels_for_rooms,
                test_list_rooms,
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
    parser = argparse.ArgumentParser(description='Demo Workflows Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
