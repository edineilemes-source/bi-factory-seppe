"""Profiling -> validation -> persistence -> quality integration gate."""

from core.persistence.sqlite_repository import SQLiteAnalysisRepository
from core.profiling.models import SemanticRole
from core.profiling.workbook_profiler import profile_workbook
from core.quality.engine import analyze_data_quality
from core.semantic.models import ValidationStatus
from tests.golden.fixtures import golden_loaded_workbook


def test_persisted_validated_semantic_role_is_the_effective_quality_role(tmp_path):
    workbook = golden_loaded_workbook()
    profile = profile_workbook(workbook)
    repository = SQLiteAnalysisRepository(tmp_path / "integration.sqlite3")
    document = repository.register_document(b"semantic-quality", "golden.csv")
    analysis = repository.create_analysis(document.source_document_id, profile)
    validation = next(item for item in analysis.report.validated_semantics
                      if item.technical_name == "aux_sub_empenho")
    assert validation.original_hypothesis == SemanticRole.IDENTIFIER
    validation.validated_role = SemanticRole.IDENTIFIER
    validation.validation_status = ValidationStatus.USER_CONFIRMED
    repository.save_report(analysis.report)

    persisted = repository.get_analysis(analysis.analysis_id)
    assert persisted is not None
    quality = analyze_data_quality(workbook, persisted.report)
    repository.save_quality_report(quality)
    restored = repository.get_quality_report(analysis.analysis_id)
    field = next(item for item in restored.field_summaries
                 if item.source_field_id.endswith("::aux_sub_empenho"))
    assert field.effective_semantic_role == SemanticRole.IDENTIFIER
    assert field.effective_semantic_role != SemanticRole.MEASURE
