// A uniquely named cache bridge ensures existing ComfyUI tabs receive the latest Film Studio stylesheet.
const styleId = "krea2-one-node-style";
const href = `${new URL("./css/krea2_one_node.css", import.meta.url).href}?v=film-studio-6`;
let link = document.getElementById(styleId);
if (!link) {
  link = document.createElement("link");
  link.id = styleId;
  link.rel = "stylesheet";
  document.head.append(link);
}
if (link.href !== href) link.href = href;
