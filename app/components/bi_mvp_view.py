"""Independent persisted-artifact entry point, before any workbook ingestion."""
import os
from pathlib import Path
import streamlit as st
from core.bi_mvp.artifacts import resolve_prepared, load_model, persist_text
from core.bi_mvp.workflow import prepare_model
from core.bi_mvp.modeling import MEASURES
from core.bi_mvp.etl import load_postgresql
from core.grain.artifact_discovery import GRAIN_ENGINE_VERSION
from app.components.grain_discovery_view import render_grain_discovery


def render_bi_mvp(repository):
    st.subheader('BI MVP — análise persistida')
    analysis_id = st.text_input('Analysis ID', key='mvp_analysis_id')
    if not analysis_id: return
    try:
        reader = resolve_prepared(analysis_id, repository)
        artifact = reader.artifact
        st.caption(f'Prepared {artifact.prepared_dataset_id} · v{artifact.version} · {artifact.row_count:,} linhas')
        # Only small contracts enter this local rendering state, never the dataset.
        state = dict(repository=repository, selected_analysis_id=analysis_id,
                     current_analysis_id=analysis_id, current_prepared_artifact=artifact,
                     current_prepared_dataset_id=artifact.prepared_dataset_id,
                     source_document_id=artifact.source_document_id)
        reports = repository.list_grain_discovery_reports(artifact.prepared_dataset_id)
        state['current_grain_report'] = next((r.report for r in reports
            if r.report.engine_version == GRAIN_ENGINE_VERSION), None)
        grain = repository.get_effective_grain(artifact.prepared_dataset_id)
        state['current_grain_definition'] = grain
        render_grain_discovery(state)
        if grain is None:
            st.info('Valide o grão para propor o modelo. “Não sei” mantém a modelagem bloqueada.')
            return
        schema = st.text_input('Schema do MVP', 'bi')
        available = {f.source_name for f in artifact.schema_fields}
        additive = st.multiselect('Medidas cuja soma entre linhas você confirma',
                                  [m for m in MEASURES if m in available])
        st.caption('Deixe vazio se a aditividade ainda não foi validada. Os valores individuais serão preservados.')
        if st.button('Gerar proposta dimensional MVP'):
            prepare_model(reader, repository, additive_measures=additive, schema=schema)
        directory = Path('storage/reports/bi_mvp') / analysis_id
        paths = sorted(directory.glob('model-v*.json'), key=lambda p:int(p.stem.split('-v')[1]))
        if not paths: return
        model = load_model(paths[-1])
        if model.grain_definition_id != grain.grain_id:
            st.warning('O grão mudou; gere uma nova proposta.')
            return
        st.json(model.model_dump(mode='json'))
        if st.button('Aprovar mapeamentos e medidas selecionadas'):
            prepare_model(reader, repository, approve=True, additive_measures=additive, schema=schema)
            st.rerun()
        for path in sorted(directory.glob(f'*-v{model.version}-{schema}.*')):
            st.download_button(path.name, path.read_text(), file_name=path.name)
        if model.status.value == 'APPROVED':
            if not os.getenv('BI_MVP_POSTGRES_DSN'):
                st.info('Configure BI_MVP_POSTGRES_DSN para executar a carga PostgreSQL.')
            elif st.button('Carregar PostgreSQL e reconciliar'):
                metrics = load_postgresql(reader, model, os.environ['BI_MVP_POSTGRES_DSN'],
                                          schema=schema, apply_ddl=True)
                persist_text(directory / f'load-{metrics.run_id}.json', metrics.model_dump_json(indent=2))
                st.json(metrics.model_dump(mode='json'))
    except (ValueError, OSError, RuntimeError) as error:
        st.error(str(error))
