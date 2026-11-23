#!/usr/bin/env python3
"""Regression: laboratory 8507 reads the homologated RREO CSV when port 8505 fails."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path

PATH=Path(__file__).resolve().parent/"serve_echarts_axes_8507.py"
spec=importlib.util.spec_from_file_location("lab8507_server_fiscal_fallback",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class FiscalFallbackTests(unittest.TestCase):
    def test_offline_8505_loads_official_csv_without_writing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"rreo-2022-2026-dashboard.csv"
            base={col:"100" for col in mod.REQUIRED}
            data=[
                {**base,"ano":"2025","bimestre":"6"},
                {**base,"ano":"2026","bimestre":"4"}
            ]
            import csv
            with dest.open("w",encoding="utf-8",newline="") as writer:
                w=csv.DictWriter(writer,fieldnames=sorted(mod.REQUIRED))
                w.writeheader()
                w.writerows(data)
            original=dest.read_bytes()
            old_upstream,old_history,old_legacy=mod.UPSTREAM,mod.HISTORICAL,mod.LEGACY
            try:
                mod.UPSTREAM="http://127.0.0.1:1/api/fiscal"
                mod.HISTORICAL=dest
                mod.LEGACY=Path(tmp)/"missing.csv"
                rows,source=mod.load_fiscal()
                self.assertEqual(len(rows),2)
                self.assertEqual(rows[0]["ano"],2025)
                self.assertEqual(rows[1]["bimestre"],4)
                self.assertTrue(source.startswith("csv-local:"))
                self.assertEqual(dest.read_bytes(),original)
            finally:
                mod.UPSTREAM,mod.HISTORICAL,mod.LEGACY=old_upstream,old_history,old_legacy

    def test_missing_fiscal_file_fails_without_creating_fake_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous=(mod.UPSTREAM,mod.HISTORICAL,mod.LEGACY)
            try:
                mod.UPSTREAM="http://127.0.0.1:1/api/fiscal"
                mod.HISTORICAL=Path(tmp)/"missing-history.csv"
                mod.LEGACY=Path(tmp)/"missing-2025.csv"
                with self.assertRaises(FileNotFoundError):
                    mod.load_fiscal()
            finally:
                mod.UPSTREAM,mod.HISTORICAL,mod.LEGACY=previous

if __name__=="__main__":
    unittest.main(verbosity=2)
