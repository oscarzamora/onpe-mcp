"""Cycle 59: stress test — accentuated queries, typos, colloquial phrasing, edge mesas."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidate: accented verb "sacó"
    ("cuántos votos sacó Keiko en Lima",                   "candidate"),
    # Candidate: "reunio" typo (reunió)
    ("cuantos votos reunio Forsyth",                       "candidate"),
    # Candidate: leading noise + candidate
    ("oiga, dígame cuántos votos tuvo Sagasti",            "candidate"),
    # Candidate: "sumó" verb
    ("cuantos votos sumo Aliaga en Arequipa",              "candidate"),
    # Multi: "Lopez Aliaga vs Keiko"
    ("Lopez Aliaga vs Keiko quien fue primero",            "multi_candidate"),
    # Multi: "tanto A como B"
    ("tanto Aliaga como Sagasti cuantos votos",            "multi_candidate"),
    # Nacional: "cuantos votos en total"
    ("cuantos votos hubo en total en la eleccion",         "nacional"),
    # Nacional: "resumen de elecciones"
    ("resumen de las elecciones 2026",                     "nacional"),
    # Geo domestic: "Ancash"
    ("resultados electorales en Ancash",                   "geo_domestic"),
    # Geo domestic: "Pasco"
    ("top 3 en Pasco",                                     "geo_domestic"),
    # Geo: country with accent
    ("resultados en Canadá",                               "geo"),
    # Geo: compound country "Reino Unido"
    ("resultados en Reino Unido",                          "geo"),
    # Range: "del 020000 al 020050"
    ("del 020000 al 020050 quien fue primero",             "range_reasoning"),
    # Range: "entre 040000 y 040099"
    ("entre 040000 y 040099 quien fue el primero",        "range_reasoning"),
    # Unknown: history
    ("cuando fue la independencia del Peru",               "unknown"),
    # Unknown: science
    ("cuantos planetas tiene el sistema solar",            "unknown"),
    # Unknown: math
    ("cuanto es 15 por 15",                                "unknown"),
    # Unknown: personal
    ("cuantos anos tienes",                                "unknown"),
    # Mesa: padded code
    ("mesa 000123",                                        "mesa"),
    # Mesa: with accent in word
    ("muéstrame la mesa 999999",                          "mesa"),
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
