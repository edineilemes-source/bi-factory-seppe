import React,{useEffect,useRef,useState} from "react";
import {Canvas,Rect,Textbox,Circle,Line} from "fabric";
const FORMATS={landscape:{width:1280,height:720,label:"Paisagem · 16:9"},portrait:{width:794,height:1123,label:"Retrato · A4"},long:{width:1280,height:1800,label:"Dashboard longo"}};
export default function FreeCanvasExperiment({onClose}){
 const element=useRef(null),fabric=useRef(null);
 const [format,setFormat]=useState("landscape"),[page,setPage]=useState(FORMATS.landscape),[status,setStatus]=useState(""),[zoom,setZoom]=useState(0.75);
 const {width,height}=page;
 useEffect(()=>{
  const canvas=new Canvas(element.current,{width:FORMATS.landscape.width,height:FORMATS.landscape.height,backgroundColor:"#ffffff",preserveObjectStacking:true,selection:true});
  fabric.current=canvas;
  canvas.add(new Textbox("Dashboard experimental — arraste e redimensione",{left:30,top:28,width:650,fontSize:26,fontWeight:"bold",fill:"#15304b"}));
  canvas.add(new Rect({left:35,top:110,width:380,height:240,fill:"#dbeafe",stroke:"#2563eb",strokeWidth:2,rx:8,ry:8}));
  canvas.add(new Rect({left:445,top:125,width:270,height:180,fill:"#dcfce7",stroke:"#16a34a",strokeWidth:2,rx:8,ry:8}));
  canvas.add(new Circle({left:480,top:145,radius:58,fill:"#f59e0b"}));
  canvas.add(new Textbox("Gráfico A",{left:60,top:135,width:200,fontSize:24,fill:"#1e40af"}));
  canvas.add(new Textbox("Gráfico B",{left:740,top:155,width:240,fontSize:24,fill:"#166534"}));
  canvas.setActiveObject(canvas.item(1));canvas.requestRenderAll();
  return()=>{fabric.current=null;canvas.dispose()};
 },[]);
 function add(kind){
  const c=fabric.current;if(!c)return;
  const top=Math.min(200+(c.getObjects().length*35),height-140);
  const obj=kind==="text"?new Textbox("Edite este texto com duplo clique",{left:90,top,width:320,fontSize:22,fill:"#1e293b"}):new Rect({left:90,top,width:260,height:160,fill:kind==="chart"?"#bfdbfe":"#fef3c7",stroke:"#64748b",strokeWidth:2,rx:6,ry:6});
  c.add(obj);c.setActiveObject(obj);c.requestRenderAll();
 }
 function changeFormat(next){const dimensions=FORMATS[next];setFormat(next);setPage(dimensions);fabric.current?.setDimensions({width:dimensions.width,height:dimensions.height});fabric.current?.requestRenderAll();setStatus("Formato alterado; os objetos preservam suas coordenadas. Objetos fora da página podem ser reposicionados.")}
 function extend(){setPage(old=>{const next={...old,height:old.height+700};fabric.current?.setDimensions({width:next.width,height:next.height});fabric.current?.requestRenderAll();return next})}
 function exportJson(){const c=fabric.current;if(!c)return;const blob=new Blob([JSON.stringify({version:1,page:{width,height,format},canvas:c.toJSON()},null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="bi-factory-canvas-experimental.json";a.click();URL.revokeObjectURL(url);setStatus("JSON experimental exportado; não substitui o produto salvo.")}
 return <div style={{position:"fixed",inset:0,zIndex:1000,background:"#edf2f7",display:"flex",flexDirection:"column",fontFamily:"Arial,sans-serif"}}>
  <div style={{display:"flex",alignItems:"center",gap:10,padding:12,background:"#fff",borderBottom:"1px solid #cbd5e1",flexWrap:"wrap"}}>
   <strong>Canvas Livre · Laboratório Fabric.js</strong>
   <button onClick={()=>add("chart")}>+ Bloco de gráfico</button><button onClick={()=>add("shape")}>+ Figura</button><button onClick={()=>add("text")}>+ Texto</button>
   <label>Formato <select value={format} onChange={e=>changeFormat(e.target.value)}>{Object.entries(FORMATS).map(([key,value])=><option key={key} value={key}>{value.label}</option>)}</select></label>
   <button onClick={extend}>+ 700 px de página</button>
   <label>Zoom <select value={zoom} onChange={e=>setZoom(Number(e.target.value))}><option value={0.5}>50%</option><option value={0.75}>75%</option><option value={1}>100%</option></select></label>
   <button onClick={exportJson}>Exportar JSON de teste</button>
   <button onClick={onClose} style={{marginLeft:"auto"}}>Fechar laboratório</button>
  </div>
  <div style={{padding:"8px 16px",fontSize:13,color:"#475569"}}>Página: {width} × {height} px. Experimento isolado: mova objetos, redimensione pelas alças e sobreponha livremente. Duplo clique edita texto. Não grava produtos existentes. {status}</div>
  <div style={{flex:1,overflow:"auto",padding:24}}>
   <div style={{width:width*zoom,height:height*zoom,margin:"0 auto",background:"#fff",boxShadow:"0 4px 22px #0002",position:"relative"}}>
    <div style={{width,height,transform:`scale(${zoom})`,transformOrigin:"top left"}}><canvas ref={element}/></div>
   </div>
  </div>
 </div>
}
