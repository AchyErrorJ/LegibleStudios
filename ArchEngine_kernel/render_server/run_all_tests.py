# run_all_tests.py
"""
RevitMCP Test Runner

Usage:
    python run_all_tests.py              # Run all tests
    python run_all_tests.py --list       # List available tools
    python run_all_tests.py --quick      # Run quick smoke tests only
    python run_all_tests.py --category walls  # Test specific category
"""
import asyncio
import sys
import argparse
import json
from datetime import datetime

# ------------------------------------------------------------------
# 1. SETUP: Import network functions
# ------------------------------------------------------------------
try:
    from server import revit_post, revit_get
    REVIT_AVAILABLE = True
except ImportError:
    print("Note: Running in offline mode (no Revit connection)")
    REVIT_AVAILABLE = False
    revit_post = None
    revit_get = None

# ------------------------------------------------------------------
# 2. SETUP: Import tool modules
# ------------------------------------------------------------------
TOOL_MODULES = []

try:
    from tools.level_creation_tools import register_tools as reg_levels
    TOOL_MODULES.append(('levels', reg_levels))
except ImportError as e:
    print(f"Note: Could not import level_creation_tools: {e}")

try:
    from tools.geometry_tools import register_tools as reg_geometry
    TOOL_MODULES.append(('geometry', reg_geometry))
except ImportError as e:
    print(f"Note: Could not import geometry_tools: {e}")

try:
    from tools.annotation_tools import register_tools as reg_annotation
    TOOL_MODULES.append(('annotation', reg_annotation))
except ImportError as e:
    print(f"Note: Could not import annotation_tools: {e}")

try:
    from tools.data_tools import register_tools as reg_data
    TOOL_MODULES.append(('data', reg_data))
except ImportError as e:
    print(f"Note: Could not import data_tools: {e}")

try:
    from tools.physics_tools import register_tools as reg_physics
    TOOL_MODULES.append(('physics', reg_physics))
except ImportError as e:
    print(f"Note: Could not import physics_tools: {e}")

try:
    from tools.auto_dimensions import register_tools as reg_autodim
    TOOL_MODULES.append(('auto_dimensions', reg_autodim))
except ImportError as e:
    print(f"Note: Could not import auto_dimensions: {e}")

# ------------------------------------------------------------------
# 3. TEST CASES - Organized by category
# ------------------------------------------------------------------

# Quick smoke tests - should always pass if Revit is connected
SMOKE_TESTS = [
    {'tool_name': 'get_revit_status', 'inputs': {}, 'description': 'Check Revit connection'},
    {'tool_name': 'get_server_manifest', 'inputs': {}, 'description': 'Get server manifest'},
    {'tool_name': 'list_levels', 'inputs': {}, 'description': 'List levels'},
    {'tool_name': 'list_views', 'inputs': {}, 'description': 'List views'},
    {'tool_name': 'list_wall_types', 'inputs': {}, 'description': 'List wall types'},
]

# Read-only discovery tests - safe to run on any model
DISCOVERY_TESTS = [
    {'tool_name': 'list_levels', 'inputs': {}, 'description': 'List all levels'},
    {'tool_name': 'list_views', 'inputs': {}, 'description': 'List all views'},
    {'tool_name': 'list_walls', 'inputs': {}, 'description': 'List all walls'},
    {'tool_name': 'list_wall_types', 'inputs': {}, 'description': 'List wall types'},
    {'tool_name': 'list_door_types', 'inputs': {}, 'description': 'List door types'},
    {'tool_name': 'list_window_types', 'inputs': {}, 'description': 'List window types'},
    {'tool_name': 'list_floor_types', 'inputs': {}, 'description': 'List floor types'},
    {'tool_name': 'list_roof_types', 'inputs': {}, 'description': 'List roof types'},
    {'tool_name': 'list_ceiling_types', 'inputs': {}, 'description': 'List ceiling types'},
    {'tool_name': 'list_furniture_types', 'inputs': {}, 'description': 'List furniture types'},
    {'tool_name': 'list_families', 'inputs': {}, 'description': 'List all families'},
    {'tool_name': 'list_sheets', 'inputs': {}, 'description': 'List all sheets'},
    {'tool_name': 'get_revit_model_info', 'inputs': {}, 'description': 'Get model info'},
]

# Physics analysis tests - calculations only, no Revit changes
PHYSICS_TESTS = [
    {
        'tool_name': 'analyze_beam',
        'inputs': {
            'span_ft': 12.0,
            'tributary_width_ft': 8.0,
            'dead_load_psf': 15.0,
            'live_load_psf': 40.0,
            'material': 'wood_spf'
        },
        'description': 'Analyze wood beam'
    },
    {
        'tool_name': 'analyze_column',
        'inputs': {
            'height_ft': 9.0,
            'axial_load_lbs': 8000,
            'material': 'wood_spf'
        },
        'description': 'Analyze wood column'
    },
    {
        'tool_name': 'estimate_fasteners',
        'inputs': {
            'assembly_type': 'wall',
            'length_ft': 40.0,
            'height_ft': 9.0
        },
        'description': 'Estimate wall fasteners'
    },
    {
        'tool_name': 'list_assembly_presets',
        'inputs': {},
        'description': 'List assembly presets'
    },
]

# Creation tests - CAUTION: These modify the model
CREATION_TESTS = [
    {
        'tool_name': 'create_level',
        'inputs': {'elevation': 20.0, 'name': 'Test Level'},
        'description': 'Create a test level'
    },
    {
        'tool_name': 'create_wall',
        'inputs': {
            'start_point': [0, 0, 0],
            'end_point': [20, 0, 0],
            'level_name': 'Level 1',
            'height': 10.0
        },
        'description': 'Create a test wall'
    },
]

# All test cases combined
ALL_TESTS = SMOKE_TESTS + DISCOVERY_TESTS + PHYSICS_TESTS

# ------------------------------------------------------------------
# 4. MOCK SERVER for offline testing
# ------------------------------------------------------------------
class MockMCP:
    """Mock MCP server for tool registration"""
    def __init__(self):
        self.tools = {}

    def tool(self, name=None):
        def decorator(func):
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            return func
        return decorator

# ------------------------------------------------------------------
# 5. TEST RUNNER
# ------------------------------------------------------------------
class TestRunner:
    def __init__(self):
        self.mock_server = MockMCP()
        self.results = {
            'passed': [],
            'failed': [],
            'skipped': [],
            'start_time': None,
            'end_time': None
        }

    def register_tools(self):
        """Register all available tool modules"""
        registered = 0
        for name, register_func in TOOL_MODULES:
            try:
                register_func(self.mock_server, revit_get, revit_post)
                print(f"  Registered: {name}")
                registered += 1
            except Exception as e:
                print(f"  Failed to register {name}: {e}")
        return registered

    def list_tools(self):
        """List all registered tools"""
        print(f"\nRegistered Tools ({len(self.mock_server.tools)}):")
        print("-" * 50)
        for name in sorted(self.mock_server.tools.keys()):
            print(f"  - {name}")

    async def run_test(self, test: dict) -> dict:
        """Run a single test case"""
        t_name = test['tool_name']
        t_args = test['inputs']
        desc = test.get('description', '')

        result = {
            'tool_name': t_name,
            'description': desc,
            'status': 'unknown',
            'error': None,
            'result': None
        }

        if t_name not in self.mock_server.tools:
            result['status'] = 'skipped'
            result['error'] = f"Tool '{t_name}' not registered"
            return result

        try:
            func = self.mock_server.tools[t_name]
            output = await func(**t_args)
            result['status'] = 'passed'
            result['result'] = str(output)[:200]  # Truncate long results
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)

        return result

    async def run_tests(self, tests: list, verbose: bool = True) -> dict:
        """Run a list of test cases"""
        self.results['start_time'] = datetime.now()

        print(f"\nRunning {len(tests)} tests...")
        print("=" * 60)

        for i, test in enumerate(tests):
            t_name = test['tool_name']
            desc = test.get('description', '')

            if verbose:
                print(f"[{i+1}/{len(tests)}] {t_name}: {desc}")

            result = await self.run_test(test)

            if result['status'] == 'passed':
                self.results['passed'].append(result)
                if verbose:
                    print(f"  PASS")
            elif result['status'] == 'skipped':
                self.results['skipped'].append(result)
                if verbose:
                    print(f"  SKIP: {result['error']}")
            else:
                self.results['failed'].append(result)
                if verbose:
                    print(f"  FAIL: {result['error']}")

        self.results['end_time'] = datetime.now()
        return self.results

    def print_summary(self):
        """Print test summary"""
        duration = (self.results['end_time'] - self.results['start_time']).total_seconds()

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"  Passed:  {len(self.results['passed'])}")
        print(f"  Failed:  {len(self.results['failed'])}")
        print(f"  Skipped: {len(self.results['skipped'])}")
        print(f"  Duration: {duration:.2f}s")

        if self.results['failed']:
            print("\nFailed Tests:")
            for r in self.results['failed']:
                print(f"  - {r['tool_name']}: {r['error']}")

        # Return exit code
        return 0 if not self.results['failed'] else 1

# ------------------------------------------------------------------
# 6. MAIN
# ------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(description='RevitMCP Test Runner')
    parser.add_argument('--list', action='store_true', help='List available tools')
    parser.add_argument('--quick', action='store_true', help='Run smoke tests only')
    parser.add_argument('--discovery', action='store_true', help='Run discovery tests only')
    parser.add_argument('--physics', action='store_true', help='Run physics tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--verbose', '-v', action='store_true', default=True, help='Verbose output')
    args = parser.parse_args()

    print("RevitMCP Test Runner")
    print("=" * 60)
    print(f"Revit Available: {REVIT_AVAILABLE}")
    print(f"Tool Modules: {len(TOOL_MODULES)}")

    runner = TestRunner()

    print("\nRegistering tools...")
    registered = runner.register_tools()
    print(f"Total tools registered: {len(runner.mock_server.tools)}")

    if args.list:
        runner.list_tools()
        return 0

    # Select test suite
    if args.quick:
        tests = SMOKE_TESTS
        print("\nRunning SMOKE tests (quick)")
    elif args.discovery:
        tests = DISCOVERY_TESTS
        print("\nRunning DISCOVERY tests (read-only)")
    elif args.physics:
        tests = PHYSICS_TESTS
        print("\nRunning PHYSICS tests (calculations)")
    else:
        tests = ALL_TESTS
        print("\nRunning ALL tests")

    await runner.run_tests(tests, verbose=args.verbose)
    return runner.print_summary()

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
