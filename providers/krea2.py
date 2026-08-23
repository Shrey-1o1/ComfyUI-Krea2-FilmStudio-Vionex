"""Native ComfyUI graph expansion for KREA 2 generation."""

from __future__ import annotations

import logging
from typing import Any

import nodes as comfy_nodes
from comfy_execution.graph_utils import GraphBuilder, is_link

from ..config import GenerationConfig
from ..styles import style_suffix
from .base import BaseGenerationProvider, ExpansionResult


LOGGER = logging.getLogger("Krea2FilmStudio")


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
            "depth_preprocessor": _node_available("AIO_Preprocessor"),
            "tiled_decode": _node_available("VAEDecodeTiled"),
            "res4lyf": _node_available("ClownsharKSampler_Beta"),
            "gguf_model": _node_available("UnetLoaderGGUF"),
            "gguf_clip": _node_available("CLIPLoaderGGUF"),
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
    def _apply_loras(
        builder: GraphBuilder,
        model: list[Any],
        clip: list[Any],
        config: GenerationConfig,
        *,
        exclude: set[str] | None = None,
    ) -> tuple[list[Any], list[Any]]:
        excluded = {name.replace("\\", "/").casefold() for name in (exclude or set())}
        for spec in config.loras:
            if spec.name.replace("\\", "/").casefold() in excluded:
                continue
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
    def _empty_latent(builder: GraphBuilder, vae: list[Any], config: GenerationConfig) -> list[Any]:
        """Create the 16-channel KREA latent used by the supplied Film workflow."""

        if _node_available("VAEEncodeAdvanced"):
            latent = builder.node(
                "VAEEncodeAdvanced",
                vae=vae,
                resize_to_input="false",
                width=config.width,
                height=config.height,
                mask_channel="red",
                invert_mask=False,
                latent_type="16_channels",
                interpolation="lanczos",
                method="fill / crop",
            ).out(3)
        else:
            LOGGER.warning(
                "Krea 2 Film Studio: VAEEncodeAdvanced is unavailable; falling back to EmptyLatentImage."
            )
            latent = builder.node(
                "EmptyLatentImage",
                width=config.width,
                height=config.height,
                batch_size=1,
            ).out(0)
        if int(config.data["batch_size"]) > 1:
            latent = builder.node(
                "RepeatLatentBatch",
                samples=latent,
                amount=int(config.data["batch_size"]),
            ).out(0)
        return latent

    @staticmethod
    def _sample(builder: GraphBuilder, model: list[Any], positive: list[Any], negative: list[Any], latent: list[Any], config: GenerationConfig, denoise: float) -> list[Any]:
        data = config.data
        if data["res4lyf"].get("enabled", True):
            if not _node_available("ClownsharKSampler_Beta"):
                raise RuntimeError(
                    "RES4LYF recommended sampling is enabled, but ClownsharKSampler is unavailable. "
                    "Install RES4LYF and restart ComfyUI, or disable it in Film Studio Settings."
                )
            refinement = data["refinement"]
            refine_enabled = bool(refinement.get("enabled"))
            refine_steps = max(1, min(14, int(refinement.get("steps", 3))))
            primary_steps = max(1, 15 - refine_steps) if refine_enabled else 15
            eta = float(data["diversity"].get("eta", 0.75)) if data["diversity"].get("enabled") else 0.5
            LOGGER.info(
                "Krea 2 Film Studio: RES4LYF pass 1 linear/euler + beta, %s/15 steps, denoise %.2f.",
                primary_steps,
                denoise,
            )
            first = builder.node(
                "ClownsharKSampler_Beta",
                model=model,
                positive=positive,
                negative=negative,
                latent_image=latent,
                eta=eta,
                sampler_name="linear/euler",
                scheduler="beta",
                steps=15,
                steps_to_run=primary_steps,
                denoise=float(denoise),
                cfg=1.0,
                seed=config.seed,
                sampler_mode="standard",
                bongmath=True,
            )
            if not refine_enabled:
                LOGGER.info("Krea 2 Film Studio: refinement disabled; decoding pass 1 denoised latent.")
                return first.out(1)

            LOGGER.info(
                "Krea 2 Film Studio: RES4LYF refinement pass exponential/res_4s_munthe-kaas + kl_optimal, "
                "%s/15 steps, CFG %.2f, denoise %.2f.",
                refine_steps,
                float(refinement.get("cfg", 1.0)),
                float(refinement.get("denoise", 0.27)),
            )
            second = builder.node(
                "ClownsharKSampler_Beta",
                model=model,
                positive=positive,
                negative=negative,
                latent_image=first.out(1),
                eta=eta,
                sampler_name="exponential/res_4s_munthe-kaas",
                scheduler="kl_optimal",
                steps=15,
                steps_to_run=refine_steps,
                denoise=float(refinement.get("denoise", 0.27)),
                cfg=float(refinement.get("cfg", 1.0)),
                seed=config.seed,
                sampler_mode="standard",
                bongmath=True,
            )
            return second.out(1)

        LOGGER.info(
            "Krea 2 Film Studio: native KSampler pass 1, %s steps, %s/%s, CFG %.2f, denoise %.2f.",
            int(data["steps"]),
            data["sampler"],
            data["scheduler"],
            float(data["cfg"]),
            denoise,
        )
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
            LOGGER.info(
                "Krea 2 Film Studio: native refinement pass, %s steps, %s/%s, CFG %.2f, denoise %.2f.",
                int(refinement.get("steps", 3)),
                refinement.get("sampler", data["sampler"]),
                refinement.get("scheduler", data["scheduler"]),
                float(refinement.get("cfg", data["cfg"])),
                float(refinement.get("denoise", 0.27)),
            )
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
                temporal_size=4096,
                temporal_overlap=64,
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
        raw_model = raw_inputs.get("model")
        if is_link(raw_model):
            model = raw_model
        elif data["gguf"].get("enabled", False):
            if not caps["gguf_model"]:
                raise RuntimeError(
                    "GGUF model loading is enabled, but ComfyUI-GGUF did not register UnetLoaderGGUF. "
                    "Install or update ComfyUI-GGUF, restart ComfyUI, or disable GGUF in Film Studio Settings."
                )
            LOGGER.info("Krea 2 Film Studio: loading GGUF diffusion model %s.", data["gguf"]["model"])
            model = builder.node("UnetLoaderGGUF", unet_name=data["gguf"]["model"]).out(0)
        else:
            model = self._source(
                builder,
                raw_model,
                "UNETLoader",
                "unet_name",
                data["model"],
                weight_dtype=data["weight_dtype"],
            )
        raw_clip = raw_inputs.get("clip")
        if is_link(raw_clip):
            clip = raw_clip
        elif data["gguf"].get("clip_enabled", False):
            if not caps["gguf_clip"]:
                raise RuntimeError(
                    "GGUF text encoder loading is enabled, but ComfyUI-GGUF did not register CLIPLoaderGGUF. "
                    "Install or update ComfyUI-GGUF, restart ComfyUI, or disable the GGUF text encoder in Film Studio Settings."
                )
            LOGGER.info("Krea 2 Film Studio: loading GGUF text encoder %s.", data["gguf"]["clip"])
            clip = builder.node("CLIPLoaderGGUF", clip_name=data["gguf"]["clip"], type="krea2").out(0)
        else:
            clip = self._source(
                builder,
                raw_clip,
                "CLIPLoader",
                "clip_name",
                data["clip"],
                type="krea2",
                device=data["clip_device"],
            )
        vae = self._source(builder, raw_inputs.get("vae"), "VAELoader", "vae_name", data["vae"])

        if data["mode"] == "control":
            control = data["control"]
            model = builder.node(
                "Krea2ControlLoRALoader",
                model=model,
                lora_name=control["lora"],
                strength=float(control["strength"]),
            ).out(0)

        identity_lora = ""
        if data["mode"] == "i2i" and data["i2i"].get("pipeline") == "identity_edit":
            identity_lora = str(data["i2i"]["identity_lora"])
        model, clip = self._apply_loras(
            builder,
            model,
            clip,
            config,
            exclude={identity_lora} if identity_lora else None,
        )
        if identity_lora:
            LOGGER.info("Krea 2 Film Studio: applying required Identity Edit LoRA %s at model strength 1.0.", identity_lora)
            model = builder.node(
                "LoraLoaderModelOnly",
                model=model,
                lora_name=identity_lora,
                strength_model=1.0,
            ).out(0)
        prompt = raw_inputs.get("prompt") if is_link(raw_inputs.get("prompt")) else data["prompt"]
        suffix = style_suffix(str(data.get("cinematic_style", "")))
        if suffix:
            prompt = builder.node("Krea2PromptStyle", prompt=prompt, suffix=suffix).out(0)
        uploads = data["uploads"]

        if data["mode"] == "t2i":
            positive, negative = self._conditioning(builder, clip, prompt, str(data["negative_prompt"]))
            latent = self._empty_latent(builder, vae, config)
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
            latent = self._empty_latent(builder, vae, config)
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
            # Identity Edit was trained with an empty grounded unconditional prompt.
            neg_inputs["prompt"] = ""
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
            latent = self._empty_latent(builder, vae, config)
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

        if data["diversity"].get("enabled"):
            LOGGER.info(
                "Krea 2 Film Studio: diversity noise enabled, latent strength %.2f, RES4LYF eta %.2f.",
                float(data["diversity"]["strength"]),
                float(data["diversity"]["eta"]),
            )
            latent = builder.node(
                "Krea2DiversityNoise",
                latent=latent,
                seed=config.seed,
                strength=float(data["diversity"]["strength"]),
            ).out(0)

        sampled = self._sample(builder, model, positive, negative, latent, config, denoise)
        image = self._decode(builder, sampled, vae, config)
        save_path = str(data.get("save_path", "")).strip()
        if data.get("auto_save", True) and save_path:
            builder.node("Krea2SaveImage", images=image, output_path=save_path, filename_prefix="KREA2")
            output = builder.node("PreviewImage", images=image)
        else:
            output_type = "SaveImage" if data.get("auto_save", True) else "PreviewImage"
            output_inputs: dict[str, Any] = {"images": image}
            if output_type == "SaveImage":
                output_inputs["filename_prefix"] = "krea2-one-node/KREA2"
            output = builder.node(output_type, **output_inputs)
        output.set_override_display_id(str(raw_inputs.get("unique_id", "")))

        return ExpansionResult(graph=builder.finalize(), image=image, latent=sampled, seed=config.seed)
