from __future__ import annotations

import json
import unittest
from unittest import mock

import conftest  # noqa: F401 - installs package and ComfyUI paths
import folder_paths
import nodes as comfy_nodes

from Krea2OneNode.nodes import Krea2OneNode
from Krea2OneNode.settings import default_config


FILES = {
    "diffusion_models": ["krea2.safetensors"],
    "text_encoders": ["qwen3vl_4b.safetensors"],
    "vae": ["qwen_image_vae.safetensors"],
    "loras": ["style-a.safetensors", "style-b.safetensors", "depth-control.safetensors"],
}


def config() -> dict:
    value = default_config()
    value.update(
        model="krea2.safetensors",
        clip="qwen3vl_4b.safetensors",
        vae="qwen_image_vae.safetensors",
        randomize_seed=False,
        seed=1234,
    )
    return value


def class_types(expansion: dict) -> list[str]:
    return [node["class_type"] for node in expansion["expand"].values()]


def nodes_of_type(expansion: dict, class_type: str) -> list[dict]:
    return [node for node in expansion["expand"].values() if node["class_type"] == class_type]


class GraphExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path_patches = (
            mock.patch.object(folder_paths, "get_filename_list", side_effect=lambda folder: list(FILES.get(folder, []))),
            mock.patch.object(folder_paths, "get_full_path_or_raise", side_effect=lambda folder, name: f"/models/{folder}/{name}"),
        )
        for patcher in self.path_patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.path_patches):
            patcher.stop()

    def test_t2i_uses_native_nodes_and_returns_same_execution_links(self) -> None:
        result = Krea2OneNode().expand(json.dumps(config()), unique_id="42")
        types = class_types(result)
        required = {"UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage"}
        self.assertTrue(required <= set(types))
        self.assertIn(result["result"][0][0], result["expand"])
        self.assertIn(result["result"][1][0], result["expand"])
        self.assertEqual(result["result"][2], 1234)

    def test_multiple_loras_form_one_model_and_clip_chain(self) -> None:
        value = config()
        value["loras"] = [
            {"name":"style-a.safetensors","strength_model":.8,"strength_clip":.7,"enabled":True},
            {"name":"style-b.safetensors","strength_model":.4,"strength_clip":.2,"enabled":True},
        ]
        result = Krea2OneNode().expand(json.dumps(value), unique_id="43")
        self.assertEqual(class_types(result).count("LoraLoader"), 2)

    def test_latent_i2i_uses_connected_image_and_repeats_batch(self) -> None:
        value = config()
        value.update(mode="i2i", batch_size=3)
        result = Krea2OneNode().expand(json.dumps(value), unique_id="44", image=["upstream", 0])
        types = class_types(result)
        self.assertNotIn("LoadImage", types)
        self.assertTrue({"Krea2ImageFit", "VAEEncode", "RepeatLatentBatch"} <= set(types))

    def test_identity_edit_uses_installed_krea_nodes(self) -> None:
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"Krea2EditModelPatch":object,"Krea2EditGroundedEncode":object}):
            value = config()
            value["mode"] = "i2i"
            value["i2i"]["pipeline"] = "identity_edit"
            result = Krea2OneNode().expand(json.dumps(value), unique_id="45", image=["source-a",0], image_2=["source-b",0])
        types = class_types(result)
        self.assertIn("Krea2EditModelPatch", types)
        self.assertEqual(types.count("Krea2EditGroundedEncode"), 2)

    def test_control_uses_control_lora_encode_and_apply(self) -> None:
        mappings = {name:object for name in ("Krea2ControlLoRALoader","Krea2ControlImageEncode","Krea2ControlApply")}
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, mappings):
            value = config()
            value["mode"] = "control"
            value["control"]["lora"] = "depth-control.safetensors"
            result = Krea2OneNode().expand(json.dumps(value), unique_id="46", image=["control-map",0])
        self.assertTrue(set(mappings) <= set(class_types(result)))

    def test_external_loaders_override_empty_dropdowns(self) -> None:
        value = config()
        value.update(model="", clip="", vae="")
        value["external"] = {"model":True,"clip":True,"vae":True}
        result = Krea2OneNode().expand(json.dumps(value), unique_id="47", model=["model",0], clip=["clip",0], vae=["vae",0])
        types = class_types(result)
        self.assertNotIn("UNETLoader", types)
        self.assertNotIn("CLIPLoader", types)
        self.assertNotIn("VAELoader", types)

    def test_missing_model_has_readable_error(self) -> None:
        value = config()
        value["model"] = ""
        with self.assertRaisesRegex(ValueError, "Select a KREA model"):
            Krea2OneNode().expand(json.dumps(value), unique_id="48")

    def test_random_seed_is_generated_for_each_queue(self) -> None:
        value = config()
        value["randomize_seed"] = True
        with mock.patch("Krea2OneNode.nodes.secrets.randbelow", side_effect=[111, 222]):
            first = Krea2OneNode().expand(json.dumps(value), unique_id="49")
            second = Krea2OneNode().expand(json.dumps(value), unique_id="49")
        self.assertEqual(first["result"][2], 111)
        self.assertEqual(second["result"][2], 222)

    def test_large_fixed_seed_is_not_rounded(self) -> None:
        value = config()
        value["seed"] = 2**63 - 2
        result = Krea2OneNode().expand(json.dumps(value), unique_id="50")
        self.assertEqual(result["result"][2], 2**63 - 2)
        self.assertEqual(nodes_of_type(result, "KSampler")[0]["inputs"]["seed"], 2**63 - 2)

    def test_disabled_lora_is_removed_from_expansion(self) -> None:
        value = config()
        value["loras"] = [
            {"name":"style-a.safetensors","strength_model":1,"strength_clip":1,"enabled":False},
            {"name":"style-b.safetensors","strength_model":.5,"strength_clip":.25,"enabled":True},
        ]
        result = Krea2OneNode().expand(json.dumps(value), unique_id="51")
        loras = nodes_of_type(result, "LoraLoader")
        self.assertEqual(len(loras), 1)
        self.assertEqual(loras[0]["inputs"]["lora_name"], "style-b.safetensors")

    def test_model_selection_and_preview_mode_reach_native_nodes(self) -> None:
        FILES["diffusion_models"].append("krea2-turbo.safetensors")
        try:
            value = config()
            value["model"] = "krea2-turbo.safetensors"
            value["auto_save"] = False
            result = Krea2OneNode().expand(json.dumps(value), unique_id="52")
        finally:
            FILES["diffusion_models"].remove("krea2-turbo.safetensors")
        self.assertEqual(nodes_of_type(result, "UNETLoader")[0]["inputs"]["unet_name"], "krea2-turbo.safetensors")
        self.assertIn("PreviewImage", class_types(result))
        self.assertNotIn("SaveImage", class_types(result))
