import React,{useEffect,useState} from "react";
import KnowledgeLibrary from "./KnowledgeLibrary.jsx";

/* Uma pesquisa, fontes opcionais, seleção direta dos documentos e biblioteca.
 * Nunca promete cobertura universal nem mistura notícias com atos normativos.
 */
const SOURCES=[
 ["tesouro","Tesouro Nacional e Siconfi"],
 ["federal","DOU, Planalto e legislação federal"],
 ["lexml","LexML / Senado"],
 ["ms","TCE-MS e legislação estadual"],
 ["campo_grande","Campo Grande / DIOGRANDE"]
];
const CATEGORIES=[
 ["legislacao","Leis, portarias e decretos"],
 ["normas","Resoluções e outras normas"],
 ["manuais","Manuais e orientações"],
 ["sites_oficiais","Outras páginas oficiais"],
 ["metodos","Referências técnicas"]
];
const TOPICS=["CAPAG","Capacidade de pagamento","Receita","Despesa","Prestação de contas","RREO","RGF","DCA","PCASP","Empenho","Liquidação","Balanço"];
async function api(url,body){
 const response=await fetch(url,{method:body?"POST":"GET",cache:"no-store",
  headers:body?{"Content-Type":"application/json"}:undefined,
  body:body?JSON.stringify(body):undefined});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw Error(data.error||"Erro HTTP "+response.status);
 return data;
}
function DocumentRow({entry,selected,busy,onChange}){
 return <label style={{display:"grid",gridTemplateColumns:"auto minmax(0,1fr)",gap:12,
  border:"1px solid #dce5ef",padding:12,borderRadius:8,alignItems:"start"}}>
  <input type="checkbox" checked={selected} disabled={busy} onChange={e=>onChange(e.target.checked)}
   aria-label={"Marcar "+entry.title}/>
  <div style={{minWidth:0}}>
   <a href={entry.url} target="_blank" rel="noopener noreferrer" style={{fontWeight:700}}>
    {entry.title}</a>
   <div className="hint">{entry.source} · {entry.downloadable?"PDF disponível":"Referência / página oficial"}
    {entry.validity_note?" · "+entry.validity_note:""}</div>
  </div>
 </label>;
}
export default function OfficialKnowledgeSearch({project}){
 const id=project?.id,base="/api/projects/"+encodeURIComponent(id||"");
 const [topic,setTopic]=useState(project?.theme||"");
 const [scope,setScope]=useState(project?.scope||"Brasil");
 const [groups,setGroups]=useState(SOURCES.map(s=>s[0]));
 const [categories,setCategories]=useState(CATEGORIES.map(c=>c[0]));
 const [autoDownload,setAutoDownload]=useState(false);
 const [result,setResult]=useState(null);
 const [selected,setSelected]=useState([]);
 const [previous,setPrevious]=useState([]);
 const [libraryVersion,setLibraryVersion]=useState(0);
 const [lastDownload,setLastDownload]=useState(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 useEffect(()=>{
  setTopic(project?.theme||"");setScope(project?.scope||"Brasil");
  setResult(null);setSelected([]);setLastDownload(null);
 },[id]);
 useEffect(()=>{
  if(!id)return;
  let active=true;
  api(base+"/knowledge").then(data=>{
   if(active)setPrevious((data.items||[]).filter(x=>x.type==="research_result").reverse().slice(0,10));
  }).catch(()=>{});
  return()=>{active=false};
 },[id,base]);
 const run=async callback=>{
  setBusy(true);setError("");setNotice("");
  try{
   await callback();
   const summary=await api(base+"/knowledge");
   setPrevious((summary.items||[]).filter(x=>x.type==="research_result").reverse().slice(0,10));
  }catch(e){setError(e.message)}
  finally{setBusy(false)}
 };
 const invalidate=message=>{
  setResult(null);setSelected([]);setLastDownload(null);
  setNotice(message||"Critérios modificados. Clique em Pesquisar documentos para obter novos resultados.");
 };
 const toggle=(value,active,update)=>{
  update(old=>active?[...new Set([...old,value])]:old.filter(x=>x!==value));
  invalidate();
 };
 const choose=(sourceId,checked)=>{
  setSelected(old=>checked?(old.length>=10?old:[...old,sourceId]):old.filter(x=>x!==sourceId));
 };
 const doSearch=()=>run(async()=>{
  const data=await api(base+"/discover",{
   project_id:id,topic:topic.trim(),scope,categories,sources:groups
  });
  setResult(data);setSelected([]);setLastDownload(null);
  if(autoDownload){
   const saved=await api(base+"/auto-download",{
    project_id:id,discovery_id:data.id,max_files:5,restore_deleted:true
   });
   setLastDownload(saved);setLibraryVersion(v=>v+1);
   setNotice("Nova pesquisa concluída: "+data.sources.length+" referências. "+
    saved.downloaded+" PDF(s) baixado(s) e "+(saved.restored||0)+
    " restaurado(s) por sua solicitação. Confira os PDFs na biblioteca.");
  }else{
   setNotice("Nova pesquisa concluída: "+data.sources.length+
    " referências. Marque os PDFs e clique em Baixar e incorporar selecionados.");
  }
 });
 const addSelected=()=>run(async()=>{
  const saved=await api(base+"/approve",{
   project_id:id,discovery_id:result.id,source_ids:selected
  });
  setLibraryVersion(v=>v+1);setSelected([]);
  const restored=saved.imported.filter(x=>x.status==="restaurado da lixeira").length;
  setNotice(saved.imported.length+" documento(s)/referência(s) no acervo ("+restored+
   " recuperado(s) da lixeira). Os PDFs estão na biblioteca acima."+
   (saved.failed.length?" Falhas: "+saved.failed.map(x=>x.title+": "+x.error).join("; "):""));
 });
 if(!id)return null;
 const foundPdfs=(result?.sources||[]).filter(item=>item.downloadable);
 const foundLinks=(result?.sources||[]).filter(item=>!item.downloadable);
 const selectedPdfCount=selected.filter(sourceId=>foundPdfs.some(doc=>doc.id===sourceId)).length;
 const selectedReferenceCount=selected.length-selectedPdfCount;
 const renderItems=items=>items.map(item=><DocumentRow key={item.id} entry={item}
  busy={busy} selected={selected.includes(item.id)}
  onChange={checked=>choose(item.id,checked)}/>);
 return <section className="card" style={{padding:20,marginBottom:16,display:"grid",gap:14}}>
  <div className="eyebrow">CONHECIMENTO · PESQUISA EM FONTES OFICIAIS</div>
  <h2 style={{margin:0}}>O que você deseja pesquisar?</h2>
  <p className="hint" style={{margin:0}}>Digite um tema, número de norma ou assunto.
   A pesquisa prioriza leis, portarias e resoluções. Depois, marque o que deseja guardar.</p>
  {error&&<p role="alert" style={{color:"#a32a2a"}}>{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <div className="catalogForm" style={{display:"grid",gap:12}}>
   <label>Tema ou número da norma
    <input autoFocus value={topic} list="conhecimento-temas" onChange={e=>{
     setTopic(e.target.value);invalidate("Tema modificado. Pesquise novamente para atualizar os documentos.");
    }}
     onKeyDown={e=>{if(e.key==="Enter"&&!busy&&topic.trim().length>=3&&groups.length)doSearch()}}
     placeholder="Ex.: CAPAG, Portaria 1.583/2023, Lei 4.320, RREO"/>
   </label>
   <datalist id="conhecimento-temas">
    {TOPICS.map(value=><option key={value} value={value}/>)}
   </datalist>
   <div style={{display:"grid",gap:6}}>
    <strong>Onde pesquisar?</strong>
    <div className="hint">Todas as bases estão marcadas. Desmarque as que não quiser consultar.</div>
    <div style={{display:"flex",flexWrap:"wrap",gap:"6px 14px"}}>
     {SOURCES.map(([key,name])=><label key={key} style={{display:"flex",alignItems:"center",gap:6}}>
      <input type="checkbox" checked={groups.includes(key)} disabled={busy}
       onChange={e=>toggle(key,e.target.checked,setGroups)}/>{name}
     </label>)}
    </div>
   </div>
   <details>
    <summary>Mais filtros (opcional)</summary>
    <div style={{display:"grid",gap:12,padding:12}}>
     <label>Abrangência<input value={scope} onChange={e=>{
      setScope(e.target.value);invalidate();
     }}
      placeholder="Brasil, MS, Campo Grande"/></label>
     <strong>Tipos de documento</strong>
     <div style={{display:"flex",flexWrap:"wrap",gap:10}}>
      {CATEGORIES.map(([key,name])=><label key={key}
       style={{display:"flex",alignItems:"center",gap:6}}>
       <input type="checkbox" checked={categories.includes(key)} disabled={busy}
        onChange={e=>toggle(key,e.target.checked,setCategories)}/>{name}
      </label>)}
     </div>
     <label style={{display:"flex",alignItems:"center",gap:8}}>
      <input type="checkbox" checked={autoDownload} disabled={busy}
       onChange={e=>setAutoDownload(e.target.checked)}/>
      Baixar automaticamente até 5 PDFs encontrados (opcional)
     </label>
    </div>
   </details>
   <div className="actions">
    <button disabled={busy||topic.trim().length<3||groups.length===0||categories.length===0}
     onClick={doSearch}>{busy?"Pesquisando…":result?"Refazer pesquisa":"Pesquisar documentos"}</button>
   </div>
  </div>
  <KnowledgeLibrary project={project} revision={libraryVersion}
   onResearchAgain={doSearch}
   researchEnabled={!busy&&topic.trim().length>=3&&groups.length>0&&categories.length>0}
   onDocumentDeleted={()=>invalidate("Documento removido. Clique em Refazer pesquisa para consultar as fontes novamente e reincorporar o que desejar.")}/>
  {result&&<>
   <div style={{display:"flex",justifyContent:"space-between",gap:10,flexWrap:"wrap"}}>
    <h3 style={{margin:0}}>Pesquisa concluída — {foundPdfs.length} PDF(s) e {foundLinks.length} outra(s) referência(s)</h3>
    <span className="hint">{selected.length} de 10 marcados</span>
   </div>
   <p className="hint" style={{margin:0}}>Abaixo estão os PDFs encontrados nos portais oficiais.
    Marque os documentos desejados e clique em <strong>Baixar e incorporar selecionados</strong>.
    Quando armazenados, eles aparecem na biblioteca acima.</p>
   {foundPdfs.length>0&&<div className="actions">
    <button type="button" disabled={busy} onClick={()=>setSelected(foundPdfs.slice(0,10).map(x=>x.id))}>
     Marcar os PDFs encontrados (até 10)
    </button>
   </div>}
   {!!result.warnings?.length&&<details>
    <summary>Fontes indisponíveis ou com restrições ({result.warnings.length})</summary>
    {result.warnings.map((message,index)=><p key={index} className="hint">{message}</p>)}
   </details>}
   {foundPdfs.length>0&&<>
    <h4 style={{margin:"4px 0 0"}}>Arquivos PDF encontrados nos sites ({foundPdfs.length})</h4>
    <div style={{display:"grid",gap:8}}>{renderItems(foundPdfs)}</div>
   </>}
   {foundLinks.length>0&&<details>
    <summary>Outras normas e referências de sites — sem PDF direto ({foundLinks.length})</summary>
    <p className="hint">Estas páginas podem ser importantes, mas não são arquivos PDF já baixados.
     Se desejar guardar uma página como referência, marque-a e incorpore ao acervo.</p>
    <div style={{display:"grid",gap:8,marginTop:10}}>{renderItems(foundLinks)}</div>
   </details>}
   {result.sources.length===0&&<p>Não foram encontrados documentos nessas fontes.
    Consulte as advertências de conexão ou experimente outro termo.</p>}
   {selected.length>0&&<div className="actions">
    <button disabled={busy} onClick={addSelected}>
     {selectedPdfCount>0?"Baixar e incorporar "+selectedPdfCount+" PDF(s)":"Incorporar "+selectedReferenceCount+" referência(s)"}
     {selectedPdfCount>0&&selectedReferenceCount>0?" e "+selectedReferenceCount+" referência(s)":""}
    </button>
   </div>}
   {lastDownload&&<p className="hint">Download automático:
    {lastDownload.downloaded} novo(s) PDF(s); {lastDownload.restored||0} restaurado(s); {lastDownload.existing} já existente(s).
    Confira os arquivos na biblioteca acima.</p>}
  </>}
  {previous.length>0&&<details>
   <summary>Pesquisas anteriores ({previous.length})</summary>
   <div style={{display:"grid",gap:6,padding:12}}>
    {previous.map(item=><button key={item.id} disabled={busy} type="button"
     style={{textAlign:"left"}} onClick={()=>run(async()=>{
      const data=await api(base+"/discovery/"+encodeURIComponent(item.id));
      setResult(data);setSelected([]);setLastDownload(null);
      setNotice("Pesquisa recuperada. Marque os arquivos que deseja incorporar.");
     })}>{item.topic} · {item.count||0} referências</button>)}
   </div>
  </details>}
 </section>;
}
