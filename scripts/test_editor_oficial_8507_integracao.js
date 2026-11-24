/* Integração oficial 8507: persistência por produto e migração sem apagar
 * layouts originais. Validação de contrato; execução real HTTP no Codespaces.
 */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
const ui=path.join(root,"prototypes/editor-visual/official-8507");
const main=fs.readFileSync(path.join(root,"web/bi_factory/src/main.jsx"),"utf8");
const app=fs.readFileSync(path.join(ui,"app.js"),"utf8");
const html=fs.readFileSync(path.join(ui,"index.html"),"utf8");
const style=fs.readFileSync(path.join(ui,"style.css"),"utf8");
const engine=fs.readFileSync(path.join(ui,"engine.js"),"utf8");
const migrate=fs.readFileSync(path.join(ui,"legacy-migration.js"),"utf8");
const server=fs.readFileSync(path.join(root,"prototypes/editor-visual/server.py"),"utf8");
const api=fs.readFileSync(path.join(root,"scripts/serve_bi_factory_api.py"),"utf8");
const start=fs.readFileSync(path.join(root,"scripts/start_bi_factory_codespaces.sh"),"utf8");
const autostart=fs.readFileSync(path.join(root,"scripts/autostart_bi_factory_codespaces.sh"),"utf8");
const vite=fs.readFileSync(path.join(root,"web/bi_factory/vite.config.js"),"utf8");
assert.match(html,/bi-factory-editor-oficial-8507-r1/);
for(const asset of ["engine.js","app.js","style.css","legacy-migration.js"])
 assert.ok(html.includes("/visual-editor/official-8507/"+asset),"URL oficial do arquivo: "+asset);
assert.match(main,/\/visual-editor\/official-8507\/index\.html\?/);
assert.match(main,/bi-factory:official-save-request/);
assert.match(main,/bi-factory:official-save-result/);
assert.match(main,/visual-8507/);
assert.match(main,/\/api\/products\/.*\/layout/,"Layout anterior deve permanecer consultável");
// A ficha pode ter rótulos e funções de interface customizados no Codespaces.
// O teste valida integração funcional, sem impor textos do botão da versão base.
assert.match(main,/function saveVisualFromEditor\(/);
assert.match(main,/function visualUrl\(mode\)/);
assert.match(main,/visualMode/);
assert.match(main,/folder_id/);
assert.match(main,/technical_owner/);
assert.match(app,/function officialEndpoint\(\)/);
assert.match(html,/id="import-previous-lab"/);
assert.match(app,/async function importPreviousLab\(\)/);
assert.match(app,/requestJSON\("\/api\/visual-8507\/lab-draft"\)/);
assert.match(api,/\/api\/visual-8507\/lab-draft/);
assert.match(server,/LEGACY_LAB_8507 = ROOT/);
assert.match(app,/return OFFICIAL_SCOPE\+encodeURIComponent\(OFFICIAL_PRODUCT_ID\)\+"\/visual-8507"/);
assert.match(app,/return OFFICIAL_PRODUCT_ID\?"bi-factory-seppe-oficial-8507-"\+OFFICIAL_PRODUCT_ID:null/);
assert.match(app,/if\(OFFICIAL_PREVIEW\)\{status\("Visualização somente leitura/);
assert.match(app,/type:"bi-factory:official-save-request"/);
assert.match(app,/async function loadOfficialState\(\)/);
assert.match(app,/window\.BI8507Migrate\.migrateLegacy\(legacy,E\)/);
assert.match(app,/if\(OFFICIAL_PREVIEW\)setPanelPreview\(true\)/);
assert.match(app,/if\(OFFICIAL_PREVIEW\|\|!previewOnly\)return;/);
assert.doesNotMatch(app,/fetch\("\/lab\/draft"/);
assert.doesNotMatch(app,/requestJSON\("\/lab\/draft"/);
assert.match(server,/VISUAL_8507 = ROOT/);
assert.match(server,/parts\[3\] == "visual-8507"/);
assert.match(server,/target = VISUAL_8507 \/ \(identifier \+ "\.json"\)/);
assert.match(server,/if target\.is_file\(\):[\s\S]*?_write_json\(VISUAL_8507 \/ "previous"/);
assert.match(server,/if len\(parts\) == 4 and parts\[3\] == "layout"/,
 "Servidor não deve excluir ou alterar endpoint do GridStack anterior");
assert.match(start,/--port 8506/);
assert.match(start,/\/visual-editor\/official-8507\/index\.html/);
assert.match(start,/\/visual-editor\/official-8507\/index\.html/);
assert.match(autostart,/127\.0\.0\.1:8506\//);
assert.match(vite,/port:8506/);
assert.match(style,/#chart-zoom-overlay/);
assert.match(engine,/const autoLegend=names=>/);
const E=require(path.join(ui,"engine.js"));
const sandbox={};
new Function("window",migrate)(sandbox);
const old={
 schema:"bi-factory-editor-poc-v1",
 objects:{
  texto1:{type:"text",id:"texto1",text:"Painel antigo",size:24},
  imagem1:{type:"image",id:"imagem1",image:"data:image/png;base64,abc"},
  dado1:{type:"dashboard",id:"dado1",title:"Execução",
   chart:{type:"BAR",metrics:["Receita realizada","Despesa paga"],dimensions:["ano"]}}
 },
 layout:[{id:"texto1",x:1,y:2,w:4,h:2},
         {id:"imagem1",x:2,y:4,w:3,h:2},
         {id:"dado1",x:5,y:7,w:6,h:4}],
 filters:{selections:{ano:"2025"}}
};
const unchanged=JSON.stringify(old);
const converted=sandbox.BI8507Migrate.migrateLegacy(old,E);
assert.equal(converted.state.version,1);
assert.equal(converted.state.objects.length,3);
assert.equal(converted.state.objects[0].x,80);
assert.equal(converted.state.objects[0].y,144);
assert.equal(converted.state.objects[0].text,"Painel antigo");
assert.equal(converted.state.objects[1].src,"data:image/png;base64,abc");
assert.equal(converted.state.objects[2].type,"chart");
assert.ok(converted.state.objects[2].chart);
assert.equal(converted.state.objects[2].chart.legacyOriginal.type,"BAR");
assert.deepEqual(converted.state.filters.ano,["2025"]);
assert.equal(JSON.stringify(old),unchanged,"A conversão não pode modificar o layout original");
assert.ok(converted.warnings.length,"Informar gráficos que exigem conferência");
console.log("OK: cadastro e ficha mantidos; editor oficial 8507; cache por produto; legado preservado; 8507 incorporado na porta 8506.");
