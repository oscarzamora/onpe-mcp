"""Cycle 78 stress tests — 40 queries covering:
- 'top N DEPT' bare → geo_domestic (not nacional)
- candidatos + bare dept → geo_domestic
- multi-locale candidate queries
- range reasoning
- overseas elections with department-like names
- non-electoral (food/weather)
"""
import logging
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

CASES = [
    # Bare dept + 'candidatos' → geo_domestic
    ("Cusco candidatos",                                 "geo_domestic"),
    ("Puno candidatos",                                  "geo_domestic"),
    ("Piura candidatos",                                 "geo_domestic"),
    ("Loreto candidatos",                                "geo_domestic"),
    # candidatos + dept in preposition → geo_domestic
    ("candidatos en Lima",                               "geo_domestic"),
    ("candidatos por Lima",                              "geo_domestic"),
    # candidatos sin geo → nacional
    ("cuantos candidatos se presentaron",                "nacional"),
    ("lista de candidatos",                              "nacional"),
    ("cuantos candidatos hay",                           "nacional"),
    ("todos los candidatos",                             "nacional"),
    # top N + bare dept → geo_domestic
    ("top 3 Ica",                                        "geo_domestic"),
    ("top 5 Cusco",                                      "geo_domestic"),
    ("top 3 Puno",                                       "geo_domestic"),
    ("top 10 Arequipa",                                  "geo_domestic"),
    # top N + en dept → geo_domestic
    ("top 5 en Lima",                                    "geo_domestic"),
    ("top 3 en Arequipa",                                "geo_domestic"),
    # top N + Peru → nacional
    ("top 5 Peru",                                       "nacional"),
    ("top 5 en Peru",                                    "nacional"),
    ("top 10",                                           "nacional"),
    ("top 20",                                           "nacional"),
    # Complex candidate
    ("cuantos votos tuvo Lopez Aliaga en Arequipa",      "candidate"),
    ("quien gano en el departamento de Puno",            "geo_domestic"),
    # Range reasoning
    ("de las mesas 900001 al 900010 quien gano",         "range_reasoning"),
    ("mesas del 500001 al 500005 resultados",            "range_reasoning"),
    # Ica as geo (4 chars exact)
    ("resultados en Ica",                                "geo_domestic"),
    ("top 3 Ica",                                        "geo_domestic"),
    # Foreign with context
    ("resultados electorales en Argentina",              "geo"),
    ("votos en Toronto Canada",                          "geo"),
    # Non-electoral
    ("como preparar ceviche",                            "unknown"),
    ("dame el clima de Lima",                            "unknown"),
    ("receta de lomo saltado",                           "unknown"),
    # Mesa
    ("dame datos de la mesa 900100",                     "mesa"),
    ("la mesa 123456 estado",                            "mesa"),
    # Legislative
    ("senadores para Puno",                              "legislative_top_candidate"),
    ("diputados en Loreto",                              "legislative_top_candidate"),
    # Foreign summary
    ("cuantos peruanos votaron en el exterior",          "geo_foreign_summary"),
    # Candidate
    ("Keiko cuantos votos",                              "candidate"),
    ("Aliaga votos",                                     "candidate"),
    ("cual fue el porcentaje de Sagasti",                "candidate"),
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
