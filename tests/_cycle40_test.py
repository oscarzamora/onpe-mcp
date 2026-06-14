"""Cycle 40 — variantes lingüísticas, acortamientos, casos límite."""
import logging, os
logging.disable(logging.CRITICAL)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from onpe_mcp.server import onpe_chat

def run(q):
    r = onpe_chat(q) or {}
    return (r.get("data") or {}).get("intent", "N/A")

CASES = [
    # Candidato por apodo conocido
    ("cuantos votos tuvo la keiko",                "candidate"),
    # Candidato por apodo desconocido → candidate (no encontrado en DB)
    ("cuantos votos tuvo el flaco",                "candidate"),
    # "el norte" → geo (RENIEC/foreign catalog tiene "Norte" como ubicacion)
    ("resultados en el norte",                     "geo"),
    # Nacional: "qué pasó en las elecciones"
    ("que paso en las elecciones",                 "nacional"),
    # Legislativo: escaños
    ("cuantos escanos gano Aliaga",                "legislative_top_candidate"),
    # Candidato: pregunta con partícula "a ver"
    ("a ver cuantos votos tiene Forsyth",          "candidate"),
    # Multi con "tanto A como B"
    ("tanto Keiko como Aliaga cuantos votos",      "multi_candidate"),
    # Geo domestic: "resultados cusco" sin preposición
    ("resultados cusco",                           "geo_domestic"),
    # Candidato: "votos del candidato X"
    ("votos del candidato Boluarte",               "candidate"),
    # Nacional: "todos los candidatos"
    ("todos los candidatos cuantos votos",         "nacional"),
    # Geo foreign: ciudad con acento
    ("resultados en São Paulo",                    "geo"),
    # Candidato typo: "fujimori" → candidate
    ("cuantos votos obtuvo fujimori en lima",      "candidate"),
    # Mesa: número con "número de mesa"
    ("número de mesa 030405",                      "mesa"),
    # Nacional: "quiénes pasaron a segunda"
    ("quienes pasaron a segunda vuelta",           "nacional"),
    # Candidato con "de partido"
    ("votos de fuerza popular en Arequipa",        "candidate"),
    # Geo: solo nombre de país extranjero
    ("resultados en Canada",                       "geo"),
    # Unknown: consulta completamente irrelevante
    ("cuanto es 2 mas 2",                          "unknown"),
    # Range con "de X a Y" texto
    ("mesas de 900000 a 900999 quien fue primero", "range_reasoning"),
    # Candidato: "el ingeniero X"
    ("cuantos votos tuvo el ingeniero Aliaga",     "candidate"),
    # "en esta parte" → sin ubicación específica → unknown
    ("en esta parte cuantos votos",                "unknown"),
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
