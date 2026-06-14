"""Cycle 74 — NLU: frases con 'mejor', porcentajes, nombres raros, preguntas anidadas."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # "mejor" como superlativo electoral
    ("cual fue el mejor resultado de Aliaga",                  "candidate"),
    ("quien tuvo el mejor resultado en Loreto",                "geo_domestic"),
    # Porcentajes
    ("que porcentaje de votos obtuvo Keiko en Lima",           "candidate"),
    ("que porcentaje saco Aliaga en Puno",                     "candidate"),
    # Preguntas con "tanto"
    ("cuanto voto por Aliaga en Lima",                         "candidate"),
    ("cuanto voto por Keiko en Arequipa",                      "candidate"),
    # Variante: "cuanto obtuvo" sin "votos"
    ("cuanto obtuvo Nieto en Cusco",                           "candidate"),
    # Geo extranjero plural
    ("cuantos votos hay en los paises de Europa",              "unknown"),  # demasiado vago → sin resultado
    # Mesa con prefijo de area
    ("mesa 050099 Lima",                                       "mesa"),
    # Legislativo con partido
    ("cuantos escanos tiene Renovacion Popular",               "legislative_top_candidate"),
    # Multi-candidato con 3+ candidatos (deberia ser multi_candidate o nacional)
    ("Aliaga, Keiko y Nieto quienes sacaron mas",              "multi_candidate"),
    # No electoral: economia
    ("cual es el sueldo minimo en Peru",                       "unknown"),
    # No electoral: fauna
    ("que animales viven en la selva peruana",                 "unknown"),
    # Candidato con "a favor de"
    ("cuantos votos a favor de Aliaga en Tacna",               "candidate"),
    # Range con performance coloquial
    ("del 500001 al 500010 quien jalaron mas",                 "range_reasoning"),
    # Geo con "norte/sur"
    ("top 5 en el norte del peru",                             "nacional"),
    # Candidato con apodo largo
    ("cuantos votos saco el torero Aliaga en Lima",            "candidate"),
    # Multi-candidato formal
    ("comparacion de votos entre Keiko y Aliaga",              "multi_candidate"),
    # Mesa directa desde API
    ("dame los datos de la mesa 100001",                       "mesa"),
    # Nacional con "en el pais"
    ("cuantos votos se contabilizaron en el pais",             "nacional"),
]


def _intent(resp: dict) -> str:
    return (resp.get("data") or {}).get("intent", "unknown")


def main():
    passed = failed = 0
    for query, expected in CASES:
        resp = onpe_chat(query)
        got = _intent(resp)
        ok = got == expected
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{status} exp={expected:<25} got={got:<30} | {query}")
    print(f"\n{passed}/{len(CASES)} PASS  {failed}/{len(CASES)} FAIL")


if __name__ == "__main__":
    main()
