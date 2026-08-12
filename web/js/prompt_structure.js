import { button, el, modal } from "./components.js";

export const PROMPT_STRUCTURE_SECTIONS = [
  ["Overall concept", "A [overall visual concept / genre / scene type] of [main subject] in [main environment or location]. [Describe the main visual event, impossible element, action, or central idea], creating a powerful sense of [emotion 1], [emotion 2], and [emotion 3]."],
  ["Main subject", "The [main subject] is positioned [where they appear in the frame], wearing [clothing / armor / costume / visual details]. [Describe pose, body position, facial direction, or action]. Their [expression / posture / body language] conveys [character emotion, intention, or state of mind]."],
  ["Key environmental element", "The [main environmental object / structure / vehicle / creature / secondary subject] is [detailed physical description]. It [describe orientation, movement, scale, or relationship to the subject]. [Mention important constraints such as no railings, no visible supports, damaged surfaces, floating objects, realistic physics, etc.]."],
  ["Background and atmosphere", "The background consists of [background environment] with [clouds / buildings / mountains / fog / stars / vegetation / crowds / landscape details] stretching [distance / direction / scale]. The environment feels [minimalist / dense / futuristic / abandoned / peaceful / chaotic / monumental], emphasizing [negative space / scale / depth / isolation / speed / tension / symmetry]. [Add realistic environmental interaction such as shadows, reflections, dust, rain, smoke, wind, atmospheric haze, etc.]."],
  ["Composition", "[wide / medium / close-up / extreme-wide] shot, subject positioned [center / lower-left third / right third / foreground], [dominant visual element] leading toward [direction], [symmetrical / asymmetrical / diagonal / centered] composition, [amount of negative space], [foreground/background layering], visually balanced cinematic geometry."],
  ["Camera", "[camera body], [lens focal length] [anamorphic / spherical] cinema lens, [shot size], [eye-level / low-angle / high-angle / aerial / ground-level] perspective, [locked-off / handheld / tracking / dolly / orbit / crane] camera, [shallow / medium / deep] depth of field, [motion blur characteristics], [lens distortion / lens softness / breathing / compression characteristics]."],
  ["Lighting", "[time of day / lighting situation], [key light direction], [soft / hard / diffused] illumination, [rim light / bounce light / practical lights / skylight / reflected light], realistic global illumination, [fog / bloom / volumetric rays / atmospheric scattering], [shadow characteristics]."],
  ["Color grade", "[dominant highlight colors], [shadow colors], [skin tone treatment], [saturation level], [contrast level], [black level], [highlight roll-off], [film stock / film emulation], [grain / halation / bloom characteristics], premium cinematic finish."],
  ["Mood", "[emotion 1], [emotion 2], [emotion 3], [emotion 4], [emotion 5], [overall emotional feeling]."],
  ["Style", "photorealistic live-action [genre] film still, [realistic anatomy / realistic materials / realistic fabric simulation / physically accurate movement], [environment detail], natural atmospheric perspective, cinematic depth, [practical-effects / premium VFX / naturalistic] realism, [IMAX-scale / intimate / epic / grounded] visual presentation, 2.39:1 widescreen, no text, no watermark, no exaggerated CGI look."],
];

export const PROMPT_STRUCTURE_TEXT = PROMPT_STRUCTURE_SECTIONS.map(([title,text])=>`${title}: ${text}`).join("\n\n");

export function openPromptStructure(){
  const view=modal("CINEMATIC PROMPT STRUCTURE");
  view.panel.classList.add("k2-prompt-structure-modal");
  const intro=el("p","k2-structure-intro","Use this structure as a guide. Replace every bracketed placeholder with details for your shot; omit any section that does not help the image.");
  const copy=button("Copy full template","k2-btn k2-btn-accent k2-structure-copy");
  copy.onclick=async()=>{try{await navigator.clipboard.writeText(PROMPT_STRUCTURE_TEXT);copy.textContent="Copied";setTimeout(()=>copy.textContent="Copy full template",1400);}catch{copy.textContent="Copy failed";}};
  const grid=el("div","k2-structure-grid");
  PROMPT_STRUCTURE_SECTIONS.forEach(([title,text])=>{const card=el("section","k2-structure-card");card.append(el("h3","",title),el("p","",text));grid.append(card);});
  view.body.append(intro,copy,grid);document.body.append(view.overlay);
  return view;
}
