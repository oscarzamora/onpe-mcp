"""Cycle 63 — NLU: compound names, legislative sub-intents, geo edge, noisy queries."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Compound candidate names with accents
    ("votos de Victor Andres Belaunde en Loreto",               "candidate"),
    ("cuantos votos obtuvo Maria del Carmen",                   "candidate"),
    ("cuanto saco el partido Accion Popular",                   "candidate"),
    # Noisy queries (extra filler)
    ("oye sabes cuanto saco en total el aliaga",                "candidate"),
    ("podrias decirme cuantos votos obtuvo Castillo en total",  "candidate"),
    ("me pregunto cuantos votos habia logrado Fujimori",        "candidate"),
    # Geo domestic with preposition variations
    ("como le fue a Lima en las elecciones",                    "geo_domestic"),
    ("cuantos votos hay en el Callao",                          "geo_domestic"),
    ("quien gano en Ucayali",                                   "geo_domestic"),
    # Geo foreign variations
    ("cuantos votos en Suecia",                                 "geo"),
    ("resultados de peruanos en Australia",                     "geo"),
    ("top candidatos en Londres",                               "geo"),
    # Legislative
    ("congresistas elegidos en Cajamarca",                      "legislative_top_candidate"),
    ("cuantos escanos gano cada partido en Piura",              "legislative_top_candidate"),
    # Multi-candidate
    ("Aliaga o Fujimori quien va primero",                      "multi_candidate"),
    ("cuantos mas votos tiene Aliaga que Fujimori",             "multi_candidate"),
    # Nacional broad
    ("como van las elecciones 2026",                            "nacional"),
    ("dame el ranking de candidatos",                           "nacional"),
    # Non-electoral
    ("que pelicula gano el oscar este ano",                     "unknown"),
    # Mesa
    ("quiero ver el acta de la mesa 010101",                    "mesa"),
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
