"""JSON and dependency-free Mermaid exports for logical contracts."""

import json

from core.star.models import StarSchemaContractReport, ValidatedStarSchemaContract


def export_star_schema_contract_json(report: StarSchemaContractReport) -> bytes:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False,
                      indent=2, sort_keys=True).encode("utf-8")


def export_validated_star_schema_json(validation: ValidatedStarSchemaContract) -> bytes:
    return json.dumps(validation.model_dump(mode="json"), ensure_ascii=False,
                      indent=2, sort_keys=True).encode("utf-8")


def star_schema_mermaid(report: StarSchemaContractReport) -> str:
    lines = ["flowchart LR"]
    contract = report.contract
    names = {item.fact_id: item.logical_name for item in contract.fact_tables}
    names.update({item.dimension_id: item.logical_name for item in contract.dimension_tables})
    for relationship in contract.relationships:
        label = relationship.role_name or relationship.cardinality.value
        lines.append(f"    {names[relationship.source_table]} -->|{label}| {names[relationship.target_table]}")
    return "\n".join(lines)
