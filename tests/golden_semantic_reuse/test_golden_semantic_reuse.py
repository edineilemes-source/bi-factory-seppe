from datetime import datetime,timezone
from pathlib import Path

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext,SemanticRole,SheetProfile,WorkbookProfile,WorkbookSummary
from core.semantic.decision_engine import decide_field
from core.semantic.knowledge import SemanticKnowledgeReusePolicy,semantic_fingerprint
from core.semantic.models import (KnowledgeValidationSource,SemanticKnowledgeRecord,
    SemanticReuseAction,ValidationStatus)
from core.semantic.question_generator import ROLE_LABELS
from core.semantic.validation_service import create_validation_report


def profile(fields):
    return WorkbookProfile(context=ProjectContext(),original_name="expense.csv",source_type="browser_upload",size_bytes=1,file_type="csv",
        summary=WorkbookSummary(sheet_count=1,total_approximate_rows=10,total_columns=len(fields),warning_count=0),
        sheets=[SheetProfile(name="Dados",role_hypothesis="Base",approximate_row_count=10,column_count=len(fields),sampled_data_row_count=10,fields=fields)])


def knowledge(field,role,source=KnowledgeValidationSource.USER_CONFIRMED,version=1):
    return SemanticKnowledgeRecord(semantic_knowledge_id=f"k:{field.technical_name}",source_document_id="doc",
        source_field_id=f"Dados::{field.technical_name}",normalized_field_name=field.technical_name,
        business_concept_id=f"concept:{field.technical_name}",validated_semantic_role=role,
        validation_source=source,confidence=.95,first_validated_analysis_id="a1",last_confirmed_analysis_id="a1",
        compatibility_fingerprint=semantic_fingerprint(field),evidence_snapshot=field.semantic_evidence,version=version)


def test_a_reuse_time_component_suppresses_question():
    field=profile_field("Ano do Empenho","ano_do_empenho",[2026]*10)
    report=create_validation_report(profile([field]),prior_knowledge=[knowledge(field,SemanticRole.TIME_COMPONENT)])
    assert field.semantic_role_candidate==SemanticRole.TIME_COMPONENT
    assert report.reuse_report.reused_count==1 and not report.questions


def test_b_strong_date_auto_accepts_without_question():
    field=profile_field("Data Lançamento Empenho","data_lancamento_empenho",["14/01/2026","15/01/2026","16/01/2026"])
    report=create_validation_report(profile([field]))
    assert field.semantic_role_candidate==SemanticRole.DATE and field.semantic_role_confidence==.95
    assert report.reuse_report.auto_accepted_count==1 and not report.questions


def test_c_lexical_identifier_hint_cannot_override_date_content():
    field=profile_field("Data Lançamento Empenho","data_lancamento_empenho",["14/01/2026"]*3)
    assert "competing_name_roles" not in {x.code for x in decide_field(field).conflicts}


def test_d_user_confirmed_reused():
    field=profile_field("Credor","credor",["C1","C2","C3"])
    prior=knowledge(field,SemanticRole.IDENTIFIER,KnowledgeValidationSource.USER_CONFIRMED)
    decision,_=SemanticKnowledgeReusePolicy().decide(field,"Dados::credor",[prior])
    assert decision.action==SemanticReuseAction.REUSE


def test_e_user_correction_has_precedence_over_observed_code():
    field=profile_field("Código Credor","codigo_credor",["A1","A2","A1","A2"])
    prior=knowledge(field,SemanticRole.IDENTIFIER,KnowledgeValidationSource.USER_CORRECTED)
    report=create_validation_report(profile([field]),prior_knowledge=[prior])
    assert report.validated_semantics[0].validated_role==SemanticRole.IDENTIFIER
    assert report.validated_semantics[0].knowledge_reused


def test_f_real_change_requires_reconfirmation():
    old=profile_field("Data Evento","data_evento",["14/01/2026"]*3)
    current=profile_field("Data Evento","data_evento",["texto livre incompatível"]*3)
    report=create_validation_report(profile([current]),prior_knowledge=[knowledge(old,SemanticRole.DATE)])
    assert report.reuse_report.reconfirm_count==1 and len(report.questions)==1
    assert report.questions[0].previous_validated_role==SemanticRole.DATE


def test_g_deferred_has_no_question():
    field=profile_field("Sem Evidência","sem_evidencia",[None,"-",None])
    report=create_validation_report(profile([field])); assert report.reuse_report.deferred_count==1 and not report.questions


def test_h_new_unknown_asks():
    field=profile_field("Campo Novo","campo_novo",["alfa","beta","gama"])
    report=create_validation_report(profile([field])); assert report.reuse_report.ask_count==1 and len(report.questions)==1


def test_i_same_document_new_analysis_reuses_and_reduces_questions(tmp_path:Path):
    repository=SQLiteAnalysisRepository(tmp_path/"reuse.sqlite3"); document=repository.register_document(b"stable","expense.csv")
    field=profile_field("Campo Novo","campo_novo",["alfa","beta","gama"]); current=profile([field])
    first=repository.create_analysis(document.source_document_id,current); assert len(first.report.questions)==1
    repository.save_answer(first.analysis_id,first.report.questions[0].question_id,ROLE_LABELS[SemanticRole.IDENTIFIER])
    second=repository.create_analysis(document.source_document_id,current)
    assert first.analysis_id!=second.analysis_id and not second.report.questions
    assert second.report.reuse_report.reused_count==1


def test_j_knowledge_versioning_preserves_history(tmp_path:Path):
    repository=SQLiteAnalysisRepository(tmp_path/"versions.sqlite3"); document=repository.register_document(b"versions","expense.csv")
    field=profile_field("Campo Novo","campo_novo",["alfa","beta","gama"]); first=repository.create_analysis(document.source_document_id,profile([field]))
    repository.save_answer(first.analysis_id,first.report.questions[0].question_id,ROLE_LABELS[SemanticRole.CODE])
    latest=repository.list_semantic_knowledge(document.source_document_id)[0]
    second_report=create_validation_report(profile([field]),prior_knowledge=[latest]); second_report.analysis_id="a2"; second_report.source_document_id=document.source_document_id
    validation=second_report.validated_semantics[0]; validation.validation_status=ValidationStatus.USER_CORRECTED; validation.validated_role=SemanticRole.IDENTIFIER
    repository.save_report(second_report)
    history=repository.list_semantic_knowledge(document.source_document_id,history=True)
    assert [x.version for x in history]==[1,2] and history[-1].validated_semantic_role==SemanticRole.IDENTIFIER


def test_realistic_expense_fields_have_only_new_real_doubts():
    fields=[profile_field("Ano do Empenho","ano_do_empenho",[2026]*5),
        profile_field("Data Lançamento Empenho","data_lancamento_empenho",["14/01/2026"]*5),
        profile_field("Nº Empenho","n_empenho",["001","002","003","004","005"]),
        profile_field("Credor","credor",["C1","C2","C3","C4","C5"]),
        profile_field("Total Pago","total_pago",[10.2,20.3,-1.5,0,4.2])]
    prior=[knowledge(fields[2],SemanticRole.IDENTIFIER),knowledge(fields[3],SemanticRole.IDENTIFIER)]
    report=create_validation_report(profile(fields),prior_knowledge=prior)
    asked={q.technical_name for q in report.questions}
    assert "ano_do_empenho" not in asked and "data_lancamento_empenho" not in asked
    assert report.reuse_report.reused_count==2
