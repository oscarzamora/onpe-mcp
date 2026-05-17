"""Cycle 46 — ruido ortográfico, mayúsculas, signos y estructuras inusuales."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Todo en mayúsculas
    ("CUANTOS VOTOS TUVO ALIAGA",                   "candidate"),
    # Mix mayúsculas/minúsculas
    ("CuAnToS VoToS sAcO KeIkO",                   "candidate"),
    # Con signos de exclamación múltiples
    ("cuantos votos!!! obtuvo Sagasti!!!",          "candidate"),
    # Puntos al final
    ("resultados en Cusco.",                        "geo_domestic"),
    # Asteriscos (formato markdown)
    ("**top 5** en Loreto",                         "geo_domestic"),
    # Números escritos como palabras
    ("top cinco en Lima",                           "geo_domestic"),
    # "el candidato X"
    ("cuantos votos tuvo el candidato Aliaga",      "candidate"),
    # Abreviatura partido FP
    ("FP en Arequipa",                              "geo_domestic"),
    # Candidato con "Dr."
    ("cuantos votos saco Dr. Aliaga",               "candidate"),
    # Símbolo % en la pregunta
    ("que % de votos tuvo Sagasti",                 "candidate"),
    # Geo: continente Asia — RENIEC tiene distrito "Asia" → geo_domestic
    ("peruanos en Asia",                            "geo_domestic"),
    # Legislativo plural
    ("cuantos senadores le corresponden a Junin",   "legislative_top_candidate"),
    # Mesa con prefijo "la mesa"
    ("la mesa 100200",                              "mesa"),
    # Multi con "versus"
    ("Aliaga versus Keiko votos",                   "multi_candidate"),
    # Candidato: "datos de X"
    ("datos de Rafael Lopez Aliaga",                "candidate"),
    # Geo: "que tal le fue en"
    ("que tal le fue en Tacna",                     "geo_domestic"),
    # Nacional con "primer lugar"
    ("quien quedo en primer lugar",                 "nacional"),
    # Candidato con "cuál fue el resultado de X"
    ("cual fue el resultado de Keiko",              "candidate"),
    # Unknown: otra elección (2021)
    ("resultados de las elecciones de 2021",        "unknown"),
    # Geo domestic: "elecciones 2026 en Puno"
    ("elecciones 2026 en Puno",                     "geo_domestic"),
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
