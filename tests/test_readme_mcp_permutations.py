from __future__ import annotations

import pytest

from onpe_mcp import server as srv


README_CASES_2026 = [
    "dame los resultados de la mesa 900100 en 2026",
    "cuántos votos sacó Keiko Fujimori a nivel nacional en 2026",
    "resultados segunda vuelta en Lima 2026 — top candidatos",
    "top 5 en Puno 2026 — quiénes fueron los más votados",
    "cuál es la cobertura de actas en segunda vuelta 2026",
    "qué locales se reasignaron en Trujillo entre vueltas",
    "cómo fluyeron los votos en las mesas 900K",
    "top 3 de candidatos en Suecia 2026",
]


def _skip_if_not_hydrated() -> None:
    d = srv.onpe_health().get("data", {})
    if not d.get("hydrated"):
        pytest.skip("MCP local no está hidratado")


@pytest.mark.parametrize("query", README_CASES_2026)
def test_readme_2026_queries_answer_with_mcp(query: str) -> None:
    _skip_if_not_hydrated()
    r = srv.onpe_chat(query)
    assert r.get("ok") is True, query
    data = r.get("data") or {}
    assert isinstance(data.get("answer"), str) and data["answer"].strip(), query
    assert data.get("source") not in {"onpe_live", "onpe_live_unavailable", "api_error"}, query


def test_multi_input_mesas_batch() -> None:
    _skip_if_not_hydrated()
    r = srv.onpe_get_mesas_batch(["900100", "900101", "900102"], id_eleccion=10)
    assert r.get("ok") is True
    d = r.get("data") or {}
    assert d.get("total") == 3
    assert isinstance(d.get("items"), list) and len(d["items"]) == 3


def test_multi_input_mesas_chat_query() -> None:
    _skip_if_not_hydrated()
    q = "dame los resultados de las mesas 900100, 900101, 900102 en 2026"
    r = srv.onpe_chat(q)
    assert r.get("ok") is True
    d = r.get("data") or {}
    assert d.get("intent") == "mesa_batch"
    result = d.get("result") or {}
    assert result.get("total") == 3


def test_multi_input_departamentos_loop() -> None:
    _skip_if_not_hydrated()
    for dep in ["LIMA", "AREQUIPA", "CUSCO"]:
        r = srv.onpe_resultados_geo(nivel="departamento", filtro=dep, top_n=3)
        assert r.get("ok") is True, dep
        data = r.get("data")
        rows = data.get("resultados", []) if isinstance(data, dict) else (data or [])
        assert isinstance(rows, list), dep


def test_multi_input_paises_loop() -> None:
    _skip_if_not_hydrated()
    for pais in ["ARGENTINA", "CHILE", "ESPAÑA"]:
        r = srv.onpe_sv_resultados_geo(nivel="pais_exterior", nombre=pais, top_n=3)
        assert r.get("ok") is True, pais
        rows = (r.get("data") or {}).get("resultados") or []
        assert isinstance(rows, list), pais


def test_cusco_sv_geo_matches_cross_year_2026_v2() -> None:
    _skip_if_not_hydrated()
    r_geo = srv.onpe_sv_resultados_geo(nivel="departamento", nombre="CUSCO", top_n=10)
    r_cross = srv.onpe_comparacion_geo_cross_year(
        geo_name="CUSCO",
        nivel="departamento",
        anio_a=2021,
        anio_b=2026,
        vuelta_a=2,
        vuelta_b=2,
        top_n=10,
    )
    assert r_geo.get("ok") is True
    assert r_cross.get("ok") is True

    geo_rows = (r_geo.get("data") or {}).get("resultados") or []
    cross_b = ((r_cross.get("data") or {}).get("lado_b") or {})
    cross_rows = cross_b.get("top") or []

    geo_by_pid = {str(x.get("partido_id")): int(x.get("votos_validos") or 0) for x in geo_rows}
    cross_by_pid = {str(x.get("partido_id")): int(x.get("votos") or 0) for x in cross_rows}

    assert cross_by_pid.get("8") == geo_by_pid.get("8")
    assert cross_by_pid.get("10") == geo_by_pid.get("10")
    assert int(cross_b.get("total_validos") or 0) == sum(int(x.get("votos_validos") or 0) for x in geo_rows)
