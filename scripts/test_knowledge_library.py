"""Teste offline do ciclo PDF → biblioteca → leitura → contexto para Modelagem."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bi_factory_projects as projects
import bi_knowledge_library as library
import bi_knowledge_official as official

class LibraryTests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory(prefix="bi-knowledge-library-")
    self.original=(projects.DIR,projects.REGISTRY)
    projects.DIR=Path(self.tmp.name)
    projects.REGISTRY=projects.DIR/"projects.json"
    self.pid=projects.LEGACY_ID
    self.other="prj-test-second"
    projects._write(projects.REGISTRY,[{
      "id":self.other,"name":"Outro projeto","theme":"Compras",
      "scope":"Brasil"}])
    self.raw=b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\n%%EOF"
    sha=hashlib.sha256(self.raw).hexdigest()
    self.doc={"id":str(uuid4()),"type":"document","title":"Manual CAPAG 2026",
       "sha256":sha,"filename":sha+".pdf",
       "source_url":"https://www.gov.br/tesouronacional/exemplo.pdf",
       "validity_note":"2026","status":"PDF original armazenado"}
    path=projects.DIR/self.pid/"originals"
    path.mkdir(parents=True,exist_ok=True)
    (path/(sha+".pdf")).write_bytes(self.raw)
    projects._write(projects.DIR/self.pid/"knowledge.json",[self.doc])
 def tearDown(self):
    projects.DIR,projects.REGISTRY=self.original
    self.tmp.cleanup()
 def test_preview_checks_sha_and_refuses_wrong_project(self):
    raw,doc=library.read_pdf_bytes(self.pid,self.doc["id"])
    self.assertEqual(raw,self.raw)
    self.assertEqual(doc["title"],"Manual CAPAG 2026")
    with self.assertRaises(ValueError):
        library.read_pdf_bytes(self.other,self.doc["id"])
    file=projects.DIR/self.pid/"originals"/(self.doc["sha256"]+".pdf")
    file.write_bytes(b"%PDF-suspicious")
    with self.assertRaisesRegex(ValueError,"SHA-256"):
        library.read_pdf_bytes(self.pid,self.doc["id"])
 def test_read_builds_auditable_index_for_capag_empenho(self):
    text=("A Capacidade de Pagamento CAPAG usa o indicador de Poupança Corrente. "
          "A despesa empenhada é registrada por empenho. "
          "A liquidez relativa deve ser conferida na legislação aplicável.")
    def fake(raw):
        self.assertEqual(raw,self.raw)
        return ([{"page":3,"text":text}],
                 {"page_count":4,"pages_processed":4,
                  "pages_with_text":1,"truncated":False})
    response=library.read_selected({"project_id":self.pid,
                                  "document_ids":[self.doc["id"]]},fake)
    self.assertTrue(response["ok"])
    self.assertEqual(response["read"][0]["status"],"Indexado")
    info=library.query_concepts(self.pid,"empenho")
    self.assertGreater(len(info["matches"]),0)
    hit=info["matches"][0]
    self.assertEqual(hit["page"],3)
    self.assertEqual(hit["document_id"],self.doc["id"])
    self.assertEqual(hit["sha256"],self.doc["sha256"])
    self.assertEqual(hit["source_url"],self.doc["source_url"])
    self.assertIn("Capacidade de Pagamento",library.query_concepts(self.pid,"CAPAG")["matches"][0]["excerpt"])
    self.assertTrue(library.query_concepts(self.pid,"poupança corrente")["matches"])
    self.assertEqual(library.query_concepts(self.other,"capag")["matches"],[])
    self.assertEqual(library.list_library(self.pid)["indexed"],1)
    with patch.dict("os.environ",{"BI_KNOWLEDGE_OLLAMA_MODEL":""}):
        answer=library.interpret_for_model({"project_id":self.pid,"question":"empenho"})
    self.assertFalse(answer["ai_enabled"])
    self.assertTrue(answer["evidence"])
    self.assertIsNone(answer["interpretation"])
    self.assertTrue(answer["review_required"])
 def test_delete_removes_from_search_and_preview_but_restore_recovers(self):
    self.test_read_builds_auditable_index_for_capag_empenho()
    answer=library.delete_document(self.pid,self.doc["id"])
    self.assertTrue(answer["recoverable"])
    self.assertEqual(library.list_library(self.pid)["total"],0)
    self.assertFalse(projects.DIR.joinpath(self.pid,"originals",self.doc["sha256"]+".pdf").exists())
    self.assertTrue(projects.DIR.joinpath(self.pid,"trash",self.doc["sha256"]+".pdf").is_file())
    self.assertEqual(library.query_concepts(self.pid,"capag")["matches"],[])
    with self.assertRaises(ValueError):library.read_pdf_bytes(self.pid,self.doc["id"])
    self.assertFalse(projects.summary(self.pid)["items"],"Arquivado não fica no catálogo corrente")
    library.restore_document(self.pid,self.doc["id"])
    self.assertEqual(library.read_pdf_bytes(self.pid,self.doc["id"])[0],self.raw)
    self.assertEqual(len(projects.summary(self.pid)["items"]),1)
    self.assertGreater(len(library.query_concepts(self.pid,"capag")["matches"]),0)
 def test_reference_can_be_removed_and_restored(self):
    ref={"id":str(uuid4()),"type":"official_reference","title":"Lei 4.320",
         "source_url":"https://www.planalto.gov.br/ccivil_03/leis/l4320.htm"}
    projects._write(projects.DIR/self.pid/"knowledge.json",[self.doc,ref])
    library.delete_document(self.pid,ref["id"])
    self.assertEqual(library.list_library(self.pid)["total"],1)
    library.restore_document(self.pid,ref["id"])
    self.assertEqual(library.list_library(self.pid)["total"],2)
 def test_selection_is_bounded_and_maintains_current_index(self):
    with self.assertRaises(ValueError):library.read_selected({
      "project_id":self.pid,"document_ids":[]})
    with self.assertRaises(ValueError):library.read_selected({
      "project_id":self.pid,"document_ids":[self.doc["id"]]*2})
    with self.assertRaises(ValueError):library.read_selected({
      "project_id":self.pid,"document_ids":["bad"]},lambda a:b"")
    with self.assertRaises(ValueError):library.query_concepts(self.pid,"")
 def test_real_pypdf_read_without_text_reports_ocr_pending(self):
    from io import BytesIO
    from pypdf import PdfWriter
    writer=PdfWriter()
    writer.add_blank_page(width=280,height=220)
    buffer=BytesIO()
    writer.write(buffer)
    pages,stats=library.extract_pdf(buffer.getvalue())
    self.assertEqual(pages,[])
    self.assertEqual(stats["page_count"],1)
    self.assertEqual(stats["pages_with_text"],0)
    self.assertFalse(stats["truncated"])
 def test_thot_link_not_assumed_pdf_and_capag_seed_present(self):
    capag=[s for s in official.SEEDS if "CAPAG" in s[0]]
    self.assertTrue(capag)
    candidate=official.candidate("Portaria STN", "https://thot-arquivos.tesouro.gov.br/publicacao-anexo/29283",
          "STN","legislacao",capag[0][1],"CAPAG",["capag"])
    self.assertFalse(candidate["downloadable"])
    pdf=official.candidate("Manual","https://siconfi.tesouro.gov.br/a.pdf","STN","manuais",
            capag[0][1],"",["manual"])
    self.assertTrue(pdf["downloadable"])

if __name__=="__main__":
 unittest.main(verbosity=2)
