"""Cycle 49 — fragmentos incompletos, consultas mixtas y más variantes."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Fragmento incompleto con candidato
    ("votos de",                                   "unknown"),
    # Solo número 6 dígitos sin "mesa" → late fallback lo trata como mesa (correcto)
    ("900100",                                     "mesa"),
    # Candidato: "cuantos tuvo Aliaga en total"
    ("cuantos tuvo Aliaga en total",               "candidate"),
    # Geo domestic: "que tal ica"
    ("que tal ica",                                "geo_domestic"),
    # Multi: "Keiko vs Aliaga en primera vuelta"
    ("Keiko vs Aliaga en primera vuelta",          "multi_candidate"),
    # Range: "mesas del 900000 al 900999"
    ("mesas del 900000 al 900999",                 "range_reasoning"),
    # Nacional: "cuantos acudieron a votar"
    ("cuantos acudieron a votar",                  "nacional"),
    # Candidato: "resultado electoral de Sagasti"
    ("resultado electoral de Sagasti",             "candidate"),
    # Geo: "como les fue a los peruanos en Francia"
    ("como les fue a los peruanos en Francia",     "geo"),
    # Unknown: pregunta de cultura general
    ("cuanto mide el obelisco de Washington",      "unknown"),
    # Mesa: guión entre números
    ("mesa 090-100",                               "mesa"),
    # Nacional: "todos los votos contados"
    ("todos los votos contados",                   "nacional"),
    # Candidato con "su" (pronombre posesivo)
    ("cuantos fueron sus votos de Forsyth",        "candidate"),
    # Geo domestic: "informacion de Ucayali"
    ("informacion de Ucayali",                     "geo_domestic"),
    # Legislative: "senadores para Lambayeque"
    ("senadores para Lambayeque",                  "legislative_top_candidate"),
    # Unknown: pregunta sobre proceso electoral
    ("cuando fueron las elecciones peruanas",      "nacional"),
    # Candidato: "que tanto apoyo tuvo Aliaga"
    ("que tanto apoyo tuvo Aliaga",                "candidate"),
    # Geo: "resultados para Chile"
    ("resultados para Chile",                      "geo"),
    # Multi: "A, B y C en Lima quienes"
    ("Aliaga, Sagasti y Keiko en Lima quienes",    "multi_candidate"),
    # Unknown: pregunta filosófica electoral
    ("para que sirve votar",                       "unknown"),
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
