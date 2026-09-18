from pathlib import Path

from core.business.models import (
    BusinessContext,
    BusinessContextStatus,
    ContextProvenance,
    ContextValue,
)
from core.business.persistence import SQLiteBusinessContextStore
from core.business.service import business_context_fingerprint
from core.persistence.sqlite_repository import SQLiteAnalysisRepository


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
    base = BusinessContext(
        source_document_id="doc-1",
        analysis_id="analysis-1",
        prepared_dataset_id="prepared-1",
        prepared_dataset_version=2,
        prepared_dataset_fingerprint="prepared-fingerprint",
        analytical_objective=ContextValue(
            value="Analisar despesas municipais",
            provenance=ContextProvenance.USER_CONFIRMED,
        ),
    )
    changed_metadata = base.model_copy(deep=True)
    changed_metadata.business_context_id = "another-id"
    changed_metadata.version = 99
    changed_metadata.fingerprint = "old"

    assert business_context_fingerprint(base) == business_context_fingerprint(changed_metadata)


def test_business_context_fingerprint_changes_with_business_meaning():
    base = BusinessContext(
        source_document_id="doc-1",
        analysis_id="analysis-1",
        prepared_dataset_id="prepared-1",
        prepared_dataset_version=2,
        prepared_dataset_fingerprint="prepared-fingerprint",
        analytical_objective=ContextValue(value="Despesas"),
    )
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
    try:
        store.save(context)
    except ValueError as exc:
        assert "Prepared Dataset" in str(exc)
    else:
        raise AssertionError("ownership inválido deveria ser rejeitado")
