"""Reproducible artifact-only MVP; no XLSX reads or implicit human approvals."""
import argparse
import os
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from core.bi_mvp.artifacts import load_model, persist_text, resolve_prepared
from core.bi_mvp.workflow import prepare_model
from core.bi_mvp.etl import load_postgresql
from core.persistence.sqlite_repository import SQLiteAnalysisRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis_id')
    parser.add_argument('--database', default='storage/bi_factory.sqlite3')
    parser.add_argument('--prepared-id')
    parser.add_argument('--prepared-version', type=int)
    parser.add_argument('--schema', default='bi')
    parser.add_argument('--dsn', default=os.getenv('BI_MVP_POSTGRES_DSN'))
    parser.add_argument('--chunk-size', type=int, default=2000)
    parser.add_argument('--model', help='Resume exact persisted model JSON; validates its checksum')
    parser.add_argument('--approve-model', action='store_true', help='Explicit human approval of proposed field mappings')
    parser.add_argument('--additive-measure', action='append', default=[], help='Source name explicitly confirmed additive')
    args = parser.parse_args()
    repo = SQLiteAnalysisRepository(args.database)
    reader = resolve_prepared(args.analysis_id, repo, prepared_dataset_id=args.prepared_id, version=args.prepared_version)
    if args.model:
        model = load_model(args.model)
        grain = repo.get_effective_grain(reader.artifact.prepared_dataset_id)
        if grain is None or grain.grain_id != model.grain_definition_id:
            raise ValueError('Model grain is no longer the effective human validation.')
    else:
        model, path = prepare_model(reader, repo, approve=args.approve_model,
            additive_measures=args.additive_measure, schema=args.schema)
        print(path)
    if args.dsn:
        metrics = load_postgresql(reader, model, args.dsn, schema=args.schema,
                                 chunk_size=args.chunk_size, apply_ddl=True)
        root = Path('storage/reports/bi_mvp') / args.analysis_id
        persist_text(root / f'load-{metrics.run_id}.json', metrics.model_dump_json(indent=2))
        print(metrics.model_dump_json(indent=2))
        return 0 if metrics.reconciliation_status == 'PASS' else 2
    print(f'Model {model.status.value}; PostgreSQL not loaded. Use --model with BI_MVP_POSTGRES_DSN after approval.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
