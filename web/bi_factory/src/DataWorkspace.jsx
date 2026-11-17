import React,{useEffect,useState} from "react";

/* React presentation only. All interpretation, persistence and tests live in core/*. */
const KEY="bi-factory-last-analysis-id";
const PIPELINE=[
  ["Profiling",null],
  ["Semântica","semantic"],
  ["Qualidade","quality"],
  ["Prepared Dataset","prepared_dataset_status"],
  ["Grão","grain_status"],
  ["Dimensional","dimensional_status"],
  ["Esquema estrela","star_schema_status"],
  ["DDL","ddl_status"],
  ["ETL","etl_plan_status"],
  ["Transformação","transformation_status"],
  ["Dry Run","database_dry_run_status"],
];
const pending=q=>q.status==="PENDING";
const readBase64=async file=>{
  const data=new Uint8Array(await file.arrayBuffer());
  let binary="";
  for(let i=0;i<data.length;i+=8192){
    binary+=String.fromCharCode(...data.subarray(i,i+8192));
  }
  return btoa(binary);
};
async function api(path,body){
  const response=await fetch("/api/analytics/"+path,{
    method:body?"POST":"GET",
    headers:body?{"Content-Type":"application/json"}:undefined,
    body:body?JSON.stringify(body):undefined,
  });
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(result.error||"Falha de comunicação com a API analítica");
  return result;
}
const statusLabel=value=>{
  if(!value||value==="not_started")return "Não iniciado";
  if(value==="READY"||value==="COMPLETED")return "Concluído";
  if(value==="IN_PROGRESS")return "Em andamento";
  return String(value).replaceAll("_"," ");
};

export default function DataWorkspace({area,projectName,projectId}){
  const [cap,setCap]=useState(null),[snapshot,setSnapshot]=useState(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const [file,setFile]=useState(null),[domain,setDomain]=useState("");
  const [purpose,setPurpose]=useState(""),[answers,setAnswers]=useState({});
  const key=KEY+"-"+(projectId||"legacy");
  const [analysisId,setAnalysisId]=useState(()=>localStorage.getItem(key)||"");

  useEffect(()=>{
    api("capabilities").then(setCap).catch(e=>setError(e.message));
  },[]);
  useEffect(()=>{
    if(!analysisId)return;
    let active=true;
    api("analysis/"+encodeURIComponent(analysisId)).then(result=>{
      if(active)setSnapshot(result);
    }).catch(e=>{if(active)setError("Análise anterior: "+e.message)});
    return ()=>{active=false};
  },[analysisId]);

  const processFile=async()=>{
    if(!file)return;
    setBusy(true);setError("");setMessage("");
    try{
      if(file.size>8*1024*1024)throw Error("O limite inicial é de 8 MB por arquivo.");
      const result=await api("upload",{
        filename:file.name,base64:await readBase64(file),
        context:{project_name:projectName,business_domain:domain,purpose},
      });
      setSnapshot(result);setAnalysisId(result.analysis_id);
      localStorage.setItem(key,result.analysis_id);
      setMessage("Análise persistida. O arquivo original não foi alterado.");
    }catch(e){setError(e.message)}
    finally{setBusy(false)}
  };
  const reply=async q=>{
    const choice=answers[q.question_id]?.answer||q.options[0];
    const detail=answers[q.question_id]?.custom_answer||"";
    setBusy(true);setError("");setMessage("");
    try{
      const result=await api("answer",{
        analysis_id:snapshot.analysis_id,question_id:q.question_id,
        answer:choice,custom_answer:detail,
      });
      setSnapshot(result);setMessage("Resposta salva no catálogo semântico.");
    }catch(e){setError(e.message)}
    finally{setBusy(false)}
  };
  const restore=async()=>{
    setBusy(true);setError("");
    try{
      const result=await api("analysis/"+encodeURIComponent(analysisId.trim()));
      setSnapshot(result);localStorage.setItem(key,result.analysis_id);
      setMessage("Análise recuperada do SQLite.");
    }catch(e){setError(e.message)}finally{setBusy(false)}
  };

  const questions=snapshot?.semantic?.questions||[];
  const fields=snapshot?.profile?.sheets?.flatMap(sheet=>sheet.fields.map(f=>({...f,sheet:sheet.name})))||[];
  const unresolved=questions.filter(pending);
  const p=snapshot?.pipeline||{};

  return <div className="card" style={{padding:20}}>
    <h2>{area==="Conhecimento"?"Conhecimento do negócio":area==="Modelagem"?"Modelagem e contratos":"Entrada de dados"}</h2>
    <p>Ambiente único React + motores analíticos Python existentes. Análises persistidas no SQLite, sem abrir o Streamlit.</p>
    {error&&<p role="alert" style={{color:"#a52a2a"}}>{error}</p>}
    {message&&<p role="status">{message}</p>}
    {area==="Entrada de dados"&&<div className="catalogForm">
      <h3>Importar e analisar fonte tabular</h3>
      <p>Importadores recuperados: XLSX, XLSM e CSV. Amostragem técnica e perguntas semânticas automáticas.</p>
      <label>Domínio do negócio<input value={domain} onChange={e=>setDomain(e.target.value)} placeholder="Ex.: despesas, estoque, condomínio"/></label>
      <label>Objetivo da análise<textarea value={purpose} onChange={e=>setPurpose(e.target.value)} placeholder="O que você pretende analisar?"/></label>
      <label>Fonte<input type="file" accept=".csv,.xlsx,.xlsm" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
      <div className="actions"><button onClick={processFile} disabled={!file||busy}>{busy?"Analisando...":"Analisar arquivo"}</button></div>
      <p className="hint">Limite inicial: 8 MB. Conteúdo tratado localmente no Codespaces, sem envio ao GitHub. Guarde o original para etapas posteriores.</p>
      <h3>Fontes e conectores adicionais</h3><p>PDF, XML, JSON, APIs e bancos SQL: conectores a incorporar e validar nesta interface; nenhum deles está anunciado como funcional.</p>
    </div>}
    <div className="catalogForm">
      <h3>Análise persistida</h3>
      <label>ID da análise<input value={analysisId} onChange={e=>setAnalysisId(e.target.value)} placeholder="Identificador UUID"/></label>
      <div className="actions"><button disabled={!analysisId||busy} onClick={restore}>Recuperar análise</button></div>
      {!snapshot&&<p>Nenhuma análise selecionada. Importe uma fonte em Entrada de dados ou informe um ID anterior.</p>}
    </div>
    {snapshot&&<div>
      <h3>{snapshot.profile.original_name}</h3>
      <p><b>Etapa atual:</b> {statusLabel(p.current_stage)} · <b>Questões pendentes:</b> {unresolved.length} · <b>Campos:</b> {fields.length}</p>
      {area==="Entrada de dados"&&<>
        <h3>Diagnóstico das abas</h3>
        <table><thead><tr><th>Aba</th><th>Linhas aproximadas</th><th>Campos</th><th>Avisos</th></tr></thead><tbody>
          {snapshot.profile.sheets.map(s=><tr key={s.name}><td>{s.name}</td><td>{s.approximate_row_count}</td><td>{s.column_count}</td><td>{s.warnings.length}</td></tr>)}
        </tbody></table>
        <h3>Campos detectados</h3>
        <div className="table-scroll"><table><thead><tr><th>Campo</th><th>Tipo</th><th>Hipótese</th><th>Confiança</th></tr></thead><tbody>
          {fields.map(f=><tr key={f.sheet+f.technical_name}><td>{f.original_name}</td><td>{f.detected_type}</td><td>{f.semantic_role_candidate}</td><td>{Math.round(f.semantic_role_confidence*100)}%</td></tr>)}
        </tbody></table></div>
        <h3>Qualidade preliminar</h3>
        {snapshot.quality?<p>Relatório gerado com os motores existentes. Situação: {statusLabel(snapshot.quality.status)}. A avaliação depende de confirmação das regras de negócio.</p>:<p>Ainda não existe relatório de qualidade.</p>}
      </>}
      {area==="Conhecimento"&&<>
        <h3>Questionário semântico</h3>
        <p>O motor usa o conhecimento histórico compatível com esta fonte e abre dúvidas quando as evidências são insuficientes.</p>
        {questions.length===0?<p>Nenhuma pergunta obrigatória para esta análise.</p>:questions.map(q=><div key={q.question_id} className="catalogForm">
          <h4>{q.title} — {statusLabel(q.status)}</h4>
          <p>{q.question_text}</p>
          <p className="hint">Aba {q.sheet_name} · Tipo {q.detected_type} · Confiança {Math.round(q.confidence*100)}%</p>
          {pending(q)?<>
            <label>Classificação<select value={answers[q.question_id]?.answer||q.options[0]} onChange={e=>setAnswers(old=>({...old,[q.question_id]:{...old[q.question_id],answer:e.target.value}}))}>
              {q.options.map(o=><option key={o} value={o}>{o}</option>)}
            </select></label>
            <label>Explicação adicional<textarea value={answers[q.question_id]?.custom_answer||""} onChange={e=>setAnswers(old=>({...old,[q.question_id]:{...old[q.question_id],custom_answer:e.target.value}}))}/></label>
            <button onClick={()=>reply(q)} disabled={busy}>Salvar resposta</button>
          </>:<p>Decisão registrada: {statusLabel(q.status)}</p>}
        </div>)}
        <h3>Pesquisa e documentos normativos</h3>
        <p>Pesquisa jurídica assistida por IA e upload de normas ainda não fazem parte do motor recuperado. Precisam de implementação específica, com fontes oficiais, citação e controle de vigência.</p>
      </>}
      {area==="Modelagem"&&<>
        <h3>Pipeline de modelagem recuperado</h3>
        <table><thead><tr><th>Etapa</th><th>Estado desta análise</th></tr></thead><tbody>
          {PIPELINE.map(([label,key])=><tr key={label}><td>{label}</td><td>{key===null?"Perfil disponível":key==="semantic"?unresolved.length?"Perguntas pendentes":"Análise semântica registrada":key==="quality"?snapshot.quality?"Relatório preliminar disponível":"Não iniciado":statusLabel(p[key])}</td></tr>)}
        </tbody></table>
        <p className="hint">Os motores completos de Prepared Dataset, Grain, Dimensional, Star, DDL e ETL estão preservados em core/*. A execução/validação pela interface React será habilitada por etapas, sem aprovar modelos ou grãos automaticamente.</p>
      </>}
    </div>}
  </div>;
}
