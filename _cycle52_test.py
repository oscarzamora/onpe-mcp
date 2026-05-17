"""Cycle 52 — partidos políticos, siglas, errores fonéticos extremos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Partido por nombre completo
    ("cuantos votos tuvo Accion Popular",          "candidate"),
    # Partido: Alianza para el Progreso
    ("votos de Alianza para el Progreso",          "candidate"),
    # Partido: Perú Libre
    ("cuanto saco Peru Libre",                     "candidate"),
    # Candidato con "el Sr." prefix
    ("cuantos votos tuvo el Sr. Sagasti",          "candidate"),
    # Error fonético grave: "cuantos botos sako aliyaga"
    ("cuantos botos sako aliyaga",                 "candidate"),
    # Geo domestic: solo el nombre del departamento
    ("Moquegua",                                   "geo_domestic"),
    # Nacional: "margen de victoria"
    ("cual fue el margen de victoria",             "nacional"),
    # Candidato: "votos totales de Keiko Fujimori"
    ("votos totales de Keiko Fujimori",            "candidate"),
    # Mesa fallback: "acta numero 101010"
    ("acta numero 101010",                         "mesa"),
    # Unknown: "dónde queda Lima" (pregunta geográfica no electoral)
    ("donde queda Lima",                           "geo_domestic"),
    # Geo: "resultados Auckland"
    ("resultados Auckland",                        "geo"),
    # Candidato: "cual es el recuento de votos de Urresti"
    ("cual es el recuento de votos de Urresti",    "candidate"),
    # Multi: "Keiko y Lopez Aliaga quienes van arriba"
    ("Keiko y Lopez Aliaga quienes van arriba",    "multi_candidate"),
    # Nacional: "cuantos peruanos votaron"
    ("cuantos peruanos votaron",                   "nacional"),
    # Range: "de la mesa 200000 a la 200999"
    ("de la mesa 200000 a la 200999",              "range_reasoning"),
    # Candidato: "resultados para Aliaga"
    ("resultados para Aliaga",                     "candidate"),
    # Geo domestic: "como vamos en Junin"
    ("como vamos en Junin",                        "geo_domestic"),
    # Unknown: "dame una lista de hoteles en Lima"
    ("dame una lista de hoteles en Lima",          "unknown"),
    # Candidato: "en Cusco cuantos tuvo Urresti"
    ("en Cusco cuantos tuvo Urresti",              "candidate"),
    # Nacional: "ranking de candidatos por votos"
    ("ranking de candidatos por votos",            "nacional"),
]

ok_count = 0
fail_count = 0
for q, expected in CASES:
    intent = run(q)
    status = "PASS" if intent == expected else "FAIL"
    if status == "PASS":
        ok_count += 1
    else:
        fail_count += 1
    line = f"{status} exp={expected:<35} got={intent:<35} | {q}"
    print(line.encode("ascii", "replace").decode())

print(f"\n{ok_count}/{ok_count+fail_count} PASS  {fail_count}/{ok_count+fail_count} FAIL")
