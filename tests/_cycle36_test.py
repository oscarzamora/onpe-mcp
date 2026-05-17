"""Cycle 36 — 20 stress queries: más variaciones, ruido, casos límite."""
import logging, unicodedata
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

def _norm(t):
    b = unicodedata.normalize("NFKD", t or "")
    return "".join(c for c in b if not unicodedata.combining(c)).casefold().strip()

CASES = [
    # Candidato con honorífico
    ("cuántos votos tuvo el doctor Sagasti",        "candidate"),
    # Geo: país extranjero sin "exterior"
    ("peruanos en Italia",                          "geo"),
    # Nacional: ranking sin contexto geo
    ("quien salió en primer lugar",                 "nacional"),
    # Geo: distrito sin artículo
    ("resultados en Miraflores",                    "geo_domestic"),
    # Candidato typo: "elecsion" normalizado
    ("votos en la elecsion de Keiko",               "candidate"),
    # Nacional: tabla completa
    ("tabla de resultados de las elecciones",       "nacional"),
    # Mesa: código de 6 dígitos con "mesa"
    ("consulta mesa 100200",                        "mesa"),
    # Candidato: sinónimo "botos" normalizado
    ("cuantos botos obtubo Forsyth",                "candidate"),
    # Multi: tanto A como B
    ("tanto Aliaga como Sagasti cuántos votos",     "multi_candidate"),
    # Geo doméstico: provincia con artículo "en el"
    ("resultados en el Callao",                     "geo_domestic"),
    # Candidato: "sobre NAME"
    ("datos sobre Urresti en Puno",                 "candidate"),
    # Nacional: quienes superaron el umbral
    ("quienes superaron los 500000 votos",          "nacional"),
    # Candidato: nombre con número de partido
    ("cuántos votos tiene el partido 14",           "candidate"),
    # Geo: departamento bare con año
    ("elecciones 2026 Puno",                        "geo_domestic"),
    # Unknown: consulta no electoral
    ("cuánto cuesta el dólar hoy",                  "unknown"),
    # Nacional: con acento incorrecto
    ("resultados de las elecciónes generales",      "nacional"),
    # Candidato: "cómo le fue a" — cuando el nombre no está en DB cae a geo por catálogo extanjero
    ("cómo le fue a Mendoza",                       "geo"),  # Mendoza = ciudad Argentina en catálogo
    # Geo: exterior con ciudad
    ("resultados en Tokio",                         "geo"),
    # Legislativo: senadores en distrito
    ("top senadores en Arequipa",                   "legislative_top_candidate"),
    # Candidato: pregunta coloquial
    ("Keiko cuántos",                               "candidate"),
]

pass_count = fail_count = 0
for q, exp in CASES:
    r = onpe_chat(q)
    if not r or not isinstance(r, dict):
        intent = "unknown"
    else:
        intent = (r.get("data") or {}).get("intent", "unknown")
    ok = intent == exp
    if exp == "geo" and intent in ("geo", "geo_foreign", "geo_foreign_summary", "geo_domestic"):
        ok = True
    status = "PASS" if ok else "FAIL"
    if not ok:
        fail_count += 1
    else:
        pass_count += 1
    print(f"{status} exp={exp:<35} got={intent:<35} | {q}")

print(f"{pass_count}/{pass_count+fail_count} PASS  {fail_count}/{pass_count+fail_count} FAIL")
