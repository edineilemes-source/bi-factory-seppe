"""Central quality-gate policy: anomaly is not evidence of defect."""

from core.quality.models import (
    BlockingScope, QualityDefectStatus, QualityGateDecision, QualityGateStatus,
    QualityIssue, QualitySeverity,
)


def is_blocking_issue(issue: QualityIssue,
                      scope: BlockingScope = BlockingScope.PREPARED_DATASET) -> bool:
    if issue.quality_defect_status != QualityDefectStatus.CONFIRMED_DEFECT:
        return False
    if not issue.blocking_eligible:
        return False
    return (BlockingScope.GLOBAL in issue.blocking_scope
            or scope in issue.blocking_scope)


def decide_quality_gate(issues: list[QualityIssue],
                        scope: BlockingScope = BlockingScope.PREPARED_DATASET,
                        ) -> QualityGateDecision:
    blocking = sum(is_blocking_issue(issue, scope) for issue in issues)
    unresolved = sum(issue.quality_defect_status == QualityDefectStatus.NEEDS_BUSINESS_RULE
                     for issue in issues)
    warnings = sum(issue.severity in {QualitySeverity.WARNING, QualitySeverity.ERROR,
                                     QualitySeverity.CRITICAL} and not is_blocking_issue(issue, scope)
                   for issue in issues)
    non_blocking = len(issues) - blocking
    if blocking:
        status = QualityGateStatus.BLOCKED
        reason = f"{blocking} defeito(s) confirmado(s) bloqueiam {scope.value}."
    elif issues:
        status = QualityGateStatus.READY_WITH_WARNINGS
        reason = "Anomalias observadas exigem inspeção, mas não há defeito bloqueante confirmado."
    else:
        status = QualityGateStatus.READY
        reason = "Nenhum defeito ou anomalia foi encontrado."
    return QualityGateDecision(
        status=status, blocking_issues=blocking, non_blocking_issues=non_blocking,
        unresolved_business_rules=unresolved, warnings=warnings, reason=reason,
    )
