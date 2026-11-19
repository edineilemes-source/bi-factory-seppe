/* Testes do laboratório 8507. Rodar com:
 * node scripts/test_echarts_axes_8507.js
 * Usa dados simulados SOMENTE em memória para teste, jamais no painel.
 */
const assert=require("node:assert/strict");
const E=require("../experiments/echarts-axes-8507/engine.js");
const revenue="receita_realizada_acumulada";
const expense="despesa_empenhada_acumulada";
const paid="despesa_paga_acumulada";
const samples=[];
for(const [year,count] of [[2022,6],[2025,6],[2026,4]]){
 for(let bim=1;bim<=count;bim++){
   samples.push({
     ano:year,bimestre:bim,
     [revenue]:(year-2000)*1000+bim*10,
     [expense]:(year-2000)*800+bim*10,
     [paid]:(year-2000)*600+bim*10,
   });
 }
}
const rows=E.normalizedRows(samples);
assert.equal(rows.length,16);
const fixed=E.createChart("fixed",{
 title:"Somente Receita 2025",
 measures:[revenue],
 scope:{ano:{mode:"fixed",fixed:2025},bimestre:{mode:"all",fixed:1}},
 axes:{x:"bimestre",y:"valor",z:"valor",header:"ano"}
});
assert.deepEqual(E.validate(fixed),[]);
assert.deepEqual(E.allowedOptions([fixed],rows,"ano"),[]);
assert.deepEqual(E.allowedMeasures([fixed]),[]);
const f=E.build(fixed,rows,{ano:"2026",bimestre:"1",medida:expense},expense);
assert.equal(f.rows.length,6,"Ano fixo ignora filtro de ano e bimestre 'all' ignora filtro externo");
assert.ok(f.rows.every(r=>r.ano===2025));
assert.deepEqual(f.fields,[revenue],"Nenhuma despesa entra num gráfico somente Receita");
assert.equal(f.options.series.length,1);
assert.equal(f.options.series[0].data.at(-1),25060);
assert.match(f.header,/2025/);
const editable=E.createChart("editable",{
 title:"Execução filtrável",
 measures:[expense,paid],
 scope:{ano:{mode:"filterable"},bimestre:{mode:"filterable"}},
 measureFilterable:true,
 axes:{x:"bimestre",y:"valor",z:"medida",header:"ano"},
});
assert.deepEqual(E.allowedOptions([editable],rows,"ano"),[2022,2025,2026]);
assert.deepEqual(E.allowedOptions([editable],rows,"bimestre"),[1,2,3,4,5,6]);
assert.deepEqual(E.allowedMeasures([editable]),[expense,paid]);
const only2026=E.build(editable,rows,{ano:"2026"});
assert.equal(only2026.rows.length,4);
assert.ok(only2026.rows.every(r=>r.ano===2026));
const onlyPaid=E.build(editable,rows,{ano:"2026"},paid);
assert.deepEqual(onlyPaid.fields,[paid]);
const refusesRevenue=E.build(editable,rows,{ano:"2026"},revenue);
assert.equal(refusesRevenue.fields.length,2,"Não introduz medida ausente do contrato");
const bimestreFixed=E.createChart("b6",{
 title:"Somente 6º bimestre",
 measures:[expense],
 scope:{ano:{mode:"filterable"},bimestre:{mode:"fixed",fixed:6}}
});
assert.deepEqual(E.allowedOptions([bimestreFixed],rows,"ano"),[2022,2025],
 "Não oferece 2026 num gráfico fixado no 6º bimestre ainda não disponível");
const yearAxis=E.createChart("year",{
 measures:[revenue],axes:{x:"ano",y:"valor",z:"medida",header:"nenhum"},
 scope:{ano:{mode:"all"},bimestre:{mode:"all"}}
});
const yearly=E.build(yearAxis,rows);
assert.deepEqual(yearly.options.series[0].data,[22060,25060,26040],
 "Acumulados devem usar último bimestre de cada ano, não a soma dos bimestres");
const horizontal=E.createChart("horizontal",{
 type:"LINE",measures:[revenue],axes:{x:"valor",y:"bimestre",z:"valor",header:"ano"},
 scope:{ano:{mode:"fixed",fixed:2025},bimestre:{mode:"all"}}
});
const h=E.build(horizontal,rows);
assert.equal(h.options.xAxis.type,"value");
assert.equal(h.options.yAxis.type,"category");
assert.deepEqual(h.options.series[0].data[0],[25010,"1º bim."]);
const ranking=E.createChart("rank",{
 type:"RANKING",measures:[revenue],topN:3,
 scope:{ano:{mode:"fixed",fixed:2025},bimestre:{mode:"all"}}
});
const rank=E.build(ranking,rows);
assert.deepEqual(rank.options.series[0].data,[25060,25050,25040]);
const heat=E.createChart("heat",{
 type:"HEATMAP",measures:[revenue],axes:{x:"ano",y:"bimestre",z:"valor",header:"nenhum"},
 scope:{ano:{mode:"all"},bimestre:{mode:"all"}}
});
assert.equal(E.build(heat,rows).options.series[0].data.length,16);
const invalid=E.createChart("error",{axes:{x:"valor",y:"valor",z:"medida",header:"ano"}});
assert.ok(E.validate(invalid).length);
assert.equal(E.normalizedRows([{ano:2025,bimestre:1,[revenue]:null}])[0][revenue],null);
console.log("LAB 8507 OK: eixos, ano/medida fixos, filtros autorizados, acumulados, ranking, mapa de calor.");
