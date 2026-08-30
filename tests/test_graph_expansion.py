from __future__ import annotations

import json
import unittest
from unittest import mock

import conftest  # noqa: F401 - installs package and ComfyUI paths
import folder_paths
import nodes as comfy_nodes
import torch

from Krea2OneNode.nodes import Krea2DiversityNoise, Krea2MultiReferenceEncode, Krea2OneNode
from Krea2OneNode.settings import DEFAULT_FILM_NEGATIVE, default_config


FILES = {
    "diffusion_models": ["krea2.safetensors"],
    "unet_gguf": ["Krea 2/krea2-Q4_K_M.gguf"],
    "text_encoders": ["qwen3vl_4b.safetensors"],
    "clip_gguf": ["Krea 2/qwen3vl_4b-Q4_K_M.gguf"],
    "vae": ["qwen_image_vae.safetensors"],
    "loras": [
        "style-a.safetensors",
        "style-b.safetensors",
        "depth-control.safetensors",
        "Krea 2/krea2_identity_edit_v1_2.safetensors",
    ],
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
    value["res4lyf"]["enabled"] = False
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
        required = {"UNETLoader", "CLIPLoader", "VAELoader", "CLIPTextEncode", "KSampler", "SaveImage"}
        self.assertTrue(required <= set(types))
        self.assertTrue({"VAEDecode", "VAEDecodeTiled"} & set(types))
        self.assertIn(result["result"][0][0], result["expand"])
        self.assertIn(result["result"][1][0], result["expand"])
        self.assertEqual(result["result"][2], 1234)

    def test_res4lyf_is_enabled_by_default(self) -> None:
        defaults = default_config()
        self.assertTrue(defaults["res4lyf"]["enabled"])
        self.assertEqual((defaults["width"], defaults["height"]), (1928, 1088))
        self.assertEqual(defaults["aspect_ratio"], "16:9")
        self.assertEqual(defaults["megapixels"], 2.0)
        self.assertEqual(defaults["negative_prompt"], DEFAULT_FILM_NEGATIVE)
        self.assertTrue(defaults["refinement"]["enabled"])
        self.assertFalse(defaults["gguf"]["enabled"])
        self.assertFalse(defaults["gguf"]["clip_enabled"])
        self.assertFalse(defaults["diversity"]["enabled"])
        self.assertEqual(defaults["theme"], "blue-snow")
        self.assertEqual(defaults["multi_reference"]["vision_megapixels"], 0.3)
        self.assertEqual(set(defaults["uploads"]), {"image", "image_2", "image_3", "image_4"})

    def test_multi_reference_mode_preserves_ordered_image_slots(self) -> None:
        value = config()
        value["mode"] = "references"
        value["prompt"] = "Place Image 1 beside Image 2 using Image 3 for the environment."
        result = Krea2OneNode().expand(
            json.dumps(value),
            unique_id="references",
            image=["source-a", 0],
            image_2=["source-b", 0],
            image_3=["source-c", 0],
        )
        encoders = nodes_of_type(result, "Krea2MultiReferenceEncode")
        self.assertEqual(len(encoders), 1)
        inputs = encoders[0]["inputs"]
        self.assertEqual(inputs["image1"], ["source-a", 0])
        self.assertEqual(inputs["image2"], ["source-b", 0])
        self.assertEqual(inputs["image3"], ["source-c", 0])
        self.assertEqual(inputs["vision_megapixels"], 0.3)
        self.assertEqual(inputs["vision_position"], "before prompt")
        self.assertNotIn("VAEEncode", class_types(result))

    def test_multi_reference_vision_prompt_numbers_each_image(self) -> None:
        image = torch.zeros((1, 256, 512, 3))
        prepared, prompt = Krea2MultiReferenceEncode._prepare_vision([image, image], 0.1)
        self.assertEqual(len(prepared), 2)
        self.assertIn("Image 1 (Picture 1)", prompt)
        self.assertIn("Image 2 (Picture 2)", prompt)
        self.assertLessEqual(prepared[0].shape[1] * prepared[0].shape[2], int(0.1 * 1024 * 1024) + 1024)

    def test_gguf_toggle_uses_installed_loader(self) -> None:
        value = config()
        value["gguf"] = {"enabled": True, "model": "Krea 2\\krea2-Q4_K_M.gguf"}
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"UnetLoaderGGUF": object}):
            result = Krea2OneNode().expand(json.dumps(value), unique_id="gguf")
        self.assertNotIn("UNETLoader", class_types(result))
        loaders = nodes_of_type(result, "UnetLoaderGGUF")
        self.assertEqual(len(loaders), 1)
        self.assertEqual(loaders[0]["inputs"]["unet_name"], "Krea 2/krea2-Q4_K_M.gguf")

    def test_gguf_toggle_reports_missing_custom_node(self) -> None:
        value = config()
        value["gguf"] = {"enabled": True, "model": "Krea 2/krea2-Q4_K_M.gguf"}
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ComfyUI-GGUF"):
                Krea2OneNode().expand(json.dumps(value), unique_id="gguf-missing")

    def test_gguf_text_encoder_toggle_uses_installed_loader(self) -> None:
        value = config()
        value["gguf"].update(clip_enabled=True, clip="Krea 2\\qwen3vl_4b-Q4_K_M.gguf")
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"CLIPLoaderGGUF": object}):
            result = Krea2OneNode().expand(json.dumps(value), unique_id="gguf-clip")
        self.assertNotIn("CLIPLoader", class_types(result))
        loaders = nodes_of_type(result, "CLIPLoaderGGUF")
        self.assertEqual(len(loaders), 1)
        self.assertEqual(loaders[0]["inputs"]["clip_name"], "Krea 2/qwen3vl_4b-Q4_K_M.gguf")
        self.assertEqual(loaders[0]["inputs"]["type"], "krea2")
        self.assertNotIn("device", loaders[0]["inputs"])

    def test_gguf_text_encoder_toggle_reports_missing_custom_node(self) -> None:
        value = config()
        value["gguf"].update(clip_enabled=True, clip="Krea 2/qwen3vl_4b-Q4_K_M.gguf")
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "CLIPLoaderGGUF"):
                Krea2OneNode().expand(json.dumps(value), unique_id="gguf-clip-missing")

    def test_diversity_noise_feeds_native_sampler(self) -> None:
        value = config()
        value["diversity"].update(enabled=True, strength=0.12, eta=0.8)
        result = Krea2OneNode().expand(json.dumps(value), unique_id="diverse-native")
        noise = nodes_of_type(result, "Krea2DiversityNoise")
        self.assertEqual(len(noise), 1)
        self.assertEqual(noise[0]["inputs"]["strength"], 0.12)
        noise_id = next(node_id for node_id, node in result["expand"].items() if node is noise[0])
        first_sampler = nodes_of_type(result, "KSampler")[0]
        self.assertEqual(first_sampler["inputs"]["latent_image"], [noise_id, 0])

    def test_diversity_eta_reaches_both_res4lyf_passes(self) -> None:
        value = config()
        value["res4lyf"]["enabled"] = True
        value["diversity"].update(enabled=True, strength=0.08, eta=0.85)
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"ClownsharKSampler_Beta": object, "VAEEncodeAdvanced": object}):
            result = Krea2OneNode().expand(json.dumps(value), unique_id="diverse-res4lyf")
        samplers = nodes_of_type(result, "ClownsharKSampler_Beta")
        self.assertEqual([node["inputs"]["eta"] for node in samplers], [0.85, 0.85])

    def test_custom_save_path_uses_custom_saver_and_temp_preview(self) -> None:
        value = config()
        value["save_path"] = r"S:\Film Renders"
        result = Krea2OneNode().expand(json.dumps(value), unique_id="custom-save")
        savers = nodes_of_type(result, "Krea2SaveImage")
        self.assertEqual(len(savers), 1)
        self.assertEqual(savers[0]["inputs"]["output_path"], r"S:\Film Renders")
        self.assertEqual(len(nodes_of_type(result, "PreviewImage")), 1)
        self.assertNotIn("SaveImage", class_types(result))

    def test_diversity_noise_is_seeded_and_non_destructive(self) -> None:
        source = {"samples": torch.zeros((1, 16, 4, 4)), "batch_index": [0]}
        first = Krea2DiversityNoise().inject(source, 41, 0.1)[0]
        repeated = Krea2DiversityNoise().inject(source, 41, 0.1)[0]
        different = Krea2DiversityNoise().inject(source, 42, 0.1)[0]
        self.assertTrue(torch.equal(first["samples"], repeated["samples"]))
        self.assertFalse(torch.equal(first["samples"], different["samples"]))
        self.assertTrue(torch.equal(source["samples"], torch.zeros_like(source["samples"])))
        self.assertEqual(first["batch_index"], [0])

    def test_res4lyf_recommended_chain_uses_exact_settings(self) -> None:
        value = config()
        value["res4lyf"]["enabled"] = True
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"ClownsharKSampler_Beta": object, "VAEEncodeAdvanced": object}):
            result = Krea2OneNode().expand(json.dumps(value), unique_id="res4lyf")
        samplers = nodes_of_type(result, "ClownsharKSampler_Beta")
        self.assertEqual(len(samplers), 2)
        self.assertNotIn("KSampler", class_types(result))
        first, second = samplers
        first_id = next(node_id for node_id, node in result["expand"].items() if node is first)
        second_id = next(node_id for node_id, node in result["expand"].items() if node is second)
        self.assertEqual(first["inputs"]["eta"], 0.5)
        self.assertEqual(first["inputs"]["sampler_name"], "linear/euler")
        self.assertEqual(first["inputs"]["scheduler"], "beta")
        self.assertEqual(first["inputs"]["steps"], 15)
        self.assertEqual(first["inputs"]["steps_to_run"], 12)
        self.assertEqual(first["inputs"]["denoise"], 1.0)
        self.assertEqual(first["inputs"]["cfg"], 1.0)
        self.assertEqual(first["inputs"]["sampler_mode"], "standard")
        self.assertTrue(first["inputs"]["bongmath"])
        self.assertEqual(second["inputs"]["eta"], 0.5)
        self.assertEqual(second["inputs"]["sampler_name"], "exponential/res_4s_munthe-kaas")
        self.assertEqual(second["inputs"]["scheduler"], "kl_optimal")
        self.assertEqual(second["inputs"]["steps"], 15)
        self.assertEqual(second["inputs"]["steps_to_run"], 3)
        self.assertEqual(second["inputs"]["denoise"], 0.27)
        self.assertEqual(second["inputs"]["cfg"], 1.0)
        self.assertEqual(second["inputs"]["sampler_mode"], "standard")
        self.assertTrue(second["inputs"]["bongmath"])
        self.assertEqual(second["inputs"]["latent_image"], [first_id, 1])
        self.assertNotIn("options0", second["inputs"])
        decoder = nodes_of_type(result, "VAEDecodeTiled")[0]
        self.assertEqual(decoder["inputs"]["samples"], [second_id, 1])
        self.assertEqual(decoder["inputs"]["tile_size"], 256)
        self.assertEqual(decoder["inputs"]["temporal_size"], 4096)
        empty = nodes_of_type(result, "VAEEncodeAdvanced")[0]
        empty_id = next(node_id for node_id, node in result["expand"].items() if node is empty)
        self.assertEqual(first["inputs"]["latent_image"], [empty_id, 3])
        self.assertEqual(empty["inputs"]["latent_type"], "16_channels")

    def test_res4lyf_refinement_toggle_controls_the_second_pass(self) -> None:
        value = config()
        value["res4lyf"]["enabled"] = True
        value["refinement"]["enabled"] = False
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"ClownsharKSampler_Beta": object}):
            result = Krea2OneNode().expand(json.dumps(value), unique_id="res4lyf-single")
        samplers = nodes_of_type(result, "ClownsharKSampler_Beta")
        self.assertEqual(len(samplers), 1)
        first = samplers[0]
        first_id = next(node_id for node_id, node in result["expand"].items() if node is first)
        self.assertEqual(first["inputs"]["steps_to_run"], 15)
        decoder = nodes_of_type(result, "VAEDecodeTiled")[0]
        self.assertEqual(decoder["inputs"]["samples"], [first_id, 1])

    def test_legacy_prompt_enhancer_is_disabled(self) -> None:
        value = config()
        value["enhancer"]["enabled"] = True
        result = Krea2OneNode().expand(json.dumps(value), unique_id="no-enhancer")
        self.assertNotIn("TextGenerate", class_types(result))
        self.assertNotIn("Krea2PromptTemplate", class_types(result))

    def test_enabled_res4lyf_reports_missing_installation(self) -> None:
        value = config()
        value["res4lyf"]["enabled"] = True
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "RES4LYF recommended sampling is enabled"):
                Krea2OneNode().expand(json.dumps(value), unique_id="res4lyf-missing")

    def test_multiple_loras_form_one_model_and_clip_chain(self) -> None:
        value = config()
        value["loras"] = [
            {"name":"style-a.safetensors","strength_model":.8,"strength_clip":.7,"enabled":True},
            {"name":"style-b.safetensors","strength_model":.4,"strength_clip":.2,"enabled":True},
        ]
        result = Krea2OneNode().expand(json.dumps(value), unique_id="43")
        self.assertEqual(class_types(result).count("LoraLoader"), 2)

    def test_lora_paths_resolve_case_and_separator_differences(self) -> None:
        value = config()
        value["loras"] = [
            {"name":"User Folder/STYLE-A.SAFETENSORS","strength_model":.75,"strength_clip":.5,"enabled":True},
        ]
        result = Krea2OneNode().expand(json.dumps(value), unique_id="portable-lora")
        lora = nodes_of_type(result, "LoraLoader")[0]
        self.assertEqual(lora["inputs"]["lora_name"], "style-a.safetensors")
        self.assertEqual(lora["inputs"]["strength_model"], .75)

    def test_selected_cinematic_style_is_appended_at_queue_time(self) -> None:
        value = config()
        value["prompt"] = "A detective crossing a rain-soaked street"
        value["cinematic_style"] = "silver_thriller"
        result = Krea2OneNode().expand(json.dumps(value), unique_id="style")
        style_nodes = nodes_of_type(result, "Krea2PromptStyle")
        self.assertEqual(len(style_nodes), 1)
        self.assertEqual(style_nodes[0]["inputs"]["prompt"], value["prompt"])
        self.assertIn("Sony VENICE 2", style_nodes[0]["inputs"]["suffix"])

    def test_no_style_leaves_prompt_path_unchanged(self) -> None:
        result = Krea2OneNode().expand(json.dumps(config()), unique_id="no-style")
        self.assertNotIn("Krea2PromptStyle", class_types(result))

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
            value["prompt"] = "Place the person at a cafe table"
            result = Krea2OneNode().expand(json.dumps(value), unique_id="45", image=["source-a",0], image_2=["source-b",0])
        types = class_types(result)
        self.assertIn("Krea2EditModelPatch", types)
        self.assertEqual(types.count("Krea2EditGroundedEncode"), 2)
        self.assertEqual(types.count("LoraLoaderModelOnly"), 1)
        identity = nodes_of_type(result, "LoraLoaderModelOnly")[0]
        self.assertEqual(identity["inputs"]["lora_name"], "Krea 2/krea2_identity_edit_v1_2.safetensors")
        self.assertEqual(identity["inputs"]["strength_model"], 1.0)
        identity_id = next(node_id for node_id, node in result["expand"].items() if node is identity)
        patch = nodes_of_type(result, "Krea2EditModelPatch")[0]
        self.assertEqual(patch["inputs"]["model"], [identity_id, 0])
        self.assertEqual(patch["inputs"]["fit_mode"], "fit")
        self.assertEqual(
            {node["inputs"]["prompt"] for node in nodes_of_type(result, "Krea2EditGroundedEncode")},
            {"Place the person at a cafe table", ""},
        )
        self.assertIn("KSampler", types)

    def test_identity_edit_does_not_apply_required_lora_twice(self) -> None:
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"Krea2EditModelPatch":object,"Krea2EditGroundedEncode":object}):
            value = config()
            value["mode"] = "i2i"
            value["i2i"]["pipeline"] = "identity_edit"
            value["loras"] = [{
                "name": "Krea 2/krea2_identity_edit_v1_2.safetensors",
                "strength_model": 1,
                "strength_clip": 1,
                "enabled": True,
            }]
            result = Krea2OneNode().expand(json.dumps(value), unique_id="identity-once", image=["source",0])
        self.assertEqual(len(nodes_of_type(result, "LoraLoaderModelOnly")), 1)
        self.assertEqual(len(nodes_of_type(result, "LoraLoader")), 0)

    def test_identity_edit_lora_feeds_res4lyf_sampler_path(self) -> None:
        mappings = {
            "Krea2EditModelPatch": object,
            "Krea2EditGroundedEncode": object,
            "ClownsharKSampler_Beta": object,
            "VAEEncodeAdvanced": object,
        }
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, mappings):
            value = config()
            value["mode"] = "i2i"
            value["i2i"]["pipeline"] = "identity_edit"
            value["res4lyf"]["enabled"] = True
            result = Krea2OneNode().expand(json.dumps(value), unique_id="identity-res4lyf", image=["source",0])
        identity = nodes_of_type(result, "LoraLoaderModelOnly")[0]
        identity_id = next(node_id for node_id, node in result["expand"].items() if node is identity)
        patch = nodes_of_type(result, "Krea2EditModelPatch")[0]
        patch_id = next(node_id for node_id, node in result["expand"].items() if node is patch)
        self.assertEqual(patch["inputs"]["model"], [identity_id, 0])
        self.assertEqual(nodes_of_type(result, "ClownsharKSampler_Beta")[0]["inputs"]["model"], [patch_id, 0])
        self.assertNotIn("KSampler", class_types(result))

    def test_legacy_identity_edit_migrates_to_v12_fit_geometry(self) -> None:
        with mock.patch.dict(comfy_nodes.NODE_CLASS_MAPPINGS, {"Krea2EditModelPatch":object,"Krea2EditGroundedEncode":object}):
            value = config()
            value["version"] = 2
            value["mode"] = "i2i"
            value["i2i"].update(pipeline="identity_edit", fit_mode="crop")
            result = Krea2OneNode().expand(json.dumps(value), unique_id="identity-migration", image=["source",0])
        self.assertEqual(nodes_of_type(result, "Krea2EditModelPatch")[0]["inputs"]["fit_mode"], "fit")

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
