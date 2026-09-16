import csv
import hashlib
from datetime import datetime, timezone

from core.bi_mvp.ddl import generate_postgresql_ddl
from core.bi_mvp.modeling import build_mvp_model
from core.grain.artifact_discovery import GRAIN_ENGINE_VERSION, discover_grain_from_artifact
from core.grain.models import (GrainClassification, GrainDiscoveryStatus,
                               GrainReadiness, GrainValidationStatus)
from core.grain.validation import record_unknown_grain, validate_grain
from core.prepared.artifact_reader import PreparedDatasetArtifactReader
from core.prepared.models import (PreparedDatasetArtifact, PreparedDatasetStatus,
    PreparedField, PreparedGenerationMetrics, PreparedGenerationStatus)
from core.profiling.models import SemanticRole


def _artifact(tmp_path, rows):
    path=tmp_path/"prepared.csv"
    names=["source_row_id","sheet_name","source_row_number","Sparse ID","Empty ID",
           "Ano","Mês","Dia","UG Sigla","Credor","Fonte","Grupo de Despesa",
           "Evento Pagamento","Nº Empenho","Nº Liquidação","Total Pago","Liquidado",
           "Empenhado","Devolvido","Estornado"]
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=names); writer.writeheader(); writer.writerows(rows)
    content=path.read_bytes(); now=datetime.now(timezone.utc)
    roles={"Sparse ID":SemanticRole.IDENTIFIER,"Empty ID":SemanticRole.IDENTIFIER,
           "Ano":SemanticRole.TIME_COMPONENT,"Mês":SemanticRole.TIME_COMPONENT,
           "Dia":SemanticRole.TIME_COMPONENT,"UG Sigla":SemanticRole.CODE,
           "Credor":SemanticRole.CODE,"Fonte":SemanticRole.CODE,
           "Grupo de Despesa":SemanticRole.CATEGORY,"Evento Pagamento":SemanticRole.CODE,
           "Nº Empenho":SemanticRole.CODE,"Nº Liquidação":SemanticRole.IDENTIFIER,
           "Total Pago":SemanticRole.MEASURE,"Liquidado":SemanticRole.MEASURE,
           "Empenhado":SemanticRole.MEASURE,"Devolvido":SemanticRole.MEASURE,
           "Estornado":SemanticRole.MEASURE}
    fields=[PreparedField(source_field_id=f"S::{n}",sheet_name="S",source_name=n,
             technical_name=n.casefold().replace(" ","_").replace("º","o"),
             effective_semantic_role=role,recommended_type="text",prepared_type="text")
            for n,role in roles.items()]
    metrics=PreparedGenerationMetrics(started_at=now,finished_at=now,rows=len(rows),
        columns=len(fields),rss_start_mb=1,rss_peak_mb=1,rss_end_mb=1,
        artifact_size_bytes=len(content),status=PreparedGenerationStatus.COMPLETED)
    artifact=PreparedDatasetArtifact(prepared_dataset_id="00000000-0000-0000-0000-000000000001",
        source_document_id="sha256:"+"1"*64,analysis_id="00000000-0000-0000-0000-000000000002",
        version=2,ruleset_version="test",row_count=len(rows),field_count=len(fields),
        status=PreparedDatasetStatus.READY,generation_status=PreparedGenerationStatus.COMPLETED,
        schema=fields,fingerprint="f"*64,artifact_location=str(path),artifact_size_bytes=len(content),
        artifact_sha256=hashlib.sha256(content).hexdigest(),metrics=metrics)
    return artifact, PreparedDatasetArtifactReader(artifact,analysis_id=artifact.analysis_id,
        prepared_dataset_id=artifact.prepared_dataset_id,source_document_id=artifact.source_document_id,
        version=artifact.version,fingerprint=artifact.fingerprint)


def _rows(count=1000):
    return [{"source_row_id":f"sr:{i}","sheet_name":"S","source_row_number":i+2,
             "Sparse ID":f"x{i}" if i<3 else "","Empty ID":"", "Ano":"2026","Mês":"ago",
             "Dia":"1","UG Sigla":"UG1","Credor":f"{i%7:014d}","Fonte":"F1",
             "Grupo de Despesa":"CORRENTE","Evento Pagamento":"P" if i%2 else "",
             "Nº Empenho":str(i%10),"Nº Liquidação":str(i%100),"Total Pago":"1.25",
             "Liquidado":"2.00","Empenhado":"3.00","Devolvido":"0","Estornado":"0"}
            for i in range(count)]


def test_sparse_unique_and_zero_support_are_not_global_recommendations(tmp_path):
    artifact,reader=_artifact(tmp_path,_rows())
    report=discover_grain_from_artifact(reader)
    sparse=next(x for x in report.grain_candidates if x.candidate_fields==["S::Sparse ID"])
    empty=next(x for x in report.grain_candidates if x.candidate_fields==["S::Empty ID"])
    assert sparse.uniqueness_ratio==1 and sparse.coverage_ratio==.003
    assert sparse.business_process_compatibility=="EVENT_SUBSET_ONLY"
    assert empty.complete_row_count==0 and empty.confidence==0
    assert report.recommended_candidate_id != sparse.candidate_id
    assert report.engine_version==GRAIN_ENGINE_VERSION=="artifact-grain-v2.2"


def test_source_record_validation_model_and_ddl_preserve_lineage_and_measures(tmp_path):
    artifact,reader=_artifact(tmp_path,_rows(20))
    report=discover_grain_from_artifact(reader)
    grain=validate_grain(report,source_record_grain=True)
    model=build_mvp_model(artifact,grain,approved=True)
    ddl=generate_postgresql_ddl(model)
    assert grain.grain_fields==["source_row_id"]
    assert {m.source_field for m in model.measures}=={
        "Total Pago","Liquidado","Empenhado","Devolvido","Estornado"}
    assert "Nº Empenho" in model.preserved_identifiers
    assert "UNIQUE (analysis_id, prepared_version, source_row_id)" in ddl
    assert "NUMERIC" in ddl and "BIGSERIAL PRIMARY KEY" in ddl


def test_unknown_human_decision_does_not_unlock_modeling(tmp_path):
    artifact,reader=_artifact(tmp_path,_rows(20)); report=discover_grain_from_artifact(reader)
    decision=record_unknown_grain(report)
    assert decision.status==GrainReadiness.NOT_READY
    assert decision.validation_status==GrainValidationStatus.UNKNOWN
    try:
        build_mvp_model(artifact,decision)
    except ValueError as error:
        assert "Human-validated grain" in str(error)
    else:
        raise AssertionError("unknown decision must block modeling")


def test_unapproved_model_and_unconfirmed_sums_remain_blocked(tmp_path):
    import pytest
    from core.bi_mvp.metabase import generate_metabase_sql
    artifact, reader = _artifact(tmp_path, _rows(10))
    grain = validate_grain(discover_grain_from_artifact(reader), source_record_grain=True)
    proposal = build_mvp_model(artifact, grain)
    with pytest.raises(ValueError, match='approved'):
        generate_postgresql_ddl(proposal)
    assert 'SUM(' not in generate_metabase_sql(proposal)
    approved = build_mvp_model(artifact, grain, approved=True, additive_measures=['Total Pago'])
    sql = generate_metabase_sql(approved)
    assert 'SUM("total_pago")' in sql and 'SUM("liquidado")' not in sql
    assert 'prepared_version' in sql and 'vw_despesa_mensal' in sql
    with pytest.raises(ValueError, match='ownership'):
        build_mvp_model(artifact, grain.model_copy(update={'source_document_id':'wrong'}))


def test_model_integrity_and_deterministic_cold_rebuild(tmp_path):
    import pytest
    from core.bi_mvp.artifacts import persist_model, load_model
    artifact, reader = _artifact(tmp_path, _rows(10))
    grain = validate_grain(discover_grain_from_artifact(reader), source_record_grain=True)
    model = build_mvp_model(artifact, grain)
    path = persist_model(model, tmp_path/'models')
    assert persist_model(build_mvp_model(artifact, grain), tmp_path/'models') == path
    assert load_model(path) == model
    path.write_text(path.read_text().replace('PROPOSED', 'APPROVED'))
    with pytest.raises(ValueError, match='integrity'):
        load_model(path)


def test_all_null_dimension_is_omitted_and_unit_attributes_are_keyed(tmp_path):
    from core.bi_mvp.audit import inspect_prepared
    rows = _rows(11)
    for row in rows: row['Evento Pagamento'] = ''
    artifact, reader = _artifact(tmp_path, rows)
    audit = inspect_prepared(reader, chunk_size=3)
    grain = validate_grain(discover_grain_from_artifact(reader), source_record_grain=True)
    model = build_mvp_model(artifact, grain, nonnull_counts=audit['nonnull_counts'])
    assert all(d.name != 'evento_pagamento' for d in model.dimensions)
    assert all(d.business_key_fields == d.source_fields for d in model.dimensions)
    assert audit['rows'] == 11 and audit['chunks'] == 4
    assert len(audit['examples']) == 5


def test_artifact_integrity_ownership_and_bounded_reads(tmp_path):
    import pytest
    artifact, reader = _artifact(tmp_path, _rows(23))
    assert [len(c) for c in reader.iter_chunks(chunk_size=7)] == [7,7,7,2]
    with pytest.raises(ValueError, match='ownership'):
        PreparedDatasetArtifactReader(artifact, analysis_id='other',
            prepared_dataset_id=artifact.prepared_dataset_id,
            source_document_id=artifact.source_document_id,version=2,fingerprint=artifact.fingerprint)
    reader.path.write_text(reader.path.read_text() + '\n')
    with pytest.raises(ValueError):
        PreparedDatasetArtifactReader(artifact, analysis_id=artifact.analysis_id,
            prepared_dataset_id=artifact.prepared_dataset_id,
            source_document_id=artifact.source_document_id,version=2,fingerprint=artifact.fingerprint)


def test_grain_without_identifiers_and_historical_fields(tmp_path):
    artifact, _ = _artifact(tmp_path, _rows(10))
    for field in artifact.schema_fields:
        field.effective_semantic_role = SemanticRole.UNKNOWN
    reader = PreparedDatasetArtifactReader(artifact, analysis_id=artifact.analysis_id,
        prepared_dataset_id=artifact.prepared_dataset_id,source_document_id=artifact.source_document_id,
        version=2,fingerprint=artifact.fingerprint)
    report = discover_grain_from_artifact(reader)
    assert not report.grain_candidates and report.confidence == 0
    from core.grain.models import GrainCandidate
    legacy = dict(candidate_id='legacy', human_readable_description='legacy',
        candidate_fields=['Estorno'], row_count=181476,distinct_count=610,duplicate_count=0,
        uniqueness_ratio=1,null_ratio=.9966,stability=1,confidence=.8593)
    candidate=GrainCandidate(**legacy)
    assert candidate.coverage_ratio is None and candidate.confidence == .8593


def test_cold_resolver_never_falls_back_to_older_prepared(tmp_path):
    import pytest
    from types import SimpleNamespace
    from core.bi_mvp.artifacts import resolve_prepared
    artifact, _ = _artifact(tmp_path, _rows(10))
    class Repository:
        def list_prepared_datasets(self, analysis_id):
            return [SimpleNamespace(prepared_dataset_id='broken',version=3),
                    SimpleNamespace(prepared_dataset_id=artifact.prepared_dataset_id,version=2)]
        def get_prepared_artifact(self, prepared_id):
            return artifact if prepared_id == artifact.prepared_dataset_id else None
        def get_analysis(self, analysis_id):
            return SimpleNamespace(source_document_id=artifact.source_document_id)
    with pytest.raises(ValueError, match='ownership'):
        resolve_prepared(artifact.analysis_id,Repository())
    cold = resolve_prepared(artifact.analysis_id,Repository(),
        prepared_dataset_id=artifact.prepared_dataset_id,version=2)
    assert sum(len(chunk) for chunk in cold.iter_chunks(chunk_size=3)) == 10
    with pytest.raises(ValueError, match='version'):
        resolve_prepared(artifact.analysis_id,Repository(),
            prepared_dataset_id=artifact.prepared_dataset_id,version=1)


def _persisted_mvp(tmp_path):
    from core.persistence.sqlite_repository import SQLiteAnalysisRepository
    from tests.test_grain_persistence import _persisted_prepared
    repo = SQLiteAnalysisRepository(tmp_path / 'mvp.sqlite3')
    original = _persisted_prepared(repo)
    artifact, _ = _artifact(tmp_path, _rows(23))
    artifact = artifact.model_copy(update={'analysis_id':original.analysis_id,
        'source_document_id':original.source_document_id})
    repo.save_prepared_artifact(artifact)
    from core.bi_mvp.artifacts import resolve_prepared
    reader = resolve_prepared(artifact.analysis_id,repo)
    report = discover_grain_from_artifact(reader)
    repo.save_grain_discovery_report(report)
    return repo,reader,report


def test_cold_workflow_versions_and_unknown_revocation(tmp_path, monkeypatch):
    import pytest
    from core.bi_mvp.workflow import prepare_model
    from core.bi_mvp.artifacts import resolve_prepared
    from core.persistence.sqlite_repository import SQLiteAnalysisRepository
    repo,reader,report = _persisted_mvp(tmp_path)
    repo.save_grain_definition(validate_grain(report,source_record_grain=True))
    def forbidden(*args,**kwargs): raise AssertionError('XLSX must not be read')
    monkeypatch.setattr('core.ingestion.file_loader.load_workspace_file', forbidden)
    model,path = prepare_model(reader,repo,root=tmp_path/'models')
    cold_repo = SQLiteAnalysisRepository(tmp_path/'mvp.sqlite3')
    cold_reader = resolve_prepared(reader.artifact.analysis_id,cold_repo)
    second,second_path = prepare_model(cold_reader,cold_repo,root=tmp_path/'models')
    assert (model,path)==(second,second_path)
    approved,_ = prepare_model(cold_reader,cold_repo,root=tmp_path/'models',approve=True)
    assert approved.version==2 and model.status.value=='PROPOSED'
    cold_repo.save_grain_definition(record_unknown_grain(report,version=2))
    with pytest.raises(ValueError,match='PENDING_HUMAN'):
        prepare_model(cold_reader,cold_repo,root=tmp_path/'models')


def test_mvp_streamlit_cold_grain_examples_and_unknown(tmp_path):
    from streamlit.testing.v1 import AppTest
    repo,reader,report = _persisted_mvp(tmp_path)
    script = ('from core.persistence.sqlite_repository import SQLiteAnalysisRepository\n'
              'from app.components.bi_mvp_view import render_bi_mvp\n'
              f'render_bi_mvp(SQLiteAnalysisRepository({str(tmp_path / "mvp.sqlite3")!r}))')
    app=AppTest.from_string(script, default_timeout=15).run()
    app.text_input[0].set_value(reader.artifact.analysis_id).run()
    assert not app.exception
    assert len(app.dataframe[0].value)==5
    next(b for b in app.button if b.label=='Não sei / preciso investigar').click().run()
    assert not app.exception
    assert not any('READY_FOR_DIMENSIONAL_MODELING' in x.value for x in app.success)
    assert repo.get_effective_grain(reader.artifact.prepared_dataset_id) is None
