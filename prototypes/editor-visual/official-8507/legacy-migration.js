/* Compatibilidade de leitura: Grade/GridStack 8506 -> Canvas livre 8507.
 * O JSON anterior permanece intacto no servidor. A conversão só vira
 * layout oficial novo depois de o usuário clicar em Salvar produto.
 */
(function(global){
"use strict";
function asNumber(value,fallback){
 const n=Number(value);return Number.isFinite(n)?n:fallback;
}
function migrateLegacy(source,engine){
 if(!source||source.schema!=="bi-factory-editor-poc-v1"||
    !source.objects||typeof source.objects!=="object"||!Array.isArray(source.layout))
  throw Error("Layout antigo não reconhecido");
 const positions=new Map(source.layout.map(slot=>[String(slot.id),slot]));
 const allowed=new Set(["text","title","image","filter","filter_panel","measure_filter",
   "rectangle","square","diamond","ellipse","arrow","line","dashboard"]);
 const measureByLabel=new Map((engine.MEASURES||[]).map(([key,label])=>
   [String(label).toLowerCase(),key]));
 const names=new Set((engine.MEASURES||[]).map(([key])=>key));
 const supportedTypes=new Set(["KPI","BAR","LINE","AREA","POINTS","HORIZONTAL",
   "RANKING","SCATTER","HEATMAP","TABLE"]);
 const warnings=[],objects=[];
 for(const [key,original] of Object.entries(source.objects)){
  if(!original||typeof original!=="object")continue;
  const slot=positions.get(key)||{};
  const id=String(original.id||key);
  const type=String(original.type||"text");
  const converted={
   id,type:type==="dashboard"?"chart":allowed.has(type)?type:"text",
   title:String(original.title||""),
   x:asNumber(original.left,asNumber(slot.x,0)*80),
   y:asNumber(original.top,asNumber(slot.y,0)*72),
   pixelWidth:Math.max(80,asNumber(original.width,asNumber(slot.w,4)*80)),
   pixelHeight:Math.max(45,asNumber(original.height,asNumber(slot.h,2)*72)),
   width:asNumber(slot.w,4),height:asNumber(slot.h,2),
   bg:original.bg||"#ffffff",color:original.color||"#203047",
   borderColor:original.borderColor||"transparent",
   borderWidth:asNumber(original.borderWidth,0),
   opacity:asNumber(original.opacity,100),rotation:asNumber(original.rotation,0),
   z:asNumber(original.z,1),
   fontFamily:original.fontFamily||"Arial",
   size:asNumber(original.size,18),
   bold:Boolean(original.bold),italic:Boolean(original.italic),
   text:String(original.text||""),
   src:original.image||original.src||"",
   dimension:original.dimension||"ano",
   dimensions:Array.isArray(original.dimensions)?original.dimensions:["ano","bimestre"],
   legacyOriginal:original
  };
  if(type==="dashboard"){
   const spec=original.chart;
   if(!spec||!supportedTypes.has(spec.type)){
    converted.type="text";
    converted.text="Gráfico anterior: "+(original.title||id)+
      ". Configure novamente no ECharts; a definição original foi preservada.";
    warnings.push("Gráfico "+(original.title||id)+" requer revisão do tipo.");
   }else{
    const requested=Array.isArray(spec.metrics)?spec.metrics:[];
    const fields=requested.map(m=>names.has(m)?m:
       measureByLabel.get(String(m).toLowerCase())).filter(Boolean);
    const measures=fields.length?fields:[engine.MEASURES[0][0]];
    const dimensions=Array.isArray(spec.dimensions)?spec.dimensions:[];
    const axisX=dimensions.includes("ano")?"ano":
      dimensions.includes("bimestre")?"bimestre":"ano";
    const axes={x:axisX,y:"valor",z:"nenhum",header:"ano"};
    const chart=engine.createChart(id,{
      type:spec.type,title:original.title||spec.title||"Gráfico anterior",
      measures,axes,
      scope:{ano:{mode:"filterable",fixed:2025},
             bimestre:{mode:"all",fixed:1}},
      measureFilterable:Boolean(spec.measureFilterable)
    });
    // Registro original preservado na própria definição para conferência.
    chart.legacyOriginal=spec;
    converted.chart=chart;
    warnings.push("Confira eixos, medidas e filtros do gráfico "+
      (converted.title||id)+" migrado do modelo anterior.");
   }
  }else if(!allowed.has(type)){
   converted.text="Objeto anterior não reconhecido: "+type;
   warnings.push("Objeto "+id+" requer revisão.");
  }
  objects.push(converted);
 }
 const selected=[];
 for(const [dim,value] of Object.entries(source.filters?.selections||{})){
  if(value!==null&&value!==undefined&&String(value)!==""){
   selected.push([dim,[String(value)]]);
  }
 }
 const filters=Object.fromEntries(selected);
 return {state:{version:1,objects,filters,selected:null},
   warnings,source:"bi-factory-editor-poc-v1",convertedCount:objects.length};
}
global.BI8507Migrate={migrateLegacy};
})(typeof window!=="undefined"?window:globalThis);
