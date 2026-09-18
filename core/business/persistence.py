"""Versioned persistence for Business Context.

This adapter deliberately extends the existing SQLite database without changing
AnalysisStage or pipeline routing. The existing analysis repository remains the
source of truth for document/analysis/prepared ownership.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.business.models import BusinessContext, BusinessContextRecord
from core.business.service import business_context_fingerprint


class SQLiteBusinessContextStore:
    def __init__(self, analysis_repository) -> None:
        self.analysis_repository = analysis_repository
        self._initialize()

    def _connect(self):
        return self.analysis_repository._connect()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS business_contexts (
                    business_context_id TEXT PRIMARY KEY,
                    source_document_id TEXT NOT NULL REFERENCES source_documents(source_document_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    version INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_business_contexts_dataset
                    ON business_contexts(prepared_dataset_id, version DESC);
                CREATE INDEX IF NOT EXISTS idx_business_contexts_document
                    ON business_contexts(source_document_id, created_at DESC);
                """
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> BusinessContextRecord:
        context = BusinessContext.model_validate_json(row["context_json"])
        return BusinessContextRecord(
            business_context_id=row["business_context_id"],
            source_document_id=row["source_document_id"],
            analysis_id=row["analysis_id"],
            prepared_dataset_id=row["prepared_dataset_id"],
            version=row["version"],
            fingerprint=row["fingerprint"],
            status=row["status"],
            created_at=row["created_at"],
            context=context,
        )

    def next_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version "
                "FROM business_contexts WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,),
            ).fetchone()
        return int(row["version"])

    def list_contexts(self, prepared_dataset_id: str) -> list[BusinessContextRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM business_contexts WHERE prepared_dataset_id = ? "
                "ORDER BY version DESC",
                (prepared_dataset_id,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def get_effective(self, prepared_dataset_id: str) -> BusinessContext | None:
        records = self.list_contexts(prepared_dataset_id)
        return records[0].context if records else None

    def save(self, context: BusinessContext) -> BusinessContextRecord:
        """Persist immutable versions and reuse identical latest content."""
        with self._connect() as connection:
            prepared = connection.execute(
                "SELECT prepared_dataset_id, analysis_id, source_document_id, "
                "version, fingerprint FROM prepared_datasets "
                "WHERE prepared_dataset_id = ?",
                (context.prepared_dataset_id,),
            ).fetchone()
            if prepared is None:
                raise ValueError("Business Context requer Prepared Dataset persistido.")
            if (
                prepared["analysis_id"] != context.analysis_id
                or prepared["source_document_id"] != context.source_document_id
                or int(prepared["version"]) != context.prepared_dataset_version
                or prepared["fingerprint"] != context.prepared_dataset_fingerprint
            ):
                raise ValueError(
                    "Business Context incompatível com ownership/versão/fingerprint "
                    "do Prepared Dataset."
                )

            fingerprint = business_context_fingerprint(context)
            latest = connection.execute(
                "SELECT * FROM business_contexts WHERE prepared_dataset_id = ? "
                "ORDER BY version DESC LIMIT 1",
                (context.prepared_dataset_id,),
            ).fetchone()
            if latest is not None and latest["fingerprint"] == fingerprint:
                return self._record(latest)

            now = datetime.now(timezone.utc)
            version = 1 if latest is None else int(latest["version"]) + 1
            persisted = context.model_copy(deep=True)
            persisted.version = version
            persisted.fingerprint = fingerprint
            persisted.updated_at = now
            if latest is None:
                persisted.created_at = now

            connection.execute(
                "INSERT INTO business_contexts "
                "(business_context_id, source_document_id, analysis_id, "
                "prepared_dataset_id, version, fingerprint, status, context_json, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    persisted.business_context_id,
                    persisted.source_document_id,
                    persisted.analysis_id,
                    persisted.prepared_dataset_id,
                    persisted.version,
                    persisted.fingerprint,
                    persisted.status.value,
                    persisted.model_dump_json(),
                    persisted.created_at.isoformat(),
                    persisted.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM business_contexts WHERE business_context_id = ?",
                (persisted.business_context_id,),
            ).fetchone()
        return self._record(row)
