"""Cycle 62 — NLU: colloquial verbs, accent combos, typos, mixed case, geo edge cases."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Typos / accent variants
    ("cuantos votos tubo Lopez Aliaga",                         "candidate"),   # tubo = tuvo
    ("cuantos votos obtubo Fujimori",                           "candidate"),   # obtubo = obtuvo
    ("cuantos votos sako Castillo",                             "candidate"),   # sako = saco
    # Mixed case
    ("VOTOS DE KEIKO EN AREQUIPA",                              "candidate"),
    ("Top 5 EN lima",                                           "geo_domestic"),
    # Colloquial compound
    ("cuanto saco rla en total",                                "candidate"),
    ("que tanto voto la gente por Fujimori",                    "candidate"),
    # Past perfect / compound tense
    ("cuanto habia sacado Nieto en Puno",                       "candidate"),
    ("cuantos votos habria obtenido Aliaga",                    "candidate"),
    # Multi-candidate edge
    ("entre Aliaga y Fujimori quien tuvo mas votos",            "multi_candidate"),
    ("diferencia de votos entre Keiko y Castillo en Lima",      "multi_candidate"),
    # Nacional edge
    ("cuantas actas procesadas",                                "nacional"),
    ("cuantos distritos ya contaron",                           "nacional"),
    # Geo domestic: province level
    ("resultados en la provincia de Piura",                     "geo_domestic"),
    ("top 3 en el distrito de Miraflores",                      "geo_domestic"),
    # Geo foreign city
    ("top 5 en miami",                                          "geo"),
    # "votos en buenos aires" → ambiguous (known: Peru district + Argentina city conflict)
    ("votos en buenos aires",                                   "ambiguous"),
    # Non-electoral
    ("dime la hora en lima",                                    "unknown"),
    ("quien es el dios del sol en la mitologia griega",         "unknown"),
    # Mesa
    ("cuales son los votos en la mesa 750001",                  "mesa"),
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
