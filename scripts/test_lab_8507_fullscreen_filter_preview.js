/* Contrato de visualização em tela inteira e recolhimento dos filtros.
 * Sem dependências externas; executado pelo instalador antes de reiniciar 8507.
 */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const dir=path.join(__dirname,"../experiments/echarts-axes-8507");
const app=fs.readFileSync(path.join(dir,"app.js"),"utf8");
const html=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const css=fs.readFileSync(path.join(dir,"style.css"),"utf8");
const source=fs.readFileSync(path.join(dir,"engine.js"),"utf8");
assert.match(html,/id="visual-preview"/,"Botão de visualizar deve existir");
assert.match(html,/id="exit-panel-preview"/,"Deve haver saída da tela inteira");
assert.match(html,/aria-label="Fechar visualização do painel/);
assert.match(app,/function enterPanelPreview\(\)/);
assert.match(app,/function exitPanelPreview\(\)/);
assert.match(app,/document\.body\.classList\.toggle\("lab-panel-preview",previewOnly\)/);
assert.match(app,/panel\.requestFullscreen\(\)/);
assert.match(app,/document\.exitFullscreen\(\)/);
assert.match(app,/document\.addEventListener\("fullscreenchange",/);
assert.match(app,/\$\("visual-preview"\)\.onclick=enterPanelPreview;/);
assert.match(app,/\$\("exit-panel-preview"\)\.onclick=exitPanelPreview;/);
assert.match(app,/event\.key==="Escape"&&previewOnly/);
assert.match(css,/\.lab-panel-preview #visual-page\.workspace,/);
assert.match(css,/\.lab-panel-preview #visual-page \.sidebar,/);
assert.match(css,/\.lab-panel-preview #visual-page \.area-title,/);
assert.match(css,/\.lab-panel-preview #visual-canvas\s*\{/);
assert.match(css,/\.lab-panel-preview \.canvas-object \.move-handle,/);
assert.match(css,/#exit-panel-preview/);
assert.match(css,/\.lab-panel-preview #exit-panel-preview\{display:block\}/);
assert.match(app,/function closeFilterMenus\(except=null\)/);
assert.match(app,/function multiSelectControl\(/);
assert.match(app,/active\.length\+" selecionados"/);
assert.doesNotMatch(app,/active\.length\+" selecionados: "\+active\.map/,
  "O filtro recolhido não deve listar os anos selecionados");
assert.match(app,/done=node\("button","Aplicar e fechar","multi-select-done"\)/);
assert.match(app,/finishSelection\(\)/);
assert.match(app,/if\(previewOnly\)closeTimeout=setTimeout\(finishSelection,1600\)/);
assert.match(app,/document\.addEventListener\("pointerdown",event=>\{/);
assert.match(app,/event\.target\.closest\?\.\("\.multi-select"\)/);
assert.match(css,/\.multi-select-actions/);
assert.match(css,/\.multi-select-done/);
assert.match(html,/lab8507-legenda-automatica-z-20261123-r10/);
assert.match(app,/lab8507-legenda-automatica-z-20261123-r10/);
const E=require(path.join(dir,"engine.js"));
const rows=E.normalizedRows([2022,2023,2024,2025,2026].map(ano=>({
 ano,bimestre:1,receita_realizada_acumulada:ano*100
})));
const chart=E.createChart("check",{
 type:"BAR",measures:["receita_realizada_acumulada"],
 scope:{ano:{mode:"filterable"},bimestre:{mode:"all"}}
});
assert.equal(E.allowedRows(chart,rows,{ano:["2022","2024","2025"]}).length,3,
 "Três anos devem continuar filtrados após fechar a lista");
assert.equal(E.allowedRows(chart,rows,{ano:[]}).length,5,
 "Todos significa sem restrição");
console.log("OK: tela inteira, saída/Escape, filtro recolhe e mostra contagem; seleção múltipla preservada.");
