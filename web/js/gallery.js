import {button, el, modal} from "./components.js";
import {kreaApi} from "./api.js";

function imageCard(item, actions) {
  const card = el("article", "k2-gallery-card");
  const image = el("img"); image.loading = "lazy"; image.src = kreaApi.viewUrl(item);
  const meta = item.metadata || {};
  const info = el("div", "k2-gallery-info");
  info.append(el("strong", "", `${meta.mode || "KREA2"} · ${meta.width || "?"}×${meta.height || "?"}`), el("p", "", meta.prompt || "No prompt metadata"));
  const buttons = el("div", "k2-gallery-actions");
  const load = button("Load settings", "k2-btn k2-btn-accent"); load.onclick=()=>actions.load(meta.config);
  const copy = button("Copy prompt", "k2-btn k2-btn-quiet"); copy.onclick=()=>navigator.clipboard?.writeText(meta.prompt || "");
  const open = button("Open folder", "k2-btn k2-btn-quiet"); open.onclick=()=>kreaApi.openFolder(item).catch(actions.error);
  const forget = button("Remove", "k2-btn k2-btn-danger"); forget.onclick=()=>{ actions.remove(item); card.remove(); };
  buttons.append(load,copy,open,forget); card.append(image,info,buttons);
  image.onclick=()=>{ image.requestFullscreen?.(); };
  return card;
}

export async function openGallery({sessionItems, loadConfig, removeSession, showError}) {
  const view = modal("GALLERY");
  const status = el("div", "k2-gallery-status", "Loading…");
  const grid = el("div", "k2-gallery-grid"); view.body.append(status,grid); document.body.append(view.overlay);
  try {
    const disk = await kreaApi.gallery(0, 100);
    const seen = new Set();
    const items = [...sessionItems, ...(disk.items || [])].filter(item => {
      const key=`${item.type}/${item.subfolder}/${item.filename}`; if(seen.has(key)) return false; seen.add(key); return true;
    });
    status.textContent = items.length ? `${items.length} image${items.length===1?"":"s"}` : "No KREA 2 images yet.";
    const actions = {load: config=>{if(config){loadConfig(config);view.hide();}}, remove:removeSession, error:showError};
    items.forEach(item=>grid.append(imageCard(item,actions)));
  } catch(error) { status.textContent=error.message; showError(error); }
}
