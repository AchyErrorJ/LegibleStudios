# tools/__init__.py

# 1. Expose the master registry dictionary
from .registry import TOOL_FUNCTIONS

# 2. EXPLICITLY Import modules.
#    This forces the files to run and register their tools.
#    Do NOT use a "for loop" or "importlib" here.

from . import geometry_tools
from . import annotation_tools
from . import data_tools
from . import agent_tools
from . import documentation_tools

# 3. Import Family Editor tools
from . import family_editor_tools

# 4. Import Physics Analysis tools
from . import physics_tools

# 5. Import Camera and Channel Extractor tools
try:
    from . import camera_tools
    print(f"  - camera_tools loaded: 1 tool")
except Exception as e:
    print(f"  - camera_tools FAILED: {e}")

try:
    from . import channel_extractor_tools
    print(f"  - channel_extractor_tools loaded: 4 tools")
except Exception as e:
    print(f"  - channel_extractor_tools FAILED: {e}")

# 6. Import Auto-Dimension tools
try:
    from . import auto_dimensions
    print(f"  - auto_dimensions loaded: 4 tools")
except Exception as e:
    print(f"  - auto_dimensions FAILED: {e}")

# 7. Import Demo Workflow tools
try:
    from . import demo_workflows
    print(f"  - demo_workflows loaded: 3 tools")
except Exception as e:
    print(f"  - demo_workflows FAILED: {e}")

# 8. Import Export tools (DWG, PDF, IFC, images)
try:
    from . import export_tools
    print(f"  - export_tools loaded: 14 tools")
except Exception as e:
    print(f"  - export_tools FAILED: {e}")

# 9. Import Stair and Railing tools
try:
    from . import stair_tools
    print(f"  - stair_tools loaded: 18 tools")
except Exception as e:
    print(f"  - stair_tools FAILED: {e}")

# 10. Import Curtain Wall tools
try:
    from . import curtain_wall_tools
    print(f"  - curtain_wall_tools loaded: 24 tools")
except Exception as e:
    print(f"  - curtain_wall_tools FAILED: {e}")

# 11. Import Structural Framing tools (beams, columns, braces)
try:
    from . import structural_tools
    print(f"  - structural_tools loaded: 22 tools")
except Exception as e:
    print(f"  - structural_tools FAILED: {e}")

# 12. Import CAD/Image/Point Cloud import tools
try:
    from . import import_tools
    print(f"  - import_tools loaded: 24 tools")
except Exception as e:
    print(f"  - import_tools FAILED: {e}")

# 13. Import View Filter and VG Override tools
try:
    from . import view_filter_tools
    print(f"  - view_filter_tools loaded: 26 tools")
except Exception as e:
    print(f"  - view_filter_tools FAILED: {e}")

# 14. Import Detail Line and Drafting tools
try:
    from . import detail_tools
    print(f"  - detail_tools loaded: 26 tools")
except Exception as e:
    print(f"  - detail_tools FAILED: {e}")

# 15. Import Smart Tool Selector (for local LLM mode)
try:
    from . import tool_selector
    print(f"  - tool_selector loaded: 3 tools")
except Exception as e:
    print(f"  - tool_selector FAILED: {e}")

# 16. Print confirmation
print(f"Tools Package Loaded. Actual Count: {len(TOOL_FUNCTIONS)}")
