"""LLM abstraction layer for building schema generation and modification.

This module provides a unified interface to multiple LLM backends (LM Studio,
OpenAI, Claude, Gemini) for generating and modifying building schemas from
natural language descriptions.

Quick Start:
    from llm import LLMConfig, generate_building, modify_building

    # Check available providers
    print(LLMConfig.get_available())

    # Use LM Studio (local)
    LLMConfig.set_active("lmstudio")

    # Generate a building
    schema = generate_building("3 bedroom 2 bath ranch house 1800 sqft")

    # Modify with constraints
    modified = modify_building(
        schema,
        "Make the kitchen larger",
        pinned_elements={"rooms": ["room_living"]}
    )
"""

from .provider import LLMProvider, Message, LLMResponse
from .config import LLMConfig
from .schema_generator import SchemaGenerator
from .schema_modifier import SchemaModifier
from .action_parser import TemplateModifier, ActionParser, ActionApplier

# Initialize defaults on import
LLMConfig.register_defaults()

__all__ = [
    # Core classes
    "LLMProvider",
    "Message",
    "LLMResponse",
    "LLMConfig",
    "SchemaGenerator",
    "SchemaModifier",
    "TemplateModifier",  # Fast template-based modifier
    "ActionParser",
    "ActionApplier",
    # Helper functions
    "generate_building",
    "modify_building",
    "get_status",
]


def generate_building(description: str, **kwargs) -> dict:
    """Quick helper to generate a building from text.

    Args:
        description: Natural language description of the building
            e.g. "3 bedroom 2 bath ranch house 1800 sqft"
        **kwargs: Additional options passed to SchemaGenerator.generate()
            - temperature: Sampling temperature (default: 0.7)
            - max_tokens: Maximum tokens (default: 8000)

    Returns:
        Dict containing the building schema with walls, doors, windows, rooms

    Raises:
        RuntimeError: If no LLM provider is available
        json.JSONDecodeError: If LLM response is not valid JSON

    Example:
        >>> schema = generate_building("small 2 bedroom cabin")
        >>> print(f"Walls: {len(schema['walls_batch'])}")
    """
    generator = SchemaGenerator()
    return generator.generate(description, **kwargs)


def modify_building(
    schema: dict,
    request: str,
    pinned_elements: dict = None,
    **kwargs
) -> dict:
    """Quick helper to modify a building schema.

    Args:
        schema: Current building schema
        request: Natural language modification request
            e.g. "Make the kitchen larger"
        pinned_elements: Dict of element types to pinned IDs that should not change
            e.g. {"rooms": ["room_living"], "walls": ["0", "1"]}
        **kwargs: Additional options passed to SchemaModifier.modify()
            - temperature: Sampling temperature (default: 0.5)
            - max_tokens: Maximum tokens (default: 8000)

    Returns:
        Modified building schema

    Raises:
        RuntimeError: If no LLM provider is available
        json.JSONDecodeError: If LLM response is not valid JSON

    Example:
        >>> modified = modify_building(schema, "Add a garage", pinned_elements={"rooms": ["room_living"]})
    """
    modifier = SchemaModifier()
    return modifier.modify(schema, request, pinned_elements, **kwargs)


def get_status() -> dict:
    """Get status of all LLM providers.

    Returns:
        Dict with provider status information including:
        - active: Name of the currently active provider
        - providers: Dict of provider name to status info

    Example:
        >>> status = get_status()
        >>> for name, info in status['providers'].items():
        ...     print(f"{name}: {'available' if info['available'] else 'unavailable'}")
    """
    return LLMConfig.status()
