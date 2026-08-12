import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { kreaApi } from "./api.js";
import { button, el, field, modal, number, select, setOptions, stepper, toggle } from "./components.js";
import { openGallery } from "./gallery.js";
import { openLoraBrowser } from "./lora_browser.js";
import { openPromptHistory, rememberPrompt } from "./prompt_history.js";
import { openPromptStructure } from "./prompt_structure.js?v=film-studio-9";
import { openSettings } from "./settings.js";
import { dimensionsFor, FILM_FORMATS, metadataSnapshot, parseState, RESOLUTION_PRESETS, StateStore } from "./state.js";

const MIN_NODE_WIDTH = 900;
const MIN_UI_HEIGHT = 420;
const SOCKET_TYPES = {prompt:"STRING",image:"IMAGE",image_2:"IMAGE",model:"MODEL",clip:"CLIP",vae:"VAE"};

function hasConnectedInput(node, name) {
  return (node.inputs || []).some(input => input.name === name && input.link != null);
}

function syncSockets(node, store) {
  node.resizable=true;
  const preserved=Array.isArray(node.size)?[node.size[0],node.size[1]]:[MIN_NODE_WIDTH,MIN_UI_HEIGHT];
  const external = store.get("external") || {};
  const wanted = new Set(["prompt"]);
  if (store.get("mode") !== "t2i") wanted.add("image");
  if (store.get("mode") === "i2i" && store.get("i2i.pipeline") === "identity_edit") wanted.add("image_2");
  Object.entries(external).forEach(([name, enabled]) => { if (enabled) wanted.add(name); });
  Object.keys(SOCKET_TYPES).forEach(name => {
    const index = (node.inputs || []).findIndex(input => input.name === name);
    if (wanted.has(name) && index < 0) node.addInput(name, SOCKET_TYPES[name]);
    if (!wanted.has(name) && index >= 0 && node.inputs[index].link == null) node.removeInput(index);
  });
  const restore=()=>{node.setSize?.([preserved[0],preserved[1]]);node.setDirtyCanvas?.(true,true);};
  restore();
  queueMicrotask(restore);
  requestAnimationFrame(()=>{restore();requestAnimationFrame(restore);});
  setTimeout(restore,80);
}

function playComplete() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const context = new AudioContext();
    [660, 990].forEach((frequency, index) => {
      const oscillator=context.createOscillator(), gain=context.createGain();
      oscillator.frequency.value=frequency; oscillator.connect(gain); gain.connect(context.destination);
      const start=context.currentTime+index*.1; gain.gain.setValueAtTime(.001,start);
      gain.gain.exponentialRampToValueAtTime(.08,start+.03); gain.gain.exponentialRampToValueAtTime(.001,start+.45);
      oscillator.start(start); oscillator.stop(start+.5);
    });
  } catch (_) {}
}

function uploadZone(label, store, path, onError) {
  const zone = el("div", "k2-upload");
  const input = el("input"); input.type="file"; input.accept="image/*"; input.hidden=true;
  const icon=el("span","k2-upload-icon","▧"), title=el("strong","",label), name=el("span","k2-upload-name", store.get(path) || "Drop, paste, or choose an image");
  zone.append(icon,title,name,input); zone.onclick=()=>input.click();
  const load = async file => {
    if (!file) return;
    zone.classList.add("is-loading"); name.textContent="Uploading…";
    try { const result=await kreaApi.upload(file); store.set(path,result.path); name.textContent=result.path; }
    catch(error){ onError(error); name.textContent="Upload failed"; }
    finally { zone.classList.remove("is-loading"); }
  };
  input.onchange=()=>load(input.files?.[0]);
  zone.ondragover=event=>{event.preventDefault();zone.classList.add("is-dragging");};
  zone.ondragleave=()=>zone.classList.remove("is-dragging");
  zone.ondrop=event=>{event.preventDefault();zone.classList.remove("is-dragging");load(event.dataTransfer.files?.[0]);};
  zone.load=load;
  return zone;
}

function discoverPrompt(store) {
  const view=modal("DISCOVER PROMPTS");
  const prompts=[
    ["Cinematic portrait","Cinematic portrait, expressive natural features, dramatic motivated lighting, shallow depth of field, subtle film grain, photorealistic."],
    ["Editorial fashion","High-fashion editorial photograph, sculptural styling, clean graphic composition, controlled studio lighting, tactile fabric detail."],
    ["Atmospheric landscape","Vast atmospheric landscape at blue hour, layered depth, volumetric light, natural color separation, finely rendered environmental detail."],
    ["Product still life","Premium product still life, precise reflections, restrained luxury palette, studio gradient background, realistic materials, commercial photography."],
  ];
  const grid=el("div","k2-discover-grid");
  prompts.forEach(([name,prompt])=>{const card=button(name,"k2-discover-card");card.onclick=()=>{store.set("prompt",prompt);view.hide();};grid.append(card);});
  view.body.append(grid); document.body.append(view.overlay);
}

export function buildNodeUI(node, configWidget) {
  const root=el("div","k2-app");
  const initial=parseState(configWidget.value);
  const store=new StateStore(initial, value => {
    configWidget.value=JSON.stringify(value);
    configWidget.callback?.(configWidget.value);
    node.setDirtyCanvas?.(true, true);
  });
  const models={diffusion_models:[],text_encoders:[],vaes:[],loras:[],styles:[],samplers:[store.get("sampler") || "euler"],schedulers:[store.get("scheduler") || "simple"],capabilities:{}};
  const sessionItems=[];
  let currentImage=null, currentMetadata=null, usedSeed=null, zoom=1;

  const header=el("header","k2-header");
  const brand=el("div","k2-brand");
  const brandCopy=el("div","k2-brand-copy");brandCopy.append(el("strong","","Krea 2 Film Studio"),el("small","","LOCAL CINEMATIC IMAGE ENGINE"));
  brand.append(el("span","k2-studio-mark","K2"),brandCopy,el("span","k2-vionex-tag","MADE BY VIONEX"));
  const headerActions=el("div","k2-header-actions");
  const galleryButton=button("Gallery","k2-btn k2-btn-quiet"), promptStructureButton=button("Prompt Structure","k2-btn k2-btn-quiet k2-prompt-structure-button"), helpButton=button("Help","k2-btn k2-btn-quiet"), settingsButton=button("Settings","k2-btn k2-btn-quiet"), fullButton=button("⛶","k2-btn k2-btn-icon");
  headerActions.append(galleryButton,promptStructureButton,helpButton,settingsButton,fullButton); header.append(brand,headerActions);

  const tabs=el("nav","k2-tabs");tabs.setAttribute("aria-label","Film Studio mode");
  const tabButtons={};
  const modeCopy={t2i:["Text to Film (T2I)","Create a new cinematic frame"],i2i:["Transform Frame (I2I)","Restyle or preserve a reference"],control:["Directed Control (ControlNet)","Guide structure with a control map"]};
  ["t2i","i2i","control"].forEach(mode=>{const tab=button("","k2-tab");tab.append(el("strong","",modeCopy[mode][0]),el("small","",modeCopy[mode][1]));tab.onclick=()=>{store.set("mode",mode);syncSockets(node,store);renderMode();};tabButtons[mode]=tab;tabs.append(tab);});

  const content=el("div","k2-content"), controls=el("section","k2-controls"), preview=el("section","k2-preview");
  const size=el("section","k2-block k2-film-size"), sizeHead=el("div","k2-block-head"); sizeHead.append(el("span","k2-section-index","01"),el("strong","","Film frame"));
  const dimensionBadge=el("span","k2-dimension-badge",`${store.get("width")} × ${store.get("height")}`);sizeHead.append(dimensionBadge);
  const sizeGrid=el("div","k2-vertical-form");
  const presetItems=RESOLUTION_PRESETS.map(([label,w,h])=>({label,value:`${w}x${h}`}));
  const currentDimensions=`${store.get("width")}x${store.get("height")}`;
  const initialPreset=presetItems.some(item=>item.value===currentDimensions)?currentDimensions:presetItems[0].value;
  const preset=select(presetItems,initialPreset,value=>{customResolution.querySelector("input").checked=false;store.set("custom_resolution",false);applyPresetSize(value);renderCustomResolution();});
  const aspect=select(FILM_FORMATS,store.get("aspect_ratio") || "1:1",value=>{store.set("aspect_ratio",value);if(value!=="custom")applyCalculatedSize();});
  const mp=stepper(Number(store.get("megapixels") || 1),.5,4,.1,value=>{store.set("megapixels",Number(value));applyCalculatedSize();});
  const width=number(store.get("width"),64,16384,8,value=>{store.set("width",value);store.set("aspect_ratio","custom");aspect.value="custom";dimensionBadge.textContent=`${value} × ${store.get("height")}`;});
  const height=number(store.get("height"),64,16384,8,value=>{store.set("height",value);store.set("aspect_ratio","custom");aspect.value="custom";dimensionBadge.textContent=`${store.get("width")} × ${value}`;});
  function applyCalculatedSize(){if(aspect.value==="custom")return;const [w,h]=dimensionsFor(aspect.value,Number(mp.input.value),Number(store.get("alignment")||8));store.set("width",w);store.set("height",h);width.value=w;height.value=h;dimensionBadge.textContent=`${w} × ${h}`;}
  function applyPresetSize(value){const [w,h]=value.split("x").map(Number);store.set("width",w);store.set("height",h);width.value=w;height.value=h;dimensionBadge.textContent=`${w} × ${h}`;}
  const customPanel=el("div","k2-custom-resolution k2-vertical-form");
  const manualFields=el("div","k2-dimension-grid");manualFields.append(field("Width in pixels",width),field("Height in pixels",height));
  customPanel.append(field("Frame format",aspect,"Photography, widescreen, and cinema ratios"),field("Megapixels",mp,"Adjust area while preserving the selected format"),manualFields);
  const customResolution=toggle("Custom resolution",store.get("custom_resolution"),value=>{store.set("custom_resolution",value);if(!value)applyPresetSize(preset.value);renderCustomResolution();});customResolution.classList.add("k2-custom-toggle");
  function renderCustomResolution(){const enabled=!!store.get("custom_resolution");customPanel.hidden=!enabled;width.disabled=!enabled;height.disabled=!enabled;aspect.disabled=!enabled;mp.input.disabled=!enabled;mp.querySelectorAll("button").forEach(control=>control.disabled=!enabled);}
  sizeGrid.append(field("Film resolution",preset,"Curated production-ready KREA frames"),customResolution,customPanel); size.append(sizeHead,sizeGrid);renderCustomResolution();if(!store.get("custom_resolution")&&currentDimensions!==initialPreset)applyPresetSize(initialPreset);

  const parameters=el("section","k2-block"), paramGrid=el("div","k2-vertical-form k2-parameter-grid");
  const parameterHead=el("div","k2-block-head");parameterHead.append(el("span","k2-section-index","02"),el("strong","","Exposure & sampling"));parameters.append(parameterHead);
  const steps=number(store.get("steps"),1,1000,1,value=>{store.set("steps",value);store.set("preset","Custom");presetSelect.value="Custom";});
  const cfg=number(store.get("cfg"),0,100,.1,value=>{store.set("cfg",value);store.set("preset","Custom");presetSelect.value="Custom";});
  const seed=number(store.get("seed"),0,Number.MAX_SAFE_INTEGER,1,value=>store.set("seed",value));
  const random=toggle("Random",store.get("randomize_seed"),value=>store.set("randomize_seed",value));
  const sampler=select(models.samplers,store.get("sampler"),value=>{store.set("sampler",value);store.set("preset","Custom");presetSelect.value="Custom";});
  const scheduler=select(models.schedulers,store.get("scheduler"),value=>{store.set("scheduler",value);store.set("preset","Custom");presetSelect.value="Custom";});
  const presetSelect=select(["Fast","Balanced","Quality","Custom"],store.get("preset") || "Fast",value=>applyPreset(value));
  async function applyPreset(name){store.set("preset",name);if(name==="Custom")return;const patch=models.presets?.[name];if(!patch)return;Object.entries(patch).forEach(([key,value])=>store.set(key,value));steps.value=store.get("steps");cfg.value=store.get("cfg");sampler.value=store.get("sampler");scheduler.value=store.get("scheduler");}
  paramGrid.append(field("Studio preset",presetSelect,"Fast, balanced, or two-pass quality"),field("Sampling steps",steps),field("Prompt guidance",cfg),field("Frame seed",seed),random,field("Sampler",sampler),field("Noise schedule",scheduler));parameters.append(paramGrid);

  const stylesBlock=el("section","k2-block k2-styles-block"), stylesHead=el("div","k2-block-head");stylesHead.append(el("span","k2-section-index","03"),el("strong","","Cinematic style"));
  const styleSelect=select([{label:"No style — use prompt only",value:""}],store.get("cinematic_style")||"",value=>{store.set("cinematic_style",value);renderStyleDetails();});
  const styleDetails=el("div","k2-style-details");
  function renderStyleDetails(){const selected=models.styles.find(item=>item.value===styleSelect.value);styleDetails.replaceChildren();styleDetails.hidden=!selected;if(!selected)return;[["Camera",selected.camera],["Lighting",selected.lighting],["Color grade",selected.grade],["Mood",selected.mood],["Style",selected.style]].forEach(([label,value])=>{const row=el("div","k2-style-row");row.append(el("strong","",label),el("p","",value));styleDetails.append(row);});}
  stylesBlock.append(stylesHead,field("Style bundle",styleSelect,"Appended to the prompt only while this style is selected"),styleDetails);

  const modePanel=el("section","k2-mode-panel");
  const renderMode=()=>{
    Object.entries(tabButtons).forEach(([mode,button])=>button.classList.toggle("is-active",mode===store.get("mode")));
    tabButtons.control.disabled=models.capabilities.control===false;
    modePanel.replaceChildren();
    const mode=store.get("mode");
    if(mode==="i2i"){
      if(store.get("i2i.pipeline")==="identity_edit"&&models.capabilities.identity_edit===false){modePanel.append(el("p","k2-error","KREA Identity Edit is unavailable because the installed krea2edit nodes were not registered. Choose Latent I2I or restart after installing the extension."));return;}
      const choices=[{label:"Latent I2I",value:"latent"}]; if(models.capabilities.identity_edit)choices.push({label:"KREA Identity Edit",value:"identity_edit"});
      const pipeline=select(choices,store.get("i2i.pipeline") || "latent",value=>{store.set("i2i.pipeline",value);syncSockets(node,store);renderMode();});
      modePanel.append(field("Image pipeline",pipeline));
      const upload=uploadZone("REFERENCE IMAGE",store,"uploads.image",showError);modePanel.append(upload);
      if(store.get("i2i.pipeline")==="identity_edit"){
        modePanel.append(uploadZone("OPTIONAL SECOND REFERENCE",store,"uploads.image_2",showError));
        const grid=el("div","k2-inline-grid");grid.append(field("Fidelity",number(store.get("i2i.ref_boost"),0,1000,.1,v=>store.set("i2i.ref_boost",v))),field("Grounding px",number(store.get("i2i.grounding_px"),0,4096,64,v=>store.set("i2i.grounding_px",v))),field("Fit",select(["crop","fit"],store.get("i2i.fit_mode"),v=>store.set("i2i.fit_mode",v))));modePanel.append(grid);
      }else{
        const grid=el("div","k2-inline-grid");grid.append(field("Denoise",number(store.get("i2i.denoise"),0,1,.01,v=>store.set("i2i.denoise",v))),field("Fit",select(["crop","fit","stretch"],store.get("i2i.fit_mode"),v=>store.set("i2i.fit_mode",v))));modePanel.append(grid);
      }
    }else if(mode==="control"){
      if(models.capabilities.control===false){modePanel.append(el("p","k2-error","CONTROL is unavailable because Krea2ControlLoRALoader, Krea2ControlImageEncode, or Krea2ControlApply was not registered. T2I and I2I remain available."));return;}
      modePanel.append(uploadZone("CONTROL IMAGE / MAP",store,"uploads.image",showError));
      const grid=el("div","k2-inline-grid");
      const preprocessors=[{label:"Already preprocessed",value:"none"}];if(models.capabilities.depth_preprocessor)preprocessors.push({label:"Depth Anything V2",value:"depth_anything_v2"});
      grid.append(field("Control LoRA",select(["",...(models.loras||[])],store.get("control.lora"),v=>store.set("control.lora",v))),field("Strength",number(store.get("control.strength"),-100,100,.05,v=>store.set("control.strength",v))),field("Preprocessor",select(preprocessors,store.get("control.preprocessor"),v=>{store.set("control.preprocessor",v);renderMode();})));modePanel.append(grid);
      if(store.get("advanced")){
        const controlAdvanced=el("div","k2-inline-grid");
        controlAdvanced.append(
          field("Resize",select(["match_latent_size","keep_control_image_size"],store.get("control.resize"),v=>store.set("control.resize",v))),
          field("Upscale",select(["lanczos","bicubic","bilinear","area","nearest-exact"],store.get("control.upscale_method"),v=>store.set("control.upscale_method",v))),
          field("Crop",select(["center","disabled"],store.get("control.crop"),v=>store.set("control.crop",v))),
          field("Channels",select(["rgb","grayscale"],store.get("control.channel_mode"),v=>store.set("control.channel_mode",v))),
          field("Normalize",select(["none","per_image_minmax"],store.get("control.normalize"),v=>store.set("control.normalize",v))),
          toggle("Invert",store.get("control.invert"),v=>store.set("control.invert",v)),
        );
        if(store.get("control.preprocessor")==="depth_anything_v2")controlAdvanced.append(field("Preprocess px",number(store.get("control.preprocessor_resolution"),64,8192,64,v=>store.set("control.preprocessor_resolution",v))));
        modePanel.append(controlAdvanced);
      }
      const note=el("p","k2-note","The installed KREA2 control extension supports LoRA strength and latent-size matching. Start/end percentages are hidden because that extension does not implement them.");modePanel.append(note);
    }else{
      modePanel.append(el("p","k2-note","Text-to-image uses the native KREA2 loader, KREA text encoder, ComfyUI samplers, and selected VAE."));
    }
  };

  const runRow=el("div","k2-run-row"), generate=button("RENDER FILM FRAME","k2-generate"), batch=select([1,2,3,4].map(value=>({label:`×${value}`,value:String(value)})),String(store.get("batch_size") || 1),value=>store.set("batch_size",Number(value)),"k2-batch");
  const stop=button("Stop","k2-btn k2-btn-danger");stop.hidden=true;stop.onclick=()=>Promise.resolve(api.interrupt()).catch(showError);runRow.append(generate,batch,stop);
  const errorBox=el("div","k2-error");errorBox.hidden=true;

  const advanced=el("details","k2-advanced");advanced.open=!!store.get("advanced");
  advanced.append(el("summary","","Advanced film controls"));
  const negative=el("textarea","k2-textarea k2-negative");negative.value=store.get("negative_prompt") || "";negative.placeholder="Negative prompt (optional)";negative.oninput=()=>store.set("negative_prompt",negative.value);
  const advancedGrid=el("div","k2-inline-grid");
  const refineSampler=select(models.samplers,store.get("refinement.sampler"),v=>store.set("refinement.sampler",v));
  const refineScheduler=select(models.schedulers,store.get("refinement.scheduler"),v=>store.set("refinement.scheduler",v));
  const denoiseControl=number(store.get("denoise"),0,1,.01,v=>store.set("denoise",v));
  const refinementToggle=toggle("Refinement",store.get("refinement.enabled"),v=>store.set("refinement.enabled",v));
  const refineSteps=number(store.get("refinement.steps"),1,1000,1,v=>store.set("refinement.steps",v));
  const refineCfg=number(store.get("refinement.cfg"),0,100,.1,v=>store.set("refinement.cfg",v));
  const refineDenoise=number(store.get("refinement.denoise"),0,1,.01,v=>store.set("refinement.denoise",v));
  advancedGrid.append(field("Denoise",denoiseControl),refinementToggle,field("Refine steps",refineSteps),field("Refine CFG",refineCfg),field("Refine sampler",refineSampler),field("Refine scheduler",refineScheduler),field("Refine denoise",refineDenoise));
  advanced.append(negative,advancedGrid);
  advanced.ontoggle=()=>store.set("advanced",advanced.open);
  const previewToolbar=el("div","k2-preview-toolbar"), previewTitle=el("strong","","FINAL FILM FRAME");
  const fit=button("Fit","k2-btn k2-btn-quiet"), one=button("1:1","k2-btn k2-btn-quiet"), zoomOut=button("−","k2-btn k2-btn-icon"),zoomIn=button("+","k2-btn k2-btn-icon"),copyImage=button("Copy","k2-btn k2-btn-quiet"),saveImage=button("Save","k2-btn k2-btn-quiet"),previewFull=button("⛶","k2-btn k2-btn-icon");
  previewToolbar.append(previewTitle,fit,one,zoomOut,zoomIn,copyImage,saveImage,previewFull);
  const viewport=el("div","k2-viewport"), placeholder=el("div","k2-placeholder");placeholder.append(el("span","","K2"),el("strong","","Your film frame will appear here"),el("small","","Rendered locally in ComfyUI · IMAGE output remains connected"));
  const outputImage=el("img","k2-output-image");outputImage.hidden=true;viewport.append(placeholder,outputImage);
  const previewFoot=el("div","k2-preview-foot"), seedText=el("span","","Seed: —"), autosave=toggle("Auto-save",store.get("auto_save"),v=>store.set("auto_save",v));previewFoot.append(seedText,autosave);
  preview.append(previewToolbar,viewport,previewFoot);content.append(controls,preview);

  const promptBlock=el("section","k2-prompt-block"), promptHead=el("div","k2-prompt-head");promptHead.append(el("strong","","SCENE PROMPT"));
  const discover=button("Discover","k2-btn k2-btn-quiet"),history=button("History","k2-btn k2-btn-quiet"),addLora=button("+ Add LoRA","k2-btn k2-btn-quiet"),expandPrompt=button("Expand","k2-btn k2-btn-quiet");promptHead.append(discover,history,el("span","k2-spacer"),addLora,expandPrompt);
  const loraChips=el("div","k2-lora-chips");
  function renderLoraChips(){
    loraChips.replaceChildren(...(store.get("loras")||[]).filter(item=>item.enabled!==false&&item.name).map(item=>{
      const chip=button(`${item.name.split(/[\\/]/).at(-1).replace(/\.safetensors$/i,"")} ${Number(item.strength_model??1).toFixed(2)}${item.managed?" · ON":" ×"}`,`k2-lora-chip${item.managed?" is-managed":""}`);
      chip.title=item.managed?"Managed Film Studio LoRA — always enabled":"Remove this LoRA";chip.disabled=!!item.managed;if(!item.managed)chip.onclick=()=>store.set("loras",(store.get("loras")||[]).filter(row=>row!==item));return chip;
    }));
    loraChips.hidden=!loraChips.childElementCount;
  }
  const prompt=el("textarea","k2-prompt");prompt.value=store.get("prompt") || "";prompt.placeholder="Describe the scene, subject, lens, lighting, color grade, and mood…";prompt.oninput=()=>store.set("prompt",prompt.value);prompt.addEventListener("wheel",event=>event.stopPropagation(),{passive:true});prompt.addEventListener("pointerdown",event=>event.stopPropagation());promptBlock.append(promptHead,loraChips,prompt);renderLoraChips();
  const studioDeck=el("div","k2-studio-deck");studioDeck.append(size,parameters,stylesBlock,modePanel,advanced);
  controls.append(tabs,studioDeck,runRow,errorBox);
  const resizeGrip=el("button","k2-resize-grip");resizeGrip.type="button";resizeGrip.title="Drag to resize Krea 2 Film Studio";resizeGrip.setAttribute("aria-label","Resize Krea 2 Film Studio");
  resizeGrip.dataset.resizeVersion="6";
  resizeGrip.onmousedown=event=>{
    if(event.button!==0)return;
    event.preventDefault();event.stopPropagation();
    const startX=event.clientX,startY=event.clientY;
    const startSize=Array.isArray(node.size)?[node.size[0],node.size[1]]:[MIN_NODE_WIDTH,MIN_UI_HEIGHT];
    const rendered=root.getBoundingClientRect();
    const scale=Math.max(.05,rendered.width/(root.offsetWidth||rendered.width||1));
    const previousCursor=document.documentElement.style.cursor;
    document.documentElement.style.cursor="nwse-resize";resizeGrip.classList.add("is-resizing");
    const move=moveEvent=>{
      const next=[startSize[0]+(moveEvent.clientX-startX)/scale,startSize[1]+(moveEvent.clientY-startY)/scale];
      node.setSize?.(next);node.setDirtyCanvas?.(true,true);
    };
    const finish=()=>{document.documentElement.style.cursor=previousCursor;resizeGrip.classList.remove("is-resizing");window.removeEventListener("mousemove",move,true);window.removeEventListener("mouseup",finish,true);window.removeEventListener("blur",finish,true);};
    window.addEventListener("mousemove",move,true);window.addEventListener("mouseup",finish,true);window.addEventListener("blur",finish,true);
  };
  resizeGrip.ondragstart=event=>event.preventDefault();
  root.append(header,content,promptBlock,resizeGrip);

  function resetRunState(){generate.disabled=false;generate.textContent="RENDER FILM FRAME";stop.hidden=true;}
  function showError(error){errorBox.textContent=error?.message || String(error);errorBox.hidden=false;resetRunState();}
  function clearError(){errorBox.hidden=true;errorBox.textContent="";}
  async function refreshModels(force=false){
    const data=await kreaApi.models(force);Object.assign(models,data);
    const defaults=await kreaApi.defaults();models.presets=defaults.presets;models.styles=defaults.styles||[];
    const preserveOrSelect=(path,items,suggested="")=>{const current=store.get(path);if(!items.includes(current))store.set(path,(suggested&&items.includes(suggested)?suggested:items[0])||"");};
    preserveOrSelect("model",data.diffusion_models,data.suggested?.model);
    preserveOrSelect("clip",data.text_encoders,data.suggested?.clip);
    const currentVae=store.get("vae")||"";
    if(!data.vaes.includes(currentVae)||/qwen_image_vae/i.test(currentVae))store.set("vae",data.suggested?.vae||data.vaes[0]||"");
    preserveOrSelect("control.lora",data.loras,data.suggested?.control_lora);
    preserveOrSelect("sampler",data.samplers,"euler");
    preserveOrSelect("scheduler",data.schedulers,"simple");
    preserveOrSelect("refinement.sampler",data.samplers,store.get("sampler"));
    preserveOrSelect("refinement.scheduler",data.schedulers,store.get("scheduler"));
    const managed=[...(data.suggested?.managed_loras||[])];
    if(managed.length){const loras=[...(store.get("loras")||[])];let changed=false;managed.forEach(name=>{let item=loras.find(row=>row.name===name);if(!item){item={name,strength_model:1,strength_clip:1,enabled:true,managed:true};loras.push(item);changed=true;}else if(item.enabled===false||!item.managed){item.enabled=true;item.managed=true;changed=true;}});if(changed)store.set("loras",loras);}
    setOptions(styleSelect,[{label:"No style — use prompt only",value:""},...models.styles.map(item=>({label:item.label,value:item.value}))],store.get("cinematic_style")||"");renderStyleDetails();
    setOptions(sampler,data.samplers,store.get("sampler"));setOptions(scheduler,data.schedulers,store.get("scheduler"));
    setOptions(refineSampler,data.samplers,store.get("refinement.sampler"));setOptions(refineScheduler,data.schedulers,store.get("refinement.scheduler"));renderMode();
    return data;
  }
  function openSettingsView(){openSettings({store,models,refreshModels:()=>refreshModels(true),syncSockets:()=>syncSockets(node,store),showError});}
  settingsButton.onclick=openSettingsView;addLora.onclick=()=>openLoraBrowser({store,models});
  galleryButton.onclick=()=>openGallery({sessionItems,loadConfig:config=>store.replace(config),removeSession:item=>{const i=sessionItems.indexOf(item);if(i>=0)sessionItems.splice(i,1);},showError});
  promptStructureButton.onclick=()=>openPromptStructure();
  discover.onclick=()=>discoverPrompt(store);
  history.onclick=()=>openPromptHistory(value=>{store.set("prompt",value);prompt.value=value;});
  helpButton.onclick=()=>{const view=modal("KREA 2 FILM STUDIO HELP");view.body.innerHTML="<p>Choose the KREA 2 model, text encoder, and image VAE in Settings. Text to Film creates a new frame; Transform Frame preserves or restyles a reference; Directed Control follows a structural guide.</p><p>Describe the subject, lens, lighting, color grade, and mood in Scene Prompt. Press Ctrl/Cmd + Enter to render. IMAGE and LATENT remain available through the normal ComfyUI outputs.</p>";document.body.append(view.overlay);};
  fullButton.onclick=()=>root.requestFullscreen?.();previewFull.onclick=()=>viewport.requestFullscreen?.();
  expandPrompt.onclick=()=>{promptBlock.classList.toggle("is-expanded");expandPrompt.textContent=promptBlock.classList.contains("is-expanded")?"Collapse":"Expand";};
  fit.onclick=()=>{zoom=1;outputImage.style.transform="scale(1)";outputImage.classList.remove("is-native");viewport.scrollTo(0,0);};
  one.onclick=()=>{zoom=1;outputImage.style.transform="scale(1)";outputImage.classList.add("is-native");viewport.scrollTo(0,0);};
  zoomIn.onclick=()=>{zoom=Math.min(4,zoom+.25);outputImage.style.transform=`scale(${zoom})`;};zoomOut.onclick=()=>{zoom=Math.max(.25,zoom-.25);outputImage.style.transform=`scale(${zoom})`;};
  copyImage.onclick=async()=>{if(!currentImage)return;try{const blob=await fetch(kreaApi.viewUrl(currentImage)).then(r=>r.blob());await navigator.clipboard.write([new ClipboardItem({[blob.type]:blob})]);}catch(error){showError(error);}};
  saveImage.onclick=async()=>{if(!currentImage)return;if(currentImage.type!=="temp")return kreaApi.openFolder(currentImage).catch(showError);try{const saved=await kreaApi.saveTemp(currentImage,currentMetadata||{});currentImage=saved;saveImage.textContent="Saved";sessionItems.unshift({...saved,metadata:currentMetadata});}catch(error){showError(error);}};

  generate.onclick=async()=>{
    clearError();
    const ext=store.get("external")||{};
    if(!store.get("model")&&!(ext.model&&hasConnectedInput(node,"model")))return showError(new Error("Select a KREA model in Settings or connect MODEL."));
    if(!store.get("clip")&&!(ext.clip&&hasConnectedInput(node,"clip")))return showError(new Error("Select a KREA text encoder in Settings or connect CLIP."));
    if(!store.get("vae")&&!(ext.vae&&hasConnectedInput(node,"vae")))return showError(new Error("Select a KREA VAE in Settings or connect VAE."));
    if(store.get("mode")!=="t2i"&&!store.get("uploads.image")&&!hasConnectedInput(node,"image"))return showError(new Error("Upload an image or connect the IMAGE input."));
    if(store.get("mode")==="control"&&models.capabilities.control===false)return showError(new Error("KREA2 Control is unavailable because its installed nodes were not registered."));
    if(store.get("mode")==="i2i"&&store.get("i2i.pipeline")==="identity_edit"&&models.capabilities.identity_edit===false)return showError(new Error("KREA Identity Edit is unavailable because its installed nodes were not registered."));
    if(store.get("enhancer.enabled")&&models.capabilities.prompt_enhancer===false)return showError(new Error("Prompt enhancement is unavailable because TextGenerate was not registered."));
    if(store.get("mode")==="control"&&!store.get("control.lora"))return showError(new Error("Select the KREA Control LoRA."));
    rememberPrompt(store.get("prompt")||"");generate.disabled=true;generate.textContent="QUEUED…";stop.hidden=false;usedSeed=null;
    try{await app.queuePrompt(0,1);generate.textContent="GENERATING…";}catch(error){showError(error);}
  };
  prompt.onkeydown=event=>{if((event.ctrlKey||event.metaKey)&&event.key==="Enter"){event.preventDefault();generate.click();}};
  root.tabIndex=0;
  root.addEventListener("keydown",event=>{if(["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName))return;if(event.key.toLowerCase()==="g")galleryButton.click();if(event.key.toLowerCase()==="s")settingsButton.click();});
  root.addEventListener("paste",event=>{if(["INPUT","TEXTAREA"].includes(document.activeElement?.tagName))return;const file=[...(event.clipboardData?.files||[])].find(item=>item.type.startsWith("image/"));if(!file||store.get("mode")==="t2i")return;event.preventDefault();modePanel.querySelector(".k2-upload")?.load?.(file);});

  const handleExecuted=message=>{
    if(message?.used_seed?.length){usedSeed=Number(message.used_seed[0]);seedText.textContent=`Seed: ${usedSeed}`;if(store.get("randomize_seed")){store.set("seed",usedSeed);seed.value=usedSeed;}}
    const images=message?.images || [];
    if(!images.length)return;
    resetRunState();placeholder.hidden=true;outputImage.hidden=false;
    const baseMetadata=metadataSnapshot(store.get(),usedSeed);
    const entries=images.map((item,index)=>{
      const image={filename:item.filename,subfolder:item.subfolder||"",type:item.type|| (store.get("auto_save")?"output":"temp")};
      const metadata={...baseMetadata,batch_index:index,batch_count:images.length};
      if(image.type==="output")kreaApi.metadata(image,metadata).catch(console.warn);
      return {...image,metadata};
    });
    sessionItems.unshift(...entries);
    const first=entries[0];currentImage={filename:first.filename,subfolder:first.subfolder,type:first.type};
    currentMetadata=first.metadata;outputImage.src=`${kreaApi.viewUrl(currentImage)}&t=${Date.now()}`;
    saveImage.textContent=currentImage.type==="temp"?"Save":"Open";
    if(store.get("notification_sound"))playComplete();
  };

  let panning=false,panX=0,panY=0,panLeft=0,panTop=0;
  viewport.onpointerdown=event=>{if(outputImage.hidden||event.button!==0)return;panning=true;panX=event.clientX;panY=event.clientY;panLeft=viewport.scrollLeft;panTop=viewport.scrollTop;viewport.setPointerCapture(event.pointerId);viewport.classList.add("is-panning");};
  viewport.onpointermove=event=>{if(!panning)return;viewport.scrollLeft=panLeft-(event.clientX-panX);viewport.scrollTop=panTop-(event.clientY-panY);};
  viewport.onpointerup=viewport.onpointercancel=()=>{panning=false;viewport.classList.remove("is-panning");};

  function syncControlsFromState(){
    prompt.value=store.get("prompt")||"";negative.value=store.get("negative_prompt")||"";
    width.value=store.get("width");height.value=store.get("height");dimensionBadge.textContent=`${store.get("width")} × ${store.get("height")}`;
    const dimensionValue=`${store.get("width")}x${store.get("height")}`;preset.value=[...preset.options].some(option=>option.value===dimensionValue)?dimensionValue:presetItems[0].value;
    aspect.value=store.get("aspect_ratio")||"custom";mp.input.value=String(store.get("megapixels")||1);
    customResolution.querySelector("input").checked=!!store.get("custom_resolution");renderCustomResolution();styleSelect.value=store.get("cinematic_style")||"";renderStyleDetails();
    steps.value=store.get("steps");cfg.value=store.get("cfg");seed.value=store.get("seed");random.querySelector("input").checked=!!store.get("randomize_seed");
    sampler.value=store.get("sampler");scheduler.value=store.get("scheduler");presetSelect.value=store.get("preset")||"Custom";batch.value=String(store.get("batch_size")||1);
    denoiseControl.value=store.get("denoise");refinementToggle.querySelector("input").checked=!!store.get("refinement.enabled");refineSteps.value=store.get("refinement.steps");refineCfg.value=store.get("refinement.cfg");refineDenoise.value=store.get("refinement.denoise");
    refineSampler.value=store.get("refinement.sampler");refineScheduler.value=store.get("refinement.scheduler");advanced.open=!!store.get("advanced");autosave.querySelector("input").checked=!!store.get("auto_save");
    renderLoraChips();syncSockets(node,store);renderMode();
  }
  store.subscribe((path)=>{
    if(path==="*")syncControlsFromState();
    if(path==="prompt"&&prompt.value!==store.get("prompt"))prompt.value=store.get("prompt")||"";
    if(path==="loras")renderLoraChips();
    if(path==="auto_save")autosave.querySelector("input").checked=!!store.get("auto_save");
    if(path==="advanced"){advanced.open=!!store.get("advanced");renderMode();}
  });
  async function bootstrapAssets(){let refresh=false;try{const assets=await kreaApi.ensureAssets();refresh=!!assets.changed;if(assets.restart_required)showError(new Error("KREA ControlNet nodes were installed. Restart ComfyUI once to activate Directed Control."));}catch(error){showError(new Error(`Managed asset check failed: ${error.message}`));}await refreshModels(refresh);}
  renderMode();syncSockets(node,store);bootstrapAssets().catch(showError);
  return {root,store,models,handleExecuted,showError,handleStopped:resetRunState,syncSockets:()=>syncSockets(node,store)};
}
