"""SQLite implementation of the analysis repository."""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.persistence.models import (
    AnalysisHistoryItem, AnalysisRecord, AnalysisResumeResult, AnalysisStage,
    GrainDefinitionRecord, GrainDiscoveryRecord,
    PreparedDatasetRecord, SourceDocument, DimensionalDiscoveryRecord,
    ValidatedDimensionalRecord,
    StarSchemaContractRecord, ValidatedStarSchemaRecord,
    PhysicalSchemaPlanRecord, PostgreSQLDDLArtifactRecord,
    DimensionalETLPlanRecord, ValidatedDimensionalETLPlanRecord,
    DimensionalTransformationRunRecord,
    DatabaseDryRunRecord,
)
from core.profiling.models import WorkbookProfile
from core.semantic.models import AnalysisStatus, QuestionStatus, SemanticValidationReport
from core.semantic.models import (KnowledgeValidationSource, KnowledgeValidationStatus,
                                  SemanticKnowledgeRecord, ValidationStatus)
from core.semantic.knowledge import semantic_fingerprint
from core.semantic.validation_service import answer_question, create_validation_report
from core.quality.models import DataQualityReport
from core.prepared.models import (PreparedDataset, PreparedDatasetArtifact,
                                  PreparedGenerationStatus)
from core.grain.models import GrainDefinition, GrainDiscoveryReport
from core.grain.validation import effective_grain
from core.dimensional.models import DimensionalDiscoveryReport, ValidatedDimensionalDiscovery
from core.dimensional.validation import effective_dimensional_discovery
from core.star.models import StarSchemaContract, StarSchemaContractReport, ValidatedStarSchemaContract
from core.star.validation import effective_star_schema_contract
from core.ddl.models import PhysicalSchemaPlan, PostgreSQLDDLArtifact
from core.etl.models import DimensionalETLPlan, ValidatedDimensionalETLPlan
from core.etl.validation import effective_dimensional_etl_plan
from core.transformation.models import DimensionalTransformationRun
from core.database_dry_run.models import DatabaseDryRun


DEFAULT_DATABASE_PATH = Path("storage/bi_factory.sqlite3")
LOGGER = logging.getLogger(__name__)


class SQLiteAnalysisRepository:
    def __init__(self, database_path: Path | str = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS source_documents (
                    source_document_id TEXT PRIMARY KEY,
                    content_sha256 TEXT NOT NULL UNIQUE,
                    original_name TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    source_document_id TEXT NOT NULL REFERENCES source_documents(source_document_id),
                    status TEXT NOT NULL,
                    profile_json TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_analyses_document
                    ON analyses(source_document_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS semantic_questions (
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
                    question_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    question_json TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, question_id)
                );
                CREATE TABLE IF NOT EXISTS semantic_answers (
                    analysis_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    custom_answer TEXT,
                    answered_at TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, question_id),
                    FOREIGN KEY (analysis_id, question_id)
                        REFERENCES semantic_questions(analysis_id, question_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS semantic_knowledge (
                    semantic_knowledge_id TEXT NOT NULL,
                    source_document_id TEXT NOT NULL,
                    source_field_id TEXT NOT NULL,
                    normalized_field_name TEXT NOT NULL,
                    business_concept_id TEXT NOT NULL,
                    validated_semantic_role TEXT NOT NULL,
                    validation_source TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    knowledge_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (semantic_knowledge_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_semantic_knowledge_document_field
                    ON semantic_knowledge(source_document_id, source_field_id, version DESC);
                CREATE TABLE IF NOT EXISTS data_quality_reports (
                    analysis_id TEXT PRIMARY KEY REFERENCES analyses(analysis_id) ON DELETE CASCADE,
                    status TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS data_quality_report_versions (
                    quality_report_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    fingerprint TEXT,
                    status TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(analysis_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_quality_versions_analysis
                    ON data_quality_report_versions(analysis_id, version DESC);
                CREATE TABLE IF NOT EXISTS prepared_datasets (
                    prepared_dataset_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id) ON DELETE CASCADE,
                    source_document_id TEXT NOT NULL REFERENCES source_documents(source_document_id),
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    field_count INTEGER NOT NULL,
                    artifact_location TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(analysis_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_prepared_analysis
                    ON prepared_datasets(analysis_id, version DESC);
                CREATE TABLE IF NOT EXISTS prepared_generations (
                    prepared_dataset_id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    reason TEXT,
                    metrics_json TEXT,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_prepared_generations_analysis
                    ON prepared_generations(analysis_id, version DESC);
                CREATE TABLE IF NOT EXISTS grain_discovery_reports (
                    grain_discovery_report_id TEXT PRIMARY KEY,
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_grain_reports_dataset
                    ON grain_discovery_reports(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS grain_definitions (
                    grain_id TEXT PRIMARY KEY,
                    grain_discovery_report_id TEXT NOT NULL
                        REFERENCES grain_discovery_reports(grain_discovery_report_id),
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    definition_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_grain_definitions_dataset
                    ON grain_definitions(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS dimensional_discovery_reports (
                    report_id TEXT PRIMARY KEY,
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    grain_definition_id TEXT NOT NULL REFERENCES grain_definitions(grain_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, grain_definition_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_dimensional_reports_dataset
                    ON dimensional_discovery_reports(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS validated_dimensional_discoveries (
                    validation_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL REFERENCES dimensional_discovery_reports(report_id),
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    grain_definition_id TEXT NOT NULL REFERENCES grain_definitions(grain_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, grain_definition_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_validated_dimensional_dataset
                    ON validated_dimensional_discoveries(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS star_schema_contract_reports (
                    report_id TEXT PRIMARY KEY,
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    dimensional_discovery_id TEXT NOT NULL REFERENCES validated_dimensional_discoveries(validation_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, dimensional_discovery_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_star_reports_dataset
                    ON star_schema_contract_reports(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS validated_star_schema_contracts (
                    validation_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL REFERENCES star_schema_contract_reports(report_id),
                    prepared_dataset_id TEXT NOT NULL REFERENCES prepared_datasets(prepared_dataset_id),
                    dimensional_discovery_id TEXT NOT NULL REFERENCES validated_dimensional_discoveries(validation_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, dimensional_discovery_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_validated_star_dataset
                    ON validated_star_schema_contracts(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS physical_schema_plans (
                    physical_schema_plan_id TEXT PRIMARY KEY,
                    star_schema_contract_id TEXT NOT NULL,
                    prepared_dataset_id TEXT NOT NULL,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(star_schema_contract_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_physical_plans_dataset
                    ON physical_schema_plans(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS postgresql_ddl_artifacts (
                    ddl_artifact_id TEXT PRIMARY KEY,
                    physical_schema_plan_id TEXT NOT NULL REFERENCES physical_schema_plans(physical_schema_plan_id),
                    prepared_dataset_id TEXT NOT NULL,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    sql_text TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    human_validated INTEGER NOT NULL DEFAULT 0,
                    generated_at TEXT NOT NULL,
                    UNIQUE(physical_schema_plan_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_ddl_artifacts_dataset
                    ON postgresql_ddl_artifacts(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS dimensional_etl_plans (
                    etl_plan_id TEXT PRIMARY KEY,
                    physical_schema_plan_id TEXT NOT NULL REFERENCES physical_schema_plans(physical_schema_plan_id),
                    ddl_artifact_id TEXT NOT NULL REFERENCES postgresql_ddl_artifacts(ddl_artifact_id),
                    prepared_dataset_id TEXT NOT NULL,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    fingerprint TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(physical_schema_plan_id, version)
                );
                CREATE TABLE IF NOT EXISTS validated_dimensional_etl_plans (
                    validation_id TEXT PRIMARY KEY,
                    etl_plan_id TEXT NOT NULL REFERENCES dimensional_etl_plans(etl_plan_id),
                    prepared_dataset_id TEXT NOT NULL,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    version INTEGER NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(prepared_dataset_id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_validated_etl_dataset
                    ON validated_dimensional_etl_plans(prepared_dataset_id, version DESC);
                CREATE TABLE IF NOT EXISTS dimensional_transformation_runs (
                    run_id TEXT PRIMARY KEY,
                    etl_plan_id TEXT NOT NULL REFERENCES dimensional_etl_plans(etl_plan_id),
                    prepared_dataset_id TEXT NOT NULL,
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    status TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    artifact_root TEXT,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transformation_checkpoints (
                    run_id TEXT NOT NULL REFERENCES dimensional_transformation_runs(run_id),
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL,
                    completed_at TEXT,
                    PRIMARY KEY (run_id, step_id)
                );
                CREATE TABLE IF NOT EXISTS database_dry_runs (
                    dry_run_id TEXT PRIMARY KEY,
                    transformation_run_id TEXT NOT NULL REFERENCES dimensional_transformation_runs(run_id),
                    analysis_id TEXT NOT NULL REFERENCES analyses(analysis_id),
                    status TEXT NOT NULL,
                    test_schema TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_database_dry_runs_transformation
                    ON database_dry_runs(transformation_run_id, created_at DESC);
            """)

    @staticmethod
    def document_id(content: bytes) -> tuple[str, str]:
        digest = hashlib.sha256(content).hexdigest()
        return f"sha256:{digest}", digest

    def register_document(self, content: bytes, original_name: str) -> SourceDocument:
        source_document_id, digest = self.document_id(content)
        now = datetime.now(timezone.utc)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO source_documents VALUES (?, ?, ?, ?, ?)",
                (source_document_id, digest, original_name, len(content), now.isoformat()),
            )
            row = connection.execute(
                "SELECT * FROM source_documents WHERE source_document_id = ?", (source_document_id,)
            ).fetchone()
        return SourceDocument(**dict(row))

    def find_document(self, content: bytes) -> SourceDocument | None:
        source_document_id, _ = self.document_id(content)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_documents WHERE source_document_id = ?", (source_document_id,)
            ).fetchone()
        return SourceDocument(**dict(row)) if row else None

    def _record(self, row: sqlite3.Row) -> AnalysisRecord:
        report = SemanticValidationReport.model_validate_json(row["report_json"])
        return AnalysisRecord(
            analysis_id=row["analysis_id"], source_document_id=row["source_document_id"],
            status=row["status"], created_at=row["created_at"], updated_at=row["updated_at"],
            completed_at=row["completed_at"], report=report,
        )

    def list_analyses(self, source_document_id: str) -> list[AnalysisRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM analyses WHERE source_document_id = ? "
                "ORDER BY created_at DESC, analysis_id DESC",
                (source_document_id,),
            ).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _presence(connection: sqlite3.Connection, table: str, analysis_id: str,
                  order: str = "created_at") -> sqlite3.Row | None:
        # Table/order values are internal constants, never user input.
        return connection.execute(
            f"SELECT * FROM {table} WHERE analysis_id = ? ORDER BY {order} DESC LIMIT 1",
            (analysis_id,),
        ).fetchone()

    def list_analyses_for_document(self, source_document_id: str) -> list[AnalysisHistoryItem]:
        """Return every analysis as a deterministic metadata-only projection."""
        with self._connect() as connection:
            analyses = connection.execute(
                "SELECT * FROM analyses WHERE source_document_id = ? "
                "ORDER BY created_at DESC, analysis_id DESC", (source_document_id,),
            ).fetchall()
            result = [self._history_item(connection, row, index == 0)
                      for index, row in enumerate(analyses)]
        LOGGER.info("analysis_history_loaded source_document_id=%s count=%d",
                    source_document_id, len(result))
        return result

    def _history_item(self, connection: sqlite3.Connection, row: sqlite3.Row,
                      is_latest: bool) -> AnalysisHistoryItem:
        analysis_id = row["analysis_id"]
        report = SemanticValidationReport.model_validate_json(row["report_json"])
        answers = connection.execute(
            "SELECT COUNT(*) count FROM semantic_answers WHERE analysis_id=?", (analysis_id,),
        ).fetchone()["count"]
        total = len(report.questions)
        reused = sum(1 for validation in report.validated_semantics if validation.knowledge_reused)
        quality = self._presence(connection, "data_quality_reports", analysis_id, "updated_at")
        prepared = self._presence(connection, "prepared_datasets", analysis_id, "version")
        grain_report = self._presence(connection, "grain_discovery_reports", analysis_id, "version")
        grain = self._presence(connection, "grain_definitions", analysis_id, "version")
        dimensional_report = self._presence(connection, "dimensional_discovery_reports", analysis_id, "version")
        dimensional = self._presence(connection, "validated_dimensional_discoveries", analysis_id, "version")
        star_report = self._presence(connection, "star_schema_contract_reports", analysis_id, "version")
        star = self._presence(connection, "validated_star_schema_contracts", analysis_id, "version")
        physical = self._presence(connection, "physical_schema_plans", analysis_id, "version")
        ddl = self._presence(connection, "postgresql_ddl_artifacts", analysis_id, "version")
        etl = self._presence(connection, "dimensional_etl_plans", analysis_id, "version")
        etl_validated = self._presence(connection, "validated_dimensional_etl_plans", analysis_id, "version")
        transformation = self._presence(connection, "dimensional_transformation_runs", analysis_id)
        dry_run = self._presence(connection, "database_dry_runs", analysis_id)

        semantic_done = row["status"] != AnalysisStatus.IN_PROGRESS.value and answers >= total
        # Current means the first absent/incomplete stage; persisted artifacts are truth.
        if not semantic_done:
            current, last = AnalysisStage.SEMANTIC_VALIDATION, AnalysisStage.PROFILING
        elif quality is None or quality["status"] in ("not_started", "running"):
            current, last = AnalysisStage.QUALITY, AnalysisStage.SEMANTIC_VALIDATION
        elif prepared is None:
            current, last = AnalysisStage.PREPARED_DATASET, AnalysisStage.QUALITY
        elif grain is None:
            current, last = AnalysisStage.GRAIN_DISCOVERY, AnalysisStage.PREPARED_DATASET
        elif dimensional is None:
            current, last = AnalysisStage.DIMENSIONAL_DISCOVERY, AnalysisStage.GRAIN_DISCOVERY
        elif star is None:
            current, last = AnalysisStage.STAR_SCHEMA, AnalysisStage.DIMENSIONAL_DISCOVERY
        elif ddl is None:
            current, last = AnalysisStage.DDL, AnalysisStage.STAR_SCHEMA
        elif etl_validated is None:
            current, last = AnalysisStage.ETL_PLAN, AnalysisStage.DDL
        elif transformation is None or transformation["status"].lower() not in ("completed", "success", "succeeded"):
            current, last = AnalysisStage.TRANSFORMATION, AnalysisStage.ETL_PLAN
        elif dry_run is None:
            current, last = AnalysisStage.DATABASE_DRY_RUN, AnalysisStage.TRANSFORMATION
        elif dry_run["status"].lower() in ("completed", "success", "succeeded", "passed"):
            current = last = AnalysisStage.COMPLETED
        else:
            current, last = AnalysisStage.DATABASE_DRY_RUN, AnalysisStage.TRANSFORMATION

        qdata = json.loads(quality["report_json"]) if quality else {}
        artifact_rows = [quality, prepared, grain_report, grain, dimensional_report,
                         dimensional, star_report, star, physical, ddl, etl,
                         etl_validated, transformation, dry_run]
        artifact_ids: dict[str, str] = {}
        for name, artifact, key in (
            ("quality_report", quality, "analysis_id"),
            ("prepared_dataset", prepared, "prepared_dataset_id"),
            ("grain_definition", grain, "grain_id"),
            ("dimensional_validation", dimensional, "validation_id"),
            ("star_schema_validation", star, "validation_id"),
            ("physical_schema_plan", physical, "physical_schema_plan_id"),
            ("ddl_artifact", ddl, "ddl_artifact_id"), ("etl_plan", etl, "etl_plan_id"),
            ("transformation_run", transformation, "run_id"),
            ("database_dry_run", dry_run, "dry_run_id"),
        ):
            if artifact is not None:
                artifact_ids[name] = artifact[key]
        completed = current == AnalysisStage.COMPLETED
        warnings: list[str] = []
        if quality is not None and qdata.get("analysis_id") != analysis_id:
            warnings.append("ANALYSIS_RECOVERY_WARNING: quality report pertence a outra análise")
        if prepared is not None and prepared["source_document_id"] != row["source_document_id"]:
            warnings.append("ANALYSIS_RECOVERY_WARNING: prepared dataset pertence a outro documento")
        dependencies = (
            (grain_report or grain, prepared, "grão", "prepared dataset"),
            (dimensional_report or dimensional, grain, "dimensional", "grão validado"),
            (star_report or star, dimensional, "star schema", "dimensional validado"),
            (physical or ddl, star, "DDL", "star schema validado"),
            (etl or etl_validated, ddl, "ETL", "DDL"),
            (transformation, etl_validated, "transformação", "ETL validado"),
            (dry_run, transformation, "dry run", "transformação"),
        )
        for child, parent, child_name, parent_name in dependencies:
            if child is not None and parent is None:
                warnings.append(
                    f"ANALYSIS_RECOVERY_WARNING: {child_name} sem {parent_name} da mesma análise"
                )
        return AnalysisHistoryItem(
            analysis_id=analysis_id, source_document_id=row["source_document_id"],
            created_at=row["created_at"], updated_at=row["updated_at"], completed_at=row["completed_at"],
            status="completed" if completed else "in_progress", semantic_status=row["status"],
            semantic_question_count=total, semantic_answered_count=answers,
            semantic_pending_count=max(total - answers, 0), semantic_reuse_count=reused,
            quality_status=quality["status"] if quality else "not_started",
            quality_report_id=qdata.get("quality_report_id") if quality else None,
            quality_score=qdata.get("score"),
            quality_issue_count=qdata.get("issues_count", 0),
            prepared_dataset_status=prepared["status"] if prepared else "not_started",
            prepared_dataset_id=prepared["prepared_dataset_id"] if prepared else None,
            prepared_dataset_version=prepared["version"] if prepared else None,
            grain_status="validated" if grain else "discovered" if grain_report else "not_started",
            grain_definition_id=grain["grain_id"] if grain else None,
            dimensional_status="validated" if dimensional else "discovered" if dimensional_report else "not_started",
            star_schema_status="validated" if star else "discovered" if star_report else "not_started",
            ddl_status="generated" if ddl else "planned" if physical else "not_started",
            etl_plan_status="validated" if etl_validated else "planned" if etl else "not_started",
            transformation_status=transformation["status"] if transformation else "not_started",
            database_dry_run_status=dry_run["status"] if dry_run else "not_started",
            current_stage=current, last_successful_stage=last,
            artifact_count=sum(item is not None for item in artifact_rows),
            has_unfinished_work=not completed, is_completed=completed, is_latest=is_latest,
            is_resumable=not completed and not warnings, artifact_ids=artifact_ids, warnings=warnings,
        )

    def resume_analysis(self, analysis_id: str,
                        source_document_id: str | None = None) -> AnalysisResumeResult:
        """Validate and describe recovery of exactly one analysis; never fall back."""
        record = self.get_analysis(analysis_id)
        if record is None:
            LOGGER.warning("resume_failed analysis_id=%s reason=not_found", analysis_id)
            raise ValueError(f"Análise não encontrada: {analysis_id}")
        if source_document_id is not None and record.source_document_id != source_document_id:
            LOGGER.warning("resume_failed analysis_id=%s reason=document_mismatch", analysis_id)
            raise ValueError("ANALYSIS_RECOVERY_WARNING: análise não pertence ao documento selecionado")
        items = self.list_analyses_for_document(record.source_document_id)
        item = next(value for value in items if value.analysis_id == analysis_id)
        if item.warnings:
            LOGGER.warning("resume_failed analysis_id=%s reason=ownership", analysis_id)
            raise ValueError("; ".join(item.warnings))
        loaded: dict[str, object] = {"profile": record.report.observed_profile,
                                    "semantic_validation": record.report,
                                    "semantic_answers": self.get_answers(analysis_id)}
        quality = self.get_quality_report(analysis_id)
        if quality is not None:
            loaded["quality_report"] = quality
        loaded["artifact_ids"] = item.artifact_ids
        LOGGER.info("analysis_resumed analysis_id=%s current_stage=%s",
                    analysis_id, item.current_stage.value)
        return AnalysisResumeResult(
            analysis_id=analysis_id, source_document_id=record.source_document_id,
            current_stage=item.current_stage, last_successful_stage=item.last_successful_stage,
            loaded_artifacts=loaded, warnings=item.warnings,
            missing_artifacts=[], resumable=item.is_resumable, status=item.status,
        )

    def create_analysis(self, source_document_id: str, profile: WorkbookProfile) -> AnalysisRecord:
        from core.semantic.knowledge_migration import migrate_historical_semantic_knowledge
        migrate_historical_semantic_knowledge(self.database_path)
        analysis_id = str(uuid4())
        report = create_validation_report(profile, prior_knowledge=self.list_semantic_knowledge(source_document_id))
        report.analysis_id = analysis_id
        report.source_document_id = source_document_id
        if report.reuse_report:
            report.reuse_report.analysis_id=analysis_id
            report.reuse_report.source_document_id=source_document_id
        if not report.questions:
            report.analysis_status = AnalysisStatus.COMPLETED
        return self.save_report(report)

    def list_semantic_knowledge(self, source_document_id: str, *, history: bool=False) -> list[SemanticKnowledgeRecord]:
        with self._connect() as connection:
            if history:
                rows=connection.execute("SELECT knowledge_json FROM semantic_knowledge WHERE source_document_id=? ORDER BY source_field_id,version",
                                        (source_document_id,)).fetchall()
            else:
                rows=connection.execute("""SELECT k.knowledge_json FROM semantic_knowledge k
                    JOIN (SELECT semantic_knowledge_id,MAX(version) version FROM semantic_knowledge
                          WHERE source_document_id=? GROUP BY semantic_knowledge_id) latest
                    ON latest.semantic_knowledge_id=k.semantic_knowledge_id AND latest.version=k.version""",
                    (source_document_id,)).fetchall()
        return [SemanticKnowledgeRecord.model_validate_json(row["knowledge_json"]) for row in rows]

    def _sync_semantic_knowledge(self, connection: sqlite3.Connection, report: SemanticValidationReport) -> None:
        fields={f"{sheet.name}::{field.technical_name}":field for sheet in report.observed_profile.sheets for field in sheet.fields}
        source_map={ValidationStatus.USER_CORRECTED:KnowledgeValidationSource.USER_CORRECTED,
                    ValidationStatus.USER_CONFIRMED:KnowledgeValidationSource.USER_CONFIRMED,
                    ValidationStatus.AUTO_ACCEPTED:KnowledgeValidationSource.AUTO_ACCEPTED}
        for validation in report.validated_semantics:
            if validation.knowledge_reused and validation.validation_status == ValidationStatus.AUTO_ACCEPTED:
                continue
            if (validation.validated_role is None and validation.semantic_knowledge_id
                    and validation.previous_validated_role is not None):
                row=connection.execute("SELECT knowledge_json FROM semantic_knowledge WHERE semantic_knowledge_id=? ORDER BY version DESC LIMIT 1",
                                       (validation.semantic_knowledge_id,)).fetchone()
                previous=SemanticKnowledgeRecord.model_validate_json(row["knowledge_json"]) if row else None
                if previous and not (previous.validation_status==KnowledgeValidationStatus.NEEDS_RECONFIRMATION
                                     and previous.last_confirmed_analysis_id==report.analysis_id):
                    flagged=previous.model_copy(deep=True)
                    flagged.version+=1; flagged.validation_status=KnowledgeValidationStatus.NEEDS_RECONFIRMATION
                    flagged.last_confirmed_analysis_id=report.analysis_id; flagged.updated_at=datetime.now(timezone.utc)
                    connection.execute("INSERT INTO semantic_knowledge VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (flagged.semantic_knowledge_id,flagged.source_document_id,flagged.source_field_id,
                         flagged.normalized_field_name,flagged.business_concept_id,flagged.validated_semantic_role.value,
                         flagged.validation_source.value,flagged.validation_status.value,flagged.version,
                         flagged.model_dump_json(),flagged.created_at.isoformat(),flagged.updated_at.isoformat()))
                continue
            if validation.validated_role is None or validation.validation_status not in source_map: continue
            field=fields[validation.source_field_id]
            knowledge_id=validation.semantic_knowledge_id or f"knowledge:{report.source_document_id}:{validation.source_field_id}"
            row=connection.execute("SELECT knowledge_json FROM semantic_knowledge WHERE semantic_knowledge_id=? ORDER BY version DESC LIMIT 1",(knowledge_id,)).fetchone()
            previous=SemanticKnowledgeRecord.model_validate_json(row["knowledge_json"]) if row else None
            validation_source=source_map[validation.validation_status]
            if (previous and previous.validated_semantic_role==validation.validated_role
                    and previous.validation_source==validation_source
                    and previous.last_confirmed_analysis_id==report.analysis_id): continue
            now=datetime.now(timezone.utc); version=(previous.version+1 if previous else 1)
            record=SemanticKnowledgeRecord(semantic_knowledge_id=knowledge_id,
                source_document_id=report.source_document_id,source_field_id=validation.source_field_id,
                normalized_field_name=validation.technical_name,
                business_concept_id=validation.business_concept_id or f"concept:{validation.technical_name}",
                validated_semantic_role=validation.validated_role,validation_source=validation_source,
                confidence=validation.original_confidence,validation_status=KnowledgeValidationStatus.VALIDATED,
                first_validated_analysis_id=previous.first_validated_analysis_id if previous else report.analysis_id,
                last_confirmed_analysis_id=report.analysis_id,created_at=previous.created_at if previous else now,
                updated_at=now,evidence_snapshot=field.semantic_evidence,
                compatibility_fingerprint=semantic_fingerprint(field),version=version)
            validation.semantic_knowledge_id=knowledge_id
            connection.execute("INSERT INTO semantic_knowledge VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (record.semantic_knowledge_id,record.source_document_id,record.source_field_id,
                 record.normalized_field_name,record.business_concept_id,record.validated_semantic_role.value,
                 record.validation_source.value,record.validation_status.value,record.version,
                 record.model_dump_json(),record.created_at.isoformat(),record.updated_at.isoformat()))

    def get_analysis(self, analysis_id: str) -> AnalysisRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM analyses WHERE analysis_id = ?", (analysis_id,)
            ).fetchone()
        return self._record(row) if row else None

    def get_answers(self, analysis_id: str) -> dict[str, dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT question_id, answer, custom_answer FROM semantic_answers WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchall()
        return {
            row["question_id"]: {
                "answer": row["answer"], "custom_answer": row["custom_answer"]
            }
            for row in rows
        }

    def save_report(self, report: SemanticValidationReport) -> AnalysisRecord:
        if not report.analysis_id or not report.source_document_id:
            raise ValueError("analysis_id e source_document_id são obrigatórios para persistir.")
        now = datetime.now(timezone.utc)
        completed_at = now if report.analysis_status != AnalysisStatus.IN_PROGRESS else None
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT created_at FROM analyses WHERE analysis_id = ?", (report.analysis_id,)
            ).fetchone()
            created_at = existing["created_at"] if existing else now.isoformat()
            connection.execute(
                """INSERT INTO analyses
                   (analysis_id, source_document_id, status, profile_json, report_json,
                    created_at, updated_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(analysis_id) DO UPDATE SET
                    status=excluded.status, profile_json=excluded.profile_json,
                    report_json=excluded.report_json, updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at""",
                (report.analysis_id, report.source_document_id, report.analysis_status.value,
                 report.observed_profile.model_dump_json(), report.model_dump_json(),
                 created_at, now.isoformat(), completed_at.isoformat() if completed_at else None),
            )
            for question in report.questions:
                connection.execute(
                    """INSERT INTO semantic_questions VALUES (?, ?, ?, ?)
                       ON CONFLICT(analysis_id, question_id) DO UPDATE SET
                        status=excluded.status, question_json=excluded.question_json""",
                    (report.analysis_id, question.question_id, question.status.value,
                     question.model_dump_json()),
                )
            self._sync_semantic_knowledge(connection,report)
            connection.execute("UPDATE analyses SET report_json=? WHERE analysis_id=?",
                               (report.model_dump_json(),report.analysis_id))
        record = self.get_analysis(report.analysis_id)
        if record is None:
            raise RuntimeError("Falha ao recuperar a análise persistida.")
        return record

    def save_answer(self, analysis_id: str, question_id: str, answer: str,
                    custom_answer: str | None = None) -> AnalysisRecord:
        record = self.get_analysis(analysis_id)
        if record is None:
            raise ValueError(f"Análise não encontrada: {analysis_id}")
        report = record.report
        answer_question(report, question_id, answer, custom_answer)
        if all(q.status != QuestionStatus.PENDING for q in report.questions):
            report.analysis_status = (
                AnalysisStatus.COMPLETED_WITH_UNRESOLVED
                if report.summary.unresolved else AnalysisStatus.COMPLETED
            )
        saved = self.save_report(report)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO semantic_answers
                   (analysis_id, question_id, answer, custom_answer, answered_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(analysis_id, question_id) DO UPDATE SET
                    answer=excluded.answer, custom_answer=excluded.custom_answer,
                    answered_at=excluded.answered_at""",
                (analysis_id, question_id, answer, custom_answer,
                 datetime.now(timezone.utc).isoformat()),
            )
        return self.get_analysis(analysis_id) or saved

    def get_quality_report(self, analysis_id: str) -> DataQualityReport | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM data_quality_reports WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return DataQualityReport.model_validate_json(row["report_json"]) if row else None

    def list_quality_reports(self, analysis_id: str) -> list[DataQualityReport]:
        with self._connect() as connection:
            rows = connection.execute("""SELECT report_json FROM data_quality_report_versions
                WHERE analysis_id=? ORDER BY version DESC""", (analysis_id,)).fetchall()
            if not rows:
                legacy = connection.execute(
                    "SELECT report_json FROM data_quality_reports WHERE analysis_id=?",
                    (analysis_id,)).fetchone()
                rows = [legacy] if legacy else []
        return [DataQualityReport.model_validate_json(row["report_json"]) for row in rows]

    def save_quality_report(self, report: DataQualityReport) -> DataQualityReport:
        if self.get_analysis(report.analysis_id) is None:
            raise ValueError(f"Análise não encontrada: {report.analysis_id}")
        from core.quality.export import quality_report_id
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT report_json FROM data_quality_reports WHERE analysis_id=?",
                (report.analysis_id,)).fetchone()
            latest = connection.execute("""SELECT COALESCE(MAX(version),0) version
                FROM data_quality_report_versions WHERE analysis_id=?""",
                (report.analysis_id,)).fetchone()["version"]
            if existing is not None and latest == 0:
                legacy = DataQualityReport.model_validate_json(existing["report_json"])
                legacy.version = max(legacy.version, 1)
                legacy.quality_report_id = legacy.quality_report_id or quality_report_id(legacy)
                connection.execute("""INSERT OR IGNORE INTO data_quality_report_versions
                    (quality_report_id,analysis_id,version,ruleset_version,fingerprint,status,
                     report_json,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                    (legacy.quality_report_id, legacy.analysis_id, legacy.version,
                     legacy.ruleset_version, legacy.fingerprint, legacy.status.value,
                     legacy.model_dump_json(), legacy.created_at.isoformat()))
                latest = legacy.version
            report.version = int(latest) + 1 if existing is not None else max(report.version, 1)
            report.quality_report_id = None
            report.quality_report_id = quality_report_id(report)
            connection.execute("""INSERT INTO data_quality_report_versions
                (quality_report_id,analysis_id,version,ruleset_version,fingerprint,status,
                 report_json,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (report.quality_report_id, report.analysis_id, report.version,
                 report.ruleset_version, report.fingerprint, report.status.value,
                 report.model_dump_json(), report.created_at.isoformat()))
            connection.execute(
                """INSERT INTO data_quality_reports
                   (analysis_id, status, report_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(analysis_id) DO UPDATE SET
                    status=excluded.status, report_json=excluded.report_json,
                    updated_at=excluded.updated_at""",
                (report.analysis_id, report.status.value, report.model_dump_json(),
                 report.created_at.isoformat(), now),
            )
        restored = self.get_quality_report(report.analysis_id)
        if restored is None:
            raise RuntimeError("Falha ao recuperar o relatório de qualidade persistido.")
        return restored

    def next_prepared_version(self, analysis_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM prepared_datasets WHERE analysis_id = ?",
                (analysis_id,),
            ).fetchone()
        return int(row["version"])

    @staticmethod
    def _prepared_record(row: sqlite3.Row) -> PreparedDatasetRecord:
        return PreparedDatasetRecord(**dict(row))

    def list_prepared_datasets(self, analysis_id: str) -> list[PreparedDatasetRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM prepared_datasets WHERE analysis_id = ? ORDER BY version DESC",
                (analysis_id,),
            ).fetchall()
        return [self._prepared_record(row) for row in rows]

    def save_prepared_dataset(self, dataset: PreparedDataset) -> PreparedDatasetRecord:
        if self.get_analysis(dataset.analysis_id) is None:
            raise ValueError(f"Análise não encontrada: {dataset.analysis_id}")
        # Rows stay in the downloadable artifact/session. SQLite stores metadata,
        # schema and audit transformations, avoiding one record per source cell.
        metadata = dataset.model_dump(exclude={"rows"}, mode="json", by_alias=True)
        import json
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO prepared_datasets
                   (prepared_dataset_id, analysis_id, source_document_id, version,
                    status, fingerprint, ruleset_version, row_count, field_count,
                    artifact_location, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (dataset.prepared_dataset_id, dataset.analysis_id, dataset.source_document_id,
                 dataset.version, dataset.status.value, dataset.fingerprint,
                 dataset.ruleset_version, dataset.row_count, dataset.field_count,
                 dataset.artifact_location, metadata_json, dataset.created_at.isoformat()),
            )
            row = connection.execute(
                "SELECT * FROM prepared_datasets WHERE prepared_dataset_id = ?",
                (dataset.prepared_dataset_id,),
            ).fetchone()
        return self._prepared_record(row)

    def update_prepared_generation(self, prepared_dataset_id: str, analysis_id: str,
                                   version: int, status: PreparedGenerationStatus,
                                   stage: str, reason: str | None = None) -> None:
        if self.get_analysis(analysis_id) is None:
            raise ValueError(f"Análise não encontrada: {analysis_id}")
        now = datetime.now(timezone.utc).isoformat()
        finished = now if status in {PreparedGenerationStatus.COMPLETED,
                                     PreparedGenerationStatus.FAILED,
                                     PreparedGenerationStatus.INTERRUPTED} else None
        with self._connect() as connection:
            connection.execute("""INSERT INTO prepared_generations
                (prepared_dataset_id,analysis_id,version,status,stage,reason,metrics_json,
                 started_at,updated_at,finished_at) VALUES (?,?,?,?,?,?,NULL,?,?,?)
                ON CONFLICT(prepared_dataset_id) DO UPDATE SET status=excluded.status,
                 stage=excluded.stage,reason=excluded.reason,updated_at=excluded.updated_at,
                 finished_at=excluded.finished_at""",
                (prepared_dataset_id, analysis_id, version, status.value, stage, reason,
                 now, now, finished))

    def mark_stale_prepared_generations_interrupted(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute("""UPDATE prepared_generations
                SET status=?,stage='INTERRUPTED',reason='process_restart',updated_at=?,finished_at=?
                WHERE status=?""", (PreparedGenerationStatus.INTERRUPTED.value, now, now,
                                     PreparedGenerationStatus.RUNNING.value))
        return cursor.rowcount

    def save_prepared_artifact(self, artifact: PreparedDatasetArtifact) -> PreparedDatasetRecord:
        from pathlib import Path
        if artifact.generation_status != PreparedGenerationStatus.COMPLETED:
            raise ValueError("Somente artefato Prepared concluído pode ser persistido.")
        if not Path(artifact.artifact_location).is_file() or artifact.artifact_location.endswith(".partial"):
            raise ValueError("Artefato final Prepared ausente.")
        metadata_json = artifact.model_dump_json(by_alias=True)
        with self._connect() as connection:
            connection.execute("""INSERT INTO prepared_datasets
                (prepared_dataset_id,analysis_id,source_document_id,version,status,fingerprint,
                 ruleset_version,row_count,field_count,artifact_location,metadata_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (artifact.prepared_dataset_id, artifact.analysis_id, artifact.source_document_id,
                 artifact.version, artifact.status.value, artifact.fingerprint,
                 artifact.ruleset_version, artifact.row_count, artifact.field_count,
                 artifact.artifact_location, metadata_json, artifact.created_at.isoformat()))
            connection.execute("""UPDATE prepared_generations SET status=?,stage='COMPLETED',
                metrics_json=?,updated_at=?,finished_at=? WHERE prepared_dataset_id=?""",
                (PreparedGenerationStatus.COMPLETED.value, artifact.metrics.model_dump_json(),
                 datetime.now(timezone.utc).isoformat(), artifact.metrics.finished_at.isoformat()
                 if artifact.metrics.finished_at else datetime.now(timezone.utc).isoformat(),
                 artifact.prepared_dataset_id))
            row = connection.execute("SELECT * FROM prepared_datasets WHERE prepared_dataset_id=?",
                                     (artifact.prepared_dataset_id,)).fetchone()
        return self._prepared_record(row)

    def get_prepared_artifact(self, prepared_dataset_id: str) -> PreparedDatasetArtifact | None:
        with self._connect() as connection:
            row = connection.execute("SELECT metadata_json FROM prepared_datasets WHERE prepared_dataset_id=?",
                                     (prepared_dataset_id,)).fetchone()
        if row is None:
            return None
        try:
            return PreparedDatasetArtifact.model_validate_json(row["metadata_json"])
        except Exception:
            LOGGER.exception("prepared_artifact_deserialization_failed prepared_dataset_id=%s",
                             prepared_dataset_id)
            return None

    def next_grain_report_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM grain_discovery_reports WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,),
            ).fetchone()
        return int(row["version"])

    def save_grain_discovery_report(self, report: GrainDiscoveryReport) -> GrainDiscoveryRecord:
        import json
        with self._connect() as connection:
            prepared = connection.execute(
                """SELECT analysis_id, source_document_id, version, fingerprint
                   FROM prepared_datasets WHERE prepared_dataset_id = ?""",
                (report.prepared_dataset_id,),
            ).fetchone()
            if (prepared is None or prepared["analysis_id"] != report.analysis_id
                    or prepared["source_document_id"] != report.source_document_id
                    or prepared["version"] != report.prepared_dataset_version
                    or prepared["fingerprint"] != report.prepared_dataset_fingerprint):
                raise ValueError("Prepared Dataset incompatível com o relatório de grão.")
            connection.execute(
                """INSERT INTO grain_discovery_reports
                   (grain_discovery_report_id, prepared_dataset_id, analysis_id,
                    version, report_json, created_at) VALUES (?, ?, ?, ?, ?, ?)""",
                (report.grain_discovery_report_id, report.prepared_dataset_id,
                 report.analysis_id, report.version,
                 json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                 report.created_at.isoformat()),
            )
        return GrainDiscoveryRecord(
            grain_discovery_report_id=report.grain_discovery_report_id,
            prepared_dataset_id=report.prepared_dataset_id, analysis_id=report.analysis_id,
            version=report.version, created_at=report.created_at, report=report)

    def list_grain_discovery_reports(self, prepared_dataset_id: str) -> list[GrainDiscoveryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM grain_discovery_reports WHERE prepared_dataset_id = ? ORDER BY version DESC",
                (prepared_dataset_id,),
            ).fetchall()
        return [GrainDiscoveryRecord(
            grain_discovery_report_id=row["grain_discovery_report_id"],
            prepared_dataset_id=row["prepared_dataset_id"], analysis_id=row["analysis_id"],
            version=row["version"], created_at=row["created_at"],
            report=GrainDiscoveryReport.model_validate_json(row["report_json"]),
        ) for row in rows]

    def next_grain_definition_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM grain_definitions WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,),
            ).fetchone()
        return int(row["version"])

    def save_grain_definition(self, definition: GrainDefinition) -> GrainDefinitionRecord:
        import json
        with self._connect() as connection:
            report = connection.execute(
                """SELECT prepared_dataset_id, analysis_id, report_json FROM grain_discovery_reports
                   WHERE grain_discovery_report_id = ?""",
                (definition.grain_discovery_report_id,),
            ).fetchone()
            persisted_report = (GrainDiscoveryReport.model_validate_json(report["report_json"])
                                if report is not None else None)
            if (report is None or report["prepared_dataset_id"] != definition.prepared_dataset_id
                    or report["analysis_id"] != definition.analysis_id
                    or persisted_report is None
                    or persisted_report.prepared_dataset_version != definition.prepared_dataset_version
                    or persisted_report.prepared_dataset_fingerprint != definition.prepared_dataset_fingerprint
                    or persisted_report.source_document_id != definition.source_document_id):
                raise ValueError("Relatório de descoberta incompatível com a definição de grão.")
            connection.execute(
                """INSERT INTO grain_definitions
                   (grain_id, grain_discovery_report_id, prepared_dataset_id,
                    analysis_id, version, definition_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (definition.grain_id, definition.grain_discovery_report_id,
                 definition.prepared_dataset_id, definition.analysis_id, definition.version,
                 json.dumps(definition.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                 definition.created_at.isoformat()),
            )
        return GrainDefinitionRecord(
            grain_id=definition.grain_id,
            grain_discovery_report_id=definition.grain_discovery_report_id,
            prepared_dataset_id=definition.prepared_dataset_id,
            analysis_id=definition.analysis_id, version=definition.version,
            created_at=definition.created_at, definition=definition)

    def get_effective_grain(self, prepared_dataset_id: str) -> GrainDefinition | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT definition_json FROM grain_definitions
                   WHERE prepared_dataset_id = ? ORDER BY version DESC LIMIT 1""",
                (prepared_dataset_id,),
            ).fetchone()
        if row is None:
            return None
        return effective_grain(GrainDefinition.model_validate_json(row["definition_json"]))

    def next_dimensional_report_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 version FROM dimensional_discovery_reports WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,)).fetchone()
        return int(row["version"])

    def save_dimensional_discovery_report(self, report: DimensionalDiscoveryReport) -> DimensionalDiscoveryRecord:
        import json
        with self._connect() as connection:
            grain = connection.execute(
                "SELECT definition_json FROM grain_definitions WHERE grain_id = ?",
                (report.grain_definition_id,)).fetchone()
            definition = GrainDefinition.model_validate_json(grain["definition_json"]) if grain else None
            if (definition is None or definition.prepared_dataset_id != report.prepared_dataset_id
                    or definition.analysis_id != report.analysis_id
                    or definition.version != report.grain_version
                    or definition.prepared_dataset_version != report.prepared_dataset_version
                    or definition.prepared_dataset_fingerprint != report.prepared_dataset_fingerprint
                    or definition.source_document_id != report.source_document_id):
                raise ValueError("Effective Grain incompatível com a descoberta dimensional.")
            connection.execute(
                "INSERT INTO dimensional_discovery_reports VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report.report_id, report.prepared_dataset_id, report.grain_definition_id,
                 report.analysis_id, report.version,
                 json.dumps(report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                 report.created_at.isoformat()))
        return DimensionalDiscoveryRecord(
            report_id=report.report_id, prepared_dataset_id=report.prepared_dataset_id,
            grain_definition_id=report.grain_definition_id, analysis_id=report.analysis_id,
            version=report.version, created_at=report.created_at, report=report)

    def list_dimensional_discovery_reports(self, prepared_dataset_id: str) -> list[DimensionalDiscoveryRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM dimensional_discovery_reports WHERE prepared_dataset_id = ? ORDER BY version DESC",
                (prepared_dataset_id,)).fetchall()
        return [DimensionalDiscoveryRecord(
            report_id=row["report_id"], prepared_dataset_id=row["prepared_dataset_id"],
            grain_definition_id=row["grain_definition_id"], analysis_id=row["analysis_id"],
            version=row["version"], created_at=row["created_at"],
            report=DimensionalDiscoveryReport.model_validate_json(row["report_json"])) for row in rows]

    def next_dimensional_validation_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 version FROM validated_dimensional_discoveries WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,)).fetchone()
        return int(row["version"])

    def save_validated_dimensional_discovery(self, validation: ValidatedDimensionalDiscovery) -> ValidatedDimensionalRecord:
        import json
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM dimensional_discovery_reports WHERE report_id = ?",
                (validation.report_id,)).fetchone()
            report = DimensionalDiscoveryReport.model_validate_json(row["report_json"]) if row else None
            if (report is None or report.prepared_dataset_id != validation.prepared_dataset_id
                    or report.grain_definition_id != validation.grain_definition_id
                    or report.analysis_id != validation.analysis_id
                    or report.prepared_dataset_version != validation.prepared_dataset_version
                    or report.prepared_dataset_fingerprint != validation.prepared_dataset_fingerprint
                    or report.grain_version != validation.grain_version
                    or report.source_document_id != validation.source_document_id):
                raise ValueError("Proposta dimensional incompatível com a validação.")
            connection.execute(
                "INSERT INTO validated_dimensional_discoveries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (validation.validation_id, validation.report_id, validation.prepared_dataset_id,
                 validation.grain_definition_id, validation.analysis_id, validation.version,
                 validation.model_dump_json(), validation.validated_at.isoformat()))
        return ValidatedDimensionalRecord(
            validation_id=validation.validation_id, report_id=validation.report_id,
            prepared_dataset_id=validation.prepared_dataset_id,
            grain_definition_id=validation.grain_definition_id, analysis_id=validation.analysis_id,
            version=validation.version, created_at=validation.validated_at, validation=validation)

    def get_effective_dimensional_discovery(self, prepared_dataset_id: str) -> ValidatedDimensionalDiscovery | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT validation_json FROM validated_dimensional_discoveries WHERE prepared_dataset_id = ? ORDER BY version DESC LIMIT 1",
                (prepared_dataset_id,)).fetchone()
        return effective_dimensional_discovery(
            ValidatedDimensionalDiscovery.model_validate_json(row["validation_json"]) if row else None)

    def next_star_schema_report_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 version FROM star_schema_contract_reports WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,)).fetchone()
        return int(row["version"])

    def save_star_schema_contract_report(self, report: StarSchemaContractReport) -> StarSchemaContractRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT validation_json FROM validated_dimensional_discoveries WHERE validation_id = ?",
                (report.contract.dimensional_discovery_id,)).fetchone()
            dimensional = ValidatedDimensionalDiscovery.model_validate_json(row["validation_json"]) if row else None
            lineage = report.lineage
            if (dimensional is None or dimensional.prepared_dataset_id != lineage.prepared_dataset_id
                    or dimensional.prepared_dataset_version != lineage.prepared_dataset_version
                    or dimensional.prepared_dataset_fingerprint != lineage.prepared_dataset_fingerprint
                    or dimensional.grain_definition_id != lineage.grain_definition_id
                    or dimensional.grain_version != lineage.grain_version
                    or dimensional.analysis_id != lineage.analysis_id
                    or dimensional.source_document_id != lineage.source_document_id
                    or dimensional.version != lineage.dimensional_discovery_version):
                raise ValueError("Effective Dimensional Discovery incompatível com o Star Schema Contract.")
            connection.execute(
                "INSERT INTO star_schema_contract_reports VALUES (?, ?, ?, ?, ?, ?, ?)",
                (report.report_id, lineage.prepared_dataset_id, lineage.dimensional_discovery_id,
                 lineage.analysis_id, report.version, report.model_dump_json(), report.created_at.isoformat()))
        return StarSchemaContractRecord(
            report_id=report.report_id, prepared_dataset_id=lineage.prepared_dataset_id,
            dimensional_discovery_id=lineage.dimensional_discovery_id,
            analysis_id=lineage.analysis_id, version=report.version,
            created_at=report.created_at, report=report)

    def list_star_schema_contract_reports(self, prepared_dataset_id: str) -> list[StarSchemaContractRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM star_schema_contract_reports WHERE prepared_dataset_id = ? ORDER BY version DESC",
                (prepared_dataset_id,)).fetchall()
        return [StarSchemaContractRecord(
            report_id=row["report_id"], prepared_dataset_id=row["prepared_dataset_id"],
            dimensional_discovery_id=row["dimensional_discovery_id"], analysis_id=row["analysis_id"],
            version=row["version"], created_at=row["created_at"],
            report=StarSchemaContractReport.model_validate_json(row["report_json"])) for row in rows]

    def next_star_schema_validation_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 version FROM validated_star_schema_contracts WHERE prepared_dataset_id = ?",
                (prepared_dataset_id,)).fetchone()
        return int(row["version"])

    def save_validated_star_schema_contract(self, validation: ValidatedStarSchemaContract) -> ValidatedStarSchemaRecord:
        contract = validation.contract
        with self._connect() as connection:
            row = connection.execute(
                "SELECT report_json FROM star_schema_contract_reports WHERE report_id = ?",
                (validation.report_id,)).fetchone()
            report = StarSchemaContractReport.model_validate_json(row["report_json"]) if row else None
            if (report is None or report.contract.contract_id != validation.observed_contract_id
                    or report.lineage != contract.lineage
                    or report.contract.dimensional_discovery_id != contract.dimensional_discovery_id):
                raise ValueError("Star Schema Contract incompatível com a validação.")
            connection.execute(
                "INSERT INTO validated_star_schema_contracts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (validation.validation_id, validation.report_id, contract.prepared_dataset_id,
                 contract.dimensional_discovery_id, contract.analysis_id, validation.version,
                 validation.model_dump_json(), validation.validated_at.isoformat()))
        return ValidatedStarSchemaRecord(
            validation_id=validation.validation_id, report_id=validation.report_id,
            prepared_dataset_id=contract.prepared_dataset_id,
            dimensional_discovery_id=contract.dimensional_discovery_id,
            analysis_id=contract.analysis_id, version=validation.version,
            created_at=validation.validated_at, validation=validation)

    def get_effective_star_schema_contract(self, prepared_dataset_id: str) -> StarSchemaContract | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT validation_json FROM validated_star_schema_contracts WHERE prepared_dataset_id = ? ORDER BY version DESC LIMIT 1",
                (prepared_dataset_id,)).fetchone()
        validation = ValidatedStarSchemaContract.model_validate_json(row["validation_json"]) if row else None
        return effective_star_schema_contract(validation)

    def next_ddl_version(self, star_schema_contract_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 version FROM physical_schema_plans WHERE star_schema_contract_id = ?",
                (star_schema_contract_id,)).fetchone()
        return int(row["version"])

    def save_physical_schema_plan(self, plan: PhysicalSchemaPlan) -> PhysicalSchemaPlanRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT validation_json FROM validated_star_schema_contracts WHERE prepared_dataset_id = ? ORDER BY version DESC LIMIT 1",
                (plan.prepared_dataset_id,)).fetchone()
            validation = ValidatedStarSchemaContract.model_validate_json(row["validation_json"]) if row else None
            effective = effective_star_schema_contract(validation)
            if (effective is None or effective.contract_id != plan.star_schema_contract_id
                    or effective.version != plan.star_schema_contract_version
                    or effective.analysis_id != plan.analysis_id
                    or effective.source_document_id != plan.source_document_id):
                raise ValueError("Physical Schema Plan não deriva do Effective Star Schema Contract atual.")
            connection.execute(
                "INSERT INTO physical_schema_plans VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (plan.physical_schema_plan_id, plan.star_schema_contract_id, plan.prepared_dataset_id,
                 plan.analysis_id, plan.version, plan.fingerprint, plan.model_dump_json(),
                 plan.created_at.isoformat()))
        return PhysicalSchemaPlanRecord(physical_schema_plan_id=plan.physical_schema_plan_id,
                                        star_schema_contract_id=plan.star_schema_contract_id,
                                        analysis_id=plan.analysis_id, version=plan.version,
                                        created_at=plan.created_at, plan=plan)

    def save_postgresql_ddl_artifact(self, artifact: PostgreSQLDDLArtifact) -> PostgreSQLDDLArtifactRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plan_json FROM physical_schema_plans WHERE physical_schema_plan_id = ?",
                (artifact.physical_schema_plan_id,)).fetchone()
            plan = PhysicalSchemaPlan.model_validate_json(row["plan_json"]) if row else None
            if (plan is None or plan.lineage != artifact.lineage
                    or hashlib.sha256(artifact.sql.encode("utf-8")).hexdigest() != artifact.fingerprint):
                raise ValueError("DDL Artifact incompatível com o Physical Schema Plan ou fingerprint.")
            connection.execute(
                "INSERT INTO postgresql_ddl_artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (artifact.ddl_artifact_id, artifact.physical_schema_plan_id,
                 artifact.lineage.prepared_dataset_id, artifact.lineage.analysis_id,
                 artifact.version, artifact.fingerprint, artifact.sql, artifact.model_dump_json(),
                 int(artifact.human_validated), artifact.generated_at.isoformat()))
        return PostgreSQLDDLArtifactRecord(ddl_artifact_id=artifact.ddl_artifact_id,
                                           physical_schema_plan_id=artifact.physical_schema_plan_id,
                                           analysis_id=artifact.lineage.analysis_id,
                                           version=artifact.version, generated_at=artifact.generated_at,
                                           artifact=artifact)

    def get_postgresql_ddl_artifact(self, ddl_artifact_id: str) -> PostgreSQLDDLArtifact | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT artifact_json FROM postgresql_ddl_artifacts WHERE ddl_artifact_id = ?",
                (ddl_artifact_id,)).fetchone()
        return PostgreSQLDDLArtifact.model_validate_json(row["artifact_json"]) if row else None

    def validate_postgresql_ddl_artifact(self, artifact: PostgreSQLDDLArtifact) -> PostgreSQLDDLArtifact:
        if not artifact.validation_passed:
            raise ValueError("DDL estruturalmente inválido não pode ser validado.")
        validated = artifact.model_copy(deep=True)
        validated.human_validated = True
        validated.ready_for_dimensional_etl = True
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE postgresql_ddl_artifacts SET artifact_json = ?, human_validated = 1 WHERE ddl_artifact_id = ?",
                (validated.model_dump_json(), validated.ddl_artifact_id))
            if result.rowcount != 1:
                raise ValueError("DDL Artifact não encontrado para validação.")
        return validated

    def get_effective_physical_schema(self, prepared_dataset_id: str) -> PhysicalSchemaPlan | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT p.plan_json FROM physical_schema_plans p
                   JOIN postgresql_ddl_artifacts a ON a.physical_schema_plan_id = p.physical_schema_plan_id
                   WHERE p.prepared_dataset_id = ? AND a.human_validated = 1
                   ORDER BY p.version DESC LIMIT 1""", (prepared_dataset_id,)).fetchone()
        if not row:
            return None
        plan = PhysicalSchemaPlan.model_validate_json(row["plan_json"])
        from core.ddl.models import PhysicalSchemaStatus
        plan.lifecycle_status = PhysicalSchemaStatus.EFFECTIVE
        return plan

    def next_etl_plan_version(self, physical_schema_plan_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 version FROM dimensional_etl_plans WHERE physical_schema_plan_id = ?",
                                     (physical_schema_plan_id,)).fetchone()
        return int(row["version"])

    def save_dimensional_etl_plan(self, plan: DimensionalETLPlan) -> DimensionalETLPlanRecord:
        with self._connect() as connection:
            physical_row = connection.execute("SELECT plan_json FROM physical_schema_plans WHERE physical_schema_plan_id = ?",
                                              (plan.physical_schema_plan_id,)).fetchone()
            artifact_row = connection.execute("SELECT artifact_json, human_validated FROM postgresql_ddl_artifacts WHERE ddl_artifact_id = ?",
                                              (plan.ddl_artifact_id,)).fetchone()
            physical = PhysicalSchemaPlan.model_validate_json(physical_row["plan_json"]) if physical_row else None
            artifact = PostgreSQLDDLArtifact.model_validate_json(artifact_row["artifact_json"]) if artifact_row else None
            if (physical is None or artifact is None or not artifact_row["human_validated"]
                    or physical.physical_schema_plan_id != artifact.physical_schema_plan_id
                    or plan.prepared_dataset_id != physical.prepared_dataset_id
                    or plan.star_schema_contract_id != physical.star_schema_contract_id):
                raise ValueError("ETL Plan não deriva do Effective Physical Schema validado.")
            connection.execute("INSERT INTO dimensional_etl_plans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (plan.etl_plan_id, plan.physical_schema_plan_id, plan.ddl_artifact_id,
                 plan.prepared_dataset_id, plan.analysis_id, plan.version, plan.fingerprint,
                 plan.model_dump_json(), plan.created_at.isoformat()))
        return DimensionalETLPlanRecord(etl_plan_id=plan.etl_plan_id,
            physical_schema_plan_id=plan.physical_schema_plan_id, prepared_dataset_id=plan.prepared_dataset_id,
            analysis_id=plan.analysis_id, version=plan.version, created_at=plan.created_at, plan=plan)

    def get_dimensional_etl_plan(self, etl_plan_id: str) -> DimensionalETLPlan | None:
        with self._connect() as connection:
            row = connection.execute("SELECT plan_json FROM dimensional_etl_plans WHERE etl_plan_id = ?",
                                     (etl_plan_id,)).fetchone()
        return DimensionalETLPlan.model_validate_json(row["plan_json"]) if row else None

    def next_etl_validation_version(self, prepared_dataset_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COALESCE(MAX(version), 0) + 1 version FROM validated_dimensional_etl_plans WHERE prepared_dataset_id = ?",
                                     (prepared_dataset_id,)).fetchone()
        return int(row["version"])

    def save_validated_dimensional_etl_plan(self, validation: ValidatedDimensionalETLPlan) -> ValidatedDimensionalETLPlanRecord:
        plan = validation.plan
        with self._connect() as connection:
            row = connection.execute("SELECT fingerprint FROM dimensional_etl_plans WHERE etl_plan_id = ?",
                                     (validation.etl_plan_id,)).fetchone()
            if row is None or row["fingerprint"] != plan.fingerprint:
                raise ValueError("Validated ETL Plan não corresponde ao plano persistido.")
            connection.execute("INSERT INTO validated_dimensional_etl_plans VALUES (?, ?, ?, ?, ?, ?, ?)",
                (validation.validation_id, validation.etl_plan_id, plan.prepared_dataset_id,
                 plan.analysis_id, validation.version, validation.model_dump_json(),
                 validation.validated_at.isoformat()))
        return ValidatedDimensionalETLPlanRecord(validation_id=validation.validation_id,
            etl_plan_id=validation.etl_plan_id, prepared_dataset_id=plan.prepared_dataset_id,
            analysis_id=plan.analysis_id, version=validation.version,
            created_at=validation.validated_at, validation=validation)

    def get_effective_dimensional_etl_plan(self, prepared_dataset_id: str) -> DimensionalETLPlan | None:
        with self._connect() as connection:
            row = connection.execute("SELECT validation_json FROM validated_dimensional_etl_plans WHERE prepared_dataset_id = ? ORDER BY version DESC LIMIT 1",
                                     (prepared_dataset_id,)).fetchone()
        validation = ValidatedDimensionalETLPlan.model_validate_json(row["validation_json"]) if row else None
        return effective_dimensional_etl_plan(validation)

    def save_dimensional_transformation_run(self, run: DimensionalTransformationRun) -> DimensionalTransformationRunRecord:
        metadata = run.model_copy(deep=True)
        for result in metadata.dimension_results:
            result.staged_rows = []; result.surrogate_key_map = []; result.rejected_rows = []
        for result in metadata.fact_results: result.staged_rows = []
        for result in metadata.bridge_results: result.staged_rows = []
        metadata.surrogate_key_maps = []; metadata.rejected_rows = []; metadata.quarantine_rows = []
        with self._connect() as connection:
            plan_row = connection.execute("SELECT plan_json FROM dimensional_etl_plans WHERE etl_plan_id = ?",
                                          (run.etl_plan_id,)).fetchone()
            if plan_row is None:
                raise ValueError("Transformation Run requer Effective ETL Plan persistido.")
            plan = DimensionalETLPlan.model_validate_json(plan_row["plan_json"])
            if plan.prepared_dataset_id != run.prepared_dataset_id or plan.version != run.etl_plan_version:
                raise ValueError("Transformation Run incompatível com ETL Plan.")
            connection.execute("INSERT INTO dimensional_transformation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run.run_id, run.etl_plan_id, run.prepared_dataset_id, run.lineage.analysis_id,
                 run.status.value, run.fingerprint, run.artifact_root, metadata.model_dump_json(),
                 run.created_at.isoformat()))
            for checkpoint in run.execution_steps:
                connection.execute("INSERT INTO transformation_checkpoints VALUES (?, ?, ?, ?, ?, ?)",
                    (run.run_id, checkpoint.step_id, checkpoint.status.value, checkpoint.fingerprint,
                     checkpoint.model_dump_json(), checkpoint.completed_at.isoformat() if checkpoint.completed_at else None))
        return DimensionalTransformationRunRecord(run_id=run.run_id, etl_plan_id=run.etl_plan_id,
            prepared_dataset_id=run.prepared_dataset_id, analysis_id=run.lineage.analysis_id,
            status=run.status.value, fingerprint=run.fingerprint, created_at=run.created_at, run=metadata)

    def get_dimensional_transformation_run(self, run_id: str) -> DimensionalTransformationRun | None:
        with self._connect() as connection:
            row = connection.execute("SELECT run_json FROM dimensional_transformation_runs WHERE run_id = ?",
                                     (run_id,)).fetchone()
        return DimensionalTransformationRun.model_validate_json(row["run_json"]) if row else None

    def save_database_dry_run(self, run: DatabaseDryRun) -> DatabaseDryRunRecord:
        # DatabaseDryRunConfig/credentials are not part of this contract by design.
        with self._connect() as connection:
            parent = connection.execute("SELECT run_id FROM dimensional_transformation_runs WHERE run_id = ?",
                                        (run.transformation_run_id,)).fetchone()
            if parent is None:
                raise ValueError("Database Dry Run requer Transformation Run persistido.")
            connection.execute("INSERT INTO database_dry_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run.dry_run_id, run.transformation_run_id, run.lineage.analysis_id, run.status.value,
                 run.test_schema, run.fingerprint, run.model_dump_json(), run.created_at.isoformat()))
        return DatabaseDryRunRecord(dry_run_id=run.dry_run_id,
            transformation_run_id=run.transformation_run_id, analysis_id=run.lineage.analysis_id,
            status=run.status.value, fingerprint=run.fingerprint, created_at=run.created_at, run=run)

    def get_database_dry_run(self, dry_run_id: str) -> DatabaseDryRun | None:
        with self._connect() as connection:
            row=connection.execute("SELECT run_json FROM database_dry_runs WHERE dry_run_id = ?",(dry_run_id,)).fetchone()
        return DatabaseDryRun.model_validate_json(row["run_json"]) if row else None
