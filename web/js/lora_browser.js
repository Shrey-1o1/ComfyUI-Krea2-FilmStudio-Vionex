import {button, el, modal, textInput} from "./components.js";
import {kreaApi} from "./api.js";

const FAVORITES_KEY = "krea2-one-node:lora-favorites";
const RECENT_KEY = "krea2-one-node:lora-recent";

function readNames(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value.filter(item => typeof item === "string") : [];
  } catch (_) {
    return [];
  }
}

function writeNames(key, names) {
  try { localStorage.setItem(key, JSON.stringify(names)); } catch (_) {}
}

function shortName(name) {
  return name.split(/[\\/]/).at(-1)?.replace(/\.safetensors$/i, "") || name;
}

export function openLoraBrowser({store, models}) {
  const view = modal("ADD LORA");
  const tools = el("div", "k2-browser-tools");
  let mode = "all";
  let favorites = readNames(FAVORITES_KEY);
  let recent = readNames(RECENT_KEY);
  const search = textInput("", render, "Search LoRAs…");
  const all = button("All", "k2-btn k2-btn-accent");
  const favoriteFilter = button("Favorites", "k2-btn k2-btn-quiet");
  const recentFilter = button("Recent", "k2-btn k2-btn-quiet");
  const status = el("p", "k2-note", "Choose a LoRA. It remains a normal ComfyUI model patch and is never baked into the base model.");
  const list = el("div", "k2-browser-list");
  tools.append(search, all, favoriteFilter, recentFilter);
  view.body.append(tools, status, list);

  function setMode(value) {
    mode = value;
    [[all,"all"],[favoriteFilter,"favorites"],[recentFilter,"recent"]].forEach(([item,key]) => {
      item.className = `k2-btn ${mode === key ? "k2-btn-accent" : "k2-btn-quiet"}`;
    });
    render();
  }

  function add(name) {
    const rows = [...(store.get("loras") || [])];
    const index = rows.findIndex(item => item.name === name);
    if (index >= 0) rows[index] = {...rows[index], enabled:true};
    else rows.push({name, strength_model:1, strength_clip:1, enabled:true});
    store.set("loras", rows);
    recent = [name, ...recent.filter(item => item !== name)].slice(0, 20);
    writeNames(RECENT_KEY, recent);
    status.textContent = `Added ${shortName(name)}.`;
    kreaApi.loraMetadata(name).then(data => {
      if (data.triggers?.length) status.textContent = `Added ${shortName(name)}. Trigger: ${data.triggers.join(", ")}`;
    }).catch(() => {});
    render();
  }

  function render() {
    const query = search.value.trim().toLowerCase();
    let names = mode === "favorites" ? favorites : mode === "recent" ? recent : (models.loras || []);
    names = names.filter(name => (models.loras || []).includes(name) && name.toLowerCase().includes(query));
    const visible = names.slice(0, 250);
    list.replaceChildren(...visible.map(name => {
      const row = el("div", "k2-browser-row");
      const favorite = favorites.includes(name);
      const star = button(favorite ? "★" : "☆", "k2-btn k2-btn-icon");
      star.title = favorite ? "Remove favorite" : "Add favorite";
      star.onclick = () => {
        favorites = favorite ? favorites.filter(item => item !== name) : [name, ...favorites];
        writeNames(FAVORITES_KEY, favorites);
        render();
      };
      const choose = button(shortName(name), "k2-lora-choice");
      choose.title = name;
      choose.onclick = () => add(name);
      row.append(star, choose, el("small", "", name));
      return row;
    }));
    if (!visible.length) list.append(el("p", "k2-note", "No matching LoRAs."));
    if (names.length > visible.length) list.append(el("p", "k2-note", `Showing the first ${visible.length} matches. Narrow the search to see more.`));
  }

  all.onclick = () => setMode("all");
  favoriteFilter.onclick = () => setMode("favorites");
  recentFilter.onclick = () => setMode("recent");
  render();
  document.body.append(view.overlay);
  search.focus();
}
