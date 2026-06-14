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
