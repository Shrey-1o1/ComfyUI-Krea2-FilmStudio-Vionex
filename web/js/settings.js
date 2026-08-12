import {button, el, field, modal, number, section, select, toggle} from "./components.js";

function loraRow(store, item, index, models, render) {
  const row = el("div", "k2-lora-row");
  const choose = select(["", ...(models.loras || [])], item.name || "", value => {
    const list = [...(store.get("loras") || [])]; list[index] = {...list[index], name:value}; store.set("loras", list);
  });
  const modelStrength = number(item.strength_model ?? 1, -10, 10, .05, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], strength_model:value}; store.set("loras", list);
  });
  const clipStrength = number(item.strength_clip ?? 1, -10, 10, .05, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], strength_clip:value}; store.set("loras", list);
  });
  const enabled = toggle("On", item.enabled !== false, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], enabled:value}; store.set("loras", list);
  });
  const remove = button("×", "k2-btn k2-btn-danger");
  remove.onclick = () => { const list = [...store.get("loras")]; list.splice(index, 1); store.set("loras", list); render(); };
  if (item.managed) {
    choose.disabled = true;
    enabled.querySelector("input").disabled = true;
    enabled.querySelector(".k2-toggle-label").textContent = "Managed · On";
    remove.disabled = true;
    remove.title = "Required Film Studio LoRA";
  }
  row.append(choose, field("Model", modelStrength), field("CLIP", clipStrength), enabled, remove);
  return row;
}

export function openSettings({store, models, refreshModels, syncSockets, showError}) {
  const view = modal("FILM STUDIO SETTINGS");
  const refresh = button("↻ Scan model library", "k2-btn k2-btn-quiet");
  view.head.insertBefore(refresh, view.close);

  const render = () => {
    view.body.replaceChildren();
    const creator = section("Studio");
    const creatorCard = el("div", "k2-creator-card");
    const creatorCopy = el("div");
    creatorCopy.append(el("strong", "", "Krea 2 Film Studio"), el("p", "k2-note", "Designed and built by VIONEX for local cinematic image generation in ComfyUI."));
    const youtube = el("a", "k2-youtube-link", "Watch VIONEX AI on YouTube ↗");
    youtube.href = "https://www.youtube.com/@VionexAI";
    youtube.target = "_blank";
    youtube.rel = "noopener noreferrer";
    creatorCard.append(creatorCopy, youtube);
    creator.append(creatorCard);

    const assets = section("Managed film assets");
    const assetList = el("div", "k2-asset-list");
    const assetRow = (name, detail, href, ready) => {
      const row = el("div", `k2-asset-row${ready?" is-ready":" is-missing"}`);
      const copy = el("div");copy.append(el("strong", "", name), el("small", "", detail));
      const source = el("a", "k2-asset-source", "Source ↗");source.href=href;source.target="_blank";source.rel="noopener noreferrer";
      row.append(copy,el("span","k2-asset-status",ready?"Installed":"Missing"),source);return row;
    };
    const managedNames=models.suggested?.managed_loras||[];
    assetList.append(
      assetRow("Canon UltraReal", "Managed LoRA · always enabled", "https://civitai.red/models/2783143/canon-ultrareal", managedNames.some(name=>/canon_krea2\.safetensors$/i.test(name))),
      assetRow("Cinematic Movie Still", "Managed LoRA · always enabled", "https://civitai.red/models/2840790/cinematic-movie-still", managedNames.some(name=>/cinematic_movie_still_krea2\.safetensors$/i.test(name))),
      assetRow("KREA Depth Control", "Required depth LoRA", "https://huggingface.co/Patil/Krea-2-depth-controlnet/tree/main", !!models.suggested?.control_lora),
      assetRow("KREA ControlNet nodes", "Native control workflow", "https://github.com/facok/comfyui-krea2-controlnet", models.capabilities?.control!==false),
      assetRow("Wan 2.1 VAE", "Default Film Studio decoder", "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/blob/main/split_files/vae/wan_2.1_vae.safetensors", /wan_2\.1_vae\.safetensors$/i.test(models.suggested?.vae||"")),
    );
    assets.append(assetList);

    const modelSection = section("Film engine");
    const grid = el("div", "k2-settings-grid");
    grid.append(
      field("KREA 2 MODEL", select(models.diffusion_models || [], store.get("model"), value => store.set("model", value)), models.paths?.model),
      field("TEXT ENCODER", select(models.text_encoders || [], store.get("clip"), value => store.set("clip", value)), models.paths?.clip),
      field("IMAGE VAE", select(models.vaes || [], store.get("vae"), value => store.set("vae", value)), models.paths?.vae),
      field("MODEL PRECISION", select(["default","fp8_e4m3fn","fp8_e4m3fn_fast","fp8_e5m2"], store.get("weight_dtype"), value => store.set("weight_dtype", value))),
      field("ENCODER PLACEMENT", select(["default","cpu"], store.get("clip_device"), value => store.set("clip_device", value))),
    );
    modelSection.append(grid);

    const loras = section("LoRAs");
    const list = el("div", "k2-lora-list");
    (store.get("loras") || []).forEach((item, index) => list.append(loraRow(store, item, index, models, render)));
    const add = button("+ Add LoRA", "k2-btn k2-btn-accent");
    add.onclick = () => { store.set("loras", [...(store.get("loras") || []), {name:"",strength_model:1,strength_clip:1,enabled:true}]); render(); };
    loras.append(list, add);

    const prefs = section("Studio preferences");
    prefs.append(
      toggle("Notification sound", store.get("notification_sound"), value => store.set("notification_sound", value)),
      toggle("Advanced controls", store.get("advanced"), value => store.set("advanced", value)),
      toggle("Auto-save", store.get("auto_save"), value => store.set("auto_save", value)),
      toggle("External MODEL / CLIP / VAE inputs", Object.values(store.get("external") || {}).some(Boolean), value => {
        store.set("external", {model:value,clip:value,vae:value}); syncSockets();
      }),
      field("REFERENCE DETAIL", select([
        {label:"Original",value:"Original"},{label:"0.5 MP",value:"0.5"},{label:"0.75 MP",value:"0.75"},
        {label:"1 MP",value:"1"},{label:"1.5 MP",value:"1.5"},{label:"2 MP",value:"2"},
      ], String(store.get("reference_downscale_mp") ?? 1), value => store.set("reference_downscale_mp", value === "Original" ? "Original" : Number(value)))),
      field("FINAL FRAME DECODE", select(models.capabilities?.tiled_decode === false ? ["auto","normal"] : ["auto","normal","tiled"], store.get("vae_decode.mode"), value => {store.set("vae_decode.mode", value);render();})),
    );
    if (store.get("vae_decode.mode") === "tiled") {
      const tiles = el("div", "k2-settings-grid");
      tiles.append(field("Tile size", number(store.get("vae_decode.tile_size"),64,4096,64,v=>store.set("vae_decode.tile_size",v))), field("Overlap", number(store.get("vae_decode.overlap"),0,1024,32,v=>store.set("vae_decode.overlap",v))));
      prefs.append(tiles);
    }

    const enhancer = section("Local scene writer");
    if (models.capabilities?.prompt_enhancer === false) {
      enhancer.append(el("p", "k2-note", "Unavailable: this ComfyUI build did not register the local TextGenerate node."));
    } else {
      enhancer.append(
        toggle("Enhancer enabled", store.get("enhancer.enabled"), value => store.set("enhancer.enabled", value)),
        field("Behavior", select(["light","balanced","detailed"], store.get("enhancer.behavior"), value=>store.set("enhancer.behavior",value))),
      );
      const enhanceGrid = el("div", "k2-settings-grid");
      enhanceGrid.append(
        field("Max length", number(store.get("enhancer.max_length"),32,2048,16,v=>store.set("enhancer.max_length",v))),
        field("Temperature", number(store.get("enhancer.temperature"),0,2,.05,v=>store.set("enhancer.temperature",v))),
        field("Top K", number(store.get("enhancer.top_k"),1,1000,1,v=>store.set("enhancer.top_k",v))),
        field("Top P", number(store.get("enhancer.top_p"),0,1,.01,v=>store.set("enhancer.top_p",v))),
        field("Repetition penalty", number(store.get("enhancer.repetition_penalty"),.1,4,.05,v=>store.set("enhancer.repetition_penalty",v))),
        field("Enhancer seed", number(store.get("enhancer.seed"),0,Number.MAX_SAFE_INTEGER,1,v=>store.set("enhancer.seed",v))),
      );
      enhancer.append(enhanceGrid, toggle("Thinking", store.get("enhancer.thinking"), value=>store.set("enhancer.thinking",value)));
    }
    view.body.append(creator, assets, modelSection, loras, prefs, enhancer);
  };
  refresh.onclick = async () => { refresh.disabled = true; try { await refreshModels(); render(); } catch(error) { showError(error); } finally { refresh.disabled = false; } };
  render(); document.body.append(view.overlay);
}
