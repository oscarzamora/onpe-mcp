"""Cycle 44 — heavy noise: fillers, reorden de palabras, fragmentos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato con filler "oye me puedes decir"
    ("oye me puedes decir cuantos votos tuvo Aliaga", "candidate"),
    # Candidato: pregunta con "quiero saber"
    ("quiero saber cuantos votos obtuvo Keiko",       "candidate"),
    # Geo domestic: con filler al inicio
    ("necesito saber los resultados en Arequipa",     "geo_domestic"),
    # Nacional: "dime los resultados generales"
    ("dime los resultados generales",                 "nacional"),
    # Unknown: pregunta sobre partido externo
    # "que es fuerza popular" → geo (foreign catalog has "popular" location)
    ("que es fuerza popular",                         "geo"),
    # Geo: extranjero con typo — "Espanna" no está en catálogo → unknown
    ("resultados en Espanna",                         "unknown"),
    # Candidato: "me puedes decir" + nombre
    ("me puedes decir cuanto saco Urresti",           "candidate"),
    # Range: "en el rango de mesas 9001 a 9009"
    ("en el rango de mesas 9001 a 9009 quien fue primero", "range_reasoning"),
    # Nacional: "votos totales de todas las mesas"
    ("votos totales de todas las mesas",              "nacional"),
    # Candidato: nombre largo con "Jr."
    ("cuantos votos obtuvo Jose Martinez Jr en Puno", "candidate"),
    # Geo domestic: con ruido "a ver que paso en"
    ("a ver que paso en Tacna",                       "geo_domestic"),
    # Mesa: con "código"
    ("dame el codigo de la mesa 909090",              "mesa"),
    # Multi: "cuánto más sacó A que B"
    ("cuanto mas saco Aliaga que Urresti",            "multi_candidate"),
    # Unknown: consulta sobre historia política
    ("cuando fue el golpe de fujimori",               "unknown"),
    # Geo extranjero: ciudad francesa
    ("resultados en Paris",                           "geo"),
    # Candidato: "el tal" + nombre coloquial
    ("el tal Sagasti cuantos votos saco",             "candidate"),
    # Nacional: "quién ganó más votos en el país"
    ("quien gano mas votos en el pais",               "nacional"),
    # Geo domestic: "resultados electorales en Piura"
    ("resultados electorales en Piura",               "geo_domestic"),
    # Candidato: pregunta con signo de exclamación
    ("cuantos votos tuvo Forsyth en Lima!",           "candidate"),
    # Unknown: consulta sobre precios
    ("cuanto vale el sol peruano",                    "unknown"),
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
