import os
from pathlib import Path

import pytest

from core.bi_mvp.etl import load_postgresql
from core.bi_mvp.modeling import build_mvp_model
from core.grain.artifact_discovery import discover_grain_from_artifact
from core.grain.validation import validate_grain
from tests.test_sprint_4_4_8 import _artifact, _rows


@pytest.mark.postgres_integration
def test_postgresql_chunked_replay_is_idempotent_and_reconciled(tmp_path):
    dsn=os.environ.get("TEST_POSTGRES_DSN")
    if not dsn: pytest.skip("TEST_POSTGRES_DSN not configured")
    artifact,reader=_artifact(tmp_path,_rows(23))
    grain=validate_grain(discover_grain_from_artifact(reader),source_record_grain=True)
    model=build_mvp_model(artifact,grain,approved=True); schema="bi_s448_pytest"
    import psycopg
    with psycopg.connect(dsn) as connection:
        connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE"); connection.commit()
    first=load_postgresql(reader,model,dsn,schema=schema,chunk_size=7,apply_ddl=True)
    replay=load_postgresql(reader,model,dsn,schema=schema,chunk_size=5,apply_ddl=True)
    assert first.rows_read==first.rows_loaded==first.database_row_count==23
    assert first.chunk_count==4 and first.reconciliation_status=="PASS"
    assert replay.rows_loaded==0 and replay.rows_already_loaded==23
    assert replay.database_row_count==23 and replay.reconciliation_status=="PASS"
    assert first.source_totals=={"total_pago":"28.75","liquidado":"46.00",
        "empenhado":"69.00","devolvido":"0","estornado":"0"}


@pytest.mark.postgres_integration
def test_exact_source_duplicates_identifiers_and_failure_rollback(tmp_path):
    dsn=os.environ.get('TEST_POSTGRES_DSN')
    if not dsn: pytest.skip('TEST_POSTGRES_DSN not configured')
    import psycopg
    from uuid import uuid4
    from decimal import Decimal
    schema = 'bi_s448_' + uuid4().hex[:12]
    rows = _rows(12)
    template = dict(rows[0])
    for row in rows:
        lineage = {k:row[k] for k in ('source_row_id','source_row_number')}
        row.update(template)
        row.update(lineage)
        row['Nº Empenho'] = '000012'
        row['Total Pago'] = '344.3499999999999'
    artifact, reader = _artifact(tmp_path, rows)
    grain=validate_grain(discover_grain_from_artifact(reader),source_record_grain=True)
    model=build_mvp_model(artifact,grain,approved=True,additive_measures=['Total Pago'])
    first=load_postgresql(reader,model,dsn,schema=schema,chunk_size=4,apply_ddl=True)
    assert first.reconciliation_status == 'PASS'
    assert Decimal(first.source_totals['total_pago']) == Decimal('344.3499999999999')*12
    with psycopg.connect(dsn) as conn:
        values=conn.execute(f'SELECT COUNT(DISTINCT despesa_registro_sk), COUNT(*), MIN("no_empenho") FROM "{schema}".fato_despesa_registro').fetchone()
        assert values == (12,12,'000012')
        assert conn.execute(f'SELECT source_values ->> \'Nº Empenho\' FROM "{schema}".fato_despesa_registro LIMIT 1').fetchone()[0]=='000012'
        assert conn.execute(f'SELECT quantidade_registros FROM "{schema}".vw_despesa_executivo').fetchone()[0]==12
    # Failure after one staged chunk must not publish a partial dataset.
    fail_schema = schema + '_fail'
    original = reader.iter_chunks
    def failing_chunks(**kwargs):
        yield next(original(**kwargs))
        raise ValueError('injected read failure')
    reader.iter_chunks = failing_chunks
    with pytest.raises(ValueError,match='injected'):
        load_postgresql(reader,model,dsn,schema=fail_schema,chunk_size=4,apply_ddl=True)
    with psycopg.connect(dsn) as conn:
        assert conn.execute(f'SELECT COUNT(*) FROM "{fail_schema}".fato_despesa_registro').fetchone()[0]==0
        assert conn.execute(f'SELECT status FROM "{fail_schema}".bi_load_run').fetchone()[0]=='FAILED'
    reader.iter_chunks = original
    assert load_postgresql(reader,model,dsn,schema=fail_schema,chunk_size=4).rows_loaded==12
    changed = model.model_copy(update={'prepared_artifact_sha256':'0'*64})
    with pytest.raises(ValueError, match='integrity'):
        load_postgresql(reader,changed,dsn,schema=schema)
