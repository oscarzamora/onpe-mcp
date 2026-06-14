import sys, io, logging
if __name__ == '__main__':  # encoding fix only for direct run, not pytest
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logging.disable(logging.CRITICAL)
from onpe_mcp.server import onpe_chat

def run(q, exp):
    r = onpe_chat(q)
    d = r.get("data") or {}
    intent = d.get("intent", "ERR") if d else (r.get("errors") or [{}])[0].get("code", "ERR")
    ok = intent == exp
    if not ok:
        ans = str(d.get("answer", "no-ans") if d else "no data")[:72]
        print(f"FAIL exp={exp:<26} got={intent:<26} | {q[:58]}")
        print(f"   {ans}")
    else:
        print(f"PASS exp={exp:<26} got={intent:<26} | {q[:58]}")
    return ok

tests = [
    # Candidato con "en" redundante o doble
    ("cuantos votos saco Keiko en Lima en la primera vuelta", "candidate"),
    ("cuantos votos recibio Nieto en Arequipa en primera vuelta", "candidate"),
    # Candidatos con "apodo" o referencia indirecta
    ("el del sombrero cuantos votos obtuvo en Lima", "candidate"),  # alias cultural → Sánchez
    ("la de los lentes cuantos votos saco en Puno", "candidate"),  # desconocido → candidate con not found
    # Geo con acento en nombre de distrito
    ("votos en Cañete", "geo_domestic"),
    ("resultados en Huaráz", "geo_domestic"),
    ("cuantos votos en Callao", "geo_domestic"),
    # Multi-candidato con 3 nombres
    ("Keiko Forsyth y Aliaga en Lima cuantos votos", "multi_candidate"),
    # Geo extranjero con ciudad compuesta
    ("resultados para peruanos en Nueva York", "geo"),
    ("cuantos votaron en Los Angeles", "geo"),
    # Nacional con "elecciones" word
    ("cuantos candidatos participaron en las elecciones", "nacional"),
    ("resumen de elecciones 2026", "nacional"),
    # Mesa con variantes
    ("información de la mesa electoral 900100", "mesa"),
    ("mesa electoral 050101", "mesa"),
    # "Lima" es un geo name → cuando se usa como candidato, el sistema lo ruta a geo
    ("cuantos votos saco Lima en Tacna", "geo_domestic"),   # Lima es geo primero
    ("resultados de Lima en Arequipa", "geo_domestic"),      # Lima → geo scope, Arequipa → geo
    # Geo con "el"
    ("resultados en el Callao", "geo_domestic"),
    # Ambigua: solo candidato sin geo
    ("votos de Aliaga", "candidate"),
    ("resultados de Fujimori", "candidate"),
    # Regresión: "en" al inicio + candidatos + geo → geo_domestic
    ("en Arequipa que candidatos sacaron mas votos", "geo_domestic"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
