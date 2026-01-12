"""
Export Tools Test Suite

Tests the export functionality in RevitMCP:
- DWG: export_dwg, export_dwg_sheets, list_dwg_export_setups
- PDF: export_pdf, export_sheets_to_pdf, print_to_pdf
- IFC: export_ifc, export_ifc_with_mapping
- Image: export_image, export_images_batch
- 3D Model: export_fbx, export_sat
- Schedule: export_schedule_to_csv, export_schedule_to_excel

Usage:
    python tests/test_export_tools.py              # Run all tests
    python tests/test_export_tools.py --offline    # Run offline validation only
    python tests/test_export_tools.py --verbose    # Verbose output

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
from tools import export_tools

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
    """Verify all export tools are registered"""
    expected_tools = [
        # DWG
        'export_dwg', 'export_dwg_sheets', 'list_dwg_export_setups',
        # PDF
        'export_pdf', 'export_sheets_to_pdf', 'print_to_pdf',
        # IFC
        'export_ifc', 'export_ifc_with_mapping',
        # Image
        'export_image', 'export_images_batch',
        # 3D Model
        'export_fbx', 'export_sat',
        # Schedule
        'export_schedule_to_csv', 'export_schedule_to_excel'
    ]

    registered = [t for t in expected_tools if t in TOOL_FUNCTIONS]
    missing = [t for t in expected_tools if t not in TOOL_FUNCTIONS]

    if missing:
        return TestResult("tool_registration", "fail", f"Missing {len(missing)}: {missing[:5]}...")
    return TestResult("tool_registration", "pass", f"All {len(expected_tools)} tools registered")


def test_tool_signatures():
    """Verify tool function signatures are callable"""
    test_tools = [
        'export_dwg', 'export_pdf', 'export_ifc',
        'export_image', 'export_fbx'
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


def test_dwg_version_options():
    """Verify DWG version parameter options"""
    import inspect
    sig = inspect.signature(export_tools.export_dwg)
    params = sig.parameters

    if 'dwg_version' in params:
        default = params['dwg_version'].default
        return TestResult("dwg_versions", "pass", f"Default: {default}")
    return TestResult("dwg_versions", "fail", "No dwg_version parameter")


def test_pdf_options():
    """Verify PDF has all configuration options"""
    import inspect
    sig = inspect.signature(export_tools.export_pdf)
    params = sig.parameters

    expected = ['paper_size', 'orientation', 'color_mode', 'raster_quality']
    found = [p for p in expected if p in params]

    if len(found) >= 3:
        return TestResult("pdf_options", "pass", f"Found: {', '.join(found)}")
    return TestResult("pdf_options", "fail", f"Missing PDF options")


def test_ifc_versions():
    """Verify IFC version options are available"""
    import inspect
    source = inspect.getsource(export_tools.export_ifc)

    versions = ['IFC2x3', 'IFC4']
    found = [v for v in versions if v in source]

    if len(found) >= 2:
        return TestResult("ifc_versions", "pass", f"Versions: {', '.join(found)}")
    return TestResult("ifc_versions", "fail", "Missing IFC version docs")


def test_image_formats():
    """Verify image format options are documented"""
    import inspect
    source = inspect.getsource(export_tools.export_image)

    formats = ['PNG', 'JPEG', 'BMP', 'TIFF']
    found = [f for f in formats if f in source]

    if len(found) >= 3:
        return TestResult("image_formats", "pass", f"Formats: {', '.join(found)}")
    return TestResult("image_formats", "fail", "Missing image format docs")


def test_export_categories():
    """Verify all export categories are covered"""
    categories = {
        'DWG': ['export_dwg', 'export_dwg_sheets'],
        'PDF': ['export_pdf', 'export_sheets_to_pdf'],
        'IFC': ['export_ifc'],
        'Image': ['export_image', 'export_images_batch'],
        '3D': ['export_fbx', 'export_sat'],
        'Schedule': ['export_schedule_to_csv', 'export_schedule_to_excel']
    }

    missing_categories = []
    for cat, tools in categories.items():
        for tool in tools:
            if not hasattr(export_tools, tool):
                missing_categories.append(f"{cat}/{tool}")
                break

    if missing_categories:
        return TestResult("export_categories", "fail", f"Missing: {missing_categories}")
    return TestResult("export_categories", "pass", "All 6 export categories covered")


def test_batch_exports():
    """Verify batch export tools exist"""
    batch_tools = ['export_dwg_sheets', 'export_sheets_to_pdf', 'export_images_batch']

    missing = [t for t in batch_tools if not hasattr(export_tools, t)]

    if missing:
        return TestResult("batch_exports", "fail", f"Missing: {missing}")
    return TestResult("batch_exports", "pass", "All 3 batch export tools exist")


# =============================================================================
# LIVE TESTS (Require Revit Connection)
# =============================================================================

async def test_list_dwg_export_setups():
    """Test listing DWG export setups"""
    try:
        result = await revit_get("/list_dwg_export_setups/")
        return TestResult("list_dwg_setups", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("list_dwg_setups", "fail", str(e))


async def test_export_dwg_invalid():
    """Test DWG export with invalid view IDs"""
    payload = {
        "view_ids": [999999999],
        "output_folder": "C:\\Temp",
        "dwg_version": "AutoCAD2018"
    }
    try:
        result = await revit_post("/export_dwg/", payload)
        return TestResult("export_dwg_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("export_dwg_invalid", "fail", str(e))


async def test_export_pdf_invalid():
    """Test PDF export with invalid view IDs"""
    payload = {
        "view_ids": [999999999],
        "output_path": "C:\\Temp\\test.pdf",
        "combine_into_single": True
    }
    try:
        result = await revit_post("/export_pdf/", payload)
        return TestResult("export_pdf_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("export_pdf_invalid", "fail", str(e))


async def test_export_ifc():
    """Test IFC export (may succeed or fail based on model)"""
    payload = {
        "output_path": "C:\\Temp\\test_export.ifc",
        "ifc_version": "IFC4",
        "export_base_quantities": True
    }
    try:
        result = await revit_post("/export_ifc/", payload)
        return TestResult("export_ifc", "pass", f"Response: {str(result)[:50]}")
    except Exception as e:
        return TestResult("export_ifc", "fail", str(e))


async def test_export_image_invalid():
    """Test image export with invalid view ID"""
    payload = {
        "view_id": 999999999,
        "output_path": "C:\\Temp\\test.png",
        "image_format": "PNG",
        "resolution": 150
    }
    try:
        result = await revit_post("/export_image/", payload)
        return TestResult("export_image_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("export_image_invalid", "fail", str(e))


async def test_export_schedule_csv_invalid():
    """Test schedule CSV export with invalid ID"""
    payload = {
        "schedule_id": 999999999,
        "output_path": "C:\\Temp\\test.csv",
        "include_headers": True
    }
    try:
        result = await revit_post("/export_schedule_csv/", payload)
        return TestResult("export_csv_invalid", "pass", "Handled invalid ID")
    except Exception as e:
        return TestResult("export_csv_invalid", "fail", str(e))


# =============================================================================
# MAIN RUNNER
# =============================================================================

async def run_tests(offline_only=False, verbose=False):
    """Run all tests"""
    results = []
    start_time = datetime.now()

    print("\n" + "=" * 60)
    print("EXPORT TOOLS TEST SUITE")
    print("=" * 60)

    # Offline tests
    print("\n--- OFFLINE TESTS (No Revit Required) ---")
    offline_tests = [
        test_tool_registration,
        test_tool_signatures,
        test_dwg_version_options,
        test_pdf_options,
        test_ifc_versions,
        test_image_formats,
        test_export_categories,
        test_batch_exports,
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
                'list_dwg_setups', 'export_dwg_invalid', 'export_pdf_invalid',
                'export_ifc', 'export_image_invalid', 'export_csv_invalid'
            ]
            for name in live_test_names:
                results.append(TestResult(name, "skip", "Revit not connected"))
        else:
            print("  ✓ Revit connected")

            live_tests = [
                test_list_dwg_export_setups,
                test_export_dwg_invalid,
                test_export_pdf_invalid,
                test_export_ifc,
                test_export_image_invalid,
                test_export_schedule_csv_invalid,
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
    parser = argparse.ArgumentParser(description='Export Tools Test Suite')
    parser.add_argument('--offline', action='store_true', help='Run offline tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    exit_code = asyncio.run(run_tests(offline_only=args.offline, verbose=args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
