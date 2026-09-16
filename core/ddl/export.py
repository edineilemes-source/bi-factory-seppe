"""Byte-stable exports of persisted artifacts (no regeneration)."""

from core.ddl.models import PhysicalSchemaPlan, PostgreSQLDDLArtifact


def export_postgresql_sql(artifact: PostgreSQLDDLArtifact) -> bytes:
    return artifact.sql.encode("utf-8")


def export_physical_schema_plan_json(plan: PhysicalSchemaPlan) -> bytes:
    return plan.model_dump_json(indent=2).encode("utf-8")


def export_ddl_report_json(artifact: PostgreSQLDDLArtifact) -> bytes:
    return artifact.model_dump_json(indent=2).encode("utf-8")


def validate_ddl_artifact(artifact: PostgreSQLDDLArtifact) -> PostgreSQLDDLArtifact:
    validated = artifact.model_copy(deep=True)
    if not validated.validation_passed:
        raise ValueError("DDL estruturalmente inválido não pode ser validado pelo usuário.")
    validated.human_validated = True
    validated.ready_for_dimensional_etl = True
    return validated
