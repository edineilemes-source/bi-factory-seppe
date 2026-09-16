"""Tests for the Streamlit-independent session lifecycle."""

from core.profiling.field_profiler import profile_field
from core.profiling.models import ProjectContext, SheetProfile, WorkbookProfile, WorkbookSummary
from core.semantic.question_generator import ROLE_LABELS
from app.session_state import (
    SourceChangeRequiresConfirmation,
    get_or_create_analysis,
    initialize_session_state,
    reset_analysis_state,
    save_semantic_answer,
    set_current_question,
    source_change_requires_confirmation,
)


def _profile() -> WorkbookProfile:
    fields = [
        profile_field("Identificador A", "identificador_a", [1, 1, 1, 2, 2, 2]),
        profile_field("Identificador B", "identificador_b", [3, 3, 3, 4, 4, 4]),
    ]
    sheet = SheetProfile(
        name="Dados", role_hypothesis="A validar", approximate_row_count=4,
        column_count=2, sampled_data_row_count=4, fields=fields,
    )
    return WorkbookProfile(
        context=ProjectContext(), original_name="state.csv", source_type="browser_upload",
        size_bytes=42, file_type="csv",
        summary=WorkbookSummary(
            sheet_count=1, total_approximate_rows=4, total_columns=2, warning_count=0,
        ),
        sheets=[sheet],
    )


def test_first_initialization_is_safe_and_idempotent() -> None:
    state = {}
    initialize_session_state(state)
    state["semantic_answers"]["saved"] = {"answer": "x"}
    initialize_session_state(state)
    assert state["analysis_completed"] is False
    assert state["semantic_answers"] == {"saved": {"answer": "x"}}


def test_answer_survives_and_second_answer_does_not_erase_first() -> None:
    state = {}
    get_or_create_analysis(state, ("upload", "one"), _profile)
    first, second = state["semantic_questions"]
    save_semantic_answer(state, first.question_id, ROLE_LABELS[first.current_hypothesis])
    first_saved = dict(state["semantic_answers"][first.question_id])
    save_semantic_answer(state, second.question_id, ROLE_LABELS[second.current_hypothesis])
    assert state["semantic_answers"][first.question_id] == first_saved
    assert second.question_id in state["semantic_answers"]


def test_normal_rerun_does_not_regenerate_questions_or_recalculate_profile() -> None:
    state = {}
    calls = 0

    def factory() -> WorkbookProfile:
        nonlocal calls
        calls += 1
        return _profile()

    profile, created = get_or_create_analysis(state, ("upload", "one"), factory)
    questions = state["semantic_questions"]
    same_profile, recreated = get_or_create_analysis(state, ("upload", "one"), factory)
    assert created is True and recreated is False
    assert calls == 1
    assert same_profile is profile
    assert state["semantic_questions"] is questions


def test_current_question_advances_and_navigation_is_bounded() -> None:
    state = {}
    get_or_create_analysis(state, ("upload", "one"), _profile)
    first = state["semantic_questions"][0]
    save_semantic_answer(state, first.question_id, ROLE_LABELS[first.current_hypothesis])
    assert state["current_question_index"] == 1
    set_current_question(state, -10)
    assert state["current_question_index"] == 0
    set_current_question(state, 999)
    assert state["current_question_index"] == len(state["semantic_questions"]) - 1


def test_reset_clears_analysis_and_semantic_widget_state() -> None:
    state = {"semantic_answer_widget": "old", "unrelated": "keep"}
    get_or_create_analysis(state, ("upload", "one"), _profile)
    reset_analysis_state(state)
    assert state["current_profile"] is None
    assert state["current_validation_report"] is None
    assert state["semantic_questions"] == []
    assert state["semantic_answers"] == {}
    assert state["selected_source"] is None
    assert state["current_question_index"] == 0
    assert "semantic_answer_widget" not in state
    assert state["unrelated"] == "keep"


def test_source_change_detects_answers_and_requires_confirmation() -> None:
    state = {}
    get_or_create_analysis(state, ("upload", "one"), _profile)
    first = state["semantic_questions"][0]
    save_semantic_answer(state, first.question_id, ROLE_LABELS[first.current_hypothesis])
    assert source_change_requires_confirmation(state, ("upload", "two")) is True
    try:
        get_or_create_analysis(state, ("upload", "two"), _profile)
    except SourceChangeRequiresConfirmation:
        pass
    else:
        raise AssertionError("A troca deveria exigir confirmação")
    assert first.question_id in state["semantic_answers"]


def test_confirmed_source_change_replaces_previous_analysis() -> None:
    state = {}
    get_or_create_analysis(state, ("upload", "one"), _profile)
    first = state["semantic_questions"][0]
    save_semantic_answer(state, first.question_id, ROLE_LABELS[first.current_hypothesis])
    get_or_create_analysis(
        state, ("upload", "two"), _profile,
        confirm_source_change=True,
    )
    assert state["selected_source"] == ("upload", "two")
    assert state["semantic_answers"] == {}
