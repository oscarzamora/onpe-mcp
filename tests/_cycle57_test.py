"""Cycle 57 — ruido en frases, puntuación múltiple, reformulaciones conversacionales."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato con reformulación conversacional
    ("oye cuantos votos tuvo Lopez Aliaga",        "candidate"),
    # Mesa con "por favor"
    ("por favor muéstrame la mesa 500100",         "mesa"),
    # Nacional: "podría decirme quien gano"
    ("podria decirme quien gano",                  "unknown"),  # sin contexto → unknown
    # Geo domestic: "cómo andan los resultados en Piura"
    ("como andan los resultados en Piura",         "geo_domestic"),
    # Candidato: "dime cuanto saco Keiko"
    ("dime cuanto saco Keiko",                     "candidate"),
    # Geo extranjero con emoji: "resultados en 🇯🇵 Japon"
    ("resultados en Japon",                        "geo"),
    # Multi: "entre Sagasti y Forsyth quien fue primero"
    ("entre Sagasti y Forsyth quien fue primero",  "multi_candidate"),
    # Nacional: "quien está arriba en el conteo"
    ("quien esta arriba en el conteo",             "nacional"),
    # Candidato: "sabes cuanto tuvo Aliaga"
    ("sabes cuanto tuvo Aliaga",                   "candidate"),
    # Range: "serie de mesas 030 quien fue primero"
    ("serie de mesas 030 quien fue primero",       "range_reasoning"),
    # Unknown: pregunta de física
    ("cuanto pesa la tierra",                      "unknown"),
    # Candidato: "en Loreto cuantos votos obtuvo Aliaga"
    ("en Loreto cuantos votos obtuvo Aliaga",      "candidate"),
    # Geo domestic: "top 5 en la region de Lima"
    ("top 5 en la region de Lima",                 "geo_domestic"),
    # Nacional: "tabla completa de candidatos"
    ("tabla completa de candidatos",               "nacional"),
    # Candidato: "cuanto porcentaje obtuvo Sagasti a nivel nacional"
    ("cuanto porcentaje obtuvo Sagasti a nivel nacional", "candidate"),
    # Geo extranjero: "resultados en Corea del Sur"
    ("resultados en Corea del Sur",                "geo"),
    # Unknown: pregunta de gastronomia
    ("cual es el plato tipico de Arequipa",        "unknown"),
    # Mesa: "dame la info del 010101"
    ("dame la info del 010101",                    "mesa"),
    # Nacional: "cuales son los resultados finales"
    ("cuales son los resultados finales",          "nacional"),
    # Candidato: "votos que saco Forsyth en Junin"
    ("votos que saco Forsyth en Junin",            "candidate"),
]

ok_count = 0
fail_count = 0
for q, expected in CASES:
    intent = run(q)
    status = "PASS" if intent == expected else "FAIL"
    if status == "PASS":
        ok_count += 1
    else:
        fail_count += 1
    line = f"{status} exp={expected:<35} got={intent:<35} | {q}"
    print(line.encode("ascii", "replace").decode())

print(f"\n{ok_count}/{ok_count+fail_count} PASS  {fail_count}/{ok_count+fail_count} FAIL")
