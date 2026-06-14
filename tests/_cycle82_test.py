"""Cycle 82 — demographics guard, terremoto/pbi non-electoral, como-van-los-votos national, quienes-quedaron national."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # candidate
    ("cuantos votos le sacaron a aliaga", "candidate"),
    ("que tal le fue a keiko", "candidate"),
    ("en que lugar quedo aliaga", "candidate"),
    ("cual fue el porcentaje de fujimori en arequipa", "candidate"),
    ("cuantos votos tiene aliaga hasta ahora", "candidate"),
    # geo domestic
    ("resultados en san martin", "geo_domestic"),
    ("top 5 en la libertad", "geo_domestic"),
    ("cuantos votos en madre de dios", "geo_domestic"),
    ("candidatos en san juan de lurigancho", "geo_domestic"),
    # nacional
    ("todos los candidatos presidenciales", "nacional"),
    ("lista completa de candidatos", "nacional"),
    ("cuantos votos en blanco hubo", "nacional"),
    ("votos nulos a nivel nacional", "nacional"),
    ("porcentaje de votos blancos", "nacional"),
    ("quienes quedaron en el top 5", "nacional"),
    ("quien lidera el conteo", "nacional"),
    ("como van los votos", "nacional"),
    ("cuantos votos totales hubo", "nacional"),
    ("cuantos votos emitidos", "nacional"),
    # mesa
    ("consulta mesa 900100", "mesa"),
    ("informacion de la mesa 005678", "mesa"),
    ("datos mesa numero 123456", "mesa"),
    ("acta 900100", "mesa"),
    # multi-candidate
    ("keiko y aliaga cuantos votos sacaron", "multi_candidate"),
    ("cuantos votos sacaron keiko y urresti", "multi_candidate"),
    ("fujimori vs aliaga", "multi_candidate"),
    # foreign geo
    ("top 3 candidatos en australia", "geo"),
    ("cuantos peruanos votaron en canada", "geo"),
    ("resultados en nueva zelanda", "geo"),
    # unknown
    ("quien fue presidente en 1990", "unknown"),
    ("cuando fue el terremoto de lima", "unknown"),
    ("cuanto mide el machu picchu", "unknown"),
    ("cual es la capital del peru", "unknown"),
    ("quien fue alan garcia", "unknown"),
    ("cuando murio fujimori", "unknown"),
    ("cual es el pbi del peru", "unknown"),
    ("cuantos habitantes tiene lima", "unknown"),
    ("que paso con la constitucion de 1993", "unknown"),
])
def test_cycle82(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
