"""Shared execution of the real semantic pipeline for tests and diagnostics."""

from core.profiling.workbook_profiler import profile_workbook
from core.semantic.decision_engine import decide_field
from core.semantic.validation_service import create_validation_report
from tests.golden.fixtures import golden_loaded_workbook


def run_golden_pipeline():
    profile = profile_workbook(golden_loaded_workbook())
    report = create_validation_report(profile)
    fields = {field.technical_name: field for field in profile.sheets[0].fields}
    decisions = {name: decide_field(field) for name, field in fields.items()}
    return profile, report, fields, decisions
