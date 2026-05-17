"""Cycle 64 — NLU: informal contractions, non-electoral domains, geo provinces, range combos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Informal contractions / slang
    ("cuantos votos jalo Lopez Aliaga",                         "candidate"),   # jalo = jalé (coloquial)
    ("cuantos puntos tuvo el nieto",                            "candidate"),
    ("que salio Aliaga en las elecciones",                      "candidate"),
    # Inverted order with verb
    ("Fujimori cuanto llevo en Lima",                           "candidate"),
    ("Castillo que tan alto llego",                             "candidate"),
    # Foreign geo edge
    ("resultados en nueva york",                                "geo"),
    ("cuantos votos en Ciudad de Mexico",                       "geo"),
    # Domestic geo province + district
    ("top 3 en la provincia de Ica",                            "geo_domestic"),
    ("votos en el distrito de Barranco",                        "geo_domestic"),
    # Multi-candidate with more context
    ("diferencia de porcentaje entre Aliaga y Keiko",           "multi_candidate"),
    ("Aliaga tiene mas votos que Fujimori verdad",              "multi_candidate"),
    # Nacional
    ("cuantas mesas se procesaron",                             "nacional"),
    ("cual fue el total de votos validos",                      "nacional"),
    # Legislative
    ("cuantos senadores gano Accion Popular",                   "legislative_top_candidate"),
    ("que congresistas salieron en Huanuco",                    "legislative_top_candidate"),
    # Non-electoral
    ("como se dice hola en japones",                            "unknown"),
    ("cuanto cuesta un vuelo a miami",                          "unknown"),
    ("en que ano se fundo lima",                                "unknown"),
    # Range
    ("entre la mesa 010000 y 010020 quien fue primero",         "range_reasoning"),
    # Mesa
    ("informacion de la mesa numero 800001",                    "mesa"),
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
