"""
Error Helpers for RevitMCP
==========================
Centralized error handling with helpful messages and recovery guidance.
"""

import httpx
from typing import Dict, Any, Optional
from enum import Enum


class ErrorCategory(Enum):
    CONNECTION = "connection"
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    REVIT_ERROR = "revit_error"
    TIMEOUT = "timeout"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


# Error messages with recovery guidance
ERROR_MESSAGES = {
    ErrorCategory.CONNECTION: {
        "message": "Cannot connect to Revit",
        "recovery": [
            "1. Ensure Revit is running",
            "2. Check that the RevitMCP add-in is loaded (Add-Ins tab)",
            "3. Verify the add-in server is started (click 'Start Server' in add-in)",
            "4. Check firewall allows localhost:48884",
            "5. Try restarting Revit if the issue persists"
        ]
    },
    ErrorCategory.NOT_FOUND: {
        "message": "Element not found in model",
        "recovery": [
            "1. Verify the element ID is correct",
            "2. Check that the element hasn't been deleted",
            "3. Ensure you're looking at the correct level/view",
            "4. Use list_* tools to find valid element IDs"
        ]
    },
    ErrorCategory.INVALID_INPUT: {
        "message": "Invalid input parameters",
        "recovery": [
            "1. Check parameter types (numbers vs strings)",
            "2. Ensure required parameters are provided",
            "3. Verify coordinate values are reasonable",
            "4. Check that element IDs are integers"
        ]
    },
    ErrorCategory.REVIT_ERROR: {
        "message": "Revit operation failed",
        "recovery": [
            "1. Check Revit for error dialogs",
            "2. Ensure the model isn't in a read-only state",
            "3. Verify you have permission to modify the model",
            "4. Try undoing recent operations and retrying"
        ]
    },
    ErrorCategory.TIMEOUT: {
        "message": "Operation timed out",
        "recovery": [
            "1. The model may be very large - try a simpler operation",
            "2. Revit might be busy - wait and retry",
            "3. Close other heavy applications",
            "4. Consider breaking the operation into smaller steps"
        ]
    },
    ErrorCategory.PERMISSION: {
        "message": "Permission denied",
        "recovery": [
            "1. Check if the model is opened for editing",
            "2. Verify you're not in a read-only view",
            "3. Ensure the file isn't locked by another user",
            "4. Check Revit worksharing status"
        ]
    }
}


def categorize_error(error_message: str) -> ErrorCategory:
    """Categorize an error based on its message."""
    msg_lower = error_message.lower()

    if any(x in msg_lower for x in ["connect", "connection", "refused", "unreachable", "timeout"]):
        if "timeout" in msg_lower:
            return ErrorCategory.TIMEOUT
        return ErrorCategory.CONNECTION

    if any(x in msg_lower for x in ["not found", "does not exist", "invalid id", "no element"]):
        return ErrorCategory.NOT_FOUND

    if any(x in msg_lower for x in ["invalid", "parameter", "type", "expected"]):
        return ErrorCategory.INVALID_INPUT

    if any(x in msg_lower for x in ["permission", "access denied", "read-only"]):
        return ErrorCategory.PERMISSION

    if any(x in msg_lower for x in ["revit", "transaction", "failed to"]):
        return ErrorCategory.REVIT_ERROR

    return ErrorCategory.UNKNOWN


def format_error_response(
    error: Exception,
    context: str = None,
    original_error: str = None
) -> Dict[str, Any]:
    """
    Format an error with helpful recovery guidance.

    Args:
        error: The exception that occurred
        context: What operation was being attempted
        original_error: Original error message from Revit

    Returns:
        Formatted error response with recovery steps
    """
    error_msg = str(error)

    # Categorize the error
    category = categorize_error(error_msg)
    error_info = ERROR_MESSAGES.get(category, ERROR_MESSAGES[ErrorCategory.UNKNOWN])

    response = {
        "status": "error",
        "category": category.value,
        "message": error_info["message"],
        "details": error_msg,
        "recovery_steps": error_info["recovery"]
    }

    if context:
        response["context"] = context

    if original_error and original_error != error_msg:
        response["original_error"] = original_error

    return response


def check_revit_connection() -> Dict[str, Any]:
    """
    Check if Revit is connected and responding.

    Returns:
        Connection status with helpful message
    """
    import asyncio

    async def _check():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "http://localhost:48884/revit_mcp/status/",
                    timeout=5.0
                )
                if resp.status_code == 200:
                    return {
                        "connected": True,
                        "message": "Revit is connected and responding"
                    }
                else:
                    return {
                        "connected": False,
                        "message": f"Revit returned status {resp.status_code}",
                        "recovery_steps": ERROR_MESSAGES[ErrorCategory.CONNECTION]["recovery"]
                    }
        except httpx.TimeoutException:
            return {
                "connected": False,
                "message": "Connection to Revit timed out",
                "recovery_steps": ERROR_MESSAGES[ErrorCategory.TIMEOUT]["recovery"]
            }
        except Exception as e:
            return {
                "connected": False,
                "message": str(e),
                "recovery_steps": ERROR_MESSAGES[ErrorCategory.CONNECTION]["recovery"]
            }

    return asyncio.get_event_loop().run_until_complete(_check())


def validate_element_ids(element_ids: list) -> Optional[str]:
    """
    Validate a list of element IDs.

    Returns:
        Error message if invalid, None if valid
    """
    if not element_ids:
        return "No element IDs provided"

    if not isinstance(element_ids, list):
        return "element_ids must be a list"

    for i, eid in enumerate(element_ids):
        if not isinstance(eid, (int, str)):
            return f"Element ID at index {i} is not a valid type (got {type(eid).__name__})"

        if isinstance(eid, str):
            try:
                int(eid)
            except ValueError:
                return f"Element ID '{eid}' at index {i} cannot be converted to integer"

    return None


def validate_point(point: list, name: str = "point") -> Optional[str]:
    """
    Validate a 3D point.

    Returns:
        Error message if invalid, None if valid
    """
    if not point:
        return f"{name} is required"

    if not isinstance(point, list):
        return f"{name} must be a list [x, y, z]"

    if len(point) < 2:
        return f"{name} must have at least 2 coordinates [x, y] or [x, y, z]"

    for i, coord in enumerate(point[:3]):
        if not isinstance(coord, (int, float)):
            return f"{name}[{i}] must be a number, got {type(coord).__name__}"

    return None


def validate_level_name(level_name: str) -> Optional[str]:
    """
    Validate a level name.

    Returns:
        Error message if invalid, None if valid
    """
    if not level_name:
        return None  # Optional - will use default

    if not isinstance(level_name, str):
        return f"level_name must be a string, got {type(level_name).__name__}"

    if len(level_name) > 100:
        return "level_name is too long (max 100 characters)"

    return None


# Decorator for adding error handling to async functions
def with_error_handling(context: str = None):
    """
    Decorator that adds standardized error handling to async tools.

    Usage:
        @with_error_handling("creating walls")
        async def create_walls(...):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except httpx.ConnectError as e:
                return format_error_response(e, context or func.__name__)
            except httpx.TimeoutException as e:
                return format_error_response(e, context or func.__name__)
            except Exception as e:
                return format_error_response(e, context or func.__name__)
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
