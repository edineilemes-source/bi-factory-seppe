/* Garante clique direto no gráfico existente, sem duplicação e sem perda dos atributos.
 * Teste de contrato estático: não depende da biblioteca ECharts no servidor.
 */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const dir=path.join(__dirname,"../experiments/echarts-axes-8507");
const app=fs.readFileSync(path.join(dir,"app.js"),"utf8");
const css=fs.readFileSync(path.join(dir,"style.css"),"utf8");
const html=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const canvas=app.split("function renderCanvas(){")[1].split("function refreshVisualCharts(){")[0];
const entry=app.split("function setChartActive(id){")[1].split("function openChart(id)")[0];
const navigate=app.split("function showScreen(screen){")[1].split("function setChartActive(id){")[0];
const back=app.split('$("back-to-visual").onclick=()=>{')[1].split('for(const id of ["axis-x"',1)[0];
assert.ok(canvas&&entry&&navigate&&back,"Editor do gráfico e retorno devem existir");
const chart=canvas.split('if(obj.type==="chart"&&obj.chart){')[1].split('}else if(TEXT_TYPES.has(obj.type))')[0];
assert.ok(chart,"Eventos devem estar na área interna de um gráfico existente");
assert.match(chart,/inner\.addEventListener\("click",event=>\{\s*event\.stopPropagation\(\);\s*openChart\(obj\.id\);\s*\},true\)/,
 "Clique sobre desenho/canvas chama editor pelo ID do objeto, em captura");
assert.match(chart,/inner\.addEventListener\("pointerdown",event=>event\.stopPropagation\(\)\)/,
 "Mover um gráfico só deve ocorrer pela alça externa");
assert.match(chart,/inner\.addEventListener\("keydown",event=>\{/,
 "O gráfico também pode ser editado pelo teclado");
assert.match(chart,/if\(!previewOnly\)\{/,
 "Na visualização o clique não deve abrir o editor");
assert.match(chart,/inner\.setAttribute\("aria-label","Editar no ECharts: "/);
assert.match(entry,/const obj=object\(id\)/);
assert.match(entry,/if\(!obj\|\|obj\.type!=="chart"\)return/);
assert.match(entry,/state\.selected=id;editing=obj\.chart/,
 "Manter referência exata ao gráfico, sem copiar sua configuração");
assert.match(entry,/showScreen\("echarts"\)/);
assert.doesNotMatch(entry,/createChart\(|addObject\(|structuredClone\(|JSON\.parse\(/,
 "Não criar ou clonar gráfico ao editar");
assert.match(navigate,/fillChartEditor\(editing\);renderPreview\(\)/);
const fill=app.split("function fillChartEditor(spec){")[1].split("function updateScopeVisibility(){")[0];
for(const field of ['chart-type','axis-x','axis-y','axis-z','axis-header','chart-title',
 'year-mode','period-mode','year-fixed','period-fixed','allow-measure-filter',
 'show-values','measure-choices']){
 assert.ok(fill.includes('"'+field+'"'),"ECharts não carrega a propriedade "+field);
}
assert.match(back,/editing=null;showScreen\("visual"\)/);
assert.doesNotMatch(back,/addObject\(|createChart\(|state\.objects\.push\(/,
 "Voltar para o visual não insere outro gráfico");
assert.match(css,/\.chart-edit-target/);
assert.match(html,/lab8507-click-editar-echarts-20261123-r9/);
console.log("OK 8507: clique abre mesmo gráfico no ECharts com campos preenchidos, sem duplicar ou perder posições.");
