import {button, el, field, modal, number, section, select, textInput, toggle} from "./components.js?v=film-studio-29";

function normalizedLoraName(name) {
  return String(name || "").replaceAll("\\", "/").toLowerCase();
}

function rememberDismissedRecommendedLora(store, item) {
  if (!item?.managed || !item.name) return;
  const dismissed = [...(store.get("dismissed_managed_loras") || [])];
  if (!dismissed.some(name => normalizedLoraName(name) === normalizedLoraName(item.name))) {
    store.set("dismissed_managed_loras", [...dismissed, item.name]);
  }
}

function loraRow(store, item, index, models, render) {
  const row = el("div", "k2-lora-row");
  const choose = select(["", ...(models.loras || [])], item.name || "", value => {
    const list = [...(store.get("loras") || [])];
    const previous = list[index];
    const wasManaged = !!previous?.managed;
    if (wasManaged && normalizedLoraName(previous.name) !== normalizedLoraName(value)) {
      rememberDismissedRecommendedLora(store, previous);
    }
    list[index] = {...previous, name:value, ...(wasManaged?{managed:false}:{})};
    store.set("loras", list);
    if(wasManaged)render();
  });
  choose.title = item.managed ? "Recommended by Film Studio. You may select a different LoRA." : "Choose any LoRA found by ComfyUI.";
  const modelStrength = number(item.strength_model ?? 1, -10, 10, .05, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], strength_model:value}; store.set("loras", list);
  });
  const clipStrength = number(item.strength_clip ?? 1, -10, 10, .05, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], strength_clip:value}; store.set("loras", list);
  });
  const enabled = toggle("On", item.enabled !== false, value => {
    const list = [...store.get("loras")]; list[index] = {...list[index], enabled:value}; store.set("loras", list);
    if (item.managed) render();
  });
  const remove = button("×", "k2-btn k2-btn-danger");
  remove.onclick = () => {
    rememberDismissedRecommendedLora(store, item);
    const list = [...store.get("loras")]; list.splice(index, 1); store.set("loras", list); render();
  };
  if (item.managed) {
    enabled.querySelector(".k2-toggle-label").textContent = `Recommended · ${item.enabled !== false ? "On" : "Off"}`;
    remove.title = "Remove this recommended LoRA";
  }
  row.append(choose, field("Model", modelStrength), field("CLIP", clipStrength), enabled, remove);
  return row;
}

export function openSettings({store, models, refreshModels, syncSockets, showError}) {
  const view = modal("FILM STUDIO SETTINGS");
  view.overlay.dataset.theme=store.get("theme")||"blue-snow";
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
    const promptCrafter = el("a", "k2-youtube-link", "Open Prompt Crafter ↗");
    promptCrafter.href = store.get("prompt_crafter_url") || "https://chatgpt.com/g/g-6a7ea7070fd0819196ae9307a5e70529-vionex-prompt-crafter";
    promptCrafter.target = "_blank";
    promptCrafter.rel = "noopener noreferrer";
    const creatorActions=el("div","k2-creator-actions");creatorActions.append(promptCrafter,youtube);
    creatorCard.append(creatorCopy, creatorActions);
    creator.append(
      creatorCard,
      field("PROMPT CRAFTER LINK", textInput(store.get("prompt_crafter_url"), value=>{store.set("prompt_crafter_url",value);promptCrafter.href=value;}), "Paste any http(s) link; Open Prompt Crafter launches it in a new tab."),
    );

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
      assetRow("Canon UltraReal", "Recommended LoRA · enabled by default", "https://civitai.red/models/2783143/canon-ultrareal", managedNames.some(name=>/canon_krea2\.safetensors$/i.test(name))),
      assetRow("Cinematic Movie Still", "Recommended LoRA · enabled by default", "https://civitai.red/models/2840790/cinematic-movie-still", managedNames.some(name=>/cinematic_movie_still_krea2\.safetensors$/i.test(name))),
      assetRow("KREA Identity Edit v1.2", "Loaded automatically for Identity Edit", "https://huggingface.co/conradlocke/krea2-identity-edit/blob/main/krea2_identity_edit_v1_2.safetensors", !!models.suggested?.identity_lora),
      assetRow("KREA Depth Control", "Required depth LoRA", "https://huggingface.co/Patil/Krea-2-depth-controlnet/tree/main", !!models.suggested?.control_lora),
      assetRow("KREA ControlNet nodes", "Native control workflow", "https://github.com/facok/comfyui-krea2-controlnet", models.capabilities?.control!==false),
      assetRow("RES4LYF", "Recommended two-pass sampler engine", "https://github.com/ClownsharkBatwing/RES4LYF", models.capabilities?.res4lyf!==false),
      assetRow("ComfyUI-GGUF", "Optional quantized diffusion and text-encoder loaders", "https://github.com/city96/ComfyUI-GGUF", models.capabilities?.gguf_model!==false&&models.capabilities?.gguf_clip!==false),
      assetRow("Krea2 Multi-Reference", "Built-in ordered Qwen3-VL vision conditioning", "https://github.com/ethanfel/ComfyUI-Krea2TextEncoder", models.capabilities?.multi_reference!==false),
      assetRow("Wan 2.1 VAE", "Default Film Studio decoder", "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/blob/main/split_files/vae/wan_2.1_vae.safetensors", /wan_2\.1_vae\.safetensors$/i.test(models.suggested?.vae||"")),
    );
    assets.append(assetList);

    const modelSection = section("Film engine");
    const grid = el("div", "k2-settings-grid");
    const ggufEnabled = store.get("gguf.enabled") === true;
    const ggufClipEnabled = store.get("gguf.clip_enabled") === true;
    const ggufToggle = toggle("Use GGUF diffusion model", ggufEnabled, value => {store.set("gguf.enabled", value);render();});
    const ggufClipToggle = toggle("Use GGUF text encoder", ggufClipEnabled, value => {store.set("gguf.clip_enabled", value);render();});
    modelSection.append(ggufToggle, ggufClipToggle);
    grid.append(
      ggufEnabled
        ? field("KREA 2 GGUF MODEL", select(models.gguf_models || [], store.get("gguf.model"), value => store.set("gguf.model", value)), models.paths?.gguf_model)
        : field("KREA 2 MODEL", select(models.diffusion_models || [], store.get("model"), value => store.set("model", value)), models.paths?.model),
      ggufClipEnabled
        ? field("KREA 2 GGUF TEXT ENCODER", select(models.gguf_text_encoders || [], store.get("gguf.clip"), value => store.set("gguf.clip", value)), models.paths?.gguf_clip)
        : field("TEXT ENCODER", select(models.text_encoders || [], store.get("clip"), value => store.set("clip", value)), models.paths?.clip),
      field("IMAGE VAE", select(models.vaes || [], store.get("vae"), value => store.set("vae", value)), models.paths?.vae),
    );
    if(!ggufClipEnabled)grid.append(field("ENCODER PLACEMENT", select(["default","cpu"], store.get("clip_device"), value => store.set("clip_device", value))));
    if(!ggufEnabled)grid.append(field("MODEL PRECISION", select(["default","fp8_e4m3fn","fp8_e4m3fn_fast","fp8_e5m2"], store.get("weight_dtype"), value => store.set("weight_dtype", value))));
    modelSection.append(grid);
    if(ggufEnabled&&models.capabilities?.gguf_model===false)modelSection.append(el("p","k2-error","ComfyUI-GGUF is not active. Install or update it, restart ComfyUI, or turn this toggle off."));
    else if(ggufEnabled&&!(models.gguf_models||[]).length)modelSection.append(el("p","k2-error","No GGUF diffusion models were found. Place a Krea 2 .gguf file in models/diffusion_models or models/unet, then scan the model library."));
    else if(ggufEnabled)modelSection.append(el("p","k2-note","The diffusion model will use UnetLoaderGGUF."));
    if(ggufClipEnabled&&models.capabilities?.gguf_clip===false)modelSection.append(el("p","k2-error","The ComfyUI-GGUF text-encoder loader is not active. Install or update ComfyUI-GGUF, restart ComfyUI, or turn this toggle off."));
    else if(ggufClipEnabled&&!(models.gguf_text_encoders||[]).length)modelSection.append(el("p","k2-error","No GGUF text encoders were found. Place a Krea-compatible .gguf text encoder in models/text_encoders or models/clip, then scan the model library."));
    else if(ggufClipEnabled)modelSection.append(el("p","k2-note","The text encoder will use CLIPLoaderGGUF with Krea 2 encoder type. Encoder placement is managed by ComfyUI-GGUF."));

    const sampling = section("Sampling engine");
    const recommended = toggle(
      "Use RES4LYF recommended samplers (Recommended)",
      store.get("res4lyf.enabled") !== false,
      value => { store.set("res4lyf.enabled", value); render(); },
    );
    sampling.append(recommended);
    if (models.capabilities?.res4lyf === false) {
      sampling.append(el("p", "k2-error", "RES4LYF is not active. Install it and restart ComfyUI, or turn this option off to use native KSampler."));
    } else if (store.get("res4lyf.enabled") !== false) {
      sampling.append(el("p", "k2-note", "Pass 1 uses linear/euler with beta. When Refinement is enabled, pass 2 uses exponential/res_4s_munthe-kaas with kl_optimal and the Advanced Film Controls values for steps, CFG, and denoise. Eta 0.50, Standard mode, and BongMath remain fixed."));
    } else {
      sampling.append(el("p", "k2-note", "Native ComfyUI KSampler is active. Configure its sampler, scheduler, steps, CFG, and optional refinement in the main studio panel."));
    }
    const diversityEnabled=store.get("diversity.enabled")===true;
    sampling.append(toggle("Extra diversity noise injection",diversityEnabled,value=>{store.set("diversity.enabled",value);render();}));
    if(diversityEnabled){
      const diversityGrid=el("div","k2-settings-grid");
      diversityGrid.append(
        field("LATENT NOISE STRENGTH",number(store.get("diversity.strength")??.08,0,1,.01,value=>store.set("diversity.strength",value)),"Applied before either sampler backend."),
        field("RES4LYF SDE ETA",number(store.get("diversity.eta")??.75,0,2,.05,value=>store.set("diversity.eta",value)),"Per-step noise amount when RES4LYF is active."),
      );
      sampling.append(diversityGrid,el("p","k2-note","Experimental diversity boost: low-amplitude latent noise works with native and RES4LYF sampling; RES4LYF also uses the selected eta for controlled noise after each step."));
    }

    const loras = section("LoRAs");
    const list = el("div", "k2-lora-list");
    (store.get("loras") || []).forEach((item, index) => list.append(loraRow(store, item, index, models, render)));
    const add = button("+ Add LoRA", "k2-btn k2-btn-accent");
    add.onclick = () => { store.set("loras", [...(store.get("loras") || []), {name:(models.loras||[])[0]||"",strength_model:1,strength_clip:1,enabled:true}]); render(); };
    const rescan = button("↻ Rescan LoRA folders", "k2-btn k2-btn-quiet");
    rescan.onclick = async () => {
      rescan.disabled=true;rescan.textContent="Scanning…";
      try{await refreshModels();render();}catch(error){showError(error);}
      finally{rescan.disabled=false;rescan.textContent="↻ Rescan LoRA folders";}
    };
    if(!(models.loras||[]).length)list.append(el("p","k2-note","No LoRAs are registered by ComfyUI. Place files in models/loras, then use Rescan LoRA folders."));
    const actions=el("div","k2-settings-actions");actions.append(add,rescan);loras.append(list,actions);

    const prefs = section("Studio preferences");
    prefs.append(
      field("STUDIO THEME",select([
        {label:"Red Fire",value:"red-fire"},{label:"Blue Snow",value:"blue-snow"},{label:"Crimson",value:"crimson"},{label:"Glass",value:"glass"},{label:"Black",value:"black"},
      ],store.get("theme")||"blue-snow",value=>{store.set("theme",value);view.overlay.dataset.theme=value;})),
      toggle("Notification sound", store.get("notification_sound"), value => store.set("notification_sound", value)),
      toggle("Advanced controls", store.get("advanced"), value => store.set("advanced", value)),
      toggle("Auto-save", store.get("auto_save"), value => store.set("auto_save", value)),
      field("AUTOMATIC SAVE FOLDER",textInput(store.get("save_path"),value=>store.set("save_path",value),"Leave blank for ComfyUI/output/krea2-one-node"),"Use an absolute local folder path. Film Studio creates it when the next frame is saved."),
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

    view.body.append(creator, assets, modelSection, sampling, loras, prefs);
  };
  refresh.onclick = async () => { refresh.disabled = true; try { await refreshModels(); render(); } catch(error) { showError(error); } finally { refresh.disabled = false; } };
  render(); document.body.append(view.overlay);
}
