"""Cycle 51 — acentos/diacríticos, queries largas, candidatos con partículas especiales."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Acento doble: Cuzco con z
    ("resultados en Cuzco",                        "geo_domestic"),
    # Candidato con tilde al inicio de la pregunta
    ("¿Cuántos votos obtuvo Aliaga?",              "candidate"),
    # Candidato: "sabe usted cuantos votos tuvo"
    ("sabe usted cuantos votos tuvo Keiko",        "candidate"),
    # Multi con número explícito de candidatos
    ("top 3 entre Aliaga y Sagasti en Lima",       "multi_candidate"),
    # Nacional: "cuantos escrutinios hubo"
    ("cuantos escrutinios hubo",                   "nacional"),
    # Mesa: número pegado a letras
    ("consultar 900100x",                          "unknown"),
    # Candidato: partido en lugar de nombre
    ("cuantos votos tuvo fuerza popular",          "candidate"),
    # Geo: ciudad "New York" → extranjero
    ("peruanos en New York",                       "geo"),
    # Unknown: siglas sin contexto
    ("JNE OEA ONPE",                               "unknown"),
    # Nacional: "primera vuelta resultados"
    ("primera vuelta resultados",                  "nacional"),
    # Candidato: "performance de Urresti"
    ("performance de Urresti",                     "candidate"),
    # Geo domestic: "en la region Puno"
    ("en la region Puno",                          "geo_domestic"),
    # Mesa: "revisar acta 100200"
    ("revisar acta 100200",                        "mesa"),
    # Multi: "Aliaga o Fujimori quien gano"
    ("Aliaga o Fujimori quien gano",               "multi_candidate"),
    # Unknown: emoji solo
    ("🗳️",                                          "unknown"),
    # Geo: "resultados Los Angeles"
    ("resultados Los Angeles",                     "geo"),
    # Candidato: "numero de votos de Forsyth"
    ("numero de votos de Forsyth",                 "candidate"),
    # Nacional: "el ganador de la primera vuelta"
    ("el ganador de la primera vuelta",            "nacional"),
    # Range: "desde la mesa 001000 hasta 001999"
    ("desde la mesa 001000 hasta 001999",          "range_reasoning"),
    # Candidato: "cuanto porcentaje tiene Keiko"
    ("cuanto porcentaje tiene Keiko",              "candidate"),
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
