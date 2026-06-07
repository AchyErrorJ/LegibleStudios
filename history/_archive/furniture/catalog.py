"""
Furniture catalog management.

Provides storage and retrieval of furniture definitions,
including built-in items and user-defined custom furniture.
"""
import json
import os
from typing import Dict, List, Optional, Iterator
from pathlib import Path

from furniture.models import (
    FurnitureItem,
    FurnitureCategory,
    FurnitureStyle,
    Dimensions,
    Material,
    Materials,
)


class FurnitureCatalog:
    """
    Manages a collection of furniture items.

    Supports:
    - Built-in default furniture
    - Loading from JSON files
    - Saving custom furniture
    - Filtering by category, style, tags
    """

    def __init__(self):
        self._items: Dict[str, FurnitureItem] = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load built-in default furniture items."""
        defaults = self._create_default_items()
        for item in defaults:
            self._items[item.id] = item

    def _create_default_items(self) -> List[FurnitureItem]:
        """Create the default furniture catalog."""
        return [
            # ===== SEATING =====
            FurnitureItem(
                id="chair_dining_modern",
                name="Modern Dining Chair",
                category=FurnitureCategory.SEATING,
                furniture_type="dining_chair",
                dimensions=Dimensions(
                    width=450,
                    depth=500,
                    height=850,
                    seat_height=450,
                    back_height=400,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                secondary_material=Materials.FABRIC_GRAY,
                tags=["dining", "chair", "modern"],
                clearance_front=600,
                clearance_back=100,
            ),
            FurnitureItem(
                id="chair_office_ergonomic",
                name="Ergonomic Office Chair",
                category=FurnitureCategory.OFFICE,
                furniture_type="office_chair",
                dimensions=Dimensions(
                    width=650,
                    depth=650,
                    height=1100,
                    seat_height=450,
                    arm_height=200,
                    back_height=550,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.BLACK_METAL,
                secondary_material=Materials.FABRIC_GRAY,
                tags=["office", "ergonomic", "adjustable"],
                clearance_front=700,
                clearance_back=200,
                clearance_left=100,
                clearance_right=100,
            ),
            FurnitureItem(
                id="sofa_3seat_modern",
                name="3-Seater Sofa",
                category=FurnitureCategory.SEATING,
                furniture_type="sofa_3seat",
                dimensions=Dimensions(
                    width=2100,
                    depth=900,
                    height=850,
                    seat_height=450,
                    arm_height=200,
                    back_height=350,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.FABRIC_GRAY,
                secondary_material=Materials.OAK,
                tags=["living", "sofa", "3-seater"],
                clearance_front=800,
            ),
            FurnitureItem(
                id="sofa_2seat_modern",
                name="2-Seater Loveseat",
                category=FurnitureCategory.SEATING,
                furniture_type="sofa_2seat",
                dimensions=Dimensions(
                    width=1500,
                    depth=900,
                    height=850,
                    seat_height=450,
                    arm_height=200,
                    back_height=350,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.FABRIC_BEIGE,
                tags=["living", "sofa", "loveseat"],
                clearance_front=800,
            ),
            FurnitureItem(
                id="armchair_modern",
                name="Modern Armchair",
                category=FurnitureCategory.SEATING,
                furniture_type="armchair",
                dimensions=Dimensions(
                    width=800,
                    depth=850,
                    height=900,
                    seat_height=450,
                    arm_height=200,
                    back_height=400,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.LEATHER_BROWN,
                tags=["living", "armchair"],
                clearance_front=600,
            ),

            # ===== TABLES =====
            FurnitureItem(
                id="table_dining_6seat",
                name="6-Person Dining Table",
                category=FurnitureCategory.TABLES,
                furniture_type="dining_table",
                dimensions=Dimensions(
                    width=1800,
                    depth=900,
                    height=750,
                    table_top_thickness=40,
                    leg_width=80,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                tags=["dining", "table", "6-person"],
                clearance_front=800,
                clearance_back=800,
                clearance_left=600,
                clearance_right=600,
            ),
            FurnitureItem(
                id="table_dining_4seat",
                name="4-Person Dining Table",
                category=FurnitureCategory.TABLES,
                furniture_type="dining_table",
                dimensions=Dimensions(
                    width=1200,
                    depth=800,
                    height=750,
                    table_top_thickness=35,
                    leg_width=70,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.WALNUT,
                tags=["dining", "table", "4-person"],
                clearance_front=700,
                clearance_back=700,
                clearance_left=600,
                clearance_right=600,
            ),
            FurnitureItem(
                id="table_coffee_rect",
                name="Rectangular Coffee Table",
                category=FurnitureCategory.TABLES,
                furniture_type="coffee_table",
                dimensions=Dimensions(
                    width=1200,
                    depth=600,
                    height=450,
                    table_top_thickness=25,
                    leg_width=50,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                secondary_material=Materials.BLACK_METAL,
                tags=["living", "coffee", "table"],
                clearance_front=400,
                clearance_back=400,
            ),
            FurnitureItem(
                id="table_side_round",
                name="Round Side Table",
                category=FurnitureCategory.TABLES,
                furniture_type="side_table",
                dimensions=Dimensions(
                    width=500,
                    depth=500,
                    height=550,
                    table_top_thickness=20,
                    leg_width=40,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.WALNUT,
                tags=["side", "table", "round"],
            ),
            FurnitureItem(
                id="desk_office",
                name="Office Desk",
                category=FurnitureCategory.OFFICE,
                furniture_type="desk",
                dimensions=Dimensions(
                    width=1600,
                    depth=800,
                    height=750,
                    table_top_thickness=30,
                    leg_width=60,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                secondary_material=Materials.BRUSHED_STEEL,
                tags=["office", "desk", "work"],
                clearance_front=700,
                clearance_back=100,
            ),

            # ===== BEDS =====
            FurnitureItem(
                id="bed_queen",
                name="Queen Size Bed",
                category=FurnitureCategory.BEDS,
                furniture_type="bed_queen",
                dimensions=Dimensions(
                    width=1600,
                    depth=2100,
                    height=500,
                    back_height=1100,  # Headboard height
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                secondary_material=Materials.FABRIC_GRAY,
                tags=["bedroom", "bed", "queen"],
                clearance_front=600,
                clearance_left=600,
                clearance_right=600,
            ),
            FurnitureItem(
                id="bed_king",
                name="King Size Bed",
                category=FurnitureCategory.BEDS,
                furniture_type="bed_king",
                dimensions=Dimensions(
                    width=1930,
                    depth=2100,
                    height=500,
                    back_height=1100,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.WALNUT,
                secondary_material=Materials.FABRIC_BEIGE,
                tags=["bedroom", "bed", "king"],
                clearance_front=600,
                clearance_left=600,
                clearance_right=600,
            ),
            FurnitureItem(
                id="bed_single",
                name="Single Bed",
                category=FurnitureCategory.BEDS,
                furniture_type="bed_single",
                dimensions=Dimensions(
                    width=1000,
                    depth=2000,
                    height=450,
                    back_height=900,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.PINE,
                tags=["bedroom", "bed", "single"],
                clearance_front=500,
                clearance_left=400,
                clearance_right=400,
            ),

            # ===== STORAGE =====
            FurnitureItem(
                id="wardrobe_double",
                name="Double Door Wardrobe",
                category=FurnitureCategory.STORAGE,
                furniture_type="wardrobe",
                dimensions=Dimensions(
                    width=1200,
                    depth=600,
                    height=2000,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                tags=["bedroom", "storage", "wardrobe"],
                clearance_front=700,
            ),
            FurnitureItem(
                id="bookshelf_tall",
                name="Tall Bookshelf",
                category=FurnitureCategory.STORAGE,
                furniture_type="bookshelf",
                dimensions=Dimensions(
                    width=800,
                    depth=350,
                    height=1800,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                tags=["storage", "bookshelf", "shelving"],
                clearance_front=600,
            ),
            FurnitureItem(
                id="dresser_6drawer",
                name="6-Drawer Dresser",
                category=FurnitureCategory.STORAGE,
                furniture_type="dresser",
                dimensions=Dimensions(
                    width=1400,
                    depth=500,
                    height=800,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.WALNUT,
                tags=["bedroom", "storage", "dresser"],
                clearance_front=700,
            ),
            FurnitureItem(
                id="nightstand",
                name="Nightstand",
                category=FurnitureCategory.STORAGE,
                furniture_type="nightstand",
                dimensions=Dimensions(
                    width=500,
                    depth=450,
                    height=550,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.OAK,
                tags=["bedroom", "nightstand", "storage"],
            ),

            # ===== FIXTURES =====
            FurnitureItem(
                id="toilet_standard",
                name="Standard Toilet",
                category=FurnitureCategory.FIXTURES,
                furniture_type="toilet",
                dimensions=Dimensions(
                    width=400,
                    depth=700,
                    height=400,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.PLASTIC_WHITE,
                tags=["bathroom", "toilet", "fixture"],
                clearance_front=600,
                clearance_left=200,
                clearance_right=200,
            ),
            FurnitureItem(
                id="sink_pedestal",
                name="Pedestal Sink",
                category=FurnitureCategory.FIXTURES,
                furniture_type="sink",
                dimensions=Dimensions(
                    width=550,
                    depth=450,
                    height=850,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.PLASTIC_WHITE,
                tags=["bathroom", "sink", "fixture"],
                clearance_front=600,
            ),
            FurnitureItem(
                id="bathtub_standard",
                name="Standard Bathtub",
                category=FurnitureCategory.FIXTURES,
                furniture_type="bathtub",
                dimensions=Dimensions(
                    width=700,
                    depth=1700,
                    height=550,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.PLASTIC_WHITE,
                tags=["bathroom", "bathtub", "fixture"],
                clearance_front=700,
            ),
            FurnitureItem(
                id="shower_square",
                name="Square Shower Enclosure",
                category=FurnitureCategory.FIXTURES,
                furniture_type="shower",
                dimensions=Dimensions(
                    width=900,
                    depth=900,
                    height=2000,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.GLASS,
                tags=["bathroom", "shower", "fixture"],
            ),

            # ===== APPLIANCES =====
            FurnitureItem(
                id="refrigerator_standard",
                name="Standard Refrigerator",
                category=FurnitureCategory.APPLIANCES,
                furniture_type="refrigerator",
                dimensions=Dimensions(
                    width=900,
                    depth=700,
                    height=1800,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.BRUSHED_STEEL,
                tags=["kitchen", "appliance", "refrigerator"],
                clearance_front=800,
            ),
            FurnitureItem(
                id="stove_4burner",
                name="4-Burner Stove",
                category=FurnitureCategory.APPLIANCES,
                furniture_type="stove",
                dimensions=Dimensions(
                    width=600,
                    depth=600,
                    height=900,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.BRUSHED_STEEL,
                tags=["kitchen", "appliance", "stove"],
                clearance_front=900,
            ),
            FurnitureItem(
                id="dishwasher",
                name="Dishwasher",
                category=FurnitureCategory.APPLIANCES,
                furniture_type="dishwasher",
                dimensions=Dimensions(
                    width=600,
                    depth=600,
                    height=850,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.BRUSHED_STEEL,
                tags=["kitchen", "appliance", "dishwasher"],
                clearance_front=700,
            ),
            FurnitureItem(
                id="washing_machine",
                name="Washing Machine",
                category=FurnitureCategory.APPLIANCES,
                furniture_type="washing_machine",
                dimensions=Dimensions(
                    width=600,
                    depth=600,
                    height=850,
                ),
                style=FurnitureStyle.MODERN,
                primary_material=Materials.PLASTIC_WHITE,
                tags=["laundry", "appliance", "washer"],
                clearance_front=700,
            ),
        ]

    def get(self, item_id: str) -> Optional[FurnitureItem]:
        """Get a furniture item by ID."""
        return self._items.get(item_id)

    def get_all(self) -> List[FurnitureItem]:
        """Get all furniture items."""
        return list(self._items.values())

    def add(self, item: FurnitureItem) -> None:
        """Add a furniture item to the catalog."""
        self._items[item.id] = item

    def remove(self, item_id: str) -> bool:
        """Remove a furniture item by ID. Returns True if removed."""
        if item_id in self._items:
            del self._items[item_id]
            return True
        return False

    def filter_by_category(self, category: FurnitureCategory) -> List[FurnitureItem]:
        """Get all items in a category."""
        return [item for item in self._items.values() if item.category == category]

    def filter_by_style(self, style: FurnitureStyle) -> List[FurnitureItem]:
        """Get all items matching a style."""
        return [item for item in self._items.values() if item.style == style]

    def filter_by_tag(self, tag: str) -> List[FurnitureItem]:
        """Get all items with a specific tag."""
        tag_lower = tag.lower()
        return [item for item in self._items.values() if tag_lower in [t.lower() for t in item.tags]]

    def search(self, query: str) -> List[FurnitureItem]:
        """Search items by name, type, or tags."""
        query_lower = query.lower()
        results = []
        for item in self._items.values():
            if (query_lower in item.name.lower() or
                query_lower in item.furniture_type.lower() or
                any(query_lower in tag.lower() for tag in item.tags)):
                results.append(item)
        return results

    def __iter__(self) -> Iterator[FurnitureItem]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, item_id: str) -> bool:
        return item_id in self._items

    # ===== File I/O =====

    def save_to_json(self, filepath: str) -> None:
        """Save catalog to a JSON file."""
        data = {
            "version": "1.0",
            "items": [item.to_dict() for item in self._items.values()]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load_from_json(self, filepath: str, merge: bool = True) -> None:
        """
        Load catalog from a JSON file.

        Args:
            filepath: Path to JSON file
            merge: If True, add to existing items. If False, replace all.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not merge:
            self._items.clear()

        for item_data in data.get("items", []):
            item = FurnitureItem.from_dict(item_data)
            self._items[item.id] = item

    def export_category(self, category: FurnitureCategory, filepath: str) -> None:
        """Export a single category to JSON."""
        items = self.filter_by_category(category)
        data = {
            "version": "1.0",
            "category": category.value,
            "items": [item.to_dict() for item in items]
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)


# Singleton instance
_default_catalog: Optional[FurnitureCatalog] = None


def get_default_catalog() -> FurnitureCatalog:
    """Get the default furniture catalog singleton."""
    global _default_catalog
    if _default_catalog is None:
        _default_catalog = FurnitureCatalog()
    return _default_catalog
