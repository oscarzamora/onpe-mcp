"""Tests for the 7 new geo lookup + cross-year comparison methods."""
from __future__ import annotations

from pathlib import Path

import pytest

from onpe_mcp.storage import DataStore


@pytest.fixture()
def store(tmp_path: Path) -> DataStore:
    """Minimal fixture with mesas_data + mesas_sv + mesas_2021 + ubigeo_reniec."""
    ds = DataStore(tmp_path / "db")
    now = ds.now_iso()
    with ds._connect() as conn:
        # Reniec catalog (the source of truth for geo lookups)
        conn.executemany(
            """INSERT INTO ubigeo_reniec
               (ubigeo, distrito, provincia, departamento,
                distrito_norm, provincia_norm, departamento_norm, fetched_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                ("150122", "Miraflores", "Lima", "Lima",
                 "miraflores", "lima", "lima", now),
                ("150110", "La Molina", "Lima", "Lima",
                 "la molina", "lima", "lima", now),
                ("010603", "El Cenepa", "Condorcanqui", "Amazonas",
                 "el cenepa", "condorcanqui", "amazonas", now),
                ("150101", "Lima", "Lima", "Lima",
                 "lima", "lima", "lima", now),
            ],
        )
        # 2026 1V: mesa en Miraflores (ubigeo 6-dig) + mesa rural Amazonas (5-dig)
        conn.executemany(
            """INSERT INTO mesas_data (codigo_mesa, ubigeo, local_votacion,
               electores_habiles, votos_emitidos, votos_validos,
               blancos, nulos, impugnados, estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [
                ("045010", "150122", "Local Miraflores 1", 300, 250, 230,
                 10, 10, 0, "Contabilizada", now),
                ("045011", "150122", "Local Miraflores 2", 280, 220, 200,
                 12, 8, 0, "Contabilizada", now),
                ("900100", "10603", "IEI 326", 248, 210, 180, 15, 15, 0,
                 "Contabilizada", now),  # 5-digit ubigeo (dpto 01 Amazonas)
            ],
        )
        conn.executemany(
            "INSERT INTO agrupaciones (partido_id, nombre, fetched_at) VALUES (?,?,?)",
            [("10", "JxP", now), ("8", "FP", now), ("80", "BL", now)],
        )
        conn.executemany(
            "INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
            [
                ("045010", "10", 80, now), ("045010", "8", 150, now),
                ("045011", "10", 70, now), ("045011", "8", 130, now),
                ("900100", "10", 160, now), ("900100", "8", 20, now),
            ],
        )
        # 2026 SV
        conn.executemany(
            """INSERT INTO mesas_sv (codigo_mesa, id_ubigeo, nombre_local,
               id_ambito, electores_habiles, votos_emitidos, votos_validos,
               total_asistentes, codigo_estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [
                ("045010", "150122", "Local Miraflores 1", 1, 300, 250, 240,
                 250, "C", now),
                ("045011", "150122", "Local Miraflores 2", 1, 280, 220, 210,
                 220, "C", now),
                ("900100", "010603", "IEI 326", 1, 248, 207, 194, 207, "C", now),
            ],
        )
        conn.executemany(
            "INSERT INTO agrupaciones_sv (partido_id, nombre, fetched_at) VALUES (?,?,?)",
            [("10", "JxP", now), ("8", "FP", now)],
        )
        conn.executemany(
            "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
            [
                ("045010", "10", 90, now), ("045010", "8", 150, now),
                ("045011", "10", 80, now), ("045011", "8", 130, now),
                ("900100", "10", 190, now), ("900100", "8", 4, now),
            ],
        )
        conn.executemany(
            """INSERT INTO ubicaciones_sv (ubigeo, ambito, departamento, provincia,
               distrito, continente, pais, ciudad, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                ("150122", "NACIONAL", "Lima", "Lima", "Miraflores",
                 "", "", "", now),
                ("010603", "NACIONAL", "Amazonas", "Condorcanqui", "El Cenepa",
                 "", "", "", now),
            ],
        )
        # 2021 1V + 2V (mesa 900100)
        conn.executemany(
            """INSERT INTO mesas_2021 (vuelta, codigo_mesa, ubigeo, departamento,
               provincia, distrito, tipo_eleccion, descrip_estado_acta, tipo_observacion,
               n_cvas, n_elec_habil, votos_vb, votos_vn, votos_vi,
               votos_emitidos, votos_validos, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (1, "900100", "010603", "AMAZONAS", "CONDORCANQUI", "EL CENEPA",
                 "P", "CONTABILIZADA", "", 18, 186, 30, 5, 0, 100, 65, now),
                (2, "900100", "010603", "AMAZONAS", "CONDORCANQUI", "EL CENEPA",
                 "P", "CONTABILIZADA", "", 2, 186, 5, 5, 0, 130, 120, now),
                (1, "045010", "150122", "LIMA", "LIMA", "MIRAFLORES",
                 "P", "CONTABILIZADA", "", 18, 300, 10, 5, 0, 250, 235, now),
                (2, "045010", "150122", "LIMA", "LIMA", "MIRAFLORES",
                 "P", "CONTABILIZADA", "", 2, 300, 5, 2, 0, 270, 263, now),
            ],
        )
        conn.executemany(
            """INSERT INTO partidos_2021 (vuelta, partido_id, nombre_partido,
               candidato, fetched_at) VALUES (?,?,?,?,?)""",
            [
                (1, "PC", "Perú Libre", "Pedro Castillo Terrones", now),
                (1, "K", "Fuerza Popular", "Keiko Fujimori Higuchi", now),
                (2, "PC", "Perú Libre", "Pedro Castillo Terrones", now),
                (2, "K", "Fuerza Popular", "Keiko Fujimori Higuchi", now),
            ],
        )
        conn.executemany(
            """INSERT INTO votos_2021 (vuelta, codigo_mesa, partido_id, votos, fetched_at)
               VALUES (?,?,?,?,?)""",
            [
                (1, "900100", "PC", 40, now), (1, "900100", "K", 25, now),
                (2, "900100", "PC", 90, now), (2, "900100", "K", 30, now),
                (1, "045010", "PC", 50, now), (1, "045010", "K", 185, now),
                (2, "045010", "PC", 60, now), (2, "045010", "K", 203, now),
            ],
        )
    return ds


# ── lookup_ubigeo ───────────────────────────────────────────────────────────

def test_lookup_ubigeo_exact_distrito(store: DataStore) -> None:
    out = store.lookup_ubigeo("La Molina")
    assert out["total"] == 1
    assert out["rows"][0]["ubigeo"] == "150110"
    assert out["rows"][0]["nivel"] == "distrito"


def test_lookup_ubigeo_accent_insensitive(store: DataStore) -> None:
    # 'Cenepa' should not match (no exact), but 'El Cenepa' does
    out = store.lookup_ubigeo("EL CENEPA")
    assert out["total"] >= 1
    assert any(r["distrito"] == "El Cenepa" for r in out["rows"])


def test_lookup_ubigeo_no_match(store: DataStore) -> None:
    out = store.lookup_ubigeo("FantasyDistrict")
    assert out["total"] == 0


# ── listar_mesas_por_geo ────────────────────────────────────────────────────

def test_listar_mesas_por_geo_2026_distrito(store: DataStore) -> None:
    out = store.listar_mesas_por_geo(año=2026, vuelta=1, distrito="Miraflores")
    assert out["available"] is True
    assert out["total"] == 2
    assert {r["codigo_mesa"] for r in out["rows"]} == {"045010", "045011"}


def test_listar_mesas_por_geo_2021_distrito(store: DataStore) -> None:
    out = store.listar_mesas_por_geo(año=2021, vuelta=1, distrito="MIRAFLORES")
    assert out["available"] is True
    assert out["total"] == 1


def test_listar_mesas_por_geo_year_not_available(store: DataStore) -> None:
    out = store.listar_mesas_por_geo(año=2016, vuelta=1, distrito="Miraflores")
    assert out["available"] is False
    assert "2016" in out["reason"]


def test_listar_mesas_por_geo_rural_5digit_ubigeo(store: DataStore) -> None:
    """Verifica que mesas con ubigeo 5-digit en mesas_data se enlazan al reniec 6-digit."""
    out = store.listar_mesas_por_geo(año=2026, vuelta=1, distrito="El Cenepa")
    assert out["total"] == 1
    assert out["rows"][0]["codigo_mesa"] == "900100"


# ── listar_locales_por_geo ──────────────────────────────────────────────────

def test_listar_locales_por_geo_2026(store: DataStore) -> None:
    out = store.listar_locales_por_geo(año=2026, vuelta=1, distrito="Miraflores")
    assert out["available"] is True
    assert out["total"] == 2  # 2 locales distintos en Miraflores
    by_local = {r["local_votacion"]: r for r in out["rows"]}
    assert "Local Miraflores 1" in by_local
    assert by_local["Local Miraflores 1"]["n_mesas"] == 1


def test_listar_locales_por_geo_2021_no_data(store: DataStore) -> None:
    out = store.listar_locales_por_geo(año=2021, distrito="Miraflores")
    assert out["available"] is True
    assert out["total"] == 0
    assert "no incluye" in out.get("note", "")


# ── mesa_geo_lookup ────────────────────────────────────────────────────────

def test_mesa_geo_lookup_2026_normal_ubigeo(store: DataStore) -> None:
    out = store.mesa_geo_lookup("045010", año=2026, vuelta=1)
    assert out["found"] is True
    assert out["departamento"] == "Lima"
    assert out["distrito"] == "Miraflores"


def test_mesa_geo_lookup_2026_5digit_ubigeo(store: DataStore) -> None:
    """Mesa rural Amazonas con ubigeo 5-dig debe encontrarse en reniec."""
    out = store.mesa_geo_lookup("900100", año=2026, vuelta=1)
    assert out["found"] is True
    assert out["departamento"] == "Amazonas"
    assert out["distrito"] == "El Cenepa"


def test_mesa_geo_lookup_2026_sv(store: DataStore) -> None:
    out = store.mesa_geo_lookup("900100", año=2026, vuelta=2)
    assert out["found"] is True
    assert out["departamento"] == "Amazonas"
    assert out["distrito"] == "El Cenepa"


def test_mesa_geo_lookup_2021(store: DataStore) -> None:
    out = store.mesa_geo_lookup("900100", año=2021, vuelta=1)
    assert out["found"] is True
    assert out["distrito"] == "EL CENEPA"


def test_mesa_geo_lookup_not_found(store: DataStore) -> None:
    out = store.mesa_geo_lookup("999999", año=2026, vuelta=1)
    assert out["found"] is False


def test_mesa_geo_lookup_year_not_available(store: DataStore) -> None:
    out = store.mesa_geo_lookup("900100", año=2016)
    assert out["found"] is False
    assert "2016" in out["reason"]


# ── comparacion_mesa_2021 ──────────────────────────────────────────────────

def test_comparacion_mesa_2021(store: DataStore) -> None:
    out = store.comparacion_mesa_2021("900100")
    assert out["available_1v"] is True
    assert out["available_2v"] is True
    assert out["primera_vuelta"]["votos_validos"] == 65
    assert out["segunda_vuelta"]["votos_validos"] == 120


def test_comparacion_mesa_2021_not_found(store: DataStore) -> None:
    out = store.comparacion_mesa_2021("999999")
    assert out["available_1v"] is False
    assert out["available_2v"] is False


# ── comparacion_mesa_cross_year ────────────────────────────────────────────

def test_comparacion_mesa_cross_year_2021_vs_2026(store: DataStore) -> None:
    out = store.comparacion_mesa_cross_year("900100", año_a=2021, año_b=2026,
                                             vuelta_a=1, vuelta_b=1)
    a = out["lado_a"]
    b = out["lado_b"]
    assert a["available"] is True and a["found"] is True
    assert b["available"] is True and b["found"] is True
    assert a["top"][0]["candidato"] == "Pedro Castillo Terrones"
    assert b["top"][0]["partido_id"] == "10"


def test_comparacion_mesa_cross_year_unavailable_year(store: DataStore) -> None:
    out = store.comparacion_mesa_cross_year("421234", año_a=2016, año_b=2021)
    assert out["lado_a"]["available"] is False
    assert "2016" in out["lado_a"]["reason"]


def test_comparacion_mesa_cross_year_2026_1v_vs_2v(store: DataStore) -> None:
    out = store.comparacion_mesa_cross_year("900100", año_a=2026, año_b=2026,
                                             vuelta_a=1, vuelta_b=2)
    assert out["lado_a"]["found"] is True
    assert out["lado_b"]["found"] is True


# ── comparacion_geo_cross_year ─────────────────────────────────────────────

def test_comparacion_geo_cross_year_distrito(store: DataStore) -> None:
    out = store.comparacion_geo_cross_year(
        nivel="distrito", geo_name="MIRAFLORES",
        año_a=2021, año_b=2026, vuelta_a=2, vuelta_b=2,
    )
    a = out["lado_a"]
    b = out["lado_b"]
    assert a["available"] is True
    assert b["available"] is True
    # Mesa 045010 en Miraflores: 2021 2V → K=203, PC=60
    by_a = {r["candidato"]: r["votos"] for r in a["top"]}
    assert by_a.get("Keiko Fujimori Higuchi", 0) > by_a.get("Pedro Castillo Terrones", 0)


def test_comparacion_geo_cross_year_2026_sv_uses_sv_geo_membership(store: DataStore) -> None:
    """2026 2V debe usar la geografía SV (ubicaciones_sv), no solo ubigeo_reniec."""
    now = store.now_iso()
    with store._connect() as conn:
        # Ubigeo SV extra en Amazonas que NO existe en ubigeo_reniec del fixture.
        conn.execute(
            """INSERT INTO ubicaciones_sv (ubigeo, ambito, departamento, provincia,
               distrito, continente, pais, ciudad, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            ("010699", "NACIONAL", "Amazonas", "Condorcanqui", "Nuevo Distrito", "", "", "", now),
        )
        conn.execute(
            """INSERT INTO mesas_sv (codigo_mesa, id_ubigeo, nombre_local, id_ambito,
               electores_habiles, votos_emitidos, votos_validos, total_asistentes,
               codigo_estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("900199", "010699", "Local Extra", 1, 200, 160, 150, 160, "C", now),
        )
        conn.executemany(
            "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
            [
                ("900199", "10", 120, now),
                ("900199", "8", 30, now),
                ("900199", "80", 0, now),
                ("900199", "81", 0, now),
                ("900199", "82", 0, now),
            ],
        )

    out = store.comparacion_geo_cross_year(
        nivel="departamento", geo_name="AMAZONAS",
        año_a=2021, año_b=2026, vuelta_a=2, vuelta_b=2,
        top_n=5,
    )
    b = out["lado_b"]
    by_b = {r["partido_id"]: r["votos"] for r in b["top"]}
    # Base fixture Amazonas 2V: partido 10=190, partido 8=4 (mesa 900100)
    # + mesa extra 900199: partido 10=120, partido 8=30.
    assert by_b["10"] == 310
    assert by_b["8"] == 34
    # total_validos en 2V se calcula como suma de votos por partido (incluye especiales)
    assert b["total_validos"] == 344
    assert b["mesas"] == 2


def test_comparacion_geo_cross_year_year_unavailable(store: DataStore) -> None:
    out = store.comparacion_geo_cross_year(
        nivel="distrito", geo_name="Miraflores",
        año_a=2016, año_b=2021,
    )
    assert out["lado_a"]["available"] is False
    assert out["lado_b"]["available"] is True


def test_comparacion_geo_cross_year_invalid_nivel(store: DataStore) -> None:
    with pytest.raises(ValueError):
        store.comparacion_geo_cross_year(
            nivel="continente", geo_name="X",
            año_a=2021, año_b=2026,
        )
