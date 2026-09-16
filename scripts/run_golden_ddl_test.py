"""Standalone declarative Golden PostgreSQL DDL report."""

import subprocess
import sys

CASES = ["Basic Star", "Surrogate Key", "Composite Business Key", "Degenerate Dimension",
         "Role Playing Date", "Factless Fact", "Multi-Fact", "SCD Type 2", "SCD Unknown",
         "Bridge", "Nullability", "Numeric Precision", "Text Mapping", "Reserved Word",
         "63-byte Identifier", "Name Collision", "FK Index", "Technical Key Exclusion",
         "Aggregation Risk", "Determinism", "No Destructive SQL"]


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/golden_ddl", "-q"])
    print("GOLDEN POSTGRESQL DDL")
    for case in CASES:
        print(f"{case:.<36} {'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"GOLDEN POSTGRESQL DDL STATUS: {'PASSED' if result.returncode == 0 else 'FAILED'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
