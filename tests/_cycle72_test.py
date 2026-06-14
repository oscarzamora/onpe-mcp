"""Cycle 72 — NLU: variantes de multi-candidato, frases complejas, fragmentos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Multi-candidato con "e" (instead of "y")
    ("votos de Aliaga e Fujimori en Lima",                     "multi_candidate"),
    # Multi-candidato con vs
    ("Aliaga vs Fujimori quien va ganando",                    "multi_candidate"),
    # Candidato seguido de un numero (no mesa)
    ("cuantos votos obtuvo el candidato numero 5",             "nacional"),  # "candidato" → nacional fallback
    # Geo con 2 geos y "y" → no multi_candidate
    ("resultados en Lima y Arequipa",                          "geo_domestic"),
    # Geo extranjero pais
    ("resultados en Francia",                                  "geo"),
    ("top 5 en Alemania",                                      "geo"),
    # Nacional con "total"
    ("total de votos validos en el pais",                      "nacional"),
    # Mesa con texto alrededor
    ("la mesa 123456 que resultados tiene",                    "mesa"),
    ("que paso con la mesa 056001",                            "mesa"),
    # Range
    ("mesas del 400001 al 400015 quien fue primero",           "range_reasoning"),
    # Candidato en minusculas
    ("cuantos votos tuvo pedro castillo en lima",              "candidate"),
    # No electoral con "resultado"
    ("cual fue el resultado del partido peru vs brasil",       "unknown"),
    # Legislativo con "escanos"
    ("cuantos escanos tiene derecho Pasco",                    "legislative_top_candidate"),
    # Frases que empiezan con saludo
    ("hola, cuantos votos saco aliaga",                        "candidate"),
    ("buenos dias, top 5 en Arequipa",                        "geo_domestic"),
    # Geo con articulo definido
    ("resultados del departamento de Amazonas",               "geo_domestic"),
    # Candidato con doble apellido
    ("cuantos votos saco Urresti Elera",                       "candidate"),
    # Nacional sin candidato explicito
    ("resumen de los resultados electorales",                  "nacional"),
    # Geo extranjero ciudad especifica
    ("cuantos votaron en Sao Paulo",                           "geo"),
    # Non-electoral: tecnologia
    ("que es la inteligencia artificial",                      "unknown"),
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
