import re

from core.bi_mvp.models import MVPModel, MVPStatus


def identifier(value: str) -> str:
    if not re.fullmatch(r"[^\W\d]\w*", value) or len(value.encode("utf-8")) > 63:
        raise ValueError(f"Unsafe PostgreSQL identifier: {value}")
    return value


def generate_postgresql_ddl(model: MVPModel, *, schema: str = "bi") -> str:
    if model.status != MVPStatus.APPROVED:
        raise ValueError("DDL requires an approved MVP model.")
    s = identifier(schema)
    identifier(model.fact_name)
    for value in model.source_fields.values(): identifier(value)
    for measure in model.measures:
        identifier(measure.name)
        if measure.postgres_type != "NUMERIC": raise ValueError("Unsupported monetary type")
    for dim in model.dimensions: identifier(dim.name)
    statements = [f'CREATE SCHEMA IF NOT EXISTS "{s}";']
    for dim in model.dimensions:
        table = identifier("dim_" + dim.name)
        attrs = ",\n  ".join(f'"{model.source_fields[x]}" TEXT' for x in dim.source_fields)
        statements.append(f'''CREATE TABLE IF NOT EXISTS "{s}"."{table}" (
  "{dim.name}_sk" BIGSERIAL PRIMARY KEY,
  business_key_hash TEXT NOT NULL UNIQUE,
  {attrs}
);''')
    dimension_fks = []
    for dim in model.dimensions:
        dimension_fks.append(
            f'"{dim.name}_sk" BIGINT REFERENCES "{s}"."dim_{dim.name}"("{dim.name}_sk")')
    identifiers = [f'"{model.source_fields[x]}" TEXT' for x in model.preserved_identifiers]
    measures = [f'"{item.name}" {item.postgres_type}' for item in model.measures]
    payload = ",\n  ".join(dimension_fks + identifiers + measures)
    statements.append(f'''CREATE TABLE IF NOT EXISTS "{s}"."{model.fact_name}" (
  despesa_registro_sk BIGSERIAL PRIMARY KEY,
  analysis_id UUID NOT NULL,
  prepared_dataset_id UUID NOT NULL,
  prepared_version INTEGER NOT NULL,
  source_document_id TEXT NOT NULL,
  source_row_id TEXT NOT NULL,
  sheet_name TEXT NOT NULL,
  source_row_number BIGINT NOT NULL,
  source_values JSONB NOT NULL,
  {payload + chr(44) if payload else ""}
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (analysis_id, prepared_version, source_row_id)
);''')
    statements.append(f'''CREATE TABLE IF NOT EXISTS "{s}".bi_load_run (
  run_id UUID PRIMARY KEY, analysis_id UUID NOT NULL, prepared_dataset_id UUID NOT NULL,
  prepared_version INTEGER NOT NULL, artifact_sha256 TEXT NOT NULL, status TEXT NOT NULL,
  rows_read BIGINT NOT NULL DEFAULT 0, rows_loaded BIGINT NOT NULL DEFAULT 0,
  metrics JSONB NOT NULL DEFAULT '{{}}'::jsonb, started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ
);''')
    statements.append(f'''CREATE TABLE IF NOT EXISTS "{s}".bi_model_contract (
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
  contract JSONB NOT NULL
);''')
    return "\n\n".join(statements) + "\n"
