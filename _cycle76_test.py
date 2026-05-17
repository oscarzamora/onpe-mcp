"""Cycle 76 stress tests — 40 queries covering:
- Sports scheduling guard ('cuando es el proximo partido')
- 'peruanos' substring vs 'peru' word-boundary  
- Multi-candidate 'o ... quien'
- Geo with 'region' prefix
- Legislative variants
- Mesa priority over candidate
- Various edge cases
"""
import logging
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

CASES = [
    # Sports scheduling → unknown
    ("cuando es el proximo partido de Peru",             "unknown"),
    ("cuando es el partido Peru vs Chile",               "unknown"),
    ("cuando se juega el partido de futbol",             "unknown"),
    ("a que hora es el partido Peru hoy",                "unknown"),
    # Candidate with electoral 'partido' context → still works
    ("cuantos votos tuvo Aliaga en partido de Lima",     "candidate"),
    ("resultados del partido Renovacion Popular",        "candidate"),
    # peruanos substring doesn't match \bperu\b
    ("cuantos peruanos hay en Lima",                     "geo_domestic"),
    ("peruanos que viven en Arequipa",                   "geo_domestic"),
    ("top 5 candidatos para peruanos en Italia",         "geo"),
    # Lima Peru → domestic
    ("candidatos en Lima Peru",                          "geo_domestic"),
    ("resultados en Lima Peru",                          "geo_domestic"),
    # Multi-candidate 'o ... quien'
    ("Aliaga o Keiko quien saco mas",                    "multi_candidate"),
    ("Fujimori o Urresti quien gano en Lima",            "multi_candidate"),
    ("Lopez Aliaga o Sagasti quien tiene mas votos",     "multi_candidate"),
    # Geo with 'region'
    ("resultados en la region Puno",                     "geo_domestic"),
    ("top 5 en la region de Loreto",                     "geo_domestic"),
    ("quien gano en la region Lima",                     "geo_domestic"),
    # Legislative variants
    ("escanos para Junin diputados",                     "legislative_top_candidate"),
    ("quienes son los senadores de Arequipa",            "legislative_top_candidate"),
    ("cuantos escanos gano cada partido",                "legislative_top_candidate"),
    # Mesa priority
    ("en la mesa 900100 cuantos votos tuvo Aliaga",      "mesa"),
    ("la mesa 050100 quien gano",                        "mesa"),
    ("dame la mesa 123456",                              "mesa"),
    # Multi-candidate numeric guard stays
    ("candidatos entre 10000 y 50000 votos",             "nacional"),
    ("quienes tienen entre 500000 y 2000000 votos",      "nacional"),
    # Unknown sports/general
    ("quien gano el mundial",                            "unknown"),
    ("cuando es el proximo partido de Alianza Lima",     "unknown"),
    # Candidate variations
    ("cuantos votos tuvo Pedro Castillo Terrones",       "candidate"),
    ("resultados de Keiko Sofia Fujimori Higuchi",       "candidate"),
    # Exterior summary
    ("cuantos peruanos votaron en el exterior",          "geo_foreign_summary"),
    ("votos de peruanos en el extranjero",               "geo_foreign_summary"),
    # National with explicit Peru
    ("top 20 en Peru",                                   "nacional"),
    ("quien gano en Peru",                               "nacional"),
    # Non-electoral
    ("cuando nacio Lopez Aliaga",                        "unknown"),
    ("cual es la capital de Peru",                       "unknown"),
    # Foreign geo
    ("resultados para Peru en China",                    "geo"),
    ("votos de Peru en Francia",                         "geo"),
    # Domestic + Peru suffix
    ("resultados en Arequipa Peru",                      "geo_domestic"),
    # Candidate short name
    ("Keiko cuantos votos",                              "candidate"),
    ("Aliaga votos",                                     "candidate"),
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
