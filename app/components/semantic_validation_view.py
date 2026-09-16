"""Streamlit view for session-persistent assisted semantic validation."""

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from app.session_state import save_semantic_answer
from core.semantic.models import AnalysisStatus, QuestionStatus, SemanticQuestion, SemanticValidationReport
from core.semantic.question_generator import OTHER_OPTION


def _question_context(question: SemanticQuestion) -> None:
    st.markdown(f"#### {question.title}")
    st.write(question.question_text)
    st.caption(
        f"Campo: {question.field_name} · Tipo detectado: {question.detected_type} · "
        f"Tipo recomendado: {question.recommended_type} · Hipótese: "
        f"{question.current_hypothesis.value} · Confiança: {question.confidence:.0%}"
    )
    st.write("Exemplos da amostra:", question.examples or ["Sem valores na amostra."])
    with st.expander("Por que o sistema perguntou?"):
        st.write(question.reason)
        st.write("Evidências:", question.evidence or ["Sem evidência suficiente."])
        if question.conflicts:
            st.write("Conflitos:", [conflict.message for conflict in question.conflicts])


def _render_question(state: MutableMapping[str, Any], question: SemanticQuestion) -> None:
    _question_context(question)
    saved = state["semantic_answers"].get(question.question_id, {})
    default_answer = saved.get("answer")
    default_index = question.options.index(default_answer) if default_answer in question.options else 0
    answer = st.radio(
        "Escolha a opção que melhor descreve o campo",
        question.options,
        index=default_index,
        key=f"semantic_answer_{question.question_id}",
    )
    with st.form(f"semantic_form_{question.question_id}"):
        custom_answer = None
        if answer == OTHER_OPTION:
            custom_answer = st.text_input(
                "Explique com suas palavras",
                value=saved.get("custom_answer") or "",
                key=f"semantic_custom_{question.question_id}",
            )
        submitted = st.form_submit_button("Salvar e continuar")
    if submitted:
        try:
            save_semantic_answer(
                state, question.question_id, answer,
                custom_answer,
            )
        except ValueError as error:
            st.error(str(error))
        else:
            # The complete state is saved first; this rerun only renders the next question immediately.
            st.rerun()


def render_semantic_validation(state: MutableMapping[str, Any]) -> None:
    """Render the current question, persistent progress, metrics and current export."""
    report: SemanticValidationReport = state["current_validation_report"]
    questions: list[SemanticQuestion] = state["semantic_questions"]
    st.markdown("## Validação Semântica")
    st.caption("As respostas são persistidas localmente e o profiling observado não é alterado.")
    summary = report.summary
    columns = st.columns(5)
    columns[0].metric("Campos analisados", summary.fields_analyzed)
    columns[1].metric("Aceitos automaticamente", summary.auto_accepted)
    columns[2].metric("Precisam confirmação", summary.need_confirmation)
    columns[3].metric("Precisam resposta", summary.need_answer)
    columns[4].metric("Não resolvidos", summary.unresolved)
    if report.reuse_report:
        reuse=report.reuse_report
        reuse_columns=st.columns(5)
        reuse_columns[0].metric("Conhecimento reutilizado",reuse.reused_count)
        reuse_columns[1].metric("Autoaceitos",reuse.auto_accepted_count)
        reuse_columns[2].metric("Reconfirmações",reuse.reconfirm_count)
        reuse_columns[3].metric("Perguntas novas",reuse.ask_count)
        reuse_columns[4].metric("Sem evidência",reuse.deferred_count)

    pending_questions = [q for q in questions if q.status == QuestionStatus.PENDING]
    completed = report.analysis_status != AnalysisStatus.IN_PROGRESS
    if completed:
        st.success("Validação Semântica concluída")
        if report.analysis_status == AnalysisStatus.COMPLETED_WITH_UNRESOLVED:
            st.warning("A análise foi concluída com respostas que precisam de verificação posterior.")
    elif pending_questions:
        question = pending_questions[0]
        answered_count = len(questions) - len(pending_questions)
        st.write(f"Próxima pergunta · {answered_count + 1} de {len(questions)}")
        st.progress(answered_count / len(questions), text=f"{answered_count} de {len(questions)} respondidas")
        with st.container(border=True):
            _render_question(state, question)
    else:
        st.success("Validação Semântica concluída")

    with st.expander("Revisar respostas e conhecimento validado", expanded=completed):
        st.json([item.model_dump(mode="json") for item in report.validated_semantics])
    st.download_button(
        "Baixar diagnóstico validado", data=report.model_dump_json(indent=2),
        file_name=f"{report.observed_profile.original_name}.diagnostico-validado.json",
        mime="application/json",
    )
