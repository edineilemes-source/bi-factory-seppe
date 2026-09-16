"""Reproduce the real Prepared audit without approving business rules or re-reading XLSX."""
import argparse
import json
from pathlib import Path
import sys
import time
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.bi_mvp.artifacts import resolve_prepared, persist_text
from core.bi_mvp.audit import inspect_prepared
from core.bi_mvp.etl import _rss_mb
from core.grain.artifact_discovery import discover_grain_from_artifact, GRAIN_ENGINE_VERSION
from core.persistence.sqlite_repository import SQLiteAnalysisRepository


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis_id')
    parser.add_argument('--prepared-id', required=True)
    parser.add_argument('--prepared-version', type=int, required=True)
    args=parser.parse_args()
    repo=SQLiteAnalysisRepository()
    start=time.perf_counter(); initial=_rss_mb()
    reader=resolve_prepared(args.analysis_id,repo,prepared_dataset_id=args.prepared_id,version=args.prepared_version)
    audit=inspect_prepared(reader)
    report=next((x.report for x in repo.list_grain_discovery_reports(args.prepared_id)
        if x.report.engine_version == GRAIN_ENGINE_VERSION),None)
    if report is None:
        report=discover_grain_from_artifact(reader,version=repo.next_grain_report_version(args.prepared_id))
        repo.save_grain_discovery_report(report)
    audit['grain_report_id']=report.grain_discovery_report_id
    audit['grain_report_version']=report.version
    audit['grain_engine']=report.engine_version
    audit['grain_classification']=report.grain_classification.value
    audit['grain_validated']=repo.get_effective_grain(args.prepared_id) is not None
    audit['catalog']=[k.model_dump(mode='json') for k in repo.list_semantic_knowledge(reader.artifact.source_document_id)]
    audit['end_to_end_rss_start_mb']=initial
    audit['end_to_end_rss_end_mb']=_rss_mb()
    import resource
    audit['process_peak_rss_mb']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    audit['end_to_end_elapsed_seconds']=time.perf_counter()-start
    root=Path('storage/reports/bi_mvp')/args.analysis_id
    path=persist_text(root/f'audit-{uuid4()}.json',json.dumps(audit,ensure_ascii=False,indent=2))
    persist_text(root/f'grain-report-v{report.version}.json',report.model_dump_json(indent=2))
    print(path)
    print(json.dumps({k:v for k,v in audit.items() if k not in ('examples','catalog','nonnull_counts')},indent=2))


if __name__=='__main__': main()
