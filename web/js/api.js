import { api } from "../../../scripts/api.js";

async function json(path, options) {
  const response = await api.fetchApi(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

export const kreaApi = {
  models: refresh => json(`/krea2_one/models${refresh ? "?refresh=1" : ""}`),
  defaults: () => json("/krea2_one/defaults"),
  ensureAssets: () => json("/krea2_one/ensure_assets", {method:"POST"}),
  gallery: (offset=0, limit=60) => json(`/krea2_one/gallery?offset=${offset}&limit=${limit}`),
  metadata: (image, metadata) => json("/krea2_one/metadata", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({...image, metadata}),
  }),
  saveTemp: (image, metadata) => json("/krea2_one/save_temp", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({...image, metadata}),
  }),
  openFolder: image => json("/krea2_one/open_folder", {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(image),
  }),
  loraMetadata: name => json(`/krea2_one/lora_metadata?name=${encodeURIComponent(name)}`),
  async upload(file) {
    const form = new FormData();
    form.append("image", file, file.name);
    form.append("type", "input");
    form.append("overwrite", "false");
    const response = await api.fetchApi("/upload/image", {method:"POST", body:form});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Image upload failed.");
    return {...data, path: data.subfolder ? `${data.subfolder}/${data.name}` : data.name};
  },
  viewUrl(image) {
    const query = new URLSearchParams({filename:image.filename, subfolder:image.subfolder || "", type:image.type || "output"});
    return api.apiURL(`/view?${query}`);
  },
};
