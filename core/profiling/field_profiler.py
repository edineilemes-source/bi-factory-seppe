"""Column-level profiling and generic semantic hypotheses."""

import re
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from statistics import mean
from typing import Any

from core.profiling.heuristics import (
    DEFAULT_PLACEHOLDER_VALUES,
    is_empty,
    is_placeholder,
    value_kind,
)
from core.profiling.identifiers import canonicalize_identifier
from core.profiling.models import (
    FieldProfile,
    SampleStatus,
    SemanticRole,
    StructuralWarning,
)


IDENTIFIER_TOKENS = {
    "id", "identificador", "chave", "numero", "no", "nr", "processo",
    "empenho", "liquidacao", "reserva", "contrato", "documento", "protocolo",
    "aux", "auxiliar", "subempenho",
}
CODE_TOKENS = {"codigo", "cod", "sigla", "tipo", "classe"}
TIME_TOKENS = {"ano", "mes", "dia", "trimestre", "bimestre", "semestre", "competencia"}
# Event/process words (for example "pagamento") are deliberately absent.  A
# name-based date hypothesis requires an explicit temporal marker.
DATE_TOKENS = {"data", "date", "dt"}
MEASURE_TOKENS = {
    "valor", "total", "quantidade", "qtd", "percentual", "porcentagem", "saldo",
    "custo", "preco", "taxa", "montante", "media", "pago", "liquidado",
    "estornado", "devolvido", "desconto", "acrescimo", "juros", "multa",
}
DESCRIPTION_TOKENS = {
    "descricao", "observacao", "historico", "objeto", "justificativa", "nome",
    "comentario", "detalhe",
}


def _tokens(name: str) -> set[str]:
    return set(filter(None, re.split(r"_+", name.casefold())))


def _serializable(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def _warning(code: str, message: str, original_name: str, sheet_name: str | None,
             level: str = "warning") -> StructuralWarning:
    return StructuralWarning(code=code, message=message, level=level,
                             sheet_name=sheet_name, field_name=original_name)


def profile_field(original_name: str, technical_name: str, values: Sequence[Any], *,
                  sheet_name: str | None = None,
                  placeholder_values: frozenset[str] = DEFAULT_PLACEHOLDER_VALUES) -> FieldProfile:
    """Create a deterministic technical profile and explainable semantic hypothesis."""
    total = len(values)
    physical_non_null = [value for value in values if not is_empty(value)]
    placeholders = [
        value for value in values if is_placeholder(value, placeholder_values)
    ]
    # Significant values drive type and semantic inference. Source values remain
    # untouched and placeholders are reported separately from physical nulls.
    non_null = [value for value in values if not is_empty(value) and not is_placeholder(
        value, placeholder_values
    )]
    non_null_count = len(non_null)
    null_count = total - len(physical_non_null)
    placeholder_count = len(placeholders)
    kinds = Counter(value_kind(value) for value in non_null)

    if not kinds:
        detected_type, recommended_type = "empty", "unknown"
    elif len(kinds) == 1:
        detected_type = next(iter(kinds))
        recommended_type = "decimal" if detected_type == "number" else detected_type
    elif set(kinds) <= {"integer", "number"}:
        detected_type, recommended_type = "number", "decimal"
    else:
        detected_type, recommended_type = "mixed", "text"

    distinct: dict[tuple[str, str], Any] = {}
    for value in non_null:
        distinct.setdefault((type(value).__name__, repr(value)), value)
    distinct_count = len(distinct)
    distinct_ratio = distinct_count / non_null_count if non_null_count else 0.0
    null_percentage = (null_count / total * 100) if total else 0.0
    sample_status = (SampleStatus.EMPTY_IN_SAMPLE if not non_null else
                     SampleStatus.PARTIALLY_POPULATED
                     if null_count or placeholder_count else SampleStatus.POPULATED)

    # Canonical text is analysis-only. Examples and source values stay untouched.
    texts = [canonicalize_identifier(value) for value in non_null]
    lengths = [len(value) for value in texts]
    avg_length = mean(lengths) if lengths else None
    stable_length_ratio = 0.0
    if lengths:
        stable_length_ratio = Counter(lengths).most_common(1)[0][1] / len(lengths)
    leading_zero = any(re.fullmatch(r"0\d+", value) for value in texts)
    numeric_values: list[float] = []
    if kinds and set(kinds) <= {"integer", "number"}:
        for value in non_null:
            try:
                numeric_values.append(float(str(value).replace(",", ".")))
            except ValueError:
                numeric_values = []
                break

    name_tokens = _tokens(technical_name)
    identifier_name = bool(name_tokens & IDENTIFIER_TOKENS)
    code_name = bool(name_tokens & CODE_TOKENS)
    time_name = bool(name_tokens & TIME_TOKENS)
    date_name = bool(name_tokens & DATE_TOKENS)
    measure_name = bool(name_tokens & MEASURE_TOKENS)
    description_name = bool(name_tokens & DESCRIPTION_TOKENS)
    long_numeric = bool(texts) and sum(v.isdigit() and len(v) >= 10 for v in texts) / len(texts) >= .8
    category_shape = non_null_count >= 2 and distinct_ratio <= .35 and distinct_count <= 100
    date_ratio = kinds.get("date", 0) / non_null_count if non_null_count else 0.0
    brazilian_date_ratio = (
        sum(
            isinstance(value, str)
            and bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", value.strip()))
            and value_kind(value) == "date"
            for value in non_null
        ) / non_null_count
        if non_null_count else 0.0
    )
    numeric_code_shape = (
        non_null_count >= 4
        and set(kinds) <= {"integer", "number"}
        and stable_length_ratio >= .8
        and distinct_count >= 2
        and distinct_ratio <= .5
        and not date_ratio
    )
    negative_ratio = (
        sum(value < 0 for value in numeric_values) / len(numeric_values)
        if numeric_values else 0.0
    )
    decimal_ratio = (
        sum(not value.is_integer() for value in numeric_values) / len(numeric_values)
        if numeric_values else 0.0
    )
    mixed_signs = bool(numeric_values) and min(numeric_values) < 0 < max(numeric_values)
    magnitude_variable = (
        bool(numeric_values)
        and len(set(numeric_values)) >= 3
        and max(abs(value) for value in numeric_values)
        >= 10 * max(min((abs(value) for value in numeric_values if value), default=1), 1)
    )
    quantitative_shape = bool(numeric_values) and (
        decimal_ratio >= .2 or negative_ratio >= .2 or mixed_signs or magnitude_variable
    )
    long_description_shape = (
        detected_type == "text"
        and (avg_length or 0) >= 30
        and distinct_ratio >= .6
    )

    role = SemanticRole.UNKNOWN
    confidence = 0.25 if non_null else 0.1
    evidence: list[str] = []

    # Evidence precedence: content > distribution > physical type > isolated name.
    if not non_null:
        evidence.append(
            "Inferência semântica adiada: não há valores significativos observáveis na amostra"
        )
    elif date_ratio >= .8:
        role, confidence = SemanticRole.DATE, min(.95, .65 + date_ratio * .3)
        if brazilian_date_ratio >= .8:
            evidence.append(
                f"{brazilian_date_ratio:.0%} dos valores observados são datas válidas "
                "no formato DD/MM/YYYY"
            )
        else:
            evidence.append(f"{date_ratio:.0%} dos valores da amostra têm tipo ou formato de data")
    elif detected_type == "boolean":
        role, confidence = SemanticRole.BOOLEAN, .98
        evidence.append("Valores observados são booleanos")
    elif long_description_shape:
        role, confidence = SemanticRole.DESCRIPTION, min(.92, .72 + distinct_ratio * .2)
        evidence.append(
            f"Conteúdo textual possui comprimento médio elevado ({avg_length:.1f}) "
            f"e alta cardinalidade ({distinct_ratio:.0%}), sugerindo descrição"
        )
        if date_name:
            evidence.append("Nome do campo sugere data, mas conteúdo observado contradiz essa hipótese")
    elif time_name:
        role, confidence = SemanticRole.TIME_COMPONENT, .92 if non_null else .35
        evidence.append("Nome sugere componente de tempo")
    elif measure_name and numeric_values:
        role, confidence = SemanticRole.MEASURE, .9
        evidence.append("Nome sugere medida e os valores observados são numéricos")
        if distinct_count > 1:
            evidence.append("Valores numéricos apresentam variabilidade")
        else:
            evidence.append(
                "A distribuição constante descreve a amostra atual sem redefinir o significado da medida"
            )
        if negative_ratio or decimal_ratio:
            evidence.append("Valores negativos ou decimais reforçam comportamento quantitativo")
    elif quantitative_shape and not leading_zero and not identifier_name:
        role, confidence = SemanticRole.MEASURE, .88 if (negative_ratio or decimal_ratio) else .85
        evidence.append("Distribuição, sinais ou magnitudes indicam valores quantitativos")
    elif identifier_name or long_numeric:
        role = SemanticRole.IDENTIFIER
        confidence = min(.95, .58 + (.17 if identifier_name else 0) +
                         (.12 if distinct_ratio >= .7 else 0) + (.08 if stable_length_ratio >= .8 else 0))
        if identifier_name:
            evidence.append("Nome sugere identificador")
        if distinct_ratio >= .7:
            evidence.append("Alta cardinalidade semântica compatível com referência")
        if long_numeric:
            evidence.append("Valores numéricos longos sugerem identificador")
        integer_like_numeric = (
            set(kinds) <= {"integer", "number"}
            and all(re.fullmatch(r"[-+]?\d+", value) for value in texts)
        )
        numeric_identifier_competition = (
            identifier_name
            and integer_like_numeric
            and stable_length_ratio >= .8
            and distinct_ratio >= .7
            and not leading_zero
        )
        if numeric_identifier_competition:
            confidence = min(confidence, .82)
            evidence.append(
                "Estrutura numérica também admite leitura quantitativa; hipótese requer confirmação"
            )
    elif code_name:
        role, confidence = SemanticRole.CODE, .82
        evidence.append("Nome sugere código")
        if stable_length_ratio >= .8:
            evidence.append(f"{stable_length_ratio:.0%} dos valores possuem comprimento predominante")
    elif numeric_code_shape:
        role, confidence = SemanticRole.CODE, .78
        evidence.append(
            "Valores numéricos possuem comprimento estável e baixa cardinalidade, sugerindo código"
        )
    elif description_name and (avg_length or 0) >= 12:
        role, confidence = SemanticRole.DESCRIPTION, min(.9, .65 + distinct_ratio * .2)
        evidence.extend(["Nome sugere conteúdo descritivo", "Texto possui comprimento médio elevado"])
    elif date_name:
        role, confidence = SemanticRole.DATE, .7 if non_null else .3
        evidence.append("Inferência de data baseada apenas no nome" if not non_null else "Nome sugere data")
    elif category_shape:
        role, confidence = SemanticRole.CATEGORY, .78
        evidence.append("Baixa razão entre valores distintos e preenchidos")
    elif detected_type == "text" and stable_length_ratio >= .8 and distinct_ratio < .7:
        role, confidence = SemanticRole.CODE, .6
        evidence.append("Texto repetido com comprimento relativamente estável")

    identifier_like = role in {SemanticRole.IDENTIFIER, SemanticRole.CODE}
    if leading_zero:
        recommended_type = "text"
        evidence.append("Valores apresentam zeros à esquerda")
    elif identifier_like and (detected_type in {"integer", "number"} or long_numeric):
        recommended_type = "text"
        evidence.append("Texto preserva a representação do identificador ou código")

    warnings: list[StructuralWarning] = []
    if sample_status == SampleStatus.EMPTY_IN_SAMPLE:
        warnings.append(_warning("empty_in_sample", "Campo sem valores na amostra analisada.",
                                 original_name, sheet_name, "info"))
        warnings.append(_warning(
            "semantic_inference_deferred_no_evidence",
            "Inferência semântica adiada até que uma carga apresente valores significativos.",
            original_name, sheet_name, "info",
        ))
    if null_percentage >= 50 and non_null:
        warnings.append(_warning("high_null_rate", f"Campo com {null_percentage:.2f}% de valores nulos na amostra.",
                                 original_name, sheet_name))
    if detected_type == "mixed":
        warnings.append(_warning("mixed_types", "Possível mistura de tipos detectada na amostra.",
                                 original_name, sheet_name))
    if leading_zero:
        warnings.append(_warning("leading_zero_risk", "Valores podem perder zeros à esquerda; texto é recomendado.",
                                 original_name, sheet_name))
    constant_value = _serializable(next(iter(distinct.values()))) if distinct_count == 1 else None
    if distinct_count == 1:
        warnings.append(_warning("constant_field", f"Valor constante identificado na amostra: {constant_value!s}.",
                                 original_name, sheet_name, "info"))
    elif non_null_count >= 10 and Counter(
        (type(value).__name__, repr(value)) for value in non_null
    ).most_common(1)[0][1] / non_null_count >= .99:
        warnings.append(_warning("near_constant_field", "Campo quase constante na amostra.",
                                 original_name, sheet_name, "info"))
    if role == SemanticRole.IDENTIFIER:
        warnings.append(_warning("possible_identifier", "Possível identificador; hipótese requer validação.",
                                 original_name, sheet_name, "info"))
    if role == SemanticRole.CODE:
        warnings.append(_warning("possible_code", "Possível código; hipótese requer validação.",
                                 original_name, sheet_name, "info"))
    if detected_type == "text" and distinct_ratio >= .9 and non_null_count >= 20:
        warnings.append(_warning("high_cardinality_text", "Texto com alta cardinalidade na amostra.",
                                 original_name, sheet_name, "info"))

    return FieldProfile(
        original_name=original_name, technical_name=technical_name,
        detected_type=detected_type, recommended_type=recommended_type,
        null_count=null_count, null_percentage=round(null_percentage, 2),
        placeholder_count=placeholder_count,
        placeholder_percentage=round((placeholder_count / total * 100) if total else 0.0, 2),
        distinct_count=distinct_count, non_null_count=non_null_count,
        distinct_ratio=round(distinct_ratio, 4), sample_status=sample_status,
        semantic_role_candidate=role, semantic_role_confidence=round(confidence, 2),
        semantic_evidence=evidence, examples=[_serializable(v) for v in list(distinct.values())[:5]],
        average_text_length=round(avg_length, 2) if avg_length is not None else None,
        min_text_length=min(lengths) if lengths else None,
        max_text_length=max(lengths) if lengths else None,
        numeric_min=min(numeric_values) if numeric_values else None,
        numeric_max=max(numeric_values) if numeric_values else None,
        numeric_mean=round(mean(numeric_values), 6) if numeric_values else None,
        negative_count=sum(v < 0 for v in numeric_values) if numeric_values else None,
        zero_count=sum(v == 0 for v in numeric_values) if numeric_values else None,
        constant_value=constant_value,
        is_candidate_key=bool(non_null) and null_count == 0 and distinct_ratio == 1.0,
        is_possible_date=role == SemanticRole.DATE,
        is_possible_measure=role == SemanticRole.MEASURE,
        is_possible_category=role == SemanticRole.CATEGORY,
        warnings=warnings,
    )
