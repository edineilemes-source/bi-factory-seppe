#!/usr/bin/env python3
"""Tests the product-specific official 8507 layout API against temporary files.
Does not touch existing product registries, real layouts, API 8505, or ports 8506/8507.
"""
from __future__ import annotations
import importlib.util
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"prototypes/editor-visual/server.py"
spec=importlib.util.spec_from_file_location("bi_visual_8507_official_test",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ID1="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ID2="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

class OfficialProductEditorTests(unittest.TestCase):
    def test_per_product_isolation_backup_and_legacy_preservation(self):
        with tempfile.TemporaryDirectory(prefix="bi-official-8507-test-") as directory:
            base=Path(directory)
            old_visual,old_layouts,old_find,old_update,old_lab=(
                module.VISUAL_8507,module.LAYOUTS,module._get_product,
                module.registry.update_product,module.LEGACY_LAB_8507
            )
            module.VISUAL_8507=base/"visual_8507"
            module.LAYOUTS=base/"legacy"
            module.LEGACY_LAB_8507=base/"lab-state.json"
            laboratory={"version":1,"objects":[
                {"id":"lab1","type":"text","text":"Rascunho experimental"}],
                "filters":{},"selected":None}
            module.LEGACY_LAB_8507.write_text(json.dumps(laboratory),encoding="utf-8")
            lab_original=module.LEGACY_LAB_8507.read_bytes()
            module._get_product=lambda identifier: (
                {"id":identifier,"name":"Produto "+identifier[:4]}
                if identifier in (ID1,ID2) else None
            )
            updated=[]
            module.registry.update_product=lambda identifier:updated.append(identifier)
            module.LAYOUTS.mkdir(parents=True)
            legacy={"schema":"bi-factory-editor-poc-v1","objects":{"a":{"type":"text"}},
                    "layout":[{"id":"a","x":0,"y":0,"w":4,"h":2}]}
            legacy_path=module.LAYOUTS/(ID1+".json")
            legacy_path.write_text(json.dumps(legacy),encoding="utf-8")
            original_bytes=legacy_path.read_bytes()
            server=ThreadingHTTPServer(("127.0.0.1",0),module.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            url="http://127.0.0.1:"+str(server.server_port)
            def get(identifier):
                with urlopen(url+"/api/products/"+identifier+"/visual-8507",timeout=3) as resp:
                    self.assertEqual(resp.status,200)
                    return json.load(resp)
            def put(identifier,data):
                request=Request(url+"/api/products/"+identifier+"/visual-8507",
                    data=json.dumps(data,ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type":"application/json"},method="PUT")
                with urlopen(request,timeout=3) as resp:
                    return json.load(resp)
            try:
                with urlopen(url+"/api/visual-8507/lab-draft",timeout=3) as response:
                    self.assertEqual(json.load(response),laboratory)
                self.assertEqual(module.LEGACY_LAB_8507.read_bytes(),lab_original)
                self.assertIsNone(get(ID1))
                self.assertIsNone(get(ID2))
                first={"version":1,"objects":[
                    {"id":"chart-1","type":"chart","title":"Receita",
                     "chart":{"type":"BAR","measures":["receita_realizada_acumulada"]}},
                    {"id":"text-1","type":"text","text":"Visual Oficial"}],
                    "filters":{"ano":["2024","2025"]},"selected":"chart-1"}
                self.assertTrue(put(ID1,first)["ok"])
                self.assertEqual(get(ID1),first)
                self.assertIsNone(get(ID2))
                second={"version":1,"objects":[
                    {"id":"text-2","type":"text","text":"Outro produto"}],
                    "filters":{},"selected":None}
                self.assertTrue(put(ID2,second)["ok"])
                self.assertEqual(get(ID1),first)
                self.assertEqual(get(ID2),second)
                changed={**first,"filters":{"ano":["2025"]}}
                self.assertTrue(put(ID1,changed)["ok"])
                self.assertEqual(get(ID1),changed)
                previous=module.VISUAL_8507/"previous"/(ID1+".json")
                self.assertEqual(json.loads(previous.read_text(encoding="utf-8")),first)
                self.assertEqual(legacy_path.read_bytes(),original_bytes)
                self.assertTrue(ID1 in updated and ID2 in updated)
                invalid={**changed,"objects":[{"id":"unsupported","type":"executable"}]}
                with self.assertRaises(HTTPError) as http:
                    put(ID1,invalid)
                self.assertEqual(http.exception.code,400)
                self.assertEqual(get(ID1),changed)
                self.assertEqual(legacy_path.read_bytes(),original_bytes)
                self.assertEqual(module.LEGACY_LAB_8507.read_bytes(),lab_original)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                module.VISUAL_8507,module.LAYOUTS,module.LEGACY_LAB_8507=old_visual,old_layouts,old_lab
                module._get_product=old_find
                module.registry.update_product=old_update

if __name__=="__main__":
    unittest.main(verbosity=2)
