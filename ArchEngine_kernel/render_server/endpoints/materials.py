"""Material generation and management endpoints"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
import json
import os
import sys

router = APIRouter(prefix="/api/materials", tags=["materials"])

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class MaterialGenerateRequest(BaseModel):
    """Request to generate a new material."""
    prompt: str
    name: str
    output_root: str = "materials"
    size: int = 1024
    steps: int = 30
    guidance: float = 7.5
    seed: Optional[int] = None
    tileable: bool = True
    seam_width: Optional[int] = None
    negative_prompt: str = "blurry, low quality, distorted, watermark"
    roughness: Optional[float] = None
    metallic: Optional[float] = None
    emissive: Optional[float] = None
    opacity: Optional[float] = None


class MaterialUpscaleRequest(BaseModel):
    """Request to upscale material textures."""
    material_path: str
    output_path: Optional[str] = None
    scale: int = 4
    method: str = "realesrgan"  # realesrgan, sdxl, ultra


class TextureUpscaleRequest(BaseModel):
    """Request to upscale a single texture."""
    input_path: str
    output_path: str
    scale: int = 4
    method: str = "realesrgan"


class MaterialListResponse(BaseModel):
    """Response listing materials."""
    materials: List[Dict]
    count: int


@router.get("/list")
async def list_materials(root: str = "materials") -> MaterialListResponse:
    """List all available materials."""
    materials_root = Path(root)
    if not materials_root.is_absolute():
        # Relative to render_server parent
        materials_root = Path(__file__).parent.parent.parent / root

    if not materials_root.exists():
        return MaterialListResponse(materials=[], count=0)

    materials = []
    for entry in sorted(materials_root.iterdir()):
        if not entry.is_dir():
            continue

        # Check for albedo texture
        albedo = None
        for ext in [".png", ".jpg", ".jpeg"]:
            for name in ["albedo", "diffuse", "basecolor"]:
                p = entry / f"{name}{ext}"
                if p.exists():
                    albedo = str(p)
                    break
            if albedo:
                break

        if albedo:
            materials.append({
                "name": entry.name,
                "path": str(entry),
                "albedo": albedo
            })

    return MaterialListResponse(materials=materials, count=len(materials))


@router.post("/generate")
async def generate_material(request: MaterialGenerateRequest):
    """Generate a new PBR material using AI."""
    try:
        from channel_extractor import ChannelExtractor

        output_dir = Path(request.output_root)
        if not output_dir.is_absolute():
            output_dir = Path(__file__).parent.parent.parent / request.output_root

        material_dir = output_dir / request.name
        material_dir.mkdir(parents=True, exist_ok=True)

        print(f"Generating material: {request.name}")
        print(f"Prompt: {request.prompt}")
        print(f"Output: {material_dir}")

        # Initialize channel extractor
        extractor = ChannelExtractor()

        # Generate albedo (base texture)
        albedo_path = material_dir / "albedo.png"
        print("Generating albedo texture...")

        # Use SD to generate base texture
        from diffusers import StableDiffusionPipeline
        import torch

        pipe = StableDiffusionPipeline.from_pretrained(
            "stabilityai/stable-diffusion-2-1",
            torch_dtype=torch.float16
        )
        pipe.to("cuda")
        pipe.enable_attention_slicing()

        # Generate tileable texture
        full_prompt = f"seamless tileable texture of {request.prompt}, PBR material, 4k, detailed"

        image = pipe(
            prompt=full_prompt,
            negative_prompt=request.negative_prompt,
            width=request.size,
            height=request.size,
            num_inference_steps=request.steps,
            guidance_scale=request.guidance,
            generator=torch.Generator("cuda").manual_seed(request.seed) if request.seed else None
        ).images[0]

        # Make tileable if requested
        if request.tileable:
            image = _make_tileable(image, request.seam_width or 64)

        image.save(albedo_path)
        print(f"Saved albedo: {albedo_path}")

        # Extract PBR channels
        print("Extracting PBR channels...")
        channels = extractor.extract_all_channels(str(albedo_path), str(material_dir))

        # Override with constants if specified
        if request.roughness is not None:
            _create_constant_texture(material_dir / "roughness.png", request.roughness, request.size)
        if request.metallic is not None:
            _create_constant_texture(material_dir / "metallic.png", request.metallic, request.size)
        if request.emissive is not None:
            _create_constant_texture(material_dir / "emissive.png", request.emissive, request.size)
        if request.opacity is not None:
            _create_constant_texture(material_dir / "opacity.png", request.opacity, request.size)

        # Cleanup
        del pipe
        torch.cuda.empty_cache()

        return {
            "status": "ok",
            "name": request.name,
            "path": str(material_dir),
            "textures": list(material_dir.glob("*.png"))
        }

    except ImportError as e:
        return {"status": "error", "error": f"Missing dependency: {e}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@router.post("/upscale")
async def upscale_texture(request: TextureUpscaleRequest):
    """Upscale a single texture using AI."""
    try:
        from upscaler import get_upscaler

        input_path = Path(request.input_path)
        output_path = Path(request.output_path)

        if not input_path.exists():
            return {"status": "error", "error": f"Input file not found: {input_path}"}

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Upscaling: {input_path} -> {output_path}")
        print(f"Method: {request.method}, Scale: {request.scale}x")

        upscaler = get_upscaler(request.method)
        result = upscaler.upscale(str(input_path), str(output_path), scale=request.scale)

        return {
            "status": "ok",
            "input": str(input_path),
            "output": str(result),
            "method": request.method,
            "scale": request.scale
        }

    except ImportError as e:
        return {"status": "error", "error": f"Missing dependency: {e}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


@router.post("/upscale-material")
async def upscale_material(request: MaterialUpscaleRequest):
    """Upscale all textures in a material."""
    try:
        from upscaler import get_upscaler

        material_path = Path(request.material_path)
        if not material_path.exists():
            return {"status": "error", "error": f"Material not found: {material_path}"}

        output_path = Path(request.output_path) if request.output_path else material_path.parent / f"{material_path.name}_upscaled"
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"Upscaling material: {material_path}")
        print(f"Output: {output_path}")
        print(f"Method: {request.method}, Scale: {request.scale}x")

        upscaler = get_upscaler(request.method)
        results = []

        for tex_file in material_path.glob("*.png"):
            out_file = output_path / tex_file.name
            print(f"  {tex_file.name}...", end=" ", flush=True)

            try:
                upscaler.upscale(str(tex_file), str(out_file), scale=request.scale)
                results.append({"texture": tex_file.name, "status": "ok"})
                print("OK")
            except Exception as e:
                results.append({"texture": tex_file.name, "status": "error", "error": str(e)})
                print(f"FAILED: {e}")

        return {
            "status": "ok",
            "material": str(material_path),
            "output": str(output_path),
            "results": results
        }

    except ImportError as e:
        return {"status": "error", "error": f"Missing dependency: {e}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def _make_tileable(image, seam_width: int = 64):
    """Make an image tileable by blending edges."""
    from PIL import Image, ImageFilter
    import numpy as np

    img = np.array(image).astype(np.float32)
    h, w = img.shape[:2]

    # Blend left-right
    for i in range(seam_width):
        alpha = i / seam_width
        img[:, i] = img[:, i] * alpha + img[:, w - seam_width + i] * (1 - alpha)
        img[:, w - seam_width + i] = img[:, i]

    # Blend top-bottom
    for i in range(seam_width):
        alpha = i / seam_width
        img[i, :] = img[i, :] * alpha + img[h - seam_width + i, :] * (1 - alpha)
        img[h - seam_width + i, :] = img[i, :]

    return Image.fromarray(img.astype(np.uint8))


def _create_constant_texture(path: Path, value: float, size: int):
    """Create a constant grayscale texture."""
    from PIL import Image
    img = Image.new("L", (size, size), int(value * 255))
    img.save(path)
