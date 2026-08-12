import { app } from "../../scripts/app.js";

function restoreThroughLayout(node,size){
  if(!size)return;
  const restore=()=>{node.setSize?.([size[0],size[1]]);node.setDirtyCanvas?.(true,true);};
  queueMicrotask(restore);
  requestAnimationFrame(()=>{restore();requestAnimationFrame(restore);});
  setTimeout(restore,80);
  setTimeout(restore,180);
}

function attachSizeLock(node,attempt=0){
  const widget=(node.widgets||[]).find(item=>item.name==="krea2_ui");
  const element=widget?.element;
  const root=element?.classList?.contains("k2-app")?element:element?.querySelector?.(".k2-app");
  if(!root){if(attempt<30)requestAnimationFrame(()=>attachSizeLock(node,attempt+1));return;}
  root.querySelectorAll(".k2-tab").forEach(tab=>{
    if(tab.dataset.sizeLock==="11")return;
    tab.dataset.sizeLock="11";
    tab.addEventListener("click",()=>{
      const preserved=Array.isArray(node.size)?[node.size[0],node.size[1]]:null;
      restoreThroughLayout(node,preserved);
    },true);
  });
  root.dataset.sizeLockVersion="11";
}

app.registerExtension({
  name:"Krea2.OneNode.SizeLock.v11",
  nodeCreated(node){
    if(node.comfyClass==="Krea2OneNode"||node.type==="Krea2OneNode")attachSizeLock(node);
  },
});
