"""Pesquisa temática simultânea em portais oficiais selecionados.

O motor consulta páginas e seus links reais; nunca inventa PDFs,
não confunde página de índice com resultado documental, e não alega
cobertura exaustiva de bases com formulários JavaScript.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit, urljoin
import urllib.error
import re
import bi_knowledge_official as base

PORTALS = [
 {"id":"planalto","label":"Planalto — legislação federal","group":"Leis e decretos",
  "url":"https://www4.planalto.gov.br/legislacao/portal-legis/busca-avancada"},
 {"id":"senado","label":"Senado Federal — normas jurídicas","group":"Leis e decretos",
  "url":"https://www25.senado.leg.br/web/atividade/legislacao"},
 {"id":"camara","label":"Câmara dos Deputados — legislação","group":"Leis e decretos",
  "url":"https://www2.camara.leg.br/atividade-legislativa/legislacao/pesquisa"},
 {"id":"lexml","label":"LexML — pesquisa jurídica integrada","group":"Leis e decretos",
  "url":"https://www.lexml.gov.br/"},
 {"id":"tesouro","label":"Tesouro Nacional / Tesouro Transparente","group":"Normas fiscais e manuais",
  "url":"https://www.gov.br/tesouronacional/pt-br"},
 {"id":"siconfi","label":"Siconfi — demonstrativos e guias","group":"Normas fiscais e manuais",
  "url":"https://siconfi.tesouro.gov.br/siconfi/"},
 {"id":"municipio_cg","label":"Campo Grande — legislação municipal","group":"Legislação de Campo Grande e MS",
  "url":"https://www.campogrande.ms.gov.br/transparencia/legislacao-municipal/"},
 {"id":"biblioteca_cg","label":"Biblioteca de Legislação Municipal — Campo Grande","group":"Legislação de Campo Grande e MS",
  "url":"https://biblioteca.campogrande.ms.gov.br/"},
 {"id":"doems","label":"Diário Oficial de Mato Grosso do Sul","group":"Legislação de Campo Grande e MS",
  "url":"https://www.diariooficial.ms.gov.br/"},
 {"id":"tcems","label":"TCE-MS — normas e atos","group":"Legislação de Campo Grande e MS",
  "url":"https://www.tce.ms.gov.br/legislacao"},
]
PORTAL_INDEX={p["id"]:p for p in PORTALS}
EXTRA = [
 ("planalto","Pesquisa avançada — Planalto","legislacao","lei decreto portaria orçamento"),
 ("senado","Pesquisa de normas — Senado","legislacao","lei decreto resolução portaria"),
 ("camara","Legislação — Câmara","legislacao","lei decreto resolução orçamento"),
 ("lexml","Acervo jurídico brasileiro — LexML","legislacao","normas federais estaduais municipais"),
 ("municipio_cg","Legislação municipal — Campo Grande","legislacao","leis decretos portarias municipais"),
 ("biblioteca_cg","Biblioteca municipal de legislação — Campo Grande","legislacao","leis decretos atos municipais"),
 ("doems","Diário Oficial de Mato Grosso do Sul","normas","normas estaduais portarias decretos leis"),
 ("tcems","Atos normativos — TCE-MS","normas","resoluções orientações controle externo fiscalização"),
]
MAX_PAGES=18
MAX_RESULTS=80

def catalog():
    return {"portals":[dict(p) for p in PORTALS],
            "default_ids":[p["id"] for p in PORTALS],
            "note":"Busca em páginas oficiais selecionadas. Sites dinâmicos podem exigir pesquisa no próprio portal."}

def portal_for(url):
    host=(urlsplit(url).hostname or "").lower()
    if "siconfi" in host or "manualsiconfi" in host:return "siconfi"
    if "planalto" in host:return "planalto"
    if "tesouro" in host or "gov.br/tesouronacional" in url:return "tesouro"
    if "senado" in host:return "senado"
    if "camara" in host:return "camara"
    if "lexml" in host:return "lexml"
    return ""

def gather(project_id,topic,categories,scope,portals=None,fetch=None,ai_terms=None):
    if not isinstance(topic,str) or not 3<=len(topic.strip())<=180:
        raise ValueError("Informe um tema de 3 a 180 caracteres")
    if (not isinstance(categories,list) or not categories or
        any(not isinstance(x,str) for x in categories) or
        set(categories)-base._VALID_CATEGORY):
        raise ValueError("Escolha os tipos documentais")
    if portals is None: selected=set(PORTAL_INDEX)
    elif (not isinstance(portals,list) or not portals or
          any(not isinstance(x,str) for x in portals) or
          len(portals)!=len(set(portals)) or set(portals)-set(PORTAL_INDEX)):
        raise ValueError("Escolha fontes oficiais válidas")
    else:selected=set(portals)
    base.projects.get(project_id)
    if fetch is None:fetch=base.read_official
    q=base.terms(topic+" "+(scope or ""))
    if ai_terms is None:extra,ai_status=base.optional_local_ai_terms(topic)
    else:extra,ai_status=ai_terms,"Termos auxiliares do teste"
    q=list(dict.fromkeys(q+extra))[:28]
    entries=[]
    for title,url,source,kind,context in base.SEEDS:
        pid=portal_for(url)
        if pid:entries.append((pid,title,url,source,kind,context))
    for pid,title,kind,context in EXTRA:
        portal=PORTAL_INDEX[pid]
        entries.append((pid,title,portal["url"],portal["label"],kind,context))
    entries=[row for row in entries if row[0] in selected and
             (row[4] in categories or "sites_oficiais" in categories or
              (row[4]=="manuais" and "normas" in categories))]
    found={}
    reports={k:{"id":k,"label":PORTAL_INDEX[k]["label"],
                "pages":0,"results":0,"status":"SEM_PAGINA_ELEGIVEL"}
             for k in sorted(selected)}
    for pid,title,url,source,kind,context in entries:
        if not base.allowed_url(url):continue
        item=base.candidate(title,url,source,kind,url,context,q)
        if item and item["score"]>0 and (
           item["category"] in categories or "sites_oficiais" in categories):
            item["portal_id"]=pid
            found[item["id"]]=item
    grouped={}
    for row in entries:
        if not urlsplit(row[2]).path.lower().endswith(".pdf"):
            grouped.setdefault(row[0],[]).append(row)
    to_visit=[]
    for pid in sorted(selected):
        ordered=sorted(grouped.get(pid,[]),key=lambda x:-base.score(x[1],x[2],x[5],q))
        if ordered:to_visit.append(ordered[0])
        grouped[pid]=ordered[1:]
    to_visit+=sorted([r for rows in grouped.values() for r in rows],
                     key=lambda x:-base.score(x[1],x[2],x[5],q))
    to_visit=to_visit[:MAX_PAGES]
    warnings=[]
    def visit(row):
        pid,title,url,source,kind,context=row
        try:
            data,final,content_type=fetch(url,base.MAX_HTML)
            if data.lstrip().startswith(b"%PDF-"):return pid,[],None
            if b"<" not in data[:250]:return pid,[],"Resposta sem HTML consultável"
            parser=base.ExtractLinks()
            parser.feed(data.decode("utf-8","replace"))
            output=[]
            for href,label in parser.links[:400]:
                destination=urljoin(final,href).split("#")[0]
                if not label or not base.allowed_url(destination):continue
                text=base.normalize(label+" "+destination)
                if not any(word in text for word in base._OFFICIAL_KEYWORDS):continue
                item=base.candidate(label,destination,source,kind,url,"",q)
                if not item or item["score"]<=0:continue
                if item["category"] not in categories and "sites_oficiais" not in categories:continue
                item["portal_id"]=pid
                output.append(item)
            return pid,output,None
        except (OSError,ValueError,UnicodeError,urllib.error.URLError) as exc:
            return pid,[],str(exc)[:110]
    with ThreadPoolExecutor(max_workers=6) as executor:
        for future in as_completed([executor.submit(visit,row) for row in to_visit]):
            pid,items,error=future.result()
            reports[pid]["pages"]+=1
            if error:
                reports[pid]["status"]="INDISPONIVEL"
                warnings.append(PORTAL_INDEX[pid]["label"]+": "+error)
            else:reports[pid]["status"]="CONSULTADO"
            for item in items:
                prev=found.get(item["id"])
                if prev is None or item["score"]>prev["score"]:
                    found[item["id"]]=item
    rows=sorted(found.values(),key=lambda r:(
         -r["score"],0 if r["category"] in ("legislacao","normas") else 1,
         not r["downloadable"],r["title"]))[:MAX_RESULTS]
    for item in rows:
        reports[item["portal_id"]]["results"]+=1
    return {"topic":topic.strip(),"scope":scope or "",
            "sources":rows,"selected_portals":sorted(selected),
            "portal_report":[reports[k] for k in sorted(reports)],
            "provider":"Portais oficiais selecionados","ai_status":ai_status,
            "warnings":list(dict.fromkeys(warnings))[:20],
            "scope_note":"Busca em páginas e links dos portais selecionados, até 18 páginas por rodada. Não cobre integralmente bases que exigem pesquisa interna ou JavaScript.",
            "searched_at":base.now()}
