"""Native ComfyUI graph expansion for KREA 2 generation."""

from __future__ import annotations

from typing import Any

import nodes as comfy_nodes
from comfy_execution.graph_utils import GraphBuilder, is_link

from ..config import GenerationConfig
from ..styles import style_suffix
from .base import BaseGenerationProvider, ExpansionResult


def _node_available(name: str) -> bool:
    return name in comfy_nodes.NODE_CLASS_MAPPINGS


class Krea2Provider(BaseGenerationProvider):
    """Builds native loader/conditioning/sampler nodes without owning model memory."""

    def capabilities(self) -> dict[str, Any]:
        return {
            "t2i": True,
            "i2i": True,
            "identity_edit": _node_available("Krea2EditModelPatch") and _node_available("Krea2EditGroundedEncode"),
            "control": all(_node_available(name) for name in (
                "Krea2ControlLoRALoader",
                "Krea2ControlImageEncode",
                "Krea2ControlApply",
            )),
            "prompt_enhancer": _node_available("TextGenerate"),
            "depth_preprocessor": _node_available("AIO_Preprocessor"),
            "tiled_decode": _node_available("VAEDecodeTiled"),
        }

    @staticmethod
    def _source(builder: GraphBuilder, raw: Any, loader_type: str, loader_input: str, value: str, **extra: Any) -> list[Any]:
        if is_link(raw):
            return raw
        return builder.node(loader_type, **{loader_input: value, **extra}).out(0)

    @staticmethod
    def _image_source(builder: GraphBuilder, raw: Any, filename: str, label: str) -> list[Any]:
        if is_link(raw):
            return raw
        if not filename:
            raise ValueError(f"{label} requires an uploaded image or connected IMAGE input.")
        return builder.node("LoadImage", image=filename).out(0)

    @staticmethod
    def _downscale(builder: GraphBuilder, image: list[Any], megapixels: Any) -> list[Any]:
        if megapixels in (None, "Original", "original", 0, 0.0):
            return image
        return builder.node("Krea2ReferenceDownscale", image=image, megapixels=float(megapixels)).out(0)

    @staticmethod
    def _enhance_prompt(builder: GraphBuilder, prompt: Any, clip: list[Any], cfg: dict[str, Any]) -> Any:
        enhancer = cfg["enhancer"]
        if not enhancer.get("enabled"):
            return prompt
        if not _node_available("TextGenerate"):
            raise RuntimeError("Prompt enhancement is enabled, but this ComfyUI build has no TextGenerate node.")
        templated = builder.node(
            "Krea2PromptTemplate",
            prompt=prompt,
            behavior=str(enhancer.get("behavior", "balanced")),
        )
        generated = builder.node(
            "TextGenerate",
            clip=clip,
            prompt=templated.out(0),
            max_length=int(enhancer.get("max_length", 256)),
            sampling_mode="on",
            **{
                "sampling_mode.temperature": float(enhancer.get("temperature", 0.7)),
                "sampling_mode.top_k": int(enhancer.get("top_k", 64)),
                "sampling_mode.top_p": float(enhancer.get("top_p", 0.95)),
                "sampling_mode.min_p": 0.05,
                "sampling_mode.repetition_penalty": float(enhancer.get("repetition_penalty", 1.05)),
                "sampling_mode.seed": int(enhancer.get("seed", 0)),
                "sampling_mode.presence_penalty": 0.0,
                "thinking": bool(enhancer.get("thinking", False)),
                "use_default_template": True,
            },
        )
        return generated.out(0)

    @staticmethod
    def _conditioning(builder: GraphBuilder, clip: list[Any], prompt: Any, negative: str) -> tuple[list[Any], list[Any]]:
        positive = builder.node("CLIPTextEncode", clip=clip, text=prompt)
        if negative.strip():
            negative_node = builder.node("CLIPTextEncode", clip=clip, text=negative)
        else:
            negative_node = builder.node("ConditioningZeroOut", conditioning=positive.out(0))
        return positive.out(0), negative_node.out(0)

    @staticmethod
    def _apply_loras(builder: GraphBuilder, model: list[Any], clip: list[Any], config: GenerationConfig) -> tuple[list[Any], list[Any]]:
        for spec in config.loras:
            node = builder.node(
                "LoraLoader",
                model=model,
                clip=clip,
                lora_name=spec.name,
                strength_model=spec.strength_model,
                strength_clip=spec.strength_clip,
            )
            model, clip = node.out(0), node.out(1)
        return model, clip

    @staticmethod
    def _sample(builder: GraphBuilder, model: list[Any], positive: list[Any], negative: list[Any], latent: list[Any], config: GenerationConfig, denoise: float) -> list[Any]:
        data = config.data
        sampler = builder.node(
            "KSampler",
            model=model,
            seed=config.seed,
            steps=int(data["steps"]),
            cfg=float(data["cfg"]),
            sampler_name=data["sampler"],
            scheduler=data["scheduler"],
            positive=positive,
            negative=negative,
            latent_image=latent,
            denoise=denoise,
        )
        sampled = sampler.out(0)
        refinement = data["refinement"]
        if refinement.get("enabled"):
            refined = builder.node(
                "KSampler",
                model=model,
                seed=config.seed,
                steps=int(refinement.get("steps", 3)),
                cfg=float(refinement.get("cfg", data["cfg"])),
                sampler_name=refinement.get("sampler", data["sampler"]),
                scheduler=refinement.get("scheduler", data["scheduler"]),
                positive=positive,
                negative=negative,
                latent_image=sampled,
                denoise=float(refinement.get("denoise", 0.27)),
            )
            sampled = refined.out(0)
        return sampled

    @staticmethod
    def _decode(builder: GraphBuilder, latent: list[Any], vae: list[Any], config: GenerationConfig) -> list[Any]:
        decode = config.data["vae_decode"]
        mode = str(decode.get("mode", "auto")).lower()
        tiled_available = _node_available("VAEDecodeTiled")
        if mode == "tiled" and not tiled_available:
            raise RuntimeError("Tiled VAE decode is selected, but this ComfyUI build has no VAEDecodeTiled node.")
        tiled = tiled_available and (mode == "tiled" or (mode == "auto" and config.width * config.height > 1_500_000))
        if tiled:
            node = builder.node(
                "VAEDecodeTiled",
                samples=latent,
                vae=vae,
                tile_size=int(decode.get("tile_size", 512)),
                overlap=int(decode.get("overlap", 64)),
                temporal_size=64,
                temporal_overlap=8,
            )
        else:
            node = builder.node("VAEDecode", samples=latent, vae=vae)
        return node.out(0)

    def expand(self, config: GenerationConfig, **raw_inputs: Any) -> ExpansionResult:
        data = config.data
        caps = self.capabilities()
        if data["mode"] == "control" and not caps["control"]:
            raise RuntimeError("CONTROL requires the installed comfyui-krea2-controlnet nodes. Restart after installing them.")
        if data["mode"] == "i2i" and data["i2i"].get("pipeline") == "identity_edit" and not caps["identity_edit"]:
            raise RuntimeError("Identity Edit requires the installed comfyui-krea2edit nodes.")

        builder = GraphBuilder()
        model = self._source(builder, raw_inputs.get("model"), "UNETLoader", "unet_name", data["model"], weight_dtype=data["weight_dtype"])
        clip = self._source(builder, raw_inputs.get("clip"), "CLIPLoader", "clip_name", data["clip"], type="krea2", device=data["clip_device"])
        vae = self._source(builder, raw_inputs.get("vae"), "VAELoader", "vae_name", data["vae"])

        if data["mode"] == "control":
            control = data["control"]
            model = builder.node(
                "Krea2ControlLoRALoader",
                model=model,
                lora_name=control["lora"],
                strength=float(control["strength"]),
            ).out(0)

        model, clip = self._apply_loras(builder, model, clip, config)
        prompt = raw_inputs.get("prompt") if is_link(raw_inputs.get("prompt")) else data["prompt"]
        suffix = style_suffix(str(data.get("cinematic_style", "")))
        if suffix:
            prompt = builder.node("Krea2PromptStyle", prompt=prompt, suffix=suffix).out(0)
        prompt = self._enhance_prompt(builder, prompt, clip, data)
        uploads = data["uploads"]

        if data["mode"] == "t2i":
            positive, negative = self._conditioning(builder, clip, prompt, str(data["negative_prompt"]))
            latent = builder.node(
                "EmptyLatentImage",
                width=config.width,
                height=config.height,
                batch_size=int(data["batch_size"]),
            ).out(0)
            denoise = 1.0

        elif data["mode"] == "i2i" and data["i2i"].get("pipeline") == "identity_edit":
            image = self._image_source(builder, raw_inputs.get("image"), uploads.get("image", ""), "Identity Edit")
            image = self._downscale(builder, image, data.get("reference_downscale_mp"))
            image_2 = None
            if is_link(raw_inputs.get("image_2")) or uploads.get("image_2"):
                image_2 = self._image_source(builder, raw_inputs.get("image_2"), uploads.get("image_2", ""), "Second reference")
                image_2 = self._downscale(builder, image_2, data.get("reference_downscale_mp"))
            source_latent = builder.node("VAEEncode", pixels=image, vae=vae).out(0)
            source_latent_2 = builder.node("VAEEncode", pixels=image_2, vae=vae).out(0) if image_2 else None
            latent = builder.node(
                "EmptyLatentImage",
                width=config.width,
                height=config.height,
                batch_size=int(data["batch_size"]),
            ).out(0)
            edit = data["i2i"]
            model_inputs: dict[str, Any] = {
                "model": model,
                "source_latent": source_latent,
                "ref_boost": float(edit.get("ref_boost", 4.0)),
                "ref_boost_a": float(edit.get("ref_boost_a", 1.0)),
                "fit_mode": "fit" if edit.get("fit_mode") != "crop" else "crop (legacy)",
                "vae": vae,
                "source_image": image,
                "target_latent": latent,
            }
            cond_inputs: dict[str, Any] = {
                "clip": clip,
                "prompt": prompt,
                "image": image,
                "grounding_px": int(edit.get("grounding_px", 768)),
                "system_prompt": "",
            }
            neg_inputs = dict(cond_inputs)
            neg_inputs["prompt"] = str(data["negative_prompt"])
            if image_2:
                model_inputs.update({"source_latent_b": source_latent_2, "source_image_b": image_2})
                cond_inputs["image_b"] = image_2
                neg_inputs["image_b"] = image_2
            model = builder.node("Krea2EditModelPatch", **model_inputs).out(0)
            positive = builder.node("Krea2EditGroundedEncode", **cond_inputs).out(0)
            negative = builder.node("Krea2EditGroundedEncode", **neg_inputs).out(0)
            denoise = 1.0

        elif data["mode"] == "i2i":
            positive, negative = self._conditioning(builder, clip, prompt, str(data["negative_prompt"]))
            image = self._image_source(builder, raw_inputs.get("image"), uploads.get("image", ""), "I2I")
            image = self._downscale(builder, image, data.get("reference_downscale_mp"))
            scaled = builder.node(
                "Krea2ImageFit",
                image=image,
                width=config.width,
                height=config.height,
                mode=data["i2i"].get("fit_mode", "crop"),
            ).out(0)
            latent = builder.node("VAEEncode", pixels=scaled, vae=vae).out(0)
            if int(data["batch_size"]) > 1:
                latent = builder.node("RepeatLatentBatch", samples=latent, amount=int(data["batch_size"])).out(0)
            denoise = float(data["i2i"].get("denoise", data["denoise"]))

        else:
            positive, negative = self._conditioning(builder, clip, prompt, str(data["negative_prompt"]))
            image = self._image_source(builder, raw_inputs.get("image"), uploads.get("image", ""), "CONTROL")
            image = self._downscale(builder, image, data.get("reference_downscale_mp"))
            control = data["control"]
            if control.get("preprocessor") == "depth_anything_v2":
                if not caps["depth_preprocessor"]:
                    raise RuntimeError("Depth preprocessing was selected, but AIO_Preprocessor is not installed.")
                image = builder.node(
                    "AIO_Preprocessor",
                    image=image,
                    preprocessor="DepthAnythingV2Preprocessor",
                    resolution=int(control.get("preprocessor_resolution", 1024)),
                ).out(0)
            latent = builder.node(
                "EmptyLatentImage",
                width=config.width,
                height=config.height,
                batch_size=int(data["batch_size"]),
            ).out(0)
            control_latent = builder.node(
                "Krea2ControlImageEncode",
                control_image=image,
                vae=vae,
                latent=latent,
                resize=control.get("resize", "match_latent_size"),
                upscale_method=control.get("upscale_method", "lanczos"),
                crop=control.get("crop", "center"),
                channel_mode=control.get("channel_mode", "rgb"),
                normalize=control.get("normalize", "none"),
                invert=bool(control.get("invert", False)),
                batch_mode="independent_images",
            ).out(0)
            model = builder.node("Krea2ControlApply", model=model, control_latent=control_latent).out(0)
            denoise = float(data["denoise"])

        sampled = self._sample(builder, model, positive, negative, latent, config, denoise)
        image = self._decode(builder, sampled, vae, config)
        output_type = "SaveImage" if data.get("auto_save", True) else "PreviewImage"
        output_inputs: dict[str, Any] = {"images": image}
        if output_type == "SaveImage":
            output_inputs["filename_prefix"] = "krea2-one-node/KREA2"
        output = builder.node(output_type, **output_inputs)
        output.set_override_display_id(str(raw_inputs.get("unique_id", "")))

        return ExpansionResult(graph=builder.finalize(), image=image, latent=sampled, seed=config.seed)
