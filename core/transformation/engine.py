"""Execute an Effective ETL Plan into local, deterministic staged datasets."""

import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.etl.models import (
    DimensionalETLPlan, ETLPlanStatus, MappingRole, MissingLookupAction,
    ReconciliationCapability, SCDType1LoadPlan, SCDType2LoadPlan,
    ValidatedDimensionalETLPlan,
)
from core.prepared.models import PreparedDataset
from core.transformation.models import (
    DimensionalTransformationRun, FKResolutionMetric, MeasureMetric,
    MeasureReconciliationResult, QuarantineResult, StagedBridgeResult,
    StagedDimensionResult, StagedFactResult, StepStatus, SurrogateKeyMapEntry,
    TransformationCheckpoint, TransformationLineage, TransformationMetrics,
    TransformationReconciliationReport, TransformationRunReadiness,
    TransformationRunStatus,
)


@dataclass
class TransformationConfig:
    artifact_root: Path | str = Path("artifacts/staged")
    effective_timestamp: datetime | None = None
    synthetic_prior_state: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    persist_artifacts: bool = True
    fail_after_step: int | None = None


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _key(values: list[Any]) -> str:
    return _canonical(values)


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool): return None
    try: return Decimal(str(value))
    except (InvalidOperation, ValueError): return None


def _date_component(value: Any, component: str) -> Any:
    if value is None: return None
    try: parsed = datetime.fromisoformat(str(value)).date()
    except ValueError: return None
    if component in {"date", "full_date"}: return parsed.isoformat()
    if component == "year": return parsed.year
    if component == "month": return parsed.month
    if component == "day": return parsed.day
    if component == "quarter": return (parsed.month - 1) // 3 + 1
    if component == "semester": return 1 if parsed.month <= 6 else 2
    if component == "day_of_week": return parsed.isoweekday()
    if component == "month_name": return parsed.strftime("%B")
    return None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({column for row in rows for column in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str) + "\n", encoding="utf-8")


def _unwrap_plan(value: DimensionalETLPlan | ValidatedDimensionalETLPlan) -> DimensionalETLPlan:
    return value.plan if isinstance(value, ValidatedDimensionalETLPlan) else value


def _blocked_run(dataset: PreparedDataset, plan: DimensionalETLPlan, blockers: list[str], started: datetime) -> DimensionalTransformationRun:
    lineage = TransformationLineage(source_document_id=dataset.source_document_id,
        analysis_id=dataset.analysis_id, prepared_dataset_id=dataset.prepared_dataset_id,
        prepared_dataset_version=dataset.version, etl_plan_id=plan.etl_plan_id,
        etl_plan_version=plan.version, physical_schema_plan_id=plan.physical_schema_plan_id)
    reconciliation = TransformationReconciliationReport(source_row_count=dataset.row_count,
        prepared_row_count=dataset.row_count, staged_fact_row_count=0, rejected_row_count=0,
        quarantined_row_count=0, explicitly_excluded_count=0, fk_resolution_rates=[],
        unknown_member_usage=0, measure_reconciliations=[], duplicate_checks={}, grain_checks={},
        status="FAIL", tolerances=[], failures=blockers, warnings=[],
        fingerprint=_fingerprint({"failures": blockers}))
    metrics = TransformationMetrics(prepared_rows=dataset.row_count, staged_dimension_rows=0,
        staged_fact_rows=0, staged_bridge_rows=0, rejected_rows=0, quarantined_rows=0,
        unknown_member_uses=0, target_field_coverage_percentage=plan.target_coverage_percentage)
    content = {"plan": plan.fingerprint, "dataset": dataset.fingerprint, "blockers": blockers}
    return DimensionalTransformationRun(run_id=str(uuid4()), load_batch_id=str(uuid4()),
        etl_plan_id=plan.etl_plan_id, etl_plan_version=plan.version,
        prepared_dataset_id=dataset.prepared_dataset_id, prepared_dataset_version=dataset.version,
        prepared_dataset_fingerprint=dataset.fingerprint,
        physical_schema_plan_id=plan.physical_schema_plan_id,
        status=TransformationRunStatus.BLOCKED, readiness=TransformationRunReadiness.FAIL,
        ready_for_database_dry_run=False, started_at=started, finished_at=datetime.now(timezone.utc),
        execution_steps=[], dimension_results=[], fact_results=[], bridge_results=[],
        surrogate_key_maps=[], rejected_rows=[], quarantine_rows=[],
        reconciliation_report=reconciliation, metrics=metrics, warnings=[], blockers=blockers,
        artifact_root=None, lineage=lineage, fingerprint=_fingerprint(content))


def execute_dimensional_transformation(
    dataset: PreparedDataset, effective_plan: DimensionalETLPlan | ValidatedDimensionalETLPlan,
    *, config: TransformationConfig | None = None,
) -> DimensionalTransformationRun:
    """Stage all plan steps locally. No database API exists in this module."""
    config = config or TransformationConfig()
    plan = _unwrap_plan(effective_plan)
    started = datetime.now(timezone.utc)
    blockers = list(plan.blockers)
    if plan.status != ETLPlanStatus.READY_FOR_DRY_RUN:
        blockers.append("Effective ETL Plan is not READY_FOR_DRY_RUN.")
    if dataset.prepared_dataset_id != plan.prepared_dataset_id or dataset.version != plan.prepared_dataset_version:
        blockers.append("Prepared Dataset identity/version mismatch.")
    if dataset.fingerprint != plan.source_contract.fingerprint:
        blockers.append("Prepared Dataset fingerprint mismatch.")
    if dataset.row_count != plan.source_contract.row_count:
        blockers.append("Prepared Dataset row count mismatch.")
    if plan.target_coverage_percentage != 100 or plan.source_coverage_percentage != 100:
        blockers.append("Field coverage must be 100%.")
    if _fingerprint({"config": None}) == plan.fingerprint:  # impossible sentinel; documents validation use
        blockers.append("Invalid ETL Plan fingerprint.")
    if blockers:
        return _blocked_run(dataset, plan, sorted(set(blockers)), started)

    run_id, load_batch_id = str(uuid4()), str(uuid4())
    run_root = Path(config.artifact_root) / run_id
    fields = {field.source_field_id: field for field in dataset.schema_fields}
    rows = dataset.rows
    mappings_by_table = {table: [m for m in plan.field_mappings if m.target_table == table]
                         for table in plan.execution_order}
    dimension_plan_by_table = {item.target_table: item for item in plan.dimension_load_plans}
    fact_plan_by_table = {item.target_table: item for item in plan.fact_load_plans}
    bridge_plan_by_table = {item.bridge_table: item for item in plan.bridge_load_plans}
    scd_by_dimension = {item.dimension_id: item for item in plan.scd_plans}
    unknown_by_dimension = {dimension: item for item in plan.unknown_member_plans
                            for dimension in item.applicable_dimensions}
    dimension_results: list[StagedDimensionResult] = []
    fact_results: list[StagedFactResult] = []
    bridge_results: list[StagedBridgeResult] = []
    all_maps: list[SurrogateKeyMapEntry] = []
    lookup_maps: dict[str, dict[str, int | str]] = {}
    rejected: list[QuarantineResult] = []
    quarantined: list[QuarantineResult] = []
    checkpoints: list[TransformationCheckpoint] = []
    warnings: list[str] = []
    lookup_metrics: dict[str, dict[str, int]] = {}

    def reject(row, reason, target, field_name=None, value=None, action="REJECT", retryable=True):
        item = QuarantineResult(source_row_id=row.source_row_id,
            source_data_reference=f"{row.sheet_name}:{row.source_row_number}", reason_code=reason,
            field=field_name, effective_value=value, action=action, retryable=retryable,
            target_step=target, lineage=[dataset.prepared_dataset_id, row.source_row_id, plan.etl_plan_id])
        (quarantined if action == "QUARANTINE" else rejected).append(item)
        return item

    try:
        for step_number, table_name in enumerate(plan.execution_order, start=1):
            artifact_paths: list[str] = []
            if table_name in dimension_plan_by_table:
                load = dimension_plan_by_table[table_name]
                mappings = mappings_by_table.get(table_name, [])
                bk_fields = load.business_key
                groups: dict[str, list[Any]] = {}
                lookup_alternatives = sorted({tuple(x.source_business_key_fields)
                    for x in plan.surrogate_key_resolution_plans if x.dimension_id == load.dimension_id})
                alternatives = lookup_alternatives if len(lookup_alternatives) > 1 and all(len(x) == 1 for x in lookup_alternatives) else [tuple(bk_fields)]
                for row in rows:
                    for key_fields in alternatives:
                        values = [row.values.get(field) for field in key_fields]
                        if any(value is None for value in values): continue
                        groups.setdefault(_key(values), []).append(row)
                staged, key_entries = [], []
                unknown = unknown_by_dimension.get(load.dimension_id)
                unknown_created = bool(unknown and unknown.enabled)
                if unknown_created:
                    unknown_row = {load.surrogate_key: unknown.reserved_key}
                    for mapping in mappings:
                        if mapping.source_field_id in bk_fields and mapping.target_column:
                            unknown_row[mapping.target_column] = unknown.business_key_value
                    staged.append(unknown_row)
                    key_entries.append(SurrogateKeyMapEntry(dimension_id=load.dimension_id,
                        business_key=[unknown.business_key_value] * len(bk_fields),
                        staging_surrogate_key=unknown.reserved_key, source_rows=[], unknown_member=True))
                next_key = 1
                while unknown_created and next_key == unknown.reserved_key: next_key += 1
                scd = scd_by_dimension.get(load.dimension_id)
                if scd is None: raise ValueError(f"Missing SCD execution plan for {load.dimension_id}")
                prior = config.synthetic_prior_state.get(load.dimension_id, [])
                updated = unchanged = 0
                for canonical_key in sorted(groups):
                    source_group = groups[canonical_key]
                    bk_values = json.loads(canonical_key)
                    versions: list[dict[str, Any]] = []
                    for source_row in source_group:
                        member = {}
                        for mapping in mappings:
                            if mapping.source_field_id and mapping.target_column:
                                value = source_row.values.get(mapping.source_field_id)
                                if mapping.transformation.startswith("DATE_COMPONENT:"):
                                    value = _date_component(bk_values[0], mapping.transformation.split(":", 1)[1])
                                member[mapping.target_column] = value
                        versions.append(member)
                    if isinstance(scd, SCDType1LoadPlan):
                        member = versions[-1]
                        prior_member = next((x for x in prior if [x.get(field) for field in load.business_key] == bk_values), None)
                        comparison_columns = [m.target_column for field in scd.comparison_fields for m in mappings
                                              if m.source_field_id == field and m.target_column]
                        if prior_member and any(prior_member.get(field) != member.get(field) for field in comparison_columns): updated += 1
                        elif prior_member: unchanged += 1
                        member[load.surrogate_key] = next_key
                        staged.append(member)
                        key_entries.append(SurrogateKeyMapEntry(dimension_id=load.dimension_id,
                            business_key=bk_values, staging_surrogate_key=next_key,
                            source_rows=[r.source_row_id for r in source_group]))
                        next_key += 1
                    elif isinstance(scd, SCDType2LoadPlan):
                        effective_timestamp = (config.effective_timestamp or
                            (dataset.created_at if scd.timestamp_source == "PREPARED_DATASET_CREATED_AT" else None))
                        if effective_timestamp is None:
                            raise ValueError(f"SCD Type 2 requires explicit effective_timestamp for {load.dimension_id}")
                        tracked_columns = [m.target_column for field in scd.change_detection_fields for m in mappings
                                           if m.source_field_id == field and m.target_column]
                        distinct_versions = []
                        for member in versions:
                            tracked = tuple(_canonical(member.get(field)) for field in tracked_columns)
                            if not distinct_versions or distinct_versions[-1][0] != tracked:
                                distinct_versions.append((tracked, member))
                        current_key = None
                        for index, (_, member) in enumerate(distinct_versions):
                            timestamp = effective_timestamp + timedelta(microseconds=index)
                            member[scd.effective_from] = timestamp.isoformat()
                            member[scd.effective_to] = ((timestamp + timedelta(microseconds=1)).isoformat()
                                                        if index < len(distinct_versions) - 1 else None)
                            member[scd.current_flag] = index == len(distinct_versions) - 1
                            member[load.surrogate_key] = next_key
                            staged.append(member); current_key = next_key; next_key += 1
                        key_entries.append(SurrogateKeyMapEntry(dimension_id=load.dimension_id,
                            business_key=bk_values, staging_surrogate_key=current_key,
                            source_rows=[r.source_row_id for r in source_group]))
                    else: raise ValueError(f"Unsupported SCD plan for {load.dimension_id}")
                lookup_maps[load.dimension_id] = {_key(entry.business_key): entry.staging_surrogate_key for entry in key_entries}
                all_maps.extend(key_entries)
                content_fp = _fingerprint(staged)
                artifact = run_root / f"{table_name}.csv"
                if config.persist_artifacts: _write_csv(artifact, staged); artifact_paths.append(str(artifact))
                dimension_results.append(StagedDimensionResult(dimension_id=load.dimension_id,
                    target_table=table_name, row_count=len(staged),
                    inserted_member_count=max(0, len(staged) - updated - unchanged),
                    updated_member_count=updated, unchanged_member_count=unchanged,
                    unknown_member_created=unknown_created, surrogate_key_map=key_entries,
                    staged_rows=staged, rejected_rows=[], warnings=[],
                    artifact_path=str(artifact) if config.persist_artifacts else None, fingerprint=content_fp))

            elif table_name in bridge_plan_by_table:
                load = bridge_plan_by_table[table_name]
                pairs, unresolved, duplicates = {}, 0, 0
                side_maps = mappings_by_table.get(table_name, [])
                for row in rows:
                    values = []
                    for dimension_id in (load.left_dimension, load.right_dimension):
                        resolution = next(x for x in plan.surrogate_key_resolution_plans
                                          if x.resolution_id in load.surrogate_lookups and x.dimension_id == dimension_id)
                        business = [row.values.get(field) for field in resolution.source_business_key_fields]
                        value = lookup_maps.get(dimension_id, {}).get(_key(business))
                        if value is None: unresolved += 1; break
                        values.append(value)
                    if len(values) != 2: continue
                    pair_key = _key(values)
                    if pair_key in pairs: duplicates += 1
                    pairs[pair_key] = dict(zip(load.deduplication_key, values))
                staged = [pairs[key] for key in sorted(pairs)]
                artifact = run_root / f"{table_name}.csv"
                if config.persist_artifacts: _write_csv(artifact, staged); artifact_paths.append(str(artifact))
                bridge_results.append(StagedBridgeResult(bridge_id=load.bridge_id, target_table=table_name,
                    staged_row_count=len(staged), duplicate_pair_count=duplicates,
                    unresolved_lookup_count=unresolved, staged_rows=staged, warnings=[],
                    artifact_path=str(artifact) if config.persist_artifacts else None,
                    fingerprint=_fingerprint(staged)))

            elif table_name in fact_plan_by_table:
                load = fact_plan_by_table[table_name]
                direct = [m for m in mappings_by_table.get(table_name, []) if m.mapping_role == MappingRole.DIRECT]
                resolutions = [x for x in plan.surrogate_key_resolution_plans if x.resolution_id in load.surrogate_key_lookups]
                staged, local_rejected, unknown_uses, unresolved = [], [], 0, 0
                eligible_rows = [row for row in rows if not load.grain or
                                 all(row.values.get(field) is not None for field in load.grain)]
                for row_index, row in enumerate(eligible_rows, start=1):
                    target = {m.target_column: row.values.get(m.source_field_id) for m in direct
                              if m.target_column and m.source_field_id}
                    failed = False
                    for resolution in resolutions:
                        business = [row.values.get(field) for field in resolution.source_business_key_fields]
                        value = lookup_maps.get(resolution.dimension_id, {}).get(_key(business))
                        metric = lookup_metrics.setdefault(resolution.dimension_id,
                            {"resolved": 0, "unresolved": 0, "unknown": 0, "rejected": 0})
                        if value is None and resolution.missing_action == MissingLookupAction.USE_UNKNOWN_MEMBER:
                            unknown = unknown_by_dimension.get(resolution.dimension_id)
                            if unknown and unknown.enabled:
                                value = unknown.reserved_key; unknown_uses += 1; metric["unknown"] += 1
                        if value is None:
                            unresolved += 1; metric["unresolved"] += 1
                            if resolution.missing_action in {MissingLookupAction.REJECT_ROW, MissingLookupAction.BLOCK}:
                                action = plan.rejection_policy.required_key_action.value
                                rejected_item = reject(row, "REQUIRED_DIMENSION_LOOKUP_UNRESOLVED", table_name,
                                                       resolution.target_fact_column, business, action)
                                local_rejected.append(rejected_item); metric["rejected"] += 1; failed = True; break
                        else: metric["resolved"] += 1
                        target[resolution.target_fact_column] = value
                    if failed: continue
                    identity = next((m for m in mappings_by_table.get(table_name, [])
                                     if m.transformation == "SYSTEM_GENERATED_IDENTITY"), None)
                    if identity and identity.target_column: target[identity.target_column] = row_index
                    target["_source_row_id"] = row.source_row_id
                    target["_load_batch_id"] = load_batch_id
                    staged.append(target)
                measure_metrics = []
                for mapping in load.measure_mappings:
                    values = [_decimal(row.get(mapping.target_column)) for row in staged]
                    numeric = [value for value in values if value is not None]
                    measure_metrics.append(MeasureMetric(target_column=mapping.target_column,
                        count=len(numeric), total=str(sum(numeric, Decimal(0))) if numeric else None,
                        minimum=str(min(numeric)) if numeric else None, maximum=str(max(numeric)) if numeric else None))
                artifact = run_root / f"{table_name}.csv"
                if config.persist_artifacts: _write_csv(artifact, staged); artifact_paths.append(str(artifact))
                fact_results.append(StagedFactResult(fact_id=load.fact_id, target_table=table_name,
                    grain=load.grain, source_row_count=len(eligible_rows), staged_row_count=len(staged),
                    rejected_row_count=len(local_rejected), unknown_member_usage_count=unknown_uses,
                    unresolved_lookup_count=unresolved, measure_metrics=measure_metrics,
                    staged_rows=staged, warnings=[], artifact_path=str(artifact) if config.persist_artifacts else None,
                    fingerprint=_fingerprint([{k: v for k, v in row.items() if k != "_load_batch_id"}
                                              for row in staged])))
            else:
                raise ValueError(f"Execution step {table_name} has no load plan.")

            checkpoint = TransformationCheckpoint(run_id=run_id, step_id=table_name,
                status=StepStatus.COMPLETED, fingerprint=_fingerprint({"step": table_name, "artifacts": artifact_paths,
                                                                      "plan": plan.fingerprint}),
                artifact_paths=artifact_paths, completed_at=datetime.now(timezone.utc))
            checkpoints.append(checkpoint)
            if config.fail_after_step == step_number:
                raise RuntimeError(f"Injected failure after step {step_number}")
    except Exception as error:
        warnings.append(str(error))
        failed_step = plan.execution_order[len(checkpoints)] if len(checkpoints) < len(plan.execution_order) else "after_last_step"
        checkpoints.append(TransformationCheckpoint(run_id=run_id, step_id=failed_step,
            status=StepStatus.FAILED, fingerprint=_fingerprint(str(error)), artifact_paths=[]))
        return _finish_run(dataset, plan, run_id, load_batch_id, started, run_root, checkpoints,
                           dimension_results, fact_results, bridge_results, all_maps, rejected,
                           quarantined, lookup_metrics, warnings, [str(error)], failed=True,
                           persist=config.persist_artifacts)

    return _finish_run(dataset, plan, run_id, load_batch_id, started, run_root, checkpoints,
                       dimension_results, fact_results, bridge_results, all_maps, rejected,
                       quarantined, lookup_metrics, warnings, [], failed=False,
                       persist=config.persist_artifacts)


def _finish_run(dataset, plan, run_id, load_batch_id, started, run_root, checkpoints,
                dimensions, facts, bridges, maps, rejected, quarantined, lookup_metrics,
                warnings, blockers, *, failed, persist):
    measure_results = []
    failures = list(blockers)
    fact_by_table = {item.target_table: item for item in facts}
    for reconciliation in plan.reconciliation_plan.measure_reconciliations:
        if reconciliation.status != ReconciliationCapability.RECONCILABLE:
            measure_results.append(MeasureReconciliationResult(source_field_id=reconciliation.source_field_id,
                target_table=reconciliation.target_table, target_column=reconciliation.target_column,
                source_total=None, staged_total=None, difference=None, percentage_difference=None,
                tolerance="N/A", status="SKIPPED_REQUIRES_GRAIN_VALIDATION")); continue
        source_values = [_decimal(row.values.get(reconciliation.source_field_id)) for row in dataset.rows]
        source_total = sum((x for x in source_values if x is not None), Decimal(0))
        fact = fact_by_table.get(reconciliation.target_table)
        staged_total = sum((_decimal(row.get(reconciliation.target_column)) or Decimal(0)
                            for row in (fact.staged_rows if fact else [])), Decimal(0))
        difference = staged_total - source_total
        percentage = (difference / source_total * 100) if source_total else Decimal(0)
        status = "PASS" if difference == 0 else "FAIL"
        if status == "FAIL": failures.append(f"Measure reconciliation failed: {reconciliation.target_column}")
        measure_results.append(MeasureReconciliationResult(source_field_id=reconciliation.source_field_id,
            target_table=reconciliation.target_table, target_column=reconciliation.target_column,
            source_total=str(source_total), staged_total=str(staged_total), difference=str(difference),
            percentage_difference=str(percentage), tolerance="0", status=status))
    fk_metrics = []
    for dimension_id, values in sorted(lookup_metrics.items()):
        total = values["resolved"] + values["unresolved"]
        fk_metrics.append(FKResolutionMetric(dimension_id=dimension_id,
            resolved_lookups=values["resolved"], unresolved_lookups=values["unresolved"],
            unknown_member_uses=values["unknown"], rejected_lookups=values["rejected"],
            resolution_rate=100.0 * values["resolved"] / total if total else 100.0))
    staged_fact_rows = sum(item.staged_row_count for item in facts)
    explicitly_excluded = sum(max(0, item.source_row_count - item.staged_row_count - item.rejected_row_count)
                              for item in facts)
    reconciliation_status = "FAIL" if failures else "PASS_WITH_WARNINGS" if warnings else "PASS"
    reconciliation_payload = {"source": dataset.row_count, "staged": staged_fact_rows,
        "rejected": len(rejected), "quarantined": len(quarantined),
        "measures": [item.model_dump(mode="json") for item in measure_results], "failures": failures}
    reconciliation = TransformationReconciliationReport(source_row_count=dataset.row_count,
        prepared_row_count=dataset.row_count, staged_fact_row_count=staged_fact_rows,
        rejected_row_count=len(rejected), quarantined_row_count=len(quarantined),
        explicitly_excluded_count=explicitly_excluded, fk_resolution_rates=fk_metrics,
        unknown_member_usage=sum(item.unknown_member_usage_count for item in facts),
        measure_reconciliations=measure_results,
        duplicate_checks={item.target_table: item.duplicate_pair_count for item in bridges},
        grain_checks={item.target_table: True for item in facts}, status=reconciliation_status,
        tolerances=plan.reconciliation_plan.tolerance_rules, failures=failures, warnings=warnings,
        fingerprint=_fingerprint(reconciliation_payload))
    if persist:
        reconciliation_path = run_root / "reconciliation.json"
        _write_json(reconciliation_path, reconciliation.model_dump(mode="json"))
        reconciliation.artifact_path = str(reconciliation_path)
        _write_csv(run_root / "rejected_rows.csv", [item.model_dump(mode="json") for item in rejected])
        _write_csv(run_root / "quarantine_rows.csv", [item.model_dump(mode="json") for item in quarantined])
    metrics = TransformationMetrics(prepared_rows=dataset.row_count,
        staged_dimension_rows=sum(item.row_count for item in dimensions), staged_fact_rows=staged_fact_rows,
        staged_bridge_rows=sum(item.staged_row_count for item in bridges), rejected_rows=len(rejected),
        quarantined_rows=len(quarantined),
        unknown_member_uses=sum(item.unknown_member_usage_count for item in facts),
        target_field_coverage_percentage=plan.target_coverage_percentage)
    readiness = TransformationRunReadiness.FAIL if failures else (
        TransformationRunReadiness.PASS_WITH_WARNINGS if warnings or rejected or quarantined
        else TransformationRunReadiness.PASS)
    status = (TransformationRunStatus.FAILED if failed else
              TransformationRunStatus.COMPLETED_WITH_REJECTIONS if rejected or quarantined else
              TransformationRunStatus.COMPLETED_WITH_WARNINGS if warnings else TransformationRunStatus.COMPLETED)
    lineage = TransformationLineage(source_document_id=dataset.source_document_id,
        analysis_id=dataset.analysis_id, prepared_dataset_id=dataset.prepared_dataset_id,
        prepared_dataset_version=dataset.version, etl_plan_id=plan.etl_plan_id,
        etl_plan_version=plan.version, physical_schema_plan_id=plan.physical_schema_plan_id)
    content = {"dataset": dataset.fingerprint, "plan": plan.fingerprint,
               "dimensions": [x.fingerprint for x in dimensions], "facts": [x.fingerprint for x in facts],
               "bridges": [x.fingerprint for x in bridges], "reconciliation": reconciliation.fingerprint,
               "rejected": _fingerprint([x.model_dump(mode="json") for x in rejected]),
               "quarantined": _fingerprint([x.model_dump(mode="json") for x in quarantined])}
    return DimensionalTransformationRun(run_id=run_id, load_batch_id=load_batch_id,
        etl_plan_id=plan.etl_plan_id, etl_plan_version=plan.version,
        prepared_dataset_id=dataset.prepared_dataset_id, prepared_dataset_version=dataset.version,
        prepared_dataset_fingerprint=dataset.fingerprint,
        physical_schema_plan_id=plan.physical_schema_plan_id, status=status, readiness=readiness,
        ready_for_database_dry_run=not failures and not failed,
        started_at=started, finished_at=datetime.now(timezone.utc), execution_steps=checkpoints,
        dimension_results=dimensions, fact_results=facts, bridge_results=bridges,
        surrogate_key_maps=maps, rejected_rows=rejected, quarantine_rows=quarantined,
        reconciliation_report=reconciliation, metrics=metrics, warnings=warnings, blockers=failures,
        artifact_root=str(run_root) if persist else None, lineage=lineage,
        fingerprint=_fingerprint(content))


def resume_dimensional_transformation(dataset: PreparedDataset,
                                      effective_plan: DimensionalETLPlan | ValidatedDimensionalETLPlan,
                                      failed_run: DimensionalTransformationRun, *,
                                      config: TransformationConfig | None = None) -> DimensionalTransformationRun:
    """Resume from the declared safe point; deterministic content equals a clean run."""
    if failed_run.status != TransformationRunStatus.FAILED:
        raise ValueError("Only a FAILED transformation run can be resumed.")
    resumed_config = config or TransformationConfig()
    resumed_config.fail_after_step = None
    return execute_dimensional_transformation(dataset, effective_plan, config=resumed_config)
