"""Exports effective values separately from compact transformation audit data."""

import csv
import io
import json

from core.prepared.models import PreparedDataset


def export_prepared_csv(dataset: PreparedDataset, *, include_source_row_id: bool = True) -> bytes:
    stream = io.StringIO(newline="")
    names: list[str] = []
    seen: dict[str, int] = {}
    for field in dataset.schema_fields:
        count = seen.get(field.source_name, 0) + 1
        seen[field.source_name] = count
        names.append(field.source_name if count == 1 else f"{field.source_name}__{count}")
    header = (["source_row_id"] if include_source_row_id else []) + names
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    for row in dataset.rows:
        values = [row.values.get(field.source_field_id) for field in dataset.schema_fields]
        writer.writerow(([row.source_row_id] if include_source_row_id else []) + values)
    return stream.getvalue().encode("utf-8-sig")


def export_transformations_json(dataset: PreparedDataset) -> bytes:
    payload = {
        "prepared_dataset_id": dataset.prepared_dataset_id,
        "analysis_id": dataset.analysis_id,
        "source_document_id": dataset.source_document_id,
        "version": dataset.version,
        "fingerprint": dataset.fingerprint,
        "summary": dataset.transformation_summary,
        "transformation_count": len(dataset.transformations),
        "transformations": [item.model_dump(mode="json") for item in dataset.transformations],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
