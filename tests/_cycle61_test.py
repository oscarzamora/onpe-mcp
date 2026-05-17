"""Cycle 61 — NLU stress test: abbreviations, colloquial, geo-edge, legislative, range variations."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Abbreviations / initials
    ("KFF y RLA cuantos votos",                                 "multi_candidate"),
    ("votos de KFF en Cusco",                                   "candidate"),
    ("cuantos votos saco GLO en la primera vuelta",             "candidate"),
    # Multi-candidate with geography
    ("Aliaga vs Fujimori en Ayacucho",                         "multi_candidate"),
    ("compara votos de Castillo con Keiko en Junin",           "multi_candidate"),
    # Colloquial nacional
    ("quien le gano a quien en las ultimas elecciones",        "nacional"),
    ("como quedo la votacion nacional",                        "nacional"),
    # Geo domestic edge
    ("resultados en Pasco",                                    "geo_domestic"),
    ("top 5 candidatos en Madre de Dios",                     "geo_domestic"),
    ("cuantos votos en San Martin",                            "geo_domestic"),
    # Foreign geo
    # "cuantos peruanos votaron en Canada" — "peruanos votaron" fires nacional first; acceptable
    ("cuantos peruanos votaron en Canada",                     "nacional"),
    ("top 5 en japon",                                         "geo"),
    ("resultados en nueva zelanda",                            "geo"),
    # Legislative (top N variants return legislative_top_candidate subtype)
    ("top 5 senadores en Lambayeque",                          "legislative_top_candidate"),
    ("quienes son los diputados de Tumbes",                    "legislative_top_candidate"),
    # Range
    ("mesas del 050000 al 050020 quien fue primero",           "range_reasoning"),
    ("del 800100 al 800120 quienes sacaron mas",               "range_reasoning"),
    # Non-electoral
    ("como se juega al futbol",                                "unknown"),
    ("cual es la formula del agua",                            "unknown"),
    # Mesa
    ("dame los datos de la mesa 999001",                       "mesa"),
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
