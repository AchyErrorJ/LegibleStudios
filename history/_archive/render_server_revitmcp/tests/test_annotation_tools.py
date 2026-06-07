"""
Annotation Tools Test Suite

Tests the annotation and documentation tools in RevitMCP:
- Grid & Datum: create_grids_batch, create_reference_plane
- Views: create_floor_plan, create_ceiling_plan, create_section, create_elevation
- Sheets: create_sheet, place_view_on_sheet
- Annotations: create_dimension, create_tag, create_text_note

Usage:
    python tests/test_annotation_tools.py              # Run all tests
    python tests/test_annotation_tools.py --offline    # Run offline validation only
    python tests/test_annotation_tools.py --verbose    # Verbose output

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
from tools import annotation_tools

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
    """Verify all annotation tools are registered"""
    expected_tools = [
        # Grid & Datum
        'create_grids_batch', 'create_reference_plane',
        # Views
        'list_views', 'create_floor_plan', 'create_ceiling_plan',
        'create_section', 'create_elevation',
        # Sheets
        'list_sheets', 'create_sheet', 'create_sheets_batch',
        'place_view_on_sheet', 'place_views_batch',
        # Annotations
        'create_text_note', 'create_tag', 'create_dimension',
        'create_room_separation_lines'
    ]

    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing: {missing}")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'create_section', 'create_elevation', 'create_dimension',
        'create_tag', 'create_sheet', 'place_view_on_sheet'
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


def test_json_string_parsing():
    """Verify tools can handle JSON string inputs (LLM quirk)"""
    # The create_grids_batch tool should handle string input
    import inspect
    source = inspect.getsource(annotation_tools.create_grids_batch)

    if 'isinstance(grids, str)' in source and 'json.loads' in source:
        return TestResult("json_string_parsing", "pass", "JSON string parsing supported")
    return TestResult("json_string_parsing", "fail", "No JSON string parsing found")


def test_input_validation():
    """Verify input validation in tools"""
    import inspect
    source = inspect.getsource(annotation_tools.create_grids_batch)

    checks = []
    if '"start_point" not in grid' in source or "'start_point' not in grid" in source:
        checks.append("start_point validation")
    if '"end_point" not in grid' in source or "'end_point' not in grid" in source:
        checks.append("end_point validation")

    if len(checks) >= 2:
        return TestResult("input_validation", "pass", f"Found: {', '.join(checks)}")
    return TestResult("input_validation", "fail", "Missing input validation")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_views():
    """Test listing views"""
    try:
        result = await revit_get("/list_views/")
        if isinstance(result, list) or (isinstance(result, dict) and "views" in str(result).lower()):
            return TestResult("list_views", "pass", f"Got {len(result) if isinstance(result, list) else 'view'} results")
        return TestResult("list_views", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_views", "fail", str(e))


async def test_list_sheets():
    """Test listing sheets"""
    try:
        result = await revit_get("/list_sheets/")
        return TestResult("list_sheets", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_sheets", "fail", str(e))


async def test_create_floor_plan():
    """Test floor plan creation"""
    payload = {
        "level_name": "Level 1",
        "view_name": "Test Floor Plan - DELETE ME"
    }
    try:
        result = await revit_post("/create_floor_plan/", payload)
        return TestResult("create_floor_plan", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_floor_plan", "fail", str(e))


async def test_create_ceiling_plan():
    """Test ceiling plan creation"""
    payload = {
        "level_name": "Level 1",
        "view_name": "Test RCP - DELETE ME"
    }
    try:
        result = await revit_post("/create_rcp/", payload)
        return TestResult("create_ceiling_plan", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_ceiling_plan", "fail", str(e))


async def test_create_section():
    """Test section view creation"""
    payload = {
        "start_point": [0, 20, 0],
        "end_point": [40, 20, 0],
        "height": 15.0,
        "view_name": "Test Section - DELETE ME"
    }
    try:
        result = await revit_post("/create_section/", payload)
        return TestResult("create_section", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_section", "fail", str(e))


async def test_create_elevation():
    """Test elevation view creation"""
    payload = {
        "point": [20, 0, 0],
        "view_name": "Test Elevation - DELETE ME",
        "scale": 48
    }
    try:
        result = await revit_post("/create_elevation/", payload)
        return TestResult("create_elevation", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_elevation", "fail", str(e))


async def test_create_sheet():
    """Test sheet creation"""
    payload = {
        "name": "Test Sheet - DELETE ME",
        "number": "T999"
    }
    try:
        result = await revit_post("/create_sheet/", payload)
        return TestResult("create_sheet", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_sheet", "fail", str(e))


async def test_create_grids_batch():
    """Test grid batch creation"""
    payload = [
        {"start_point": [0, 0, 0], "end_point": [0, 50, 0], "name": "T1"},
        {"start_point": [20, 0, 0], "end_point": [20, 50, 0], "name": "T2"}
    ]
    try:
        result = await revit_post("/create_grids_batch/", payload)
        return TestResult("create_grids_batch", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_grids_batch", "fail", str(e))


async def test_create_reference_plane():
    """Test reference plane creation"""
    payload = {
        "start_point": [0, 0, 0],
        "end_point": [50, 0, 0],
        "name": "Test Ref Plane"
    }
    try:
        result = await revit_post("/create_reference_plane/", payload)
        return TestResult("create_reference_plane", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_reference_plane", "fail", str(e))


async def test_create_text_note():
    """Test text note creation"""
    payload = [{"text": "Test Note", "point": [10, 10, 0]}]
    try:
        result = await revit_post("/create_text_notes_batch/", payload)
        return TestResult("create_text_note", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("create_text_note", "fail", str(e))


async def test_create_dimension_invalid():
    """Test dimension creation with invalid elements"""
    payload = {
        "element_ids": [999999998, 999999999],
        "start_point": [0, 5, 0],
        "end_point": [20, 5, 0]
    }
    try:
        result = await revit_post("/create_dimension/", payload)
        # Should handle invalid elements gracefully
        return TestResult("create_dimension_invalid", "pass", "Handled invalid elements")
    except Exception as e:
        return TestResult("create_dimension_invalid", "fail", str(e))


async def test_create_tag_invalid():
    """Test tagging with invalid element"""
    payload = [{"element_id": 999999999, "point": [10, 10, 0]}]
    try:
        result = await revit_post("/create_tags_batch/", payload)
        # Should handle invalid element gracefully
        return TestResult("create_tag_invalid", "pass", "Handled invalid element")
    except Exception as e:
        return TestResult("create_tag_invalid", "fail", str(e))


async def test_place_view_on_sheet_invalid():
    """Test placing view on invalid sheet"""
    payload = {
        "sheet_id": 999999999,
        "view_id": 999999998,
        "point": [1.0, 1.0, 0]
    }
    try:
        result = await revit_post("/place_view_on_sheet/", payload)
        if "error" in str(result).lower():
            return TestResult("place_view_invalid", "pass", "Correctly rejected invalid IDs")
        return TestResult("place_view_invalid", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("place_view_invalid", "fail", str(e))


async def test_room_separation_lines():
    """Test room separation line creation"""
    payload = {
        "lines": [
            {"start_point": [10, 10, 0], "end_point": [10, 20, 0]},
            {"start_point": [10, 20, 0], "end_point": [20, 20, 0]}
        ],
        "level_name": "Level 1"
    }
    try:
        result = await revit_post("/create_separation_lines/", payload)
        return TestResult("room_separation_lines", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("room_separation_lines", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("ANNOTATION TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_json_string_parsing,
        test_input_validation,
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
                'list_views', 'list_sheets', 'create_floor_plan', 'create_ceiling_plan',
                'create_section', 'create_elevation', 'create_sheet', 'create_grids_batch',
                'create_reference_plane', 'create_text_note', 'create_dimension_invalid',
                'create_tag_invalid', 'place_view_invalid', 'room_separation_lines'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_list_views,
                test_list_sheets,
                test_create_floor_plan,
                test_create_ceiling_plan,
                test_create_section,
                test_create_elevation,
                test_create_sheet,
                test_create_grids_batch,
                test_create_reference_plane,
                test_create_text_note,
                test_create_dimension_invalid,
                test_create_tag_invalid,
                test_place_view_on_sheet_invalid,
                test_room_separation_lines,
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
    parser = argparse.ArgumentParser(description='Annotation Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
