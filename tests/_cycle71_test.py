"""Cycle 71 — NLU: doble geo, preguntas inversas, ruido extremo, partido+candidato."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Preguntas con doble ubicacion (deberia priorizar la mas especifica)
    ("resultados en Lima provincia",                            "geo_domestic"),
    ("top 5 en Arequipa ciudad",                               "geo_domestic"),
    # Candidatos referidos por partido
    ("cuantos votos saco Renovacion Popular en Moquegua",      "candidate"),
    ("cuantos votos obtuvo Fuerza Popular en Lima",            "candidate"),
    # Formulaciones raras pero validas
    ("quien encabeza en Madre de Dios",                        "geo_domestic"),
    ("los resultados de Loreto por favor",                     "geo_domestic"),
    # Nacional inequivoco
    ("quien gano las presidenciales 2026",                     "nacional"),
    ("cuantos votos validos hubo en total",                    "nacional"),
    # Candidato con ciudad y ruido
    ("oiga me puede decir cuantos votos tuvo Nieto en Ica",   "candidate"),
    ("buenas cuantos votos saco aliaga en trujillo",           "candidate"),
    # Multi-candidato variante formal
    ("diferencia de votos entre Aliaga y Fujimori en Lima",   "multi_candidate"),
    ("cuanto mas saco Keiko que Nieto en total",               "multi_candidate"),
    # Range con candidato
    ("en las mesas 600001 al 600020 quien fue primero",        "range_reasoning"),
    # Legislativo variantes
    ("a cuantos diputados tiene derecho Cusco",                "legislative_top_candidate"),
    ("quienes ganaron un escano en Lambayeque",                "legislative_top_candidate"),
    # Geo extranjero variantes
    ("top 3 peruanos en Berlin",                               "geo"),
    ("cuantos votantes hay en Miami",                          "geo"),
    # No electoral
    ("cuanto cuesta un vuelo Lima Paris",                      "unknown"),
    ("que es el voto electronico",                             "unknown"),
    # Mesa
    ("resultado de la mesa 777001",                            "mesa"),
    # Candidato con numero largo sin contexto mesa
    ("cuantos votos tuvo Aliaga a nivel nacional",             "candidate"),
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
