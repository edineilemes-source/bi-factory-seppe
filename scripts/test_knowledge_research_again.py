"""Regressão: excluir documentos, refazer busca e reincorporar sem perder dados."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import bi_factory_projects as projects
import bi_knowledge_official as official
import bi_knowledge_library as library

class ReSearchAfterDeletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="knowledge-research-")
        self.old=projects.DIR,projects.REGISTRY
        projects.DIR=Path(self.tmp.name)
        projects.REGISTRY=projects.DIR/"projects.json"
        self.pid=projects.LEGACY_ID
        self.pdf=b"%PDF-1.5\n1 0 obj\n<</Type/Catalog>>\nendobj\n%%EOF"
        self.pdf_url="https://www.gov.br/tesouronacional/arquivo/capag-1583.pdf"
        self.reference_url="https://www.in.gov.br/web/dou/portaria-capag"
        self.pdf_item=official.candidate("CAPAG Portaria 1583 PDF",self.pdf_url,
            "DOU","legislacao",self.pdf_url,"capag",["capag"])
        self.ref_item=official.candidate("CAPAG Portaria DOU",self.reference_url,
            "DOU","legislacao",self.reference_url,"capag",["capag"])
        self.assertTrue(self.pdf_item["downloadable"])
        self.assertFalse(self.ref_item["downloadable"])

    def tearDown(self):
        projects.DIR,projects.REGISTRY=self.old
        self.tmp.cleanup()

    def save_discovery(self,discovery_id):
        saved={"id":discovery_id,"project_id":self.pid,"topic":"CAPAG",
            "searched_at":official.now(),"scope":"Brasil",
            "sources":[self.pdf_item,self.ref_item]}
        projects._write(projects.DIR/self.pid/"discoveries"/(discovery_id+".json"),saved)
        return saved

    def approve(self,discovery_id,ids=None):
        chosen=ids or [self.pdf_item["id"],self.ref_item["id"]]
        return official.approve_for_project({
            "project_id":self.pid,"discovery_id":discovery_id,"source_ids":chosen})

    def read_mock(self,url,*args):
        self.assertEqual(url,self.pdf_url)
        return self.pdf,url,"application/pdf"

    def test_search_again_restores_deleted_pdf_and_reference(self):
        first_id="b"*32
        second_id="c"*32
        self.save_discovery(first_id)
        self.save_discovery(second_id)
        with patch.object(official,"read_official",side_effect=self.read_mock):
            added=self.approve(first_id)
            self.assertEqual(len(added["imported"]),2)
            rows=library.list_library(self.pid)["documents"]
            self.assertEqual(len(rows),2)
            original_ids={row["source_url"]:row["id"] for row in rows}
            pdf=next(row for row in rows if row["type"]=="document")
            digest=hashlib.sha256(self.pdf).hexdigest()
            self.assertEqual(pdf["sha256"],digest)
            for row in rows:
                library.delete_document(self.pid,row["id"])
            self.assertEqual(library.list_library(self.pid)["total"],0)
            self.assertEqual(sum(bool(x["deleted_at"]) for x in
                library.list_library(self.pid)["documents"]),2)
            restored=self.approve(second_id)
        self.assertEqual(len(restored["imported"]),2)
        self.assertEqual(restored["failed"],[])
        self.assertTrue(all(row["status"]=="restaurado da lixeira" for row in restored["imported"]))
        current=library.list_library(self.pid)["documents"]
        self.assertEqual(len(current),2,"Sem duplicar registros ao refazer pesquisa")
        self.assertEqual(library.list_library(self.pid)["total"],2)
        self.assertTrue(all(not row.get("deleted_at") for row in current))
        self.assertEqual({row["source_url"]:row["id"] for row in current},original_ids)
        self.assertEqual(library.read_pdf_bytes(self.pid,pdf["id"])[0],self.pdf)
        self.assertTrue(next(x for x in current if x["type"]=="document")["file_available"])
        again=self.approve(second_id,ids=[self.ref_item["id"]])
        self.assertEqual(again["imported"][0]["status"],"já consta no acervo")

    def test_auto_search_requires_explicit_restoration(self):
        discovery_id="d"*32
        self.save_discovery(discovery_id)
        fetched=lambda url,limit:(self.pdf,url,"application/pdf")
        command={"project_id":self.pid,"discovery_id":discovery_id,"max_files":3}
        original=official.auto_download_for_project(command,fetch=fetched)
        self.assertEqual(original["downloaded"],1)
        pdf_id=next(x["id"] for x in library.list_library(self.pid)["documents"]
                    if x["type"]=="document")
        library.delete_document(self.pid,pdf_id)
        self.assertEqual(library.list_library(self.pid)["total"],0)
        blocked=official.auto_download_for_project(command,fetch=fetched)
        self.assertEqual(blocked["downloaded"],0)
        self.assertEqual(blocked["restored"],0)
        self.assertEqual(library.list_library(self.pid)["total"],0)
        # Nova pesquisa solicitada com opção explícita de baixar novamente.
        requested={**command,"restore_deleted":True}
        back=official.auto_download_for_project(requested,fetch=fetched)
        self.assertEqual(back["downloaded"],0)
        self.assertEqual(back["restored"],1)
        self.assertEqual(back["documents"][0]["id"],pdf_id)
        self.assertEqual(library.list_library(self.pid)["total"],1)
        self.assertEqual(library.read_pdf_bytes(self.pid,pdf_id)[0],self.pdf)
        self.assertEqual(official.auto_download_for_project(requested,fetch=fetched)["existing"],1)

    def test_updated_pdf_same_url_creates_new_version_without_restoring_old_hash(self):
        discovery_id="e"*32
        self.save_discovery(discovery_id)
        with patch.object(official,"read_official",side_effect=self.read_mock):
            original=self.approve(discovery_id,ids=[self.pdf_item["id"]])
        old_id=original["imported"][0]["item"]["id"]
        library.delete_document(self.pid,old_id)
        changed=self.pdf+b"\n% Novos anexos\n"
        with patch.object(official,"read_official",
            return_value=(changed,self.pdf_url,"application/pdf")):
            new=self.approve(discovery_id,ids=[self.pdf_item["id"]])
        self.assertNotEqual(new["imported"][0]["status"],"restaurado da lixeira")
        active=[row for row in library.list_library(self.pid)["documents"]
                if not row.get("deleted_at")]
        self.assertEqual(len(active),1)
        self.assertNotEqual(active[0]["id"],old_id)
        self.assertEqual(library.read_pdf_bytes(self.pid,active[0]["id"])[0],changed)
        self.assertEqual(len(library.list_library(self.pid)["documents"]),2)

    def test_invalid_explicit_restore_flag_is_rejected(self):
        discovery_id="f"*32
        self.save_discovery(discovery_id)
        with self.assertRaisesRegex(ValueError,"restaurar itens"):
            official.auto_download_for_project({
                "project_id":self.pid,"discovery_id":discovery_id,
                "max_files":2,"restore_deleted":"true"},fetch=self.read_mock)

if __name__=="__main__":
    unittest.main(verbosity=2)
