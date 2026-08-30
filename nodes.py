"""ComfyUI node definitions."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
from typing import Any

import comfy.utils
import nodes as comfy_nodes
import torch
from comfy_execution.graph_utils import is_link

from .config import parse_config
from .providers import Krea2Provider
from .settings import default_config


LOGGER = logging.getLogger("Krea2FilmStudio")


try:
    from comfy.text_encoders.krea2 import KREA2_TEMPLATE
except Exception:  # pragma: no cover - compatibility with older ComfyUI builds
    KREA2_TEMPLATE = (
        "<|im_start|>system\nDescribe the image by detailing the color, shape, size, texture, "
        "quantity, text, spatial relationships of the objects and background:<|im_end|>\n"
        "<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n"
    )


_KREA2_SYSTEM_MATCH = re.search(r"<\|im_start\|>system\n(.*?)<\|im_end\|>", KREA2_TEMPLATE, re.S)
KREA2_SYSTEM_DEFAULT = _KREA2_SYSTEM_MATCH.group(1) if _KREA2_SYSTEM_MATCH else (
    "Describe the image by detailing the color, shape, size, texture, quantity, text, "
    "spatial relationships of the objects and background:"
)


class Krea2MultiReferenceEncode:
    """Vision-aware Krea2 conditioning with four explicitly ordered references.

    The vision-token assembly follows the MIT-licensed ComfyUI-Krea2TextEncoder
    implementation by ethanfel: https://github.com/ethanfel/ComfyUI-Krea2TextEncoder
    Film Studio keeps a fixed four-slot surface so prompt references remain stable.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "prompt": ("STRING", {"multiline": True, "dynamicPrompts": True}),
                "system_prompt": ("STRING", {"multiline": True}),
                "vision_megapixels": ("FLOAT", {"default": 0.3, "min": 0.1, "max": 8.0, "step": 0.1}),
                "vision_position": (["before prompt", "after prompt"],),
            },
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
            },
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "encode"
    CATEGORY = "KREA / Film Studio/internal"
    DESCRIPTION = "Ordered multi-image vision conditioning for the Krea2 Qwen3-VL text encoder."

    @staticmethod
    def _prepare_vision(images: list[Any], vision_megapixels: float) -> tuple[list[torch.Tensor], str]:
        prepared: list[torch.Tensor] = []
        prompts: list[str] = []
        total = int(float(vision_megapixels) * 1024 * 1024)
        for order, item in enumerate(images, start=1):
            slot, image = item if isinstance(item, tuple) else (order, item)
            samples = image[..., :3].movedim(-1, 1)
            scale = min(1.0, math.sqrt(total / (samples.shape[3] * samples.shape[2])))
            width = max(1, round(samples.shape[3] * scale))
            height = max(1, round(samples.shape[2] * scale))
            resized = comfy.utils.common_upscale(samples, width, height, "area", "disabled")
            prepared.append(resized.movedim(1, -1))
            prompts.append(f"Image {slot} (Picture {slot}): <|vision_start|><|image_pad|><|vision_end|>")
        return prepared, "\n".join(prompts) + "\n"

    def encode(
        self,
        clip,
        prompt: str,
        system_prompt: str,
        vision_megapixels: float = 0.3,
        vision_position: str = "before prompt",
        **kwargs: Any,
    ):
        images = [(index, kwargs.get(f"image{index}")) for index in range(1, 5) if kwargs.get(f"image{index}") is not None]
        if not images:
            raise ValueError("Reference Studio needs at least one reference image.")
        images_vl, image_prompt = self._prepare_vision(images, vision_megapixels)
        system = str(system_prompt or "").strip() or KREA2_SYSTEM_DEFAULT
        template = (
            "<|im_start|>system\n" + system + "<|im_end|>\n"
            "<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n"
        )
        prompt = str(prompt or "").strip()
        text = f"{prompt}\n{image_prompt}" if vision_position == "after prompt" else f"{image_prompt}{prompt}"
        tokens = clip.tokenize(text, images=images_vl, llama_template=template)
        try:
            return (clip.encode_from_tokens_scheduled(tokens),)
        except NotImplementedError as exc:
            if "Float8" in str(exc):
                raise RuntimeError(
                    "Krea2 multi-reference vision encoding cannot use this FP8 text encoder. "
                    "Select a BF16/FP16 Qwen3-VL-4B Krea2 text encoder (standard or compatible GGUF) "
                    "and render again."
                ) from exc
            raise


class Krea2ReferenceDownscale:
    """Downscale only oversized references while preserving their aspect ratio."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "megapixels": ("FLOAT", {"default": 1.0, "min": 0.05, "max": 32.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "downscale"
    CATEGORY = "KREA / Film Studio/internal"

    def downscale(self, image: torch.Tensor, megapixels: float):
        height, width = int(image.shape[1]), int(image.shape[2])
        target_area = float(megapixels) * 1_000_000
        if width * height <= target_area:
            return (image,)
        scale = math.sqrt(target_area / (width * height))
        target_width = max(8, int(round(width * scale / 8)) * 8)
        target_height = max(8, int(round(height * scale / 8)) * 8)
        samples = image[..., :3].movedim(-1, 1)
        result = comfy.utils.common_upscale(samples, target_width, target_height, "lanczos", "disabled")
        return (result.movedim(1, -1),)


class Krea2ImageFit:
    """Resize an IMAGE to a canvas with explicit crop, fit, or stretch behavior."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "mode": (["crop", "fit", "stretch"],),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "resize"
    CATEGORY = "KREA / Film Studio/internal"

    def resize(self, image: torch.Tensor, width: int, height: int, mode: str):
        samples = image.movedim(-1, 1)
        if mode != "fit":
            crop = "center" if mode == "crop" else "disabled"
            resized = comfy.utils.common_upscale(samples, width, height, "lanczos", crop)
            return (resized.movedim(1, -1),)

        source_height, source_width = int(image.shape[1]), int(image.shape[2])
        scale = min(width / source_width, height / source_height)
        fit_width = max(1, min(width, int(round(source_width * scale))))
        fit_height = max(1, min(height, int(round(source_height * scale))))
        resized = comfy.utils.common_upscale(samples, fit_width, fit_height, "lanczos", "disabled")
        canvas = samples.new_zeros((samples.shape[0], samples.shape[1], height, width))
        top = (height - fit_height) // 2
        left = (width - fit_width) // 2
        canvas[:, :, top : top + fit_height, left : left + fit_width] = resized
        return (canvas.movedim(1, -1),)


class Krea2PromptTemplate:
    """Prepare an instruction for the local Qwen TextGenerate enhancer."""

    BEHAVIORS = {
        "light": "Lightly polish the prompt. Preserve every requested subject and detail. Return one prompt paragraph only.",
        "balanced": "Expand this into a clear text-to-image prompt with grounded composition, lighting, and style. Preserve all requested details and add no conflicting subjects. Return one paragraph only.",
        "detailed": "Write a richly detailed but coherent text-to-image prompt. Preserve the user's intent, clarify spatial relationships, camera, lighting, materials, and mood. Return one paragraph only.",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "behavior": (list(cls.BEHAVIORS),),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "format"
    CATEGORY = "KREA / Film Studio/internal"

    def format(self, prompt: str, behavior: str):
        return (f"{self.BEHAVIORS.get(behavior, self.BEHAVIORS['balanced'])}\n\nUser prompt:\n{prompt}",)


class Krea2PromptStyle:
    """Append a selected cinematic style without altering the saved user prompt."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "forceInput": True}),
                "suffix": ("STRING", {"multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "append"
    CATEGORY = "KREA / Film Studio/internal"

    def append(self, prompt: str, suffix: str):
        prompt = str(prompt or "").strip()
        suffix = str(suffix or "").strip()
        if not suffix:
            return (prompt,)
        return (f"{prompt}\n\n{suffix}" if prompt else suffix,)


class Krea2DiversityNoise:
    """Add deterministic low-amplitude latent noise before either sampler backend."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent": ("LATENT",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "strength": ("FLOAT", {"default": 0.08, "min": 0.0, "max": 1.0, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "inject"
    CATEGORY = "KREA / Film Studio/internal"

    def inject(self, latent: dict[str, Any], seed: int, strength: float):
        result = dict(latent)
        samples = latent["samples"]
        generator = torch.Generator(device="cpu")
        generator.manual_seed(int(seed) & 0xffffffffffffffff)
        noise = torch.randn(samples.shape, generator=generator, device="cpu", dtype=torch.float32)
        result["samples"] = samples + noise.to(device=samples.device, dtype=samples.dtype) * float(strength)
        return (result,)


class Krea2SaveImage(comfy_nodes.SaveImage):
    """Save images to an explicit absolute folder while preserving ComfyUI metadata."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "output_path": ("STRING", {"default": ""}),
                "filename_prefix": ("STRING", {"default": "KREA2"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    def save_images(self, images, output_path="", filename_prefix="KREA2", prompt=None, extra_pnginfo=None):
        expanded = os.path.expandvars(os.path.expanduser(str(output_path or "").strip()))
        target = Path(expanded)
        if not expanded or not target.is_absolute():
            raise ValueError("Krea 2 Film Studio custom save path must be an absolute folder path.")
        target.mkdir(parents=True, exist_ok=True)
        if not target.is_dir():
            raise ValueError(f"Krea 2 Film Studio save path is not a folder: {target}")
        self.output_dir = str(target.resolve())
        self.type = "output"
        return super().save_images(images, filename_prefix, prompt, extra_pnginfo)


class Krea2OneNode:
    """VIONEX film-studio interface that expands to native ComfyUI nodes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": (
                    "STRING",
                    {"default": json.dumps(default_config(), ensure_ascii=False), "multiline": True, "hidden": True},
                )
            },
            "optional": {
                "prompt": ("STRING", {"forceInput": True, "rawLink": True}),
                "image": ("IMAGE", {"rawLink": True}),
                "image_2": ("IMAGE", {"rawLink": True}),
                "image_3": ("IMAGE", {"rawLink": True}),
                "image_4": ("IMAGE", {"rawLink": True}),
                "model": ("MODEL", {"rawLink": True}),
                "clip": ("CLIP", {"rawLink": True}),
                "vae": ("VAE", {"rawLink": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "LATENT", "INT")
    RETURN_NAMES = ("image", "latent", "used_seed")
    FUNCTION = "expand"
    CATEGORY = "KREA / Film Studio"
    OUTPUT_NODE = True
    DESCRIPTION = "Krea 2 Film Studio by VIONEX: local Text to Film, Transform Frame, and Directed Control workflows built from native ComfyUI nodes."

    def expand(self, config: str, unique_id: str | None = None, **raw_inputs: Any):
        try:
            raw = json.loads(config or "{}")
        except json.JSONDecodeError:
            raw = {}
        randomize = bool(raw.get("randomize_seed", True))
        # Keep browser-visible random seeds inside JavaScript's exact integer range.
        seed = secrets.randbelow(2**53) if randomize else raw.get("seed", 0)
        external = raw.get("external") if isinstance(raw.get("external"), dict) else {}
        parsed = parse_config(
            config,
            need_model=not (external.get("model") and is_link(raw_inputs.get("model"))),
            need_clip=not (external.get("clip") and is_link(raw_inputs.get("clip"))),
            need_vae=not (external.get("vae") and is_link(raw_inputs.get("vae"))),
            seed=seed,
        )
        LOGGER.info(
            "Krea 2 Film Studio: queue node=%s mode=%s resolution=%sx%s seed=%s model=%s text_encoder=%s sampler=%s refinement=%s.",
            unique_id,
            parsed.mode.upper(),
            parsed.width,
            parsed.height,
            parsed.seed,
            "GGUF" if parsed.data["gguf"].get("enabled") else "standard",
            "GGUF" if parsed.data["gguf"].get("clip_enabled") else "standard",
            "RES4LYF recommended" if parsed.data["res4lyf"].get("enabled", True) else "native KSampler",
            "on" if parsed.data["refinement"].get("enabled") else "off",
        )
        usable = {
            "unique_id": unique_id,
            "prompt": raw_inputs.get("prompt"),
            "image": raw_inputs.get("image"),
            "image_2": raw_inputs.get("image_2"),
            "image_3": raw_inputs.get("image_3"),
            "image_4": raw_inputs.get("image_4"),
            "model": raw_inputs.get("model") if external.get("model") else None,
            "clip": raw_inputs.get("clip") if external.get("clip") else None,
            "vae": raw_inputs.get("vae") if external.get("vae") else None,
        }
        result = Krea2Provider().expand(parsed, **usable)
        return {
            "result": (result.image, result.latent, result.seed),
            "expand": result.graph,
            "ui": {"used_seed": [result.seed], "mode": [parsed.mode]},
        }

    @classmethod
    def IS_CHANGED(cls, config: str, **_kwargs: Any):
        try:
            if json.loads(config or "{}").get("randomize_seed", True):
                return float("nan")
        except json.JSONDecodeError:
            return float("nan")
        return config


NODE_CLASS_MAPPINGS = {
    "Krea2OneNode": Krea2OneNode,
    "Krea2ReferenceDownscale": Krea2ReferenceDownscale,
    "Krea2MultiReferenceEncode": Krea2MultiReferenceEncode,
    "Krea2ImageFit": Krea2ImageFit,
    "Krea2PromptTemplate": Krea2PromptTemplate,
    "Krea2PromptStyle": Krea2PromptStyle,
    "Krea2DiversityNoise": Krea2DiversityNoise,
    "Krea2SaveImage": Krea2SaveImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2OneNode": "Krea 2 Film Studio",
    "Krea2ReferenceDownscale": "KREA 2 Reference Downscale (internal)",
    "Krea2MultiReferenceEncode": "KREA 2 Multi-Reference Encode (internal)",
    "Krea2ImageFit": "KREA 2 Image Fit (internal)",
    "Krea2PromptTemplate": "KREA 2 Prompt Template (internal)",
    "Krea2PromptStyle": "KREA 2 Cinematic Style (internal)",
    "Krea2DiversityNoise": "KREA 2 Diversity Noise (internal)",
    "Krea2SaveImage": "KREA 2 Custom Save (internal)",
}
