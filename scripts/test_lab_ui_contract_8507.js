/* Contratos estáticos do protótipo 8507: UI e isolamento da aplicação 8506. */
const fs=require("node:fs");
const path=require("node:path");
const assert=require("node:assert/strict");
const dir=path.join(__dirname,"../experiments/echarts-axes-8507");
const html=fs.readFileSync(path.join(dir,"index.html"),"utf8");
const app=fs.readFileSync(path.join(dir,"app.js"),"utf8");
const srv=fs.readFileSync(path.join(__dirname,"serve_echarts_axes_8507.py"),"utf8");
assert.match(html,/id="visual-page"/);
assert.match(html,/id="echarts-page"/);
for(const id of ["axis-x","axis-y","axis-z","axis-header","year-mode","period-mode","measure-choices"]){
 assert.ok(html.includes('id="'+id+'"'),"ECharts sem controle "+id);
}
for(const id of ["fiscal-year","fiscal-bimester"]){
 assert.ok(!html.includes('id="'+id+'"'),"Editor Visual não deve ter dropdown de dados "+id);
}
const visual=html.split('id="visual-page"')[1].split('id="echarts-page"')[0];
assert.ok(!/id="year-fixed"|id="period-fixed"|id="axis-x"/.test(visual));
assert.match(visual,/id="add-filter"/);
assert.match(visual,/id="add-measure-filter"/);
// O filtro do painel recebe o contexto de outros filtros selecionados.
assert.match(app,/E\\.allowedOptions\\(\\s*charts\\(\\)\\s*,\\s*rows\\s*,\\s*dim\\s*,\\s*state\\.filters\\s*\\)/);
assert.match(app,/E\.allowedMeasures\(charts\(\)\)/);
assert.match(srv,/UPSTREAM="http:\/\/127\.0\.0\.1:8505\/api\/fiscal"/);
assert.match(srv,/storage\/labs\/echarts-axes-8507/);
assert.ok(!srv.includes("8506/api"),"8507 jamais chama APIs de escrita da 8506");
console.log("LAB 8507: UI separada e isolamento da 8506 conferidos.");
