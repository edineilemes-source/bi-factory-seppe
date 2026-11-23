/* BI Factory SEPPE / laboratório 8507 — editor visual e ECharts independentes.
 * Não acessa nem escreve produtos ou layouts da aplicação 8506.
 */
(()=>{
"use strict";
const LAB_BUILD="lab8507-editor-wide-curtains-20261123-r8";
document.documentElement.dataset.labBuild=LAB_BUILD;
const E=window.BIAxesEngine;
if(!E){document.body.textContent="Motor do laboratório não foi carregado.";return}
const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(cls)item.className=cls;return item};
const modeLabels={fixed:"Fixo",filterable:"Filtrável no produto",all:"Todos, independente dos filtros"};
let state={version:1,objects:[],filters:{},selected:null};
let rows=[],currentScreen="visual",editing=null,previewOnly=false;
const SHAPES=new Set(["rectangle","square","diamond","ellipse","arrow","line"]);
const TEXT_TYPES=new Set(["text","title"]);
const OBJECT_TYPES=new Set(["chart","text","title","image","filter","filter_panel","measure_filter",...SHAPES]);
let undoStack=[],redoStack=[];
function checkpoint(){
 undoStack.push(JSON.stringify(snapshotDraft()));
 if(undoStack.length>80)undoStack.shift();
 redoStack=[];
}
function restoreSnapshot(content){
 const snapshot=JSON.parse(content);
 if(!draftValid(snapshot))throw Error("Estado de edição inválido");
 state={version:1,objects:snapshot.objects,filters:snapshot.filters||{},selected:snapshot.selected||null};
 cacheDraft(snapshot,false);
 renderCanvas();renderProperties();
}
function undoVisual(){
 if(!undoStack.length)return;
 redoStack.push(JSON.stringify(snapshotDraft()));
 restoreSnapshot(undoStack.pop());
 status("Última alteração desfeita no laboratório 8507.");
}
function redoVisual(){
 if(!redoStack.length)return;
 undoStack.push(JSON.stringify(snapshotDraft()));
 restoreSnapshot(redoStack.pop());
 status("Alteração refeita no laboratório 8507.");
}
const bounded=(val,min,max,fallback)=>{
 const n=Number(val);return Number.isFinite(n)?Math.max(min,Math.min(max,n)):fallback;
};
const defaults=type=>({
 id:newId(),type,title:"",width:type==="chart"?6:type==="title"?8:4,
 height:type==="chart"?4:type==="text"?2:2,
 bg:"#ffffff",color:"#203047",borderColor:"transparent",borderWidth:0,
 borderRadius:8,fontFamily:"Arial",bold:false,italic:false,size:type==="title"?28:18,
 textAlign:"left",opacity:100,rotation:0,z:1,offsetX:0,offsetY:0
});
function labelOfType(type){
 return {chart:"Gráfico / Indicador ECharts",text:"Texto",title:"Título",
 image:"Imagem",filter:"Filtro de dimensão",filter_panel:"Painel de filtros",
 measure_filter:"Seletor de medidas",rectangle:"Retângulo",square:"Quadrado",
 diamond:"Losango",ellipse:"Elipse",arrow:"Seta",line:"Linha"}[type]||"Objeto";
}
function deleteObject(id){
 if(previewOnly)return;
 const index=state.objects.findIndex(o=>o.id===id);
 if(index<0)return;
 checkpoint();
 state.objects.splice(index,1);
 if(state.selected===id)state.selected=state.objects.at(-1)?.id||null;
 if(state.selected===null)editing=null;
 renderCanvas();renderProperties();
 status("Objeto excluído. Use Desfazer para recuperá-lo.");
}
function duplicateObject(id){
 const src=object(id);if(!src||previewOnly)return;
 checkpoint();const copy=JSON.parse(JSON.stringify(src));copy.id=newId();
 copy.x=bounded(src.x,-4000,15000,12)+22;
 copy.y=bounded(src.y,-4000,15000,12)+22;
 copy.z=bounded(src.z,-1000,1000,1)+1;
 if(copy.chart)copy.chart.id=copy.id;
 state.objects.splice(state.objects.indexOf(src)+1,0,copy);
 selectObject(copy.id);
}
function ensureFreeLayout(canvas){
 // Migração não destrutiva: converter a grade antiga em coordenadas livres UMA VEZ,
 // preservando os objetos e dimensões já salvos no laboratório.
 const avail=Math.max(420,canvas.clientWidth-28),gap=12;
 let nextX=12,nextY=12,rowHeight=0;
 for(const obj of state.objects){
  const legacyW=bounded(obj.width,1,12,4),legacyH=bounded(obj.height,1,12,2);
  const w=bounded(obj.pixelWidth,80,2400,Math.max(90,Math.round(legacyW*(avail+gap)/12-gap)));
  const h=bounded(obj.pixelHeight,45,2000,Math.max(70,legacyH*76-gap));
  const exists=Number.isFinite(Number(obj.x))&&Number.isFinite(Number(obj.y));
  if(!exists){
   if(nextX>12&&nextX+w>avail+12){
    nextX=12;nextY+=rowHeight+gap;rowHeight=0;
   }
   obj.x=nextX+bounded(obj.offsetX,-4000,4000,0);
   obj.y=nextY+bounded(obj.offsetY,-4000,4000,0);
   obj.offsetX=0;obj.offsetY=0;
   nextX+=w+gap;rowHeight=Math.max(rowHeight,h);
  }else{
   nextY=Math.max(nextY,Math.max(0,Number(obj.y))+h+gap);
  }
  obj.pixelWidth=w;obj.pixelHeight=h;
 }
 canvas.style.minHeight=Math.max(560,...state.objects.map(o=>
   bounded(o.y,-4000,15000,0)+bounded(o.pixelHeight,45,2000,120)+30))+"px";
}
function updateCanvasHeight(canvas){
 canvas.style.minHeight=Math.max(560,...state.objects.map(o=>
   bounded(o.y,-4000,15000,0)+bounded(o.pixelHeight,45,2000,120)+30))+"px";
}
function applyObjectStyle(block,obj){
 block.style.position="absolute";
 block.style.left=bounded(obj.x,-4000,15000,12)+"px";
 block.style.top=bounded(obj.y,-4000,15000,12)+"px";
 block.style.width=bounded(obj.pixelWidth,80,2400,280)+"px";
 block.style.height=bounded(obj.pixelHeight,45,2000,190)+"px";
 block.style.opacity=String(bounded(obj.opacity,0,100,100)/100);
 block.style.background=obj.bg||"transparent";
 block.style.color=obj.color||"#203047";
 block.style.borderColor=obj.borderColor||"transparent";
 block.style.borderWidth=bounded(obj.borderWidth,0,20,0)+"px";
 block.style.borderRadius=bounded(obj.borderRadius,0,80,8)+"px";
 block.style.zIndex=String(bounded(obj.z,-1000,1000,1)+1001);
 block.style.transform="rotate("+bounded(obj.rotation,-180,180,0)+"deg)";
}
const instances=new Map();
const formatNumber=v=>v===null||v===undefined?"Valor indisponível":E.money(v);
let statusTimer=null;
function status(message,bad=false){
 const line=$("global-status");
 line.textContent=message;line.style.color=bad?"#a14635":"#496473";
 const floating=$("editor-status");
 if(!floating)return;
 floating.textContent=message;
 floating.classList.toggle("error",Boolean(bad));
 if(document.body.classList.contains("lab-edit-workspace")&&!previewOnly){
  floating.hidden=false;
  if(statusTimer!==null)clearTimeout(statusTimer);
  statusTimer=setTimeout(()=>{floating.hidden=true;statusTimer=null},5000);
 }else floating.hidden=true;
}
function object(id){return state.objects.find(o=>o.id===id)}
function charts(){return state.objects.filter(o=>o.type==="chart"&&o.chart).map(o=>o.chart)}
function newId(){return "o-"+(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2))}
function elementLabel(o){return o.title||labelOfType(o.type)}
function addObject(type,details={},edit=false){
 if(!OBJECT_TYPES.has(type)){status("Objeto não reconhecido: "+type,true);return null}
 checkpoint();
 const obj={...defaults(type),...details};
 if(type==="chart"){
   obj.chart=obj.chart||E.createChart(obj.id,{title:obj.title||"Novo gráfico",type:"BAR"});
   obj.chart.id=obj.id;
   obj.title=obj.title||obj.chart.title;
 }
 if(type==="filter")obj.dimension=obj.dimension||"ano";
 if(type==="filter_panel")obj.dimensions=obj.dimensions||["ano","bimestre"];
 if(TEXT_TYPES.has(type))obj.text=obj.text??"";
 state.objects.push(obj);
 state.selected=obj.id;
 if(edit&&type==="chart")openChart(obj.id);
 else{
  renderCanvas();renderProperties();
  if(type==="image"){
   // O clique em "+ Imagem" também abre o seletor imediatamente.
   const picker=[...$("visual-canvas").querySelectorAll("[data-object-id]")]
     .find(el=>el.dataset.objectId===obj.id)?.querySelector(".image-file-input");
   picker?.click();
  }
  if(TEXT_TYPES.has(type)){
   requestAnimationFrame(()=>{
    const element=document.querySelector('[data-object-id="'+obj.id+'"] [contenteditable="true"]');
    element?.focus();
  });
  }
 }
 return obj;
}
function disposeAll(){
 for(const chart of instances.values())try{chart.dispose()}catch(_){}
 instances.clear();
}
function closeFilterMenus(except=null){
 for(const dropdown of document.querySelectorAll(".multi-select[open]")){
  if(dropdown!==except){
   if(typeof dropdown.cancelAutoClose==="function")dropdown.cancelAutoClose();
   dropdown.open=false;
  }
 }
}
function refreshPreviewCharts(){
 requestAnimationFrame(()=>{
  for(const chart of instances.values())try{chart.resize()}catch(_){}
 });
}
function setEditorCurtain(which,open){
 const ids={
  tools:["visual-tools-drawer","toggle-tools-drawer"],
  props:["visual-props-drawer","toggle-props-drawer"]
 };
 const pair=ids[which];
 if(!pair)return;
 const curtain=$(pair[0]),toggle=$(pair[1]);
 const willOpen=Boolean(open);
 curtain.classList.toggle("drawer-open",willOpen);
 curtain.setAttribute("aria-hidden",String(!willOpen));
 toggle.setAttribute("aria-expanded",String(willOpen));
 toggle.classList.toggle("active",willOpen);
}
function toggleEditorCurtain(which){
 const id=which==="tools"?"visual-tools-drawer":"visual-props-drawer";
 const opening=!$(id).classList.contains("drawer-open");
 // Se uma cortina estiver aberta, fecha-a antes de abrir a outra.
 if(opening)setEditorCurtain(which==="tools"?"props":"tools",false);
 setEditorCurtain(which,opening);
}
function syncVisualWorkspaceMode(){
 document.body.classList.toggle("lab-edit-workspace",currentScreen==="visual"&&!previewOnly);
}
function collapseEditorToolbar(collapse){
 const page=$("visual-page");
 page.classList.toggle("toolbar-collapsed",Boolean(collapse));
 $("editor-toolbar-show").hidden=!collapse;
}
function toggleEditorNativeFullscreen(){
 const el=$("visual-page");
 if(document.fullscreenElement===el){
  const action=document.exitFullscreen?.();
  if(action?.catch)action.catch(()=>status("Não foi possível sair do modo tela cheia.",true));
 }else if(el.requestFullscreen){
  const action=el.requestFullscreen();
  if(action?.catch)action.catch(()=>status("Seu navegador bloqueou a tela cheia. O canvas continua na largura total.",true));
 }else status("O canvas já ocupa a página inteira; este navegador não oferece tela cheia nativa.",true);
}
function setPanelPreview(enabled){
 previewOnly=Boolean(enabled);
 document.body.classList.toggle("lab-panel-preview",previewOnly);
 syncVisualWorkspaceMode();
 $("exit-panel-preview").hidden=!previewOnly;
 $("visual-preview").textContent=previewOnly?"Voltar à edição":"Visualizar painel";
 closeFilterMenus();
 renderCanvas();
 refreshPreviewCharts();
}
function enterPanelPreview(){
 if(previewOnly)return;
 setPanelPreview(true);
 const panel=$("visual-page");
 // O modo imersivo via CSS funciona mesmo quando o navegador bloqueia a API Fullscreen.
 if(panel.requestFullscreen){
  try{
   const promise=panel.requestFullscreen();
   if(promise&&typeof promise.catch==="function")promise.catch(()=>{});
  }catch(_){}
 }
}
function exitPanelPreview(){
 if(!previewOnly)return;
 setPanelPreview(false);
 if(document.fullscreenElement===$("visual-page")&&document.exitFullscreen){
  const promise=document.exitFullscreen();
  if(promise&&typeof promise.catch==="function")promise.catch(()=>{});
 }
}
function showScreen(screen){
 currentScreen=screen;
 syncVisualWorkspaceMode();
 $("visual-page").hidden=screen!=="visual";
 $("echarts-page").hidden=screen!=="echarts";
 $("go-visual").classList.toggle("active",screen==="visual");
 $("go-charts").classList.toggle("active",screen==="echarts");
 if(screen==="visual"){renderCanvas();renderProperties()}
 else if(editing){fillChartEditor(editing);renderPreview()}
}
function setChartActive(id){
 const obj=object(id);
 if(!obj||obj.type!=="chart")return;
 state.selected=id;editing=obj.chart;
 showScreen("echarts");
 status("Configurando "+(obj.title||"gráfico")+". As restrições ficam salvas com este objeto.");
}
function openChart(id){setChartActive(id)}
function selectObject(id){state.selected=id;renderCanvas();renderProperties()}
function configureOptions(select,values,chosen){
 select.replaceChildren();
 for(const [key,label] of values){const opt=new Option(label,key);select.add(opt)}
 select.value=String(chosen??values[0]?.[0]??"");
}
function renderChartIn(host,chart,filterState={},selectedMeasure=""){
 const view=E.build(chart,rows,filterState,selectedMeasure);
 if(view.error||view.empty){
  const note=node("div",view.error||view.empty,"filter-locked");note.style.margin="12px";host.replaceChildren(note);return;
 }
 if(view.kind==="kpi"){
  host.replaceChildren();
  const value=node("div",formatNumber(view.value),"kpi-value");
  const sub=node("div",(view.metric||"Medida")+" · "+view.period,"kpi-sub");
  host.append(value,sub);return;
 }
 if(view.kind==="table"){
  host.replaceChildren();const table=node("table");table.style.cssText="width:100%;font-size:12px;border-collapse:collapse";
  const head=node("tr");for(const text of ["Ano","Bimestre",...view.fields.map(f=>E.byKey[f])]){
   const th=node("th",text);th.style.cssText="text-align:left;padding:7px;border-bottom:1px solid #ddd";head.append(th);
  }table.append(head);
  for(const record of view.rows){const tr=node("tr");
   for(const text of [String(record.ano),String(record.bimestre),...view.fields.map(f=>formatNumber(record[f]))]){
    const td=node("td",text);td.style.cssText="font-size:11px;padding:7px;border-bottom:1px solid #eee";tr.append(td)}
   table.append(tr)}
  host.append(table);return;
 }
 if(!window.echarts){host.replaceChildren(node("div","ECharts indisponível: verifique a biblioteca de gráficos.","filter-locked"));return}
 const inner=node("div",undefined,"chart-host");
 const h=host.dataset.chartHeight;inner.style.height=(Number(h)||260)+"px";
 host.replaceChildren(inner);
 const chartInstance=echarts.init(inner);
 instances.set(inner,chartInstance);
 chartInstance.setOption(view.options,{notMerge:true});
}
function previewChart(chart){
 disposeAll();
 const host=$("chart-preview"),fallback=$("preview-fallback");
 host.replaceChildren();host.dataset.chartHeight="405";host.style.height="405px";
 const view=E.build(chart,rows);
 $("preview-heading").textContent=view.header||chart.title;
 if(view.error||view.empty){
   fallback.hidden=false;fallback.textContent=view.error||view.empty;return;
 }
 fallback.hidden=true;
 renderChartIn(host,chart);
 $("binding-summary").textContent="X "+E.AXES[chart.axes.x]+" · Y "+E.AXES[chart.axes.y]+" · Z "+
  ({medida:"Medida",valor:"Valor",nenhum:"Sem rótulo"}[chart.axes.z])+" · "+chart.measures.length+" medida(s)";
}
function startObjectResize(event,obj,block,canvas){
 if(previewOnly||event.button!==0)return;
 event.preventDefault();event.stopPropagation();
 checkpoint();
 const startX=event.clientX,startY=event.clientY;
 const width=bounded(obj.pixelWidth,80,2400,280);
 const height=bounded(obj.pixelHeight,45,2000,160);
 const move=e=>{
  e.preventDefault();
  obj.pixelWidth=bounded(width+e.clientX-startX,80,2400,width);
  obj.pixelHeight=bounded(height+e.clientY-startY,45,2000,height);
  applyObjectStyle(block,obj);
  updateCanvasHeight(canvas);
 };
 const done=()=>{
  document.removeEventListener("pointermove",move);
  document.removeEventListener("pointerup",done);
  document.removeEventListener("pointercancel",done);
  renderCanvas();renderProperties();
 };
 document.addEventListener("pointermove",move);
 document.addEventListener("pointerup",done);
 document.addEventListener("pointercancel",done);
}
function startFreeMove(event,obj,block,force=false){
 if(previewOnly||event.button!==0)return;
 if(!force&&event.target.closest('input,textarea,select,button,[contenteditable="true"],.filter-control,.chart-host'))return;
 event.preventDefault();event.stopPropagation();
 checkpoint();
 state.selected=obj.id;
 // Selecionar a alça de um objeto antigo também desfaz a seleção visual anterior.
 for(const previous of $("visual-canvas").querySelectorAll(".canvas-object.active")){
  previous.classList.remove("active");
 }
 block.classList.add("active");
 const x=event.clientX,y=event.clientY;
 const oldX=bounded(obj.x,-4000,15000,12),oldY=bounded(obj.y,-4000,15000,12);
 const move=e=>{
  e.preventDefault();
  obj.x=bounded(oldX+e.clientX-x,-4000,15000,oldX);
  obj.y=bounded(oldY+e.clientY-y,-4000,15000,oldY);
  applyObjectStyle(block,obj);
  updateCanvasHeight($("visual-canvas"));
 };
 const finish=()=>{
  document.removeEventListener("pointermove",move);
  document.removeEventListener("pointerup",finish);
  document.removeEventListener("pointercancel",finish);
  renderCanvas();renderProperties();
 };
 document.addEventListener("pointermove",move);
 document.addEventListener("pointerup",finish);
 document.addEventListener("pointercancel",finish);
}
function renderCanvas(){
 // Rascunho do laboratório mantido no navegador, sem acessar os dados da 8506.
 cacheDraft(snapshotDraft(),false);
 disposeAll();
 const canvas=$("visual-canvas");
 canvas.replaceChildren();
 ensureFreeLayout(canvas);
 cacheDraft(snapshotDraft(),false);
 if(!state.objects.length){
  canvas.append(node("div","Produto vazio. Use os objetos à esquerda para começar.","canvas-empty"));
  return;
 }
 for(const obj of state.objects){
   const block=node("section",undefined,"canvas-object");
   block.dataset.objectId=obj.id;
   block.dataset.kind=obj.type==="chart"&&obj.chart?.type==="KPI"?"kpi":obj.type;
   applyObjectStyle(block,obj);
   if(obj.id===state.selected&&!previewOnly)block.classList.add("active");
   block.draggable=false;
   block.addEventListener("click",event=>{
    if(previewOnly||event.target.closest("select,button,input,[contenteditable],textarea,.resize-handle,.move-handle,.multi-select,.filter-control,.image-click-surface"))return;
    if(state.selected!==obj.id)selectObject(obj.id);
   });
   if(!previewOnly&&!TEXT_TYPES.has(obj.type)&&obj.type!=="image")
    block.addEventListener("pointerdown",event=>startFreeMove(event,obj,block));
   const inner=node("div",undefined,"object-inner");
   block.append(inner);
   if(obj.type==="chart"&&obj.chart){
      inner.classList.add("chart-item");
      inner.dataset.chartHeight=String(Math.max(75,bounded(obj.pixelHeight,45,2000,230)-8));
   }else if(TEXT_TYPES.has(obj.type)){
      inner.classList.add("text-container");
      const editable=node("div",obj.text??"","text-edit");
      editable.contentEditable=!previewOnly;editable.spellcheck=true;
      editable.style.fontFamily=obj.fontFamily||"Arial";
      editable.style.fontSize=bounded(obj.size,8,120,obj.type==="title"?28:18)+"px";
      editable.style.fontWeight=obj.bold?"700":"400";
      editable.style.fontStyle=obj.italic?"italic":"normal";
      editable.style.textAlign=obj.textAlign||"left";
      editable.style.color=obj.color||"#203047";
      editable.style.background="transparent";
      editable.setAttribute("aria-label",obj.type==="title"?"Editar título":"Escrever texto");
      editable.addEventListener("pointerdown",event=>event.stopPropagation());
      editable.addEventListener("mousedown",event=>event.stopPropagation());
      editable.addEventListener("focus",()=>{
       state.selected=obj.id;
       for(const previous of canvas.querySelectorAll(".canvas-object.active")){
        previous.classList.remove("active");
       }
       block.classList.add("active");
       renderProperties();
      });
      editable.addEventListener("input",()=>{
       obj.text=editable.innerText;
       cacheDraft(snapshotDraft(),false);
       const control=$("visual-props").querySelector('[data-object-text-input]');
       if(control)control.value=obj.text;
      });
      inner.append(editable);
   }else if(obj.type==="image"){
      inner.classList.add("image-picker");
      const picker=node("input");picker.type="file";
      picker.accept="image/png,image/jpeg,image/webp,image/gif";
      picker.className="image-file-input";picker.hidden=true;
      picker.onchange=()=>{
       const file=picker.files?.[0];if(!file)return;
       if(file.size>2*1024*1024||!["image/png","image/jpeg","image/webp","image/gif"].includes(file.type)){
        status("Use PNG, JPG, WebP ou GIF de até 2 MB.",true);return;
       }
       const reader=new FileReader();
       reader.onload=()=>{checkpoint();obj.src=String(reader.result);renderCanvas();renderProperties()};
       reader.readAsDataURL(file);
      };
      inner.append(picker);
      const surface=node("div",undefined,"image-click-surface");
      surface.setAttribute("role","button");surface.tabIndex=previewOnly?-1:0;
      surface.setAttribute("aria-label","Escolher arquivo de imagem");
      if(obj.src){
       const image=node("img");image.src=obj.src;image.alt=obj.title||"Imagem";
       image.draggable=false;surface.append(image);
      }else if(!previewOnly){
       surface.append(node("span","Clique para escolher imagem","image-pick-hint"));
      }
      if(!previewOnly){
       surface.onclick=e=>{e.stopPropagation();state.selected=obj.id;picker.click();};
       surface.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();picker.click()}};
      }
      inner.append(surface);
   }else if(obj.type==="filter"){renderFilterControl(obj,inner)}
   else if(obj.type==="filter_panel"){
      const dims=Array.isArray(obj.dimensions)?obj.dimensions:["ano","bimestre"];
      const panel=node("div",undefined,"filter-panel-content");
      for(const dim of dims)if(E.DIMENSIONS[dim]){
       const entry=node("div",undefined,"filter-panel-field");
       renderFilterControl({dimension:dim},entry);
       panel.append(entry);
      }
      inner.append(panel);
   }else if(obj.type==="measure_filter"){renderMeasureControl(obj,inner)}
   else if(SHAPES.has(obj.type)){
      inner.classList.add("shape-content");
      const drawing=node("div",undefined,"shape-drawing shape-"+obj.type);
      drawing.style.background=obj.color||"#259ea6";
      inner.append(drawing);
   }
   canvas.append(block);
   // A alça de mover fica disponível em TODOS os objetos durante a edição.
   // Apenas a alça de redimensionar depende de selecionar o objeto.
   if(!previewOnly){
      const moveHandle=node("button","⠿","move-handle");
      moveHandle.type="button";
      moveHandle.title="Arraste para mover este objeto, mesmo quando outro estiver selecionado";
      moveHandle.setAttribute("aria-label","Mover "+elementLabel(obj));
      moveHandle.addEventListener("pointerdown",event=>startFreeMove(event,obj,block,true));
      block.append(moveHandle);
      if(state.selected===obj.id){
         const handle=node("button","", "resize-handle");
         handle.type="button";
         handle.title="Arraste para alterar largura e altura";
         handle.setAttribute("aria-label","Redimensionar "+elementLabel(obj));
         handle.addEventListener("pointerdown",event=>startObjectResize(event,obj,block,canvas));
         block.append(handle);
      }
   }
   if(obj.type==="chart"&&obj.chart)
      renderChartIn(inner,obj.chart,state.filters,state.filters.medida||[]);
   // Alças externas não ocupam a área de texto, imagem ou gráfico.
 }
}
function refreshVisualCharts(){
 for(const chart of instances.values())try{chart.dispose()}catch(_){}
 instances.clear();
 for(const obj of state.objects){
  if(obj.type!=="chart"||!obj.chart)continue;
  const block=[...$("visual-canvas").querySelectorAll("[data-object-id]")]
   .find(el=>el.dataset.objectId===obj.id);
  const host=block?.querySelector(".object-inner.chart-item");
  if(host)renderChartIn(host,obj.chart,state.filters,state.filters.medida||[]);
 }
 cacheDraft(snapshotDraft(),false);
}
function refreshOtherDimensionMenus(changedKey){
 if(!E.DIMENSIONS[changedKey])return;
 const boxes=[...$("visual-canvas").querySelectorAll(".filter-control[data-filter-dimension]")];
 for(const box of boxes){
  const dim=box.dataset.filterDimension;
  if(dim===changedKey||!E.DIMENSIONS[dim])continue;
  const host=box.parentElement;
  box.remove();
  renderFilterControl({dimension:dim},host);
 }
}
function multiSelectControl(key,options,display,caption){
 const selected=E.filterValues(state.filters[key]).filter(v=>options.some(option=>String(option)===v));
 state.filters[key]=selected;
 const root=node("details",undefined,"multi-select");
 root.dataset.filterKey=key;
 root.addEventListener("click",event=>event.stopPropagation());
 root.addEventListener("pointerdown",event=>event.stopPropagation());
 let closeTimeout=null;
 const cancelAutoClose=()=>{
  if(closeTimeout!==null){clearTimeout(closeTimeout);closeTimeout=null}
 };
 const finishSelection=()=>{
  cancelAutoClose();
  root.open=false;
 };
 root.cancelAutoClose=cancelAutoClose;
 root.addEventListener("toggle",()=>{
  if(root.open)closeFilterMenus(root);
  else cancelAutoClose();
 });
 const scheduleAutoClose=()=>{
  cancelAutoClose();
  // Na visualização, permite marcar vários itens em sequência e recolhe a lista
  // após a última escolha; há também um botão Aplicar para fechar imediatamente.
  if(previewOnly)closeTimeout=setTimeout(finishSelection,1600);
 };
 const summary=node("summary",undefined,"multi-select-summary");
 const labelText=()=>{
  const active=E.filterValues(state.filters[key]);
  return active.length===0?"Todos":active.length===1?
    display(active[0]):active.length+" selecionados";
 };
 const summaryText=node("span",labelText(),"multi-select-text");
 summary.append(summaryText);
 root.append(summary);
 const content=node("div",undefined,"multi-select-options");
 content.addEventListener("pointerdown",event=>event.stopPropagation());
 content.addEventListener("click",event=>event.stopPropagation());
 const sync=()=>{
  const active=E.filterValues(state.filters[key]);
  summaryText.textContent=labelText();
  for(const {input,value} of inputs){
   input.checked=value==="__all__"?!active.length:active.includes(value);
  }
 };
 root.syncSelection=sync;
 const apply=next=>{
  checkpoint();
  state.filters[key]=[...new Set(next.map(String))];
  for(const filter of $("visual-canvas").querySelectorAll(".multi-select")){
   if(typeof filter.syncSelection==="function")filter.syncSelection();
  }
  refreshOtherDimensionMenus(key);
  refreshVisualCharts();
  scheduleAutoClose();
 };
 const inputs=[];
 const row=(label,value)=>{
  const line=node("label",undefined,"multi-select-line");
  const input=node("input");input.type="checkbox";
  input.checked=value==="__all__"?!selected.length:selected.includes(value);
  const captionNode=node("span",label);
  line.append(input,captionNode);
  input.addEventListener("change",()=>{
   if(value==="__all__"){apply([]);return}
   const updated=new Set(E.filterValues(state.filters[key]));
   if(input.checked)updated.add(value);else updated.delete(value);
   apply([...updated]);
  });
  inputs.push({input,value});
  content.append(line);
 };
 row("Todos","__all__");
 for(const option of options)row(display(String(option)),String(option));
 const actions=node("div",undefined,"multi-select-actions");
 const done=node("button","Aplicar e fechar","multi-select-done");
 done.type="button";
 done.addEventListener("click",event=>{
  event.preventDefault();event.stopPropagation();
  finishSelection();
 });
 actions.append(done);
 content.append(actions);
 root.append(content);
 root.title=caption;
 return root;
}
function renderFilterControl(obj,host){
 const dim=E.DIMENSIONS[obj.dimension]?obj.dimension:"ano";
 const options=E.allowedOptions(charts(),rows,dim,state.filters);
 const box=node("div",undefined,"filter-control");
 box.dataset.filterDimension=dim;
 box.append(node("label","Filtro: "+E.DIMENSIONS[dim]));
 if(!options.length){
  box.append(node("div","Nenhum gráfico autoriza variar "+E.DIMENSIONS[dim]+
   ". Ajuste o escopo para 'Filtrável no produto' dentro do ECharts.","filter-locked"));
 }else{
  const display=v=>dim==="bimestre"?v+"º bimestre":String(v);
  box.append(multiSelectControl(dim,options,display,"Seleção múltipla de "+E.DIMENSIONS[dim]));
  box.append(node("p","Marque um, vários ou Todos. Gráficos com período fixo não são alterados.","small muted"));
 }
 host.append(box);
}
function renderMeasureControl(obj,host){
 const options=E.allowedMeasures(charts());
 const box=node("div",undefined,"filter-control");
 box.append(node("label","Seletor de medidas"));
 if(!options.length){
  box.append(node("div","Nenhum gráfico autoriza variar medidas. A seleção definida no ECharts permanece fixa.","filter-locked"));
 }else{
  box.append(multiSelectControl("medida",options,
    key=>E.byKey[key]||key,"Seleção múltipla apenas das medidas autorizadas"));
  box.append(node("p","Marque uma, várias ou Todas. Cada gráfico mantém somente suas medidas autorizadas.","small muted"));
 }
 host.append(box);
}
function propertiesField(label,value,onchange,kind="input",options=[]){
 const container=node("label");container.append(node("span",label));
 let field;
 if(kind==="select"){
  field=node("select");for(const [v,t] of options)field.add(new Option(t,v));field.value=String(value);
 }else if(kind==="textarea"){field=node("textarea");field.value=value||"";field.rows=5}
 else{field=node("input");field.type=["number","color"].includes(kind)?kind:"text";field.value=value??""}
 field.addEventListener("change",()=>onchange(field.value));
 container.append(field);return container;
}
function propButton(text,fn,kind=""){
 const btn=node("button",text,kind);btn.onclick=fn;return btn;
}
function propsCheckbox(label,checked,callback){
 const item=node("label",undefined,"props-checkline");
 const input=node("input");input.type="checkbox";input.checked=Boolean(checked);
 input.addEventListener("change",()=>callback(input.checked));
 item.append(input,node("span",label));
 return item;
}
function renderProperties(){
 const root=$("visual-props");root.replaceChildren();
 const o=object(state.selected);
 if(!o){root.append(node("p","Selecione um objeto no canvas.","small muted"));return}
 root.append(node("h3",elementLabel(o)));
 const field=(name,key,kind="input",options=[],parse=v=>v)=>{
  const v=o[key]??(key==="color"?"#203047":key==="fontFamily"?"Arial":kind==="color"?"#ffffff":"");
  const control=propertiesField(name,kind==="color"&&(v==="transparent"||v==="")?"#ffffff":v,
   value=>{checkpoint();o[key]=parse(value);renderCanvas()},kind,options);
  root.append(control);
  return control;
 };
 const number=(name,key,min,max,fallback)=>{
  const element=propertiesField(name,o[key]??fallback,v=>{
   checkpoint();o[key]=bounded(v,min,max,fallback);renderCanvas();renderProperties()
  },"number");
  root.append(element);
 };
 if(o.type==="chart"){
   field("Nome do gráfico","title","input",[],value=>{
    o.chart.title=value;return value
   });
   root.append(propButton("Editar KPI, medidas, X, Y, Z e Cabeçalho no ECharts",()=>openChart(o.id),"primary"));
   root.append(node("p","Ano: "+E.fixedBadge(o.chart,"ano")+" · Bimestre: "+
    E.fixedBadge(o.chart,"bimestre"),"small muted"));
 }else if(TEXT_TYPES.has(o.type)){
   const textField=propertiesField("Texto (edição também direto no canvas)",o.text||"",v=>{
    checkpoint();o.text=v;renderCanvas()
   },"textarea");
   const textarea=textField.querySelector("textarea");
   textarea?.setAttribute("data-object-text-input","");
   root.append(textField);
   field("Fonte","fontFamily","select",[
    ["Arial","Arial"],["Georgia","Georgia"],["Verdana","Verdana"],
    ["Tahoma","Tahoma"],["Times New Roman","Times New Roman"],
    ["Courier New","Courier New"]
   ]);
   number("Tamanho da fonte (px)","size",8,120,o.type==="title"?28:18);
   field("Alinhamento do texto","textAlign","select",[
    ["left","Esquerda"],["center","Centro"],["right","Direita"],["justify","Justificado"]
   ]);
   root.append(propsCheckbox("Negrito",o.bold,checked=>{checkpoint();o.bold=checked;renderCanvas()}));
   root.append(propsCheckbox("Itálico",o.italic,checked=>{checkpoint();o.italic=checked;renderCanvas()}));
 }else if(o.type==="image"){
   field("Nome da imagem","title");
   const source=propertiesField("URL HTTPS da imagem",o.src?.startsWith("https://")?o.src:"",v=>{
    if(v&&!/^https:\/\//i.test(v)){
      status("A URL da imagem precisa começar com https://",true);return
    }
    checkpoint();o.src=v;renderCanvas()
   },"input");
   root.append(source);
   const upload=node("input");upload.type="file";
   upload.accept="image/png,image/jpeg,image/webp,image/gif";
   upload.onchange=()=>{
    const file=upload.files?.[0];if(!file)return;
    if(file.size>2*1024*1024||!["image/png","image/jpeg","image/webp","image/gif"].includes(file.type)){
     status("Selecione PNG, JPG, WebP ou GIF de até 2 MB.",true);return
    }
    const reader=new FileReader();
    reader.onload=()=>{checkpoint();o.src=String(reader.result);renderCanvas()};
    reader.readAsDataURL(file);
   };
   root.append(upload);
 }else if(o.type==="filter"){
   field("Título do filtro","title");
   field("Dimensão","dimension","select",Object.entries(E.DIMENSIONS),v=>{
    const previous=o.dimension;if(previous!==v)delete state.filters[previous];
    return v
   });
   root.append(node("p","Os valores são definidos exclusivamente pelos gráficos que autorizam esse filtro no ECharts.","small muted"));
 }else if(o.type==="filter_panel"){
   field("Título do painel de filtros","title");
   root.append(node("h3","Dimensões exibidas"));
   for(const [key,label] of Object.entries(E.DIMENSIONS)){
    root.append(propsCheckbox(label,(o.dimensions||[]).includes(key),checked=>{
     checkpoint();const allowed=new Set(o.dimensions||[]);
     if(checked)allowed.add(key);else allowed.delete(key);
     o.dimensions=[...allowed];renderCanvas()
    }));
   }
 }else if(o.type==="measure_filter"){
   field("Título do seletor","title");
   root.append(node("p","A seleção de medidas permanece limitada ao contrato de cada gráfico, definido no ECharts.","small muted"));
 }else if(SHAPES.has(o.type)){
   field("Nome da figura","title");
 }
 root.append(node("h3","Dimensões e posição"));
 number("Largura (px)","pixelWidth",80,2400,280);
 number("Altura (px)","pixelHeight",45,2000,160);
 number("Posição horizontal X (px)","x",-4000,15000,12);
 number("Posição vertical Y (px)","y",-4000,15000,12);
 number("Rotação (graus)","rotation",-180,180,0);
 number("Opacidade (%)","opacity",0,100,100);
 root.append(node("h3","Aparência"));
 field(SHAPES.has(o.type)?"Preenchimento":"Cor do texto / gráfico","color","color");
 const bg=propertiesField("Plano de fundo",o.bg==="transparent"?"#ffffff":o.bg||"#ffffff",v=>{
    checkpoint();o.bg=v;renderCanvas()
 },"color");
 root.append(bg);
 root.append(propsCheckbox("Fundo transparente",o.bg==="transparent",checked=>{
   checkpoint();o.bg=checked?"transparent":"#ffffff";renderCanvas();renderProperties()
 }));
 field("Cor do contorno","borderColor","color",[],v=>v);
 number("Espessura da borda (px)","borderWidth",0,20,0);
 number("Arredondamento das bordas (px)","borderRadius",0,80,8);
 const layer=node("div",undefined,"properties-actions");
 layer.append(propButton("Trazer à frente",()=>{
   checkpoint();o.z=bounded((Number(o.z)||1)+100,-1000,1000,101);renderCanvas()
 },"secondary"));
 layer.append(propButton("Enviar para trás",()=>{
   checkpoint();o.z=bounded((Number(o.z)||1)-100,-1000,1000,-99);renderCanvas()
 },"secondary"));
 root.append(layer);
 root.append(node("p","Arraste o objeto ou a alça no canto superior esquerdo. Para ajustes precisos, use as setas do teclado (Shift + seta = 10 px). Redimensione pelo canto inferior direito. A sobreposição é livre.","small muted"));
 root.append(propButton("Duplicar objeto",()=>duplicateObject(o.id),"secondary"));
 root.append(propButton("Excluir objeto",()=>deleteObject(o.id),"danger"));
}
function fillChartEditor(spec){
 if(!spec)return;
 configureOptions($("chart-type"),Object.entries(E.TYPES),spec.type);
 const axisChoices=Object.entries(E.AXES);
 configureOptions($("axis-x"),axisChoices,spec.axes.x);
 configureOptions($("axis-y"),axisChoices,spec.axes.y);
 configureOptions($("axis-z"),[["medida","Medida / legenda"],["valor","Valor / rótulo"],["nenhum","Nenhum"]],spec.axes.z);
 configureOptions($("axis-header"),[["ano","Ano"],["bimestre","Bimestre"],["medida","Medida"],["nenhum","Sem cabeçalho"]],spec.axes.header);
 $("chart-title").value=spec.title;
 const years=[...new Set(rows.map(r=>r.ano))].sort();
 configureOptions($("year-fixed"),(years.length?years:[2022,2023,2024,2025,2026]).map(y=>[y,String(y)]),spec.scope.ano.fixed);
 configureOptions($("period-fixed"),[1,2,3,4,5,6].map(p=>[p,p+"º bimestre"]),spec.scope.bimestre.fixed);
 $("year-mode").value=spec.scope.ano.mode;
 $("period-mode").value=spec.scope.bimestre.mode;
 $("allow-measure-filter").checked=Boolean(spec.measureFilterable);
 $("show-values").checked=Boolean(spec.showLabels);
 $("top-n").value=String([0,5,10,15].includes(spec.topN)?spec.topN:10);
 const choices=$("measure-choices");choices.replaceChildren();
 for(const [key,label] of E.MEASURES){
  const row=node("label",undefined,"measure-row");
  const input=node("input");input.type="checkbox";input.value=key;
  input.checked=spec.measures.includes(key);
  input.onchange=()=>{const selected=[...choices.querySelectorAll("input:checked")].map(x=>x.value);spec.measures=selected;
    if(selected.length<2&&spec.measureFilterable){spec.measureFilterable=false;$("allow-measure-filter").checked=false}
    renderPreview()};
  row.append(input,node("span",label));choices.append(row)
 }
 updateScopeVisibility();
}
function updateScopeVisibility(){
 $("year-fixed").hidden=$("year-mode").value!=="fixed";
 $("period-fixed").hidden=$("period-mode").value!=="fixed";
 $("top-n").hidden=$("chart-type").value!=="RANKING";
}
function renderContract(chart){
 const root=$("chart-contract");root.replaceChildren();
 const show=(text,style)=>root.append(node("div",text,style));
 show("X: "+(E.AXES[chart.axes.x]||"?")+" · Y: "+(E.AXES[chart.axes.y]||"?"),"");
 show("Z: "+({medida:"Identifica medidas",valor:"Mostra valor",nenhum:"Nenhum"}[chart.axes.z]||"?")+
      " · Cabeçalho: "+({ano:"Ano",bimestre:"Bimestre",medida:"Medida",nenhum:"Nenhum"}[chart.axes.header]),"");
 for(const d of ["ano","bimestre"]){
  show(E.fixedBadge(chart,d),chart.scope[d].mode==="filterable"?"editable":"locked");
 }
 show("Medidas permitidas: "+(chart.measures.map(m=>E.byKey[m]).filter(Boolean).join(", ")||"Nenhuma"),"locked");
 show("Seletor de medidas no produto: "+(chart.measureFilterable?"Permitido entre essas medidas":"Bloqueado"),chart.measureFilterable?"editable":"locked");
}
function renderPreview(){
 if(!editing)return;
 renderContract(editing);
 previewChart(editing);
 const issues=E.validate(editing);
 if(issues.length)status("Configuração incompleta: "+issues.join("; "),true);
 else status("Gráfico configurado. Escopos fixos não aceitam alterações pelos filtros do Editor Visual.");
}
function updateBinding(){
 if(!editing)return;
 editing.type=$("chart-type").value;
 editing.axes.x=$("axis-x").value;
 editing.axes.y=$("axis-y").value;
 editing.axes.z=$("axis-z").value;
 editing.axes.header=$("axis-header").value;
 editing.title=$("chart-title").value.trim()||"Gráfico sem nome";
 editing.scope.ano.mode=$("year-mode").value;
 editing.scope.ano.fixed=Number($("year-fixed").value);
 editing.scope.bimestre.mode=$("period-mode").value;
 editing.scope.bimestre.fixed=Number($("period-fixed").value);
 editing.measureFilterable=$("allow-measure-filter").checked&&editing.measures.length>1;
 editing.showLabels=$("show-values").checked;
 editing.topN=Number($("top-n").value);
 const obj=object(state.selected);
 if(obj&&obj.chart===editing)obj.title=editing.title;
 updateScopeVisibility();renderPreview();
}
function exampleChart(title,type,measures,width,opts={}){
 const chart=E.createChart(newId(),{title,type,measures,width,
    axes:opts.axes||{x:"bimestre",y:"valor",z:"medida",header:"ano"},
    scope:{
      ano:{mode:opts.yearMode||"fixed",fixed:opts.year??2025},
      bimestre:{mode:opts.periodMode||"all",fixed:opts.period??1}
    },
    measureFilterable:Boolean(opts.measureFilterable),showLabels:Boolean(opts.showLabels),
    height:opts.height||4,topN:opts.topN||10
 });
 return {id:chart.id,type:"chart",title,width,height:chart.height,chart};
}
function buildExample(){
 if(state.objects.length&&!confirm("Substituir o rascunho atual da 8507 pelo painel de exemplo? A versão 8506 não será modificada."))return;
 checkpoint();
 const a=E.MEASURES;
 const revenue=a[0][0],committed=a[1][0],liquidated=a[2][0],paid=a[3][0];
 state.objects=[
   exampleChart("Receita de 2025 · fixa","KPI",[revenue],4,{year:2025,periodMode:"all"}),
   exampleChart("Empenhado · 2025","KPI",[committed],4,{year:2025,periodMode:"all"}),
   exampleChart("Pago · 2025","KPI",[paid],4,{year:2025,periodMode:"all"}),
   exampleChart("Execução por bimestre","BAR",[committed,liquidated,paid],6,
     {yearMode:"filterable",periodMode:"all",measureFilterable:true,showLabels:false}),
   exampleChart("Ranking de bimestres (liquidado)","RANKING",[liquidated],6,
     {year:2025,periodMode:"all",showLabels:true,topN:6,height:5}),
   exampleChart("Evolução das despesas","LINE",[committed,liquidated,paid],12,
     {yearMode:"filterable",periodMode:"all",measureFilterable:true,showLabels:true}),
   exampleChart("Pontos por bimestre","POINTS",[committed,liquidated,paid],12,
     {yearMode:"filterable",periodMode:"all",measureFilterable:true,showLabels:true})
 ];
 state.objects.unshift({id:newId(),type:"filter",dimension:"ano",title:"Ano (somente gráficos filtráveis)",width:4,height:1});
 state.objects.unshift({id:newId(),type:"measure_filter",title:"Selecionar medida permitida",width:4,height:1});
 state.filters={};
 state.selected=state.objects.find(o=>o.type==="chart")?.id||null;
 showScreen("visual");
 status("Painel experimental criado. A Receita 2025 é fixa; os gráficos de execução e evolução permitem filtrar Ano.");
}
const LAB_DRAFT_CACHE="bi-factory-seppe-lab-8507-draft-v1";
function snapshotDraft(){
 return {version:1,objects:state.objects,filters:state.filters,selected:state.selected};
}
function draftValid(payload){
 return payload?.version===1&&Array.isArray(payload.objects)&&
   payload.objects.length<=100&&payload.filters&&typeof payload.filters==="object";
}
function cacheDraft(payload,synced=false){
 if(!draftValid(payload))return false;
 try{
  localStorage.setItem(LAB_DRAFT_CACHE,JSON.stringify({
   payload,updatedAt:new Date().toISOString(),synced:Boolean(synced)
  }));
  return true;
 }catch(error){return false}
}
function recoverDraft(){
 try{
  const entry=JSON.parse(localStorage.getItem(LAB_DRAFT_CACHE)||"null");
  return entry&&draftValid(entry.payload)?entry:null;
 }catch(error){return null}
}
function applyDraft(saved){
 state={version:1,objects:saved.objects,filters:saved.filters||{},selected:saved.selected||null};
}
async function saveLab(){
 const payload=snapshotDraft();
 const cached=cacheDraft(payload,false);
 try{
  const response=await fetch("/lab/draft",{
   method:"POST",cache:"no-store",
   headers:{"Content-Type":"application/json","Accept":"application/json"},
   body:JSON.stringify(payload)
  });
  let info;
  try{info=await response.json()}catch(error){
   throw Error("servidor retornou HTTP "+response.status+" sem JSON");
  }
  if(!response.ok||!info?.ok)throw Error(info?.error||"HTTP "+response.status);
  cacheDraft(payload,true);
  status("Rascunho salvo no laboratório 8507: "+info.objects+" objetos. A 8506 permanece intacta.");
 }catch(error){
  if(cached){
   status("Rascunho guardado SOMENTE neste navegador. Não foi possível gravar no servidor 8507 ("+
    error.message+"). Não apague os dados do navegador antes de sincronizar.",true);
  }else{
   status("Falha ao salvar no servidor e no navegador: "+error.message,true);
  }
 }
}
async function requestJSON(path,retries=2){
 let lastError=null;
 for(let attempt=0;attempt<=retries;attempt++){
  try{
   const response=await fetch(path,{cache:"no-store",headers:{"Accept":"application/json"}});
   let payload;
   try{payload=await response.json()}catch(_){throw Error(path+" retornou uma resposta não JSON (HTTP "+response.status+")")}
   if(!response.ok){
    const message=payload?.error||"HTTP "+response.status;
    if([502,503,504].includes(response.status)&&attempt<retries){
     await new Promise(resolve=>setTimeout(resolve,450*(attempt+1)));
     continue;
    }
    throw Error(path+": "+message+" (HTTP "+response.status+")");
   }
   return payload;
  }catch(error){
   lastError=error;
   if(attempt<retries&&/network|fetch|502|503|504/i.test(String(error?.message||error))){
    await new Promise(resolve=>setTimeout(resolve,450*(attempt+1)));
    continue;
   }
   throw error;
  }
 }
 throw lastError||Error("Falha desconhecida na consulta "+path);
}
async function loadLab(){
 const [stored,fiscal]=await Promise.allSettled([
   requestJSON("/lab/draft"),
   requestJSON("/api/fiscal")
 ]);
 let stateIssue="",fiscalIssue="";
 const cached=recoverDraft();
 if(stored.status==="fulfilled"){
  const saved=stored.value;
  if(draftValid(saved)){
   // Um rascunho alterado sem confirmação de gravação no servidor tem prioridade.
   if(cached&&!cached.synced)applyDraft(cached.payload);
   else{applyDraft(saved);cacheDraft(saved,true)}
  }else if(cached){
   applyDraft(cached.payload);
   stateIssue="Estado do servidor inválido; rascunho recuperado deste navegador";
  }else stateIssue="Rascunho remoto indisponível; você pode iniciar um novo painel";
 }else{
  if(cached){
   applyDraft(cached.payload);
   stateIssue="Servidor de rascunhos indisponível; rascunho recuperado deste navegador";
  }else{
   stateIssue="Servidor de rascunhos indisponível ("+
     String(stored.reason?.message||stored.reason)+"). Você pode montar um painel e salvar localmente.";
  }
 }
 if(fiscal.status==="fulfilled"){
  if(Array.isArray(fiscal.value)){
   rows=E.normalizedRows(fiscal.value);
   const valid=new Set(rows.map(r=>r.ano+"-"+r.bimestre));
   $("data-status").textContent=valid.size+" períodos STN · laboratório 8507";
  }else{
   fiscalIssue="API fiscal não retornou uma lista";
   $("data-status").textContent="Fonte fiscal indisponível";
  }
 }else{
  fiscalIssue=String(fiscal.reason?.message||fiscal.reason);
  $("data-status").textContent="Fonte fiscal indisponível";
 }
 showScreen("visual");
 // Após carregar estado remoto, restaurar confirmação de sincronização apagada pelo redraw.
 if(stored.status==="fulfilled"&&draftValid(stored.value)&&!stateIssue&&
    !(cached&&!cached.synced))cacheDraft(stored.value,true);
 if(!stateIssue&&!fiscalIssue){
  status("Laboratório 8507 com "+rows.length+" bimestres oficiais. A 8506 permanece separada.");
 }else{
  const issues=[stateIssue?"Rascunho: "+stateIssue:"",fiscalIssue?"Dados fiscais: "+fiscalIssue:""].filter(Boolean);
  status("Laboratório parcialmente disponível. "+issues.join(" | "),true);
 }
}
function wire(){
 $("toggle-tools-drawer").onclick=()=>toggleEditorCurtain("tools");
 $("toggle-props-drawer").onclick=()=>toggleEditorCurtain("props");
 $("editor-open-echarts").onclick=()=>$("go-charts").click();
 $("editor-save").onclick=saveLab;
 $("editor-fullscreen").onclick=toggleEditorNativeFullscreen;
 $("editor-toolbar-hide").onclick=()=>collapseEditorToolbar(true);
 $("editor-toolbar-show").onclick=()=>collapseEditorToolbar(false);
 $("go-visual").onclick=()=>showScreen("visual");
 $("go-charts").onclick=()=>{
  const sel=object(state.selected);
  if(sel?.type==="chart")return openChart(sel.id);
  const first=state.objects.find(o=>o.type==="chart");
  if(first)return openChart(first.id);
  addObject("chart",{title:"Novo gráfico"},true);
 };
 $("add-text").onclick=()=>addObject("text",{title:"",text:"",width:6,height:2});
 $("add-title").onclick=()=>addObject("title",{title:"",text:"",width:8,height:1,size:28,bold:true});
 $("add-image").onclick=()=>addObject("image",{title:"Imagem",width:6});
 $("add-chart").onclick=()=>addObject("chart",{title:"Novo gráfico",width:6},true);
 for(const type of SHAPES){
   const btn=$("add-"+type);
   if(btn)btn.onclick=()=>addObject(type,{title:"",width:type==="line"?6:4,height:type==="line"?1:3,
    color:"#259ea6",bg:"transparent",borderColor:"transparent"});
 }
 $("add-filter-panel").onclick=()=>addObject("filter_panel",{
  title:"Filtros do painel",dimensions:["ano","bimestre"],width:6,height:2
 });
 $("add-filter").onclick=()=>addObject("filter",{title:"Filtro de dimensão",dimension:"ano",height:1});
 $("add-measure-filter").onclick=()=>addObject("measure_filter",{title:"Seletor de medidas",height:1});
 $("add-example").onclick=buildExample;
 $("visual-undo").onclick=undoVisual;
 $("visual-redo").onclick=redoVisual;
 $("save-lab").onclick=saveLab;
 $("visual-preview").onclick=enterPanelPreview;
 $("exit-panel-preview").onclick=exitPanelPreview;
 document.addEventListener("fullscreenchange",()=>{
  const active=document.fullscreenElement===$("visual-page");
  $("editor-fullscreen").setAttribute("aria-pressed",String(active));
  $("editor-fullscreen").textContent=active?"Sair da tela cheia":"Tela cheia";
  if(previewOnly&&!active)exitPanelPreview();
  else refreshPreviewCharts();
 });
 document.addEventListener("pointerdown",event=>{
  if(!event.target.closest?.(".multi-select"))closeFilterMenus();
  if(currentScreen==="visual"&&!previewOnly){
   if(!event.target.closest?.("#visual-tools-drawer,#toggle-tools-drawer"))setEditorCurtain("tools",false);
   if(!event.target.closest?.("#visual-props-drawer,#toggle-props-drawer"))setEditorCurtain("props",false);
  }
 });
 $("back-to-visual").onclick=()=>{
  if(editing){
   const issues=E.validate(editing);
   if(issues.length){status("A configuração ainda tem pendências: "+issues.join("; "),true);return}
  }
  editing=null;showScreen("visual");
  status("Gráfico atualizado dentro do laboratório. Salve o rascunho para manter as alterações.");
 };
 for(const id of ["axis-x","axis-y","axis-z","axis-header","chart-title",
  "year-mode","year-fixed","period-mode","period-fixed","allow-measure-filter",
  "show-values","top-n"]){
  $(id).addEventListener("change",updateBinding);
 }
 $("chart-type").addEventListener("change",()=>{
   if(!editing)return;
   const type=$("chart-type").value;
   if(type==="RANKING"||type==="HORIZONTAL"){
     $("axis-x").value="valor";$("axis-y").value="bimestre";
   }else if(type==="HEATMAP"){
     $("axis-x").value="ano";$("axis-y").value="bimestre";
   }else if(type==="SCATTER"){
     $("axis-x").value="valor";$("axis-y").value="valor";
     if(editing.measures.length<2){
       const additional=E.MEASURES.map(m=>m[0]).find(k=>!editing.measures.includes(k));
       if(additional)editing.measures.push(additional);
       for(const checkbox of $("measure-choices").querySelectorAll("input"))
         checkbox.checked=editing.measures.includes(checkbox.value);
     }
   }
   updateBinding();
 });
 $("chart-title").addEventListener("input",updateBinding);
 document.addEventListener("keydown",event=>{
  if(event.key==="Escape"&&document.querySelector(".multi-select[open]")){
   event.preventDefault();
   closeFilterMenus();
   return;
  }
  if(event.key==="Escape"&&previewOnly){
   event.preventDefault();
   exitPanelPreview();
   return;
  }
  if(currentScreen!=="visual"||previewOnly)return;
  if(event.key==="Escape"&&(
    $("visual-tools-drawer").classList.contains("drawer-open")||
    $("visual-props-drawer").classList.contains("drawer-open")
  )){
   setEditorCurtain("tools",false);
   setEditorCurtain("props",false);
   event.preventDefault();
   return;
  }
  if(event.key==="Escape"){state.selected=null;renderCanvas();renderProperties();return}
  const target=event.target;
  if(target?.closest?.('input,textarea,select,[contenteditable="true"]'))return;
  if((event.key==="Delete"||event.key==="Backspace")&&state.selected){
   event.preventDefault();deleteObject(state.selected);
  }
  const arrows={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
  if(arrows[event.key]&&state.selected){
   const item=object(state.selected);
   if(item){
    event.preventDefault();
    checkpoint();
    const speed=event.shiftKey?10:1;
    item.x=bounded(item.x+arrows[event.key][0]*speed,-4000,15000,12);
    item.y=bounded(item.y+arrows[event.key][1]*speed,-4000,15000,12);
    renderCanvas();renderProperties();
    return;
   }
  }
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="z"){
   event.preventDefault();event.shiftKey?redoVisual():undoVisual();
  }
 });
 window.addEventListener("resize",()=>{
  for(const chart of instances.values())try{chart.resize()}catch(_){}
 });
}
wire();loadLab();
})();
