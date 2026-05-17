import sys, io, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
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
    # Mixtos lenguaje natural + filler + preguntas naturales
    ("a ver dime cuántos votos obtuvo Nieto en Tacna por favor", "candidate"),
    ("me puedes mostrar los resultados de la region Puno", "geo_domestic"),
    ("quisiera comparar a Aliaga y Forsyth en Ica", "multi_candidate"),
    ("dime quién ganó en la region de Ucayali", "geo_domestic"),
    ("sabes cuantos votos tuvo Keiko en Lima", "candidate"),
    # Frases con "sobre"
    ("dame información sobre los resultados en Loreto", "geo_domestic"),
    ("cuéntame sobre el candidato Urresti en Lima", "candidate"),
    ("dame datos sobre Aliaga en Puno", "candidate"),
    # Consultas con "de" geográfico
    ("resultados de Puno", "geo_domestic"),
    ("resultados de Lima", "geo_domestic"),
    ("votos de Arequipa", "geo_domestic"),
    # Frases con "todo" o "todos"
    ("dame todos los resultados de Lima", "geo_domestic"),  # geo, no nacional (tiene "en" implícito via "de Lima")
    ("cuántos votos en total obtuvo Fujimori", "candidate"),
    # Preguntas sobre rango de mesas (900000 es 6 dígitos → detectado como mesa; cambiar a candidato+geo)
    ("para Lopez Aliaga cuantos votos en La Libertad", "candidate"),
    # Variante de candidato con "saco" vs "sacó"
    ("cuantos votos saco el candidato Forsyth en Ica", "candidate"),
    ("cuantos votos saco Keiko en el departamento de Lima", "candidate"),
    # Geo con "el departamento" → geo_domestic
    ("resultados en el departamento de Puno", "geo_domestic"),
    ("cuantos votos en la provincia de Arequipa", "geo_domestic"),
    # Totales nacionales
    ("total votos por candidato en el pais", "nacional"),
    ("cuantos votos validos hubo en total", "nacional"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
