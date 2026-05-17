"""Cycle 75 stress tests — 40 queries covering:
- geo-override fixes (exterior/extranjero, va ganando, hay resultados)
- numeric range guard (candidatos entre N y N → nacional not multi_candidate)
- Peru-as-country guard (Peru not a candidate)
- en Peru → nacional
- Variants of foreign summary, domestic geo, candidate, legislative
"""
import logging
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

CASES = [
    # Geo override: exterior/extranjero → geo_foreign_summary
    ("cuantos peruanos votaron en el exterior",          "geo_foreign_summary"),
    ("cuantos votaron en el extranjero",                 "geo_foreign_summary"),
    ("resultados de peruanos en el exterior",            "geo_foreign_summary"),
    ("peruanos que votaron en el extranjero",            "geo_foreign_summary"),
    ("votos de peruanos residentes en el extranjero",    "geo_foreign_summary"),
    ("cuantos peruanos en el exterior votaron",          "geo_foreign_summary"),
    # "en Peru" → nacional (país completo)
    ("top 5 en Peru",                                    "nacional"),
    ("top 10 en Peru quien lidera",                      "nacional"),
    ("resultados en Peru",                               "nacional"),
    ("top 20 candidatos en Peru",                        "nacional"),
    ("quien gano en Peru",                               "nacional"),
    ("cuantos votos en Peru",                            "nacional"),
    # Numeric range guard → nacional
    ("candidatos entre 50000 y 300000 votos",            "nacional"),
    ("quienes tienen entre 500000 y 2000000 votos",      "nacional"),
    ("candidatos entre 10000 y 50000 votos",             "nacional"),
    ("quienes superaron 500000 votos",                   "nacional"),
    ("candidatos con mas de 100000 votos",               "nacional"),
    ("entre 500 y 900 votos quien quedo",                "nacional"),
    # Peru-as-country not a candidate
    ("resultados para Peru en China",                    "geo"),
    ("votos para Peru en Japon",                         "geo"),
    ("resultados para Peru en Arabia Saudita",           "geo"),
    ("votos de Peru en Italia",                          "geo"),
    # Real candidates still detected
    ("resultados para Aliaga en Lima",                   "candidate"),
    ("votos para Keiko en Arequipa",                     "candidate"),
    ("cuantos votos saco Lopez Aliaga",                  "candidate"),
    # Ya hay resultados → geo_domestic with geo
    ("ya hay resultados de Arequipa",                    "geo_domestic"),
    ("ya hay resultados de Cusco",                       "geo_domestic"),
    ("ya hay resultados de la primera vuelta",           "nacional"),
    # Quien va ganando → geo_domestic with geo
    ("quien va ganando en Puno",                         "geo_domestic"),
    ("quien lidera en Loreto",                           "geo_domestic"),
    ("quien esta arriba en Piura",                       "geo_domestic"),
    # Foreign countries → geo
    ("resultados para peruanos en Bolivia",              "geo"),
    ("cuantos votos en Brasil",                          "geo"),
    # Non-electoral
    ("cuantos hospitales tiene Lima",                    "unknown"),
    ("fauna de la selva peruana",                        "unknown"),
    ("sueldo minimo en Peru",                            "unknown"),
    # Mesa still works
    ("dame datos de la mesa 900100",                     "mesa"),
    ("la mesa 123456 cuantos votos tiene",               "mesa"),
    # Legislative
    ("senadores top 5 para Lima",                        "legislative_top_candidate"),
    ("diputados para Cusco top 3",                       "legislative_top_candidate"),
]

ok_count = 0
fail_count = 0
for q, expected in CASES:
    r = onpe_chat(q)
    intent = (r.get("data") or {}).get("intent", "ERR")
    status = "PASS" if intent == expected else "FAIL"
    if status == "PASS":
        ok_count += 1
    else:
        fail_count += 1
    print(f"{status} exp={expected:<30} got={intent:<30} | {q}")

print(f"\n{ok_count}/{ok_count+fail_count} PASS  {fail_count}/{ok_count+fail_count} FAIL")
