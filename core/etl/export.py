"""Exports persisted plan content without replanning."""

import csv
import io
import json

from core.etl.models import DimensionalETLPlan


def export_etl_plan_json(plan: DimensionalETLPlan) -> bytes:
    return plan.model_dump_json(indent=2).encode("utf-8")


def export_execution_order_json(plan: DimensionalETLPlan) -> bytes:
    return json.dumps({"etl_plan_id": plan.etl_plan_id, "execution_order": plan.execution_order,
                       "dependencies": plan.dependencies}, ensure_ascii=False,
                      sort_keys=True, indent=2).encode("utf-8")


def export_etl_mapping_csv(plan: DimensionalETLPlan) -> bytes:
    output = io.StringIO(newline="")
    fields = ["source_field", "effective_semantic_role", "source_type", "target_table",
              "target_column", "target_type", "mapping_role", "transformation",
              "lookup_dimension", "nullable", "required", "warning"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in plan.field_mappings:
        writer.writerow({"source_field": item.source_field_id or "", "effective_semantic_role": item.effective_semantic_role or "",
                         "source_type": item.source_type or "", "target_table": item.target_table or "",
                         "target_column": item.target_column or "", "target_type": item.target_type or "",
                         "mapping_role": item.mapping_role.value, "transformation": item.transformation,
                         "lookup_dimension": item.lookup_dimension or "", "nullable": item.nullable,
                         "required": item.required_for_load, "warning": " | ".join(item.warnings)})
    return output.getvalue().encode("utf-8")
