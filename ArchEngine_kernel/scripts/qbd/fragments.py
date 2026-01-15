"""Fragment types and parser for QBD Algebra.

Fragments are atomic actions that modify state.
The LLM emits fragments; the system validates and applies them.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import uuid


class FragmentAction(Enum):
    """All possible fragment actions."""
    # Room operations
    ADD_ROOM = "add_room"
    REMOVE_ROOM = "remove_room"
    UPDATE_ROOM = "update_room"

    # Furniture operations
    ADD_FURNITURE = "add_furniture"
    REMOVE_FURNITURE = "remove_furniture"

    # Relationship operations
    SET_ADJACENCY = "set_adjacency"
    REMOVE_ADJACENCY = "remove_adjacency"
    SET_SEPARATION = "set_separation"
    REMOVE_SEPARATION = "remove_separation"

    # Site operations
    SET_SITE = "set_site"
    ADD_SITE_FEATURE = "add_site_feature"
    REMOVE_SITE_FEATURE = "remove_site_feature"
    ADD_VIEW = "add_view"

    # Constraint operations
    SET_CONSTRAINT = "set_constraint"
    SET_PRIORITY = "set_priority"

    # Character operations
    SET_STYLE = "set_style"

    # Control operations
    PIN_ROOM = "pin_room"
    UNPIN_ROOM = "unpin_room"
    PIN_ELEMENT = "pin_element"
    UNPIN_ELEMENT = "unpin_element"

    # -------------------------------------------------------------------------
    # REALITY LAYER OPERATIONS
    # -------------------------------------------------------------------------

    # Environment (Physics) operations
    SET_WINDOW_AREA = "set_window_area"  # Specify window glazing area
    SET_ORIENTATION = "set_orientation"  # Room/window orientation
    SET_INSULATION = "set_insulation"  # Insulation level
    SET_THERMAL_MASS = "set_thermal_mass"  # Thermal mass properties
    SET_FINISHES = "set_finishes"  # Interior finish materials

    # Materiality (Economics) operations
    SET_CONSTRUCTION_SYSTEM = "set_construction_system"  # Primary structure type
    SET_QUALITY_LEVEL = "set_quality_level"  # Basic/Standard/Premium/Custom
    SET_MATERIAL = "set_material"  # Specify material for element
    SET_BUDGET = "set_budget"  # Budget constraints

    # Perception (Psychology) operations
    SET_PRIVACY_LEVEL = "set_privacy_level"  # Public/Social/Private/Intimate
    SET_AFFECT_QUALITY = "set_affect_quality"  # Desired emotional quality
    ADD_BIOPHILIC_ELEMENT = "add_biophilic_element"  # Plants, natural materials
    SET_SPATIAL_SEQUENCE = "set_spatial_sequence"  # Entrance sequence control


@dataclass
class Fragment:
    """A single atomic action."""
    id: str
    action: FragmentAction
    data: Dict[str, Any]
    timestamp: Optional[float] = None

    @classmethod
    def create(cls, action: Union[str, FragmentAction], data: Dict[str, Any]) -> "Fragment":
        """Create a new fragment."""
        if isinstance(action, str):
            action = FragmentAction(action)
        return cls(
            id=f"frag-{uuid.uuid4().hex[:8]}",
            action=action,
            data=data
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action.value,
            **self.data
        }


# =============================================================================
# Fragment Validation Schemas
# =============================================================================

FRAGMENT_SCHEMAS: Dict[FragmentAction, Dict[str, Any]] = {
    FragmentAction.ADD_ROOM: {
        "required": ["room"],
        "room_fields": ["name", "type"],
    },
    FragmentAction.REMOVE_ROOM: {
        "required": ["room_id"],
    },
    FragmentAction.UPDATE_ROOM: {
        "required": ["room_id", "updates"],
    },
    FragmentAction.ADD_FURNITURE: {
        "required": ["room_id", "furniture"],
        "furniture_fields": ["type"],
    },
    FragmentAction.REMOVE_FURNITURE: {
        "required": ["room_id", "furniture_index"],
    },
    FragmentAction.SET_ADJACENCY: {
        "required": ["room_a", "room_b"],
        "optional": ["strength", "connection_type"],
    },
    FragmentAction.REMOVE_ADJACENCY: {
        "required": ["room_a", "room_b"],
    },
    FragmentAction.SET_SEPARATION: {
        "required": ["room_a", "room_b"],
        "optional": ["strength", "buffer"],
    },
    FragmentAction.REMOVE_SEPARATION: {
        "required": ["room_a", "room_b"],
    },
    FragmentAction.SET_SITE: {
        "required": ["updates"],
    },
    FragmentAction.ADD_SITE_FEATURE: {
        "required": ["feature"],
        "feature_fields": ["type"],
    },
    FragmentAction.ADD_VIEW: {
        "required": ["view"],
        "view_fields": ["direction"],
    },
    FragmentAction.SET_CONSTRAINT: {
        "required": ["target", "value"],
    },
    FragmentAction.SET_PRIORITY: {
        "required": ["factor", "value"],
    },
    FragmentAction.SET_STYLE: {
        "required": ["style"],
        "optional": ["keywords", "avoid"],
    },
    FragmentAction.PIN_ROOM: {
        "required": ["room_id"],
        "optional": ["locked_properties"],
    },
    FragmentAction.UNPIN_ROOM: {
        "required": ["room_id"],
    },

    # -------------------------------------------------------------------------
    # REALITY LAYER SCHEMAS
    # -------------------------------------------------------------------------

    # Environment (Physics)
    FragmentAction.SET_WINDOW_AREA: {
        "required": ["room_id", "area"],
    },
    FragmentAction.SET_ORIENTATION: {
        "required": ["room_id", "orientation"],
    },
    FragmentAction.SET_INSULATION: {
        "required": ["room_id", "level"],  # "code_minimum", "improved", "passive_house"
    },
    FragmentAction.SET_THERMAL_MASS: {
        "required": ["room_id", "mass"],  # "light", "medium", "heavy"
    },
    FragmentAction.SET_FINISHES: {
        "required": ["room_id", "finishes"],  # {"floor": "...", "walls": "...", "ceiling": "..."}
    },

    # Materiality (Economics)
    FragmentAction.SET_CONSTRUCTION_SYSTEM: {
        "required": ["system"],  # ConstructionSystem enum value
    },
    FragmentAction.SET_QUALITY_LEVEL: {
        "required": ["level"],  # QualityLevel enum value
    },
    FragmentAction.SET_MATERIAL: {
        "required": ["element", "material_id"],
    },
    FragmentAction.SET_BUDGET: {
        "required": ["category", "amount"],
    },

    # Perception (Psychology)
    FragmentAction.SET_PRIVACY_LEVEL: {
        "required": ["room_id", "level"],  # PrivacyLevel enum value
    },
    FragmentAction.SET_AFFECT_QUALITY: {
        "required": ["room_id", "quality"],  # AffectQuality enum value
    },
    FragmentAction.ADD_BIOPHILIC_ELEMENT: {
        "required": ["room_id", "element_type"],
    },
    FragmentAction.SET_SPATIAL_SEQUENCE: {
        "required": ["sequence"],  # List of room IDs in order
    },
}


# =============================================================================
# Fragment Parser
# =============================================================================

class FragmentParser:
    """Parse and validate fragments from LLM output."""

    @staticmethod
    def parse(data: Dict[str, Any]) -> Fragment:
        """Parse a dictionary into a Fragment.

        Args:
            data: Dictionary with 'action' key and action-specific data

        Returns:
            Fragment object

        Raises:
            ValueError: If action is invalid or required fields missing
        """
        action_str = data.get("action")
        if not action_str:
            raise ValueError("Fragment missing 'action' field")

        try:
            action = FragmentAction(action_str)
        except ValueError:
            raise ValueError(f"Unknown fragment action: {action_str}")

        # Extract action-specific data
        fragment_data = {k: v for k, v in data.items() if k != "action"}

        return Fragment.create(action, fragment_data)

    @staticmethod
    def validate_structure(fragment: Fragment) -> List[str]:
        """Validate fragment structure against schema.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        schema = FRAGMENT_SCHEMAS.get(fragment.action)

        if not schema:
            return [f"No schema defined for action: {fragment.action.value}"]

        # Check required fields
        for field in schema.get("required", []):
            if field not in fragment.data:
                errors.append(f"Missing required field: {field}")

        # Check nested required fields
        if "room_fields" in schema and "room" in fragment.data:
            room = fragment.data["room"]
            for field in schema["room_fields"]:
                if field not in room:
                    errors.append(f"Room missing required field: {field}")

        if "furniture_fields" in schema and "furniture" in fragment.data:
            furniture = fragment.data["furniture"]
            for field in schema["furniture_fields"]:
                if field not in furniture:
                    errors.append(f"Furniture missing required field: {field}")

        return errors

    @staticmethod
    def parse_batch(fragments_data: List[Dict[str, Any]]) -> List[Fragment]:
        """Parse multiple fragments."""
        return [FragmentParser.parse(f) for f in fragments_data]


# =============================================================================
# Fragment Factories
# =============================================================================

def add_room(name: str, room_type: str, **kwargs) -> Fragment:
    """Create an add_room fragment."""
    room_data = {"name": name, "type": room_type}
    room_data.update(kwargs)
    return Fragment.create(FragmentAction.ADD_ROOM, {"room": room_data})


def remove_room(room_id: str) -> Fragment:
    """Create a remove_room fragment."""
    return Fragment.create(FragmentAction.REMOVE_ROOM, {"room_id": room_id})


def update_room(room_id: str, updates: Dict[str, Any]) -> Fragment:
    """Create an update_room fragment."""
    return Fragment.create(FragmentAction.UPDATE_ROOM, {
        "room_id": room_id,
        "updates": updates
    })


def add_furniture(room_id: str, furniture_type: str, **kwargs) -> Fragment:
    """Create an add_furniture fragment."""
    furniture_data = {"type": furniture_type}
    furniture_data.update(kwargs)
    return Fragment.create(FragmentAction.ADD_FURNITURE, {
        "room_id": room_id,
        "furniture": furniture_data
    })


def set_adjacency(
    room_a: str,
    room_b: str,
    strength: str = "required",
    connection_type: str = "door"
) -> Fragment:
    """Create a set_adjacency fragment."""
    return Fragment.create(FragmentAction.SET_ADJACENCY, {
        "room_a": room_a,
        "room_b": room_b,
        "strength": strength,
        "connection_type": connection_type
    })


def remove_adjacency(room_a: str, room_b: str) -> Fragment:
    """Create a remove_adjacency fragment."""
    return Fragment.create(FragmentAction.REMOVE_ADJACENCY, {
        "room_a": room_a,
        "room_b": room_b
    })


def set_separation(
    room_a: str,
    room_b: str,
    strength: str = "required",
    buffer: int = None
) -> Fragment:
    """Create a set_separation fragment."""
    data = {"room_a": room_a, "room_b": room_b, "strength": strength}
    if buffer is not None:
        data["buffer"] = buffer
    return Fragment.create(FragmentAction.SET_SEPARATION, data)


def set_site(updates: Dict[str, Any]) -> Fragment:
    """Create a set_site fragment."""
    return Fragment.create(FragmentAction.SET_SITE, {"updates": updates})


def set_constraint(target: str, value: Any) -> Fragment:
    """Create a set_constraint fragment."""
    return Fragment.create(FragmentAction.SET_CONSTRAINT, {
        "target": target,
        "value": value
    })


def set_priority(factor: str, value: int) -> Fragment:
    """Create a set_priority fragment."""
    return Fragment.create(FragmentAction.SET_PRIORITY, {
        "factor": factor,
        "value": value
    })


def set_style(style: str, keywords: List[str] = None, avoid: List[str] = None) -> Fragment:
    """Create a set_style fragment."""
    data = {"style": style}
    if keywords:
        data["keywords"] = keywords
    if avoid:
        data["avoid"] = avoid
    return Fragment.create(FragmentAction.SET_STYLE, data)


def pin_room(room_id: str, locked_properties: List[str] = None) -> Fragment:
    """Create a pin_room fragment."""
    data = {"room_id": room_id}
    if locked_properties:
        data["locked_properties"] = locked_properties
    return Fragment.create(FragmentAction.PIN_ROOM, data)


def unpin_room(room_id: str) -> Fragment:
    """Create an unpin_room fragment."""
    return Fragment.create(FragmentAction.UNPIN_ROOM, {"room_id": room_id})


# =============================================================================
# Reality Layer Fragment Factories
# =============================================================================

# Environment (Physics)

def set_window_area(room_id: str, area: float) -> Fragment:
    """Create a set_window_area fragment.

    Args:
        room_id: Room identifier
        area: Window glazing area in square meters
    """
    return Fragment.create(FragmentAction.SET_WINDOW_AREA, {
        "room_id": room_id,
        "area": area
    })


def set_orientation(room_id: str, orientation: str) -> Fragment:
    """Create a set_orientation fragment.

    Args:
        room_id: Room identifier
        orientation: Cardinal direction ("N", "S", "E", "W", "NE", etc.)
    """
    return Fragment.create(FragmentAction.SET_ORIENTATION, {
        "room_id": room_id,
        "orientation": orientation
    })


def set_insulation(room_id: str, level: str) -> Fragment:
    """Create a set_insulation fragment.

    Args:
        room_id: Room identifier
        level: Insulation level ("code_minimum", "improved", "passive_house")
    """
    return Fragment.create(FragmentAction.SET_INSULATION, {
        "room_id": room_id,
        "level": level
    })


def set_thermal_mass(room_id: str, mass: str) -> Fragment:
    """Create a set_thermal_mass fragment.

    Args:
        room_id: Room identifier
        mass: Thermal mass ("light", "medium", "heavy")
    """
    return Fragment.create(FragmentAction.SET_THERMAL_MASS, {
        "room_id": room_id,
        "mass": mass
    })


def set_finishes(room_id: str, finishes: Dict[str, str]) -> Fragment:
    """Create a set_finishes fragment.

    Args:
        room_id: Room identifier
        finishes: Dict with "floor", "walls", "ceiling" keys
    """
    return Fragment.create(FragmentAction.SET_FINISHES, {
        "room_id": room_id,
        "finishes": finishes
    })


# Materiality (Economics)

def set_construction_system(system: str) -> Fragment:
    """Create a set_construction_system fragment.

    Args:
        system: Construction system type ("wood_light_frame", "concrete_cmu", etc.)
    """
    return Fragment.create(FragmentAction.SET_CONSTRUCTION_SYSTEM, {
        "system": system
    })


def set_quality_level(level: str) -> Fragment:
    """Create a set_quality_level fragment.

    Args:
        level: Quality level ("basic", "standard", "premium", "custom")
    """
    return Fragment.create(FragmentAction.SET_QUALITY_LEVEL, {
        "level": level
    })


def set_material(element: str, material_id: str) -> Fragment:
    """Create a set_material fragment.

    Args:
        element: Building element (e.g., "exterior_walls", "roof", "flooring")
        material_id: Material identifier from MaterialLibrary
    """
    return Fragment.create(FragmentAction.SET_MATERIAL, {
        "element": element,
        "material_id": material_id
    })


def set_budget(category: str, amount: float) -> Fragment:
    """Create a set_budget fragment.

    Args:
        category: Budget category ("total", "construction", "interior", etc.)
        amount: Budget amount in USD
    """
    return Fragment.create(FragmentAction.SET_BUDGET, {
        "category": category,
        "amount": amount
    })


# Perception (Psychology)

def set_privacy_level(room_id: str, level: str) -> Fragment:
    """Create a set_privacy_level fragment.

    Args:
        room_id: Room identifier
        level: Privacy level ("public", "social", "semi_private", "private", "intimate")
    """
    return Fragment.create(FragmentAction.SET_PRIVACY_LEVEL, {
        "room_id": room_id,
        "level": level
    })


def set_affect_quality(room_id: str, quality: str) -> Fragment:
    """Create a set_affect_quality fragment.

    Args:
        room_id: Room identifier
        quality: Affect quality ("shelter", "expansion", "intimacy", "awe", "delight", "calm", "focus")
    """
    return Fragment.create(FragmentAction.SET_AFFECT_QUALITY, {
        "room_id": room_id,
        "quality": quality
    })


def add_biophilic_element(room_id: str, element_type: str) -> Fragment:
    """Create an add_biophilic_element fragment.

    Args:
        room_id: Room identifier
        element_type: Biophilic element ("plants", "natural_light", "views", "natural_materials", "water")
    """
    return Fragment.create(FragmentAction.ADD_BIOPHILIC_ELEMENT, {
        "room_id": room_id,
        "element_type": element_type
    })


def set_spatial_sequence(sequence: List[str]) -> Fragment:
    """Create a set_spatial_sequence fragment.

    Args:
        sequence: Ordered list of room IDs representing entrance sequence
    """
    return Fragment.create(FragmentAction.SET_SPATIAL_SEQUENCE, {
        "sequence": sequence
    })
