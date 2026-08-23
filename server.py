"""Local-only model discovery, gallery, and metadata routes."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import uuid
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout, web
import comfy.samplers
import folder_paths
from server import PromptServer

from .providers import Krea2Provider
from .config import suggest_identity_edit_lora
from .settings import PRESETS, default_config
from .styles import style_payload


OUTPUT_SUBFOLDER = "krea2-one-node"
METADATA_SUBFOLDER = "metadata"
ASSET_LOCK = asyncio.Lock()
MANAGED_FILES = (
    {
        "id": "canon_ultrareal",
        "folder": "loras",
        "subfolder": "Krea 2",
        "filename": "canon_krea2.safetensors",
        "aliases": (
            r"canon.*(?:krea.?2|ultra.?real).*\.safetensors$",
            r"(?:krea.?2|ultra.?real).*canon.*\.safetensors$",
            r"ultra.?real.*krea.?2.*\.safetensors$",
        ),
        "url": "https://civitai.com/api/download/models/3134717",
        "sha256": "3295DEC59AB1195631FE9B3DD3493BA9C1546056DA86179CC3119C4B029420CE",
    },
    {
        "id": "cinematic_movie_still",
        "folder": "loras",
        "subfolder": "Krea 2",
        "filename": "cinematic_movie_still_krea2.safetensors",
        "aliases": (
            r"cinematic.*movie.*still.*krea.?2.*\.safetensors$",
            r"krea.?2.*cinematic.*movie.*still.*\.safetensors$",
        ),
        "url": "https://civitai.com/api/download/models/3206785",
        "sha256": "94A23A044D718FF050E3CA595BB9840EDD93384FB6ED86DAE13FDFA1C2EE5B4E",
    },
    {
        "id": "identity_edit_v1_2",
        "folder": "loras",
        "subfolder": "Krea 2",
        "filename": "krea2_identity_edit_v1_2.safetensors",
        "aliases": (
            r"krea.?2.*identity.*edit.*v1[_-]?2\.safetensors$",
        ),
        "url": "https://huggingface.co/conradlocke/krea2-identity-edit/resolve/main/krea2_identity_edit_v1_2.safetensors",
        "sha256": "6ADF9A69CC9502D286DB7B69964D37DA7E9CFE4B05B4D004BC275F087D3FD3CF",
    },
    {
        "id": "depth_control",
        "folder": "loras",
        "subfolder": "Krea 2",
        "filename": "depth-control-lora.safetensors",
        "url": "https://huggingface.co/Patil/Krea-2-depth-controlnet/resolve/main/depth-control-lora.safetensors",
        "sha256": "FB80547ED79B47C1E3FEA7BB9D36297E3917B2115FAB6700CA1501350F9F483C",
    },
    {
        "id": "wan_2_1_vae",
        "folder": "vae",
        "subfolder": "",
        "filename": "wan_2.1_vae.safetensors",
        "url": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
        "sha256": "2FC39D31359A4B0A64F55876D8FF7FA8D780956AE2CB13463B0223E15148976B",
    },
)


def _route(method: str, path: str):
    """Register when running under ComfyUI, but keep offline imports testable."""

    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        return lambda function: function
    return getattr(instance.routes, method)(path)


def _safe_path(base: str, subfolder: str = "", filename: str = "") -> Path:
    root = Path(base).resolve()
    target = (root / subfolder / filename).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid path.") from exc
    return target


def _metadata_path(image_path: Path) -> Path:
    return image_path.parent / METADATA_SUBFOLDER / f"{image_path.stem}.json"


def _validate_image_path(path: Path) -> Path:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Only image files are supported.")
    return path


def _listed(folder: str) -> list[str]:
    try:
        return folder_paths.get_filename_list(folder)
    except KeyError:
        return []


def _installed_asset(spec: dict[str, str]) -> Path | None:
    for name in _listed(spec["folder"]):
        if _asset_name_matches(spec, name):
            path = folder_paths.get_full_path_or_raise(spec["folder"], name)
            return Path(path)
    return None


def _asset_name_matches(spec: dict[str, Any], name: str) -> bool:
    basename = Path(str(name).replace("\\", "/")).name.casefold()
    if basename == spec["filename"].casefold():
        return True
    return any(re.search(pattern, basename, re.IGNORECASE) for pattern in spec.get("aliases", ()))


async def _download_managed_file(session: ClientSession, spec: dict[str, str]) -> dict[str, Any]:
    installed = _installed_asset(spec)
    if installed is not None:
        return {"id": spec["id"], "status": "installed", "path": str(installed), "changed": False}
    roots = folder_paths.get_folder_paths(spec["folder"])
    if not roots:
        raise RuntimeError(f"ComfyUI has no models/{spec['folder']} directory configured.")
    destination = (Path(roots[0]) / spec["subfolder"] / spec["filename"]).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    digest = hashlib.sha256()
    try:
        async with session.get(spec["url"], allow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                async for chunk in response.content.iter_chunked(4 * 1024 * 1024):
                    handle.write(chunk)
                    digest.update(chunk)
        actual = digest.hexdigest().upper()
        if actual != spec["sha256"]:
            raise RuntimeError(f"Checksum mismatch for {spec['filename']}: {actual}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"id": spec["id"], "status": "downloaded", "path": str(destination), "changed": True}


async def _ensure_control_nodes() -> dict[str, Any]:
    target = Path(__file__).resolve().parent.parent / "comfyui-krea2-controlnet"
    if target.is_dir():
        return {"id": "control_nodes", "status": "installed", "path": str(target), "changed": False}
    process = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "https://github.com/facok/comfyui-krea2-controlnet", str(target),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"ControlNet node install failed: {stderr.decode(errors='replace').strip()}")
    return {"id": "control_nodes", "status": "downloaded", "path": str(target), "changed": True, "restart_required": True}


async def _ensure_res4lyf_nodes() -> dict[str, Any]:
    target = Path(__file__).resolve().parent.parent / "RES4LYF"
    if target.is_dir():
        return {"id": "res4lyf_nodes", "status": "installed", "path": str(target), "changed": False}
    process = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "https://github.com/ClownsharkBatwing/RES4LYF", str(target),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await process.communicate()
    if process.returncode:
        raise RuntimeError(f"RES4LYF node install failed: {stderr.decode(errors='replace').strip()}")
    return {"id": "res4lyf_nodes", "status": "downloaded", "path": str(target), "changed": True, "restart_required": True}


def _model_payload() -> dict[str, Any]:
    models = _listed("diffusion_models")
    clips = _listed("text_encoders")
    vaes = _listed("vae")
    loras = _listed("loras")
    gguf_models = _listed("unet_gguf")
    gguf_clips = _listed("clip_gguf")
    by_basename = lambda values, filename: next(
        (name for name in values if Path(name.replace("\\", "/")).name.lower() == filename.lower()), ""
    )
    recommended_loras = [
        name for spec in MANAGED_FILES[:2]
        if (name := next((candidate for candidate in loras if _asset_name_matches(spec, candidate)), ""))
    ]
    return {
        "diffusion_models": models,
        "text_encoders": clips,
        "vaes": vaes,
        "loras": loras,
        "gguf_models": gguf_models,
        "gguf_text_encoders": gguf_clips,
        "samplers": list(comfy.samplers.KSampler.SAMPLERS),
        "schedulers": list(comfy.samplers.KSampler.SCHEDULERS),
        "suggested": {
            "model": next((name for name in models if "krea2" in name.lower() and "turbo" in name.lower()), "")
            or next((name for name in models if "krea2" in name.lower() or "krea-2" in name.lower()), ""),
            "gguf_model": next(
                (name for name in gguf_models if "krea2" in name.lower() or "krea-2" in name.lower()),
                gguf_models[0] if gguf_models else "",
            ),
            "gguf_clip": next(
                (name for name in gguf_clips if "qwen3vl" in name.lower() or "qwen3-vl" in name.lower()),
                gguf_clips[0] if gguf_clips else "",
            ),
            "clip": next((name for name in clips if "qwen3vl_4b" in name.lower()), ""),
            "vae": by_basename(vaes, "wan_2.1_vae.safetensors")
            or next((name for name in vaes if "qwen_image_vae" in name.lower()), ""),
            "managed_loras": recommended_loras,
            "identity_lora": suggest_identity_edit_lora(loras),
            "control_lora": by_basename(loras, "depth-control-lora.safetensors"),
        },
        "paths": {
            "model": "/models/diffusion_models",
            "gguf_model": "/models/diffusion_models or /models/unet · .gguf",
            "clip": "/models/text_encoders",
            "gguf_clip": "/models/text_encoders or /models/clip · .gguf",
            "vae": "/models/vae",
            "loras": "/models/loras",
        },
        "capabilities": Krea2Provider().capabilities(),
    }


@_route("get", "/krea2_one/models")
async def models(request: web.Request) -> web.Response:
    if request.query.get("refresh") == "1":
        folder_paths.cache_helper.clear()
    return web.json_response(_model_payload())


@_route("get", "/krea2_one/defaults")
async def defaults(_request: web.Request) -> web.Response:
    return web.json_response({"config": default_config(), "presets": PRESETS, "styles": style_payload()})


@_route("post", "/krea2_one/ensure_assets")
async def ensure_assets(_request: web.Request) -> web.Response:
    """Install the requested Film Studio assets once, with fixed hashes and paths."""

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    async with ASSET_LOCK:
        timeout = ClientTimeout(total=None, connect=30, sock_read=120)
        async with ClientSession(timeout=timeout, headers={"User-Agent": "Krea2-Film-Studio/1.0"}) as session:
            for spec in MANAGED_FILES:
                try:
                    results.append(await _download_managed_file(session, spec))
                except (ClientError, OSError, RuntimeError, web.HTTPException) as exc:
                    errors.append(str(exc))
        try:
            results.append(await _ensure_control_nodes())
        except (OSError, RuntimeError) as exc:
            errors.append(str(exc))
        try:
            results.append(await _ensure_res4lyf_nodes())
        except (OSError, RuntimeError) as exc:
            errors.append(str(exc))
        changed = any(item.get("changed") for item in results)
        if changed:
            folder_paths.cache_helper.clear()
    return web.json_response({
        "ok": not errors,
        "results": results,
        "errors": errors,
        "changed": changed,
        "restart_required": any(item.get("restart_required") for item in results),
    }, status=200 if not errors else 502)


@_route("get", "/krea2_one/gallery")
async def gallery(request: web.Request) -> web.Response:
    try:
        offset = max(0, int(request.query.get("offset", 0)))
        limit = min(100, max(1, int(request.query.get("limit", 30))))
    except ValueError:
        return web.json_response({"error": "Invalid pagination."}, status=400)

    output_root = folder_paths.get_output_directory()
    gallery_root = _safe_path(output_root, OUTPUT_SUBFOLDER)
    images: list[Path] = []
    if gallery_root.is_dir():
        images = sorted(
            (path for path in gallery_root.rglob("*.png") if METADATA_SUBFOLDER not in path.parts),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    items = []
    for path in images[offset : offset + limit]:
        rel_parent = path.parent.relative_to(Path(output_root).resolve()).as_posix()
        metadata = None
        meta_path = _metadata_path(path)
        if meta_path.is_file():
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = None
        items.append(
            {
                "filename": path.name,
                "subfolder": rel_parent,
                "type": "output",
                "mtime": path.stat().st_mtime,
                "metadata": metadata,
            }
        )
    return web.json_response({"items": items, "total": len(images), "offset": offset, "limit": limit})


@_route("post", "/krea2_one/metadata")
async def save_metadata(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        filename = str(payload.get("filename", ""))
        subfolder = str(payload.get("subfolder", ""))
        metadata = payload.get("metadata")
        if not filename or not isinstance(metadata, dict):
            return web.json_response({"ok": False, "error": "Filename and metadata are required."}, status=400)
        image_path = _validate_image_path(_safe_path(folder_paths.get_output_directory(), subfolder, filename))
        if not image_path.is_file():
            return web.json_response({"ok": False, "error": "Output image was not found."}, status=404)
        meta_path = _metadata_path(image_path)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = meta_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, meta_path)
        return web.json_response({"ok": True})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


@_route("post", "/krea2_one/save_temp")
async def save_temp(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        filename = str(payload.get("filename", ""))
        subfolder = str(payload.get("subfolder", ""))
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        source = _validate_image_path(_safe_path(folder_paths.get_temp_directory(), subfolder, filename))
        if not source.is_file():
            return web.json_response({"ok": False, "error": "Temporary image was not found."}, status=404)
        destination_dir = _safe_path(folder_paths.get_output_directory(), OUTPUT_SUBFOLDER)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"KREA2_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.png"
        shutil.copy2(source, destination)
        if metadata:
            meta_path = _metadata_path(destination)
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return web.json_response(
            {"ok": True, "filename": destination.name, "subfolder": OUTPUT_SUBFOLDER, "type": "output"}
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


@_route("post", "/krea2_one/open_folder")
async def open_folder(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        path = _validate_image_path(_safe_path(
            folder_paths.get_output_directory(),
            str(payload.get("subfolder", "")),
            str(payload.get("filename", "")),
        ))
        if not path.is_file():
            return web.json_response({"ok": False, "error": "Output image was not found."}, status=404)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)], creationflags=0x08000000)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
        return web.json_response({"ok": True})
    except (ValueError, OSError) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


def _lora_metadata(name: str) -> dict[str, Any]:
    path = folder_paths.get_full_path_or_raise("loras", name)
    if not path.lower().endswith(".safetensors"):
        return {"triggers": []}
    with open(path, "rb") as handle:
        header_size = struct.unpack("<Q", handle.read(8))[0]
        if header_size > 100 * 1024 * 1024:
            return {"triggers": []}
        header = json.loads(handle.read(header_size).decode("utf-8"))
    metadata = header.get("__metadata__", {})
    values = []
    for key in ("modelspec.trigger_phrase", "trigger_phrase", "trigger_word"):
        value = metadata.get(key)
        if isinstance(value, str):
            values.extend(part.strip() for part in value.split(",") if part.strip())
    raw = metadata.get("ss_trigger_words")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                values.extend(str(value).strip() for value in parsed if str(value).strip())
        except json.JSONDecodeError:
            values.extend(part.strip() for part in raw.split(",") if part.strip())
    return {"triggers": list(dict.fromkeys(values))}


@_route("get", "/krea2_one/lora_metadata")
async def lora_metadata(request: web.Request) -> web.Response:
    name = request.query.get("name", "")
    try:
        return web.json_response({"ok": True, **_lora_metadata(name)})
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError, struct.error, UnicodeDecodeError) as exc:
        return web.json_response({"ok": False, "error": str(exc), "triggers": []}, status=404)
