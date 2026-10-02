import json

from core.siconfi.snapshot import save_rreo_year_snapshot


class FakeClient:
    def fetch_rreo_year(self, **kwargs):
        return {
            1: [{"periodo": 1, "cod_conta": "A", "valor": 1}],
            2: [{"periodo": 2, "cod_conta": "B", "valor": 2}],
            3: [],
            4: [{"periodo": 4, "cod_conta": "C", "valor": 3}],
            5: [],
            6: [{"periodo": 6, "cod_conta": "D", "valor": 4}],
        }


def test_save_rreo_year_snapshot_preserves_records_and_manifest(tmp_path):
    result = save_rreo_year_snapshot(
        FakeClient(),
        exercicio=2025,
        anexo="RREO-Anexo 01",
        id_ente=5002704,
        output_dir=tmp_path,
    )

    assert result.period_counts == {1: 1, 2: 1, 3: 0, 4: 1, 5: 0, 6: 1}

    p1 = json.loads(result.files[1].read_text(encoding="utf-8"))
    assert p1["items"] == [{"periodo": 1, "cod_conta": "A", "valor": 1}]
    assert p1["source"] == "STN/Siconfi"

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["total_records"] == 4
    assert manifest["period_counts"]["6"] == 1
    assert len(manifest["period_sha256"]["1"]) == 64
