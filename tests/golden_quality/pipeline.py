import json
from pathlib import Path

from core.ingestion.file_loader import load_tabular_file
from core.profiling.models import ProjectContext, SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.engine import analyze_data_quality
from core.semantic.validation_service import create_validation_report

ROOT = Path(__file__).parent


def golden_quality_result():
    content = (ROOT / "dataset.csv").read_bytes()
    workbook = load_tabular_file("dataset.csv", content)
    semantic = create_validation_report(profile_workbook(workbook, ProjectContext()))
    semantic.analysis_id = "golden-quality"
    semantic.source_document_id = "sha256:golden-quality"
    roles = {
        "identificador": SemanticRole.IDENTIFIER, "medida": SemanticRole.MEASURE,
        "categoria": SemanticRole.CATEGORY, "data": SemanticRole.DATE,
        "descricao": SemanticRole.DESCRIPTION,
    }
    for item in semantic.validated_semantics:
        item.validated_role = roles[item.technical_name]
    return analyze_data_quality(workbook, semantic)


def expectations():
    return json.loads((ROOT / "expected.json").read_text(encoding="utf-8"))
