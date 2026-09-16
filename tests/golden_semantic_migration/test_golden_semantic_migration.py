import sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
import pytest

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext,SemanticRole,SheetProfile,WorkbookProfile,WorkbookSummary
from core.semantic.knowledge_migration import migrate_historical_semantic_knowledge
from core.semantic.models import AnalysisStatus,QuestionStatus,SemanticValidationReport,ValidationStatus
from core.semantic.question_generator import OTHER_OPTION,ROLE_LABELS
from core.semantic.validation_service import create_validation_report


def _profile(names=("confirmed_field","corrected_field","custom_field","versioned_field")):
    fields=[profile_field(name.replace("_"," ").title(),name,["alfa","beta","gama"]) for name in names]
    fields.append(profile_field("Ano Histórico","ano_historico",[2024,2025,2026]))
    return WorkbookProfile(context=ProjectContext(),original_name="legacy.csv",source_type="browser_upload",size_bytes=1,file_type="csv",
        summary=WorkbookSummary(sheet_count=1,total_approximate_rows=3,total_columns=len(fields),warning_count=0),
        sheets=[SheetProfile(name="Dados",role_hypothesis="Base",approximate_row_count=3,column_count=len(fields),sampled_data_row_count=3,fields=fields)])


def _insert_legacy(connection,document_id,analysis_id,profile,created,roles,custom=False):
    report=create_validation_report(profile); report.analysis_id=analysis_id; report.source_document_id=document_id; report.analysis_status=AnalysisStatus.COMPLETED
    answers=[]
    for validation in report.validated_semantics:
        if validation.technical_name=="ano_historico": continue
        if validation.technical_name not in roles: continue
        role,status=roles[validation.technical_name]
        validation.validated_role=role; validation.validation_status=status; validation.validated_at=created
        question=next(q for q in report.questions if q.technical_name==validation.technical_name)
        if custom and validation.technical_name=="custom_field":
            validation.validated_role=None; validation.user_answer="Descrição livre sem papel"; answer=OTHER_OPTION; custom_answer="Descrição livre sem papel"
        else:
            validation.user_answer=ROLE_LABELS[role]; answer=ROLE_LABELS[role]; custom_answer=None
        question.status=QuestionStatus.ANSWERED; answers.append((question.question_id,answer,custom_answer))
    connection.execute("INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?)",(analysis_id,document_id,"completed",profile.model_dump_json(),report.model_dump_json(),created.isoformat(),created.isoformat(),created.isoformat()))
    for q in report.questions:
        connection.execute("INSERT INTO semantic_questions VALUES (?,?,?,?)",(analysis_id,q.question_id,q.status.value,q.model_dump_json()))
    for qid,answer,custom_answer in answers:
        connection.execute("INSERT INTO semantic_answers VALUES (?,?,?,?,?)",(analysis_id,qid,answer,custom_answer,created.isoformat()))


@pytest.fixture
def migrated(tmp_path:Path):
    path=tmp_path/"legacy.sqlite3"; repo=SQLiteAnalysisRepository(path); doc=repo.register_document(b"legacy-one","legacy.csv")
    other=repo.register_document(b"legacy-two","other.csv"); base=datetime(2025,1,1,tzinfo=timezone.utc); profile=_profile()
    with sqlite3.connect(path) as con:
        _insert_legacy(con,doc.source_document_id,"analysis-1",profile,base,{
            "confirmed_field":(SemanticRole.UNKNOWN,ValidationStatus.USER_CONFIRMED),
            "corrected_field":(SemanticRole.IDENTIFIER,ValidationStatus.USER_CORRECTED),
            "custom_field":(SemanticRole.UNKNOWN,ValidationStatus.USER_CORRECTED),
            "versioned_field":(SemanticRole.CODE,ValidationStatus.USER_CORRECTED)},custom=True)
        _insert_legacy(con,doc.source_document_id,"analysis-2",profile,base+timedelta(days=1),{
            "versioned_field":(SemanticRole.IDENTIFIER,ValidationStatus.USER_CORRECTED)})
        _insert_legacy(con,other.source_document_id,"other-analysis",profile,base,{
            "corrected_field":(SemanticRole.CODE,ValidationStatus.USER_CORRECTED)})
    before_answers=sqlite3.connect(path).execute("SELECT COUNT(*) FROM semantic_answers").fetchone()[0]
    first=migrate_historical_semantic_knowledge(path); second=migrate_historical_semantic_knowledge(path)
    return path,doc.source_document_id,other.source_document_id,before_answers,first,second


def _history(path,document):
    return SQLiteAnalysisRepository(path).list_semantic_knowledge(document,history=True)


def test_historical_user_confirmed_migration(migrated):
    path,doc,*_=migrated; assert any(x.normalized_field_name=="confirmed_field" and x.validation_source.value=="USER_CONFIRMED" for x in _history(path,doc))
def test_historical_user_corrected_migration(migrated):
    path,doc,*_=migrated; assert any(x.normalized_field_name=="corrected_field" and x.validated_semantic_role==SemanticRole.IDENTIFIER for x in _history(path,doc))
def test_custom_answer_preservation_without_invention(migrated):
    path,doc,_,_,report,_=migrated; assert report.records_unresolved==1 and not any(x.normalized_field_name=="custom_field" for x in _history(path,doc))
    assert any(x.migration_action=="UNRESOLVED_SEMANTIC_MAPPING" and x.historical_answer=="Descrição livre sem papel" for x in report.decisions)
def test_multiple_answer_versioning(migrated):
    path,doc,*_=migrated; versions=[x for x in _history(path,doc) if x.normalized_field_name=="versioned_field"]
    assert [x.version for x in versions]==[1,2]
def test_latest_applicable_knowledge(migrated):
    path,doc,*_=migrated; latest={x.normalized_field_name:x for x in SQLiteAnalysisRepository(path).list_semantic_knowledge(doc)}
    assert latest["versioned_field"].validated_semantic_role==SemanticRole.IDENTIFIER
def test_idempotency(migrated):
    *_,second=migrated; assert second.records_created==0 and second.idempotency_status=="PASS_ALREADY_APPLIED_NO_NEW_RECORDS"
def test_document_isolation(migrated):
    path,doc,other,*_=migrated; assert all(x.source_document_id==doc for x in _history(path,doc)) and all(x.source_document_id==other for x in _history(path,other))
def test_field_identity_preservation(migrated):
    path,doc,*_=migrated; item=next(x for x in _history(path,doc) if x.normalized_field_name=="corrected_field"); assert item.source_field_id=="Dados::corrected_field"
def test_reuse_after_migration(migrated):
    path,doc,*_=migrated; prior=SQLiteAnalysisRepository(path).list_semantic_knowledge(doc); report=create_validation_report(_profile(),prior_knowledge=prior)
    decision=next(x for x in report.reuse_report.decisions if x.normalized_field_name=="corrected_field"); assert decision.action.value=="REUSE"
def test_reconfirm_after_real_change(migrated):
    path,doc,*_=migrated; prior=SQLiteAnalysisRepository(path).list_semantic_knowledge(doc)
    changed=_profile(("versioned_field",)); changed.sheets[0].fields[0]=profile_field("Versioned Field","versioned_field",[object(),object(),object()])
    report=create_validation_report(changed,prior_knowledge=prior); decision=next(x for x in report.reuse_report.decisions if x.normalized_field_name=="versioned_field")
    assert decision.action.value=="RECONFIRM" and report.questions
def test_auto_accept_history_and_answers_immutable(migrated):
    path,doc,_,before,report,_=migrated; after=sqlite3.connect(path).execute("SELECT COUNT(*) FROM semantic_answers").fetchone()[0]
    assert before==after and any(x.normalized_field_name=="ano_historico" and x.validation_source.value=="AUTO_ACCEPTED" for x in _history(path,doc))
