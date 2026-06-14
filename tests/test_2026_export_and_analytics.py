"""Tests for the 2026 raw-data + analytics storage methods.

Builds a tiny but realistic SQLite fixture with mesas_data/votos/agrupaciones
(1V) + mesas_sv/votos_sv/agrupaciones_sv/ubicaciones_sv (2V) and exercises
all 17 new methods end-to-end.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from onpe_mcp.storage import DataStore


# ── Fixture: tiny but valid 2026 dataset ────────────────────────────────────


@pytest.fixture()
def store(tmp_path: Path) -> DataStore:
    ds = DataStore(tmp_path / "db")
    now = ds.now_iso()
    with ds._connect() as conn:
        # 2026 1V — 3 mesas, 2 dptos, 2 partidos reales + blanco/nulo
        conn.executemany(
            """INSERT INTO mesas_data (codigo_mesa, ubigeo, local_votacion,
               electores_habiles, votos_emitidos, votos_validos,
               blancos, nulos, impugnados, estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ("000001", "150101", "Local A", 300, 250, 230, 10, 10, 0,
                 "Contabilizada", now),
                ("000002", "150101", "Local B", 280, 220, 200, 12, 8, 0,
                 "Contabilizada", now),
                ("900100", "010603", "Local C", 250, 200, 180, 15, 5, 0,
                 "Contabilizada", now),
            ],
        )
        conn.executemany(
            "INSERT INTO agrupaciones (partido_id, nombre, fetched_at) VALUES (?,?,?)",
            [
                ("10", "JUNTOS POR EL PERÚ", now),
                ("8", "FUERZA POPULAR", now),
                ("80", "VOTOS EN BLANCO", now),
                ("81", "VOTOS NULOS", now),
            ],
        )
        conn.executemany(
            "INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at) "
            "VALUES (?,?,?,?)",
            [
                ("000001", "10", 130, now), ("000001", "8", 100, now),
                ("000002", "10", 110, now), ("000002", "8", 90, now),
                ("900100", "10", 150, now), ("900100", "8", 30, now),
            ],
        )
        # Geo enrichment via ubigeo_reniec (source of truth in cache; ubigeo_onpe_api
        # requires explicit sync via onpe_sync_domestic_catalog and is empty otherwise).
        conn.executemany(
            """INSERT INTO ubigeo_reniec (ubigeo, distrito, provincia, departamento,
               distrito_norm, provincia_norm, departamento_norm, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                ("150101", "LIMA", "LIMA", "LIMA", "lima", "lima", "lima", now),
                ("010603", "EL CENEPA", "CONDORCANQUI", "AMAZONAS",
                 "el cenepa", "condorcanqui", "amazonas", now),
            ],
        )
        # 2026 SV — same 3 mesas
        conn.executemany(
            """INSERT INTO mesas_sv (codigo_mesa, id_ubigeo, nombre_local,
               id_ambito, electores_habiles, votos_emitidos, votos_validos,
               total_asistentes, codigo_estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                ("000001", "150101", "Local A", 1, 300, 250, 240, 250, "C", now),
                ("000002", "150101", "Local B", 1, 280, 220, 215, 220, "C", now),
                ("900100", "010603", "Local C", 1, 250, 200, 195, 200, "C", now),
            ],
        )
        conn.executemany(
            "INSERT INTO agrupaciones_sv (partido_id, nombre, fetched_at) VALUES (?,?,?)",
            [
                ("10", "JUNTOS POR EL PERÚ", now),
                ("8", "FUERZA POPULAR", now),
                ("80", "VOTOS EN BLANCO", now),
                ("81", "VOTOS NULOS", now),
            ],
        )
        conn.executemany(
            "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) "
            "VALUES (?,?,?,?)",
            [
                ("000001", "10", 140, now), ("000001", "8", 100, now),
                ("000002", "10", 115, now), ("000002", "8", 100, now),
                ("900100", "10", 170, now), ("900100", "8", 25, now),
            ],
        )
        conn.executemany(
            """INSERT INTO ubicaciones_sv (ubigeo, ambito, departamento, provincia,
               distrito, continente, pais, ciudad, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                ("150101", "NACIONAL", "LIMA", "LIMA", "LIMA", "", "", "", now),
                ("010603", "NACIONAL", "AMAZONAS", "CONDORCANQUI", "EL CENEPA",
                 "", "", "", now),
            ],
        )
        # foreign_catalog (vacío salvo 1 fila para test list_foreign_geo)
        conn.execute(
            "INSERT INTO foreign_catalog (ubigeo, continente, pais, ciudad, fetched_at) "
            "VALUES (?,?,?,?,?)",
            ("250101", "EUROPA", "ESPAÑA", "MADRID", now),
        )
    return ds


# ── 2026 1V export ──────────────────────────────────────────────────────────


def test_export_mesas_2026_1v_basic(store: DataStore) -> None:
    out = store.export_mesas_2026_1v()
    assert out["vuelta"] == 1
    assert out["total"] == 3
    assert out["has_more"] is False
    cods = {r["codigo_mesa"] for r in out["rows"]}
    assert cods == {"000001", "000002", "900100"}
    sample = next(r for r in out["rows"] if r["codigo_mesa"] == "000001")
    assert sample["departamento"] == "LIMA"
    assert sample["distrito"] == "LIMA"
    assert sample["electores_habiles"] == 300


def test_export_mesas_2026_1v_filters(store: DataStore) -> None:
    # mesa_prefix
    out_900 = store.export_mesas_2026_1v(mesa_prefix="9")
    assert out_900["total"] == 1
    assert out_900["rows"][0]["codigo_mesa"] == "900100"
    # departamento (case-insensitive)
    out_amazonas = store.export_mesas_2026_1v(departamento="amazonas")
    assert out_amazonas["total"] == 1
    assert out_amazonas["rows"][0]["departamento"] == "AMAZONAS"
    # estado_acta
    out_cont = store.export_mesas_2026_1v(estado_acta="Contabilizada")
    assert out_cont["total"] == 3


def test_export_mesas_2026_1v_pagination(store: DataStore) -> None:
    page1 = store.export_mesas_2026_1v(limit=2, offset=0)
    page2 = store.export_mesas_2026_1v(limit=2, offset=2)
    assert page1["returned"] == 2 and page1["has_more"] is True
    assert page2["returned"] == 1 and page2["has_more"] is False


def test_export_votos_2026_1v_joins_geo_and_partido(store: DataStore) -> None:
    out = store.export_votos_2026_1v()
    # 3 mesas × 2 partidos = 6 rows
    assert out["total"] == 6
    assert all(r["nombre_partido"] for r in out["rows"])
    assert all(r["departamento"] for r in out["rows"])
    # partido filter
    out_10 = store.export_votos_2026_1v(partido_ids=["10"])
    assert out_10["total"] == 3
    assert all(r["partido_id"] == "10" for r in out_10["rows"])
    # combined geo + partido
    out_lima_10 = store.export_votos_2026_1v(partido_ids=["10"], departamento="LIMA")
    assert out_lima_10["total"] == 2


def test_export_partidos_2026_1v(store: DataStore) -> None:
    out = store.export_partidos_2026_1v()
    assert out["total"] == 4
    assert out["candidatos"] == 2  # 10 + 8
    by_pid = {r["partido_id"]: r for r in out["rows"]}
    assert "candidato" in by_pid["10"]
    assert by_pid["10"]["candidato"] == ""
    assert by_pid["10"]["is_candidate"] is True
    assert by_pid["80"]["is_candidate"] is False


def test_summary_2026_1v(store: DataStore) -> None:
    s = store.summary_2026_1v()
    assert s["vuelta"] == 1
    assert s["mesas"] == 3
    assert s["electores_habiles"] == 830  # 300+280+250
    assert s["votos_emitidos"] == 670     # 250+220+200
    assert s["votos_validos"] == 610      # 230+200+180
    by_pid = {r["partido_id"]: r for r in s["por_partido"]}
    # JxP = 130+110+150 = 390 ; FP = 100+90+30 = 220
    assert by_pid["10"]["total_votos"] == 390
    assert by_pid["8"]["total_votos"] == 220


# ── 2026 SV export ──────────────────────────────────────────────────────────


def test_export_mesas_2026_sv_basic(store: DataStore) -> None:
    out = store.export_mesas_2026_sv()
    assert out["vuelta"] == 2
    assert out["total"] == 3
    sample = next(r for r in out["rows"] if r["codigo_mesa"] == "900100")
    assert sample["departamento"] == "AMAZONAS"
    assert sample["codigo_estado_acta"] == "C"


def test_export_votos_2026_sv_partido_filter(store: DataStore) -> None:
    out = store.export_votos_2026_sv(partido_ids=["10"])
    assert out["total"] == 3
    assert all(r["partido_id"] == "10" for r in out["rows"])


def test_export_partidos_2026_sv(store: DataStore) -> None:
    out = store.export_partidos_2026_sv()
    assert out["total"] == 4
    assert out["candidatos"] == 2


def test_summary_2026_sv(store: DataStore) -> None:
    s = store.summary_2026_sv()
    assert s["mesas_contabilizadas"] == 3
    assert s["votos_validos"] == 650  # 240+215+195
    by_pid = {r["partido_id"]: r for r in s["por_partido"]}
    # JxP = 140+115+170 = 425 ; FP = 100+100+25 = 225
    assert by_pid["10"]["total_votos"] == 425
    assert by_pid["8"]["total_votos"] == 225


# ── Geo agregados 1V ────────────────────────────────────────────────────────


def test_resultados_geo_2026_1v_nacional(store: DataStore) -> None:
    out = store.resultados_geo_2026_1v(nivel="nacional", top_n=5)
    assert out["nivel"] == "nacional"
    assert out["mesas"] == 3
    assert out["top"][0]["partido_id"] == "10"
    assert out["top"][0]["total_votos"] == 390


def test_resultados_geo_2026_1v_dpto_filter(store: DataStore) -> None:
    out = store.resultados_geo_2026_1v(
        nivel="departamento", filtro="AMAZONAS", top_n=3
    )
    assert out["filtro"] == "AMAZONAS"
    assert out["mesas"] == 1
    # JxP wins in Amazonas (150 vs 30)
    assert out["top"][0]["partido_id"] == "10"


def test_cobertura_2026_1v(store: DataStore) -> None:
    out = store.cobertura_2026_1v()
    assert out["total_mesas"] == 3
    assert out["contabilizadas"] == 3
    assert out["pct_contabilizadas"] == 100.0


# ── Catálogos / Listados ────────────────────────────────────────────────────


def test_list_departamentos(store: DataStore) -> None:
    out = store.list_departamentos()
    assert out["total"] == 2
    deps = {r["departamento"] for r in out["rows"]}
    assert deps == {"LIMA", "AMAZONAS"}


def test_list_partidos_v1(store: DataStore) -> None:
    out = store.list_partidos(vuelta=1)
    assert out["vuelta"] == 1
    assert out["candidatos"] == 2


def test_list_partidos_v2(store: DataStore) -> None:
    out = store.list_partidos(vuelta=2)
    assert out["vuelta"] == 2
    assert out["candidatos"] == 2


def test_list_foreign_geo(store: DataStore) -> None:
    out = store.list_foreign_geo()
    assert out["total_ciudades"] == 1
    assert out["total_paises"] == 1
    assert out["rows"][0]["pais"] == "ESPAÑA"


# ── Analítica ───────────────────────────────────────────────────────────────


def test_top_candidato_geo_v1_partido_id(store: DataStore) -> None:
    out = store.top_candidato_geo(
        vuelta=1, partido_id="10", nivel="departamento", top_n=5
    )
    # JxP: 130+110=240 (Lima) + 150 (Amazonas) → Lima wins por más votos
    assert out["top"][0]["geo"] == "LIMA"
    assert out["top"][0]["votos"] == 240
    assert out["top"][1]["geo"] == "AMAZONAS"
    assert out["top"][1]["votos"] == 150


def test_top_candidato_geo_v1_candidato_query(store: DataStore) -> None:
    out = store.top_candidato_geo(
        vuelta=1, candidato_query="JUNTOS", nivel="departamento", top_n=5
    )
    assert out["partido_id"] == "10"


def test_top_candidato_geo_v2(store: DataStore) -> None:
    out = store.top_candidato_geo(
        vuelta=2, partido_id="8", nivel="departamento", top_n=5
    )
    # FP: 100+100=200 (Lima) + 25 (Amazonas) → Lima wins
    assert out["top"][0]["geo"] == "LIMA"
    assert out["top"][0]["votos"] == 200


def test_top_candidato_geo_requires_input(store: DataStore) -> None:
    with pytest.raises(ValueError):
        store.top_candidato_geo(vuelta=1, nivel="distrito")


def test_stats_participacion_v1(store: DataStore) -> None:
    out = store.stats_participacion(vuelta=1)
    assert out["n_mesas"] == 3
    p = out["participacion_pct"]
    # Mesas: 250/300=83.3, 220/280=78.6, 200/250=80.0  → mean ~80.6%
    assert 75.0 <= p["mean"] <= 85.0
    assert p["min"] <= p["median"] <= p["max"]


def test_stats_participacion_filter_dpto(store: DataStore) -> None:
    out = store.stats_participacion(vuelta=1, departamento="AMAZONAS")
    assert out["n_mesas"] == 1
    assert out["participacion_pct"]["mean"] == pytest.approx(80.0, abs=0.1)


def test_audit_votos_consistency_no_issues(store: DataStore) -> None:
    """En el fixture, votos por mesa están balanceados con votos_validos +
    blancos + nulos = votos_emitidos, pero votos_validos en cabecera SI debe
    coincidir con Σ partidos reales (10 + 8). Verifiquemos: mesa 000001:
    230 cabecera vs 130+100=230. ✓
    """
    out = store.audit_votos_consistency(vuelta=1)
    assert out["n_inconsistentes"] == 0


def test_audit_votos_consistency_detects_inconsistency(store: DataStore) -> None:
    # Corrupt one mesa's vote count
    now = store.now_iso()
    with store._connect() as conn:
        conn.execute(
            "UPDATE votos SET votos = 200 WHERE codigo_mesa = '000001' AND partido_id = '10'"
        )
    out = store.audit_votos_consistency(vuelta=1, limit=10)
    assert out["n_inconsistentes"] == 1
    bad = out["rows"][0]
    assert bad["codigo_mesa"] == "000001"
    # cabecera = 230, ahora suma = 200+100 = 300 → diff = +70
    assert bad["diff"] == 70


def test_audit_coverage_v1(store: DataStore) -> None:
    out = store.audit_coverage(vuelta=1)
    assert out["total_mesas"] == 3
    assert out["mesas_con_votos"] == 3
    assert out["huecos_totales"] == 0
    assert out["pct_hidratado_global"] == 100.0


def test_audit_coverage_detects_huecos(store: DataStore) -> None:
    # Add a mesa without votos
    now = store.now_iso()
    with store._connect() as conn:
        conn.execute(
            """INSERT INTO mesas_data (codigo_mesa, ubigeo, local_votacion,
               electores_habiles, votos_emitidos, votos_validos,
               blancos, nulos, impugnados, estado_acta, fetched_at)
               VALUES ('000003','150101','D',200,0,0,0,0,0,'Pendiente',?)""",
            (now,),
        )
    out = store.audit_coverage(vuelta=1)
    assert out["total_mesas"] == 4
    assert out["mesas_con_votos"] == 3
    assert out["huecos_totales"] == 1
