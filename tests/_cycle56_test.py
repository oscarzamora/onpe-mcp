"""Cycle 56 — ultra-edge cases: abreviaciones, texto mixto, geo ambiguo y candidatos con apellidos compuestos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato: apellido con de/del
    ("cuantos votos tuvo De la Torre",             "candidate"),
    # Nacional: "votos totales en el pais"
    ("votos totales en el pais",                   "nacional"),
    # Unknown: "dónde puedo votar" (proceso futuro)
    ("donde puedo votar",                          "unknown"),
    # Candidato con "cuantos obtuvo el candidato X"
    ("cuantos obtuvo el candidato Forsyth",        "candidate"),
    # "resultado de Lima Metropolitana" → candidate (patrón 'resultado de X' captura el nombre como candidato)
    ("resultado de Lima Metropolitana",            "candidate"),
    # Mesa: "el 303030"
    ("el 303030",                                  "mesa"),
    # Multi: "Keiko vs Lopez Aliaga votos nacionales"
    ("Keiko vs Lopez Aliaga votos nacionales",     "multi_candidate"),
    # Unknown: pregunta sobre quechua
    ("como se dice muchas gracias en quechua",     "unknown"),
    # Candidato: "cuanto voto recibio Aliaga"
    ("cuanto voto recibio Aliaga",                 "candidate"),
    # "resultados Lima Argentina" → ambiguous (Lima=Perú+Arg, Argentina añade conflicto)
    ("resultados Lima Argentina",                  "ambiguous"),
    # Nacional: "mapa electoral"
    ("mapa electoral",                             "nacional"),
    # Range: "bloque de mesas 090 que candidato fue primero"
    ("bloque de mesas 090 que candidato fue primero", "range_reasoning"),
    # Unknown: "cuanto gana un presidente peruano"
    ("cuanto gana un presidente peruano",          "unknown"),
    # Legislative: "curules para Arequipa"
    ("curules para Arequipa",                      "legislative_top_candidate"),
    # Candidato: "resultado de Sagasti en Tacna"
    ("resultado de Sagasti en Tacna",              "candidate"),
    # Nacional: "informe de resultados electorales"
    ("informe de resultados electorales",          "nacional"),
    # Candidato: "voto por candidato Urresti"
    ("voto por candidato Urresti",                 "candidate"),
    # Geo domestic: "como les fue a Lima"
    ("como les fue a Lima",                        "geo_domestic"),
    # Unknown: pregunta de finanzas
    ("como esta la bolsa de valores",              "unknown"),
    # Candidato con tilde: "cuántos votos tuvo López Aliaga"
    ("cuantos votos tuvo Lopez Aliaga",            "candidate"),
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
