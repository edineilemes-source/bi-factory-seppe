import hashlib

from core.bi_mvp.models import DimensionSpec, MeasureSpec, MVPModel, MVPStatus
from core.grain.models import GrainDefinition, GrainReadiness, GrainValidationStatus
from core.prepared.models import PreparedDatasetArtifact


DIMENSION_RULES = {
    "tempo": (["Ano", "Mês", "Dia"], ["Ano", "Mês", "Dia"]),
    "unidade_gestora": (["UG Sigla", "UG Empenho", "UG Liquidação"], ["UG Sigla"]),
    "credor": (["Credor"], ["Credor"]),
    "natureza_despesa": (["Elemento de Despesa", "Item Elemento Despesa", "Grupo de Despesa"],
                         ["Elemento de Despesa", "Item Elemento Despesa", "Grupo de Despesa"]),
    "fonte_recurso": (["Fonte", "GPF Descriçao"], ["Fonte", "GPF Descriçao"]),
    "evento_pagamento": (["Evento Pagamento"], ["Evento Pagamento"]),
}
MEASURES = ["Total Pago", "Liquidado", "Empenhado", "Devolvido", "Estornado"]
IDENTIFIERS = ["Nº Empenho", "Nº Liquidação", "Nº Reserva", "Nº Estorno",
               "Aux Sub Empenho", "Processo", "Nº Contrato", "Ano do Empenho"]


def build_mvp_model(artifact: PreparedDatasetArtifact, grain: GrainDefinition,
                    *, version: int = 1, approved: bool = False,
                    additive_measures: list[str] | None = None,
                    nonnull_counts: dict[str, int] | None = None) -> MVPModel:
    if (grain.status != GrainReadiness.READY_FOR_DIMENSIONAL_MODELING
            or grain.validation_status not in {GrainValidationStatus.CONFIRMED, GrainValidationStatus.CORRECTED}):
        raise ValueError("Human-validated grain is required before MVP modeling.")
    if (grain.analysis_id, grain.source_document_id, grain.prepared_dataset_id, grain.prepared_dataset_version,
            grain.prepared_dataset_fingerprint) != (artifact.analysis_id, artifact.source_document_id,
            artifact.prepared_dataset_id, artifact.version, artifact.fingerprint):
        raise ValueError("Grain and Prepared ownership/version/integrity mismatch.")
    available = {field.source_name: field for field in artifact.schema_fields}
    additive_measures = additive_measures or []
    if set(additive_measures) - (set(MEASURES) & set(available)):
        raise ValueError("Confirmed additive measures must exist in the Prepared schema.")
    dimensions = []
    for name, (attrs, keys) in DIMENSION_RULES.items():
        present_attrs = [x for x in attrs if x in available
                         and (nonnull_counts is None or nonnull_counts.get(x, 0) > 0)]
        present_keys = [x for x in keys if x in present_attrs]
        if present_attrs and present_keys:
            dimensions.append(DimensionSpec(name=name, source_fields=present_attrs,
                                            business_key_fields=present_attrs))
    measures = [MeasureSpec(source_field=name, name=available[name].technical_name,
                            additive_confirmed=name in additive_measures)
                for name in MEASURES if name in available]
    identifiers = [name for name in IDENTIFIERS if name in available]
    identity = "|".join([artifact.analysis_id, artifact.prepared_dataset_id,
                         str(version), grain.grain_id])
    return MVPModel(
        model_id="mvp:" + hashlib.sha256(identity.encode()).hexdigest()[:20],
        version=version, status=MVPStatus.APPROVED if approved else MVPStatus.PROPOSED,
        analysis_id=artifact.analysis_id, source_document_id=artifact.source_document_id,
        prepared_dataset_id=artifact.prepared_dataset_id, prepared_version=artifact.version,
        prepared_fingerprint=artifact.fingerprint,
        prepared_artifact_sha256=artifact.artifact_sha256,
        grain_definition_id=grain.grain_id, grain_description=grain.effective_grain_description,
        dimensions=dimensions, measures=measures, preserved_identifiers=identifiers,
        created_at=grain.validated_at or grain.created_at,
        source_fields={name: field.technical_name for name, field in available.items()},
    )
