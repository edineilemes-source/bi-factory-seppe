"""HTTP-level smoke check of the unified React/Python analytics API.

Runs only against a loopback ephemeral port and isolated synthetic SQLite/files.
"""
import base64
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from http.server import ThreadingHTTPServer
import serve_bi_factory_api as service
import bi_factory_analytics_adapter as adapter


class AnalyticsHttpSmoke(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database_patch = patch.object(adapter, "DATABASE", Path(self.directory.name) / "analysis.sqlite3")
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.storage_patch = patch.object(adapter, "RAW_DIRECTORY", Path(self.directory.name) / "working")
        self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.port = self.server.server_address[1]

    def request(self, route, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(f"http://127.0.0.1:{self.port}{route}", data=data,
                      headers={"Content-Type": "application/json"} if data else {},
                      method="POST" if data else "GET")
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)

    def test_upload_profile_persist_and_legacy_routes(self):
        status, capabilities = self.request("/api/analytics/capabilities")
        self.assertEqual(status, 200)
        self.assertIn(".csv", capabilities["file_types"])

        content = b"Codigo,Valor,Unidade\n001,100,Saude\n002,200,Educacao\n"
        status, uploaded = self.request("/api/analytics/upload", {
            "filename": "teste.csv",
            "base64": base64.b64encode(content).decode("ascii"),
            "context": {"project_name": "Sintetico"},
        })
        self.assertEqual(status, 201)
        self.assertEqual(uploaded["profile"]["summary"]["total_columns"], 3)
        self.assertEqual(
            (adapter.RAW_DIRECTORY / uploaded["analysis_id"] / "teste.csv").read_bytes(), content)
        status, retrieved = self.request("/api/analytics/analysis/" + uploaded["analysis_id"])
        self.assertEqual(status, 200)
        self.assertEqual(retrieved["analysis_id"], uploaded["analysis_id"])

        status, overview = self.request("/api/overview")
        self.assertEqual(status, 200)
        self.assertIn("products", overview)

    def test_malformed_upload_does_not_create_analysis(self):
        req = Request(f"http://127.0.0.1:{self.port}/api/analytics/upload",
                      data=json.dumps({"filename": "not-a-pdf.pdf", "base64": "YQ=="}).encode(),
                      headers={"Content-Type": "application/json"}, method="POST")
        with self.assertRaises(HTTPError) as caught:
            urlopen(req, timeout=10)
        self.assertEqual(caught.exception.code, 400)
        self.assertFalse(adapter.DATABASE.exists())


if __name__ == "__main__":
    unittest.main()
