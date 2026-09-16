import hashlib
import json
from pathlib import Path

from core.bi_mvp.models import MVPModel
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.prepared.artifact_reader import PreparedDatasetArtifactReader


def resolve_prepared(analysis_id: str, repository: SQLiteAnalysisRepository, *,
                     prepared_dataset_id: str | None = None, version: int | None = None):
    records = repository.list_prepared_datasets(analysis_id)
    if not records:
        raise ValueError(f"Analysis {analysis_id} has no persisted Prepared artifact.")
    record = records[0]
    if prepared_dataset_id is not None:
        record = next((r for r in records if r.prepared_dataset_id == prepared_dataset_id), None)
        if record is None: raise ValueError("Prepared does not belong to the requested analysis.")
    if version is not None and record.version != version:
        raise ValueError("Prepared version mismatch; no fallback is allowed.")
    artifact = repository.get_prepared_artifact(record.prepared_dataset_id)
    if (artifact is None or artifact.analysis_id != analysis_id
            or artifact.prepared_dataset_id != record.prepared_dataset_id):
        raise ValueError("Prepared artifact ownership mismatch.")
    if hasattr(record, "fingerprint") and record.fingerprint != artifact.fingerprint:
        raise ValueError("Persisted Prepared fingerprint mismatch.")
    analysis = repository.get_analysis(analysis_id)
    if analysis is None or artifact.source_document_id != analysis.source_document_id or artifact.version != record.version:
        raise ValueError("Analysis/Prepared source ownership or version mismatch.")
    return PreparedDatasetArtifactReader(
        artifact, analysis_id=analysis_id, prepared_dataset_id=artifact.prepared_dataset_id,
        source_document_id=artifact.source_document_id, version=artifact.version,
        fingerprint=artifact.fingerprint)


def persist_model(model: MVPModel, root: Path | str = "storage/reports/bi_mvp") -> Path:
    directory = Path(root) / model.analysis_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"model-v{model.version}.json"
    if path.exists():
        existing = load_model(path)
        if existing != model:
            raise FileExistsError(f"Versioned model already exists: {path}")
        return path
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    path.with_suffix(".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    return path


def load_model(path: Path | str) -> MVPModel:
    path = Path(path)
    if path.with_suffix(".sha256").read_text().strip() != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Model contract integrity mismatch.")
    return MVPModel.model_validate_json(path.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def persist_text(path: Path | str, value: str) -> Path:
    target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_text(encoding="utf-8") != value:
        raise FileExistsError(f"Versioned artifact already exists: {target}")
    target.write_text(value, encoding="utf-8")
    return target
