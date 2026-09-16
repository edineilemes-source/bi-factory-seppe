"""Framework-light lifecycle for analysis state kept by Streamlit."""

from collections.abc import Callable, MutableMapping
import logging
from typing import Any

from core.profiling.models import WorkbookProfile
from core.persistence.models import AnalysisRecord
from core.persistence.models import AnalysisStage
from core.persistence.repository import AnalysisRepository
from core.prepared.models import PreparedDatasetArtifact, PreparedDatasetStatus
from core.prepared.artifact_reader import PreparedDatasetArtifactReader
from core.semantic.models import AnalysisStatus, QuestionStatus, SemanticValidationReport
from core.semantic.validation_service import answer_question, create_validation_report


SESSION_DEFAULTS: dict[str, Any] = {
    "current_profile": None,
    "current_validation_report": None,
    "semantic_questions": None,
    "semantic_answers": None,
    "selected_source": None,
    "analysis_completed": False,
    "current_question_index": 0,
    "analysis_id": None,
    "current_analysis_id": None,
    "selected_analysis_id": None,
    "current_analysis_stage": None,
    "last_successful_stage": None,
    "source_document_id": None,
    "analysis_status": None,
    "repository": None,
    "current_workbook": None,
    "current_quality_report": None,
    "current_prepared_dataset": None,
    "current_prepared_dataset_id": None,
    "current_prepared_artifact": None,
    "current_source_content": None,
    "current_source_name": None,
    "current_source_type": None,
    "current_grain_report": None,
    "current_grain_definition": None,
    "current_dimensional_report": None,
    "current_validated_dimensional": None,
    "current_star_schema_report": None,
    "current_validated_star_schema": None,
    "current_physical_schema_plan": None,
    "current_ddl_artifact": None,
    "current_etl_plan": None,
    "current_validated_etl_plan": None,
    "current_transformation_run": None,
    "current_database_dry_run": None,
}

LOGGER = logging.getLogger(__name__)


class SourceChangeRequiresConfirmation(RuntimeError):
    """Raised before replacing an analysis that already has user answers."""


def initialize_session_state(state: MutableMapping[str, Any]) -> None:
    """Initialize missing keys without overwriting values from an earlier rerun."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in state:
            state[key] = {} if key == "semantic_answers" else [] if key == "semantic_questions" else default


def has_semantic_answers(state: MutableMapping[str, Any]) -> bool:
    initialize_session_state(state)
    return bool(state["semantic_answers"])


def source_change_requires_confirmation(state: MutableMapping[str, Any], source: Any) -> bool:
    initialize_session_state(state)
    return (
        bool(state["analysis_completed"])
        and state["selected_source"] != source
        and has_semantic_answers(state)
    )


def get_or_create_analysis(
    state: MutableMapping[str, Any],
    source: Any,
    profile_factory: Callable[[], WorkbookProfile],
    *,
    force: bool = False,
    confirm_source_change: bool = False,
) -> tuple[WorkbookProfile, bool]:
    """Profile only on first analysis, explicit reanalysis, or confirmed source change."""
    initialize_session_state(state)
    same_source = state["analysis_completed"] and state["selected_source"] == source
    if same_source and not force:
        return state["current_profile"], False
    if source_change_requires_confirmation(state, source) and not confirm_source_change:
        raise SourceChangeRequiresConfirmation(
            "Já existem respostas salvas. Confirme antes de trocar a fonte."
        )

    profile = profile_factory()
    report = create_validation_report(profile)
    priority = {"high": 0, "medium": 1, "low": 2}
    report.questions.sort(key=lambda question: priority[question.priority.value])
    state["current_profile"] = profile
    state["current_validation_report"] = report
    state["semantic_questions"] = report.questions
    state["semantic_answers"] = {}
    state["selected_source"] = source
    state["analysis_completed"] = True
    state["current_question_index"] = 0
    return profile, True


def _load_record(
    state: MutableMapping[str, Any], record: AnalysisRecord,
    repository: AnalysisRepository,
) -> WorkbookProfile:
    """Hydrate temporary UI state from the repository source of truth."""
    reset_analysis_state(state)
    report = record.report
    priority = {"high": 0, "medium": 1, "low": 2}
    report.questions.sort(key=lambda question: priority[question.priority.value])
    state["current_profile"] = report.observed_profile
    state["current_validation_report"] = report
    state["semantic_questions"] = report.questions
    state["semantic_answers"] = repository.get_answers(record.analysis_id)
    state["selected_source"] = record.source_document_id
    state["source_document_id"] = record.source_document_id
    state["analysis_id"] = record.analysis_id
    state["current_analysis_id"] = record.analysis_id
    state["analysis_status"] = record.status
    state["repository"] = repository
    state["current_quality_report"] = repository.get_quality_report(record.analysis_id)
    prepared_records = repository.list_prepared_datasets(record.analysis_id)
    if prepared_records:
        artifact = repository.get_prepared_artifact(prepared_records[0].prepared_dataset_id)
        if artifact is None:
            raise ValueError(
                "ANALYSIS_RECOVERY_WARNING: metadata do Prepared Dataset mais recente é inválida"
            )
        state["current_prepared_dataset_id"] = artifact.prepared_dataset_id
        state["current_prepared_artifact"] = artifact
        reports = repository.list_grain_discovery_reports(artifact.prepared_dataset_id)
        if reports:
            state["current_grain_report"] = reports[0].report
        state["current_grain_definition"] = repository.get_effective_grain(
            artifact.prepared_dataset_id)
    state["analysis_completed"] = True
    pending = next(
        (index for index, question in enumerate(report.questions)
         if question.status == QuestionStatus.PENDING),
        0,
    )
    state["current_question_index"] = pending
    return report.observed_profile


def start_persistent_analysis(
    state: MutableMapping[str, Any], repository: AnalysisRepository,
    content: bytes, original_name: str,
    profile_factory: Callable[[], WorkbookProfile],
) -> AnalysisRecord:
    document = repository.register_document(content, original_name)
    record = repository.create_analysis(document.source_document_id, profile_factory())
    _load_record(state, record, repository)
    return record


def resume_persistent_analysis(
    state: MutableMapping[str, Any], repository: AnalysisRepository, analysis_id: str,
) -> AnalysisRecord:
    initialize_session_state(state)
    selected = state.get("selected_analysis_id")
    if selected is not None and selected != analysis_id:
        raise ValueError("ANALYSIS_RECOVERY_WARNING: seleção e análise solicitada divergem")
    expected_source = state.get("source_document_id")
    result = repository.resume_analysis(analysis_id, expected_source)
    record = repository.get_analysis(result.analysis_id)
    if record is None:
        raise ValueError(f"Análise não encontrada: {analysis_id}")
    _load_record(state, record, repository)
    state["selected_analysis_id"] = analysis_id
    state["current_analysis_id"] = analysis_id
    state["current_analysis_stage"] = result.current_stage
    state["last_successful_stage"] = result.last_successful_stage
    state["current_quality_report"] = result.loaded_artifacts.get("quality_report")
    if not (state["selected_analysis_id"] == result.analysis_id == state["current_analysis_id"]):
        reset_analysis_state(state)
        raise RuntimeError("ANALYSIS_RECOVERY_WARNING: invariantes de seleção violadas")
    return record


def select_analysis(state: MutableMapping[str, Any], analysis_id: str,
                    source_document_id: str) -> None:
    """Record an explicit UI choice, clearing choices from another document."""
    initialize_session_state(state)
    previous_source = state.get("source_document_id")
    if previous_source is not None and previous_source != source_document_id:
        state["current_analysis_id"] = None
    state["source_document_id"] = source_document_id
    state["selected_analysis_id"] = analysis_id


def resolve_render_stage(state: MutableMapping[str, Any]) -> AnalysisStage:
    """Return the sole UI routing value, failing instead of guessing a stage."""
    initialize_session_state(state)
    stage = state.get("current_analysis_stage")
    if not isinstance(stage, AnalysisStage):
        try:
            stage = AnalysisStage(stage)
        except (TypeError, ValueError) as error:
            raise ValueError("Etapa persistida ausente ou inválida; retomada necessária.") from error
    if stage == AnalysisStage.GRAIN_DISCOVERY:
        resolve_prepared_artifact_for_analysis(state)
    return stage


def resolve_prepared_artifact_for_analysis(
    state: MutableMapping[str, Any],
) -> PreparedDatasetArtifact:
    """Resolve Prepared from persistence; session state is only a validated cache."""
    initialize_session_state(state)
    analysis_id = state.get("analysis_id") or state.get("current_analysis_id")
    source_document_id = state.get("source_document_id")
    repository = state.get("repository")
    if not analysis_id or repository is None:
        raise ValueError("Grain Discovery indisponível: análise/repositório não resolvido.")
    artifact = state.get("current_prepared_artifact")
    if not isinstance(artifact, PreparedDatasetArtifact):
        records = repository.list_prepared_datasets(analysis_id)
        LOGGER.info("prepared_lookup analysis_id=%s persisted_count=%d session_artifact=false",
                    analysis_id, len(records))
        if not records:
            raise ValueError("Grain Discovery indisponível: análise não possui Prepared persistido.")
        selected = records[0]
        try:
            artifact = repository.get_prepared_artifact(selected.prepared_dataset_id)
        except Exception:
            LOGGER.exception("prepared_hydration_failed analysis_id=%s prepared_dataset_id=%s",
                             analysis_id, selected.prepared_dataset_id)
            raise
        if artifact is None:
            raise ValueError(
                "Grain Discovery indisponível: metadata persistida do Prepared mais recente é inválida."
            )
        state["current_prepared_dataset_id"] = artifact.prepared_dataset_id
        state["current_prepared_artifact"] = artifact
    else:
        LOGGER.info("prepared_lookup analysis_id=%s session_artifact=true prepared_dataset_id=%s",
                    analysis_id, artifact.prepared_dataset_id)
    if artifact.analysis_id != analysis_id:
        raise ValueError("Grain Discovery bloqueado: Prepared Dataset pertence a outra análise.")
    if artifact.source_document_id != source_document_id:
        raise ValueError("Grain Discovery bloqueado: Prepared Dataset pertence a outro documento.")
    if artifact.prepared_dataset_id != state.get("current_prepared_dataset_id"):
        raise ValueError("Grain Discovery bloqueado: identificador do Prepared Dataset diverge.")
    if artifact.status == PreparedDatasetStatus.BLOCKED:
        raise ValueError("Grain Discovery bloqueado: Quality Gate do Prepared Dataset está BLOCKED.")
    records = repository.list_prepared_datasets(analysis_id)
    record = next((item for item in records
                   if item.prepared_dataset_id == artifact.prepared_dataset_id), None)
    if (record is None or record.analysis_id != artifact.analysis_id
            or record.source_document_id != artifact.source_document_id
            or record.version != artifact.version
            or record.fingerprint != artifact.fingerprint):
        raise ValueError("Grain Discovery bloqueado: ownership/versão/fingerprint incompatível.")
    reader = PreparedDatasetArtifactReader(
        artifact, analysis_id=analysis_id, prepared_dataset_id=artifact.prepared_dataset_id,
        source_document_id=source_document_id, version=artifact.version,
        fingerprint=artifact.fingerprint,
    )
    path = reader.path
    LOGGER.info(
        "prepared_resolved analysis_id=%s prepared_dataset_id=%s version=%s path=%s "
        "exists=%s size=%s reader_created=true",
        analysis_id, artifact.prepared_dataset_id, artifact.version, path,
        path.is_file(), path.stat().st_size if path.is_file() else None,
    )
    return artifact


def validate_grain_prepared_artifact(
    state: MutableMapping[str, Any],
) -> PreparedDatasetArtifact:
    """Backward-compatible name for the official persistence-backed resolver."""
    return resolve_prepared_artifact_for_analysis(state)


def transition_prepared_to_grain(state: MutableMapping[str, Any]) -> AnalysisStage:
    """Synchronize persistence-derived lifecycle and session without creating artifacts."""
    artifact = validate_grain_prepared_artifact(state)
    repository: AnalysisRepository = state["repository"]
    result = repository.resume_analysis(artifact.analysis_id, artifact.source_document_id)
    if result.current_stage != AnalysisStage.GRAIN_DISCOVERY:
        raise ValueError(
            f"Transição PREPARED_DATASET → GRAIN_DISCOVERY recusada: persistência resolveu "
            f"{result.current_stage.value}."
        )
    state["analysis_id"] = result.analysis_id
    state["current_analysis_id"] = result.analysis_id
    state["selected_analysis_id"] = result.analysis_id
    state["source_document_id"] = result.source_document_id
    state["current_analysis_stage"] = result.current_stage
    state["last_successful_stage"] = result.last_successful_stage
    return result.current_stage


def save_semantic_answer(
    state: MutableMapping[str, Any],
    question_id: str,
    answer: str,
    custom_answer: str | None = None,
) -> None:
    """Persist an answer, update validation, and advance without losing prior answers."""
    initialize_session_state(state)
    report: SemanticValidationReport | None = state["current_validation_report"]
    if report is None:
        raise ValueError("Não há diagnóstico ativo para receber respostas.")
    repository: AnalysisRepository | None = state.get("repository")
    analysis_id = state.get("analysis_id")
    if repository is not None and analysis_id:
        record = repository.save_answer(analysis_id, question_id, answer, custom_answer)
        report = record.report
        state["analysis_status"] = record.status
    else:
        answer_question(report, question_id, answer, custom_answer)
    answers = dict(state["semantic_answers"])
    answers[question_id] = {"answer": answer, "custom_answer": custom_answer}
    state["semantic_answers"] = answers
    state["current_validation_report"] = report
    state["semantic_questions"] = report.questions
    next_pending = next(
        (index for index, question in enumerate(report.questions)
         if question.status == QuestionStatus.PENDING),
        None,
    )
    if next_pending is not None:
        state["current_question_index"] = next_pending


def set_current_question(state: MutableMapping[str, Any], index: int) -> None:
    initialize_session_state(state)
    questions = state["semantic_questions"]
    maximum = max(len(questions) - 1, 0)
    state["current_question_index"] = min(max(index, 0), maximum)


def reset_analysis_state(state: MutableMapping[str, Any]) -> None:
    """Clear analysis data and semantic widget values only on explicit reset."""
    for key in list(state.keys()):
        if key.startswith(("semantic_answer_", "semantic_custom_")):
            del state[key]
    for key in SESSION_DEFAULTS:
        if key in state:
            del state[key]
    initialize_session_state(state)
