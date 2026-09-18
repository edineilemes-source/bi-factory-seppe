from pathlib import Path

import pytest

from core.business.models import (
    BusinessContext,
    BusinessContextStatus,
    ContextProvenance,
    ContextValue,
)
from core.business.persistence import SQLiteBusinessContextStore
from core.business.service import business_context_fingerprint
from core.persistence.sqlite_repository import SQLiteAnalysisRepository


def _store_with_prepared(tmp_path: Path):
    repository = SQLiteAnalysisRepository(tmp_path / "test.sqlite3")
    store = SQLiteBusinessContextStore(repository)
    with repository._connect() as connection:
        connection.execute(
            "INSERT INTO source_documents "
            "(source_document_id, content_sha256, original_name, size_bytes, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("doc-1", "sha-doc-1", "despesas.csv", 10, "2026-09-18T10:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO analyses "
            "(analysis_id, source_document_id, status, profile_json, report_json, "
            "created_at, updated_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "analysis-1",
                "doc-1",
                "in_progress",
                "{}",
                "{}",
                "2026-09-18T10:00:00+00:00",
                "2026-09-18T10:00:00+00:00",
                None,
            ),
        )
        connection.execute(
            "INSERT INTO prepared_datasets "
            "(prepared_dataset_id, analysis_id, source_document_id, version, status, "
            "fingerprint, ruleset_version, row_count, field_count, artifact_location, "
            "metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "prepared-1",
                "analysis-1",
                "doc-1",
                2,
                "READY_WITH_WARNINGS",
                "prepared-fingerprint",
                "prepared-v2",
                181476,
                38,
                "storage/working/prepared/test.csv",
                "{}",
                "2026-09-18T10:00:00+00:00",
            ),
        )
    return repository, store


def _context(objective: str = "Analisar despesas municipais") -> BusinessContext:
    return BusinessContext(
        source_document_id="doc-1",
        analysis_id="analysis-1",
        prepared_dataset_id="prepared-1",
        prepared_dataset_version=2,
        prepared_dataset_fingerprint="prepared-fingerprint",
        analytical_objective=ContextValue(
            value=objective,
            provenance=ContextProvenance.USER_CONFIRMED,
        ),
        business_domain=ContextValue(
            value="Despesa pública municipal",
            provenance=ContextProvenance.USER_CONFIRMED,
        ),
    )


def test_business_context_table_is_initialized(tmp_path: Path):
    repository = SQLiteAnalysisRepository(tmp_path / "test.sqlite3")
    SQLiteBusinessContextStore(repository)
    with repository._connect() as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='business_contexts'"
        ).fetchone()
    assert row is not None


def test_business_context_fingerprint_ignores_persistence_metadata():
    base = _context()
    changed_metadata = base.model_copy(deep=True)
    changed_metadata.business_context_id = "another-id"
    changed_metadata.version = 99
    changed_metadata.fingerprint = "old"

    assert business_context_fingerprint(base) == business_context_fingerprint(changed_metadata)


def test_business_context_fingerprint_changes_with_business_meaning():
    base = _context("Despesas")
    changed = base.model_copy(deep=True)
    changed.analytical_objective.value = "Pagamentos"
    assert business_context_fingerprint(base) != business_context_fingerprint(changed)


def test_business_context_status_and_provenance_contracts():
    assert BusinessContextStatus.VALIDATED.value == "VALIDATED"
    assert ContextProvenance.USER_CORRECTED.value == "USER_CORRECTED"


def test_store_rejects_missing_prepared_dataset(tmp_path: Path):
    repository = SQLiteAnalysisRepository(tmp_path / "test.sqlite3")
    store = SQLiteBusinessContextStore(repository)
    context = BusinessContext(
        source_document_id="doc-missing",
        analysis_id="analysis-missing",
        prepared_dataset_id="prepared-missing",
        prepared_dataset_version=1,
        prepared_dataset_fingerprint="missing",
    )
    with pytest.raises(ValueError, match="Prepared Dataset"):
        store.save(context)


def test_create_read_and_effective_context(tmp_path: Path):
    _, store = _store_with_prepared(tmp_path)
    saved = store.save(_context())

    assert saved.version == 1
    assert saved.context.version == 1
    assert saved.fingerprint == saved.context.fingerprint
    effective = store.get_effective("prepared-1")
    assert effective is not None
    assert effective.analytical_objective.value == "Analisar despesas municipais"
    assert effective.version == 1


def test_identical_save_is_idempotent(tmp_path: Path):
    _, store = _store_with_prepared(tmp_path)
    context = _context()
    first = store.save(context)
    second = store.save(context.model_copy(deep=True))

    assert second.business_context_id == first.business_context_id
    assert second.version == 1
    assert len(store.list_contexts("prepared-1")) == 1


def test_changed_meaning_creates_new_version_and_preserves_history(tmp_path: Path):
    _, store = _store_with_prepared(tmp_path)
    context = _context("Analisar despesas")
    first = store.save(context)
    changed = context.model_copy(deep=True)
    changed.analytical_objective = ContextValue(
        value="Analisar pagamentos por credor",
        provenance=ContextProvenance.USER_CORRECTED,
    )
    second = store.save(changed)

    assert first.version == 1
    assert second.version == 2
    assert second.business_context_id == first.business_context_id
    history = store.list_contexts("prepared-1")
    assert [item.version for item in history] == [2, 1]
    assert history[1].context.analytical_objective.value == "Analisar despesas"
    assert history[0].context.analytical_objective.value == "Analisar pagamentos por credor"
    assert store.get_effective("prepared-1").version == 2


def test_next_version_tracks_history(tmp_path: Path):
    _, store = _store_with_prepared(tmp_path)
    assert store.next_version("prepared-1") == 1
    store.save(_context())
    assert store.next_version("prepared-1") == 2


@pytest.mark.parametrize(
    ("attribute", "wrong_value"),
    [
        ("analysis_id", "analysis-other"),
        ("source_document_id", "doc-other"),
        ("prepared_dataset_version", 99),
        ("prepared_dataset_fingerprint", "wrong-fingerprint"),
    ],
)
def test_store_rejects_prepared_ownership_mismatch(tmp_path: Path, attribute, wrong_value):
    _, store = _store_with_prepared(tmp_path)
    context = _context()
    setattr(context, attribute, wrong_value)

    with pytest.raises(ValueError, match="ownership/versão/fingerprint"):
        store.save(context)
