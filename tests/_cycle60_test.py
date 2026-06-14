"""Cycle 60: geo edge cases, abbreviation handling, partial queries, noisy natural language."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidate: abbreviated name with context
    ("votos de RLA en Lima",                               "candidate"),
    # Candidate: colloquial "la fujimori"
    ("cuantos votos saco la fujimori",                     "candidate"),
    # Candidate: "el aliaga"
    ("cuantos votos tiene el aliaga",                      "candidate"),
    # Candidate: past tense "habia obtenido"
    ("cuantos votos habia obtenido Keiko",                 "candidate"),
    # Multi: "A y B comparacion de votos"
    ("Aliaga y Keiko comparacion de votos",                "multi_candidate"),
    # Multi: "quien gano entre A y B"
    ("quien gano entre Aliaga y Sagasti",                  "multi_candidate"),
    # Nacional: "cuantos votaron en total"
    ("cuantos votaron en total en peru",                   "nacional"),
    # Nacional: question about first place
    ("quien salio primero en las elecciones",              "nacional"),
    # Geo domestic: "Ica"
    ("resultados en Ica",                                  "geo_domestic"),
    # Geo domestic: "Huancavelica"
    ("top 5 en Huancavelica",                              "geo_domestic"),
    # Geo: "en Francia"
    ("cuantos votos en Francia",                           "geo"),
    # Geo: "en Alemania"
    ("top 3 en Alemania",                                  "geo"),
    # Range: "mesas 9001 hasta 9002 quien primero"
    ("mesas 9001 hasta 9002 quien primero",                "range_reasoning"),
    # "del 100 al 200" — 3-digit numbers don't match mesa range (need 4+); "quien gano" → unknown
    ("del 100 al 200 quien gano",                          "unknown"),
    # Unknown: opinion
    ("crees que la democracia esta bien",                  "unknown"),
    # Unknown: about the AI
    ("cuantos anos tienes tu",                             "unknown"),
    # Unknown: news
    ("cuales son las noticias de hoy",                     "unknown"),
    # Unknown: greetings
    ("buenas tardes",                                      "unknown"),
    # Mesa: explicit with word
    ("resultado de la mesa 123456",                        "mesa"),
    # Mesa: coloquial "el acta 050607"
    ("ver el acta 050607",                                 "mesa"),
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
