"""Cycle 84 — avance/recuento/estado-del-conteo national, propuesta guard, acumulados non-candidate."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # candidate (natural phrasing)
    ("cual es el total de votos de aliaga", "candidate"),
    ("cuantos votos en total obtuvo keiko", "candidate"),
    ("votos obtenidos por fujimori", "candidate"),
    ("que tan bien le fue a nieto", "candidate"),
    ("aliaga saco cuantos votos", "candidate"),
    ("cuantos sufragios obtuvo aliaga", "candidate"),
    ("cuantos votos habia obtenido fujimori", "candidate"),
    ("resultados de la candidata mendoza", "candidate"),
    # geo domestic
    ("top 5 en piura", "geo_domestic"),
    ("resultados de lima metropolitana", "geo_domestic"),
    ("candidatos en arequipa", "geo_domestic"),
    ("resultados en la region puno", "geo_domestic"),
    ("quienes ganaron en apurimac", "geo_domestic"),
    ("quien estuvo primero en moquegua", "geo_domestic"),
    ("top 3 en loreto", "geo_domestic"),
    ("votos en huancavelica", "geo_domestic"),
    ("resultados en san martin", "geo_domestic"),
    # nacional
    ("cuantas personas votaron en total", "nacional"),
    ("cual fue el margen de victoria", "nacional"),
    ("segunda vuelta confirmada", "nacional"),
    ("quien encabezo la votacion", "nacional"),
    ("cual fue la participacion electoral", "nacional"),
    ("como va el recuento", "nacional"),
    ("avance de votos", "nacional"),
    ("resultados preliminares", "nacional"),
    ("votos acumulados", "nacional"),
    ("estado actual del conteo", "nacional"),
    # unknown (biographical/editorial)
    ("cuando es navidad", "unknown"),
    ("cuantos anos tiene keiko fujimori", "unknown"),
    ("donde nacio lopez aliaga", "unknown"),
    ("cual es el patrimonio de keiko", "unknown"),
    ("quien es la esposa de aliaga", "unknown"),
    ("cual es el programa de gobierno de fujimori", "unknown"),
    ("en que colegio estudio nieto", "unknown"),
    ("que edad tiene urresti", "unknown"),
    ("cual es la propuesta economica de aliaga", "unknown"),
])
def test_cycle84(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
