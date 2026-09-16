from copy import deepcopy

import pytest

from core.ddl.generator import generate_postgresql_ddl
from core.ddl.models import PhysicalSchemaStatus
from core.etl.export import export_etl_mapping_csv, export_etl_plan_json
from core.etl.models import ETLPlanStatus, MappingRole, MissingLookupAction, ReconciliationCapability
from core.etl.planner import build_dimensional_etl_plan, topological_execution_order
from core.profiling.models import SemanticRole
from core.star.models import Nullability, SCDType
from tests.golden_ddl.test_golden_ddl import generated


def etl(name="etl", *, scd=SCDType.TYPE_1, columns=None, data=None, grain=None, transform=None):
    dataset, ids, validation, _ = generated(name, columns=columns, data=data, grain=grain)
    for dimension in validation.contract.dimension_tables:
        dimension.scd_strategy.strategy = scd
        dimension.scd_strategy.requires_validation = False
        if scd == SCDType.TYPE_2:
            dimension.scd_strategy.effective_from_field_plan = "effective_from"
            dimension.scd_strategy.effective_to_field_plan = "effective_to"
            dimension.scd_strategy.current_flag_plan = "is_current"
            dimension.scd_strategy.tracked_attributes = dimension.attributes
    if transform: transform(dataset, validation)
    physical, artifact = generate_postgresql_ddl(validation)
    physical.lifecycle_status = PhysicalSchemaStatus.EFFECTIVE
    artifact.human_validated = artifact.ready_for_dimensional_etl = True
    plan = build_dimensional_etl_plan(dataset, validation.contract, physical, artifact)
    return dataset, validation, physical, artifact, plan


def test_a_basic_dimension_and_fact():
    *_, plan = etl()
    assert plan.status == ETLPlanStatus.READY_FOR_DRY_RUN
    assert plan.execution_order.index(plan.dimension_load_plans[0].target_table) < plan.execution_order.index(plan.fact_load_plans[0].target_table)
    assert plan.fact_load_plans[0].measure_mappings


def test_b_business_key_lookup():
    *_, plan = etl("lookup")
    assert any(m.mapping_role == MappingRole.SURROGATE_KEY_LOOKUP for m in plan.field_mappings)


def test_c_unknown_member_for_optional_lookup():
    *_, plan = etl("unknown")
    assert plan.unknown_member_plans[0].enabled
    assert plan.surrogate_key_resolution_plans[0].missing_action == MissingLookupAction.USE_UNKNOWN_MEMBER


def test_d_required_dimension_failure_is_explicit():
    def required(_, validation):
        for fact in validation.contract.fact_tables:
            for fk in fact.foreign_keys: fk.optionality = Nullability.NOT_NULLABLE
    *_, plan = etl("required", transform=required)
    assert plan.surrogate_key_resolution_plans[0].missing_action == MissingLookupAction.REJECT_ROW
    assert "REJECT_REQUIRED_FAILURE" in plan.fact_load_plans[0].rejection_policy


def test_e_scd_type_1():
    *_, plan = etl("scd1")
    assert plan.scd_plans and plan.scd_plans[0].update_policy == "UPDATE_CHANGED_ATTRIBUTES"


def test_f_scd_type_2():
    *_, plan = etl("scd2plan", scd=SCDType.TYPE_2)
    scd = plan.scd_plans[0]
    assert scd.close_current_row_action and scd.insert_new_version_action and scd.change_detection_fields is not None


def test_g_role_playing_date():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("order_date", SemanticRole.DATE),
            ("ship_date", SemanticRole.DATE), ("payment_date", SemanticRole.DATE)]
    *_, plan = etl("etl_roles", columns=cols,
        data=[["E1", "2026-01-01", "2026-01-02", "2026-01-03"]], grain=["event_id"])
    assert len(plan.dimension_load_plans) == 1 and len(plan.surrogate_key_resolution_plans) == 3
    assert len({x.dimension_id for x in plan.surrogate_key_resolution_plans}) == 1


def test_h_factless_fact():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER)]
    *_, plan = etl("etl_factless", columns=cols, data=[["E1", "C1"]], grain=["event_id"])
    assert plan.fact_load_plans and not plan.fact_load_plans[0].measure_mappings


def test_i_multi_fact():
    from core.dimensional.validation import validate_dimensional_discovery
    from core.star.engine import build_star_schema_contract
    from core.star.validation import validate_star_schema_contract
    from tests.golden_dimensional.test_golden_dimensional import proposal
    dataset, _, grain_def, _, report = proposal("etl_multi_real", [
        ("event_a", SemanticRole.IDENTIFIER), ("event_b", SemanticRole.IDENTIFIER),
        ("customer_id", SemanticRole.IDENTIFIER), ("amount", SemanticRole.MEASURE)],
        [["A1", None, "C1", 2], [None, "B1", "C1", 3]], ["event_a", "event_b"],
        multi_groups=[["event_a"], ["event_b"]])
    dimensional = validate_dimensional_discovery(report, accepted_unresolved_fields=report.unresolved_fields)
    validation = validate_star_schema_contract(build_star_schema_contract(dataset, grain_def, dimensional))
    for d in validation.contract.dimension_tables: d.scd_strategy.strategy=SCDType.TYPE_1; d.scd_strategy.requires_validation=False
    physical, artifact = generate_postgresql_ddl(validation); physical.lifecycle_status=PhysicalSchemaStatus.EFFECTIVE; artifact.human_validated=True
    plan = build_dimensional_etl_plan(dataset, validation.contract, physical, artifact)
    assert len(plan.fact_load_plans) == 2 and len(plan.dimension_load_plans) == 1


def test_j_bridge_order():
    def bridge(_, validation):
        for item in validation.contract.bridge_candidates: item.requires_validation = False
    cols = [("event_id", SemanticRole.IDENTIFIER), ("person_id", SemanticRole.IDENTIFIER), ("group_id", SemanticRole.IDENTIFIER)]
    *_, plan = etl("etl_bridge", columns=cols, transform=bridge,
        data=[["E1", "P1", "G1"], ["E2", "P1", "G2"], ["E3", "P2", "G1"], ["E4", "P2", "G2"]], grain=["event_id"])
    assert len(plan.bridge_load_plans) == 1 and plan.bridge_load_plans[0].business_mappings
    bridge_plan = plan.bridge_load_plans[0]
    assert all(plan.execution_order.index(dep) < plan.execution_order.index(bridge_plan.bridge_table)
               for dep in plan.dependencies[bridge_plan.bridge_table])


def test_k_reconciliation_additive():
    *_, plan = etl("reconcile")
    assert plan.reconciliation_plan.measure_reconciliations


def test_l_non_additive_not_summed():
    def nonadd(_, validation):
        for fact in validation.contract.fact_tables:
            for measure in fact.measures: measure.additivity = __import__("core.grain.models", fromlist=["MeasureAggregationHint"]).MeasureAggregationHint.NON_ADDITIVE
    *_, plan = etl("nonadd", transform=nonadd)
    assert plan.reconciliation_plan.measure_reconciliations[0].status == ReconciliationCapability.NOT_RECONCILABLE


def test_m_identifier_leading_zero_not_cast():
    *_, plan = etl("leading", data=[["E1", "00123", 10]])
    mapping = next(m for m in plan.field_mappings if m.prepared_field_name == "customer_id")
    assert mapping.target_type == "TEXT" and "CAST" not in mapping.transformation


def test_n_precision_safety_blocks():
    dataset, validation, physical, artifact, _ = etl("precision", data=[["E1", "C1", 10.25]])
    measure = next(c for t in physical.tables for c in t.columns if c.role == "MEASURE")
    measure.postgres_type = "NUMERIC(5,1)"
    plan = build_dimensional_etl_plan(dataset, validation.contract, physical, artifact)
    assert plan.status == ETLPlanStatus.BLOCKED and any("Precision loss" in x for x in plan.blockers)


def test_o_rejection_contract():
    *_, plan = etl("reject")
    assert plan.rejection_policy.no_silent_discard and "source_row_id" in plan.rejection_policy.rejected_row_contract.fields


def test_p_idempotency():
    *_, plan = etl("idempotent")
    assert plan.idempotency_plan.strategy == "LOAD_BATCH_ID" and plan.idempotency_plan.duplicate_prevention


def test_q_restartability():
    *_, plan = etl("restart")
    assert plan.restart_plan.safe_restart_point == "AFTER_COMPLETED_DIMENSIONS_BEFORE_FACTS"


def test_r_load_batch():
    *_, plan = etl("batch")
    assert plan.idempotency_plan.load_batch_id_planned and "run_id" in plan.load_audit_plan.fields


def test_s_dependency_cycle():
    with pytest.raises(ValueError, match="cycle"):
        topological_execution_order({"a": ["b"], "b": ["a"]})


def test_t_field_coverage():
    *_, plan = etl("coverage")
    assert plan.target_coverage_percentage == plan.source_coverage_percentage == 100


def test_u_no_silent_data_loss_and_determinism():
    dataset, validation, physical, artifact, plan = etl("lossless")
    assert all(field.source_field_id in {m.source_field_id for m in plan.field_mappings}
               for field in dataset.schema_fields)
    repeated = build_dimensional_etl_plan(dataset, validation.contract, physical, artifact)
    assert plan.fingerprint == repeated.fingerprint and plan.execution_order == repeated.execution_order
    assert export_etl_plan_json(plan) and export_etl_mapping_csv(plan)


def test_scd_unknown_is_a_blocker():
    *_, plan = etl("scd_unknown", scd=SCDType.UNKNOWN)
    assert plan.status == ETLPlanStatus.BLOCKED and any("unresolved SCD" in x for x in plan.blockers)
