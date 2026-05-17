"""Cycle 73 — NLU: mezcla de idiomas, frases muy largas, candidatos con numeros."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Candidatos ambiguos (no existen pero deben ser candidatos)
    ("cuantos votos saco Garcia Belaunde en Lima",              "candidate"),
    ("cuantos votos obtuvo Ollanta en Lima",                    "candidate"),
    # Preguntas con signos de puntuacion
    ("cuantos votos saco Keiko? en Lima",                      "candidate"),
    ("top 5... en Arequipa",                                    "geo_domestic"),
    # Candidatos con "el" antes del nombre
    ("cuantos votos saco el Nieto en Cuzco",                   "candidate"),
    ("cuantos votos tuvo el Aliaga en Piura",                   "candidate"),
    # Multi-candidato con nombres de 1 sola palabra
    ("Keiko y Aliaga quienes sacaron mas votos",               "multi_candidate"),
    # Geo con preposicion "para"
    ("resultados para Amazonas",                               "geo_domestic"),
    ("top 3 para San Martin",                                   "geo_domestic"),
    # Range con guion
    ("mesas 700001-700010 quien fue primero",                  "range_reasoning"),
    # Nacional variante con "todo el pais"
    ("resultados de todo el pais",                             "nacional"),
    # Candidato coloquial sin "votos"
    ("como le fue a Keiko en Lima",                             "candidate"),
    ("como le fue a Aliaga en Cusco",                          "candidate"),
    # Mesa variante
    ("quiero ver la mesa 888001",                               "mesa"),
    # Legislativo pregunta informal
    ("cuantos congresistas se eligen en Lima",                  "legislative_top_candidate"),
    # No electoral: salud
    ("cuantos hospitales hay en Lima",                         "unknown"),
    # Extranjero con acentos
    ("top 5 en Bogotá Colombia",                               "geo"),
    # Multi-candidato con "o"
    ("Aliaga o Keiko quien saco mas en Lima",                  "multi_candidate"),
    # Candidato muy coloquial
    ("que tal le fue a fujimori en Puno",                      "candidate"),
    # Nacional puro
    ("quien gano las elecciones presidenciales",               "nacional"),
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
