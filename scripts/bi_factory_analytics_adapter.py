"""Adapter: expose the *existing* Python analysis and semantic engines to React.

No Streamlit runtime is required by the React UI. This adapter reuses the
persisted SQLite analyses, does not alter source files or visual products, and
never infers that a dimensional model has been approved.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import os
import tempfile
from pathlib import Path

from core.ingestion.file_loader import load_tabular_file, SUPPORTED_EXTENSIONS
from core.profiling.models import ProjectContext
from core.profiling.workbook_profiler import profile_workbook
from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.quality.engine import analyze_data_quality

MAX_FILE_BYTES = 8 * 1024 * 1024
SAFE_ANALYSIS_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,40}$")
ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "storage" / "bi_factory.sqlite3"
RAW_DIRECTORY = ROOT / "storage" / "working" / "react_analytics"


def repository():
    return SQLiteAnalysisRepository(DATABASE)


def _validated_id(value):
    if not isinstance(value, str) or not SAFE_ANALYSIS_ID.fullmatch(value):
        raise ValueError("Identificador de análise inválido")
    return value


def _snapshot(repo, analysis_id):
    record = repo.get_analysis(_validated_id(analysis_id))
    if record is None:
        raise ValueError("Análise não encontrada")
    report = record.report
    # Do not return the entire input dataset. Profile is a sampled report.
    history = repo.list_analyses_for_document(record.source_document_id)
    item = next((x for x in history if x.analysis_id == analysis_id), None)
    return {
        "analysis_id": analysis_id,
        "source_document_id": record.source_document_id,
        "status": record.status.value,
        "created_at": record.created_at.isoformat(),
        "profile": report.observed_profile.model_dump(mode="json"),
        "semantic": {
            "summary": report.summary.model_dump(mode="json"),
            "questions": [q.model_dump(mode="json") for q in report.questions],
            "validated_semantics": [v.model_dump(mode="json") for v in report.validated_semantics],
            "reuse_report": report.reuse_report.model_dump(mode="json") if report.reuse_report else None,
        },
        "quality": repo.get_quality_report(analysis_id).model_dump(mode="json")
            if repo.get_quality_report(analysis_id) is not None else None,
        "source_file_retained_locally": (RAW_DIRECTORY / analysis_id).is_dir(),
        "pipeline": {
            "current_stage": item.current_stage.value if item else "SEMANTIC_VALIDATION",
            "last_successful_stage": item.last_successful_stage.value if item else "PROFILING",
            "prepared_dataset_status": item.prepared_dataset_status if item else "not_started",
            "grain_status": item.grain_status if item else "not_started",
            "dimensional_status": item.dimensional_status if item else "not_started",
            "star_schema_status": item.star_schema_status if item else "not_started",
            "ddl_status": item.ddl_status if item else "not_started",
            "etl_plan_status": item.etl_plan_status if item else "not_started",
            "transformation_status": item.transformation_status if item else "not_started",
            "database_dry_run_status": item.database_dry_run_status if item else "not_started",
            "warnings": item.warnings if item else [],
        },
    }


def upload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Objeto JSON obrigatório")
    name = str(payload.get("filename") or "").strip()
    # Only a basename, never a directory or absolute path from the browser.
    if (not name or len(name) > 160 or name in {".", ".."}
            or "/" in name or "\\" in name or Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS):
        raise ValueError("Nome de arquivo inválido; formatos XLSX, XLSM e CSV")
    encoded = payload.get("base64")
    if not isinstance(encoded, str) or len(encoded) > MAX_FILE_BYTES * 4 // 3 + 16:
        raise ValueError("Arquivo excede o limite de 8 MB")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Conteúdo base64 inválido") from error
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Arquivo vazio ou maior que 8 MB")
    business = payload.get("context") or {}
    if not isinstance(business, dict):
        raise ValueError("Contexto inválido")
    ctx = ProjectContext(**{key: str(business.get(key) or "")[:500]
        for key in ("project_name", "business_domain", "purpose", "notes")})
    workbook = load_tabular_file(name, data)
    profile = profile_workbook(workbook, ctx)
    repo = repository()
    document = repo.register_document(data, name)
    analysis = repo.create_analysis(document.source_document_id, profile)
    # Preserve the original locally, outside Git, to make subsequent
    # preparation/modeling reproducible rather than relying on a browser session.
    target_dir = RAW_DIRECTORY / analysis.analysis_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / name
    if target.is_symlink():
        raise ValueError("Destino não permitido")
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".upload-", delete=False) as temporary:
            try:
                temporary.write(data)
                temporary.flush()
                os.fsync(temporary.fileno())
                pending_file = Path(temporary.name)
            except Exception:
                Path(temporary.name).unlink(missing_ok=True)
                raise
        try:
            os.chmod(pending_file, 0o600)
            os.replace(pending_file, target)
        finally:
            pending_file.unlink(missing_ok=True)
    # Quality is provisional and based on the sampled rows. It cannot replace
    # business validation and is not a certified dimensional model.
    quality = analyze_data_quality(workbook, analysis.report)
    repo.save_quality_report(quality)
    return _snapshot(repo, analysis.analysis_id)


def answer(payload):
    if not isinstance(payload, dict):
        raise ValueError("Objeto JSON obrigatório")
    analysis_id = _validated_id(payload.get("analysis_id"))
    question_id = payload.get("question_id")
    selection = payload.get("answer")
    if not isinstance(question_id, str) or len(question_id) > 128:
        raise ValueError("Pergunta inválida")
    if not isinstance(selection, str) or not selection or len(selection) > 200:
        raise ValueError("Resposta inválida")
    comment = payload.get("custom_answer")
    if comment is not None and (not isinstance(comment, str) or len(comment) > 1000):
        raise ValueError("Justificativa inválida")
    repo = repository()
    record = repo.get_analysis(analysis_id)
    if record is None:
        raise ValueError("Análise não encontrada")
    question = next((q for q in record.report.questions if q.question_id == question_id), None)
    if question is None or selection not in question.options:
        raise ValueError("Opção de resposta inválida para esta pergunta")
    repo.save_answer(analysis_id, question_id, selection, comment)
    return _snapshot(repo, analysis_id)


def get(analysis_id):
    return _snapshot(repository(), _validated_id(analysis_id))


def capabilities():
    return {
        "interface": "React 8506", "engine": "existing core/* Python + SQLite",
        "file_types": sorted(SUPPORTED_EXTENSIONS),
        "max_file_bytes": MAX_FILE_BYTES,
        "stages": [
            "Ingestão", "Profiling", "Semântica", "Qualidade",
            "Prepared Dataset", "Grão", "Dimensional", "Star",
            "DDL", "ETL", "Transformação", "Dry Run",
        ],
        "active_actions": ["upload", "semantic_questions", "analysis_resume"],
        "note": "Etapas posteriores possuem motores legados recuperados, mas ainda exigem adaptadores e validação antes de serem acionadas no React.",
    }
