"""Tests de comportamiento conversacional de onpe_chat.

Todos los tests usan monkeypatch para evitar llamadas HTTP y efectos en SQLite.
Cubre los intents: mesa, geo (extranjero), geo_domestic, legislative, range_reasoning,
range_existence_verify y range_claim_verify.
"""
from __future__ import annotations

import dataclasses
from typing import Any

import onpe_mcp.server as server_module
from onpe_mcp.onpe_api import DistrictItem
from onpe_mcp.server import onpe_chat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disable_autosync(monkeypatch) -> None:
    """Reemplaza settings con auto_sync_foreign_catalog_on_demand=False y auto_hydrate_on_demand=False."""
    monkeypatch.setattr(
        server_module,
        "settings",
        dataclasses.replace(
            server_module.settings,
            auto_sync_foreign_catalog_on_demand=False,
            auto_hydrate_on_demand=False,
        ),
    )


_FAKE_COVERAGE_EMPTY: dict[str, Any] = {
    "total_mesas": 0, "mesas_con_votos": 0,
    "votos_emitidos": 0, "votos_validos": 0,
    "coverage_pct": 0.0, "verdict": "sin_datos", "hydrated_this_call": 0,
}

_FAKE_COVERAGE_WITH_DATA: dict[str, Any] = {
    "total_mesas": 45, "mesas_con_votos": 45,
    "votos_emitidos": 7200, "votos_validos": 6800,
    "coverage_pct": 100.0, "verdict": "completo", "hydrated_this_call": 0,
}


def _noop(*_a: Any, **_kw: Any) -> None:
    return None


def _setup_range_reasoning(
    monkeypatch,
    *,
    candidate_map: dict[str, str] | None = None,
    aggregates: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
) -> None:
    """Mocks comunes para tests del intent range_reasoning."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(
        server_module.store,
        "load_candidate_map",
        lambda path: candidate_map if candidate_map is not None
        else {"P1": "RAFAEL LOPEZ ALIAGA CAZORLA"},
    )
    monkeypatch.setattr(
        server_module.store,
        "aggregate_votes_by_party",
        lambda ubigeos=None: aggregates if aggregates is not None
        else [{"partido_id": "P1", "nombre_partido": "HONOR Y DEMOCRACIA", "total_votos": 100}],
    )
    default_analysis: dict[str, Any] = {
        "mesa_prefix": "",
        "total_mesas_prefijo": 5,
        "mesas_con_votos": 4,
        "mesas_primero": 3,
        "lugares": [
            {
                "ubigeo": "150101",
                "local_votacion": "IE LIMA NORTE",
                "continente": "",
                "pais": "",
                "ciudad": "",
                "mesas_primero": 2,
            },
            {
                "ubigeo": "150102",
                "local_votacion": "IE LIMA SUR",
                "continente": "",
                "pais": "",
                "ciudad": "",
                "mesas_primero": 1,
            },
        ],
    }
    monkeypatch.setattr(
        server_module.store,
        "candidate_first_places_by_mesa_prefix",
        lambda **kw: {**default_analysis, "mesa_prefix": kw.get("mesa_prefix", ""), **(analysis or {})},
    )
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    # Also stub describe and all_first_places to prevent accidental triggers
    monkeypatch.setattr(
        server_module.store, "describe_mesa_prefix",
        lambda prefix, **kw: {"mesa_prefix": prefix, "total_mesas": 0, "total_votos_emitidos": 0,
                               "total_electores_habiles": 0, "locations": []},
    )
    monkeypatch.setattr(
        server_module.store, "all_first_places_by_prefix",
        lambda prefix, **kw: {"mesa_prefix": prefix, "total_mesas": 0, "mesas_con_votos": 0, "ranking": []},
    )
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])


# ---------------------------------------------------------------------------
# 1. Mesa por número natural: "consulta mesa 900100"
# ---------------------------------------------------------------------------

def test_consulta_mesa_por_numero(monkeypatch) -> None:
    """'consulta mesa 900100' debe resolver como intent=mesa sin ambigüedad geo."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "get_cached_mesa", lambda code, ttl: None)
    # Simula mesa en DB local (Tier 1b) — evita llamada al API
    local_bundle: dict[str, Any] = {
        "codigo_mesa": "900100",
        "found": True,
        "mesa_data": {
            "codigo_mesa": "900100",
            "ubigeo": "160101",
            "local_votacion": "IE LORETO",
            "electores_habiles": 200,
            "votos_emitidos": 180,
            "votos_validos": 175,
            "blancos": 2,
            "nulos": 3,
            "impugnados": 0,
            "estado_acta": "Contabilizada",
        },
        "agrupaciones": [],
        "votos": [{"partido_id": "35", "nombre_partido": "RENOVACION POPULAR", "votos": 80}],
        "source": "local_db",
    }
    monkeypatch.setattr(server_module.store, "get_mesa_from_local", lambda code: local_bundle)
    monkeypatch.setattr(server_module.store, "load_candidate_map", lambda path: {"35": "RAFAEL LOPEZ ALIAGA CAZORLA"})
    monkeypatch.setattr(server_module.store, "describe_mesa_prefix", lambda p, **kw: {"total_mesas": 0, "mesa_prefix": p, "total_votos_emitidos": 0, "total_electores_habiles": 0, "locations": []})
    monkeypatch.setattr(server_module.store, "all_first_places_by_prefix", lambda p, **kw: {"total_mesas": 0, "mesa_prefix": p, "mesas_con_votos": 0, "ranking": []})
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)

    result = onpe_chat("consulta mesa 900100")

    assert result["ok"] is True
    assert result["data"]["intent"] == "mesa"
    assert result["data"]["result"]["codigo_mesa"] == "900100"
    assert result["data"]["result"]["found"] is True
    assert result["data"]["source"] == "local_db"
    assert "Contabilizada" in result["data"]["answer"]


# ---------------------------------------------------------------------------
# 2. Geo extranjero: "top 3 de candidatos en Suecia"
# ---------------------------------------------------------------------------

def test_geo_extranjero_candidatos_en_suecia(monkeypatch) -> None:
    """'top 3 de candidatos en Suecia' debe resolver como intent=geo con 3 resultados."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(
        server_module,
        "_resolve_foreign_geo_query",
        lambda q: (
            None,
            "suecia",
            [{"ubigeo": "EU001", "Continente": "EUROPA", "pais": "SUECIA", "ciudad": "ESTOCOLMO"}],
        ),
    )
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "get_geo_query_cache", lambda key, ttl: None)
    monkeypatch.setattr(
        server_module.store,
        "aggregate_votes_by_party",
        lambda ubigeos=None: [
            {"partido_id": "P1", "nombre_partido": "FUERZA POPULAR", "total_votos": 55},
            {"partido_id": "P2", "nombre_partido": "ALIANZA", "total_votos": 30},
            {"partido_id": "P3", "nombre_partido": "OTRO", "total_votos": 10},
        ],
    )
    monkeypatch.setattr(server_module.store, "count_mesas_by_ubigeos", lambda ubigeos: 3)
    monkeypatch.setattr(server_module.store, "upsert_geo_query_cache", _noop)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])

    result = onpe_chat("top 3 de candidatos en Suecia")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "geo"
    assert data["result"]["query"] == "suecia"
    assert data["result"]["top_n"] == 3
    assert data["result"]["ubigeos_match"] == 1
    assert len(data["result"]["top_partidos"]) == 3


# ---------------------------------------------------------------------------
# 3. Geo extranjero por ciudad: "resultados en Estocolmo"
# ---------------------------------------------------------------------------

def test_geo_extranjero_ciudad_estocolmo(monkeypatch) -> None:
    """'resultados en Estocolmo' debe resolver como intent=geo usando la ciudad."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(
        server_module,
        "_resolve_foreign_geo_query",
        lambda q: (
            None,
            "estocolmo",
            [{"ubigeo": "EU001", "Continente": "EUROPA", "pais": "SUECIA", "ciudad": "ESTOCOLMO"}],
        ),
    )
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "get_geo_query_cache", lambda key, ttl: None)
    monkeypatch.setattr(server_module.store, "aggregate_votes_by_party", lambda ubigeos=None: [])
    monkeypatch.setattr(server_module.store, "count_mesas_by_ubigeos", lambda ubigeos: 0)
    monkeypatch.setattr(server_module.store, "upsert_geo_query_cache", _noop)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])

    result = onpe_chat("resultados en Estocolmo")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "geo"
    assert data["result"]["query"] == "estocolmo"
    assert data["result"]["is_partial"] is True


# ---------------------------------------------------------------------------
# 4. Geo doméstico: "top 3 en Loreto"
# ---------------------------------------------------------------------------

def test_geo_domestico_loreto(monkeypatch) -> None:
    """'top 3 en Loreto' debe resolver como intent=geo_domestic con dept_prefix='16'."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(
        server_module,
        "_resolve_domestic_geo_query",
        lambda q: ("loreto", {"160101", "160102"}),
    )
    monkeypatch.setattr(
        server_module,
        "find_peru_department_prefix",
        lambda q: ("loreto", "16"),
    )
    monkeypatch.setattr(server_module.store, "get_geo_query_cache", lambda key, ttl: None)
    monkeypatch.setattr(
        server_module.store,
        "aggregate_votes_by_party",
        lambda ubigeos=None: [
            {"partido_id": "P1", "nombre_partido": "FUERZA POPULAR", "total_votos": 80},
            {"partido_id": "P2", "nombre_partido": "ALIANZA", "total_votos": 40},
        ],
    )
    monkeypatch.setattr(server_module.store, "count_mesas_by_ubigeos", lambda ubigeos: 2)
    monkeypatch.setattr(server_module.store, "upsert_geo_query_cache", _noop)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])

    result = onpe_chat("top 3 en Loreto")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "geo_domestic"
    assert data["result"]["dept_prefix"] == "16"
    assert data["result"]["top_n"] == 3
    assert data["result"]["mesas_match"] == 2
    assert data["result"]["ubigeos_match"] == 2


# ---------------------------------------------------------------------------
# 5. Legislativo con preposición "para": "senadores top 10 para Cuzco"
# ---------------------------------------------------------------------------

def test_legislativo_senadores_para_cusco(monkeypatch) -> None:
    """'senadores top 10 para Cuzco' debe resolver como intent=legislative_top_candidate
    usando la preposición 'para' para extraer el distrito 'Cuzco'."""
    monkeypatch.setattr(
        server_module.onpe_api,
        "resolve_district",
        lambda q: DistrictItem(id_distrito_electoral=8, nombre="CUSCO")
        if "cuzco" in q.lower() or "cusco" in q.lower()
        else None,
    )
    monkeypatch.setattr(
        server_module.onpe_api,
        "get_candidates_by_district",
        lambda **kw: [
            {
                "nombre_candidato": "JUAN PEREZ QUISPE",
                "nombre_agrupacion": "FUERZA POPULAR",
                "codigo_agrupacion": "P1",
                "votos_validos": 5000,
                "lista": None,
            },
            {
                "nombre_candidato": "MARIA GARCIA FLORES",
                "nombre_agrupacion": "ALIANZA PERU",
                "codigo_agrupacion": "P2",
                "votos_validos": 4200,
                "lista": None,
            },
        ],
    )
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)

    result = onpe_chat("senadores top 10 para Cuzco")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "legislative_top_candidate"
    assert data["result"]["cargo"] == "senadores"
    assert data["result"]["distrito"]["nombre"] == "CUSCO"
    assert "JUAN PEREZ QUISPE" in data["answer"]
    assert len(data["result"]["top_10"]) == 2


# ---------------------------------------------------------------------------
# 6. Consulta ambigua o incompleta → intent=unknown con mensaje útil
# ---------------------------------------------------------------------------

def test_consulta_ambigua_devuelve_unknown(monkeypatch) -> None:
    """Una consulta sin intención clara debe retornar intent=unknown con ejemplos de uso."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)

    # Query genuinamente ambigua: sin candidato, geo, ni contexto electoral claro
    result = onpe_chat("dame algo")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "unknown"
    assert "No identifiqué" in data["answer"]
    assert "mesa" in data["answer"].lower()
    assert data["source"] == "knowledge_base"
    assert data["data_tier"] == "tier_3_knowledge_base"


# ---------------------------------------------------------------------------
# 7–11. Range reasoning: razonamiento por prefijo de mesas
# ---------------------------------------------------------------------------

def test_range_reasoning_fue_primero_candidato(monkeypatch) -> None:
    """'fue primero López Aliaga' → extraer candidato DESPUÉS de 'primero'."""
    _setup_range_reasoning(monkeypatch)

    result = onpe_chat(
        "De las mesas que arrancan en 900000 quiero saber en qué lugares fue primero López Aliaga"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_reasoning"
    assert data["result"]["mesa_prefix"] == "900000"
    assert data["result"]["candidate"] == "López Aliaga"
    assert data["result"]["mesas_primero"] == 3
    assert len(data["result"]["lugares"]) == 2
    assert data["result"]["lugares"][0]["local_votacion"] == "IE LIMA NORTE"


def test_range_reasoning_gano_candidato(monkeypatch) -> None:
    """'ganó López Aliaga' → patrón alternativo sin 'primero'."""
    _setup_range_reasoning(monkeypatch)

    result = onpe_chat(
        "en qué mesas que empiezan en 90000 ganó López Aliaga"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_reasoning"
    assert data["result"]["mesa_prefix"] == "90000"
    assert "Lopez Aliaga" in data["result"]["candidate"] or "López Aliaga" in data["result"]["candidate"]
    assert "P1" in data["result"]["matched_partido_ids"]


def test_range_reasoning_candidato_primero_orden_inverso(monkeypatch) -> None:
    """'fue López Aliaga primero' → patrón con candidato ANTES de 'primero'."""
    _setup_range_reasoning(monkeypatch)

    result = onpe_chat(
        "En qué mesas del prefijo 900 fue López Aliaga primero"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_reasoning"
    assert data["result"]["mesa_prefix"] == "900"
    assert "Lopez Aliaga" in data["result"]["candidate"] or "López Aliaga" in data["result"]["candidate"]


def test_range_reasoning_sin_prefijo_pide_aclaracion(monkeypatch) -> None:
    """Sin número de prefijo → respuesta de aclaración, no error."""
    _setup_range_reasoning(monkeypatch)

    result = onpe_chat(
        "en las mesas que arrancan fue primero López Aliaga"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_reasoning"
    assert data["source"] == "clarification_needed"
    assert "prefijo" in data["answer"].lower()
    assert data["result"] is None


def test_range_reasoning_candidato_no_encontrado(monkeypatch) -> None:
    """Candidato desconocido → respuesta parcial honesta, sin inventar resultados."""
    _setup_range_reasoning(
        monkeypatch,
        candidate_map={"P1": "RAFAEL LOPEZ ALIAGA CAZORLA"},
        aggregates=[
            {"partido_id": "P1", "nombre_partido": "HONOR Y DEMOCRACIA", "total_votos": 100}
        ],
    )

    result = onpe_chat(
        "De las mesas que arrancan en 90000 fue primero Mickey Mouse"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_reasoning"
    assert data["result"] is not None
    assert "candidate" in data["result"]
    assert data["result"]["candidate"] == "Mickey Mouse"
    assert "Mickey Mouse" in data["answer"] or "no encontré" in data["answer"].lower()


# ---------------------------------------------------------------------------
# 12–13. Range existence verify: responder a "mesas fantasma"
# ---------------------------------------------------------------------------

def _setup_existence_verify(monkeypatch) -> None:
    """Mocks para tests de range_existence_verify."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])
    monkeypatch.setattr(
        server_module.store, "all_first_places_by_prefix",
        lambda p, **kw: {"mesa_prefix": p, "total_mesas": 0, "mesas_con_votos": 0, "ranking": []},
    )


def test_range_existence_verify_con_datos(monkeypatch) -> None:
    """'las mesas 900 son fantasma' → muestra que SÍ existen con ubicaciones reales."""
    _setup_existence_verify(monkeypatch)
    fake_description = {
        "mesa_prefix": "900",
        "total_mesas": 45,
        "total_votos_emitidos": 7200,
        "total_electores_habiles": 9000,
        "locations": [
            {
                "ubigeo": "160101",
                "local_votacion": "IE LORETO 01",
                "pais": "",
                "ciudad": "",
                "num_mesas": 20,
                "votos_emitidos": 3200,
                "electores_habiles": 4000,
            },
            {
                "ubigeo": "160201",
                "local_votacion": "IE LORETO 02",
                "pais": "",
                "ciudad": "",
                "num_mesas": 25,
                "votos_emitidos": 4000,
                "electores_habiles": 5000,
            },
        ],
    }
    monkeypatch.setattr(
        server_module.store, "describe_mesa_prefix",
        lambda prefix, **kw: {**fake_description, "mesa_prefix": prefix},
    )

    result = onpe_chat("mi amigo dice que las mesas 900 no existen son fantasma")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_existence_verify"
    assert data["result"]["total_mesas"] == 45
    assert "SÍ existen" in data["answer"] or "sí existen" in data["answer"].lower()
    assert "45" in data["answer"]
    assert data["source"] == "sqlite"


def test_range_existence_verify_sin_datos(monkeypatch) -> None:
    """Sin datos en cache → respuesta parcial honesta con instrucción de hidratación."""
    _setup_existence_verify(monkeypatch)
    monkeypatch.setattr(
        server_module.store, "describe_mesa_prefix",
        lambda prefix, **kw: {"mesa_prefix": prefix, "total_mesas": 0, "total_votos_emitidos": 0,
                               "total_electores_habiles": 0, "locations": []},
    )

    result = onpe_chat("hay mesas fantasma en el rango 900 no existen")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_existence_verify"
    assert data["result"]["total_mesas"] == 0
    assert data["source"] == "sqlite_empty"


# ---------------------------------------------------------------------------
# 16. Año no se interpreta como mesa: "elecciones 2021 vs 2026"
# ---------------------------------------------------------------------------

def test_año_no_interpretado_como_mesa(monkeypatch) -> None:
    """'¿quién ganó en 2021?' no debe disparar intent=mesa — 2021 es un año, no mesa."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)

    result = onpe_chat("quien gano las elecciones en 2021")

    assert result["ok"] is True
    data = result["data"]
    # No debe tratarse como consulta de mesa (código 2021 no es válido como mesa sin keyword "mesa")
    assert data["intent"] != "mesa", (
        "Una consulta con '2021' sin la palabra 'mesa' NO debe resolverse como intent=mesa"
    )


# ---------------------------------------------------------------------------
# 17. Mesa con año explícito SÍ funciona: "dame los resultados de la mesa 002021"
# ---------------------------------------------------------------------------

def test_mesa_con_numero_que_parece_año_pero_tiene_keyword(monkeypatch) -> None:
    """'dame los resultados de la mesa 002021' SÍ debe tratarse como intent=mesa."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "get_cached_mesa", lambda code, ttl: None)
    local_bundle: dict[str, Any] = {
        "codigo_mesa": "002021",
        "found": True,
        "mesa_data": {
            "codigo_mesa": "002021",
            "ubigeo": "150101",
            "local_votacion": "IE LIMA NORTE",
            "electores_habiles": 180,
            "votos_emitidos": 150,
            "votos_validos": 145,
            "blancos": 2,
            "nulos": 3,
            "impugnados": 0,
            "estado_acta": "Contabilizada",
        },
        "agrupaciones": [],
        "votos": [],
        "source": "local_db",
    }
    monkeypatch.setattr(server_module.store, "get_mesa_from_local", lambda code: local_bundle)
    monkeypatch.setattr(server_module.store, "load_candidate_map", lambda path: {})
    monkeypatch.setattr(server_module.store, "describe_mesa_prefix", lambda p, **kw: {"total_mesas": 0, "mesa_prefix": p, "total_votos_emitidos": 0, "total_electores_habiles": 0, "locations": []})
    monkeypatch.setattr(server_module.store, "all_first_places_by_prefix", lambda p, **kw: {"total_mesas": 0, "mesa_prefix": p, "mesas_con_votos": 0, "ranking": []})
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)

    result = onpe_chat("dame los resultados de la mesa 002021")

    assert result["ok"] is True
    assert result["data"]["intent"] == "mesa"


# ---------------------------------------------------------------------------
# 18. Senadores con endpoint no disponible → respuesta graceful (no error 500)
# ---------------------------------------------------------------------------

def test_senadores_endpoint_no_disponible_respuesta_graceful(monkeypatch) -> None:
    """Si el endpoint de senadores devuelve HTML/falla, debe retornar respuesta útil, no excepción."""
    from onpe_mcp.onpe_api import OnpeApiError, DistrictItem

    monkeypatch.setattr(
        server_module.onpe_api,
        "resolve_district",
        lambda q: DistrictItem(id_distrito_electoral=1, nombre="AREQUIPA"),
    )

    def _raise_html_error(**kw):
        raise OnpeApiError("Respuesta HTML inesperada del servidor ONPE")

    monkeypatch.setattr(server_module.onpe_api, "get_candidates_by_district", _raise_html_error)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)

    result = onpe_chat("senador más votado en Arequipa")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "legislative_top_candidate"
    assert data["result"]["available"] is False
    assert "AREQUIPA" in data["answer"] or "arequipa" in data["answer"].lower()
    # No debe haber error en el wrapper externo
    assert result.get("errors", []) == []


# ---------------------------------------------------------------------------
# 19. Hidratación mandatoria: DB vacía retorna db_not_hydrated, NO error
# ---------------------------------------------------------------------------

def test_db_vacia_retorna_db_not_hydrated(monkeypatch) -> None:
    """Con DB vacía onpe_chat debe retornar intent=db_not_hydrated con instrucciones, no error."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module.store, "total_mesas_local", lambda: 0)

    result = onpe_chat("top 5 en Lima")

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "db_not_hydrated"
    assert data["hydrated"] is False
    assert "next_step" in data
    assert data["total_mesas_local"] == 0
    assert "bootstrap" in data["answer"].lower() or "hidrat" in data["answer"].lower()


# ---------------------------------------------------------------------------
# 14–15. Range claim verify: refutar claims de fraude
# ---------------------------------------------------------------------------

def _setup_claim_verify(monkeypatch) -> None:
    """Mocks para tests de range_claim_verify."""
    _disable_autosync(monkeypatch)
    monkeypatch.setattr(server_module, "_resolve_foreign_geo_query", lambda q: None)
    monkeypatch.setattr(server_module, "_resolve_domestic_geo_query", lambda q: None)
    monkeypatch.setattr(server_module.store, "append_raw_event", _noop)
    monkeypatch.setattr(server_module.store, "get_coverage_metrics", lambda **kw: _FAKE_COVERAGE_EMPTY)
    monkeypatch.setattr(server_module.store, "get_uncovered_mesas", lambda **kw: [])
    monkeypatch.setattr(
        server_module.store, "describe_mesa_prefix",
        lambda p, **kw: {"mesa_prefix": p, "total_mesas": 0, "total_votos_emitidos": 0,
                         "total_electores_habiles": 0, "locations": []},
    )
    monkeypatch.setattr(
        server_module.store, "load_candidate_map",
        lambda path: {"35": "RAFAEL LOPEZ ALIAGA CAZORLA", "1": "DINA BOLUARTE ZEGARRA"},
    )


def test_range_claim_verify_refuta_fraude(monkeypatch) -> None:
    """'hay fraude porque solo sale Sanchez primero en mesas 900K' → refutar con ranking real."""
    _setup_claim_verify(monkeypatch)
    monkeypatch.setattr(
        server_module.store, "all_first_places_by_prefix",
        lambda prefix, **kw: {
            "mesa_prefix": prefix,
            "total_mesas": 50,
            "mesas_con_votos": 45,
            "ranking": [
                {"partido_id": "1", "nombre_partido": "FUERZA DEL PUEBLO", "mesas_primero": 20},
                {"partido_id": "35", "nombre_partido": "HONOR Y DEMOCRACIA", "mesas_primero": 15},
                {"partido_id": "8", "nombre_partido": "FUERZA POPULAR", "mesas_primero": 10},
            ],
        },
    )

    result = onpe_chat(
        "hay fraude porque en las mesas 900 solo sale Sanchez primero"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_claim_verify"
    assert data["result"]["is_refuted"] is True
    assert data["result"]["ranking"] is not None
    assert len(data["result"]["ranking"]) > 1
    assert "No" in data["answer"] or "no" in data["answer"]


def test_range_claim_verify_sin_datos(monkeypatch) -> None:
    """Sin datos en cache → respuesta honesta de que falta hidratar."""
    _setup_claim_verify(monkeypatch)
    monkeypatch.setattr(
        server_module.store, "all_first_places_by_prefix",
        lambda prefix, **kw: {"mesa_prefix": prefix, "total_mesas": 0, "mesas_con_votos": 0, "ranking": []},
    )

    result = onpe_chat(
        "hay fraude en las mesas 900 siempre gana el mismo primero"
    )

    assert result["ok"] is True
    data = result["data"]
    assert data["intent"] == "range_claim_verify"
    assert data["result"]["is_partial"] is True
    assert data["source"] == "sqlite_empty"
