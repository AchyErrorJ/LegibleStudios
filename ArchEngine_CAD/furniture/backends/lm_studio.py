"""
LM Studio backend for AI furniture generation.

Uses a Vision-Language model (like Qwen VL) to:
1. Analyze reference images of furniture
2. Generate detailed structural specifications
3. Convert specs into procedural geometry

The VL model acts as an intelligent "geometry architect" that understands
furniture structure and outputs buildable specifications.
"""
import json
import base64
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import math

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from furniture.ai_generator import (
    AIBackend,
    GenerationRequest,
    GenerationResult,
    GenerationQuality,
)
from furniture.models import (
    Mesh,
    Vertex,
    Material,
    Dimensions,
)
from furniture.primitives import (
    create_box,
    create_cylinder,
    create_rounded_box,
    create_wedge,
    merge_meshes,
    transform_mesh,
)


@dataclass
class GeometrySpec:
    """Specification for a geometry primitive from VL model."""
    primitive_type: str  # box, cylinder, rounded_box, wedge
    dimensions: Dict[str, float]  # width, height, depth, radius, etc.
    position: Tuple[float, float, float]  # x, y, z offset
    rotation: float = 0  # Y-axis rotation in degrees
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5)
    material_name: Optional[str] = None
    part_name: Optional[str] = None  # e.g., "seat", "backrest", "leg_1"


@dataclass
class FurnitureSpec:
    """Complete furniture specification from VL model."""
    name: str
    parts: List[GeometrySpec]
    overall_dimensions: Dimensions
    materials: Dict[str, Dict[str, Any]] = None  # material definitions
    description: str = ""


# System prompt for the VL model
GEOMETRY_SYSTEM_PROMPT = """You are a furniture geometry architect. Your job is to analyze furniture and output precise geometric specifications that can be built from primitives.

When given a furniture description (and optionally an image), output a JSON specification with these exact fields:

{
  "name": "furniture name",
  "description": "brief description",
  "overall_dimensions": {"width": mm, "depth": mm, "height": mm},
  "parts": [
    {
      "part_name": "descriptive name like 'seat_cushion' or 'left_front_leg'",
      "primitive_type": "box|cylinder|rounded_box|wedge",
      "dimensions": {
        // For box: width, height, depth
        // For cylinder: radius, height, segments (optional, default 16)
        // For rounded_box: width, height, depth, corner_radius
        // For wedge: width, height_front, height_back, depth
      },
      "position": [x, y, z],  // center position in mm, Y is up
      "rotation": degrees,     // rotation around Y axis
      "color": [r, g, b],      // 0-1 range
      "material_name": "material key or null"
    }
  ],
  "materials": {
    "material_key": {
      "name": "display name",
      "base_color": [r, g, b],
      "metallic": 0-1,
      "roughness": 0-1
    }
  }
}

Guidelines:
- All dimensions in millimeters
- Y axis points UP (height), X is width, Z is depth
- Position is the CENTER of each primitive
- Break furniture into logical parts (legs, seat, back, arms, etc.)
- Use appropriate primitives: cylinders for round legs, rounded_box for cushions, boxes for flat surfaces
- Match colors/materials to the description or image
- Keep geometry simple but accurate to the design
- Aim for 5-20 parts for most furniture

For LOD3 (no materials): set all colors to neutral gray (0.5, 0.5, 0.5) and omit materials
For LOD4 (with materials): include realistic colors and material definitions"""


class LMStudioBackend(AIBackend):
    """
    LM Studio backend using a Vision-Language model.

    Connects to LM Studio's OpenAI-compatible API to analyze
    furniture images/descriptions and generate geometry specs.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1234/v1",
        model: str = "default",
        timeout: float = 120.0,
    ):
        self._base_url = base_url
        self._model = model
        self._timeout = timeout
        self._client = None
        self._available = False

        if HTTPX_AVAILABLE:
            self._client = httpx.Client(timeout=timeout)
            self._check_availability()

    def _check_availability(self):
        """Check if LM Studio is running and responsive."""
        try:
            response = self._client.get(f"{self._base_url}/models")
            self._available = response.status_code == 200
        except Exception:
            self._available = False

    def is_available(self) -> bool:
        if not HTTPX_AVAILABLE:
            return False
        self._check_availability()
        return self._available

    def get_name(self) -> str:
        return "lm_studio"

    def supports_text_input(self) -> bool:
        return True

    def supports_image_input(self) -> bool:
        return True  # Qwen VL supports vision

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Generate mesh from request using VL model."""
        if not self.is_available():
            return GenerationResult(
                success=False,
                error_message="LM Studio not available"
            )

        start_time = time.time()
        seed = request.seed or random.randint(0, 2**31)

        try:
            # Build the prompt
            prompt = self._build_prompt(request)
            messages = [
                {"role": "system", "content": GEOMETRY_SYSTEM_PROMPT},
            ]

            # Add image if provided
            if request.reference_image_path:
                image_content = self._encode_image(request.reference_image_path)
                if image_content:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_content}},
                            {"type": "text", "text": prompt}
                        ]
                    })
                else:
                    messages.append({"role": "user", "content": prompt})
            else:
                messages.append({"role": "user", "content": prompt})

            # Call LM Studio API
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.3,  # Lower for more consistent geometry
                    "max_tokens": 4096,
                    "seed": seed,
                }
            )

            if response.status_code != 200:
                return GenerationResult(
                    success=False,
                    error_message=f"LM Studio API error: {response.status_code}"
                )

            result_data = response.json()
            content = result_data["choices"][0]["message"]["content"]

            # Parse the JSON spec from response
            spec = self._parse_spec(content)
            if spec is None:
                return GenerationResult(
                    success=False,
                    error_message="Failed to parse geometry specification from model output"
                )

            # Apply dimension constraints if provided
            if request.dimensions:
                spec = self._apply_dimension_constraints(spec, request.dimensions)

            # Build mesh from spec
            mesh = self._build_mesh(spec)

            # Build materials dict
            materials = None
            if request.generate_materials and spec.materials:
                materials = {}
                for key, mat_data in spec.materials.items():
                    materials[key] = Material(
                        name=mat_data.get("name", key),
                        base_color=tuple(mat_data.get("base_color", [0.5, 0.5, 0.5])),
                        metallic=mat_data.get("metallic", 0.0),
                        roughness=mat_data.get("roughness", 0.5),
                    )

            generation_time = (time.time() - start_time) * 1000

            return GenerationResult(
                success=True,
                mesh=mesh,
                materials=materials,
                generation_time_ms=generation_time,
                model_used=f"lm_studio:{self._model}",
                seed_used=seed,
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                error_message=f"Generation failed: {str(e)}"
            )

    def _build_prompt(self, request: GenerationRequest) -> str:
        """Build the prompt for the VL model."""
        parts = []

        # LOD level instruction
        if request.generate_materials:
            parts.append("Generate LOD4 furniture geometry WITH materials and realistic colors.")
        else:
            parts.append("Generate LOD3 furniture geometry WITHOUT materials (use neutral gray colors).")

        # Main description
        if request.description:
            parts.append(f"\nFurniture description: {request.description}")

        # Style
        if request.style_prompt:
            parts.append(f"Style: {request.style_prompt}")

        # Negative prompt
        if request.negative_prompt:
            parts.append(f"Avoid: {request.negative_prompt}")

        # Dimensions constraint
        if request.dimensions:
            d = request.dimensions
            parts.append(f"\nTarget dimensions (approximate):")
            parts.append(f"  Width: {d.width}mm, Depth: {d.depth}mm, Height: {d.height}mm")

        # Material hints
        if request.material_hints:
            parts.append("\nMaterial hints:")
            for part, material in request.material_hints.items():
                parts.append(f"  {part}: {material}")

        # Quality instruction
        if request.quality == GenerationQuality.DRAFT:
            parts.append("\nKeep geometry simple (5-10 parts).")
        elif request.quality == GenerationQuality.HIGH:
            parts.append("\nCreate detailed geometry (15-25 parts) with accurate proportions.")

        # Image instruction
        if request.reference_image_path:
            weight = request.reference_image_weight
            if weight > 0.7:
                parts.append("\nClosely match the furniture in the provided image.")
            elif weight > 0.3:
                parts.append("\nUse the image as a reference, but adapt to the description.")
            else:
                parts.append("\nUse the image for general inspiration only.")

        parts.append("\nOutput ONLY the JSON specification, no other text.")

        return "\n".join(parts)

    def _encode_image(self, image_path: str) -> Optional[str]:
        """Encode image as base64 data URL."""
        try:
            path = Path(image_path)
            if not path.exists():
                return None

            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()

            # Determine MIME type
            suffix = path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime = mime_types.get(suffix, "image/jpeg")

            return f"data:{mime};base64,{data}"

        except Exception:
            return None

    def _parse_spec(self, content: str) -> Optional[FurnitureSpec]:
        """Parse JSON geometry specification from model output."""
        try:
            # Try to extract JSON from response
            # Model might include markdown code blocks
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end]
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end]

            data = json.loads(content.strip())

            # Parse parts
            parts = []
            for part_data in data.get("parts", []):
                parts.append(GeometrySpec(
                    primitive_type=part_data.get("primitive_type", "box"),
                    dimensions=part_data.get("dimensions", {}),
                    position=tuple(part_data.get("position", [0, 0, 0])),
                    rotation=part_data.get("rotation", 0),
                    color=tuple(part_data.get("color", [0.5, 0.5, 0.5])),
                    material_name=part_data.get("material_name"),
                    part_name=part_data.get("part_name"),
                ))

            # Parse overall dimensions
            dims_data = data.get("overall_dimensions", {})
            overall_dims = Dimensions(
                width=dims_data.get("width", 500),
                depth=dims_data.get("depth", 500),
                height=dims_data.get("height", 500),
            )

            return FurnitureSpec(
                name=data.get("name", "furniture"),
                parts=parts,
                overall_dimensions=overall_dims,
                materials=data.get("materials"),
                description=data.get("description", ""),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[LMStudio] Failed to parse spec: {e}")
            print(f"[LMStudio] Raw content: {content[:500]}...")
            return None

    def _apply_dimension_constraints(
        self,
        spec: FurnitureSpec,
        target: Dimensions
    ) -> FurnitureSpec:
        """Scale specification to match target dimensions."""
        current = spec.overall_dimensions

        # Calculate scale factors
        scale_x = target.width / current.width if current.width > 0 else 1
        scale_y = target.height / current.height if current.height > 0 else 1
        scale_z = target.depth / current.depth if current.depth > 0 else 1

        # Scale each part
        scaled_parts = []
        for part in spec.parts:
            new_dims = {}
            for key, value in part.dimensions.items():
                if key in ("width", "radius"):
                    new_dims[key] = value * scale_x
                elif key in ("height", "height_front", "height_back"):
                    new_dims[key] = value * scale_y
                elif key in ("depth",):
                    new_dims[key] = value * scale_z
                else:
                    new_dims[key] = value

            new_pos = (
                part.position[0] * scale_x,
                part.position[1] * scale_y,
                part.position[2] * scale_z,
            )

            scaled_parts.append(GeometrySpec(
                primitive_type=part.primitive_type,
                dimensions=new_dims,
                position=new_pos,
                rotation=part.rotation,
                color=part.color,
                material_name=part.material_name,
                part_name=part.part_name,
            ))

        return FurnitureSpec(
            name=spec.name,
            parts=scaled_parts,
            overall_dimensions=target,
            materials=spec.materials,
            description=spec.description,
        )

    def _build_mesh(self, spec: FurnitureSpec) -> Mesh:
        """Build mesh from geometry specification."""
        meshes = []

        for part in spec.parts:
            mesh = self._build_primitive(part)
            if mesh:
                meshes.append(mesh)

        if not meshes:
            # Fallback: create a simple box
            return create_box(
                spec.overall_dimensions.width,
                spec.overall_dimensions.height,
                spec.overall_dimensions.depth,
                color=(0.5, 0.5, 0.5)
            )

        return merge_meshes(meshes)

    def _build_primitive(self, part: GeometrySpec) -> Optional[Mesh]:
        """Build a single primitive from specification."""
        dims = part.dimensions
        color = part.color

        try:
            if part.primitive_type == "box":
                mesh = create_box(
                    width=dims.get("width", 100),
                    height=dims.get("height", 100),
                    depth=dims.get("depth", 100),
                    offset=part.position,
                    color=color,
                )
            elif part.primitive_type == "cylinder":
                mesh = create_cylinder(
                    radius=dims.get("radius", 50),
                    height=dims.get("height", 100),
                    segments=dims.get("segments", 16),
                    offset=part.position,
                    color=color,
                )
            elif part.primitive_type == "rounded_box":
                mesh = create_rounded_box(
                    width=dims.get("width", 100),
                    height=dims.get("height", 100),
                    depth=dims.get("depth", 100),
                    corner_radius=dims.get("corner_radius", 10),
                    offset=part.position,
                    color=color,
                )
            elif part.primitive_type == "wedge":
                mesh = create_wedge(
                    width=dims.get("width", 100),
                    height_front=dims.get("height_front", 50),
                    height_back=dims.get("height_back", 100),
                    depth=dims.get("depth", 100),
                    offset=part.position,
                    color=color,
                )
            else:
                # Unknown primitive, use box
                mesh = create_box(
                    width=dims.get("width", 100),
                    height=dims.get("height", 100),
                    depth=dims.get("depth", 100),
                    offset=part.position,
                    color=color,
                )

            # Apply rotation if specified
            if part.rotation != 0:
                mesh = transform_mesh(mesh, rotate_y=part.rotation)

            return mesh

        except Exception as e:
            print(f"[LMStudio] Failed to build primitive '{part.part_name}': {e}")
            return None
