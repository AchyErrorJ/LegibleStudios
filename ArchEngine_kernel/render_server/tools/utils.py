# -*- coding: utf-8 -*-
"""Utility functions for MCP tools"""

import functools

def format_response(response):
    """Helper function to format API responses consistently for MCP tools.

    Args:
        response: The response from a revit_get or revit_post call, can be dict or string

    Returns:
        str: Formatted string response suitable for MCP tool return values
    """
    if isinstance(response, dict):
        # FIX 1: Cast to string before .lower() to prevent crashes on integer status codes (e.g. 200)
        status = str(response.get("status", "")).lower()
        health = str(response.get("health", "")).lower()
        
        # BATCH OPERATIONS - Handle specially
        if status == "batch_complete":
            results = response.get("results", [])
            
            # Count successes
            success_count = 0
            for r in results:
                # Check both result.status and result.result.status patterns
                r_status = str(r.get("status", "")).lower()
                if r_status in ["success", "200", "ok"]:
                    success_count += 1
                elif isinstance(r.get("result"), dict):
                    nested_status = str(r["result"].get("status", "")).lower()
                    if nested_status in ["success", "200", "ok"]:
                        success_count += 1
            
            total = len(results)
            
            if success_count == total:
                return "Batch operation completed successfully: {}/{} items created.\n{}".format(
                    success_count, total, str(response))
            else:
                return "Batch operation completed: {}/{} successful, {} failed.\n{}".format(
                    success_count, total, total - success_count, str(response))
        
        # FIX 2: Expanded Success conditions to include "200", "ok", "true"
        is_success = (status in ["success", "200", "ok", "true"] or 
                     (status == "active" and health == "healthy") or
                     (status == "active" and "revit_available" in response and response["revit_available"]))
        
        if is_success:
            # For successful responses, return the most relevant data
            if "output" in response:  # Code execution responses
                return response["output"]
            elif "message" in response:
                return response["message"]
            elif "result" in response:
                return str(response["result"])
            elif "data" in response:
                return str(response["data"])
            elif status == "active":  # Status check responses
                # Format status response nicely
                status_parts = ["=== REVIT STATUS ==="]
                status_parts.append("Status: {}".format(response.get("status", "Unknown")))
                status_parts.append("Health: {}".format(response.get("health", "Unknown")))
                
                if "api_name" in response:
                    status_parts.append("API: {}".format(response["api_name"]))
                if "document_title" in response:
                    status_parts.append("Document: {}".format(response["document_title"]))
                if "revit_available" in response:
                    status_parts.append("Revit Available: {}".format(response["revit_available"]))
                
                # Add any other fields that might be present
                known_fields = {"status", "health", "api_name", "document_title", "revit_available"}
                other_fields = set(response.keys()) - known_fields
                if other_fields:
                    status_parts.append("")
                    for field in sorted(other_fields):
                        status_parts.append("{}: {}".format(field.replace("_", " ").title(), response[field]))
                
                return "\n".join(status_parts)
            else:
                return "Operation completed successfully"
        else:
            # Error case - provide verbose debugging information
            error_msg = response.get("error", "Unknown error occurred")
            traceback_info = response.get("traceback", "")
            details = response.get("details", "")
            
            # Build comprehensive error message
            error_parts = ["=== ERROR DETAILS ==="]
            error_parts.append("Status: {}".format(status))
            error_parts.append("Error: {}".format(error_msg))
            
            if details:
                error_parts.append("Details: {}".format(details))
            
            if traceback_info:  # Code execution error with traceback
                error_parts.append("\n=== TRACEBACK ===")
                error_parts.append(traceback_info)
            
            # Add any additional fields that might be helpful for debugging
            debug_fields = ["code_attempted", "endpoint", "request_data", "response_code"]
            for field in debug_fields:
                if field in response:
                    error_parts.append("{}: {}".format(field.replace("_", " ").title(), response[field]))
            
            # Include full response for debugging if it has unexpected fields
            response_keys = set(response.keys()) - {"error", "traceback", "details", "status", "code_attempted", "endpoint", "request_data", "response_code"}
            if response_keys:
                error_parts.append("\n=== ADDITIONAL RESPONSE DATA ===")
                for key in sorted(response_keys):
                    error_parts.append("{}: {}".format(key, response[key]))
            
            return "\n".join(error_parts)
    else:
        # If response is already a string (error case from _revit_call)
        return str(response)

# The private, master dictionary holding ALL registered tools
# Key: The tool's unique name (e.g., "create_wall")
# Value: The actual Python function object (e.g., <function walls_tools.create_wall>)
_TOOL_REGISTRY = {}


def mcp_tool(name: str, description: str, parameters: dict):
    """Decorator to register a function as an LLM tool with metadata."""
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # 1. Get the module name where this tool is defined
        module_name = func.__module__
        
        # 2. Store the function in the global registry
        # FIX: Check if it exists, warn, and OVERWRITE instead of crashing.
        if name in _TOOL_REGISTRY:
            print(f"⚠️  Warning: Tool '{name}' re-registered (Double-Import detected). Overwriting.")
            
        _TOOL_REGISTRY[name] = {
            "function": func,
            "module": module_name,
            "description": description,
            "parameters": parameters,
        }
        return wrapper
    return decorator


# ==============================================================================
# 2. REGISTRY ACCESSORS
# ==============================================================================

def get_tool_functions_for_module(module_name: str) -> list:
    """
    Returns a list of the actual Python function objects registered 
    in the master registry for a specific module.
    """
    local_functions = []
    
    for tool_data in _TOOL_REGISTRY.values():
        if tool_data["module"] == module_name:
            local_functions.append(tool_data["function"])
            
    return local_functions

def get_full_tool_registry() -> dict:
    """
    Returns the full dictionary of tool names mapped to function objects.
    """
    return {name: data["function"] for name, data in _TOOL_REGISTRY.items()}

