/* 8507: Visualizar > clicar no gráfico > abrir em tela inteira > voltar ao painel.
 * Teste isolado de contrato e execução das funções, sem tocar no rascunho real.
 */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const base=path.join(__dirname,"../experiments/echarts-axes-8507");
const app=fs.readFileSync(path.join(base,"app.js"),"utf8");
const html=fs.readFileSync(path.join(base,"index.html"),"utf8");
const css=fs.readFileSync(path.join(base,"style.css"),"utf8");
const engine=require(path.join(base,"engine.js"));

assert.match(html,/id="chart-zoom-overlay"/);
assert.match(html,/role="dialog"/);
assert.match(html,/aria-modal="true"/);
assert.match(html,/id="chart-zoom-title"/);
assert.match(html,/id="chart-zoom-host"/);
assert.match(html,/id="close-chart-zoom"/);
assert.match(html,/lab8507-preview-zoom-grafico-20261123-r11/);
assert.match(app,/lab8507-preview-zoom-grafico-20261123-r11/);
assert.match(app,/inner\.classList\.add\("chart-zoom-target"\)/);
assert.match(app,/if\(!previewOnly\)\{[\s\S]*?openChart\(obj\.id\);[\s\S]*?\}else\{[\s\S]*?openExpandedChart\(obj\.id\)/);
assert.match(app,/inner\.addEventListener\("click",event=>\{\s*event\.stopPropagation\(\);\s*openExpandedChart\(obj\.id\);\s*\},true\)/);
assert.match(app,/\$\("close-chart-zoom"\)\.onclick=closeExpandedChart/);
assert.match(app,/if\(event\.key==="Escape"&&!\$\("chart-zoom-overlay"\)\.hidden\)/);
assert.match(app,/if\(!enabled\)closeExpandedChart\(\)/);
assert.match(app,/inner\.style\.height="100%"/);
assert.match(css,/#chart-zoom-overlay\[hidden\]\{display:none!important\}/);
assert.match(css,/#visual-page #chart-zoom-overlay\s*\{[\s\S]*?position:fixed;[\s\S]*?inset:0;[\s\S]*?height:100dvh;/);
assert.match(css,/#visual-page \.chart-zoom-host\s*\{[\s\S]*?flex:1 1 auto;/);
assert.match(css,/#visual-page \.chart-zoom-host \.chart-host\s*\{[\s\S]*?height:100%!important;/);
assert.match(css,/body\.lab-panel-preview \.canvas-object \.chart-zoom-target\s*\{[\s\S]*?cursor:zoom-in/);
assert.doesNotMatch(app,/previewOnly\)openChart\(/,"Preview must not open editor");

const first=app.indexOf("function closeExpandedChart(){");
const last=app.indexOf("function setPanelPreview(enabled){",first);
assert.ok(first>=0&&last>first,"Lifecycle of zoom must exist");
const fragment=app.slice(first,last);
assert.doesNotMatch(fragment,/addObject\(|newId\(|state\.objects\.push\(|state\.objects\.splice\(/,
 "Ampliar não pode criar, substituir ou apagar objetos do painel");

const filters={ano:["2022","2024","2025"],bimestre:[],medida:[]};
const graph=engine.createChart("existing-graph",{
 title:"Receita e despesa",
 type:"BAR",
 measures:["receita_realizada_acumulada","despesa_paga_acumulada"],
 scope:{ano:{mode:"filterable"},bimestre:{mode:"all"}}
});
const original={id:"object-4",type:"chart",chart:graph,x:350,y:80,pixelWidth:340,pixelHeight:250};
const snapshot=JSON.stringify(original);
const state={objects:[original],filters,selected:"object-4"};
let closedInstance=0;
let focusedRestore=0;
let focusClose=0;
const inner={style:{},isConnected:true};
const bigHost={
 dataset:{},clientHeight:620,
 querySelector(selector){return selector===".chart-host"?inner:null},
 replaceChildren(){this.cleaned=true}
};
const overlay={hidden:true};
const title={textContent:""};
const closeButton={focus(){focusClose++}};
const ui={
 "chart-zoom-overlay":overlay,"chart-zoom-host":bigHost,
 "chart-zoom-title":title,"close-chart-zoom":closeButton
};
const classes=new Set();
const document={
 activeElement:{isConnected:true,focus(){focusedRestore++}},
 body:{classList:{add:v=>classes.add(v),remove:v=>classes.delete(v)}}
};
const instances=new Map();
let rendered=null;
let cleared=0;
function renderChartIn(host,chart,filterState,selectedMeasure){
 rendered={host,chart,filterState,selectedMeasure};
 instances.set(inner,{dispose(){closedInstance++},resize(){}});
}
const factory=new Function("$","object","document","state","renderChartIn","closeFilterMenus",
 "requestAnimationFrame","instances","inner","graph",`
 let previewOnly=true,currentScreen="visual",expandedChartId=null,zoomFocusOrigin=null;
 ${fragment}
 return {openExpandedChart,closeExpandedChart,
         getId:()=>expandedChartId,setPreview:v=>previewOnly=v};
`);
const modal=factory(id=>ui[id],id=>state.objects.find(o=>o.id===id),document,state,
 renderChartIn,()=>cleared++,callback=>callback(),instances,inner,graph);
modal.openExpandedChart(original.id);
assert.equal(overlay.hidden,false);
assert.equal(modal.getId(),original.id);
assert.equal(title.textContent,"Receita e despesa");
assert.equal(rendered.chart,graph,"Must render the exact pre-existing ECharts specification");
assert.equal(rendered.filterState,filters,"Must keep panel filters");
assert.deepEqual(rendered.selectedMeasure,[]);
assert.equal(focusClose,1);
assert.equal(cleared,1);
assert.ok(classes.has("lab-chart-expanded"));
assert.equal(JSON.stringify(original),snapshot,"Zoom must not change object positions or settings");
modal.closeExpandedChart();
assert.equal(overlay.hidden,true);
assert.equal(modal.getId(),null);
assert.equal(closedInstance,1,"Must dispose only fullscreen chart instance");
assert.equal(instances.size,0);
assert.equal(focusedRestore,1);
assert.equal(JSON.stringify(original),snapshot);
modal.setPreview(false);
modal.openExpandedChart(original.id);
assert.equal(overlay.hidden,true,"Edit mode must not open chart zoom");
console.log("OK 8507: clique em Visualizar amplia gráfico filtrado em tela inteira, fecha com segurança e preserva painel.");
