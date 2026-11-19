import React,{useEffect,useState} from "react";

/* Catálogo de metadados: sem preencher períodos ausentes com valores fictícios. */
export default function FiscalSourcePicker({year,bimester,onChange}){
 const [catalog,setCatalog]=useState(null),[error,setError]=useState("");
 useEffect(()=>{let active=true;fetch("/api/fiscal-catalog").then(async r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json()}).then(x=>{if(active)setCatalog(x)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[]);
 const available=new Set((catalog?.available||[]).map(x=>x.ano+"-"+x.bimestre));
 const currentAvailable=!year||!bimester||available.has(year+"-"+bimester);
 return <section className="fiscalSourcePicker" aria-label="Fonte de dados fiscais para novos produtos">
  <h3>Fonte de dados · STN/SICONFI</h3>
  <p>RREO — Execução orçamentária de Campo Grande-MS, exercícios 2022 a 2026.</p>
  {error&&<p role="alert">Não foi possível conferir os arquivos disponíveis: {error}</p>}
  <div className="fiscalSourceControls">
   <label>Ano<select value={year||""} onChange={e=>onChange({fiscal_ano:e.target.value,fiscal_bimestre:""})}>
    <option value="">Todos os anos</option>{[2022,2023,2024,2025,2026].map(y=><option key={y} value={String(y)}>{y}</option>)}
   </select></label>
   <label>Bimestre<select value={bimester||""} onChange={e=>onChange({fiscal_bimestre:e.target.value})}>
    <option value="">Todos os bimestres</option>{[1,2,3,4,5,6].map(b=><option key={b} value={String(b)}>{b}º bimestre</option>)}
   </select></label>
  </div>
  <p className="fiscalSourceStatus">{catalog?<>Registros disponíveis: <strong>{available.size} de 30 bimestres previstos</strong>. {currentAvailable?"":"Este período não possui dados validados/importados; 5º bimestre de 2026 pode estar pendente de envio e 6º ainda não está encerrado."}</>:"Consultando cobertura da base fiscal..."}</p>
  <details><summary>Dimensões e medidas existentes</summary>
   <p><b>Dimensões:</b> Ano, Bimestre.</p>
   <ul>{(catalog?.measures||[]).map(m=><li key={m.field}>{m.label}</li>)}</ul>
  </details>
  <p className="fiscalSourceNote">RREO possui valores acumulados por bimestre; não some bimestres. RGF (quadrimestral) terá fonte separada. A seleção inicial será usada ao abrir o editor.</p>
 </section>
}
