import hashlib
import json
import resource
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from uuid import uuid4

from core.bi_mvp.ddl import identifier
from core.bi_mvp.models import LoadMetrics, MVPModel, MVPStatus
from core.prepared.artifact_reader import PreparedDatasetArtifactReader


def _rss_mb() -> float:
    # Linux reports KiB; this project runs and benchmarks on Linux containers.
    with open("/proc/self/statm") as stream:
        import os
        return int(stream.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024**2


def _hash(values) -> str:
    canonical = json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _decimal(value):
    if value is None: return None
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Monetary value exceeds exact NUMERIC representation")
        return number
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid monetary value in Prepared artifact: {value!r}")


def add_exact(left, right):
    # Align exponents and reserve enough integer digits; never use ambient precision.
    with localcontext() as context:
        context.prec = max(left.adjusted(), right.adjusted(), 0) - min(left.as_tuple().exponent, right.as_tuple().exponent, 0) + 3
        return left + right


def _stage_columns(model):
    columns = ["source_row_id", "sheet_name", "source_row_number", "source_values"]
    for dim in model.dimensions:
        columns.append("bk_" + dim.name)
        columns.extend(model.source_fields[x] for x in dim.source_fields)
    columns.extend(model.source_fields[x] for x in model.preserved_identifiers)
    columns.extend(m.name for m in model.measures)
    return list(dict.fromkeys(columns))


def _stage_row(model, row):
    from psycopg.types.json import Jsonb
    out={"source_values": Jsonb(row), "source_row_id":row.get("source_row_id"), "sheet_name":row.get("sheet_name"),
         "source_row_number":int(row["source_row_number"])}
    for dim in model.dimensions:
        values=[row.get(x) for x in dim.business_key_fields]
        out["bk_"+dim.name]=_hash(values)
        for source in dim.source_fields: out[model.source_fields[source]]=row.get(source)
    for source in model.preserved_identifiers: out[model.source_fields[source]]=row.get(source)
    for measure in model.measures: out[measure.name]=_decimal(row.get(measure.source_field))
    return out


def load_postgresql(reader: PreparedDatasetArtifactReader, model: MVPModel, dsn: str, *,
                    schema: str = "bi", chunk_size: int = 2_000,
                    apply_ddl: bool = False) -> LoadMetrics:
    import psycopg
    from core.bi_mvp.ddl import generate_postgresql_ddl
    from core.bi_mvp.metabase import generate_metabase_sql
    if model.status != MVPStatus.APPROVED: raise ValueError("Approved model required.")
    a=reader.artifact
    if (a.analysis_id,a.source_document_id,a.prepared_dataset_id,a.version,a.fingerprint,a.artifact_sha256) != (
            model.analysis_id,model.source_document_id,model.prepared_dataset_id,model.prepared_version,
            model.prepared_fingerprint,model.prepared_artifact_sha256):
        raise ValueError("Model/Prepared ownership, version or integrity mismatch.")
    from core.prepared.generation import verify_prepared_artifact
    verify_prepared_artifact(a)
    generate_postgresql_ddl(model, schema=schema)  # Validate every interpolated identifier even on replay.
    s=identifier(schema); run_id=str(uuid4()); started=time.perf_counter(); rss0=_rss_mb()
    metrics=LoadMetrics(run_id=run_id,analysis_id=a.analysis_id,
        prepared_dataset_id=a.prepared_dataset_id,prepared_version=a.version,rss_start_mb=rss0)
    totals={m.name:Decimal(0) for m in model.measures}; columns=_stage_columns(model)
    quoted=", ".join(f'"{x}"' for x in columns)
    types=[]
    for x in columns:
        types.append(f'"{x}" ' + ("BIGINT" if x=="source_row_number" else
                     "JSONB" if x=="source_values" else "NUMERIC" if x in totals else "TEXT"))
    run_registered = False
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                if apply_ddl:
                    cur.execute(generate_postgresql_ddl(model,schema=s))
                    cur.execute(generate_metabase_sql(model,schema=s))
                # One immutable model per target schema; incompatible versions require a new schema.
                contract = model.model_dump_json()
                cur.execute(f'SELECT pg_advisory_xact_lock(hashtext(%s))', (s,))
                cur.execute(f'INSERT INTO "{s}".bi_model_contract (singleton, contract) VALUES (TRUE,%s::jsonb) ON CONFLICT DO NOTHING', (contract,))
                cur.execute(f'SELECT contract FROM "{s}".bi_model_contract WHERE singleton')
                if cur.fetchone()[0] != json.loads(contract):
                    raise ValueError("Target schema belongs to a different model/version; choose a new schema.")
                cur.execute(f'''INSERT INTO "{s}".bi_load_run
                    (run_id,analysis_id,prepared_dataset_id,prepared_version,artifact_sha256,status,started_at)
                    VALUES (%s,%s,%s,%s,%s,'RUNNING',%s)''',
                    (run_id,a.analysis_id,a.prepared_dataset_id,a.version,a.artifact_sha256,
                     datetime.now(timezone.utc)))
            conn.commit()
            run_registered = True
            required={"source_row_id", "sheet_name", "source_row_number"}
            required.update(model.source_fields)
            required.update(x for dim in model.dimensions for x in dim.source_fields)
            required.update(model.preserved_identifiers)
            required.update(m.source_field for m in model.measures)
            for chunk in reader.iter_chunks(chunk_size=chunk_size,columns=required):
                staged=[_stage_row(model,row) for row in chunk]
                with conn.cursor() as cur:
                    cur.execute("DROP TABLE IF EXISTS pg_temp.bi_mvp_stage")
                    cur.execute("CREATE TEMP TABLE bi_mvp_stage ("+", ".join(types)+") ON COMMIT DROP")
                    with cur.copy(f"COPY bi_mvp_stage ({quoted}) FROM STDIN") as copy:
                        for row in staged: copy.write_row([row[x] for x in columns])
                    for dim in model.dimensions:
                        attrs=[model.source_fields[x] for x in dim.source_fields]
                        attr_sql=", ".join(f'"{x}"' for x in attrs)
                        cur.execute(f'''INSERT INTO "{s}"."dim_{dim.name}" (business_key_hash,{attr_sql})
                            SELECT DISTINCT "bk_{dim.name}",{attr_sql} FROM bi_mvp_stage
                            ON CONFLICT (business_key_hash) DO NOTHING''')
                    fact_cols=[f'"{d.name}_sk"' for d in model.dimensions]
                    fact_cols += [f'"{model.source_fields[x]}"' for x in model.preserved_identifiers]
                    fact_cols += [f'"{m.name}"' for m in model.measures]
                    select_cols=[f'd{i}."{d.name}_sk"' for i,d in enumerate(model.dimensions)]
                    select_cols += [f's."{model.source_fields[x]}"' for x in model.preserved_identifiers]
                    select_cols += [f's."{m.name}"' for m in model.measures]
                    joins=" ".join(f'JOIN "{s}"."dim_{d.name}" d{i} ON d{i}.business_key_hash=s."bk_{d.name}"'
                                   for i,d in enumerate(model.dimensions))
                    cur.execute(f'''INSERT INTO "{s}"."{model.fact_name}"
                        (analysis_id,prepared_dataset_id,prepared_version,source_document_id,
                         source_row_id,sheet_name,source_row_number,source_values{',' if fact_cols else ''}{','.join(fact_cols)})
                        SELECT %s,%s,%s,%s,s.source_row_id,s.sheet_name,s.source_row_number,s.source_values{',' if select_cols else ''}{','.join(select_cols)}
                        FROM bi_mvp_stage s {joins}
                        ON CONFLICT (analysis_id,prepared_version,source_row_id) DO NOTHING''',
                        (a.analysis_id,a.prepared_dataset_id,a.version,a.source_document_id))
                    loaded=cur.rowcount
                metrics.rows_read+=len(chunk); metrics.rows_loaded+=loaded
                metrics.rows_already_loaded+=len(chunk)-loaded; metrics.chunk_count+=1
                for row in staged:
                    for name in totals:
                        if row[name] is not None: totals[name]=add_exact(totals[name],row[name])
                metrics.rss_peak_mb=max(metrics.rss_peak_mb,_rss_mb())
            with conn.cursor() as cur:
                expressions=", ".join(f'COALESCE(SUM("{m.name}"),0)' for m in model.measures)
                cur.execute(f'''SELECT COUNT(*){',' if expressions else ''}{expressions} FROM "{s}"."{model.fact_name}"
                    WHERE analysis_id=%s AND prepared_version=%s''',(a.analysis_id,a.version))
                result=cur.fetchone(); db_count=result[0]; metrics.database_row_count=db_count
                db_totals={m.name:Decimal(result[i+1]) for i,m in enumerate(model.measures)}
                metrics.source_totals={k:str(v) for k,v in totals.items()}
                metrics.database_totals={k:str(v) for k,v in db_totals.items()}
                metrics.reconciliation_status=("PASS" if db_count==metrics.rows_read==a.row_count and
                    all(db_totals[k]==v for k,v in totals.items()) else "FAIL")
                if metrics.reconciliation_status != "PASS":
                    raise ValueError("Row count or monetary reconciliation failed; data transaction rolled back.")
                metrics.rss_end_mb=_rss_mb(); metrics.elapsed_seconds=time.perf_counter()-started
                cur.execute(f'''UPDATE "{s}".bi_load_run SET status=%s,rows_read=%s,
                    rows_loaded=%s,metrics=%s::jsonb,finished_at=%s WHERE run_id=%s''',
                    (metrics.reconciliation_status,metrics.rows_read,metrics.rows_loaded,
                     metrics.model_dump_json(),datetime.now(timezone.utc),run_id))
            conn.commit()
    except Exception as error:
        metrics.error=str(error); metrics.reconciliation_status="FAILED"
        metrics.rss_end_mb=_rss_mb(); metrics.elapsed_seconds=time.perf_counter()-started
        if run_registered:
            # The data transaction has rolled back. Record failure separately.
            metrics.rows_loaded = 0
            try:
                with psycopg.connect(dsn) as failed_conn:
                    failed_conn.execute(f'''UPDATE "{s}".bi_load_run SET status='FAILED',
                        metrics=%s::jsonb,finished_at=%s WHERE run_id=%s''',
                        (metrics.model_dump_json(), datetime.now(timezone.utc),run_id))
            except Exception as logging_error:
                error.add_note(f"Could not persist failed execution {run_id}: {type(logging_error).__name__}")
        raise
    return metrics
