"""Cycle 80 — greeting/foreign-geo/resultados-finales/bare-cuantos-votos fixes."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # geo domestic
    ("resultados en Puno", "geo_domestic"),
    ("resultados en Madre de Dios", "geo_domestic"),
    ("top 5 en San Martin", "geo_domestic"),
    ("top candidatos en La Libertad", "geo_domestic"),
    ("quien gano en Huancavelica", "geo_domestic"),
    ("quienes ganaron en Tacna", "geo_domestic"),
    # candidate with geo
    ("cuantos votos obtuvo Fujimori en Cusco", "candidate"),
    ("cuantos votos consiguio Aliaga en Puno", "candidate"),
    # nacional
    ("top 5 a nivel nacional", "nacional"),
    ("quien va ganando", "nacional"),
    ("como van los resultados", "nacional"),
    ("ranking de candidatos", "nacional"),
    ("escrutinio nacional", "nacional"),
    ("resultados finales", "nacional"),
    ("informacion sobre las elecciones 2026", "nacional"),
    ("datos electorales", "nacional"),
    ("resumen electoral", "nacional"),
    ("quienes son los candidatos", "nacional"),
    # foreign geo (intent = "geo")
    ("resultados en Suecia", "geo"),
    ("top 3 en Estocolmo", "geo"),
    ("peruanos en Tokio", "geo"),
    ("votos en Paris", "geo"),
    # legislative
    ("senadores por Cusco", "legislative_top_candidate"),
    ("diputados en Lima", "legislative_top_candidate"),
    # candidate bare forms
    ("cuantos votos Keiko", "candidate"),
    ("cuantos votos Lopez Aliaga", "candidate"),
    ("votos de Urresti", "candidate"),
    ("porcentaje de Nieto", "candidate"),
    ("Lopez Aliaga votos", "candidate"),
    ("Fujimori resultados", "candidate"),
    ("resultados de Keiko Fujimori", "candidate"),
    # multi-candidate
    ("votos de Aliaga y Keiko", "multi_candidate"),
    ("Aliaga y Fujimori cuantos votos", "multi_candidate"),
    # mesa
    ("mesa 123456", "mesa"),
    ("dame la mesa 900100", "mesa"),
    # unknown
    ("el clima en Lima", "unknown"),
    ("hola buenas tardes", "unknown"),
    ("precio del dolar", "unknown"),
    ("cuanto cuesta el pan", "unknown"),
])
def test_cycle80(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
