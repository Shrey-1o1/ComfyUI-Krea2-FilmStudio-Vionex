import { app } from "../../scripts/app.js";

const DOM_WIDGET_INSET=10;

function socketHeight(node){
  return Math.max(node.inputs?.length||0,node.outputs?.length||0)*20;
}

function findRoot(node){
  const widget=(node.widgets||[]).find(item=>item.name==="krea2_ui");
  const element=widget?.element;
  return element?.classList?.contains("k2-app")?element:element?.querySelector?.(".k2-app");
}

function fitRoot(node,attempt=0){
  const root=findRoot(node);
  if(!root){if(attempt<30)requestAnimationFrame(()=>fitRoot(node,attempt+1));return;}
  const width=Math.max(1,Number(node.size?.[0]||0)-DOM_WIDGET_INSET*2);
  const height=Math.max(1,Number(node.size?.[1]||0)-socketHeight(node)-DOM_WIDGET_INSET*2);
  root.style.width=`${width}px`;
  root.style.height=`${height}px`;
  root.dataset.fitVersion="10";
}

app.registerExtension({
  name:"Krea2.OneNode.Fit.v10",
  nodeCreated(node){
    if(node.comfyClass!=="Krea2OneNode"&&node.type!=="Krea2OneNode")return;
    const resized=node.onResize;
    node.onResize=function(){
      const result=resized?.apply(this,arguments);
      fitRoot(this);
      requestAnimationFrame(()=>fitRoot(this));
      return result;
    };
    fitRoot(node);
  },
});
