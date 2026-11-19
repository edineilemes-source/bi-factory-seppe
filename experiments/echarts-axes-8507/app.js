/* BI Factory SEPPE / laboratório 8507 — editor visual e ECharts independentes.
 * Não acessa nem escreve produtos ou layouts da aplicação 8506.
 */
(()=>{
"use strict";
const E=window.BIAxesEngine;
if(!E){document.body.textContent="Motor do laboratório não foi carregado.";return}
const $=id=>document.getElementById(id);
const node=(tag,text,cls)=>{const item=document.createElement(tag);if(text!==undefined)item.textContent=text;if(cls)item.className=cls;return item};
const modeLabels={fixed:"Fixo",filterable:"Filtrável no produto",all:"Todos, independente dos filtros"};
let state={version:1,objects:[],filters:{},selected:null};
let rows=[],currentScreen="visual",editing=null,previewOnly=false;
const instances=new Map();
const formatNumber=v=>v===null||v===undefined?"Valor indisponível":E.money(v);
function status(message,bad=false){const line=$("global-status");line.textContent=message;line.style.color=bad?"#a14635":"#496473"}
function object(id){return state.objects.find(o=>o.id===id)}
function charts(){return state.objects.filter(o=>o.type==="chart"&&o.chart).map(o=>o.chart)}
function newId(){return "o-"+(crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+Math.random().toString(36).slice(2))}
function elementLabel(o){return o.title||({chart:"Gráfico",text:"Texto",image:"Imagem",filter:"Filtro de dimensão",measure_filter:"Seletor de medidas"}[o.type]||"Objeto")}
function addObject(type,details={},edit=false){
 const obj={id:newId(),type,title:"",width:type==="chart"?6:4,height:type==="chart"?4:2,...details};
 if(type==="chart"){
   obj.chart=obj.chart||E.createChart(obj.id,{title:obj.title||"Novo gráfico",type:"BAR"});
   obj.title=obj.title||obj.chart.title;
 }
 if(type==="filter")obj.dimension=obj.dimension||"ano";
 if(type==="text")obj.text=obj.text||"Clique aqui e escreva seu texto.";
 state.objects.push(obj);
 state.selected=obj.id;
 if(edit&&type==="chart")openChart(obj.id);
 else{renderCanvas();renderProperties()}
 return obj;
}
function disposeAll(){
 for(const chart of instances.values())try{chart.dispose()}catch(_){}
 instances.clear();
}
function showScreen(screen){
 currentScreen=screen;
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
function renderCanvas(){
 disposeAll();
 const canvas=$("visual-canvas");
 canvas.replaceChildren();
 if(!state.objects.length){
  canvas.append(node("div","Produto vazio. Adicione objetos ou use “Montar painel fiscal de exemplo”.","canvas-empty"));
  return;
 }
 for(const obj of state.objects){
   const block=node("section",undefined,"canvas-object");
   const w=Math.min(12,Math.max(3,Number(obj.width)||6));
   block.style.gridColumn="span "+w;
   if(obj.id===state.selected&&!previewOnly)block.classList.add("active");
   block.draggable=!previewOnly;
   block.dataset.objectId=obj.id;
   block.dataset.kind=obj.type==="chart"&&obj.chart?.type==="KPI"?"kpi":obj.type;
   block.addEventListener("click",event=>{if(previewOnly||event.target.closest("select,button,input,[contenteditable]"))return;selectObject(obj.id)});
   block.addEventListener("dragstart",event=>{if(!previewOnly)event.dataTransfer.setData("text/plain",obj.id)});
   block.addEventListener("dragover",event=>event.preventDefault());
   block.addEventListener("drop",event=>{
      event.preventDefault();
      if(previewOnly)return;
      const other=event.dataTransfer.getData("text/plain");
      const from=state.objects.findIndex(o=>o.id===other),to=state.objects.findIndex(o=>o.id===obj.id);
      if(from<0||to<0||from===to)return;
      const moved=state.objects.splice(from,1)[0];
      state.objects.splice(to,0,moved);renderCanvas();
   });
   const header=node("div",undefined,"object-header");
   header.append(node("strong",elementLabel(obj)));
   header.append(node("span",obj.type==="chart"?"ECharts":"Estrutura","hint-id"));
   block.append(header);
   const inner=node("div",undefined,"object-inner");
   block.append(inner);
   if(obj.type==="chart"&&obj.chart){
      inner.classList.add("chart-item");
      inner.dataset.chartHeight=String(Math.max(100,Number(obj.height||4)*65));
      if(obj.chart.type==="KPI")inner.dataset.chartHeight="115";
   }else if(obj.type==="text"){
      const editable=node("div",obj.text||"","text-edit");
      editable.contentEditable=!previewOnly;editable.spellcheck=true;
      editable.addEventListener("blur",()=>{obj.text=editable.innerText});
      editable.addEventListener("mousedown",event=>event.stopPropagation());
      inner.append(editable);
   }else if(obj.type==="image"){
      if(obj.src){const image=node("img");image.src=obj.src;image.alt=obj.title||"Imagem";inner.append(image)}
      else inner.append(node("p","Selecione o objeto e informe a imagem nas propriedades.","small muted"));
   }else if(obj.type==="filter"){renderFilterControl(obj,inner)}
   else if(obj.type==="measure_filter"){renderMeasureControl(obj,inner)}
   canvas.append(block);
   if(obj.type==="chart"&&obj.chart)
      renderChartIn(inner,obj.chart,state.filters,state.filters.medida||"");
 }
}
function renderFilterControl(obj,host){
 const d=E.DIMENSIONS[obj.dimension]?obj.dimension:"ano";
 const options=E.allowedOptions(charts(),rows,d);
 const box=node("div",undefined,"filter-control");
 box.append(node("label","Filtro: "+E.DIMENSIONS[d]));
 if(!options.length){
  box.append(node("div","Nenhum gráfico autoriza alterar "+E.DIMENSIONS[d]+". Configure “Filtrável no produto” no ECharts.","filter-locked"));
 }else{
  const select=node("select");select.add(new Option("Todos os valores permitidos",""));
  for(const val of options)select.add(new Option(d==="bimestre"?val+"º bimestre":String(val),String(val)));
  if(!options.some(val=>String(val)===String(state.filters[d]))){delete state.filters[d]}
  select.value=String(state.filters[d]||"");
  select.addEventListener("click",e=>e.stopPropagation());
  select.addEventListener("mousedown",e=>e.stopPropagation());
  select.onchange=()=>{state.filters[d]=select.value;renderCanvas()};
  box.append(select);
  box.append(node("p","Somente gráficos autorizados mudam; os gráficos fixos ficam intactos.","small muted"));
 }
 host.append(box);
}
function renderMeasureControl(obj,host){
 const options=E.allowedMeasures(charts());
 const box=node("div",undefined,"filter-control");box.append(node("label","Seletor de medidas"));
 if(!options.length){
  box.append(node("div","Nenhum gráfico autoriza variar medidas. O seletor não pode adicionar Receita/Despesa fora do definido no ECharts.","filter-locked"));
 }else{
  const select=node("select");select.add(new Option("Medidas originais dos gráficos",""));
  for(const key of options)select.add(new Option(E.byKey[key],key));
  if(!options.includes(state.filters.medida))state.filters.medida="";
  select.value=state.filters.medida||"";
  select.addEventListener("click",e=>e.stopPropagation());
  select.addEventListener("mousedown",e=>e.stopPropagation());
  select.onchange=()=>{state.filters.medida=select.value;renderCanvas()};
  box.append(select);
  box.append(node("p","Gráficos não autorizados mantêm suas medidas originais.","small muted"));
 }
 host.append(box);
}
function propertiesField(label,value,onchange,kind="input",options=[]){
 const container=node("label");container.append(node("span",label));
 let field;
 if(kind==="select"){
  field=node("select");for(const [v,t] of options)field.add(new Option(t,v));field.value=String(value);
 }else if(kind==="textarea"){field=node("textarea");field.value=value||"";field.rows=5}
 else{field=node("input");field.value=value??"";field.type=kind==="number"?"number":"text"}
 field.addEventListener("change",()=>onchange(field.value));
 container.append(field);return container;
}
function propButton(text,fn,kind=""){
 const btn=node("button",text,kind);btn.onclick=fn;return btn;
}
function renderProperties(){
 const root=$("visual-props");root.replaceChildren();
 const o=object(state.selected);
 if(!o){root.append(node("p","Selecione um objeto no canvas.","small muted"));return}
 root.append(node("h3",elementLabel(o)));
 root.append(propertiesField("Título",o.title||"",v=>{o.title=v;if(o.chart)o.chart.title=v;renderCanvas()}));
 root.append(propertiesField("Largura",o.width,v=>{o.width=Number(v);renderCanvas()},"select",
  [[3,"3 colunas"],[4,"4 colunas"],[6,"6 colunas"],[8,"8 colunas"],[12,"12 colunas"]]));
 if(o.type==="chart"){
  root.append(propertiesField("Altura",o.height||4,v=>{o.height=Number(v);renderCanvas()},"select",
    [[2,"Baixa"],[3,"Compacta"],[4,"Padrão"],[5,"Alta"],[6,"Muito alta"]]));
  root.append(propButton("Editar X, Y, Z e Cabeçalho no ECharts",()=>openChart(o.id),"primary"));
  root.append(node("p","Escopo atual: "+E.fixedBadge(o.chart,"ano")+"; "+E.fixedBadge(o.chart,"bimestre"),"small muted"));
 }else if(o.type==="filter"){
  root.append(propertiesField("Dimensão do filtro",o.dimension,v=>{o.dimension=v;renderCanvas()},"select",
   Object.entries(E.DIMENSIONS)));
  root.append(node("p","Aqui você posiciona e identifica o filtro. Os valores permitidos vêm dos gráficos.","small muted"));
 }else if(o.type==="text"){
  root.append(propertiesField("Texto",o.text||"",v=>{o.text=v;renderCanvas()},"textarea"));
 }else if(o.type==="image"){
  root.append(propertiesField("URL HTTPS da imagem",o.src?.startsWith("http")?o.src:"",v=>{
    if(v&&!/^https:\/\//i.test(v)){status("A URL da imagem precisa usar HTTPS.",true);return}
    o.src=v;renderCanvas()
  }));
  const input=node("input");input.type="file";input.accept="image/png,image/jpeg,image/webp";input.style.marginTop="8px";
  input.onchange=()=>{const file=input.files?.[0];if(!file)return;
    if(file.size>500000){status("Imagem acima de 500 KB; reduza o arquivo antes de enviar.",true);return}
    const reader=new FileReader();reader.onload=()=>{o.src=String(reader.result);renderCanvas()};reader.readAsDataURL(file)};
  root.append(input);
 }
 root.append(propButton("Duplicar objeto",()=>{
   const copy=JSON.parse(JSON.stringify(o));copy.id=newId();
   if(copy.chart)copy.chart.id=copy.id;
   state.objects.splice(state.objects.indexOf(o)+1,0,copy);selectObject(copy.id);
 },"secondary"));
 root.append(propButton("Excluir objeto",()=>{
    if(!confirm("Excluir este objeto do laboratório?"))return;
    state.objects=state.objects.filter(item=>item.id!==o.id);
    state.selected=state.objects.at(-1)?.id||null;renderCanvas();renderProperties()
 },"danger"));
}
