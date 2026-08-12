import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { buildNodeUI } from "./js/ui.js?v=film-studio-11";

const styleId="krea2-one-node-style";
if(!document.getElementById(styleId)){
  const link=document.createElement("link");link.id=styleId;link.rel="stylesheet";link.href=`${new URL("./css/krea2_one_node.css",import.meta.url).href}?v=film-studio-11`;document.head.append(link);
}

const controllers=new Map();
const DEFAULT_NODE_WIDTH=1280;
const DEFAULT_UI_HEIGHT=500;
const MIN_NODE_WIDTH=900;
const MIN_UI_HEIGHT=420;
const DOM_WIDGET_INSET=10;

function socketHeight(node){
  return Math.max(node.inputs?.length||0,node.outputs?.length||0)*20;
}

function normalizedSize(node,size=node.size){
  const sockets=socketHeight(node);
  const width=Math.max(MIN_NODE_WIDTH,Number(size?.[0])||DEFAULT_NODE_WIDTH);
  const height=Math.max(MIN_UI_HEIGHT+sockets,Number(size?.[1])||DEFAULT_UI_HEIGHT+sockets);
  return [width,height];
}

function syncRootSize(node,size=node.size){
  const root=controllers.get(node)?.root;
  if(!root)return;
  const normalized=normalizedSize(node,size);
  root.style.width=`${Math.max(1,normalized[0]-DOM_WIDGET_INSET*2)}px`;
  root.style.height=`${Math.max(1,normalized[1]-socketHeight(node)-DOM_WIDGET_INSET*2)}px`;
}

function hideConfigWidget(node, widget){
  if(!widget)return;
  widget.hidden=true;
  widget.options={...(widget.options||{}),hidden:true};
  widget.computeSize=()=>[0,-4];
  widget.element?.style?.setProperty("display","none","important");
  requestAnimationFrame(()=>{
    const vueNode=document.querySelector(`.lg-node[data-node-id="${node.id}"]`);
    vueNode?.classList.add("k2-studio-node");
    const configInput=vueNode?.querySelector('[name="config"],textarea[aria-label="config"],input[aria-label="config"]');
    const configRow=configInput?.closest('[data-widget-name="config"]')||configInput?.parentElement?.parentElement?.parentElement;
    configRow?.style?.setProperty("display","none","important");
    if(vueNode&&(node.widgets||[]).includes(widget)){
      const snapshot=[...node.widgets];
      node.widgets=[];
      node.widgets=snapshot;
    }
    node.setDirtyCanvas?.(true,true);
  });
}

function suppressNativePreview(node){
  node.imgs=null;
  node.imageIndex=null;
  node.overIndex=null;
}

app.registerExtension({
  name:"Krea2.OneNode.v1",
  async beforeRegisterNodeDef(nodeType,nodeData){
    if(nodeData.name!=="Krea2OneNode")return;
    nodeType.prototype.resizable=true;
    const created=nodeType.prototype.onNodeCreated;
    const executed=nodeType.prototype.onExecuted;
    const removed=nodeType.prototype.onRemoved;
    const configured=nodeType.prototype.onConfigure;
    const resized=nodeType.prototype.onResize;

    nodeType.prototype.onNodeCreated=function(){
      created?.apply(this,arguments);this.color="#08090b";this.bgcolor="#08090b";this.resizable=true;
      const configWidget=(this.widgets||[]).find(widget=>widget.name==="config");
      if(!configWidget)return;
      hideConfigWidget(this,configWidget);
      suppressNativePreview(this);
      requestAnimationFrame(()=>{
        if(controllers.has(this))return;
        const controller=buildNodeUI(this,configWidget);controllers.set(this,controller);
        const self=this;
        const widget=this.addDOMWidget("krea2_ui","div",controller.root,{
          serialize:false,
          canvasOnly:false,
          getValue(){return null;},
          setValue(){},
          getMinHeight(){return MIN_UI_HEIGHT;},
          computeSize(){return normalizedSize(self);},
        });
        widget.computeLayoutSize=()=>({minWidth:1,minHeight:MIN_UI_HEIGHT});
        const initial=normalizedSize(this,[DEFAULT_NODE_WIDTH,DEFAULT_UI_HEIGHT+socketHeight(this)]);
        syncRootSize(this,initial);
        this.setSize(initial);
      });
    };
    nodeType.prototype.onExecuted=function(message){
      executed?.apply(this,arguments);
      suppressNativePreview(this);
      queueMicrotask(()=>suppressNativePreview(this));
      requestAnimationFrame(()=>suppressNativePreview(this));
      controllers.get(this)?.handleExecuted(message);
    };
    nodeType.prototype.onConfigure=function(info){
      configured?.apply(this,arguments);
      this.resizable=true;
      hideConfigWidget(this,(this.widgets||[]).find(widget=>widget.name==="config"));
      suppressNativePreview(this);
      requestAnimationFrame(()=>controllers.get(this)?.syncSockets());
    };
    nodeType.prototype.onRemoved=function(){controllers.delete(this);removed?.apply(this,arguments);};
    nodeType.prototype.onResize=function(size){
      const normalized=normalizedSize(this,size);
      if(Array.isArray(size)){size[0]=normalized[0];size[1]=normalized[1];}
      if(Array.isArray(this.size)){this.size[0]=normalized[0];this.size[1]=normalized[1];}
      else this.size=normalized;
      syncRootSize(this,normalized);
      return resized?.apply(this,arguments);
    };
  },
});

api.addEventListener("execution_error",event=>{
  const detail=event.detail||{};
  const failed=String(detail.display_node??detail.node_id??"");
  let matched=false;
  for(const [node,controller] of controllers){
    const id=String(node.id);
    if(failed===id||failed.startsWith(`${id}:`)){matched=true;controller.showError(new Error(detail.exception_message||"KREA 2 execution failed."));}
  }
  if(!matched)for(const controller of controllers.values())controller.handleStopped();
});

api.addEventListener("execution_interrupted",()=>{
  for(const controller of controllers.values())controller.handleStopped();
});

api.addEventListener("execution_success",()=>{
  for(const controller of controllers.values())controller.handleStopped();
});
