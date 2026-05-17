"""Cycle 79 — resultados-de-X parsing fix + elecciones-trigger + bare resultados."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # resultados Madre de Dios fix
    ("resultados Madre de Dios", "geo_domestic"),
    ("resultados San Martin", "geo_domestic"),
    ("resultados La Libertad", "geo_domestic"),
    ("resultados Madre de Dios 2026", "geo_domestic"),
    # informacion de elecciones → nacional
    ("informacion de elecciones", "nacional"),
    ("datos de las elecciones", "nacional"),
    ("noticias sobre las elecciones", "nacional"),
    ("informacion electoral", "nacional"),
    # standalone resultados → nacional
    ("resultados", "nacional"),
    # bare cuantos votos NAME
    ("cuantos votos Aliaga", "candidate"),
    ("cuantos votos Fujimori", "candidate"),
    ("cuantos votos Keiko", "candidate"),
    # resultados NAME (bare)
    ("resultados Aliaga", "candidate"),
    ("resultados Fujimori", "candidate"),
    # comparar dos departamentos → geo_domestic (both are depts → mc_both_geo cleared)
    ("comparar Arequipa y Lima", "geo_domestic"),
    ("comparar Loreto y Ucayali", "geo_domestic"),
    # extreme typo → unknown
    ("cuantos botoa tubo aliaga", "unknown"),
    # existing non-regressions
    ("resultados en Lima", "geo_domestic"),
    ("resultados Lima", "geo_domestic"),
    ("resultados de Arequipa", "geo_domestic"),
    ("resultados de Loreto", "geo_domestic"),
    ("cuantos votos tuvo Aliaga", "candidate"),
    ("cuantos votos obtuvo Keiko en Lima", "candidate"),
    ("cuantos votos Lima", "geo_domestic"),
    ("cuantos votos Loreto", "geo_domestic"),
])
def test_cycle79(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
