# file: family_editor_tools/setup.py
from mcp.server.fastmcp import Context
from tools.utils import format_response

def register_tools(mcp, revit_get, revit_post, revit_image=None):
    """Register family setup and template tools."""

    @mcp.tool()
    async def list_family_templates(ctx: Context = None) -> str:
        """
        Lists all available Family Templates (.rft files).
        Use this to find a valid template name before creating a new family.
        """
        # This calls the C# route we discussed earlier
        response = await revit_get("/family/list_templates", ctx)
        return format_response(response)

    @mcp.tool()
    async def create_new_family(
        template_name: str,
        ctx: Context = None
    ) -> str:
        """
        Creates a new Family Document (.rfa) from a template.
        Args:
            template_name: The file name (e.g., "Metric Generic Model.rft").
        """
        payload = {"template_name": template_name}
        response = await revit_post("/family/create_new", payload, ctx)
        return format_response(response)
