"""Offline contract for selecting official sites and retrieving real topical links."""
import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bi_factory_projects as p
import bi_knowledge_multisource as m
class Search(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.old=p.DIR,p.REGISTRY
  p.DIR=Path(self.t.name);p.REGISTRY=p.DIR/"projects.json"
 def tearDown(self):
  p.DIR,p.REGISTRY=self.old;self.t.cleanup()
 def test_portals(self):
  self.assertEqual(len(m.catalog()["portals"]),10)
  self.assertTrue({"planalto","lexml","tesouro","municipio_cg","tcems"}<=set(m.catalog()["default_ids"]))
 def test_topic_and_provenance(self):
  src="https://biblioteca.campogrande.ms.gov.br/"
  good=src+"leis/lei-orcamentaria.pdf"
  def fetch(u,limit):
   self.assertEqual(u,src)
   return ("<html><a href='"+good+"'>Lei Orçamentária municipal</a>"
           "<a href='https://bad.invalid/lei-orcamentaria.pdf'>Falsa</a></html>").encode(),u,"text/html"
  r=m.gather(p.LEGACY_ID,"Lei orçamentária",["legislacao"],"Campo Grande",
    portals=["biblioteca_cg"],fetch=fetch,ai_terms=[])
  self.assertIn(good,[x["url"] for x in r["sources"]])
  self.assertTrue(all(x["portal_id"]=="biblioteca_cg" for x in r["sources"]))
 def test_fail_closed(self):
  for bad in ([],["bogus"],["planalto","planalto"],"planalto"):
   with self.assertRaises(ValueError):
    m.gather(p.LEGACY_ID,"empenho",["normas"],"Brasil",portals=bad,ai_terms=[])
 def test_timeout_is_reported(self):
  def broken(*_):raise OSError("offline")
  r=m.gather(p.LEGACY_ID,"CAPAG",["normas","manuais"],"Brasil",
    portals=["tesouro"],fetch=broken,ai_terms=[])
  self.assertTrue(r["warnings"]);self.assertEqual(r["portal_report"][0]["status"],"INDISPONIVEL")
if __name__=="__main__":unittest.main()
