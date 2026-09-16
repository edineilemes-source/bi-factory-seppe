"""Human-readable CI gate for the prepared dataset."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.prepared.service import prepare_dataset
from tests.golden_prepared.pipeline import golden_prepared_inputs

workbook, semantic, quality = golden_prepared_inputs()
result = prepare_dataset(workbook, semantic, quality)
assert result.row_count == 4
assert result.field_count == 8
print("GOLDEN PREPARED DATASET = PASS")
print(f"SOURCE ROWS = {result.statistics['source_row_count']}")
print(f"PREPARED ROWS = {result.row_count}")
print(f"SOURCE FIELDS = {result.statistics['source_field_count']}")
print(f"PREPARED FIELDS = {result.field_count}")
print(f"TRANSFORMATIONS = {len(result.transformations)}")
print(f"QUALITY GATE = {result.status.value}")
