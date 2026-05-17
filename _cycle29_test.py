"""Cycle 29 stress tests — 20 queries:
- Candidatos con variantes de nombre (abreviaciones, alias)
- Preguntas con "cuánto porcentaje"
- Preguntas sobre "segunda vuelta" en distintas formas
- Geo con artículo: "la ciudad de X"
- Consultas negativas: "X no ganó en Y"
- Consultas con símbolo %
- Candidatos con preposición en apellido: "De la Torre", "Del Castillo"
- Queries en mayúsculas
- Ruido extremo
- Mesas con letra previa
"""
import io, logging, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

TESTS = [
    # Porcentaje
    ("cuanto porcentaje saco Aliaga en Lima", "candidate"),
    ("que porcentaje tuvo Keiko en total", "candidate"),
    # Segunda vuelta queries
    ("quien paso a la segunda vuelta", "nacional"),
    ("cuales candidatos clasificaron a segunda vuelta", "nacional"),
    ("segunda vuelta resultados", "nacional"),
    # Geo con artículo "la ciudad de"
    ("resultados en la ciudad de Trujillo", "geo_domestic"),
    ("top 5 en la region de Puno", "geo_domestic"),
    # Candidato con preposición en apellido
    ("cuantos votos tuvo De la Torre en Lima", "candidate"),
    ("resultados del candidato Del Castillo", "candidate"),
    # Negación
    ("Aliaga no gano en Piura verdad", "candidate"),
    # Símbolo %
    ("que % obtuvo Sagasti", "candidate"),
    # Alias conocidos — "el chicharron" no es candidato pero el patrón lo detecta → candidate (no encontrado)
    ("cuantos votos tuvo el chicharron", "candidate"),  # patrón correcto, candidato no existe
    # Ruido extremo
    ("jaja bueno pues a ver dime cuantos votos saco el señor Fujimori en Puno oe", "candidate"),
    # Pregunta sobre mesas total
    ("cuantas mesas hay en total", "nacional"),
    # Candidato mayúsculas + tilde
    ("CUÁNTOS VOTOS OBTUVO KEIKO FUJIMORI", "candidate"),
    # Geo extranjero bien conocido — "Tokyo" (sin tilde) no está en catálogo (catálogo tiene "TOKIO")
    ("resultados en Tokyo", "unknown"),
    # "quien gano" con geo
    ("quien gano en Tacna", "geo_domestic"),
    # Multiple candidatos con "versus"
    ("Aliaga versus Sagasti quien tuvo mas votos", "multi_candidate"),
    # Mesa con ruido verbal
    ("necesito info de la mesa 010203 urgente", "mesa"),
    # Short query geo ambiguous
    ("Cusco", "geo_domestic"),
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
