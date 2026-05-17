"""Cycle 81 — guerra guard, participaron/quien-quedo-segundo/cual-fue-el-resultado national, Mendoza=geo."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # candidate variants
    ("cuantos votos saco aliaga", "candidate"),
    ("que porcentaje tuvo keiko", "candidate"),
    ("cuantos votos jalo urresti", "candidate"),
    ("como le fue a fujimori", "candidate"),
    ("votos para nieto", "candidate"),
    ("resultados de acuna", "candidate"),
    ("aliaga cuantos votos obtuvo", "candidate"),
    ("cuantos puntos tuvo keiko en primera vuelta", "candidate"),
    ("cuantos votos obtuvo rla", "candidate"),
    # geo (Mendoza = Argentine city → geo)
    ("resultados de mendoza", "geo"),
    # geo domestic
    ("top 3 en ayacucho", "geo_domestic"),
    ("resultados en moquegua", "geo_domestic"),
    ("quien gano en ucayali", "geo_domestic"),
    ("candidatos de junin", "geo_domestic"),
    ("cuantos votos hubo en tumbes", "geo_domestic"),
    ("votos en pasco", "geo_domestic"),
    ("quien lidero en amazonas", "geo_domestic"),
    ("top en callao", "geo_domestic"),
    ("resultados cajamarca", "geo_domestic"),
    ("resultados ancash", "geo_domestic"),
    # nacional
    ("quien gano las elecciones", "nacional"),
    ("como quedo la primera vuelta", "nacional"),
    ("lista de todos los candidatos", "nacional"),
    ("cuantos candidatos hubo", "nacional"),
    ("quienes participaron", "nacional"),
    ("quien quedo segundo", "nacional"),
    ("distribucion de votos", "nacional"),
    ("todos los resultados", "nacional"),
    ("cual fue el resultado", "nacional"),
    ("como fue la primera vuelta", "nacional"),
    # foreign geo (intent = "geo")
    ("resultados en canada", "geo"),
    ("votos peruanos en berlin", "geo"),
    ("cuantos votaron en miami", "geo"),
    ("top 5 en new york", "geo"),
    # unknown
    ("que hora es", "unknown"),
    ("como se hace una paella", "unknown"),
    ("cuantos planetas hay", "unknown"),
    ("cuando fue la guerra del pacifico", "unknown"),
    ("quien invento la bombilla", "unknown"),
    ("como llegar al aeropuerto", "unknown"),
])
def test_cycle81(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
