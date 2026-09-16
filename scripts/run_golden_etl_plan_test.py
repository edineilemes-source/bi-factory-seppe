"""Standalone Golden Dimensional ETL Plan report."""

import subprocess
import sys

CASES = ["Basic Dimension + Fact", "Business Key Lookup", "Unknown Member",
         "Required Dimension Failure", "SCD Type 1", "SCD Type 2", "Role Playing Date",
         "Factless Fact", "Multi-Fact", "Bridge", "Reconciliation", "Non-Additive",
         "Leading Zero", "Precision Safety", "Rejection", "Idempotency", "Restartability",
         "Load Batch", "Dependency Cycle", "Field Coverage", "No Silent Data Loss"]


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/golden_etl_plan", "-q"])
    print("GOLDEN DIMENSIONAL ETL PLAN")
    for case in CASES:
        print(f"{case:.<36} {'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"GOLDEN ETL PLAN STATUS: {'PASSED' if result.returncode == 0 else 'FAILED'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
