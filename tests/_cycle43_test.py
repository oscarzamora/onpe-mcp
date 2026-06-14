"""Cycle 43 — edge cases: agregación geo, candidatos con tildes, multi-vuelta."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Geo domestic: múltiples palabras
    ("resultados en San Juan de Lurigancho",        "geo_domestic"),
    # Candidato: nombre con ñ
    ("cuantos votos tuvo Peña Nieto",               "candidate"),
    # Mesa: con texto antes
    ("quiero conocer los resultados de la mesa 123456", "mesa"),
    # Nacional: "cuantos candidatos en total"
    ("cuantos candidatos en total",                 "nacional"),
    # Geo domestic: "provincia de"
    ("resultados en la provincia de Cajamarca",     "geo_domestic"),
    # Candidato: "el señor X"
    ("cuantos votos tuvo el señor Urresti",         "candidate"),
    # Multi: "A frente a B"
    ("Keiko frente a Aliaga en Arequipa",           "multi_candidate"),
    # Unknown: consulta en blanco (espacios)
    ("   ",                                         "unknown"),
    # Geo foreign: país sudamericano
    ("resultados en Bolivia",                       "geo"),
    # Range: "mesas del bloque 9001"
    ("mesas del bloque 9001 quien fue primero",     "range_reasoning"),
    # Nacional: "porcentaje final"
    ("porcentaje final de votos",                   "nacional"),
    # Candidato: "votos contabilizados de X"
    ("votos contabilizados de Forsyth",             "candidate"),
    # Geo domestic: "Lima Metropolitana"
    ("resultados Lima Metropolitana",               "geo_domestic"),
    # Legislative: "congresistas electos"
    ("congresistas electos para Piura",             "legislative_top_candidate"),
    # Multi: A o B quien mas
    ("Aliaga o Keiko quien saco mas votos",         "multi_candidate"),
    # Candidato: apellido doble
    ("cuantos votos saco De La Rosa",               "candidate"),
    # Nacional: "lista de ganadores"
    ("lista de ganadores de las elecciones",        "nacional"),
    # Unknown: pregunta existencial
    ("que es la democracia",                        "unknown"),
    # Geo domestic: distrito sin preposición
    ("Miraflores resultados",                       "geo_domestic"),
    # Mesa: typo "ver la msa"
    ("ver la msa 030405",                           "mesa"),
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
