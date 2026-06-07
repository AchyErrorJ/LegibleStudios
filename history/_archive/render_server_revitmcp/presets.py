MATERIAL_PRESETS = {
    "Brick - Red Running Bond": "red brick wall, running bond pattern, mortar joints, weathered",
    "Brick - White Painted": "white painted brick, clean, modern",
    "Brick - Brown Flemish": "brown flemish bond brick, traditional, detailed mortar",
    "Siding - Lap White": "white horizontal lap siding, clean lines, shadow gaps",
    "Siding - Board Batten": "vertical board and batten siding, rustic, wood grain",
    "Stucco - Smooth Gray": "smooth gray stucco, modern, clean finish",
    "Stucco - Santa Fe": "tan adobe stucco, southwestern style, textured",
    "Stone - Limestone": "limestone veneer, natural texture, warm tones",
    "Stone - Field Stone": "natural field stone, irregular shapes, rustic",
}

ROOF_PRESETS = {
    "Asphalt - Charcoal": "charcoal asphalt shingles, dimensional, shadow lines",
    "Asphalt - Brown": "brown asphalt shingles, architectural grade",
    "Metal - Standing Seam": "standing seam metal roof, clean lines, modern",
    "Metal - Corrugated": "corrugated metal roofing, industrial",
    "Tile - Clay": "clay roof tiles, terracotta, spanish style",
    "Tile - Concrete": "concrete roof tiles, flat profile",
    "Slate - Gray": "gray slate roof, natural stone, traditional",
}

STYLE_PRESETS = {
    "Clean Studio": {
        "suffix": "studio lighting, white background, product shot, clean render",
        "negative": "landscape, trees, sky, outdoor environment, cluttered",
        "strength": 0.35,
        "guidance": 8.0
    },
    "Sunny Day": {
        "suffix": "bright sunny day, blue sky, green lawn, suburban setting",
        "negative": "overcast, dark, gloomy, night",
        "strength": 0.4,
        "guidance": 7.5
    },
    "Golden Hour": {
        "suffix": "golden hour lighting, warm tones, long shadows, dramatic sky",
        "negative": "midday, harsh shadows, overcast",
        "strength": 0.45,
        "guidance": 8.0
    },
    "Overcast Soft": {
        "suffix": "overcast sky, soft diffused lighting, no harsh shadows",
        "negative": "sunny, harsh shadows, dramatic",
        "strength": 0.35,
        "guidance": 7.0
    },
    "Evening Dusk": {
        "suffix": "dusk lighting, warm interior glow from windows, purple sky",
        "negative": "daylight, bright, midday",
        "strength": 0.5,
        "guidance": 8.5
    },
    "Sketch Style": {
        "suffix": "architectural sketch, pencil drawing, clean lines, presentation drawing",
        "negative": "photorealistic, photograph, detailed textures",
        "strength": 0.6,
        "guidance": 9.0
    },
    "Watercolor": {
        "suffix": "watercolor painting, soft washes, artistic, architectural illustration",
        "negative": "photorealistic, sharp, digital",
        "strength": 0.65,
        "guidance": 8.5
    }
}

def build_prompt(wall_material: str, roof_material: str, style: str, custom: str = "") -> dict:
    """Build a complete prompt from presets."""
    
    parts = ["architectural visualization, residential home"]
    
    if wall_material and wall_material != "None" and wall_material in MATERIAL_PRESETS:
        parts.append(MATERIAL_PRESETS[wall_material])
    
    if roof_material and roof_material != "None" and roof_material in ROOF_PRESETS:
        parts.append(ROOF_PRESETS[roof_material])
    
    style_config = STYLE_PRESETS.get(style, STYLE_PRESETS["Clean Studio"])
    parts.append(style_config["suffix"])
    
    if custom:
        parts.append(custom)
    
    return {
        "prompt": ", ".join(parts),
        "negative": style_config["negative"],
        "strength": style_config["strength"],
        "guidance": style_config["guidance"]
    }
