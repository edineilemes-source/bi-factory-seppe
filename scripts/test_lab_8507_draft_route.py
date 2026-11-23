#!/usr/bin/env python3
"""Tests /lab/draft HTTP GET+POST without touching the real 8507 server or drafts."""
from __future__ import annotations
import importlib.util
import json
import threading
import tempfile
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("bi_lab_state_server",HERE/"serve_echarts_axes_8507.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class DraftRouteTests(unittest.TestCase):
    def test_dedicated_route_and_legacy_alias_store_same_draft(self):
        old_state=mod.STATE
        with tempfile.TemporaryDirectory() as tmp:
            mod.STATE=Path(tmp)/"lab8507"/"draft.json"
            server=ThreadingHTTPServer(("127.0.0.1",0),mod.Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            url=f"http://127.0.0.1:{server.server_port}"
            def get(path):
                with urllib.request.urlopen(url+path,timeout=4) as response:
                    self.assertEqual(response.status,200)
                    return json.load(response)
            try:
                empty=get("/lab/draft")
                self.assertEqual(empty["objects"],[])
                payload={
                    "version":1,"objects":[{
                      "id":"chart-stable-1","type":"chart","title":"Receita 2025"
                    }],"filters":{"ano":"2025"},"selected":"chart-stable-1",
                }
                request=urllib.request.Request(url+"/lab/draft",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type":"application/json"},method="POST")
                with urllib.request.urlopen(request,timeout=4) as response:
                    result=json.load(response)
                self.assertTrue(result["ok"])
                self.assertEqual(result["objects"],1)
                self.assertEqual(get("/lab/draft"),payload)
                self.assertEqual(get("/api/state"),payload)
                self.assertEqual(json.loads(mod.STATE.read_text("utf-8")),payload)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=4)
                mod.STATE=old_state

if __name__=="__main__":
    unittest.main(verbosity=2)
