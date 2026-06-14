"""Cycle 65 — NLU: partido names, passive voice, trailing noise, regional queries, neg-context."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Party names as candidate proxy
    ("cuantos votos logro Fuerza Popular",                      "candidate"),
    ("que saco el partido Peru Libre",                          "candidate"),
    ("que tanto obtuvo Avancemos Peru",                         "candidate"),
    # Passive voice
    ("cuantos votos fueron adjudicados a Aliaga",               "candidate"),
    ("cuantos votos le fueron asignados a Fujimori",            "candidate"),
    # Trailing noise
    ("votos de Aliaga en Cusco porfavor",                       "candidate"),
    ("resultados de Fujimori en Ayacucho, gracias",             "candidate"),
    # Geo with prepositions
    ("top 5 candidatos para el departamento de Loreto",         "geo_domestic"),
    # "quienes ganaron en el norte del peru" → nacional (regional without specific dept)
    ("quienes ganaron en el norte del peru",                    "nacional"),
    # Multi-candidate
    ("entre Aliaga y Keiko quien lidera",                       "multi_candidate"),
    ("Nieto vs Aliaga quien saco mas",                          "multi_candidate"),
    # Nacional
    ("quien fue el mas votado en todo el peru",                 "nacional"),
    ("cuantos votos en blanco hubo en total",                   "nacional"),
    # Foreign geo
    ("cuantos votos habia en Tokio",                            "geo"),
    ("top 3 en Viena",                                          "geo"),
    # Legislative
    ("quienes ganaron escanos en Junin",                        "legislative_top_candidate"),
    # Non-electoral
    ("cuando es el proximo mundial de futbol",                  "unknown"),
    ("como funciona el sistema nervioso",                       "unknown"),
    # Range
    ("mesas desde 020000 hasta 020020 quien primero",           "range_reasoning"),
    # Mesa  
    ("ver acta mesa 123001",                                    "mesa"),
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
