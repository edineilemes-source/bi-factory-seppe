"""Business-language questions derived from semantic decisions."""

from uuid import NAMESPACE_URL, uuid5

from core.profiling.models import FieldProfile, SemanticRole
from core.semantic.decision_engine import SemanticDecision
from core.semantic.models import DecisionLevel, QuestionPriority, QuestionType, SemanticQuestion, SemanticReuseAction


ROLE_LABELS = {
    SemanticRole.IDENTIFIER: "Identificador de uma entidade ou registro",
    SemanticRole.CODE: "Código ou classificação",
    SemanticRole.MEASURE: "Quantidade, valor ou percentual",
    SemanticRole.DATE: "Data de um acontecimento",
    SemanticRole.TIME_COMPONENT: "Parte de um período, como ano ou mês",
    SemanticRole.CATEGORY: "Categoria ou situação",
    SemanticRole.DESCRIPTION: "Nome, descrição ou observação",
    SemanticRole.BOOLEAN: "Resposta do tipo sim ou não",
    SemanticRole.UNKNOWN: "Outro significado",
}
UNKNOWN_OPTION = "Não sei / preciso verificar"
OTHER_OPTION = "Outro"


def _question_type(role: SemanticRole, decision: SemanticDecision) -> QuestionType:
    if any(conflict.code == "date_name_non_date_content" for conflict in decision.conflicts):
        return QuestionType.TYPE_CONFIRMATION
    return {
        SemanticRole.IDENTIFIER: QuestionType.IDENTIFIER_MEANING,
        SemanticRole.CODE: QuestionType.CODE_MEANING,
        SemanticRole.MEASURE: QuestionType.MEASURE_MEANING,
        SemanticRole.DATE: QuestionType.DATE_MEANING,
        SemanticRole.UNKNOWN: QuestionType.FIELD_PURPOSE,
    }.get(role, QuestionType.SEMANTIC_ROLE)


def generate_question(sheet_name: str, field: FieldProfile, decision: SemanticDecision,
                      previous_validated_role: SemanticRole | None = None) -> SemanticQuestion | None:
    # CONFIRM remains visible in the report as an optional review decision; only
    # genuine ASK cases enter the mandatory questionnaire in this sprint.
    if decision.level not in {DecisionLevel.ASK, DecisionLevel.RECONFIRM}:
        return None
    role_label = ROLE_LABELS[field.semantic_role_candidate]
    conflict_text = " ".join(conflict.message for conflict in decision.conflicts)
    context = (f"Este campo foi anteriormente validado como {ROLE_LABELS[previous_validated_role]}, "
               "mas os dados atuais apresentam características diferentes. "
               "Confirme se o significado continua o mesmo."
               if decision.level == DecisionLevel.RECONFIRM and previous_validated_role else
               decision.reason if decision.level == DecisionLevel.RECONFIRM else conflict_text or decision.reason)
    suggested = [] if field.semantic_role_candidate == SemanticRole.UNKNOWN else [role_label]
    options = list(dict.fromkeys(suggested + [
        "Identificador de uma entidade ou registro",
        "Código ou classificação",
        "Quantidade, valor ou percentual",
        "Categoria ou situação",
        "Data de um acontecimento",
        OTHER_OPTION,
        UNKNOWN_OPTION,
    ]))
    question_id = str(uuid5(NAMESPACE_URL, f"{sheet_name}:{field.technical_name}"))
    return SemanticQuestion(
        question_id=question_id,
        sheet_name=sheet_name,
        field_name=field.original_name,
        technical_name=field.technical_name,
        question_type=_question_type(field.semantic_role_candidate, decision),
        title=f"Confirme o significado de “{field.original_name}”",
        question_text=f"{context} O que este campo representa?",
        reason=decision.reason,
        current_hypothesis=field.semantic_role_candidate,
        confidence=field.semantic_role_confidence,
        options=options,
        priority=QuestionPriority.HIGH if decision.level == DecisionLevel.ASK else QuestionPriority.MEDIUM,
        evidence=field.semantic_evidence,
        conflicts=list(decision.conflicts),
        examples=field.examples[:5],
        detected_type=field.detected_type,
        recommended_type=field.recommended_type,
        reuse_action=SemanticReuseAction.RECONFIRM if decision.level == DecisionLevel.RECONFIRM else SemanticReuseAction.ASK,
    )
