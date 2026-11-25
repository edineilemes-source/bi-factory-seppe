import React,{useEffect,useState} from "react";

async function libraryApi(url,body,method){
 const response=await fetch(url,{method:method||(body?"POST":"GET"),
  headers:body?{"Content-Type":"application/json"}:undefined,
  body:body?JSON.stringify(body):undefined,cache:"no-store"});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw Error(data.error||"Falha no acervo documental");
 return data;
}
const describeSize=size=>size?((size/1024/1024).toFixed(2)+" MB"):"Tamanho não informado";
export default function KnowledgeLibrary({project,revision=0}){
 const id=project?.id;
 const api="/api/projects/"+encodeURIComponent(id||"");
 const [documents,setDocuments]=useState([]);
 const [selected,setSelected]=useState([]);
 const [busy,setBusy]=useState(false);
 const [notice,setNotice]=useState("");
 const [error,setError]=useState("");
 const [query,setQuery]=useState("");
 const [matches,setMatches]=useState(null);
 const [lastRead,setLastRead]=useState(null);
 const reload=async()=>{
  const response=await libraryApi(api+"/library");
  setDocuments(response.documents||[]);
  setSelected(old=>old.filter(value=>(response.documents||[]).some(d=>
   d.id===value&&!d.deleted_at&&d.type==="document")));
 };
 useEffect(()=>{if(!id)return;let active=true;
  libraryApi(api+"/library").then(response=>{if(active){
   setDocuments(response.documents||[]);
   setSelected([]);
  }}).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[api,id,revision]);
 const execute=async cb=>{
  setBusy(true);setError("");setNotice("");
  try{await cb();await reload()}
  catch(e){setError(e.message)}
  finally{setBusy(false)}
 };
 const live=documents.filter(x=>!x.deleted_at);
 const removed=documents.filter(x=>x.deleted_at);
 const pdfs=live.filter(x=>x.type==="document"&&x.sha256);
 const infoText="O botão Ler e indexar extrai trechos verificáveis (página, documento e URL). "+
  "Não é treinamento permanente de um modelo de IA; a Modelagem consulta esse índice do projeto.";
 return <section className="card" style={{padding:20,marginTop:16,display:"grid",gap:13}}>
  <h2 style={{margin:0}}>Biblioteca de documentos do projeto</h2>
  <p className="hint">Arquivos aprovados ficam aqui, acessíveis para conferência antes da leitura. Você pode abrir o PDF, excluir do acervo ou selecionar os que deseja indexar.</p>
  {error&&<p role="alert" style={{color:"#b22"}}>{error}</p>}
  {notice&&<p role="status">{notice}</p>}
  <div className="actions">
   <button type="button" disabled={busy} onClick={()=>execute(async()=>{})}>Atualizar biblioteca</button>
   <button type="button" disabled={busy||!pdfs.length}
    onClick={()=>setSelected(pdfs.slice(0,6).map(x=>x.id))}>Selecionar até 6 PDFs</button>
   <button type="button" disabled={busy||!selected.length}
    onClick={()=>setSelected([])}>Limpar seleção</button>
   <button disabled={busy||!selected.length} onClick={()=>execute(async()=>{
    const reply=await libraryApi(api+"/read-documents",{
     project_id:id,document_ids:selected});
    setLastRead(reply);setSelected([]);
    setNotice(reply.read.length+" arquivo(s) processado(s). "+
     "Os trechos reconhecidos já podem ser consultados na Modelagem.");
   })}>{busy?"Processando…":"Ler e indexar arquivos ("+selected.length+")"}</button>
  </div>
  <p className="hint">{infoText}</p>
  {live.length===0?<p>O acervo ainda está vazio. Selecione e incorpore documentos nos resultados da pesquisa oficial acima.</p>:
   <div style={{display:"grid",gap:9}}>
    {live.map(doc=><div key={doc.id} style={{border:"1px solid #dce5ef",borderRadius:9,padding:13,display:"grid",gap:7}}>
     <div style={{display:"flex",justifyContent:"space-between",gap:12,alignItems:"start"}}>
      <label style={{display:"flex",gap:8,alignItems:"start",minWidth:0,flex:1}}>
       {doc.type==="document"&&doc.sha256?<input type="checkbox" disabled={busy}
        aria-label={"Selecionar para leitura "+doc.title} checked={selected.includes(doc.id)}
        onChange={e=>setSelected(old=>e.target.checked?old.length>=6?old:[...old,doc.id]:old.filter(x=>x!==doc.id))}/>:null}
       <strong>{doc.title}</strong>
      </label>
     </div>
     <div className="hint">{[doc.source,doc.category,doc.validity_note,describeSize(doc.size_bytes),doc.read_status].filter(Boolean).join(" · ")}</div>
     {doc.subject&&<div className="hint">Assunto da pesquisa: {doc.subject}</div>}
     <div className="actions">
      {doc.type==="document"&&doc.sha256&&<>
       <a href={api+"/documents/"+encodeURIComponent(doc.id)+"/view"} target="_blank"
        rel="noopener noreferrer">Abrir PDF para conferir</a>
       <a href={api+"/documents/"+encodeURIComponent(doc.id)+"/download"}>
        Baixar PDF</a>
      </>}
      {doc.source_url&&<a target="_blank" rel="noopener noreferrer"
       href={doc.source_url}>Consultar no órgão</a>}
      <button type="button" disabled={busy} onClick={()=>{
       if(!window.confirm("Remover '"+doc.title+"' do acervo e do índice de conhecimento? "+
        "O arquivo será guardado na lixeira para recuperação."))return;
       execute(async()=>{
        await libraryApi(api+"/documents/"+encodeURIComponent(doc.id),null,"DELETE");
        setSelected(old=>old.filter(x=>x!==doc.id));
        setMatches(null);
        setNotice("Arquivo retirado do acervo e da consulta de conceitos. Recuperação disponível na Lixeira.");
       });
      }}>Excluir do acervo</button>
     </div>
     {doc.sha256&&<div className="hint">Verificação SHA-256: {doc.sha256.slice(0,20)}…</div>}
    </div>)}
   </div>}
  {lastRead&&<div style={{border:"1px solid #dce5ef",padding:12,borderRadius:9}}>
   <h3>Resultado da leitura</h3>
   {lastRead.read.map(item=><p key={item.document_id}>
    <strong>{item.title}</strong>: {item.status} · {item.stats.pages_with_text} página(s) com texto
    de {item.stats.page_count} · {item.concept_count} trecho(s) sobre conceitos identificados.
    {item.stats.truncated?" Foi analisada somente a parte inicial do PDF.":""}
   </p>)}
  </div>}
  <div className="catalogForm">
   <h3>Consultar conceitos que serão usados na Modelagem</h3>
   <label>Conceito, nome da medida ou coluna
    <input value={query} onChange={e=>setQuery(e.target.value)}
     placeholder="Ex.: empenho, poupança corrente, CAPAG ou liquidez relativa"/>
   </label>
   <button disabled={busy||!query.trim()} onClick={()=>execute(async()=>{
    const data=await libraryApi(api+"/concepts?query="+encodeURIComponent(query)+"&limit=8");
    setMatches(data);
   })}>Pesquisar nos arquivos lidos</button>
   {matches&&<div style={{display:"grid",gap:10,marginTop:10}}>
    <p className="hint">{matches.indexed_documents} documento(s) indexado(s). {matches.status}</p>
    {!matches.matches.length?<p>Nenhum trecho encontrado. Selecione PDFs e use Ler e indexar para preencher a base.</p>:
     matches.matches.map((m,i)=><blockquote key={m.document_id+"-"+m.page+"-"+i}
      style={{margin:0,padding:"10px 14px",borderLeft:"3px solid #4485a4",background:"#f5f8fa"}}>
      <p>{m.excerpt}</p>
      <small>{m.title} · página {m.page} · fonte e SHA-256 registrados
       {m.validity_note?" · "+m.validity_note:""} · <strong>interpretação pendente de validação</strong></small>
      {m.source_url&&<div><a href={m.source_url} target="_blank" rel="noopener noreferrer">Abrir origem oficial</a></div>}
     </blockquote>)}
   </div>}
  </div>
  {removed.length>0&&<details>
   <summary>Lixeira — arquivos removidos ({removed.length})</summary>
   <div style={{display:"grid",gap:6,padding:10}}>
    {removed.map(doc=><div key={doc.id} style={{display:"flex",gap:8,alignItems:"center",justifyContent:"space-between"}}>
     <span>{doc.title}</span>
     <button disabled={busy} onClick={()=>execute(async()=>{
      await libraryApi(api+"/documents/"+encodeURIComponent(doc.id)+"/restore",{project_id:id});
      setNotice("Documento restaurado ao acervo.");
     })}>Restaurar</button>
    </div>)}
   </div>
  </details>}
 </section>;
}
