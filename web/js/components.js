export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function button(label, className="k2-btn") {
  const node = el("button", className, label);
  node.type = "button";
  return node;
}

function animateAdjustment(node) {
  node.animate?.([
    {transform:"translateY(0) scale(1)", boxShadow:"0 0 0 0 rgba(80,150,255,0)"},
    {transform:"translateY(-1px) scale(1.012)", boxShadow:"0 0 0 3px rgba(80,150,255,.18)"},
    {transform:"translateY(0) scale(1)", boxShadow:"0 0 0 0 rgba(80,150,255,0)"},
  ], {duration:180,easing:"ease-out"});
}

export function field(label, control, hint="") {
  const wrap = el("label", "k2-field");
  wrap.append(el("span", "k2-label", label), control);
  if (hint) wrap.append(el("span", "k2-hint", hint));
  return wrap;
}

export function select(items, value, onChange, className="") {
  const node = el("select", `k2-input ${className}`.trim());
  setOptions(node, items, value);
  node.onchange = () => { animateAdjustment(node); onChange(node.value); };
  return node;
}

export function setOptions(node, items, value) {
  const current = value ?? node.value;
  const makeOption = item => {
    const option = el("option");
    if (typeof item === "object") { option.value = item.value; option.textContent = item.label; }
    else { option.value = item; option.textContent = item; }
    return option;
  };
  node.replaceChildren(...(items || []).map(item => {
    if (item && typeof item === "object" && Array.isArray(item.items)) {
      const group = el("optgroup");
      group.label = item.group || item.label || "";
      group.append(...item.items.map(makeOption));
      return group;
    }
    return makeOption(item);
  }));
  if ([...node.options].some(option => option.value === String(current))) node.value = current;
}

export function number(value, min, max, step, onChange) {
  const node = el("input", "k2-input");
  Object.assign(node, {type:"number", value, min, max, step});
  node.onchange = () => { animateAdjustment(node); onChange(Number(node.value)); };
  return node;
}

export function stepper(value, min, max, step, onChange) {
  const wrap = el("div", "k2-stepper");
  const minus = button("−", "k2-stepper-btn");
  const input = number(value, min, max, step, onChange);
  const plus = button("+", "k2-stepper-btn");
  const adjust = direction => {
    const next = Math.min(max, Math.max(min, Number(input.value) + direction * step));
    const decimals = String(step).includes(".") ? String(step).split(".")[1].length : 0;
    input.value = Number(next.toFixed(decimals));
    animateAdjustment(wrap);
    onChange(Number(input.value));
  };
  minus.onclick = () => adjust(-1);
  plus.onclick = () => adjust(1);
  wrap.append(minus, input, plus);
  wrap.input = input;
  return wrap;
}

export function textInput(value, onChange, placeholder="") {
  const node = el("input", "k2-input");
  Object.assign(node, {type:"text", value:value || "", placeholder});
  node.oninput = () => onChange(node.value);
  return node;
}

export function toggle(label, checked, onChange) {
  const wrap = el("label", "k2-toggle");
  const input = el("input"); input.type = "checkbox"; input.checked = !!checked;
  const track = el("span", "k2-toggle-track");
  input.onchange = () => { animateAdjustment(wrap); onChange(input.checked); };
  wrap.append(el("span", "k2-toggle-label", label), input, track);
  return wrap;
}

export function modal(title) {
  const overlay = el("div", "k2-overlay");
  const panel = el("section", "k2-modal");
  const head = el("header", "k2-modal-head");
  const close = button("× Close", "k2-btn k2-btn-quiet");
  head.append(el("h2", "", title), close);
  const body = el("div", "k2-modal-body");
  panel.append(head, body); overlay.append(panel);
  let key;
  const hide = () => { overlay.remove(); document.removeEventListener("keydown", key); };
  close.onclick = hide;
  overlay.onclick = event => { if (event.target === overlay) hide(); };
  key = event => { if (event.key === "Escape") hide(); };
  document.addEventListener("keydown", key);
  return {overlay, panel, head, body, close, hide};
}

export function section(title) {
  const node = el("section", "k2-settings-section");
  node.append(el("h3", "", title));
  return node;
}
