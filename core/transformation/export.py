"""Transformation report and artifact exports without re-execution."""

import csv
import json
from pathlib import Path

from core.transformation.models import DimensionalTransformationRun


def export_transformation_run_report(run: DimensionalTransformationRun) -> bytes:
    payload = run.model_dump(mode="json")
    for result in payload["dimension_results"]: result["staged_rows"] = []
    for result in payload["fact_results"]: result["staged_rows"] = []
    for result in payload["bridge_results"]: result["staged_rows"] = []
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def export_reconciliation_json(run: DimensionalTransformationRun) -> bytes:
    return (json.dumps(run.reconciliation_report.model_dump(mode="json"), ensure_ascii=False,
                       sort_keys=True, indent=2) + "\n").encode()


def read_staged_artifact(path: str) -> bytes:
    return Path(path).read_bytes()


def validate_artifact_consistency(run: DimensionalTransformationRun) -> list[str]:
    errors = []
    for result in [*run.dimension_results, *run.fact_results, *run.bridge_results]:
        if not result.artifact_path or not Path(result.artifact_path).is_file():
            errors.append(f"Missing artifact for {result.target_table}"); continue
        with Path(result.artifact_path).open(encoding="utf-8", newline="") as handle:
            count = sum(1 for _ in csv.DictReader(handle))
        expected = getattr(result, "row_count", getattr(result, "staged_row_count", 0))
        if count != expected: errors.append(f"Artifact row count mismatch for {result.target_table}")
    if not run.reconciliation_report.artifact_path or not Path(run.reconciliation_report.artifact_path).is_file():
        errors.append("Missing reconciliation artifact")
    return errors
