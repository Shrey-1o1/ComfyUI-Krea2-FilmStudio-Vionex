"""Workflow configuration parsing and boundary validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

import comfy.samplers
import folder_paths

from .resolution import validate_dimensions
from .settings import DEFAULT_CONFIG, DEFAULT_FILM_NEGATIVE
from .styles import CINEMATIC_STYLES


def _merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _number(value: Any, name: str, low: float, high: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(result) or result < low or result > high:
        raise ValueError(f"{name} must be between {low} and {high}.")
    return result


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{name} must be an integer.")
    if result < low or result > high:
        raise ValueError(f"{name} must be between {low} and {high}.")
    return result


def _mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a configuration object.")
    return value


def _filename(folder: str, value: str, label: str, required: bool = True) -> str:
    value = str(value or "").strip()
    if not value:
        if required:
            raise ValueError(f"Select a {label} in KREA 2 · One Node Settings.")
        return ""
    listed = folder_paths.get_filename_list(folder)

    def normalized(name: str) -> str:
        return PurePosixPath(str(name).replace("\\", "/")).as_posix().casefold()

    wanted = normalized(value)
    matches = [name for name in listed if normalized(name) == wanted]
    if not matches:
        wanted_basename = PurePosixPath(wanted).name
        matches = [name for name in listed if PurePosixPath(normalized(name)).name == wanted_basename]
    if not matches:
        raise ValueError(f"Selected {label} was not found in models/{folder}: {value}")
    if len(matches) > 1:
        raise ValueError(
            f"Selected {label} is ambiguous in models/{folder}: {value}. "
            "Choose it again from the refreshed Film Studio list."
        )
    resolved = matches[0]
    folder_paths.get_full_path_or_raise(folder, resolved)
    return resolved


def suggest_identity_edit_lora(names: list[str] | tuple[str, ...]) -> str:
    """Return the best installed Krea 2 Identity Edit weight, preferring full v1.2."""

    candidates = [
        name for name in names
        if re.search(r"krea.?2.*identity.*edit.*\.safetensors$", PurePosixPath(str(name).replace("\\", "/")).name, re.IGNORECASE)
    ]
    if not candidates:
        return ""

    def rank(name: str) -> tuple[int, int, str]:
        basename = PurePosixPath(str(name).replace("\\", "/")).name.casefold()
        version_rank = 3 if "v1_2" in basename or "v1-2" in basename else 2 if "v1_1" in basename or "v1-1" in basename else 1
        capacity_rank = 2 if "_r64" not in basename and "_r128" not in basename else 1 if "_r128" in basename else 0
        return version_rank, capacity_rank, basename

    return max(candidates, key=rank)


@dataclass(frozen=True)
class LoraSpec:
    name: str
    strength_model: float
    strength_clip: float


@dataclass(frozen=True)
class GenerationConfig:
    data: dict[str, Any]
    width: int
    height: int
    seed: int
    loras: tuple[LoraSpec, ...]

    @property
    def mode(self) -> str:
        return self.data["mode"]


def parse_config(raw: str, *, need_model: bool, need_clip: bool, need_vae: bool, seed: Any) -> GenerationConfig:
    try:
        incoming = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"KREA 2 · One Node configuration is not valid JSON: {exc.msg}") from exc
    if not isinstance(incoming, dict):
        raise ValueError("KREA 2 · One Node configuration must be a JSON object.")

    incoming_version = int(incoming.get("version", 1) or 1)
    if incoming_version < 2:
        incoming = deepcopy(incoming)
        incoming["version"] = 2
        if not str(incoming.get("negative_prompt", "")).strip():
            incoming["negative_prompt"] = DEFAULT_FILM_NEGATIVE
        if (
            incoming.get("custom_resolution", False) is False
            and int(incoming.get("width", 1024) or 1024) == 1024
            and int(incoming.get("height", 1024) or 1024) == 1024
        ):
            incoming.update(width=1928, height=1088, aspect_ratio="16:9", megapixels=2.0)
        if isinstance(incoming.get("res4lyf"), dict) and incoming["res4lyf"].get("enabled", True):
            refinement = incoming.setdefault("refinement", {})
            if isinstance(refinement, dict):
                refinement["enabled"] = True
        decode = incoming.setdefault("vae_decode", {})
        if isinstance(decode, dict) and decode.get("mode", "auto") == "auto":
            decode.update(mode="tiled", tile_size=256, overlap=64)
    if incoming_version < 3:
        incoming = deepcopy(incoming)
        incoming["version"] = 3
        i2i_migration = incoming.setdefault("i2i", {})
        if isinstance(i2i_migration, dict):
            i2i_migration["fit_mode"] = "fit"
            i2i_migration.setdefault("identity_lora", "")

    data = _merge(DEFAULT_CONFIG, incoming)
    mode = str(data.get("mode", "t2i")).lower()
    if mode not in {"t2i", "i2i", "control"}:
        raise ValueError(f"Unsupported KREA 2 mode: {mode}")
    data["mode"] = mode

    alignment = _integer(data.get("alignment", 8), "Resolution alignment", 8, 32)
    if alignment not in {8, 16, 32}:
        raise ValueError("Resolution alignment must be 8, 16, or 32.")
    width, height = validate_dimensions(
        _integer(data.get("width"), "Width", 64, 16384),
        _integer(data.get("height"), "Height", 64, 16384),
        alignment,
    )
    data["width"], data["height"] = width, height
    data["batch_size"] = _integer(data.get("batch_size", 1), "Batch size", 1, 16)
    data["steps"] = _integer(data.get("steps", 8), "Steps", 1, 1000)
    data["cfg"] = _number(data.get("cfg", 1), "CFG", 0, 100)
    data["denoise"] = _number(data.get("denoise", 1), "Denoise", 0, 1)
    data["seed"] = _integer(data.get("seed", 0), "Seed", 0, 2**63 - 1)
    used_seed = _integer(seed, "Used seed", 0, 2**63 - 1)
    data["prompt"] = str(data.get("prompt", ""))
    data["negative_prompt"] = str(data.get("negative_prompt", ""))
    data["custom_resolution"] = bool(data.get("custom_resolution", False))
    data["scroll_zoom"] = bool(data.get("scroll_zoom", False))
    data["theme"] = str(data.get("theme", "blue-snow"))
    if data["theme"] not in {"red-fire", "blue-snow", "crimson", "glass"}:
        raise ValueError("Studio theme must be Red Fire, Blue Snow, Crimson, or Glass.")
    data["save_path"] = str(data.get("save_path", "")).strip()
    if data["save_path"] and not Path(os.path.expandvars(data["save_path"])).expanduser().is_absolute():
        raise ValueError("Custom image save path must be an absolute folder path.")
    data["prompt_crafter_url"] = str(data.get("prompt_crafter_url", "")).strip()
    data["cinematic_style"] = str(data.get("cinematic_style", ""))
    if data["cinematic_style"] and data["cinematic_style"] not in CINEMATIC_STYLES:
        raise ValueError(f"Unknown cinematic style: {data['cinematic_style']}")
    if data.get("weight_dtype") not in {"default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"}:
        raise ValueError("Unsupported model weight dtype.")
    if data.get("clip_device") not in {"default", "cpu"}:
        raise ValueError("Text encoder device must be default or cpu.")

    samplers = tuple(comfy.samplers.KSampler.SAMPLERS)
    schedulers = tuple(comfy.samplers.KSampler.SCHEDULERS)
    if data["sampler"] not in samplers:
        raise ValueError(f"Sampler is not available in this ComfyUI install: {data['sampler']}")
    if data["scheduler"] not in schedulers:
        raise ValueError(f"Scheduler is not available in this ComfyUI install: {data['scheduler']}")

    res4lyf = _mapping(data, "res4lyf")
    res4lyf["enabled"] = bool(res4lyf.get("enabled", True))

    gguf = _mapping(data, "gguf")
    gguf["enabled"] = bool(gguf.get("enabled", False))
    gguf["model"] = str(gguf.get("model", ""))
    gguf["clip_enabled"] = bool(gguf.get("clip_enabled", False))
    gguf["clip"] = str(gguf.get("clip", ""))

    refinement = _mapping(data, "refinement")
    refinement["enabled"] = bool(refinement.get("enabled", True))
    refinement["steps"] = _integer(refinement.get("steps", 3), "Refinement steps", 1, 1000)
    refinement["cfg"] = _number(refinement.get("cfg", data["cfg"]), "Refinement CFG", 0, 100)
    refinement["denoise"] = _number(refinement.get("denoise", 0.27), "Refinement denoise", 0, 1)
    if refinement.get("sampler") not in samplers:
        raise ValueError(f"Refinement sampler is not available: {refinement.get('sampler')}")
    if refinement.get("scheduler") not in schedulers:
        raise ValueError(f"Refinement scheduler is not available: {refinement.get('scheduler')}")

    diversity = _mapping(data, "diversity")
    diversity["enabled"] = bool(diversity.get("enabled", False))
    diversity["strength"] = _number(diversity.get("strength", 0.08), "Diversity latent noise", 0, 1)
    diversity["eta"] = _number(diversity.get("eta", 0.75), "Diversity RES4LYF eta", 0, 2)

    decode = _mapping(data, "vae_decode")
    if decode.get("mode") not in {"auto", "normal", "tiled"}:
        raise ValueError("VAE decode mode must be auto, normal, or tiled.")
    decode["tile_size"] = _integer(decode.get("tile_size", 512), "VAE tile size", 64, 4096)
    decode["overlap"] = _integer(decode.get("overlap", 64), "VAE tile overlap", 0, 4096)
    if decode["overlap"] >= decode["tile_size"]:
        raise ValueError("VAE tile overlap must be smaller than tile size.")

    enhancer = _mapping(data, "enhancer")
    # Kept only for loading old workflow JSON. Film Studio no longer runs a prompt enhancer.
    enhancer["enabled"] = False
    if enhancer.get("behavior") not in {"light", "balanced", "detailed"}:
        raise ValueError("Prompt enhancer behavior must be light, balanced, or detailed.")
    enhancer["max_length"] = _integer(enhancer.get("max_length", 256), "Enhancer max length", 1, 4096)
    enhancer["temperature"] = _number(enhancer.get("temperature", 0.7), "Enhancer temperature", 0, 10)
    enhancer["top_k"] = _integer(enhancer.get("top_k", 64), "Enhancer Top K", 1, 10000)
    enhancer["top_p"] = _number(enhancer.get("top_p", 0.95), "Enhancer Top P", 0, 1)
    enhancer["repetition_penalty"] = _number(enhancer.get("repetition_penalty", 1.05), "Enhancer repetition penalty", 0, 10)
    enhancer["seed"] = _integer(enhancer.get("seed", 0), "Enhancer seed", 0, 2**63 - 1)

    i2i = _mapping(data, "i2i")
    if i2i.get("pipeline") not in {"latent", "identity_edit"}:
        raise ValueError("I2I pipeline must be latent or identity_edit.")
    i2i["denoise"] = _number(i2i.get("denoise", 0.65), "I2I denoise", 0, 1)
    if i2i.get("fit_mode") not in {"crop", "fit", "stretch"}:
        raise ValueError("I2I fit mode must be crop, fit, or stretch.")
    i2i["identity_lora"] = str(i2i.get("identity_lora", "")).strip()
    i2i["ref_boost"] = _number(i2i.get("ref_boost", 4), "Identity fidelity", 0, 1000)
    i2i["ref_boost_a"] = _number(i2i.get("ref_boost_a", 1), "Identity reference A boost", 0, 1000)
    i2i["grounding_px"] = _integer(i2i.get("grounding_px", 768), "Identity grounding pixels", 64, 8192)

    reference_mp = data.get("reference_downscale_mp", 1)
    if isinstance(reference_mp, str) and reference_mp.lower() == "original":
        data["reference_downscale_mp"] = "Original"
    else:
        data["reference_downscale_mp"] = _number(reference_mp, "Reference downscale megapixels", 0.05, 32)

    uploads = _mapping(data, "uploads")
    uploads["image"] = str(uploads.get("image", ""))
    uploads["image_2"] = str(uploads.get("image_2", ""))
    external = _mapping(data, "external")
    for key in ("model", "clip", "vae"):
        external[key] = bool(external.get(key, False))

    if mode == "i2i" and i2i.get("pipeline") == "identity_edit":
        selected_identity_lora = i2i["identity_lora"] or suggest_identity_edit_lora(folder_paths.get_filename_list("loras"))
        i2i["identity_lora"] = _filename("loras", selected_identity_lora, "KREA Identity Edit LoRA")

    if need_model:
        if gguf["enabled"]:
            gguf["model"] = _filename("unet_gguf", gguf.get("model", ""), "KREA GGUF model")
        else:
            data["model"] = _filename("diffusion_models", data.get("model", ""), "KREA model")
    if need_clip:
        if gguf["clip_enabled"]:
            gguf["clip"] = _filename("clip_gguf", gguf.get("clip", ""), "KREA GGUF text encoder")
        else:
            data["clip"] = _filename("text_encoders", data.get("clip", ""), "KREA text encoder")
    if need_vae:
        data["vae"] = _filename("vae", data.get("vae", ""), "KREA VAE")

    loras: list[LoraSpec] = []
    raw_loras = data.get("loras") or []
    if not isinstance(raw_loras, list):
        raise ValueError("loras must be a list.")
    for index, item in enumerate(raw_loras):
        if not isinstance(item, dict) or item.get("enabled", True) is False:
            continue
        name = _filename("loras", item.get("name", ""), f"LoRA #{index + 1}", required=False)
        if not name:
            continue
        loras.append(
            LoraSpec(
                name=name,
                strength_model=_number(item.get("strength_model", item.get("strength", 1)), "LoRA model strength", -100, 100),
                strength_clip=_number(item.get("strength_clip", item.get("strength", 1)), "LoRA CLIP strength", -100, 100),
            )
        )

    if mode == "control":
        control = _mapping(data, "control")
        control["lora"] = _filename("loras", control.get("lora", ""), "KREA control LoRA")
        control["strength"] = _number(control.get("strength", 1), "Control strength", -100, 100)
        if control.get("resize") not in {"keep_control_image_size", "match_latent_size"}:
            raise ValueError("Unsupported control resize mode.")
        if control.get("upscale_method") not in {"lanczos", "bicubic", "bilinear", "area", "nearest-exact"}:
            raise ValueError("Unsupported control upscale method.")
        if control.get("crop") not in {"center", "disabled"}:
            raise ValueError("Unsupported control crop mode.")
        if control.get("channel_mode") not in {"rgb", "grayscale"}:
            raise ValueError("Unsupported control channel mode.")
        if control.get("normalize") not in {"none", "per_image_minmax"}:
            raise ValueError("Unsupported control normalization mode.")
        if control.get("preprocessor") not in {"none", "depth_anything_v2"}:
            raise ValueError("Unsupported control preprocessor.")
        control["preprocessor_resolution"] = _integer(
            control.get("preprocessor_resolution", 1024), "Control preprocessor resolution", 64, 8192
        )

    return GenerationConfig(data=data, width=width, height=height, seed=used_seed, loras=tuple(loras))
