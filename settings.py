"""Central defaults and editable generation presets."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_FILM_NEGATIVE = (
    "low quality, blurry, pixelated, bad anatomy, deformed body, extra limbs, malformed hands, "
    "extra fingers, distorted face, asymmetrical eyes, duplicate subjects, warped background, "
    "incorrect perspective, cropped limbs, plastic skin, unrealistic lighting, oversaturated, "
    "text, watermark, logo, CGI, cartoon, motion blur, flicker, jitter, morphing, temporal inconsistency"
)


PRESETS: dict[str, dict[str, Any]] = {
    "Fast": {
        "steps": 8,
        "cfg": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "refinement": {"enabled": True, "steps": 3, "denoise": 0.27},
    },
    "Balanced": {
        "steps": 12,
        "cfg": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "refinement": {"enabled": True, "steps": 3, "denoise": 0.27},
    },
    "Quality": {
        "steps": 15,
        "cfg": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "refinement": {
            "enabled": True,
            "steps": 3,
            "cfg": 1.0,
            "sampler": "euler",
            "scheduler": "simple",
            "denoise": 0.27,
        },
    },
}


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 4,
    "mode": "t2i",
    "preset": "Fast",
    "prompt": "",
    "negative_prompt": DEFAULT_FILM_NEGATIVE,
    "width": 1928,
    "height": 1088,
    "alignment": 8,
    "aspect_ratio": "16:9",
    "megapixels": 2.0,
    "custom_resolution": False,
    "batch_size": 1,
    "steps": 8,
    "cfg": 1.0,
    "seed": 0,
    "randomize_seed": True,
    "sampler": "euler",
    "scheduler": "simple",
    "denoise": 1.0,
    "res4lyf": {
        "enabled": True,
    },
    "gguf": {
        "enabled": False,
        "model": "",
        "clip_enabled": False,
        "clip": "",
    },
    "model": "",
    "clip": "",
    "vae": "",
    "weight_dtype": "default",
    "clip_device": "default",
    "loras": [],
    "advanced": False,
    "auto_save": True,
    "save_path": "",
    "scroll_zoom": False,
    "compare_enabled": False,
    "theme": "blue-snow",
    "prompt_crafter_url": "https://chatgpt.com/g/g-6a7ea7070fd0819196ae9307a5e70529-vionex-prompt-crafter",
    "notification_sound": False,
    "cinematic_style": "",
    "reference_downscale_mp": 1.0,
    "vae_decode": {
        "mode": "tiled",
        "tile_size": 256,
        "overlap": 64,
    },
    "refinement": {
        "enabled": True,
        "steps": 3,
        "cfg": 1.0,
        "sampler": "euler",
        "scheduler": "simple",
        "denoise": 0.27,
    },
    "diversity": {
        "enabled": False,
        "strength": 0.08,
        "eta": 0.75,
    },
    "enhancer": {
        "enabled": False,
        "behavior": "balanced",
        "max_length": 256,
        "temperature": 0.7,
        "top_k": 64,
        "top_p": 0.95,
        "repetition_penalty": 1.05,
        "seed": 0,
        "thinking": False,
    },
    "i2i": {
        "pipeline": "latent",
        "denoise": 0.65,
        "fit_mode": "fit",
        "identity_lora": "",
        "ref_boost": 4.0,
        "ref_boost_a": 1.0,
        "grounding_px": 768,
    },
    "multi_reference": {
        "vision_megapixels": 0.3,
        "vision_position": "before prompt",
        "system_prompt": (
            "Study every numbered reference image, preserve the requested identity, object, wardrobe, "
            "style, lighting, and environment cues, then combine them into one coherent new shot that "
            "follows the user's spatial instructions. Treat Image N and Picture N as the same reference."
        ),
    },
    "control": {
        "lora": "",
        "strength": 1.0,
        "resize": "match_latent_size",
        "upscale_method": "lanczos",
        "crop": "center",
        "channel_mode": "rgb",
        "normalize": "none",
        "invert": False,
        "preprocessor": "none",
        "preprocessor_resolution": 1024,
    },
    "external": {"model": False, "clip": False, "vae": False},
    "uploads": {"image": "", "image_2": "", "image_3": "", "image_4": ""},
    "stats": {
        "images_generated": 0,
        "renders_completed": 0,
        "total_render_ms": 0.0,
        "last_render_ms": 0.0,
        "last_batch": 0,
        "last_completed_at": "",
    },
}


def default_config() -> dict[str, Any]:
    """Return an isolated copy suitable for a workflow widget."""

    return deepcopy(DEFAULT_CONFIG)
