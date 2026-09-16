"""Human-readable golden quality gate."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.golden_quality.pipeline import expectations, golden_quality_result

report = golden_quality_result()
expected = expectations()
kinds = {issue.issue_type.value for issue in report.issues}
missing = set(expected["required_issue_types"]) - kinds
if missing:
    raise SystemExit(f"GOLDEN DATA QUALITY: FAIL (missing={sorted(missing)})")
print(f"GOLDEN DATA QUALITY: PASS | cases=10 | issues={report.issues_count} | score={report.score:.2f}")
