from __future__ import annotations

from pathlib import Path

from onpe_mcp import storage as storage_module
from onpe_mcp.storage import DataStore


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="cp1252")


def test_bootstrap_2021_and_queries(tmp_path: Path) -> None:
    repo_2021 = tmp_path / "peruvoto2021"
    file_1v = repo_2021 / "data" / "Resultados_1ra_vuelta_Version_PCM.csv"
    file_2v = repo_2021 / "data" / "Resultados_2da_vuelta_Version_PCM.csv"

    _write_csv(
        file_1v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_P3;VOTOS_P4;VOTOS_P5;VOTOS_P6;VOTOS_P7;VOTOS_P8;VOTOS_P9;VOTOS_P10;VOTOS_P11;VOTOS_P12;VOTOS_P13;VOTOS_P14;VOTOS_P15;VOTOS_P16;VOTOS_P17;VOTOS_P18;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                # VOTOS_P13 → Rafael López Aliaga (RL, Renovación Popular)
                # VOTOS_P11 → Keiko Fujimori (K, Fuerza Popular)
                # VOTOS_P7  → Hernando de Soto (AP2, Avanza País)
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;18;300;10;5;0;0;0;0;8;0;0;0;2;0;20;0;0;0;0;0;1;1;0',
                '"150102";"LIMA";"LIMA";"ANCON";"PRESIDENCIAL";"000002";"CONTABILIZADA";;18;250;2;1;0;0;0;0;4;0;0;0;16;0;3;0;0;0;0;0;0;1;0',
            ]
        ),
    )
    _write_csv(
        file_2v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;2;300;90;95;2;3;0',
                '"150102";"LIMA";"LIMA";"ANCON";"PRESIDENCIAL";"000002";"CONTABILIZADA";;2;250;80;60;1;2;0',
            ]
        ),
    )

    store = DataStore(tmp_path / "db")
    result = store.bootstrap_elecciones_2021(repo_2021, force=True)
    assert result["skipped"] is False
    assert result["vuelta1_mesas"] == 2
    assert result["vuelta2_mesas"] == 2
    assert store.total_mesas_2021(1) == 2
    assert store.total_mesas_2021(2) == 2

    mesa = store.get_mesa_2021_from_local("000001", vuelta=1)
    assert mesa is not None
    assert mesa["departamento"] == "LIMA"
    assert mesa["votos_emitidos"] > 0
    assert mesa["votos"][0]["votos"] >= mesa["votos"][1]["votos"]

    agg = store.aggregate_votes_2021(vuelta=1, geo_query="Lima", top_n=3)
    assert agg["nivel"] in {"departamento", "provincia", "distrito"}
    assert len(agg["top"]) == 3

    cand = store.get_candidate_votes_2021(vuelta=1, candidate_query="Rafael Lopez Aliaga", geo_query="Lima")
    assert cand is not None
    assert cand["partido_id"] == "RL"
    assert cand["votos"] > 0


def test_bootstrap_2021_auto_rehydrates_on_party_map_change(
    tmp_path: Path, monkeypatch
) -> None:
    """If `_PARTY_MAP_2021_1V` changes between runs, the next bootstrap must
    auto-re-hydrate even when called with `force=False` — otherwise pulled
    fixes to the mapping would be silently ignored when SQLite already has
    rows from a previous (stale) run.
    """
    repo_2021 = tmp_path / "peruvoto2021"
    file_1v = repo_2021 / "data" / "Resultados_1ra_vuelta_Version_PCM.csv"
    file_2v = repo_2021 / "data" / "Resultados_2da_vuelta_Version_PCM.csv"

    _write_csv(
        file_1v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_P3;VOTOS_P4;VOTOS_P5;VOTOS_P6;VOTOS_P7;VOTOS_P8;VOTOS_P9;VOTOS_P10;VOTOS_P11;VOTOS_P12;VOTOS_P13;VOTOS_P14;VOTOS_P15;VOTOS_P16;VOTOS_P17;VOTOS_P18;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;18;300;10;5;0;0;0;0;8;0;0;0;2;0;20;0;0;0;0;0;1;1;0',
            ]
        ),
    )
    _write_csv(
        file_2v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;2;300;90;95;2;3;0',
            ]
        ),
    )

    store = DataStore(tmp_path / "db")
    first = store.bootstrap_elecciones_2021(repo_2021, force=True)
    assert first["skipped"] is False
    first_fp = first["fingerprint"]

    # Same code, second call → must skip (cache hit).
    second = store.bootstrap_elecciones_2021(repo_2021, force=False)
    assert second["skipped"] is True
    assert second["fingerprint"] == first_fp

    # Mutate the in-code map to simulate pulling a fix that changes candidates.
    original_map = dict(storage_module._PARTY_MAP_2021_1V)
    mutated_map = dict(original_map)
    mutated_map["VOTOS_P11"] = ("K", "Fuerza Popular", "Keiko Fujimori UPDATED")
    monkeypatch.setattr(storage_module, "_PARTY_MAP_2021_1V", mutated_map)

    # Third call without force → must auto-re-hydrate due to fingerprint drift.
    third = store.bootstrap_elecciones_2021(repo_2021, force=False)
    assert third["skipped"] is False, "stale cache should have been auto-refreshed"
    assert third["fingerprint"] != first_fp

    # Verify the new candidate name landed in SQLite.
    cand = store.get_candidate_votes_2021(
        vuelta=1, candidate_query="Keiko Fujimori UPDATED", geo_query="Lima"
    )
    assert cand is not None
    assert cand["partido_id"] == "K"


def _seed_minimal_2021(tmp_path: Path) -> DataStore:
    """Helper: builds a tiny but valid 2021 dataset for export tests."""
    repo_2021 = tmp_path / "peruvoto2021"
    file_1v = repo_2021 / "data" / "Resultados_1ra_vuelta_Version_PCM.csv"
    file_2v = repo_2021 / "data" / "Resultados_2da_vuelta_Version_PCM.csv"
    _write_csv(
        file_1v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_P3;VOTOS_P4;VOTOS_P5;VOTOS_P6;VOTOS_P7;VOTOS_P8;VOTOS_P9;VOTOS_P10;VOTOS_P11;VOTOS_P12;VOTOS_P13;VOTOS_P14;VOTOS_P15;VOTOS_P16;VOTOS_P17;VOTOS_P18;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                # P11=K, P13=RL, P16=PC, P18=APP (las columnas mapeadas correctamente)
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;18;300;0;0;0;0;0;0;0;0;0;0;20;0;15;0;0;30;0;5;1;1;0',
                '"150102";"LIMA";"LIMA";"ANCON";"PRESIDENCIAL";"900001";"CONTABILIZADA";;18;250;0;0;0;0;0;0;0;0;0;0;10;0;5;0;0;40;0;3;0;1;0',
                '"080101";"CUSCO";"CUSCO";"CUSCO";"PRESIDENCIAL";"000002";"CONTABILIZADA";;18;200;0;0;0;0;0;0;0;0;0;0;5;0;3;0;0;50;0;2;1;1;0',
            ]
        ),
    )
    _write_csv(
        file_2v,
        "\n".join(
            [
                "UBIGEO;DEPARTAMENTO;PROVINCIA;DISTRITO;TIPO_ELECCION;MESA_DE_VOTACION;DESCRIP_ESTADO_ACTA;TIPO_OBSERVACION;N_CVAS;N_ELEC_HABIL;VOTOS_P1;VOTOS_P2;VOTOS_VB;VOTOS_VN;VOTOS_VI",
                # P1=PC, P2=K
                '"150101";"LIMA";"LIMA";"LIMA";"PRESIDENCIAL";"000001";"CONTABILIZADA";;2;300;80;120;3;5;0',
                '"150102";"LIMA";"LIMA";"ANCON";"PRESIDENCIAL";"900001";"CONTABILIZADA";;2;250;90;60;2;4;0',
                '"080101";"CUSCO";"CUSCO";"CUSCO";"PRESIDENCIAL";"000002";"CONTABILIZADA";;2;200;120;30;2;3;0',
            ]
        ),
    )
    store = DataStore(tmp_path / "db")
    store.bootstrap_elecciones_2021(repo_2021, force=True)
    return store


def test_export_mesas_2021_basic(tmp_path: Path) -> None:
    store = _seed_minimal_2021(tmp_path)
    out = store.export_mesas_2021(vuelta=1)
    assert out["vuelta"] == 1
    assert out["total"] == 3
    assert out["returned"] == 3
    assert out["has_more"] is False
    assert {r["codigo_mesa"] for r in out["rows"]} == {"000001", "000002", "900001"}
    assert "electores_habiles" in out["schema"]
    # Check a sample
    sample = next(r for r in out["rows"] if r["codigo_mesa"] == "000001")
    assert sample["departamento"] == "LIMA"
    assert sample["electores_habiles"] == 300
    # P11(K)=20, P13(RL)=15, P16(PC)=30, P18(APP)=5 → 70
    assert sample["votos_validos"] == 70


def test_export_mesas_2021_with_filters_and_pagination(tmp_path: Path) -> None:
    store = _seed_minimal_2021(tmp_path)
    # filter by departamento
    out_lima = store.export_mesas_2021(vuelta=1, departamento="LIMA")
    assert out_lima["total"] == 2
    # case-insensitive
    out_lima_lower = store.export_mesas_2021(vuelta=1, departamento="lima")
    assert out_lima_lower["total"] == 2
    # filter by mesa prefix
    out_900 = store.export_mesas_2021(vuelta=1, mesa_prefix="9")
    assert out_900["total"] == 1
    assert out_900["rows"][0]["codigo_mesa"] == "900001"
    # pagination
    page1 = store.export_mesas_2021(vuelta=1, limit=2, offset=0)
    page2 = store.export_mesas_2021(vuelta=1, limit=2, offset=2)
    assert page1["returned"] == 2 and page1["has_more"] is True
    assert page2["returned"] == 1 and page2["has_more"] is False


def test_export_votos_2021_joins_geo_and_supports_partido_filter(tmp_path: Path) -> None:
    store = _seed_minimal_2021(tmp_path)
    out = store.export_votos_2021(vuelta=2)
    # 3 mesas × 2 partidos = 6 rows
    assert out["total"] == 6
    assert all(r["ubigeo"] for r in out["rows"])
    assert all(r["departamento"] for r in out["rows"])
    # Filter by partido_id
    out_pc = store.export_votos_2021(vuelta=2, partido_ids=["PC"])
    assert out_pc["total"] == 3
    assert all(r["partido_id"] == "PC" for r in out_pc["rows"])
    # Check that geo filter + partido filter work together
    out_lima_pc = store.export_votos_2021(vuelta=2, partido_ids=["PC"], departamento="LIMA")
    assert out_lima_pc["total"] == 2


def test_export_partidos_2021(tmp_path: Path) -> None:
    store = _seed_minimal_2021(tmp_path)
    # both rounds
    all_p = store.export_partidos_2021()
    assert all_p["total"] == 18 + 2
    # 1V only
    one = store.export_partidos_2021(vuelta=1)
    assert one["total"] == 18
    assert all(r["vuelta"] == 1 for r in one["rows"])
    # 2V only
    two = store.export_partidos_2021(vuelta=2)
    assert two["total"] == 2
    pids = {r["partido_id"] for r in two["rows"]}
    assert pids == {"PC", "K"}


def test_summary_2021_aggregations(tmp_path: Path) -> None:
    store = _seed_minimal_2021(tmp_path)
    s2 = store.summary_2021(vuelta=2)
    assert s2["vuelta"] == 2
    assert s2["mesas"] == 3
    # 80+120+3+5 + 90+60+2+4 + 120+30+2+3 = 519
    assert s2["votos_emitidos"] == 519
    # validos = 80+120 + 90+60 + 120+30 = 500
    assert s2["votos_validos"] == 500
    assert s2["validez_pct"] == 500 / 519 * 100.0
    # PC = 80+90+120 = 290; K = 120+60+30 = 210
    by_pid = {r["partido_id"]: r["total_votos"] for r in s2["por_partido"]}
    assert by_pid["PC"] == 290
    assert by_pid["K"] == 210
    # pct must sum ~100% over candidates
    pcts = [r["pct_validos"] for r in s2["por_partido"]]
    assert abs(sum(pcts) - 100.0) < 1e-6

