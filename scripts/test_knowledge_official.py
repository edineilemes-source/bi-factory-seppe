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
