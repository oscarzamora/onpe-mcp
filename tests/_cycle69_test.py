"""Cycle 69 — NLU: segunda vuelta, provincia, aliasas, mixtos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Segunda vuelta
    ("cuantos votos saco fujimori en segunda vuelta",           "candidate"),
    ("quien gano la segunda vuelta",                            "nacional"),
    ("resultados de la segunda vuelta en Arequipa",             "geo_domestic"),
    # Alias culturales / apodos
    ("cuantos votos saco el chino fujimori",                    "candidate"),
    ("que saco la keiko en Lima",                               "candidate"),
    ("cuantos votos tuvo el Nieto en Cusco",                    "candidate"),
    # Geo con ruido y preguntas largas
    ("me podrias decir quienes fueron los mas votados en Puno", "geo_domestic"),
    ("sabes cuantos votos tuvo Aliaga en Ica",                  "candidate"),
    # Candidato solo, sin geo
    ("cuantos votos en total saco Lopez Aliaga",                "candidate"),
    # Extranjero con ruido
    ("peruanos que votaron en Australia cuantos fueron",        "geo"),
    ("cuantos votos se emitieron en Frankfurt",                 "geo"),
    # Nacional variantes
    ("quienes son los candidatos mas votados a nivel nacional", "nacional"),
    ("dame el ranking final de candidatos",                     "nacional"),
    # Legislativo variantes
    ("quienes son los congresistas elegidos en Loreto",         "legislative_top_candidate"),
    ("cuantos diputados le tocan a Ancash",                     "legislative_top_candidate"),
    # Mesa + rango
    ("mesa 999001",                                             "mesa"),
    ("de la mesa 300001 a la 300010 quienes salieron primero", "range_reasoning"),
    # Multi-candidato
    ("Aliaga y Moreno quienes sacaron mas votos",               "multi_candidate"),
    # No electoral
    ("como se llama el parque nacional mas grande del peru",    "unknown"),
    # "en Lima" solo → geo_domestic es razonable (top en Lima)
    ("en Lima",                                                 "geo_domestic"),
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
