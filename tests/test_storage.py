from __future__ import annotations

from pathlib import Path

from onpe_mcp.storage import DataStore


def test_storage_crea_artefactos(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    assert (tmp_path / "onpe.db").exists()
    assert (tmp_path / "raw" / "events.jsonl").exists() is False
    assert (tmp_path / "reports").exists()

    store.append_raw_event("test", {"ok": True})
    assert (tmp_path / "raw" / "events.jsonl").exists()


def test_cache_roundtrip(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    payload = {
        "codigo_mesa": "000123",
        "found": True,
        "mesa_data": {
            "codigo_mesa": "000123",
            "ubigeo": "150101",
            "local_votacion": "LOCAL TEST",
            "electores_habiles": 100,
            "votos_emitidos": 90,
            "votos_validos": 88,
            "blancos": 1,
            "nulos": 1,
            "impugnados": 0,
            "estado_acta": "Contabilizada",
        },
        "agrupaciones": [{"partido_id": "1", "nombre": "PARTIDO 1"}],
        "votos": [{"codigo_mesa": "000123", "partido_id": "1", "votos": 88}],
    }

    store.upsert_mesa_bundle("000123", payload, source="test", id_eleccion=10)

    cached = store.get_cached_mesa("000123", max_age_seconds=3600)
    assert cached is not None
    assert cached["codigo_mesa"] == "000123"
    assert cached["found"] is True


def test_find_foreign_ubigeos_prioriza_match_exacto_y_campo(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_foreign_catalog(
        [
            {"ubigeo": "A1", "Continente": "AMERICA", "pais": "ESTADOS UNIDOS", "ciudad": "MIAMI"},
            {"ubigeo": "A2", "Continente": "AMERICA", "pais": "ESTADOS UNIDOS", "ciudad": "MIAMI BEACH"},
            {"ubigeo": "A3", "Continente": "AMERICA", "pais": "CHILE", "ciudad": "SANTIAGO"},
        ]
    )

    by_city = store.find_foreign_ubigeos("miami", field="ciudad")
    assert [row["ubigeo"] for row in by_city] == ["A1"]

    by_country = store.find_foreign_ubigeos("estados unidos", field="pais")
    assert {row["ubigeo"] for row in by_country} == {"A1", "A2"}

    any_match = store.find_foreign_ubigeos("miami")
    assert [row["ubigeo"] for row in any_match] == ["A1"]


def test_aggregate_votes_by_party_reemplaza_mesa_sin_duplicar(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    payload_v1 = {
        "codigo_mesa": "000777",
        "found": True,
        "mesa_data": {
            "codigo_mesa": "000777",
            "ubigeo": "U1",
            "local_votacion": "LOCAL",
            "electores_habiles": 100,
            "votos_emitidos": 50,
            "votos_validos": 50,
            "blancos": 0,
            "nulos": 0,
            "impugnados": 0,
            "estado_acta": "Contabilizada",
        },
        "agrupaciones": [
            {"partido_id": "1", "nombre": "PARTIDO 1"},
            {"partido_id": "2", "nombre": "PARTIDO 2"},
        ],
        "votos": [
            {"codigo_mesa": "000777", "partido_id": "1", "votos": 30},
            {"codigo_mesa": "000777", "partido_id": "2", "votos": 20},
        ],
    }
    store.upsert_mesa_bundle("000777", payload_v1, source="test", id_eleccion=10)

    payload_v2 = {
        "codigo_mesa": "000777",
        "found": True,
        "mesa_data": {
            "codigo_mesa": "000777",
            "ubigeo": "U1",
            "local_votacion": "LOCAL",
            "electores_habiles": 100,
            "votos_emitidos": 55,
            "votos_validos": 55,
            "blancos": 0,
            "nulos": 0,
            "impugnados": 0,
            "estado_acta": "Contabilizada",
        },
        "agrupaciones": [
            {"partido_id": "1", "nombre": "PARTIDO 1"},
            {"partido_id": "2", "nombre": "PARTIDO 2"},
        ],
        "votos": [
            {"codigo_mesa": "000777", "partido_id": "1", "votos": 10},
            {"codigo_mesa": "000777", "partido_id": "2", "votos": 45},
        ],
    }
    store.upsert_mesa_bundle("000777", payload_v2, source="test", id_eleccion=10)

    agg = store.aggregate_votes_by_party({"U1"})
    by_party = {item["partido_id"]: item["total_votos"] for item in agg}

    assert by_party["1"] == 10
    assert by_party["2"] == 45


def test_geo_query_cache_roundtrip(tmp_path: Path) -> None:
    store = DataStore(tmp_path)
    payload = {
        "intent": "geo",
        "answer": "ok",
        "result": {"top_partidos": []},
        "source": "sqlite",
    }

    store.upsert_geo_query_cache("k1", payload)
    cached = store.get_geo_query_cache("k1", max_age_seconds=60)

    assert cached is not None
    assert cached["intent"] == "geo"
    assert cached["answer"] == "ok"


def test_candidate_first_places_by_mesa_prefix(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    # Mesa 900001: partido 9 gana
    store.upsert_mesa_bundle(
        "900001",
        {
            "codigo_mesa": "900001",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "900001",
                "ubigeo": "942701",
                "local_votacion": "LOCAL A",
                "electores_habiles": 100,
                "votos_emitidos": 90,
                "votos_validos": 90,
                "blancos": 0,
                "nulos": 0,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [
                {"partido_id": "9", "nombre": "PARTIDO 9"},
                {"partido_id": "1", "nombre": "PARTIDO 1"},
            ],
            "votos": [
                {"codigo_mesa": "900001", "partido_id": "9", "votos": 60},
                {"codigo_mesa": "900001", "partido_id": "1", "votos": 30},
            ],
        },
        source="test",
        id_eleccion=10,
    )

    # Mesa 900002: partido 9 no gana
    store.upsert_mesa_bundle(
        "900002",
        {
            "codigo_mesa": "900002",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "900002",
                "ubigeo": "942703",
                "local_votacion": "LOCAL B",
                "electores_habiles": 100,
                "votos_emitidos": 90,
                "votos_validos": 90,
                "blancos": 0,
                "nulos": 0,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [
                {"partido_id": "9", "nombre": "PARTIDO 9"},
                {"partido_id": "1", "nombre": "PARTIDO 1"},
            ],
            "votos": [
                {"codigo_mesa": "900002", "partido_id": "9", "votos": 20},
                {"codigo_mesa": "900002", "partido_id": "1", "votos": 70},
            ],
        },
        source="test",
        id_eleccion=10,
    )

    store.upsert_foreign_catalog(
        [
            {"ubigeo": "942701", "Continente": "EUROPA", "pais": "SUECIA", "ciudad": "ESTOCOLMO"},
            {"ubigeo": "942703", "Continente": "EUROPA", "pais": "SUECIA", "ciudad": "MALMO"},
        ]
    )

    result = store.candidate_first_places_by_mesa_prefix(
        mesa_prefix="9000",
        partido_ids={"9"},
        top_n=5,
    )

    assert result["total_mesas_prefijo"] == 2
    assert result["mesas_con_votos"] == 2
    assert result["mesas_primero"] == 1
    assert len(result["lugares"]) == 1
    assert result["lugares"][0]["pais"] == "SUECIA"
    assert result["lugares"][0]["ciudad"] == "ESTOCOLMO"


def test_summarize_mesa_prefix_incluye_metricas_factuales(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_mesa_bundle(
        "900001",
        {
            "codigo_mesa": "900001",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "900001",
                "ubigeo": "942701",
                "local_votacion": "LOCAL A",
                "electores_habiles": 100,
                "votos_emitidos": 80,
                "votos_validos": 75,
                "blancos": 2,
                "nulos": 3,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [{"partido_id": "1", "nombre": "PARTIDO 1"}],
            "votos": [{"codigo_mesa": "900001", "partido_id": "1", "votos": 75}],
        },
        source="test",
        id_eleccion=10,
    )

    store.upsert_foreign_catalog(
        [{"ubigeo": "942701", "Continente": "EUROPA", "pais": "SUECIA", "ciudad": "ESTOCOLMO"}]
    )

    summary = store.summarize_mesa_prefix("900000")
    assert summary["total_mesas"] == 1
    assert summary["mesas_con_votos"] == 1
    assert summary["votos_emitidos"] == 80
    assert summary["votos_validos"] == 75
    assert summary["total_paises"] == 1
    assert summary["total_ciudades"] == 1
    assert len(summary["top_ciudades"]) == 1


def test_summarize_mesa_prefix_usa_cache_ubicacion_si_falta_foreign(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_mesa_bundle(
        "150101",
        {
            "codigo_mesa": "150101",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "150101",
                "ubigeo": "150101",
                "local_votacion": "LOCAL LIMA",
                "electores_habiles": 120,
                "votos_emitidos": 95,
                "votos_validos": 90,
                "blancos": 2,
                "nulos": 3,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [{"partido_id": "1", "nombre": "PARTIDO 1"}],
            "votos": [{"codigo_mesa": "150101", "partido_id": "1", "votos": 90}],
        },
        source="test",
        id_eleccion=10,
    )

    ok = store.upsert_ubigeo_location(
        {
            "ubigeo": "150101",
            "ambito": "peru",
            "departamento": "LIMA",
            "ciudad": "LIMA",
            "pais": "",
        }
    )
    assert ok is True

    summary = store.summarize_mesa_prefix("150000")
    assert summary["total_mesas"] == 1
    assert summary["total_ciudades"] == 1
    assert summary["top_ciudades"][0]["departamento"] == "LIMA"
    assert summary["sample"][0]["departamento"] == "LIMA"


def test_find_ubigeos_missing_city_or_department_by_mesa_prefix(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_mesa_bundle(
        "150102",
        {
            "codigo_mesa": "150102",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "150102",
                "ubigeo": "150102",
                "local_votacion": "LOCAL TEST",
                "electores_habiles": 80,
                "votos_emitidos": 60,
                "votos_validos": 58,
                "blancos": 1,
                "nulos": 1,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [{"partido_id": "1", "nombre": "P1"}],
            "votos": [{"codigo_mesa": "150102", "partido_id": "1", "votos": 58}],
        },
        source="test",
        id_eleccion=10,
    )

    missing_before = store.find_ubigeos_missing_city_or_department_by_mesa_prefix("150000")
    assert "150102" in missing_before

    store.upsert_ubigeo_location(
        {
            "ubigeo": "150102",
            "ambito": "peru",
            "departamento": "LIMA",
            "ciudad": "LIMA",
            "pais": "",
        }
    )
    missing_after = store.find_ubigeos_missing_city_or_department_by_mesa_prefix("150000")
    assert "150102" not in missing_after


def test_find_ubigeos_missing_city_or_department_by_ubigeo_prefix(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_mesa_bundle(
        "150201",
        {
            "codigo_mesa": "150201",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "150201",
                "ubigeo": "150201",
                "local_votacion": "LOCAL 1",
                "electores_habiles": 100,
                "votos_emitidos": 80,
                "votos_validos": 76,
                "blancos": 2,
                "nulos": 2,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [{"partido_id": "1", "nombre": "P1"}],
            "votos": [{"codigo_mesa": "150201", "partido_id": "1", "votos": 76}],
        },
        source="test",
        id_eleccion=10,
    )

    missing = store.find_ubigeos_missing_city_or_department_by_ubigeo_prefix("15")
    assert "150201" in missing

    store.upsert_ubigeo_location(
        {
            "ubigeo": "150201",
            "ambito": "peru",
            "departamento": "LIMA",
            "ciudad": "HUAURA",
            "pais": "",
        }
    )
    missing_after = store.find_ubigeos_missing_city_or_department_by_ubigeo_prefix("15")
    assert "150201" not in missing_after


def test_summarize_ubigeo_prefix_devuelve_sample_enriquecido(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    store.upsert_mesa_bundle(
        "160101",
        {
            "codigo_mesa": "160101",
            "found": True,
            "mesa_data": {
                "codigo_mesa": "160101",
                "ubigeo": "160101",
                "local_votacion": "LOCAL IQUITOS",
                "electores_habiles": 110,
                "votos_emitidos": 85,
                "votos_validos": 82,
                "blancos": 1,
                "nulos": 2,
                "impugnados": 0,
                "estado_acta": "Contabilizada",
            },
            "agrupaciones": [{"partido_id": "1", "nombre": "P1"}],
            "votos": [{"codigo_mesa": "160101", "partido_id": "1", "votos": 82}],
        },
        source="test",
        id_eleccion=10,
    )

    store.upsert_ubigeo_location(
        {
            "ubigeo": "160101",
            "ambito": "peru",
            "departamento": "LORETO",
            "ciudad": "IQUITOS",
            "pais": "",
        }
    )

    summary = store.summarize_ubigeo_prefix("16", sample_size=3)
    assert summary["ubigeo_prefix"] == "16"
    assert len(summary["sample"]) == 1
    assert summary["sample"][0]["departamento"] == "LORETO"
    assert summary["sample"][0]["ciudad"] == "IQUITOS"


# ─────────────────────────────────────────────────────────────────────────────
# get_proyeccion_sv_by_mesa_prefix: proyección NNLS por prefijo de mesa
# ─────────────────────────────────────────────────────────────────────────────

def _seed_mesa_1v_2v(
    store: DataStore,
    codigo_mesa: str,
    *,
    ubigeo: str,
    electores: int,
    emitidos_1v: int,
    votos_1v: dict[str, int],
    emitidos_2v: int,
    votos_2v: dict[str, int],
) -> None:
    """Helper: inserta una mesa con votos en ambas vueltas (insert directo en tablas)."""
    now = store.now_iso()
    validos_1v = sum(v for pid, v in votos_1v.items() if pid not in {"80", "81", "82"})
    validos_2v = sum(v for pid, v in votos_2v.items() if pid not in {"80", "81", "82"})
    with store._connect() as conn:
        # mesas_data + votos (1V)
        conn.execute(
            """INSERT INTO mesas_data (codigo_mesa, ubigeo, local_votacion, electores_habiles,
               votos_emitidos, votos_validos, blancos, nulos, impugnados, estado_acta, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (codigo_mesa, ubigeo, "LOCAL TEST", electores, emitidos_1v, validos_1v,
             votos_1v.get("80", 0), votos_1v.get("81", 0), votos_1v.get("82", 0),
             "Contabilizada", now),
        )
        for pid, v in votos_1v.items():
            conn.execute(
                "INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
                (codigo_mesa, pid, v, now),
            )
        # mesas_sv + votos_sv (2V)
        conn.execute(
            """INSERT INTO mesas_sv (codigo_mesa, id_ubigeo, nombre_local, id_ambito,
               electores_habiles, votos_emitidos, votos_validos, total_asistentes,
               codigo_estado_acta, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (codigo_mesa, ubigeo, "LOCAL TEST", 1, electores, emitidos_2v, validos_2v,
             emitidos_2v, "C", now),
        )
        for pid, v in votos_2v.items():
            conn.execute(
                "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
                (codigo_mesa, pid, v, now),
            )


def _seed_agrupaciones(store: DataStore, mapping: dict[str, str]) -> None:
    now = store.now_iso()
    with store._connect() as conn:
        for pid, nombre in mapping.items():
            conn.execute(
                "INSERT INTO agrupaciones (partido_id, nombre, fetched_at) VALUES (?,?,?)",
                (pid, nombre, now),
            )


def test_get_proyeccion_sv_by_mesa_prefix_aggrega_predice_y_compara(tmp_path: Path) -> None:
    store = DataStore(tmp_path)

    # Partido 8 = FUERZA POPULAR (Keiko), 10 = JUNTOS POR EL PERU (Sanchez)
    _seed_agrupaciones(
        store,
        {
            "8": "FUERZA POPULAR",
            "10": "JUNTOS POR EL PERU",
            "14": "PARTIDO CIVICO OBRAS",
            "32": "PODEMOS PERU",
            "35": "RENOVACION POPULAR",
            "80": "VOTOS EN BLANCO",
            "81": "VOTOS NULOS",
        },
    )

    # Mesa 900100 (bloque 900K rural)
    _seed_mesa_1v_2v(
        store, "900100",
        ubigeo="010101", electores=200,
        emitidos_1v=160,
        votos_1v={"8": 20, "10": 50, "14": 10, "32": 5, "35": 8, "80": 40, "81": 27},
        emitidos_2v=150,
        votos_2v={"8": 50, "10": 95, "80": 0, "81": 5},
    )
    # Mesa 900200 (bloque 900K rural)
    _seed_mesa_1v_2v(
        store, "900200",
        ubigeo="010102", electores=180,
        emitidos_1v=140,
        votos_1v={"8": 15, "10": 45, "14": 8, "32": 4, "35": 6, "80": 35, "81": 27},
        emitidos_2v=130,
        votos_2v={"8": 42, "10": 84, "80": 0, "81": 4},
    )
    # Mesa 100100 (fuera del bloque 900K - debe ser ignorada)
    _seed_mesa_1v_2v(
        store, "100100",
        ubigeo="150101", electores=300,
        emitidos_1v=250,
        votos_1v={"8": 200, "10": 30, "80": 10, "81": 10},
        emitidos_2v=240,
        votos_2v={"8": 220, "10": 20, "80": 0, "81": 0},
    )

    # === Test: prefijo "9" debe cubrir solo las dos mesas 900K ===
    result = store.get_proyeccion_sv_by_mesa_prefix("9", top_partidos=10)

    assert result["mesa_prefix"] == "9"
    assert result["primera_vuelta"]["mesas"] == 2
    assert result["primera_vuelta"]["electores_habiles"] == 380
    assert result["primera_vuelta"]["votos_emitidos"] == 300
    # Pool 1V incluye blancos y nulos
    assert result["primera_vuelta"]["pool_total_1v"] == 300

    obs = result["segunda_vuelta_observada"]
    assert obs["mesas"] == 2
    assert obs["keiko"] == 92  # 50 + 42
    assert obs["sanchez"] == 179  # 95 + 84
    assert obs["nulos"] == 9  # 5 + 4

    # La predicción NNLS debe ser > 0 (modelo aplica pesos a cada partido)
    pred = result["proyeccion_nnls_nacional"]
    assert pred["keiko"] > 0
    assert pred["sanchez"] > 0
    assert "NNLS" in pred["modelo"]

    # Error es int/float, no None (porque obs > 0)
    err = result["error_modelo"]
    assert err["keiko_pct"] is not None
    assert err["sanchez_pct"] is not None

    # Breakdown debe incluir partidos ordenados por votos 1V desc
    names = [p["nombre"] for p in result["breakdown_partidos_top"]]
    assert "JUNTOS POR EL PERU" in names
    assert "FUERZA POPULAR" in names
    # JxP (10) tiene más votos 1V que FP (8) en este escenario
    assert names.index("JUNTOS POR EL PERU") < names.index("FUERZA POPULAR")


def test_get_proyeccion_sv_by_mesa_prefix_prefijo_inexistente_devuelve_ceros(
    tmp_path: Path,
) -> None:
    store = DataStore(tmp_path)
    _seed_agrupaciones(store, {"8": "FUERZA POPULAR", "10": "JUNTOS POR EL PERU"})

    result = store.get_proyeccion_sv_by_mesa_prefix("99999999")

    assert result["mesa_prefix"] == "99999999"
    assert result["primera_vuelta"]["mesas"] == 0
    assert result["primera_vuelta"]["pool_total_1v"] == 0
    assert result["segunda_vuelta_observada"]["keiko"] == 0
    assert result["segunda_vuelta_observada"]["sanchez"] == 0
    # Cuando obs es 0, el pct error es None (sin división por cero)
    assert result["error_modelo"]["keiko_pct"] is None
    assert result["error_modelo"]["sanchez_pct"] is None
    assert result["breakdown_partidos_top"] == []


def test_get_proyeccion_sv_by_mesa_prefix_valida_input(tmp_path: Path) -> None:
    import pytest

    store = DataStore(tmp_path)

    for bad in ["", "  ", "abc", "9a", "1 2 3"]:
        with pytest.raises(ValueError, match="mesa_prefix"):
            store.get_proyeccion_sv_by_mesa_prefix(bad)


def test_get_proyeccion_sv_by_mesa_prefix_filtra_por_prefijo_estricto(
    tmp_path: Path,
) -> None:
    """Verifica que '900' no incluya mesas '100100' (que no comienzan con 900)."""
    store = DataStore(tmp_path)
    _seed_agrupaciones(
        store, {"8": "FUERZA POPULAR", "10": "JUNTOS POR EL PERU", "80": "VOTOS EN BLANCO", "81": "VOTOS NULOS"}
    )

    _seed_mesa_1v_2v(
        store, "900001",
        ubigeo="010101", electores=100,
        emitidos_1v=80,
        votos_1v={"8": 10, "10": 60, "80": 5, "81": 5},
        emitidos_2v=75,
        votos_2v={"8": 25, "10": 50, "80": 0, "81": 0},
    )
    _seed_mesa_1v_2v(
        store, "901000",
        ubigeo="010102", electores=100,
        emitidos_1v=70,
        votos_1v={"8": 5, "10": 50, "80": 10, "81": 5},
        emitidos_2v=70,
        votos_2v={"8": 20, "10": 50, "80": 0, "81": 0},
    )

    # Prefijo "900" debe incluir solo mesa 900001
    r900 = store.get_proyeccion_sv_by_mesa_prefix("900")
    assert r900["primera_vuelta"]["mesas"] == 1
    assert r900["segunda_vuelta_observada"]["keiko"] == 25

    # Prefijo "9" debe incluir ambas mesas
    r9 = store.get_proyeccion_sv_by_mesa_prefix("9")
    assert r9["primera_vuelta"]["mesas"] == 2
    assert r9["segunda_vuelta_observada"]["keiko"] == 45  # 25 + 20
    assert r9["segunda_vuelta_observada"]["sanchez"] == 100  # 50 + 50


# ─────────────────────────────────────────────────────────────────────────────
# get_sv_conteo_actual: lee resultado SV desde cache hidratado (cache-first)
# ─────────────────────────────────────────────────────────────────────────────

def _seed_sv_minimal(store: DataStore) -> None:
    """Helper: poblar tablas SV mínimas para tests del conteo de segunda vuelta."""
    now = store.now_iso()
    with store._connect() as conn:
        # Crear tablas SV si no existen (en algunas DBs nuevas el _init_schema
        # no las incluye porque vienen de un bootstrap externo)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sv_resumen_nacional (
                partido_id TEXT, nombre_candidato TEXT, nombre_agrupacion TEXT,
                votos_validos INTEGER, pct_votos_validos REAL, pct_votos_emitidos REAL,
                actas_contabilizadas_pct REAL, contabilizadas INTEGER, total_actas INTEGER,
                participacion_ciudadana REAL, fecha_actualizacion TEXT, fuente TEXT,
                loaded_at TEXT
            );
            CREATE TABLE IF NOT EXISTS mesas_sv (
                codigo_mesa TEXT PRIMARY KEY, id_ubigeo TEXT, nombre_local TEXT,
                id_ambito INTEGER, electores_habiles INTEGER, votos_emitidos INTEGER,
                votos_validos INTEGER, total_asistentes INTEGER,
                codigo_estado_acta TEXT, fetched_at TEXT
            );
            CREATE TABLE IF NOT EXISTS votos_sv (
                codigo_mesa TEXT, partido_id TEXT, votos INTEGER, fetched_at TEXT,
                PRIMARY KEY (codigo_mesa, partido_id)
            );
            """
        )

        conn.execute(
            """INSERT INTO sv_resumen_nacional
            (partido_id, nombre_candidato, nombre_agrupacion, votos_validos,
             pct_votos_validos, pct_votos_emitidos, actas_contabilizadas_pct,
             contabilizadas, total_actas, participacion_ciudadana,
             fecha_actualizacion, fuente, loaded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("8", "KEIKO FUJIMORI", "FUERZA POPULAR", 9_035_493, 50.003, 0.0,
             98.25, 91146, 92766, 70.75, now, "test", now),
        )
        conn.execute(
            """INSERT INTO sv_resumen_nacional
            (partido_id, nombre_candidato, nombre_agrupacion, votos_validos,
             pct_votos_validos, pct_votos_emitidos, actas_contabilizadas_pct,
             contabilizadas, total_actas, participacion_ciudadana,
             fecha_actualizacion, fuente, loaded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("10", "ROBERTO SANCHEZ", "JUNTOS POR EL PERU", 9_034_466, 49.997, 0.0,
             98.25, 91146, 92766, 70.75, now, "test", now),
        )

        for codigo, estado, electores, k_votos, s_votos in [
            ("100001", "C", 300, 150, 130),
            ("100002", "E", 250, 100, 80),
            ("100003", "P", 200, 0, 0),
        ]:
            conn.execute(
                """INSERT INTO mesas_sv (codigo_mesa, id_ubigeo, nombre_local, id_ambito,
                electores_habiles, votos_emitidos, votos_validos, total_asistentes,
                codigo_estado_acta, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (codigo, "150101", "LOCAL TEST", 1, electores, k_votos + s_votos,
                 k_votos + s_votos, k_votos + s_votos, estado, now),
            )
            if k_votos:
                conn.execute(
                    "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
                    (codigo, "8", k_votos, now),
                )
            if s_votos:
                conn.execute(
                    "INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at) VALUES (?,?,?,?)",
                    (codigo, "10", s_votos, now),
                )


def test_get_sv_conteo_actual_devuelve_oficial_desglose_y_proyectado(tmp_path: Path) -> None:
    store = DataStore(tmp_path)
    _seed_sv_minimal(store)

    result = store.get_sv_conteo_actual()

    assert result["sv_hidratada"] is True

    oficial = result["oficial"]
    assert oficial["actas_contabilizadas"] == 91146
    assert oficial["total_actas"] == 92766
    assert oficial["pct_contabilizadas"] == round(91146 / 92766 * 100, 4)
    assert oficial["participacion"] == 70.75
    nombres = [c["nombre"] for c in oficial["candidatos"]]
    assert "KEIKO FUJIMORI" in nombres
    assert "ROBERTO SANCHEZ" in nombres

    desglose = {row["codigo_estado"]: row for row in result["desglose_por_estado"]}
    assert desglose["C"]["mesas"] == 1
    assert desglose["C"]["keiko"] == 150
    assert desglose["C"]["sanchez"] == 130
    assert desglose["C"]["margen_keiko_sanchez"] == 20
    assert desglose["E"]["mesas"] == 1
    assert desglose["E"]["keiko"] == 100
    assert desglose["E"]["sanchez"] == 80
    assert desglose["P"]["mesas"] == 1
    assert desglose["P"]["keiko"] == 0

    proy = result["proyectado_con_crudo"]
    assert proy["keiko"] == 250  # 150 + 100
    assert proy["sanchez"] == 210  # 130 + 80
    assert proy["margen_keiko_sanchez"] == 40
    assert proy["pct_keiko"] > proy["pct_sanchez"]


def test_get_sv_conteo_actual_sin_tablas_sv_retorna_no_hidratada(tmp_path: Path) -> None:
    """Si las tablas SV no existen, debe retornar estructura vacía con sv_hidratada=False."""
    store = DataStore(tmp_path)

    with store._connect() as conn:
        for tabla in ("sv_resumen_nacional", "mesas_sv", "votos_sv"):
            conn.execute(f"DROP TABLE IF EXISTS {tabla}")

    result = store.get_sv_conteo_actual()

    assert result["sv_hidratada"] is False
    assert result["oficial"]["candidatos"] == []
    assert result["desglose_por_estado"] == []
    assert result["proyectado_con_crudo"]["keiko"] == 0
    assert result["proyectado_con_crudo"]["sanchez"] == 0


def test_get_sv_conteo_actual_no_consulta_onpe_live(tmp_path: Path, monkeypatch) -> None:
    """Garantiza que la lectura SV es 100% offline desde SQLite — nunca toca la red."""
    import urllib.request as urlreq

    def _fail_network(*args, **kwargs):
        raise AssertionError(
            "get_sv_conteo_actual NO debe abrir conexiones de red; debe usar solo SQLite"
        )

    monkeypatch.setattr(urlreq, "urlopen", _fail_network)
    try:
        import curl_cffi.requests as cffi
        monkeypatch.setattr(cffi, "get", _fail_network, raising=False)
    except ImportError:
        pass

    store = DataStore(tmp_path)
    _seed_sv_minimal(store)

    result = store.get_sv_conteo_actual()
    assert result["sv_hidratada"] is True
    assert result["oficial"]["actas_contabilizadas"] == 91146
