"""
Tool Input Validation Module

Validates tool inputs before sending to Revit to catch errors early
and provide helpful error messages.

Usage:
    from tools.validation import validate_point, validate_level_name, ValidationError

    @mcp.tool()
    async def create_wall(start_point, end_point, level_name, height=10.0):
        # Validate inputs
        validate_point(start_point, "start_point")
        validate_point(end_point, "end_point")
        validate_level_name(level_name)
        validate_positive(height, "height")

        # If we get here, inputs are valid
        ...
"""

from typing import Any, List, Optional, Union
import re


class ValidationError(Exception):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: str = None, value: Any = None, suggestion: str = None):
        self.field = field
        self.value = value
        self.suggestion = suggestion
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "status": "error",
            "error_type": "INVALID_INPUT",
            "message": str(self),
            "field": self.field,
            "value": str(self.value) if self.value is not None else None,
            "recovery": self.suggestion
        }


# =============================================================================
# POINT VALIDATION
# =============================================================================

def validate_point(value: Any, field_name: str = "point") -> List[float]:
    """
    Validate a 3D point [x, y, z].
    Accepts: [x,y,z], (x,y,z), {"x":x, "y":y, "z":z}
    Returns: [x, y, z] as floats
    """
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
            suggestion="Provide a point as [x, y, z] in feet"
        )

    # Handle dict format
    if isinstance(value, dict):
        try:
            return [float(value.get('x', 0)), float(value.get('y', 0)), float(value.get('z', 0))]
        except (TypeError, ValueError):
            raise ValidationError(
                f"{field_name} dict must have numeric x, y, z values",
                field=field_name,
                value=value
            )

    # Handle list/tuple
    if isinstance(value, (list, tuple)):
        if len(value) < 2:
            raise ValidationError(
                f"{field_name} must have at least 2 coordinates (x, y)",
                field=field_name,
                value=value,
                suggestion="Use format [x, y, z] or [x, y]"
            )
        try:
            x = float(value[0])
            y = float(value[1])
            z = float(value[2]) if len(value) > 2 else 0.0
            return [x, y, z]
        except (TypeError, ValueError):
            raise ValidationError(
                f"{field_name} coordinates must be numbers",
                field=field_name,
                value=value
            )

    # Handle single number (assume x coordinate)
    if isinstance(value, (int, float)):
        raise ValidationError(
            f"{field_name} must be a point [x, y, z], not a single number",
            field=field_name,
            value=value,
            suggestion="Use format [x, y, z] in feet"
        )

    raise ValidationError(
        f"{field_name} must be a list [x, y, z]",
        field=field_name,
        value=value
    )


def validate_points_list(value: Any, field_name: str = "points", min_count: int = 3) -> List[List[float]]:
    """
    Validate a list of points (e.g., for floor boundary).
    """
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
            suggestion=f"Provide at least {min_count} points as [[x,y,z], [x,y,z], ...]"
        )

    if not isinstance(value, (list, tuple)):
        raise ValidationError(
            f"{field_name} must be a list of points",
            field=field_name,
            value=value
        )

    if len(value) < min_count:
        raise ValidationError(
            f"{field_name} must have at least {min_count} points",
            field=field_name,
            value=f"Got {len(value)} points",
            suggestion=f"Provide at least {min_count} boundary points"
        )

    validated = []
    for i, pt in enumerate(value):
        try:
            validated.append(validate_point(pt, f"{field_name}[{i}]"))
        except ValidationError as e:
            raise ValidationError(
                f"Invalid point at index {i}: {e}",
                field=field_name,
                value=pt
            )

    return validated


# =============================================================================
# STRING VALIDATION
# =============================================================================

def validate_string(value: Any, field_name: str, allow_empty: bool = False) -> str:
    """Validate a string field"""
    if value is None:
        if allow_empty:
            return ""
        raise ValidationError(
            f"{field_name} is required",
            field=field_name
        )

    if not isinstance(value, str):
        # Try to convert
        try:
            value = str(value)
        except:
            raise ValidationError(
                f"{field_name} must be a string",
                field=field_name,
                value=value
            )

    if not allow_empty and not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name
        )

    return value.strip()


def validate_level_name(value: Any, field_name: str = "level_name") -> str:
    """Validate a level name"""
    name = validate_string(value, field_name)

    # Common mistakes
    if name.lower() in ['level', 'floor', 'ground']:
        raise ValidationError(
            f"{field_name} '{name}' is incomplete",
            field=field_name,
            value=name,
            suggestion="Use full level name like 'Level 1' or 'Ground Floor'. Use list_levels to see available levels."
        )

    return name


def validate_type_name(value: Any, field_name: str, category: str = "element") -> str:
    """Validate a type name"""
    return validate_string(value, field_name, allow_empty=True)


# =============================================================================
# NUMERIC VALIDATION
# =============================================================================

def validate_number(value: Any, field_name: str) -> float:
    """Validate a numeric value"""
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name
        )

    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{field_name} must be a number",
            field=field_name,
            value=value
        )


def validate_positive(value: Any, field_name: str, allow_zero: bool = False) -> float:
    """Validate a positive number"""
    num = validate_number(value, field_name)

    if allow_zero:
        if num < 0:
            raise ValidationError(
                f"{field_name} must be >= 0",
                field=field_name,
                value=num
            )
    else:
        if num <= 0:
            raise ValidationError(
                f"{field_name} must be > 0",
                field=field_name,
                value=num
            )

    return num


def validate_range(value: Any, field_name: str, min_val: float, max_val: float) -> float:
    """Validate a number within a range"""
    num = validate_number(value, field_name)

    if num < min_val or num > max_val:
        raise ValidationError(
            f"{field_name} must be between {min_val} and {max_val}",
            field=field_name,
            value=num
        )

    return num


def validate_integer(value: Any, field_name: str) -> int:
    """Validate an integer"""
    num = validate_number(value, field_name)
    return int(num)


def validate_element_id(value: Any, field_name: str = "element_id") -> int:
    """Validate a Revit element ID"""
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
            suggestion="Provide a valid element ID (integer)"
        )

    try:
        id_val = int(value)
        if id_val <= 0:
            raise ValidationError(
                f"{field_name} must be a positive integer",
                field=field_name,
                value=value
            )
        return id_val
    except (TypeError, ValueError):
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
            value=value,
            suggestion="Element IDs are integers returned by list_* tools"
        )


# =============================================================================
# COLLECTION VALIDATION
# =============================================================================

def validate_list(value: Any, field_name: str, min_items: int = 0) -> list:
    """Validate a list/array"""
    if value is None:
        if min_items > 0:
            raise ValidationError(
                f"{field_name} is required",
                field=field_name
            )
        return []

    if isinstance(value, str):
        # Try to parse as JSON
        import json
        try:
            value = json.loads(value)
        except:
            raise ValidationError(
                f"{field_name} must be a list, not a string",
                field=field_name,
                value=value[:50] + "..." if len(value) > 50 else value
            )

    if not isinstance(value, (list, tuple)):
        raise ValidationError(
            f"{field_name} must be a list",
            field=field_name,
            value=type(value).__name__
        )

    if len(value) < min_items:
        raise ValidationError(
            f"{field_name} must have at least {min_items} items",
            field=field_name,
            value=f"Got {len(value)} items"
        )

    return list(value)


def validate_dict(value: Any, field_name: str, required_keys: List[str] = None) -> dict:
    """Validate a dictionary"""
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name
        )

    if isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except:
            raise ValidationError(
                f"{field_name} must be an object/dict",
                field=field_name
            )

    if not isinstance(value, dict):
        raise ValidationError(
            f"{field_name} must be an object/dict",
            field=field_name,
            value=type(value).__name__
        )

    if required_keys:
        missing = [k for k in required_keys if k not in value]
        if missing:
            raise ValidationError(
                f"{field_name} is missing required keys: {missing}",
                field=field_name,
                suggestion=f"Required keys: {required_keys}"
            )

    return value


# =============================================================================
# GEOMETRY VALIDATION
# =============================================================================

def validate_wall_params(start_point, end_point, height=None) -> dict:
    """Validate wall creation parameters"""
    start = validate_point(start_point, "start_point")
    end = validate_point(end_point, "end_point")

    # Check that start and end are different
    if start[0] == end[0] and start[1] == end[1]:
        raise ValidationError(
            "start_point and end_point cannot be the same",
            field="end_point",
            value=end,
            suggestion="Wall must have length > 0"
        )

    # Calculate wall length
    import math
    length = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

    if length < 0.1:
        raise ValidationError(
            f"Wall is too short ({length:.2f} ft)",
            field="end_point",
            suggestion="Minimum wall length is ~1 inch"
        )

    result = {"start_point": start, "end_point": end, "length": length}

    if height is not None:
        result["height"] = validate_positive(height, "height")

    return result


def validate_floor_boundary(points) -> List[List[float]]:
    """Validate floor boundary points"""
    validated = validate_points_list(points, "points", min_count=3)

    # Check that points form a closed loop or can close
    # (Floor API typically auto-closes)

    return validated


# =============================================================================
# CONVENIENCE DECORATORS
# =============================================================================

def with_validation(func):
    """
    Decorator that catches ValidationErrors and returns proper error responses.

    Usage:
        @mcp.tool()
        @with_validation
        async def my_tool(param1, param2):
            validate_string(param1, "param1")
            ...
    """
    import functools
    import json

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ValidationError as e:
            return json.dumps(e.to_dict())

    return wrapper
