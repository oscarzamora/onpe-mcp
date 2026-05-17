"""Cycle 45 — variantes extremas: diálogos, referencias cruzadas, fragmentos incompletos."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato: interrogación al inicio
    ("¿cuantos votos tuvo Lopez Aliaga?",           "candidate"),
    # Geo domestic: con tildes correctas
    ("resultados en Áncash",                        "geo_domestic"),
    # Mesa: número 5 dígitos
    ("mesa 09876",                                  "mesa"),
    # Nacional: "votos validos totales"
    ("cuantos votos validos en total",              "nacional"),
    # Candidato: apodo coloquial "el pingüino"
    ("cuantos votos tuvo el pinguino",              "candidate"),
    # Geo: país con artículo
    ("resultados en la India",                      "geo"),
    # Multi: "cuantos mas votos tuvo A que B en C"
    ("cuantos mas votos tuvo Aliaga que Keiko en Lima", "multi_candidate"),
    # Unknown: pregunta filosófica
    ("que es el voto informado",                    "unknown"),
    # Candidato: nombre con "von" / partícula nobiliar
    ("cuantos votos obtuvo von Schultz",            "candidate"),
    # Legislativo: "representantes"
    ("representantes para Lambayeque",              "legislative_top_candidate"),
    # Nacional: "lista completa de partidos"
    ("lista completa de partidos",                  "nacional"),
    # Geo domestic: "resultados de las elecciones en Ica"
    ("resultados de las elecciones en Ica",         "geo_domestic"),
    # Candidato: reordenado "en Lima cuantos tuvo Forsyth"
    ("en Lima cuantos tuvo Forsyth",                "candidate"),
    # Mesa: número 1 dígito → muy corto, pero válido si hay "mesa"
    ("mesa 5",                                      "mesa"),
    # Unknown: solicitud de ayuda general
    ("ayuda",                                       "unknown"),
    # Nacional: "todos los resultados"
    ("todos los resultados",                        "nacional"),
    # Candidato: "a cuanto llegó X"
    ("a cuanto llego Aliaga en el conteo",          "candidate"),
    # Geo domestic: "como le fue a Lima"
    ("como le fue a Lima",                          "geo_domestic"),
    # Multi con comas: A, B, C
    ("votos de Aliaga, Keiko y Sagasti",            "multi_candidate"),
    # Unknown: pregunta sobre historia
    ("quien fue Pedro Castillo antes de ser presidente", "unknown"),
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
