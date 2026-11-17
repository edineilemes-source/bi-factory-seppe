"""Synthetic integration checks for the React/Python legacy analysis adapter."""
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from scripts import bi_factory_analytics_adapter as adapter


class AnalyticsAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database = Path(self.temp.name) / "test-only.sqlite3"
        self.patcher = patch.object(adapter, "DATABASE", database)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.raw_patcher = patch.object(adapter, "RAW_DIRECTORY", Path(self.temp.name) / "uploads")
        self.raw_patcher.start()
        self.addCleanup(self.raw_patcher.stop)

    def test_end_to_end_upload_and_restore(self):
        content = b"Codigo,Valor,Unidade\n001,120,Saude\n002,250,Educacao\n003,80,Saude\n"
        result = adapter.upload({
            "filename": "synthetic.csv",
            "base64": base64.b64encode(content).decode("ascii"),
            "context": {"project_name": "Teste sintético", "business_domain": "genérico"},
        })
        self.assertEqual(result["profile"]["summary"]["sheet_count"], 1)
        self.assertEqual(result["profile"]["summary"]["total_columns"], 3)
        self.assertTrue(result["analysis_id"])
        self.assertIsNotNone(result["quality"])
        restored = adapter.get(result["analysis_id"])
        self.assertEqual(restored["analysis_id"], result["analysis_id"])
        self.assertEqual(restored["profile"]["original_name"], "synthetic.csv")
        self.assertIn("prepared_dataset_status", result["pipeline"])
        self.assertTrue(result["source_file_retained_locally"])
        self.assertEqual((adapter.RAW_DIRECTORY / result["analysis_id"] / "synthetic.csv").read_bytes(), content)

    def test_bad_files_rejected_without_database_mutation(self):
        for filename, body in (
            ("../unsafe.csv", "YQ=="), ("sample.pdf", "YQ=="), ("test.csv", "!!!!"),
        ):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    adapter.upload({"filename": filename, "base64": body})
        self.assertFalse(adapter.DATABASE.exists())

    def test_answers_must_match_existing_question_and_option(self):
        csv = b"Xyzabc\nA\nB\nC\n"
        result = adapter.upload({
            "filename": "ambiguous.csv",
            "base64": base64.b64encode(csv).decode("ascii"),
        })
        questions = result["semantic"]["questions"]
        with self.assertRaises(ValueError):
            adapter.answer({
                "analysis_id": result["analysis_id"],
                "question_id": str(uuid4()),
                "answer": "foo",
            })
        if questions:
            question = questions[0]
            with self.assertRaises(ValueError):
                adapter.answer({
                    "analysis_id": result["analysis_id"],
                    "question_id": question["question_id"],
                    "answer": "not a listed option",
                })
            updated = adapter.answer({
                "analysis_id": result["analysis_id"],
                "question_id": question["question_id"],
                "answer": "Não sei / preciso verificar",
            })
            self.assertTrue(updated["semantic"]["questions"])


if __name__ == "__main__":
    unittest.main()
