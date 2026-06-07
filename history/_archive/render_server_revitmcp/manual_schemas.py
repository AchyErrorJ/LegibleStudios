# manual_schemas.py
# Hand-crafted schemas for complex tools that need precise input formats
# These override auto-generated schemas for better LLM understanding

MANUAL_SCHEMAS = {
    # ==================== WALLS ====================
    "create_wall": {
        "type": "function",
        "function": {
            "name": "create_wall",
            "description": "Create a single wall between two points.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_point": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] in feet"},
                    "end_point": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] in feet"},
                    "level_name": {"type": "string", "description": "e.g. 'Level 0'"},
                    "height": {"type": "number"},
                    "wall_type": {"type": "string"}
                },
                "required": ["start_point", "end_point", "level_name"]
            }
        }
    },
    
    "create_walls_batch": {
        "type": "function",
        "function": {
            "name": "create_walls_batch",
            "description": "Create multiple walls. walls must be array of OBJECTS, not flat array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "walls": {
                        "type": "array",
                        "items": {
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
                "required": ["walls"]
            }
        }
    },

    # ==================== GRIDS ====================
    "create_grids_batch": {
        "type": "function",
        "function": {
            "name": "create_grids_batch",
            "description": "Create multiple grids. grids must be array of OBJECTS, not flat array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "grids": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "e.g. '1', 'A'"},
                                "start_point": {"type": "array", "items": {"type": "number"}},
                                "end_point": {"type": "array", "items": {"type": "number"}}
                            },
                            "required": ["name", "start_point", "end_point"]
                        }
                    }
                },
                "required": ["grids"]
            }
        }
    },

    # ==================== FLOORS ====================
    "create_floor": {
        "type": "function",
        "function": {
            "name": "create_floor",
            "description": "Create floor from boundary points. points must be array of [x,y,z] arrays.",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "[[x,y,z], [x,y,z], ...] minimum 3 points"
                    },
                    "level_name": {"type": "string"},
                    "floor_type": {"type": "string"}
                },
                "required": ["points", "level_name"]
            }
        }
    },

    # ==================== ROOFS ====================
    "create_roof_footprint": {
        "type": "function",
        "function": {
            "name": "create_roof_footprint",
            "description": "Create roof from boundary points. points must be array of [x,y,z] arrays.",
            "parameters": {
                "type": "object",
                "properties": {
                    "points": {
                        "type": "array",
                        "items": {"type": "array", "items": {"type": "number"}},
                        "description": "[[x,y,z], [x,y,z], ...] minimum 3 points"
                    },
                    "level_name": {"type": "string"},
                    "slope_degrees": {"type": "number", "description": "0 for flat"},
                    "roof_type": {"type": "string"}
                },
                "required": ["points", "level_name"]
            }
        }
    },

    # ==================== ROOMS ====================
    "create_room": {
        "type": "function",
        "function": {
            "name": "create_room",
            "description": "Create a room at a point inside enclosed walls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "point": {"type": "array", "items": {"type": "number"}, "description": "[x,y,z] inside room"},
                    "level_name": {"type": "string"},
                    "room_name": {"type": "string"},
                    "room_number": {"type": "string"}
                },
                "required": ["point", "level_name"]
            }
        }
    },

    "create_rooms_batch": {
        "type": "function",
        "function": {
            "name": "create_rooms_batch",
            "description": "Create multiple rooms. rooms must be array of OBJECTS, not flat array.",
            "parameters": {
                "type": "object",
                "properties": {
                    "rooms": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "point": {"type": "array", "items": {"type": "number"}},
                                "level_name": {"type": "string"},
                                "room_name": {"type": "string"},
                                "room_number": {"type": "string"}
                            },
                            "required": ["point", "level_name"]
                        }
                    }
                },
                "required": ["rooms"]
            }
        }
    },

    # ==================== DOORS & WINDOWS ====================
    "place_door": {
        "type": "function",
        "function": {
            "name": "place_door",
            "description": "Place a door in a wall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host_id": {"type": "integer", "description": "Wall element ID"},
                    "point": {"type": "array", "items": {"type": "number"}},
                    "door_type": {"type": "string"}
                },
                "required": ["host_id", "point"]
            }
        }
    },

    "place_window": {
        "type": "function",
        "function": {
            "name": "place_window",
            "description": "Place a window in a wall.",
            "parameters": {
                "type": "object",
                "properties": {
                    "host_id": {"type": "integer", "description": "Wall element ID"},
                    "point": {"type": "array", "items": {"type": "number"}},
                    "window_type": {"type": "string"}
                },
                "required": ["host_id", "point"]
            }
        }
    },

    "place_hosted_batch": {
        "type": "function",
        "function": {
            "name": "place_hosted_batch",
            "description": "Place multiple doors/windows. elements must be array of OBJECTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "elements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "host_id": {"type": "integer"},
                                "point": {"type": "array", "items": {"type": "number"}},
                                "category": {"type": "string", "description": "'Door' or 'Window'"},
                                "type_name": {"type": "string"}
                            },
                            "required": ["host_id", "point", "category"]
                        }
                    }
                },
                "required": ["elements"]
            }
        }
    },

    # ==================== TAGS ====================
    "create_tag": {
        "type": "function",
        "function": {
            "name": "create_tag",
            "description": "Create a tag for an element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "view_id": {"type": "integer"},
                    "point": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["element_id", "view_id"]
            }
        }
    },

    "create_tags_batch": {
        "type": "function",
        "function": {
            "name": "create_tags_batch",
            "description": "Create multiple tags. tags must be array of OBJECTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "element_id": {"type": "integer"},
                                "view_id": {"type": "integer"},
                                "point": {"type": "array", "items": {"type": "number"}}
                            },
                            "required": ["element_id", "view_id"]
                        }
                    }
                },
                "required": ["tags"]
            }
        }
    },

    # ==================== TEXT NOTES ====================
    "create_text_note": {
        "type": "function",
        "function": {
            "name": "create_text_note",
            "description": "Create a text note in a view.",
            "parameters": {
                "type": "object",
                "properties": {
                    "view_id": {"type": "integer"},
                    "point": {"type": "array", "items": {"type": "number"}},
                    "text": {"type": "string"}
                },
                "required": ["view_id", "point", "text"]
            }
        }
    },

    "create_text_notes_batch": {
        "type": "function",
        "function": {
            "name": "create_text_notes_batch",
            "description": "Create multiple text notes. notes must be array of OBJECTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "view_id": {"type": "integer"},
                                "point": {"type": "array", "items": {"type": "number"}},
                                "text": {"type": "string"}
                            },
                            "required": ["view_id", "point", "text"]
                        }
                    }
                },
                "required": ["notes"]
            }
        }
    },

    # ==================== SEPARATION LINES ====================
   "create_room_separation_lines": {
    "type": "function",
    "function": {
        "name": "create_room_separation_lines",
        "description": "Create room separation lines. lines must be array of OBJECTS.",
        "parameters": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_point": {"type": "array", "items": {"type": "number"}},
                            "end_point": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["start_point", "end_point"]
                    }
                },
                "level_name": {"type": "string"}
            },
            "required": ["lines", "level_name"]
        }
    }
},

    # ==================== SHEETS ====================
    "create_sheet": {
        "type": "function",
        "function": {
            "name": "create_sheet",
            "description": "Create a drawing sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_number": {"type": "string", "description": "e.g. 'A-100'"},
                    "sheet_name": {"type": "string"},
                    "title_block": {"type": "string"}
                },
                "required": ["sheet_number", "sheet_name"]
            }
        }
    },

    "place_view_on_sheet": {
        "type": "function",
        "function": {
            "name": "place_view_on_sheet",
            "description": "Place a view on a sheet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet_id": {"type": "integer"},
                    "view_id": {"type": "integer"},
                    "point": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["sheet_id", "view_id", "point"]
            }
        }
    },

    "place_views_batch": {
        "type": "function",
        "function": {
            "name": "place_views_batch",
            "description": "Place multiple views on sheets. placements must be array of OBJECTS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "placements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sheet_id": {"type": "integer"},
                                "view_id": {"type": "integer"},
                                "point": {"type": "array", "items": {"type": "number"}}
                            },
                            "required": ["sheet_id", "view_id", "point"]
                        }
                    }
                },
                "required": ["placements"]
            }
        }
    },

    # ==================== LEVELS ====================
    "create_level": {
        "type": "function",
        "function": {
            "name": "create_level",
            "description": "Create a new level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level_name": {"type": "string"},
                    "elevation": {"type": "number", "description": "Height in feet"}
                },
                "required": ["level_name", "elevation"]
            }
        }
    },

    # ==================== DIMENSIONS ====================
    "create_dimension": {
        "type": "function",
        "function": {
            "name": "create_dimension",
            "description": "Create a dimension.",
            "parameters": {
                "type": "object",
                "properties": {
                    "view_id": {"type": "integer"},
                    "element_ids": {"type": "array", "items": {"type": "integer"}},
                    "line_point": {"type": "array", "items": {"type": "number"}}
                },
                "required": ["view_id", "element_ids"]
            }
        }
    },

    # ==================== SCHEDULES ====================
    "create_schedule": {
        "type": "function",
        "function": {
            "name": "create_schedule",
            "description": "Create a schedule.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "category": {"type": "string", "description": "e.g. 'Doors', 'Rooms'"},
                    "fields": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["name", "category"]
            }
        }
    },

    # ==================== PARAMETERS ====================
    "set_parameter": {
        "type": "function",
        "function": {
            "name": "set_parameter",
            "description": "Set a parameter value on an element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer"},
                    "parameter_name": {"type": "string"},
                    "value": {"type": "string"}
                },
                "required": ["element_id", "parameter_name", "value"]
            }
        }
    }
}


def get_manual_schema(tool_name: str):
    """Get manual schema for a tool if it exists."""
    return MANUAL_SCHEMAS.get(tool_name)


def merge_schemas(auto_schemas: list, manual_schemas: dict = MANUAL_SCHEMAS) -> list:
    """Merge auto-generated schemas with manual overrides."""
    merged = []
    manual_names = set(manual_schemas.keys())
    
    for schema in auto_schemas:
        func_name = schema.get("function", {}).get("name", "")
        
        if func_name in manual_names:
            merged.append(manual_schemas[func_name])
            print(f"📋 Using manual schema for: {func_name}")
        else:
            merged.append(schema)
    
    return merged


def estimate_tokens(schemas: list) -> int:
    """Estimate token count for schemas."""
    import json
    return len(json.dumps(schemas)) // 4


def print_schema_comparison(auto_schemas: list, merged_schemas: list):
    """Print comparison of auto vs merged schema sizes."""
    auto_tokens = estimate_tokens(auto_schemas)
    merged_tokens = estimate_tokens(merged_schemas)
    
    print(f"\n📊 Schema Comparison:")
    print(f"   Auto-generated: {auto_tokens:,} tokens")
    print(f"   With manual:    {merged_tokens:,} tokens")
    print(f"   Difference:     {auto_tokens - merged_tokens:,} tokens")