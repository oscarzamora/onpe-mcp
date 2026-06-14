"""Cycle 28 stress tests — 20 queries:
- Preguntas con "a nivel" (nacional implícito)
- Queries de "cuántos votos en blanco/nulo" (no candidato)
- Candidato con sufijo honorífico ("doctor Sagasti")
- Consultas de ranking por provincia
- Queries muy largas con ruido
- Doble geo ("Lima Lima" como región y provincia)
- Consulta de mesa con "la mesa 123456"
- Mix candidato + partido
"""
import io, logging, sys

if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # "a nivel" implica nacional
    ("resultados a nivel nacional", "nacional"),
    ("top 5 a nivel país", "nacional"),
    ("cuantos votos saco cada candidato a nivel nacional", "nacional"),
    # Blancos/nulos: no son candidatos
    ("cuantos votos en blanco hubo", "nacional"),
    ("cuantos votos nulos tuvo la eleccion", "nacional"),
    ("cuantos votos viciados se registraron", "nacional"),
    # Candidato con honorífico
    ("cuantos votos obtuvo el doctor Sagasti", "candidate"),
    ("resultados del ingeniero Lopez Aliaga", "candidate"),
    # Ranking por provincia/distrito
    ("top 3 en la provincia de Chiclayo", "geo_domestic"),
    ("quien quedo primero en el distrito de Miraflores", "geo_domestic"),
    # Queries largas con ruido
    ("oye bro me puedes decir quienes fueron los mas votados a nivel de todo el pais en la primera vuelta de las elecciones", "nacional"),
    ("quisiera saber si puedes darme el ranking de candidatos en la region de Cajamarca por favor", "geo_domestic"),
    # Doble geo
    ("resultados en Lima Lima", "geo_domestic"),
    # Mesa con palabra "la"
    ("la mesa 100200 que resultados tuvo", "mesa"),  # sistema ahora detecta mesa correctamente
    ("consulta la mesa numero 050100", "mesa"),
    # Mix candidato + región
    ("cuantos votos obtuvo Fujimori en la region Puno", "candidate"),
    # Año que no es candidato
    ("resultados de 2026", "nacional"),
    # Candidato con apellido compuesto
    ("votos de De la Torre en Lima", "candidate"),
    # Consulta en mayúsculas
    ("CUANTOS VOTOS TUVO ALIAGA EN AREQUIPA", "candidate"),
    # Consulta mezclada candidato + legislativo (legislativo toma precedencia)
    ("cuantos senadores saco Aliaga", "legislative_top_candidate"),
]


def run():
    passed = 0
    failed = 0
    for query, expected in TESTS:
        r = onpe_chat(query)
        d = r.get("data") or {}
        intent = d.get("intent", "ERR")
        ok = intent == expected
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
            print(f"FAIL exp={expected:<28} got={intent:<28} | {query}")
        else:
            passed += 1
            print(f"PASS exp={expected:<28} got={intent:<28} | {query}")
    print(f"\n{passed}/{len(TESTS)} PASS  {failed}/{len(TESTS)} FAIL")


if __name__ == "__main__":
    run()
