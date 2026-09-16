"""Standalone declarative Golden Star Schema Contract report."""

import subprocess
import sys

CASES = ["Transaction Star", "Degenerate Identifier", "Role Playing Date", "Factless Fact",
         "Multi-Fact", "Many-to-Many", "SCD Unknown", "SCD Type 2 Contract",
         "Aggregation Risk", "Business Key", "Technical Key Exclusion", "Nullability",
         "Name Collision", "Field Coverage"]


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/golden_star_schema", "-q"])
    print("GOLDEN STAR SCHEMA CONTRACT")
    for case in CASES:
        print(f"{case:.<36} {'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"GOLDEN STAR SCHEMA STATUS: {'PASSED' if result.returncode == 0 else 'FAILED'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
