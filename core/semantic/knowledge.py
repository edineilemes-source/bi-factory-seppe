"""Central semantic knowledge compatibility and reuse policy."""
import hashlib
import json
from core.profiling.models import FieldProfile, SemanticRole
from core.semantic.decision_engine import DecisionSettings, SemanticDecision, decide_field
from core.semantic.models import (DecisionLevel, KnowledgeValidationSource,
    SemanticCompatibilityResult, SemanticKnowledgeRecord, SemanticReuseAction,
    SemanticReuseDecision)


SOURCE_PRECEDENCE={
    KnowledgeValidationSource.USER_CORRECTED:4,
    KnowledgeValidationSource.USER_CONFIRMED:3,
    KnowledgeValidationSource.AUTO_ACCEPTED:2,
    KnowledgeValidationSource.SYSTEM_INFERRED:1,
    KnowledgeValidationSource.IMPORTED:1,
}


def semantic_fingerprint(field: FieldProfile) -> str:
    payload={"name":field.technical_name,"role":field.semantic_role_candidate.value,
        "detected_type":field.detected_type,"recommended_type":field.recommended_type,
        "confidence":field.semantic_role_confidence,"non_null":field.non_null_count > 0,
        "evidence":field.semantic_evidence}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _type_supports(role: SemanticRole, detected: str) -> bool:
    if role==SemanticRole.DATE: return detected=="date"
    if role==SemanticRole.TIME_COMPONENT: return detected in {"integer","number","text"}
    if role==SemanticRole.BOOLEAN: return detected=="boolean"
    if role==SemanticRole.MEASURE: return detected in {"integer","number"}
    if role in {SemanticRole.IDENTIFIER,SemanticRole.CODE}: return detected in {"integer","number","text"}
    if role in {SemanticRole.DESCRIPTION,SemanticRole.CATEGORY}: return detected in {"text","mixed"}
    return False


class SemanticKnowledgeReusePolicy:
    def __init__(self, settings: DecisionSettings | None=None): self.settings=settings or DecisionSettings()

    def best_knowledge(self, field: FieldProfile, source_field_id: str,
                       records: list[SemanticKnowledgeRecord]) -> SemanticKnowledgeRecord | None:
        candidates=[x for x in records if x.source_field_id==source_field_id]
        if not candidates:
            candidates=[x for x in records if x.normalized_field_name==field.technical_name]
        return max(candidates,key=lambda x:(SOURCE_PRECEDENCE[x.validation_source],x.version,x.updated_at),default=None)

    def compatibility(self, field: FieldProfile, knowledge: SemanticKnowledgeRecord) -> SemanticCompatibilityResult:
        support=[]; conflict=[]; score=0.0
        if field.technical_name==knowledge.normalized_field_name: support.append("Stable normalized field identity"); score+=.35
        if field.semantic_role_candidate==knowledge.validated_semantic_role: support.append("Current inference agrees with validated role"); score+=.4
        elif field.semantic_role_confidence>=self.settings.auto_accept_confidence:
            conflict.append(f"Strong current inference is {field.semantic_role_candidate.value}")
        if _type_supports(knowledge.validated_semantic_role,field.detected_type): support.append("Current content type supports validated role"); score+=.25
        elif field.non_null_count: conflict.append(f"Detected type {field.detected_type} contradicts validated role")
        compatible=score>=.6 and not conflict
        return SemanticCompatibilityResult(compatible=compatible,compatibility_score=min(score,1),
            supporting_evidence=support,conflicting_evidence=conflict,
            reason="Validated knowledge remains compatible with current observations." if compatible else
                   "Previously validated knowledge materially differs from current observations.",
            action=SemanticReuseAction.REUSE if compatible else SemanticReuseAction.RECONFIRM)

    def decide(self, field: FieldProfile, source_field_id: str,
               records: list[SemanticKnowledgeRecord]) -> tuple[SemanticReuseDecision,SemanticDecision]:
        observed=decide_field(field,self.settings); prior=self.best_knowledge(field,source_field_id,records)
        # Absence of current evidence must remain silent even when historical
        # knowledge exists; it is preserved for a future populated load.
        if observed.level==DecisionLevel.DEFERRED_NO_EVIDENCE:
            compatibility=SemanticCompatibilityResult(compatible=False,compatibility_score=0,
                reason="Current load has no significant values; historical knowledge was preserved without reconfirmation.",
                action=SemanticReuseAction.DEFER)
            return SemanticReuseDecision(source_field_id=source_field_id,normalized_field_name=field.technical_name,
                action=SemanticReuseAction.DEFER,current_role=field.semantic_role_candidate,
                previous_validated_role=prior.validated_semantic_role if prior else None,
                semantic_knowledge_id=prior.semantic_knowledge_id if prior else None,
                compatibility=compatibility),observed
        if prior:
            compatibility=self.compatibility(field,prior)
            action=compatibility.action
            level=DecisionLevel.REUSE if action==SemanticReuseAction.REUSE else DecisionLevel.RECONFIRM
            decision=SemanticDecision(level,observed.conflicts,
                compatibility.reason if action==SemanticReuseAction.REUSE else
                f"Este campo havia sido validado anteriormente como {prior.validated_semantic_role.value}, mas a nova análise encontrou {field.semantic_role_candidate.value}.")
            return SemanticReuseDecision(source_field_id=source_field_id,normalized_field_name=field.technical_name,
                action=action,current_role=field.semantic_role_candidate,
                effective_role=prior.validated_semantic_role if compatibility.compatible else None,
                previous_validated_role=prior.validated_semantic_role,semantic_knowledge_id=prior.semantic_knowledge_id,
                compatibility=compatibility),decision
        action={DecisionLevel.AUTO_ACCEPT:SemanticReuseAction.AUTO_ACCEPT,
            DecisionLevel.DEFERRED_NO_EVIDENCE:SemanticReuseAction.DEFER,
            DecisionLevel.ASK:SemanticReuseAction.ASK,
            DecisionLevel.CONFIRM:SemanticReuseAction.OPTIONAL_CONFIRM}[observed.level]
        compatibility=SemanticCompatibilityResult(compatible=False,compatibility_score=0,
            reason="No reusable validated knowledge exists.",action=action)
        return SemanticReuseDecision(source_field_id=source_field_id,normalized_field_name=field.technical_name,
            action=action,current_role=field.semantic_role_candidate,
            effective_role=field.semantic_role_candidate if action==SemanticReuseAction.AUTO_ACCEPT else None,
            compatibility=compatibility),observed
