import React,{useState} from "react";

async function request(path, payload) {
  const r=await fetch(path,{method:payload?"POST":"GET",headers:payload?{"Content-Type":"application/json"}:{},body:payload?JSON.stringify(payload):undefined});
  const result=await r.json().catch(()=>({}));
  if(!r.ok)throw Error(result.error||"Não foi possível consultar os projetos.");
  return result;
}

export default function ProjectHome({projects,loading,onRefresh,onOpen}){
  const [creating,setCreating]=useState(false);
  const [draft,setDraft]=useState({name:"",theme:"",goal:"",scope:"",description:"",organization:""});
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const save=async(e)=>{
    e.preventDefault();if(busy)return;
    setBusy(true);setError("");
    try{
      const project=await request("/api/projects",draft);
      await onRefresh();
      setCreating(false);onOpen(project);
    }catch(err){setError(err.message)}
    finally{setBusy(false)}
  };
  return <div style={{display:"grid",gap:18}}>
    <div className="card hero">
      <div className="eyebrow">PLATAFORMA DE INTELIGÊNCIA DE NEGÓCIOS</div>
      <h2>Da compreensão do negócio à publicação dos dados</h2>
      <p>Crie ou abra um projeto. O BI Factory organiza o conhecimento, as fontes, a modelagem, os produtos de informação e as publicações em um único ambiente.</p>
      <div className="actions"><button onClick={()=>{setCreating(true);setError("")}}>+ Novo projeto</button></div>
    </div>
    {creating&&<form className="card catalogForm" onSubmit={save} style={{padding:20}}>
      <h2>Cadastrar novo projeto</h2>
      <p>Primeiro informe o que deseja estudar. Ainda não precisa importar dados nem conhecer os detalhes técnicos.</p>
      {error&&<p role="alert" style={{color:"#aa2525"}}>{error}</p>}
      <label>Nome do projeto *<input required maxLength={180} value={draft.name} onChange={e=>setDraft(x=>({...x,name:e.target.value}))} placeholder="Ex.: Gestão do almoxarifado"/></label>
      <label>Tema do projeto *<input required maxLength={300} value={draft.theme} onChange={e=>setDraft(x=>({...x,theme:e.target.value}))} placeholder="Ex.: controle de estoque, movimentações e consumo"/></label>
      <label>Objetivo do projeto<textarea value={draft.goal} onChange={e=>setDraft(x=>({...x,goal:e.target.value}))} placeholder="Quais perguntas os dashboards precisam responder?"/></label>
      <label>Organização / responsável<input value={draft.organization} onChange={e=>setDraft(x=>({...x,organization:e.target.value}))} placeholder="Órgão, empresa ou condomínio"/></label>
      <label>Abrangência<input value={draft.scope} onChange={e=>setDraft(x=>({...x,scope:e.target.value}))} placeholder="Ex.: Brasil, Mato Grosso do Sul, município, entidade"/></label>
      <label>Descrição complementar<textarea value={draft.description} onChange={e=>setDraft(x=>({...x,description:e.target.value}))}/></label>
      <div className="actions"><button type="submit" disabled={busy||!draft.name.trim()||!draft.theme.trim()}>{busy?"Salvando...":"Criar projeto e iniciar conhecimento"}</button><button type="button" onClick={()=>setCreating(false)}>Cancelar</button></div>
    </form>}
    <div className="card" style={{padding:20}}>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"}}><h2>Meus projetos</h2><button onClick={onRefresh} disabled={loading}>Atualizar lista</button></div>
      {loading?<p>Carregando projetos...</p>:projects.length===0?<p>Nenhum projeto cadastrado.</p>:<div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:12}}>
        {projects.map(p=><div key={p.id} style={{border:"1px solid #d9e3ed",padding:18,borderRadius:12}}>
          <div className="eyebrow">{p.legacy?"PROJETO RECUPERADO":"PROJETO CADASTRADO"}</div>
          <h3>{p.name}</h3><p>{p.theme||"Tema não informado"}</p>
          <p className="hint">{p.scope||"Abrangência não definida"} · {p.status||"Novo"}</p>
          <button onClick={()=>onOpen(p)}>Abrir projeto</button>
        </div>)}
      </div>}
      <p className="hint">O projeto PMCG existente continua preservado. Novos projetos têm cadastro e conhecimento próprios; a associação dos produtos antigos não é alterada.</p>
    </div>
  </div>;
}
