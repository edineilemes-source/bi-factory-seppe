"""Testes offline de multiplas fontes, CAPAG e LexML sem rede."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bi_knowledge_official as official
import bi_knowledge_federated as federated
import bi_factory_projects as projects

class FederatedSearchTests(unittest.TestCase):
    def test_groups_cover_local_and_federal(self):
        self.assertEqual(federated.source_group(
            "https://diogrande.campogrande.ms.gov.br/"),"campo_grande")
        self.assertEqual(federated.source_group(
            "https://www.tce.ms.gov.br/legislacao"),"ms")
        self.assertEqual(federated.source_group(
            "https://www.gov.br/tesouronacional/pt-br/"),"tesouro")
        self.assertEqual(federated.source_group(
            "https://www.in.gov.br/web/dou/"),"federal")
        self.assertEqual(federated.source_group(
            "https://www.lexml.gov.br/busca/SRU"),"lexml")

    def test_capag_references_original_normative_act(self):
        def no_network(url, limit):
            raise OSError("Fora do ar no teste")
        found=official.discover(
            projects.LEGACY_ID,"CAPAG",
            ["legislacao","normas","manuais","sites_oficiais"],
            "Brasil",fetch=no_network,ai_terms=[],
            sources=["federal","tesouro"])
        names=[row["title"] for row in found["sources"]]
        self.assertTrue(any("1.583/2023" in name and "Portaria" in name
                            for name in names),names)
        self.assertEqual(found["source_groups"],["federal","tesouro"])
        self.assertTrue(all("siconfi" not in row["title"].lower() for row in found["sources"]))
        self.assertEqual(found["sources"][0]["category"],"legislacao")

    def test_only_ms_group_and_no_unwanted_sources(self):
        found=official.discover(projects.LEGACY_ID,"legislação Mato Grosso do Sul",
            ["legislacao","normas"],"MS",
            fetch=lambda url,limit: (_ for _ in ()).throw(OSError("offline")),
            ai_terms=[],sources=["ms"])
        self.assertTrue(found["sources"],found)
        self.assertTrue(all(item.get("source_group")=="ms" for item in found["sources"]))
        with self.assertRaises(ValueError):
            official.discover(projects.LEGACY_ID,"CAPAG",
                ["legislacao"],"Brasil",ai_terms=[],sources=["exemplo-falso"])

    def test_lexml_parses_only_real_official_links(self):
        data=b"""<?xml version='1.0'?><searchRetrieveResponse>
          <records><record><recordData><entry>
           <title>Portaria CAPAG 1583</title>
           <relation>https://www.in.gov.br/web/dou/portaria-1583</relation>
           <relation>https://evil.example/phishing</relation>
          </entry></recordData></record></records></searchRetrieveResponse>"""
        def fake(url,limit):
            self.assertIn("busca/SRU",url)
            return data,url,"application/xml"
        items=federated.lexml_documents("CAPAG",fake,official.allowed_url,official.MAX_HTML)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0][1],"https://www.in.gov.br/web/dou/portaria-1583")

if __name__=="__main__":
    unittest.main()
