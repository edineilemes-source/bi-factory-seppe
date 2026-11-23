/* Verificação do contrato de filtros múltiplos, sem alteração de dados. */
const assert=require("node:assert/strict");
const E=require("../experiments/echarts-axes-8507/engine.js");
const revenue="receita_realizada_acumulada";
const paid="despesa_paga_acumulada";
const committed="despesa_empenhada_acumulada";
const rows=[];
for(const year of [2022,2023,2024,2025,2026]){
 for(let bim=1;bim<=(year===2026?4:6);bim++){
  rows.push({
   ano:year,bimestre:bim,
   [revenue]:year*10000+bim*1000,
   [paid]:year*1000+bim*100,
   [committed]:year*2000+bim*200
  });
 }
}
const official=E.normalizedRows(rows);
assert.equal(official.length,28);
const editable=E.createChart("editable",{
 type:"BAR",measures:[revenue,paid,committed],
 scope:{ano:{mode:"filterable"},bimestre:{mode:"filterable"}},
 measureFilterable:true
});
const fixed=E.createChart("fixed",{
 type:"BAR",measures:[revenue],
 scope:{ano:{mode:"fixed",fixed:2025},bimestre:{mode:"all"}},
 measureFilterable:false
});
const select=filters=>E.allowedRows(editable,official,filters);
assert.equal(select({ano:["2022","2024"]}).length,12);
assert.equal(select({ano:["2022","2024"],bimestre:["1","3"]}).length,4);
assert.equal(select({ano:["2022","2024"],bimestre:[]}).length,12);
assert.equal(select({ano:[]}).length,28);
assert.equal(select({ano:"2023"}).length,6,"Legacy scalar filter remains compatible");
assert.equal(select({ano:["2026"],bimestre:["5"]}).length,0);
assert.equal(select({ano:["2026"],bimestre:["4"]}).length,1);
assert.deepEqual(E.allowedOptions([editable],official,"ano"),[2022,2023,2024,2025,2026]);
assert.deepEqual(E.allowedOptions([editable],official,"bimestre",{ano:["2026"]}),[1,2,3,4]);
assert.deepEqual(E.allowedMeasures([editable]),[revenue,paid,committed]);
const multi=E.build(editable,official,{ano:["2022","2024"],bimestre:["1","3"]},[paid,committed]);
assert.equal(multi.rows.length,4);
assert.deepEqual(multi.fields,[paid,committed]);
assert.ok(multi.options.series.every(s=>["Despesa paga","Despesa empenhada"].includes(s.name)));
const allMeasures=E.build(editable,official,{ano:[]},[]);
assert.equal(allMeasures.fields.length,3);
const unauthorized=E.build(editable,official,{},["liquidada_nao_paga"]);
assert.deepEqual(unauthorized.fields,[revenue,paid,committed]);
const fixedResult=E.build(fixed,official,{ano:["2022","2024"],bimestre:["1","2"],medida:[paid]},[paid]);
assert.equal(fixedResult.rows.length,6,"Fixed chart ignores global year and period filters");
assert.ok(fixedResult.rows.every(row=>row.ano===2025));
assert.deepEqual(fixedResult.fields,[revenue],"Fixed measure cannot be overridden");
const combined=E.build(editable,official,{ano:["2022","2024"],bimestre:["1","2"]},[]);
assert.deepEqual(combined.options.xAxis.data,[
 "2022 / 1º bim.","2022 / 2º bim.","2024 / 1º bim.","2024 / 2º bim."
]);
const invalidBim5=E.allowedOptions([editable],official,"ano",{bimestre:["5"]});
assert.ok(!invalidBim5.includes(2026));
assert.deepEqual(E.filterValues(null),[]);
assert.deepEqual(E.filterValues("2022"),["2022"]);
assert.deepEqual(E.filterValues(["2022","2022","2024"]),["2022","2024"]);
console.log("OK: 28 bimestres, anos/bimestres/medidas múltiplos, Todos, 2026, fixos e rascunhos antigos.");
