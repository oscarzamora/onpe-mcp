"""Cycle 83 — cuantos-le-dieron pattern, definitional guard, cuantas-mesas/ranking/presidencia national."""
import pytest
from onpe_mcp.server import onpe_chat

def intent(q):
    r = onpe_chat(q)
    return (r.get("data") or {}).get("intent", "unknown")

@pytest.mark.parametrize("query,expected", [
    # candidate (regional)
    ("cuantos votos obtuvo aliaga en callao", "candidate"),
    ("cuantos votos obtuvo keiko en puno", "candidate"),
    ("que porcentaje saco aliaga en lima", "candidate"),
    ("cuanto obtuvo nieto en ica", "candidate"),
    ("resultados de keiko en piura", "candidate"),
    ("votos de fujimori en lima", "candidate"),
    ("aliaga en junin cuantos votos", "candidate"),
    ("cuantos le dieron a keiko", "candidate"),
    ("le fue bien a keiko en arequipa", "candidate"),
    ("que tal le fue a lopez aliaga", "candidate"),
    # geo domestic (districts)
    ("top 5 en san isidro", "geo_domestic"),
    ("resultados en lince", "geo_domestic"),
    ("quien gano en miraflores", "geo_domestic"),
    ("candidatos en cusco", "geo_domestic"),
    ("top 3 en puno", "geo_domestic"),
    ("votos en tacna", "geo_domestic"),
    ("quien gano en iquitos", "geo_domestic"),
    ("resultados en trujillo", "geo_domestic"),
    ("top en arequipa", "geo_domestic"),
    ("resultados huancayo", "geo_domestic"),
    # nacional
    ("como estan las elecciones", "nacional"),
    ("quien gano la presidencia", "nacional"),
    ("resultado final de las elecciones", "nacional"),
    ("cuantas mesas se han contado", "nacional"),
    ("porcentaje de participacion", "nacional"),
    ("cual es el ranking actual", "nacional"),
    ("quienes pasaron a segunda vuelta", "nacional"),
    ("cuantos votos validos hubo", "nacional"),
    ("hay segunda vuelta", "nacional"),
    ("quien paso a segunda vuelta", "nacional"),
    # unknown
    ("que temperatura hace en lima hoy", "unknown"),
    ("dame una receta de lomo saltado", "unknown"),
    ("cual es el partido de futbol hoy", "unknown"),
    ("cuanto cuesta un vuelo a cusco", "unknown"),
    ("quien es el presidente del peru", "unknown"),
    ("que es la constitucion", "unknown"),
    ("define democracia", "unknown"),
    ("traducir hola al ingles", "unknown"),
    ("como funciona el sistema electoral peruano", "unknown"),
    ("que es el JNE", "unknown"),
])
def test_cycle83(query, expected):
    assert intent(query) == expected, f"Query: {query!r} → {intent(query)!r} (expected {expected!r})"
