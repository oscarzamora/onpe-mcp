"""Cycle 41 — NLU normalization stress test: typos, code-switching, multi-entity."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Typo extremo con código de mesa
    ("quero ver la messa 030405",                  "mesa"),
    # Candidato: mayúscula sólo en apellido
    ("cuantos VOTOS tuvo ALIAGA en Lima",          "candidate"),
    # Code-switching español/inglés — sistema en español, sin patrones ingleses
    ("how many votes did Aliaga get",              "unknown"),
    # Candidato: patrón con coma intermedia
    ("Lopez Aliaga, cuantos votos",                "candidate"),
    # Geo: país en mayúsculas
    ("resultados en ALEMANIA",                     "geo"),
    # Multi: con "y también"
    ("Aliaga y tambien Keiko en Puno",             "multi_candidate"),
    # Mesa con guion
    ("mesa 03-0405",                               "mesa"),
    # Candidato: "el doc" → candidato no encontrado → candidate intent
    ("cuantos votos tuvo el doc",                  "candidate"),
    # Nacional: "quienes fueron los candidatos"
    ("quienes fueron los candidatos",              "nacional"),
    # Geo domestic: con "departamento de"
    ("resultados en el departamento de Puno",      "geo_domestic"),
    # Candidato: nombre con "Jr." → desconocido
    ("cuantos votos tuvo Jr Lopez",                "candidate"),
    # Nacional: "participacion total"
    ("cual fue la participacion total",            "nacional"),
    # Range: "mesas prefijo 900" + quien primero
    ("en las mesas del prefijo 900 quien fue primero", "range_reasoning"),
    # Geo foreign: país con artículo "los"
    ("resultados en los Estados Unidos",           "geo"),
    # Candidato: pregunta con "dígame"
    ("digame cuantos votos saco Sagasti",          "candidate"),
    # Mesa: "ver mesa numero" 
    ("ver mesa numero 123456",                     "mesa"),
    # Multi: tres candidatos con "entre A B C"
    ("entre Aliaga Keiko y Urresti quien gano",    "multi_candidate"),
    # Nacional: "porcentaje de votos por candidato"
    ("porcentaje de votos por candidato",          "nacional"),
    # Geo: ciudad con tilde
    ("votos en Bogotá",                            "geo"),
    # Unknown: pregunta personal
    ("como te llamas",                             "unknown"),
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
