"""Cycle 85 — personal-bio guard, standalone-keywords national, villa-el-salvador as geo."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # candidate (typos)
    ("cuantos votos sako aliaga", "candidate"),
    ("cuantos votos obtubo keiko", "candidate"),
    ("cuantos votos tubo fujimori", "candidate"),
    ("cuantos votos se llevo acuna", "candidate"),
    # geo domestic
    ("resultados en san juan de miraflores", "geo_domestic"),
    ("candidatos en el callao", "geo_domestic"),
    ("top en la victoria", "geo_domestic"),
    ("quienes ganaron en jesus maria", "geo_domestic"),
    # foreign geo (intent = "geo" or "ambiguous")
    ("top 5 en villa el salvador", "geo"),
    ("resultados en santiago", "geo"),
    ("cuantos peruanos votaron en boston", "geo"),
    ("votos en madrid", "geo"),
    ("resultados en sao paulo", "geo"),
    ("top 3 en buenos aires", "ambiguous"),
    # nacional
    ("quienes pasaron a la segunda vuelta", "nacional"),
    ("hay segunda vuelta confirmada", "nacional"),
    ("quien enfrenta a quien en segunda vuelta", "nacional"),
    ("cuando es la segunda vuelta", "nacional"),
    ("que candidatos van a segunda vuelta", "nacional"),
    # legislative
    ("senadores para Arequipa", "legislative_top_candidate"),
    ("diputados de Cusco", "legislative_top_candidate"),
    ("congresistas de Lima", "legislative_top_candidate"),
    ("cuantos senadores para Loreto", "legislative_top_candidate"),
    # unknown (biographical)
    ("cuantos hijos tiene aliaga", "unknown"),
    ("donde vive fujimori", "unknown"),
    ("cual es el twitter de keiko", "unknown"),
    ("cuando nacio nieto", "unknown"),
    ("que porcentaje obtenbo nieto", "unknown"),
    ("quienes", "unknown"),
    # standalone nacional keywords
    ("resultados", "nacional"),
    ("votos", "nacional"),
    ("candidatos", "nacional"),
    ("elecciones", "nacional"),
    ("2026", "nacional"),
    ("primera vuelta", "nacional"),
    ("segunda vuelta", "nacional"),
    ("ganador", "nacional"),
    # mesa alone → unknown (not enough context)
    ("mesa", "unknown"),
])
def test_cycle85(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
