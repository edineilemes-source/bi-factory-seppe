#!/usr/bin/env python3
"""Versioned reanalysis of the real homologation quality report."""

import hashlib
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ingestion.file_loader import load_tabular_file
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.quality.engine import analyze_data_quality
from core.quality.export import quality_report_id
from core.quality.gate import decide_quality_gate, is_blocking_issue
from core.quality.models import QualityDefectStatus, QualityIssueType


FILE = Path("storage/originals/rela de pagos PMCG 10 ago 2026.xlsx")
ANALYSIS_ID = "ca5cf2d7-98d8-4404-a5cd-916eda0810db"


def _result(report, field_name: str, kind: QualityIssueType | None = None) -> str:
    found = [issue for issue in report.issues
             if issue.field_name == field_name and (kind is None or issue.issue_type == kind)]
    if not found:
        return "NOT_FOUND"
    return "; ".join(
        f"{issue.issue_type.value}/{issue.quality_defect_status.value}/blocking={is_blocking_issue(issue)}"
        for issue in found)


def main() -> None:
    content = FILE.read_bytes(); source_hash = hashlib.sha256(content).hexdigest()
    repository = SQLiteAnalysisRepository()
    analysis = repository.get_analysis(ANALYSIS_ID)
    old = repository.get_quality_report(ANALYSIS_ID)
    if analysis is None or old is None:
        raise RuntimeError("Análise/relatório real não encontrado")
    workbook = load_tabular_file(FILE.name, content, source_type="workspace")
    new = analyze_data_quality(workbook, analysis.report, version=old.version + 1)
    new = repository.save_quality_report(new)
    if hashlib.sha256(FILE.read_bytes()).hexdigest() != source_hash:
        raise RuntimeError("SOURCE IMMUTABILITY FAILED")
    old_id = old.quality_report_id or quality_report_id(old)
    old_gate = old.gate_decision or decide_quality_gate(old.issues)
    new_gate = new.gate_decision or decide_quality_gate(new.issues)
    needs_rule = sum(issue.quality_defect_status == QualityDefectStatus.NEEDS_BUSINESS_RULE
                     for issue in new.issues)
    # Legacy gate blocked directly on ERROR; retain that historical interpretation.
    old_blocking = old_gate.blocking_issues if old.gate_decision else old.error_count
    print("REAL QUALITY GATE HARDENING TEST")
    print(f"OLD QUALITY REPORT ID: {old_id}")
    print(f"NEW QUALITY REPORT ID: {new.quality_report_id}")
    print(f"OLD QUALITY SCORE: {old.score}")
    print(f"NEW QUALITY SCORE: {new.score}")
    print(f"OLD ERROR COUNT: {old.error_count}")
    print(f"NEW ERROR COUNT: {new.error_count}")
    print(f"OLD BLOCKING COUNT: {old_blocking}")
    print(f"NEW BLOCKING COUNT: {new_gate.blocking_issues}")
    print(f"WARNINGS: {new.warning_count}")
    print(f"NEEDS BUSINESS RULE: {needs_rule}")
    print(f"QUALITY GATE STATUS: {new_gate.status.value}")
    print(f"Nº ESTORNO RESULT: {_result(new, 'Nº Estorno')}")
    print(f"Nº LIQUIDAÇÃO RESULT: {_result(new, 'Nº Liquidação')}")
    print(f"AUX SUB EMPENHO RESULT: {_result(new, 'Aux Sub Empenho')}")
    print(f"Nº EMPENHO LEVENSHTEIN RESULT: {_result(new, 'Nº Empenho', QualityIssueType.DOMAIN_INCONSISTENCY)}")
    print(f"FONTE LEVENSHTEIN RESULT: {_result(new, 'Fonte', QualityIssueType.DOMAIN_INCONSISTENCY)}")
    print(f"TOTAL PAGO OUTLIER RESULT: {_result(new, 'Total Pago', QualityIssueType.OUTLIER)}")
    print("SOURCE IMMUTABILITY: PASS")


if __name__ == "__main__":
    main()
