/* Regression: moving a previous object remains possible after selecting another.
 * Tested on source since browser interaction must be confirmed in Codespaces.
 */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const dir=path.join(__dirname,"../experiments/echarts-axes-8507");
const app=fs.readFileSync(path.join(dir,"app.js"),"utf8");
const css=fs.readFileSync(path.join(dir,"style.css"),"utf8");
const html=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const canvas=app.split("function renderCanvas(){")[1].split("function refreshVisualCharts(")[0];
assert.ok(canvas,"renderCanvas precisa existir");
assert.ok(canvas.includes("for(const obj of state.objects)"),"Cada objeto deve ser renderizado");
const handles=canvas.match(/const moveHandle=node\("button","⠿","move-handle"\)/g)||[];
assert.equal(handles.length,1,"Alça de mover deve ser criada uma vez por objeto");
assert.match(canvas,/if\(!previewOnly\)\s*\{\s*const moveHandle=/,
  "Alça de movimentação deve ser montada para qualquer objeto em edição");
assert.doesNotMatch(canvas,/if\(!previewOnly&&state\.selected===obj\.id\)\s*\{\s*const moveHandle=/,
  "Selecionar outro objeto não pode remover a alça anterior");
const movePos=canvas.indexOf("block.append(moveHandle)");
const resizePos=canvas.indexOf("if(state.selected===obj.id)",movePos);
assert.ok(movePos>=0&&resizePos>movePos,
 "A alça de mover deve ficar fora da condição que exibe a alça de redimensionar");
assert.match(canvas,/moveHandle\.addEventListener\("pointerdown",event=>startFreeMove\(event,obj,block,true\)\)/);
assert.match(app,/state\.selected=obj\.id;[\s\S]*?classList\.remove\("active"\)/,
 "Ao mover antigo objeto deve ser possível torná-lo ativo");
assert.match(canvas,/if\(!previewOnly\)/,
 "No modo visualização as alças devem ficar ocultas");
assert.match(css,/\.canvas-object \.move-handle\s*\{\s*display:grid;\s*visibility:visible;/);
assert.doesNotMatch(canvas,/const header=node\("div",undefined,"object-header"\)/,
 "Nenhuma barra superior pode voltar a ocupar o objeto");
assert.match(html,/id="visual-canvas"/);
console.log("OK: alça de mover presente em texto/título/imagem/gráfico mesmo após selecionar outro; sem faixa interna.");
