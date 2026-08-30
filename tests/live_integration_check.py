"""Read-only graph-expansion check against this machine's live ComfyUI install."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(TEST_ROOT))
import conftest  # noqa: E402,F401

import folder_paths  # noqa: E402
import nodes as comfy_nodes  # noqa: E402

from Krea2OneNode.nodes import Krea2OneNode  # noqa: E402
from Krea2OneNode.settings import default_config  # noqa: E402


COMFY_ROOT = Path(r"S:\AI\ComfyUI\ComfyUI")


def load_mappings(path: Path, module_name: str) -> None:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    comfy_nodes.NODE_CLASS_MAPPINGS.update(module.NODE_CLASS_MAPPINGS)


def choose(folder: str, predicate) -> str:
    values = folder_paths.get_filename_list(folder)
    return next(value for value in values if predicate(value.lower()))


def types(result: dict) -> list[str]:
    return sorted(node["class_type"] for node in result["expand"].values())


def main() -> None:
    load_mappings(COMFY_ROOT / "custom_nodes/comfyui-krea2-controlnet/nodes.py", "live_krea_control")
    load_mappings(COMFY_ROOT / "custom_nodes/comfyui-krea2edit/__init__.py", "live_krea_edit")

    config = default_config()
    config.update(
        model=choose("diffusion_models", lambda name: "krea2" in name),
        clip=choose("text_encoders", lambda name: "qwen3vl_4b" in name),
        vae=choose("vae", lambda name: "wan_2.1_vae" in name),
        randomize_seed=False,
        seed=20260812,
    )

    t2i = Krea2OneNode().expand(json.dumps(config), unique_id="live-t2i")
    config["mode"] = "i2i"
    latent_i2i = Krea2OneNode().expand(json.dumps(config), unique_id="live-i2i", image=["source", 0])
    config["i2i"]["pipeline"] = "identity_edit"
    identity = Krea2OneNode().expand(json.dumps(config), unique_id="live-edit", image=["source", 0], image_2=["subject", 0])
    config["mode"] = "control"
    config["control"]["lora"] = choose("loras", lambda name: "depth-control" in name)
    control = Krea2OneNode().expand(json.dumps(config), unique_id="live-control", image=["control", 0])

    print(json.dumps({
        "selected": {key: config[key] for key in ("model", "clip", "vae")},
        "t2i": types(t2i),
        "i2i": types(latent_i2i),
        "identity_edit": types(identity),
        "control": types(control),
    }, indent=2))


if __name__ == "__main__":
    main()
