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
export default function KnowledgeStart({project,onProjectChanged}){
 const [rows,setRows]=useState([]),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const [topic,setTopic]=useState(project.theme||""),[scope,setScope]=useState(project.scope||""),[categoriesSelected,setCategoriesSelected]=useState(["legislacao","normas","sites_oficiais"]);
 const [file,setFile]=useState(null),[title,setTitle]=useState(""),[source,setSource]=useState(""),[reference,setReference]=useState(""),[description,setDescription]=useState("");
 const base="/api/projects/"+encodeURIComponent(project.id);
 useEffect(()=>{let active=true;request(base+"/knowledge").then(x=>{if(active)setRows(x.items||[])}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[base]);
 const act=async(fn)=>{setBusy(true);setError("");setNotice("");try{await fn();const x=await request(base+"/knowledge");setRows(x.items||[])}catch(e){setError(e.message)}finally{setBusy(false)}};
 return <div style={{display:"grid",gap:16}}>
  <div className="card" style={{padding:20}}>
   <div className="eyebrow">ETAPA 1 · CONHECIMENTO DO NEGÓCIO</div><h2>{project.name}</h2>
   <p>Primeiro definimos o tema, encontramos documentos oficiais e reunimos os conhecimentos do projeto. Depois vêm os dados e a modelagem.</p>
   {error&&<p role="alert" style={{color:"#b22"}}>{error}</p>}{notice&&<p role="status">{notice}</p>}
  </div>
  <div className="card catalogForm" style={{padding:20}}>
   <h2>Definir assunto e referências da pesquisa</h2>
   <p>Informe o assunto e a abrangência para preparar uma solicitação de pesquisa documental.</p>
   <label>Tema ou assunto<input value={topic} onChange={e=>setTopic(e.target.value)} placeholder="Ex.: prestação de contas de convênios"/></label>
   <label>Abrangência<input value={scope} onChange={e=>setScope(e.target.value)} placeholder="Ex.: Brasil, TCE-MS, Campo Grande"/></label>
   <section className="knowledgeResearchTypes" aria-labelledby="knowledge-research-title">
    <h3 id="knowledge-research-title">Fontes que deseja pesquisar</h3>
    <p>Selecione os tipos de documentos e fontes que devem orientar a pesquisa sobre o tema e a abrangência informados acima.</p>
    <div className="knowledgeResearchOptions" role="group" aria-label="Tipos de fontes para pesquisa">
     {categories.map(([id,name])=><label key={id} className={"knowledgeResearchOption"+(categoriesSelected.includes(id)?" isSelected":"")}>
      <input type="checkbox" checked={categoriesSelected.includes(id)} onChange={e=>setCategoriesSelected(old=>e.target.checked?[...old,id]:old.filter(x=>x!==id))}/>
      <span>{name}</span>
     </label>)}
    </div>
    <p className="knowledgeResearchSummary">{categoriesSelected.length} {categoriesSelected.length===1?"tipo selecionado":"tipos selecionados"}</p>
   </section>
   <div className="actions">
    <button disabled={busy||!topic.trim()||!categoriesSelected.length} onClick={()=>act(async()=>{await request(base+"/research",{project_id:project.id,topic,categories:categoriesSelected,scope});setNotice("Solicitação registrada. A pesquisa automática por IA ainda será conectada; nenhuma busca foi executada.")})}>Registrar pesquisa</button>
    <button disabled={busy||!topic.trim()} onClick={()=>act(async()=>{const updated=await request(base,{theme:topic,scope},"PATCH");onProjectChanged(updated);setNotice("Tema salvo no projeto.")})}>Salvar tema</button>
   </div>
   <p className="hint">Ao registrar, a solicitação fica salva no projeto. A pesquisa automática por IA ainda não está integrada e não será executada neste momento.</p>
  </div>
  <div className="card catalogForm" style={{padding:20}}>
   <h2>2. Incluir documentos formais</h2>
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
   <h2>3. Acervo de conhecimento</h2>
   {rows.length===0?<p>Este projeto ainda não possui documentos ou solicitações. Comece pela pesquisa ou pelo envio de normas.</p>:
    <div style={{display:"grid",gap:12}}>{rows.map(x=><div key={x.id} style={{border:"1px solid #e0e6ef",borderRadius:8,padding:14}}>
     <strong>{x.type==="document"?x.title:x.topic}</strong>
     <div className="hint">{x.type==="document"?"Documento recebido":"Pesquisa solicitada"} · {x.status}</div>
     {x.type==="document"&&<p>{[x.source,x.reference].filter(Boolean).join(" · ")}</p>}
     {x.note&&<p className="hint">{x.note}</p>}
    </div>)}</div>}
  </div>
 </div>;
}
