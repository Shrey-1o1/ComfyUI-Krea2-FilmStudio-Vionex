export const RESOLUTION_PRESETS = [
  {group:"Recommended",items:[
    ["Optimal Film 16:9 · 1928 × 1088",1928,1088],
    ["Krea Square · 1024 × 1024",1024,1024],
    ["Krea Square 2K · 2048 × 2048",2048,2048],
  ]},
  {group:"Horizontal",items:[
    ["Krea Landscape · 1216 × 832",1216,832],
    ["Classic Frame · 1152 × 896",1152,896],
    ["Widescreen Film · 1344 × 768",1344,768],
    ["Cinema Flat · 1408 × 768",1408,768],
    ["CinemaScope · 1536 × 640",1536,640],
  ]},
  {group:"Vertical",items:[
    ["Krea Portrait · 832 × 1216",832,1216],
    ["Classic Portrait · 896 × 1152",896,1152],
    ["Vertical Film · 768 × 1344",768,1344],
  ]},
];

export const FILM_FORMATS = [
  {label:"1:1 (Square)",value:"1:1"},
  {label:"2:3 (Portrait Photo)",value:"2:3"},
  {label:"3:2 (Photo)",value:"3:2"},
  {label:"3:4 (Portrait Standard)",value:"3:4"},
  {label:"4:3 (Classic Standard)",value:"4:3"},
  {label:"9:16 (Vertical Film)",value:"9:16"},
  {label:"16:9 (Widescreen)",value:"16:9"},
  {label:"1.85:1 (Cinema Flat)",value:"1.85:1"},
  {label:"2.39:1 (CinemaScope)",value:"2.39:1"},
  {label:"21:9 (Ultra-wide)",value:"21:9"},
  {label:"Custom ratio",value:"custom"},
];

export const ASPECTS = {
  "1:1":[1,1],"16:9":[16,9],"9:16":[9,16],"4:3":[4,3],"3:4":[3,4],
  "3:2":[3,2],"2:3":[2,3],"21:9":[21,9],"1.85:1":[1.85,1],"2.39:1":[2.39,1],
};

const clone = value => JSON.parse(JSON.stringify(value));

export const DEFAULT_FILM_NEGATIVE = "low quality, blurry, pixelated, bad anatomy, deformed body, extra limbs, malformed hands, extra fingers, distorted face, asymmetrical eyes, duplicate subjects, warped background, incorrect perspective, cropped limbs, plastic skin, unrealistic lighting, oversaturated, text, watermark, logo, CGI, cartoon, motion blur, flicker, jitter, morphing, temporal inconsistency";

export function parseState(raw) {
  try {
    const value = JSON.parse(raw || "{}");
    if (!value || typeof value !== "object") return {};
    if (Number(value.version || 1) < 2) {
      value.version = 2;
      if (!String(value.negative_prompt || "").trim()) value.negative_prompt = DEFAULT_FILM_NEGATIVE;
      if (!value.custom_resolution && Number(value.width) === 1024 && Number(value.height) === 1024) {
        Object.assign(value, {width:1928,height:1088,aspect_ratio:"16:9",megapixels:2});
      }
      if (value.res4lyf?.enabled !== false) {
        value.refinement = {...(value.refinement || {}), enabled:true};
      }
      if (!value.vae_decode || value.vae_decode.mode === "auto") {
        value.vae_decode = {...(value.vae_decode || {}),mode:"tiled",tile_size:256,overlap:64};
      }
    }
    if (Number(value.version || 1) < 3) {
      value.version = 3;
      value.i2i = {...(value.i2i || {}),fit_mode:"fit",identity_lora:value.i2i?.identity_lora||""};
    }
    if (Number(value.version || 1) < 4) {
      value.version = 4;
      value.compare_enabled = false;
      value.uploads = {...(value.uploads || {}),image_3:"",image_4:""};
      value.multi_reference = {
        vision_megapixels:.3,
        vision_position:"before prompt",
        system_prompt:"Study every numbered reference image, preserve the requested identity, object, wardrobe, style, lighting, and environment cues, then combine them into one coherent new shot that follows the user's spatial instructions. Treat Image N and Picture N as the same reference.",
        ...(value.multi_reference || {}),
      };
      value.stats = {images_generated:0,renders_completed:0,total_render_ms:0,last_render_ms:0,last_batch:0,last_completed_at:"",...(value.stats || {})};
    }
    value.enhancer = {...(value.enhancer || {}),enabled:false};
    return value;
  } catch (_) { return {}; }
}

export function pathGet(object, path) {
  return path.split(".").reduce((value, key) => value?.[key], object);
}

export function pathSet(object, path, value) {
  const keys = path.split(".");
  let current = object;
  keys.slice(0, -1).forEach(key => {
    if (!current[key] || typeof current[key] !== "object") current[key] = {};
    current = current[key];
  });
  current[keys.at(-1)] = value;
}

export class StateStore {
  constructor(value, onChange) {
    this.value = clone(value);
    this.onChange = onChange;
    this.listeners = new Set();
  }
  get(path) { return path ? pathGet(this.value, path) : this.value; }
  set(path, value) {
    pathSet(this.value, path, value);
    this.onChange?.(this.value);
    this.listeners.forEach(listener => listener(path, value, this.value));
  }
  update(patch) {
    Object.assign(this.value, patch);
    this.onChange?.(this.value);
    this.listeners.forEach(listener => listener("*", null, this.value));
  }
  replace(value) {
    this.value = clone(value);
    this.onChange?.(this.value);
    this.listeners.forEach(listener => listener("*", null, this.value));
  }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
}

export function dimensionsFor(aspect, megapixels, alignment=8) {
  if (aspect === "16:9" && Math.abs(Number(megapixels) - 2) < 0.0001) {
    return [1928, 1088];
  }
  const [aw, ah] = ASPECTS[aspect] || ASPECTS["1:1"];
  const area = Math.max(.05, Number(megapixels) || 1) * 1_000_000;
  const width = Math.sqrt(area * aw / ah);
  const height = width * ah / aw;
  const align = value => Math.max(alignment, Math.round(value / alignment) * alignment);
  return [align(width), align(height)];
}

export function metadataSnapshot(state, usedSeed) {
  return {
    version: 1, timestamp: new Date().toISOString(), mode: state.mode,
    prompt: state.prompt, negative_prompt: state.negative_prompt,
    seed: usedSeed ?? state.seed, width: state.width, height: state.height,
    steps: state.steps, cfg: state.cfg, sampler: state.sampler,
    scheduler: state.scheduler, denoise: state.mode === "i2i" ? state.i2i?.denoise : state.denoise,
    sampling_backend: state.res4lyf?.enabled !== false ? "RES4LYF recommended" : "Native KSampler",
    diversity: state.diversity,
    references: state.mode === "references" ? state.multi_reference : undefined,
    theme: state.theme,
    model_backend: state.gguf?.enabled ? "GGUF" : "Standard",
    model: state.gguf?.enabled ? state.gguf?.model : state.model,
    text_encoder_backend: state.gguf?.clip_enabled ? "GGUF" : "Standard",
    clip: state.gguf?.clip_enabled ? state.gguf?.clip : state.clip,
    vae: state.vae,
    loras: (state.loras || []).filter(item => item.enabled !== false),
    refinement: state.refinement,
    config: clone(state),
  };
}
