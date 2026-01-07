# schema_generator.py - Optimized for minimal token usage
import inspect
import typing
from typing import List, Optional, Union, Dict, Any
import re


def python_type_to_json_type(py_type):
    """Maps Python types to JSON Schema types."""
    if py_type == str:
        return "string"
    if py_type == int:
        return "integer"
    if py_type == float:
        return "number"
    if py_type == bool:
        return "boolean"
    if py_type == list or py_type == List:
        return "array"
    if py_type == dict or py_type == Dict:
        return "object"
    return "string"


def extract_short_description(docstring: str) -> str:
    """
    Extract only the first sentence/line of a docstring.
    Removes Args:, Example:, etc. sections.
    """
    if not docstring:
        return ""
    
    # Split by common section headers
    sections = re.split(r'\n\s*(Args:|Arguments:|Parameters:|Returns:|Example:|Examples:|Note:|Notes:)', docstring, flags=re.IGNORECASE)
    first_part = sections[0].strip()
    
    # Get first sentence only (ends with period, or first line)
    lines = first_part.split('\n')
    first_line = lines[0].strip()
    
    # If first line ends with period, use it
    if first_line.endswith('.'):
        return first_line
    
    # Otherwise find first sentence
    match = re.match(r'^(.+?\.)\s', first_part)
    if match:
        return match.group(1)
    
    # Fallback: first line, max 100 chars
    return first_line[:100]


def extract_param_descriptions(docstring: str) -> Dict[str, str]:
    """
    Extract parameter descriptions from Args: section.
    Returns short versions only.
    """
    param_descs = {}
    if not docstring:
        return param_descs
    
    # Find Args section
    args_match = re.search(r'Args:\s*\n(.*?)(?=\n\s*(?:Returns:|Example:|Notes:|$))', docstring, re.DOTALL | re.IGNORECASE)
    if not args_match:
        return param_descs
    
    args_text = args_match.group(1)
    
    # Parse each parameter line
    # Pattern: param_name: description or param_name (type): description
    param_pattern = re.compile(r'^\s*(\w+)(?:\s*\([^)]*\))?:\s*(.+?)(?=\n\s*\w+:|$)', re.MULTILINE | re.DOTALL)
    
    for match in param_pattern.finditer(args_text):
        param_name = match.group(1)
        desc = match.group(2).strip()
        # Take only first line/sentence, max 60 chars
        first_line = desc.split('\n')[0].strip()
        short_desc = first_line[:60]
        if len(first_line) > 60:
            short_desc = short_desc.rsplit(' ', 1)[0] + '...'
        param_descs[param_name] = short_desc
    
    return param_descs


def get_openai_tool_schema(func, verbose=False):
    """
    Converts a Python function into an OpenAI Tool Definition.
    
    Args:
        func: The function to convert
        verbose: If True, include full descriptions. If False, use minimal descriptions.
    """
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    
    # Use short or full description based on verbose flag
    if verbose:
        description = doc.strip()
    else:
        description = extract_short_description(doc)
    
    # Get parameter descriptions from docstring
    param_descs = extract_param_descriptions(doc) if verbose else {}
    
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    for name, param in sig.parameters.items():
        # SKIP the 'ctx' context parameter
        if name == "ctx":
            continue
        
        # Get Type
        type_hint = param.annotation
        json_type = "string"
        items_type = None
        
        # Handle typing.List[...], typing.Union[...], etc.
        origin = getattr(type_hint, "__origin__", None)
        
        if origin == list:
            json_type = "array"
            # Get item type if available
            args = getattr(type_hint, "__args__", None)
            if args:
                inner_type = args[0]
                inner_origin = getattr(inner_type, "__origin__", None)
                if inner_origin == list:
                    # List[List[float]] -> array of arrays
                    items_type = {"type": "array", "items": {"type": "number"}}
                elif inner_type == float or inner_type == int:
                    items_type = {"type": "number"}
                elif inner_type == str:
                    items_type = {"type": "string"}
                    # Check if docstring describes object properties
                    if "start_point" in doc and "end_point" in doc:
                        items_type = {
                            "type": "object",
                            "properties": {
                                "start_point": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "Starting point [x, y, z]"
                                },
                                "end_point": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "Ending point [x, y, z]"
                                }
                            },
                            "required": ["start_point", "end_point"]
                        }
        
                        # Add level_name if mentioned in docstring
                        if "level_name" in doc:
                            items_type["properties"]["level_name"] = {
                                "type": "string",
                                "description": "Level name"
                            }
                            items_type["required"].append("level_name")
                elif inner_type == dict or str(inner_type) == "<class 'dict'>":
                    # List[dict] -> array of objects
                    # Try to infer structure from docstring
                    items_type = {"type": "object"}
            
                    # For create_walls_batch specifically, add proper schema
                    if func.__name__ == "create_walls_batch":
                        items_type = {
                            "type": "object",
                            "properties": {
                                "start_point": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "Starting point [x, y, z]"
                                },
                                "end_point": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "description": "Ending point [x, y, z]"
                                },
                                "level_name": {
                                    "type": "string",
                                    "description": "Level name"
                                },
                                "height": {
                                    "type": "number",
                                    "description": "Wall height (optional)"
                                },
                                "wall_type": {
                                    "type": "string",
                                    "description": "Wall type (optional)"
                                }
                            },
                            "required": ["start_point", "end_point", "level_name"]
                        }
                else:
                    items_type = {"type": "object"}  # Generic object for unknown types
        elif origin == Union:
            # Handle Optional (Union with None) or Union types
            args = getattr(type_hint, "__args__", ())
            non_none_args = [a for a in args if a is not type(None)]
            if non_none_args:
                json_type = python_type_to_json_type(non_none_args[0])
        else:
            json_type = python_type_to_json_type(type_hint)
        
        # Build parameter schema
        param_schema = {"type": json_type}
        
        # Add items for arrays
        if json_type == "array" and items_type:
            param_schema["items"] = items_type
        elif json_type == "array":
            param_schema["items"] = {"type": "number"}  # Default for points
        
        # Add description only if verbose and available
        if verbose and name in param_descs:
            param_schema["description"] = param_descs[name]
        
        parameters["properties"][name] = param_schema
        
        # Check if required (no default value and not Optional)
        is_optional = origin == Union and type(None) in getattr(type_hint, "__args__", ())
        if param.default == inspect.Parameter.empty and not is_optional:
            parameters["required"].append(name)
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": parameters
        }
    }


def generate_all_schemas(tool_registry, verbose=False):
    """
    Generates a list of schemas for all tools in your registry.
    
    Args:
        tool_registry: Your tool registry with tools_map
        verbose: If True, include full descriptions. If False, minimal descriptions.
    """
    schemas = []
    for name, func in tool_registry.tools_map.items():
        try:
            schema = get_openai_tool_schema(func, verbose=verbose)
            schemas.append(schema)
        except Exception as e:
            print(f"Failed to generate schema for {name}: {e}")
    return schemas


# --- EVEN MORE COMPACT: Manual schema definitions ---
def get_compact_tool_schemas():
    """
    Manually defined compact schemas for maximum token efficiency.
    Use this if auto-generation is still too verbose.
    """
    return [
        # Example of ultra-compact schema
        {
            "type": "function",
            "function": {
                "name": "create_wall",
                "description": "Create wall between two points",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start_point": {"type": "array", "items": {"type": "number"}},
                        "end_point": {"type": "array", "items": {"type": "number"}},
                        "level_name": {"type": "string"},
                        "height": {"type": "number"},
                        "wall_type": {"type": "string"}
                    },
                    "required": ["start_point", "end_point", "level_name"]
                }
            }
        },
        # Add more tools here...
        {
            "type": "function",
            "function": {
                "name": "create_walls_batch",
                "description": "Creates MULTIPLE Walls in one transaction. More efficient than calling create_wall multiple times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "walls": {
                            "type": "array",
                            "description": "List of wall objects to create",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_point": {
                                        "type": "array",
                                        "description": "Starting point [x, y, z] in feet",
                                        "items": {"type": "number"}
                                    },
                                    "end_point": {
                                        "type": "array",
                                        "description": "Ending point [x, y, z] in feet",
                                        "items": {"type": "number"}
                                    },
                                    "level_name": {
                                        "type": "string",
                                        "description": "Level name (e.g. 'Level 0')"
                                    },
                                    "height": {
                                        "type": "number",
                                        "description": "Wall height in feet (optional)"
                                    },
                                    "wall_type": {
                                        "type": "string",
                                        "description": "Wall type name (optional)"
                                    }
                                },
                                "required": ["start_point", "end_point", "level_name"]
                            }
                        }
                    },
                    "required": ["walls"]
                }
            }
        }
    ]


# --- UTILITY: Estimate token count ---
def estimate_schema_tokens(schemas):
    """Estimate token count for schemas (rough: 4 chars per token)"""
    import json
    total_chars = len(json.dumps(schemas))
    estimated_tokens = total_chars // 4
    return estimated_tokens


def print_schema_stats(schemas):
    """Print statistics about schema sizes"""
    import json
    
    print(f"\n📊 Schema Statistics:")
    print(f"   Total tools: {len(schemas)}")
    
    total_chars = 0
    longest_tool = ("", 0)
    
    for schema in schemas:
        func = schema.get("function", schema)
        name = func.get("name", "unknown")
        chars = len(json.dumps(schema))
        total_chars += chars
        
        if chars > longest_tool[1]:
            longest_tool = (name, chars)
    
    print(f"   Total chars: {total_chars:,}")
    print(f"   Est. tokens: {total_chars // 4:,}")
    print(f"   Avg per tool: {total_chars // len(schemas):,} chars ({total_chars // len(schemas) // 4} tokens)")
    print(f"   Longest tool: {longest_tool[0]} ({longest_tool[1]} chars, ~{longest_tool[1]//4} tokens)")