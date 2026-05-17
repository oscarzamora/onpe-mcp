"""Cycle 68 — NLU: partidos, candidatos menos conocidos, preguntas de aclaración."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from onpe_mcp.server import onpe_chat

CASES = [
    # Partidos políticos
    ("cuantos votos obtuvo el partido Renovacion Popular",      "candidate"),
    ("cuantos escanos saco Fuerza Popular",                     "legislative_top_candidate"),  # escanos = curules → legislativo
    ("que porcentaje obtuvo Peru Libre en Ayacucho",           "candidate"),
    # Candidatos con guiones o mayusculas raras
    ("cuantos votos obtuvo Nieto-Degregori en Lima",            "candidate"),
    ("cuantos votos obtuvo ALIAGA en Lima",                     "candidate"),
    # Preguntas de confirmacion
    ("tienes resultados de la mesa 010101",                     "mesa"),
    ("se puede consultar la mesa 030202",                       "mesa"),
    # Geo extranjero especifico
    ("top 5 en Tokio",                                          "geo"),
    ("cuantos votos hubo en Nueva York",                        "geo"),
    # Nacional / agregado
    ("cuantos peruanos votaron en el exterior",                 "nacional"),
    ("cuantos peruanos residentes en el extranjero votaron",    "nacional"),
    # Legislativo variantes
    ("que congresistas salieron elegidos en Piura",             "legislative_top_candidate"),
    ("cuantos senadores le corresponden a Tumbes",              "legislative_top_candidate"),
    # Rango de mesas
    ("quienes ganaron en las mesas 050001 a 050005",            "range_reasoning"),
    # Multi candidato
    ("comparar resultados de Aliaga y Moreno",                  "multi_candidate"),
    ("Aliaga vs Lescano cuantos votos",                         "multi_candidate"),
    # No electoral
    ("que dice la constitucion del peru",                       "unknown"),
    ("cuantos departamentos tiene el peru",                     "unknown"),
    # Candidato en geo con ruido
    ("a ver digame cuantos votos saco fujimori en La Libertad", "candidate"),
    # Ambiguedad → pedir aclaracion
    ("resultados",                                              "unknown"),
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
