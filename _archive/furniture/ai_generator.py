"""
AI-powered furniture mesh generation.

Provides LOD3 (base geometry) and LOD4 (geometry + materials) generation
using local AI models. Supports both text descriptions and reference images.

LOD Levels:
- LOD3: Clean base mesh without materials (for iteration)
- LOD4: Full mesh with PBR materials
- LOD5: Reserved for documentation/reference
"""
import os
import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from furniture.models import (
    FurnitureItem,
    Mesh,
    Vertex,
    Material,
    Dimensions,
    LODLevel,
)


class GenerationQuality(Enum):
    """Quality presets for AI generation."""
    DRAFT = "draft"          # Fast, lower quality (for previews)
    STANDARD = "standard"    # Balanced quality/speed
    HIGH = "high"            # High quality, slower


@dataclass
class GenerationRequest:
    """
    Request for AI mesh generation.

    Can use text description, reference image, or both.
    When both are provided, they reinforce each other.
    """
    # Text-based inputs
    description: Optional[str] = None      # e.g., "modern leather armchair"
    style_prompt: Optional[str] = None     # e.g., "minimalist scandinavian"
    negative_prompt: Optional[str] = None  # e.g., "ornate, baroque"

    # Dimensional constraints (mm)
    dimensions: Optional[Dimensions] = None

    # Reference image
    reference_image_path: Optional[str] = None
    reference_image_weight: float = 0.7    # How much to follow the image (0-1)

    # Generation settings
    quality: GenerationQuality = GenerationQuality.STANDARD
    seed: Optional[int] = None             # For reproducibility

    # Material settings (LOD4 only)
    generate_materials: bool = False       # True for LOD4
    material_hints: Optional[Dict[str, str]] = None  # e.g., {"seat": "leather", "frame": "oak"}

    def get_cache_key(self) -> str:
        """Generate a unique cache key for this request."""
        key_data = {
            "desc": self.description,
            "style": self.style_prompt,
            "neg": self.negative_prompt,
            "dims": self.dimensions.to_dict() if self.dimensions else None,
            "img": self.reference_image_path,
            "img_w": self.reference_image_weight,
            "quality": self.quality.value,
            "seed": self.seed,
            "mats": self.generate_materials,
            "mat_hints": self.material_hints,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]


@dataclass
class GenerationResult:
    """Result from AI mesh generation."""
    success: bool
    mesh: Optional[Mesh] = None
    materials: Optional[Dict[str, Material]] = None  # Named materials for parts

    # Metadata
    generation_time_ms: float = 0
    model_used: str = ""
    cache_hit: bool = False

    # Error info
    error_message: Optional[str] = None

    # For iteration
    seed_used: Optional[int] = None        # Seed used (for reproducibility)
    intermediate_images: List[str] = field(default_factory=list)  # Debug views


class AIBackend(ABC):
    """
    Abstract base class for AI mesh generation backends.

    Implementations can use different models:
    - TripoSR (fast image-to-3D)
    - Shap-E (OpenAI's text/image-to-3D)
    - InstantMesh
    - Custom fine-tuned models
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available (model loaded, GPU ready)."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get backend name for logging."""
        pass

    @abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        Generate a mesh from the request.

        Args:
            request: Generation parameters

        Returns:
            GenerationResult with mesh (and optionally materials)
        """
        pass

    @abstractmethod
    def supports_text_input(self) -> bool:
        """Whether this backend supports text-to-3D."""
        pass

    @abstractmethod
    def supports_image_input(self) -> bool:
        """Whether this backend supports image-to-3D."""
        pass

    def preprocess_image(self, image_path: str) -> Optional[str]:
        """
        Preprocess reference image (background removal, etc.)

        Returns path to processed image or None if failed.
        Default implementation returns the original path.
        """
        return image_path


class AIFurnitureGenerator:
    """
    High-level interface for AI furniture generation.

    Manages backends, caching, and generation workflow.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self._backends: List[AIBackend] = []
        self._active_backend: Optional[AIBackend] = None

        # Cache directory for generated meshes
        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            self._cache_dir = Path.home() / ".archengine" / "furniture_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Generation history for undo/iteration
        self._history: List[Tuple[GenerationRequest, GenerationResult]] = []

    def register_backend(self, backend: AIBackend):
        """Register an AI backend."""
        self._backends.append(backend)
        if self._active_backend is None and backend.is_available():
            self._active_backend = backend

    def set_active_backend(self, name: str) -> bool:
        """Set active backend by name."""
        for backend in self._backends:
            if backend.get_name() == name and backend.is_available():
                self._active_backend = backend
                return True
        return False

    def get_available_backends(self) -> List[str]:
        """Get names of available backends."""
        return [b.get_name() for b in self._backends if b.is_available()]

    def generate_lod3(
        self,
        item: FurnitureItem,
        reference_image: Optional[str] = None,
        quality: GenerationQuality = GenerationQuality.STANDARD,
    ) -> GenerationResult:
        """
        Generate LOD3 mesh (base geometry, no materials).

        Uses item description and dimensions, optionally with reference image.
        """
        # Build description from item
        description = self._build_description(item)

        request = GenerationRequest(
            description=description,
            style_prompt=f"{item.style.value} style furniture",
            dimensions=item.dimensions,
            reference_image_path=reference_image,
            quality=quality,
            generate_materials=False,  # LOD3 = no materials
        )

        return self._generate_with_cache(request)

    def generate_lod4(
        self,
        item: FurnitureItem,
        reference_image: Optional[str] = None,
        quality: GenerationQuality = GenerationQuality.STANDARD,
        lod3_mesh: Optional[Mesh] = None,
    ) -> GenerationResult:
        """
        Generate LOD4 mesh (geometry with materials).

        Can optionally use a LOD3 mesh as starting point for faster generation.
        """
        description = self._build_description(item)

        # Build material hints from item
        material_hints = {}
        if item.primary_material:
            material_hints["primary"] = item.primary_material.name
        if item.secondary_material:
            material_hints["secondary"] = item.secondary_material.name

        request = GenerationRequest(
            description=description,
            style_prompt=f"{item.style.value} style furniture with realistic materials",
            dimensions=item.dimensions,
            reference_image_path=reference_image,
            quality=quality,
            generate_materials=True,  # LOD4 = with materials
            material_hints=material_hints,
        )

        return self._generate_with_cache(request)

    def iterate_on_mesh(
        self,
        previous_result: GenerationResult,
        adjustments: Dict[str, Any],
    ) -> GenerationResult:
        """
        Iterate on a previously generated mesh.

        Args:
            previous_result: Result from previous generation
            adjustments: Changes to make, e.g.:
                - {"scale": (1.1, 1.0, 1.0)}  # Make wider
                - {"style": "more modern"}
                - {"material": "darker wood"}
        """
        # Find the original request in history
        original_request = None
        for req, res in self._history:
            if res.seed_used == previous_result.seed_used:
                original_request = req
                break

        if original_request is None:
            return GenerationResult(
                success=False,
                error_message="Original request not found in history"
            )

        # Create modified request
        new_request = GenerationRequest(
            description=original_request.description,
            style_prompt=adjustments.get("style", original_request.style_prompt),
            dimensions=original_request.dimensions,
            reference_image_path=original_request.reference_image_path,
            quality=original_request.quality,
            generate_materials=original_request.generate_materials,
            seed=previous_result.seed_used,  # Use same seed for consistency
        )

        # Modify description if adjustments provided
        if "description" in adjustments:
            new_request.description = f"{original_request.description}, {adjustments['description']}"

        return self._generate_with_cache(new_request)

    def _build_description(self, item: FurnitureItem) -> str:
        """Build a generation description from a FurnitureItem."""
        parts = [item.name]

        if item.description:
            parts.append(item.description)

        # Add category and type
        parts.append(f"{item.category.value} furniture")
        parts.append(f"type: {item.furniture_type}")

        # Add material descriptions
        if item.primary_material:
            parts.append(f"made of {item.primary_material.name}")

        # Add tags
        if item.tags:
            parts.append(f"style: {', '.join(item.tags)}")

        return ", ".join(parts)

    def _generate_with_cache(self, request: GenerationRequest) -> GenerationResult:
        """Generate mesh, checking cache first."""
        cache_key = request.get_cache_key()
        cache_path = self._cache_dir / f"{cache_key}.json"

        # Check cache
        if cache_path.exists():
            try:
                result = self._load_from_cache(cache_path)
                if result:
                    result.cache_hit = True
                    return result
            except Exception:
                pass  # Cache miss, generate new

        # Generate
        if self._active_backend is None:
            return GenerationResult(
                success=False,
                error_message="No AI backend available"
            )

        result = self._active_backend.generate(request)

        # Cache successful results
        if result.success:
            self._save_to_cache(cache_path, request, result)
            self._history.append((request, result))

        return result

    def _load_from_cache(self, cache_path: Path) -> Optional[GenerationResult]:
        """Load a cached generation result."""
        with open(cache_path, 'r') as f:
            data = json.load(f)

        # Reconstruct mesh from cached vertex/index data
        vertices = []
        for v_data in data.get("vertices", []):
            vertices.append(Vertex(
                position=tuple(v_data["pos"]),
                normal=tuple(v_data["norm"]),
                color=tuple(v_data["col"]),
                tex_coord=tuple(v_data.get("uv", [0, 0])),
                stress=v_data.get("stress", 0),
            ))

        mesh = Mesh(
            vertices=vertices,
            indices=data.get("indices", [])
        ) if vertices else None

        # Reconstruct materials
        materials = {}
        for name, mat_data in data.get("materials", {}).items():
            materials[name] = Material(
                name=mat_data["name"],
                base_color=tuple(mat_data["base_color"]),
                metallic=mat_data.get("metallic", 0),
                roughness=mat_data.get("roughness", 0.5),
            )

        return GenerationResult(
            success=True,
            mesh=mesh,
            materials=materials if materials else None,
            generation_time_ms=data.get("generation_time_ms", 0),
            model_used=data.get("model_used", "cached"),
            seed_used=data.get("seed_used"),
        )

    def _save_to_cache(self, cache_path: Path, request: GenerationRequest, result: GenerationResult):
        """Save generation result to cache."""
        # Serialize mesh
        vertices_data = []
        if result.mesh:
            for v in result.mesh.vertices:
                vertices_data.append({
                    "pos": list(v.position),
                    "norm": list(v.normal),
                    "col": list(v.color),
                    "uv": list(v.tex_coord),
                    "stress": v.stress,
                })

        # Serialize materials
        materials_data = {}
        if result.materials:
            for name, mat in result.materials.items():
                materials_data[name] = {
                    "name": mat.name,
                    "base_color": list(mat.base_color),
                    "metallic": mat.metallic,
                    "roughness": mat.roughness,
                }

        data = {
            "vertices": vertices_data,
            "indices": result.mesh.indices if result.mesh else [],
            "materials": materials_data,
            "generation_time_ms": result.generation_time_ms,
            "model_used": result.model_used,
            "seed_used": result.seed_used,
        }

        with open(cache_path, 'w') as f:
            json.dump(data, f)

    def clear_cache(self):
        """Clear all cached generations."""
        for f in self._cache_dir.glob("*.json"):
            f.unlink()

    def get_cache_size(self) -> int:
        """Get number of cached items."""
        return len(list(self._cache_dir.glob("*.json")))


# Singleton instance
_ai_generator: Optional[AIFurnitureGenerator] = None


def get_ai_generator() -> AIFurnitureGenerator:
    """Get the global AI furniture generator instance."""
    global _ai_generator
    if _ai_generator is None:
        _ai_generator = AIFurnitureGenerator()
    return _ai_generator
