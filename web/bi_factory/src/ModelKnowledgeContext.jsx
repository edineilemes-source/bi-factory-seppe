import React,{useEffect,useMemo,useState} from "react";

/* Modelagem só recebe evidências documentais do mesmo projeto.
 * A correspondência de um campo nunca altera medidas, fórmulas ou etapas
 * do pipeline sem revisão explícita de regras e de dados.
 */
export default function ModelKnowledgeContext({projectId,fields=[]}){
 const [term,setTerm]=useState("");
 const [matches,setMatches]=useState({});
 const [selected,setSelected]=useState(null);
 const [error,setError]=useState("");
 const [interpretation,setInterpretation]=useState(null);
 const [busy,setBusy]=useState(false);
 const candidates=useMemo(()=>[...new Map((fields||[]).map(f=>{
  const name=String(f.original_name||f.technical_name||"").trim();
  return [name.toLowerCase(),name];
 }).filter(([key,value])=>key&&value)).values()].slice(0,16),[fields]);
 const base="/api/projects/"+encodeURIComponent(projectId||"");
 const search=async(value,quiet=false)=>{
  if(!projectId||!value?.trim())return;
  if(!quiet)setBusy(true);
  setError("");
  try{
   const res=await fetch(base+"/concepts?query="+encodeURIComponent(value.trim())+"&limit=5",{cache:"no-store"});
   const data=await res.json().catch(()=>({}));
   if(!res.ok)throw Error(data.error||"Não foi possível consultar o acervo do projeto");
   setMatches(old=>({...old,[value]:data}));
   if(!quiet){setSelected(value);setInterpretation(null)}
  }catch(e){setError(e.message)}
  finally{if(!quiet)setBusy(false)}
 };
 useEffect(()=>{
  if(!projectId)return;
  let active=true;
  const autos=candidates.slice(0,8).filter(Boolean);
  Promise.all(autos.map(async value=>{
   const r=await fetch(base+"/concepts?query="+encodeURIComponent(value)+"&limit=3",
                      {cache:"no-store"});
   if(!r.ok)return [value,null];
   return [value,await r.json()];
  })).then(items=>{if(active){
   setMatches(Object.fromEntries(items.filter(([,result])=>result)));
  }}).catch(()=>{});
  return()=>{active=false};
 },[projectId,candidates.join("|")]);
 if(!projectId)return <p>Selecione um projeto para consultar o Conhecimento na modelagem.</p>;
 const current=selected?matches[selected]:null;
 const known=candidates.filter(n=>(matches[n]?.matches||[]).length);
 return <section className="card" style={{padding:16,margin:"16px 0",display:"grid",gap:10}}>
  <h3 style={{margin:0}}>Conhecimento normativo aplicado à Modelagem</h3>
  <p className="hint">Trechos dos PDFs que você selecionou e mandou ler no projeto. Quando uma coluna como Empenho ou Poupança corrente é detectada, o sistema procura evidências nos documentos antes de propor classificações. Nenhuma fórmula é homologada automaticamente.</p>
  {error&&<p role="alert" style={{color:"#b22"}}>{error}</p>}
  {candidates.length>0&&<div>
   <strong>Campos da fonte em análise</strong>
   <div style={{display:"flex",gap:7,flexWrap:"wrap",marginTop:8}}>
    {candidates.map(name=><button key={name} type="button" disabled={busy}
     onClick={()=>search(name)} style={{padding:"6px 8px",fontSize:12}}>
     {name}{matches[name]?.matches?.length?" · "+matches[name].matches.length+" evidência(s)":""}
    </button>)}
   </div>
   <p className="hint">{known.length} campo(s) com evidências documentais já encontradas automaticamente. Clique em um campo para conferir as fontes.</p>
  </div>}
  <div className="catalogForm" style={{display:"flex",gap:8,alignItems:"end",flexWrap:"wrap"}}>
   <label style={{flex:"1 1 240px"}}>Pesquisar conceito ou medida
    <input value={term} onChange={e=>setTerm(e.target.value)}
     onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();search(term)}}}
     placeholder="Empenho, CAPAG, poupança corrente, receita…"/>
   </label>
   <button onClick={()=>search(term)} disabled={busy||!term.trim()}>
    {busy?"Consultando…":"Consultar conhecimento do projeto"}</button>
  </div>
  {current&&<div style={{display:"grid",gap:8}}>
   <strong>{selected}: {current.matches?.length||0} evidência(s)</strong>
   {!!current.matches?.length&&<div className="actions">
    <button disabled={busy} onClick={async()=>{
     setBusy(true);setError("");setInterpretation(null);
     try{
      const r=await fetch(base+"/interpret",{method:"POST",
       headers:{"Content-Type":"application/json"},cache:"no-store",
       body:JSON.stringify({project_id:projectId,question:selected})});
      const data=await r.json().catch(()=>({}));
      if(!r.ok)throw Error(data.error||"Interpretação indisponível");
      setInterpretation(data);
     }catch(e){setError(e.message)}finally{setBusy(false)}
    }}>Pedir interpretação à IA local (opcional)</button>
   </div>}
   {interpretation&&<div style={{padding:12,border:"1px solid #cfdae5",borderRadius:8}}>
    <strong>{interpretation.status}</strong>
    {interpretation.interpretation&&<>
     <p>{interpretation.interpretation.explicacao}</p>
     <p className="hint">Classificação sugerida: {interpretation.interpretation.tipo_sugerido}</p>
     {interpretation.interpretation.formula_sugerida&&<p>Fórmula sugerida, não aprovada: <code>{interpretation.interpretation.formula_sugerida}</code></p>}
     <p className="hint">Lacunas: {interpretation.interpretation.lacunas||"a conferir"}</p>
    </>}
   </div>}
   {!current.matches?.length?<p>Não existe trecho indexado para este campo. Vá a Conhecimento, abra o PDF e use Ler e indexar.</p>:
    current.matches.map((m,i)=><div key={m.document_id+"-"+m.page+"-"+i}
     style={{borderLeft:"3px solid #6e9bb1",padding:"8px 12px",background:"#f6f8fa"}}>
     <p style={{margin:"0 0 5px"}}>{m.excerpt}</p>
     <small>{m.title} · página {m.page} · referência documental para conferência
      {m.validity_note?" · "+m.validity_note:""}</small>
     <div style={{marginTop:6}}>
      <a href={base+"/documents/"+encodeURIComponent(m.document_id)+"/view"}
       target="_blank" rel="noopener noreferrer">Conferir página no PDF original</a>
     </div>
    </div>)}
   <p className="hint">A classificação como dimensão, medida, fórmula e período de vigência depende da revisão do responsável. Evidência textual não prova, por si, a regra de cálculo.</p>
  </div>}
 </section>;
}
