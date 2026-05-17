"""Cycle 55 — multi-intención, variantes verbales extra, estructuras complejas."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato: "en cuanto quedo Aliaga"
    ("en cuanto quedo Aliaga",                     "candidate"),
    # Nacional: "cuantos blancos y nulos hubo"
    ("cuantos blancos y nulos hubo",               "nacional"),
    # Mesa: "codigo de mesa 789012"
    ("codigo de mesa 789012",                      "mesa"),
    # Candidato: "Aliaga sumó cuántos votos"
    ("Aliaga sumo cuantos votos",                  "candidate"),
    # Geo domestic: "elecciones en San Juan de Lurigancho"
    ("elecciones en San Juan de Lurigancho",       "geo_domestic"),
    # Unknown: "como se dice voto en ingles"
    ("como se dice voto en ingles",                "unknown"),
    # Multi: "diferencia de votos entre Aliaga y Keiko en Puno"
    ("diferencia de votos entre Aliaga y Keiko en Puno", "multi_candidate"),
    # Candidato: "Aliaga en Loreto cuantos votos"
    ("Aliaga en Loreto cuantos votos",             "candidate"),
    # Geo: "resultados en Buenos Aires Argentina" → ambiguous (Peru district + Argentina)
    ("resultados en Buenos Aires Argentina",       "ambiguous"),
    # Nacional: "quien obtuvo el primer lugar"
    ("quien obtuvo el primer lugar",               "nacional"),
    # Candidato: "que numero de votos junto Forsyth"
    ("que numero de votos junto Forsyth",          "candidate"),
    # Range: "mesas que arrancan en 500 quien gano"
    ("mesas que arrancan en 500 quien gano",       "range_reasoning"),
    # Candidato: "como le fue a Keiko en la costa"
    ("como le fue a Keiko en la costa",            "candidate"),
    # Legislativo: "cuantos legisladores le tocan a Cusco"
    ("cuantos legisladores le tocan a Cusco",      "legislative_top_candidate"),
    # Unknown: "que significa abstencion"
    ("que significa abstencion",                   "unknown"),
    # Geo domestic: "resultados de la region Lima"
    ("resultados de la region Lima",               "geo_domestic"),
    # Candidato: "en la primera vuelta Keiko cuantos votos saco"
    ("en la primera vuelta Keiko cuantos votos saco", "candidate"),
    # Multi con "ambos": "ambos Keiko y Aliaga cuantos votos"
    ("ambos Keiko y Aliaga cuantos votos",         "multi_candidate"),
    # Mesa: "ver acta 654321"
    ("ver acta 654321",                            "mesa"),
    # Nacional: "balance electoral"
    ("balance electoral",                          "nacional"),
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
