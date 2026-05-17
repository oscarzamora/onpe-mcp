"""Cycle 37 — 20 edge-case stress tests post cycle 36 fixes."""
import logging
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

CASES = [
    # 4-word candidate name
    ("cuantos votos tuvo Rafael Lopez Aliaga Rabines",   "candidate"),
    # Abbreviated name (2-3 chars) — system now detects as candidate via pattern
    ("RLA cuantos votos",                               "candidate"),
    # Multi-candidate 3-way: A, B y C
    ("votos de Aliaga Sagasti y Fujimori",              "multi_candidate"),
    # Continent query — no specific foreign city
    ("peruanos en Europa cuantos votos",                "unknown"),
    # 2021 results in specific geo — year guard correctly blocks non-2026 years → unknown
    ("resultados 2021 en Arequipa",                     "unknown"),
    # "inscripcion" / registration query — non-electoral
    ("cuando fue la inscripcion de candidatos",         "nacional"),
    # Bare firstname only
    ("Keiko",                                           "unknown"),
    # Emoji in query
    ("🗳️ cuantos votos tuvo Aliaga",                    "candidate"),
    # Reversed: "en Lima cuantos votos obtuvo Sagasti"
    ("en Lima cuantos votos obtuvo Sagasti",            "candidate"),
    # "qué porcentaje" collective candidatos → nacional
    ("qué porcentaje de votos tuvo cada candidato",     "nacional"),
    # Geo + año puntual
    ("votos en Junin 2026",                             "geo_domestic"),
    # Unknown — weather
    ("va a llover mañana en Lima",                      "unknown"),
    # Bare single place name without context → geo_domestic (reasonable routing)
    ("Puno",                                            "geo_domestic"),
    # Candidate with accent variant
    ("cuantos votos tiene Fujimori Higuchi",            "candidate"),
    # Legislative: diputados
    ("diputados para Loreto",                           "legislative_top_candidate"),
    # Candidate comparison: "X tuvo mas que Y en Z"
    ("Aliaga tuvo mas votos que Urresti en Ica",        "multi_candidate"),
    # "quien gano" → nacional
    ("quien gano las elecciones",                       "nacional"),
    # Multi: con coma
    ("Castillo, Aliaga y Keiko en Puno",               "multi_candidate"),
    # Range-reasoning query
    ("de las mesas 900100 a 900200 quien fue primero",  "range_reasoning"),
    # Geo domestic: district with accent
    ("resultados en San Martín",                       "geo_domestic"),
]

ok_count = 0
fail_count = 0
for q, expected in CASES:
    try:
        r = onpe_chat(q) or {}
        data = r.get("data") or {}
        intent = data.get("intent", "N/A")
    except Exception as e:
        intent = f"EXCEPTION:{e}"
    status = "PASS" if intent == expected else "FAIL"
    if status == "PASS":
        ok_count += 1
    else:
        fail_count += 1
    print(f"{status} exp={expected:<35} got={intent:<35} | {q}")

print(f"\n{ok_count}/{ok_count+fail_count} PASS  {fail_count}/{ok_count+fail_count} FAIL")
