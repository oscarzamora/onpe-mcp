"""Cycle 47 — nulos/blancos/viciados, geo extranjero variantes, edge cases extremos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Nulos en geo
    ("cuantos votos nulos en Lima",                "geo_domestic"),
    # Blancos en geo
    ("votos en blanco en Arequipa",               "geo_domestic"),
    # Viciados nacional
    ("cuantos votos viciados hubo en total",       "nacional"),
    # Candidato con acento difícil
    ("cuantos votos obtuvo Quispe Mamani",         "candidate"),
    # Mesa con rango "entre 900100 y 900200"
    ("mesas entre 900100 y 900200",                "range_reasoning"),
    # Geo extranjero: ciudad + país
    ("peruanos en Toronto Canada",                 "geo"),
    # Geo extranjero: ciudad difícil
    ("resultados en Dubai",                        "geo"),
    # Geo extranjero: país en minúscula
    ("resultados en japon",                        "geo"),
    # Legislativo: "cuantos escaños"
    ("cuantos escanos le corresponden a Puno",     "legislative_top_candidate"),
    # Unknown: pregunta sobre partidos sin contexto electoral
    ("cuando se fundó el APRA",                    "unknown"),
    # Nacional: "quien ganó"
    ("quien gano las elecciones",                  "nacional"),
    # Candidato: "en qué posición quedó X"
    ("en que posicion quedo Forsyth",              "candidate"),
    # Mesa: número 6 dígitos completo
    ("mesa 010101",                                "mesa"),
    # Geo domestic: "como va Madre de Dios"
    ("como va Madre de Dios",                      "geo_domestic"),
    # Multi: "tanto A como B"
    ("tanto Aliaga como Sagasti cuantos votos",    "multi_candidate"),
    # Unknown: "cuantos congresistas tiene el Peru" → legislative (tiene datos de congresistas)
    ("cuantos congresistas tiene el Peru",         "legislative_top_candidate"),
    # Nacional: "resumen general de resultados"
    ("resumen general de resultados",              "nacional"),
    # Candidato: nombre compuesto largo
    ("cuantos votos tuvo Juan Carlos Ugaz",        "candidate"),
    # Geo extranjero: país con acento — Bélgica puede ser ambiguous si hay conflicto en catalogo
    ("resultados en Bélgica",                      "ambiguous"),
    # Mesa con texto antes: "ver la mesa 900100"
    ("ver la mesa 900100",                         "mesa"),
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
