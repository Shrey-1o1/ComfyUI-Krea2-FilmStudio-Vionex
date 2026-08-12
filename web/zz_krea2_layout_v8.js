import { app } from "../../scripts/app.js";

function applyReferenceLayout(node,attempt=0){
  const widget=(node.widgets||[]).find(item=>item.name==="krea2_ui");
  const element=widget?.element;
  const root=element?.classList?.contains("k2-app")?element:element?.querySelector?.(".k2-app");
  if(!root){if(attempt<20)requestAnimationFrame(()=>applyReferenceLayout(node,attempt+1));return;}
  const controls=root.querySelector(".k2-controls");
  const prompt=root.querySelector(".k2-prompt-block");
  const grip=root.querySelector(".k2-resize-grip");
  if(prompt&&prompt.parentElement===controls)root.insertBefore(prompt,grip||null);
  root.dataset.layoutVersion="8";
  node.setDirtyCanvas?.(true,true);
}

app.registerExtension({
  name:"Krea2.OneNode.Layout.v8",
  nodeCreated(node){
    if(node.comfyClass==="Krea2OneNode"||node.type==="Krea2OneNode")applyReferenceLayout(node);
  },
});
