"""Cycle 70 — NLU: apodos, acentos, errores de tipeo, legislativo avanzado."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Typos y errores de ortografia
    ("cuantos votos obtubo lopes aliaga",                       "candidate"),   # obtubo typo
    ("cuantos vots sako fujimori",                              "candidate"),   # sako typo
    ("cuantos votos tubo keiko en arequipa",                    "candidate"),   # tubo typo
    # Nombres con acento o sin acento
    ("cuantos votos obtuvo Lopez Aliaga",                       "candidate"),
    ("cuantos votos obtuvo López Aliaga",                       "candidate"),
    # Geo con acentos
    ("top 5 en Junín",                                          "geo_domestic"),
    ("resultados en Apurímac",                                  "geo_domestic"),
    # Pregunta con puntuacion
    ("¿cuántos votos obtuvo Nieto en Lima?",                    "candidate"),
    ("¿quién ganó en Puno?",                                    "geo_domestic"),
    # Comparacion multi-candidato
    ("entre Aliaga y Keiko quien saco mas",                     "multi_candidate"),
    ("Aliaga tiene mas votos que Keiko verdad",                 "multi_candidate"),
    # Nacional con frase ambigua
    ("cuantos peruanos votaron",                                "nacional"),
    ("cual fue el total de votos emitidos",                     "nacional"),
    # Legislativo avanzado
    ("cuantos diputados le corresponden a Piura",               "legislative_top_candidate"),
    ("que congresistas represent an a Tacna",                   "legislative_top_candidate"),
    # Geo extranjero
    ("peruanos en Japon cuantos votos",                         "geo"),
    ("resultados en Toronto Canada",                            "geo"),
    # Range
    ("entre la mesa 200001 y 200010 quienes salieron",         "range_reasoning"),
    # Mesa directa
    ("informacion de la mesa 400500",                          "mesa"),
    # Non-electoral
    ("quien fue el primer alcalde de Lima",                    "unknown"),
    ("cuanto gana un presidente en Peru",                      "unknown"),
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
