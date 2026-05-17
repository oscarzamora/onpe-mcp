"""Cycle 54 — variantes verbales de candidatos + geo extranjero extremos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato con "alcanzó"
    ("cuantos votos alcanzo Aliaga",               "candidate"),
    # Candidato con "acumuló"
    ("cuantos votos acumulo Sagasti",              "candidate"),
    # Candidato con "se adjudicó"
    ("cuantos votos se adjudico Keiko",            "candidate"),
    # Candidato: "logro X votos Forsyth"
    ("logro cuantos votos Forsyth",                "candidate"),
    # Multi: "entre Aliaga y Sagasti quien fue primero"
    ("entre Aliaga y Sagasti quien fue primero",   "multi_candidate"),
    # Geo extranjero: "Lima Peru" → confusión
    ("resultados en Lima Peru",                    "geo_domestic"),
    # Geo: "peruanos en Miami"
    ("peruanos en Miami",                          "geo"),
    # Nacional: "cual es el porcentaje final"
    ("cual es el porcentaje final",                "nacional"),
    # Candidato: "Aliaga recibio cuantos votos"
    ("Aliaga recibio cuantos votos",               "candidate"),
    # Candidato: cuánto consiguió
    ("cuanto consiguio Urresti",                   "candidate"),
    # Geo domestic: "en la sierra"
    ("resultados en la sierra",                    "nacional"),
    # Range: "mesas de 010000 a 010999 primero Lopez Aliaga"
    ("mesas de 010000 a 010999 primero Lopez Aliaga", "range_reasoning"),
    # Candidato: "tasa de votos de Sagasti"
    ("tasa de votos de Sagasti",                   "candidate"),
    # Unknown: "cuantos años tiene Aliaga"
    ("cuantos anos tiene Aliaga",                  "unknown"),
    # Mesa: "codigo 303030"
    ("codigo 303030",                              "mesa"),
    # Legislativo: "parlamentarios para Piura"
    ("parlamentarios para Piura",                  "legislative_top_candidate"),
    # Candidato: "cómo le fue a Aliaga"
    ("como le fue a Aliaga",                       "candidate"),
    # Unknown: "dame el clima de Arequipa"
    ("dame el clima de Arequipa",                  "unknown"),
    # Nacional: "ultimos resultados electorales"
    ("ultimos resultados electorales",             "nacional"),
    # Geo: "resultados en Tokio"
    ("resultados en Tokio",                        "geo"),
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
