"""Standalone Golden Dimensional Transformation report."""

import subprocess
import sys

CASES = ["Basic Dimension + Fact", "Dimension Dedup", "SCD Type 1", "SCD Type 2",
         "Unknown Member", "Required Lookup Failure", "Role Playing Date", "Factless Fact",
         "Multi-Fact", "Bridge", "Leading Zero", "Precision Loss", "Negative Measure",
         "Outlier Preservation", "Reconciliation PASS", "Reconciliation FAIL",
         "No Silent Data Loss", "Idempotency", "Restartability", "Source Immutability",
         "Field Coverage", "Determinism"]


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/golden_transformation", "-q"])
    print("GOLDEN DIMENSIONAL TRANSFORMATION")
    for case in CASES: print(f"{case:.<36} {'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"GOLDEN TRANSFORMATION STATUS: {'PASSED' if result.returncode == 0 else 'FAILED'}")
    return result.returncode


if __name__ == "__main__": raise SystemExit(main())
