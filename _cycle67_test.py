"""Cycle 67 — NLU: slang, informal, question variants, domain edge cases."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Slang / colloquial Peruvian
    ("cuantos votos chapó Aliaga en Lima",                      "candidate"),   # chapó = agarró/consiguió
    ("cuantos votos pesco Fujimori en Cusco",                   "candidate"),   # pescó = consiguió
    ("cuanto cargo el congreso para aliaga",                     "unknown"),  # "cargo" slang pero "congreso" no = candidato → ambiguo
    # Question inversion
    ("de cuantos votos dispone Aliaga",                         "candidate"),
    ("a favor de quien votaron mas en Lima",                    "geo_domestic"),
    # Geo with article variations
    ("resultados en el callao",                                  "geo_domestic"),
    ("top 5 en la region de Loreto",                            "geo_domestic"),
    # Foreign geo with country/city disambiguation
    ("cuantos votos en Madrid",                                  "geo"),
    ("top 3 en Paris",                                          "geo"),
    # Multi-candidate with "y" ambiguity
    ("Aliaga Fujimori quienes van adelante",                    "geo"),  # sin "y" entre nombres → geo o unknown
    ("Lopez Aliaga y Keiko quien gano mas",                     "multi_candidate"),
    # Nacional
    ("quienes pasaron a segunda vuelta",                        "nacional"),
    ("cual fue la participacion ciudadana",                     "nacional"),
    # Legislative
    ("cuantos representantes por region en Cusco",              "legislative_top_candidate"),
    # Non-electoral
    ("cual es el PIB del peru",                                 "unknown"),
    ("cuanta inflacion tiene el peru",                          "unknown"),
    ("quien fue el primer presidente del peru",                 "unknown"),  # historical
    ("que tiempo hace en lima hoy",                             "unknown"),
    # Range
    ("de las mesas 100001 al 100010 quien fue primero",         "range_reasoning"),
    # Mesa
    ("mesa 320099",                                              "mesa"),
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
