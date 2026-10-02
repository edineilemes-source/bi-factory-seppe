"""Persistence helpers for raw Siconfi RREO snapshots.

The raw payload is stored exactly as returned by the API, grouped by period.
No fiscal interpretation happens here.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.siconfi.client import SiconfiClient


@dataclass(frozen=True)
class RreoSnapshotResult:
    exercicio: int
    anexo: str
    id_ente: int
    output_dir: Path
    period_counts: dict[int, int]
    files: dict[int, Path]
    manifest_path: Path


def _canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def save_rreo_year_snapshot(
    client: SiconfiClient,
    *,
    exercicio: int,
    anexo: str,
    id_ente: int,
    output_dir: str | Path,
    esfera: str = "M",
) -> RreoSnapshotResult:
    """Download the six RREO periods and persist untouched STN records plus a manifest."""
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    periods = client.fetch_rreo_year(
        exercicio=exercicio,
        anexo=anexo,
        id_ente=id_ente,
        esfera=esfera,
    )

    period_counts: dict[int, int] = {}
    files: dict[int, Path] = {}
    period_sha256: dict[int, str] = {}

    for periodo, items in periods.items():
        period_counts[periodo] = len(items)
        payload = {
            "source": "STN/Siconfi",
            "exercicio": exercicio,
            "periodo": periodo,
            "periodicidade": "B",
            "anexo": anexo,
            "id_ente": id_ente,
            "esfera": esfera,
            "items": items,
        }
        raw = _canonical_json_bytes(payload)
        path = root / f"rreo-{exercicio}-p{periodo}-anexo01.json"
        path.write_bytes(raw + b"\n")
        files[periodo] = path
        period_sha256[periodo] = hashlib.sha256(raw).hexdigest()

    manifest = {
        "source": "STN/Siconfi",
        "exercicio": exercicio,
        "anexo": anexo,
        "id_ente": id_ente,
        "esfera": esfera,
        "period_counts": period_counts,
        "period_sha256": period_sha256,
        "total_records": sum(period_counts.values()),
    }
    manifest_path = root / f"rreo-{exercicio}-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return RreoSnapshotResult(
        exercicio=exercicio,
        anexo=anexo,
        id_ente=id_ente,
        output_dir=root,
        period_counts=period_counts,
        files=files,
        manifest_path=manifest_path,
    )
