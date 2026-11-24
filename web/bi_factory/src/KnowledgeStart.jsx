import React,{useEffect,useState} from "react";
async function request(path,payload,method="POST"){
 const r=await fetch(path,{method:payload?method:"GET",headers:payload?{"Content-Type":"application/json"}:{},body:payload?JSON.stringify(payload):undefined});
 const v=await r.json().catch(()=>({}));if(!r.ok)throw Error(v.error||"Falha na comunicação");return v;
}
async function asBase64(file){
 const bytes=new Uint8Array(await file.arrayBuffer());let raw="";
 for(let i=0;i<bytes.length;i+=8192)raw+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(raw);
}
const categories=[["legislacao","Leis e decretos"],["normas","Resoluções e normas"],["manuais","Manuais e orientações"],["sites_oficiais","Sites de órgãos oficiais"],["metodos","Métodos e referências técnicas"]];
const suggestedTopics=["Receita orçamentária","Despesa orçamentária","Empenho","Liquidação da despesa","Pagamento","Balanço patrimonial","Prestação de contas","RREO","RGF","DCA","PCASP"];
export default function KnowledgeStart({project,onProjectChanged}){
 const [rows,setRows]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [discovery,setDiscovery]=useState(null),[selectedSources,setSelectedSources]=useState([]);
 const [topic,setTopic]=useState(project.theme||""),[scope,setScope]=useState(project.scope||""),[categoriesSelected,setCategoriesSelected]=useState(["legislacao","normas","manuais","sites_oficiais"]);
 const [file,setFile]=useState(null),[title,setTitle]=useState(""),[source,setSource]=useState(""),[reference,setReference]=useState(""),[description,setDescription]=useState("");
 const base="/api/projects/"+encodeURIComponent(project.id);
 useEffect(()=>{let active=true;request(base+"/knowledge").then(x=>{if(active)setRows(x.items||[])}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[base]);
 const act=async(fn)=>{setBusy(true);setError("");setNotice("");try{await fn();const x=await request(base+"/knowledge");setRows(x.items||[])}catch(e){setError(e.message)}finally{setBusy(false)}};
 return <div style={{display:"grid",gap:16}}>
  <div className="card" style={{padding:20}}>
   <div className="eyebrow">ETAPA 1 · CONHECIMENTO DO NEGÓCIO</div><h2>{project.name}</h2>
   <p>Pesquise legislação, MCASP, MDF, normas e documentação Siconfi diretamente nas fontes oficiais. Revise e aprove quais documentos devem entrar no acervo deste projeto; só então os PDFs são baixados.</p>
   {error&&<p role="alert" style={{color:"#b22"}}>{error}</p>}{notice&&<p role="status">{notice}</p>}
  </div>
  <div className="card catalogForm" style={{padding:20}}>
   <h2>1. O que você deseja conhecer?</h2>
   <label>Tema ou assunto<input value={topic} onChange={e=>setTopic(e.target.value)} placeholder="Ex.: prestação de contas de convênios"/></label>
   <div className="hint">Temas relacionados à modelagem de receita e despesa:</div>
   <div style={{display:"flex",gap:8,flexWrap:"wrap",marginBottom:10}}>
    {suggestedTopics.map(name=><button key={name} type="button"
      disabled={busy} onClick={()=>setTopic(name)} style={{fontSize:12,padding:"7px 10px"}}>
      {name}</button>)}
   </div>
   <label>Abrangência<input value={scope} onChange={e=>setScope(e.target.value)} placeholder="Ex.: Brasil, TCE-MS, Campo Grande"/></label>
   <fieldset style={{border:"1px solid #dce5ef",padding:14,borderRadius:10}}><legend>Quais documentos pesquisar?</legend>
    {categories.map(([id,name])=><label key={id} style={{display:"flex",alignItems:"center",gap:10,margin:"9px 0"}}>
     <input type="checkbox" checked={categoriesSelected.includes(id)} onChange={e=>setCategoriesSelected(old=>e.target.checked?[...old,id]:old.filter(x=>x!==id))}/>{name}</label>)}
   </fieldset>
   <div className="actions">
    <button disabled={busy||topic.trim().length<3||!categoriesSelected.length} onClick={()=>act(async()=>{
     const found=await request(base+"/discover",{project_id:project.id,topic,categories:categoriesSelected,scope});
     setDiscovery(found);setSelectedSources([]);
     setNotice("Pesquisa oficial executada: "+found.sources.length+" referências encontradas. Selecione os PDFs e documentos que deseja guardar no projeto.");
    })}>{busy?"Pesquisando…":"Pesquisar fontes oficiais"}</button>
    <button disabled={busy||!topic.trim()} onClick={()=>act(async()=>{const updated=await request(base,{theme:topic,scope},"PATCH");onProjectChanged(updated);setNotice("Tema salvo no projeto.")})}>Salvar tema</button>
   </div>
   <p className="hint">A busca funciona sem chave de API paga: consulta portais oficiais selecionados. Uma IA local via Ollama (opcional, se configurada no servidor) pode sugerir termos, mas jamais criar leis ou documentos. A cobertura inicial não é exaustiva.</p>
  </div>
  <div className="card" style={{padding:20}}>
   <h2>2. Resultados da pesquisa oficial — revisar antes de importar</h2>
   {!discovery?<p className="hint">Informe um tema e clique em Pesquisar fontes oficiais. Nenhum arquivo será baixado sem a sua seleção e aprovação.</p>:<>
    <p className="hint">{discovery.provider} · {discovery.searched_at?.slice(0,16)?.replace("T"," ")} · {discovery.ai_status}</p>
    <p className="hint">{discovery.scope_note}</p>
    {(discovery.warnings||[]).length>0&&<details><summary>Fontes temporariamente indisponíveis ({discovery.warnings.length})</summary>
     <ul>{discovery.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    <div className="actions">
     <button type="button" disabled={busy||!discovery.sources.some(s=>s.downloadable)}
      onClick={()=>setSelectedSources(discovery.sources.filter(s=>s.downloadable).slice(0,10).map(s=>s.id))}>
      Selecionar até 10 PDFs</button>
     <button type="button" disabled={busy||!selectedSources.length} onClick={()=>setSelectedSources([])}>Limpar seleção</button>
     <button type="button" disabled={busy||!selectedSources.length}
      onClick={()=>act(async()=>{
       const response=await request(base+"/approve",{
        project_id:project.id,discovery_id:discovery.id,source_ids:selectedSources
       });
       setSelectedSources([]);
       setNotice(response.imported.length+" referências incorporadas. "+
        (response.failed.length?response.failed.length+" falharam: "+response.failed.map(e=>e.title+": "+e.error).join("; "):
        "Os PDFs aprovados foram guardados no repositório de dados do projeto."));
      })}>Aprovar e incorporar ({selectedSources.length})</button>
    </div>
    {!discovery.sources.length?<p>Não foram encontradas referências nessas fontes. Verifique a conexão com os portais, tente outros termos ou consulte as advertências acima.</p>:
    <div style={{display:"grid",gap:10,marginTop:12}}>{discovery.sources.map(item=><div key={item.id}
      style={{display:"grid",gridTemplateColumns:"auto minmax(0,1fr)",gap:12,alignItems:"start",border:"1px solid #dce5ef",padding:12,borderRadius:9}}>
      <input aria-label={"Selecionar "+item.title} type="checkbox" checked={selectedSources.includes(item.id)}
       disabled={busy} onChange={event=>setSelectedSources(old=>{
        if(!event.target.checked)return old.filter(id=>id!==item.id);
        return old.length>=10?old:[...old,item.id];
       })}/>
      <div style={{minWidth:0}}>
       <strong><a href={item.url} target="_blank" rel="noreferrer noopener">{item.title}</a></strong>
       <div className="hint">{item.source} · {item.category} · {item.downloadable?"PDF — será baixado após aprovação":"Página oficial — somente referência"} · pontuação {item.score}{item.validity_note?" · "+item.validity_note:""}</div>
       {item.origin!==item.url&&<div className="hint">Encontrado em <a href={item.origin} target="_blank" rel="noreferrer noopener">página do órgão</a></div>}
      </div>
     </div>)}</div>}
   </>}
  </div>
  <div className="card catalogForm" style={{padding:20}}>
   <h2>3. Incluir documentos próprios</h2>
   <p>Adicione legislação, normas, manuais e regulamentos. O arquivo original e a origem informada serão guardados no projeto.</p>
   <label>Arquivo PDF, DOCX ou TXT<input type="file" accept=".pdf,.docx,.txt" onChange={e=>{let f=e.target.files?.[0]||null;setFile(f);setTitle(f?.name||"")}}/></label>
   <label>Título<input value={title} onChange={e=>setTitle(e.target.value)}/></label>
   <label>Órgão emissor<input value={source} onChange={e=>setSource(e.target.value)} placeholder="Ex.: Tribunal de Contas"/></label>
   <label>Referência ou número<input value={reference} onChange={e=>setReference(e.target.value)} placeholder="Ex.: Resolução nº 123"/></label>
   <label>Descrição<textarea value={description} onChange={e=>setDescription(e.target.value)}/></label>
   <div className="actions"><button disabled={busy||!file} onClick={()=>act(async()=>{
    if(file.size>12*1024*1024)throw Error("O limite é 12 MB.");
    await request(base+"/documents",{project_id:project.id,filename:file.name,base64:await asBase64(file),title,source,reference,description});
    setFile(null);setTitle("");setSource("");setReference("");setDescription("");
    setNotice("Documento recebido e preservado no acervo deste projeto. Extração de regras ainda pendente.");
   })}>Enviar documento</button></div>
  </div>
  <div className="card" style={{padding:20}}>
   <h2>4. Acervo de conhecimento do projeto</h2>
   {rows.length===0?<p>Este projeto ainda não possui documentos ou solicitações. Comece pela pesquisa ou pelo envio de normas.</p>:
    <div style={{display:"grid",gap:12}}>{rows.map(x=><div key={x.id} style={{border:"1px solid #e0e6ef",borderRadius:8,padding:14}}>
     <strong>{x.type==="document"||x.type==="official_reference"?x.title:x.topic}</strong>
     <div className="hint">{x.type==="document"?"Arquivo preservado":x.type==="official_reference"?"Fonte catalogada":x.type==="research_result"?"Busca oficial executada":"Solicitação antiga"} · {x.status}</div>
     {(x.type==="document"||x.type==="official_reference")&&<p>{[x.source,x.reference,x.validity_note].filter(Boolean).join(" · ")}</p>}
     {x.source_url&&<p><a href={x.source_url} target="_blank" rel="noreferrer noopener">Consultar documento no órgão emissor</a>
      {x.relative_path&&" · "}
      {x.relative_path&&<a href={base+"/documents/"+encodeURIComponent(x.id)+"/download"}>Baixar cópia PDF armazenada</a>}</p>}
     {x.sha256&&<div className="hint">SHA-256: <code>{x.sha256.slice(0,16)}…</code> · Incorporado em {x.approved_at?.slice(0,10)}</div>}
     {x.type==="research_result"&&<button type="button" disabled={busy}
       onClick={()=>act(async()=>{const saved=await request(base+"/discovery/"+encodeURIComponent(x.id));setDiscovery(saved);setSelectedSources([]);setNotice("Resultados recuperados; selecione o que deseja incorporar.")})}>
       Reabrir resultados ({x.count})</button>}
     {x.note&&<p className="hint">{x.note}</p>}
    </div>)}</div>}
  </div>
 </div>;
}
