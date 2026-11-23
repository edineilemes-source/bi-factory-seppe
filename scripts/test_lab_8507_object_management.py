#!/usr/bin/env python3
"""Teste isolado de persistência de formas, texto e exclusão no laboratório 8507.

Nunca toca nos arquivos nem rascunhos reais da 8506 ou 8507.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

SCRIPT=Path(__file__).resolve().parent/"serve_echarts_axes_8507.py"
spec=importlib.util.spec_from_file_location("lab8507_objects_test_server",SCRIPT)
server_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

class ObjectPersistenceTests(unittest.TestCase):
    def test_save_load_and_delete_many_object_types(self):
        original_state=server_module.STATE
        original_workspace=server_module.WORKSPACE
        with tempfile.TemporaryDirectory(prefix="bi-lab8507-objects-") as directory:
            server_module.WORKSPACE=Path(directory)/"only-test"
            server_module.STATE=server_module.WORKSPACE/"state.json"
            server=ThreadingHTTPServer(("127.0.0.1",0),server_module.Handler)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            root=f"http://127.0.0.1:{server.server_port}"
            def get(path):
                with urllib.request.urlopen(root+path,timeout=4) as reply:
                    self.assertEqual(reply.status,200)
                    return json.load(reply)
            def put(draft):
                request=urllib.request.Request(
                    root+"/lab/draft",
                    data=json.dumps(draft,ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type":"application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request,timeout=4) as reply:
                    self.assertEqual(reply.status,200)
                    return json.load(reply)
            try:
                empty=get("/lab/draft")
                self.assertEqual(empty["objects"],[])
                self.assertIsNone(empty["selected"])
                types=["text","title","image","filter","filter_panel","measure_filter",
                       "chart","rectangle","square","diamond","ellipse","arrow","line"]
                objects=[]
                for idx,kind in enumerate(types):
                    item={
                        "id":f"obj-{idx}","type":kind,"title":kind,"width":3,"height":4,
                        "bg":"#ffffff","color":"#1177aa","borderWidth":2,
                        "borderColor":"#333333","fontFamily":"Georgia","size":26,
                        "bold":True,"italic":False,"opacity":65,"rotation":10,
                        "offsetX":15,"offsetY":-8,"z":5,
                    }
                    if kind in ("text","title"):item["text"]=""
                    if kind=="filter_panel":item["dimensions"]=["ano","bimestre"]
                    objects.append(item)
                payload={"version":1,"objects":objects,"filters":{},"selected":"obj-0"}
                saved=put(payload)
                self.assertTrue(saved["ok"])
                self.assertEqual(saved["objects"],len(types))
                recovered=get("/lab/draft")
                self.assertEqual(recovered,payload)
                self.assertEqual(recovered["objects"][0]["text"],"")
                self.assertEqual(recovered["objects"][0]["fontFamily"],"Georgia")
                self.assertEqual(recovered["objects"][0]["size"],26)
                self.assertEqual(recovered["objects"][0]["height"],4)
                self.assertEqual(recovered["objects"][0]["offsetX"],15)
                self.assertEqual(recovered["objects"][0]["opacity"],65)
                # Exclusão é armazenar estado sem os objetos removidos.
                removed={"version":1,"objects":[],"filters":{},"selected":None}
                self.assertTrue(put(removed)["ok"])
                self.assertEqual(get("/lab/draft")["objects"],[])
                self.assertTrue((server_module.WORKSPACE/"state.previous.json").exists())
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                server_module.STATE=original_state
                server_module.WORKSPACE=original_workspace

if __name__=="__main__":
    unittest.main(verbosity=2)
