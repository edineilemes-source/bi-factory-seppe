/* Regressões do editor de página inteira com cortinas 8507 (sem CDN). */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const base=path.join(__dirname,"../experiments/echarts-axes-8507");
const ui=fs.readFileSync(path.join(base,"index.html"),"utf8");
const app=fs.readFileSync(path.join(base,"app.js"),"utf8");
const css=fs.readFileSync(path.join(base,"style.css"),"utf8");

assert.match(ui,/id="visual-page" class="workspace lab-wide-editor"/);
assert.match(ui,/id="visual-tools-drawer"/);
assert.match(ui,/id="visual-props-drawer"/);
assert.match(ui,/id="toggle-tools-drawer"[^>]+aria-expanded="false"/);
assert.match(ui,/id="toggle-props-drawer"[^>]+aria-expanded="false"/);
for(const id of ["editor-open-echarts","editor-save","editor-fullscreen",
 "visual-undo","visual-redo","visual-preview",
 "editor-toolbar-hide","editor-toolbar-show","editor-status"]){
 assert.ok(ui.includes('id="'+id+'"'),"Controle ausente: "+id);
}
assert.match(app,/function setEditorCurtain\(which,open\)/);
assert.match(app,/function toggleEditorCurtain\(which\)/);
assert.match(app,/function syncVisualWorkspaceMode\(\)/);
assert.match(app,/classList\.toggle\("lab-edit-workspace",currentScreen==="visual"&&!previewOnly\)/);
assert.match(app,/function showScreen\(screen\)\{\s*currentScreen=screen;\s*syncVisualWorkspaceMode\(\);/);
assert.match(app,/function setPanelPreview\(enabled\)\{[\s\S]*?syncVisualWorkspaceMode\(\)/);
assert.match(app,/\$\("toggle-tools-drawer"\)\.onclick=\(\)=>toggleEditorCurtain\("tools"\)/);
assert.match(app,/\$\("toggle-props-drawer"\)\.onclick=\(\)=>toggleEditorCurtain\("props"\)/);
assert.match(app,/\$\("editor-open-echarts"\)\.onclick=\(\)=>\$\("go-charts"\)\.click\(\)/);
assert.match(app,/\$\("editor-save"\)\.onclick=saveLab/);
assert.match(app,/function collapseEditorToolbar\(collapse\)/);
assert.match(app,/\$\("editor-toolbar-show"\)\.hidden=!collapse/);
assert.match(app,/function toggleEditorNativeFullscreen\(\)/);
assert.match(app,/if\(!event\.target\.closest\?\.\("#visual-tools-drawer,#toggle-tools-drawer"\)\)/);
assert.match(app,/if\(!event\.target\.closest\?\.\("#visual-props-drawer,#toggle-props-drawer"\)\)/);
assert.match(css,/body\.lab-edit-workspace #visual-page\.lab-wide-editor\s*\{[\s\S]*?width:100vw;[\s\S]*?height:100dvh;/);
assert.match(css,/body\.lab-edit-workspace #visual-page \.main-area\s*\{[\s\S]*?width:100%;/);
assert.match(css,/body\.lab-edit-workspace #visual-canvas\s*\{[\s\S]*?width:100%;/);
assert.match(css,/body\.lab-edit-workspace #visual-page > \.sidebar\s*\{[\s\S]*?position:fixed;[\s\S]*?pointer-events:none;/);
assert.match(css,/body\.lab-edit-workspace #visual-page > #visual-tools-drawer\.drawer-open,/);
assert.match(css,/body\.lab-edit-workspace #visual-page > #visual-props-drawer\.drawer-open/);
assert.match(css,/body\.lab-panel-preview #visual-page \.editor-canvas-toolbar,/);
assert.match(css,/body\.lab-panel-preview #visual-canvas\s*\{[\s\S]*?width:100%;/);
assert.equal(app.split("Math.max(560,Math.ceil(window.innerHeight||0)").length-1,2,
 "O canvas deve acompanhar a altura da tela, inclusive objetos que passam do rodapé");
assert.doesNotMatch(css,/min-height:100d?vh!important;/,
 "A altura mínima CSS não pode impedir o crescimento vertical do canvas");

assert.match(css,/body\.lab-edit-workspace #visual-page\.toolbar-collapsed \.editor-canvas-toolbar/);
assert.match(css,/body\.lab-edit-workspace #visual-page #editor-toolbar-show/);
assert.match(ui,/lab8507-preview-zoom-grafico-20261123-r11/);
assert.match(app,/lab8507-preview-zoom-grafico-20261123-r11/);
// IMPORTANT: No rewrite of saved x/y or data contracts during transitions.
const show=app.split("function showScreen(screen){")[1].split("function setChartActive(")[0];
const preview=app.split("function setPanelPreview(enabled){")[1].split("function enterPanelPreview()")[0];
assert.ok(!/obj\.x=|obj\.y=|state\.objects=/.test(show+preview),
 "Alternar edição/visualização não deve reescrever posições");
assert.ok(!css.includes("grid-template-columns:260px minmax(460px,1fr) 270px;\n/* r8"),"O editor não pode herdar faixa central estreita");
console.log("OK: editor usa a largura inteira, cortinas sobrepostas, ferramentas recolhíveis, ECharts acessível e prévia preserva as coordenadas.");
