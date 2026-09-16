"""Fast checks for imports, configuration and principal service wiring."""

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.field_profiler import profile_field
from core.semantic.decision_engine import decide_field
from core.semantic.question_generator import generate_question


def test_main_application_modules_import() -> None:
    import app.main  # noqa: F401
    import streamlit_app  # noqa: F401


def test_repository_initializes(tmp_path) -> None:
    repository = SQLiteAnalysisRepository(tmp_path / "smoke.sqlite3")
    assert repository.database_path.exists()


def test_decision_engine_and_question_generator_execute() -> None:
    field = profile_field("Campo", "campo", ["alfa", "beta", "gama"])
    decision = decide_field(field)
    question = generate_question("Dados", field, decision)
    assert decision.level.value == "ask"
    assert question is not None
