import json
from unittest.mock import patch

import pytest

from core.siconfi.client import SiconfiClient, SiconfiRreoQuery


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, *args, **kwargs):
        return json.dumps(self.payload).encode("utf-8")


def test_rreo_query_rejects_invalid_bimester():
    with pytest.raises(ValueError, match="entre 1 e 6"):
        SiconfiRreoQuery(exercicio=2025, periodo=7, anexo="RREO-Anexo 01", id_ente=5002704)


def test_build_rreo_url_contains_official_query_parameters():
    client = SiconfiClient()
    url = client.build_rreo_url(
        SiconfiRreoQuery(exercicio=2025, periodo=6, anexo="RREO-Anexo 01", id_ente=5002704)
    )
    assert "/rreo?" in url
    assert "an_exercicio=2025" in url
    assert "nr_periodo=6" in url
    assert "co_tipo_demonstrativo=RREO" in url
    assert "no_anexo=RREO-Anexo+01" in url
    assert "co_esfera=M" in url
    assert "id_ente=5002704" in url


def test_fetch_rreo_preserves_stn_record():
    payload = {
        "items": [
            {
                "exercicio": 2025,
                "demonstrativo": "RREO",
                "periodo": 6,
                "periodicidade": "B",
                "instituicao": "Prefeitura Municipal de Campo Grande - MS",
                "cod_ibge": 5002704,
                "uf": "MS",
                "anexo": "RREO-Anexo 01",
                "esfera": "M",
                "rotulo": "Padrão",
                "coluna": "Até o Bimestre (c)",
                "cod_conta": "ReceitasExcetoIntraOrcamentarias",
                "conta": "RECEITAS (EXCETO INTRA-ORÇAMENTÁRIAS) (I)",
                "valor": 5838073948.78,
            }
        ]
    }
    client = SiconfiClient()
    with patch("urllib.request.urlopen", return_value=_Response(payload)):
        items = client.fetch_rreo(
            SiconfiRreoQuery(exercicio=2025, periodo=6, anexo="RREO-Anexo 01", id_ente=5002704)
        )
    assert items == payload["items"]


def test_fetch_rreo_rejects_invalid_payload():
    client = SiconfiClient()
    with patch("urllib.request.urlopen", return_value=_Response({"unexpected": []})):
        with pytest.raises(ValueError, match="campo 'items'"):
            client.fetch_rreo(
                SiconfiRreoQuery(exercicio=2025, periodo=6, anexo="RREO-Anexo 01", id_ente=5002704)
            )
