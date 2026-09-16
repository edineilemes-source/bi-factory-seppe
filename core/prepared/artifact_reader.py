"""Validated, bounded-memory access to persisted Prepared CSV artifacts."""

import csv
from collections.abc import Iterator
from pathlib import Path

from core.prepared.generation import verify_prepared_artifact
from core.prepared.models import PreparedDatasetArtifact


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PreparedDatasetArtifactReader:
    """Read a Prepared artifact without materializing it or consulting its source XLSX."""

    def __init__(self, artifact: PreparedDatasetArtifact, *, analysis_id: str,
                 prepared_dataset_id: str, source_document_id: str,
                 version: int, fingerprint: str) -> None:
        expected = (analysis_id, prepared_dataset_id, source_document_id, version, fingerprint)
        actual = (artifact.analysis_id, artifact.prepared_dataset_id,
                  artifact.source_document_id, artifact.version, artifact.fingerprint)
        if actual != expected:
            raise ValueError("Prepared artifact ownership/version/fingerprint incompatível.")
        location = Path(artifact.artifact_location)
        if not location.is_absolute():
            location = PROJECT_ROOT / location
        self.artifact = artifact.model_copy(update={"artifact_location": str(location)})
        verify_prepared_artifact(self.artifact)

    @property
    def path(self) -> Path:
        return Path(self.artifact.artifact_location)

    def iter_chunks(self, *, chunk_size: int = 2_000,
                    columns: set[str] | None = None) -> Iterator[list[dict[str, str | None]]]:
        """Yield bounded row dictionaries; empty CSV cells become nulls."""
        if chunk_size < 1:
            raise ValueError("chunk_size deve ser positivo")
        count = 0
        chunk: list[dict[str, str | None]] = []
        with self.path.open("r", encoding="utf-8", newline="") as stream:
            rows = csv.DictReader(stream)
            if rows.fieldnames is None:
                raise ValueError("Prepared CSV sem cabeçalho.")
            missing = columns - set(rows.fieldnames) if columns else set()
            if missing:
                raise ValueError(f"Prepared CSV não contém colunas contratadas: {sorted(missing)}")
            for row in rows:
                count += 1
                selected = columns or row.keys()
                chunk.append({name: (row[name] if row[name] != "" else None) for name in selected})
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
        if count != self.artifact.row_count:
            raise ValueError(
                f"Prepared CSV diverge da metadata: {count} linhas, esperado {self.artifact.row_count}."
            )
