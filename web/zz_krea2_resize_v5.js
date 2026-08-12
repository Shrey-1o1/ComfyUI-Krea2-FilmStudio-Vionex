import { app } from "../../scripts/app.js";

const MIN_NODE_WIDTH=900;
const MIN_UI_HEIGHT=420;

function attachResizeGrip(node,attempt=0){
  node.resizable=true;
  const widget=(node.widgets||[]).find(item=>item.name==="krea2_ui");
  const element=widget?.element;
  const root=element?.classList?.contains("k2-app")?element:element?.querySelector?.(".k2-app");
  if(!root){if(attempt<20)requestAnimationFrame(()=>attachResizeGrip(node,attempt+1));return;}
  if(root.querySelector(".k2-resize-grip"))return;
  const grip=document.createElement("button");grip.type="button";grip.className="k2-resize-grip";grip.title="Drag to resize Krea 2 Film Studio";grip.setAttribute("aria-label","Resize Krea 2 Film Studio");
  grip.onpointerdown=event=>{
    if(event.button!==0)return;
    event.preventDefault();event.stopPropagation();
    const startX=event.clientX,startY=event.clientY;
    const startSize=Array.isArray(node.size)?[node.size[0],node.size[1]]:[MIN_NODE_WIDTH,MIN_UI_HEIGHT];
    const rendered=root.getBoundingClientRect();
    const scale=Math.max(.05,rendered.width/(root.offsetWidth||rendered.width||1));
    grip.setPointerCapture?.(event.pointerId);grip.classList.add("is-resizing");
    const move=moveEvent=>{node.setSize?.([startSize[0]+(moveEvent.clientX-startX)/scale,startSize[1]+(moveEvent.clientY-startY)/scale]);node.setDirtyCanvas?.(true,true);};
    const finish=()=>{grip.classList.remove("is-resizing");grip.removeEventListener("pointermove",move);grip.removeEventListener("pointerup",finish);grip.removeEventListener("pointercancel",finish);};
    grip.addEventListener("pointermove",move);grip.addEventListener("pointerup",finish);grip.addEventListener("pointercancel",finish);
  };
  root.append(grip);
}

app.registerExtension({
  name:"Krea2.OneNode.Resizable.v5",
  nodeCreated(node){
    if(node.comfyClass==="Krea2OneNode"||node.type==="Krea2OneNode")attachResizeGrip(node);
  },
});
