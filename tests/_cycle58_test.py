"""Cycle 58: compound geo names, captó/hizo, range desde-al, mundial guard."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidate: "captó" verb
    ("cuantos votos captó Aliaga",                         "candidate"),
    # Candidate: "hizo" (informal)
    ("cuantos votos hizo Lopez Aliaga",                    "candidate"),
    # Candidate: rhetorical intro
    ("a ver cuantos votos saco Forsyth",                   "candidate"),
    # Candidate: "juntó"
    ("cuantos votos junto Keiko en Cusco",                 "candidate"),
    # Multi-candidate: "A contra B"
    ("Aliaga contra Keiko quien saco mas votos",           "multi_candidate"),
    # Multi-candidate: "A frente a B"
    ("Sagasti frente a Forsyth quien fue mejor",           "multi_candidate"),
    # Nacional: rhetorical
    ("como quedaron los resultados finales",               "nacional"),
    # Nacional: "quien quedo primero"
    ("quien quedo primero a nivel nacional",               "nacional"),
    # Geo domestic: compound name
    ("resultados en San Martin",                           "geo_domestic"),
    # Geo domestic: long compound
    ("resultados en Madre de Dios",                        "geo_domestic"),
    # Geo foreign: compound city (requires foreign catalog)
    ("resultados en Nueva York",                           "geo"),
    # Geo foreign: capital (requires foreign catalog)
    ("resultados en Ciudad de Mexico",                     "geo"),
    # Range: "prefijo 0203"
    ("mesas con prefijo 0203 quien primero",               "range_reasoning"),
    # Range: "desde el X al Y"
    ("mesas desde el 100000 al 100099 quien fue primero",  "range_reasoning"),
    # Unknown: rhetorical political
    ("para que sirve la democracia",                       "unknown"),
    # Unknown: philosophical
    ("que es la justicia social",                          "unknown"),
    # Unknown: sport (mundial ≠ eleccion)
    ("quien gano el mundial",                              "unknown"),
    # Unknown: cooking
    ("como se hace el ceviche",                            "unknown"),
    # Mesa: with "datos" context word
    ("datos de la mesa 040506",                            "mesa"),
    # Mesa: "detalle del XXXXXX"
    ("detalle del 070809",                                 "mesa"),
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

