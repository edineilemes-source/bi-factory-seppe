/* Contrato da edição visual 8507 — sem dependências externas. */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const base=path.join(__dirname,"../experiments/echarts-axes-8507");
const ui=fs.readFileSync(path.join(base,"index.html"),"utf8");
const app=fs.readFileSync(path.join(base,"app.js"),"utf8");
const css=fs.readFileSync(path.join(base,"style.css"),"utf8");
const engine=fs.readFileSync(path.join(base,"engine.js"),"utf8");
assert.doesNotMatch(ui,/id="add-kpi"/,"KPI só deve ser escolhido no ECharts");
assert.match(engine,/KPI:"Indicador"/);
assert.match(ui,/id="add-chart"/);
assert.match(ui,/id="add-title"/);
for(const s of ["rectangle","square","diamond","ellipse","arrow","line"])
 assert.ok(ui.includes('id="add-'+s+'"'),"Falta botão para a figura "+s);
assert.match(ui,/id="add-filter-panel"/);
assert.match(ui,/id="visual-undo"/);
assert.match(ui,/id="visual-redo"/);
assert.doesNotMatch(app,/Clique aqui e escreva seu texto/,"Texto deve iniciar vazio");
assert.match(app,/if\(TEXT_TYPES\.has\(type\)\)obj\.text=obj\.text\?\?""/);
assert.match(app,/contentEditable=!previewOnly/);
assert.match(app,/const editable=node\("div",obj\.text\?\?""/);
for(const control of [
 "function startObjectResize(", "function startFreeMove(",
 "function deleteObject(", "function duplicateObject(",
 "function undoVisual(", "function redoVisual(",
 "fontFamily", "Tamanho da fonte", "Cor do texto", "Plano de fundo",
 "Opacidade", "Rotação", "borderColor", "borderWidth", "offsetX", "offsetY"
]){
 assert.ok(app.includes(control),"Falta funcionalidade: "+control);
}
assert.match(app,/event\.key==="Delete"/);
assert.match(app,/newId\(\)/);
assert.match(css,/\.resize-handle/);
assert.match(css,/\.shape-diamond/);
assert.match(css,/\.shape-arrow/);
assert.match(css,/caret-color/);
assert.match(ui,/lab8507-preview-zoom-grafico-20261123-r11/);
console.log("OK 8507: KPI apenas ECharts, texto vazio, figuras, resize, propriedades, apagar, duplicar e histórico.");
