"""Streaming observations; no business approval is inferred from source statistics."""
import time
from decimal import Decimal
from core.bi_mvp.etl import _rss_mb, _decimal, add_exact
from core.bi_mvp.modeling import MEASURES


def inspect_prepared(reader, *, chunk_size=2000):
    started = time.perf_counter()
    start = peak = _rss_mb()
    counts = {f.source_name: 0 for f in reader.artifact.schema_fields}
    totals = {name: Decimal(0) for name in MEASURES if name in counts}
    rows = chunks = 0
    examples = []
    for chunk in reader.iter_chunks(chunk_size=chunk_size):
        chunks += 1
        for row in chunk:
            rows += 1
            for name in counts:
                counts[name] += row[name] is not None
            for name in totals:
                if row[name] is not None: totals[name] = add_exact(totals[name], _decimal(row[name]))
            if len(examples) < 5: examples.append(row)
        peak = max(peak, _rss_mb())
    return dict(analysis_id=reader.artifact.analysis_id,
                prepared_dataset_id=reader.artifact.prepared_dataset_id,
                prepared_version=reader.artifact.version,
                artifact_sha256=reader.artifact.artifact_sha256,
                rows=rows, chunks=chunks, chunk_size=chunk_size,
                nonnull_counts=counts, source_totals={k:str(v) for k,v in totals.items()},
                examples=examples, rss_start_mb=start, rss_peak_mb=peak,
                rss_end_mb=_rss_mb(), elapsed_seconds=time.perf_counter()-started,
                totals_are_business_validated=False)
