"""Cycle 48 — pronombres, interrogativas mixtas, multi-candidato variantes."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # "cuánto obtuvo él en Lima" → ambiguous pronoun
    ("cuanto obtuvo el en Lima",                   "geo_domestic"),
    # "dame los resultados de Aliaga"
    ("dame los resultados de Aliaga",              "candidate"),
    # "quiero saber cuantos votos tuvo Sagasti"
    ("quiero saber cuantos votos tuvo Sagasti",    "candidate"),
    # "necesito el resultado de Keiko en Puno"
    ("necesito el resultado de Keiko en Puno",     "candidate"),
    # "compare Aliaga con Fujimori en Arequipa"
    ("compare Aliaga con Fujimori en Arequipa",    "multi_candidate"),
    # "cual es la diferencia entre Aliaga y Keiko"
    ("cual es la diferencia entre Aliaga y Keiko", "multi_candidate"),
    # "resultados segunda vuelta" → depende de elección, nacional probable
    ("resultados segunda vuelta",                  "nacional"),
    # "me puedes decir cuantos votos tuvo Lopez Aliaga"
    ("me puedes decir cuantos votos tuvo Lopez Aliaga", "candidate"),
    # "por favor dime cuanto saco Keiko"
    ("por favor dime cuanto saco Keiko",           "candidate"),
    # "si Aliaga gano en Loreto"
    ("si Aliaga gano en Loreto",                   "candidate"),
    # "ganó Keiko o Aliaga en Cusco"
    ("gano Keiko o Aliaga en Cusco",               "multi_candidate"),
    # "quien es el candidato con mas votos"
    ("quien es el candidato con mas votos",        "nacional"),
    # "cuantos votos faltan por contar"
    ("cuantos votos faltan por contar",            "nacional"),
    # "resultados en San Borja" → con DB vacía, RENIEC no disponible, catalogo extranjero gana
    ("resultados en San Borja",                    "geo"),
    # "top 10 en villa el salvador" → idem, sin DB local
    ("top 10 en villa el salvador",                "geo"),
    # "que paso en jesus maria"
    ("que paso en jesus maria",                    "geo_domestic"),
    # "mesa 999999"
    ("mesa 999999",                                "mesa"),
    # "Aliaga gano en primera vuelta"
    ("Aliaga gano en primera vuelta",              "candidate"),
    # "cual fue la votacion de Keiko"
    ("cual fue la votacion de Keiko",              "candidate"),
    # "cuanto es 2+2" → math guard
    ("cuanto es 2+2",                              "unknown"),
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
