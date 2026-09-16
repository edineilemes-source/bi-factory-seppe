"""Explicit logical-to-PostgreSQL type mapping policy."""

from dataclasses import dataclass

from core.star.models import LogicalDataType


@dataclass(frozen=True)
class NumericEvidence:
    observed_precision: int
    observed_scale: int


class PostgresTypeMapper:
    def __init__(self, *, unknown_policy: str = "TEXT_WITH_WARNING", numeric_precision_margin: int = 2):
        self.unknown_policy = unknown_policy
        self.numeric_precision_margin = max(0, numeric_precision_margin)

    def map(self, logical_type: LogicalDataType, *, numeric_evidence: NumericEvidence | None = None,
            timezone_explicit: bool = False, varchar_length: int | None = None) -> tuple[str, dict, str | None]:
        if logical_type == LogicalDataType.TEXT:
            return (f"VARCHAR({varchar_length})" if varchar_length else "TEXT", {}, None)
        if logical_type == LogicalDataType.INTEGER:
            return "BIGINT", {}, None
        if logical_type == LogicalDataType.DECIMAL:
            if numeric_evidence:
                selected = numeric_evidence.observed_precision + self.numeric_precision_margin
                metadata = {"observed_precision": numeric_evidence.observed_precision,
                            "observed_scale": numeric_evidence.observed_scale,
                            "selected_precision": selected,
                            "selected_scale": numeric_evidence.observed_scale,
                            "reason": "Observed precision plus configured conservative margin."}
                return f"NUMERIC({selected},{numeric_evidence.observed_scale})", metadata, None
            return "NUMERIC", {"reason": "No contract-level precision/scale evidence."}, None
        if logical_type == LogicalDataType.DATE:
            return "DATE", {}, None
        if logical_type == LogicalDataType.DATETIME:
            return ("TIMESTAMP WITH TIME ZONE" if timezone_explicit else "TIMESTAMP WITHOUT TIME ZONE"), {}, None
        if logical_type == LogicalDataType.BOOLEAN:
            return "BOOLEAN", {}, None
        if logical_type == LogicalDataType.UUID:
            return "UUID", {}, None
        if self.unknown_policy == "BLOCK":
            raise ValueError("Tipo lógico UNKNOWN bloqueado pela política configurada.")
        if self.unknown_policy != "TEXT_WITH_WARNING":
            raise ValueError(f"Política UNKNOWN inválida: {self.unknown_policy}")
        return "TEXT", {"unknown_type_fallback": True}, "Tipo UNKNOWN materializado como TEXT por política explícita."
