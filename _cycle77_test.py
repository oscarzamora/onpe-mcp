"""Cycle 77 stress tests — 40 queries covering:
- Greeting phrases ('hola como estas' → unknown)
- 'porcentaje de NAME' → candidate
- Geo with 'provincia' prefix
- Implicit geo (bare dept name + topic)
- Legislative complex queries
- Multi-candidate 3-way
- Various edge cases
"""
import logging
logging.disable(logging.CRITICAL)

from onpe_mcp.server import onpe_chat

CASES = [
    # Greeting variants → unknown
    ("hola como estas",                                  "unknown"),
    ("hola como esta",                                   "unknown"),
    ("hola que tal",                                     "unknown"),
    ("buenos dias",                                      "unknown"),
    ("buenas tardes",                                    "unknown"),
    # Porcentaje de NAME → candidate
    ("cual fue el porcentaje de Fujimori",               "candidate"),
    ("que porcentaje de votos obtuvo Aliaga",            "candidate"),
    ("el porcentaje del partido AP",                     "candidate"),
    ("porcentaje de votos de Keiko en Arequipa",         "candidate"),
    # Candidate with 'porcentaje' + geo
    ("que porcentaje obtuvo Aliaga en Lima",             "candidate"),
    # National with 'a nivel'
    ("resultados a nivel nacional",                      "nacional"),
    ("cuantos votos a nivel nacional cada candidato",    "nacional"),
    # Geo with 'provincia'
    ("resultados en la provincia de Ica",                "geo_domestic"),
    ("top 3 en la provincia de Piura",                   "geo_domestic"),
    ("quien gano en la provincia de Lima",               "geo_domestic"),
    # Implicit geo (bare dept + topic)
    ("Puno resultados",                                  "geo_domestic"),
    ("Loreto votos",                                     "geo_domestic"),
    ("Arequipa candidatos",                              "geo_domestic"),
    # Legislative complex
    ("cuantos senadores le corresponden a Cajamarca",    "legislative_top_candidate"),
    ("cuantos diputados gano Fuerza Popular en Lima",    "legislative_top_candidate"),
    ("escanos para Junin diputados",                     "legislative_top_candidate"),
    # Multi-candidate 3-way
    ("Aliaga Keiko y Urresti quienes sacaron mas",       "multi_candidate"),
    ("entre Aliaga Fujimori y Sagasti quien gano",       "multi_candidate"),
    # Mesa variations
    ("ver mesa 900100",                                  "mesa"),
    ("mesa 050050 resultados",                           "mesa"),
    ("dame la mesa 123456",                              "mesa"),
    # Complex candidate queries
    ("en que lugar quedo Lopez Aliaga en las elecciones de Lima", "candidate"),
    ("como le fue a Keiko en Puno",                      "candidate"),
    ("cual fue el lugar de Fujimori en la eleccion",     "candidate"),
    # Non-electoral
    ("hola",                                             "unknown"),
    ("gracias",                                          "unknown"),
    ("que hora es",                                      "unknown"),
    ("cual es el precio del dolar",                      "unknown"),
    # Exterior
    ("cuantos peruanos votaron en el exterior",          "geo_foreign_summary"),
    ("resultados de peruanos en el extranjero",          "geo_foreign_summary"),
    # Foreign country
    ("resultados en Bolivia",                            "geo"),
    ("votos en Suecia",                                  "geo"),
    # Candidate short
    ("Keiko cuantos votos",                              "candidate"),
    ("Aliaga votos",                                     "candidate"),
    ("Fujimori resultados",                              "candidate"),
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
