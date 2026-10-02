"""Minimal client for the official Siconfi open-data API.

Phase 1 intentionally preserves the STN payload semantics.  No fiscal concept
mapping, aggregation or dashboard transformation happens here.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


SICONFI_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"


@dataclass(frozen=True)
class SiconfiRreoQuery:
    exercicio: int
    periodo: int
    anexo: str
    id_ente: int
    esfera: str = "M"
    tipo_demonstrativo: str = "RREO"

    def __post_init__(self) -> None:
        if not 1 <= self.periodo <= 6:
            raise ValueError("RREO bimestral exige período entre 1 e 6.")

    def params(self) -> dict[str, Any]:
        return {
            "an_exercicio": self.exercicio,
            "nr_periodo": self.periodo,
            "co_tipo_demonstrativo": self.tipo_demonstrativo,
            "no_anexo": self.anexo,
            "co_esfera": self.esfera,
            "id_ente": self.id_ente,
        }


class SiconfiClient:
    def __init__(self, base_url: str = SICONFI_BASE_URL, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def build_rreo_url(self, query: SiconfiRreoQuery) -> str:
        return f"{self.base_url}/rreo?{urllib.parse.urlencode(query.params())}"

    def fetch_rreo(self, query: SiconfiRreoQuery) -> list[dict[str, Any]]:
        url = self.build_rreo_url(query)
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "bi-factory-seppe/1.0"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.load(response)

        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("Resposta Siconfi inválida: campo 'items' ausente ou não é lista.")
        return items

    def fetch_rreo_year(
        self,
        *,
        exercicio: int,
        anexo: str,
        id_ente: int,
        esfera: str = "M",
    ) -> dict[int, list[dict[str, Any]]]:
        """Fetch all six official RREO bimesters without changing STN records."""
        return {
            periodo: self.fetch_rreo(
                SiconfiRreoQuery(
                    exercicio=exercicio,
                    periodo=periodo,
                    anexo=anexo,
                    id_ente=id_ente,
                    esfera=esfera,
                )
            )
            for periodo in range(1, 7)
        }
