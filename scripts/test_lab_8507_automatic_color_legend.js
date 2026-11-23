/* Regressão 8507: legendas por cor independentes do Z e rótulos sem uso da legenda.
 * Dados de teste inteiramente sintéticos, não alteram o RREO.
 */
const assert=require("node:assert/strict");
const E=require("../experiments/echarts-axes-8507/engine.js");
const revenue="receita_realizada_acumulada";
const paid="despesa_paga_acumulada";
const committed="despesa_empenhada_acumulada";
const samples=[];
for(const ano of [2024,2025]){
 for(const bimestre of [1,2,3]){
  samples.push({ano,bimestre,
   [revenue]:ano*100000+bimestre*110,
   [paid]:ano*70000+bimestre*100,
   [committed]:ano*90000+bimestre*130});
 }
}
const rows=E.normalizedRows(samples);
function make(type,z="nenhum",overrides={}){
 return E.createChart("t-"+type+"-"+z,{
  type,measures:[revenue,paid],
  axes:{x:"bimestre",y:"valor",z,header:"ano"},
  scope:{ano:{mode:"fixed",fixed:2025},bimestre:{mode:"all",fixed:1}},
  ...overrides
 });
}
for(const type of ["BAR","LINE","AREA","POINTS","HORIZONTAL","RANKING","SCATTER","HEATMAP"]){
 for(const z of ["medida","valor","rotulo","nenhum"]){
  const extra=type==="HORIZONTAL"?{axes:{x:"valor",y:"bimestre",z,header:"ano"}}:
   type==="SCATTER"?{axes:{x:"valor",y:"valor",z,header:"ano"}}:
   type==="HEATMAP"?{axes:{x:"ano",y:"bimestre",z,header:"nenhum"},
     scope:{ano:{mode:"all"},bimestre:{mode:"all"}}}:{};
  const graph=make(type,z,extra);
  const out=E.build(graph,rows);
  assert.equal(out.kind,"chart",type+" should draw a graph: "+JSON.stringify(out.error||out.empty));
  if(type==="HEATMAP"){
   assert.equal(out.options.visualMap.show,true,"Heatmap must always display the scale");
   assert.match(out.options.visualMap.text.join(" "),/Receita realizada/);
   assert.ok(Array.isArray(out.options.visualMap.inRange.color));
  }else{
   assert.equal(out.options.legend.show,true,type+" must show automatic legend even with Z="+z);
   assert.ok(out.options.legend.data.length>=1,type+" legend has labels");
   for(const s of out.options.series)
    assert.ok(out.options.legend.data.includes(s.name),type+" must identify each colored series");
  }
  for(const series of out.options.series){
   assert.equal(series.label.show,z!=="nenhum",type+" Z="+z+" label visibility");
  }
 }
}
const bar=E.build(make("BAR","nenhum"),rows).options;
assert.deepEqual(bar.legend.data,["Receita realizada","Despesa paga"]);
const barValue=E.build(make("BAR","valor"),rows).options;
assert.match(barValue.series[0].label.formatter({name:"1º bim.",value:1234}),/mil/);
const barMeasure=E.build(make("BAR","medida"),rows).options;
assert.equal(barMeasure.series[0].label.formatter({name:"1º bim.",value:1234}),"Receita realizada");
const barCategory=E.build(make("BAR","rotulo"),rows).options;
assert.equal(barCategory.series[0].label.formatter({name:"1º bim.",value:1234}),"1º bim.");
const category=E.build(make("BAR","nenhum",{
 axes:{x:"medida",y:"valor",z:"nenhum",header:"ano"}
}),rows).options;
assert.deepEqual(category.legend.data,["Receita realizada","Despesa paga"]);
assert.equal(category.series.length,2);
assert.notEqual(category.series[0].itemStyle.color,category.series[1].itemStyle.color);
const scatter=E.build(make("SCATTER","nenhum",{
 axes:{x:"valor",y:"valor",z:"nenhum",header:"ano"}
}),rows).options;
assert.deepEqual(scatter.legend.data,["Receita realizada × Despesa paga"]);
const ranking=E.build(make("RANKING","nenhum"),rows).options;
assert.deepEqual(ranking.legend.data,["Receita realizada"]);
const legacy=E.createChart("legacy",{type:"BAR",measures:[revenue,paid]});
delete legacy.labelSchema;
legacy.axes.z="medida";
legacy.showLabels=false;
assert.equal(E.zMode(legacy),"nenhum","old Z=medida used to only mean legend");
assert.equal(E.build(legacy,rows).options.legend.show,true);
legacy.showLabels=true;
assert.equal(E.zMode(legacy),"valor","old explicit value labels remain available");
assert.equal(E.zMode(E.createChart("new")),"nenhum");
console.log("OK: legenda automática em barras/linhas/área/pontos/ranking/dispersão, escala do mapa de calor, Z com quatro rótulos e legado.");
