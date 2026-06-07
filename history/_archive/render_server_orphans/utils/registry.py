"""Tool registry for managing Revit tools"""

class ToolRegistry:
    """Registry for storing and managing tool functions"""
    
    def __init__(self):
        self.tools_map = {}
        self.tools_list = []
    
    def tool(self):
        """Decorator to register a tool function"""
        def decorator(func):
            self.tools_map[func.__name__] = func
            return func
        return decorator
