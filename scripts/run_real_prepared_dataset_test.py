#!/usr/bin/env python3
"""Read-only source/analysis validation of bounded-memory Prepared generation."""

import hashlib
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.prepared.generation import DEFAULT_PREPARED_CHUNK_SIZE, generate_prepared_dataset_artifact


FILE = Path("storage/originals/rela de pagos PMCG 10 ago 2026.xlsx")
ANALYSIS_ID = "ca5cf2d7-98d8-4404-a5cd-916eda0810db"
ARTIFACT_ROOT = Path("storage/working/prepared-real-test")


def main() -> None:
    content = FILE.read_bytes()
    source_before = hashlib.sha256(content).hexdigest()
    repository = SQLiteAnalysisRepository("storage/bi_factory.sqlite3")
    analysis = repository.get_analysis(ANALYSIS_ID)
    if analysis is None:
        raise SystemExit(f"Análise real não encontrada: {ANALYSIS_ID}")
    quality = repository.get_quality_report(ANALYSIS_ID)
    artifact = generate_prepared_dataset_artifact(
        FILE.name, content, analysis.report, quality,
        version=repository.next_prepared_version(ANALYSIS_ID),
        artifact_root=ARTIFACT_ROOT, chunk_size=DEFAULT_PREPARED_CHUNK_SIZE,
    )
    source_after = hashlib.sha256(FILE.read_bytes()).hexdigest()
    if source_after != source_before:
        raise RuntimeError("SOURCE IMMUTABILITY FAILED")
    metrics = artifact.metrics
    estimated_mb = metrics.estimated_dataframe_memory_bytes / (1024 * 1024)
    memory_ratio = ((metrics.rss_peak_mb - metrics.rss_start_mb) / estimated_mb
                    if estimated_mb else 0.0)
    duration = ((metrics.finished_at - metrics.started_at).total_seconds()
                if metrics.finished_at else 0.0)
    print("REAL PREPARED DATASET TEST")
    print(f"FILE: {FILE}")
    print(f"FILE SIZE: {len(content)}")
    print(f"ROWS: {analysis.report.observed_profile.summary.total_approximate_rows}")
    print(f"FIELDS: {artifact.field_count}")
    print(f"CHUNK SIZE: {DEFAULT_PREPARED_CHUNK_SIZE}")
    print(f"START RSS: {metrics.rss_start_mb:.2f} MB")
    print(f"PEAK RSS: {metrics.rss_peak_mb:.2f} MB")
    print(f"END RSS: {metrics.rss_end_mb:.2f} MB")
    print(f"MEMORY RATIO: {memory_ratio:.2f}")
    print(f"DURATION: {duration:.2f} s")
    print(f"PREPARED ROWS: {artifact.row_count}")
    print(f"PREPARED FIELDS: {artifact.field_count}")
    print(f"TRANSFORMATIONS: {artifact.total_transformations}")
    print(f"ARTIFACT FORMAT: {artifact.artifact_format.upper()}")
    print(f"ARTIFACT SIZE: {artifact.artifact_size_bytes}")
    print(f"FINGERPRINT: {artifact.fingerprint}")
    print(f"STATUS: {artifact.generation_status.value}")
    print("SOURCE IMMUTABILITY: PASS")


if __name__ == "__main__":
    main()
