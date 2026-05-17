"""Cycle 39 — cross-regression + new edge cases."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # --- Regresiones de ciclos anteriores ---
    ("cuantos votos saco Keiko Fujimori",           "candidate"),  # cycle26
    ("top 3 candidatos en Suecia",                  "geo"),        # cycle26
    ("resultados en Estocolmo",                     "geo"),        # cycle26
    ("top 3 en Loreto",                             "geo_domestic"), # cycle26
    ("senadores top 10 para Cuzco",                 "legislative_top_candidate"),  # cycle26
    ("consulta mesa 900100",                        "mesa"),       # cycle26
    ("de las mesas que arrancan en 900000 quien fue primero Lopez Aliaga", "range_reasoning"),  # cycle27
    ("Aliaga tuvo mas votos que Sagasti en Puno",   "multi_candidate"),  # cycle30
    ("resultados del partido morado",               "candidate"),  # cycle27
    ("elecciones 2021 en Puno",                     "unknown"),  # cycle33 → year guard: 2021 ≠ 2026
    # --- Ciclo 34 regresiones ya corregidas ---
    ("quien salio en primer lugar",                 "nacional"),   # cycle34
    ("cuantos votos saco cada candidato a nivel nacional", "nacional"),  # cycle34
    ("qué porcentaje de votos tuvo cada candidato", "nacional"),   # cycle34
    ("distribución de votos entre candidatos",      "nacional"),   # cycle34
    ("votos en blanco en Lima",                     "geo_domestic"),  # cycle34
    # --- Nuevos edge cases ---
    # Coloquial con ruido
    ("oye dime cuantos votos saco Forsyth",         "candidate"),
    # Buenos Aires: ambiguo (Perú tiene "Buenos Aires", también es ciudad argentina)
    ("resultados en Buenos Aires",                  "ambiguous"),
    # Typo severo en candidato: "Castilo" no reconocido → geo por "Cusco"
    ("cuantos obtubo Castilo en Cusco",             "geo_domestic"),
    # "el presidente" solo → nacional
    ("quien fue el presidente electo del peru",     "nacional"),
    # Mesa con ruido de texto anterior
    ("quiero ver la mesa 012345",                   "mesa"),
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
