#!/usr/bin/env python3
"""
ArchEngine Pipeline Test Suite
Tests the end-to-end pipeline: text → JSON → geometry → render → plans

Run: python tests/pipeline_test.py
"""

import json
import os
import sys
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum

# Add scripts to path
SUITE_ROOT = Path(__file__).parent.parent
KERNEL_SCRIPTS = SUITE_ROOT / "ArchEngine_kernel" / "scripts"
sys.path.insert(0, str(KERNEL_SCRIPTS))

class TestStatus(Enum):
    PASS = "[PASS]"
    FAIL = "[FAIL]"
    SKIP = "[SKIP]"
    WARN = "[WARN]"

@dataclass
class TestResult:
    name: str
    status: TestStatus
    message: str = ""
    duration: float = 0.0

class PipelineTest:
    def __init__(self):
        self.results: List[TestResult] = []
        self.suite_root = SUITE_ROOT
        self.output_dir = SUITE_ROOT / "Shared" / "TestData" / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_test(self, name: str, test_func) -> TestResult:
        """Run a single test and record result"""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print('='*60)

        start = time.time()
        try:
            success, message = test_func()
            status = TestStatus.PASS if success else TestStatus.FAIL
        except Exception as e:
            status = TestStatus.FAIL
            message = f"Exception: {str(e)}"
        duration = time.time() - start

        result = TestResult(name, status, message, duration)
        self.results.append(result)

        print(f"Result: {status.value}")
        if message:
            print(f"Details: {message}")
        print(f"Duration: {duration:.2f}s")

        return result

    # =========================================================================
    # TEST 1: Schema Validation
    # =========================================================================
    def test_schema_files_exist(self) -> Tuple[bool, str]:
        """Check that all schema files exist"""
        schemas = [
            "Shared/Schemas/building.schema.json",
            "Shared/Schemas/assembly.schema.json",
            "Shared/Schemas/qbd_output.schema.json",
        ]
        missing = []
        for schema in schemas:
            path = self.suite_root / schema
            if not path.exists():
                missing.append(schema)

        if missing:
            return False, f"Missing schemas: {missing}"
        return True, f"All {len(schemas)} schema files present"

    def test_schema_valid_json(self) -> Tuple[bool, str]:
        """Check that schema files are valid JSON"""
        schema_dir = self.suite_root / "Shared" / "Schemas"
        errors = []
        count = 0

        for schema_file in schema_dir.glob("*.json"):
            try:
                with open(schema_file) as f:
                    json.load(f)
                count += 1
            except json.JSONDecodeError as e:
                errors.append(f"{schema_file.name}: {e}")

        if errors:
            return False, f"Invalid JSON: {errors}"
        return True, f"All {count} schemas are valid JSON"

    # =========================================================================
    # TEST 2: Text to JSON (QBD Parser)
    # =========================================================================
    def test_text_to_json_import(self) -> Tuple[bool, str]:
        """Check that text_to_json module can be imported"""
        try:
            from text_to_json import text_to_json, parse_description
            return True, "Module imported successfully"
        except ImportError as e:
            return False, f"Import error: {e}"

    def test_text_to_json_simple(self) -> Tuple[bool, str]:
        """Test basic text to JSON conversion"""
        try:
            from text_to_json import text_to_json

            result = text_to_json("3 bedroom 2 bath house 1800 sqft")

            # Validate required fields
            required = ['walls_batch', 'doors', 'windows', 'rooms']
            missing = [f for f in required if f not in result]

            if missing:
                return False, f"Missing fields: {missing}"

            # Check we got reasonable output
            wall_count = len(result.get('walls_batch', []))
            door_count = len(result.get('doors', []))
            room_count = len(result.get('rooms', {}))

            if wall_count < 4:
                return False, f"Too few walls: {wall_count}"

            return True, f"Generated {wall_count} walls, {door_count} doors, {room_count} rooms"

        except Exception as e:
            return False, f"Error: {e}"

    def test_text_to_json_variations(self) -> Tuple[bool, str]:
        """Test various input descriptions"""
        try:
            from text_to_json import text_to_json

            test_cases = [
                "2 bedroom 1 bath 1200 sqft",
                "4 bedroom 3 bath modern house 2500 sqft",
                "studio apartment 600 sqft",
                "3 bed 2 bath with garage 2000 sqft",
            ]

            results = []
            for desc in test_cases:
                try:
                    result = text_to_json(desc)
                    walls = len(result.get('walls_batch', []))
                    results.append(f"'{desc[:30]}...': {walls} walls")
                except Exception as e:
                    results.append(f"'{desc[:30]}...': FAILED - {e}")

            failures = [r for r in results if 'FAILED' in r]
            if failures:
                return False, f"Some cases failed: {failures}"

            return True, f"All {len(test_cases)} variations succeeded"

        except Exception as e:
            return False, f"Error: {e}"

    def test_text_to_json_output_file(self) -> Tuple[bool, str]:
        """Test that output file is written correctly"""
        try:
            from text_to_json import text_to_json

            result = text_to_json("3 bedroom 2 bath house 1800 sqft")

            output_path = self.output_dir / "generated_building.json"
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)

            # Verify file exists and is valid
            if not output_path.exists():
                return False, "Output file not created"

            with open(output_path) as f:
                loaded = json.load(f)

            if loaded.get('walls_batch') != result.get('walls_batch'):
                return False, "Output file content mismatch"

            return True, f"Output written to {output_path}"

        except Exception as e:
            return False, f"Error: {e}"

    # =========================================================================
    # TEST 3: Plan Generators
    # =========================================================================
    def test_plan_generator_import(self) -> Tuple[bool, str]:
        """Check that plan generator can be imported"""
        try:
            from generate_plans import PlanGenerator
            return True, "PlanGenerator imported successfully"
        except ImportError as e:
            return False, f"Import error: {e}"

    def test_plan_generator_floor_plan(self) -> Tuple[bool, str]:
        """Test floor plan SVG generation"""
        try:
            from generate_plans import PlanGenerator

            # Use the generated building JSON
            json_path = self.output_dir / "generated_building.json"
            if not json_path.exists():
                return False, "No input JSON file - run text_to_json test first"

            generator = PlanGenerator(str(json_path))

            # Generate floor plan
            svg_path = self.output_dir / "floor_plan.svg"
            svg_content = generator.generate_floor_plan()

            with open(svg_path, 'w') as f:
                f.write(svg_content)

            # Validate SVG
            if not svg_content.startswith('<?xml') and not svg_content.startswith('<svg'):
                return False, "Output is not valid SVG"

            if len(svg_content) < 1000:
                return False, f"SVG too small ({len(svg_content)} bytes)"

            return True, f"Floor plan SVG: {len(svg_content)} bytes → {svg_path}"

        except Exception as e:
            return False, f"Error: {e}"

    def test_roof_plan_generator(self) -> Tuple[bool, str]:
        """Test roof plan generation"""
        try:
            from generate_plans import PlanGenerator

            json_path = self.output_dir / "generated_building.json"
            if not json_path.exists():
                return False, "No input JSON file"

            generator = PlanGenerator(str(json_path))

            # Check if roof plan method exists
            if not hasattr(generator, 'generate_roof_plan'):
                return False, "generate_roof_plan method not found"

            svg_path = self.output_dir / "roof_plan.svg"
            svg_content = generator.generate_roof_plan()

            with open(svg_path, 'w') as f:
                f.write(svg_content)

            return True, f"Roof plan SVG: {len(svg_content)} bytes → {svg_path}"

        except Exception as e:
            return False, f"Error: {e}"

    def test_elevation_generator(self) -> Tuple[bool, str]:
        """Test elevation generation"""
        try:
            from generate_elevations import ElevationGenerator

            json_path = self.output_dir / "generated_building.json"
            if not json_path.exists():
                return False, "No input JSON file"

            generator = ElevationGenerator(str(json_path))

            # Generate all elevations
            elevations = ['north', 'south', 'east', 'west']
            generated = []

            for direction in elevations:
                try:
                    method = getattr(generator, f'generate_{direction}_elevation', None)
                    if method:
                        svg = method()
                        svg_path = self.output_dir / f"elevation_{direction}.svg"
                        with open(svg_path, 'w') as f:
                            f.write(svg)
                        generated.append(direction)
                except Exception as e:
                    pass  # Some elevations may not be implemented

            if not generated:
                return False, "No elevations could be generated"

            return True, f"Generated elevations: {generated}"

        except ImportError:
            return False, "ElevationGenerator not found"
        except Exception as e:
            return False, f"Error: {e}"

    def test_section_generator(self) -> Tuple[bool, str]:
        """Test section generation"""
        try:
            from generate_sections import SectionGenerator

            json_path = self.output_dir / "generated_building.json"
            if not json_path.exists():
                return False, "No input JSON file"

            generator = SectionGenerator(str(json_path))

            # Try to generate a section
            svg_path = self.output_dir / "section.svg"

            if hasattr(generator, 'generate_section'):
                svg = generator.generate_section()
                with open(svg_path, 'w') as f:
                    f.write(svg)
                return True, f"Section SVG generated → {svg_path}"
            else:
                return False, "generate_section method not found"

        except ImportError:
            return False, "SectionGenerator not found"
        except Exception as e:
            return False, f"Error: {e}"

    # =========================================================================
    # TEST 4: PDF Export
    # =========================================================================
    def test_pdf_export(self) -> Tuple[bool, str]:
        """Test PDF export capability"""
        try:
            from pdf_export import HAS_REPORTLAB, PDFExporter

            if not HAS_REPORTLAB:
                return False, "reportlab not installed (pip install reportlab)"

            # Try to create a simple PDF
            pdf_path = self.output_dir / "test_export.pdf"

            exporter = PDFExporter(str(pdf_path))
            # Just check if we can instantiate

            return True, "PDF export available (reportlab installed)"

        except ImportError as e:
            return False, f"Import error: {e}"
        except Exception as e:
            return False, f"Error: {e}"

    # =========================================================================
    # TEST 5: Schema Validator
    # =========================================================================
    def test_schema_validator(self) -> Tuple[bool, str]:
        """Test schema validation"""
        try:
            from schema_validator import validate_qbd_output

            json_path = self.output_dir / "generated_building.json"
            if not json_path.exists():
                return False, "No input JSON file"

            with open(json_path) as f:
                data = json.load(f)

            is_valid, errors = validate_qbd_output(data)

            if not is_valid:
                return False, f"Validation errors: {errors[:3]}..."  # First 3 errors

            return True, "Generated JSON passes schema validation"

        except ImportError:
            return False, "schema_validator not found"
        except Exception as e:
            return False, f"Error: {e}"

    # =========================================================================
    # TEST 6: Kernel Build Check
    # =========================================================================
    def test_kernel_executable_exists(self) -> Tuple[bool, str]:
        """Check if kernel executable exists"""
        kernel_paths = [
            self.suite_root / "ArchEngine_kernel" / "build" / "Release" / "archengine_kernel.exe",
            self.suite_root / "ArchEngine_kernel" / "build" / "Debug" / "archengine_kernel.exe",
            self.suite_root / "ArchEngine_kernel" / "build" / "archengine_kernel.exe",
        ]

        for path in kernel_paths:
            if path.exists():
                return True, f"Found kernel at: {path}"

        return False, "Kernel executable not found - needs to be built"

    def test_kernel_shaders_exist(self) -> Tuple[bool, str]:
        """Check if compiled shaders exist"""
        shader_dir = self.suite_root / "ArchEngine_kernel" / "shaders"

        required_shaders = [
            "structural.vert.spv",
            "structural.frag.spv",
        ]

        missing = []
        for shader in required_shaders:
            if not (shader_dir / shader).exists():
                missing.append(shader)

        if missing:
            # Check for source shaders instead
            sources = list(shader_dir.glob("*.vert")) + list(shader_dir.glob("*.frag"))
            if sources:
                return True, f"Shader sources present ({len(sources)} files), SPIR-V may need compilation"
            return False, f"Missing shaders: {missing}"

        return True, "All required shaders compiled"

    # =========================================================================
    # TEST 7: CAD Viewer Check
    # =========================================================================
    def test_cad_imports(self) -> Tuple[bool, str]:
        """Check if CAD viewer modules can be imported"""
        cad_path = self.suite_root / "ArchEngine_CAD"
        sys.path.insert(0, str(cad_path))

        modules_to_check = [
            ("core.document", "ArchDocument"),
            ("tools.wall_tool", "WallTool"),
            ("tools.select_tool", "SelectTool"),
        ]

        results = []
        for module_name, class_name in modules_to_check:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name, None)
                if cls:
                    results.append(f"{class_name}: OK")
                else:
                    results.append(f"{class_name}: class not found")
            except ImportError as e:
                results.append(f"{module_name}: import failed ({e})")

        failures = [r for r in results if 'OK' not in r]
        if failures:
            return False, f"Import issues: {failures}"

        return True, f"All {len(modules_to_check)} CAD modules importable"

    # =========================================================================
    # TEST 8: LiveSync Check
    # =========================================================================
    def test_livesync_server(self) -> Tuple[bool, str]:
        """Check if LiveSync server module exists"""
        try:
            cad_path = self.suite_root / "ArchEngine_CAD"
            sys.path.insert(0, str(cad_path))

            from sync.livesync_server import LiveSyncServer
            return True, "LiveSyncServer module available"
        except ImportError as e:
            return False, f"Import error: {e}"

    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================
    def run_all(self):
        """Run all tests and print summary"""
        print("\n" + "="*60)
        print("ARCHENGINE PIPELINE TEST SUITE")
        print("="*60)
        print(f"Suite Root: {self.suite_root}")
        print(f"Output Dir: {self.output_dir}")

        # Group 1: Schema
        print("\n" + "-"*60)
        print("GROUP 1: SCHEMA DEFINITION")
        print("-"*60)
        self.run_test("Schema files exist", self.test_schema_files_exist)
        self.run_test("Schema valid JSON", self.test_schema_valid_json)

        # Group 2: Text to JSON
        print("\n" + "-"*60)
        print("GROUP 2: TEXT TO JSON (QBD PARSER)")
        print("-"*60)
        self.run_test("text_to_json import", self.test_text_to_json_import)
        self.run_test("text_to_json simple", self.test_text_to_json_simple)
        self.run_test("text_to_json variations", self.test_text_to_json_variations)
        self.run_test("text_to_json output file", self.test_text_to_json_output_file)

        # Group 3: Plan Generators
        print("\n" + "-"*60)
        print("GROUP 3: PLAN GENERATORS")
        print("-"*60)
        self.run_test("PlanGenerator import", self.test_plan_generator_import)
        self.run_test("Floor plan generation", self.test_plan_generator_floor_plan)
        self.run_test("Roof plan generation", self.test_roof_plan_generator)
        self.run_test("Elevation generation", self.test_elevation_generator)
        self.run_test("Section generation", self.test_section_generator)

        # Group 4: PDF Export
        print("\n" + "-"*60)
        print("GROUP 4: PDF EXPORT")
        print("-"*60)
        self.run_test("PDF export capability", self.test_pdf_export)

        # Group 5: Validation
        print("\n" + "-"*60)
        print("GROUP 5: SCHEMA VALIDATION")
        print("-"*60)
        self.run_test("Schema validator", self.test_schema_validator)

        # Group 6: Kernel
        print("\n" + "-"*60)
        print("GROUP 6: VULKAN KERNEL")
        print("-"*60)
        self.run_test("Kernel executable", self.test_kernel_executable_exists)
        self.run_test("Kernel shaders", self.test_kernel_shaders_exist)

        # Group 7: CAD Viewer
        print("\n" + "-"*60)
        print("GROUP 7: CAD VIEWER")
        print("-"*60)
        self.run_test("CAD module imports", self.test_cad_imports)
        self.run_test("LiveSync server", self.test_livesync_server)

        # Summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)

        passed = sum(1 for r in self.results if r.status == TestStatus.PASS)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAIL)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIP)
        warned = sum(1 for r in self.results if r.status == TestStatus.WARN)
        total = len(self.results)

        print(f"\nTotal: {total} tests")
        print(f"  [PASS]:  {passed}")
        print(f"  [FAIL]:  {failed}")
        print(f"  [SKIP]:  {skipped}")
        print(f"  [WARN]:  {warned}")

        if failed > 0:
            print("\n[FAILED TESTS]:")
            for r in self.results:
                if r.status == TestStatus.FAIL:
                    print(f"  - {r.name}: {r.message}")

        print("\n" + "="*60)
        if failed == 0:
            print("*** ALL TESTS PASSED! ***")
        else:
            print(f"*** {failed} TEST(S) NEED ATTENTION ***")
        print("="*60)

        # Return exit code
        return 0 if failed == 0 else 1


if __name__ == "__main__":
    tester = PipelineTest()
    exit_code = tester.run_all()
    sys.exit(exit_code)
