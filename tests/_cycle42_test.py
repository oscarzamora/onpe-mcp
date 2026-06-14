"""Cycle 42 — final comprehensive regression + stability sweep."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # ── Mesa ──
    ("consulta mesa 900100",                            "mesa"),
    ("quiero ver la mesa 01234",                        "mesa"),
    ("mesa 030405",                                     "mesa"),
    ("messa 030405",                                    "mesa"),  # typo
    # ── Candidato ──
    ("cuantos votos saco Keiko Fujimori",               "candidate"),
    ("Rafael Lopez Aliaga cuantos votos",               "candidate"),
    ("Lopez Aliaga cuantos votos",                      "candidate"),
    ("Keiko cuantos",                                   "candidate"),
    ("a ver cuantos votos tiene Forsyth",               "candidate"),
    ("cuantos votos obtuvo fujimori en lima",           "candidate"),
    ("cuantos votos tuvo Sanchez el del sombrero",      "candidate"),
    # ── Multi-candidato ──
    ("Aliaga vs Keiko en Cajamarca",                    "multi_candidate"),
    ("tanto Keiko como Aliaga cuantos votos",           "multi_candidate"),
    ("entre Aliaga Keiko y Urresti quien gano",         "multi_candidate"),
    ("Aliaga tuvo mas votos que Sagasti en Puno",       "multi_candidate"),
    # ── Nacional ──
    ("a nivel nacional quien gano",                     "nacional"),
    ("dame el resumen de resultados",                   "nacional"),
    ("segunda vuelta quien paso",                       "nacional"),
    ("quienes pasaron a segunda vuelta",                "nacional"),
    ("quien es el presidente electo",                   "nacional"),
    # ── Geo domestic ──
    ("top 3 en Loreto",                                 "geo_domestic"),
    ("resultados en Lima",                              "geo_domestic"),
    ("votos en Junin 2026",                             "geo_domestic"),
    # ── Geo extranjero ──
    ("top 3 candidatos en Suecia",                      "geo"),
    ("resultados en Estocolmo",                         "geo"),
    ("resultados en Canada",                            "geo"),
    # ── Legislativo ──
    ("senadores top 10 para Cuzco",                     "legislative_top_candidate"),
    ("diputados para Loreto",                           "legislative_top_candidate"),
    ("cuantos escanos gano Aliaga",                     "legislative_top_candidate"),
    # ── Range reasoning ──
    ("de las mesas que arrancan en 900000 quien fue primero Lopez Aliaga", "range_reasoning"),
    ("mesas de 900000 a 900999 quien fue primero",      "range_reasoning"),
    ("en las mesas 9001 quien fue primero",             "range_reasoning"),
    # ── Unknown ──
    ("cuanto cuesta el dolar hoy",                      "unknown"),
    ("va a llover en Lima manana",                      "unknown"),
    ("cuanto es 2 mas 2",                               "unknown"),
    ("como te llamas",                                  "unknown"),
    ("hay trafico en Lima",                             "unknown"),
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
