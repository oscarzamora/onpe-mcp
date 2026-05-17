"""Cycle 66 — NLU: complex geo context, noisy candidate, tech/sports non-electoral."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Geo domestic: regions and macroregions
    ("cuantos votos hubo en Arequipa y Moquegua",               "geo_domestic"),
    ("resultados de la region Grau",                            "geo_domestic"),
    ("quienes lideraron en la sierra sur",                      "nacional"),    # no specific dept
    # Candidate with complex context
    ("que porcentaje de votos obtuvo Aliaga en primera vuelta",  "candidate"),
    ("cuantos puntos obtuvo Fujimori en el primer escrutinio",   "candidate"),
    ("en cuanto cerro Nieto",                                    "candidate"),
    # Multi-candidate
    ("Aliaga y Fujimori en Loreto cuantos votos",               "multi_candidate"),
    ("compara a Keiko con Nieto en Piura",                      "multi_candidate"),
    # Nacional
    ("quien obtuvo mas votos en todo el territorio peruano",    "nacional"),
    ("cual es el numero de votos validos a nivel nacional",     "nacional"),
    # Foreign geo
    ("resultados en Tel Aviv",                                   "geo"),
    ("cuantos votos en Helsinki",                                "geo"),
    # Legislative
    ("cuantos escanos logro cada agrupacion en Loreto",         "legislative_top_candidate"),
    ("quienes son los representantes de Lima",                  "legislative_top_candidate"),
    # Non-electoral (tech/sports/other)
    ("que gano el real madrid en la champions",                 "unknown"),
    ("cuanto cuesta el iphone 15",                              "unknown"),
    ("que equipos bajaron de division",                         "unknown"),
    # Ambiguous but electoral context
    ("hay resultados disponibles",                              "nacional"),
    # Range
    ("ver mesas 050001 al 050010 quien fue primero",            "range_reasoning"),
    # Mesa direct
    ("datos mesa 450200",                                        "mesa"),
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
