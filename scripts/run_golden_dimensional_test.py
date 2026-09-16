"""Standalone Golden Dimensional report."""

import subprocess
import sys

CASES = ["Transaction Fact", "Dimension Attributes", "Degenerate Dimension",
         "Role Playing Date", "Aggregation Risk", "Factless Fact", "Multi-Grain",
         "Junk Dimension", "Quality Dependency", "Not Evaluated Field",
         "Technical Key Exclusion", "Field Coverage"]

def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/golden_dimensional", "-q"])
    print("GOLDEN DIMENSIONAL DISCOVERY")
    for case in CASES:
        print(f"{case:.<36} {'PASS' if result.returncode == 0 else 'FAIL'}")
    print(f"GOLDEN DIMENSIONAL STATUS: {'PASSED' if result.returncode == 0 else 'FAILED'}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
