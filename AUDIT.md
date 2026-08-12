# Phase 1 audit: installed KREA 2 stack

Audit target: `S:\AI\ComfyUI\ComfyUI` (read-only during development).

## KREA 2 implementation found

ComfyUI `0.31.1` contains native KREA 2 support:

- `comfy/ldm/krea2/model.py` — KREA 2 diffusion transformer.
- `comfy/model_base.py` — `Krea2` base-model integration.
- `comfy/supported_models.py` and `comfy/model_detection.py` — checkpoint detection.
- `comfy/text_encoders/krea2.py` — Qwen3-VL 4B KREA tokenizer/template and 12-layer tapped conditioning.
- `comfy/sd.py` — `CLIPType.KREA2` loader path.
- `comfy/lora.py` and `comfy/utils.py` — KREA 2 LoRA key mapping.

Installed KREA extensions:

- `custom_nodes/comfyui-krea2-controlnet/nodes.py`
  - `Krea2ControlLoRALoader`
  - `Krea2ControlImageEncode`
  - `Krea2ControlApply`
- `custom_nodes/comfyui-krea2edit/__init__.py`
  - `Krea2EditModelPatch`
  - `Krea2EditGroundedEncode`
- `custom_nodes/ComfyUI-Krea2T-Enhancer/`
  - model-side prompt-adherence patches (not prompt text generation).

## Existing One Node FLUX implementation found

`custom_nodes/one-node-flux-2-klein/` contains:

- `nodes.py` — local routes, model scanning, gallery metadata, and a last-preview `IMAGE` shim.
- `web/one_node_flux_2_klein.js` — application UI, modal/gallery/settings/upload handling, and client-side workflow queuing.
- `workflows/*.json` — separate backend prompt templates for each mode.

The visual language, modal behavior, uploads, settings, and gallery are reusable product concepts. Its execution/output shim was not copied: it queues a separate prompt and returns the previously saved preview on a later outer-graph execution. KREA 2 One Node instead uses ComfyUI graph expansion so downstream nodes receive the current generation in the same execution.

## Proven local T2I workflows

`user/default/workflows/image_krea2_turbo_t2i.json` uses:

`UNETLoader → optional LoraLoaderModelOnly → CLIPLoader(type=krea2) → CLIPTextEncode → ConditioningZeroOut → EmptyLatentImage → KSampler → VAEDecode → SaveImage`

The bundled Turbo example is 8 steps, CFG 1, Euler, Simple. These are editable defaults, not filename-dependent behavior.

`user/default/workflows/KREA2 - Film.json` and `KREA2 - Film V2.json` use multiple LoRAs and two sampler stages. The first stage runs the primary denoise; the second runs a short, low-denoise refinement before tiled VAE decode. The provider therefore supports an optional configurable refinement stage.

## Proven local Control workflow

The `KREA2 (CONTROLNET)` subgraph in `KREA2 - Film V2.json` uses:

`UNETLoader → Krea2ControlLoRALoader → ordinary LoRAs → Krea2ControlImageEncode → Krea2ControlApply → sampling`

Its image path runs a depth preprocessor, encodes the control map through the selected VAE, and injects the resulting latent through the KREA control projection. The installed extension exposes control LoRA strength and resize/encode settings. It does **not** expose start/end percentages or multiple control slots; those controls are intentionally not shown.

## LoRA behavior

Native ComfyUI `LoraLoader`/`LoraLoaderModelOnly` clone model patchers and apply patches without permanently baking weights into the base model. KREA mappings are implemented by ComfyUI core. KREA 2 One Node emits a dynamic chain of native `LoraLoader` nodes, so model and CLIP strengths are real graph inputs and ComfyUI owns cache/invalidation behavior.

The KREA control LoRA is loaded first through its specialized loader, matching the proven workflow. Ordinary style LoRAs are chained afterward.

## Compatibility findings

- The installed KREA text-conditioning path expects the KREA Qwen3-VL 4B layout. Model discovery shows all text encoders but prefers a filename containing `qwen3vl_4b`; ComfyUI remains the final format validator.
- Both `qwen_image_vae` and a Wan VAE appear in saved local workflows. The UI does not hardcode either and lets native `VAELoader` validate the selected file.
- `comfyui-krea2edit` is a specialized trained edit/reference path and requires a compatible identity-edit LoRA. It is exposed separately from ordinary latent I2I.
- The installed KREA control extension has no start/end scheduling API. Showing those settings would be fake, so they remain absent.
- The FLUX One Node source is a single very large JavaScript file. The KREA package splits state, API, components, settings, gallery, UI, and CSS into separate modules.

## New architecture

`Krea2OneNode` owns serialized UI configuration and expands through `Krea2Provider` into native ComfyUI nodes. Loader, LoRA, sampler, VAE, device, offload, and VRAM lifecycles remain owned by ComfyUI. Small internal nodes exist only for reference-only downscaling, aspect-preserving I2I canvas fitting, and formatting the local TextGenerate enhancer instruction.

No existing ComfyUI or FLUX One Node files are modified.
