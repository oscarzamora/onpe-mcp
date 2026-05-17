"""Cycle 31 stress tests — 20 queries:
- Candidatos con "el candidato X" sin apellido
- Preguntas de rango "entre X y Y votos"
- Consulta explícita de elecciones presidenciales
- Queries con "a ver" / "déjame ver" coloquial
- Candidato + dos ciudades distintas (geo ambiguo)
- Consulta para candidato fallecido / histórico
- Queries de tabla / ranking completo
- Candidato con "del" en nombre: "Del Castillo"
- Preguntas de tiempo: "hasta ahora", "en este momento"
- Consultas con siglas de partido
"""
import io, logging, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # Candidato explícito
    ("el candidato Aliaga cuantos votos tuvo", "candidate"),
    ("el candidato Keiko cuantos votos saco en Piura", "candidate"),
    # Rango "entre X y Y votos" → no mesa
    ("candidatos entre 10000 y 50000 votos", "nacional"),
    ("quienes tienen entre 500000 y 2000000 votos", "nacional"),
    # Elecciones presidenciales
    ("resultados de las elecciones presidenciales", "nacional"),
    ("quienes participaron en las elecciones presidenciales 2026", "nacional"),
    # Coloquial inicio
    ("a ver cuantos votos tuvo Aliaga en Arequipa", "candidate"),
    ("dejame ver los resultados de Sagasti", "candidate"),
    # Candidato + dos ciudades (ambiguo)
    ("Aliaga gano en Lima o en Arequipa", "candidate"),
    # Queries de tabla
    ("dame el ranking completo de candidatos", "nacional"),
    ("tabla de resultados electoral completa", "nacional"),
    # Del Castillo como candidato
    ("cuantos votos tuvo Del Castillo", "candidate"),
    # Tiempo presente / hasta ahora
    ("cuantos votos lleva Aliaga hasta ahora", "candidate"),
    ("resultados actuales de Sagasti", "candidate"),
    # Siglas de partido (2 letras, demasiado corto para candidato lookup)
    ("cuantos votos saco FP en Lima", "geo_domestic"),  # "FP" len<3 → no candidato → geo Lima
    ("resultados del AP en Cusco", "geo_domestic"),  # "AP" len<3 → no candidato → geo Cusco
    # Consulta sin verbo + geo
    ("Aliaga en Lima porcentaje", "candidate"),
    # Consulta extremadamente corta — sin contexto → unknown
    ("Aliaga", "unknown"),
    # Consulta de candidatos con "cuántos"
    ("cuantos candidatos compitieron", "nacional"),
    # Geo en minúsculas sin tilde
    ("resultados en amazonas", "geo_domestic"),
]


def run():
    passed = 0
    failed = 0
    for query, expected in TESTS:
        r = onpe_chat(query)
        d = r.get("data") or {}
        intent = d.get("intent", "ERR")
        ok = intent == expected
        if not ok:
            failed += 1
            print(f"FAIL exp={expected:<28} got={intent:<28} | {query}")
        else:
            passed += 1
            print(f"PASS exp={expected:<28} got={intent:<28} | {query}")
    print(f"\n{passed}/{len(TESTS)} PASS  {failed}/{len(TESTS)} FAIL")


if __name__ == "__main__":
    run()
