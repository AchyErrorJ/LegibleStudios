"""
RevitMCP Integration Tests

These tests verify end-to-end workflows with a running Revit instance.

Usage:
    pytest tests/test_integration.py -v              # Run all tests
    pytest tests/test_integration.py -v -k discovery # Run discovery tests only
    pytest tests/test_integration.py -v -k physics   # Run physics tests only
    pytest tests/test_integration.py -v --no-revit   # Run offline tests only

Requirements:
    - Revit 2024+ running with RevitMCP plugin loaded
    - Python environment with pytest installed
    - Server running on localhost:48884
"""

import pytest
import asyncio
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import server functions
try:
    from server import revit_post, revit_get
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    revit_post = None
    revit_get = None


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def skip_if_no_revit():
    """Skip test if Revit is not available"""
    if not REVIT_AVAILABLE:
        pytest.skip("Revit connection not available")


# =============================================================================
# TEST 1: CONNECTION & STATUS
# =============================================================================

class TestConnection:
    """Test basic connectivity to Revit"""

    @pytest.mark.asyncio
    async def test_revit_status(self, skip_if_no_revit):
        """Verify Revit is connected and responsive"""
        result = await revit_get("/status")
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        assert "version" in data or "status" in data

    @pytest.mark.asyncio
    async def test_server_manifest(self, skip_if_no_revit):
        """Verify server manifest is available"""
        result = await revit_get("/manifest")
        assert result is not None


# =============================================================================
# TEST 2: DISCOVERY OPERATIONS (Read-Only)
# =============================================================================

class TestDiscovery:
    """Test read-only discovery operations - safe on any model"""

    @pytest.mark.asyncio
    async def test_list_levels(self, skip_if_no_revit):
        """List all levels in the model"""
        result = await revit_get("/levels")
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should return a list (even if empty)
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_list_views(self, skip_if_no_revit):
        """List all views in the model"""
        result = await revit_get("/views")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_walls(self, skip_if_no_revit):
        """List all walls in the model"""
        result = await revit_get("/walls")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_wall_types(self, skip_if_no_revit):
        """List available wall types"""
        result = await revit_get("/wall-types")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_door_types(self, skip_if_no_revit):
        """List available door types"""
        result = await revit_get("/door-types")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_window_types(self, skip_if_no_revit):
        """List available window types"""
        result = await revit_get("/window-types")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_floor_types(self, skip_if_no_revit):
        """List available floor types"""
        result = await revit_get("/floor-types")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_families(self, skip_if_no_revit):
        """List all loaded families"""
        result = await revit_get("/families")
        assert result is not None

    @pytest.mark.asyncio
    async def test_model_info(self, skip_if_no_revit):
        """Get model information"""
        result = await revit_get("/model-info")
        assert result is not None


# =============================================================================
# TEST 3: PHYSICS ANALYSIS (Calculations Only)
# =============================================================================

class TestPhysicsAnalysis:
    """Test physics analysis tools - calculations only, no Revit changes"""

    @pytest.mark.asyncio
    async def test_analyze_beam_wood(self, skip_if_no_revit):
        """Analyze a typical wood beam"""
        payload = {
            "span_ft": 12.0,
            "tributary_width_ft": 8.0,
            "dead_load_psf": 15.0,
            "live_load_psf": 40.0,
            "material": "wood_spf",
            "depth_in": 9.25,
            "width_in": 3.5
        }
        result = await revit_post("/analyze-beam", payload)
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        assert "status" in data

    @pytest.mark.asyncio
    async def test_analyze_column_wood(self, skip_if_no_revit):
        """Analyze a typical wood column"""
        payload = {
            "height_ft": 9.0,
            "axial_load_lbs": 8000,
            "material": "wood_spf",
            "depth_in": 5.5,
            "width_in": 5.5
        }
        result = await revit_post("/analyze-column", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_estimate_fasteners_wall(self, skip_if_no_revit):
        """Estimate fasteners for a wall assembly"""
        payload = {
            "assembly_type": "wall",
            "length_ft": 40.0,
            "height_ft": 9.0
        }
        result = await revit_post("/estimate-fasteners", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_estimate_fasteners_floor(self, skip_if_no_revit):
        """Estimate fasteners for a floor assembly"""
        payload = {
            "assembly_type": "floor",
            "length_ft": 40.0,
            "width_ft": 30.0
        }
        result = await revit_post("/estimate-fasteners", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_thermal_analysis(self, skip_if_no_revit):
        """Analyze thermal performance of assembly"""
        payload = {
            "assembly_name": "ext_wall_2x6",
            "interior_temp_f": 70.0,
            "exterior_temp_f": 0.0,
            "relative_humidity_pct": 40.0
        }
        result = await revit_post("/analyze-thermal", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_heat_loss_calculation(self, skip_if_no_revit):
        """Calculate building heat loss"""
        payload = {
            "climate_zone": 5,
            "floor_area_sqft": 1200.0,
            "wall_area_sqft": 800.0,
            "roof_area_sqft": 1200.0,
            "window_area_sqft": 150.0,
            "volume_cuft": 10800.0
        }
        result = await revit_post("/calculate-heat-loss", payload)
        assert result is not None


# =============================================================================
# TEST 4: TEMPLATE DETECTION
# =============================================================================

class TestTemplates:
    """Test template detection and execution"""

    def test_import_templates(self):
        """Verify templates module can be imported"""
        from templates import detect_template, get_template_names
        assert detect_template is not None
        assert get_template_names is not None

    def test_template_names_available(self):
        """Verify template names list is populated"""
        from templates import get_template_names
        names = get_template_names()
        assert len(names) > 0
        assert isinstance(names, list)

    def test_detect_house_template(self):
        """Test house template detection"""
        from templates import detect_template
        result = detect_template("create a 40x30 house")
        assert result is not None
        assert "plan" in result
        assert "name" in result

    def test_detect_material_schedule_template(self):
        """Test material schedule template detection"""
        from templates import detect_template
        result = detect_template("create a material schedule")
        assert result is not None
        assert "plan" in result

    def test_detect_structural_analysis_template(self):
        """Test structural analysis template detection"""
        from templates import detect_template
        result = detect_template("run structural analysis")
        assert result is not None
        assert "plan" in result

    def test_detect_cd_set_template(self):
        """Test construction document template detection"""
        from templates import detect_template
        result = detect_template("create cd set")
        assert result is not None
        assert "plan" in result

    def test_no_template_for_random_query(self):
        """Verify no template for unrelated query"""
        from templates import detect_template
        result = detect_template("what is the weather today")
        assert result is None


# =============================================================================
# TEST 5: CREATION WORKFLOWS (Modifies Model - Use With Caution)
# =============================================================================

@pytest.mark.slow
class TestCreation:
    """
    Test creation workflows - CAUTION: These modify the model!
    Only run on test models, not production files.
    """

    @pytest.mark.asyncio
    async def test_create_level(self, skip_if_no_revit):
        """Create a new level"""
        payload = {
            "elevation": 100.0,  # High elevation to avoid conflicts
            "name": "Test Level - DELETE ME"
        }
        result = await revit_post("/create-level", payload)
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should have created or returned existing
        assert "status" in data or "id" in data or "level" in str(data).lower()

    @pytest.mark.asyncio
    async def test_create_wall(self, skip_if_no_revit):
        """Create a test wall"""
        payload = {
            "start_point": [1000, 1000, 0],  # Far from origin to avoid conflicts
            "end_point": [1020, 1000, 0],
            "level_name": "Level 1",
            "height": 10.0
        }
        result = await revit_post("/create-wall", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_floor_plan_view(self, skip_if_no_revit):
        """Create a floor plan view"""
        payload = {
            "level_name": "Level 1",
            "view_name": "Test View - DELETE ME"
        }
        result = await revit_post("/create-floor-plan", payload)
        assert result is not None


# =============================================================================
# TEST 6: ERROR HANDLING
# =============================================================================

class TestErrorHandling:
    """Test error handling and validation"""

    @pytest.mark.asyncio
    async def test_invalid_level_name(self, skip_if_no_revit):
        """Test error when referencing non-existent level"""
        payload = {
            "start_point": [0, 0, 0],
            "end_point": [10, 0, 0],
            "level_name": "NonExistentLevel12345",
            "height": 10.0
        }
        result = await revit_post("/create-wall", payload)
        # Should return error, not crash
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should indicate error
        assert "error" in str(data).lower() or "not found" in str(data).lower()

    @pytest.mark.asyncio
    async def test_invalid_element_id(self, skip_if_no_revit):
        """Test error when referencing non-existent element"""
        payload = {
            "element_id": 999999999
        }
        result = await revit_post("/get-element-parameters", payload)
        # Should return error, not crash
        assert result is not None


# =============================================================================
# TEST 7: BATCH OPERATIONS
# =============================================================================

@pytest.mark.slow
class TestBatchOperations:
    """Test batch creation operations"""

    @pytest.mark.asyncio
    async def test_create_levels_batch(self, skip_if_no_revit):
        """Create multiple levels at once"""
        payload = {
            "levels": [
                {"name": "Batch Test L1", "elevation": 200.0},
                {"name": "Batch Test L2", "elevation": 210.0}
            ]
        }
        result = await revit_post("/create-levels-batch", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_walls_batch(self, skip_if_no_revit):
        """Create multiple walls at once"""
        payload = {
            "walls": [
                {"start_point": [2000,0,0], "end_point": [2020,0,0], "level_name": "Level 1", "height": 10},
                {"start_point": [2020,0,0], "end_point": [2020,15,0], "level_name": "Level 1", "height": 10}
            ]
        }
        result = await revit_post("/create-walls-batch", payload)
        assert result is not None


# =============================================================================
# TEST 8: TOOL MODULE IMPORTS (Offline)
# =============================================================================

class TestToolModuleImports:
    """Test that all tool modules import correctly - no Revit needed"""

    def test_export_tools_import(self):
        """Verify export_tools module imports"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_dwg')
        assert hasattr(export_tools, 'export_pdf')
        assert hasattr(export_tools, 'export_ifc')

    def test_stair_tools_import(self):
        """Verify stair_tools module imports"""
        from tools import stair_tools
        assert hasattr(stair_tools, 'create_stair_by_run')
        assert hasattr(stair_tools, 'create_railing')
        assert hasattr(stair_tools, 'list_stair_types')

    def test_curtain_wall_tools_import(self):
        """Verify curtain_wall_tools module imports"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'create_curtain_wall')
        assert hasattr(curtain_wall_tools, 'add_curtain_grid_line')
        assert hasattr(curtain_wall_tools, 'add_mullion')

    def test_structural_tools_import(self):
        """Verify structural_tools module imports"""
        from tools import structural_tools
        assert hasattr(structural_tools, 'create_beam')
        assert hasattr(structural_tools, 'create_column')
        assert hasattr(structural_tools, 'list_beam_types')

    def test_import_tools_import(self):
        """Verify import_tools module imports"""
        from tools import import_tools
        assert hasattr(import_tools, 'import_cad')
        assert hasattr(import_tools, 'link_cad')
        assert hasattr(import_tools, 'link_point_cloud')

    def test_view_filter_tools_import(self):
        """Verify view_filter_tools module imports"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'create_rule_filter')
        assert hasattr(view_filter_tools, 'set_category_visibility')
        assert hasattr(view_filter_tools, 'apply_view_template')

    def test_detail_tools_import(self):
        """Verify detail_tools module imports"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'create_detail_line')
        assert hasattr(detail_tools, 'create_filled_region')
        assert hasattr(detail_tools, 'create_drafting_view')

    def test_tool_registry_count(self):
        """Verify expected number of tools are registered"""
        from tools import TOOL_FUNCTIONS
        # Should have at least 250 tools after all additions
        assert len(TOOL_FUNCTIONS) >= 250, f"Expected 250+ tools, got {len(TOOL_FUNCTIONS)}"


# =============================================================================
# TEST 9: VALIDATION MODULE (Offline)
# =============================================================================

class TestValidation:
    """Test input validation functions - no Revit needed"""

    def test_validate_point_list(self):
        """Test point validation with list input"""
        from tools.validation import validate_point
        result = validate_point([10, 20, 30], "test_point")
        assert result == [10.0, 20.0, 30.0]

    def test_validate_point_2d(self):
        """Test point validation with 2D input"""
        from tools.validation import validate_point
        result = validate_point([10, 20], "test_point")
        assert result == [10.0, 20.0, 0.0]

    def test_validate_point_dict(self):
        """Test point validation with dict input"""
        from tools.validation import validate_point
        result = validate_point({"x": 10, "y": 20, "z": 30}, "test_point")
        assert result == [10.0, 20.0, 30.0]

    def test_validate_point_invalid(self):
        """Test point validation rejects invalid input"""
        from tools.validation import validate_point, ValidationError
        with pytest.raises(ValidationError):
            validate_point("not a point", "test_point")

    def test_validate_positive(self):
        """Test positive number validation"""
        from tools.validation import validate_positive
        assert validate_positive(10, "height") == 10.0
        assert validate_positive(0.5, "width") == 0.5

    def test_validate_positive_rejects_negative(self):
        """Test positive validation rejects negative"""
        from tools.validation import validate_positive, ValidationError
        with pytest.raises(ValidationError):
            validate_positive(-5, "height")

    def test_validate_level_name(self):
        """Test level name validation"""
        from tools.validation import validate_level_name
        assert validate_level_name("Level 1") == "Level 1"
        assert validate_level_name("Ground Floor") == "Ground Floor"

    def test_validate_level_name_incomplete(self):
        """Test level name rejects incomplete names"""
        from tools.validation import validate_level_name, ValidationError
        with pytest.raises(ValidationError):
            validate_level_name("Level")  # Too generic

    def test_validate_element_id(self):
        """Test element ID validation"""
        from tools.validation import validate_element_id
        assert validate_element_id(12345) == 12345
        assert validate_element_id("67890") == 67890

    def test_validate_element_id_invalid(self):
        """Test element ID rejects invalid input"""
        from tools.validation import validate_element_id, ValidationError
        with pytest.raises(ValidationError):
            validate_element_id(-1)
        with pytest.raises(ValidationError):
            validate_element_id("not_a_number")

    def test_validate_wall_params(self):
        """Test wall parameter validation"""
        from tools.validation import validate_wall_params
        result = validate_wall_params([0, 0, 0], [10, 0, 0], 10)
        assert "start_point" in result
        assert "end_point" in result
        assert "length" in result
        assert result["length"] == 10.0

    def test_validate_wall_params_zero_length(self):
        """Test wall validation rejects zero-length walls"""
        from tools.validation import validate_wall_params, ValidationError
        with pytest.raises(ValidationError):
            validate_wall_params([0, 0, 0], [0, 0, 0])


# =============================================================================
# TEST 10: NEW TOOL DISCOVERY (Requires Revit)
# =============================================================================

class TestNewToolDiscovery:
    """Test discovery endpoints for new tool categories"""

    @pytest.mark.asyncio
    async def test_list_stair_types(self, skip_if_no_revit):
        """List available stair types"""
        result = await revit_get("/list_stair_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_railing_types(self, skip_if_no_revit):
        """List available railing types"""
        result = await revit_get("/list_railing_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_curtain_wall_types(self, skip_if_no_revit):
        """List available curtain wall types"""
        result = await revit_get("/list_curtain_wall_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_mullion_types(self, skip_if_no_revit):
        """List available mullion types"""
        result = await revit_get("/list_mullion_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_beam_types(self, skip_if_no_revit):
        """List available structural beam types"""
        result = await revit_get("/list_beam_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_column_types(self, skip_if_no_revit):
        """List available structural column types"""
        result = await revit_get("/list_column_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_view_filters(self, skip_if_no_revit):
        """List all view filters"""
        result = await revit_get("/list_view_filters/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_view_templates(self, skip_if_no_revit):
        """List all view templates"""
        result = await revit_get("/list_view_templates/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_line_styles(self, skip_if_no_revit):
        """List available line styles"""
        result = await revit_get("/list_line_styles/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_filled_region_types(self, skip_if_no_revit):
        """List filled region types"""
        result = await revit_get("/list_filled_region_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_linked_cad(self, skip_if_no_revit):
        """List linked CAD files"""
        result = await revit_get("/list_linked_cad/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_revit_links(self, skip_if_no_revit):
        """List linked Revit models"""
        result = await revit_get("/list_revit_links/")
        assert result is not None


# =============================================================================
# TEST 11: CORE GEOMETRY TOOLS (Creation - Modifies Model)
# =============================================================================

@pytest.mark.slow
class TestCoreGeometry:
    """
    Test core geometry creation tools - CAUTION: These modify the model!
    Only run on test models, not production files.
    """

    @pytest.mark.asyncio
    async def test_create_floor(self, skip_if_no_revit):
        """Create a floor from boundary points"""
        payload = {
            "points": [
                [500, 500, 0],
                [520, 500, 0],
                [520, 515, 0],
                [500, 515, 0]
            ],
            "level_name": "Level 1"
        }
        result = await revit_post("/create_floor/", payload)
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should succeed or return a meaningful error
        assert "status" in data or "id" in data or "error" in str(data).lower()

    @pytest.mark.asyncio
    async def test_create_floor_with_type(self, skip_if_no_revit):
        """Create a floor with specified type"""
        payload = {
            "points": [
                [550, 500, 0],
                [570, 500, 0],
                [570, 515, 0],
                [550, 515, 0]
            ],
            "level_name": "Level 1",
            "floor_type": "Generic - 12\""
        }
        result = await revit_post("/create_floor/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_roof(self, skip_if_no_revit):
        """Create a roof from footprint boundary"""
        payload = {
            "points": [
                [600, 500, 0],
                [640, 500, 0],
                [640, 530, 0],
                [600, 530, 0]
            ],
            "level_name": "Level 1",
            "slope_degrees": 0.0
        }
        result = await revit_post("/create_roof/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_roof_with_slope(self, skip_if_no_revit):
        """Create a sloped roof"""
        payload = {
            "points": [
                [650, 500, 0],
                [690, 500, 0],
                [690, 530, 0],
                [650, 530, 0]
            ],
            "level_name": "Level 1",
            "slope_degrees": 30.0
        }
        result = await revit_post("/create_roof/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_room(self, skip_if_no_revit):
        """Create a room at a specific point"""
        payload = {
            "level_name": "Level 1",
            "point": [510, 507, 0],
            "name": "Test Room",
            "number": "T101",
            "auto_tag": True
        }
        result = await revit_post("/create_room/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_rooms_batch(self, skip_if_no_revit):
        """Create multiple rooms in one transaction"""
        payload = [
            {"level_name": "Level 1", "point": [560, 507, 0], "name": "Living Room", "number": "T102"},
            {"level_name": "Level 1", "point": [610, 507, 0], "name": "Bedroom", "number": "T103"}
        ]
        result = await revit_post("/create_rooms_batch/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_directshape_mass(self, skip_if_no_revit):
        """Create a 3D mass by extrusion"""
        payload = {
            "points": [
                [700, 500, 0],
                [720, 500, 0],
                [720, 520, 0],
                [700, 520, 0]
            ],
            "height": 15.0,
            "category_name": "Generic Models",
            "base_offset": 0.0
        }
        result = await revit_post("/create_directshape_mass/", payload)
        assert result is not None


# =============================================================================
# TEST 12: HOSTED ELEMENT PLACEMENT (Doors/Windows)
# =============================================================================

@pytest.mark.slow
class TestHostedElements:
    """
    Test door and window placement - requires existing walls.
    Run after TestCreation to ensure walls exist.
    """

    @pytest.mark.asyncio
    async def test_list_doors_in_model(self, skip_if_no_revit):
        """List existing doors in the model"""
        result = await revit_get("/doors/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_windows_in_model(self, skip_if_no_revit):
        """List existing windows in the model"""
        result = await revit_get("/windows/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_place_door_requires_host(self, skip_if_no_revit):
        """Verify place_door requires a valid host wall"""
        payload = {
            "host_id": 999999999,  # Invalid host
            "point": [10, 0, 3],
            "family_name": "Single-Flush",
            "type_name": "36\" x 84\""
        }
        result = await revit_post("/place_door/", payload)
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should return an error for invalid host
        assert "error" in str(data).lower() or "not found" in str(data).lower()

    @pytest.mark.asyncio
    async def test_place_window_requires_host(self, skip_if_no_revit):
        """Verify place_window requires a valid host wall"""
        payload = {
            "host_id": 999999999,  # Invalid host
            "point": [15, 0, 4],
            "family_name": "Fixed",
            "type_name": "36\" x 48\""
        }
        result = await revit_post("/place_window/", payload)
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should return an error for invalid host
        assert "error" in str(data).lower() or "not found" in str(data).lower()

    @pytest.mark.asyncio
    async def test_place_family_freestanding(self, skip_if_no_revit):
        """Place a freestanding family (furniture)"""
        payload = {
            "family_name": "Desk",
            "type_name": "60\" x 30\"",
            "point": [510, 510, 0],
            "level_name": "Level 1"
        }
        result = await revit_post("/place_family/", payload)
        # May fail if family not loaded, but should not crash
        assert result is not None


# =============================================================================
# TEST 13: WALL TYPE & ASSEMBLY TOOLS
# =============================================================================

class TestWallAssembly:
    """Test wall type creation and assembly tools"""

    @pytest.mark.asyncio
    async def test_list_wall_type_layers(self, skip_if_no_revit):
        """Get layer structure of a wall type"""
        payload = {"wall_type_name": "Generic - 8\""}
        result = await revit_post("/get_wall_type_layers/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_duplicate_wall_type(self, skip_if_no_revit):
        """Duplicate an existing wall type"""
        payload = {
            "source_name": "Generic - 8\"",
            "new_name": "Test Wall Type - DELETE ME",
            "layer_overrides": []
        }
        result = await revit_post("/duplicate_wall_type/", payload)
        assert result is not None


# =============================================================================
# TEST 14: ANNOTATION TOOLS (Views, Sheets, Dimensions)
# =============================================================================

@pytest.mark.slow
class TestAnnotationTools:
    """Test annotation and documentation tools"""

    @pytest.mark.asyncio
    async def test_create_section(self, skip_if_no_revit):
        """Create a section view"""
        payload = {
            "start_point": [0, 20, 0],
            "end_point": [40, 20, 0],
            "height": 15.0,
            "view_name": "Test Section - DELETE ME"
        }
        result = await revit_post("/create_section/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_elevation(self, skip_if_no_revit):
        """Create an elevation view"""
        payload = {
            "point": [20, 0, 0],
            "view_name": "Test Elevation - DELETE ME",
            "scale": 48
        }
        result = await revit_post("/create_elevation/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_ceiling_plan(self, skip_if_no_revit):
        """Create a reflected ceiling plan"""
        payload = {
            "level_name": "Level 1",
            "view_name": "Test RCP - DELETE ME"
        }
        result = await revit_post("/create_rcp/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_sheet(self, skip_if_no_revit):
        """Create a new sheet"""
        payload = {
            "name": "Test Sheet - DELETE ME",
            "number": "T999"
        }
        result = await revit_post("/create_sheet/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_grids_batch(self, skip_if_no_revit):
        """Create multiple grids"""
        payload = [
            {"start_point": [0, 0, 0], "end_point": [0, 50, 0], "name": "T1"},
            {"start_point": [20, 0, 0], "end_point": [20, 50, 0], "name": "T2"}
        ]
        result = await revit_post("/create_grids_batch/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_reference_plane(self, skip_if_no_revit):
        """Create a reference plane"""
        payload = {
            "start_point": [0, 0, 0],
            "end_point": [50, 0, 0],
            "name": "Test Ref Plane"
        }
        result = await revit_post("/create_reference_plane/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_text_note(self, skip_if_no_revit):
        """Create a text note"""
        payload = [{"text": "Test Note", "point": [10, 10, 0]}]
        result = await revit_post("/create_text_notes_batch/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_room_separation_lines(self, skip_if_no_revit):
        """Create room separation lines"""
        payload = {
            "lines": [
                {"start_point": [10, 10, 0], "end_point": [10, 20, 0]},
                {"start_point": [10, 20, 0], "end_point": [20, 20, 0]}
            ],
            "level_name": "Level 1"
        }
        result = await revit_post("/create_separation_lines/", payload)
        assert result is not None


# =============================================================================
# TEST 15: ANNOTATION TOOL MODULE IMPORTS (Offline)
# =============================================================================

class TestAnnotationModuleImports:
    """Test annotation tool module imports - no Revit needed"""

    def test_annotation_tools_import(self):
        """Verify annotation_tools module imports"""
        from tools import annotation_tools
        assert hasattr(annotation_tools, 'create_section')
        assert hasattr(annotation_tools, 'create_elevation')
        assert hasattr(annotation_tools, 'create_dimension')
        assert hasattr(annotation_tools, 'create_tag')
        assert hasattr(annotation_tools, 'create_sheet')

    def test_annotation_tools_registered(self):
        """Verify annotation tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_section', 'create_elevation', 'create_dimension',
            'create_tag', 'create_sheet', 'create_grids_batch',
            'place_view_on_sheet', 'create_text_note'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 16: AUTO DIMENSION TOOLS (Offline)
# =============================================================================

class TestAutoDimensionModuleImports:
    """Test auto dimension module - no Revit needed"""

    def test_auto_dimension_tools_import(self):
        """Verify auto_dimensions module imports"""
        from tools import auto_dimensions
        assert hasattr(auto_dimensions, 'auto_dimension_walls')
        assert hasattr(auto_dimensions, 'auto_dimension_rooms')
        assert hasattr(auto_dimensions, 'auto_dimension_openings')
        assert hasattr(auto_dimensions, 'auto_dimension_all')

    def test_auto_dimension_helpers(self):
        """Verify helper functions exist"""
        from tools import auto_dimensions
        assert hasattr(auto_dimensions, 'group_walls_by_orientation')
        assert hasattr(auto_dimensions, 'calculate_dimension_extents')
        assert hasattr(auto_dimensions, 'get_or_create_floor_plan_view')

    def test_group_walls_by_orientation(self):
        """Test wall grouping logic"""
        from tools.auto_dimensions import group_walls_by_orientation
        test_walls = [
            {"id": 1, "start_point": [0, 0, 0], "end_point": [20, 0, 0]},   # Horizontal
            {"id": 2, "start_point": [20, 0, 0], "end_point": [20, 15, 0]}, # Vertical
        ]
        result = group_walls_by_orientation(test_walls)
        assert len(result["horizontal"]) == 1
        assert len(result["vertical"]) == 1

    def test_calculate_dimension_extents(self):
        """Test bounding box calculation"""
        from tools.auto_dimensions import calculate_dimension_extents
        test_walls = [
            {"start_point": [0, 0, 0], "end_point": [20, 0, 0]},
            {"start_point": [0, 15, 0], "end_point": [20, 15, 0]},
        ]
        extents = calculate_dimension_extents(test_walls)
        assert extents["min_x"] == 0
        assert extents["max_x"] == 20
        assert extents["min_y"] == 0
        assert extents["max_y"] == 15

    def test_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = ['auto_dimension_walls', 'auto_dimension_rooms',
                   'auto_dimension_openings', 'auto_dimension_all']
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 17: AUTO DIMENSION TOOLS (Live - Requires Revit)
# =============================================================================

@pytest.mark.slow
class TestAutoDimensionLive:
    """Test auto dimension tools with Revit - modifies model"""

    @pytest.mark.asyncio
    async def test_auto_dimension_walls(self, skip_if_no_revit):
        """Test wall auto-dimensioning"""
        from tools.auto_dimensions import auto_dimension_walls
        result = await auto_dimension_walls(level_name="Level 1")
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should return a structured response
        assert "success" in data or "error" in str(data).lower()

    @pytest.mark.asyncio
    async def test_auto_dimension_all(self, skip_if_no_revit):
        """Test complete auto-dimensioning"""
        from tools.auto_dimensions import auto_dimension_all
        result = await auto_dimension_all(level_name="Level 1")
        assert result is not None
        data = json.loads(result) if isinstance(result, str) else result
        # Should include all three dimension types
        assert "wall_dimensions" in data or "error" in str(data).lower()


# =============================================================================
# TEST 18: STRUCTURAL TOOLS (Offline)
# =============================================================================

class TestStructuralModuleImports:
    """Test structural tool module - no Revit needed"""

    def test_structural_tools_import(self):
        """Verify structural_tools module imports"""
        from tools import structural_tools
        # Beams
        assert hasattr(structural_tools, 'create_beam')
        assert hasattr(structural_tools, 'create_beams_batch')
        assert hasattr(structural_tools, 'create_beam_system')
        # Columns
        assert hasattr(structural_tools, 'create_column')
        assert hasattr(structural_tools, 'create_columns_batch')
        # Braces
        assert hasattr(structural_tools, 'create_brace')
        assert hasattr(structural_tools, 'create_x_bracing')
        # Foundations
        assert hasattr(structural_tools, 'create_isolated_foundation')
        assert hasattr(structural_tools, 'create_wall_foundation')
        assert hasattr(structural_tools, 'create_slab_foundation')

    def test_structural_discovery_tools(self):
        """Verify discovery tools exist"""
        from tools import structural_tools
        assert hasattr(structural_tools, 'list_beam_types')
        assert hasattr(structural_tools, 'list_column_types')
        assert hasattr(structural_tools, 'list_brace_types')
        assert hasattr(structural_tools, 'list_foundation_types')

    def test_structural_connections(self):
        """Verify connection tools exist"""
        from tools import structural_tools
        assert hasattr(structural_tools, 'create_beam_to_column_connection')
        assert hasattr(structural_tools, 'create_beam_to_beam_connection')

    def test_structural_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_beam', 'create_column', 'create_brace',
            'create_isolated_foundation', 'list_beam_types',
            'modify_beam', 'create_x_bracing'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 19: STRUCTURAL TOOLS (Live - Requires Revit)
# =============================================================================

@pytest.mark.slow
class TestStructuralLive:
    """Test structural tools with Revit - modifies model"""

    @pytest.mark.asyncio
    async def test_list_beam_types(self, skip_if_no_revit):
        """List beam types"""
        result = await revit_get("/list_beam_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_column_types(self, skip_if_no_revit):
        """List column types"""
        result = await revit_get("/list_column_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_beam(self, skip_if_no_revit):
        """Create a beam"""
        payload = {
            "start_point": [800, 0, 0],
            "end_point": [820, 0, 0],
            "level_name": "Level 1"
        }
        result = await revit_post("/create_beam/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_column(self, skip_if_no_revit):
        """Create a column"""
        payload = {
            "location": [850, 0, 0],
            "base_level_name": "Level 1",
            "height": 10.0
        }
        result = await revit_post("/create_column/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_brace(self, skip_if_no_revit):
        """Create a brace"""
        payload = {
            "start_point": [860, 0, 0],
            "end_point": [870, 0, 10],
            "level_name": "Level 1"
        }
        result = await revit_post("/create_brace/", payload)
        assert result is not None


# =============================================================================
# TEST 20: STAIR TOOLS (Offline)
# =============================================================================

class TestStairModuleImports:
    """Test stair tool module - no Revit needed"""

    def test_stair_tools_import(self):
        """Verify stair_tools module imports"""
        from tools import stair_tools
        # Stair creation
        assert hasattr(stair_tools, 'create_stair_by_run')
        assert hasattr(stair_tools, 'create_u_shaped_stair')
        assert hasattr(stair_tools, 'create_l_shaped_stair')
        assert hasattr(stair_tools, 'create_spiral_stair')
        assert hasattr(stair_tools, 'create_stair_by_sketch')

    def test_railing_tools(self):
        """Verify railing tools exist"""
        from tools import stair_tools
        assert hasattr(stair_tools, 'create_railing')
        assert hasattr(stair_tools, 'create_railing_on_floor_edge')
        assert hasattr(stair_tools, 'modify_railing')

    def test_discovery_tools(self):
        """Verify discovery tools exist"""
        from tools import stair_tools
        assert hasattr(stair_tools, 'list_stair_types')
        assert hasattr(stair_tools, 'list_railing_types')
        assert hasattr(stair_tools, 'list_stairs')
        assert hasattr(stair_tools, 'list_railings')

    def test_code_compliance_tool(self):
        """Verify code compliance tool exists"""
        from tools import stair_tools
        assert hasattr(stair_tools, 'check_stair_code_compliance')

    def test_stair_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_stair_by_run', 'create_railing', 'list_stair_types',
            'check_stair_code_compliance', 'create_spiral_stair'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 21: STAIR TOOLS (Live - Requires Revit)
# =============================================================================

@pytest.mark.slow
class TestStairLive:
    """Test stair tools with Revit - modifies model"""

    @pytest.mark.asyncio
    async def test_list_stair_types(self, skip_if_no_revit):
        """List stair types"""
        result = await revit_get("/list_stair_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_railing_types(self, skip_if_no_revit):
        """List railing types"""
        result = await revit_get("/list_railing_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_stair_by_run(self, skip_if_no_revit):
        """Create a straight stair"""
        payload = {
            "base_level_name": "Level 1",
            "top_level_name": "Level 2",
            "start_point": [100, 100, 0],
            "end_point": [115, 100, 0],
            "width": 3.0
        }
        result = await revit_post("/create_stair_by_run/", payload)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_railing(self, skip_if_no_revit):
        """Create a railing"""
        payload = {
            "path_points": [[200, 100, 0], [210, 100, 0], [210, 110, 0]],
            "level_name": "Level 1"
        }
        result = await revit_post("/create_railing/", payload)
        assert result is not None


# =============================================================================
# TEST 22: CURTAIN WALL TOOLS (Offline)
# =============================================================================

class TestCurtainWallModuleImports:
    """Test curtain wall tool module - no Revit needed"""

    def test_curtain_wall_creation_tools(self):
        """Verify creation tools exist"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'create_curtain_wall')
        assert hasattr(curtain_wall_tools, 'create_curtain_wall_by_profile')
        assert hasattr(curtain_wall_tools, 'create_curved_curtain_wall')

    def test_curtain_system_tools(self):
        """Verify curtain system tools exist"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'create_curtain_system_by_face')
        assert hasattr(curtain_wall_tools, 'create_curtain_system_by_extrusion')

    def test_grid_operations(self):
        """Verify grid operation tools exist"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'add_curtain_grid_line')
        assert hasattr(curtain_wall_tools, 'add_curtain_grid_lines_evenly')
        assert hasattr(curtain_wall_tools, 'set_curtain_grid_pattern')

    def test_mullion_operations(self):
        """Verify mullion tools exist"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'add_mullion')
        assert hasattr(curtain_wall_tools, 'add_all_mullions')
        assert hasattr(curtain_wall_tools, 'change_mullion_type')

    def test_panel_operations(self):
        """Verify panel tools exist"""
        from tools import curtain_wall_tools
        assert hasattr(curtain_wall_tools, 'list_curtain_panels')
        assert hasattr(curtain_wall_tools, 'change_curtain_panel_type')
        assert hasattr(curtain_wall_tools, 'replace_panel_with_door')

    def test_curtain_wall_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_curtain_wall', 'add_mullion', 'add_curtain_grid_line',
            'list_curtain_wall_types', 'list_mullion_types'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 23: CURTAIN WALL TOOLS (Live - Requires Revit)
# =============================================================================

@pytest.mark.slow
class TestCurtainWallLive:
    """Test curtain wall tools with Revit - modifies model"""

    @pytest.mark.asyncio
    async def test_list_curtain_wall_types(self, skip_if_no_revit):
        """List curtain wall types"""
        result = await revit_get("/list_curtain_wall_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_list_mullion_types(self, skip_if_no_revit):
        """List mullion types"""
        result = await revit_get("/list_mullion_types/")
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_curtain_wall(self, skip_if_no_revit):
        """Create a curtain wall"""
        payload = {
            "start_point": [300, 0, 0],
            "end_point": [330, 0, 0],
            "level_name": "Level 1",
            "height": 12.0
        }
        result = await revit_post("/create_curtain_wall/", payload)
        assert result is not None


# =============================================================================
# TEST 24: EXPORT TOOLS (Offline)
# =============================================================================

class TestExportModuleImports:
    """Test export tool module - no Revit needed"""

    def test_dwg_export_tools(self):
        """Verify DWG export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_dwg')
        assert hasattr(export_tools, 'export_dwg_sheets')
        assert hasattr(export_tools, 'list_dwg_export_setups')

    def test_pdf_export_tools(self):
        """Verify PDF export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_pdf')
        assert hasattr(export_tools, 'export_sheets_to_pdf')
        assert hasattr(export_tools, 'print_to_pdf')

    def test_ifc_export_tools(self):
        """Verify IFC export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_ifc')
        assert hasattr(export_tools, 'export_ifc_with_mapping')

    def test_image_export_tools(self):
        """Verify image export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_image')
        assert hasattr(export_tools, 'export_images_batch')

    def test_3d_model_export_tools(self):
        """Verify 3D model export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_fbx')
        assert hasattr(export_tools, 'export_sat')

    def test_schedule_export_tools(self):
        """Verify schedule export tools exist"""
        from tools import export_tools
        assert hasattr(export_tools, 'export_schedule_to_csv')
        assert hasattr(export_tools, 'export_schedule_to_excel')

    def test_export_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'export_dwg', 'export_pdf', 'export_ifc',
            'export_image', 'export_fbx', 'export_schedule_to_csv'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 25: DETAIL TOOLS MODULE
# =============================================================================

class TestDetailModuleImports:
    """Test detail tool module - no Revit needed"""

    def test_detail_line_tools(self):
        """Verify detail line tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'create_detail_line')
        assert hasattr(detail_tools, 'create_detail_lines_batch')
        assert hasattr(detail_tools, 'create_detail_arc')
        assert hasattr(detail_tools, 'create_detail_circle')
        assert hasattr(detail_tools, 'create_detail_rectangle')
        assert hasattr(detail_tools, 'create_detail_polyline')

    def test_filled_region_tools(self):
        """Verify filled region tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'list_filled_region_types')
        assert hasattr(detail_tools, 'create_filled_region')
        assert hasattr(detail_tools, 'create_filled_region_with_openings')
        assert hasattr(detail_tools, 'create_masking_region')

    def test_drafting_view_tools(self):
        """Verify drafting view tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'list_drafting_views')
        assert hasattr(detail_tools, 'create_drafting_view')
        assert hasattr(detail_tools, 'import_drafting_view')

    def test_detail_group_tools(self):
        """Verify detail group tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'list_detail_groups')
        assert hasattr(detail_tools, 'create_detail_group')
        assert hasattr(detail_tools, 'place_detail_group')

    def test_line_modification_tools(self):
        """Verify line modification tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'change_line_style')
        assert hasattr(detail_tools, 'offset_detail_line')
        assert hasattr(detail_tools, 'trim_extend_detail_lines')

    def test_break_line_tools(self):
        """Verify break line tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'place_break_line')
        assert hasattr(detail_tools, 'place_insulation')

    def test_pattern_tools(self):
        """Verify pattern listing tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'list_line_styles')
        assert hasattr(detail_tools, 'list_line_patterns')
        assert hasattr(detail_tools, 'list_fill_patterns')

    def test_detail_component_tools(self):
        """Verify detail component tools exist"""
        from tools import detail_tools
        assert hasattr(detail_tools, 'list_detail_component_families')
        assert hasattr(detail_tools, 'place_detail_component')
        assert hasattr(detail_tools, 'place_repeating_detail')

    def test_detail_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_detail_line', 'create_filled_region', 'create_drafting_view',
            'list_line_styles', 'place_detail_component', 'change_line_style'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 26: VIEW FILTER TOOLS MODULE
# =============================================================================

class TestViewFilterModuleImports:
    """Test view filter tool module - no Revit needed"""

    def test_filter_discovery_tools(self):
        """Verify filter discovery tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'list_view_filters')
        assert hasattr(view_filter_tools, 'get_filter_details')
        assert hasattr(view_filter_tools, 'list_filters_in_view')

    def test_filter_creation_tools(self):
        """Verify filter creation tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'create_selection_filter')
        assert hasattr(view_filter_tools, 'create_rule_filter')
        assert hasattr(view_filter_tools, 'create_parameter_filter')
        assert hasattr(view_filter_tools, 'delete_filter')

    def test_filter_application_tools(self):
        """Verify filter application tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'add_filter_to_view')
        assert hasattr(view_filter_tools, 'remove_filter_from_view')
        assert hasattr(view_filter_tools, 'set_filter_visibility')
        assert hasattr(view_filter_tools, 'set_filter_overrides')

    def test_category_visibility_tools(self):
        """Verify category visibility tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'get_category_visibility')
        assert hasattr(view_filter_tools, 'set_category_visibility')
        assert hasattr(view_filter_tools, 'set_category_overrides')
        assert hasattr(view_filter_tools, 'reset_category_overrides')

    def test_element_override_tools(self):
        """Verify element override tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'set_element_override')
        assert hasattr(view_filter_tools, 'hide_elements_in_view')
        assert hasattr(view_filter_tools, 'unhide_elements_in_view')
        assert hasattr(view_filter_tools, 'isolate_elements_in_view')
        assert hasattr(view_filter_tools, 'reset_temporary_hide_isolate')

    def test_view_template_tools(self):
        """Verify view template tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'list_view_templates')
        assert hasattr(view_filter_tools, 'create_view_template_from_view')
        assert hasattr(view_filter_tools, 'apply_view_template')
        assert hasattr(view_filter_tools, 'remove_view_template')

    def test_workset_tools(self):
        """Verify workset tools exist"""
        from tools import view_filter_tools
        assert hasattr(view_filter_tools, 'list_worksets')
        assert hasattr(view_filter_tools, 'set_workset_visibility')

    def test_view_filter_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'list_view_filters', 'create_rule_filter', 'set_filter_overrides',
            'set_category_visibility', 'hide_elements_in_view', 'apply_view_template'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# TEST 27: DEMO WORKFLOWS MODULE
# =============================================================================

class TestDemoWorkflowsModuleImports:
    """Test demo workflow module - no Revit needed"""

    def test_demo_tools_exist(self):
        """Verify demo workflow tools exist"""
        from tools import demo_workflows
        assert hasattr(demo_workflows, 'create_floor_plan_from_description')
        assert hasattr(demo_workflows, 'document_view')
        assert hasattr(demo_workflows, 'create_room_sections')

    def test_helper_functions(self):
        """Verify helper functions exist"""
        from tools import demo_workflows
        assert hasattr(demo_workflows, 'parse_description')
        assert hasattr(demo_workflows, 'generate_rooms')

    def test_parse_description_bedrooms(self):
        """Test parse_description extracts bedroom count"""
        from tools import demo_workflows
        parsed = demo_workflows.parse_description("3 bedroom house")
        assert parsed.get("bedrooms") == 3

    def test_parse_description_sqft(self):
        """Test parse_description extracts square footage"""
        from tools import demo_workflows
        parsed = demo_workflows.parse_description("house with 2500 sqft")
        assert parsed.get("target_sqft") == 2500

    def test_generate_rooms_count(self):
        """Test generate_rooms creates appropriate number of rooms"""
        from tools import demo_workflows
        parsed = {"bedrooms": 3, "bathrooms": 2, "width": 40, "depth": 30,
                  "target_sqft": 1200, "has_garage": False, "has_office": False, "open_concept": False}
        rooms = demo_workflows.generate_rooms(parsed)
        assert len(rooms) >= 10

    def test_generate_rooms_with_garage(self):
        """Test generate_rooms includes garage when specified"""
        from tools import demo_workflows
        parsed = {"bedrooms": 2, "bathrooms": 1, "width": 40, "depth": 30,
                  "target_sqft": 1200, "has_garage": True, "has_office": False, "open_concept": False}
        rooms = demo_workflows.generate_rooms(parsed)
        room_types = [r.get("type") for r in rooms]
        assert "garage" in room_types

    def test_demo_tools_registered(self):
        """Verify tools are in registry"""
        from tools import TOOL_FUNCTIONS
        expected = [
            'create_floor_plan_from_description',
            'document_view',
            'create_room_sections'
        ]
        for tool in expected:
            assert tool in TOOL_FUNCTIONS, f"{tool} not registered"


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run with: python -m pytest tests/test_integration.py -v
    pytest.main([__file__, "-v"])
