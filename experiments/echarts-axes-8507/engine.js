/* BI Factory SEPPE — laboratório isolado da porta 8507.
 * X, Y, Z e Cabeçalho são papéis visuais; os únicos campos de origem
 * do RREO são Ano, Bimestre e medidas acumuladas.
 * Não agrega nem soma bimestres acumulados.
 */
(function(root,factory){
 const api=factory();
 if(typeof module==="object"&&module.exports)module.exports=api;
 root.BIAxesEngine=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
 "use strict";
 const MEASURES=[
  ["receita_realizada_acumulada","Receita realizada"],
  ["despesa_empenhada_acumulada","Despesa empenhada"],
  ["despesa_liquidada_acumulada","Despesa liquidada"],
  ["despesa_paga_acumulada","Despesa paga"],
  ["resultado_orcamentario_formal","Resultado orçamentário formal"],
  ["margem_receita_menos_liquidada","Margem receita × liquidada"],
  ["liquidada_nao_paga","Liquidada não paga"]
 ];
 const byKey=Object.fromEntries(MEASURES);
 const DIMENSIONS={ano:"Ano",bimestre:"Bimestre"};
 const AXES={ano:"Ano",bimestre:"Bimestre",valor:"Valor",medida:"Medida"};
 const TYPES={BAR:"Colunas",LINE:"Linhas",AREA:"Área",HORIZONTAL:"Barras horizontais",
  RANKING:"Ranking",POINTS:"Pontos",SCATTER:"Dispersão",HEATMAP:"Mapa de calor",
  KPI:"Indicador",TABLE:"Tabela"};
 const colors=["#25a0a7","#b0d96d","#ee9946","#6d7cce","#c66091","#4badd6","#dbbc56"];
 const money=v=>new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL",maximumFractionDigits:2}).format(v);
 const compact=v=>{const a=Math.abs(v);return a>=1e9?(v/1e9).toLocaleString("pt-BR",{maximumFractionDigits:1})+" bi":
     a>=1e6?(v/1e6).toLocaleString("pt-BR",{maximumFractionDigits:1})+" mi":
     a>=1e3?(v/1e3).toLocaleString("pt-BR",{maximumFractionDigits:1})+" mil":v.toLocaleString("pt-BR",{maximumFractionDigits:0})};
 const numeric=v=>{if(v===null||v===undefined||v==="")return null;const n=Number(v);return Number.isFinite(n)?n:null};
 function normalizedRows(rows){
   if(!Array.isArray(rows))return [];
   const seen=new Set();
   return rows.map(r=>{
    const ano=Number(r.ano??r.exercicio), bimestre=Number(r.bimestre);
    if(!Number.isInteger(ano)||!Number.isInteger(bimestre)||bimestre<1||bimestre>6)return null;
    const key=ano+"-"+bimestre;if(seen.has(key))return null;seen.add(key);
    const item={ano,bimestre};
    for(const [field] of MEASURES)item[field]=numeric(r[field]);
    return item;
   }).filter(Boolean).sort((a,b)=>a.ano-b.ano||a.bimestre-b.bimestre);
 }
 const scope=(mode="filterable",fixed=null)=>({mode,fixed});
 function createChart(id,opts={}){
  const available=new Set(MEASURES.map(([key])=>key));
  const picked=(opts.measures||["receita_realizada_acumulada"]).filter(k=>available.has(k));
  return {
   id:id||"g-"+Math.random().toString(36).slice(2),type:opts.type||"BAR",
   title:opts.title||"Novo gráfico",
   axes:{x:opts.axes?.x||"bimestre",y:opts.axes?.y||"valor",
     z:opts.axes?.z||"nenhum",header:opts.axes?.header||"ano"},
   labelSchema:2,
   measures:picked.length?picked:["receita_realizada_acumulada"],
   scope:{
    ano:scope(opts.scope?.ano?.mode||"fixed",opts.scope?.ano?.fixed??2025),
    bimestre:scope(opts.scope?.bimestre?.mode||"filterable",opts.scope?.bimestre?.fixed??1)
   },
   measureFilterable:Boolean(opts.measureFilterable),
   showLabels:opts.showLabels??false,
   topN:Number(opts.topN??10),
   width:Number(opts.width||6),
   height:Number(opts.height||4),
   palette:opts.palette||colors.slice(),
  };
 }
 function validate(chart){
  const problems=[];
  if(!TYPES[chart.type])problems.push("Tipo de gráfico inválido");
  const x=chart.axes?.x,y=chart.axes?.y;
  if(!AXES[x]||!AXES[y])problems.push("Defina X e Y com campos válidos");
  if(x===y&&!(chart.type==="SCATTER"&&x==="valor"))
   problems.push("Eixos X e Y devem ter funções diferentes");
  if(chart.type==="SCATTER"&&(x!=="valor"||y!=="valor"))
   problems.push("Dispersão usa Valor nos dois eixos, com uma medida diferente em cada eixo");
  const keys=(chart.measures||[]).filter(k=>byKey[k]);
  if(!keys.length)problems.push("Escolha pelo menos uma medida");
  if(chart.type==="SCATTER"&&keys.length<2)problems.push("Dispersão exige duas medidas: X e Y");
  if(["BAR","LINE","AREA","HORIZONTAL","RANKING","POINTS"].includes(chart.type)){
   const vals=[x,y].filter(k=>k==="valor").length;
   if(vals!==1)problems.push("Este gráfico precisa de Valor em um eixo e Ano, Bimestre ou Medida no outro");
  }
  if(chart.type==="HEATMAP"&&(x==="valor"||y==="valor"))
   problems.push("Mapa de calor exige dois eixos categóricos; Valor será a intensidade");
  for(const dim of ["ano","bimestre"]){
    const s=chart.scope?.[dim];
    if(!s||!["fixed","filterable","all"].includes(s.mode))
      problems.push("Escopo "+DIMENSIONS[dim]+" inválido");
    if(s?.mode==="fixed"&&!Number.isInteger(Number(s.fixed)))
      problems.push("Escolha um valor fixo de "+DIMENSIONS[dim]);
  }
  return problems;
 }
 // Agora Z controla somente os rótulos, e não a legenda.
 // Compatibilidade: antes da versão 2, Z="medida" controlava a legenda.
 function zMode(chart){
  const z=chart.axes?.z||"nenhum";
  if(chart.labelSchema!==2&&z==="medida")return chart.showLabels?"valor":"nenhum";
  if(chart.labelSchema!==2&&z==="nenhum"&&chart.showLabels)return "valor";
  return ["medida","valor","rotulo","nenhum"].includes(z)?z:"nenhum";
 }
 function dataLabel(mode,measure,category,value){
  if(mode==="medida")return measure||"";
  if(mode==="rotulo")return category||"";
  if(mode==="valor")return value==null?"":compact(value);
  return "";
 }
 const autoLegend=names=>({show:true,type:"scroll",top:0,left:"center",data:[...new Set(names)]});
 function filterValues(value){
  // [] e valor ausente significam Todos, inclusive para rascunhos antigos.
  if(value==null||value===""||value==="all")return [];
  const values=Array.isArray(value)?value:[value];
  return [...new Set(values.filter(v=>v!==null&&v!==undefined&&v!==""&&v!=="all").map(String))];
 }
 function allowedRows(chart,rows,globalFilters={}){
  return rows.filter(row=>{
   for(const d of ["ano","bimestre"]){
    const s=chart.scope?.[d];
    if(s?.mode==="fixed"&&String(row[d])!==String(s.fixed))return false;
    const selected=filterValues(globalFilters[d]);
    if(s?.mode==="filterable"&&selected.length&&!selected.includes(String(row[d])))return false;
   }
   return true;
  });
 }
 function allowedOptions(charts,rows,dimension,globalFilters={}){
  if(!DIMENSIONS[dimension])return [];
  const applicable=charts.filter(c=>c.scope?.[dimension]?.mode==="filterable");
  if(!applicable.length)return [];
  const found=new Set();
  // Respeitar o escopo fixo de cada gráfico e os outros filtros do painel.
  const otherFilters={...globalFilters};delete otherFilters[dimension];
  for(const chart of applicable)for(const row of allowedRows(chart,rows,otherFilters))found.add(row[dimension]);
  return [...found].sort((a,b)=>a-b);
 }
 function allowedMeasures(charts){
  const found=new Set();
  for(const chart of charts){
   if(chart.measureFilterable)for(const field of chart.measures||[])if(byKey[field])found.add(field);
  }
  return [...found];
 }
 function fixedBadge(chart,dimension){
   const sc=chart.scope?.[dimension];
   if(sc?.mode==="fixed")return DIMENSIONS[dimension]+": "+sc.fixed+" (fixo no ECharts)";
   if(sc?.mode==="filterable")return DIMENSIONS[dimension]+": filtrável no produto";
   return DIMENSIONS[dimension]+": todos (sem filtro externo)";
 }
 function dimensionLabel(row,dim,field){
  if(dim==="medida")return byKey[field]||field;
  if(dim==="ano")return String(row.ano);
  if(dim==="bimestre")return row.bimestre+"º bim.";
  return "";
 }
 function build(chart,rawRows,globalFilters={},measureSelection=""){
  const issues=validate(chart);
  if(issues.length)return {error:issues.join(". ")};
  const rows=allowedRows(chart,rawRows,globalFilters);
  if(!rows.length)return {empty:"Sem registros para o escopo definido no ECharts"};
  let fields=chart.measures.filter(f=>byKey[f]);
  if(chart.measureFilterable){
   const chosen=filterValues(measureSelection);
   const matching=fields.filter(f=>chosen.includes(f));
   if(chosen.length&&matching.length)fields=matching;
  }
  const x=chart.axes.x,y=chart.axes.y,z=zMode(chart),heading=chart.axes.header;
  const headingParts=[chart.title];
  if(heading==="ano"){
   const years=[...new Set(rows.map(r=>r.ano))];
   headingParts.push(years.length===1?"Ano "+years[0]:years[0]+"–"+years.at(-1));
  }else if(heading==="bimestre"){
   const periods=[...new Set(rows.map(r=>r.bimestre))];
   headingParts.push(periods.length===1?periods[0]+"º bimestre":"Vários bimestres");
  }else if(heading==="medida")headingParts.push(fields.map(f=>byKey[f]).join(" / "));
  const header=headingParts.join(" · ");
  if(chart.type==="KPI"){
   // Não somar períodos acumulados: o valor exibido é o último registro.
   const last=rows.at(-1),field=fields[0];
   return {kind:"kpi",header,value:last[field],metric:byKey[field],period:last.ano+" / "+last.bimestre+"º bim.",
     rows,fields};
  }
  if(chart.type==="TABLE"){
   return {kind:"table",header,rows,fields};
  }
  if(chart.type==="SCATTER"){
   const ax=fields[0],ay=fields[1];
   const seriesName=byKey[ax]+" × "+byKey[ay];
   const points=rows.map(r=>[r[ax],r[ay],r.ano+" / "+r.bimestre+"º bim."])
     .filter(p=>p[0]!==null&&p[1]!==null);
   return {kind:"chart",header,rows,fields,options:{
      color:chart.palette||colors,legend:autoLegend([seriesName]),
      grid:{left:20,right:20,top:60,bottom:62,containLabel:true},
      xAxis:{type:"value",name:byKey[ax],nameLocation:"middle",nameGap:34,axisLabel:{formatter:compact}},
      yAxis:{type:"value",name:byKey[ay],nameLocation:"middle",nameGap:64,axisLabel:{formatter:compact}},
      tooltip:{trigger:"item",formatter:p=>p.value[2]+": "+money(p.value[0])+" × "+money(p.value[1])},
      series:[{type:"scatter",name:seriesName,symbolSize:12,data:points,
       label:{show:z!=="nenhum",position:"top",formatter:p=>
        z==="valor"?compact(p.value[0])+" × "+compact(p.value[1]):
        dataLabel(z,seriesName,p.value[2],p.value[1])}}]
    }};
  }
  const first=fields[0],categorical=x==="valor"?y:x;
  const chartRows=[];
  const multipleYears=new Set(rows.map(r=>r.ano)).size>1;
  for(const row of rows){
    for(const field of fields){
      const label=categorical==="bimestre"&&multipleYears?
        row.ano+" / "+row.bimestre+"º bim.":dimensionLabel(row,categorical,field);
      const value=row[field];
      if(value!==null)chartRows.push({label,value,field,row});
    }
  }
  if(chart.type==="HEATMAP"){
    const xs=[...new Set(rows.map(r=>dimensionLabel(r,x,first)))];
    const ys=[...new Set(rows.map(r=>dimensionLabel(r,y,first)))];
    const values=[];for(const r of rows){
      const i=xs.indexOf(dimensionLabel(r,x,first)),j=ys.indexOf(dimensionLabel(r,y,first));
      if(i>=0&&j>=0&&r[first]!==null)values.push([i,j,r[first]]);
    }
    if(!values.length)return {empty:"Sem valores para o mapa de calor"};
    const all=values.map(v=>v[2]);
    return {kind:"chart",header,rows,fields,options:{
      tooltip:{position:"top",formatter:p=>xs[p.value[0]]+" / "+ys[p.value[1]]+": "+money(p.value[2])},
      grid:{top:28,left:20,right:35,bottom:95,containLabel:true},
      xAxis:{type:"category",data:xs,splitArea:{show:true}},
      yAxis:{type:"category",data:ys,splitArea:{show:true}},
      // Legenda contínua automática: associa explicitamente a escala de cores à medida.
      visualMap:{show:true,min:Math.min(...all),max:Math.max(...all),calculable:true,
       text:[byKey[first]+" · maior valor","Menor valor"],textGap:10,
       orient:"horizontal",left:"center",bottom:4,inRange:{color:["#eaf4f7","#27a0a7"]}},
      series:[{type:"heatmap",name:byKey[first],data:values,
       label:{show:z!=="nenhum",formatter:p=>dataLabel(z,byKey[first],
        xs[p.value[0]]+" / "+ys[p.value[1]],p.value[2])}}]
    }};
  }
  if(!chartRows.length)return {empty:"Sem dados numéricos para o gráfico"};
  const categories=[...new Set(chartRows.map(p=>p.label))];
  const labelFor=p=>p.label;
  let series=[];
  if(chart.type==="RANKING"){
    const perCat=new Map();
    // Para campos temporais, existe uma única observação por categoria e medida.
    for(const p of chartRows.filter(p=>p.field===first)){
      if(!perCat.has(p.label)||p.row.ano>perCat.get(p.label).row.ano||
         (p.row.ano===perCat.get(p.label).row.ano&&p.row.bimestre>perCat.get(p.label).row.bimestre))
          perCat.set(p.label,p);
    }
    let ranked=[...perCat.values()].sort((a,b)=>b.value-a.value);
    if(chart.topN>0)ranked=ranked.slice(0,chart.topN);
    const labelPosition=x==="valor"?"right":"top";
    return {kind:"chart",header,rows,fields,options:{
      color:chart.palette||colors,legend:autoLegend([byKey[first]]),
      grid:{left:20,right:85,top:60,bottom:40,containLabel:true},
      xAxis:{type:"value",axisLabel:{formatter:compact}},
      yAxis:{type:"category",inverse:true,data:ranked.map(p=>p.label),
       axisLabel:{width:145,overflow:"truncate",interval:0}},
      tooltip:{trigger:"axis",valueFormatter:money,axisPointer:{type:"shadow"}},
      series:[{type:"bar",name:byKey[first],barMaxWidth:28,data:ranked.map(p=>p.value),
       label:{show:z!=="nenhum",position:"right",formatter:p=>dataLabel(z,byKey[first],
        ranked[p.dataIndex]?.label,p.value)}}]
     }};
  }
  // Evitar somas de acumulados: se o eixo usa Ano, escolher último bimestre
  // de cada ano; o escopo de bimestre fixo/filtrável já foi aplicado acima.
  let prepared=rows;
  if(categorical==="ano"&&chart.scope.bimestre.mode!=="fixed"&&
     !(chart.scope.bimestre.mode==="filterable"&&filterValues(globalFilters.bimestre).length)){
    const map=new Map();for(const r of rows)map.set(r.ano,r);prepared=[...map.values()];
  }
  let categoryValues=[];
  if(categorical==="medida")categoryValues=fields.map(f=>byKey[f]);
  else categoryValues=[...new Set(prepared.map(r=>dimensionLabel(r,categorical,fields[0])))];
  // Quando o período é um bimestre e há diversos anos, distinguir cada par.
  const useCombined=categorical==="bimestre"&&new Set(prepared.map(r=>r.ano)).size>1;
  if(useCombined)categoryValues=prepared.map(r=>r.ano+" / "+r.bimestre+"º bim.");
  const labelOf=r=>useCombined?r.ano+" / "+r.bimestre+"º bim.":dimensionLabel(r,categorical,fields[0]);
  const valueFor=(field,label)=>{
    if(categorical==="medida"){
      const last=prepared.at(-1);return field===fields.find(f=>byKey[f]===label)?last[field]:null;
    }
    const row=prepared.find(r=>labelOf(r)===label);
    return row?row[field]:null;
  };
  const horizontal=x==="valor";
  if(categorical==="medida"){
    // Cada categoria Medida recebe sua própria cor e nome na legenda.
    const latest=prepared.at(-1);
    series=fields.map((field,i)=>({
      name:byKey[field],type:chart.type==="LINE"||chart.type==="AREA"?"line":
        chart.type==="POINTS"?"scatter":"bar",
      barMaxWidth:40,symbolSize:chart.type==="POINTS"?12:undefined,
      itemStyle:{color:(chart.palette||colors)[i%(chart.palette||colors).length]},
      areaStyle:chart.type==="AREA"?{}:undefined,
      data:categoryValues.map(label=>label===byKey[field]?latest[field]:null),
      label:{show:z!=="nenhum",position:horizontal?"right":"top",
       formatter:p=>dataLabel(z,byKey[field],p.name,p.value)}
    }));
  }else series=fields.map((field,i)=>({
    name:byKey[field],type:["LINE","AREA"].includes(chart.type)?"line":
      chart.type==="POINTS"?"scatter":"bar",
    barMaxWidth:40,symbolSize:chart.type==="POINTS"?12:undefined,
    areaStyle:chart.type==="AREA"?{}:undefined,
    data:categoryValues.map(label=>{
      const v=valueFor(field,label);
      if(v===null)return null;
      return horizontal&&["LINE","AREA","POINTS"].includes(chart.type)?[v,label]:v;
    }),
    label:{show:z!=="nenhum",position:horizontal?"right":"top",
      formatter:p=>{const v=Array.isArray(p.value)?p.value[0]:p.value;
        return dataLabel(z,byKey[field],p.name,v)}}
  }));
  const categoryAxis={type:"category",data:categoryValues,
   axisLabel:{hideOverlap:true,width:120,overflow:"truncate",interval:"auto"}},
   valueAxis={type:"value",axisLabel:{formatter:compact}};
  return {kind:"chart",header,rows,fields,options:{
    color:chart.palette||colors,
    legend:autoLegend(series.map(item=>item.name)),
    tooltip:{trigger:"axis",valueFormatter:v=>money(Array.isArray(v)?v[0]:v)},
    grid:{left:20,right:28,top:60,bottom:48,containLabel:true},
    xAxis:horizontal?valueAxis:categoryAxis,
    yAxis:horizontal?categoryAxis:valueAxis,
    series
  }};
 }
 return {MEASURES,byKey,DIMENSIONS,AXES,TYPES,colors,money,compact,normalizedRows,
   createChart,validate,zMode,filterValues,allowedRows,allowedOptions,allowedMeasures,fixedBadge,build};
});
