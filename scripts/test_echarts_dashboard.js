/* Smoke test for ECharts options shared by Studio and Visual Editor.
 * Run: node scripts/test_echarts_dashboard.js
 */
const assert=require("node:assert/strict");
const path=require("node:path");
global.window={};
require(path.join(__dirname,"../prototypes/editor-visual/echarts-bi-options.js"));
const charts=window.BIFactoryChartOptions;
assert.ok(charts&&typeof charts.build==="function");
const rows=[
 {ano:2025,bimestre:1,a:100,b:80,c:60},
 {ano:2025,bimestre:2,a:200,b:140,c:100},
 {ano:2025,bimestre:3,a:300,b:230,c:180},
];
const labels=["2025 / 1º","2025 / 2º","2025 / 3º"];
const keys=["a","b","c"],metrics=["Empenhada","Liquidada","Paga"];
const build=spec=>charts.build({spec,rows,keys,metrics,labels});
const grouped=build({type:"BAR"});
assert.equal(grouped.series.length,3);
assert.ok(grouped.series.every(s=>s.type==="bar"&&!s.stack));
assert.deepEqual(grouped.series[0].data,[100,200,300]);
const ranking=build({type:"RANKING",topN:2,showLabels:true});
assert.deepEqual(ranking.yAxis.data,["2025 / 3º","2025 / 2º"]);
assert.deepEqual(ranking.series[0].data,[300,200]);
assert.equal(ranking.series[0].label.show,true);
const points=build({type:"POINTS"});
assert.equal(points.series.length,3);
assert.equal(points.series[0].type,"scatter");
assert.equal(points.xAxis.type,"category");
const scatter=build({type:"SCATTER",scatterX:"a",scatterY:"b"});
assert.equal(scatter.xAxis.type,"value");
assert.equal(scatter.yAxis.type,"value");
assert.deepEqual(scatter.series[0].data[0],[100,80,"2025 / 1º"]);
assert.equal(build({type:"SCATTER",metrics:["Empenhada"]}).series.length,1);
assert.equal(charts.number(null),null);
assert.equal(charts.number(""),null);
console.log("ECharts painel: OK — agrupadas, ranking, pontos, dispersão e valores ausentes");
