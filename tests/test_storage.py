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
