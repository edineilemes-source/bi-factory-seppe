import React,{useEffect,useState} from "react";
import{createRoot}from"react-dom/client";
import{FolderKanban,Database,BookOpen,Network,PanelsTopLeft,Send,Folder,FileBarChart,ExternalLink,RefreshCw}from"lucide-react";
import "./style.css";
import ProductEditor from "./ProductEditor";
import FreeCanvasExperiment from "./FreeCanvasExperiment";
const sections=[["Conhecimento",BookOpen],["Entrada de dados",Database],["Modelagem",Network],["Produtos",PanelsTopLeft],["Publicações",Send]];
function App(){
const [section,setSection]=useState("Projetos"),[data,setData]=useState(null),[error,setError]=useState("");
const [creation,setCreation]=useState(""),[draft,setDraft]=useState({}),[notice,setNotice]=useState("");
const [editing,setEditing]=useState(null),[preview,setPreview]=useState(null),[productEditor,setProductEditor]=useState(null),[universalProduct,setUniversalProduct]=useState(null),[productReadOnly,setProductReadOnly]=useState(false);
function editChart(item){setEditing(item);setNotice("")}
useEffect(()=>{
 if(!editing)return;
 const listener=event=>{
   if(event.origin!==window.location.origin||event.source!==document.getElementById("studioFrame")?.contentWindow)return;
   if(event.data?.type==="bi-factory:studio-ready"){
     event.source.postMessage({type:"bi-factory:load-component",component:editing},event.origin);
   }
   if(event.data?.type==="bi-factory:save-component"){
     const components=event.data.components;
     if(!Array.isArray(components)){setNotice("Erro: dados inválidos");return}
     fetch("/api/create/update-component",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:editing.id,content:{studio_items:components}})})
       .then(async response=>{const result=await response.json();if(!response.ok)throw Error(result.error||"Falha ao salvar");return fetch("/api/overview")})
       .then(async response=>{if(!response.ok)throw Error("Falha ao atualizar catálogo");return response.json()})
       .then(next=>{setData(next);setEditing(null);setNotice("Componente salvo com sucesso. Editor fechado; publicações preservadas.")})
       .catch(error=>setNotice("Erro: "+error.message));
   }
 };
 window.addEventListener("message",listener);
 return ()=>window.removeEventListener("message",listener);
},[editing]);
useEffect(()=>{
 if(!preview)return;
 const listener=event=>{
  if(event.origin!==window.location.origin||event.source!==document.getElementById("previewFrame")?.contentWindow||event.data?.type!=="bi-factory:studio-ready")return;
  event.source.postMessage({type:"bi-factory:preview",items:preview.items},event.origin);
 };
 window.addEventListener("message",listener);
 return ()=>window.removeEventListener("message",listener);
},[preview]);
function previewComponent(item){
 const items=item.content?.studio_items;
 setPreview({title:item.name,items:Array.isArray(items)?items:[],description:Array.isArray(items)&&items.length?"":"Este componente ainda não possui visualização salva."});
}
function previewProduct(product){
 const refs=components[product.id]||[];
 const own=data?.product_canvases?.[product.id];
 if(Array.isArray(own)&&own.length){setPreview({title:product.name,items:own,description:""});return}
 const items=refs.flatMap(ref=>{
  const library=(data?.shared_components||[]).find(x=>x.id===ref.library_component_id);
  return Array.isArray(library?.content?.studio_items)?library.content.studio_items:[];
 });
 setPreview({title:product.name,items,description:items.length?"":"Este produto ainda não possui componentes gráficos reutilizáveis com visualização salva. Os demais componentes continuam listados na ficha."});
}
useEffect(()=>{
 if(!productEditor)return;
 const listener=event=>{
  if(event.origin!==window.location.origin||event.source!==document.getElementById("productStudioFrame")?.contentWindow)return;
  if(event.data?.type==="bi-factory:studio-ready"){
   event.source.postMessage({type:"bi-factory:load-product",items:data?.product_canvases?.[productEditor.id]||[]},event.origin);
  }
  if(event.data?.type==="bi-factory:save-product"){
   apiPost("save-canvas",{product_id:productEditor.id,items:event.data.components})
    .then(()=>refreshCatalog()).then(()=>{setProductEditor(null);setNotice("Produto salvo como rascunho. Editor fechado.")})
    .catch(error=>setNotice("Erro ao salvar produto: "+error.message));
  }
 };
 window.addEventListener("message",listener);
 return ()=>window.removeEventListener("message",listener);
},[productEditor,data]);
async function apiPost(operation,payload){
 const response=await fetch("/api/create/"+operation,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
 const result=await response.json();
 if(!response.ok)throw Error(result.error||"Falha ao salvar");
 return result.item;
}
async function refreshCatalog(){
 const response=await fetch("/api/overview");
 if(!response.ok)throw Error("Falha ao atualizar catálogo");
 setData(await response.json());
}
async function attachToProduct(productId,componentId){
 try{
  await apiPost("attach",{product_id:productId,component_id:componentId});
  await refreshCatalog();
  setOpenProducts(old=>[...new Set([...old,productId])]);
  setNotice("Componente da biblioteca vinculado ao produto com sucesso.");
 }catch(error){setNotice("Erro ao vincular componente: "+error.message)}
}
async function save(){
 try{
  const payload={...draft};
  delete payload.component_id;
  delete payload.component_type;
  const created=await apiPost(creation,payload);
  if(false&&creation==="product"&&draft.component_id){
   try{await apiPost("attach",{product_id:created.id,component_id:draft.component_id})}
   catch(error){setNotice("Produto criado, mas o vínculo falhou: "+error.message);await refreshCatalog();setCreation("");return}
  }
  await refreshCatalog();
  if(creation==="component"&&created.type==="Gráfico")setEditing(created);
  if(creation==="product"){setOpenProducts(old=>[...new Set([...old,created.id])]);setProductReadOnly(false);setUniversalProduct(created)}
  setCreation("");setDraft({});
  setNotice("Cadastro salvo com sucesso.");
 }catch(error){setNotice("Erro: "+error.message)}
}
const [openProducts,setOpenProducts]=useState([]),[expanded,setExpanded]=useState([]),[folderId,setFolderId]=useState("__all__"),[search,setSearch]=useState(""),[fiscal,setFiscal]=useState(null);
useEffect(()=>{fetch("/api/overview").then(async r=>{if(!r.ok)throw Error("API HTTP "+r.status);return r.json()}).then(setData).catch(e=>setError(e.message))},[]);
useEffect(()=>{if(section==="Entrada de dados"&&!fiscal)fetch("/api/fiscal-preview").then(r=>r.json()).then(setFiscal).catch(e=>setError(e.message))},[section,fiscal]);
const project=data?.project;
const [activeProject,setActiveProject]=useState("pmcg-financas-publicas");
const folders=data?.folders||[];const products=data?.products||[];const components=data?.components_by_product||{};
const descendants=new Set();function collect(id){if(descendants.has(id))return;descendants.add(id);folders.filter(f=>f.parent_id===id).forEach(f=>collect(f.id))}if(folderId!=="__all__")collect(folderId);
const visible=products.filter(p=>(folderId==="__all__"?true:folderId==="__none__"?!p.folder_id:descendants.has(p.folder_id))&&[p.name,p.code,p.type].join(" ").toLowerCase().includes(search.toLowerCase()));
const folderPath=id=>{if(!id)return "Sem pasta";const names=[],seen=new Set();while(id&&!seen.has(id)){seen.add(id);const f=folders.find(x=>x.id===id);if(!f)break;names.unshift(f.name);id=f.parent_id}return names.join(" / ")||"Sem pasta"};
const fmt=n=>typeof n==="number"?new Intl.NumberFormat("pt-BR",{style:"currency",currency:"BRL",maximumFractionDigits:0}).format(n):"—";
return <>{universalProduct&&<FreeCanvasExperiment key={universalProduct.id} product={universalProduct} readOnly={productReadOnly} initialCanvas={data?.free_canvases?.[universalProduct.id]} onClose={()=>setUniversalProduct(null)} onSave={async payload=>{await apiPost("save-free-canvas",{product_id:universalProduct.id,...payload});await refreshCatalog();}}/>} {productEditor&&<ProductEditor key={productEditor.id} product={productEditor} readOnly={Boolean(productEditor.__preview)} initialItems={data?.product_canvases?.[productEditor.id]||[]} onClose={()=>setProductEditor(null)} onSave={async items=>{await apiPost("save-canvas",{product_id:productEditor.id,items});await refreshCatalog();setProductEditor(null);setNotice("Produto salvo com sucesso. Editor fechado.")}}/>}<div className="shell"><aside><div className="brand">SEPPE<span>.</span></div><div className="brandSub">BI Factory · Plataforma de Inteligência</div><div className="group">HOME</div><nav><button className={section==="Projetos"?"active":""} onClick={()=>setSection("Projetos")}><FolderKanban size={18}/>Projetos</button></nav><div className="group">PROJETO ATIVO</div><div className="projectPicker"><FolderKanban size={16}/> {project?.name||"PMCG — Finanças Públicas"}</div><div className="group modulesTitle">MÓDULOS DO PROJETO</div><nav>{sections.map(([name,Icon])=><button key={name} className={section===name?"active":""} onClick={()=>setSection(name)}><Icon size={18}/>{name}</button>)}</nav><div className="asideFoot">Nova interface experimental<br/>8502 permanece intacta</div></aside><main><header><div><div className="eyebrow">BI FACTORY / {section.toUpperCase()}</div><h1>{section}</h1></div><div className="tag">Projeto piloto</div></header>{error&&<div className="error">Não foi possível conectar à API Python: {error}. Inicie a porta 8505.</div>}
{section==="Projetos"?<><div className="card hero"><div className="eyebrow">PROJETO 001</div><h2>{project?.name||"PMCG — Finanças Públicas"}</h2><p>Execução orçamentária municipal · série histórica 2022–2026</p><div className="actions"><button onClick={()=>setSection("Entrada de dados")}><Database size={16}/> Ver fontes</button><button onClick={()=>setSection("Produtos")}><PanelsTopLeft size={16}/> Abrir produtos</button></div></div><div className="metrics"><div className="card"><span>Exercícios identificados</span><strong>{data?.fiscal?.years?.filter(y=>y.files>0).length??"—"} / 5</strong></div><div className="card"><span>Produtos cadastrados</span><strong>{data?.products?.length??"—"}</strong></div><div className="card"><span>Pastas cadastradas</span><strong>{data?.folders?.length??"—"}</strong></div></div></>:
section==="Entrada de dados"?<div className="card"><h2>Fontes fiscais disponíveis</h2><p>Inventário local da STN/SICONFI. Ausência de arquivos não significa ausência de publicação na STN.</p><table><thead><tr><th>Exercício</th><th>Arquivos RREO</th><th>Situação local</th></tr></thead><tbody>{(data?.fiscal?.years||[]).map(y=><tr key={y.year}><td>{y.year}</td><td>{y.files}</td><td>{y.files?"Disponível para análise":"Importação pendente"}</td></tr>)}</tbody></table><h2>Prévia de execução orçamentária</h2><p>Dados acumulados por bimestre; não somar bimestres. A prévia mostra apenas os exercícios normalizados disponíveis.</p>{fiscal?.rows?.length?<div className="table-scroll"><table><thead><tr><th>Ano</th><th>Bimestre</th><th>Empenhado</th><th>Liquidado</th><th>Pago</th></tr></thead><tbody>{fiscal.rows.map((row,i)=><tr key={i}><td>{row.ano}</td><td>{row.bimestre}</td><td>{fmt(row.despesa_empenhada_acumulada)}</td><td>{fmt(row.despesa_liquidada_acumulada)}</td><td>{fmt(row.despesa_paga_acumulada)}</td></tr>)}</tbody></table></div>:<p>Não há relatório normalizado disponível.</p>}</div>:
section==="Produtos"?<><div className="card" style={{marginBottom:16}}><h2>Gerenciar catálogo</h2><div className="actions"><button onClick={()=>{setCreation("product");setDraft({folder_id:folderId==="__all__"||folderId==="__none__"?null:folderId,type:"Painel"});setNotice("")}}>Novo produto</button></div>{creation&&<div className="catalogForm"><h3>{creation==="folder"?"Cadastro de pasta":creation==="product"?"Novo produto":"Componente reutilizável"}</h3><label>Nome<input value={draft.name||""} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>{creation==="folder"&&<label>Pasta pai<select value={draft.parent_id||""} onChange={e=>setDraft({...draft,parent_id:e.target.value||null})}><option value="">Raiz</option>{folders.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>}{creation==="product"&&<><label>Tipo<select value={draft.type||"Painel"} onChange={e=>setDraft({...draft,type:e.target.value})}>{["Painel","Relatório","PDF","Site","Portal","Outro"].map(t=><option key={t}>{t}</option>)}</select></label><label>Pasta<select value={draft.folder_id||""} onChange={e=>setDraft({...draft,folder_id:e.target.value||null})}><option value="">Sem pasta</option>{folders.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label><p className="hint">Código do produto gerado automaticamente.</p><label>Descrição<textarea value={draft.description||""} onChange={e=>setDraft({...draft,description:e.target.value})}/></label></>}{creation==="component"&&<label>Tipo<select value={draft.type||"Gráfico"} onChange={e=>setDraft({...draft,type:e.target.value})}>{["Gráfico","Tabela","Texto","Imagem","Indicador","Mapa","Outro"].map(t=><option key={t}>{t}</option>)}</select></label>}<div className="actions"><button onClick={save}>{creation==="product"?"Abrir editor de produto":"Salvar"}</button><button onClick={()=>setCreation("")}>Cancelar</button></div></div>}{notice&&<p>{notice}</p>}<p className="hint">Os objetos são criados e editados dentro do produto. Os painéis publicados não são alterados.</p></div><div className="columns"><div className="card"><h2><Folder size={19}/> Pastas</h2><button className={folderId==="__all__"?"folder selected":"folder"} onClick={()=>setFolderId("__all__")}><Folder size={16}/> Todos os produtos</button><button className={folderId==="__none__"?"folder selected":"folder"} onClick={()=>setFolderId("__none__")}><Folder size={16}/> Sem pasta</button>{(()=>{const byParent=new Map();folders.forEach(f=>{const parent=folders.some(p=>p.id===f.parent_id)?f.parent_id:null;byParent.set(parent,[...(byParent.get(parent)||[]),f])});const render=(parent,depth=0,seen=new Set())=>(byParent.get(parent)||[]).map(f=>{if(seen.has(f.id))return null;const children=byParent.get(f.id)||[];const open=expanded.includes(f.id);return <React.Fragment key={f.id}><div className="treeRow" style={{paddingLeft:10+depth*20}}>{children.length?<button className="treeToggle" onClick={()=>setExpanded(old=>open?old.filter(id=>id!==f.id):[...old,f.id])}>{open?"▾":"▸"}</button>:<span className="treeToggle"/>}<button className={folderId===f.id?"folder selected":"folder"} onClick={()=>{setFolderId(f.id);setExpanded(old=>[...new Set([...old,f.id])])}}><Folder size={16}/>{f.name}</button></div>{open&&render(f.id,depth+1,new Set([...seen,f.id]))}</React.Fragment>});return render(null)})()}</div><div className="card"><h2><FileBarChart size={19}/> Produtos</h2><input className="search" placeholder="Pesquisar objetos e produtos..." value={search} onChange={e=>setSearch(e.target.value)}/><p>{visible.length} produto(s) nesta seleção</p>{visible.length?(visible.map(p=><div className="productPanel" key={p.id}><button className="productHeading" onClick={()=>previewProduct(p)}><span><b>{p.name}</b><small>{p.type} · {p.code||"Sem código"} · {folderPath(p.folder_id)}</small></span><span className="productStatus">{p.status||"Cadastrado"}</span></button><button onClick={()=>{setProductReadOnly(false);setUniversalProduct(p);setPreview(null)}}>Editar produto</button><button onClick={()=>{setProductReadOnly(true);setUniversalProduct(p);setPreview(null)}}>Visualizar produto</button><button disabled={p.id==="legacy-published"||!products.some(x=>x.id===p.id&&x.code!=="SEM CADASTRO")} onClick={async()=>{if(!window.confirm(`Apagar definitivamente o produto "${p.name}"? Esta ação não pode ser desfeita.`))return;try{await apiPost("delete-product",{product_id:p.id,confirm:p.id});await refreshCatalog();setNotice(`Produto "${p.name}" apagado.`)}catch(error){setNotice("Erro ao apagar produto: "+error.message)}}}>Apagar produto</button></div>)):<p>Nenhum produto cadastrado no catálogo local.</p>}{preview&&<div className="catalogForm"><div className="studioHeader"><h3>Pré-visualização — {preview.title}</h3><button onClick={()=>setPreview(null)}>Fechar prévia</button></div>{preview.description&&<p>{preview.description}</p>}{preview.items.length>0&&<iframe key={preview.title} id="previewFrame" title={"Prévia de "+preview.title} src="/studio-component.html?preview=1" style={{width:"100%",height:760,border:"1px solid #dce6f0",borderRadius:10}}/>}</div>}{editing&&<div className="catalogForm"><div className="studioHeader"><h3>Estúdio Visual — {editing.name}</h3><button onClick={()=>setEditing(null)}>Fechar editor</button></div><p>Editor original ECharts da 8502, adaptado para componentes. As alterações são salvas como rascunho.</p><iframe key={editing.id} id="studioFrame" title="Estúdio Visual de componentes" src="/studio-component.html" style={{width:"100%",height:1050,border:"1px solid #dce6f0",borderRadius:10}}/></div>}</div></div></>:
section==="Publicações"?<div className="card"><h2>Sala de Situação</h2><p>Os produtos publicados continuam disponíveis na porta 8503. Esta interface não modifica publicações existentes.</p><a href={window.location.protocol+"//"+window.location.host.replace("-8504.","-8503.")} target="_blank" rel="noreferrer">Abrir Sala de Situação <ExternalLink size={15}/></a></div>:
<div className="card"><h2>{section}</h2><p>Módulo previsto na arquitetura. A implantação completa será realizada após a entrega dos painéis financeiros.</p><p className="hint">O cadastro do projeto, as fontes fiscais e o catálogo de objetos são as prioridades da versão inicial.</p></div>}
<footer>BI Factory SEPPE · React + Python · Ambiente de migração</footer></main></div></>}
createRoot(document.getElementById("root")).render(<App/>);
