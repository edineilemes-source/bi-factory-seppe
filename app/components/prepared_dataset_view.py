"""Bounded-memory Prepared Dataset generation UI."""

from collections.abc import MutableMapping
import json
import time
from typing import Any
from uuid import uuid4

import streamlit as st

from app.dataframe_compat import arrow_compatible_dataframe
from core.prepared.generation import (
    DEFAULT_PREPARED_CHUNK_SIZE, generate_prepared_dataset_artifact,
    verify_prepared_artifact,
)
from core.prepared.models import (PreparedDatasetArtifact, PreparedDatasetStatus,
                                  PreparedProgressEvent)
from app.session_state import transition_prepared_to_grain


def generate_prepared_dataset(
    state: MutableMapping[str, Any], *, progress_callback=None,
) -> PreparedDatasetArtifact:
    content = state.get("current_source_content")
    name = state.get("current_source_name")
    semantic = state.get("current_validation_report")
    if not content or not name or semantic is None:
        raise ValueError("A fonte original e a análise semântica são obrigatórias.")
    repository = state.get("repository")
    version = repository.next_prepared_version(semantic.analysis_id) if repository else 1
    prepared_id = str(uuid4())

    def status_callback(status, stage, reason):
        if repository:
            repository.update_prepared_generation(
                prepared_id, semantic.analysis_id, version, status, stage, reason)

    artifact = generate_prepared_dataset_artifact(
        name, content, semantic, state.get("current_quality_report"), version=version,
        chunk_size=DEFAULT_PREPARED_CHUNK_SIZE, progress_callback=progress_callback,
        status_callback=status_callback, prepared_dataset_id=prepared_id,
    )
    if repository:
        repository.save_prepared_artifact(artifact)
    state["current_prepared_dataset"] = None
    state["current_prepared_dataset_id"] = artifact.prepared_dataset_id
    state["current_prepared_artifact"] = artifact
    return artifact


def _summary_bytes(artifact: PreparedDatasetArtifact) -> bytes:
    payload = artifact.model_dump(mode="json", by_alias=True, exclude={"preview"})
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def render_prepared_dataset(state: MutableMapping[str, Any]) -> None:
    st.markdown("## PREPARED DATASET")
    artifact: PreparedDatasetArtifact | None = state.get("current_prepared_artifact")
    label = "Gerar nova versão" if artifact else "GERAR DATASET PREPARADO"
    if st.button(label):
        progress_bar = st.progress(0.0, text="Preparando dataset...")
        status_line = st.empty(); started = time.monotonic()

        def update(event: PreparedProgressEvent) -> None:
            ratio = event.rows_processed / event.total_rows if event.total_rows else 0.0
            progress_bar.progress(min(max(ratio, 0.0), 1.0), text=event.message)
            status_line.caption(
                f"{event.rows_processed:,} linhas · {event.elapsed_seconds:.1f}s · {event.stage}")
        try:
            generate_prepared_dataset(state, progress_callback=update)
        except MemoryError:
            st.error("Memória insuficiente durante a geração; estado FAILED persistido.")
        except (ValueError, OSError, IOError, RuntimeError) as error:
            st.error(f"Não foi possível gerar o Prepared Dataset: {error}")
        except Exception as error:
            st.error(f"Falha inesperada na geração: {type(error).__name__}: {error}")
        else:
            progress_bar.progress(1.0, text="Prepared Dataset concluído")
            status_line.caption(f"Concluído em {time.monotonic() - started:.1f}s")
            st.rerun()
    if artifact is None:
        st.caption("A preparação final usa chunks e não mantém o dataset completo na sessão.")
        return
    try:
        verify_prepared_artifact(artifact)
    except ValueError as error:
        st.error(str(error)); return
    st.success("Prepared Dataset concluído")
    metrics = st.columns(7)
    metrics[0].metric("Status", artifact.generation_status.value)
    metrics[1].metric("Rows", artifact.row_count)
    metrics[2].metric("Fields", artifact.field_count)
    metrics[3].metric("Transformations", artifact.total_transformations)
    metrics[4].metric("Versão", artifact.version)
    metrics[5].metric("Formato", artifact.artifact_format.upper())
    metrics[6].metric("Fingerprint", artifact.fingerprint[:12])
    st.caption(f"Artifact: {artifact.artifact_location} · {artifact.artifact_size_bytes:,} bytes")
    if artifact.transformation_summary:
        st.dataframe(arrow_compatible_dataframe([
            {"Transformação": name, "Quantidade": count}
            for name, count in artifact.transformation_summary.items()
        ], integer_columns=("Quantidade",)), hide_index=True, use_container_width=True)
    st.markdown("### Preview limitado")
    st.dataframe(arrow_compatible_dataframe(artifact.preview),
                 hide_index=True, use_container_width=True)
    st.download_button("Baixar resumo", _summary_bytes(artifact),
                       file_name=f"prepared-{artifact.analysis_id}-v{artifact.version}-summary.json",
                       mime="application/json")
    if artifact.status == PreparedDatasetStatus.BLOCKED:
        st.warning("Quality Gate BLOCKED; revise os bloqueios antes do Grain Discovery.")
    elif st.button("Continuar para Grain Discovery"):
        try:
            transition_prepared_to_grain(state)
        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"Não foi possível abrir Grain Discovery: {error}")
        else:
            st.rerun()
