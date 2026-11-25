"""Testes offline: descoberta oficial, isolamento por projeto, autorização e PDFs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bi_factory_projects as projects
import bi_knowledge_official as official

class OfficialKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="bi-knowledge-official-")
        self.previous=projects.DIR,projects.REGISTRY
        projects.DIR=Path(self.temp.name)
        projects.REGISTRY=projects.DIR/"projects.json"
        self.pid=projects.LEGACY_ID

    def tearDown(self):
        projects.DIR,projects.REGISTRY=self.previous
        self.temp.cleanup()

    def test_trusted_official_domains_only(self):
        for url in ("https://www.gov.br/tesouronacional/manual",
                    "https://siconfi.tesouro.gov.br/foo.pdf",
                    "https://www2.camara.leg.br/lei"):
            self.assertTrue(official.allowed_url(url))
        for url in ("https://gov.br.attacker.example/a.pdf",
                    "http://www.gov.br/a.pdf",
                    "https://localhost/file.pdf",
                    "https://127.0.0.1/private.pdf",
                    "file:///etc/passwd",
                    "https://www.gov.br:8443/pdf",
                    "https://www.gov.br@evil.net/pdf"):
            self.assertFalse(official.allowed_url(url),url)

    def test_real_links_only_no_generated_law_urls(self):
        url=official.SEEDS[0][1]
        pdf="https://thot-arquivos.tesouro.gov.br/arquivo/mcasp11.pdf"
        html=('<html><head><title>MCASP</title></head>'
             '<body><a href="'+pdf+'">Manual de Contabilidade Pública 11ª edição</a>'
             '<a href="https://gov.br.falso.com/manual.pdf">Fake PDF</a>'
             '<a href="https://www.gov.br/sobre">Anúncios</a></body></html>').encode()
        def source(url,limit):
            return html,url,"text/html"
        result=official.discover(self.pid,"empenho e despesa pública",
            ["legislacao","normas","manuais","sites_oficiais"],"Brasil",
            fetch=source,ai_terms=[])
        self.assertEqual(result["provider"],"Portais oficiais brasileiros")
        urls=[x["url"] for x in result["sources"]]
        self.assertIn(pdf,urls)
        self.assertNotIn("https://gov.br.falso.com/manual.pdf",urls)
        self.assertTrue(all(official.allowed_url(u) for u in urls))
        self.assertTrue(any(r["title"].startswith("MCASP") for r in result["sources"]))
        self.assertTrue(any(r["downloadable"] for r in result["sources"]))
        self.assertIn("não equivale",result["scope_note"])

    def test_approval_download_sha_dedup_and_provenance(self):
        pid=self.pid
        sample=b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\n%%EOF"
        url="https://manualsiconfi.tesouro.gov.br/manual_completo.pdf"
        info=official.candidate("Manual do Siconfi",url,"Tesouro Nacional",
            "manuais",url,"siconfi contas",["siconfi"])
        saved={"id":"c"*32,"project_id":pid,"searched_at":official.now(),
               "topic":"prestação de contas","sources":[info]}
        disk=projects.DIR/pid/"discoveries"/(saved["id"]+".json")
        projects._write(disk,saved)
        self.assertFalse((projects.DIR/pid/"originals").exists(),
            "Pesquisar não deve baixar nenhum documento")
        with patch.object(official,"read_official",return_value=(sample,url,"application/pdf")) as get:
            request={"project_id":pid,"discovery_id":saved["id"],"source_ids":[info["id"]]}
            result=official.approve_for_project(request)
            self.assertEqual(len(result["imported"]),1)
            self.assertEqual(result["failed"],[])
            get.assert_called_once()
            item=projects.summary(pid)["items"][0]
            self.assertEqual(item["source_url"],url)
            self.assertEqual(item["sha256"],hashlib.sha256(sample).hexdigest())
            self.assertEqual(item["type"],"document")
            self.assertEqual((ROOT/item["relative_path"]).name,
                             hashlib.sha256(sample).hexdigest()+".pdf")
            self.assertEqual(Path(projects.DIR/pid/"originals"/item["filename"]).read_bytes(),sample)
            again=official.approve_for_project(request)
            self.assertEqual(again["imported"][0]["status"],"já consta no acervo")
            self.assertEqual(len(projects.summary(pid)["items"]),1)
        with self.assertRaises(ValueError):
            official.approve_for_project({"project_id":pid,"discovery_id":saved["id"],
                                          "source_ids":["unknown"]})

    def test_capag_search_filters_unrelated_siconfi_and_has_current_manual(self):
        def fake_fetch(url,limit):
            return b"<html><body><a href='https://siconfi.tesouro.gov.br/rgf2026.pdf'>RGF</a></body></html>",url,"text/html"
        result=official.discover(self.pid,"CAPAG",
            ["legislacao","normas","manuais","sites_oficiais"],"Campo Grande",
            fetch=fake_fetch,ai_terms=[])
        titles=[entry["title"] for entry in result["sources"]]
        self.assertTrue(any("Manual de Análise Fiscal 2026" in x for x in titles))
        self.assertTrue(all("DCA" not in x and "RGF" not in x for x in titles))
        self.assertTrue(any(entry["downloadable"] for entry in result["sources"]))

    def test_auto_downloads_only_actual_pdf_from_official_site(self):
        pdf=b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\n%%EOF"
        url="https://cdn.tesouro.gov.br/manuais/capag-2026.pdf"
        page="https://www.tesourotransparente.gov.br/capag"
        found={"id":"e"*32,"project_id":self.pid,"topic":"CAPAG",
            "scope":"Campo Grande, MS","searched_at":official.now(),
            "sources":[official.candidate("CAPAG Manual de Análise Fiscal 2026",url,
                 "Tesouro Nacional","manuais",page,"capag",["capag"])]}
        projects._write(projects.DIR/self.pid/"discoveries"/(found["id"]+".json"),found)
        self.assertFalse((projects.DIR/self.pid/"originals").exists())
        def provider(u,limit):
            self.assertEqual(u,url)
            return pdf,u,"application/pdf"
        command={"project_id":self.pid,"discovery_id":found["id"],"max_files":5}
        result=official.auto_download_for_project(command,fetch=provider)
        self.assertEqual(result["downloaded"],1)
        self.assertEqual(result["failed"],[])
        item=projects.summary(self.pid)["items"][0]
        self.assertEqual(item["sha256"],hashlib.sha256(pdf).hexdigest())
        self.assertEqual(item["source_url"],url)
        self.assertEqual(item["import_method"],"automatic_official")
        self.assertEqual((projects.DIR/self.pid/"originals"/item["filename"]).read_bytes(),pdf)
        retry=official.auto_download_for_project(command,fetch=provider)
        self.assertEqual(retry["downloaded"],0)
        self.assertEqual(retry["existing"],1)
        self.assertEqual(len(projects.summary(self.pid)["items"]),1)
        # Se o usuário descarta o PDF, uma nova pesquisa automática não
        # pode contrariar essa escolha nem recriá-lo no acervo ativo.
        record=projects._read(projects.DIR/self.pid/"knowledge.json",[])
        record[0]["deleted_at"]=official.now()
        projects._write(projects.DIR/self.pid/"knowledge.json",record)
        discarded=official.auto_download_for_project(command,fetch=provider)
        self.assertEqual(discarded["downloaded"],0)
        self.assertIn("descartado anteriormente",discarded["documents"][0]["status"])
        self.assertEqual(len(projects._read(projects.DIR/self.pid/"knowledge.json",[])),1)

    def test_auto_follows_official_download_links_not_html_placeholder(self):
        raw=b"%PDF-1.7\nPage 1\n%%EOF"
        start="https://www.tesourotransparente.gov.br/publicacoes/capag"
        wrapper="https://thot-arquivos.tesouro.gov.br/publicacao/54134"
        final="https://cdn.tesouro.gov.br/capag/Manual2026.pdf"
        item=official.candidate("CAPAG Manual",start,"STN","manuais",start,
            "capag",["capag"])
        found={"id":"a"*32,"project_id":self.pid,"topic":"CAPAG",
            "searched_at":official.now(),"sources":[item]}
        projects._write(projects.DIR/self.pid/"discoveries"/(found["id"]+".json"),found)
        def provider(url,limit):
            if url==start:return (b'<a href="'+wrapper.encode()+b'">Download</a>',url,"text/html")
            if url==wrapper:return (b'<iframe src="'+final.encode()+b'"></iframe>',url,"text/html")
            if url==final:return (raw,url,"application/pdf")
            raise AssertionError(url)
        result=official.auto_download_for_project({
            "project_id":self.pid,"discovery_id":found["id"],"max_files":5},fetch=provider)
        self.assertEqual(result["downloaded"],1)
        self.assertEqual(projects.summary(self.pid)["items"][0]["source_url"],final)

    def test_auto_html_is_not_saved_as_pdf_and_rejects_other_projects(self):
        url="https://www.tesourotransparente.gov.br/capag"
        item=official.candidate("CAPAG",url,"STN","normas",url,"capag",["capag"])
        found={"id":"b"*32,"project_id":self.pid,"topic":"CAPAG",
            "searched_at":official.now(),"sources":[item]}
        projects._write(projects.DIR/self.pid/"discoveries"/(found["id"]+".json"),found)
        data={"project_id":self.pid,"discovery_id":found["id"],"max_files":3}
        response=official.auto_download_for_project(data,
            fetch=lambda u,l:(b"<html>Sem PDF</html>",u,"text/html"))
        self.assertEqual(response["downloaded"],0)
        self.assertFalse((projects.DIR/self.pid/"originals").exists())
        self.assertEqual(projects.summary(self.pid)["items"],[])
        with self.assertRaises(ValueError):
            official.auto_download_for_project({**data,"discovery_id":"f"*32})

    def test_wrong_bytes_not_saved(self):
        url="https://siconfi.tesouro.gov.br/arquivo.pdf"
        cand=official.candidate("Manual",url,"Tesouro","manuais",url,"siconfi",["siconfi"])
        discovery={"id":"d"*32,"project_id":self.pid,"sources":[cand],
                   "searched_at":official.now()}
        projects._write(projects.DIR/self.pid/"discoveries"/(discovery["id"]+".json"),
                        discovery)
        with patch.object(official,"read_official",return_value=(b"<html>not pdf</html>",url,"text/html")):
            answer=official.approve_for_project({"project_id":self.pid,
                            "discovery_id":discovery["id"],"source_ids":[cand["id"]]})
        self.assertEqual(len(answer["imported"]),0)
        self.assertEqual(len(answer["failed"]),1)
        self.assertEqual(projects.summary(self.pid)["items"],[])

    def test_research_metadata_persisted_and_separate_from_project(self):
        original={"topic":"balanço",
                  "scope":"Brasil",
                  "sources":[],
                  "searched_at":official.now(),
                  "scope_note":"Pesquisa parcial",
                  "ai_status":"Sem IA",
                  "provider":"Oficiais"}
        with patch.object(official,"discover",return_value=original):
            data=official.discover_for_project({"project_id":self.pid,
                  "topic":"balanço","categories":["manuais"],"scope":"Brasil"})
        self.assertTrue((projects.DIR/self.pid/"discoveries"/(data["id"]+".json")).is_file())
        item=projects.summary(self.pid)["items"][0]
        self.assertEqual(item["type"],"research_result")
        self.assertEqual(item["id"],data["id"])
        self.assertFalse((projects.DIR/self.pid/"originals").exists())

if __name__=="__main__":
    unittest.main(verbosity=2)
