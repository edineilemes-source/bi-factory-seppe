"""Pesquisa auditável de documentos oficiais para o módulo Conhecimento.

Não depende de IA paga nem mistura dados de projetos. A IA local (Ollama, MIT)
é opt-in; só sugere termos de pesquisa, nunca cria uma fonte. O catálogo das
fontes usa HTML/PDF real encontrado nas páginas oficiais em tempo de execução.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import tempfile
from urllib.parse import urlsplit, urljoin, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler
import urllib.error
import unicodedata
from xml.etree import ElementTree
from uuid import uuid4

import bi_factory_projects as projects
from bi_knowledge_federated import SOURCE_GROUPS, EXTRA_SEEDS, source_group, lexml_documents, tesouro_search_seed

MAX_DOCUMENT = 25 * 1024 * 1024
MAX_HTML = 1_500_000
MAX_RESULTS = 75
MAX_REQUESTS = 12
HOST_SUFFIXES = (".gov.br", ".leg.br")
STOP = set("a as o os um uma e de da do das dos em para por que com sobre na no nas nos seu sua"
           " regras documentos leis normas manuais tudo assunto brasileiro federal municipal".split())
CONTEXT = {
 "empenho": ("despesa", "orcamentaria", "mcasp", "lei 4320"),
 "capag": ("capacidade de pagamento", "poupanca corrente", "liquidez relativa", "endividamento"),
 "poupanca": ("corrente", "capag", "despesa receita corrente"),
 "liquidacao": ("despesa", "mcasp", "lei 4320"),
 "receita": ("orcamentaria", "mcasp", "rreo"),
 "despesa": ("orcamentaria", "mcasp", "rreo"),
 "balanco": ("demonstracoes contabeis", "mcasp", "dca"),
 "prestacao": ("contas", "siconfi", "dca", "rgf"),
 "contas": ("dca", "siconfi", "mcap", "mdf"),
 "resultado": ("orcamentario", "rreo", "mdf"),
 "rreo": ("mdf", "siconfi", "demonstrativos fiscais"),
 "rgf": ("mdf", "siconfi", "gestao fiscal"),
 "dca": ("siconfi", "contas anuais"),
}
SEEDS = (
 ("MCASP · 11ª edição", "https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/manuais/manual-de-contabilidade-aplicada-ao-setor-publico-mcasp-1", "Tesouro Nacional", "manuais",
  "contabilidade despesa receita empenho liquidacao balanco demonstracoes contabeis mcasp"),
 ("MDF · manual e edições", "https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/manuais/manual-de-demonstrativos-fiscais-mdf", "Tesouro Nacional", "manuais",
  "rreo rgf prestacao contas demonstrativos fiscais resultado orcamentario mdf"),
 ("Siconfi · guias de preenchimento", "https://siconfi.tesouro.gov.br/siconfi/pages/public/conteudo/conteudo.jsf?id=42",
  "Tesouro Nacional / Siconfi", "manuais", "dca rgf rreo declaracao contas anuais preenchimento"),
 ("Siconfi · documentação e tabelas", "https://siconfi.tesouro.gov.br/siconfi/pages/public/conteudo/conteudo.jsf?id=46903",
  "Tesouro Nacional / Siconfi", "manuais", "dca rgf rreo declaracao contas anuais tabela fatos"),
 ("PCASP · Plano de Contas", "https://www.gov.br/tesouronacional/pt-br/contabilidade-e-custos/federacao/plano-de-contas-aplicado-ao-setor-publico-pcasp-1",
  "Tesouro Nacional", "normas", "plano contas contabilidade pcasp natureza classificacao"),
 ("Lei 4.320/1964 · texto compilado", "https://www.planalto.gov.br/ccivil_03/leis/l4320compilado.htm",
  "Presidência da República / Planalto", "legislacao", "receita despesa empenho liquidacao pagamento balanco orcamento"),
 ("Lei Complementar 101/2000 · LRF", "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp101.htm",
  "Presidência da República / Planalto", "legislacao", "gestao fiscal prestacao contas rreo rgf transparencia receitas despesas"),
 ("Manual completo do Siconfi · PDF", "https://manualsiconfi.tesouro.gov.br/manual_completo.pdf",
  "Tesouro Nacional / Siconfi", "manuais", "siconfi declaracao contas anuais dca manual"),
 ("Manual de Análise Fiscal 2026 — CAPAG, Receita e Despesa",
  "https://cdn.tesouro.gov.br/sistemas-internos/apex/producao/sistemas/thot/arquivos/publicacoes/54134_1693346/Manual%20de%20an%C3%A1lise%20fiscal%20-%20Vers%C3%A3o%20Final%202026.pdf",
  "Tesouro Nacional / Manual oficial 2026", "manuais",
  "capag capacidade pagamento poupanca corrente endividamento liquidez receitas despesas 2026"),
 ("Manual de Análise Fiscal 2026 — publicação",
  "https://www.tesourotransparente.gov.br/publicacoes/manual-de-analise-fiscal-de-estados-e-municipios/2026/114?ano_selecionado=2026",
  "Tesouro Nacional / Tesouro Transparente", "manuais",
  "capag capacidade pagamento poupanca corrente endividamento liquidez manual 2026"),
 ("CAPAG · metodologia vigente e indicadores", "https://www.tesourotransparente.gov.br/temas/estados-e-municipios/capacidade-de-pagamento-capag",
  "Tesouro Nacional / Tesouro Transparente", "normas",
  "capag capacidade pagamento municipios endividamento poupanca corrente liquidez relativa"),
 ("CAPAG · metodologia da Portaria Normativa 1.583/2023", "https://www.gov.br/tesouronacional/pt-br/noticias/ministerio-da-fazenda-altera-metodologia-para-calculo-da-analise-da-capacidade-de-pagamento-capag",
  "Tesouro Nacional", "legislacao",
  "capag capacidade pagamento portaria 1583 2023 indicador endividamento poupanca corrente"),
)
_OFFICIAL_KEYWORDS = ("manual","mcas","mdf","prestacao","contas","rreo","rgf","dca",
 "empenho","liquidacao","receita","despesa","orcament","balanc","portaria","norma",
 "lei","resoluc","anexo","orientac","preenchimento","instruc","siconfi","fiscal",
 "sintese","guia","demonstrativ","plano","pcasp","relatorio","publicac")
_VALID_CATEGORY = {"legislacao","normas","manuais","sites_oficiais","metodos"}

def now():
    return datetime.now(timezone.utc).isoformat()

def normalize(value):
    unaccented=unicodedata.normalize("NFKD",str(value))
    return "".join(c for c in unaccented if not unicodedata.combining(c)).lower()

def terms(topic):
    words=[w for w in re.findall(r"[a-z0-9]+",normalize(topic))
           if len(w)>=3 and w not in STOP]
    out=list(dict.fromkeys(words))
    for w in words:
        out.extend(CONTEXT.get(w,()))
    return list(dict.fromkeys(out))[:22]

def allowed_url(url):
    try:
        p=urlsplit(url)
        if (p.scheme!="https" or not p.hostname or p.username or p.password
            or p.port not in (None,443) or len(url)>1500):
            return False
        host=p.hostname.lower().rstrip(".")
        return (host.endswith(HOST_SUFFIXES) and host not in
                {"localhost","127.0.0.1"})
    except (ValueError,AttributeError):
        return False

class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("Redirecionamento fora de portal oficial")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def read_official(url,limit,accept="text/html,application/pdf"):
    if not allowed_url(url):
        raise ValueError("Apenas URLs HTTPS de domínios oficiais .gov.br e .leg.br")
    opener=build_opener(OfficialRedirect())
    req=Request(url,headers={"User-Agent":"BI-Factory-SEPPE-Knowledge/1.0 (pesquisa documental)",
                             "Accept":accept})
    with opener.open(req,timeout=8) as resp:
        if not allowed_url(resp.geturl()):
            raise ValueError("Origem final fora de domínio oficial")
        size=resp.headers.get("Content-Length")
        if size and int(size)>limit:
            raise ValueError("Documento acima do limite de tamanho")
        data=resp.read(limit+1)
        if len(data)>limit:
            raise ValueError("Arquivo acima do limite de tamanho")
        return data,resp.geturl(),resp.headers.get("Content-Type","")

class ExtractLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[]
        self.href=None
        self.label=[]
        self.title=""
        self.title_mode=False

    def handle_starttag(self,tag,attrs):
        att=dict(attrs)
        if tag=="a":
            self.href=att.get("href")
            self.label=[]
        if tag in ("iframe","embed"):
            src=att.get("src")
            if src:self.links.append((src,"download PDF iframe"))
        if tag=="title":
            self.title_mode=True

    def handle_data(self,text):
        if self.href is not None:
            self.label.append(text)
        if self.title_mode:
            self.title+=text

    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            label=re.sub(r"\s+"," "," ".join(self.label)).strip()
            self.links.append((self.href,label[:210]))
            self.href=None
            self.label=[]
        if tag=="title":self.title_mode=False

def classify(label,url,default):
    norm=normalize(label+" "+url)
    if any(t in norm for t in ("lei ","portaria","decreto","legislacao","in.gov.br")):
        return "legislacao"
    if any(t in norm for t in ("instrucao","resolucao","norma","pcasp")):
        return "normas"
    if any(t in norm for t in ("manual","guia","mcas","mdf","orientac","preenchimento")):
        return "manuais"
    return default

def score(title,url,context,query_terms):
    haystack=normalize(title+" "+url+" "+context)
    exact=sum(5 for t in query_terms if " " in t and t in haystack)
    partial=sum(3 for t in query_terms if " " not in t and t in haystack)
    return exact+partial

def candidate(title,url,source,kind,origin,context,query_terms):
    if not allowed_url(url):
        return None
    title=(title.strip() or unquote(urlsplit(url).path.rsplit("/",1)[-1]))[:210]
    if not title:return None
    lower_label=normalize(title)
    host=urlsplit(url).hostname or ""
    # Endereços THOT /publicacao-anexo/<id> frequentemente entregam
    # página HTML. Só afirmar PDF quando o caminho termina em .pdf.
    # Confirmação definitiva dos bytes ocorre durante a incorporação.
    ispdf=urlsplit(url).path.lower().endswith(".pdf")
    version=None
    if "manual-de-demonstrativos-fiscais" in origin:
        if "16ª" in title or "16a" in lower_label:
            version="MDF 16ª edição — aplicável a partir de 2027"
        elif "15ª" in title or "15a" in lower_label:
            version="MDF 15ª edição — vigente para 2026"
    if "manual-de-contabilidade" in origin and ("11ª" in title or "11a" in lower_label):
        version="MCASP 11ª edição — válido a partir de 2025"
    return {"id":hashlib.sha256(url.encode("utf-8")).hexdigest()[:24],
            "title":title,"url":url,"source":source,
            "category":classify(title,url,kind),"format":"PDF" if ispdf else "LINK",
            "downloadable":ispdf,"origin":origin,"score":score(title,url,context,query_terms),
            "validity_note":version}

def optional_local_ai_terms(topic):
    """Only opt-in, local loopback. No names, files or documents sent to cloud."""
    model=os.environ.get("BI_KNOWLEDGE_OLLAMA_MODEL","").strip()
    if not model:return [],"Pesquisa oficial sem IA; IA local não configurada"
    address=os.environ.get("BI_KNOWLEDGE_OLLAMA_URL","http://127.0.0.1:11434")
    p=urlsplit(address)
    if p.scheme!="http" or p.hostname not in ("127.0.0.1","localhost") or p.port not in (11434,):
        return [],"Endereço de IA local recusado por segurança"
    prompt=("Liste no máximo 5 palavras-chave sobre legislação de finanças públicas, "
            "no formato JSON {\"termos\":[...]}. Não invente fontes nem números de normas. "
            "Tema: "+topic[:250])
    body=json.dumps({"model":model,"prompt":prompt,"stream":False,
                     "format":"json","options":{"num_predict":110}}).encode()
    try:
        req=Request(address.rstrip("/")+"/api/generate",data=body,
                    headers={"Content-Type":"application/json"},method="POST")
        with build_opener().open(req,timeout=5) as response:
            if response.status!=200:raise ValueError("Falha na IA local")
            result=json.loads(response.read(30_000))
        terms_=[normalize(t) for t in json.loads(result.get("response","{}")).get("termos",[])
                if isinstance(t,str) and len(t)<50]
        return terms_[:5],"Ollama local ("+model+") · termos auxiliares, fontes verificadas"
    except (OSError,ValueError,KeyError,TypeError,urllib.error.URLError):
        return [],"IA local indisponível; pesquisa oficial realizada sem IA"

def discover(project_id,topic,categories,scope,fetch=read_official,ai_terms=None,sources=None):
    if not isinstance(topic,str) or not 3<=len(topic.strip())<=180:
        raise ValueError("Informe um tema de 3 a 180 caracteres")
    if (not isinstance(categories,list) or not categories or
        set(categories)-_VALID_CATEGORY):
        raise ValueError("Selecione os tipos de documentos")
    projects.get(project_id)
    selected_groups=set(SOURCE_GROUPS if sources is None else sources)
    if not selected_groups or selected_groups-set(SOURCE_GROUPS):
        raise ValueError('Selecione uma fonte oficial válida')
    query_terms=terms(topic+" "+(scope or ""))
    focused_capag=("capag" in normalize(topic) or
                   "capacidade de pagamento" in normalize(topic) or
                   "poupanca corrente" in normalize(topic))
    if ai_terms is None: extra,ai_status=optional_local_ai_terms(topic)
    else:extra,ai_status=ai_terms,"IA: termos auxiliares informados no teste"
    query_terms=list(dict.fromkeys(query_terms+extra))[:28]
    seen={}
    warnings=[]
    attempts=0
    seeded=list(SEEDS)+list(EXTRA_SEEDS)+[tesouro_search_seed(topic)]
    # Primeiro uma página por base; depois prioriza relevância entre as restantes.
    seeded.sort(key=lambda e:(-score(e[0],e[1],e[4],query_terms),e[0]))
    first=[];remaining=[];visited_groups=set()
    for entry in seeded:
        group=source_group(entry[1])
        if group not in visited_groups:
            visited_groups.add(group);first.append(entry)
        else:remaining.append(entry)
    for title,url,source,kind,context in first+remaining:
        group=source_group(url)
        if group not in selected_groups:continue
        # CAPAG: fontes específicas. Evita lotar a página com RGF/DCA
        # de outros assuntos e anos, embora eles sejam portais oficiais.
        if focused_capag and not any(
          x in normalize(title+" "+url) for x in
          ("capag","capacidade-de-pagamento","manual-de-analise-fiscal")):
            continue
        if (kind not in categories and "sites_oficiais" not in categories and
            not (kind=="manuais" and "normas" in categories)):
            continue
        original=candidate(title,url,source,kind,url,context,query_terms)
        if original and original["score"]>0 and (kind in categories or "sites_oficiais" in categories):
            original["source_group"]=group
            seen[original["id"]]=original
        if urlsplit(url).path.lower().endswith(".pdf") or attempts>=MAX_REQUESTS:
            continue
        attempts+=1
        try:
            data,final,ctype=fetch(url,MAX_HTML)
            if data.lstrip().startswith(b"%PDF-"):continue
            # HTMLParser does not execute JavaScript; generated links may be unavailable.
            if b"<" not in data[:200]:continue
            page=ExtractLinks()
            page.feed(data.decode("utf-8","replace"))
            for href,label in page.links[:300]:
                absolute=urljoin(final,href).split("#")[0]
                if not allowed_url(absolute) or not label:continue
                norm=normalize(label+" "+absolute)
                if not any(word in norm for word in _OFFICIAL_KEYWORDS):continue
                item=candidate(label,absolute,source,kind,url,"",query_terms)
                if not item:continue
                if item["category"] not in categories and "sites_oficiais" not in categories:
                    continue
                if focused_capag and not any(term in normalize(label+" "+absolute)
                   for term in ("capag","capacidade de pagamento","analise fiscal","poupanca corrente")):
                    continue
                if item["score"]==0:continue
                item["source_group"]=group
                old=seen.get(item["id"])
                if not old or item["score"]>old["score"]:
                    seen[item["id"]]=item
        except (OSError,ValueError,UnicodeError,urllib.error.URLError) as error:
            warnings.append(source+": "+str(error)[:90])
    # LexML: consulta federada real; indisponibilidade não interrompe as demais fontes.
    if "lexml" in selected_groups:
        try:
            for title,url,source,kind,origin,context in lexml_documents(
                topic,fetch,allowed_url,MAX_HTML):
                item=candidate(title,url,source,kind,origin,context,query_terms)
                if item and item["score"]>0 and (
                    item["category"] in categories or "sites_oficiais" in categories):
                    item["source_group"]="lexml"
                    seen[item["id"]]=item
        except (OSError,ValueError,UnicodeError,ElementTree.ParseError,urllib.error.URLError) as error:
            warnings.append("LexML: "+str(error)[:120])
    # Atos normativos antes de manuais; dentro de cada grupo, por relevância.
    priority={"legislacao":0,"normas":1,"manuais":2,"metodos":3,"sites_oficiais":4}
    rows=sorted(seen.values(),key=lambda item:(
        priority.get(item["category"],5),-item["score"],
        not item["downloadable"],item["title"]))
    return {"topic":topic.strip(),"scope":scope,"sources":rows[:MAX_RESULTS],
            "provider":"Portais oficiais brasileiros",
            "ai_status":ai_status,
            "warnings":list(dict.fromkeys(warnings))[:12],
            "source_groups":sorted(selected_groups),
            "scope_note":"Pesquisa inicial em portais oficiais selecionados; não equivale a uma busca exaustiva da legislação nacional.",
            "searched_at":now()}

def discover_for_project(payload):
    if not isinstance(payload,dict):raise ValueError("Solicitação inválida")
    pid=payload.get("project_id")
    projects.get(pid)
    topic=payload.get("topic","")
    categories=payload.get("categories",["legislacao","normas","manuais"])
    scope=payload.get("scope","")
    if not isinstance(scope,str) or len(scope)>200:raise ValueError("Abrangência inválida")
    data=discover(pid,topic,categories,scope,sources=payload.get("sources"))
    identity=uuid4().hex
    data["id"]=identity
    data["project_id"]=pid
    with projects.LOCK:
        dest=projects.DIR/pid/"discoveries"/(identity+".json")
        projects._write(dest,data)
        path=projects._sources_path(pid)
        records=projects._read(path,[])
        records.append({"id":identity,"type":"research_result","topic":topic,
                        "scope":scope,"created_at":now(),"status":"Pesquisa realizada — aguardando aprovação",
                        "count":len(data["sources"]),"note":data["scope_note"]})
        projects._write(path,records)
    return data

def approve_for_project(payload):
    """Explicit review. Only previously discovered official links are accepted."""
    if not isinstance(payload,dict):raise ValueError("Solicitação inválida")
    pid=payload.get("project_id")
    projects.get(pid)
    discovery_id=payload.get("discovery_id","")
    chosen=payload.get("source_ids",[])
    if (not isinstance(discovery_id,str) or not re.fullmatch(r"[0-9a-f]{32}",discovery_id)
        or not isinstance(chosen,list) or not 1<=len(chosen)<=10
        or len(set(chosen))!=len(chosen)):
        raise ValueError("Escolha até 10 documentos da pesquisa apresentada")
    original=projects.DIR/pid/"discoveries"/(discovery_id+".json")
    discovery=projects._read(original,None)
    if not isinstance(discovery,dict) or discovery.get("project_id")!=pid:
        raise ValueError("Pesquisa não encontrada neste projeto")
    permitted={c["id"]:c for c in discovery.get("sources",[])}
    if any(i not in permitted for i in chosen):
        raise ValueError("Documento não pertence à pesquisa aprovada")
    imported,failed=[],[]
    for source_id in chosen:
        item=permitted[source_id]
        try:
            url=item["url"]
            if not allowed_url(url):raise ValueError("Fonte oficial inválida")
            data=None
            ext=""
            if item["downloadable"]:
                data,final,mime=read_official(url,MAX_DOCUMENT,"application/pdf")
                if not data.startswith(b"%PDF-"):
                    raise ValueError("O portal retornou HTML ou outro formato, não um PDF. Consulte o link oficial; nada foi gravado.")
                ext=".pdf"
            digest=hashlib.sha256(data).hexdigest() if data is not None else None
            with projects.LOCK:
                knowledge=projects._sources_path(pid)
                existing=projects._read(knowledge,[])
                if any(e.get("source_url")==url or (digest and e.get("sha256")==digest)
                       for e in existing if e.get("type") in ("document","official_reference")):
                    imported.append({"title":item["title"],"status":"já consta no acervo"})
                    continue
                target=None
                if data is not None:
                    target=projects.DIR/pid/"originals"/(digest+ext)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():
                        fd,tmp=tempfile.mkstemp(prefix=".official-",dir=target.parent)
                        try:
                            with os.fdopen(fd,"wb") as f:
                                f.write(data);f.flush();os.fsync(f.fileno())
                            os.chmod(tmp,0o600)
                            os.replace(tmp,target)
                        finally:
                            if os.path.exists(tmp):os.unlink(tmp)
                entry={"id":str(uuid4()),
                       "type":"document" if data is not None else "official_reference",
                       "title":item["title"],"source":item["source"],
                       "source_url":url,"source_page":item["origin"],
                       "reference":"","category":item["category"],
                       "status":"PDF original armazenado" if data else "Referência oficial catalogada",
                       "filename":target.name if target else None,
                       "relative_path":str(Path("storage/working/projects")/pid/"originals"/target.name) if target else None,
                       "sha256":digest,
                       "size_bytes":len(data) if data is not None else None,
                       "subject":discovery.get("topic"),"scope":discovery.get("scope"),
                       "discovered_at":discovery["searched_at"],"approved_at":now(),
                       "validity_note":item.get("validity_note"),
                       "discovery_id":discovery_id}
                existing.append(entry)
                projects._write(knowledge,existing)
                imported.append({"title":item["title"],"status":entry["status"],"item":entry})
        except (OSError,ValueError,urllib.error.URLError) as error:
            failed.append({"title":item["title"],"error":str(error)[:180]})
    return {"ok":not failed,"imported":imported,"failed":failed,
            "note":"PDFs aprovados ficam em storage/working/projects/<projeto>/originals. Não são enviados automaticamente ao Git remoto."}


MAX_AUTO_FILES=5
MAX_AUTO_PAGES=4

def _real_pdf(url, origin, fetch=read_official):
    """Locate actual PDF bytes in an official portal, not just a .pdf-looking URL.

    Follows HTML download links and iframe sources on official domains only,
    bounded to three pages. No JS execution, cookies, sign-in, or crawling
    arbitrary external sites.
    """
    queue=[url]
    visited=set()
    pages=0
    while queue and pages<3:
        current=queue.pop(0)
        if current in visited or not allowed_url(current):continue
        visited.add(current);pages+=1
        raw,final,ctype=fetch(current,MAX_DOCUMENT)
        if raw.lstrip().startswith(b"%PDF-"):
            return raw,final,ctype
        if len(raw)>MAX_HTML or b"<" not in raw[:500]:
            continue
        page=ExtractLinks()
        page.feed(raw.decode("utf-8","replace"))
        # Iframes often contain the actual download, especially on THOT.
        # The extended parser collects iframe src alongside anchor links.
        links=list(page.links)
        for href,label in links[:200]:
            absolute=urljoin(final,href).split("#")[0]
            if not allowed_url(absolute) or absolute in visited:continue
            hint=normalize(label+" "+absolute)
            if (absolute.lower().split("?")[0].endswith(".pdf") or
                "download" in hint or "baixar" in hint or
                "publicacao/" in absolute or "publicacao-anexo/" in absolute):
                queue.append(absolute)
                if len(queue)>10:break
    return None,None,None

def auto_download_for_project(payload,fetch=read_official):
    """One click: fetch and archive real PDFs; never require manual site visits.

    Only sources already found by a project-scoped discovery are eligible.
    The user may inspect/delete PDFs afterward. Existing files are untouched.
    """
    if not isinstance(payload,dict):raise ValueError("Solicitação inválida")
    pid=payload.get("project_id")
    projects.get(pid)
    discovery_id=payload.get("discovery_id","")
    if not isinstance(discovery_id,str) or not re.fullmatch(r"[0-9a-f]{32}",discovery_id):
        raise ValueError("Pesquisa inválida")
    number=payload.get("max_files",MAX_AUTO_FILES)
    if type(number)!=int or not 1<=number<=MAX_AUTO_FILES:
        raise ValueError("Máximo de cinco PDFs por rodada")
    path=projects.DIR/pid/"discoveries"/(discovery_id+".json")
    found=projects._read(path,None)
    if not isinstance(found,dict) or found.get("project_id")!=pid:
        raise ValueError("Pesquisa não encontrada neste projeto")
    topic=normalize(found.get("topic",""))
    capag=any(t in topic for t in ("capag","capacidade de pagamento","poupanca corrente"))
    sources=found.get("sources",[])
    if not isinstance(sources,list):raise ValueError("Resultado inválido")
    documents=[]
    pages=0
    examined=0
    failures=[]
    for item in sources:
        if len(documents)>=number:break
        url=item.get("url","")
        if not allowed_url(url):continue
        label=normalize(item.get("title","")+" "+url)
        if capag and not any(t in label for t in
          ("capag","analise fiscal","capacidade de pagamento","poupanca")):
            continue
        direct=item.get("downloadable") is True
        if not direct and pages>=MAX_AUTO_PAGES:continue
        if not direct:
            pages+=1
        examined+=1
        try:
            raw,final,mime=_real_pdf(url,item.get("origin",url),fetch=fetch)
            if not raw:
                # HTML remains a reference; cannot pretend it is downloaded.
                continue
            digest=hashlib.sha256(raw).hexdigest()
            entry=None
            with projects.LOCK:
                knowledge=projects._sources_path(pid)
                existing=projects._read(knowledge,[])
                seen=next((e for e in existing if
                   not e.get("deleted_at") and e.get("type")=="document" and
                   (e.get("sha256")==digest or e.get("source_url")==final)),None)
                if seen:
                    documents.append({"title":seen.get("title"),"status":"já armazenado",
                        "id":seen["id"]})
                    continue
                # Exclusão é uma decisão do usuário: nova pesquisa não deve
                # reimportar automaticamente documento que ele descartou.
                discarded=next((e for e in existing if
                    e.get("deleted_at") and e.get("type")=="document" and
                    (e.get("sha256")==digest or e.get("source_url")==final)),None)
                if discarded:
                    documents.append({"title":discarded.get("title"),
                        "status":"descartado anteriormente; restaure na lixeira",
                        "id":discarded["id"]})
                    continue
                target=projects.DIR/pid/"originals"/(digest+".pdf")
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():
                    fd,tmp=tempfile.mkstemp(prefix=".auto-official-",dir=target.parent)
                    try:
                        with os.fdopen(fd,"wb") as writer:
                            writer.write(raw)
                            writer.flush()
                            os.fsync(writer.fileno())
                        os.chmod(tmp,0o600)
                        os.replace(tmp,target)
                    finally:
                        if os.path.exists(tmp):os.unlink(tmp)
                entry={"id":str(uuid4()),"type":"document",
                    "title":item.get("title","Documento oficial")[:210],
                    "source":item.get("source","Fonte oficial"),
                    "source_url":final,"source_page":url,
                    "category":item.get("category","manuais"),
                    "status":"PDF original armazenado — download automático",
                    "filename":target.name,
                    "relative_path":str(Path("storage/working/projects")/pid/"originals"/target.name),
                    "sha256":digest,"size_bytes":len(raw),
                    "subject":found.get("topic"),"scope":found.get("scope"),
                    "discovered_at":found.get("searched_at"),"approved_at":now(),
                    "validity_note":item.get("validity_note"),
                    "discovery_id":discovery_id,"import_method":"automatic_official"}
                existing.append(entry)
                projects._write(knowledge,existing)
            documents.append({"title":entry["title"],"status":"baixado",
                "id":entry["id"],"size_bytes":len(raw)})
        except (ValueError,OSError,urllib.error.URLError) as err:
            failures.append({"title":item.get("title","Fonte oficial"),
                "error":str(err)[:140]})
    return {"project_id":pid,"discovery_id":discovery_id,
        "downloaded":sum(x["status"]=="baixado" for x in documents),
        "existing":sum(x["status"]=="já armazenado" for x in documents),
        "documents":documents,"examined":examined,
        "failed":failures[:5],
        "note":"Arquivos efetivos na Biblioteca do projeto. Abra e exclua os que não servirão; leitura pela IA continua opcional."}
