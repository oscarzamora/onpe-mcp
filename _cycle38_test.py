"""Cycle 38 — stress test: typos, synonyms, geo ambiguity, legislative, aggregation."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

CASES = [
    # Typos in candidate names
    ("cuantos botos saco Lopes Aliaga",             "candidate"),
    # Weather with Lima — not electoral
    ("va a llover en Lima manana",                  "unknown"),
    # Candidate with "el" article
    ("el candidato Forsyth cuantos votos",          "candidate"),
    # Foreign geo: China
    ("resultados en China",                         "geo"),
    # Geo domestic with preposition "hacia"
    ("votos hacia Ayacucho",                        "geo_domestic"),
    # Presidential: "presidente electo" → nacional
    ("quien es el presidente electo",               "nacional"),
    # Multi with "vs"
    ("Aliaga vs Keiko en Cajamarca",               "multi_candidate"),
    # Bare name + "resultados" suffix
    ("Castillo resultados",                         "candidate"),
    # Sanchez alias for Castillo (sombrero logic)
    ("cuantos votos tuvo Sanchez el del sombrero",  "candidate"),
    # Legislative: congresistas
    ("congresistas para Tacna",                     "legislative_top_candidate"),
    # Geo district with article "el"
    ("resultados en el Agustino",                   "geo_domestic"),
    # "segunda vuelta" without geo → nacional
    ("segunda vuelta quien paso",                   "nacional"),
    # Non-electoral: traffic
    ("hay trafico en Lima",                         "unknown"),
    # Candidate: "que tal le fue a Lopez Aliaga"
    ("que tal le fue a Lopez Aliaga",               "candidate"),
    # Foreign geo: Japan city not in catalog → unknown
    ("votos en Osaka",                              "unknown"),
    # Nacional: "resumen de resultados"
    ("dame el resumen de resultados",               "nacional"),
    # Geo: "resultados en Miraflores, Lima"
    ("resultados en Miraflores Lima",               "geo_domestic"),
    # Candidate: reversed with accent
    ("Urresti cuántos sacó",                       "candidate"),
    # Range with performance but no candidate → asks for clarification
    ("en las mesas 9001 quien fue primero",         "range_reasoning"),
    # Multi-candidate with commas: A, B y C
    ("compara votos de Aliaga Castillo y Urresti",  "multi_candidate"),
]

ok_count = 0
fail_count = 0
for q, expected in CASES:
    try:
        r = onpe_chat(q) or {}
        data = r.get("data") or {}
        intent = data.get("intent", "N/A")
    except Exception as e:
        intent = f"EXCEPTION:{type(e).__name__}"
    status = "PASS" if intent == expected else "FAIL"
    if status == "PASS":
        ok_count += 1
    else:
        fail_count += 1
    line = f"{status} exp={expected:<35} got={intent:<35} | {q}"
    print(line.encode("ascii", "replace").decode())

print(f"\n{ok_count}/{ok_count+fail_count} PASS  {fail_count}/{ok_count+fail_count} FAIL")
