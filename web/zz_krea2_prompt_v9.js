import { app } from "../../scripts/app.js";
import { button } from "./js/components.js";
import { openPromptStructure } from "./js/prompt_structure.js?v=film-studio-9";

function applyPromptFixes(node,attempt=0){
  const widget=(node.widgets||[]).find(item=>item.name==="krea2_ui");
  const element=widget?.element;
  const root=element?.classList?.contains("k2-app")?element:element?.querySelector?.(".k2-app");
  if(!root){if(attempt<20)requestAnimationFrame(()=>applyPromptFixes(node,attempt+1));return;}
  const prompt=root.querySelector(".k2-prompt");
  if(prompt&&!prompt.dataset.scrollFix){prompt.dataset.scrollFix="9";prompt.addEventListener("wheel",event=>event.stopPropagation(),{passive:true});prompt.addEventListener("pointerdown",event=>event.stopPropagation());}
  const actions=root.querySelector(".k2-header-actions");
  if(actions&&!actions.querySelector(".k2-prompt-structure-button")){
    const structure=button("Prompt Structure","k2-btn k2-btn-quiet k2-prompt-structure-button");structure.onclick=()=>openPromptStructure();
    const gallery=[...actions.children].find(item=>item.textContent.trim()==="Gallery");gallery?.after(structure);
  }
  root.querySelectorAll(".k2-tab").forEach(tab=>{
    if(tab.dataset.sizeLock)return;tab.dataset.sizeLock="9";
    tab.addEventListener("pointerdown",()=>{tab._k2NodeSize=Array.isArray(node.size)?[node.size[0],node.size[1]]:null;},{capture:true});
    tab.addEventListener("click",()=>{const size=tab._k2NodeSize;if(size)requestAnimationFrame(()=>{node.setSize?.(size);node.setDirtyCanvas?.(true,true);});});
  });
  root.dataset.promptVersion="9";
}

app.registerExtension({
  name:"Krea2.OneNode.Prompt.v9",
  nodeCreated(node){
    if(node.comfyClass==="Krea2OneNode"||node.type==="Krea2OneNode")applyPromptFixes(node);
  },
});
