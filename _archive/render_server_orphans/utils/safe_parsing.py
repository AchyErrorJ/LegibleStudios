"""
Safe Parsing Utilities
======================
Utilities for safely parsing user input and API responses to prevent crashes.
"""

from typing import Any, List, Tuple, Optional, Union


def safe_parse_coords(coord: Any, required_dims: int = 2) -> Tuple[Optional[List[float]], Optional[str]]:
    """
    Safely parse coordinates from various formats.

    Args:
        coord: Coordinate data (string "{x, y, z}", dict {"x": 0, "y": 0}, list [x, y, z])
        required_dims: Minimum number of dimensions required (default 2)

    Returns:
        Tuple of (coordinates list, error message or None)

    Examples:
        >>> safe_parse_coords("{0.0, 10.5, 0.0}")
        ([0.0, 10.5, 0.0], None)
        >>> safe_parse_coords({"x": 5, "y": 10})
        ([5.0, 10.0], None)
        >>> safe_parse_coords([1, 2, 3])
        ([1.0, 2.0, 3.0], None)
        >>> safe_parse_coords("invalid")
        (None, "Invalid coordinate format: invalid")
    """
    try:
        coords = []

        if coord is None:
            return None, "Coordinate is None"

        if isinstance(coord, str):
            # Handle format like "{0.0, 10.5, 0.0}" or "[0, 10, 0]"
            cleaned = coord.strip('{}[]() ')
            if not cleaned:
                return None, "Empty coordinate string"
            parts = [p.strip() for p in cleaned.split(',')]
            coords = [float(p) for p in parts if p]

        elif isinstance(coord, dict):
            # Handle format like {"x": 0, "y": 0, "z": 0}
            if 'x' in coord or 'X' in coord:
                coords = [
                    float(coord.get('x', coord.get('X', 0))),
                    float(coord.get('y', coord.get('Y', 0))),
                ]
                if 'z' in coord or 'Z' in coord:
                    coords.append(float(coord.get('z', coord.get('Z', 0))))
            else:
                return None, f"Dict missing x/y keys: {coord}"

        elif isinstance(coord, (list, tuple)):
            coords = [float(c) for c in coord]

        else:
            return None, f"Invalid coordinate type: {type(coord).__name__}"

        if len(coords) < required_dims:
            return None, f"Need {required_dims} dimensions, got {len(coords)}"

        return coords[:max(required_dims, len(coords))], None

    except ValueError as e:
        return None, f"Non-numeric coordinate value: {e}"
    except Exception as e:
        return None, f"Coordinate parsing error: {e}"


def safe_split_extract(text: str, delimiter: str, index: int, default: Optional[str] = None) -> str:
    """
    Safely split a string and extract an element at the given index.

    Args:
        text: String to split
        delimiter: Delimiter to split on
        index: Index to extract
        default: Value to return if index doesn't exist

    Returns:
        Extracted string or default value

    Examples:
        >>> safe_split_extract("a:b:c", ":", 1)
        "b"
        >>> safe_split_extract("a:b", ":", 5, "missing")
        "missing"
    """
    if not isinstance(text, str):
        return default if default is not None else ""

    parts = text.split(delimiter, max(index + 1, 1))
    if len(parts) > index:
        return parts[index].strip()
    return default if default is not None else ""


def safe_get_first(lst: Any, key: Optional[str] = None, default: Any = None) -> Any:
    """
    Safely get the first element of a list, optionally extracting a key from it.

    Args:
        lst: List to get first element from
        key: Optional key to extract from first element (if it's a dict)
        default: Value to return if list is empty or key missing

    Returns:
        First element, key value, or default

    Examples:
        >>> safe_get_first([{"id": 123}, {"id": 456}], "id")
        123
        >>> safe_get_first([], "id", "no items")
        "no items"
        >>> safe_get_first([1, 2, 3])
        1
    """
    if not isinstance(lst, (list, tuple)) or len(lst) == 0:
        return default

    first = lst[0]

    if key is not None and isinstance(first, dict):
        return first.get(key, default)

    return first


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    Args:
        value: Value to convert
        default: Value to return on conversion failure

    Returns:
        Float value or default

    Examples:
        >>> safe_float("3.14")
        3.14
        >>> safe_float("abc", 0.0)
        0.0
        >>> safe_float(None)
        0.0
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to int.

    Args:
        value: Value to convert
        default: Value to return on conversion failure

    Returns:
        Int value or default
    """
    if value is None:
        return default
    try:
        return int(float(value))  # Handle "3.5" -> 3
    except (ValueError, TypeError):
        return default


def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get a nested value from a dictionary.

    Args:
        data: Dictionary to traverse
        *keys: Keys to follow in order
        default: Value to return if any key is missing

    Returns:
        Nested value or default

    Examples:
        >>> safe_get_nested({"a": {"b": {"c": 1}}}, "a", "b", "c")
        1
        >>> safe_get_nested({"a": 1}, "a", "b", "c", default="missing")
        "missing"
    """
    if not isinstance(data, dict):
        return default

    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default

    return current


def safe_json_get(response: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely extract values from a JSON-like response structure.
    Handles common API response patterns.

    Args:
        response: API response (dict, list, or string)
        *keys: Keys to extract in order
        default: Value to return on failure

    Returns:
        Extracted value or default
    """
    if response is None:
        return default

    # If response is a list and first key is numeric, get by index
    if isinstance(response, list):
        if keys and keys[0].isdigit():
            idx = int(keys[0])
            if 0 <= idx < len(response):
                if len(keys) == 1:
                    return response[idx]
                return safe_json_get(response[idx], *keys[1:], default=default)
        return default

    if isinstance(response, dict):
        return safe_get_nested(response, *keys, default=default)

    return default


def validate_element_ids(ids: Any) -> Tuple[List[str], List[str]]:
    """
    Validate and clean a list of element IDs.

    Args:
        ids: List of IDs (can be ints, strings, or dicts with 'id' key)

    Returns:
        Tuple of (valid IDs, invalid entries)
    """
    valid = []
    invalid = []

    if not isinstance(ids, (list, tuple)):
        return [], [str(ids)]

    for item in ids:
        if isinstance(item, (int, str)) and str(item).strip():
            valid.append(str(item).strip())
        elif isinstance(item, dict) and 'id' in item:
            valid.append(str(item['id']).strip())
        else:
            invalid.append(str(item))

    return valid, invalid
