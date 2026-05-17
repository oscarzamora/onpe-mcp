"""Cycle 35 — 20 stress-test queries: edge cases geo, candidato, nacional, multi, mesa."""
import logging, sys, unicodedata
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

def _norm(t):
    b = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in b if not unicodedata.combining(c)).casefold().strip()

CASES = [
    # Geo doméstico sin preposición
    ("resultados Arequipa 2026",           "geo_domestic"),
    # Nacional: año + país explícito
    ("elecciones 2026 a nivel del peru",   "nacional"),
    # Nacional: todos los candidatos
    ("muéstrame a todos los candidatos",   "nacional"),
    # Geo doméstico: distrito con artículo
    ("top 5 en La Molina",                 "geo_domestic"),
    # Candidato: patrón invertido "le fue a NAME"
    ("cómo le fue a Urresti en Lima",      "candidate"),
    # Candidato: "cómo quedó NAME en GEO"
    ("cómo quedó Aliaga en Cajamarca",     "candidate"),
    # Nacional: votos nulos sin geo
    ("cuántos votos nulos hubo",           "nacional"),
    # Geo domestic: votos nulos con lugar
    ("cuántos votos nulos hubo en Puno",   "geo_domestic"),
    # Multi-candidato: comparación directa
    ("Keiko vs Aliaga cuántos votos",      "multi_candidate"),
    # Nacional: distribución
    ("distribución de votos entre candidatos", "nacional"),
    # Candidato: partido como nombre de candidato
    ("cuántos votos tuvo el Partido Morado", "candidate"),
    # Geo: bare dept name con contexto electoral
    ("resultados Loreto",                  "geo_domestic"),
    # Unknown: pregunta sin sentido electoral
    ("quién ganó el mundial",              "unknown"),
    # Nacional: primera vuelta sin lugar
    ("resultados de la primera vuelta",    "nacional"),
    # Geo domestic: primera vuelta con lugar
    ("primera vuelta en Junín",            "geo_domestic"),
    # Candidato: typo b→v
    ("cuantos botos tubo Lopez Aliaga",    "candidate"),
    # Multi-candidato: mas votos que
    ("Fujimori tuvo más votos que Mendoza en Arequipa", "multi_candidate"),
    # Nacional: listado completo
    ("dame el listado completo",           "nacional"),
    # Candidato: "para NAME cuantos votos en GEO"
    ("para Urresti cuántos votos en Callao", "candidate"),
    # Geo foreign: país extranjero
    ("resultados de peruanos en España",   "geo"),
]

pass_count = fail_count = 0
for q, exp in CASES:
    r = onpe_chat(q)
    intent = r.get("data", {}).get("intent", "unknown") if isinstance(r, dict) else "error"
    if intent == "geo_domestic": intent = "geo_domestic"
    elif intent == "geo": intent = "geo"
    ok = (intent == exp) or (exp == "geo" and intent in ("geo", "geo_foreign", "geo_foreign_summary", "geo_domestic"))
    # Normalizar geo aliases
    if exp == "geo" and intent in ("geo", "geo_foreign", "geo_foreign_summary"):
        ok = True
    status = "PASS" if ok else "FAIL"
    if not ok:
        fail_count += 1
        print(f"{status} exp={exp:<30} got={intent:<30} | {q}")
    else:
        pass_count += 1
        print(f"{status} exp={exp:<30} got={intent:<30} | {q}")

print(f"{pass_count}/{pass_count+fail_count} PASS  {fail_count}/{pass_count+fail_count} FAIL")
