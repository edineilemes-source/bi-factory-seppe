"""Credential-free JSON exports for dry-run artifacts."""
import json
from core.database_dry_run.models import DatabaseDryRun

def _json(value) -> bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,default=str)+"\n").encode()

def export_database_dry_run(run: DatabaseDryRun) -> bytes: return _json(run.model_dump(mode="json"))
def export_database_validation_report(run: DatabaseDryRun) -> bytes: return _json(run.validation_results.model_dump(mode="json") if run.validation_results else {})
def export_database_reconciliation(run: DatabaseDryRun) -> bytes: return _json(run.reconciliation_results.model_dump(mode="json") if run.reconciliation_results else {})
