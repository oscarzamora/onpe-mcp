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
    # Regresión ciclos anteriores (muestreo amplio)
    ("consulta mesa 900100", "mesa"),
    ("top 3 de candidatos en Suecia", "geo"),
    ("resultados en Estocolmo", "geo"),
    ("top 3 en Loreto", "geo_domestic"),
    ("senadores top 10 para Cuzco", "legislative_top_candidate"),
    ("cuántos votos obtuvo Rafael López Aliaga en primera vuelta", "candidate"),
    ("cuántos votos obtuvo nieto en arequipa", "candidate"),
    ("cuántos votos obtuvo Rafael López Aliaga y fujimori en iquitos", "multi_candidate"),
    ("en total cuantos votos validos hubo", "nacional"),
    ("cuantos candidatos participaron en las elecciones", "nacional"),
    # Nuevas: candidatos con frases completamente diferentes
    ("quien es el mejor posicionado en Lima", "geo_domestic"),  # "quien es" → geo
    ("dónde obtuvo más votos Aliaga", "candidate"),
    ("en qué región ganó Keiko", "geo"),  # "region" matchea en catálogo geo
    # Geo con puntuación
    ("¿Cuántos votos en Puno?", "geo_domestic"),
    ("¿Qué resultados tuvo Forsyth en Lima?", "candidate"),
    # Multi-candidato tácito
    ("Aliaga versus Keiko, ¿quién ganó?", "multi_candidate"),
    ("Fujimori contra Castillo cuantos votos tuvo cada uno", "multi_candidate"),
    # Candidato con apellido de lugar (prueba word-boundary)
    ("cuantos votos saco Ica Lopez en Lima", "candidate"),  # "Ica" en nombre
    # Nacional varios
    ("¿Cuántos votos válidos hubo en total en el país?", "nacional"),
    ("¿Qué candidato ganó las elecciones 2026?", "nacional"),
]
ok_count = sum(run(q, e) for q, e in tests)
print(f"\n{ok_count}/{len(tests)} PASS  {len(tests)-ok_count}/{len(tests)} FAIL")
