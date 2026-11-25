import React,{useEffect,useState} from "react";
import KnowledgeLibrary from "./KnowledgeLibrary.jsx";

/* Módulo independente: pode ser agregado à tela Conhecimento existente
 * sem substituir campos personalizados nem o cadastro de projetos.
 */
const CATEGORIES=[
 ["legislacao","Leis e decretos"],
 ["normas","Normas e resoluções"],
 ["manuais","Manuais oficiais"],
 ["sites_oficiais","Portais oficiais"],
 ["metodos","Referências técnicas"]
];
const TOPICS=["Receita","Despesa","Empenho","Liquidação","Pagamento",
 "Balanço","Prestação de contas","RREO","RGF","DCA","PCASP","CAPAG","Poupança corrente"];
async function knowledgeApi(url,data){
 const r=await fetch(url,{method:data?"POST":"GET",
  headers:data?{"Content-Type":"application/json"}:undefined,
  body:data?JSON.stringify(data):undefined,cache:"no-store"});
 const value=await r.json().catch(()=>({}));
 if(!r.ok)throw Error(value.error||"Erro HTTP "+r.status);
 return value;
}
export default function OfficialKnowledgeSearch({project}){
 const id=project?.id;
 const endpoint="/api/projects/"+encodeURIComponent(id||"");
 const [topic,setTopic]=useState(project?.theme||"");
 const [scope,setScope]=useState(project?.scope||"Brasil");
 const [types,setTypes]=useState(["legislacao","normas","manuais","sites_oficiais"]);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const [result,setResult]=useState(null);
 const [selected,setSelected]=useState([]);
 const [previous,setPrevious]=useState([]);
 const [libraryVersion,setLibraryVersion]=useState(0);
 useEffect(()=>{
  setTopic(project?.theme||"");
  setScope(project?.scope||"Brasil");
  setResult(null);setSelected([]);setPrevious([]);
 },[id]);
 useEffect(()=>{
  if(!id)return;
  let live=true;
  knowledgeApi(endpoint+"/knowledge").then(data=>{
   if(live){
    setPrevious((data.items||[]).filter(x=>x.type==="research_result").reverse().slice(0,12));

   }
  }).catch(()=>{});
  return()=>{live=false};
 },[endpoint,id]);
 const action=async callback=>{
  setBusy(true);setError("");setNotice("");
  try{
   await callback();
   const all=await knowledgeApi(endpoint+"/knowledge");
   setPrevious((all.items||[]).filter(x=>x.type==="research_result").reverse().slice(0,12));

  }catch(e){setError(e.message)}
  finally{setBusy(false)}
 };
 if(!id)return null;
 return <section className="card" style={{padding:20,marginBottom:16,display:"grid",gap:12}}>
  <div className="eyebrow">BASE DE CONHECIMENTO · PESQUISA OFICIAL</div>
  <h2 style={{margin:0}}>Pesquisar legislação, manuais e PDFs oficiais</h2>
  <p className="hint">Pesquisa nas fontes nacionais cadastradas (Tesouro Nacional, Siconfi e Planalto).
   A lista mostra a origem antes de incorporar. Nenhum documento é baixado sem sua aprovação. Depois, confira, descarte ou mande ler os PDFs na Biblioteca.</p>
  {error&&<p role="alert" style={{color:"#a32a2a"}}>{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <div className="catalogForm" style={{display:"grid",gap:10}}>
   <label>Tema ou assunto
    <input value={topic} onChange={e=>setTopic(e.target.value)}
     placeholder="Ex.: liquidação da despesa, balanço ou prestação de contas" />
   </label>
   <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
    {TOPICS.map(text=><button type="button" key={text}
     disabled={busy} onClick={()=>setTopic(text)}
     style={{fontSize:12,padding:"6px 10px"}}>{text}</button>)}
   </div>
   <label>Abrangência
    <input value={scope} onChange={e=>setScope(e.target.value)}
     placeholder="Brasil · STN, Siconfi, Campo Grande, MS"/>
   </label>
   <fieldset style={{padding:10,border:"1px solid #dce5ef",borderRadius:8}}>
    <legend>Tipos de documento</legend>
    <div style={{display:"flex",flexWrap:"wrap",gap:14}}>
     {CATEGORIES.map(([key,label])=><label key={key} style={{display:"flex",alignItems:"center",gap:6}}>
      <input type="checkbox" checked={types.includes(key)}
       onChange={e=>setTypes(old=>e.target.checked?[...old,key]:old.filter(x=>x!==key))}/>{label}
     </label>)}
    </div>
   </fieldset>
   <div className="actions">
    <button disabled={busy||topic.trim().length<3||!types.length}
     onClick={()=>action(async()=>{
      const data=await knowledgeApi(endpoint+"/discover",{
       project_id:id,topic:topic.trim(),categories:types,scope
      });
      setResult(data);setSelected([]);
      setNotice("Pesquisa concluída: "+data.sources.length+
       " referências apresentadas. Confira os links e escolha o que incorporar.");
     })}>{busy?"Processando…":"Pesquisar fontes oficiais"}</button>
   </div>
  </div>
  {previous.length>0&&<details>
   <summary>Pesquisas anteriores deste projeto ({previous.length})</summary>
   <div style={{display:"grid",gap:6,padding:10}}>
    {previous.map(row=><button key={row.id} type="button" disabled={busy}
     style={{textAlign:"left"}} onClick={()=>action(async()=>{
      const data=await knowledgeApi(endpoint+"/discovery/"+encodeURIComponent(row.id));
      setResult(data);setSelected([]);setNotice("Pesquisa anterior recuperada.");
     })}>{row.topic} · {row.created_at?.slice(0,10)} · {row.count||0} referências</button>)}
   </div>
  </details>}
  {result&&<>
   <h3 style={{margin:"8px 0 0"}}>Resultados encontrados ({result.sources.length})</h3>
   <p className="hint">{result.provider} · {result.ai_status} · {result.scope_note}</p>
   {!!result.warnings?.length&&<details><summary>Fontes indisponíveis ({result.warnings.length})</summary>
    <ul>{result.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul>
   </details>}
   <div className="actions">
    <button type="button" disabled={busy} onClick={()=>
     setSelected(result.sources.filter(s=>s.downloadable).slice(0,10).map(s=>s.id))}>
     Selecionar PDFs</button>
    <button type="button" disabled={busy} onClick={()=>setSelected([])}>Limpar</button>
    <button disabled={busy||!selected.length} onClick={()=>action(async()=>{
     const response=await knowledgeApi(endpoint+"/approve",{
      project_id:id,discovery_id:result.id,source_ids:selected
     });
     setSelected([]);
     setLibraryVersion(n=>n+1);
     setNotice(response.imported.length+" documentos/referências incorporados. Confira-os na Biblioteca abaixo."+
      (response.failed.length?" Falhas: "+
       response.failed.map(x=>x.title+": "+x.error).join("; "):""));
    })}>Aprovar e incorporar ({selected.length})</button>
   </div>
   <div style={{display:"grid",gap:8}}>
    {result.sources.length===0?<p>Não houve resultados nessas fontes. Experimente outra expressão.</p>:
     result.sources.map(s=><label key={s.id}
      style={{display:"grid",gridTemplateColumns:"auto 1fr",gap:10,
       padding:12,borderRadius:8,border:"1px solid #dce5ef",alignItems:"start"}}>
      <input type="checkbox" disabled={busy} checked={selected.includes(s.id)}
       onChange={e=>setSelected(old=>e.target.checked?
        old.length>=10?old:[...old,s.id]:old.filter(i=>i!==s.id))}/>
      <div style={{minWidth:0}}>
       <a href={s.url} target="_blank" rel="noopener noreferrer" style={{fontWeight:700}}>
        {s.title}</a>
       <div className="hint">{s.source} · {s.category} ·
        {s.downloadable?" PDF (após aprovação)":" página oficial (referência)"} ·
        {s.validity_note||"Vigência: verificar no documento"}</div>
       {s.origin!==s.url&&<div className="hint">Localizado em: <a href={s.origin}
        target="_blank" rel="noopener noreferrer">página do órgão</a></div>}
      </div>
     </label>)}
   </div>
  </>}
  <KnowledgeLibrary project={project} revision={libraryVersion}/>
 </section>;
}
