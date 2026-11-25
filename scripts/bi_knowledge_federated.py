"""Fontes oficiais federadas para pesquisa normativa na BI Factory SEPPE.

Metadados dos portais sao pontos de entrada, nao respostas ficticias.
A API LexML e consultada em tempo real; fontes bloqueadas sao reportadas.
Dependencias: somente biblioteca padrao Python, sem chaves ou scraping privado.
"""
from urllib.parse import urlsplit, urlencode
from xml.etree import ElementTree

SOURCE_GROUPS = ("tesouro", "federal", "lexml", "ms", "campo_grande")
EXTRA_SEEDS = (
 ("CAPAG — Portaria Normativa MF nº 1.583/2023 (texto do Diário Oficial da União)",
  "https://www.in.gov.br/en/web/dou/-/portaria-normativa-mf-n-1.583-de-13-de-dezembro-de-2023-530597625",
  "Diário Oficial da União / Ministério da Fazenda", "legislacao",
  "capag capacidade pagamento portaria 1583 poupanca corrente liquidez endividamento"),
 ("CAPAG — legislação aplicável e alterações da Portaria 1.583/2023",
  "https://www.gov.br/tesouronacional/pt-br/divida-publica-federal/garantias-da-uniao/legislacao-sobre-garantias-da-uniao",
  "Tesouro Nacional / legislação", "legislacao",
  "capag capacidade pagamento portaria 1583 1764 2024 2025 2026 garantias"),
 ("CAPAG — legislação dos programas fiscais",
  "https://www.tesourotransparente.gov.br/paginas-complementares/programas-de-acompanhamento-fiscal/legislacao-relacionada-aos-programas-fiscais-dos-entes-subnacionais",
  "Tesouro Transparente / legislação", "legislacao",
  "capag capacidade pagamento portaria 1583 2023 normas resolucoes"),
 ("Portal da Legislação Federal — pesquisa normativa",
  "https://www4.planalto.gov.br/legislacao/portal-legis/busca-avancada",
  "Presidência da República", "legislacao",
  "lei decreto legislacao federal normas orcamento receita despesa"),
 ("Diário Oficial da União — atos normativos",
  "https://www.in.gov.br/", "Imprensa Nacional / DOU", "legislacao",
  "diario oficial uniao lei decreto portaria resolucao normas"),
 ("TCE-MS — atos normativos",
  "https://www.tce.ms.gov.br/legislacao", "Tribunal de Contas de MS", "normas",
  "tribunal contas Mato Grosso Sul resolucoes despesa receita fiscal"),
 ("Governo de Mato Grosso do Sul — legislação",
  "https://www.segov.ms.gov.br/legislacao/",
  "Secretaria de Governo de MS", "legislacao",
  "mato grosso sul estadual leis decretos normas orcamento"),
 ("Diário Oficial de Mato Grosso do Sul",
  "https://www.diariooficial.ms.gov.br/",
  "Imprensa Oficial de MS", "legislacao",
  "mato grosso sul diario oficial lei decreto portaria"),
 ("Assembleia Legislativa de MS — legislação",
  "https://al.ms.gov.br/Paginas/46/biblioteca",
  "Assembleia Legislativa de MS", "legislacao",
  "mato grosso sul legislacao leis estaduais resolucoes"),
 ("DIOGRANDE — Diário Oficial de Campo Grande",
  "https://diogrande.campogrande.ms.gov.br/",
  "Município de Campo Grande", "legislacao",
  "campo grande ms legislacao municipal diogrande lei decreto portaria"),
)

def source_group(url):
    parsed=urlsplit(url)
    host=(parsed.hostname or "").lower()
    if host.endswith("lexml.gov.br"):return "lexml"
    if "campogrande.ms.gov.br" in host or host=="capital.ms.gov.br":return "campo_grande"
    if host.endswith(".ms.gov.br") or host=="al.ms.gov.br":return "ms"
    if ("tesouro" in host or "siconfi" in host or
        "/tesouronacional/" in parsed.path):return "tesouro"
    return "federal"

def lexml_documents(topic, fetch, allowed_url, max_html):
    """Registros reais do webservice SRU do LexML; ignora URNs sem URL oficial."""
    url="https://www.lexml.gov.br/busca/SRU?"+urlencode({
        "operation":"searchRetrieve","version":"1.1","query":topic[:100],
        "maximumRecords":"25"})
    raw,_,_=fetch(url,max_html)
    tree=ElementTree.fromstring(raw)
    results=[]
    for record in tree.iter():
        if record.tag.rsplit("}",1)[-1]!="record":continue
        fields={}
        for node in record.iter():
            name=node.tag.rsplit("}",1)[-1].lower()
            if name in ("title","identifier","relation") and node.text:
                fields.setdefault(name,[]).append(node.text.strip())
        titles=fields.get("title",[])
        links=[link for key in ("relation","identifier")
               for link in fields.get(key,[])
               if link.startswith("https://") and allowed_url(link)]
        if titles and links:
            results.append((titles[0],links[0],"LexML / fonte oficial",
                            "legislacao",url,topic))
        if len(results)>=25:break
    return results

def tesouro_search_seed(topic):
    """URL de busca textual baseada em tema, sem interpolar hosts do usuário."""
    url="https://www.gov.br/tesouronacional/pt-br/@@search?"+urlencode(
        {"SearchableText":topic[:120]})
    return ("Tesouro Nacional — pesquisa textual: "+topic[:100],url,
            "Tesouro Nacional / índice", "normas", topic)
