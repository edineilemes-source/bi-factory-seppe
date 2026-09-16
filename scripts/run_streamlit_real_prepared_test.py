#!/usr/bin/env python3
"""Exercise the real Prepared button through Streamlit's component test runtime."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest


ANALYSIS_ID = "ca5cf2d7-98d8-4404-a5cd-916eda0810db"


def main() -> None:
    app = AppTest.from_file("streamlit_app.py", default_timeout=360).run()
    if list(app.exception):
        raise RuntimeError(list(app.exception))
    app.button(key=f"continue_workspace_{ANALYSIS_ID}").click().run(timeout=360)
    if app.session_state["current_analysis_id"] != ANALYSIS_ID:
        raise RuntimeError("A análise explícita não foi carregada")
    generate = next(button for button in app.button
                    if button.label in {"GERAR DATASET PREPARADO", "Gerar nova versão"})
    generate.click().run(timeout=360)
    if list(app.exception):
        raise RuntimeError(list(app.exception))
    artifact = app.session_state["current_prepared_artifact"]
    if artifact is None or artifact.generation_status.value != "COMPLETED":
        raise RuntimeError("Prepared Dataset não concluiu pela UI")
    if app.session_state["current_prepared_dataset"] is not None:
        raise RuntimeError("Sessão reteve Prepared Dataset completo")
    print("STREAMLIT REAL TEST: PASS")
    print(f"ANALYSIS ID: {ANALYSIS_ID}")
    print(f"ROWS: {artifact.row_count}")
    print(f"FIELDS: {artifact.field_count}")
    print(f"STATUS: {artifact.generation_status.value}")
    print("SESSION MEMORY SAFETY: PASS")


if __name__ == "__main__":
    main()
