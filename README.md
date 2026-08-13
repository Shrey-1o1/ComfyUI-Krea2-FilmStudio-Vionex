# Krea 2 Film Studio

A local, cinematic KREA 2 generation studio for ComfyUI, designed and built by [VIONEX](https://www.youtube.com/@VionexAI). It does not call KREA or any other external inference API. The node expands into native ComfyUI loaders, conditioning, LoRA, sampler, VAE, save/preview, and installed KREA extension nodes.

## Installation

Copy this entire directory into:

```text
ComfyUI/custom_nodes/comfyui-krea2-one-node/
```

Restart ComfyUI, then add **Krea 2 Film Studio** from the **KREA → Film Studio** category.

The package adds no Python dependencies beyond a working current ComfyUI installation.

Film Studio also integrates [RES4LYF](https://github.com/ClownsharkBatwing/RES4LYF) as its default recommended sampler backend. The managed asset check installs the custom nodes when absent; restart ComfyUI once after that installation.

## Required model files

Use KREA 2-compatible files already supported by native ComfyUI. This installation's workflows reference a KREA diffusion model, a Qwen3-VL 4B KREA text encoder, and default to the Wan 2.1 VAE requested for Film Studio output. Filenames are examples only; the UI scans the actual configured ComfyUI model paths.

```text
ComfyUI/
└── models/
    ├── diffusion_models/
    │   └── [KREA 2 model].safetensors
    ├── text_encoders/
    │   └── [compatible Qwen3-VL 4B encoder].safetensors
    ├── vae/
    │   └── wan_2.1_vae.safetensors
    └── loras/
        ├── [optional KREA style LoRA].safetensors
        ├── [optional KREA identity-edit LoRA].safetensors
        └── [optional KREA control LoRA].safetensors
```

Open **Settings**, click **Refresh models**, and select the model, text encoder, and VAE. Model lists come from `folder_paths`; filenames are never fixed in the package.

On first load, Film Studio verifies the requested Canon UltraReal and Cinematic Movie Still LoRAs, the KREA Depth Control LoRA, the KREA ControlNet custom node, and Wan 2.1 VAE. Missing assets are downloaded from their pinned source URLs with SHA-256 verification. The two cinematic LoRAs are kept enabled as managed studio assets.

## Cinematic styles

The **Cinematic style** menu contains ten VIONEX camera, lighting, color-grade, mood, and finishing bundles. **No style** leaves the prompt unchanged. A selected bundle is appended inside the native execution graph when the frame is queued, so the visible scene prompt always remains the user's original text.

## T2I

1. Select **T2I**.
2. Use the default **Optimal Film 16:9 · 1928 × 1088** frame, or choose another preset/aspect ratio.
3. Set steps, CFG, seed, sampler, scheduler, and batch count.
4. Write the prompt and click **Generate** or press `Ctrl/Cmd + Enter`.

The supplied Film workflow's quality negative prompt is included by default and can be edited in Advanced Film Controls.

## Sampling engines

**Use RES4LYF recommended samplers (Recommended)** is enabled by default in Film Studio Settings. It expands to the exact two-node `ClownsharKSampler_Beta` chain used by the studio workflow:

- pass 1: `linear/euler`, `beta`, 15 total steps, 12 steps to run, eta 0.50, CFG 1.00, Standard mode, BongMath on;
- pass 2: `exponential/res_4s_munthe-kaas`, `kl_optimal`, 15 total steps, 3 steps to run, denoise 0.27, eta 0.50, CFG 1.00, Standard mode, BongMath on;
- the pass-1 **denoised** latent feeds pass 2, and the pass-2 denoised latent feeds the VAE decoder, matching the supplied Film workflow;
- T2I and Control use `VAEEncodeAdvanced` to create the required 16-channel empty latent when RES4LYF is installed.

For T2I and Control, pass 1 uses denoise 1.00. For latent I2I it preserves the selected transform denoise so the reference-strength control still works. Advanced Film Controls enables/disables pass 2 and controls its steps, CFG, and denoise for RES4LYF; native KSampler uses the same refinement switch plus its sampler and scheduler fields.

## I2I

Select **I2I → Latent I2I**, upload/drop/paste an image or connect the `IMAGE` socket, then set denoise and fit mode. Crop preserves aspect while filling the canvas, Fit preserves the whole image with letterboxing, and Stretch fills the exact dimensions. The prepared image is VAE-encoded and sampled through native `KSampler`.

Reference downscaling affects only source/control images; it never changes the selected final generation dimensions.

## KREA Identity Edit / multiple references

When `comfyui-krea2edit` is installed, **KREA Identity Edit** appears as an I2I pipeline. It uses the installed `Krea2EditModelPatch` and `Krea2EditGroundedEncode` nodes, not standard img2img presented as special conditioning.

Add the compatible identity-edit LoRA in Settings, provide one reference image, and optionally provide a second reference. The first image is the scene/reference A; the second is reference B/subject. Fidelity maps to the installed `ref_boost` input.

## Control

CONTROL is enabled only when these installed nodes are available:

- `Krea2ControlLoRALoader`
- `Krea2ControlImageEncode`
- `Krea2ControlApply`

Select the matching KREA control LoRA and provide a preprocessed control map. If `AIO_Preprocessor` is installed, the UI can run the detected Depth Anything V2 preprocessor first.

The currently installed control extension has no start/end percentage or multi-control API, so the UI deliberately does not show those settings.

## LoRAs

Click **+ Add LoRA** to add any number of dynamic rows. Each row has:

- model strength;
- CLIP strength;
- enable/disable;
- remove.

The main-panel button opens a searchable browser with recent and favorite lists. Active LoRAs appear as removable chips above the prompt. Trigger phrases are read locally from safetensors metadata when present.

Both the LoRA browser and Settings include **Rescan LoRA folders**. Saved selections are resolved case-insensitively across Windows/POSIX separators and by a unique filename, so moving a LoRA between subfolders does not invalidate an otherwise unambiguous selection. Common Civitai filenames for the two managed Film LoRAs are recognized without requiring users to rename them.

The provider emits one native `LoraLoader` per enabled row. LoRAs stay as model patches and are not baked into the base model. Changing a row changes the serialized graph configuration and invalidates the relevant native expansion.

## Settings and serialization

The hidden `config` widget is the workflow source of truth. Saving, reopening, or duplicating the workflow preserves mode, prompts, dimensions, sampling, seed behavior, models, LoRAs, I2I/Control, VAE decode, autosave, and advanced settings.

Local browser state is not required to reproduce a saved workflow. Uploaded images are stored through ComfyUI's normal input upload path; large base64 image payloads are not put into workflow JSON.

## External MODEL / CLIP / VAE

Enable **External MODEL / CLIP / VAE inputs** in Settings. Connected sockets override the dropdown loaders. Unconnected external sockets fall back to the internal selections.

The primary `IMAGE` and optional `LATENT` outputs are links to the current expanded execution, not a previously saved preview. `used_seed` reports the actual seed selected for that execution.

## Preview, save, and gallery

- Auto-save on: native `SaveImage` writes to `output/krea2-one-node/`.
- Auto-save off: native `PreviewImage` writes a temporary image; click **Save** to copy it into the gallery.
- The gallery lazy-loads thumbnails and stores sidecar metadata for settings reload.
- **Remove** only removes the item from the current UI view. This package has no physical-delete endpoint.
- Prompt history keeps the latest 30 queued prompts in browser-local storage.

## VAE decoding and memory

VAE decode modes:

- **Auto**: normal decode up to 1.5 MP, tiled above it.
- **Normal**: always native `VAEDecode`.
- **Tiled**: native `VAEDecodeTiled` with tile size and overlap.

Model loading, GPU placement, offloading, low-VRAM behavior, cleanup, interruption, and caching remain owned by ComfyUI. The package does not keep a parallel model cache or persistent tensor store.

## Troubleshooting

### Missing model

Click **Refresh models**. Confirm the file is in the folder shown under the dropdown and that any `extra_model_paths.yaml` entry is active. Missing selections fail with a readable error before graph expansion.

### Conditioning shape error

Load the text encoder with KREA type. The native KREA 2 path expects the compatible Qwen3-VL 4B tapped-conditioning layout. A different Qwen model can appear in the broad ComfyUI text-encoder list but is not necessarily KREA-compatible.

### CUDA out of memory

- lower resolution or batch size;
- enable reference downscaling;
- use tiled VAE decode;
- use the quantized model/text-encoder variants appropriate for your hardware;
- start ComfyUI with its normal low-VRAM/offload options.

### CONTROL is disabled

Install/update `comfyui-krea2-controlnet`, then restart ComfyUI. The package checks node capabilities at runtime.

### Identity Edit is missing

Install/update `comfyui-krea2edit`, restart, and add its compatible trained edit LoRA in the LoRA list.

## Validation

The included tests cover resolution alignment, fixed seeds, native T2I expansion, multiple LoRAs, I2I batching, Identity Edit, Control, external loaders, and missing-model errors. Frontend modules are syntax-checked independently.

See [AUDIT.md](AUDIT.md) for the exact installed classes, proven workflows, reuse decision, and compatibility findings.
