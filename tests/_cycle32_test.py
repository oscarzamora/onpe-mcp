"""Cycle 32 stress tests — 20 queries:
- Candidato con "saco" coloquial sin "votos"
- Preguntas de candidato con apellido compuesto "De la Torre"
- Geo con "al sur de"
- Consulta de candidato + número de mesas
- Ruido: ortografía alternativa (lleva vs lleba)
- Preguntas de candidato con pronombre reflexivo "se"
- Geo extranjero: países de Asia/África
- Preguntas temporales: "ya hay resultados de"
- Candidato con "el presidente" como honorífico
- Confusión candidato/geo: "Lima como candidato"
"""
import io, logging, sys

if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # "saco" coloquial sin "votos"
    ("cuantos saco Aliaga en total", "candidate"),
    ("cuanto saco Keiko en Lima", "candidate"),
    # Apellido compuesto
    ("votos de Pedro Castillo en Puno", "candidate"),
    ("resultados de De la Torre", "candidate"),
    # Candidato con "el presidente"
    ("cuantos votos tuvo el presidente Sagasti", "candidate"),
    ("resultados del presidente Boluarte", "candidate"),
    # Ya hay resultados (temporal)
    ("ya hay resultados de Lima", "geo_domestic"),
    ("ya hay resultados de la primera vuelta", "nacional"),
    # Ortografía alternativa
    ("cuantos votos lleba Aliaga", "candidate"),  # lleba → lleva typo
    ("cuantos votos obtubo Sagasti", "candidate"),  # typo b/v
    # Pronombre reflexivo "se"
    ("cuantos votos se llevo Aliaga en Cusco", "candidate"),
    # Geo extranjero Asia/Africa
    ("resultados para Peru en Arabia Saudita", "geo"),
    ("top 5 en Seul", "geo"),
    # Consulta de número de mesas
    ("cuantas mesas tiene Arequipa", "geo_domestic"),
    # Confusión candidato/geo — nacional es la respuesta más razonable
    ("Lima como candidato", "nacional"),  # "candidato" keyword → nacional
    # Candidato con "mi" antes
    ("mi candidato favorito es Aliaga cuantos votos tuvo", "candidate"),
    # Candidato + fecha
    ("cuantos votos obtuvo Aliaga el 9 de abril", "candidate"),
    # Candidato en el exterior
    ("cuantos votos tuvo Fujimori en Francia", "candidate"),
    # Consulta sobre partido no candidato
    ("cuantos votos tuvo el Partido Morado", "candidate"),  # partido como entidad, no candidato persona
    # Bare geo con artículo
    ("el departamento Cusco", "geo_domestic"),
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
