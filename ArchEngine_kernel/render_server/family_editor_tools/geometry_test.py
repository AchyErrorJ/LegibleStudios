# =========================================================
# FAMILY EDITOR TEST TOOL
# =========================================================
def register_tools(mcp, revit_get, revit_post, revit_image=None):
    async def hello_family_editor(args):
        """
        Simple connection test for Family Editor mode.
        """
        return "✅ The Family Editor Tool Suite is connected and ready!"

   