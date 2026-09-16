"""Restartable model proposal and explicit approval with immutable contracts."""
from pathlib import Path
from core.bi_mvp.artifacts import load_model, persist_model, persist_text
from core.bi_mvp.audit import inspect_prepared
from core.bi_mvp.modeling import build_mvp_model
from core.bi_mvp.ddl import generate_postgresql_ddl
from core.bi_mvp.metabase import generate_metabase_sql, dashboard_instructions


def prepare_model(reader, repository, *, root='storage/reports/bi_mvp',
                  approve=False, additive_measures=None, schema='bi'):
    grain = repository.get_effective_grain(reader.artifact.prepared_dataset_id)
    if grain is None:
        raise ValueError('PENDING_HUMAN_GRAIN_VALIDATION: valide o grão antes de gerar o modelo.')
    # Consult persisted corporate knowledge before proposing local dimension mappings.
    knowledge = repository.list_semantic_knowledge(reader.artifact.source_document_id)
    observed = inspect_prepared(reader)
    directory = Path(root) / reader.artifact.analysis_id
    paths = sorted(directory.glob('model-v*.json'), key=lambda p: int(p.stem.split('-v')[1]))
    previous = load_model(paths[-1]) if paths else None
    model = build_mvp_model(reader.artifact, grain,
        version=previous.version if previous else 1,
        approved=approve, additive_measures=additive_measures,
        nonnull_counts=observed['nonnull_counts'])
    if previous and previous != model:
        model = build_mvp_model(reader.artifact, grain, version=previous.version+1,
            approved=approve, additive_measures=additive_measures,
            nonnull_counts=observed['nonnull_counts'])
    path = persist_model(model, root)
    import json
    catalog = [k.model_dump(mode='json') for k in knowledge]
    persist_text(directory / f'catalog-v{model.version}.json', json.dumps(catalog,ensure_ascii=False,indent=2))
    if approve:
        persist_text(directory / f'ddl-v{model.version}-{schema}.sql', generate_postgresql_ddl(model,schema=schema))
        persist_text(directory / f'metabase-v{model.version}-{schema}.sql', generate_metabase_sql(model,schema=schema))
        persist_text(directory / f'dashboard-v{model.version}-{schema}.md', dashboard_instructions(model,schema=schema))
    return model, path
