import {button, el, modal} from "./components.js";

const HISTORY_KEY = "krea2-one-node:prompt-history";

function readHistory() {
  try {
    const value = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(value) ? value.filter(item => typeof item === "string") : [];
  } catch (_) {
    return [];
  }
}

export function rememberPrompt(prompt) {
  const value = prompt.trim();
  if (!value) return;
  const history = [value, ...readHistory().filter(item => item !== value)].slice(0, 30);
  try { localStorage.setItem(HISTORY_KEY, JSON.stringify(history)); } catch (_) {}
}

export function openPromptHistory(onLoad) {
  const view = modal("PROMPT HISTORY");
  const list = el("div", "k2-prompt-history");
  const history = readHistory();
  history.forEach(prompt => {
    const row = el("div", "k2-history-row");
    const text = el("p", "", prompt);
    const load = button("Load", "k2-btn k2-btn-accent");
    const copy = button("Copy", "k2-btn k2-btn-quiet");
    load.onclick = () => { onLoad(prompt); view.hide(); };
    copy.onclick = () => navigator.clipboard?.writeText(prompt);
    row.append(text, load, copy);
    list.append(row);
  });
  if (!history.length) list.append(el("p", "k2-note", "Prompt history is empty. Prompts are added when you queue generation."));
  view.body.append(list);
  document.body.append(view.overlay);
}
