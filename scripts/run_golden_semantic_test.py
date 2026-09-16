"""Print a human-readable report for the permanent Golden Semantic Test."""

from collections import Counter
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.golden.expected_semantics import EXPECTED_REQUIRED_QUESTIONS, EXPECTED_SEMANTICS
from tests.golden.pipeline import run_golden_pipeline


def main() -> None:
    _, report, fields, decisions = run_golden_pipeline()
    counts = Counter(decision.level.value for decision in decisions.values())
    asked = {question.technical_name for question in report.questions}
    print("GOLDEN SEMANTIC TEST")
    print(f"Fields analyzed: {len(fields)}")
    print(f"AUTO_ACCEPT: {counts['auto_accept']}")
    print(f"CONFIRM: {counts['confirm']}")
    print(f"ASK: {counts['ask']}")
    print(f"Required questions: {len(asked)}")
    for name, expected in EXPECTED_SEMANTICS.items():
        field = fields[name]
        decision = decisions[name]
        passed = (
            field.semantic_role_candidate.value == expected["role"]
            and decision.level.value == expected["decision"]
            and (name in asked) == expected["required_question"]
        )
        print(f"{'PASS' if passed else 'FAIL'} {name:<24} {field.semantic_role_candidate.value:<16} {decision.level.value.upper()}")
        if not passed:
            raise SystemExit(1)
    budget_passed = len(asked) == EXPECTED_REQUIRED_QUESTIONS
    print(f"QUESTION BUDGET: {'PASS' if budget_passed else 'FAIL'} ({len(asked)}/{EXPECTED_REQUIRED_QUESTIONS})")
    if not budget_passed:
        raise SystemExit(1)
    print("GOLDEN SEMANTIC TEST: PASSED")


if __name__ == "__main__":
    main()
