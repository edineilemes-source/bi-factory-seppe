"""Exact Grain candidate discovery over a disk-backed Prepared artifact."""

import hashlib
import itertools
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4

from core.grain.discovery import GrainDiscoveryConfig, _lexical_hypotheses
from core.grain.models import (CandidateStatus, GrainCandidate, GrainClassification,
                               GrainDiscoveryReport, GrainDiscoveryStatus)
from core.prepared.artifact_reader import PreparedDatasetArtifactReader
from core.profiling.models import SemanticRole


GRAIN_ENGINE_VERSION = "artifact-grain-v2.2"


def _qid(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def discover_grain_from_artifact(reader: PreparedDatasetArtifactReader, *,
                                 version: int = 1,
                                 config: GrainDiscoveryConfig | None = None) -> GrainDiscoveryReport:
    """Evaluate bounded candidates exactly while row storage stays on temporary disk."""
    config = config or GrainDiscoveryConfig()
    artifact = reader.artifact
    fields = artifact.schema_fields
    eligible = [field for field in fields
                if field.effective_semantic_role in {SemanticRole.IDENTIFIER, SemanticRole.CODE}
                and field.source_field_id != "source_row_id"
                and field.technical_name != "source_row_id"][:config.max_identifier_fields]
    processes, events = _lexical_hypotheses(fields)
    process = processes[0].name if processes else None
    event = events[0].name if events else None
    source_names = {field.source_field_id: field.source_name for field in eligible}
    selected_names = list(dict.fromkeys(source_names.values()))

    with tempfile.TemporaryDirectory(prefix="bi-grain-") as directory:
        database = Path(directory) / "grain.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            definitions = ",".join(f"{_qid(name)} TEXT" for name in selected_names)
            connection.execute(f"CREATE TABLE prepared ({definitions or '_empty TEXT'})")
            placeholders = ",".join("?" for _ in selected_names)
            names_sql = ",".join(_qid(name) for name in selected_names)
            insert = f"INSERT INTO prepared ({names_sql}) VALUES ({placeholders})"
            if selected_names:
                for chunk in reader.iter_chunks(columns=set(selected_names)):
                    connection.executemany(insert, ([row[name] for name in selected_names] for row in chunk))
            connection.commit()

            candidates: list[GrainCandidate] = []
            theoretical = 0
            for size in range(1, min(config.max_candidate_fields, len(eligible)) + 1):
                if size >= 3 and any(item.uniqueness_ratio >= config.min_uniqueness_for_strong_candidate
                                     and item.confidence >= config.min_confidence for item in candidates):
                    break
                for combination in itertools.combinations(eligible, size):
                    theoretical += 1
                    if len(candidates) >= config.max_candidates:
                        break
                    names = [field.source_name for field in combination]
                    complete_where = " AND ".join(f"{_qid(name)} IS NOT NULL" for name in names)
                    group = ",".join(_qid(name) for name in names)
                    complete = connection.execute(
                        f"SELECT COUNT(*) FROM prepared WHERE {complete_where}").fetchone()[0]
                    distinct = connection.execute(
                        f"SELECT COUNT(*) FROM (SELECT 1 FROM prepared WHERE {complete_where} GROUP BY {group})"
                    ).fetchone()[0]
                    uniqueness = distinct / complete if complete else 0.0
                    coverage = complete / artifact.row_count if artifact.row_count else 0.0
                    null_ratio = (artifact.row_count - complete) / artifact.row_count if artifact.row_count else 1.0
                    optional = all(field.requirement.value in {"optional", "conditional", "unknown"}
                                   for field in combination)
                    semantic_strength = sum(1 if field.effective_semantic_role == SemanticRole.IDENTIFIER
                                            else .7 for field in combination) / len(combination)
                    # Compare conditional uniqueness in two disjoint source partitions.
                    # This observes within-file consistency, not longitudinal business stability.
                    partition_ratios = []
                    for parity in (0, 1):
                        predicate = f"({complete_where}) AND rowid % 2 = {parity}"
                        n = connection.execute(f"SELECT COUNT(*) FROM prepared WHERE {predicate}").fetchone()[0]
                        d = connection.execute(
                            f"SELECT COUNT(*) FROM (SELECT 1 FROM prepared WHERE {predicate} GROUP BY {group})"
                        ).fetchone()[0]
                        partition_ratios.append(d / n if n else 0.0)
                    stability = min(partition_ratios)
                    # Uniqueness is conditional evidence.  Coverage and actual support
                    # are independent signals so a sparse event identifier cannot be
                    # promoted to the global grain of the source.
                    support = min(1.0, complete / max(config.min_complete_rows, 1))
                    confidence = (0.0 if complete == 0 else max(0, min(1,
                        .42 * uniqueness + .33 * coverage + .10 * stability
                        + .10 * semantic_strength + .05 * support
                        - .025 * (len(combination) - 1))))
                    field_ids = [field.source_field_id for field in combination]
                    digest = hashlib.sha256("|".join(field_ids).encode()).hexdigest()[:16]
                    duplicate_count = max(0, complete - distinct)
                    counter = ([f"{duplicate_count} linha(s) ainda repetem a combinação candidata."]
                               if duplicate_count else [])
                    if null_ratio:
                        counter.append(f"{100 * null_ratio:.2f}% das linhas não possuem todos os campos.")
                    compatibility = ("EVENT_SUBSET_ONLY" if coverage < config.min_global_coverage
                                     else "GLOBAL_CANDIDATE_NOT_UNIQUE"
                                     if uniqueness < config.min_uniqueness_for_strong_candidate
                                     else "BUSINESS_COMPATIBILITY_REQUIRES_VALIDATION")
                    if coverage < config.min_global_coverage:
                        counter.append(
                            "Cobertura insuficiente para representar o grão global da fonte; "
                            "o identificador pode caracterizar apenas um subconjunto de eventos.")
                    if complete == 0:
                        counter.append("Não existem linhas completas; não há evidência estatística observada.")
                    candidates.append(GrainCandidate(
                        candidate_id=f"gc:{digest}",
                        human_readable_description=("Uma linha pode representar uma ocorrência "
                                                    f"identificada por {' + '.join(names)}."),
                        candidate_fields=field_ids, inferred_process=process, inferred_event=event,
                        row_count=artifact.row_count, complete_row_count=complete,
                        distinct_count=distinct,
                        duplicate_count=duplicate_count, uniqueness_ratio=round(uniqueness, 6),
                        coverage_ratio=round(coverage, 6),
                        null_ratio=round(null_ratio, 6), stability=round(stability, 6),
                        confidence=round(confidence, 6),
                        semantic_evidence_score=round(semantic_strength, 6),
                        business_process_compatibility=compatibility,
                        evidence=[
                            f"{distinct} combinação(ões) distinta(s) em {complete} linha(s) completas.",
                            f"Unicidade condicional de {100 * uniqueness:.2f}% nas linhas completas.",
                            f"Cobertura de {100 * coverage:.2f}% sobre o dataset total.",
                            "Papel semântico de identificador/código é evidência, não regra de negócio.",
                            "Estabilidade: menor unicidade entre duas partições da fonte; estabilidade temporal não avaliada.",
                            "Compatibilidade com o processo depende de validação humana.",
                        ], counter_evidence=counter,
                    ))
                if len(candidates) >= config.max_candidates:
                    break
        finally:
            connection.close()

    candidates.sort(key=lambda item: (-item.confidence, len(item.candidate_fields), item.candidate_id))
    globally_eligible = [item for item in candidates
                         if (item.complete_row_count or 0) > 0
                         and (item.coverage_ratio or 0) >= config.min_global_coverage
                         and item.uniqueness_ratio >= config.min_uniqueness_for_strong_candidate
                         and item.confidence >= config.min_confidence]
    recommended = globally_eligible[0] if globally_eligible else None
    strong = [item for item in globally_eligible
              if item.uniqueness_ratio >= config.min_uniqueness_for_strong_candidate
              and item.confidence >= config.min_confidence]
    if not recommended:
        classification, status = (GrainClassification.INSUFFICIENT_EVIDENCE,
                                  GrainDiscoveryStatus.INSUFFICIENT_EVIDENCE)
    elif len(strong) >= 2 and abs(strong[0].confidence - strong[1].confidence) <= config.ambiguity_margin:
        a, b = set(strong[0].candidate_fields), set(strong[1].candidate_fields)
        classification = (GrainClassification.SINGLE_GRAIN if a < b or b < a
                          else GrainClassification.AMBIGUOUS_GRAIN)
        status = (GrainDiscoveryStatus.NEEDS_VALIDATION if classification == GrainClassification.SINGLE_GRAIN
                  else GrainDiscoveryStatus.AMBIGUOUS)
    elif recommended.confidence >= config.min_confidence:
        classification, status = GrainClassification.SINGLE_GRAIN, GrainDiscoveryStatus.NEEDS_VALIDATION
    else:
        classification, status = (GrainClassification.INSUFFICIENT_EVIDENCE,
                                  GrainDiscoveryStatus.INSUFFICIENT_EVIDENCE)
    if recommended:
        recommended.status = CandidateStatus.RECOMMENDED
    return GrainDiscoveryReport(
        grain_discovery_report_id=str(uuid4()), source_document_id=artifact.source_document_id,
        prepared_dataset_id=artifact.prepared_dataset_id, prepared_dataset_version=artifact.version,
        prepared_dataset_fingerprint=artifact.fingerprint, analysis_id=artifact.analysis_id,
        status=status, dataset_row_count=artifact.row_count, candidate_count=len(candidates),
        grain_classification=classification, process_candidates=processes, event_candidates=events,
        grain_candidates=candidates, recommended_candidate_id=(recommended.candidate_id if recommended else None),
        confidence=(recommended.confidence if recommended else 0), requires_user_validation=True,
        candidate_limit_configured=config.max_candidates, candidates_truncated=theoretical > len(candidates),
        version=version, engine_version=GRAIN_ENGINE_VERSION,
    )
