"""Create reports and apply session-scoped user answers."""

from datetime import datetime, timezone

from core.profiling.models import SemanticRole, WorkbookProfile
from core.semantic.decision_engine import DecisionSettings, decide_field
from core.semantic.models import (
    DecisionLevel,
    QuestionStatus,
    SemanticValidation,
    SemanticValidationReport,
    ValidationStatus,
    ValidationSummary,
    SemanticKnowledgeRecord, SemanticReuseAction, SemanticReuseReport,
)
from core.semantic.knowledge import SemanticKnowledgeReusePolicy
from core.semantic.question_generator import OTHER_OPTION, ROLE_LABELS, UNKNOWN_OPTION, generate_question


LABEL_TO_ROLE = {label: role for role, label in ROLE_LABELS.items() if role != SemanticRole.UNKNOWN}


def _source_field_id(sheet_name: str, technical_name: str) -> str:
    return f"{sheet_name}::{technical_name}"


def _refresh_summary(report: SemanticValidationReport) -> None:
    statuses = [item.validation_status for item in report.validated_semantics]
    pending = {question.question_id: question for question in report.questions if question.status == QuestionStatus.PENDING}
    report.summary = ValidationSummary(
        fields_analyzed=len(report.validated_semantics),
        auto_accepted=statuses.count(ValidationStatus.AUTO_ACCEPTED),
        need_confirmation=sum(
            decision == DecisionLevel.CONFIRM
            for decision in report.decision_by_source_field.values()
        ),
        need_answer=sum(1 for q in pending.values() if report.decision_by_source_field[_source_field_id(q.sheet_name, q.technical_name)] in {DecisionLevel.ASK, DecisionLevel.RECONFIRM}),
        confirmed=statuses.count(ValidationStatus.USER_CONFIRMED),
        corrected=statuses.count(ValidationStatus.USER_CORRECTED),
        unresolved=sum(
            1 for item in report.validated_semantics
            if item.validation_status == ValidationStatus.UNRESOLVED
            and item.validated_at is not None
        ),
    )


def create_validation_report(profile: WorkbookProfile, settings: DecisionSettings | None = None,
                             prior_knowledge: list[SemanticKnowledgeRecord] | None = None) -> SemanticValidationReport:
    """Build a new report without mutating or replacing profiling observations."""
    settings = settings or DecisionSettings()
    questions = []
    validations = []
    decisions: dict[str, DecisionLevel] = {}
    reuse_decisions = []
    policy = SemanticKnowledgeReusePolicy(settings)
    for sheet in profile.sheets:
        for field in sheet.fields:
            source_id = _source_field_id(sheet.name, field.technical_name)
            reuse, decision = policy.decide(field, source_id, prior_knowledge or [])
            reuse_decisions.append(reuse)
            decisions[source_id] = decision.level
            question = generate_question(sheet.name, field, decision, reuse.previous_validated_role)
            if question:
                question.previous_validated_role = reuse.previous_validated_role
                questions.append(question)
            accepted = reuse.action in {SemanticReuseAction.AUTO_ACCEPT, SemanticReuseAction.REUSE}
            reused = reuse.action == SemanticReuseAction.REUSE
            validations.append(SemanticValidation(
                sheet_name=sheet.name,
                field_name=field.original_name,
                technical_name=field.technical_name,
                source_field_id=source_id,
                original_hypothesis=field.semantic_role_candidate,
                original_confidence=field.semantic_role_confidence,
                validated_role=reuse.effective_role if accepted else None,
                validation_status=ValidationStatus.AUTO_ACCEPTED if accepted else ValidationStatus.UNRESOLVED,
                validated_at=datetime.now(timezone.utc) if accepted else None,
                knowledge_reused=reused, previous_validated_role=reuse.previous_validated_role,
                semantic_knowledge_id=reuse.semantic_knowledge_id,
            ))
    counts={action:sum(x.action==action for x in reuse_decisions) for action in SemanticReuseAction}
    reuse_report=SemanticReuseReport(total_fields=len(reuse_decisions),reused_count=counts[SemanticReuseAction.REUSE],
        auto_accepted_count=counts[SemanticReuseAction.AUTO_ACCEPT],reconfirm_count=counts[SemanticReuseAction.RECONFIRM],
        ask_count=counts[SemanticReuseAction.ASK],deferred_count=counts[SemanticReuseAction.DEFER],decisions=reuse_decisions)
    report = SemanticValidationReport(
        observed_profile=profile.model_copy(deep=True), questions=questions,
        validated_semantics=validations, decision_by_source_field=decisions,
        summary=ValidationSummary(fields_analyzed=0, auto_accepted=0, need_confirmation=0, need_answer=0, confirmed=0, corrected=0, unresolved=0),
        reuse_report=reuse_report,
    )
    _refresh_summary(report)
    return report


def answer_question(report: SemanticValidationReport, question_id: str, answer: str, custom_answer: str | None = None) -> SemanticValidation:
    question = next((q for q in report.questions if q.question_id == question_id), None)
    if question is None:
        raise ValueError(f"Pergunta não encontrada: {question_id}")
    validation = next(v for v in report.validated_semantics if v.source_field_id == _source_field_id(question.sheet_name, question.technical_name))
    now = datetime.now(timezone.utc)
    if answer == UNKNOWN_OPTION:
        validation.user_answer = answer
        validation.validated_role = None
        validation.validation_status = ValidationStatus.UNRESOLVED
        validation.validated_at = now
        question.status = QuestionStatus.SKIPPED
    else:
        if answer == OTHER_OPTION:
            if not custom_answer or not custom_answer.strip():
                raise ValueError("Explique o significado do campo ao escolher Outro.")
            resolved_answer = custom_answer.strip()
            role = None
        else:
            resolved_answer = answer
            role = LABEL_TO_ROLE.get(answer)
        validation.user_answer = resolved_answer
        validation.validated_role = role
        validation.validation_status = (
            ValidationStatus.USER_CONFIRMED
            if role == validation.original_hypothesis
            else ValidationStatus.USER_CORRECTED
        )
        validation.validated_at = now
        question.status = QuestionStatus.ANSWERED
    _refresh_summary(report)
    return validation
