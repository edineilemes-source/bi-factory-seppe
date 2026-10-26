import React,{useEffect,useRef,useState} from "react";
import {Canvas,Rect,Textbox,Circle,FabricImage} from "fabric";
const FORMATS={landscape:{width:1280,height:720,label:"Paisagem · 16:9"},portrait:{width:794,height:1123,label:"Retrato · A4"},long:{width:1280,height:1800,label:"Dashboard longo"}};
export default function FreeCanvasExperiment({onClose}){
 const element=useRef(null),fabric=useRef(null),chartConfigsRef=useRef({});
 const [chartDialog,setChartDialog]=useState(null),[chartConfigs,setChartConfigs]=useState({}),[format,setFormat]=useState("landscape"),[page,setPage]=useState(FORMATS.landscape),[status,setStatus]=useState(""),[zoom,setZoom]=useState(0.75);
 const {width,height}=page;
 const [selectedObject,setSelectedObject]=useState(false);
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
  const onDoubleClick=e=>{const id=e.target?.chartId;if(id)setChartDialog({id,item:chartConfigsRef.current[id]});};
  canvas.on("mouse:dblclick",onDoubleClick);
  const syncSelection=()=>setSelectedObject(Boolean(canvas.getActiveObject()));
  canvas.on("selection:created",syncSelection);canvas.on("selection:updated",syncSelection);canvas.on("selection:cleared",syncSelection);
  const onKey=e=>{if(!["Delete","Backspace"].includes(e.key)||e.target?.closest?.("input,textarea,[contenteditable=true]")||document.getElementById("free-chart-frame"))return;const active=canvas.getActiveObjects();if(active.length){canvas.discardActiveObject();active.forEach(obj=>canvas.remove(obj));canvas.requestRenderAll();setSelectedObject(false);}};
  window.addEventListener("keydown",onKey);
  return()=>{window.removeEventListener("keydown",onKey);fabric.current=null;canvas.dispose()};
 },[]);
 useEffect(()=>{if(!chartDialog)return;const listener=e=>{if(e.origin!==location.origin||e.source!==document.getElementById("free-chart-frame")?.contentWindow)return;if(e.data?.type==="bi-factory:studio-ready")e.source.postMessage({type:"bi-factory:load-product",items:chartDialog.item?[chartDialog.item]:[]},e.origin);if(e.data?.type==="bi-factory:apply-chart"){const item=e.data.components?.[0];if(!item){setStatus("Nenhum gráfico devolvido. Crie um gráfico e clique em Aplicar ao produto.");return;}const c=fabric.current;if(!c)return;const id=chartDialog.id||crypto.randomUUID();chartConfigsRef.current[id]=item;setChartConfigs({...chartConfigsRef.current});const old=c.getObjects().find(o=>o.chartId===id);const pos=old?{left:old.left,top:old.top,width:old.getScaledWidth(),height:old.getScaledHeight()}:{left:100,top:190,width:440,height:280};setChartDialog(null);if(!e.data.preview){setStatus("O ECharts devolveu a configuração, mas não gerou a imagem. Verifique se o gráfico foi desenhado.");return;}FabricImage.fromURL(e.data.preview).then(img=>{if(fabric.current!==c)return;img.set({left:pos.left,top:pos.top,scaleX:pos.width/img.width,scaleY:pos.height/img.height});img.chartId=id;if(old)c.remove(old);c.add(img);c.setActiveObject(img);c.requestRenderAll();setSelectedObject(true);setStatus("Gráfico ECharts renderizado no canvas. Duplo clique para editar.")}).catch(err=>setStatus("Falha ao carregar a imagem do gráfico: "+err.message));}};window.addEventListener("message",listener);return()=>window.removeEventListener("message",listener)},[chartDialog]);
 function removeSelected(){const c=fabric.current;if(!c)return;const objects=c.getActiveObjects();c.discardActiveObject();objects.forEach(obj=>c.remove(obj));c.requestRenderAll();setSelectedObject(false)}
 function add(kind){
  const c=fabric.current;if(!c)return;
  const top=Math.min(200+(c.getObjects().length*35),height-140);
  const obj=kind==="text"?new Textbox("Edite este texto com duplo clique",{left:90,top,width:320,fontSize:22,fill:"#1e293b"}):new Rect({left:90,top,width:260,height:160,fill:kind==="chart"?"#bfdbfe":"#fef3c7",stroke:"#64748b",strokeWidth:2,rx:6,ry:6});
  c.add(obj);c.setActiveObject(obj);c.requestRenderAll();
 }
 function changeFormat(next){const dimensions=FORMATS[next];setFormat(next);setPage(dimensions);fabric.current?.setDimensions({width:dimensions.width,height:dimensions.height});fabric.current?.requestRenderAll();setStatus("Formato alterado; os objetos preservam suas coordenadas. Objetos fora da página podem ser reposicionados.")}
 function extend(){setPage(old=>{const next={...old,height:old.height+700};fabric.current?.setDimensions({width:next.width,height:next.height});fabric.current?.requestRenderAll();return next})}
 function exportJson(){const c=fabric.current;if(!c)return;const blob=new Blob([JSON.stringify({version:1,page:{width,height,format},canvas:c.toJSON(["chartId"]),chartConfigs:chartConfigsRef.current},null,2)],{type:"application/json"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="bi-factory-canvas-experimental.json";a.click();URL.revokeObjectURL(url);setStatus("JSON experimental exportado; não substitui o produto salvo.")}
 return <div style={{position:"fixed",inset:0,zIndex:1000,background:"#edf2f7",display:"flex",flexDirection:"column",fontFamily:"Arial,sans-serif"}}>
  <div style={{display:"flex",alignItems:"center",gap:10,padding:12,background:"#fff",borderBottom:"1px solid #cbd5e1",flexWrap:"wrap"}}>
   <strong>Canvas Livre · Laboratório Fabric.js</strong>
   <button onClick={()=>setChartDialog({id:null,item:null})}>+ Gráfico ECharts</button><button onClick={()=>add("shape")}>+ Figura</button><button onClick={removeSelected} disabled={!selectedObject}>Excluir selecionado</button><button onClick={()=>add("text")}>+ Texto</button>
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
  {chartDialog&&<div style={{position:"fixed",inset:0,zIndex:1100,background:"#0f172acc",padding:"3vh 3vw"}}><div style={{height:"94vh",background:"white",borderRadius:10,display:"flex",flexDirection:"column",overflow:"hidden"}}><div style={{padding:12,display:"flex",justifyContent:"space-between"}}><strong>Editor ECharts · Para retornar, clique em “Aplicar ao produto” dentro do ECharts</strong><button onClick={()=>setChartDialog(null)}>Cancelar e voltar</button></div><iframe id="free-chart-frame" title="Editor ECharts" src="/studio-component.html?picker=1" style={{width:"100%",border:0,flex:1}}/></div></div>}
 </div>
}
