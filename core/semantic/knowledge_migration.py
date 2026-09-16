"""Versioned backfill of pre-knowledge-layer semantic validation history."""
import hashlib
import json
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

from core.profiling.models import WorkbookProfile
from core.semantic.knowledge import semantic_fingerprint
from core.semantic.models import (KnowledgeValidationSource,KnowledgeValidationStatus,
    SemanticKnowledgeMigration,SemanticKnowledgeMigrationDecision,
    SemanticKnowledgeMigrationStatus,SemanticKnowledgeRecord,SemanticValidationReport,
    ValidationStatus)

MIGRATION_ID="historical-semantic-knowledge-backfill"
MIGRATION_VERSION=1


def _canonical(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str)
def _fingerprint(value): return hashlib.sha256(_canonical(value).encode()).hexdigest()


def ensure_migration_schema(connection:sqlite3.Connection)->None:
    connection.execute("""CREATE TABLE IF NOT EXISTS semantic_knowledge_migrations (
        migration_id TEXT NOT NULL, migration_version INTEGER NOT NULL, status TEXT NOT NULL,
        report_json TEXT NOT NULL, started_at TEXT NOT NULL, completed_at TEXT NOT NULL,
        fingerprint TEXT NOT NULL, PRIMARY KEY(migration_id,migration_version))""")


def _already_applied(row)->SemanticKnowledgeMigration:
    prior=SemanticKnowledgeMigration.model_validate_json(row["report_json"])
    now=datetime.now(timezone.utc)
    return SemanticKnowledgeMigration(migration_id=MIGRATION_ID,migration_version=MIGRATION_VERSION,
        started_at=now,completed_at=now,status=SemanticKnowledgeMigrationStatus.ALREADY_APPLIED,
        records_scanned=prior.records_scanned,records_eligible=prior.records_eligible,records_created=0,
        records_updated_versioned=0,records_skipped=prior.records_scanned,
        records_unresolved=prior.records_unresolved,conflicts=prior.conflicts,decisions=[],
        idempotency_status="PASS_ALREADY_APPLIED_NO_NEW_RECORDS",
        fingerprint=_fingerprint({"migration":MIGRATION_ID,"version":MIGRATION_VERSION,"already_applied":True}))


def migrate_historical_semantic_knowledge(database_path:Path|str)->SemanticKnowledgeMigration:
    """Backfill once without changing answers, reports, profiles, or source values."""
    started=datetime.now(timezone.utc); connection=sqlite3.connect(database_path)
    connection.row_factory=sqlite3.Row; ensure_migration_schema(connection)
    applied=connection.execute("SELECT report_json FROM semantic_knowledge_migrations WHERE migration_id=? AND migration_version=?",
                               (MIGRATION_ID,MIGRATION_VERSION)).fetchone()
    if applied: connection.close(); return _already_applied(applied)
    decisions=[]; scanned=eligible=created=updated=skipped=unresolved=conflicts=0
    try:
        connection.execute("BEGIN IMMEDIATE")
        analyses=connection.execute("SELECT analysis_id,source_document_id,report_json,created_at,updated_at FROM analyses ORDER BY created_at,analysis_id").fetchall()
        existing_snapshots={}
        for row in connection.execute("SELECT knowledge_json FROM semantic_knowledge ORDER BY semantic_knowledge_id,version"):
            record=SemanticKnowledgeRecord.model_validate_json(row["knowledge_json"])
            existing_snapshots[record.semantic_knowledge_id]=record
        events=[]
        for analysis in analyses:
            report=SemanticValidationReport.model_validate_json(analysis["report_json"])
            fields={f"{sheet.name}::{field.technical_name}":field for sheet in report.observed_profile.sheets for field in sheet.fields}
            answers={row["question_id"]:row for row in connection.execute(
                "SELECT question_id,answer,custom_answer,answered_at FROM semantic_answers WHERE analysis_id=?",(analysis["analysis_id"],))}
            questions={q.question_id:q for q in report.questions}
            for validation in report.validated_semantics:
                answer_row=next((a for qid,a in answers.items() if qid in questions and
                    questions[qid].technical_name==validation.technical_name and questions[qid].sheet_name==validation.sheet_name),None)
                human=answer_row is not None; auto=validation.validation_status==ValidationStatus.AUTO_ACCEPTED
                if not human and not auto: continue
                scanned+=1
                question=next((q for q in questions.values() if q.technical_name==validation.technical_name and q.sheet_name==validation.sheet_name),None)
                answer=(answer_row["custom_answer"] or answer_row["answer"]) if answer_row else None
                if validation.validated_role is None:
                    unresolved+=1
                    decisions.append(SemanticKnowledgeMigrationDecision(field=validation.technical_name,
                        source_analysis_id=analysis["analysis_id"],question_id=question.question_id if question else None,
                        historical_answer=answer,migration_action="UNRESOLVED_SEMANTIC_MAPPING",
                        reason="Historical answer has no structured SemanticRole; no role was invented.")); continue
                eligible+=1
                source={ValidationStatus.USER_CORRECTED:KnowledgeValidationSource.USER_CORRECTED,
                    ValidationStatus.USER_CONFIRMED:KnowledgeValidationSource.USER_CONFIRMED,
                    ValidationStatus.AUTO_ACCEPTED:KnowledgeValidationSource.AUTO_ACCEPTED}[validation.validation_status]
                field=fields[validation.source_field_id]
                knowledge_id=f"knowledge:{analysis['source_document_id']}:{validation.source_field_id}"
                # A validation already represented by the current knowledge layer is not historical backfill input.
                represented=connection.execute("SELECT 1 FROM semantic_knowledge WHERE semantic_knowledge_id=? AND (json_extract(knowledge_json,'$.first_validated_analysis_id')=? OR json_extract(knowledge_json,'$.last_confirmed_analysis_id')=?)",
                    (knowledge_id,analysis["analysis_id"],analysis["analysis_id"])).fetchone()
                if represented:
                    skipped+=1
                    decisions.append(SemanticKnowledgeMigrationDecision(field=validation.technical_name,
                        source_analysis_id=analysis["analysis_id"],question_id=question.question_id if question else None,
                        historical_answer=answer,mapped_role=validation.validated_role,migration_action="SKIPPED_ALREADY_REPRESENTED",
                        reason="Analysis provenance already exists in semantic knowledge.")); continue
                event_at=answer_row["answered_at"] if answer_row else (validation.validated_at.isoformat() if validation.validated_at else analysis["updated_at"])
                events.append((analysis,validation,field,question,answer,event_at,source,knowledge_id))
        touched=set()
        for analysis,validation,field,question,answer,event_at,source,knowledge_id in events:
            latest=connection.execute("SELECT knowledge_json FROM semantic_knowledge WHERE semantic_knowledge_id=? ORDER BY version DESC LIMIT 1",(knowledge_id,)).fetchone()
            prior=SemanticKnowledgeRecord.model_validate_json(latest["knowledge_json"]) if latest else None
            version=prior.version+1 if prior else 1
            created_at=datetime.fromisoformat(event_at) if event_at else started
            first_analysis=(analysis["analysis_id"] if prior is None or created_at < prior.created_at
                            else prior.first_validated_analysis_id)
            first_created=created_at if prior is None or created_at < prior.created_at else prior.created_at
            record=SemanticKnowledgeRecord(semantic_knowledge_id=knowledge_id,source_document_id=analysis["source_document_id"],
                source_field_id=validation.source_field_id,normalized_field_name=validation.technical_name,
                business_concept_id=validation.business_concept_id or f"concept:{validation.technical_name}",
                validated_semantic_role=validation.validated_role,validation_source=source,
                confidence=validation.original_confidence,validation_status=KnowledgeValidationStatus.VALIDATED,
                first_validated_analysis_id=first_analysis,last_confirmed_analysis_id=analysis["analysis_id"],
                created_at=first_created,updated_at=created_at,
                evidence_snapshot=field.semantic_evidence,compatibility_fingerprint=semantic_fingerprint(field),version=version,
                origin_question_id=question.question_id if question else None,historical_answer=answer,
                migrated_by=f"{MIGRATION_ID}:v{MIGRATION_VERSION}")
            connection.execute("INSERT INTO semantic_knowledge VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (record.semantic_knowledge_id,record.source_document_id,record.source_field_id,record.normalized_field_name,
                 record.business_concept_id,record.validated_semantic_role.value,record.validation_source.value,
                 record.validation_status.value,record.version,record.model_dump_json(),record.created_at.isoformat(),record.updated_at.isoformat()))
            created+=1; updated+=int(prior is not None); touched.add(knowledge_id)
            decisions.append(SemanticKnowledgeMigrationDecision(field=validation.technical_name,
                source_analysis_id=analysis["analysis_id"],question_id=question.question_id if question else None,
                historical_answer=answer,mapped_role=validation.validated_role,migration_action="KNOWLEDGE_VERSION_CREATED",
                knowledge_version=version,reason="Structured historical validation migrated with original provenance."))
        # Existing post-layer knowledge remains effective after older history is appended.
        for knowledge_id in touched:
            snapshot=existing_snapshots.get(knowledge_id)
            if not snapshot: continue
            latest_version=connection.execute("SELECT MAX(version) FROM semantic_knowledge WHERE semantic_knowledge_id=?",(knowledge_id,)).fetchone()[0]
            latest_row=connection.execute("SELECT knowledge_json FROM semantic_knowledge WHERE semantic_knowledge_id=? ORDER BY version DESC LIMIT 1",(knowledge_id,)).fetchone()
            migrated_latest=SemanticKnowledgeRecord.model_validate_json(latest_row["knowledge_json"])
            restored=snapshot.model_copy(deep=True); restored.version=latest_version+1
            restored.first_validated_analysis_id=migrated_latest.first_validated_analysis_id
            restored.created_at=migrated_latest.created_at
            restored.migrated_by=f"{MIGRATION_ID}:v{MIGRATION_VERSION}:effective-snapshot"
            connection.execute("INSERT INTO semantic_knowledge VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (restored.semantic_knowledge_id,restored.source_document_id,restored.source_field_id,restored.normalized_field_name,
                 restored.business_concept_id,restored.validated_semantic_role.value,restored.validation_source.value,
                 restored.validation_status.value,restored.version,restored.model_dump_json(),restored.created_at.isoformat(),restored.updated_at.isoformat()))
            created+=1; updated+=1
        completed=datetime.now(timezone.utc); payload={"scanned":scanned,"eligible":eligible,"created":created,
            "updated":updated,"skipped":skipped,"unresolved":unresolved,"decisions":[x.model_dump(mode="json") for x in decisions]}
        report=SemanticKnowledgeMigration(migration_id=MIGRATION_ID,migration_version=MIGRATION_VERSION,
            started_at=started,completed_at=completed,status=SemanticKnowledgeMigrationStatus.COMPLETED,
            records_scanned=scanned,records_eligible=eligible,records_created=created,
            records_updated_versioned=updated,records_skipped=skipped,records_unresolved=unresolved,
            conflicts=conflicts,decisions=decisions,idempotency_status="PASS_VERSION_RECORDED",fingerprint=_fingerprint(payload))
        connection.execute("INSERT INTO semantic_knowledge_migrations VALUES (?,?,?,?,?,?,?)",
            (MIGRATION_ID,MIGRATION_VERSION,report.status.value,report.model_dump_json(),started.isoformat(),completed.isoformat(),report.fingerprint))
        connection.commit(); return report
    except Exception:
        connection.rollback(); raise
    finally: connection.close()


def render_semantic_knowledge_migration_report(report:SemanticKnowledgeMigration)->str:
    lines=["SEMANTIC KNOWLEDGE MIGRATION REPORT",f"MIGRATION VERSION: {report.migration_version}",
        f"HISTORICAL ANSWERS SCANNED: {report.records_scanned}",f"ELIGIBLE: {report.records_eligible}",
        f"KNOWLEDGE CREATED: {report.records_created}",f"VERSIONS CREATED: {report.records_updated_versioned}",
        f"SKIPPED: {report.records_skipped}",f"UNRESOLVED: {report.records_unresolved}",
        f"CONFLICTS: {report.conflicts}",f"IDEMPOTENCY STATUS: {report.idempotency_status}",""]
    for item in report.decisions:
        lines.extend([f"FIELD: {item.field}",f"SOURCE ANALYSIS: {item.source_analysis_id}",
            f"HISTORICAL ANSWER: {item.historical_answer or '-'}",f"MAPPED ROLE: {item.mapped_role.value if item.mapped_role else '-'}",
            f"MIGRATION ACTION: {item.migration_action}",f"KNOWLEDGE VERSION: {item.knowledge_version or '-'}",
            f"REASON: {item.reason}",""])
    return "\n".join(lines)
