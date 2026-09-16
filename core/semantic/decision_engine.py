"""Configurable decisions and generic conflicts for semantic hypotheses."""

from dataclasses import dataclass

from core.profiling.models import FieldProfile, SemanticRole
from core.semantic.models import DecisionLevel, EvidenceClass, QuestionPriority, SemanticConflict


DATE_NAME_TOKENS = frozenset({"data", "date", "dt"})
IDENTIFIER_NAME_TOKENS = frozenset({
    "id", "identificador", "chave", "numero", "nr", "processo", "empenho",
    "liquidacao", "reserva", "contrato", "documento", "protocolo", "aux",
    "auxiliar", "subempenho",
})
MEASURE_NAME_TOKENS = frozenset({
    "valor", "total", "quantidade", "qtd", "percentual", "saldo", "preco",
    "pago", "liquidado", "estornado", "devolvido", "desconto", "acrescimo",
    "juros", "multa",
})


@dataclass(frozen=True)
class DecisionSettings:
    """All tunable decision limits live here."""

    auto_accept_confidence: float = 0.85
    confirm_confidence: float = 0.60
    low_cardinality_ratio: float = 0.35
    high_cardinality_ratio: float = 0.70
    long_numeric_length: int = 10


DEFAULT_DECISION_SETTINGS = DecisionSettings()


@dataclass(frozen=True)
class SemanticDecision:
    level: DecisionLevel
    conflicts: tuple[SemanticConflict, ...]
    reason: str


def _name_tokens(field: FieldProfile) -> set[str]:
    return set(field.technical_name.casefold().split("_"))


def detect_conflicts(
    field: FieldProfile, settings: DecisionSettings = DEFAULT_DECISION_SETTINGS
) -> list[SemanticConflict]:
    """Compare name, content, distribution, physical type and inferred role."""
    tokens = _name_tokens(field)
    conflicts: list[SemanticConflict] = []

    def add(code: str, message: str, sources: list[str],
            severity: QuestionPriority = QuestionPriority.HIGH,
            evidence_class: EvidenceClass = EvidenceClass.STRUCTURAL_EVIDENCE) -> None:
        conflicts.append(SemanticConflict(
            code=code, message=message, sources=sources, severity=severity,
            evidence_class=evidence_class,
        ))

    name_role_signals = {
        "data": bool(tokens & DATE_NAME_TOKENS),
        "identificador": bool(tokens & IDENTIFIER_NAME_TOKENS),
        "quantidade ou valor": bool(tokens & MEASURE_NAME_TOKENS),
    }
    signaled_roles = [label for label, present in name_role_signals.items() if present]
    strong_content_role = (
        field.semantic_role_confidence >= settings.auto_accept_confidence
        and ((field.semantic_role_candidate == SemanticRole.DATE and field.detected_type == "date")
             or field.semantic_role_candidate in {SemanticRole.TIME_COMPONENT, SemanticRole.MEASURE, SemanticRole.BOOLEAN})
    )
    if len(signaled_roles) > 1 and not strong_content_role:
        add(
            "competing_name_roles",
            "Partes do nome apontam para significados diferentes: "
            + ", ".join(signaled_roles)
            + ".",
            ["field_name", "semantic_role"], evidence_class=EvidenceClass.LEXICAL_HINT,
        )

    content_supports_date = field.detected_type == "date" or any(
        "valores" in item.casefold() and "data" in item.casefold()
        for item in field.semantic_evidence
    )
    if tokens & DATE_NAME_TOKENS and field.non_null_count and not content_supports_date:
        add("date_name_non_date_content", "O nome sugere uma data, mas os valores observados não têm formato de data.", ["field_name", "content", "physical_type"], evidence_class=EvidenceClass.CONTENT_EVIDENCE)
    if (tokens & IDENTIFIER_NAME_TOKENS and field.non_null_count >= 3
            and field.distinct_ratio <= settings.low_cardinality_ratio and not strong_content_role):
        add("identifier_name_category_distribution", "O nome sugere um identificador, mas poucos valores se repetem como uma categoria.", ["field_name", "distribution"])
    if field.detected_type in {"integer", "number"} and field.non_null_count >= 3 and field.distinct_ratio <= settings.low_cardinality_ratio and field.semantic_role_candidate in {SemanticRole.MEASURE, SemanticRole.CATEGORY, SemanticRole.UNKNOWN}:
        severity = (
            QuestionPriority.LOW
            if field.semantic_role_candidate == SemanticRole.MEASURE
            and field.semantic_role_confidence >= settings.auto_accept_confidence
            else QuestionPriority.HIGH
        )
        add("numeric_low_cardinality", "O campo é numérico e possui baixa variedade; esta é uma observação de distribuição, não evidência suficiente de código.", ["physical_type", "distribution", "semantic_role"], severity)
    has_leading_zero = any(isinstance(value, str) and len(value) > 1 and value.startswith("0") and value.isdigit() for value in field.examples)
    if has_leading_zero:
        add("numeric_text_leading_zero", "Os valores parecem números, mas possuem zeros à esquerda que precisam ser preservados.", ["content", "physical_type", "recommended_type"], QuestionPriority.LOW)
    if field.semantic_role_candidate == SemanticRole.CATEGORY and tokens & MEASURE_NAME_TOKENS:
        add("category_measure_name", "O nome sugere uma quantidade ou valor, mas a distribuição se comporta como categoria.", ["field_name", "distribution", "semantic_role"])
    return conflicts


def decide_field(
    field: FieldProfile, settings: DecisionSettings = DEFAULT_DECISION_SETTINGS
) -> SemanticDecision:
    if field.non_null_count == 0:
        return SemanticDecision(
            DecisionLevel.DEFERRED_NO_EVIDENCE,
            (),
            "Inferência semântica adiada por ausência de valores significativos observáveis.",
        )
    conflicts = tuple(detect_conflicts(field, settings))
    critical_conflicts = tuple(
        conflict for conflict in conflicts if conflict.severity == QuestionPriority.HIGH
    )
    if critical_conflicts:
        return SemanticDecision(DecisionLevel.ASK, conflicts, "Há conflito relevante entre as evidências observadas.")
    if field.semantic_role_candidate == SemanticRole.UNKNOWN:
        return SemanticDecision(DecisionLevel.ASK, conflicts, "Não há evidência suficiente para atribuir um significado ao campo.")
    if field.semantic_role_confidence >= settings.auto_accept_confidence:
        return SemanticDecision(DecisionLevel.AUTO_ACCEPT, conflicts, "Hipótese apoiada por evidência forte e sem conflito relevante.")
    if field.semantic_role_confidence >= settings.confirm_confidence:
        return SemanticDecision(DecisionLevel.CONFIRM, conflicts, "A hipótese é razoável, mas merece confirmação de quem conhece os dados.")
    return SemanticDecision(DecisionLevel.ASK, conflicts, "A confiança é insuficiente para validar a hipótese automaticamente.")
