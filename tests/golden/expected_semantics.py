"""Declarative expected outcomes; no production heuristic is duplicated here."""

EXPECTED_SEMANTICS = {
    "ano_referencia": {"role": "time_component", "decision": "auto_accept", "required_question": False},
    "data_lancamento": {"role": "date", "decision": "auto_accept", "required_question": False},
    "descricao_evento": {"role": "description", "decision": "auto_accept", "required_question": False},
    "codigo_evento": {"role": "code", "decision": "confirm", "required_question": False},
    "identificador_externo": {"role": "identifier", "decision": "auto_accept", "required_question": False, "recommended_type": "text", "leading_zero_risk": True},
    "valor_total": {"role": "measure", "decision": "auto_accept", "required_question": False},
    "valor_movimento": {"role": "measure", "decision": "auto_accept", "required_question": False},
    "valor_estorno": {"role": "measure", "decision": "auto_accept", "required_question": False},
    "classificacao_retencao_i": {"role": "unknown", "decision": "deferred_no_evidence", "required_question": False},
    "devolvido": {"role": "measure", "decision": "auto_accept", "required_question": False},
    "aux_sub_empenho": {"role": "identifier", "decision": "confirm", "required_question": False},
    "campo_ambiguo": {"role": "unknown", "decision": "ask", "required_question": True},
}

EXPECTED_REQUIRED_QUESTIONS = 1
EXPECTED_ASKED_FIELDS = {"campo_ambiguo"}
