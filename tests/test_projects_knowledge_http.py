"""Synthetic project/onboarding HTTP tests. Never touches operational Codespaces data."""
import base64
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import serve_bi_factory_api as api
import bi_factory_projects as projects
from http.server import ThreadingHTTPServer


class ProjectsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        for label,path in (("DIR",root/"projects"),("REGISTRY",root/"projects"/"projects.json")):
            p=patch.object(projects,label,path)
            p.start()
            self.addCleanup(p.stop)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),api.Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.origin=f"http://127.0.0.1:{self.server.server_port}"

    def call(self,path,payload=None,method=None):
        req=Request(self.origin+path,
                    data=json.dumps(payload).encode() if payload is not None else None,
                    headers={"Content-Type":"application/json"} if payload is not None else {},
                    method=method or ("POST" if payload is not None else "GET"))
        with urlopen(req,timeout=12) as r:
            return r.status,json.load(r)

    def test_project_creation_is_persisted_and_legacy_kept(self):
        _,first=self.call("/api/projects")
        self.assertEqual(first["projects"][0]["id"],projects.LEGACY_ID)
        status,item=self.call("/api/projects",{"name":"Almoxarifado","theme":"Controle de estoque","scope":"MS"})
        self.assertEqual(status,201)
        self.assertTrue(item["id"].startswith("prj-"))
        _,result=self.call("/api/projects")
        self.assertEqual(len(result["projects"]),2)
        _,legacy=self.call("/api/projects/"+projects.LEGACY_ID)
        self.assertEqual(legacy["name"],projects.LEGACY["name"])

    def test_knowledge_requests_and_upload_are_scoped(self):
        _,a=self.call("/api/projects",{"name":"Condominio A","theme":"Prestação de contas"})
        _,b=self.call("/api/projects",{"name":"Condominio B","theme":"Finanças"})
        path="/api/projects/"+a["id"]
        status,res=self.call(path+"/research",{"project_id":a["id"],"topic":"Prestação de contas",
                    "scope":"Brasil","categories":["legislacao","sites_oficiais"]})
        self.assertEqual(status,201)
        self.assertEqual(res["type"],"research_request")
        self.assertIn("nenhuma pesquisa",res["note"].lower())
        pdf=b"%PDF-1.4\nsynthetic test pdf only"
        _,uploaded=self.call(path+"/documents",{"project_id":a["id"],"filename":"norma.pdf",
                "title":"Norma local","base64":base64.b64encode(pdf).decode(),
                "source":"Tribunal de Contas"})
        self.assertEqual(uploaded["size_bytes"],len(pdf))
        _,knowledge=self.call(path+"/knowledge")
        self.assertEqual(len(knowledge["items"]),2)
        _,other=self.call("/api/projects/"+b["id"]+"/knowledge")
        self.assertEqual(other["items"],[])
        self.assertTrue((projects.DIR/a["id"]/"originals"/(uploaded["sha256"]+".pdf")).is_file())

    def test_invalid_cross_project_or_file_type_is_rejected(self):
        _,project=self.call("/api/projects",{"name":"Folha","theme":"Folha pagamento"})
        url="/api/projects/"+project["id"]+"/documents"
        for body in [
            {"project_id":"wrong-project","filename":"sample.pdf","base64":"YQ=="},
            {"project_id":project["id"],"filename":"../secret.pdf","base64":"YQ=="},
            {"project_id":project["id"],"filename":"untrusted.exe","base64":"YQ=="},
            {"project_id":project["id"],"filename":"fake.pdf","base64":"YQ=="},
        ]:
            with self.subTest(body=body),self.assertRaises(HTTPError) as cm:
                self.call(url,body)
            self.assertEqual(cm.exception.code,400)
        _,result=self.call("/api/projects/"+project["id"]+"/knowledge")
        self.assertEqual(result["items"],[])


if __name__=="__main__":
    unittest.main()
