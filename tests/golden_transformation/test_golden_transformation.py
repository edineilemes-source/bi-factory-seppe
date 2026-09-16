from copy import deepcopy
from datetime import datetime, timezone

from core.etl.models import MappingRole
from core.profiling.models import SemanticRole
from core.star.models import Nullability, SCDType
from core.transformation.engine import (
    TransformationConfig, execute_dimensional_transformation, resume_dimensional_transformation,
)
from core.transformation.models import TransformationRunReadiness, TransformationRunStatus
from tests.golden_etl_plan.test_golden_etl_plan import etl


def transformed(name="transform", *, scd=SCDType.TYPE_1, columns=None, data=None, grain=None,
                transform=None, timestamp=None, persist=False):
    dataset, validation, physical, artifact, plan = etl(
        name, scd=scd, columns=columns, data=data, grain=grain, transform=transform)
    run = execute_dimensional_transformation(dataset, plan, config=TransformationConfig(
        persist_artifacts=persist, effective_timestamp=timestamp))
    return dataset, plan, run


def test_a_basic_dimension_fact_and_surrogate_lookup():
    _, _, run = transformed()
    assert run.status == TransformationRunStatus.COMPLETED
    assert run.dimension_results and run.fact_results and run.surrogate_key_maps
    assert run.fact_results[0].unresolved_lookup_count == 0


def test_b_dimension_dedup_by_business_key():
    _, _, run = transformed("dedup", data=[["E1", "C1", 10], ["E2", "C1", 20]])
    assert run.dimension_results[0].row_count == 2  # one business member plus reserved unknown


def test_c_scd_type_1_keeps_one_current_member():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER),
            ("customer_name", SemanticRole.DESCRIPTION), ("amount", SemanticRole.MEASURE)]
    def track(dataset, validation):
        source = next(f.source_field_id for f in dataset.schema_fields if f.technical_name == "customer_name")
        validation.contract.dimension_tables[0].attributes.append(source)
    _, _, run = transformed("scd1_exec", columns=cols, transform=track,
        data=[["E1", "C1", "Old", 1], ["E2", "C1", "New", 2]], grain=["event_id"])
    members = [row for row in run.dimension_results[0].staged_rows if row.get("customer_sk") != 0]
    assert len(members) == 1 and "New" in members[0].values()


def test_d_scd_type_2_creates_versions_with_one_current():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER),
            ("customer_name", SemanticRole.DESCRIPTION), ("amount", SemanticRole.MEASURE)]
    def track(dataset, validation):
        source = next(f.source_field_id for f in dataset.schema_fields if f.technical_name == "customer_name")
        dimension = validation.contract.dimension_tables[0]
        dimension.attributes.append(source)
        dimension.scd_strategy.tracked_attributes = [source]
    _, _, run = transformed("scd2_exec", scd=SCDType.TYPE_2, columns=cols, transform=track,
        data=[["E1", "C1", "Old", 1], ["E2", "C1", "New", 2]], grain=["event_id"],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc))
    members = [row for row in run.dimension_results[0].staged_rows if row.get("customer_sk") != 0]
    assert len(members) == 2 and sum(bool(row["is_current"]) for row in members) == 1
    assert all(row["effective_from"] for row in members)


def test_e_unknown_member_resolves_optional_lookup():
    _, _, run = transformed("unknown_exec", data=[["E1", None, 10]])
    assert run.dimension_results[0].unknown_member_created
    assert run.fact_results[0].unknown_member_usage_count == 1
    assert 0 in run.fact_results[0].staged_rows[0].values()


def test_f_required_lookup_failure_is_never_null():
    def required(_, validation):
        for fact in validation.contract.fact_tables:
            for fk in fact.foreign_keys: fk.optionality = Nullability.NOT_NULLABLE
    _, _, run = transformed("required_exec", data=[["E1", None, 10]], transform=required)
    assert run.status == TransformationRunStatus.COMPLETED_WITH_REJECTIONS
    assert not run.fact_results[0].staged_rows and run.rejected_rows


def test_g_role_playing_date_uses_one_dimension_and_three_lookups():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("order_date", SemanticRole.DATE),
            ("ship_date", SemanticRole.DATE), ("payment_date", SemanticRole.DATE)]
    _, _, run = transformed("roles_exec", columns=cols,
        data=[["E1", "2026-01-01", "2026-01-02", "2026-01-03"]], grain=["event_id"])
    assert len(run.dimension_results) == 1
    row = run.fact_results[0].staged_rows[0]
    assert all(row[name] for name in ("order_date_sk", "ship_date_sk", "payment_date_sk"))


def test_h_factless_fact():
    cols = [("event_id", SemanticRole.IDENTIFIER), ("customer_id", SemanticRole.IDENTIFIER)]
    _, _, run = transformed("factless_exec", columns=cols, data=[["E1", "C1"]], grain=["event_id"])
    assert run.fact_results[0].staged_row_count == 1 and not run.fact_results[0].measure_metrics


def test_i_multi_fact():
    from tests.golden_etl_plan.test_golden_etl_plan import test_i_multi_fact
    # Recreate the multi-fact pipeline using its declarative setup helpers.
    from core.dimensional.validation import validate_dimensional_discovery
    from core.ddl.generator import generate_postgresql_ddl
    from core.ddl.models import PhysicalSchemaStatus
    from core.etl.planner import build_dimensional_etl_plan
    from core.star.engine import build_star_schema_contract
    from core.star.validation import validate_star_schema_contract
    from tests.golden_dimensional.test_golden_dimensional import proposal
    dataset, _, grain_def, _, report = proposal("transform_multi", [
        ("event_a", SemanticRole.IDENTIFIER), ("event_b", SemanticRole.IDENTIFIER),
        ("customer_id", SemanticRole.IDENTIFIER), ("amount", SemanticRole.MEASURE)],
        [["A1", None, "C1", 2], [None, "B1", "C1", 3]], ["event_a", "event_b"],
        multi_groups=[["event_a"], ["event_b"]])
    dimensional = validate_dimensional_discovery(report, accepted_unresolved_fields=report.unresolved_fields)
    validation = validate_star_schema_contract(build_star_schema_contract(dataset, grain_def, dimensional))
    for dim in validation.contract.dimension_tables: dim.scd_strategy.strategy=SCDType.TYPE_1; dim.scd_strategy.requires_validation=False
    physical, artifact=generate_postgresql_ddl(validation);physical.lifecycle_status=PhysicalSchemaStatus.EFFECTIVE;artifact.human_validated=True
    plan=build_dimensional_etl_plan(dataset,validation.contract,physical,artifact)
    run=execute_dimensional_transformation(dataset,plan,config=TransformationConfig(persist_artifacts=False))
    assert len(run.fact_results) == 2 and all(item.staged_row_count == 1 for item in run.fact_results)


def test_j_bridge_staging():
    def bridge(_, validation):
        for item in validation.contract.bridge_candidates: item.requires_validation = False
    cols = [("event_id", SemanticRole.IDENTIFIER), ("person_id", SemanticRole.IDENTIFIER), ("group_id", SemanticRole.IDENTIFIER)]
    _, _, run = transformed("bridge_exec", columns=cols, transform=bridge,
        data=[["E1", "P1", "G1"], ["E2", "P1", "G2"], ["E3", "P2", "G1"], ["E4", "P2", "G2"]], grain=["event_id"])
    assert run.bridge_results and run.bridge_results[0].staged_row_count == 4


def test_k_leading_zero_preserved():
    _, _, run = transformed("zero_exec", data=[["E1", "00123", 10]])
    assert any("00123" in row.values() for row in run.dimension_results[0].staged_rows)


def test_l_precision_loss_plan_blocks_execution():
    dataset, plan, _ = transformed("precision_exec", data=[["E1", "C1", 10.25]])
    plan.status = __import__("core.etl.models", fromlist=["ETLPlanStatus"]).ETLPlanStatus.BLOCKED
    plan.blockers.append("Precision loss")
    run = execute_dimensional_transformation(dataset, plan, config=TransformationConfig(persist_artifacts=False))
    assert run.status == TransformationRunStatus.BLOCKED and run.readiness == TransformationRunReadiness.FAIL


def test_m_negative_measure_preserved():
    _, _, run = transformed("negative_exec", data=[["E1", "C1", -12.5]])
    assert -12.5 in run.fact_results[0].staged_rows[0].values()


def test_n_outlier_preserved():
    _, _, run = transformed("outlier_exec", data=[["E1", "C1", 999999999]])
    assert 999999999 in run.fact_results[0].staged_rows[0].values()


def test_o_reconciliation_pass():
    _, _, run = transformed("recon_pass")
    assert run.reconciliation_report.status == "PASS"
    assert run.reconciliation_report.measure_reconciliations[0].difference == "0"


def test_p_reconciliation_fail():
    dataset, plan, _ = transformed("recon_fail")
    plan.reconciliation_plan.measure_reconciliations[0].target_column = "synthetic_missing_measure"
    run = execute_dimensional_transformation(dataset, plan, config=TransformationConfig(persist_artifacts=False))
    assert run.reconciliation_report.status == "FAIL" and run.readiness == TransformationRunReadiness.FAIL


def test_q_no_silent_data_loss():
    _, _, run = transformed("loss_exec")
    report = run.reconciliation_report
    assert report.prepared_row_count == report.staged_fact_row_count + report.rejected_row_count + report.quarantined_row_count + report.explicitly_excluded_count


def test_r_idempotency_fingerprints_stable_runs_distinct():
    dataset, plan, first = transformed("idem_exec")
    second = execute_dimensional_transformation(dataset, plan, config=TransformationConfig(persist_artifacts=False))
    assert first.run_id != second.run_id and first.load_batch_id != second.load_batch_id
    assert first.fingerprint == second.fingerprint


def test_s_restart_after_checkpoint_matches_clean_result():
    dataset, plan, clean = transformed("restart_exec")
    failed = execute_dimensional_transformation(dataset, plan,
        config=TransformationConfig(persist_artifacts=False, fail_after_step=1))
    assert failed.status == TransformationRunStatus.FAILED and failed.execution_steps[0].status.value == "COMPLETED"
    resumed = resume_dimensional_transformation(dataset, plan, failed,
        config=TransformationConfig(persist_artifacts=False))
    assert resumed.fingerprint == clean.fingerprint


def test_t_source_immutability():
    dataset, _, _, _, plan = etl("immutable_exec")
    before = dataset.model_dump_json()
    execute_dimensional_transformation(dataset, plan, config=TransformationConfig(persist_artifacts=False))
    assert dataset.model_dump_json() == before


def test_u_field_coverage():
    _, plan, run = transformed("field_exec")
    assert plan.target_coverage_percentage == run.metrics.target_field_coverage_percentage == 100


def test_v_deterministic_staged_content_fingerprints():
    dataset, plan, first = transformed("det_exec")
    second = execute_dimensional_transformation(dataset, plan, config=TransformationConfig(persist_artifacts=False))
    assert [x.fingerprint for x in first.dimension_results] == [x.fingerprint for x in second.dimension_results]
    assert [x.fingerprint for x in first.fact_results] == [x.fingerprint for x in second.fact_results]
